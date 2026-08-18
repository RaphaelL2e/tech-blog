---
title: Kubernetes调度器核心原理：Pod是如何被安排到节点的
date: 2026-08-18T10:00:00+08:00
updated: '2026-08-18T10:00:00+08:00'
description: 'Pod是怎么被调度到合适的节点的？Kubernetes调度器的工作原理是什么？为什么你的Pod一直处于Pending状态？为什么两个Pod被调度到了同一个节点？调度器是如何在数千个节点的集群中找到最优解的？本文从调度框架出发，深入讲解Predicates、Priorities、Scoring机制、调度队列、抢占机制与调度器性能调优，结合生产案例帮你从根源理解Pod调度的每一个环节。'
topic: devops-cloud
level: advanced
status: maintained
tags:
- Kubernetes
- 调度器
- Scheduler
- Pod调度
- 资源管理
- 云原生
- 容器编排
categories:
- 云原生与 DevOps
draft: false
author: 飞哥
---

> Pod是怎么被调度到合适的节点的？Kubernetes调度器的工作原理是什么？为什么你的Pod一直处于Pending状态？为什么两个Pod被调度到了同一个节点？调度器是如何在数千个节点的集群中找到最优解的？本文从调度框架出发，深入讲解Predicates、Priorities、Scoring机制、调度队列、抢占机制与调度器性能调优，结合生产案例帮你从根源理解Pod调度的每一个环节。

## 一、为什么理解调度器很重要

面试高频问题背后往往藏着真实的痛点。在生产环境中，你可能遇到过以下场景：

- 业务高峰期，新Pod创建后始终处于 `Pending` 状态，等了10分钟也没调度
- 内存型业务的Pod和计算型业务的Pod挤在同一批节点，资源互相影响
- 新增了一个 Label 标签，想把特定Pod固定到特定节点，却发现调度不符合预期
- 集群有100个节点，但调度器只用了其中20个，资源严重不均

这些问题背后都指向同一个核心组件——**Kubernetes调度器（kube-scheduler）**。

调度器是Kubernetes的数据面和控制面的交汇点：它读取集群状态（节点资源、Pod拓扑），按照调度策略为每个未调度的Pod选择最优节点。理解调度器的工作原理，不仅能帮你解决上述问题，更能让你在设计大规模容器化架构时做出更好的决策。

本文的目标是让你从内部视角看清调度器的工作机制，不再只停留在「用kubectl手动绑nodeName」的水平。

## 二、调度器架构全景

### 2.1 调度器在Kubernetes中的位置

Kubernetes集群中，调度器是一个独立的组件（Deployment），与 API Server、etcd、Controller Manager、Kube Proxy 等组件协同工作。调度器的核心职责是**监听未调度的Pod（Pod.spec.nodeName为空），为每个Pod选择最优节点，并更新Pod的nodeName字段**。

整个调度流程可以概括为三个阶段：

1. **Scheduling Cycle（调度周期）**：对单个Pod做出调度决策——选择最优节点
2. **Binding Cycle（绑定周期）**：将调度决策持久化到etcd——将Pod绑定到节点
3. **Scheduling Queue（调度队列）**：管理待调度的Pod队列——决定先调度谁

调度周期和绑定周期可以异步并行执行——一个Pod的绑定可以与下一个Pod的调度同时进行，这是v1.19+引入的**Scheduling Framework**的重要优化。

### 2.2 Scheduling Framework 调度框架

从 Kubernetes 1.19 开始，调度器采用了 **Scheduling Framework**（调度框架）替代了原来插件化的架构。这个框架定义了一组扩展点（Extension Points），让开发者可以自定义调度逻辑而不必fork调度器代码。

调度框架定义了以下扩展点，按执行顺序排列：

```
QueueSort → PreFilter → Filter → PostFilter → 
Scoring → Reserve → Permit → PreBind → Bind → PostBind
```

每个扩展点都可以注册一个或多个插件（Plugin）。Kubernetes内置了大量插件，同时也支持通过 `Scheduler Framework` 的 Webhook 机制扩展。

