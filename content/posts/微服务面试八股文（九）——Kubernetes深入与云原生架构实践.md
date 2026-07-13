---
title: "微服务面试八股文（九）——Kubernetes深入与云原生架构实践"
date: 2026-07-13T10:00:00+08:00
draft: false
categories: ["微服务", "Spring Cloud"]
tags: ["面试", "八股文", "微服务", "Kubernetes", "K8s", "云原生", "Docker", "Helm", "StatefulSet", "ConfigMap", "Secret", "RBAC", "NetworkPolicy", "12-Factor", "Cloud Native", "YAML", "kubectl", "Ingress", "Service Mesh", "Sidecar", "Istio"]
author: "飞哥"
---

# 微服务面试八股文（九）——Kubernetes深入与云原生架构实践

> 🎯 **本文目标**：承接微服务容器化与部署实战，深入解析 Kubernetes 核心概念与进阶用法——Pod 生命周期与调度、StatefulSet 有状态部署、RBAC 权限模型、NetworkPolicy 网络策略、Helm 包管理，以及云原生 12-Factor 设计原则，构建生产级 Kubernetes 运维能力。

---

## 一、Kubernetes 架构全景：从节点到集群

### 1.1 集群核心组件

```
┌──────────────────────────────────────────────────────────────┐
│                        Control Plane                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────┐ │
│  │ API Server │  │ Scheduler  │  │Controller  │  │ etcd│ │
│  │ (统一入口)  │  │ (调度Pod)  │  │Manager(控制)│  │(状态)│ │
│  └────────────┘  └────────────┘  └────────────┘  └─────┘ │
└──────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         ┌────────┐      ┌────────┐      ┌────────┐
         │Worker 1│      │Worker 2│      │Worker 3│
         │  kubelet│      │  kubelet│      │  kubelet│
         │ kube-proxy│    │ kube-proxy│    │ kube-proxy│
         │  Docker │      │  Docker │      │  Docker │
         │  Pod A  │      │  Pod C  │      │  Pod E  │
         │  Pod B  │      │  Pod D  │      │  Pod F  │
         └────────┘      └────────┘      └────────┘

核心组件职责：
• API Server：集群统一入口，处理所有 REST 请求，是唯一与 etcd 通信的组件
• Scheduler：监听未调度 Pod，为其分配合适的 Worker 节点（考虑资源、亲和性等）
• Controller Manager：运行各种控制器（Deployment/ReplicaSet/StatefulSet...），
  确保期望状态与实际状态一致
• kubelet：运行在每个 Worker 节点，负责创建/销毁 Pod、管理容器
• kube-proxy：维护网络规则，实现 Service 的负载均衡
• etcd：分布式一致性 KV 存储，保存集群所有状态数据（Raft 协议保证一致性）
```

### 1.2 核心概念关系图

```
Namespace（命名空间）← 逻辑隔离，不同团队/环境
    │
    └── Deployment（无状态应用）→ 管理 ReplicaSet → 管理 Pod
    │   └── 滚动更新、回滚、扩缩容
    │
    └── StatefulSet（有状态应用）→ 管理 Pod（有序号）
    │   └── 稳定的网络标识、稳定的存储、有序部署/扩缩容
    │
    └── DaemonSet（每个节点一个 Pod）→ 日志收集、监控 Agent
    │
    └── Job / CronJob（批处理任务）
    │
    └── Service（服务发现与负载均衡）
    │   ├── ClusterIP（集群内部访问）
    │   ├── NodePort（节点端口映射）
    │   ├── LoadBalancer（云厂商负载均衡器）
    │   └── ExternalName（DNS 别名）
    │
    └── Ingress（HTTP/HTTPS 七层路由）
    │
    └── ConfigMap / Secret（配置管理）
    │
    └── Volume（持久化存储）
```

---

## 二、Pod 深度解析：生命周期与调度机制

### 2.1 Pod 生命周期状态机

