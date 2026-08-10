---
title: Kubernetes与云原生面试八股文（五）——配置管理与安全
date: 2026-08-04T10:00:00+08:00
updated: '2026-08-04T10:00:00+08:00'
description: 从面试高频问题出发，系统拆解 ConfigMap/Secret 的高级用法、RBAC 权限模型、Pod Security Standards、Service Account 与 Token 机制、NetworkPolicy 实战、证书管理与轮转，建立生产级 K8s 配置与安全认知。
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 5
level: intermediate
status: maintained
tags:
- 面试
- Kubernetes
- ConfigMap
- Secret
- RBAC
categories:
- 分布式与微服务
draft: false
author: 飞哥
---

## Kubernetes与云原生面试八股文（五）——配置管理与安全

### 🎯 本文目标

配置管理和安全是 Kubernetes 生产化运营中不可绕过的核心领域。配置管理保证应用在不同环境中行为一致，安全体系保证集群在多租户、多团队场景下不被越权操作。本文将系统梳理 K8s 配置与安全的完整知识体系：从 ConfigMap/Secret 的高级用法，到 RBAC 权限模型，再到 Pod Security Standards、Service Account 与 Token 机制、NetworkPolicy 实战和证书管理与轮转。读完本文，你将能够：

1. 理解 ConfigMap/Secret 的多种注入方式及其适用场景
2. 掌握 RBAC 的 Role/ClusterRole/Binding 机制与最佳实践
3. 理解 Pod Security Standards 三个级别（baseline/restricted/privileged）的差异
4. 说清 Service Account、Token 与鉴权链路
5. 编写 NetworkPolicy 实现租户级网络隔离
6. 了解 K8s 证书体系与轮转策略

---

## 一、ConfigMap 进阶

### Q1：ConfigMap 的创建方式有哪些？各有什么优劣？

ConfigMap 支持四种创建方式：

**方式一：`--from-literal` 键值对**

```bash
kubectl create configmap app-config \
  --from-literal=LOG_LEVEL=info \
  --from-literal=MAX_CONNECTIONS=100
```

适合少量简单配置项。

**方式二：`--from-file` 单文件**

```bash
kubectl create configmap app-config \
  --from-file=app.properties \
  --from-file=logging.conf
```

文件名成为 Key，文件内容成为 Value。适合将整个配置文件注入。

**方式三：`--from-file` 目录**

```bash
kubectl create configmap app-config --from-file=./config/
```

目录下每个文件都会成为 ConfigMap 中的一个 Key。

**方式四：`--from-env-file` 环境变量文件**

```bash
kubectl create configmap app-config --from-env-file=config.env
```

文件格式为 `KEY=VALUE`，每行一个，自动解析为多个 Key。

| 方式 | 适用场景 | 优势 | 劣势 |
|------|---------|------|------|
| from-literal | 少量简单配置 | 简单直接 | 不适合复杂配置 |
| from-file | 整个配置文件 | 保持文件结构 | Key 为文件名 |
| from-file 目录 | 多配置文件批量导入 | 批量高效 | 无法自定义 Key |
| from-env-file | 环境变量注入 | 自动解析 KEY=VALUE | 仅适合扁平 KV |

### Q2：ConfigMap 的三种消费方式是什么？

ConfigMap 有三种注入 Pod 的方式，各有适用场景：

**方式一：环境变量**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  containers:
  - name: app
    image: app:1.0
    env:
    - name: LOG_LEVEL
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: LOG_LEVEL
    # 批量注入
    envFrom:
    - configMapRef:
        name: app-config
```

- **优点**：简单通用，应用启动即可读取
- **缺点**：更新 ConfigMap 后环境变量不会自动刷新，需要重启 Pod

**方式二：Volume 挂载**

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: config
      mountPath: /etc/config
      readOnly: true
  volumes:
  - name: config
    configMap:
      name: app-config
```

- **优点**：支持自动更新（kubelet 定期同步，60-120 秒延迟）
- **缺点**：需要应用支持文件配置读取，且需处理配置变更的 Hot Reload

