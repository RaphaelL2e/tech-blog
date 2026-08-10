---
title: Kubernetes与云原生面试八股文（二）——Pod深入与工作负载管理
date: 2026-07-30T10:00:00+08:00
updated: '2026-07-30T10:00:00+08:00'
description: 从面试高频问题出发，系统拆解 Pod 的本质与设计哲学、Pod 生命周期与相位管理、Init Container 与 Sidecar 模式、Deployment/StatefulSet/DaemonSet 三大工作负载的选型与实战、滚动更新与回滚机制，建立生产级 K8s 工作负载认知。
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 2
level: intermediate
status: maintained
tags:
- 面试
- Kubernetes
- K8s
- Pod
- Workload
categories:
- 分布式与微服务
draft: false
author: 飞哥
---

## Kubernetes与云-native面试八股文（二）——Pod深入与工作负载管理

### 🎯 本文目标

从面试高频问题出发，系统拆解 Pod 的本质与设计哲学、Pod 生命周期与相位管理、Init Container 与 Sidecar 模式、Deployment/StatefulSet/DaemonSet 三大工作负载的选型与实战、滚动更新与回滚机制，帮助你在面试中清晰回答"为什么 K8s 调度的是 Pod 而不是容器""Pod 的生命周期是怎样的""什么场景用 StatefulSet 而不是 Deployment""滚动更新是如何实现的"。

---

## 一、Pod 的本质与设计哲学

### 1.1 为什么是 Pod 而不是容器？

这是 K8s 面试中最高频的开场问题之一。

**核心答案**：Pod 是 K8s 的最小调度单元，而不是容器。一个 Pod 可以包含一个或多个容器，这些容器共享网络和存储命名空间。

**设计原因**：

| 维度 | 容器单独调度的问题 | Pod 解决方式 |
|------|-------------------|-------------|
| 网络共享 | 多个容器需要网络通信时需额外配置 | Pod 内容器共享 Network Namespace，通过 localhost 通信 |
| 存储共享 | 容器间共享数据需要外部方案 | Pod 内容器可挂载相同的 Volume |
| 生命周期 | 容器间没有统一的生命周期管理 | Pod 提供统一的生命周期，容器共生死 |
| 调度原子性 | 多容器无法保证调度到同一节点 | Pod 作为整体被调度到同一节点 |

**面试加分点**：Pod 的设计借鉴了"进程组"的概念。在操作系统层面，一组协作进程共享同一组资源；Pod 就是容器版的"进程组"。

### 1.2 Pod 的组成结构

```
┌─────────────────────────────────────┐
│              Pod                     │
│  ┌──────────────────────────────┐   │
│  │   Network Namespace          │   │
│  │   IP: 10.244.1.5            │   │
│  │   Port: 8080                 │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │   Volumes (共享)             │   │
│  │   - configmap-volume         │   │
│  │   - shared-data              │   │
│  └──────────────────────────────┘   │
│  ┌──────────┐  ┌──────────┐        │
│  │Container A│  │Container B│       │
│  │ (主容器)  │  │ (Sidecar)│       │
│  │ Nginx     │  │ Log Agent│       │
│  └──────────┘  └──────────┘        │
│  ┌──────────┐                       │
│  │ Init Ctr │ (启动前执行)          │
│  │ DB Migrate│                      │
│  └──────────┘                       │
└─────────────────────────────────────┘
```

**关键属性**：

- **Pod IP**：集群内唯一，Pod 内所有容器共享
- **hostname**：Pod 级别的 hostname，容器可通过 `hostname` 访问
- **restartPolicy**：Always（默认）、OnFailure、Never
- **terminationGracePeriodSeconds**：默认 30 秒，Pod 终止时的宽限期

### 1.3 Pod 的分类

