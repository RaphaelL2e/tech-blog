---
title: Kubernetes自定义调度器实战：从框架扩展到生产落地
date: 2026-08-21 10:00:00+08:00
updated: '2026-08-21T10:00:00+08:00'
description: '标准调度器满足不了你的场景？GPU集群如何让AI训练任务优先调度到有闲置卡片的节点？在线服务如何与离线批处理任务共享集群而不互相干扰？本文从调度框架扩展点出发，手把手带你写一个自定义调度器，从Demo到生产级改造，涵盖多调度器共存、调度策略注入、高可用与灰度切换，一次性打通自定义调度的全链路。'
topic: devops-cloud
level: advanced
status: maintained
tags:
- Kubernetes
- 调度器
- 自定义调度器
- Scheduler Framework
- 云原生
- 容器编排
- GPU调度
- 资源管理
categories:
- 云原生与 DevOps
draft: false
author: 飞哥
---

> 标准调度器满足不了你的场景？GPU集群如何让AI训练任务优先调度到有闲置卡片的节点？在线服务如何与离线批处理任务共享集群而不互相干扰？本文从调度框架扩展点出发，手把手带你写一个自定义调度器，从Demo到生产级改造，涵盖多调度器共存、调度策略注入、高可用与灰度切换，一次性打通自定义调度的全链路。

## 一、什么时候需要自定义调度器

在深入代码之前，先回答一个根本问题：什么时候该走自定义调度这条路？

Kubernetes默认调度器（kube-scheduler）已经很强大了——它支持基于资源用量的亲和性/反亲和性、污点容忍、拓扑分布约束……但现实场景往往有更细腻的诉求：

**典型强需求场景：**

1. **异构资源调度**：GPU、TPU、FPGA等 accelerator 资源。默认调度器只知道"有没有 CPU 和内存"，它不知道节点上哪块 GPU 空闲、哪块卡的显存更大。
2. **业务感知调度**：比如在线服务要求低延迟，希望调度到离数据库近的节点；批处理任务只要求吞吐，可以容忍稍长启动时间。
3. **多租户与配额控制**：在共享集群中，不同租户有不同优先级，需要保证关键业务的调度权重。
4. **Bin-packing vs Spread 的精细控制**：默认提供两种策略，但实际业务可能需要更复杂的资源分配模式。
5. **调度延迟敏感场景**：超大规模集群（1000+节点），默认调度器可能成为瓶颈，需要定向优化调度路径。

如果你遇到了以上场景，且现有的亲和性规则、优先级配置无法满足，自定义调度器就是答案。

> 💡 **前置阅读**：如果对调度器基础概念不熟悉，建议先阅读 [Kubernetes调度器核心原理：Pod是如何被安排到节点的](/posts/kubernetes-scheduler-principles/)。

<!--more-->

## 二、调度框架（Scheduler Framework）概览

从 Kubernetes 1.19 开始，官方推荐使用 **Scheduler Framework**（调度框架）来扩展调度器，而不是早期版本的 **scheduler-extender**（调度器扩展 Webhook）。Framework 的优势在于：

- 扩展点（Extension Points）清晰，插件化架构
- 与调度器核心在同一进程运行，性能更好
- 支持动态注册插件，无需修改调度器代码
- 完整的测试框架支持

调度器的工作流程分为多个阶段（Phases），每个阶段可以插入自定义插件：

```
QueueSort → PreFilter → Filter → PostFilter → 
PreScore → Scoring → Reserve → Permit → 
Bind → PostBind
```

**各阶段含义：**

| 阶段 | 作用 | 可否自定义 |
|------|------|----------|
| QueueSort | 决定待调度Pod的排序顺序 | ✅ |
| PreFilter | 预处理，检查节点是否满足前置条件 | ✅ |
| Filter | 过滤不符合条件的节点 | ✅ |
| PostFilter | Filter阶段后的补救，如抢占 | ✅ |
| PreScore | 预打分，准备评分数据 | ✅ |
| Scoring | 为通过的节点打分 | ✅ |
| Reserve | 预留资源，锁定节点 | ✅ |
| Permit | 审批通过/拒绝/等待 | ✅ |
| Bind | 将Pod绑定到节点 | ✅ |
| PostBind | 绑定后的清理动作 | ✅ |

