---
title: Kubernetes与云原生面试八股文（三）——Service与网络通信
date: 2026-07-31T10:00:00+08:00
updated: '2026-07-31T10:00:00+08:00'
description: 从面试高频问题出发，系统拆解 Service 四种类型与工作原理、kube-proxy 三种模式（userspace/iptables/IPVS）、Endpoints 与 EndpointSlices、Ingress 控制器选型与原理、NetworkPolicy 网络策略、CNI 插件机制与 Pod 间通信完整链路，建立生产级 K8s 网络通信认知。
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 3
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Kubernetes
- K8s
- 云原生
- Service
- 网络
- Ingress
- CNI
categories:
- 分布式与微服务
draft: false
author: 飞哥
---

## Kubernetes与云原生面试八股文（三）——Service与网络通信

### 🎯 本文目标

从面试高频问题出发，系统拆解 K8s Service 的四种类型与底层实现、kube-proxy 的三种代理模式、Endpoints 与 EndpointSlices 的演进、Ingress 控制器的选型与原理、NetworkPolicy 网络安全策略、CNI 插件机制与 Pod 间通信完整链路。帮助你在面试中清晰回答"Service 的 ClusterIP 是怎么工作的""kube-proxy 的 iptables 模式和 IPVS 模式有什么区别""Ingress 和 Service 有什么关系""CNI 插件做了什么""NetworkPolicy 怎么实现网络隔离"。

---

### 一、Service 核心概念：为什么需要 Service？

#### 1.1 问题背景

Pod 是临时的——它们会被创建、销毁、重新调度。每次 Pod 重启，IP 地址都可能变化。如果前端 Pod 直接通过 IP 访问后端 Pod，一旦后端 Pod 重建，前端就会失去连接。

**面试高频问题：Pod IP 不固定，客户端怎么找到 Pod？**

答案就是 Service。Service 提供了一个稳定的访问入口，背后通过标签选择器（Label Selector）自动关联一组 Pod，实现负载均衡和服务发现。

#### 1.2 Service 的本质

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  type: ClusterIP
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8080
    protocol: TCP
```

关键字段解读：

| 字段 | 含义 |
|------|------|
| `spec.type` | Service 类型，决定暴露方式 |
| `spec.selector` | 标签选择器，匹配后端 Pod |
| `spec.ports[].port` | Service 对外暴露的端口 |
| `spec.ports[].targetPort` | Pod 实际监听的端口 |
| `spec.ports[].protocol` | 协议，TCP 或 UDP |

#### 1.3 Service 与 Pod 的关联机制

Service 通过 Label Selector 匹配 Pod，匹配到的 Pod 信息会被写入 Endpoints（或 EndpointSlices）对象。

```
Service (selector: app=backend)
    ↓ 选择
Endpoints (addresses: [10.244.1.5, 10.244.2.3, 10.244.3.8])
    ↓ 对应
Pod-1 (app=backend, IP: 10.244.1.5)
Pod-2 (app=backend, IP: 10.244.2.3)
Pod-3 (app=backend, IP: 10.244.3.8)
```

**注意**：Service 不是直接连 Pod，而是连 Endpoints。Endpoints 是一个独立资源，由控制器自动维护。如果 Pod 不健康（未通过 readinessProbe），会从 Endpoints 中被摘除。

---

### 二、Service 的四种类型

#### 2.1 ClusterIP（默认类型）

ClusterIP 类型的 Service 只在集群内部可访问。K8s 为其分配一个虚拟 IP（ClusterIP），集群内任何 Pod 都可以通过这个 IP 访问服务。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: internal-service
spec:
  type: ClusterIP  # 默认值，可省略
  selector:
    app: backend
  ports:
  - port: 80
    targetPort: 8080
```

**ClusterIP 是虚拟 IP**：它不绑定任何网络接口，仅存在于 iptables/IPVS 规则中。访问 ClusterIP 时，数据包被 NAT 重定向到后端 Pod IP。

**面试要点**：ClusterIP 本质是一条 iptables/IPVS DNAT 规则，不是真实的网络接口。

#### 2.2 NodePort

