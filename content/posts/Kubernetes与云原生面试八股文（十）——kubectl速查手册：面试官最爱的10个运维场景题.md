---
title: Kubernetes与云原生面试八股文（十）——kubectl速查手册：面试官最爱的10个运维场景题
date: 2026-08-30 10:00:00+08:00
updated: '2026-08-30T10:00:00+08:00'
description: 作为 K8s 系列收官之作，本文聚焦 kubectl 命令行工具的实战技巧，梳理面试中出现频率最高的 10 个运维场景：从 Pod 生命周期管理、资源排查、日志采集到集群诊断、滚动更新与回滚、污点容忍等核心操作，配合生产级案例代码和面试问答模板，帮你把 kubectl 用成肌肉记忆。
topic: devops-cloud
series: k8s-cloud-native-interview
series_order: 10
level: intermediate
status: maintained
tags:
- Kubernetes
- kubectl
- 云原生
- 面试
- 运维
- 故障排查
categories:
- DevOps 与云原生
draft: false
---

## 前言

前八篇文章我们从 K8s 架构核心、Pod 生命周期、工作负载管理、Service 网络、存储卷、Helm GitOps、高可用灾备，到认证机制与 RBAC 做了系统梳理。

作为 K8s 系列收官之作，本文回归一个最朴素的问题：**面试官最常通过什么来考察候选人的 K8s 实战能力？**

答案很统一——**kubectl 命令行**。不是问你概念，而是给你一个真实场景：「Pod 起不来、Service 访问不通、节点 NotReady、滚动更新失败……」然后让你当场敲命令。

这篇文章整理了 10 个高频运维场景，配上命令模板和面试问答参考，把 kubectl 用成肌肉记忆。

---

## 场景一：Pod 起不来——从创建到失败的完整排查链

### 经典面试题

> 「一个 Deployment 下的 Pod 一直处于 Pending 状态，你觉得可能有哪些原因？」

### 排查命令链

```bash
# 1. 看 Pod 状态（最直接）
kubectl get pod <pod-name> -n <namespace> -o wide

# 2. 看详细事件（最关键！）
kubectl describe pod <pod-name> -n <namespace>

# 3. 如果是 ImagePullBackOff，看具体镜像
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[0].image}'

# 4. 如果是 Evicted（资源不足被驱逐）
kubectl get pod -n <namespace> --field-selector=status.phase=Evicted

# 5. 查看节点资源是否足够
kubectl describe node <node-name> | grep -A 5 "Allocated resources"
```

### 常见原因汇总

| 状态 | 常见原因 | 解决方向 |
|------|---------|---------|
| Pending | 资源不足（CPU/内存不够）、PVC 未绑定、调度失败 | 增加节点 / 调整资源申请 / 检查 StorageClass |
| ImagePullBackOff | 镜像名错误、私有仓库未配置 Secret、网络不通 | 修正镜像地址 / 创建 imagePullSecrets |
| CrashLoopBackOff | 应用启动脚本错误、健康检查配置不当、依赖服务不可达 | 检查 liveness/readiness 探针 / 看日志 |
| Terminating | Finalizers 卡死、资源删除链断裂 | 强制删除（慎用）/ 检查 CRD finalizer |
| Evicted | 节点资源压力导致 Pod 被驱逐 | 扩容 / 调低资源 requests / 清理节点 |

### 面试加分回答

> 「我会先用 `kubectl describe pod` 看 Events 字段，这是定位 Pending 原因的第一入口。如果显示 '0/1 nodes are available: 1 Insufficient cpu'，就说明调度阶段失败了；如果显示 'pod has unbound immediate PersistentVolumeClaims'，就说明 PVC 没有可用的 PV，此时要看 StorageClass 配置和集群 PV 状态。」

---

## 场景二：Pod 正常运行但 Service 访问不通

### 经典面试题

> 「Pod 是 Running 的，但 curl Service IP 不通，你觉得问题在哪？」

### 排查命令链

```bash
# 1. 确认 Pod IP 和 Service IP
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.podIP}'
kubectl get svc <svc-name> -n <namespace> -o jsonpath='{.spec.clusterIP}'

# 2. 在 Pod 里直接 curl Pod IP（验证应用本身是否正常）
kubectl exec -it <pod-name> -n <namespace> -- curl -s http://<pod-ip>:8080/health

# 3. 在 Pod 里 curl Service IP（验证 kube-proxy 是否工作）
kubectl exec -it <pod-name> -n <namespace> -- curl -s http://<svc-cluster-ip>:80

# 4. 查看 Service 的 Endpoint 是否健康
kubectl get endpoints <svc-name> -n <namespace>

# 5. 查看 kube-proxy 日志（定位 iptables/ipvs 规则问题）
kubectl logs -n kube-system -l k8s-app=kube-proxy
```