```
                    ┌────────────┐
                    │   Pending  │
                    │  (Pod被API Server接收，
                    │   容器镜像可能还在下载)
                    └─────┬──────┘
                          │ Scheduler 分配到 Node
                          ▼
              ┌──────────────────────────────┐
              │ ContainerCreating            │
              │ (Init Container 执行中...)   │
              └──────────────┬───────────────┘
                             │ Init Container 全部成功
                             ▼
              ┌──────────────────────────────┐
              │         Running               │
              │ (至少一个容器已启动，可接收流量)│
              │ ┌──────────────────────────┐ │
              │ │ PostStart Hook 执行中... │ │
              │ │ 主容器 Running           │ │
              │ │ PreStop Hook 待执行...  │ │
              │ └──────────────────────────┘ │
              └──────────────┬───────────────┘
                             │ 容器进程退出 / liveness 探针失败
                             ▼
              ┌──────────────────────────────┐
              │        Succeeded / Failed     │
              │ Succeeded：正常退出（Job等）  │
              │ Failed：异常退出（OOMKilled等）│
              └──────────────────────────────┘

Init Container vs Main Container 的关键区别：
1. Init Container 必须全部成功，主容器才能启动（串行执行）
2. Init Container 总是先于主容器执行
3. Init Container 不支持探针（liveness/readiness/startup）
4. 典型用途：注册到服务发现、等待数据库就绪、初始化配置、预热缓存
```

### 2.2 探针类型与健康检查

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: order-service
spec:
  containers:
  - name: order-container
    image: order-service:v1.0
    # 启动探针：容器启动后需要warmup时间，初期允许慢启动
    startupProbe:
      httpGet:
        path: /actuator/health/startup
        port: 8080
      failureThreshold: 30      # 最多失败30次
      periodSeconds: 10         # 每10秒检查一次
      # 意味着容器最多有300秒warmup时间
    # 存活探针：判断容器是否需要重启（进程存活）
    livenessProbe:
      httpGet:
        path: /actuator/health/liveness
        port: 8080
      initialDelaySeconds: 30   # 等待30秒后开始探测（让应用启动）
      periodSeconds: 10
      failureThreshold: 3
    # 就绪探针：判断容器是否可以接收流量（会影响 Endpoints）
    readinessProbe:
      httpGet:
        path: /actuator/health/readiness
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
      failureThreshold: 2

# 探针选择原则：
# livenessProbe：只检测进程是否存活，不做深度检查（避免误杀）
# readinessProbe：检测服务是否就绪（依赖下游服务），就绪前不放流量
# startupProbe：为慢启动应用设计，warmup期间其他探针不生效
```

### 2.3 Pod 调度策略

```yaml
# 节点亲和性：Pod 更喜欢/必须调度到特定节点
apiVersion: v1
kind: Pod
metadata:
  name: order-service
spec:
  affinity:
    # 节点亲和性：Pod 偏好调度到高性能节点
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        preference:
          matchExpressions:
          - key: node-type
            operator: In
            values: ["high-compute"]
    # Pod 亲和性：此 Pod 希望能和 redis Pod 在同一拓扑域
    podAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 80
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app: redis
          topologyKey: topology.kubernetes.io/zone
    # Pod 反亲和性：不要和同类 Pod 在同一节点（高可用）
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app: order-service
        topologyKey: kubernetes.io/hostname

# 污点与容忍：节点主动排斥 Pod
# 节点打污点（运维场景）：
apiVersion: v1
kind: Node
metadata:
  name: worker-node-3
spec:
  taints:
  - key: "dedicated"
    value: "ml-training"
    effect: "NoSchedule"  # 不调度 / 不运行 / 不运行但可驱逐
# Pod 添加容忍才能调度到该节点：
spec:
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "ml-training"
    effect: "NoSchedule"

# 资源请求与限制
spec:
  containers:
  - name: order-service
    resources:
      requests:           # 调度依据：节点必须满足这么多资源
        memory: "512Mi"
        cpu: "500m"
      limits:            # 硬限制：超过即 OOMKill 或限流
        memory: "1Gi"
        cpu: "2000m"