**方式三：subPath 挂载单个文件**

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: config
      mountPath: /etc/nginx/nginx.conf
      subPath: nginx.conf
      readOnly: true
  volumes:
  - name: config
    configMap:
      name: nginx-config
```

- **优点**：可以覆盖容器内已有文件（如替换 nginx.conf）
- **缺点**：使用 subPath 挂载时**不会自动更新**，因为 subPath 创建的是符号链接指向特定版本

### Q3：ConfigMap 更新后，Pod 如何感知变化？

ConfigMap 更新后有两种感知方式：

**自动更新（Volume 方式）**：
- kubelet 会定期（默认 60 秒）检查挂载的 ConfigMap 是否更新
- 更新后会将新内容写入 Pod 挂载的 Volume
- 延迟约 60-120 秒生效
- **注意**：subPath 挂载方式不会自动更新

**手动触发更新**：
- 修改 Deployment 触发滚动更新
- 使用 Reloader 等工具自动滚动更新
- 通过 kubectl rollout restart deployment 手动重启

```bash
# 修改 ConfigMap 后触发滚动更新
kubectl set env deployment/app CONFIG_REVISION=$(date +%s)
# 或者直接重启
kubectl rollout restart deployment app
```

### Q4：ConfigMap 有大小限制吗？

ConfigMap 单个最大 **1MB**（etcd 的 value 大小限制）。对于超大配置（如大型 JSON Schema、WSDL 文件），可以：

1. 拆分为多个 ConfigMap
2. 使用 Read OnlyVolume 配合对象存储（如 S3、OSS）
3. 将配置打包为镜像，通过 Init Container 拷贝到 EmptyDir

---

## 二、Secret 深入

### Q5：Secret 和 ConfigMap 有什么区别？

| 维度 | ConfigMap | Secret |
|------|-----------|--------|
| 用途 | 非敏感配置 | 敏感数据（密码、证书、Token） |
| 存储格式 | 明文 KV | Base64 编码 |
| etcd 存储 | 明文 | Base64（非加密） |
| 大小限制 | 1MB | 1MB |
| Volume 挂载 | 明文文件 | 可选明文或 Base64 |
| 环境变量 | 明文 | 明文（自动解码） |
| RBAC 控制 | 可被多角色读取 | 通常限制读取权限 |

**关键理解**：Secret 的 Base64 编码**不是加密**，只是避免在终端直接显示明文。真正的加密需要通过以下方式实现：

- 启用 K8s Encryption at Rest（etcd 层加密）
- 使用外部密钥管理（HashiCorp Vault、AWS KMS、Cloud KMS）
- 通过 CSI Secret Store Driver 从外部密钥管理系统读取

### Q6：Secret 有哪些类型？

K8s 内置了多种 Secret 类型：

```bash
# 1. Opaque（通用类型，默认）
kubectl create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password='S3cur3!'

# 2. docker-registry（镜像拉取凭证）
kubectl create secret docker-registry reg-cred \
  --docker-server=registry.example.com \
  --docker-username=admin \
  --docker-password='S3cur3!' \
  --docker-email=admin@example.com

# 3. tls（TLS 证书）
kubectl create secret tls tls-secret \
  --cert=server.crt \
  --key=server.key

# 4. service-account-token（SA Token，通常自动创建）
# 由控制器自动管理，不需要手动创建
```

### Q7：如何安全地使用 Secret？最佳实践是什么？

**生产级最佳实践**：

1. **启用 Encryption at Rest**

```bash
# 查看 API Server 是否启用加密
kubectl get encryptionconfiguration --all-namespaces 2>/dev/null
kubectl describe pod kube-apiserver -n kube-system | grep -i encryption
```

EncryptionConfiguration 配置示例：

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources:
  - secrets
  providers:
  - aesgcm:
      keys:
      - name: key1
        secret: <base64-encoded-32-byte-key>
  - identity: {}  # 兜底，确保能读取未加密的旧 Secret
```

2. **使用 RBAC 限制 Secret 读取权限**

```yaml
# 只允许特定 Service Account 读取特定 Secret
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["db-secret", "api-key"]
  verbs: ["get"]
```

