---
title: Kubernetes与云原生面试八股文（四）——存储卷与数据持久化
date: 2026-08-01T10:00:00+08:00
updated: '2026-08-01T10:00:00+08:00'
description: 从面试高频问题出发，系统拆解 K8s Volume 类型体系（emptyDir/hostPath/configMap/secret）、PV 与 PVC 生命周期与绑定机制、StorageClass 动态供给、CSI 插件架构、StatefulSet 存储管理、数据备份与恢复策略，建立生产级 K8s 存储认知。
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 4
level: intermediate
status: maintained
tags:
- 面试
- Kubernetes
- Volume
- PV
- PVC
categories:
- 分布式与微服务
draft: false
author: 飞哥
---

## Kubernetes与云原生面试八股文（四）——存储卷与数据持久化

### 🎯 本文目标

存储是 Kubernetes 中最复杂也最容易被忽视的领域之一。本文将系统梳理 K8s 存储体系的全貌：从最基础的 Volume 类型，到 PV/PVC 静态绑定，再到 StorageClass 动态供给和 CSI 插件机制，最终落地到 StatefulSet 的存储管理实战。读完本文，你将能够：

1. 说清每种 Volume 类型的适用场景和生命周期
2. 掌握 PV 与 PVC 的绑定机制和回收策略
3. 理解 StorageClass 动态供给的完整流程
4. 了解 CSI 插件架构及其解决了什么问题
5. 在 StatefulSet 中正确使用持久化存储
6. 制定生产级数据备份与恢复策略

---

## 一、为什么 Kubernetes 需要存储抽象？

### 1.1 容器存储的困境

容器的文件系统是临时的——容器销毁后，其内部写入的数据随之消失。这对于无状态应用（如 Nginx、API Gateway）不是问题，但对于数据库、消息队列、日志收集器等有状态应用来说，数据持久化是刚需。

```dockerfile
# 一个简单的数据写入示例
FROM busybox
CMD ["sh", "-c", "while true; do echo $(date) >> /data/log.txt; sleep 5; done"]
```

如果不挂载 Volume，容器重启后 `/data/log.txt` 会丢失。

### 1.2 K8s 存储抽象的层次

Kubernetes 设计了多层存储抽象，从底向上：

```
┌─────────────────────────────────────────────┐
│           Pod (Volume Mounts)               │  ← 容器视角
├─────────────────────────────────────────────┤
│              Volume                         │  ← Pod 级别存储
├─────────────────────────────────────────────┤
│     PVC (PersistentVolumeClaim)             │  ← 用户存储申请
├─────────────────────────────────────────────┤
│     PV (PersistentVolume)                   │  ← 集群存储资源
├─────────────────────────────────────────────┤
│  StorageClass → 动态供给                     │  ← 存储类与自动分配
├─────────────────────────────────────────────┤
│  CSI Driver / in-tree Plugin                │  ← 存储后端实现
├─────────────────────────────────────────────┤
│  AWS EBS / NFS / Ceph / local-disk          │  ← 物理存储
└─────────────────────────────────────────────┘
```

**面试要点**：K8s 存储体系通过分层抽象，让用户不需要关心底层存储细节，只需声明需求（PVC），集群自动匹配或创建对应资源（PV）。

---

## 二、Volume 类型体系详解

### 2.1 Volume 总览

Kubernetes Volume 是 Pod 级别的存储，生命周期与 Pod 绑定。Volume 不是独立资源，而是 Pod Spec 的一部分。

按生命周期和用途分类：

| 类别 | Volume 类型 | 生命周期 | 典型场景 |
|------|------------|---------|---------|
| 临时存储 | emptyDir | 随 Pod 消亡 | 临时缓存、多容器共享 |
| 节点存储 | hostPath | 持久（节点级） | DaemonSet 访问宿主机文件 |
| 配置注入 | configMap、secret | 随 Pod 消亡 | 配置文件、密钥注入 |
| 持久存储 | persistentVolumeClaim | 独立于 Pod | 数据库、消息队列 |
| 投射卷 | projected | 随 Pod 消亡 | 合并多个 Volume 源 |
| 下游存储 | downwardAPI | 随 Pod 消亡 | Pod 元信息注入 |

### 2.2 emptyDir

emptyDir 是最简单的 Volume 类型：Pod 创建时分配一个空目录，Pod 删除时数据随之清除。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: emptydir-demo
spec:
  containers:
  - name: writer
    image: busybox
    command: ["sh", "-c", "while true; do echo $(date) >> /shared/log.txt; sleep 5; done"]
    volumeMounts:
    - name: shared-data
      mountPath: /shared
  - name: reader
    image: busybox
    command: ["sh", "-c", "tail -f /shared/log.txt"]
    volumeMounts:
    - name: shared-data
      mountPath: /shared
  volumes:
  - name: shared-data
    emptyDir:
      sizeLimit: 500Mi  # 可选：限制大小