```

---

## 三、StatefulSet：有状态应用的正确打开方式

### 3.1 StatefulSet vs Deployment 的本质区别

```
┌─────────────────────────────────────────────────────────────┐
│                    Deployment（无状态）                       │
├─────────────────────────────────────────────────────────────┤
│ Pod 名称：无序，随机生成                                     │
│ pod-6d8fb7c5-xk4mp                                          │
│                                                              │
│ 存储：共享存储（emptyDir）或 PVC（无绑定关系）               │
│                                                              │
│ 扩缩容：随机创建/销毁，任意顺序                              │
│                                                              │
│ 网络标识：不稳定，IP 会变                                   │
│                                                              │
│ 适用：无状态服务（Web 服务、API 服务）                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   StatefulSet（有状态）                       │
├─────────────────────────────────────────────────────────────┤
│ Pod 名称：有序，固定命名                                     │
│ mysql-0（主）、mysql-1（从）、mysql-2（从）                   │
│                                                              │
│ 存储：每个 Pod 有独立 PVC，序号与 Pod 绑定                   │
│ mysql-pvc-mysql-0 / mysql-pvc-mysql-1 / mysql-pvc-mysql-2   │
│                                                              │
│ 扩缩容：严格按序号顺序创建/销毁（0→1→2 创建，2→1→0 销毁）  │
│                                                              │
│ 网络标识：稳定的 Headless Service DNS，永久固定              │
│ mysql-0.mysql-headless.default.svc.cluster.local            │
│                                                              │
│ 适用：数据库、消息队列、分布式存储、需要有序启停的服务        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 StatefulSet 实战：部署 MySQL 主从集群

```yaml
# Headless Service：为 StatefulSet 提供稳定的网络标识
apiVersion: v1
kind: Service
metadata:
  name: mysql-headless
spec:
  clusterIP: None   # Headless Service = 无 ClusterIP
  selector:
    app: mysql
  ports:
  - name: mysql
    port: 3306

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mysql
spec:
  serviceName: "mysql-headless"  # 必须与 Headless Service 名称一致
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
      # 初始化脚本：配置主从关系
      - name: init-mysql
        image: mysql:8.0
        command:
        - bash
        - "-c"
        - |
          # 获取当前 Pod 的序号
          set -ex
          [[ $(hostname) =~ -([0-9]+)$ ]] || exit 1
          ordinal=${BASH_REMATCH[1]}
          # 生成 server-id（每个节点唯一）
          echo server-id=$((ordinal + 1)) > /mnt/conf.d/server-id.cnf
          # 如果不是第一个节点，配置为只读（从库）
          if [[ $ordinal -gt 0 ]]; then
            echo "read_only=ON" >> /mnt/conf.d/server-id.cnf
          fi
        volumeMounts:
        - name: conf
          mountPath: /mnt/conf.d
      containers:
      - name: mysql
        image: mysql:8.0
        ports:
        - name: mysql
          containerPort: 3306
        volumeMounts:
        - name: data
          mountPath: /var/lib/mysql
        - name: conf
          mountPath: /etc/mysql/conf.d
        env:
        - name: MYSQL_ROOT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: mysql-secret
              key: root-password
  volumeClaimTemplates:   # 为每个 Pod 创建独立 PVC
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "ssd-storageclass"
      resources:
        requests:
          storage: 50Gi

# StatefulSet 扩缩容注意事项：
# • 扩容：从 mysql-0 到 mysql-N 逐个启动，等待前一个 Ready 后再启动下一个
# • 缩容：必须从 N 到 0 逐个缩，且要提前清理数据（防止数据丢失）
# • 不可缩减到 0：StatefulSet 不允许删除所有副本（防止意外删除）
```

---

## 四、ConfigMap 与 Secret：配置管理最佳实践

### 4.1 ConfigMap 的四种创建方式

```bash
# 方式1：从文件创建（文件名作为 key，文件内容作为 value）
kubectl create configmap app-config \
  --from-file=application.yml

# 方式2：指定 key=value 对
kubectl create configmap env-config \
  --from-literal=ENV=production \
  --from-literal=LOG_LEVEL=info

# 方式3：从目录（目录下所有文件）
kubectl create configmap html-config \
  --from-file=/path/to/static/

# 方式4：从 .env 文件批量导入
kubectl create configmap db-config \
  --from-env-file=database.env
```