3. **使用外部密钥管理器（推荐生产环境）**

```yaml
# 通过 External Secrets Operator 从 Vault/AWS SM 读取
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: db-secret
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: db-secret
    creationPolicy: Owner
  data:
  - secretKey: password
    remoteRef:
      key: production/db/password
      property: value
```

4. **避免在环境变量中使用 Secret**

环境变量可能通过日志、crash dump、`/proc/PID/environ` 泄露。推荐使用 Volume 挂载方式。

5. **使用 SA Token 投影（Projected Service Account Token）**

```yaml
spec:
  containers:
  - name: app
    volumeMounts:
    - name: sa-token
      mountPath: /var/run/secrets/tokens
      readOnly: true
  volumes:
  - name: sa-token
    projected:
      sources:
      - serviceAccountToken:
          path: token
          expirationSeconds: 3600  # 1小时过期
          audience: vault
```

---

## 三、RBAC 权限模型

### Q8：RBAC 的核心概念是什么？Role 和 ClusterRole 有什么区别？

RBAC（Role-Based Access Control）是 K8s 的权限控制框架，核心三要素：

- **Subject**：操作主体（User、Group、ServiceAccount）
- **Verb**：操作行为（get、list、watch、create、update、patch、delete、*）
- **Resource**：操作对象（pods、deployments、secrets 等）

**Role vs ClusterRole**：

| 维度 | Role | ClusterRole |
|------|------|------------|
| 作用范围 | Namespace 级别 | 集群级别 |
| 可授权资源 | Namespaced 资源 | 所有资源（含 Node、PV 等集群级资源） |
| 绑定方式 | RoleBinding | ClusterRoleBinding 或 RoleBinding |
| 典型场景 | 某命名空间内开发权限 | 集群管理员、只读用户 |

**关键理解**：ClusterRole 可以通过 RoleBinding 绑定到某个 Namespace，实现"集群级角色定义 + Namespace 级别授权"。

```yaml
# Role：只允许 default 命名空间内读取 Pod
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: default
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]

# ClusterRole：允许全集群读取 Pod
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader-global
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
```

### Q9：RoleBinding 和 ClusterRoleBinding 有什么区别？

| 维度 | RoleBinding | ClusterRoleBinding |
|------|-------------|-------------------|
| 作用范围 | Namespace 级别 | 集群级别 |
| 可绑定 | Role 或 ClusterRole | 只能绑定 ClusterRole |
| 生效范围 | 仅绑定的 Namespace | 全集群所有 Namespace |

```yaml
# RoleBinding：将 ClusterRole 绑定到特定 Namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods
  namespace: production
subjects:
- kind: ServiceAccount
  name: app-sa
  namespace: production
roleRef:
  kind: ClusterRole
  name: pod-reader-global
  apiGroup: rbac.authorization.k8s.io
```

这个例子展示了一个常见模式：定义一个 ClusterRole（复用），通过 RoleBinding 绑定到特定 Namespace，实现"角色定义一次，多处使用"。

### Q10：RBAC 中的常见权限组合有哪些？

```yaml
# 1. 只读用户（推荐给开发/运维查看）
verbs: ["get", "list", "watch"]

# 2. 开发者（可部署和调试）
verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

# 3. CI/CD 部署账号（只能操作 Deployment 和 Service）
rules:
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["services", "configmaps"]
  verbs: ["get", "list", "watch", "create", "update", "patch"]

# 4. 审计只读（全集群查看）
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["get", "list", "watch"]
- nonResourceURLs: ["*"]
  verbs: ["get"]
```

### Q11：如何排查 RBAC 权限问题？

```bash
# 1. 检查某个 SA 的权限
kubectl auth can-i list pods --as=system:serviceaccount:default:app-sa -n default

# 2. 检查某个 User 是否能执行某操作
kubectl auth can-i create deployments --as=alice -n production

# 3. 查看所有可执行的操作
kubectl auth can-i --list --as=alice -n production

# 4. 查看绑定到某个 SA 的 Role/ClusterRole
kubectl get rolebinding,clusterrolebinding -A -o json | jq '.items[] | select(.subjects[]? | select(.kind=="ServiceAccount" and .name=="app-sa"))'

# 5. 查看 Role 的具体权限
kubectl describe role pod-reader -n default
kubectl describe clusterrole cluster-admin
```