自定义调度器有两种主流写法：
1. **Scheduler Framework 插件**：编译成 Go 插件，注入到 kube-scheduler 进程
2. **独立调度器**：另起一个进程，通过 Pod 的 `.spec.schedulerName` 指定

本文采用**方案2（独立调度器）**讲解，因为它的门槛最低、演示最直观，且与 Framework 插件的原理完全相通。

## 三、从零写一个独立自定义调度器

### 3.1 架构设计

我们的目标：写一个调度器，能够根据节点上的**GPU可用数量**和**GPU型号**来调度 AI 训练任务。

```
┌─────────────────────────────────────┐
│         Kubernetes API Server       │
└──────────────┬──────────────────────┘
               │ Watch / List
┌──────────────▼──────────────────────┐
│         Custom Scheduler            │
│  ┌─────────────────────────────┐   │
│  │ 调度队列 (Pending Pods)       │   │
│  │ 调度决策 (Filter+Score)       │   │
│  │ 绑定执行 (Bind to Node)       │   │
│  └─────────────────────────────┘   │
└────────────────────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  Nodes with GPU Labels              │
│  node-A: nvidia.com/gpu-count=4    │
│          nvidia.com/gpu-model=A100  │
│  node-B: nvidia.com/gpu-count=8    │
│          nvidia.com/gpu-model=V100  │
└─────────────────────────────────────┘
```

### 3.2 核心代码实现

创建一个 Go 项目（最小化依赖，不引入重型框架）：

```
gpu-scheduler/
├── main.go
├── scheduler/
│   ├── scheduler.go
│   ├── filter.go
│   ├── score.go
│   └── bind.go
└── go.mod
```

**go.mod：**

```go
module gpu-scheduler

go 1.21

require (
    k8s.io/api v0.29.0
    k8s.io/apimachinery v0.29.0
    k8s.io/client-go v0.29.0
    k8s.io/klog/v2 v2.120.1
)
```

**main.go：**

```go
package main

import (
    "context"
    "flag"
    "fmt"
    "time"

    corev1 "k8s.io/api/core/v1"
    "k8s.io/apimachinery/pkg/labels"
    "k8s.io/apimachinery/pkg/runtime"
    "k8s.io/client-go/informers"
    "k8s.io/client-go/kubernetes"
    "k8s.io/client-go/tools/cache"
    "k8s.io/client-go/tools/clientcmd"
    "k8s.io/klog/v2"

    "gpu-scheduler/scheduler"
)

var (
    kubeconfig   = flag.String("kubeconfig", "", "Path to kubeconfig file")
    masterURL    = flag.String("master", "", "Kubernetes API server address")
    schedulerName = flag.String("scheduler-name", "gpu-scheduler", "Scheduler name")
)

func main() {
    klog.InitFlags(nil)
    flag.Parse()

    cfg, err := clientcmd.BuildConfigFromFlags(*masterURL, *kubeconfig)
    if err != nil {
        klog.Fatalf("Failed to build config: %v", err)
    }

    clientset, err := kubernetes.NewForConfig(cfg)
    if err != nil {
        klog.Fatalf("Failed to create clientset: %v", err)
    }

    // 创建调度器实例
    sched := scheduler.NewScheduler(clientset, *schedulerName)

    // 启动 SharedInformer，监听 Pod 和 Node 变化
    informersFactory := informers.NewSharedInformerFactory(clientset, 0)
    podInformer := informersFactory.Core().V1().Pods()
    nodeInformer := informersFactory.Core().V1().Nodes()

    // 注册事件处理
    podInformer.Informer().AddEventHandler(cache.FilteringResourceEventHandler{
        FilterFunc: func(obj interface{}) bool {
            pod, ok := obj.(*corev1.Pod)
            if !ok {
                return false
            }
            // 只处理我们调度器负责的、且处于Pending状态的Pod
            return pod.Spec.SchedulerName == *schedulerName &&
                   pod.DeletionTimestamp == nil &&
                   pod.Status.Phase == corev1.PodPending
        },
        Handler: cache.ResourceEventHandlerFuncs{
            AddFunc: func(obj interface{}) {
                pod := obj.(*corev1.Pod)
                klog.Infof("[%s] Pod added: %s/%s", *schedulerName, pod.Namespace, pod.Name)
                go sched.ScheduleOne(pod)
            },
        },
    })

    // 启动 informers
    stopCh := make(chan struct{})
    informersFactory.Start(stopCh)
    informersFactory.WaitForCacheSync(stopCh)

    klog.Infof("GPU Scheduler %s is running...", *schedulerName)
    <-stopCh
}
```