### 4.2 ConfigMap 的三种挂载方式对比

```yaml
# 方式1：环境变量注入（值直接注入，不支持热更新）
spec:
  containers:
  - name: order-service
    env:
    - name: DATABASE_HOST
      valueFrom:
        configMapKeyRef:
          name: db-config
          key: host
    - name: ALL_CONFIG    # 一次性注入所有 key 为 JSON
      valueFrom:
        configMapKeyRef:
          name: db-config
          optional: true   # ConfigMap 不存在也不报错

# 方式2：环境变量引用（整个 ConfigMap 所有 key 注入为环境变量）
spec:
  containers:
  - name: order-service
    envFrom:
    - configMapRef:
        name: db-config
      prefix: "DB_"  # 所有 key 加前缀

# 方式3：Volume 挂载（文件形式挂载，支持热更新，推荐方式）
spec:
  containers:
  - name: order-service
    volumeMounts:
    - name: config
      mountPath: /app/config
      readOnly: true
    - name: config2
      mountPath: /app/config/application.yml
      subPath: application.yml  # 只挂载单个文件，不影响同目录其他文件
  volumes:
  - name: config
    configMap:
      name: app-config
      items:              # 指定 key 映射
      - key: "application.yml"
        path: "application.yml"
      defaultMode: 0644
```

### 4.3 Secret 类型与安全最佳实践

```
Secret 四种类型：

┌────────────┬────────────────────────────┐
│ Opaque     │ 通用 Secret（base64 编码）  │ ← 最常用
├────────────┼────────────────────────────┤
│ kubernetes.io/tls │ TLS 证书/私钥    │
├────────────┼────────────────────────────┤
│ kubernetes.io/dockerconfigjson │ Docker仓库认证│
├────────────┼────────────────────────────┤
│ kubernetes.io/basic-auth │ 用户名密码认证│
└────────────┴────────────────────────────┘

⚠️ 安全警告：
1. Secret 只是 base64 编码（不是加密），在 etcd 中默认明文存储
2. 生产环境必须启用 EncryptionConfiguration 对 Secret 加密存储
3. 或者使用 Vault / AWS Secrets Manager / Azure Key Vault 等外部密钥管理
```

```yaml
# 启用 Secret 加密配置示例（kube-apiserver 配置）
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources:
  - secrets
  providers:
  - aescbc:
      keys:
      - name: key1
        secret: <base64-encoded-32-byte-key>
  - identity: {}  # 未加密的旧 Secret 自动解密

# Vault 集成示例（通过 External Secret Operator）
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: database-credentials
spec:
  refreshInterval: 1h
  secretStore:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: db-credentials
    creationPolicy: Owner
  data:
  - secretKey: password
    remoteRef:
      key: secret/data/mysql
      property: password
```

---

## 五、RBAC 与 NetworkPolicy：安全加固

### 5.1 RBAC 权限模型

```
RBAC 三大核心概念：

Role / ClusterRole（定义权限）
    │
    ├── Role（Namespace 级别）：只管理当前 Namespace 内的资源
    └── ClusterRole（集群级别）：可管理集群级资源（Nodes、PV 等）

RoleBinding / ClusterRoleBinding（绑定权限到主体）
    │
    ├── RoleBinding：将 Role 绑定到用户/组/SA（当前 Namespace）
    └── ClusterRoleBinding：将 ClusterRole 绑定到用户/组/SA（全集群）

主体（Subjects）：
    ├── User（用户）：通过证书认证
    ├── Group（用户组）：与 User 配合使用
    └── ServiceAccount（服务账号）：Pod 中进程的身份

权限（Verbs）= HTTP 方法对应关系：
    get / list / watch / create / update / patch / delete / deletecollection
    =  GET    LIST  WATCH   CREATE  UPDATE  PATCH  DELETE  DELETECOLLECTION
```