| 类型 | 说明 | 典型场景 |
|------|------|---------|
| 普通 Pod | 通过 Deployment/StatefulSet 等管理 | 业务应用 |
| 静态 Pod | 由 kubelet 直接管理，不经过 API Server | 控制平面组件 |
| 守护 Pod | 通过 DaemonSet 管理 | 日志收集、监控 Agent |
| Job Pod | 通过 Job/CronJob 管理 | 批处理任务 |

**静态 Pod** 是面试常考点：控制平面组件（API Server、etcd、Scheduler、Controller Manager）通常以静态 Pod 形式运行，配置文件放在 `/etc/kubernetes/manifests/` 目录下，kubelet 会自动拉起。

---

## 二、Pod 生命周期与相位管理

### 2.1 Pod 的相位（Phase）

Pod 的 `status.phase` 字段表示其整体状态：

| 相位 | 说明 | 典型场景 |
|------|------|---------|
| Pending | Pod 已创建，但容器尚未全部就绪 | 调度中、镜像拉取中、Init Container 执行中 |
| Running | Pod 已绑定到节点，所有容器已启动 | 正常运行 |
| Succeeded | 所有容器成功终止且不会重启 | Job/CronJob 完成 |
| Failed | 所有容器终止，至少一个失败 | 崩溃退出 |
| Unknown | 无法确定 Pod 状态 | 通常是与 Pod 所在节点通信失败 |

**面试注意**：Phase 是粗粒度的，不能反映细节。真正的细节看 `containerStatuses` 中的 `state` 和 `reason`。

### 2.2 容器状态机

每个容器有自己的状态，与 Pod Phase 相互关联：

```
┌──────────┐
│  Waiting  │ ← 镜像拉取、依赖等待
└────┬─────┘
     │ 启动成功
     ▼
┌──────────┐
│  Running  │ ← 正常运行
└────┬─────┘
     │ 退出
     ▼
┌──────────┐
│ Terminated│ ← 退出码 0=成功，非 0=失败
└──────────┘
```

**Waiting 状态常见 reason**：
- `ContainerCreating`：正在创建
- `ImagePullBackOff`：镜像拉取失败
- `CrashLoopBackOff`：容器反复崩溃重启

**CrashLoopBackOff** 是面试高频问题——常见原因：

1. 应用启动失败（配置错误、依赖不可用）
2. 权限不足
3. 资源限制导致 OOMKilled
4. 存活探子（livenessProbe）配置过于激进

### 2.3 Pod 的启动流程

```
用户创建 Pod (kubectl apply)
    │
    ▼
API Server 接收请求 → 写入 etcd
    │
    ▼
Scheduler 监听到 Pod（status.phase=Pending）
    │ 过滤 + 打分
    ▼
选定 Node → 更新 pod.spec.nodeName
    │
    ▼
目标 Node 的 kubelet 监听到新 Pod
    │
    ▼
kubelet 调用 CRI 创建容器
    │
    ├─→ 执行 Init Container（串行，全部成功）
    │
    ├─→ 创建主容器（并行）
    │
    ├─→ 启动 postStart hook
    │
    ├─→ 启动探子 → 就绪探子
    │
    ▼
Pod status.phase = Running
```

### 2.4 Pod 的终止流程

```
用户删除 Pod (kubectl delete)
    │
    ▼
API Server → 更新 Pod 的 deletionTimestamp
    │
    ▼
kubelet 收到终止信号
    │
    ├─→ 发送 SIGTERM 给主容器
    │
    ├─→ 等待 terminationGracePeriodSeconds（默认 30s）
    │     超时后发送 SIGKILL
    │
    ├─→ preStop hook 在 SIGTERM 之前执行
    │
    ▼
容器退出 → Pod 从 Node 移除
    │
    ▼
Endpoint Controller 从 Service Endpoints 中移除该 Pod
```

**面试关键点**：preStop hook 和 terminationGracePeriodSeconds 的配合使用。如果应用需要在退出前清理资源（如反注册到注册中心、优雅关闭连接），必须配置 preStop hook：