**为什么这个设计很重要？** 因为它解释了为什么调度器有时候表现不符合预期——当你配置了多个Filter插件时，Pod必须通过所有Filter才能进入Scoring阶段；当你有自定义Scoring插件时，调度器选出的「最优节点」可能和资源均衡无关，而是按你的自定义分数排列。

### 2.3 调度周期与绑定周期的分离

在 Scheduling Framework 之前，调度周期和绑定周期是串行的——必须等Pod绑定到节点后才能开始下一个Pod的调度。从v1.19开始，两者可以并行：

- **调度周期**：选择节点（Scheduling Cycle）
- **绑定周期**：执行绑定（Binding Cycle）

两者通过一个「permit」阶段解耦——Pod在调度周期结束后进入 Permit 阶段等待，直到绑定周期完成才真正开始执行。这种设计大幅提升了调度器的吞吐量（Throughput），在高并发Pod创建场景下效果显著。

## 三、调度队列：谁先被调度

调度队列是理解调度器行为的第一道门。在调度器的内存中，有三个主要队列：

### 3.1 ActiveQ —— 活跃队列

ActiveQ 是调度器的主战场。所有可以通过调度框架开始调度周期的Pod都放在这里。调度器的主循环（scheduling cycle）不断从ActiveQ中取Pod进行调度。

### 3.2 UnschedulableQ —— 不可调度队列

曾经尝试调度但失败的Pod会被放进这个队列。这些Pod不会立即重试——调度器会等待节点状态变化（比如新节点加入、Pod完成、资源释放）后再把它们移回ActiveQ。

**生产陷阱**：如果你的集群中存在大量不可调度的Pod（比如资源不足），UnschedulableQ会不断膨胀。每次节点状态变化时，调度器会批量把相关Pod移回ActiveQ，这可能导致调度器CPU使用率周期性飙升。

### 3.3 BackoffQ —— 退避队列

对于因 transient error（临时错误，如节点暂时不可达）而调度失败的Pod，调度器采用退避策略：第一次失败后等待一段时间再重试，等待时间指数增长，最大60秒。

**如何判断Pod在哪个队列？** 你可以用以下命令查看调度器的内部队列状态（需要调度器开启相关debug接口）：

```bash
# 查看调度器队列信息
kubectl get --raw "/apis/scheduler.k8s.io/v1/namespaces/kube-system.com"
# 开启调度器 profiling 后查看
kubectl get --raw "/debug/pprof/"
```

更直接的方式是通过 `kubectl describe pod <pod-name>` 查看 Events 中调度器给出的失败原因：

```bash
kubectl describe pod nginx-xxxx | grep -A 5 "Events:"
# 典型输出：
# Type    Reason            From               Message
# ----    ------            ----               -------
# Warning  FailedScheduling  default-scheduler  0/10 nodes are available: 
#          1 Insufficient memory, 3 node(s) had taints that the pod didn't tolerate, 
#          6 node(s) didn't match pod affinity rules.
```

## 四、Filter阶段：节点能不能用

Filter阶段（v1.19之前的版本叫 Predicates）是调度器的第一道关卡。这一阶段会评估所有节点，**排除所有不满足条件的节点**。

Filter阶段的执行是**并行**的——调度器会对所有候选节点同时运行Filter插件，任一插件返回失败，该节点即被排除。

### 4.1 核心Filter插件

**NodeResourcesFit**：最常用的Filter插件，检查节点资源是否满足Pod的请求量。

```yaml
# Pod的资源请求
resources:
  requests:
    cpu: "2"
    memory: "4Gi"
```

调度器检查的是**请求量（requests）而非实际使用量**。这意味着一个CPU使用率已经90%的节点，只要它的requests总和没超过配额，仍然可能被调度。

**NodeAffinity**：检查节点的 label 是否满足 Pod 的 nodeSelector 和 affinity 规则。

```yaml
# Pod要求调度到带有 disktype=ssd 标签的节点
nodeSelector:
  disktype: ssd

# 更灵活的 affinity 写法
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: topology.kubernetes.io/zone
          operator: In
          values:
          - us-east-1a
```

**TaintToleration**：检查Pod是否容忍了节点上的Taints。如果节点有 NoExecute taint 且 Pod 没有对应 toleration，该节点被排除。