NodePort 在 ClusterIP 基础上，在每个节点上开放一个固定端口（默认范围 30000-32767），外部可通过 `节点IP:NodePort` 访问服务。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nodeport-service
spec:
  type: NodePort
  selector:
    app: frontend
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30080   # 可选，不指定则随机分配
```

访问链路：

```
外部客户端 → 节点IP:30080 → kube-proxy(iptables/IPVS) → Pod IP:8080
```

**特点**：
- 端口范围可通过 `--service-node-port-range` 配置（默认 30000-32767）
- 任何节点都可以访问，即使 Pod 不在该节点上（会被转发）
- 简单但不够优雅，生产环境通常配合 LoadBalancer 或 Ingress 使用

#### 2.3 LoadBalancer

LoadBalancer 在 NodePort 基础上，自动调用云提供商的 API 创建一个外部负载均衡器（如 AWS ELB、阿里云 SLB），并将流量导到 NodePort。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: lb-service
spec:
  type: LoadBalancer
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 8080
  externalTrafficPolicy: Cluster  # 或 Local
```

**externalTrafficPolicy 关键字段**：

| 值 | 行为 | 特点 |
|----|------|------|
| `Cluster`（默认） | 流量可能跨节点转发 | 全局负载均衡，但可能 SNAT 丢失源 IP |
| `Local` | 流量只发给本节点 Pod | 保留客户端真实 IP，但负载可能不均 |

**面试高频问题：externalTrafficPolicy: Local 和 Cluster 的区别？**

- **Cluster 模式**：请求到达任一节点后，kube-proxy 可能将其转发到其他节点的 Pod。好处是负载均衡更好，坏处是做了 SNAT，后端看到的是节点 IP 而非客户端 IP。
- **Local 模式**：请求只发给本节点的 Pod，不跨节点转发。好处是保留客户端真实源 IP，坏处是如果本节点没有 Pod，请求会失败（需要配合节点亲和或外部 LB 健康检查）。

#### 2.4 ExternalName

ExternalName 是一个特殊的 Service 类型，它不配置 Pod 选择器，而是通过 DNS CNAME 记录将服务名映射到外部域名。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-db
spec:
  type: ExternalName
  externalName: db.example.com
```

访问 `external-db.default.svc.cluster.local` 会被 DNS 解析为 `db.example.com`。

**用途**：将外部服务封装为 K8s Service，方便后续切换为内部服务——只需修改 Service 配置，应用代码不用改。

#### 2.5 四种类型对比

| 类型 | 访问范围 | 底层机制 | 典型场景 |
|------|----------|----------|----------|
| ClusterIP | 集群内部 | iptables/IPVS DNAT | 内部服务互调 |
| NodePort | 集群外部（节点IP:端口） | ClusterIP + 节点端口监听 | 测试/演示 |
| LoadBalancer | 公网 | NodePort + 云 LB | 生产对外暴露 |
| ExternalName | 外部域名 | DNS CNAME | 外部服务引用 |

---

### 三、kube-proxy：Service 的实现引擎

#### 3.1 kube-proxy 是什么

kube-proxy 是运行在每个节点上的组件，负责将 Service 的虚拟 IP 规则写入节点的 iptables 或 IPVS 中，使访问 Service IP 的流量能正确转发到后端 Pod。

**面试高频问题：kube-proxy 的作用是什么？**

kube-proxy 监听 API Server 中 Service 和 Endpoints 的变化，实时更新节点上的转发规则。它是 Service 从"声明"到"生效"的桥梁。

#### 3.2 三种代理模式

##### userspace 模式（已弃用）

```
客户端 Pod → kube-proxy(userspace) → 后端 Pod
```

- kube-proxy 在用户态监听端口，自己做负载均衡
- 每次请求都经过用户态拷贝，性能差
- K8s 1.2 之前默认，现已弃用

**面试只需要知道：性能最差，已淘汰。**

##### iptables 模式（默认）

```
客户端 Pod → iptables DNAT → 后端 Pod
```

- kube-proxy 将转发规则写入 iptables
- 数据包在内核态处理，无需经过用户态
- 性能远优于 userspace

iptables 规则链示例（简化）：

```
# Service 链
KUBE-SVC-XXX:
  - 统计概率跳转到后端 Pod 链
  - 1/3 → KUBE-SEP-Pod1 (DNAT → 10.244.1.5:8080)
  - 1/3 → KUBE-SEP-Pod2 (DNAT → 10.244.2.3:8080)
  - 1/3 → KUBE-SEP-Pod3 (DNAT → 10.244.3.8:8080)