### 核心原理

Service 的 ClusterIP 并不是真实 IP，而是通过 **kube-proxy** 在每个节点上生成的 iptables/ipvs 规则来实现的。如果 Endpoints 为空，说明 Selector 没有匹配到任何 Pod。

```bash
# 如果 Endpoints 为空，先检查标签是否匹配
kubectl get pods -n <namespace> --show-labels | grep <selector-label>
```

---

## 场景三：节点 NotReady——集群层面的系统性排查

### 经典面试题

> 「生产集群中突然有 3 个节点变成 NotReady，你会怎么排查？」

### 排查命令链

```bash
# 1. 看节点状态
kubectl get node
kubectl get node -o wide

# 2. 看节点详细状态和事件
kubectl describe node <node-name>

# 3. 重点检查 Conditions
kubectl get node <node-name> -o jsonpath='{.status.conditions[*].type}'
# 常见问题类型：
# - MemoryPressure：内存不足
# - DiskPressure：磁盘不足
# - PIDPressure：进程数不足
# - NetworkUnavailable：网络配置问题

# 4. kubelet 日志（最直接定位 kubelet 自身问题）
journalctl -u kubelet -n 100 --no-pager

# 5. 检查节点上的 kubelet 进程和证书
systemctl status kubelet
openssl x509 -in /var/lib/kubelet/pki/kubelet.crt -noout -dates
```

### 面试加分：节点压力场景处理流程

> 「我的排查思路是：先通过 `kubectl describe node` 判断是资源问题还是组件问题。如果是 MemoryPressure，第一时间迁移 Pod：`kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data`，然后清理节点或扩容。如果是 kubelet 组件自身挂了，先看 journal 日志，再用 `systemctl restart kubelet`，如果 kubelet 证书过期则需要更新证书。」

---

## 场景四：日志采集——kubectl logs 的进阶用法

### 基础到进阶

```bash
# 标准用法：看主容器日志
kubectl logs <pod-name> -n <namespace>

# 带时间戳（必须先加 -t 开启 TTY）
kubectl logs <pod-name> -n <namespace> -t

# 实时 tail（相当于 tail -f）
kubectl logs -f <pod-name> -n <namespace>

# 查看上一个容器的日志（重启前的日志，非常有用！）
kubectl logs <pod-name> -n <namespace> --previous

# 多容器 Pod：指定容器名
kubectl logs <pod-name> -n <namespace> -c <container-name>

# 按标签选择多个 Pod，聚合日志
kubectl logs -l app=nginx -n <namespace> --all-containers=true

# 导出日志到文件（用于分析）
kubectl logs <pod-name> -n <namespace> > pod.log

# 结合 grep 过滤
kubectl logs <pod-name> -n <namespace> | grep ERROR
```

### 面试题：kubectl logs 拿不到日志怎么办？

> 常见原因：容器启动脚本没有输出到 stdout/stderr、应用写到文件而不是标准输出、日志驱动配置问题（json-file vs journald）。

```bash
# 检查 Pod 的日志配置
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.containers[*].resources}'

# 看 Docker 日志驱动（节点层面）
cat /etc/docker/daemon.json
# 应配置为 "log-driver": "json-file"
```

---

## 场景五：滚动更新与回滚——Deployment 的黄金操作

### 标准滚动更新流程

```bash
# 触发滚动更新（改镜像版本）
kubectl set image deployment/<deploy-name> <container-name>=<new-image> -n <namespace>

# 查看滚动更新状态
kubectl rollout status deployment/<deploy-name> -n <namespace>

# 查看历史版本
kubectl rollout history deployment/<deploy-name> -n <namespace>

# 查看特定版本的详细信息
kubectl rollout history deployment/<deploy-name> -n <namespace> --revision=3

# 回滚到上一个版本
kubectl rollout undo deployment/<deploy-name> -n <namespace>

# 回滚到指定版本
kubectl rollout undo deployment/<deploy-name> -n <namespace> --to-revision=2
```

### 滚动更新策略配置（面试常考）

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%        # 最多超出多少 Pod（默认25%）
      maxUnavailable: 25%  # 最多有多少 Pod 不可用（默认25%）
```

> **面试题：maxSurge 和 maxUnavailable 设为 0 会怎样？**
>
> 滚动更新会卡住！因为没有额外容量可以替换旧 Pod，也无法删除旧 Pod，Deployment 卡在 progress 状态。

### 暂停与恢复（渐进式发布）

```bash
# 暂停（适合金丝雀发布：先更新一小部分验证）
kubectl rollout pause deployment/<deploy-name> -n <namespace>

