---
title: Kubernetes与云原生面试八股文（七）——可观测性与故障排查
date: 2026-08-08T10:00:00+08:00
updated: '2026-08-08T10:00:00+08:00'
description: '面试高频问题：Prometheus 是如何采集 K8s 指标的？Grafana 如何自定义监控面板？Loki 的标签体系怎么设计？Jaeger 链路追踪如何排查跨服务慢请求？K8s 故障排查的标准流程是什么？本文系统讲解 Kubernetes 可观测性体系与生产级故障排查实战。
  Q: 可观测性三支柱是什么？'
topic: distributed-systems
series: k8s-cloud-native-interview
series_order: 7
level: intermediate
status: maintained
tags:
- 面试
- Kubernetes
- Prometheus
- Grafana
- 可观测性
categories:
- 分布式与微服务
draft: false
author: 飞哥
---

> 面试高频问题：Prometheus 是如何采集 K8s 指标的？Grafana 如何自定义监控面板？Loki 的标签体系怎么设计？Jaeger 链路追踪如何排查跨服务慢请求？K8s 故障排查的标准流程是什么？本文系统讲解 Kubernetes 可观测性体系与生产级故障排查实战。
>
> Q: 可观测性三支柱是什么？

## 系列导航

| 期数 | 主题 | 核心内容 |
|------|------|---------|
| 第一期 | K8s 架构核心与集群管理 | 控制平面/数据平面、etcd、kubelet、kubectl 原理 |
| 第二期 | Pod 深入与工作负载管理 | Pod 生命周期、Deployment/StatefulSet/DaemonSet、调度器 |
| 第三期 | Service 与网络通信 | Service 类型、kube-proxy、Ingress、CNI、NetworkPolicy |
| 第四期 | 存储卷与数据持久化 | Volume 类型、PV/PVC、StorageClass、CSI、StatefulSet 存储 |
| 第五期 | 配置管理与安全 | ConfigMap/Secret、RBAC、Pod Security、SA Token、NetworkPolicy、证书轮转 |
| 第六期 | Helm 包管理与 GitOps | Chart 结构、模板引擎、OCI Registry、ArgoCD/FluxCD、多环境配置、渐进式发布 |
| **第七期** | **可观测性与故障排查** | **Prometheus、Grafana、Loki、Jaeger、诊断工作流** |
| 第八期 | 生产级高可用与灾备（预告） | 多集群联邦、DR 策略、备份恢复、成本优化 |

---

## 一、可观测性理论基础

### 1.1 什么是可观测性

可观测性（Observability）源自控制理论，最早由匈牙利裔美国工程师鲁道夫·卡尔曼提出。在云原生领域，可观测性是指**通过系统外部输出的数据来推断其内部状态的能力**。与传统监控不同，可观测性更强调对未知问题的发现能力——系统能够告诉我们它不知道什么，而不是只告诉我们它知道什么。

**可观测性三支柱**（Three Pillars）包括：

- **Metrics（指标）**：数值型的聚合数据，如 CPU 使用率、请求 QPS、错误率等，支持时间序列查询和告警。
- **Logs（日志）**：离散的事件记录，包含时间戳、级别、消息内容等，用于追溯问题根因。
- **Traces（追踪）**：贯穿分布式请求路径的完整调用链，记录每个服务的耗时和调用关系。

> **面试高频问题**：三支柱的取舍问题
>
> 很多人认为可观测性必须同时具备三个支柱，实际上这取决于业务场景。Google 的 SRE 团队提出"监控的四个黄金信号"——**延迟、流量、错误和饱和度**，这是更实用的可观测性建设方向。很多中小型团队从 Metrics 入手，逐步引入 Logs 和 Traces，是更务实的路径。

### 1.2 Kubernetes 可观测性的特殊性

在 Kubernetes 环境中，可观测性面临独特的挑战：

