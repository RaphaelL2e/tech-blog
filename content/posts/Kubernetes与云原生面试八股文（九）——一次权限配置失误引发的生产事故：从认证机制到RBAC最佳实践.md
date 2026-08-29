---
title: Kubernetes与云原生面试八股文（九）——一次权限配置失误引发的生产事故：从认证机制到RBAC最佳实践
date: 2026-08-29 10:00:00+08:00
updated: '2026-08-29T10:00:00+08:00'
description: '面试高频问题：Kubernetes 的认证授权机制是怎么工作的？ServiceAccount、RBAC、证书认证有什么区别？线上如何正确配置权限避免生产事故？本文从一次真实权限配置事故出发，系统讲解 K8s 认证授权全链路，含最佳实践与避坑指南。
  Q: K8s 的认证（Authentication）和授权（Authorization）有什么区别？'
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 9
level: intermediate
status: maintained
tags:
- 面试
- Kubernetes
- RBAC
- 安全
- 认证
- ServiceAccount
categories:
- 分布式与微服务
draft: false
---

## 前言

周一早上9点，告警爆发：核心订单服务的 Pod 全部 CrashLoopBackOff。排查发现是运维工程师在一次例行巡检中，为一个 Deployment 新增了 `default` ServiceAccount 的 `cluster-admin` 角色绑定——目的是「临时调试方便」。绑定写错了范围，本应在 `namespace-a` 下生效，结果绑到了 `ClusterRoleBinding`，影响了全局所有 ServiceAccount。

这个误操作导致 API Server 权限校验出现异常，部分控制器（Controller）行为异常，最终引发了级联故障。

权限配置，这个在日常开发中最容易被忽视的环节，往往是生产集群中最危险的定时炸弹。本文从认证授权机制出发，深度覆盖 Kubernetes 安全模型的面试核心知识点。

---

## Q1: Kubernetes 的安全模型是什么？

**Kubernetes 采用的是"认证→授权→准入控制"三层安全模型**，请求必须依次通过这三层：

```
请求 → Authentication（认证） → Authorization（授权） → Admission Control（准入控制） → 执行
```

- **Authentication（认证）**：确认"你是谁"。识别发起请求的用户或进程身份。
- **Authorization（授权）**：确认"你能做什么"。判断已认证身份是否有权限执行该操作。
- **Admission Control（准入控制）**：在对象被持久化之前，对请求进行二次审查（如资源配额、污点管理等）。

**面试加分点**：三层模型中，认证和授权是任何请求都必须通过的，准入控制器是可选的、可插拔的插件链。常见准入控制器包括 `NamespaceLifecycle`、`LimitRanger`、`ResourceQuota`、`DefaultStorageClass` 等。

---

## Q2: Kubernetes 有哪些认证方式？

**Kubernetes 支持多种认证机制，通常同时启用多种方式，请求通过第一个匹配的认证器即可：**

### 1. ServiceAccount Token（最常用）

`ServiceAccount` 是 Pod 中运行的进程向 API Server 认证的主要方式。每个 Pod 创建时，Kubernetes 会自动为其挂载一个 ServiceAccount Token（通过 Volume 挂载到 `/var/run/secrets/kubernetes.io/serviceaccount/`）：

```yaml
# 自动挂载到 Pod 内
volumeMounts:
- name: sa-token
  mountPath: /var/run/secrets/kubernetes.io/serviceaccount
  readOnly: true
```

Token 本质是一个经过 API Server 密钥签名的 JWT，Payload 中包含：

```json
{
  "iss": "kubernetes/serviceaccount",
  "sub": "system:serviceaccount:default:my-app",
  "namespace": "default",
  "serviceaccount-name": "my-app",
  "serviceaccount-uid": "bc5f..."
}
```

**关键点**：Token 中的 `subject (sub)` 字段标识了 `system:serviceaccount:<namespace>:<name>`，这是 RBAC 授权的身份来源。

### 2. Node 认证（Node Authorization）

kubelet 需要访问 API Server 来汇报节点状态、获取 Pod 配置等。Kubernetes 对 kubelet 使用特殊的**基于 Node 的认证模式**：API Server 验证请求来源 IP 是否属于 NodeCIDR，以及请求者用户名是否为 `system:node:<nodeName>` 格式。

### 3. X.509 客户端证书

用户和管理员可以通过 CA 签发的客户端证书认证。证书的 `CN` 字段作为用户名，`O` 字段作为组：

```bash
# 查看当前证书信息
kubectl config view --raw
# 或直接看集群 CA
kubectl config view --flatten
```

### 4. Bootstrap Token（引导 Token）

用于 kubelet 初始启动时向 API Server 注册节点。采用 `Bootstrapping` 机制：先通过 Token 认证获取受限权限，用该权限向 API Server 申请正式的证书。

### 5. OIDC（OpenID Connect）第三方认证

企业场景中，常用外部 IdP（如 Keycloak、Okta、Azure AD）通过 OIDC 协议集成。用户在 IdP 完成登录，拿到的 ID Token 交给 kubectl 使用。

```bash
# kubectl 使用 OIDC Token
kubectl --token=<ID_TOKEN> get pods
```

