---
title: Spring面试八股文（四）——Spring Boot监控与运维
date: 2026-07-06 10:00:00+08:00
updated: '2026-07-06T10:00:00+08:00'
description: 🎯 本文目标：承接前三篇的IoC容器、AOP、Spring MVC与自动配置基础，深入Spring Boot的监控运维体系——Actuator四大端点类型（Health/Info/Metrics/Env）的底层实现与安全配置、Micrometer指标采集体系与Prometheus+Grafana监控。
topic: java-spring
series: spring-interview
series_order: 4
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Spring
- Spring Boot
- Actuator
categories:
- Java 与 Spring
draft: false
author: 飞哥
---

> 🎯 **本文目标**：承接前三篇的IoC容器、AOP、Spring MVC与自动配置基础，深入Spring Boot的监控运维体系——Actuator四大端点类型（Health/Info/Metrics/Env）的底层实现与安全配置、Micrometer指标采集体系与Prometheus+Grafana监控大盘搭建、Spring Boot Admin可视化运维平台、优雅停机的Shutdown机制与Graceful Shutdown原理、以及Spring Boot应用调优十大实践，构建Spring Boot运维监控的完整能力体系。

---

## 一、Spring Boot Actuator核心架构

### 1.1 Actuator是什么？

**Q: Spring Boot Actuator解决了什么问题？有哪些核心能力？**

在生产环境中，应用上线只是起点，真正的挑战在于「应用的可见性」：

```
开发阶段                        生产阶段
┌────────────┐                 ┌────────────────────┐
│ 本地DEBUG  │                 │ ❌ 不能随意打断      │
│ 随便重启   │    ──发布──▶    │ ❌ 不能直接连服务器   │
│ IDEA看状态 │                 │ ❌ 没有直观监控面板   │
│ 日志在控制台│                │ ❌ 出问题靠猜         │
└────────────┘                 └────────────────────┘
                                         │
                               Actuator 破局 ──▶
                                         │
                               ┌────────────────────┐
                               │ ✅ 健康检查端点     │
                               │ ✅ 指标采集         │
                               │ ✅ 运行时信息暴露   │
                               │ ✅ 远程管理操作     │
                               └────────────────────┘
```

**Actuator是一套开箱即用的生产级监控套件**，通过HTTP端点或JMX暴露应用的运行时状态。Spring Boot 2.x 之后核心架构如下：

```java
// Actuator的MVC等效架构（类比理解）
// ┌──────────────────────────────────────────────┐
// │         DispatcherServlet  ← 就像MVC一样       │
// │                    │                          │
// │    ┌───────────────┼───────────────┐          │
// │    ▼               ▼               ▼          │
// │ /actuator/health  /actuator/metrics /actuator/info  │
// │    │               │               │          │
// │    ▼               ▼               ▼          │
// │ HealthEndpoint  MetricsEndpoint  InfoEndpoint  │
// │    │               │               │          │
// │    ▼               ▼               ▼          │
// │ HealthIndicator  MeterRegistry   InfoContributor│
// └──────────────────────────────────────────────┘
```

### 1.2 端点分类全景图

**Q: Actuator有哪些类型的端点？各自暴露什么信息？**

Spring Boot 2.x 内置 20+ 个端点，按用途分为四大类：

```java
// ===== 第一类：Health 健康检查 =====
/actuator/health         // 应用健康状态（UP/DOWN/OUT_OF_SERVICE）
/actuator/health/{path}  // 某个健康指标的详细状态（如 /health/db）

// ===== 第二类：Info 应用信息 =====
/actuator/info           // 应用基本信息（版本、Git信息、构建信息）

// ===== 第三类：Metrics 指标采集 =====
/actuator/metrics        // 所有可用指标名称列表
/actuator/metrics/{name} // 指定指标的当前值（如 jvm.memory.used）

// ===== 第四类：Env/Config 环境与配置 =====
/actuator/env            // 所有环境属性（包括application.yml和系统属性）
/actuator/env/{name}     // 指定属性值
/actuator/configprops    // 所有 @ConfigurationProperties Bean 的配置
/actuator/beans          // 容器中所有Bean列表
/actuator/conditions     // 自动配置条件评估报告（正面/负面匹配）

// ===== 运行时状态 =====
/actuator/threaddump     // 线程转储（相当于 jstack）
/actuator/heapdump       // 堆转储文件（相当于 jmap）
/actuator/loggers        // 日志级别管理（运行时动态修改日志级别）
/actuator/logfile        // 查看日志文件内容
/actuator/mappings       // 所有 @RequestMapping 映射关系
/actuator/scheduledtasks // 所有定时任务信息 (@Scheduled)
/actuator/caches         // 所有缓存管理器信息

// ===== 管理操作（需要显式启用，危险操作！）=====
/actuator/shutdown       // 优雅关闭应用（POST）
/actuator/restart        // 重启应用（POST，需要 devtools）
```

**面试中需要特别记住的端点记忆口诀：**