```

**负载均衡方式**：iptables 使用随机概率（`statistic` 模块）实现负载均衡，不是轮询。

**iptables 模式的问题**：
- 规则数与 Service×Pod 数量成正比，大规模集群下规则可达数万条
- iptables 规则是线性匹配，O(n) 复杂度
- 更新规则需要全量替换，频繁变更时延迟较大

##### IPVS 模式（推荐大规模使用）

```
客户端 Pod → IPVS → 后端 Pod
```

- 基于 Linux 内核 IPVS（IP Virtual Server）模块
- 支持多种负载均衡算法：轮询（rr）、最小连接（lc）、源地址哈希（sh）等
- 使用哈希表查找，O(1) 复杂度
- 大规模集群性能远优于 iptables

**面试高频问题：iptables 模式和 IPVS 模式的区别？**

| 维度 | iptables | IPVS |
|------|----------|------|
| 数据结构 | 线性规则链 | 哈希表 |
| 查找复杂度 | O(n) | O(1) |
| 负载均衡 | 随机概率 | rr/lc/sh 等 10 种算法 |
| 规则更新 | 全量替换 | 增量更新 |
| 大规模性能 | 万级 Service 后明显下降 | 十万级 Service 仍稳定 |
| 内核依赖 | iptables 模块 | ip_vs, ip_vs_rr 等模块 |

**如何切换到 IPVS 模式**：

修改 kube-proxy 配置：

```yaml
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
mode: "ipvs"
ipvs:
  scheduler: "lc"  # 最小连接数
```

#### 3.3 kube-proxy 的会话保持

Service 默认是轮询负载均衡，但有些场景需要会话保持（同一个客户端总是访问同一个后端 Pod）。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: sticky-service
spec:
  type: ClusterIP
  selector:
    app: backend
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800  # 默认 3 小时
  ports:
  - port: 80
    targetPort: 8080
```

**实现原理**：
- iptables 模式：使用 `recent` 模块记录客户端 IP 最近访问的后端
- IPVS 模式：使用 `sh`（source hashing）调度算法

---

### 四、Endpoints 与 EndpointSlices

#### 4.1 Endpoints

Endpoints 是 Service 自动创建的资源，记录 Service 关联的后端 Pod IP 列表。

```bash
kubectl get endpoints backend-service
```

```yaml
apiVersion: v1
kind: Endpoints
metadata:
  name: backend-service
subsets:
- addresses:
  - ip: 10.244.1.5
  - ip: 10.244.2.3
  - ip: 10.244.3.8
  ports:
  - port: 8080
    protocol: TCP
```

#### 4.2 EndpointSlices（取代 Endpoints）

Endpoints 有一个致命问题：单个 Endpoints 对象存储所有后端地址。当后端 Pod 达到数千个时，每次变更都需要传输整个对象，给 API Server 和 etcd 带来巨大压力。

EndpointSlices 将端点信息切分为多个小对象，每个对象最多 100 个端点：

```yaml
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: backend-service-abc12
  labels:
    kubernetes.io/service-name: backend-service
addressType: IPv4
endpoints:
- addresses:
  - 10.244.1.5
  conditions:
    ready: true
  targetRef:
    kind: Pod
    name: backend-5f4d-xxx
- addresses:
  - 10.244.2.3
  conditions:
    ready: true
  targetRef:
    kind: Pod
    name: backend-5f4d-yyy
ports:
- port: 8080
  protocol: TCP
```

**面试要点**：

| 维度 | Endpoints | EndpointSlices |
|------|-----------|----------------|
| 结构 | 单一大对象 | 多个小对象（每片≤100） |
| 更新开销 | 全量更新 | 增量更新 |
| 扩展性 | 千级 Pod 后性能差 | 万级 Pod 仍流畅 |
| API 版本 | v1（核心 API） | discovery.k8s.io/v1 |
| 默认启用 | K8s < 1.21 | K8s ≥ 1.21 |

**面试高频问题：Endpoints 和 EndpointSlices 有什么区别？**

EndpointSlices 是 Endpoints 的替代品，通过分片解决了大规模服务的端点传播问题。K8s 1.21+ 默认使用 EndpointSlices。

---

### 五、Headless Service：没有 ClusterIP 的 Service

#### 5.1 什么是 Headless Service

设置 `clusterIP: None` 的 Service 称为 Headless Service。它不分配 ClusterIP，不做负载均衡，直接返回后端 Pod IP 列表。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: headless-service
spec:
  clusterIP: None  # 关键：Headless
  selector:
    app: stateful-app
  ports:
  - port: 80
    targetPort: 8080