**scheduler.go — 调度主流程：**

```go
package scheduler

import (
    "context"
    "fmt"

    corev1 "k8s.io/api/core/v1"
    "k8s.io/client-go/kubernetes"
    "k8s.io/klog/v2"
)

type Scheduler struct {
    clientset     *kubernetes.Clientset
    schedulerName string
}

func NewScheduler(clientset *kubernetes.Clientset, name string) *Scheduler {
    return &Scheduler{
        clientset:     clientset,
        schedulerName: name,
    }
}

// ScheduleOne 对单个Pod执行完整调度流程
func (s *Scheduler) ScheduleOne(pod *corev1.Pod) {
    ctx := context.Background()

    klog.Infof("Scheduling pod %s/%s", pod.Namespace, pod.Name)

    // Step 1: 获取所有候选节点
    nodes, err := s.listNodes()
    if err != nil {
        klog.Errorf("Failed to list nodes: %v", err)
        return
    }

    // Step 2: Filter — 过滤不符合条件的节点
    candidateNodes := s.filterNodes(pod, nodes)
    if len(candidateNodes) == 0 {
        klog.Warnf("No suitable nodes for pod %s/%s", pod.Namespace, pod.Name)
        return
    }

    // Step 3: Score — 对候选节点打分
    bestNode := s.scoreNodes(pod, candidateNodes)

    // Step 4: Bind — 绑定到最优节点
    err = s.bindPod(ctx, pod, bestNode)
    if err != nil {
        klog.Errorf("Failed to bind pod %s/%s to node %s: %v",
            pod.Namespace, pod.Name, bestNode.Name, err)
        return
    }

    klog.Infof("Pod %s/%s scheduled to node %s", pod.Namespace, pod.Name, bestNode.Name)
}

func (s *Scheduler) listNodes() ([]*corev1.Node, error) {
    // ... 见下一节 filter.go
}

func (s *Scheduler) filterNodes(pod *corev1.Pod, nodes []*corev1.Node) []*corev1.Node {
    // ... 见下一节
}

func (s *Scheduler) scoreNodes(pod *corev1.Pod, nodes []*corev1.Node) *corev1.Node {
    // ... 见下一节
}

func (s *Scheduler) bindPod(ctx context.Context, pod *corev1.Pod, node *corev1.Node) error {
    // ... 见下一节
}
```

### 3.3 Filter 阶段 — 节点过滤逻辑

这是调度器的核心决策层。我们的策略是：

- 如果 Pod 申请了 GPU（通过 `nvidia.com/gpu` Resource Request），只调度到有 GPU 标签的节点
- 检查节点上 GPU 是否足够
- 检查节点是否 Ready