```yaml
lifecycle:
  preStop:
    exec:
      command:
        - /bin/sh
        - -c
        - "nginx -s quit; sleep 10"
```

### 2.5 探针（Probes）详解

K8s 提供三种探针，这是面试必考题：

| 探针类型 | 作用 | 失败后果 |
|---------|------|---------|
| startupProbe | 判断容器是否已启动 | 失败则重启容器 |
| livenessProbe | 判断容器是否健康 | 失败则重启容器 |
| readinessProbe | 判断容器是否可接流量 | 失败则从 Service Endpoints 移除 |

**三种检测方式**：

```yaml
# HTTP 探测（最常用）
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 10
  failureThreshold: 3
  timeoutSeconds: 3

# TCP 探测（非 HTTP 服务）
livenessProbe:
  tcpSocket:
    port: 3306
  initialDelaySeconds: 30
  periodSeconds: 10

# 命令探测（灵活但较重）
livenessProbe:
  exec:
    command:
      - /bin/sh
      - -c
      - "pgrep nginx"
  initialDelaySeconds: 10
  periodSeconds: 5
```

**面试推荐配置策略**：

```
慢启动应用 → 配置 startupProbe（避免 liveness 在应用启动前就杀容器）
                    ↓
                startup 成功后
                    ↓
livenessProbe → 判断是否存活，失败重启
readinessProbe → 判断是否可接流量，失败摘流
```

---

## 三、Init Container 与 Sidecar 模式

### 3.1 Init Container

Init Container 在主容器启动前运行，必须全部成功退出（exit 0）后主容器才会启动。

**核心特性**：
- 串行执行（一个完成才执行下一个）
- 必须成功退出
- 失败则按 restartPolicy 重启
- 不支持 lifecycle hooks
- 不支持 readiness/liveness probe

**典型场景**：

```yaml
spec:
  initContainers:
  - name: init-db
    image: busybox
    command: ['sh', '-c', 'until nslookup mydb-service; do echo waiting for db; sleep 2; done']
  - name: init-config
    image: busybox
    command: ['sh', '-c', 'wget -O /config/app.conf http://config-server/app.conf']
    volumeMounts:
    - name: config
      mountPath: /config
  containers:
  - name: app
    image: myapp:latest
    volumeMounts:
    - name: config
      mountPath: /app/config
  volumes:
  - name: config
    emptyDir: {}
```

**面试要点**：Init Container 与主容器**共享 Volume**，这是传递数据的主要方式。Init Container 完成配置拉取、依赖等待、数据迁移等准备性工作。

### 3.2 Sidecar 模式

Sidecar 是一种设计模式，而非 K8s 内置资源。它指在同一个 Pod 中运行一个辅助容器，与主容器协同工作。

**经典 Sidecar 场景**：

| 场景 | Sidecar 职责 | 主容器 |
|------|-------------|--------|
| 日志收集 | Fluentd/Filebeat 采集日志 | 业务应用 |
| 配置同步 | 监听配置变更并更新本地文件 | 读取配置文件 |
| 代理转发 | Envoy/Nginx 做反向代理 | 业务应用 |
| 监控采集 | Prometheus exporter | 业务应用 |
| TLS 证书 | 证书轮换与挂载 | HTTP 服务 |

**示例：日志 Sidecar**：

```yaml
spec:
  containers:
  - name: app
    image: myapp:latest
    command: ["/app/server"]
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
  - name: log-agent
    image: fluent-bit:latest
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
      readOnly: true
    env:
    - name: POD_NAME
      valueFrom:
        fieldRef:
          fieldPath: metadata.name
  volumes:
  - name: logs
    emptyDir: {}
```

**面试加分点**：K8s 1.28+ 引入了原生的 Sidecar Container（`restartPolicy: Always` 的 Init Container），让 Sidecar 的生命周期管理更加规范，不再需要通过普通容器方式"模拟"。