```yaml
# 示例：给某个团队只读某个 Namespace 的权限
---
# 1. 定义只读 Role
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: order-team
  name: readonly
rules:
- apiGroups: [""]
  resources: ["pods", "services", "configmaps"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch"]

---
# 2. 将 Role 绑定到 ServiceAccount
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: team-readonly
  namespace: order-team
subjects:                    # 绑定到谁
- kind: ServiceAccount
  name: order-service-account
  namespace: order-team
- kind: Group
  name: "order-team-developers"   # 开发者组
roleRef:
  kind: Role
  name: readonly
  apiGroup: rbac.authorization.k8s.io

---
# 生产环境建议：
# • 遵循最小权限原则，不给 namespace-admin 直接用 system:masters
# • 使用 Group 而非直接绑定用户，便于权限管理
# • ServiceAccount 名称与 Pod 名称对应，便于审计
```

### 5.2 NetworkPolicy：微服务网络隔离

```yaml
# 默认策略：拒绝所有入站流量（白名单模式）
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: order-team
spec:
  podSelector: {}    # 空选择器 = 选择所有 Pod
  policyTypes:
  - Ingress

---
# 允许特定来源流量的策略
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-gateway
  namespace: order-team
spec:
  podSelector:
    matchLabels:
      app: order-service
  policyTypes:
  - Ingress
  ingress:
  # 允许来自 API Gateway 的流量
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
    ports:
    - protocol: TCP
      port: 8080
  # 允许来自 Ingress Controller 的流量
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8080

# 微服务网络隔离最佳实践：
# 1. 每个 Namespace 一个 NetworkPolicy（默认拒绝）
# 2. 按需放行：order-service 只允许来自 gateway 的流量
# 3. DNS 劫持：Kubernetes DNS 可以基于 NetworkPolicy 实现 L7 过滤
# 4. 配合 Service Mesh（Istio）可实现更细粒度的 mTLS 通信策略
```

---

## 六、Helm：Kubernetes 包管理器

### 6.1 Helm 核心概念

```
Helm 三组件：
┌──────────────────────────────────────────────────────┐
│  Helm CLI（客户端）                                   │
│  • 创建 Chart（Chart = Kubernetes 应用的打包格式）   │
│  • 与 Tiller/Chart Museum 交互                       │
│  • 管理 Release 生命周期                             │
└──────────────────────────────────────────────────────┘

Helm v3 架构（移除了 Tiller）：
┌──────────────────────────────────────────────────────┐
│  Helm CLI (v3)                                        │
│  • 直接通过 kubectl 与 Kubernetes API 交互           │
│  • Release 信息存在 ConfigMap 中（而非 Tiller）       │
│  • 支持 Library Chart（共享工具 Chart）               │
└──────────────────────────────────────────────────────┘

Chart 目录结构：
mychart/
├── Chart.yaml          # 元数据：名称、版本、依赖
├── values.yaml         # 默认配置值
├── values.schema.json  # values.json 校验规则
├── templates/         # K8s 资源模板（Go template 语法）
│   ├── NOTES.txt       # 安装后显示的说明
│   ├── _helpers.tpl    # 共享模板函数
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml
└── charts/             # 子 Chart 依赖（v3 已废弃，用 Chart.yaml dependencies）
```

### 6.2 Helm 模板实战

```yaml
# Chart.yaml
apiVersion: v2
name: order-service
version: 1.0.0        # Chart 版本（Semantic Versioning）
appVersion: "2.1.0"   # 应用版本
description: "订单服务 Helm Chart"
keywords:
  - microservice
  - order
dependencies:          # 声明依赖 Chart
  - name: mysql
    version: "9.x.x"
    repository: "https://charts.bitnami.com/bitnami"
  - name: redis
    version: "17.x.x"
    repository: "https://charts.bitnami.com/bitnami"

# values.yaml
replicaCount: 3

image:
  repository: registry.example.com/order-service
  tag: "v2.1.0"
  pullPolicy: IfNotPresent

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: order.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: order-tls
      hosts:
        - order.example.com

# templates/deployment.yaml（模板示例）
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "order-service.fullname" . }}
  labels:
    {{- include "order-service.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      {{- include "order-service.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "order-service.selectorLabels" . | nindent 8 }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        ports:
        - name: http
          containerPort: 8080
          protocol: TCP
        resources:
          {{- toYaml .Values.resources | nindent 10 }}
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: http
```

