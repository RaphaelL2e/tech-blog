---
title: Kubernetes与云原生面试八股文（一）——Kubernetes架构核心与集群管理
date: 2026-07-29 10:00:00+08:00
updated: '2026-07-29T10:00:00+08:00'
description: 从面试高频问题出发，系统拆解 Kubernetes 架构核心组件、集群初始化、etcd 选主机制、API Server 请求链路，建立生产级 K8s 架构认知。本系列开篇。
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 1
level: intermediate
status: maintained
tags:
- 面试
- Kubernetes
- 云原生
- 架构
categories:
- 分布式与微服务
draft: false
author: 飞哥
---

## Kubernetes与云原生面试八股文（一）——Kubernetes架构核心与集群管理

### 🎯 本文目标

从面试高频问题出发，系统拆解 Kubernetes 架构核心组件、集群初始化流程、etcd 选主机制、API Server 请求链路，帮助你建立生产级 K8s 架构认知，面试中能清晰回答"K8s 架构是怎样的""各组件如何协作""生产环境如何保证高可用"。

---

## 一、Kubernetes 整体架构

### 1.1 控制平面（Control Plane）

控制平面是 K8s 集群的"大脑"，负责全局决策和响应集群事件：

| 组件 | 职责 | 面试关键词 |
|------|------|-----------|
| kube-apiserver | 所有组件通信的唯一入口，RESTful API | 唯一入口、认证鉴权、准入控制 |
| etcd | 分布式键值存储，保存集群所有状态数据 | 强一致、Raft、watch 机制 |
| kube-scheduler | Pod 调度器，决定 Pod 落在哪个节点 | 过滤+打分、调度队列 |
| kube-controller-manager | 运行控制器逻辑的进程 | 调谐循环、期望状态 vs 实际状态 |
| cloud-controller-manager | 与云厂商交互的控制器 | 云 provider、节点生命周期 |

### 1.2 工作节点（Worker Node）

| 组件 | 职责 |
|------|------|
| kubelet | 节点代理，管理 Pod 生命周期，向 API Server 汇报节点状态 |
| kube-proxy | 实现 Service 的负载均衡和网络代理，维护 iptables/IPVS 规则 |
| 容器运行时 | 负责运行容器，主流是 containerd（CRI 标准） |

### 1.3 架构图核心链路

```
┌─────────────────────────────────────────────────┐
│                  Control Plane                    │
│                                                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │API Server│──│  etcd    │   │ Scheduler    │ │
│  │ (入口)   │   │ (状态库) │   │ (调度器)     │ │
│  └────┬─────┘   └──────────┘   └──────────────┘ │
│       │                                           │
│  ┌────┴─────────────┐                            │
│  │ Controller Manager│                            │
│  └──────────────────┘                            │
└─────────┬───────────────────────────────────────┘
          │
    ┌─────┴─────┐
    │           │
┌───┴───┐   ┌──┴────┐
│ Node1 │   │ Node2  │
│kubelet│   │kubelet│
│proxy  │   │proxy  │
│contain│   │contain│
└───────┘   └───────┘
```

**面试要点**：所有组件都不直接访问 etcd，必须经过 API Server。这是 K8s 架构设计的核心原则——**单一数据入口**。

---

## 二、核心组件深度解析

### 2.1 kube-apiserver

API Server 是集群通信的枢纽，所有组件（kubelet、scheduler、controller-manager、kube-proxy）都通过它进行交互。

**请求处理链路**：

```
请求进入 → 认证(AuthN) → 授权(AuthZ) → 准入控制(Admission) → 写入etcd → 返回响应
```

**面试高频题：API Server 的三层安全机制**

1. **认证（Authentication）**：确认"你是谁"。支持 X509 证书、Bearer Token、OIDC 等多种方式
2. **授权（Authorization）**：确认"你能做什么"。主流用 RBAC（Role-Based Access Control）
3. **准入控制（Admission Control）**：确认"请求是否合规"。分为 Mutating（修改请求）和 Validating（验证请求）两类