```

**核心特性**：

- **生命周期**：与 Pod 绑定，Pod 删除即清除
- **存储介质**：默认使用节点磁盘，可设 `medium: Memory` 使用 tmpfs（内存）
- **大小限制**：可通过 `sizeLimit` 限制容量，超出会触发 Pod 驱逐
- **多容器共享**：同一 Pod 内多容器可通过同一 Volume 共享数据

**典型场景**：

- Init 容器与主容器之间的数据传递
- 多容器共享临时工作空间（如 Git pull + HTTP serve）
- 内存盘加速临时计算

**面试题**：emptyDir 的 `medium: Memory` 和普通磁盘有什么区别？

> 答：`medium: Memory` 使用 tmpfs（内存文件系统），读写速度极快，但占用节点内存，Pod 删除或重启时数据同样丢失。适合对性能敏感的临时数据，但要注意内存消耗。

### 2.3 hostPath

hostPath 将宿主节点的文件或目录挂载到 Pod 中。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-demo
spec:
  containers:
  - name: node-exporter
    image: prom/node-exporter
    volumeMounts:
    - name: proc
      mountPath: /host/proc
      readOnly: true
    - name: sys
      mountPath: /host/sys
      readOnly: true
  volumes:
  - name: proc
    hostPath:
      path: /proc
      type: Directory
  - name: sys
    hostPath:
      path: /sys
      type: Directory
```

**type 字段**：

| type 值 | 含义 |
|---------|------|
| （空） | 不校验，默认行为 |
| Directory | 必须存在且是目录 |
| DirectoryOrCreate | 不存在则创建空目录（权限 0755） |
| File | 必须存在且是文件 |
| FileOrCreate | 不存在则创建空文件（权限 0644） |
| Socket | 必须存在且是 socket |
| CharDevice | 必须存在且是字符设备 |
| BlockDevice | 必须存在且是块设备 |

**安全风险**：hostPath 赋予 Pod 访问宿主机文件系统的能力，可能突破容器隔离。生产环境应通过 PodSecurityPolicy/Pod Security Admission 限制使用。

**典型场景**：

- DaemonSet 类应用（node-exporter、Fluentd、监控 Agent）
- 容器运行时接口访问（挂载 `/var/run/docker.sock` 或 `/run/containerd/containerd.sock`）
- 节点系统信息采集

**面试题**：为什么不建议在普通业务 Pod 中使用 hostPath？

> 答：(1) 安全风险——Pod 可读写宿主机文件，可能被利用提权逃逸；(2) 调度耦合——Pod 被绑定到特定节点，失去调度灵活性；(3) 数据不一致——不同节点的 hostPath 内容不同，Pod 重调度后数据丢失。应优先使用 PVC。

### 2.4 configMap 和 secret 作为 Volume

configMap 和 secret 可以作为 Volume 挂载到 Pod 中，实现配置与镜像解耦。

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  application.yml: |
    server:
      port: 8080
    spring:
      datasource:
        url: jdbc:mysql://mysql-svc:3306/mydb
  logback.xml: |
    <configuration>
      <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder><pattern>%d{HH:mm:ss} %-5level %logger{36} - %msg%n</pattern></encoder>
      </appender>
      <root level="INFO"><appender-ref ref="STDOUT" /></root>
    </configuration>
---
apiVersion: v1
kind: Pod
metadata:
  name: configmap-volume-demo
spec:
  containers:
  - name: app
    image: my-app:latest
    volumeMounts:
    - name: config
      mountPath: /etc/app
      readOnly: true
  volumes:
  - name: config
    configMap:
      name: app-config
      items:  # 可选：只挂载部分 key
      - key: application.yml
        path: application.yml
      - key: logback.xml
        path: logback.xml
      defaultMode: 0644  # 文件权限
```

**Secret 作为 Volume**：

```yaml
volumes:
- name: tls-certs
  secret:
    secretName: tls-secret
    items:
    - key: tls.crt
      path: cert.pem
    - key: tls.key
      path: key.pem
    defaultMode: 0400  # Secret 文件权限应更严格
```

**关键行为**：

- ConfigMap/Secret 挂载为 Volume 后，文件内容是只读的
- 更新 ConfigMap/Secret 后，挂载的文件会自动更新（有 60-120 秒延迟）
- 使用 `subPath` 挂载单个 key 时不支持自动更新

**面试题**：ConfigMap 挂载后文件更新了，容器内是否自动感知？

> 答：作为目录挂载时，ConfigMap 更新会通过 kubelet 的同步机制在 60-120 秒内反映到容器内挂载的文件中。但如果使用 `subPath` 挂载单个文件，则不会自动更新——因为 subPath 实际上创建了一个符号链接到特定版本的文件。需要重启 Pod 才能获取更新。

### 2.5 projected Volume

projected Volume 允许将多个 Volume 源（ConfigMap、Secret、DownwardAPI、ServiceAccountToken）投射到同一个目录中。

```yaml
volumes:
- name: projected-volume
  projected:
    sources:
    - configMap:
        name: app-config
    - secret:
        name: db-credentials
    - downwardAPI:
        items:
        - path: "labels"
          fieldRef:
            fieldPath: metadata.labels
    - serviceAccountToken:
        path: token
        audience: vault
        expirationSeconds: 3600