**PodTopologySpread**：检查Pod是否能满足拓扑分布约束。这个插件从v1.19引入，是实现高可用部署的重要工具：

```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: frontend
```

这段配置的含义是：frontend Pod 在每个可用区（zone）之间的分布不均匀程度不能超过1。如果无法满足，调度器不会把这个Pod调度到该节点。

### 4.2 Filter阶段的性能问题

Filter阶段会遍历所有节点。对于有数千个节点的大规模集群，这是一个性能瓶颈。

**生产调优策略**：

1. **使用 Cluster Autoscaler 时预筛选节点**：在节点数量激增时，Filter阶段的耗时可能从几十毫秒增加到几秒。
2. **合理设置 nodeSelector 和 affinity**：减少候选节点数量可以直接缩短 Filter 时间。
3. **开启 PercentageOfNodesToScore**：调度器默认会扫描所有节点，可以通过设置让调度器在找到足够数量的候选节点后提前退出扫描。

```yaml
# kube-scheduler 配置
apiVersion: kubescheduler.config.k8s.io/v1beta3
kind: KubeSchedulerConfiguration
percentageOfNodesToScore: 50  # 默认 50%，大规模集群可降低到 10-20%
```

## 五、Scoring阶段：哪个节点最优

Filter阶段排除了不可用的节点，Scoring阶段（v1.19之前叫 Priorities）对剩余的可用节点打分，选出最优节点。

Scoring阶段**是累加的**——每个插件给出一个0-10（或0-100）的分数，最终得分是所有插件分数的加权总和。

### 5.1 核心Scoring插件

**LeastRequestedPriority**：优先调度到资源使用率低的节点。计算公式：

```
score = (capacity - sum(requests)) / capacity * 10
```

这个插件倾向于将Pod分散到不同节点，避免资源过度集中。

**BalancedResourceAllocation**：与 LeastRequestedPriority 配合使用。当节点的 CPU 和 Memory 请求比例失衡时降低分数：

```
score = 10 - abs(CPUFraction - MemoryFraction) * 10
```

**NodeAffinityPriority**：根据 node affinity 的匹配程度打分，越符合偏好分数越高。

**ImageLocalityPriority**：优先调度到已经下载了容器镜像的节点。如果镜像很大（数GB），这个插件可以显著减少Pod启动时间（ImagePull时间）。

**TaintTolerationPriority**：根据Pod的toleration与节点Taints的匹配程度打分。容忍更多taint的Pod被调度到「不太干净」的节点，保留「干净」节点给更敏感的Pod。

### 5.2 自定义Scoring：打破默认规则

调度框架的真正威力在于自定义Scoring插件。常见场景：

**场景一：优先使用SSD节点**

```yaml
# 为节点打分时，给SSD节点额外加分
# 通过编写调度框架扩展来实现
# 这里展示概念性配置
```

**场景二：多租户公平调度**

```yaml
# 公平调度插件的配置
# 每个租户的Pod数量均衡，避免某个租户抢占所有资源
```

**场景三：拓扑感知调度**

```yaml
# 优先调度到与同服务其他Pod同节点或同AZ的节点
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchExpressions:
        - key: app
          operator: In
          values:
          - cache
      topologyKey: topology.kubernetes.io/zone
```

### 5.3 Scoring 的陷阱

Scoring 插件的组合可能导致意想不到的结果。例如，LeastRequestedPriority 和 BalancedResourceAllocation 同时启用时：

- **LeastRequestedPriority** 倾向选择资源空闲率高的节点
- **BalancedResourceAllocation** 倾向选择 CPU 和 Memory 比例均衡的节点

如果一个节点 CPU 使用率低但 Memory 使用率高，而另一个节点 CPU 使用率高但 Memory 使用率低，两者可能都得到次优分数。**理解每个插件的评分维度**，是正确配置调度策略的前提。

## 六、Reserve、Permit 和 Bind

### 6.1 Reserve阶段

Reserve阶段（v1.22引入）的作用是为Pod预留资源。在Reserve阶段，调度器通知 kubelet 「我要把Pod X调度到你这里了，提前预留Y内存」， kubelet 在自己的内存中标记这个预留。