### 3.3 Native Sidecar（K8s 1.28+）

```yaml
spec:
  initContainers:
  - name: sidecar
    image: log-agent:latest
    restartPolicy: Always    # 关键：声明为 Sidecar
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
  containers:
  - name: app
    image: myapp:latest
    volumeMounts:
    - name: logs
      mountPath: /var/log/app
  volumes:
  - name: logs
    emptyDir: {}
```

**Native Sidecar 的优势**：
- 与主容器并行启动（不需要等它完成）
- 在主容器退出后继续运行做清理工作
- 生命周期由 Pod 统一管理

---

## 四、Deployment：无状态应用的首选

### 4.1 Deployment 的本质

Deployment 是对 ReplicaSet 的声明式管理，提供滚动更新和回滚能力。

```
Deployment
    │
    ├── ReplicaSet (v1) → 3 Pods
    │
    └── ReplicaSet (v2) → 3 Pods (更新版本后创建)
```

**层级关系**：Deployment → ReplicaSet → Pod

### 4.2 关键配置

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-app
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1         # 滚动更新时最多多出多少个 Pod
      maxUnavailable: 0   # 滚动更新时最多不可用多少个 Pod
  template:
    metadata:
      labels:
        app: web-app
    spec:
      containers:
      - name: web
        image: myapp:v2
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

### 4.3 滚动更新机制

```
初始状态: RS-v1 → [Pod1(v1)] [Pod2(v1)] [Pod3(v1)]

Step 1: 创建新 Pod
        RS-v1 → [Pod1(v1)] [Pod2(v1)] [Pod3(v1)]
        RS-v2 → [Pod4(v2)]
        (maxSurge=1: 多出一个)

Step 2: 新 Pod 就绪后，杀旧 Pod
        RS-v1 → [Pod1(v1)] [Pod2(v1)]
        RS-v2 → [Pod4(v2)]

Step 3: 继续创建新 Pod
        RS-v1 → [Pod1(v1)] [Pod2(v1)]
        RS-v2 → [Pod4(v2)] [Pod5(v2)]

Step 4: 重复，直到全部替换
        RS-v2 → [Pod4(v2)] [Pod5(v2)] [Pod6(v2)]

最终: RS-v1 (replicas=0, 保留用于回滚)
```

**关键参数解读**：

| 参数 | 默认值 | 作用 |
|------|--------|------|
| maxSurge | 25% | 滚动期间最多多出的 Pod 数（相对 replicas） |
| maxUnavailable | 25% | 滚动期间最多不可用的 Pod 数（相对 replicas） |
| minReadySeconds | 0 | Pod 就绪后至少等多久才认为可用 |

**面试常考配置组合**：

```
maxSurge=1, maxUnavailable=0 → 永远多一个，零停机（最安全）
maxSurge=0, maxUnavailable=1 → 不多创建，先减后增（资源受限时）
maxSurge=1, maxUnavailable=1 → 快速滚动（有短暂不可用风险）
```

### 4.4 回滚机制

```bash
# 查看发布历史
kubectl rollout history deployment/web-app

# 查看某个版本详情
kubectl rollout history deployment/web-app --revision=2

# 回滚到上一版本
kubectl rollout undo deployment/web-app

# 回滚到指定版本
kubectl rollout undo deployment/web-app --to-revision=2
```

**回滚原理**：Deployment 保留了历史 ReplicaSet（默认保留 10 个，由 `revisionHistoryLimit` 控制）。回滚本质是切换到旧 ReplicaSet 并扩容，同时缩容当前 ReplicaSet。

### 4.5 面试高频问题

**Q: maxSurge=0 且 maxUnavailable=0 会怎样？**

A: 这是无效配置。K8s 会拒绝该 Deployment 的更新——因为既不允许增加 Pod 也不允许减少 Pod，滚动更新无法进行。

**Q: 滚动更新时如何保证不导流量到新/旧 Pod？**