1. **高度动态的 Pod 生命周期**：Pod 随时可能被调度、重启、驱逐，传统基于 IP 的监控方案无法持久。
2. **多租户与命名空间隔离**：不同团队的应用部署在不同命名空间，需要细粒度的权限和视图控制。
3. **服务网格带来的复杂性**：Sidecar 代理（如 Envoy、Istio）使得网络追踪变得更加重要，同时也增加了数据量。
4. **基础设施与应用层边界模糊**：K8s 本身、容器运行时、网络插件、存储系统都产生大量指标，需要统一采集和关联。

---

## 二、Prometheus 监控体系

### 2.1 Prometheus 核心原理

Prometheus 是 CNCF 毕业项目，专为云原生环境设计的时序数据库和监控系统。其核心架构如下：

```
┌─────────────────────────────────────────────────┐
│                  Prometheus Server              │
│  ┌──────────────┐    ┌──────────────────────┐  │
│  │ ServiceDiscov│───▶│    TSDB (本地存储)    │  │
│  │ (K8s/SD/File)│    │  时序数据库，2H保留   │  │
│  └──────────────┘    └──────────────────────┘  │
│         │                     │                 │
│         ▼                     ▼                 │
│  ┌──────────────┐    ┌──────────────────────┐  │
│  │  Retriever   │    │   Alertmanager       │  │
│  │  拉取指标    │    │   触发告警规则       │  │
│  └──────────────┘    └──────────────────────┘  │
└─────────────────────────────────────────────────┘
         │                     │
         ▼                     ▼
┌────────────────┐     ┌─────────────────┐
│  exporters     │     │   Alertmanager  │
│  暴露指标端点  │     │   聚合去重告警  │
└────────────────┘     └─────────────────┘
```

Prometheus 采用**拉模式**（Pull-based）采集指标，通过 HTTP 接口定期从各个目标拉取数据。这种设计有以下优势：

- **无代理模式**：应用只需暴露 HTTP 端点，无需安装额外 agent，减少资源占用。
- **动态发现**：通过 Kubernetes SD（Service Discovery）自动发现集群中的 Pod 和 Service。
- **去中心化**：无需在每个节点部署收集器，网络故障不影响采集。

### 2.2 Kubernetes 服务发现机制

Prometheus 通过 `kubernetes_sd_configs` 自动发现集群资源。以下是完整的配置示例：

```yaml
# prometheus-config.yaml
scrape_configs:
  # 自动发现 Node 级别指标
  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - source_labels: [__address__]
        regex: '(.*):10250'
        replacement: '${1}:9100'
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - action: labelmap
        regex: __meta_kubernetes_node_label_(.+)

  # 自动发现 Pod 指标
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # 只采集标注了 prometheus.io/scrape=true 的 Pod
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      # 从 annotation 获取路径和端口
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
        replacement: '${1}'
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: '([^:]+):(\d+)'
        replacement: '${1}:${2}'
        target_label: __address__
      # 保留 namespace 和 pod 标签
      - action: labelmap
        regex: __meta_kubernetes_pod_label_(.+)
```

**面试高频问题**：为什么 Prometheus 选择拉模式而非推模式？

拉模式的优势包括：更容易实现跨集群采集（只需一个 Prometheus 端点）、更容易进行目标健康检查（超时则跳过）、方便在本地进行聚合（减少网络传输）、便于调试（可以直接 curl 目标端点）。但拉模式的缺点是：高 cardinality 指标时性能压力大，此时可以考虑 PushGateway 作为中转。

### 2.3 常用 Exporter 介绍

Prometheus 生态中有大量现成的 Exporter 用于采集各类指标：

| Exporter | 采集内容 | 端口 |
|----------|----------|------|
| node-exporter | 主机 CPU、内存、磁盘、网络 | 9100 |
| kube-state-metrics | K8s 对象状态（Deployment、Pod、Service） | 8080 |
| cadvisor | 容器级别资源使用（CPU、内存、文件系统） | 8080 |
| blackbox-exporter | HTTP/TCP/ICMP 探活检测 | 9115 |
| redis-exporter | Redis 内存、命令、连接数 | 9121 |
| mysql-exporter | MySQL 查询、连接、InnoDB 状态 | 9104 |
| nginx-ingress-controller | Ingress 请求量、延迟、错误率 | 10254 |