```

**优势**：减少 Volume 挂载点数量，简化 Pod Spec，适合需要同时注入多种配置的场景。

### 2.6 各类 Volume 对比总结

| Volume 类型 | 数据持久性 | 跨节点 | 安全性 | 典型用途 |
|------------|-----------|-------|--------|---------|
| emptyDir | Pod 级（临时） | 否（随 Pod 调度） | 低 | 临时缓存、容器间共享 |
| hostPath | 节点级 | 否 | 危险 | DaemonSet、系统管理 |
| configMap | Pod 级 | 是（集群资源） | 低 | 配置文件注入 |
| secret | Pod 级 | 是（集群资源） | 中（Base64 编码） | 密钥、证书注入 |
| PVC | 持久 | 是 | 高 | 数据库、有状态应用 |
| projected | Pod 级 | 是 | 取决于源 | 合并多源配置 |

---

## 三、PersistentVolume 与 PersistentVolumeClaim

### 3.1 为什么需要 PV/PVC？

直接在 Pod 中指定存储后端（如 NFS 路径、EBS 卷 ID）存在两个问题：

1. **耦合**：Pod Spec 绑定了基础设施细节，违反 K8s 声明式设计
2. **管理**：存储生命周期与 Pod 生命周期耦合，无法独立管理

PV/PVC 引入了"存储的请求与供给"分离模式：

- **PV（PersistentVolume）**：集群管理员声明的存储资源，是基础设施的一部分
- **PVC（PersistentVolumeClaim）**：用户对存储的申请，类似 Pod 对 CPU/内存的申请

```
用户视角:  Pod → PVC（我需要 10Gi RWO 存储）
管理员视角: PV（NFS 100Gi 可用） ← 自动/手动绑定
```

### 3.2 PV 详解

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-nfs-001
  labels:
    type: nfs
spec:
  capacity:
    storage: 50Gi
  volumeMode: Filesystem  # Filesystem 或 Block
  accessModes:
  - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain  # Retain / Delete / Recycle
  storageClassName: ""  # 空字符串表示静态 PV
  nfs:
    path: /export/data-001
    server: 192.168.1.100
    readOnly: false
  mountOptions:
  - hard
  - nfsvers=4.1
```

**accessModes（访问模式）**：

| 模式 | 缩写 | 含义 |
|------|------|------|
| ReadWriteOnce | RWO | 单节点读写（最常见） |
| ReadOnlyMany | ROX | 多节点只读 |
| ReadWriteMany | RWX | 多节点读写（需要 NFS 等共享存储） |
| ReadWriteOncePod | RWOP | 单 Pod 读写（K8s 1.22+） |

**面试题**：RWO 和 RWX 的本质区别是什么？

> 答：RWO 是块存储的典型模式（如 EBS、Ceph RBD），底层设备同一时刻只能被一个节点挂载。RWX 需要共享文件系统（如 NFS、CephFS、GlusterFS），底层允许多节点同时读写。选择哪种取决于存储后端的能力，不是 K8s 层面的限制。

**persistentVolumeReclaimPolicy（回收策略）**：

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| Retain | PVC 删除后，PV 保留数据，状态变 Released | 生产环境、重要数据 |
| Delete | PVC 删除后，PV 和底层存储一起删除 | 动态供给的临时存储 |
| Recycle | 已废弃，旧版会清空数据 | 不推荐使用 |

**volumeMode**：

- `Filesystem`（默认）：挂载为文件系统目录
- `Block`：裸块设备，跳过文件系统层，适合对性能有极致要求的场景（如数据库）

### 3.3 PVC 详解

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-mysql-data
spec:
  accessModes:
  - ReadWriteOnce
  volumeMode: Filesystem
  resources:
    requests:
      storage: 20Gi
  storageClassName: ""  # 空字符串表示使用静态 PV
  selector:  # 可选：通过标签筛选 PV
    matchLabels:
      type: nfs
```

### 3.4 PV 与 PVC 的绑定机制

绑定是**一对一**的——一个 PV 只能绑定一个 PVC，反之亦然。

**静态供给流程**：

```
1. 管理员创建 PV（50Gi, RWO, NFS）
2. 用户创建 PVC（20Gi, RWO）
3. PV Controller 寻找匹配的 PV：
   - accessModes 必须兼容（PVC 的 mode ⊆ PV 的 modes）
   - storageClassName 必须匹配（都为空或都为同一名称）
   - selector 标签匹配（如果 PVC 指定了 selector）
   - PV 的 capacity >= PVC 的 request