---

## 四、Pod Security Standards

### Q12：Pod Security Standards 有哪些级别？

Pod Security Standards（PSS）是 K8s 1.25+ 替代 Pod Security Policy（PSP）的新方案。三个级别：

| 级别 | 描述 | 适用场景 |
|------|------|---------|
| **Privileged** | 无限制 | 系统组件、特殊需求 |
| **Baseline** | 禁止最危险的配置 | 一般应用 |
| **Restricted** | 严格限制，遵循最佳实践 | 安全敏感的生产应用 |

**Restricted 级别的主要限制**：

```yaml
# Restricted 要求的 Pod 安全上下文
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  securityContext:
    runAsNonRoot: true          # 必须非 root 运行
    seccompProfile:
      type: RuntimeDefault      # 必须 enable seccomp
  containers:
  - name: app
    image: app:1.0
    securityContext:
      allowPrivilegeEscalation: false  # 禁止提权
      runAsNonRoot: true
      runAsUser: 1000           # 必须 > 0
      capabilities:
        drop:
          - ALL                  # 必须 drop 所有 capabilities
      readOnlyRootFilesystem: true  # 只读根文件系统
```

### Q13：如何为 Namespace 启用 Pod Security Standards？

通过 Namespace Label 实现：

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    # enforce：违反则拒绝创建
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    
    # audit：违反则记录审计日志
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest
    
    # warn：违反则返回警告信息
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
```

三种模式的行为：

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| **enforce** | 拒绝创建不合规 Pod | 强制安全策略 |
| **audit** | 记录审计日志，不阻止 | 过渡期观察 |
| **warn** | 返回警告，不阻止 | 提醒开发者 |

### Q14：常见的 Pod 安全配置有哪些？

```yaml
# 生产级推荐安全上下文
apiVersion: v1
kind: Pod
metadata:
  name: production-app
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000
    fsGroupChangePolicy: "OnRootMismatch"
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    image: app:1.0
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 1000
      capabilities:
        drop:
          - ALL
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/cache
  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
```

**关键点**：`readOnlyRootFilesystem: true` 要求应用不能写入容器根文件系统，需要为 `/tmp`、`/app/cache` 等可写路径单独挂载 Volume。

---

## 五、Service Account 与 Token 机制

### Q15：Service Account 的作用是什么？与 User 有什么区别？

| 维度 | Service Account | User |
|------|----------------|------|
| 身份类型 | Pod 内进程身份 | 人 |
| 认证方式 | 自动挂载 Token | 证书/X509/OIDC |
| 管理方式 | K8s API 创建和管理 | 集群外部管理 |
| 使用场景 | Pod 访问 API Server | kubectl、CI/CD |
| 命名空间 | 绑定到 Namespace | 全局 |

每个 Namespace 创建时自动创建一个 `default` Service Account。Pod 默认使用该 SA，但生产环境应该为每个应用创建专用 SA。

```yaml
# 为应用创建专用 SA
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: production
---
# Pod 使用专用 SA
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  serviceAccountName: app-sa
  containers:
  - name: app
    image: app:1.0
```

### Q16：Service Account Token 的工作原理是什么？

**传统方式（K8s 1.22 之前）**：
- 创建 SA 时自动创建 Secret
- Token 是非过期 JWT，存储在 Secret 中
- 通过 Volume 自动挂载到 `/var/run/secrets/kubernetes.io/serviceaccount/`

**新方式（K8s 1.24+，推荐）**：
- 创建 SA 时**不再自动创建 Secret**
- Token 通过 `TokenRequest` API 按需生成
- Token 有过期时间（默认 1 小时）
- kubelet 自动刷新 Token

```bash
# 手动为 SA 创建 Token（有过期时间）
kubectl create token app-sa -n production --duration=3600s