部署 node-exporter 的标准方式：

```bash
# DaemonSet 方式部署，确保每个节点都运行
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostPID: true
      hostNetwork: true
      containers:
        - name: node-exporter
          image: prom/node-exporter:v1.7.0
          args:
            - '--path.procfs=/host/proc'
            - '--path.sysfs=/host/sys'
            - '--path.rootfs=/host'
          ports:
            - containerPort: 9100
              hostPort: 9100
          volumeMounts:
            - name: proc
              mountPath: /host/proc
            - name: sys
              mountPath: /host/sys
            - name: root
              mountPath: /host/root
          resources:
            requests:
              cpu: 100m
              memory: 50Mi
            limits:
              cpu: 200m
              memory: 100Mi
      volumes:
        - name: proc
          hostPath:
            path: /proc
        - name: sys
          hostPath:
            path: /sys
        - name: root
          hostPath:
            path: /
EOF
```

### 2.4 核心 PromQL 查询

面试中经常考察的 PromQL 查询：

```promql
# 1. Pod CPU 使用率（核心数百分比）
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (pod, namespace)
  / sum(container_spec_cpu_quota{container!=""}/container_spec_cpu_period{container!=""}) by (pod, namespace) * 100

# 2. 内存使用率
sum(container_memory_working_set_bytes{container!=""}) by (pod, namespace)
  / sum(container_spec_memory_limit_bytes{container!=""}) by (pod, namespace) * 100

# 3. Pod 重启次数（最近 1 小时）
increase(kube_pod_container_status_restarts_total[1h])

# 4. Deployment 就绪率
kube_deployment_status_replicas_ready{deployment="your-app"}
  / kube_deployment_spec_replicas{deployment="your-app"}

# 5. 命名空间级别 QPS
sum(rate(http_requests_total[5m])) by (namespace, service, status_code)

# 6. P99 延迟（需要 Histogram）
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))
```

> **面试高频问题**：Histogram 和 Summary 的区别是什么？
>
> 两者都用于记录分位数，但实现方式不同。Histogram 在客户端只记录 bucket 计数器，百分位数在服务端通过 `histogram_quantile()` 计算，优点是服务端可聚合、灵活调整分位数，缺点是精度依赖 bucket 划分。Summary 在客户端计算并直接上报百分位数，精度高但不可聚合。**生产环境推荐使用 Histogram**，因为可以跨实例聚合计算全局 P99。

---

## 三、Grafana 可视化实战

### 3.1 Grafana + Prometheus 集成

Grafana 是最流行的可视化平台，与 Prometheus 深度集成。标准安装通过 Helm Chart：

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm install grafana grafana/grafana \
  --namespace monitoring \
  --set adminPassword='your-secure-password' \
  --set persistence.enabled=true \
  --set persistence.size=10Gi \
  --set datasources.datasources.prometheus.type=prometheus \
  --set datasources.datasources.prometheus.url=http://prometheus-server:80
```

### 3.2 常用监控面板 JSON

**Pod 资源使用面板**（简化版 JSON Panel）：

```json
{
  "title": "Pod CPU & Memory Usage",
  "type": "timeseries",
  "gridPos": { "x": 0, "y": 0, "w": 24, "h": 8 },
  "targets": [
    {
      "expr": "sum(rate(container_cpu_usage_seconds_total{namespace=\"$namespace\", pod=\"$pod\"}[5m])) by (pod)",
      "legendFormat": "CPU Cores",
      "refId": "A"
    },
    {
      "expr": "sum(container_memory_working_set_bytes{namespace=\"$namespace\", pod=\"$pod\"}) by (pod) / 1024 / 1024",
      "legendFormat": "Memory MB",
      "refId": "B"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "short",
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "green", "value": null },
          { "color": "yellow", "value": 70 },
          { "color": "red", "value": 90 }
        ]
      }
    }
  }
}
```

### 3.3 告警规则配置

```yaml
# prometheus-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: k8s-alerts
  namespace: monitoring