```go
package scheduler

import (
    "strconv"

    corev1 "k8s.io/api/core/v1"
    "k8s.io/apimachinery/pkg/api/resource"
)

const (
    LabelGPUCount  = "nvidia.com/gpu-count"
    LabelGPUModel  = "nvidia.com/gpu-model"
    ResourceGPU    = "nvidia.com/gpu"
)

func (s *Scheduler) filterNodes(pod *corev1.Pod, nodes []*corev1.Node) []*corev1.Node {
    // 计算Pod需要的GPU数量
    requiredGPU := getRequiredGPU(pod)
    klog.V(3).Infof("Pod requires %d GPUs", requiredGPU)

    var candidates []*corev1.Node
    for _, node := range nodes {
        // 检查节点是否 Ready
        if !isNodeReady(node) {
            klog.V(4).Infof("Node %s is not Ready, skip", node.Name)
            continue
        }

        // 如果Pod不需要GPU，则不过滤任何节点
        if requiredGPU == 0 {
            candidates = append(candidates, node)
            continue
        }

        // 检查GPU标签
        gpuCountStr, ok := node.Labels[LabelGPUCount]
        if !ok {
            klog.V(4).Infof("Node %s has no GPU label, skip", node.Name)
            continue
        }

        gpuCount, err := strconv.Atoi(gpuCountStr)
        if err != nil || gpuCount < requiredGPU {
            klog.V(4).Infof("Node %s has insufficient GPU (%d < %d), skip",
                node.Name, gpuCount, requiredGPU)
            continue
        }

        // 检查GPU是否被其他Pod占用
        allocatedGPU := s.getAllocatedGPU(node)
        availableGPU := gpuCount - allocatedGPU
        if availableGPU < requiredGPU {
            klog.V(4).Infof("Node %s has %d available GPU, need %d, skip",
                node.Name, availableGPU, requiredGPU)
            continue
        }

        candidates = append(candidates, node)
    }

    return candidates
}

// getRequiredGPU 从 Pod 的 Resource Requests 中获取 GPU 需求
func getRequiredGPU(pod *corev1.Pod) int {
    var gpuQty resource.Quantity
    for _, container := range pod.Spec.Containers {
        if q, ok := container.Resources.Requests[corev1.ResourceName(ResourceGPU)]; ok {
            gpuQty.Add(q)
        }
    }
    return int(gpuQty.Value())
}

func (s *Scheduler) getAllocatedGPU(node *corev1.Node) int {
    // 这里需要查询当前节点上已调度的 Pod 数量
    // 简化版：直接读节点的 annotaiton 或通过 clientset 列出所有 Pod
    pods, err := s.clientset.CoreV1().Pods("").List(context.TODO(),
        metav1.ListOptions{FieldSelector: "spec.nodeName="+node.Name})
    if err != nil {
        return 0
    }

    var allocated int
    for _, pod := range pods.Items {
        // 排除已终止的Pod
        if pod.Status.Phase == corev1.PodSucceeded || pod.Status.Phase == corev1.PodFailed {
            continue
        }
        for _, container := range pod.Spec.Containers {
            if q, ok := container.Resources.Requests[corev1.ResourceName(ResourceGPU)]; ok {
                allocated += int(q.Value())
            }
        }
    }
    return allocated
}

func isNodeReady(node *corev1.Node) bool {
    for _, condition := range node.Status.Conditions {
        if condition.Type == corev1.NodeReady {
            return condition.Status == corev1.ConditionTrue
        }
    }
    return false
}
```

### 3.4 Score 阶段 — 节点打分策略

过滤后的节点可能不止一个，需要打分选出最优节点。我们的打分策略：

- `nvidia.com/gpu-model` 优先：Tesla A100 > A10 > V100 > T4
- 资源利用率均衡：优先选择 GPU 空闲率更高的节点（Spread 而非 Bin-packing）
- 打分范围：0-100，归一化处理

```go
package scheduler

var gpuModelPriority = map[string]int{
    "A100":  100,
    "A10":   80,
    "V100":  60,
    "T4":    40,
    "P100":  20,
}

func (s *Scheduler) scoreNodes(pod *corev1.Pod, nodes []*corev1.Node) *corev1.Node {
    type nodeScore struct {
        node  *corev1.Node
        score int64
    }

    scores := make([]nodeScore, 0, len(nodes))

    for _, node := range nodes {
        var totalScore int64

        // 因素1: GPU型号优先级（权重 60%）
        if model, ok := node.Labels[LabelGPUModel]; ok {
            if priority, ok := gpuModelPriority[model]; ok {
                totalScore += int64(priority * 60 / 100 * 100) // 归一化
            }
        }

        // 因素2: GPU可用率（权重 40%）
        // 可用率 = (总GPU - 已占用GPU) / 总GPU
        gpuCountStr := node.Labels[LabelGPUCount]
        gpuCount, _ := strconv.Atoi(gpuCountStr)
        allocated := s.getAllocatedGPU(node)
        if gpuCount > 0 {
            utilization := float64(gpuCount-allocated) / float64(gpuCount)
            totalScore += int64(float64(100) * utilization * 0.4 * 100)
        }

        scores = append(scores, nodeScore{node: node, score: totalScore})
    }

    // 选出最高分节点
    var best nodeScore
    for _, ns := range scores {
        if ns.score > best.score {
            best = ns
        }
    }

    klog.V(2).Infof("Selected node %s with score %d (candidates: %d)",
        best.node.Name, best.score, len(scores))
    return best.node
}
```