```
健康检查 health，应用信息 info
指标度量 metrics，环境配置 env
线程转储 thread，堆转储 heap
日志级别 logger，Bean列表 beans
自动配置 conditions，映射关系 mappings
```

### 1.3 端点暴露策略与安全配置

**Q: 如何控制Actuator端点的暴露范围？生产环境应该如何配置？**

```yaml
# application.yml 端点暴露策略配置
management:
  endpoints:
    # ① 默认暴露策略：JMX全部暴露，Web只暴露health
    web:
      exposure:
        # include: 白名单（显式指定暴露哪些端点）
        # exclude: 黑名单（排除哪些端点）
        # * 表示所有端点（包括自定义的）
        include: health,info,metrics,prometheus
        exclude: shutdown,heapdump,threaddump
      # ② 自定义基础路径（默认 /actuator）
      base-path: /management
    jmx:
      exposure:
        include: "*"
        exclude: shutdown
  
  # ③ 端点级别的精细控制
  endpoint:
    health:
      show-details: when-authorized  # never | when-authorized | always
      show-components: when-authorized
      roles: ADMIN                  # 需要特定角色
    shutdown:
      enabled: true                 # shutdown默认禁用，需要显式开启
    env:
      # 脱敏配置：keys-to-sanitize 中的属性值会被替换为 "******"
      additional-keys-to-sanitize: password,secret,token,key
```

**生产环境最佳实践：**

```java
// 方案1：Spring Security + Actuator（推荐）
@Configuration
public class ActuatorSecurityConfig {
    
    @Bean
    public SecurityFilterChain actuatorFilterChain(HttpSecurity http) throws Exception {
        http.securityMatcher(EndpointRequest.toAnyEndpoint())
            .authorizeHttpRequests(auth -> auth
                // health/info 公开访问（K8s探针需要）
                .requestMatchers(EndpointRequest.to(
                    HealthEndpoint.class, InfoEndpoint.class))
                    .permitAll()
                // metrics/prometheus 给监控系统专用
                .requestMatchers(EndpointRequest.to(
                    MetricsEndpoint.class, PrometheusScrapeEndpoint.class))
                    .hasRole("MONITORING")
                // 危险端点需要ADMIN角色
                .requestMatchers(EndpointRequest.to(
                    ShutdownEndpoint.class, HeapDumpWebEndpoint.class,
                    ThreadDumpEndpoint.class))
                    .hasRole("ADMIN")
                // 其他端点需要认证
                .anyRequest().authenticated()
            )
            .httpBasic(Customizer.withDefaults());
        return http.build();
    }
}

// 方案2：独立端口（更安全）
// 将 Actuator 暴露在独立端口，不经过外网负载均衡
management:
  server:
    port: 8081           # 独立管理端口
    address: 127.0.0.1   # 只监听本地
```

**面试要点：**
> Actuator端点默认通过JMX全量暴露、Web只暴露health。生产环境必须：① 关闭shutdown等危险端点 ② 敏感信息脱敏 ③ health/show-details设为when-authorized ④ 通过Spring Security保护或使用独立端口。

---

## 二、Health健康检查深度解析

### 2.1 HealthIndicator的工作原理

**Q: `/actuator/health` 返回的 UP/DOWN 是如何判定的？**

```java
// HealthIndicator 接口
@FunctionalInterface
public interface HealthIndicator {
    Health health();  // 返回健康状态
}

// Spring Boot 内置的 HealthIndicator 实现：
// ┌─────────────────────────────────────────────────────┐
// │ DataSourceHealthIndicator    → 数据库连接是否正常     │
// │ RedisHealthIndicator         → Redis是否可连接        │
// │ MongoHealthIndicator         → MongoDB是否可连接      │
// │ RabbitHealthIndicator        → RabbitMQ是否可连接     │
// │ ElasticsearchHealthIndicator → ES是否可连接           │
// │ DiskSpaceHealthIndicator     → 磁盘剩余空间是否足够    │
// │ PingHealthIndicator          → 应用本身是否响应        │
// │ LivenessStateHealthIndicator → K8s Liveness探针       │
// │ ReadinessStateHealthIndicator→ K8s Readiness探针      │
// └─────────────────────────────────────────────────────┘
```

**Health聚合机制：**

```java
// HealthEndpoint 将所有 HealthIndicator 的结果聚合
// 聚合规则：任一组件DOWN → 整体DOWN（木桶效应）

// 示例返回：
{
  "status": "UP",
  "components": {
    "db": {
      "status": "UP",
      "details": {
        "database": "MySQL",
        "validationQuery": "SELECT 1",
        "result": 1
      }
    },
    "redis": {
      "status": "UP",
      "details": {
        "version": "7.0.5"
      }
    },
    "diskSpace": {
      "status": "UP",
      "details": {
        "total": 500107862016,
        "free": 150394752000,
        "threshold": 10485760
      }
    }
  }
}
```

### 2.2 自定义HealthIndicator