spec:
  groups:
    - name: k8s-pod-alerts
      rules:
        # Pod CPU 使用率超过 80% 持续 5 分钟
        - alert: PodHighCPU
          expr: |
            sum(rate(container_cpu_usage_seconds_total{container!=""}[5m])) by (namespace, pod)
              / sum(container_spec_cpu_quota{container!=""}/container_spec_cpu_period{container!=""}) by (namespace, pod) * 100 > 80
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} CPU 使用率过高"
            description: "CPU 使用率 {{ $value | printf \"%.2f\" }}% 超过 80%，持续 5 分钟"

        # Pod 连续重启
        - alert: PodRestartingFrequently
          expr: increase(kube_pod_container_status_restarts_total[1h]) > 3
          for: 1m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.pod }} 重启过于频繁"
            description: "过去 1 小时重启 {{ $value }} 次"

        # Deployment 副本数不足
        - alert: DeploymentReplicasUnavailable
          expr: |
            kube_deployment_spec_replicas{namespace=~".+"}
              - kube_deployment_status_replicas_available{namespace=~".+"} > 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Deployment {{ $labels.namespace }}/{{ $labels.deployment }} 副本不可用"
```

---

## 四、Loki 日志聚合系统

### 4.1 Loki 架构设计

Loki 是 Grafana Labs 开发的日志聚合系统，与 Prometheus 设计理念一脉相承——**只索引日志元数据，不索引日志内容**，因此资源消耗远低于 ELK 栈。

```
┌──────────────────────────────────────────────────────────┐
│                        Grafana                           │
│              日志查询与可视化界面                        │
└──────────────────────┬───────────────────────────────────┘
                       │ 查询
┌──────────────────────▼───────────────────────────────────┐
│                   QueryFrontend                          │
│         查询拆分、缓存、结果聚合                         │
└──────┬───────────────────────────────────────┬───────────┘
       │                                       │
┌──────▼──────┐                      ┌─────────▼──────────┐
│   Querier   │                      │      Querier       │
│  (查询实例) │                      │    (查询实例)      │
└──────┬──────┘                      └─────────┬──────────┘
       │                                       │
┌──────▼───────────────────────────────────────▼───────────┐
│                        Distributor                         │
│              日志分片、压缩、写 入                        │
└──────┬───────────────────────────────────────┬───────────┘
       │                                       │
┌──────▼──────┐                      ┌─────────▼──────────┐
│  Ingester   │  ──WAL──▶            │      Compactor     │
│  (写入实例) │                       │   日志压缩去重     │
└──────┬──────┘                       └─────────┬──────────┘
       │                                       │
┌──────▼───────────────────────────────────────▼───────────┐
│                   Object Store (S3/MinIO)                  │
│              Chunk 数据 + 索引 (按标签分片)               │
└───────────────────────────────────────────────────────────┘
```

### 4.2 Promtail 采集配置

Promtail 是 Loki 的日志采集代理，支持 Kubernetes SD：

```yaml
# promtail-config.yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /run/promtail/positions.yaml

clients:
  - url: http://loki-gateway:3100/loki/api/v1/push