### 3.5 Bind 阶段 — 绑定 Pod 到节点

```go
package scheduler

import (
    "context"

    corev1 "k8s.io/api/core/v1"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
    "k8s.io/apimachinery/pkg/types"
)

func (s *Scheduler) bindPod(ctx context.Context, pod *corev1.Pod, node *corev1.Node) error {
    // 通过 Patch 更新 Pod 的 nodeName 字段
    binding := &corev1.Binding{
        ObjectMeta: metav1.ObjectMeta{
            Name:      pod.Name,
            Namespace: pod.Namespace,
            UID:       pod.UID,
        },
        Target: corev1.ObjectReference{
            Kind: "Node",
            Name: node.Name,
        },
    }

    return s.clientset.CoreV1().Pods(pod.Namespace).Bind(ctx, binding, metav1.CreateOptions{})
}
```

### 3.6 部署自定义调度器

将调度器打包成 Deployment，与 kube-scheduler **共存**：

```yaml
# gpu-scheduler.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gpu-scheduler
  namespace: kube-system
  labels:
    app: gpu-scheduler
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gpu-scheduler
  template:
    metadata:
      labels:
        app: gpu-scheduler
    spec:
      serviceAccountName: gpu-scheduler
      containers:
        - name: gpu-scheduler
          image: your-registry/gpu-scheduler:v1.0
          args:
            - --kubeconfig=/etc/kubernetes/kubeconfig
            - --scheduler-name=gpu-scheduler
          volumeMounts:
            - name: kubeconfig
              mountPath: /etc/kubernetes
              readOnly: true
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
      volumes:
        - name: kubeconfig
          hostPath:
            path: /etc/kubernetes/admin.conf
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: gpu-scheduler
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: gpu-scheduler
rules:
  - apiGroups: [""]
    resources: ["pods", "nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/binding"]
    verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: gpu-scheduler
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: gpu-scheduler
subjects:
  - kind: ServiceAccount
    name: gpu-scheduler
    namespace: kube-system
```

### 3.7 让 Pod 使用自定义调度器

在 Pod 的 `spec.schedulerName` 中指定：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: training-job
spec:
  schedulerName: gpu-scheduler    # ← 指定使用自定义调度器
  containers:
    - name: trainer
      image: pytorch-training:v1.0
      resources:
        requests:
          nvidia.com/gpu: "2"
        limits:
          nvidia.com/gpu: "2"
```

## 四、生产级改造：从 Demo 到企业级调度器

上面的 Demo 调度器能跑，但离生产级还有距离。以下是关键改造点：

### 4.1 调度队列与失败重试

Demo 中 Pod Add 时直接调度，如果彼时没有合适节点，Pod 就被错过了。

生产级调度器需要维护自己的**调度队列**，并定期重试 Pending 的 Pod：

```go
type SchedulingQueue struct {
    lock    sync.Mutex
    pending []*v1.Pod
}

func (q *SchedulingQueue) Add(pod *v1.Pod) {
    q.lock.Lock()
    defer q.lock.Unlock()
    // 避免重复入队
    for _, p := range q.pending {
        if p.UID == pod.UID {
            return
        }
    }
    q.pending = append(q.pending, pod)
}

// 定期重试调度
func (s *Scheduler) runSchedulingLoop(ctx context.Context) {
    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            // 扫描所有Pending状态的Pod，重新调度
            pods, _ := s.clientset.CoreV1().Pods("").List(ctx, metav1.ListOptions{
                FieldSelector: "spec.schedulerName=" + s.schedulerName,
            })
            for _, pod := range pods.Items {
                if pod.Status.Phase == v1.PodPending {
                    go s.ScheduleOne(&pod)
                }
            }
        }
    }
}
```

### 4.2 调度器高可用：主备切换

独立调度器的风险是单点故障。生产环境需要多副本 + leader election：

```go
import (
    "k8s.io/client-go/tools/leaderelection"
    "k8s.io/client-go/tools/leaderelection/resourcelock"
)