```

#### 5.2 DNS 行为对比

| Service 类型 | DNS 查询结果 |
|-------------|-------------|
| 普通 ClusterIP Service | 返回 ClusterIP |
| Headless Service | 返回所有 Pod IP（A 记录多条） |

```bash
# 普通 Service
$ nslookup normal-service.default.svc.cluster.local
Name: normal-service.default.svc.cluster.local
Address: 10.96.0.100  # ClusterIP

# Headless Service
$ nslookup headless-service.default.svc.cluster.local
Name: headless-service.default.svc.cluster.local
Address: 10.244.1.5  # Pod-1 IP
Address: 10.244.2.3  # Pod-2 IP
Address: 10.244.3.8  # Pod-3 IP
```

#### 5.3 Headless Service 的典型场景

**场景一：StatefulSet 的稳定网络标识**

StatefulSet 配合 Headless Service，每个 Pod 获得稳定的 DNS 名：

```
pod-name.headless-service-name.namespace.svc.cluster.local
# 例如：
stateful-app-0.headless-service.default.svc.cluster.local → 10.244.1.5
stateful-app-1.headless-service.default.svc.cluster.local → 10.244.2.3
stateful-app-2.headless-service.default.svc.cluster.local → 10.244.3.8
```

即使 Pod 重建，DNS 名字不变（指向新的 IP）。这是 StatefulSet 有状态应用（如 MySQL 主从、ZooKeeper 集群）的基础。

**场景二：客户端自行负载均衡**

某些客户端（如 gRPC）自带负载均衡能力，不需要 K8s Service 做 LB。Headless Service 返回所有 Pod IP，客户端自行选择。

---

### 六、Ingress：HTTP 层的服务暴露

#### 6.1 为什么需要 Ingress

LoadBalancer 类型的 Service 每个服务都需要一个云负载均衡器，成本高。NodePort 端口有限且暴露端口过多。Ingress 在 HTTP/HTTPS 层面提供路由，一个入口可以路由到多个服务。

```
                    ┌──→ Service-A → Pod-A
客户端 → Ingress ──┼──→ Service-B → Pod-B
                    └──→ Service-C → Pod-C
```

#### 6.2 Ingress 资源定义

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: tls-secret
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /users
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 80
      - path: /orders
        pathType: Prefix
        backend:
          service:
            name: order-service
            port:
              number: 80
```

**关键字段**：

| 字段 | 含义 |
|------|------|
| `spec.ingressClassName` | 指定使用的 Ingress Controller |
| `spec.tls` | HTTPS 证书配置 |
| `spec.rules[].host` | 域名匹配 |
| `spec.rules[].http.paths[].path` | 路径匹配 |
| `pathType` | Prefix（前缀匹配）/ Exact（精确匹配）/ ImplementationSpecific |

#### 6.3 Ingress Controller

Ingress 资源本身只是路由规则，需要 Ingress Controller 来实际执行。常见控制器：

| 控制器 | 特点 | 适用场景 |
|--------|------|----------|
| NGINX Ingress | 最流行，社区活跃，功能全面 | 通用场景 |
| Traefik | 自动服务发现，Let's Encrypt 集成 | 云原生/微服务 |
| HAProxy Ingress | 高性能，丰富负载均衡算法 | 高并发 |
| Envoy Gateway | 基于 Envoy，强大过滤链 | Service Mesh |
| AWS ALB Ingress | 云原生集成 AWS ALB | AWS 环境 |

**面试高频问题：Ingress 和 Service 有什么关系？**

Ingress 不是替代 Service，而是在 Service 之上增加了一层 HTTP 路由。Ingress Controller 本身也是一个 Pod（通过 NodePort 或 LoadBalancer Service 暴露），它读取 Ingress 规则，将 HTTP 请求路由到对应的 Service，Service 再转发到 Pod。

完整链路：

```
客户端 → LB/NodePort → Ingress Controller Pod → Service → 后端 Pod
```

#### 6.4 Ingress 与 IngressClass

K8s 1.18+ 引入了 IngressClass，用于区分不同的 Ingress Controller 实例：

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
spec:
  controller: k8s.io/ingress-nginx