scrape_configs:
  # 采集 Pod 日志（标准输出）
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      # 从 Pod annotation 获取标签
      - action: replace
        source_labels: [__meta_kubernetes_pod_annotation_monitor]
        target_label: monitor
      # 保留命名空间和 Pod 名称作为标签
      - action: labelmap
        regex: __meta_kubernetes_pod_label_(.+)
        replacement: ${1}
      # 提取日志路径
      - action: replace
        source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        target_label: __path__
        regex: (.+)
        replacement: '${1}'
      # 默认日志路径
      - action: replace
        target_label: __path__
        replacement: /var/log/pods/*/${CONTAINER_NAME}/*.log
    pipeline_stages:
      - docker: {}  # 解析 Docker JSON 日志格式
      - labels:
          namespace: {}
          pod: {}
          container: {}
```

> **面试高频问题**：Loki 的标签设计原则
>
> Loki 使用标签索引而非全文索引，标签设计直接影响查询性能和存储效率。**高 cardinality 标签是性能杀手**——如 `pod_ip`、`user_id`、`request_id` 这类唯一值，不应作为标签，否则会导致索引爆炸。正确的做法是将这类信息放在日志内容中，通过 LogQL 的 `line_format` 过滤。推荐标签：**namespace、pod、container、host、level、service**。

### 4.3 LogQL 查询语法

```logql
# 1. 查询某个 Pod 的所有日志
{service="payment-service", namespace="default"} |= "ERROR"

# 2. 查询最近 5 分钟的错误日志，排除某类无关错误
{service="order-service"} |= "ERROR" != "timeout" | json | level="error"

# 3. 统计 QPS（按分钟）
sum(rate({service="api-gateway"}[1m])) by (namespace)

# 4. 计算平均延迟（需要 JSON 解析）
{service="user-service"} | json | latency_ms > 1000 | line_format "{{.timestamp}} {{.method}} {{.path}} took {{.latency_ms}}ms"

# 5. 关联追踪 ID 查找跨服务日志
{service=~".+"} |= "trace_id=4bf92f3577b34da6"
```

---

## 五、Jaeger 分布式追踪

### 5.1 OpenTelemetry 架构

现代分布式追踪的事实标准是 **OpenTelemetry（OTel）**，它统一了 Traces、Metrics、Logs 的采集规范：

```
┌─────────────────────────────────────────────────────────┐
│                    Instrumentation                       │
│           (应用代码 / SDK / 自动注入)                   │
└──────────────────────────┬──────────────────────────────┘
                           │ OTLP 协议
┌──────────────────────────▼──────────────────────────────┐
│                    OTel Collector                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ Receivers   │  │ Processors  │  │ Exporters       │  │
│  │ (OTLP/Agent)│─▶│ (批处理/采样)│─▶│ (Jaeger/Zipkin) │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Jaeger 部署与采集

```yaml
# jaeger-operator 方式部署
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: production-jaeger
  namespace: observability
spec:
  strategy: production
  collector:
    maxReplicas: 3
    resources:
      requests:
        cpu: 500m
        memory: 512Mi
  query:
    replicas: 2
  storage:
    type: elasticsearch
    elasticsearch:
      nodeCount: 3
      redundancyPolicy: SingleRedundancy
  ingress:
    enabled: true
    className: nginx
```

应用端集成 OpenTelemetry Go SDK：

```go
// main.go
package main

import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

func initTracer() (*trace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(context.Background(),
        otlptracegrpc.WithEndpoint("jaeger-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(
            resource.NewWithAttributes(
                semconv.SchemaURL,
                semconv.ServiceName("payment-service"),
                semconv.ServiceVersion("v1.2.3"),
                semconv.DeploymentEnvironment("production"),
            ),
        ),
        trace.WithSampler(trace.ParentBased(trace.TraceIDRatioBased(0.1))), // 10% 采样率
    )

    otel.SetTracerProvider(tp)
    return tp, nil
}
```

### 5.3 常见 Trace 查询模式

在 Jaeger UI 或 LogQL 中关联追踪：

```logql
# 从 Loki 日志中提取 trace_id 并跳转 Jaeger
{service="order-service"} |= "trace_id" | logfmt | trace_id != ""
```

**面试高频问题**：如何用 Trace 排查慢请求？

标准排查步骤：① 在 Jaeger 中搜索目标 Trace ID；② 从瀑布图中找到耗时最长的 Span；③ 确认是自身处理耗时还是下游调用耗时；④ 如果是下游调用，进一步查看下游服务 Span；⑤ 确认是数据库查询慢（查看 Span 标签中的 `db.statement`）还是网络延迟（查看 `net.peer.name` 和延迟）；⑥ 结合 Logs 关联到具体代码行。

---

## 六、Kubernetes 故障排查方法论

### 6.1 诊断工作流

K8s 故障排查遵循标准化的四层诊断模型：

```
┌────────────────────────────────────────────────────┐
│  Layer 1: 基础设施层                               │
│  Node 状态、CNI 连接、存储挂载                     │
│  命令: kubectl get nodes / kubectl describe node  │
├────────────────────────────────────────────────────┤
│  Layer 2: 控制平面层                               │
│  API Server、etcd、Controller、Scheduler 健康      │
│  命令: kubectl get componentstatuses              │
├────────────────────────────────────────────────────┤
│  Layer 3: 工作负载层                               │
│  Pod、Deployment、Service、Ingress 配置正确性      │
│  命令: kubectl get pods -n xxx / kubectl logs    │
├────────────────────────────────────────────────────┤
│  Layer 4: 应用层                                   │
│  应用日志、探针状态、资源使用、配置注入            │
│  命令: kubectl exec / kubectl top pod            │
└────────────────────────────────────────────────────┘
```

### 6.2 Pod 状态诊断

```bash
# 1. 查看 Pod 当前状态和事件
kubectl get pod -n <namespace> <pod-name> -o wide
kubectl describe pod -n <namespace> <pod-name>

# 2. 常见状态与可能原因
# Pending      → 调度失败（资源不足/亲和性/污点）
# CrashLoopBackOff → 应用启动失败（配置错误/依赖不可用）
# ImagePullBackOff → 镜像拉取失败（权限/镜像不存在/网络）
# Terminating  → 删除卡住（Finalizer 阻塞/GC 僵死）
# Error        → 主进程异常退出

# 3. 排查 CrashLoopBackOff 的标准流程
kubectl logs -n <namespace> <pod-name> --previous  # 查看上次崩溃日志
kubectl exec -it -n <namespace> <pod-name> -- /bin/sh  # 进入容器调试

# 4. 资源不足导致 Pending
kubectl describe node <node-name> | grep -A 5 "Allocated resources"
# 查看实际资源分配
kubectl top pod -n <namespace>  # 实时资源使用

# 5. 镜像拉取失败
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
kubectl describe secret <image-pull-secret> -n <namespace>
```

### 6.3 网络问题诊断

```bash
# 1. Service 端点是否就绪
kubectl get endpoints -n <namespace> <service-name>
# 结果为空说明 Selector 没有匹配到 Pod

# 2. DNS 解析测试（进入临时 Pod）
kubectl run dnsutils --image=tutum/dnsutils -n <namespace> --restart=Never -it --rm -- \
  nslookup <service-name>.<namespace>.svc.cluster.local

# 3. 网络连通性测试
kubectl run curl --image=curlimages/curl -n <namespace> --restart=Never -it --rm -- \
  curl -v http://<service-name>.<namespace>.svc.cluster.local:<port>/health

# 4. 查看 Ingress 状态
kubectl describe ingress -n <namespace> <ingress-name>
kubectl get ingress -n <namespace> <ingress-name> -o jsonpath='{.status.loadBalancer}'

# 5. 常见网络问题快速定位表
# Service 无法访问 → 检查 endpoints 是否为空、Pod 是否就绪、探针是否通过
# Ingress 404 → 检查 path、backend service、rewrite 规则
# 外网无法访问 → 检查 LoadBalancer/NodePort 配置、云厂商安全组、Ingress class
```

### 6.4 生产故障案例

**案例：Pod 内存 OOMKilled**

```
问题现象：Pod 被 Kubernetes 强制终止（OOMKilled），重启后反复出现
```

排查步骤：

```bash
# 1. 确认 OOMKilled 状态
kubectl get pod <pod-name> -n <namespace>
# Status: OOMKilled, RestartCount: 持续增加

# 2. 查看资源限制
kubectl describe pod <pod-name> -n <namespace> | grep -A 5 "Limits"
# Limits: memory: 512Mi

# 3. 查看实际内存使用趋势（历史数据）
# 在 Grafana 中查询：
# sum(container_memory_working_set_bytes{pod="<pod-name>"}) by (pod)

# 4. 查看 OOM 前一刻的日志
kubectl logs <pod-name> -n <namespace> --previous | tail -50

# 5. 解决方案
# 短期：增加 memory limit
# 长期：分析内存泄漏（添加 pprof 端点）或优化 JVM heap/GC 参数
```

---

## 七、可观测性最佳实践

### 7.1 建设路线图

一个典型的 K8s 可观测性建设路径：

| 阶段 | 目标 | 工具 | 验收标准 |
|------|------|------|----------|
| L1 | 基础设施可见 | node-exporter + Prometheus + Grafana | 节点 CPU/内存可查 |
| L2 | 应用健康可见 | kube-state-metrics + 应用 Exporter | Pod 状态、Deployment 副本数可查 |
| L3 | 日志可追溯 | Loki + Promtail | 按 namespace/pod/service 查日志 |
| L4 | 链路可追踪 | Jaeger + OpenTelemetry | Trace ID 贯穿全链路 |
| L5 | 告警自动化 | Alertmanager + 钉钉/飞书 | 告警 5 分钟内触达 |
| L6 | SLA/SLO 量化 | Sloth + Blackbox Exporter | 核心服务可用性可量化 |

### 7.2 采样策略

在生产环境中，全量采集所有 Trace 会带来巨大的资源压力。推荐的分层采样策略：

```yaml
# OpenTelemetry 采样配置
sampler:
  # 1. 根请求（外部入口）100% 采样
  parent_based:
    root: traceidratio  # 1.0 = 100%
    # 2. 有父Span的请求按比例采样（减少重复数据）
    remote_parent_sampled:
      - value: true
        probability: 0.1  # 10% 采样
    remote_parent_not_sampled:
      - value: false

# 错误请求 100% 采样（通过 Span 过滤实现）
# 在 Exporter 的 batch processor 中配置
```

### 7.3 成本优化

可观测性系统的成本主要来自存储和计算，以下是优化实践：

- **Loki 标签精简**：避免高 cardinality 标签，减少索引存储。
- **Prometheus 分片**：使用 Thanos 或 Cortex 实现全局视图和长期存储。
- **日志保留期分级**：热数据 7 天、温数据 30 天、冷数据 90 天。
- **Trace 下采样**：错误请求全量采样，成功请求按比例采样。

---

## 总结

本文系统讲解了 Kubernetes 可观测性体系的四大核心组件：

1. **Prometheus**：拉模式时序监控，Kubernetes SD 自动发现，核心是理解标签 relabeling 和 PromQL 聚合。
2. **Grafana**：统一可视化平台，通过 Panel 和 AlertRule 实现监控和告警，熟练使用变量模板。
3. **Loki**：标签索引型日志系统，标签设计决定查询性能，LogQL 是核心技能。
4. **Jaeger**：OpenTelemetry 标准分布式追踪，Span 瀑布图是排查慢请求的利器。

故障排查的核心是**分层诊断**——从基础设施到控制平面，再到工作负载，最后到应用层，每一层都有对应的诊断工具和命令。养成系统化的排查习惯，比死记硬背命令更重要。

---

## 下期预告

下一篇：**Kubernetes与云原生面试八股文（八）——生产级高可用与灾备** 将深入讲解 Kubernetes 多集群联邦设计、etcd 备份与恢复、PodDisruptionBudget 与 disruptions 预算控制、Pod 高可用调度策略、备份与灾难恢复（DR）方案设计，以及云原生时代的成本优化与资源治理，敬请期待。

---

*作者：飞哥 · Raphael Lab*

*Kubernetes与云原生面试八股文系列*