4. 绑定成功：PVC.status.phase = Bound, PV.claimRef 指向 PVC
5. Pod 通过 PVC 引用使用存储
```

**绑定选择策略**：

- 如果多个 PV 都满足条件，选择 capacity 最小的（最小匹配）
- 如果没有匹配的 PV，PVC 处于 Pending 状态

**面试题**：PVC 请求 20Gi，匹配到 50Gi 的 PV，实际可用多少存储？

> 答：实际可用 50Gi。PV 和 PVC 的绑定是资源级别的，不是分区级别的。PVC 请求 20Gi 只是最低要求，绑定后 PVC 获得整个 PV 的使用权限。但在实际使用中，如果应用只写 20Gi 的数据，底层存储也只消耗 20Gi（对于精简配置的存储）。

### 3.5 PV 的状态流转

```
Available → Bound → Released → Available（仅 Retain 策略）
                ↑                   │
                └───────────────────┘
                  管理员手动清理后

Available → Bound → Released → （Delete 策略直接删除）
```

| 状态 | 含义 |
|------|------|
| Available | 空闲，未被 PVC 绑定 |
| Bound | 已绑定到 PVC |
| Released | PVC 已删除，但 PV 数据保留（Retain 策略） |
| Failed | 自动回收失败 |

**Released 状态的特殊处理**：

当 PVC 被删除后，使用 Retain 策略的 PV 进入 Released 状态，但不会自动回到 Available。管理员需要：

1. 清理 PV 中的数据（如果需要）
2. 删除 PV 的 `claimRef` 字段，使其重新变为 Available

```bash
# 手动释放 PV 供重新使用
kubectl patch pv pv-nfs-001 --type json -p '[{"op":"remove","path":"/spec/claimRef"}]'
```

---

## 四、StorageClass 与动态供给

### 4.1 为什么需要动态供给？

静态供给需要管理员手动创建 PV，存在明显短板：

- **效率低**：每次 PVC 申请都需要人工干预
- **预估难**：无法准确预估需要多少 PV
- **资源浪费**：预先创建的 PV 可能长期闲置

动态供给通过 StorageClass 自动创建 PV，实现"按需分配"。

### 4.2 StorageClass 定义

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs  # 存储提供者
parameters:  # 传递给 provisioner 的参数
  type: gp3
  fsType: ext4
  iopsPerGB: "50"
reclaimPolicy: Delete  # 动态 PV 的默认回收策略
volumeBindingMode: WaitForFirstConsumer  # 延迟绑定
allowVolumeExpansion: true  # 允许扩容
mountOptions:
  - discard
```

**volumeBindingMode**：

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| Immediate | PVC 创建后立即绑定 PV | 集群内存储（NFS） |
| WaitForFirstConsumer | 直到 Pod 被调度后才创建并绑定 PV | 拓扑感知存储（EBS、local） |

**WaitForFirstConsumer 的意义**：

以 AWS EBS 为例，EBS 卷是可用区（AZ）级别的资源。如果 Pod 被调度到 us-east-1a，但 EBS 卷创建在 us-east-1b，则无法挂载。WaitForFirstConsumer 等到 Pod 调度确定后，再在 Pod 所在的 AZ 创建 EBS 卷。

```yaml
# 带拓扑约束的 StorageClass
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-gp3
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
parameters:
  type: gp3
  fsType: ext4
```

### 4.3 动态供给完整流程

```
1. 用户创建 PVC（storageClassName: fast-ssd）
2. PVC 处于 Pending 状态
3. [WaitForFirstConsumer] 等到 Pod 被调度
4. StorageClass 的 provisioner 被触发
5. Provisioner 调用存储后端 API 创建存储资源（如 AWS EBS 卷）
6. 自动创建 PV，与 PVC 绑定
7. Pod 挂载 PVC 使用存储
```

```
┌──────┐     ┌──────┐     ┌────────────┐     ┌─────────┐
│ PVC  │────▶│ SC   │────▶│Provisioner │────▶│ EBS/NFS │
│20Gi  │     │fast  │     │(CSI/in-tree)│     │ 20Gi 卷 │
└──────┘     └──────┘     └────────────┘     └────┬────┘
                                                │
                                          ┌─────▼─────┐
                                          │ PV (自动)  │
                                          │ 20Gi RWO  │
                                          └─────┬─────┘
                                                │
                                          ┌─────▼─────┐
                                          │ PVC Bound │
                                          └───────────┘
```

### 4.4 PVC 使用 StorageClass

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-data
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: fast-ssd  # 指定 StorageClass
  resources:
    requests:
      storage: 30Gi