```

每个 Ingress 通过 `ingressClassName` 字段选择使用的控制器。这样可以同时运行多套 Ingress Controller（如内网用 NGINX，外网用云 LB）。

---

### 七、NetworkPolicy：网络安全策略

#### 7.1 为什么需要 NetworkPolicy

默认情况下，K8s 集群中所有 Pod 之间网络是互通的——任何 Pod 都可以访问任何其他 Pod。这在生产环境中是安全隐患。NetworkPolicy 提供了 Pod 级别的网络访问控制。

#### 7.2 NetworkPolicy 定义

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 3306
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

**关键概念**：

- `podSelector`：选择受策略保护的 Pod（策略目标）
- `policyTypes`：指定 Ingress（入站）/ Egress（出站）策略
- `ingress.from`：允许哪些来源访问
- `egress.to`：允许访问哪些目标

#### 7.3 默认策略与白名单模式

NetworkPolicy 是**白名单模型**：一旦 Pod 被 NetworkPolicy 选中，只有规则明确允许的流量才能通过，其他全部拒绝。

**常见默认策略**：

```yaml
# 1. 默认拒绝所有入站
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
spec:
  podSelector: {}   # 选中所有 Pod
  policyTypes:
  - Ingress

# 2. 默认拒绝所有出站
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
spec:
  podSelector: {}
  policyTypes:
  - Egress

# 3. 默认拒绝所有入站和出站
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

#### 7.4 NetworkPolicy 的实现依赖

**重要**：NetworkPolicy 是 API 层面的声明，实际执行依赖 CNI 插件。

| CNI 插件 | 支持 NetworkPolicy |
|----------|-------------------|
| Calico | ✅ 完整支持 |
| Cilium | ✅ 完整支持（基于 eBPF） |
| Weave Net | ✅ 支持 |
| Flannel | ❌ 原生不支持（需配合 Calico） |
| Calico + Flannel（Canal） | ✅ 支持 |

**面试要点**：如果 CNI 插件不支持 NetworkPolicy，创建了 NetworkPolicy 也不会生效。Flannel 需要配合 Calico（即 Canal 方案）才能使用 NetworkPolicy。

---

### 八、CNI 插件：Pod 网络的底层基础设施

#### 8.1 什么是 CNI

CNI（Container Network Interface）是 K8s 的容器网络接口规范。当 Pod 被创建时，Kubelet 调用 CNI 插件为 Pod 分配 IP 地址、配置网络接口，使 Pod 可以与集群中其他 Pod 通信。

**面试高频问题：CNI 插件的作用是什么？**

CNI 插件负责：
1. 为 Pod 分配 IP 地址（IPAM）
2. 配置 Pod 的虚拟网卡（veth pair）
3. 配置路由规则使 Pod 之间可通信
4. 实现 NetworkPolicy（部分插件）

#### 8.2 Pod 网络模型

K8s 网络模型的核心要求：

1. **每个 Pod 有独立 IP**：不需要 NAT
2. **Pod 之间直接通信**：通过 Pod IP 互访，不需要中间代理
3. **Node 与 Pod 之间直接通信**：节点可以访问本节点和其他节点的 Pod
4. **跨节点 Pod 通信**：由 CNI 插件实现

#### 8.3 常见 CNI 插件对比

| 插件 | 模式 | 特点 | NetworkPolicy | 适用场景 |
|------|------|------|---------------|----------|
| Flannel | Overlay (VXLAN) | 简单稳定，最基础的方案 | ❌ | 小型集群/学习 |
| Calico | BGP / Overlay | 高性能，支持 BGP 路由 | ✅ | 生产环境 |
| Cilium | eBPF | 基于 eBPF，无需 iptables | ✅ | 大规模/高性能 |
| Weave Net | Overlay | 简单易用，加密通信 | ✅ | 中小集群 |
| Canal | Flannel + Calico | Flannel 网络 + Calico 策略 | ✅ | 兼顾简单与安全 |

**面试高频问题：Flannel 和 Calico 有什么区别？**

| 维度 | Flannel | Calico |
|------|---------|--------|
| 网络模式 | VXLAN Overlay | BGP（可 Overlay） |
| 性能 | VXLAN 封装有开销 | BGP 直通，性能更好 |
| NetworkPolicy | 不支持 | 支持 |
| 路由 | 每节点一个子网 | 每个 Pod 可独立路由 |
| 复杂度 | 简单 | 较复杂 |
| 适用规模 | 小中型 | 中大型 |

#### 8.4 CNI 工作流程

当 Pod 被调度到节点时：