**Q: 如何为自己的业务组件添加健康检查？**

```java
// 示例1：检查第三方支付服务是否可用
@Component
public class PaymentServiceHealthIndicator implements HealthIndicator {
    
    @Autowired
    private PaymentGatewayClient paymentClient;
    
    @Override
    public Health health() {
        try {
            // 调用支付服务的ping接口
            PaymentHealthResponse response = 
                paymentClient.healthCheck(Duration.ofSeconds(3));
            
            if (response.isHealthy()) {
                return Health.up()
                    .withDetail("gateway", "Alipay")
                    .withDetail("latency", response.getLatencyMs() + "ms")
                    .withDetail("version", response.getVersion())
                    .build();
            } else {
                return Health.down()
                    .withDetail("gateway", "Alipay")
                    .withDetail("error", response.getErrorMessage())
                    .build();
            }
        } catch (Exception e) {
            return Health.down(e)
                .withDetail("gateway", "Alipay")
                .withDetail("errorType", e.getClass().getSimpleName())
                .build();
        }
    }
}

// 示例2：检查消息积压情况（使用 ReactiveHealthIndicator）
@Component
public class MessageQueueHealthIndicator implements ReactiveHealthIndicator {
    
    @Autowired
    private KafkaAdminClient kafkaAdmin;
    
    @Override
    public Mono<Health> health() {
        return Mono.fromCallable(() -> {
            long consumerLag = kafkaAdmin.getConsumerLag("order-group");
            
            Health.Builder builder = consumerLag < 1000 
                ? Health.up() 
                : Health.status(new Status("WARNING", "消息积压超过1000"));
            
            return builder
                .withDetail("consumerGroup", "order-group")
                .withDetail("lag", consumerLag)
                .build();
        }).subscribeOn(Schedulers.boundedElastic());
    }
}
```

### 2.3 K8s探针：Liveness vs Readiness

**Q: Spring Boot 2.3+ 如何支持 K8s 的 Liveness 和 Readiness 探针？**

```yaml
# application.yml — K8s探针配置
management:
  endpoint:
    health:
      probes:
        enabled: true      # 启用 /actuator/health/liveness 和 /actuator/health/readiness
      group:
        liveness:
          include: livenessState    # Liveness 只包含 livenessState
        readiness:
          include: readinessState   # Readiness 包含 readinessState + 外部依赖
```

```yaml
# K8s Deployment 中使用
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: my-app
        # Liveness探针：应用是否"活着"（内部状态）
        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 3    # 连续失败3次 → 重启Pod
        
        # Readiness探针：应用是否"准备好接受流量"
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 5
          failureThreshold: 2    # 连续失败2次 → 摘除Service流量
```

**Liveness vs Readiness 的核心区别：**

| 维度 | Liveness | Readiness |
|------|----------|-----------|
| 本质问题 | "容器还活着吗？" | "容器能处理请求吗？" |
| 失败行为 | K8s杀死并重启Pod | K8s从Service摘除，不转发流量 |
| 触发条件 | 死锁、无限循环、OOM | 数据库不可用、缓存预热未完成 |
| 检查内容 | 应用内部状态（线程是否活动） | 外部依赖是否可用 |
| 重启策略 | 重启是唯一修复手段 | 自动恢复后重新加入Service |

---

## 三、Metrics指标采集体系

### 3.1 Micrometer：指标采集的SLF4J

**Q: Micrometer是什么？为什么要引入这个抽象层？**

```java
// Micrometer 之于 Metrics，就像 SLF4J 之于 Logging
// 
// ┌──────────────────────────────────────┐
// │         你的业务代码                    │
// │    MeterRegistry.counter(...)        │
// └──────────────┬───────────────────────┘
//                │ Micrometer API (统一抽象)
//     ┌──────────┼──────────┬──────────┬────────────┐
//     ▼          ▼          ▼          ▼            ▼
// Prometheus  InfluxDB   Graphite   Datadog    CloudWatch
// (最常用)   (时序DB)   (老牌监控)  (SaaS)    (AWS)
//
// 换监控后端 = 换一个 Maven 依赖，代码零改动！

// 只需切换依赖：
// <dependency>  // Prometheus 注册器
//     <groupId>io.micrometer</groupId>
//     <artifactId>micrometer-registry-prometheus</artifactId>
// </dependency>
```

**Micrometer支持的三种核心指标类型：**