```

### 4.5 卷扩容

当 StorageClass 设置 `allowVolumeExpansion: true` 时，可以在线扩容 PVC：

```bash
# 直接修改 PVC 的请求大小
kubectl patch pvc mysql-data --type merge -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
```

扩容是单向操作——只能扩大，不能缩小。扩容过程不需要重启 Pod（对于大多数 CSI 驱动）。

**面试题**：PVC 扩容时 Pod 需要重启吗？

> 答：大多数 CSI 驱动支持在线扩容，不需要重启 Pod。扩容分两步：(1) 底层存储卷扩容（由 CSI 驱动完成）；(2) 文件系统扩容（由 kubelet 在节点上执行 `resize2fs` 或 `xfs_growfs`）。第二步需要 Pod 所在节点上的 kubelet 检测到卷大小变化后自动执行。

---

## 五、CSI（Container Storage Interface）

### 5.1 CSI 是什么？

CSI 是一个标准接口规范，定义了容器编排系统（CO）与存储系统之间的交互协议。Kubernetes 从 1.9 版本开始引入 CSI，逐步替代 in-tree 存储插件。

**CSI 解决了 in-tree 插件的问题**：

| in-tree 插件的问题 | CSI 的解决方案 |
|-------------------|---------------|
| 代码耦合到 K8s 核心代码库 | 独立部署，与 K8s 核心解耦 |
| 新存储类型需要等 K8s 发版 | 存储厂商独立发布 |
| K8s 维护所有存储插件代码 | 厂商自行维护 |
| 升级 K8s 可能影响存储功能 | CSI 驱动独立升级 |

### 5.2 CSI 架构

```
┌──────────────────────────────────────────────────┐
│                  Kubernetes Master                │
│  ┌─────────────┐  ┌──────────┐  ┌────────────┐  │
│  │ PV Controller│  │ADSCtrl   │  │  CSI Driver │  │
│  │ (watch PVC) │  │(watch Vol)│  │  Controller │  │
│  └──────┬──────┘  └────┬─────┘  └──────┬─────┘  │
│         │              │                │         │
│         └──────────────┴────────────────┘         │
│                        │ gRPC                     │
├────────────────────────┼──────────────────────────┤
│                   CSI Controller                   │
│            (Create/Delete/Attach/Snapshot)         │
├────────────────────────────────────────────────────┤
│                    存储后端                          │
│              (EBS / Ceph / NFS / ...)              │
└────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│                  Worker Node                       │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ kubelet  │  │ CSI Node     │  │  容器运行时  │ │
│  │          │─▶│ Plugin       │─▶│  (mount)   │ │
│  └──────────┘  └──────────────┘  └────────────┘ │
│                        │ gRPC                     │
│                   Node Stage/Mount                 │
└────────────────────────────────────────────────────┘
```

### 5.3 CSI 三大组件

一个完整的 CSI 驱动包含两个运行位置和三个核心组件：

**1. CSI Controller（运行在控制平面）**

- **Identity Server**：驱动信息上报
- **Controller Server**：卷的创建/删除、快照创建/删除、卷扩容
- 通过 gRPC 与 K8s 的 sidecar 容器（如 external-provisioner、external-attacher）通信

**2. CSI Node（运行在每个节点）**

- **Node Server**：卷的 Stage（格式化+挂载到全局目录）、Publish（从全局目录 bind-mount 到 Pod 路径）、Unstage/Unpublish

**3. CSI Sidecar 容器**

| Sidecar | 职责 |
|---------|------|
| external-provisioner | 监听 PVC，调用 CSI 创建/删除卷 |
| external-attacher | 监听 VolumeAttachment，调用 CSI 挂载/卸载卷 |
| external-snapshotter | 监听 VolumeSnapshot，调用 CSI 创建/删除快照 |
| external-resizer | 监听 PVC 扩容，调用 CSI 扩展卷 |
| node-driver-registrar | 向 kubelet 注册 CSI 驱动 |
| liveness-probe | 健康检查 |

### 5.4 CSI 卷生命周期

```
Provision → Attach → Mount → Use → Unmount → Detach → Delete
    │         │        │                │         │        │
    │         │        └── NodePublishVolume ──┘ │        │
    │         └── ControllerPublishVolume ───────┘        │
    └── CreateVolume ─────────────────────────── DeleteVolume ┘