```
1. Kubelet 创建 Pod 的 network namespace
2. Kubelet 调用 CNI 插件（根据 /etc/cni/net.d/ 配置）
3. CNI 插件执行：
   a. IPAM：从配置的 IP 池中分配一个 Pod IP
   b. 创建 veth pair：一端在 Pod namespace，一端在宿主机
   c. 配置 Pod 内网卡 IP 和路由
   d. 配置宿主机路由规则（使跨节点 Pod 可达）
4. Pod 网络就绪
```

以 Calico 为例：

```
Pod (10.244.1.5) ←→ veth pair ←→ 宿主机 ←→ BGP 路由 ←→ 其他节点上的 Pod
```

---

### 九、DNS 服务发现

#### 9.1 CoreDNS

K8s 集群内置 CoreDNS 作为集群 DNS 服务。每个 Pod 默认使用 CoreDNS 进行服务名解析。

CoreDNS 配置（ConfigMap）：

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
        }
        prometheus :9153
        forward . /etc/resolv.conf
        cache 30
        loop
        reload
        loadbalance
    }
```

#### 9.2 DNS 解析规则

K8s 中的 DNS 解析遵循以下格式：

```
<service-name>.<namespace>.svc.cluster.local
```

| DNS 名 | 解析结果 | 说明 |
|--------|----------|------|
| `backend-service` | ClusterIP | 同 namespace 内简写 |
| `backend-service.production` | ClusterIP | 跨 namespace |
| `backend-service.production.svc.cluster.local` | ClusterIP | 完整 FQDN |
| `headless-svc.production.svc.cluster.local` | 所有 Pod IP | Headless Service |
| `pod-ip-dash.default.pod.cluster.local` | Pod IP | Pod 的 DNS（IP 中的 . 替换为 -） |

**面试要点**：Service 的 DNS 名是稳定的，不管后端 Pod 怎么变化。这是服务发现的核心机制。

#### 9.3 Pod 的 DNS 配置

每个 Pod 默认的 DNS 配置（`/etc/resolv.conf`）：

```
nameserver 10.96.0.10       # CoreDNS 的 ClusterIP
search default.svc.cluster.local svc.cluster.local cluster.local
options ndots:5
```

**ndots:5 的含义**：如果查询的域名包含的 dots 少于 5 个，会先尝试拼接 search domain。例如查询 `backend-service`，CoreDNS 会依次尝试：

1. `backend-service.default.svc.cluster.local`
2. `backend-service.svc.cluster.local`
3. `backend-service.cluster.local`
4. `backend-service`

**面试陷阱**：ndots:5 导致短域名查询可能触发多次 DNS 查询。建议在跨 namespace 访问时直接使用完整 `service.namespace` 格式。

---

### 十、Pod 间通信完整链路

#### 10.1 同节点 Pod 通信

```
Pod-A (10.244.1.5) → veth-a → 宿主机网桥/cni0 → veth-b → Pod-B (10.244.1.6)
```

同节点 Pod 通过 veth pair 连接到同一个网桥（如 cni0），直接二层转发。

#### 10.2 跨节点 Pod 通信

**Flannel (VXLAN 模式)**：

```
Pod-A (Node-1, 10.244.1.5)
  → veth pair → cni0 网桥
  → flannel.1 (VXLAN 封装)
  → 物理网络 (Node-1 IP → Node-2 IP)
  → flannel.1 (VXLAN 解封)
  → cni0 网桥
  → veth pair
  → Pod-B (Node-2, 10.244.2.3)
```

**Calico (BGP 模式)**：

```
Pod-A (Node-1, 10.244.1.5)
  → veth pair → 宿主机路由表
  → BGP 路由 (目的: 10.244.2.0/24 → Node-2)
  → 物理网络 (Node-1 → Node-2)
  → 宿主机路由表
  → veth pair
  → Pod-B (Node-2, 10.244.2.3)