Reserve 阶段的存在是为了解决**资源超售（over-commitment）**问题：如果Pod A调度到节点，但实际运行时占用了比requests更多的资源，后续Pod B的调度决策就会基于错误信息。Reserve 让 kubelet 有机会做预检查。

### 6.2 Permit阶段

Permit 阶段可以**拒绝或等待**一个调度决策。典型用途是实现**调度等待（wait）**：

- 当 Pod 需要等待某个条件（比如另一个Pod完成初始化）再绑定时，Permit 可以让调度器暂停这个Pod的绑定周期
- 等待超时后，Permit 可以选择拒绝调度（重新回到队列）或允许执行

**一个经典应用是 Preemption（抢占式调度）的实现**：当高优先级Pod无法找到可用节点时，调度器通过 Permit 等待低优先级Pod释放资源。

### 6.3 Bind阶段

Bind阶段将调度决策写入 etcd。在 v1.19+ 的 Framework 架构中，Bind 是异步执行的：

```bash
# Bind 的本质是更新 Pod 的 spec.nodeName
# 这个操作直接调用 API Server 的 PATCH 接口
PATCH /api/v1/namespaces/{namespace}/pods/{name}
{
  "spec": {
    "nodeName": "node-3"
  }
}
```

Bind 成功后，kubelet 监听到 Pod 的 nodeName 变化，开始拉取镜像和启动容器。

## 七、抢占式调度（Preemption）

### 7.1 什么时候需要抢占

当高优先级Pod无法找到可用节点时，Kubernetes 支持**抢占式调度**（Preemption）——调度器可以驱逐（delete）已调度的低优先级Pod，为高优先级Pod腾出空间。

```yaml
# Pod 的优先级配置
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: 100000
globalDefault: false
description: "高优先级Pod"
---
apiVersion: v1
kind: Pod
metadata:
  name: critical-app
spec:
  priorityClassName: high-priority
  containers:
  - name: app
    image: myapp:v1
```

### 7.2 抢占的执行过程

抢占不是简单的「杀掉低优先级Pod」。调度器的抢占过程分为以下步骤：

1. **候选节点识别**：找出所有可用节点中，如果有Pod被驱逐就能容纳待调度Pod的节点
2. **受害者选择**：在候选节点上选择优先级最低的一个或多个Pod作为「受害者」（victims）
3. **驱逐执行**：调度器向 API Server 发送删除请求，删除受害Pod
4. **等待重新调度**：被驱逐的Pod回到调度队列，重新参与调度

**关键问题**：被驱逐的Pod在等待重新调度期间，其容器需要重新启动。如果被驱逐Pod的容器中有未完成的计算或写入操作，这可能导致数据丢失。**生产环境应该尽量避免依赖抢占来调度关键Pod**，而是通过资源预留和资源配额（ResourceQuota）来保证关键Pod的资源。

### 7.3 非抢占式优先级的正确用法

如果你的Pod设置 `preemptionPolicy: Never`，则即使无法调度也不会抢占其他Pod：

```yaml
priorityClassName: high-priority
preemptionPolicy: Never  # 默认就是 Never，非抢占式
```

对于**有状态服务**（StatefulSet）和**数据库Pod**，强烈建议使用非抢占式优先级，避免因抢占导致服务中断。

## 八、调度器的性能调优

### 8.1 调度周期性能分析

在大规模集群中，调度器的性能瓶颈主要集中在 Filter 阶段的节点扫描。

**关键指标**：`scheduler_schedule_attempts_total` — 记录调度成功和失败的次数

```bash
# 查看调度器指标（需要开启 metrics-server）
kubectl top nodes
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes

# 查看调度器日志中的调度耗时
kubectl logs -n kube-system -l component=kube-scheduler | grep -i "scheduling"
```

### 8.2 多个调度器

Kubernetes 支持运行**多个调度器实例**，每个实例可以有不同的配置，专门调度不同类型的Pod：

```yaml
# Pod 指定使用自定义调度器
spec:
  schedulerName: my-custom-scheduler
```

这是一个被低估的功能。生产场景中，你可以：