```

**详细步骤**：

1. **CreateVolume**：CSI Controller 在存储后端创建卷
2. **ControllerPublishVolume**（Attach）：将卷挂载到目标节点（块存储需要）
3. **NodeStageVolume**：在节点上格式化并挂载到全局目录（如 `/var/lib/kubelet/plugins/kubernetes.io/csi/pv/{pv-name}/globalmount`）
4. **NodePublishVolume**：从全局目录 bind-mount 到 Pod 的挂载路径
5. **NodeUnpublishVolume**：卸载 Pod 路径
6. **NodeUnstageVolume**：卸载全局目录
7. **ControllerUnpublishVolume**（Detach）：从节点分离卷
8. **DeleteVolume**：在存储后端删除卷

### 5.5 常见 CSI 驱动

| CSI 驱动 | 存储后端 | 特性 |
|---------|---------|------|
| ebs.csi.aws.com | AWS EBS | 块存储，AZ 级别，WaitForFirstConsumer |
| pd.csi.storage.gke.io | GCE PD | Google Cloud 持久盘 |
| disk.csi.azure.com | Azure Disk | Azure 托管磁盘 |
| cephfs.csi.ceph.com | CephFS | 共享文件系统，支持 RWX |
| rbd.csi.ceph.com | Ceph RBD | 块存储 |
| nfs.csi.k8s.io | NFS | 网络文件系统，支持 RWX |
| driver.longhorn.io | Longhorn | Rancher 分布式块存储 |
| hostpath.csi.k8s.io | HostPath | 仅用于测试 |

---

## 六、StatefulSet 的存储管理

### 6.1 StatefulSet 为什么需要特殊存储？

Deployment 创建的 Pod 是无状态的——任何 Pod 可以使用任何 PVC，Pod 重建后可以挂载到不同的 PVC。但对于有状态应用（如 MySQL 主从、Kafka 集群），每个实例需要：

1. **稳定的网络标识**：Pod-0、Pod-1 始终保持固定名称和 DNS
2. **稳定的持久化存储**：Pod-0 的数据在重建后必须挂载回原来的 PVC

StatefulSet 通过 `volumeClaimTemplates` 解决第二个需求。

### 6.2 volumeClaimTemplates

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql
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
  persistentVolumeClaimRetentionPolicy:
    whenDeleted: Retain  # StatefulSet 删除时保留 PVC
    whenScaled: Retain  # 缩容时保留 PVC
```

**生成的 PVC 命名规则**：

```
{volumeClaimTemplate.name}-{statefulset.name}-{pod-index}

# 例如：
data-mysql-0  → Pod mysql-0 的 PVC
data-mysql-1  → Pod mysql-1 的 PVC
data-mysql-2  → Pod mysql-2 的 PVC
```

每个 PVC 是独立的，绑定不同的 PV。Pod-0 始终使用 `data-mysql-0`，即使 Pod 被重新调度到其他节点，也会重新挂载同一个 PVC（和底层 PV）。

### 6.3 StatefulSet 存储的调度行为

```
Pod mysql-0 创建 → PVC data-mysql-0 创建 → PV 绑定 → Pod 调度 → 挂载
Pod mysql-1 创建 → PVC data-mysql-1 创建 → PV 绑定 → Pod 调度 → 挂载
Pod mysql-2 创建 → PVC data-mysql-2 创建 → PV 绑定 → Pod 调度 → 挂载
```

**有序创建**：StatefulSet 按 0→1→2 的顺序创建 Pod，每个 Pod 必须 Ready 后才创建下一个。

**删除顺序**：缩容时按 2→1→0 的逆序删除 Pod。

**PVC 与 Pod 的关系**：
- Pod 删除（非缩容）：PVC 保留，Pod 重建后自动挂载回原 PVC
- 缩容（replicas: 3→2）：Pod-2 被删除，PVC data-mysql-2 根据 `whenScaled` 策略处理
- StatefulSet 删除：所有 Pod 被删除，PVC 根据 `whenDeleted` 策略处理

### 6.4 persistentVolumeClaimRetentionPolicy 详解

| 策略字段 | 值 | 行为 |
|---------|-----|------|
| whenDeleted | Retain | StatefulSet 删除时保留 PVC（默认） |
| whenDeleted | Delete | StatefulSet 删除时删除 PVC 和 PV |
| whenScaled | Retain | 缩容时保留被删 Pod 的 PVC（默认） |
| whenScaled | Delete | 缩容时删除被删 Pod 的 PVC 和 PV |

**生产建议**：
- 数据库类应用：`whenDeleted: Retain, whenScaled: Retain`（保护数据）
- 临时计算集群：`whenDeleted: Delete, whenScaled: Delete`（自动清理）

### 6.5 StatefulSet 存储实战：MySQL 一主多从

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: mysql-config
data:
  master.cnf: |
    [mysqld]
    log-bin=mysql-bin
    server-id=1
  slave.cnf: |
    [mysqld]
    log-bin=mysql-bin
    server-id=2
    read-only=1
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: mysql
  replicas: 3
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      initContainers:
      - name: init-mysql
        image: mysql:8.0
        command:
        - bash
        - -c
        - |
          if [[ $HOSTNAME =~ -0$ ]]; then
            cp /config/master.cnf /etc/mysql/conf.d/my.cnf
          else
            cp /config/slave.cnf /etc/mysql/conf.d/my.cnf
          fi
        volumeMounts:
        - name: config
          mountPath: /config
        - name: conf
          mountPath: /etc/mysql/conf.d
      containers:
      - name: mysql
        image: mysql:8.0
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql
        - name: conf
          mountPath: /etc/mysql/conf.d
      volumes:
      - name: config
        configMap:
          name: mysql-config
      - name: conf
        emptyDir: {}
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