```java
@Component
public class OrderMetrics {
    
    private final MeterRegistry meterRegistry;
    
    // ===== ① Counter：只增不减的计数器 =====
    private final Counter orderCreatedCounter;     // 创建订单总数
    private final Counter orderCancelledCounter;   // 取消订单总数
    
    // ===== ② Gauge：瞬时值（可增可减）=====
    // 不需要手动update，每次采集时实时获取
    private final AtomicInteger pendingOrders = new AtomicInteger(0);
    
    // ===== ③ Timer：计时器（记录耗时+调用次数）=====
    private final Timer orderProcessTimer;
    
    // ===== ④ DistributionSummary：分布摘要（记录值的分布）=====
    private final DistributionSummary orderAmountSummary;
    
    public OrderMetrics(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
        
        // Counter 通过标签区分维度
        this.orderCreatedCounter = Counter.builder("orders.created.total")
            .description("订单创建总数")
            .tag("app", "order-service")
            .tag("env", "production")
            .register(meterRegistry);
        
        this.orderCancelledCounter = Counter.builder("orders.cancelled.total")
            .description("订单取消总数")
            .register(meterRegistry);
        
        // Gauge：注册一个Supplier，采集时实时调用
        Gauge.builder("orders.pending", pendingOrders, AtomicInteger::get)
            .description("待处理订单数")
            .register(meterRegistry);
        
        // Timer：记录耗时分布（P50/P90/P99）
        this.orderProcessTimer = Timer.builder("orders.process.duration")
            .description("订单处理耗时")
            .publishPercentiles(0.5, 0.9, 0.99)   // 发布P50/P90/P99
            .publishPercentileHistogram()           // 发布直方图（Prometheus）
            .sla(Duration.ofMillis(100), Duration.ofMillis(500)) // SLA边界
            .register(meterRegistry);
        
        // DistributionSummary：记录金额分布
        this.orderAmountSummary = DistributionSummary.builder("orders.amount")
            .description("订单金额分布")
            .publishPercentiles(0.5, 0.9, 0.99)
            .register(meterRegistry);
    }
    
    public void recordOrderCreated(String channel, double amount) {
        // 带动态标签的Counter
        Counter.builder("orders.created.total")
            .tag("channel", channel)
            .register(meterRegistry)
            .increment();  // +1
        
        pendingOrders.incrementAndGet();
        orderAmountSummary.record(amount);
    }
    
    public void recordOrderProcessed(long durationMs) {
        pendingOrders.decrementAndGet();
        orderProcessTimer.record(durationMs, TimeUnit.MILLISECONDS);
    }
    
    // 更优雅的方式：使用 @Timed 注解
    @Timed(value = "orders.create", percentiles = {0.5, 0.9, 0.99})
    @PostMapping("/orders")
    public Order createOrder(@RequestBody OrderRequest request) {
        // Micrometer AOP 自动记录耗时
        return orderService.create(request);
    }
}
```

### 3.2 JVM内置指标

**Q: Spring Boot自动采集了哪些JVM指标？**

```java
// 不需要任何代码，Spring Boot自动注册以下JVM指标：
// 
// jvm.memory.used        → JVM内存使用量（按区域：heap/nonheap/pool）
// jvm.memory.max         → JVM最大内存
// jvm.memory.committed   → JVM已分配内存
// jvm.gc.pause           → GC暂停时间（Timer类型）
// jvm.gc.memory.promoted → GC后晋升内存量
// jvm.gc.max.data.size   → 老年代最大大小
// jvm.threads.live       → 活跃线程数
// jvm.threads.daemon      → 守护线程数
// jvm.threads.peak        → 历史峰值线程数
// jvm.classes.loaded      → 已加载类数
// jvm.classes.unloaded    → 已卸载类数
// jvm.buffer.count        → 直接/堆内Buffer数
// jvm.buffer.memory.used  → Buffer内存使用
// jvm.buffer.total.capacity → Buffer总容量
// 
// CPU相关：
// process.cpu.usage       → 进程CPU使用率
// system.cpu.usage        → 系统CPU使用率
// system.cpu.count        → CPU核数
//
// HTTP相关（需引入 spring-boot-starter-web）：
// http.server.requests    → HTTP请求耗时分布（Timer）
//
// 数据库连接池（需引入 HikariCP）：
// hikaricp.connections.active   → 活跃连接数
// hikaricp.connections.idle     → 空闲连接数
// hikaricp.connections.pending  → 等待连接数
// hikaricp.connections.timeout  → 超时连接数
```

### 3.3 Prometheus + Grafana 监控大盘

**Q: 如何搭建Spring Boot的Prometheus+Grafana监控体系？**

**Step 1: 引入Prometheus依赖**

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```yaml
# application.yml
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus  # 暴露 prometheus 端点
  metrics:
    tags:
      application: ${spring.application.name}  # 全局标签
```

访问 `/actuator/prometheus` 会得到Prometheus格式的数据：

```
# HELP jvm_memory_used_bytes The number of used bytes
# TYPE jvm_memory_used_bytes gauge
jvm_memory_used_bytes{area="heap",id="G1 Eden Space",application="order-service"} 6.7108864E7
jvm_memory_used_bytes{area="heap",id="G1 Old Gen",application="order-service"} 2.147483648E9
jvm_memory_used_bytes{area="nonheap",id="Metaspace",application="order-service"} 1.23456789E8

# HELP orders_created_total 订单创建总数
# TYPE orders_created_total counter
orders_created_total{channel="APP",application="order-service"} 15234
orders_created_total{channel="WEB",application="order-service"} 8921

# HELP orders_process_duration_seconds 订单处理耗时
orders_process_duration_seconds{quantile="0.5",application="order-service"} 0.125
orders_process_duration_seconds{quantile="0.99",application="order-service"} 2.531
```