```yaml
# RBAC 示例：定义一个只读角色
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: default
  name: read-pods
subjects:
- kind: User
  name: jane
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

### 2.2 etcd

etcd 是 K8s 的"数据库"，存储集群所有状态数据。

**面试高频题：为什么 K8s 选择 etcd 而不是 MySQL/Redis？**

| 特性 | etcd | MySQL | Redis |
|------|------|-------|-------|
| 一致性 | 强一致（Raft） | 强一致 | 最终一致 |
| Watch 机制 | 原生支持 | 不支持 | 不原生 |
| 数据模型 | KV 层次化 | 关系表 | KV |
| 多写一致性 | Raft 多数派 | 单主 | 主从异步 |

核心原因：**etcd 的 Watch 机制是 K8s 声明式架构的基础**。Controller 和 Scheduler 都依赖 Watch 来感知集群状态变化，而非轮询。

**etcd Raft 选主机制**：

- 集群通常部署 3 或 5 个节点（奇数）
- 写入需要多数派（N/2 + 1）确认
- 3 节点容忍 1 个故障，5 节点容忍 2 个故障
- Leader 选举通过心跳超时触发，随机超时时间避免脑裂

### 2.3 kube-scheduler

调度器负责决定 Pod 运行在哪个节点上。

**调度流程**：

```
Pod 创建 → 进入调度队列 → 过滤阶段(Predicate) → 打分阶段(Priority) → 绑定节点
```

**面试高频题：调度器的两阶段机制**

1. **过滤（Predicate）**：排除不满足条件的节点
   - 资源是否充足（CPU、内存）
   - 节点是否处于 NodeAffinity/NodeSelector 要求范围
   - 是否存在端口冲突
   - 是否违反 taint/toleration 约束

2. **打分（Priority）**：对剩余节点打分，选最优
   - 资源均衡打分（Least Requested）
   - 亲和性打分（InterPodAffinity）
   - 数据本地性打分

```python
# 伪代码理解调度逻辑
def schedule(pod, nodes):
    # 阶段1：过滤
    feasible_nodes = []
    for node in nodes:
        if has_enough_resources(node, pod) and \
           matches_node_selector(node, pod) and \
           tolerates_taints(node, pod):
            feasible_nodes.append(node)
    
    # 阶段2：打分
    best_node = None
    best_score = -1
    for node in feasible_nodes:
        score = calculate_score(node, pod)
        if score > best_score:
            best_score = score
            best_node = node
    
    return best_node
```

### 2.4 kube-controller-manager

控制器管理器运行多个控制器，每个控制器负责一种资源类型的调谐。

**核心控制器**：

| 控制器 | 职责 |
|--------|------|
| ReplicaSet Controller | 维持 Pod 副本数 |
| Deployment Controller | 管理 ReplicaSet，支持滚动更新 |
| Node Controller | 监控节点健康状态 |
| Service Controller | 管理负载均衡和 Service |
| Endpoint Controller | 维护 Service 与 Pod 的映射 |
| Job/CronJob Controller | 管理批处理任务 |

**面试高频题：什么是调谐循环（Reconcile Loop）？**

调谐循环是 K8s 声明式架构的核心设计模式：

```
获取期望状态 → 获取实际状态 → 比较差异 → 执行操作消除差异 → 回到步骤1
```

这不是一次性操作，而是持续运行的循环。当 Pod 挂了、节点宕机了，控制器会自动感知并做出调整，使实际状态无限趋近期望状态。

### 2.5 kubelet

kubelet 是每个节点上运行的代理，是"最后一公里"的执行者。

**核心职责**：

1. 向 API Server 注册节点
2. 监听 API Server 中分配到本节点的 Pod
3. 调用容器运行时（CRI）创建/销毁容器
4. 执行健康检查（liveness/readiness probe）
5. 汇报节点状态和资源使用量

**面试高频题：kubelet 如何管理 Pod 生命周期？**

```
Pod 分配到节点 → kubelet 检测到 → 调用CRI创建容器
  → 执行Init Container → 启动主容器
  → 执行post-start hook → 开始liveness/readiness探测
  → 收到删除请求 → 执行pre-stop hook → 发送SIGTERM → 等待宽限期 → SIGKILL