A: 通过 readinessProbe + Service Endpoints 实现。新 Pod 的 readinessProbe 通过后才被加入 Endpoints，旧 Pod 的 readinessProbe 失败后从 Endpoints 摘除。配合 `preStop` hook 实现优雅退出。

---

## 五、StatefulSet：有状态应用的首选

### 5.1 为什么需要 StatefulSet？

Deployment 管理的 Pod 是无序的——Pod 名带随机后缀，重启后 IP 变化，无法保证顺序。但很多有状态应用需要：

- **稳定身份**：Pod 名可预测（如 `mysql-0`, `mysql-1`）
- **稳定存储**：每个 Pod 有独立持久化存储，重启不丢失
- **有序部署/扩缩**：按顺序启动和停止
- **有序网络标识**：DNS 可解析到具体 Pod

### 5.2 StatefulSet 核心特性

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql      # 必须指定 Headless Service
  replicas: 3
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      containers:
      - name: mysql
        image: mysql:8.0
  volumeClaimTemplates:    # 每个 Pod 自动创建独立 PVC
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

**核心机制对照**：

| 特性 | Deployment Pod | StatefulSet Pod |
|------|---------------|-----------------|
| Pod 名 | `web-app-abc123` | `mysql-0` → `mysql-1` → `mysql-2` |
| DNS | 无独立 DNS | `mysql-0.mysql.default.svc.cluster.local` |
| 存储 | 共享或无 | 每个有独立 PVC，`data-mysql-0` |
| 启动顺序 | 并行 | 顺序（0 启动完才启动 1） |
| 缩容 | 随机删 | 倒序删（先删 2，再删 1） |

### 5.3 Headless Service

StatefulSet 必须配合 Headless Service 使用：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql
spec:
  clusterIP: None    # 关键：Headless
  selector:
    app: mysql
  ports:
  - port: 3306
```

**Headless Service 的作用**：
- `clusterIP: None` 表示不分配虚拟 IP
- DNS 查询 `mysql` 返回所有 Pod IP（轮询）
- DNS 查询 `mysql-0.mysql` 返回具体 Pod IP
- 这让有状态应用可被按实例寻址

### 5.4 有序启动与优雅缩容

```
部署: mysql-0 → 就绪 → mysql-1 → 就绪 → mysql-2 → 就绪
扩容: 同部署顺序
缩容: mysql-2 → 终止 → mysql-1 → 终止 → mysql-0
```

**面试关键点**：
- `podManagementPolicy`：默认 `OrderedReady`，可设为 `Parallel`（并行管理，K8s 1.7+）
- `parallelPodManagement` 配合 `Parallel` 可加速启动
- 缩容时即使 `Parallel`，也按倒序删除

### 5.5 典型适用场景

| 场景 | 是否用 StatefulSet | 原因 |
|------|-------------------|------|
| MySQL 主从 | ✅ | 需稳定身份、稳定存储、有序启动 |
| Redis Cluster | ✅ | 每个 Node 需独立数据 |
| Kafka | ✅ | Broker ID 需稳定 |
| ZooKeeper | ✅ | Ensemble 需有序 |
| Nginx 前端 | ❌ | 无状态，用 Deployment |
| API 服务 | ❌ | 无状态，用 Deployment |
| 日志采集 Agent | ❌ | 每节点一个，用 DaemonSet |

---

## 六、DaemonSet：每节点一个

### 6.1 DaemonSet 的作用

DaemonSet 确保每个节点上运行一个 Pod 副本（可配置仅特定节点）。

```
Node1 ──── Pod (Fluentd)
Node2 ──── Pod (Fluentd)
Node3 ──── Pod (Fluentd)
Node4 ──── Pod (Node Exporter)
```

**典型场景**：
- 日志收集：Fluentd、Filebeat
- 监控代理：Node Exporter、Prometheus Agent
- 网络插件：Calico、Flannel
- 存储插件：Ceph CSI、Local Volume

### 6.2 关键配置

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-agent
spec:
  selector:
    matchLabels:
      app: log-agent
  template:
    metadata:
      labels:
        app: log-agent
    spec:
      nodeSelector:           # 仅部署到特定节点
        node-role: worker
      tolerations:             # 允许调度到污点节点
      - key: node-role.k8s.io/control-plane
        effect: NoSchedule
      containers:
      - name: fluentd
        image: fluentd:latest
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
        volumeMounts:
        - name: varlog
          mountPath: /var/log
          readOnly: true
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
```