**Step 2: Prometheus配置（prometheus.yml）**

```yaml
global:
  scrape_interval: 15s       # 采集间隔
  evaluation_interval: 15s   # 规则评估间隔

scrape_configs:
  - job_name: 'spring-boot-app'
    metrics_path: '/actuator/prometheus'
    static_configs:
      - targets: ['localhost:8080']
        labels:
          env: 'production'
    # 基于Consul/Eureka的服务发现（微服务场景）
    # consul_sd_configs:
    #   - server: 'consul:8500'
```

**Step 3: Grafana创建监控大盘**

**核心指标PromQL查询：**

```promql
# QPS（每秒请求数）
rate(http_server_requests_seconds_count[1m])

# P99延迟
histogram_quantile(0.99, rate(http_server_requests_seconds_bucket[5m]))

# 错误率
sum(rate(http_server_requests_seconds_count{status=~"5.."}[1m])) 
/ sum(rate(http_server_requests_seconds_count[1m]))

# 堆内存使用率
jvm_memory_used_bytes{area="heap"} / jvm_memory_max_bytes{area="heap"} * 100

# GC频率
rate(jvm_gc_pause_seconds_count[5m])

# GC耗时占比
rate(jvm_gc_pause_seconds_sum[5m]) / rate(jvm_gc_pause_seconds_count[5m])

# GC停顿P99
histogram_quantile(0.99, rate(jvm_gc_pause_seconds_bucket[5m]))

# 线程数
jvm_threads_live_threads

# 数据库连接池使用率
hikaricp_connections_active / hikaricp_connections_max * 100
```

**Grafana Dashboard JSON模板结构：**

```
监控大盘布局（建议结构）：
┌─────────────────────────────────────────────────────┐
│ Row 1: 概览指标（SingleStat）                       │
│ [QPS] [P99延迟] [错误率] [CPU使用率] [内存使用率]    │
├─────────────────────────────────────────────────────┤
│ Row 2: HTTP请求趋势                                 │
│ [QPS曲线图] [P50/P90/P99延迟曲线图]                 │
├─────────────────────────────────────────────────────┤
│ Row 3: JVM监控                                      │
│ [堆内存使用曲线] [GC频率与耗时] [线程数]             │
├─────────────────────────────────────────────────────┤
│ Row 4: 业务指标                                     │
│ [订单创建数] [订单处理耗时] [待处理订单数]           │
└─────────────────────────────────────────────────────┘
```

---

## 四、Spring Boot Admin可视化运维平台

### 4.1 Spring Boot Admin架构

**Q: Spring Boot Admin是什么？和Actuator是什么关系？**

```java
// Spring Boot Admin (SBA) = Actuator数据的可视化聚合平台
//
// ┌──────────────────────────────────────────────────┐
// │           Spring Boot Admin Server               │
// │  ┌─────────┐  ┌──────────┐  ┌───────────────┐  │
// │  │Dashboard│  │Wallboard │  │Notifications │  │
// │  │ (概览)   │  │ (大屏展示) │  │ (邮件/钉钉告警)│  │
// │  └─────────┘  └──────────┘  └───────────────┘  │
// │         ↕ HTTP/JMX ↕         ↕ 事件通知 ↕        │
// └──────────────────────────────────────────────────┘
//      ↕               ↕               ↕
// ┌──────────┐  ┌──────────┐  ┌──────────┐
// │ Client A │  │ Client B │  │ Client C │
// │(Actuator)│  │(Actuator)│  │(Actuator)│
// └──────────┘  └──────────┘  └──────────┘
```

**搭建Admin Server：**

```java
// Admin Server 端 —— pom.xml
<dependency>
    <groupId>de.codecentric</groupId>
    <artifactId>spring-boot-admin-starter-server</artifactId>
    <version>3.2.0</version>
</dependency>

// 启动类加 @EnableAdminServer
@SpringBootApplication
@EnableAdminServer
public class AdminServerApplication {
    public static void main(String[] args) {
        SpringApplication.run(AdminServerApplication.class, args);
    }
}
```

**客户端注册方式：**

```java
// 方式1：直接注册（客户端引入 spring-boot-admin-starter-client）
// application.yml
spring:
  boot:
    admin:
      client:
        url: http://localhost:9090    # Admin Server地址
        instance:
          name: order-service         # 显示名称
          service-url: http://localhost:8080  # 自身地址
        username: admin               # 如果Server有安全认证
        password: admin

// 方式2：通过服务发现（Eureka/Nacos/Consul）自动注册
// 无需配置 url，SBA Server自动从注册中心发现所有服务
spring:
  application:
    name: order-service
```

### 4.2 SBA核心功能一览