**面试加分点**：说明各认证方式的适用场景——ServiceAccount 用于 Pod 内进程，证书用于管理员/用户，OIDC 用于企业 SSO。

---

## Q3: 什么是 RBAC？它的核心概念是什么？

**RBAC（Role-Based Access Control）是 Kubernetes 默认且最常用的授权方式**，通过 `Role` / `ClusterRole` 和 `RoleBinding` / `ClusterRoleBinding` 控制谁能对哪些资源做什么操作。

### 核心概念

| 概念 | 作用域 | 说明 |
|------|--------|------|
| Role | 单一命名空间 | 定义一组权限规则，作用于一个 namespace |
| ClusterRole | 集群级别 | 定义集群级权限，或跨 namespace 的权限 |
| RoleBinding | 单一命名空间 | 将 Role 绑定到 User/Group/ServiceAccount |
| ClusterRoleBinding | 集群级别 | 将 ClusterRole 绑定到集群范围的实体 |

### Role 示例

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
```

### ClusterRole 示例（用于跨 namespace 或集群级资源）

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: secret-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
  # 未指定 namespace 时表示集群级，secrets 属于核心 API 组 ""
  # 对 secrets 的 cluster-wide 权限
```

### RoleBinding 将权限赋予主体

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-binding
  namespace: production
subjects:           # 主体：可以是 User、Group 或 ServiceAccount
- kind: ServiceAccount
  name: my-app
  namespace: production
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

**关键区别**：ClusterRoleBinding 的 subjects 可以绑定 ClusterRole 到集群内任意 namespace 的 ServiceAccount。

---

## Q4: Role 和 ClusterRole 的区别是什么？什么时候用哪个？

这是高频面试题，需要从**作用域**和**适用资源**两个维度回答：

### 作用域维度

- `Role` + `RoleBinding`：**只在同一个 namespace 内生效**
- `ClusterRole` + `ClusterRoleBinding`：在**整个集群**所有 namespace 内生效
- `ClusterRole` + `RoleBinding`：跨 namespace 生效（ClusterRole 定义权限，RoleBinding 限定范围）

### 适用资源维度

部分资源只能通过 ClusterRole 授权，因为它们是**集群级别的资源**，不存在于任何 namespace 下：

- `nodes`、`persistentvolumes`、`componentstatuses`、`namespaces`、`storageclasses`
- `certificatesigningrequests`、`clusterroles`、`clusterrolebindings`

### 最佳实践

1. **优先使用 Role + RoleBinding**：权限最小化，作用域最小化
2. **只在对集群级资源授权、或需要跨所有 namespace 授权时才用 ClusterRole**
3. **避免滥用 default ServiceAccount**：`default` SA 是每个 namespace 自带的，很多初学者习惯直接给 `default` SA 赋权，这会意外影响所有 Pod

---

## Q5: 如何排查 RBAC 权限问题？

### 方式一：kubectl auth can-i（最常用）

```bash
# 当前上下文能否查看 pods
kubectl auth can-i get pods

# 模拟指定用户/SA
kubectl auth can-i get pods --as=system:serviceaccount:production:my-app

# 模拟查看 secrets（敏感操作）
kubectl auth can-i get secrets --as=system:serviceaccount:production:my-app

# 查看对所有资源的所有权限
kubectl auth can-i --list --as=system:serviceaccount:production:my-app
```

### 方式二：describe 查看详细拒绝原因

```bash
kubectl describe clusterrolebinding <name>
kubectl describe rolebinding <name> -n <namespace>
```

### 方式三：启用 API Server 审计日志

在 `kube-apiserver` 开启审计策略，记录所有被拒绝的请求：

```yaml
# audit-policy.yaml
apiVersion: audit.k8s.io/v1
kind: Policy
rules:
- level: Metadata
  resources:
  - group: ""
    resources: ["secrets", "configmaps"]
    verbs: ["get", "list", "watch"]
- level: RequestResponse
  resources:
  - group: ""
    resources: ["pods"]
```

### 真实案例：Token 挂载未同步导致 403

**场景**：应用迁移到新 namespace 后持续收到 403。排查发现：ServiceAccount `my-app` 在新 namespace 下被自动创建，但对应的 RoleBinding 只绑在了旧 namespace，导致新 namespace 下的 SA 有名无实。

**解决**：在新 namespace 下重建 RoleBinding，或使用 ClusterRoleBinding 跨 namespace 授权。

---

## Q6: ServiceAccount 和 User 有什么区别？

| 维度 | ServiceAccount | User |
|------|---------------|------|
| 用途 | Pod 内进程 / Kubernetes 内部组件 | 真实的人或外部系统 |
| 认证方式 | ServiceAccount Token（JWT） | 证书 / OIDC Token |
| 管理方式 | Kubernetes API 对象 | Kubernetes 外部管理（企业 IdP） |
| 作用域 | 通常绑定到 namespace | 集群级别 |
| 命名规范 | `system:serviceaccount:<namespace>:<name>` | `system:` 前缀保留给系统用户 |

---

## Q7: 如何实现证书轮换？