```

### 2.6 kube-proxy

kube-proxy 实现 Service 的负载均衡和网络代理。

**两种模式对比**：

| 模式 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| iptables | 通过 iptables 规则做 DNAT | 内核态，性能好 | 规则多时更新慢 |
| IPVS | 通过 IPVS 做负载均衡 | 支持多种算法，性能更优 | 依赖内核模块 |

**面试要点**：生产环境推荐 IPVS 模式。当 Service 数量超过 1000 时，iptables 模式的规则匹配变为 O(n) 线性扫描，而 IPVS 基于哈希表，查找效率 O(1)。

---

## 三、集群初始化与高可用

### 3.1 kubeadm 初始化流程

`kubeadm init` 是官方推荐的集群初始化方式：

```bash
# 初始化控制平面
kubeadm init \
  --apiserver-advertise-address=10.0.0.1 \
  --pod-network-cidr=10.244.0.0/16 \
  --kubernetes-version=v1.28.0

# 工作节点加入
kubeadm join 10.0.0.1:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

**初始化过程做了什么**：

1. 预检查（preflight checks）：检查系统环境
2. 生成 CA 证书和 kubeconfig
3. 启动 etcd 静态 Pod
4. 启动各控制平面组件（静态 Pod 方式）
5. 配置 RBAC 和集群默认资源
6. 部署 CNI 网络插件（需手动）

### 3.2 生产级高可用集群

**高可用架构**：

```
                    ┌─── Load Balancer (HAProxy/Keepalived) ───┐
                    │              VIP: 10.0.0.100               │
                    │                                           │
          ┌─────────┴──┐  ┌──────────┐  ┌──────────┐  ┌────────┴──┐
          │ Master 1   │  │ Master 2 │  │ Master 3 │  │           │
          │ API Server │  │ API Server│  │ API Server│  │           │
          │ etcd       │  │ etcd      │  │ etcd      │  │           │
          └────────────┘  └──────────┘  └──────────┘  └───────────┘
```

**面试高频题：K8s 高可用的关键点**

1. **API Server 高可用**：多实例 + 负载均衡，无状态服务可水平扩展
2. **etcd 高可用**：Raft 多数派，3 节点容忍 1 故障，5 节点容忍 2 故障
3. **Scheduler/Controller Manager 高可用**：多实例但只有一个 leader 工作（leader-election 机制）
4. **kubelet 连接**：指向 LB 的 VIP，而非具体某个 Master

### 3.3 静态 Pod（Static Pod）

**面试高频题：什么是静态 Pod？**

静态 Pod 由 kubelet 直接管理，不经过 API Server。配置文件放在 `/etc/kubernetes/manifests/` 目录下，kubelet 监听该目录，自动创建对应 Pod。

控制平面组件（apiserver、etcd、scheduler、controller-manager）在 kubeadm 部署中就是以静态 Pod 方式运行的。

```yaml
# /etc/kubernetes/manifests/etcd.yaml (简化)
apiVersion: v1
kind: Pod
metadata:
  name: etcd
  namespace: kube-system
spec:
  containers:
  - name: etcd
    image: registry.k8s.io/etcd:3.5.9
    command:
    - etcd
    - --data-dir=/var/lib/etcd
    volumeMounts:
    - mountPath: /var/lib/etcd
      name: etcd-data
  hostNetwork: true
  volumes:
  - name: etcd-data
    hostPath:
      path: /var/lib/etcd
```

---

## 四、高频面试题精选

### Q1: K8s 组件之间的通信方式是什么？

**答**：
- 所有组件 → API Server：通过 HTTPS（6443 端口）
- API Server → kubelet：HTTPS（10250 端口），用于日志/exec 等操作
- API Server → etcd：gRPC（2379 端口）
- etcd 节点之间：gRPC（2380 端口），Raft 通信
- kubelet → 容器运行时：通过 CRI gRPC 接口
- kube-proxy → iptables/IPVS：通过内核 netfilter 框架