**Q: Spring Boot Admin提供了哪些运维能力？**

```
SBA 提供的功能清单：

📊 概览 Dashboard
├── 应用列表（实例数、健康状态、版本号）
├── 启动时间、运行时长
├── 内存/CPU使用率实时曲线
└── 线程数、GC统计

🔍 详情面板
├── Health：所有健康检查组件状态
├── Metrics：所有指标的可视化
├── Environment：环境变量和配置
├── Loggers：运行时修改日志级别
├── Thread Dump：线程转储可视化
├── Heap Dump：在线生成堆转储
├── Mappings：所有端点映射
├── Beans：Bean依赖关系图
├── Caches：缓存命中率
└── Scheduled Tasks：定时任务状态

🔔 通知告警
├── 状态变更通知（UP→DOWN→OFFLINE）
├── 支持邮件、钉钉、企业微信、Slack、Teams
├── 去重机制（不重复告警）
└── 告警规则自定义

📈 日志查看
├── 在线查看日志文件
└── 支持日志级别动态调整
```

**通知配置示例：**

```yaml
# Admin Server 的告警配置
spring:
  boot:
    admin:
      notify:
        dingtalk:
          enabled: true
          webhook-url: https://oapi.dingtalk.com/robot/send?access_token=xxx
          secret: SECxxx
        mail:
          enabled: true
          to: ops-team@company.com
          from: admin-server@company.com
          # 去重：30分钟内不重复发送
          reminder-period: 30m
```

---

## 五、优雅停机机制

### 5.1 什么是优雅停机？

**Q: 为什么需要优雅停机？Kill -9 有什么问题？**

```java
// 暴力停机 (kill -9) 的问题：
// ┌─────────────────────────────────────────────┐
// │ 时刻 T0: 服务收到 kill -9 信号               │
// │ 时刻 T1: 进程立刻终止                        │
// │                                             │
// │ ❌ 正在处理的请求 → 客户端收到连接断开         │
// │ ❌ 未提交的事务 → 数据不一致                  │
// │ ❌ 线程池任务 → 丢失                          │
// │ ❌ 消息队列消费 → 消息丢失（如果手动ACK）      │
// │ ❌ 资源未释放 → 连接泄漏                     │
// └─────────────────────────────────────────────┘

// 优雅停机 (Graceful Shutdown)：
// ┌─────────────────────────────────────────────┐
// │ 时刻 T0: K8s 发送 SIGTERM 信号               │
// │ 时刻 T1: 停止接收新请求（返回503）            │
// │ 时刻 T2: 等待正在处理的请求完成（grace-period）│
// │ 时刻 T3: 关闭线程池                          │
// │ 时刻 T4: 提交/回滚事务                        │
// │ 时刻 T5: 关闭数据库连接池、Redis连接等         │
// │ 时刻 T6: 进程退出                             │
// │                                             │
// │ ✅ 正在处理的请求 → 正常完成                   │
// │ ✅ 事务 → 正确提交或回滚                      │
// │ ✅ 连接 → 优雅关闭                           │
// └─────────────────────────────────────────────┘
```

### 5.2 Spring Boot Graceful Shutdown配置

**Q: Spring Boot 2.3+ 如何配置优雅停机？**

```yaml
# application.yml
server:
  shutdown: graceful      # 开启优雅停机（默认 immediate）

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # 每个关闭阶段的超时时间
```

```java
// 自定义关闭时的资源清理
@Component
public class GracefulShutdownHandler implements DisposableBean {
    
    @Autowired
    private ThreadPoolTaskExecutor taskExecutor;
    
    @Override
    public void destroy() throws Exception {
        log.info("开始优雅停机...");
        
        // 1. 停止接收新任务
        taskExecutor.shutdown();
        
        // 2. 等待已有任务完成
        if (!taskExecutor.getThreadPoolExecutor()
                .awaitTermination(30, TimeUnit.SECONDS)) {
            log.warn("线程池未在30秒内完成，强制关闭");
            taskExecutor.getThreadPoolExecutor().shutdownNow();
        }
        
        log.info("优雅停机完成");
    }
}

// 更推荐的方式：使用 @PreDestroy
@Component
public class ResourceCleanup {
    
    @PreDestroy
    public void cleanup() {
        log.info("执行清理操作：关闭连接、刷新缓冲区等");
    }
}

// 使用 ApplicationListener 监听关闭事件
@Component
public class ShutdownListener {
    
    @EventListener(ContextClosedEvent.class)
    public void onShutdown(ContextClosedEvent event) {
        log.info("ApplicationContext 正在关闭，reason: {}", 
            event.getApplicationContext().getId());
        // 执行自定义关闭逻辑
    }
}
```

### 5.3 四层关闭机制

**Q: Spring Boot优雅停机的完整分层机制是怎样的？**