# 查看 TokenRequest API 生成的 Token
kubectl create token app-sa -n production --audience=vault
```

### Q17：Pod 如何安全地访问 API Server？

```yaml
# 推荐方式：Projected Volume + 短期 Token
apiVersion: v1
kind: Pod
metadata:
  name: api-client
spec:
  serviceAccountName: app-sa
  containers:
  - name: app
    image: app:1.0
    volumeMounts:
    - name: sa-token
      mountPath: /var/run/secrets/tokens
      readOnly: true
  volumes:
  - name: sa-token
    projected:
      sources:
      - serviceAccountToken:
          path: token
          expirationSeconds: 3600
          audience: https://kubernetes.default.svc
```

应用通过读取 `/var/run/secrets/tokens/token` 获取短期 Token，访问 API Server：

```python
import requests

token = open("/var/run/secrets/tokens/token").read().strip()
headers = {"Authorization": f"Bearer {token}"}
url = "https://kubernetes.default.svc/api/v1/namespaces/production/pods"
resp = requests.get(url, headers=headers, verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
```

---

## 六、NetworkPolicy 实战

### Q18：NetworkPolicy 的作用是什么？有什么限制？

NetworkPolicy 是 K8s 原生的网络隔离方案，通过 Label Selector 控制哪些 Pod 可以互相通信。

**核心概念**：
- 默认允许所有流量（无 NetworkPolicy 时）
- NetworkPolicy 生效后，只有明确允许的流量才能通过
- 支持按 `ingress`（入站）和 `egress`（出站）分别控制

**关键限制**：
- 需要网络插件支持（Calico、Cilium、Antrea 等支持，Flannel 默认不支持）
- 只能控制 L3/L4 层流量，不能控制 L7（需要用 Istio/Linkerd 等服务网格）
- 只能控制 Pod 到 Pod 的流量，不能控制 ExternalIP 到 Pod 的流量（部分插件支持）

### Q19：如何编写一个生产级 NetworkPolicy？

**场景**：一个多租户集群，需要实现以下隔离：

1. 每个租户只能访问自己 Namespace 内的 Pod
2. 前端 Pod 可以访问后端 Pod
3. 后端 Pod 可以访问数据库 Pod
4. 所有 Pod 可以访问 DNS 和出站互联网

```yaml
# 1. 默认拒绝所有入站和出站
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: tenant-a
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
# 2. 允许前端到后端的流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-to-backend
  namespace: tenant-a
spec:
  podSelector:
    matchLabels:
      app: backend
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 8080
---
# 3. 允许后端到数据库的流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-to-db
  namespace: tenant-a
spec:
  podSelector:
    matchLabels:
      app: database
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: backend
    ports:
    - protocol: TCP
      port: 5432
---
# 4. 允许所有 Pod 访问 DNS
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: tenant-a
spec:
  podSelector: {}
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

### Q20：NetworkPolicy 的常见排查方法？

```bash
# 1. 检查网络插件是否支持 NetworkPolicy
kubectl get pods -n kube-system | grep -E "calico|cilium|antrea"

# 2. 查看 NetworkPolicy
kubectl get networkpolicy -A -o wide

# 3. 查看 Pod 被哪些 Policy 影响
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Network Policies"

# 4. 使用 calicoctl 查看详细策略（Calico 环境）
calicoctl get networkPolicy -n <namespace> -o wide

# 5. 使用 kubectl trace 测试连通性
kubectl trace node <node-name> --image=nicolaka/netshoot -- tcpdump -i any port 8080
```

---

## 七、证书管理与轮转

### Q21：K8s 的证书体系是怎样的？

K8s 集群涉及大量证书，分为两类：

**1. 集群组件证书**

| 证书 | 用途 | 默认有效期 |
|------|------|------------|
| apiserver.crt | API Server HTTPS | 1 年 |
| apiserver-kubelet-client.crt | API Server 访问 kubelet | 1 年 |
| front-proxy-client.crt | API 聚合层代理 | 1 年 |
| etcd-server.crt | etcd 通信 | 1 年 |
| ca.crt | 根 CA | 10 年 |

**2. Pod 证书（自动轮转）**

- kubelet 的客户端证书：默认有效期 1 年，自动轮转（在过期前 70% 时自动申请新证书）
- SA Token：通过 TokenRequest API 生成，有过期时间

### Q22：如何检查和续期集群证书？

```bash
# 检查证书过期时间（kubeadm 集群）
sudo kubeadm certs check-expiration

# 输出示例：
# CERTIFICATE                EXPIRES                   RESIDUAL TIME   EXTERNALLY MANAGED
# apiserver                  Aug 04, 2027 10:00 UTC   365d            no
# apiserver-kubelet-client   Aug 04, 2027 10:00 UTC   365d            no
# etcd-server                Aug 04, 2027 10:00 UTC   365d            no
# ...

# 续期所有证书（在控制节点上执行）
sudo kubeadm certs renew all

# 续期后需要重启相关组件
sudo systemctl restart kube-apiserver kube-controller-manager kube-scheduler etcd

# 注意：续期不会影响已运行 Pod 的 SA Token
```

### Q23：如何实现证书自动轮转？

**kubelet 客户端证书自动轮转**（默认已启用）：

```yaml
# kubelet 配置
apiVersion: kubelet.config.k8s.io/v1
kind: KubeletConfiguration
rotateCertificates: true          # 启用自动轮转
```

轮转流程：
1. kubelet 在证书有效期剩余 30% 时，向 API Server 发起 CSR
2. Controller Manager 中的 `csrapprover` 自动批准
3. kubelet 获取新证书，写入文件
4. kubelet 重新建立与 API Server 的连接

**自定义 CA 轮转**：

```bash
# 1. 生成新 CA
openssl genrsa -out ca-new.key 4096
openssl req -x509 -new -key ca-new.key -days 3650 -out ca-new.crt -subj "/CN=kubernetes"

# 2. 更新 kubeconfig
kubectl config set-cluster kubernetes --certificate-authority=ca-new.crt

# 3. 更新 API Server 配置使用新 CA
# 4. 逐步轮转所有组件证书
# 5. 确认所有组件正常后删除旧 CA
```

---

## 八、综合安全最佳实践

### Q24：生产级 K8s 安全加固清单有哪些？

**集群层面**：

- [ ] 启用 Encryption at Rest
- [ ] 启用 Audit Log
- [ ] 禁用匿名访问（`--anonymous-auth=false`）
- [ ] 启用 Node Authorization（`--authorization-mode=Node,RBAC`）
- [ ] 限制 API Server 访问（防火墙/安全组）
- [ ] 定期续期证书
- [ ] 启用 Pod Security Standards（restricted 模式）

**Pod 层面**：

- [ ] 使用专用 ServiceAccount
- [ ] `runAsNonRoot: true`
- [ ] `readOnlyRootFilesystem: true`
- [ ] `allowPrivilegeEscalation: false`
- [ ] `drop ALL capabilities`
- [ ] 启用 seccomp RuntimeDefault
- [ ] 资源限制（requests + limits）
- [ ] NetworkPolicy 网络隔离

**Secret 管理层面**：

- [ ] 避免环境变量传递 Secret
- [ ] 使用外部密钥管理器
- [ ] RBAC 限制 Secret 读取
- [ ] 定期轮转密钥

**审计层面**：

```yaml
# Audit Policy 示例
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
# 记录 Secret 操作
- level: Metadata
  resources:
  - group: ""
    resources: ["secrets"]
# 记录 RBAC 变更
- level: RequestResponse
  resources:
  - group: "rbac.authorization.k8s.io"
# 忽略 get/list/watch
- level: None
  verbs: ["get", "list", "watch"]
# 其他记录 Metadata
- level: Metadata
```

### Q25：多租户场景下的安全隔离方案？

| 层级 | 隔离方案 | 实现方式 |
|------|---------|---------|
| **软隔离** | Namespace + RBAC + NetworkPolicy | 同集群不同 NS |
| **强隔离** | 虚拟集群（vcluster） | 每个 NS 是独立 K8s |
| **硬隔离** | 独立集群 | 每个租户一个集群 |

**软隔离方案（同集群多 Namespace）**：

```yaml
# 1. 创建租户 Namespace 和 Admin
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-a
  labels:
    tenant: tenant-a
    pod-security.kubernetes.io/enforce: restricted
---
# 2. 创建租户 Admin SA 和 RBAC
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tenant-admin
  namespace: tenant-a
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: tenant-admin
  namespace: tenant-a
subjects:
- kind: ServiceAccount
  name: tenant-admin
  namespace: tenant-a
roleRef:
  kind: ClusterRole
  name: admin
  apiGroup: rbac.authorization.k8s.io
---
# 3. NetworkPolicy 隔离租户
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-a
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          tenant: tenant-a
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          tenant: tenant-a
    # 允许 DNS
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
```

---

## 九、面试高频综合题

### Q26：如何实现"应用只能访问自己的 Secret，不能查看其他 Secret"？

```yaml
# 1. 创建专用 SA
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: production
---
# 2. Role 只允许读取特定 Secret
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-secret-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["app-config", "app-db-cred"]
  verbs: ["get"]
---
# 3. 绑定 SA 和 Role
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-secret-reader
  namespace: production
subjects:
- kind: ServiceAccount
  name: app-sa
  namespace: production
roleRef:
  kind: Role
  name: app-secret-reader
  apiGroup: rbac.authorization.k8s.io
---
# 4. Pod 使用专用 SA
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  serviceAccountName: app-sa
  containers:
  - name: app
    image: app:1.0
```

### Q27：如何实现"Pod 不能访问 API Server"？

```yaml
# 方法一：automountServiceAccountToken: false
apiVersion: v1
kind: Pod
metadata:
  name: no-api-access
spec:
  automountServiceAccountToken: false
  containers:
  - name: app
    image: app:1.0
---
# 方法二：在 SA 层面禁止
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: production
automountServiceAccountToken: false
```

### Q28：NetworkPolicy 中 namespaceSelector 和 podSelector 同时使用是什么语义？

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: cross-namespace
  namespace: production
spec:
  podSelector: {}
  ingress:
  - from:
    # AND 语义：同时匹配 Namespace 和 Pod Label
    - namespaceSelector:
        matchLabels:
          team: backend
      podSelector:
        matchLabels:
          app: api-gateway
```

**关键理解**：当 `namespaceSelector` 和 `podSelector` 在同一个 `from` 条目中时，是 **AND** 语义——必须同时满足 Namespace 标签和 Pod 标签。如果分别在两个 `from` 条目中，则是 **OR** 语义。

---

## 十、本系列知识体系总览

| 期数 | 主题 | 核心要点 |
|------|------|---------|
| 第一期 | K8s 架构核心与集群管理 | 控制平面/数据平面、etcd、kubelet、kubectl 原理 |
| 第二期 | Pod 深入与工作负载管理 | Pod 生命周期、Deployment/StatefulSet/DaemonSet、调度器 |
| 第三期 | Service 与网络通信 | Service 类型、kube-proxy、Ingress、CNI、NetworkPolicy |
| 第四期 | 存储卷与数据持久化 | Volume 类型、PV/PVC、StorageClass、CSI、StatefulSet 存储 |
| **第五期** | **配置管理与安全** | **ConfigMap/Secret、RBAC、Pod Security、SA Token、NetworkPolicy、证书轮转** |
| 第六期 | Helm 包管理与 GitOps（预告） | Helm Chart 开发、ArgoCD、FluxCD、GitOps 工作流 |

---

## 下期预告

下一篇：**Kubernetes与云原生面试八股文（六）——Helm 包管理与 GitOps** 将深入讲解 Helm Chart 开发最佳实践、Template 与函数、OCI Registry 集成、ArgoCD 与 FluxCD 的 GitOps 工作流、多环境配置管理、渐进式发布与回滚策略，敬请期待。

---

*作者：飞哥 · Raphael Lab*

*Kubernetes与云原生面试八股文系列*