### Q2: 为什么 K8s 用声明式 API 而不是命令式？

**答**：
- **声明式**：告诉系统"期望状态是什么"，系统自动调谐（如"我要 3 个 Nginx Pod"）
- **命令式**：告诉系统"执行什么操作"（如"启动一个 Nginx Pod"）

声明式优势：
1. **自愈能力**：Pod 挂了控制器自动重建
2. **可审计**：所有期望状态都在 etcd 中，可随时查看和回滚
3. **幂等性**：多次提交相同声明，结果一致
4. **GitOps 友好**：声明式 YAML 可版本管理，实现基础设施即代码

### Q3: API Server 如何处理高并发请求？

**答**：
1. API Server 本身是无状态的，可水平扩展多实例
2. 前面挂 LB 做负载均衡
3. 内部使用 watch 缓存机制：客户端 watch 后，数据变更通过长连接推送，避免轮询
4. etcd watch 机制：API Server watch etcd 变更，缓存到本地，减少 etcd 压力
5. 请求限流：APF（API Priority and Fairness）按优先级和公平性分配请求

### Q4: 生产环境中 etcd 如何运维？

**答**：
1. **备份**：定期 `etcdctl snapshot save` 备份数据，这是灾难恢复的最后防线
2. **监控**：关注 leader 切换次数、DB 大小、写入延迟、快照频率
3. **磁盘**：使用 SSD，etcd 对磁盘 IO 延迟敏感
4. **网络**：etcd 节点间网络延迟应低于 10ms
5. **压缩**：定期执行 `etcdctl compact` 清理历史版本，默认保留 5 分钟修订历史
6. **资源**：生产环境推荐至少 8GB 内存，避免 OOM 导致集群不可用

### Q5: 如何排查 Pod 一直处于 Pending 状态？

**答**：
```bash
# Step 1: 查看 Pod 事件
kubectl describe pod <pod-name> -n <namespace>
# 关注 Events 部分

# Step 2: 常见原因
# ① 资源不足：Insufficient cpu/memory
# ② 节点 taint 不容忍：node(s) had taints
# ③ 调度约束不匹配：node selector/affinity 不匹配
# ④ PVC 未就绪：pod has unbound immediate PersistentVolumeClaims
# ⑤ 超出资源配额：exceeded quota

# Step 3: 查看调度器日志
kubectl logs -n kube-system <scheduler-pod-name> | grep <pod-name>
```

---

## 五、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| 整体架构 | 控制平面 + 工作节点，API Server 单一入口 | Control Plane、Worker Node |
| API Server | 认证→授权→准入控制三层安全链路 | AuthN/AuthZ/Admission、RBAC |
| etcd | 强一致 KV 存储，Raft 选主，Watch 机制 | Raft、多数派、Watch |
| Scheduler | 过滤+打分两阶段调度 | Predicate/Priority |
| Controller | 调谐循环，期望 vs 实际状态 | Reconcile Loop |
| kubelet | 节点代理，管理 Pod 全生命周期 | CRI、Probe |
| kube-proxy | iptables/IPVS 两种模式 | DNAT、负载均衡 |
| 高可用 | 多实例 + LB + etcd 多数派 | Leader Election、VIP |

**架构认知三个层次：**
1. **组件层**：知道每个组件是干什么的
2. **链路层**：理解组件之间如何通信、请求如何流转
3. **设计层**：明白为什么这样设计（单一入口、声明式、调谐循环）

---

## 下期预告

下一篇：**Kubernetes与云原生面试八股文（二）——Pod深入与工作负载管理** 将深入讲解 Pod 的本质（为什么不是容器直接调度）、Pod 生命周期与相位、Init Container 与 Sidecar 模式、Deployment/StatefulSet/DaemonSet 三大工作负载的选型与实战、以及滚动更新与回滚机制，敬请期待。

---

*作者：飞哥 · Raphael Lab*

*Kubernetes与云原生面试八股文系列*