func runWithLeaderElection(ctx context.Context, runFunc func(context.Context)) {
    lock := &resourcelock.ConfigMapLock{
        ConfigMapMeta: metav1.ObjectMeta{
            Name:      "gpu-scheduler-leader",
            Namespace: "kube-system",
        },
        ClientConfig: clientset.CoreV1().RESTClient(),
    }

    leaderelection.RunOrDie(ctx, leaderelection.LeaderElectionConfig{
        Lock:            lock,
        LeaseDuration:   15 * time.Second,
        RenewDeadline:   10 * time.Second,
        RetryPeriod:     5 * time.Second,
        ReleaseOnCancel: true,
        LeaderElect:     true,
        LeaderElectionCallbacks: leaderelection.LeaderCallbacks{
            OnStartedLeading: func(ctx context.Context) {
                klog.Info("Won leadership, starting scheduler")
                runFunc(ctx)
            },
            OnStoppedLeading: func() {
                klog.Info("Lost leadership, stopping scheduler")
            },
        },
    })
}
```

### 4.3 与默认调度器混合调度

生产中往往需要两个调度器共存——默认调度器处理普通服务，自定义调度器处理特殊任务。

配置多个调度器有两种推荐方式：

**方式一：Pod 级指定（推荐）：**
```yaml
# 普通服务 → 默认调度器（不需要指定，默认就是 default-scheduler）
spec:
  containers:
    - name: web
      image: nginx:1.25

# AI训练任务 → GPU调度器
spec:
  schedulerName: gpu-scheduler
  containers:
    - name: trainer
      image: pytorch:v2.0
```

**方式二：Node 亲和性配合：**
```yaml
# 为有GPU的节点打上标签
kubectl label node node-gpu-1 nvidia.com/gpu-model=A100
kubectl label node node-gpu-1 gpu-capable=true

# 通过节点亲和性，让特定Pod只调度到GPU节点
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: gpu-capable
                operator: Exists
```

### 4.4 调度策略热更新

生产环境调度策略可能需要频繁调整（比如促销期间临时提升批处理任务优先级），不想每次改代码都要重新部署镜像。

解决方案：**将调度策略写入 ConfigMap，通过文件挂载或 API 动态加载**：

```go
type SchedulerConfig struct {
    GPUModelPriority map[string]int `json:"gpuModelPriority"`
    GPUWeight        float64        `json:"gpuWeight"`
    AvailableWeight  float64        `json:"availableWeight"`
}