```java
// Spring Boot 优雅停机的四层架构：
//
// ┌──────────────────────────────────────────────────────┐
// │ 第1层：外部流量层                                      │
// │ ─────────────────────────────────────                 │
// │ · K8s Service 摘除 Pod → 不再转发新请求到该Pod        │
// │ · 负载均衡健康检查失败 → 自动摘除节点                  │
// │ · 关键参数: terminationGracePeriodSeconds: 60         │
// │   # K8s: preStop hook → sleep 20 → 给LB足够时间摘除    │
// │   lifecycle.preStop.exec.command:                     │
// │     ["/bin/sh", "-c", "sleep 20"]                     │
// ├──────────────────────────────────────────────────────┤
// │ 第2层：Web服务器层                                     │
// │ ─────────────────────────────                         │
// │ · Tomcat/Jetty/Undertow 停止接收新请求                │
// │ · 等待正在处理的请求完成                               │
// │ · 关键参数: server.shutdown=graceful                  │
// │ · 超时控制: spring.lifecycle.timeout-per-shutdown-phase│
// ├──────────────────────────────────────────────────────┤
// │ 第3层：Spring容器层                                    │
// │ ───────────────────────                               │
// │ · @PreDestroy 回调                                    │
// │ · DisposableBean.destroy()                            │
// │ · @EventListener(ContextClosedEvent)                  │
// │ · SmartLifecycle.stop()                               │
// ├──────────────────────────────────────────────────────┤
// │ 第4层：外部资源层                                      │
// │ ─────────────────                                     │
// │ · 数据库连接池（HikariCP/Druid）关闭                  │
// │ · Redis 连接池关闭                                     │
// │ · 消息队列 Consumer 关闭                               │
// │ · 分布式锁释放                                        │
// │ · 服务注册中心注销（Nacos/Eureka）                     │
// └──────────────────────────────────────────────────────┘
```

**K8s完整配置示例：**

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 60  # K8s总共等待60秒
      containers:
      - name: my-app
        lifecycle:
          preStop:
            exec:
              # 等待20秒让Service摘除生效，再给Spring Boot 30秒优雅停机
              command: ["/bin/sh", "-c", "sleep 20"]
        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          failureThreshold: 1  # 立即失败 → 立刻从Service摘除
```

---

## 六、Spring Boot应用调优十大实践

### 6.1 性能调优全景

**Q: Spring Boot应用常见的性能瓶颈在哪里？如何优化？**

```yaml
# ① Tomcat线程池调优
server:
  tomcat:
    threads:
      max: 200              # 最大工作线程数（默认200）
      min-spare: 10          # 最小空闲线程数（默认10）
    accept-count: 100        # 等待队列长度（默认100）
    max-connections: 10000   # 最大连接数（默认8192）
    connection-timeout: 5000 # 连接超时
  # 经验公式：max-threads = ((IO时间 + CPU时间) / CPU时间) * CPU核数

# ② 数据库连接池调优（HikariCP）
spring:
  datasource:
    hikari:
      maximum-pool-size: 20       # 最大连接数
      minimum-idle: 10            # 最小空闲连接
      connection-timeout: 3000    # 获取连接超时（默认30s太长）
      idle-timeout: 600000        # 空闲连接最大存活时间
      max-lifetime: 1800000       # 连接最大存活时间（比数据库wait_timeout短）
      leak-detection-threshold: 10000  # 连接泄漏检测（开发环境开启）
  # 关键公式：pool-size = Tn * (Cm - 1) + 1
  # Tn = 最大线程数, Cm = 单个线程持有的最大连接数

# ③ JVM调优
# -Xms2g -Xmx2g (堆大小固定，避免动态调整开销)
# -XX:+UseG1GC (大堆用G1，小堆(<=4G)可用ParallelGC)
# -XX:MaxGCPauseMillis=200 (G1目标停顿时间)
# -XX:+PrintGCDetails -XX:+PrintGCDateStamps (GC日志)
# -XX:+HeapDumpOnOutOfMemoryError (OOM时自动dump)
```

```java
// ④ 异步化：非关键路径全部异步
@Configuration
@EnableAsync
public class AsyncConfig {
    
    @Bean("taskExecutor")
    public ThreadPoolTaskExecutor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(500);
        executor.setRejectedExecutionHandler(
            new ThreadPoolExecutor.CallerRunsPolicy()); // 拒绝策略：由调用线程执行
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }
}

// ⑤ 缓存：多级缓存策略
@Service
public class ProductService {
    
    // L1：本地缓存（Caffeine）
    @Cacheable(value = "product", key = "#id", 
               cacheManager = "caffeineCacheManager",
               unless = "#result == null")
    public Product getById(Long id) {
        // L2：分布式缓存（Redis）
        Product product = redisTemplate.opsForValue().get("product:" + id);
        if (product != null) return product;
        
        // L3：数据库
        product = productMapper.selectById(id);
        if (product != null) {
            redisTemplate.opsForValue()
                .set("product:" + id, product, 30, TimeUnit.MINUTES);
        }
        return product;
    }
}