# 验证没问题后恢复
kubectl rollout resume deployment/<deploy-name> -n <namespace>
```

---

## 场景六：资源限制与配额——namespace 层面的Quota管理

### 核心面试题

> 「如何在 namespace 层面限制资源使用，防止某个应用吃光整个集群资源？」

### 命令链

```bash
# 创建 ResourceQuota
kubectl create quota <quota-name> \
  --hard=cpu=20,memory=40Gi,pods=100,services=10 \
  -n <namespace>

# 创建 LimitRange（设置 Pod/Container 默认资源限制）
kubectl create limitrange <limit-name> \
  --default-cpu=200m --default-memory=512Mi \
  --min-cpu=50m --min-memory=128Mi \
  --max-cpu=4 --max-memory=8Gi \
  -n <namespace>

# 查看 namespace 资源使用情况
kubectl describe resourcequota -n <namespace>
kubectl describe limitrange -n <namespace>

# 实时看各 Pod 的资源使用（需要 Metrics Server）
kubectl top pod -n <namespace>
kubectl top node
```

### LimitRange 与 ResourceQuota 的区别

| 对象 | 作用层级 | 解决的问题 |
|------|---------|-----------|
| LimitRange | namespace 内单个 Pod/Container | 防止未设限的容器无限申请资源 |
| ResourceQuota | namespace 整体 | 防止 namespace 总用量超限 |

---

## 场景七：污点（Taints）与容忍（ Tolerations）——精准调度

### 核心概念

污点作用于**节点**，容忍作用于 **Pod**。节点通过 Taint 声明「我不接受普通 Pod」，Pod 通过 Toleration 表示「我能接受这类 Taint」。

### 常用命令

```bash
# 查看节点的污点
kubectl describe node <node-name> | grep -A 5 Taints

# 给节点打污点（NoSchedule：不允许新Pod调度；NoExecute：驱逐已有Pod）
kubectl taint node <node-name> key=value:NoSchedule
kubectl taint node <node-name> dedicated=ml-gpu:NoExecute

# 去除污点
kubectl taint node <node-name> key:NoSchedule-
kubectl taint node <node-name> dedicated-

# Pod 配置容忍（YAML 片段）
spec:
  tolerations:
    - key: "dedicated"
      operator: "Equal"
      value: "ml-gpu"
      effect: "NoExecute"
      tolerationSeconds: 3600  # 容忍3600秒后才会被驱逐
    - key: "node.kubernetes.io/not-ready"
      operator: "Exists"
      effect: "NoExecute"
      tolerationSeconds: 300  # 节点 NotReady 时容忍300秒
```

### 经典面试题

> 「集群有一批 GPU 节点专门跑机器学习任务，怎么让普通 Web 服务不调度到这些节点？」

> 「GPU 节点打了 `nvidia.com/gpu: true:NoSchedule` 污点，一个 ML 训练 Job 怎样才能调度上去？」

> 「节点进入维护模式（cordon + drain）时，Pod 是立即被驱逐吗？有没有优雅等待期？」

---

## 场景八：ConfigMap 与 Secret 的热更新

### 基础操作

```bash
# 创建 ConfigMap（从文件）
kubectl create configmap app-config --from-file=application.yml -n <namespace>

# 创建 ConfigMap（从字面量）
kubectl create configmap app-env --from-literal=ENV=prod --from-literal=LOG_LEVEL=info -n <namespace>

# 查看 ConfigMap
kubectl get configmap app-config -n <namespace> -o yaml

# 加密查看 Secret（需要解码）
kubectl get secret db-credentials -n <namespace> -o jsonpath='{.data.password}' | base64 -d
```

### 热更新问题（面试高频）

ConfigMap 和 Secret 挂载为卷时，默认**不会自动更新**。需要以下方式触发更新：

```bash
# 方式1：滚动更新 Pod（强制重建）
kubectl rollout restart deployment/<deploy-name> -n <namespace>

# 方式2：开启自动同步（subPath 问题需注意）
# subPath 会导致卷内容不更新，解决方案是不用 subPath

# 方式3：使用 envFrom 注入（配合 reload 机制）
# 应用需要监听配置变更并 reload
```

> **面试题：ConfigMap 挂载后修改，Pod 里的文件会自动更新吗？**
>
> 不会。需要重建 Pod 或重启应用。生产环境推荐使用配置中心（如 Apollo/Nacos）来做动态配置推送，而不是依赖 ConfigMap 热更新。

---

## 场景九：临时调试——kubectl debug 与临时容器

### 临时进入容器

```bash
# 标准 exec
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# 如果容器没有 shell（如 distroless 镜像）
kubectl exec -it <pod-name> -n <namespace> -- cat /etc/os-release

# 如果是多个容器，指定容器
kubectl exec -it <pod-name> -c <container-name> -n <namespace> -- /bin/bash
```

### kubectl debug（K8s 1.23+，临时容器）

```bash
# 调试一个运行中的 Pod（创建临时容器，带网络工具）
kubectl debug <pod-name> -it --image=busybox --share-processes --copy-to=debug-pod -n <namespace>