长期有效的证书一旦泄露风险极大，Kubernetes 支持证书自动轮换：

### kubelet 证书轮换

kubelet 使用 Bootstrap 机制：初始用 Bootstrap Token 认证，向 API Server 申请由 CA 签发的客户端证书。证书默认有效期一年，快过期时 kubelet 自动申请续期。

### API Server 证书轮换

API Server 的 serving 证书（用于 TLS 握手）可以通过 Kubernetes 1.19+ 的内建自动轮换机制更新，无需重启 API Server。

### etcd 证书轮换

etcd 的 Peer 证书和 Client 证书同样需要定期轮换，通常通过 Ansible/Salt 等配置管理工具配合 CFSSL 工具链实现。

**面试加分点**：提到 API Server 的 `kube-apiserver` 启动参数 `--tls-cert-file` 和 `--tls-private-key-file`，说明证书路径配置方式。

---

## Q8: 如何设计生产环境的权限矩阵？

生产环境推荐**分层权限模型**：

```
Level 1: 集群管理员（ClusterRoleBinding，仅限少数人）
    ↓ 使用范围受限的管理员（ClusterRole with limited scope）
    ↓ 应用开发者（Role in own namespace）
    ↓ 应用运行时（最小 ServiceAccount 权限）
```

**具体实践**：

1. **应用开发者 namespace**：给 DevOps 团队绑定 `edit` 或 `admin` Role（仅限自己的 namespace）
2. **CI/CD Pipeline**：
   ```yaml
   # pipeline-sa 最小权限
   kind: Role
   apiVersion: rbac.authorization.k8s.io/v1
   metadata:
     name: ci-pipeline
     namespace: production
   rules:
   - apiGroups: [""]
     resources: ["pods"]
     verbs: ["get", "list", "watch", "create", "update", "patch"]
   - apiGroups: [""]
     resources: ["pods/log"]
     verbs: ["get"]
   ```
3. **只读监控账号**：
   ```yaml
   kind: ClusterRole
   apiVersion: rbac.authorization.k8s.io/v1
   metadata:
     name: readonly-all
   rules:
   - apiGroups: ["*"]
     resources: ["*"]
     verbs: ["get", "list", "watch"]
   ```
4. **禁止规则**：`nevergreen` 机制在 Kubernetes 1.29+ 支持拒绝规则（Denying Rules），可以明确禁止某些危险操作。

---

## Q9: Pod 如何安全地使用 ServiceAccount？

**最小特权原则在 Pod 层面的实践**：

### 自动挂载问题

默认情况下，每个 Pod 会自动挂载其 SA 的 Token。如果 Pod 不需要访问 API Server，应当显式禁止：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: static-job
  namespace: production
spec:
  serviceAccountName: default  # 不需要 API 访问
  automountServiceAccountToken: false  # 禁止自动挂载 Token
```

### 使用专用 SA（最佳实践）

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service-sa
  namespace: production
---
# 只授予该应用需要的最小权限
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: order-service-role
  namespace: production
rules:
- apiGroups: [""]
  resources: ["services"]
  verbs: ["get", "list"]
- apiGroups: ["networking.k8s.io"]
  resources: ["ingresses"]
  verbs: ["get"]
```

---

## Q10: 什么是 PSP（PodSecurityPolicy）？已被什么替代？

**PodSecurityPolicy（PSP）是历史遗留的集群级安全策略**，用于控制 Pod 的安全上下文（如特权模式、HostPath 挂载、容器 Capability 等）。但 PSP 设计复杂，2021 年已标记废弃，**Kubernetes 1.25+ 已完全移除**。

**PSP 的替代方案**：

1. **Pod Security Standards（PSS）**：Kubernetes 官方的安全分级标准（Privileged / Baseline / Restricted）
2. **Pod Security Admission（PSA）**：内置的准入控制器，强制实施 PSS
3. **第三方方案**：Open Policy Agent（OPA/Gatekeeper）是最流行的 PSP 替代品

```yaml
# PSA 配置示例
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted  # 强制 Restricted 级别
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

---

## 面试总结

| 问题 | 核心答案 |
|------|---------|
| K8s 安全模型三层 | 认证→授权→准入控制 |
| 认证方式 | SA Token、Node 认证、X.509 证书、Bootstrap Token、OIDC |
| RBAC 核心概念 | Role/ClusterRole（定义权限）+ RoleBinding/ClusterRoleBinding（绑定到主体） |
| Role vs ClusterRole | Role 限于 namespace，ClusterRole 集群级或跨 namespace |
| 权限排查工具 | `kubectl auth can-i`、describe、审计日志 |
| SA vs User | SA 用于 Pod，User 用于人；SA 由 K8s 管理，User 由外部 IdP 管理 |
| 生产权限矩阵 | 分层：集群管理员→namespace 管理员→应用运行时→最小 SA 权限 |

---

## 下期预告

K8s 与云原生面试八股文（十）将聚焦**网络策略与零信任安全**：Kubernetes NetworkPolicy 的实现原理、Cilium eBPF 层的网络控制，以及如何用零信任理念设计 Pod 间安全通信。