这个示例中：
- 每个 MySQL 实例有独立的 50Gi PVC
- Pod-0 为主节点（可写），Pod-1/2 为从节点（只读）
- 配置通过 ConfigMap + initContainer 注入
- 数据存储在 PVC 中，Pod 重建后数据不丢失

**面试题**：StatefulSet 的 Pod 删除后重建，数据还在吗？

> 答：在。StatefulSet 通过 volumeClaimTemplates 为每个 Pod 创建独立的 PVC。Pod 删除时 PVC 不会被删除（默认 Retain 策略），Pod 重建后会自动重新挂载同一个 PVC，数据得以保留。只有手动删除 PVC 或设置 Delete 策略时，数据才会被清除。

---

## 七、存储快照与备份恢复

### 7.1 VolumeSnapshot

CSI 驱动支持卷快照功能，通过 VolumeSnapshot 和 VolumeSnapshotClass 管理。

```yaml
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotClass
metadata:
  name: ebs-snapshot
driver: ebs.csi.aws.com
deletionPolicy: Delete
---
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: mysql-snapshot
spec:
  volumeSnapshotClassName: ebs-snapshot
  source:
    persistentVolumeClaimName: data-mysql-0
```

**快照恢复**：从快照创建新的 PVC。

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: mysql-restore
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: fast-ssd
  resources:
    requests:
      storage: 50Gi
  dataSource:
    name: mysql-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

### 7.2 生产级备份策略

| 策略 | 工具 | 适用场景 | RPO | RTO |
|------|------|---------|-----|-----|
| 存储快照 | VolumeSnapshot | 日常快照备份 | 分钟级 | 分钟级 |
| 应用级备份 | mysqldump / pg_dump | 数据库逻辑备份 | 小时级 | 小时级 |
| 异地复制 | Velero + S3 | 灾难恢复 | 小时级 | 小时级 |
| 持续复制 | 存储层同步复制 | 关键业务 | 秒级 | 秒级 |

### 7.3 Velero 备份方案

Velero（原 Heptio Ark）是 K8s 生态中最流行的备份工具：

```bash
# 安装 Velero
velero install \
  --provider aws \
  --bucket velero-backups \
  --backup-location-config region=us-east-1 \
  --snapshot-location-config region=us-east-1

# 创建备份
velero backup create mysql-backup \
  --include-namespaces default \
  --include-resources persistentvolumeclaims,persistentvolumes \
  --snapshot-volumes=true

# 恢复
velero restore create --from-backup mysql-backup
```

**Velero 的优势**：
- 备份 K8s 资源清单 + PV 数据
- 支持命名空间级别备份
- 支持跨集群恢复
- 支持定时备份计划

---

## 八、存储选型与实践建议

### 8.1 存储类型选型矩阵

| 场景 | 推荐 Volume 类型 | 原因 |
|------|----------------|------|
| 无状态应用临时存储 | emptyDir | 随 Pod 生命周期，无需管理 |
| 配置文件注入 | configMap | 声明式管理，支持热更新 |
| 密钥/证书 | secret | Base64 编码，可加密存储 |
| 单实例数据库 | PVC (RWO) | 持久化，独立于 Pod |
| 集群化数据库 | StatefulSet + PVC | 每实例独立存储，稳定标识 |
| 多 Pod 共享数据 | PVC (RWX) + NFS/CephFS | 多节点同时读写 |
| 监控/日志 Agent | hostPath | 需要访问宿主机文件 |
| 高性能数据库 | PVC (Block 模式) | 绕过文件系统，裸设备 I/O |

### 8.2 生产环境最佳实践

**1. 使用动态供给**
- 默认使用 StorageClass 动态创建 PV
- 设置 `allowVolumeExpansion: true` 以支持扩容
- 使用 `WaitForFirstConsumer` 避免拓扑问题

**2. 数据保护**
- 重要数据设置 `reclaimPolicy: Retain`
- StatefulSet 设置 `persistentVolumeClaimRetentionPolicy: Retain`
- 定期创建 VolumeSnapshot
- 使用 Velero 做集群级备份

**3. 性能考量**
- 数据库类应用使用 SSD 存储类
- 考虑使用 Block volumeMode 绕过文件系统开销
- emptyDir 临时数据设 `medium: Memory` 加速（注意内存限制）
- 监控 PVC 的 IOPS 和吞吐量