func (s *Scheduler) loadConfig(path string) (*SchedulerConfig, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    var cfg SchedulerConfig
    if err := json.Unmarshal(data, &cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
```

通过 Kubernetes ConfigMap 挂载：
```yaml
volumeMounts:
  - name: scheduler-config
    mountPath: /etc/scheduler/config.json
    readOnly: true
volumes:
  - name: scheduler-config
    configMap:
      name: gpu-scheduler-config
```

修改 ConfigMap 后，调度器 reload 配置即可生效，无需重启 Pod。

## 五、性能优化：万节点集群的调度实践

当集群规模超过 1000 个节点时，调度器的性能会成为瓶颈。以下是经过验证的优化手段：

### 5.1 Node 缓存层

不要每次调度都调用 API Server 列举节点，用 Informer + Local Cache：

```go
// 启动时一次性加载所有节点到本地缓存
nodeInformer.Informer().AddEventHandler(cache.ResourceEventHandlerFuncs{
    AddFunc:    func(obj) { s.nodeCache.Add(obj) },
    UpdateFunc: func(old, new) { s.nodeCache.Add(new) },
    DeleteFunc: func(obj) { s.nodeCache.Delete(obj) },
})

func (s *Scheduler) listNodes() []*corev1.Node {
    s.nodeCache.Range(func(key, value interface{}) bool {
        nodes = append(nodes, value.(*corev1.Node))
        return true
    })
    return nodes
}
```

### 5.2 并行化 Filter 和 Score

多个节点之间没有依赖关系，完全可以并行打分：

```go
import "sync"

func (s *Scheduler) scoreNodesParallel(pod *corev1.Pod, nodes []*corev1.Node) *corev1.Node {
    type result struct {
        node  *corev1.Node
        score int64
    }

    results := make(chan result, len(nodes))
    var wg sync.WaitGroup

    for _, n := range nodes {
        wg.Add(1)
        go func(node *corev1.Node) {
            defer wg.Done()
            score := s.calculateScore(pod, node)
            results <- result{node, score}
        }(n)
    }

    go func() {
        wg.Wait()
        close(results)
    }()

    var best result
    for r := range results {
        if r.score > best.score {
            best = r
        }
    }
    return best.node
}
```

### 5.3 调度队列优先级

用 Go 的 `container/heap` 实现优先级队列，让紧急任务优先调度：

```go
type PriorityQueue struct {
    items    []*v1.Pod
    priority func(*v1.Pod) int
}

func (pq *PriorityQueue) Push(pod *v1.Pod) {
    heap.Push(pq, pod)
}

func (pq *PriorityQueue) Pop() *v1.Pod {
    return heap.Pop(pq).(*v1.Pod)
}
```

## 六、实战案例：GPU 集群调度踩坑记

分享几个实际落地过程中遇到的典型问题：

**问题一：Pod 调度成功后 GPU 不可用**

Root Cause：节点上 GPU 被其他进程（nvidia-container-runtime 外的进程）占用，但 Kubernetes 不知道。

Solution：引入 DCGM（Data Center GPU Manager）监控，在 Filter 阶段主动探测 GPU 健康状态：

```go
func (s *Scheduler) checkGPUHealth(nodeName string) bool {
    // 通过节点 Annotations 获取 GPU 健康状态
    // DCGM Exporter 会定期更新节点 annotations
    node, err := s.clientset.CoreV1().Nodes().Get(ctx, nodeName, metav1.GetOptions{})
    if err != nil {
        return false
    }
    health, ok := node.Annotations["nvidia.com/gpu.health"]
    return ok && health == "healthy"
}
```

**问题二：调度器更新导致 Pod 漂移**

某次调度器配置更新后，所有已在 GPU 节点上运行的 Pod 被认为"调度到了错误节点"，需要重建。

Solution：调度器的 Filter 阶段只影响新调度请求，**不要**在 Filter 中包含已运行 Pod 的重新决策。如果需要迁移，用 Descheduler（反调度器）单独处理，不要让调度器主动驱逐。

**问题三：节点标签变更后调度不生效**

Node 的 GPU 标签变了，但调度器缓存的还是旧值。

Solution：Informer 的 Update 事件要完整刷新 Node 缓存，而不是增量合并：

```go
UpdateFunc: func(old, new interface{}) {
    node := new.(*corev1.Node)
    klog.Infof("Node %s updated, refreshing cache", node.Name)
    s.nodeCache.Add(new)  // 直接覆盖
},
```

## 七、总结与后续方向

本文从零构建了一个自定义 GPU 调度器，覆盖了：

1. **何时需要自定义调度器** — 异构资源、业务感知、多租户等场景
2. **Scheduler Framework vs 独立调度器** — 两种扩展方式的对比
3. **完整调度器实现** — Filter → Score → Bind 三大阶段
4. **部署与使用** — 多调度器共存、Pod 级指定
5. **生产级改造** — 队列管理、高可用、热更新、性能优化
6. **踩坑案例** — GPU 健康探测、Pod 漂移、缓存失效

**后续演进方向：**

- **Scheduler Framework 插件化**：将上述逻辑编译为 Kube Scheduler 插件，直接注入默认调度器，享受原生调度器的高可用能力
- **调度可视化**：接入 Prometheus + Grafana，监控调度延迟、成功率、资源分配率
- **成本优化**：结合云厂商 Spot 实例，在调度策略中加入成本权重

调度器是 Kubernetes 扩展性最强的组件之一。希望本文帮你打通了从原理到实战的全链路，有任何问题欢迎留言交流。

---

**推荐阅读：**

- [Kubernetes调度器核心原理：Pod是如何被安排到节点的](/posts/kubernetes-scheduler-principles/) — 调度器内部工作流程详解
- [Kubernetes与云原生面试八股文（一）——Kubernetes架构核心与集群管理](/posts/kubernetes-interview-one/) — K8s 基础知识体系
- [Kubernetes与云原生面试八股文（八）——生产级高可用与灾备](/posts/kubernetes-interview-eight/) — 集群高可用设计

---