# 调试节点（创建节点级调试容器）
kubectl debug node/<node-name> -it --image=busybox -- crictr exec -it <container-id> sh

# 在 Pod 中注入带有网络工具的临时容器
kubectl debug <pod-name> -it --container=debugger --image=nicolaka/netshoot -n <namespace>
```

### 经典场景题

> 「Pod 里的应用是只读文件系统，没有 bash，只有 sh，且没有 curl/wget，怎么排查网络？」

```bash
# 方式1：临时容器注入网络工具
kubectl debug <pod-name> --image=nicolaka/netshoot -it -c debugger -n <namespace>

# 方式2：用 nsenter 进入 Pod 的网络命名空间
PID=$(kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.status.containerStatuses[0].containerID}' | sed 's|containerd://||')
nsenter -t $PID -n curl http://service-name.namespace.svc.cluster.local
```

---

## 场景十：网络策略（NetworkPolicy）——微服务安全隔离

### 基础命令

```bash
# 查看 namespace 的网络策略
kubectl get networkpolicy -n <namespace>

# 查看详细配置
kubectl describe networkpolicy <policy-name> -n <namespace>

# 查看某 Pod 的入站/出站规则（需要网络插件支持，如 Calico）
kubectl get networkpolicy <pod-name> -n <namespace> -o yaml
```

### 典型 NetworkPolicy 示例（面试必考）

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-allow-frontend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api-service
  policyTypes:
    - Ingress    # 只定义入站规则
    - Egress     # 可选：定义出站规则
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
```

> **面试题：NetworkPolicy 写了不生效，怎么排查？**
>
> 1. 确认网络插件是否支持 NetworkPolicy（Cilium/Calico 支持，Flannel 不支持）
> 2. 检查 Policy 规则的 podSelector 标签是否和 Pod 实际标签匹配
> 3. 检查是否定义了 `policyTypes`，未定义则规则不生效
> 4. 用 `kubectl logs` 查看 CNI 插件日志

---

## 面试核心考点总结

| 场景 | 核心考点 | 命令关键词 |
|------|---------|-----------|
| Pod Pending | 调度失败、资源不足、存储未绑定 | `describe pod` / `kubectl get events` |
| Service 不通 | kube-proxy / Endpoints / 标签匹配 | `kubectl get endpoints` / `kubectl logs kube-proxy` |
| 节点 NotReady | kubelet / 资源压力 / 证书过期 | `describe node` / `journalctl -u kubelet` |
| 日志采集 | stdout/stderr / previous / 多容器 | `kubectl logs -f --previous -c` |
| 滚动更新 | maxSurge/maxUnavailable / 回滚 | `rollout status/undo/history` |
| 资源配额 | LimitRange / ResourceQuota / top | `create quota` / `kubectl top pod` |
| 污点容忍 | Taint/Toleration / 调度策略 | `kubectl taint node` / `tolerations` |
| 配置热更新 | subPath / envFrom / reload | `rollout restart` |
| 临时调试 | kubectl debug / nsenter / netshoot | `kubectl debug` / `nsenter` |
| 网络策略 | NetworkPolicy / CNI 支持 | `kubectl get networkpolicy` |

---

## 结语

kubectl 是 K8s 工程师的「第二语言」。面试官不会只问你"知道哪些命令"，而是给你一个真实场景让你分析、排查、解决。

这篇文章覆盖了 10 个最常见的运维场景，覆盖了 Pod、Node、Network、Storage、Config 五大核心维度。把这 10 个场景的命令练熟、原理搞懂，K8s 面试的命令行部分就游刃有余了。

K8s 系列从架构核心到生产高可用，覆盖了从入门到进阶的核心知识体系。祝大家面试顺利！ 🚀

---

## 系列完结索引

- **Kubernetes与云原生面试八股文（一）**——Kubernetes架构核心与集群管理
- **Kubernetes与云原生面试八股文（二）**——Pod深入与工作负载管理
- **Kubernetes与云原生面试八股文（三）**——Service与网络通信
- **Kubernetes与云原生面试八股文（四）**——存储卷与数据持久化
- **Kubernetes与云原生面试八股文（五）**——配置管理与安全
- **Kubernetes与云原生面试八股文（六）**——Helm包管理与GitOps
- **Kubernetes与云原生面试八股文（七）**——可观测性与故障排查
- **Kubernetes与云原生面试八股文（八）**——生产级高可用与灾备
- **Kubernetes与云原生面试八股文（九）**——一次权限配置失误引发的生产事故：从认证机制到RBAC最佳实践
- **Kubernetes与云原生面试八股文（十）**——kubectl速查手册：面试官最爱的10个运维场景题 ← 本篇