```

**区别**：Flannel 通过 VXLAN 封装数据包（增加 50 字节开销），Calico BGP 模式直接路由，无封装开销。

#### 10.3 Service 访问的完整链路

从 Pod-A 访问 `backend-service:80` 的完整链路：

```
1. Pod-A 发起请求: backend-service:80
2. CoreDNS 解析 → 返回 ClusterIP (10.96.0.100)
3. Pod-A 向 10.96.0.100:80 发送数据包
4. 数据包到达节点的 iptables/IPVS 规则
5. kube-proxy 规则 DNAT: 10.96.0.100:80 → 10.244.2.3:8080 (后端 Pod)
6. 数据包路由到后端 Pod（可能跨节点）
7. 后端 Pod 处理请求并返回响应
```

---

### 十一、高频面试题速查

#### Q1: Service 的 ClusterIP 是怎么工作的？

ClusterIP 是一个虚拟 IP，不绑定任何网络接口。它通过 iptables 或 IPVS 的 DNAT 规则实现——访问 ClusterIP 的数据包会被重写目标地址为后端 Pod IP。整个过程在内核态完成。

#### Q2: kube-proxy 的 iptables 和 IPVS 模式有什么区别？

iptables 使用线性规则链（O(n) 查找），随机概率做负载均衡，大规模下规则数量爆炸。IPVS 使用哈希表（O(1) 查找），支持 rr/lc/sh 等多种调度算法，大规模性能更优。

#### Q3: Ingress 和 Service 有什么关系？

Ingress 是在 Service 之上的 HTTP 层路由。Ingress Controller 读取 Ingress 规则，将请求路由到对应 Service，Service 再转发到 Pod。Ingress 不是替代 Service，而是补充。

#### Q4: Headless Service 什么时候用？

两种场景：1) StatefulSet 需要为每个 Pod 提供稳定 DNS 名；2) 客户端自带负载均衡（如 gRPC），不需要 K8s 做 LB。

#### Q5: NetworkPolicy 如何实现网络隔离？

NetworkPolicy 是白名单模型——选中 Pod 后，只有明确允许的流量才能通过。实际执行依赖 CNI 插件（如 Calico、Cilium）。Flannel 原生不支持 NetworkPolicy。

#### Q6: CNI 插件做了什么？

CNI 插件在 Pod 创建时为其分配 IP、创建虚拟网卡、配置路由规则，使 Pod 可以与集群内其他 Pod 通信。不同 CNI 的实现方式不同（Flannel 用 VXLAN 封装，Calico 用 BGP 路由，Cilium 用 eBPF）。

#### Q7: Endpoints 和 EndpointSlices 有什么区别？

Endpoints 用单个对象存储所有后端地址，大规模下更新开销大。EndpointSlices 将端点切分为多个小对象（每片≤100），支持增量更新，K8s 1.21+ 默认使用。

#### Q8: externalTrafficPolicy: Local 和 Cluster 有什么区别？

Cluster 模式流量可能跨节点转发，做 SNAT，后端看不到客户端真实 IP。Local 模式只转发到本节点 Pod，保留客户端真实 IP，但负载可能不均匀。

---

### 十二、知识体系总结

| 主题 | 核心要点 |
|------|----------|
| Service 四种类型 | ClusterIP（内部）、NodePort（节点端口）、LoadBalancer（云 LB）、ExternalName（DNS CNAME） |
| kube-proxy 三种模式 | userspace（弃用）、iptables（默认）、IPVS（大规模推荐） |
| Endpoints vs EndpointSlices | 单对象 vs 分片，EndpointSlices 更适合大规模集群 |
| Headless Service | 无 ClusterIP，DNS 返回 Pod IP，用于 StatefulSet 和客户端自 LB |
| Ingress | HTTP 层路由，一个入口路由到多个 Service，需 Ingress Controller 执行 |
| NetworkPolicy | Pod 级白名单网络策略，依赖 CNI 插件执行 |
| CNI 插件 | Pod 网络基础设施，负责 IP 分配和跨节点通信（Flannel/Calico/Cilium） |
| DNS 服务发现 | CoreDNS 提供稳定的 Service DNS 名，ndots:5 影响解析行为 |

**学习建议**：

1. **概念层**：理解 Service 为什么存在（Pod IP 不固定）、四种类型的区别
2. **原理层**：掌握 iptables/IPVS 的 DNAT 机制、CNI 的网络模型
3. **配置层**：能写完整的 Service + Ingress + NetworkPolicy 配置
4. **面试层**：能流畅回答 kube-proxy 模式对比、Ingress 与 Service 关系、CNI 选型

---

## 下期预告

下一篇：**Kubernetes与云原生面试八股文（四）——存储卷与数据持久化** 将深入讲解 Volume 类型体系（emptyDir/hostPath/configMap/secret/PVC/PV）、StorageClass 动态供给、CSI 插件机制、StatefulSet 的存储管理、数据备份与恢复策略，敬请期待。

---

*作者：飞哥 · Raphael Lab*

*Kubernetes与云原生面试八股文系列*