**4. 安全性**
- 限制 hostPath 使用（通过 Pod Security Standards）
- Secret 挂载使用最小权限（`defaultMode: 0400`）
- 敏感数据考虑使用加密 StorageClass（如 EBS 加密卷）

**5. 容量规划**
- 预留 20-30% 存储余量
- 设置 PVC 监控告警（使用率 > 80% 报警）
- 定期审计孤儿 PVC（已无 Pod 使用但未删除的 PVC）

---

## 九、高频面试题速查

### Q1：PV 和 PVC 的区别是什么？

PV 是集群级别的存储资源，由管理员创建；PVC 是用户对存储的申请。PV 是"供给"，PVC 是"需求"，通过绑定机制连接。PV 的生命周期独立于 Pod，PVC 的生命周期独立于 Pod 但依赖命名空间。

### Q2：静态供给和动态供给的区别？

静态供给：管理员手动创建 PV，PVC 从已有 PV 中匹配。动态供给：PVC 指定 StorageClass，系统自动创建 PV。动态供给无需人工干预，按需创建，是生产环境的推荐方式。

### Q3：StorageClass 的 WaitForFirstConsumer 有什么用？

延迟 PV 的创建和绑定，直到有 Pod 被调度到具体节点。对于可用区（AZ）级别的存储（如 AWS EBS），可以确保 PV 创建在 Pod 所在的 AZ，避免跨 AZ 挂载失败。

### Q4：CSI 为什么要替代 in-tree 插件？

in-tree 插件与 K8s 核心代码耦合，新存储类型需要等 K8s 发版，升级存储插件需要升级整个 K8s。CSI 将存储驱动独立部署，解耦存储与 K8s 版本，让存储厂商自主迭代。

### Q5：StatefulSet 的 volumeClaimTemplates 有什么作用？

为每个 Pod 副本自动创建独立的 PVC。Pod-0 绑定 `data-{sts}-0`，Pod-1 绑定 `data-{sts}-1`，即使 Pod 重建也会挂载回原来的 PVC，保证数据一致性。

### Q6：PVC 扩容需要重启 Pod 吗？

通常不需要。支持 `allowVolumeExpansion: true` 的 StorageClass 可以在线扩容，CSI 驱动先扩展底层存储卷，然后 kubelet 自动扩展文件系统。但对于某些不支持在线扩容的存储类型，可能需要卸载再重新挂载。

### Q7：emptyDir 和 hostPath 有什么区别？

emptyDir 是 Pod 级别的临时存储，随 Pod 创建和删除，不依赖节点路径。hostPath 挂载宿主机路径，数据持久在节点上但 Pod 重调度后无法访问。emptyDir 安全性更高，hostPath 适合 DaemonSet 类应用。

### Q8：如何实现 K8s 存储的灾难恢复？

多层次策略：(1) VolumeSnapshot 做日常快照；(2) Velero 做集群级备份（资源+数据）到对象存储；(3) 数据库层做主从复制或异地备份；(4) 关键业务使用存储层同步复制。RPO/RTO 根据业务需求选择。

### Q9：configMap 挂载的文件更新后容器内会自动同步吗？

作为目录挂载时会自动同步（60-120 秒延迟），因为 kubelet 会定期重新同步 ConfigMap 内容。但使用 `subPath` 挂载单个文件时不会自动更新，因为 subPath 创建的是到特定版本文件的符号链接。需要重启 Pod 才能生效。

### Q10：RWX 模式有哪些限制？

RWX 需要共享文件系统支持（NFS、CephFS、GlusterFS），块存储（EBS、Ceph RBD）不支持。RWX 性能通常不如 RWO，因为需要网络文件系统开销。多 Pod 同时写入同一文件可能需要应用层加锁。

---

## 十、本系列文章知识体系总览

| 期数 | 主题 | 核心要点 |
|------|------|---------|
| 第一期 | K8s 架构核心与集群管理 | 控制平面/数据平面、etcd、kubelet、kubectl 原理 |
| 第二期 | Pod 深入与工作负载管理 | Pod 生命周期、Deployment/StatefulSet/DaemonSet、调度器 |
| 第三期 | Service 与网络通信 | Service 类型、kube-proxy、Ingress、CNI、NetworkPolicy |
| **第四期** | **存储卷与数据持久化** | **Volume 类型、PV/PVC、StorageClass、CSI、StatefulSet 存储** |
| 第五期 | 配置管理与安全（预告） | ConfigMap/Secret 进阶、RBAC、Pod Security、Service Account |

---

## 下期预告

下一篇：**Kubernetes与云原生面试八股文（五）——配置管理与安全** 将深入讲解 ConfigMap/Secret 的高级用法、RBAC 权限模型、Pod Security Standards、Service Account 与 Token 机制、网络策略实战、证书管理与轮转，敬请期待。

---

*作者：飞哥 · Raphael Lab*

*Kubernetes与云原生面试八股文系列*