### 6.3 DaemonSet 更新策略

| 策略 | 说明 |
|------|------|
| OnDelete | 手动删除 Pod 后才创建新 Pod（默认旧版） |
| RollingUpdate | 自动滚动更新（默认） |

```yaml
updateStrategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1    # 最多多少个节点同时不可用
    maxSurge: 0          # DaemonSet 不支持 maxSurge > 0
```

**面试要点**：DaemonSet 不设置 `replicas`，Pod 数量等于（符合条件的）节点数量。新节点加入集群后，DaemonSet 会自动在该节点创建 Pod。

---

## 七、三种工作负载对比总结

| 维度 | Deployment | StatefulSet | DaemonSet |
|------|-----------|-------------|-----------|
| 有状态 | 无 | 有 | 无 |
| Pod 名 | 随机后缀 | 有序编号 | 随机但每节点一个 |
| 存储 | 共享或无 | 独立 PVC | 通常用 hostPath |
| 调度策略 | 分散调度 | 顺序调度 | 每节点一个 |
| 滚动更新 | maxSurge + maxUnavailable | 逆序更新，从最大编号开始 | 逐节点更新 |
| 回滚 | 支持，保留历史 RS | 支持，保留历史 | 支持 |
| 典型应用 | Web/API/微服务 | 数据库/MQ/协调服务 | 日志/监控/网络 |
| 是否需要 Service | 通常 ClusterIP | 必须 Headless | 通常不需要 |

**面试口诀**：

```
无状态用 Deployment，
有状态用 StatefulSet，
每节点一个用 DaemonSet。
```

---

## 八、Pod 亲和性与反亲和性

### 8.1 为什么需要亲和性？

默认情况下，Scheduler 会将 Pod 尽量分散到不同节点。但有些场景需要更精细的控制：

| 需求 | 策略 |
|------|------|
| 同应用的 Pod 尽量分散 | 反亲和（Anti-Affinity） |
| 前端与后端尽量同节点 | 亲和（Affinity） |
| 调度到有 SSD 的节点 | 节点亲和 |
| 避免与 GPU 任务同节点 | 反亲和 |

### 8.2 节点亲和性

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:   # 硬约束
        nodeSelectorTerms:
        - matchExpressions:
          - key: disk-type
            operator: In
            values:
            - ssd
      preferredDuringSchedulingIgnoredDuringExecution:  # 软约束
      - weight: 80
        preference:
          matchExpressions:
          - key: zone
            operator: In
            values:
            - east
```

### 8.3 Pod 反亲和性

```yaml
spec:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app: web-app
          topologyKey: kubernetes.io/hostname
```

**面试要点**：
- `requiredDuringScheduling` = 硬约束，不满足就不调度
- `preferredDuringScheduling` = 软约束，尽量满足
- `topologyKey: kubernetes.io/hostname` = 按节点打散
- `topologyKey: topology.kubernetes.io/zone` = 按可用区打散

---

## 九、Pod 调度器工作原理

### 9.1 两阶段调度

```
待调度 Pod 进入调度队列
        │
        ▼
┌─────────────────┐
│  Filter（过滤）   │  ← PreFilter + Filter 插件
│  排除不满足的节点  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Score（打分）    │  ← Score 插件
│  对候选节点排序    │
└────────┬────────┘
         │
         ▼
    选定最高分节点