// ⑥ 数据库查询优化
// · 使用连接池监控：HikariCP metrics → Grafana
// · N+1查询：用JOIN或批量查询替代循环查询
// · 慢SQL监控：开启 Druid 的慢SQL记录
// · 分页查询：大数据量必须分页，且用游标分页而非OFFSET
```

```java
// ⑦ 优雅的参数校验
@RestController
public class OrderController {
    
    @PostMapping("/orders")
    public Result createOrder(@Valid @RequestBody CreateOrderRequest request) {
        // @Valid 失败会抛出 MethodArgumentNotValidException
        // 通过 @ControllerAdvice 统一处理
        return Result.success(orderService.create(request));
    }
}

@ControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result handleValidation(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors()
            .stream()
            .map(err -> err.getField() + ": " + err.getDefaultMessage())
            .collect(Collectors.joining(", "));
        return Result.fail(400, message);
    }
}

// ⑧ 日志优化
// logback-spring.xml 配置：
// · 异步日志：<appender name="ASYNC" class="ch.qos.logback.classic.AsyncAppender">
// · 合理日志级别：生产环境WARN，开发环境DEBUG
// · 日志滚动策略：按天滚动，保留30天
// · 避免日志打印大对象（toString包含所有字段）

// ⑨ 静态资源优化
// · 使用CDN分发静态资源
// · Nginx直接处理静态资源，不经过Spring MVC
// · 开启Gzip压缩：server.compression.enabled=true
// · 合理设置缓存头：Cache-Control: max-age=31536000

// ⑩ 启动优化
// · 懒加载：spring.main.lazy-initialization=true（谨慎使用）
// · 减少不必要自动配置：@SpringBootApplication(exclude=...)
// · 温启动预热：应用启动后主动调用关键接口进行预热
// · Class Data Sharing (CDS)：减少JVM类加载时间
```

**十大实践总结表：**

| 序号 | 优化方向 | 关键配置 | 效果 |
|------|---------|---------|------|
| ① | Tomcat线程池 | max-threads, accept-count | 提升并发处理能力 |
| ② | 数据库连接池 | maximum-pool-size, leak-detection | 防止连接泄漏和等待 |
| ③ | JVM调优 | G1GC, Xms=Xmx, HeapDump | 减少GC停顿 |
| ④ | 异步化 | @Async + 自定义线程池 | 释放Web线程 |
| ⑤ | 多级缓存 | Caffeine + Redis + DB | 减少数据库压力 |
| ⑥ | 数据库优化 | 慢SQL监控、批量查询、分页 | 提升查询性能 |
| ⑦ | 参数校验 | @Valid + 统一异常处理 | 提前拦截无效请求 |
| ⑧ | 日志优化 | 异步日志、合理级别 | 减少IO开销 |
| ⑨ | 静态资源 | CDN、Nginx、Gzip | 减小带宽消耗 |
| ⑩ | 启动优化 | 懒加载、缩小自动配置范围、预热 | 缩短启动时间 |

---

## 七、面试高频题总结

```
Actuator 5连问：
1. Actuator默认暴露了哪些端点？生产环境如何安全配置？
2. /actuator/health 的返回结果是如何聚合的？如何添加自定义健康检查？
3. Liveness Probe 和 Readiness Probe 有什么区别？分别应该检查什么？
4. 如何通过Actuator动态修改日志级别？实现的原理是什么？
5. shutdown端点如何安全地使用？需要注意什么？

Metrics 5连问：
6. Micrometer的核心抽象是什么？支持哪些监控系统？
7. Counter、Gauge、Timer分别适用于什么场景？
8. @Timed注解是如何工作的？底层用了什么AOP机制？
9. 如何将自定义业务指标集成到Prometheus+Grafana？
10. 微服务架构下如何实现统一的指标采集与聚合？

运维 5连问：
11. Spring Boot Admin和Actuator是什么关系？Admin Server如何发现客户端？
12. 优雅停机的完整流程是怎样的？四层关闭机制各负责什么？
13. Kill -9 和 Kill -15 的区别？为什么优雅停机需要SIGTERM而非SIGKILL？
14. K8s环境中如何配置PreStop Hook？terminationGracePeriodSeconds如何设置？
15. Spring Boot应用如何排查内存泄漏？有哪些工具和步骤？
```

---

## 八、下期预告

下一篇将深入 **Spring Boot 2.x到3.x迁移实战**——Jakarta EE命名空间迁移（javax→jakarta）的自动与手动处理、Spring Security 6的Lambda DSL配置方式、AOT编译与Spring Native的原生镜像构建、虚拟线程(Virtual Threads)在Spring Boot 3.2+中的应用与限制、Observability可观测性三大支柱（Tracing/Metrics/Logging）的Micrometer Tracing统一方案、以及HTTP Interface声明式HTTP客户端的实战应用，构建Spring Boot升级迁移的完整指南。敬请期待！🦐

---

*本系列持续更新中，欢迎关注公众号获取最新文章。*