### 6.3 Helm Release 管理

```bash
# 安装 Chart
helm install order-service ./mychart --namespace order-team
helm install mysql bitnami/mysql --set auth.rootPassword=secret123

# 使用 values 文件覆盖默认配置
helm install order-service ./mychart -f prod-values.yaml

# 升级 / 回滚
helm upgrade order-service ./mychart --set replicaCount=5
helm rollback order-service 1    # 回滚到第 1 个版本

# 查看 Release 状态
helm list --namespace order-team
helm history order-service       # 查看所有版本历史
helm get values order-service    # 获取当前配置
helm get all order-service       # 获取完整渲染后的资源

# 常用命令速查
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update
helm search repo mysql
helm dependency build            # 更新 Chart 依赖
helm template ./mychart          # 本地渲染模板（无需安装）
```

---

## 七、12-Factor：云原生应用设计原则

### 7.1 十二要素详解

```
12-Factor（云原生应用设计圣经，由 Heroku 提出）：

I.   代码基准（Codebase）
     一套代码，多处部署（每个环境一个 Git 分支）

II.  依赖声明（Dependencies）
     显式声明所有依赖（Python: requirements.txt，Java: pom.xml）

III. 配置分离（Config）
     配置随环境变化，不写入代码 → 使用环境变量或配置中心
     ❌  BAD: DATABASE_HOST = "localhost"  (硬编码)
     ✅  GOOD: DATABASE_HOST = os.getenv("DATABASE_HOST")

IV.  后端服务（Backing Services）
     数据库/缓存/消息队列 视为可替换资源（连接字符串配置化）

V.   构建、发布、运行（Build, Release, Run）
     严格分离构建阶段和运行阶段（CI/CD Pipeline）

VI.  无状态进程（Processes）
     应用无状态，状态存储在后端服务（Redis/DB）→ 便于水平扩展
     ❌  BAD: 将 Session 存储在本地内存
     ✅  GOOD: 使用 Redis 集中存储 Session

VII. 端口绑定（Port Binding）
     Web 应用自包含，端口绑定由运行环境管理（而不是代码监听）

VIII. 并发（Concurrency）
     通过进程模型扩展（而非线程/多进程），无共享状态

IX.  易处置（Disposability）
     快速启动（warmup 时间短）+ 优雅停止（处理完当前请求再退出）
     → SIGTERM → 停止接收新请求 → 处理完在途请求 → 退出

X.   开发/生产对等（Dev/Prod Parity）
     开发、预发布、生产环境尽量保持一致（容器化是关键推动力）
     "The twelve-factor app is designed for continuous deployment"

XI.  日志（Logs）
     日志作为事件流（stdout）→ 由执行环境收集（不写入文件）
     → ELK / Loki / CloudWatch Logs 等统一收集

XII. 管理进程（Admin Processes）
     管理/维护任务作为一次性进程运行（数据库迁移、批处理脚本）
```

### 7.2 12-Factor 在微服务中的实践映射

```
传统 Spring Boot 应用 → 12-Factor 改造：

┌────────────────────────────────────────────────────────────┐
│ III. Config（最常见的问题）                                  │
│ 原方案：application-prod.yml 写在代码仓库                  │
│ 改造方案：                                                  │
│   1. 使用 Spring Cloud Config / Apollo / Nacos 集中配置   │
│   2. 使用 Kubernetes ConfigMap/Secret（K8s 优先）        │
│   3. 配置加密：敏感信息用 Sealed Secret 或 Vault          │
├────────────────────────────────────────────────────────────┤
│ VI. 无状态进程 + IX. 易处置                                 │
│ 原方案：Spring Session 存储在本地 JVM Heap                  │
│ 改造方案：                                                  │
│   1. 使用 Spring Session + Redis（共享 Session）          │
│   2. Application Shutdown Hook：@PreDestroy 处理优雅退出   │
│   3. 设置 terminationGracePeriodSeconds（K8s）             │
├────────────────────────────────────────────────────────────┤
│ XI. 日志作为事件流                                          │
│ 原方案：Logback 写入本地文件                                │
│ 改造方案：                                                  │
│   1. Spring Boot 默认 stdout → Logback JSON 格式          │
│   2. Docker: docker-compose stdout/log driver → Fluentd   │
│   3. K8s: DaemonSet Fluentd/Bit方式收集                    │
│   4. Service Mesh: Envoy 自动收集(access log)            │
└────────────────────────────────────────────────────────────┘
```