```

**常见过滤条件**：
- 资源是否足够（CPU/Memory）
- 节点是否污点排斥
- Pod 亲和/反亲和
- Volume 是否可挂载
- NodeSelector 是否匹配

**常见打分策略**：
- LeastRequestedPriority：资源使用率越低分越高
- BalancedResourceAllocation：CPU 和内存使用率越均衡分越高
- NodeAffinityPriority：符合节点亲和加分
- AntiAffinityPriority：符合反亲和加分

### 9.2 调度器面试要点

**Q: 如果所有节点都不满足过滤条件，Pod 会怎样？**

A: Pod 处于 Pending 状态，事件中会记录 `FailedScheduling` 原因。调度器会持续重试。

**Q: 调度器如何保证高可用？**

A: 多副本部署，通过 leader election 机制保证只有一个调度器在工作。其他副本作为备胎，主调度器挂了自动切换。

---

## 十、实战配置模板

### 10.1 生产级 Deployment 模板

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
  labels:
    app: api-service
spec:
  replicas: 3
  revisionHistoryLimit: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: api-service
  template:
    metadata:
      labels:
        app: api-service
    spec:
      terminationGracePeriodSeconds: 60
      containers:
      - name: api
        image: api-service:v2.0
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 1Gi
        startupProbe:
          httpGet:
            path: /health
            port: 8080
          failureThreshold: 30
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          periodSeconds: 5
          failureThreshold: 2
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]
        env:
        - name: APP_ENV
          value: "production"
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchLabels:
                  app: api-service
              topologyKey: kubernetes.io/hostname
```

### 10.2 生产级 StatefulSet 模板

```yaml
apiVersion: v1
kind: Service
metadata:
  name: mysql
  labels:
    app: mysql
spec:
  clusterIP: None
  selector:
    app: mysql
  ports:
  - port: 3306
    name: mysql
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql
  replicas: 3
  podManagementPolicy: OrderedReady
  updateStrategy:
    type: RollingUpdate
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: mysql
        image: mysql:8.0
        ports:
        - name: mysql
          containerPort: 3306
        env:
        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: root-password
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 50Gi
```

---

## 本期总结

| 知识点 | 核心内容 |
|--------|---------|
| Pod 本质 | 最小调度单元，共享网络和存储的容器组 |
| Pod 生命周期 | Pending → Running → Succeeded/Failed，细看容器状态 |
| 探针 | startup（启动）+ liveness（存活）+ readiness（就绪） |
| Init Container | 启动前串行执行，完成准备性工作 |
| Sidecar 模式 | 同 Pod 内辅助容器，Native Sidecar 1.28+ |
| Deployment | 无状态，滚动更新，maxSurge + maxUnavailable |
| StatefulSet | 有状态，稳定身份/存储/有序，Headless Service |
| DaemonSet | 每节点一个，日志/监控/网络 |
| 亲和性 | 节点亲和（硬/软），Pod 反亲和（分散调度） |
| 调度器 | Filter + Score 两阶段，leader election 高可用 |

**学习建议**：

1. **概念层**：理解 Pod 为什么是最小调度单元，为什么有状态应用需要 StatefulSet
2. **配置层**：能写完整的 Deployment + Probe + Lifecycle 配置
3. **原理层**：理解滚动更新的完整链路、回滚机制、调度器两阶段
4. **面试层**：能流畅回答三种工作负载的选型依据和各自适用场景

---

## 下期预告

下一篇：**Kubernetes与云原生面试八股文（三）——Service与网络通信** 将深入讲解 Service 的四种类型（ClusterIP/NodePort/LoadBalancer/ExternalName）、kube-proxy 三种模式（userspace/iptables/IPVS）、Ingress 控制器选型、NetworkPolicy 与 CNI 插件、Pod 间通信完整链路解析，敬请期待。

---

*作者：飞哥 · Raphael Lab*

*Kubernetes与云原生面试八股文系列*