- **部署一个「GPU调度器」**：专门负责GPU节点的调度，内置GPU亲和性、CUDA版本匹配等规则
- **部署一个「批处理调度器」**：专门调度批量作业类Pod，允许更激进的资源超售
- **部署一个「延迟敏感调度器」**：对延迟敏感的业务Pod，使用专用的低延迟调度策略

### 8.3 调度器配置实战

```yaml
# kube-scheduler-config.yaml
apiVersion: kubescheduler.config.k8s.io/v1beta3
kind: KubeSchedulerConfiguration
clientConnection:
  kubeconfig: /etc/kubernetes/scheduler.conf
profiles:
- schedulerName: default-scheduler
  percentageOfNodesToScore: 30
  plugins:
    score:
      disabled:
      - name: NodeResourcesFit  # 如果用自定义资源插件可以禁用默认插件
      enabled:
      - name: NodeResourcesBalancedAllocation
        weight: 5
      - name: ImageLocality
        weight: 3
```

## 九、生产实战：常见调度问题排查

### 9.1 Pod始终处于Pending

**排查步骤**：

```bash
# 1. 查看 Pod 详情
kubectl describe pod <pod-name> -n <namespace>

# 2. 检查是否有节点满足资源
kubectl describe node <node-name> | grep -A 5 "Allocated resources"

# 3. 检查 Taints 和 Tolerations
kubectl get node <node-name> -o jsonpath='{.spec.taints}'
kubectl get pod <pod-name> -o jsonpath='{.spec.tolerations}'

# 4. 检查节点状态
kubectl get node <node-name> -o wide
# 查看是否 Ready、是否有 MemoryPressure/DiskPressure/PIDPressure

# 5. 检查调度器日志
kubectl logs -n kube-system -l component=kube-scheduler --tail=100 | grep <pod-name>
```

### 9.2 Pod调度不均衡

**问题现象**：部分节点负载很高，部分节点几乎空闲。

**排查与解决**：

```bash
# 查看各节点Pod数量分布
kubectl get pod -o wide --all-namespaces | awk '{print $8}' | sort | uniq -c | sort -rn

# 检查是否有硬亲和性约束导致调度集中
kubectl get pod <pod-name> -o yaml | grep -A 20 "affinity:"

# 使用 descheduler 重新平衡（需要安装 descheduler 组件）
kubectl create configmap descheduler -n kube-system --from-file=policy.yaml
```

### 9.3 特定节点无法调度

```bash
# 检查节点污点
kubectl get nodes -o json | jq '.items[].spec.taints'

# 检查节点的 label（Pod可能依赖特定label）
kubectl get nodes <node-name> --show-labels

# 检查 Pod 的 nodeSelector 和节点 label 是否匹配
kubectl get pod <pod-name> -o jsonpath='{.spec.nodeSelector}'
```

## 十、总结

Kubernetes调度器的设计体现了分布式系统的核心权衡：**准确性 vs. 可扩展性**。通过 Filter-Scoring 两阶段设计，调度器在保证调度质量的同时，通过并行化、提前退出和队列管理实现了大规模集群下的可接受性能。

理解调度器的关键在于：

- **QueueSort → Filter → Scoring → Bind** 的执行流水线
- **Filter 是排除法，Scoring 是比较法**——两者策略不同
- **Reserve/Permit/Bind 是解耦点**——它们让调度周期和绑定周期并行执行
- **Preemption 是双刃剑**——能解决紧急调度问题，但可能导致被驱逐Pod的服务中断
- **多调度器是生产级扩展方案**——不同业务场景需要不同的调度策略

当你下次遇到 Pod Pending、调度不均或节点选择不符合预期的问题时，现在你有了定位问题根源的工具箱——从队列状态到Filter插件，从Scoring权重到Taint机制，每个环节都有对应的调试手段。

**下一期预告**：调度器选出了最优节点，但节点上 kubelet 怎么把容器拉起来、启动起来的？下一期我们来深入解析 **kubelet 机制——Pod 是如何从调度到运行的**。

---

*如果你觉得这篇文章有帮助，欢迎在GitHub上star这个博客。你的支持是我持续输出的动力。*