---

## 八、面试高频问题汇总

**Q1：K8s 中 Pod 驱逐策略是什么？何时会触发驱逐？**

Pod 驱逐由 Kubelet 触发，主要场景：

1. **资源压力驱逐**：节点内存/CPU 不足时，优先驱逐 `BestEffort` 和 `Burstable` QoS Pod
2. **OOMKilled**：容器内存超 limit，被 Linux OOM Killer 杀掉
3. **节点压力驱逐**：磁盘不足、节点 NotReady、镜像拉取失败
4. **Pod 拓扑分布约束**：Evicted（被抢占）

QoS 等级（决定驱逐优先级）：
```
Guaranteed（最高优先级，不轻易驱逐）
  → memory.limit = memory.request，且两者均已设置
  
Burstable（中等优先级）
  → 不满足 Guaranteed 条件，但有设置 resource request
  
BestEffort（最低优先级，资源不足时首批被驱逐）
  → 未设置任何 resource request/limit
```

**Q2：Kubernetes Service 如何实现负载均衡？**

1. **userspace 模式**：Kube-proxy 监听 Service 变化，在 Node 本地启动 Proxy 进程，转发请求（早期模式，已弃用）
2. **iptables 模式**（默认）：Kube-proxy 为每个 Service 生成 iptables 规则，随机选择后端 Pod（N ≤ 256 时效率好）
3. **IPVS 模式**（推荐）：使用 Linux IP Virtual Server，支持更多负载均衡算法（rr/wrr/lc/sh/lblc 等），性能优于 iptables

```bash
# 查看 kube-proxy 使用哪种模式
kubectl get configmap kube-proxy -n kube-system -o yaml | grep mode
```

**Q3：如何实现不停机发布（Zero-Downtime Deployment）？**

核心要点：
1. **readinessProbe**：Kubelet 只向 Ready 的 Pod 发送流量，新 Pod Ready 后才开始销毁旧 Pod
2. **preStop Hook**：收到 SIGTERM 后等待 N 秒（如 5s），让 iptables 规则更新完成
3. **terminationGracePeriodSeconds**：足够长的优雅退出时间，确保请求处理完毕
4. **Pod Disruption Budget（PDB）**：限制同时不可用的 Pod 数量

```yaml
spec:
  terminationGracePeriodSeconds: 60
  containers:
  - name: order-service
    lifecycle:
      preStop:
        exec:
          command: ["sh", "-c", "sleep 5"]  # 等待 iptables 更新
```

**Q4：StatefulSet 的「稳定」是什么意思？**

- **网络标识稳定**：Pod hostname 固定（mysql-0、mysql-1...），通过 Headless Service 可解析
- **存储稳定**：PVC 与 Pod 序号绑定，Pod 重建后仍绑定相同 PVC（除非 PVC 被删除）
- **部署/扩缩容有序**：必须按序号顺序创建/销毁（0→N 创建，N→0 销毁）

---

## 九、下期预告

> 📌 **下期预告**：《微服务面试八股文（十）——混沌工程、灰度发布与系统韧性设计》
>
> 稳定性是微服务生产环境的终极考验。本篇将聚焦三个核心维度：
> - **混沌工程**：Chaos Monkey/Litmus 故障注入实战、FMEA 故障模式分析
> - **灰度发布**：金丝雀部署、蓝绿发布、A/B 测试、Feature Flag 完整方案
> - **系统韧性**：SRE 错误预算、SLO/SLI/SLA 三者关系、容量规划与压测实战

---

*本文属于「微服务面试八股文」系列，深入解析微服务架构在工程实践中的核心技术点。*
