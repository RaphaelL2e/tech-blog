---
title: "Spring面试八股文（五）——Spring Cloud微服务架构实战"
date: 2026-07-08T10:00:00+08:00
draft: false
categories: ["Spring Cloud"]
tags: ["Spring Cloud", "微服务", "Nacos", "Sentinel", "Gateway", "OpenFeign", "LoadBalancer", "面试", "八股文"]
---

# Spring面试八股文（五）——Spring Cloud微服务架构实战

> 🎯 **本文目标**：在Spring Boot的基础上，深入解析Spring Cloud Alibaba生态的核心组件——服务注册发现Nacos、服务调用OpenFeign、负载均衡LoadBalancer、服务容错Sentinel、API网关Gateway，并结合实战经验构建微服务架构能力体系。

---

## 一、Spring Cloud vs Spring Cloud Alibaba

### 1.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Spring Cloud和Spring Cloud Alibaba的区别？ | ⭐⭐⭐⭐⭐ | SC是Netflix组件（部分停更），SCA是阿里生态，国内主流 |
| 2 | Spring Cloud版本号怎么理解？ | ⭐⭐⭐ | 使用发布名称（2022.0.x），非数字版本号 |
| 3 | Spring Cloud Alibaba有哪些核心组件？ | ⭐⭐⭐⭐⭐ | Nacos注册中心+配置中心、Sentinel限流熔断、Seata分布式事务 |
| 4 | 微服务拆分的原则是什么？ | ⭐⭐⭐⭐ | 业务边界清晰、高内聚低耦合、独立部署、数据隔离 |

### 1.2 组件对比表

| 功能领域 | Spring Cloud Netflix | Spring Cloud Alibaba | 推荐选择 |
|---------|---------------------|---------------------|---------|
| 服务注册发现 | Eureka（停更） | Nacos | ✅ Nacos |
| 配置中心 | Spring Cloud Config | Nacos | ✅ Nacos |
| 负载均衡 | Ribbon（停更） | LoadBalancer | ✅ LoadBalancer |
| 服务调用 | Feign（停更） | OpenFeign | ✅ OpenFeign |
| 熔断降级 | Hystrix（停更） | Sentinel | ✅ Sentinel |
| API网关 | Zuul（停更） | Spring Cloud Gateway | ✅ Gateway |
| 分布式事务 | - | Seata | ✅ Seata |

**最佳实践**：新项目直接使用 **Spring Cloud Alibaba + Spring Cloud** 组合（Nacos + Sentinel + Gateway + OpenFeign）。

---

## 二、Nacos：服务注册与配置中心

### 2.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Nacos作为注册中心的原理？ | ⭐⭐⭐⭐⭐ | 服务注册→心跳续约→服务发现→健康检查 |
| 2 | Nacos如何保证高可用？ | ⭐⭐⭐⭐ | 集群部署（3节点起步）+ Raft协议 + MySQL持久化 |
| 3 | Nacos的AP和CP模式怎么切换？ | ⭐⭐⭐⭐ | 临时实例AP（默认）、持久化实例CP |
| 4 | Nacos配置中心的热更新机制？ | ⭐⭐⭐⭐⭐ | 长轮询机制 + @RefreshScope |
| 5 | Nacos和Eureka的区别？ | ⭐⭐⭐⭐ | Nacos支持CP/AP切换、支持配置中心、健康检查更丰富 |

### 2.2 Nacos注册中心原理

```
┌─────────────────────────────────────────────────────────────┐
│                       Nacos Server                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  注册表      │  │  健康检查   │  │  配置管理   │        │
│  │  (Map)      │  │  (定时任务)  │  │  (MySQL)    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
└─────────┼────────────────┼────────────────┼────────────────┘
          │                │                │
    ┌─────▼─────┐    ┌────▼────┐    ┌──────▼──────┐
    │ Provider  │    │ Consumer│    │ Admin控制台  │
    │ 心跳续约   │    │ 订阅服务 │    │ 配置下发     │
    └───────────┘    └─────────┘    └─────────────┘
```

**服务注册流程**：
1. Provider启动 → 向Nacos发送注册请求（POST /nacos/v1/ns/instance）
2. Nacos维护注册表：`Map<namespace, Map<group::serviceName, Service>>`
3. Provider每5秒发送心跳（PUT /nacos/v1/ns/instance/beat）
4. Nacos超时未收到心跳（默认15秒）→ 标记为不健康 → 30秒后剔除
5. Consumer订阅服务 → Nacos推送服务列表变更

### 2.3 Nacos配置中心热更新原理

```java
// 1. Bootstrap配置（bootstrap.yml）
spring:
  cloud:
    nacos:
      config:
        server-addr: 127.0.0.1:8848
        namespace: dev
        group: DEFAULT_GROUP
        file-extension: yaml
        refresh-enabled: true  # 自动刷新

// 2. 配置热更新示例
@RestController
@RefreshScope  // 关键注解：支持动态刷新
public class ConfigController {
    
    @Value("${app.config.timeout:3000}")
    private int timeout;
    
    @GetMapping("/config")
    public String getConfig() {
        return "timeout: " + timeout;
    }
}
```

**长轮询机制**：
1. 客户端发起长轮询请求（超时30秒）
2. 服务端检查配置MD5是否变化
3. 有变化：立即返回新配置
4. 无变化：hold住请求，等待变更或超时
5. 客户端收到响应后立即发起下一次长轮询

```java
// Nacos ConfigService 核心逻辑（简化）
public void checkConfigInfo() {
    // 分批检查配置变更
    for (CacheData cacheData : cacheMap.values()) {
        // 比较MD5
        if (!cacheData.getMd5().equals(serverMd5)) {
            // 触发监听器
            for (Listener listener : cacheData.getListeners()) {
                listener.receiveConfigInfo(newConfig);
            }
        }
    }
}
```

### 2.4 Nacos集群部署

```yaml
# cluster.conf（3节点集群）
192.168.1.101:8848
192.168.1.102:8848
192.168.1.103:8848

# application.properties
nacos.cluster.enable=true
nacos.datasource.platform=mysql
nacos.datasource.url=jdbc:mysql://192.168.1.100:3306/nacos
nacos.datasource.username=nacos
nacos.datasource.password=nacos
```

---

## 三、OpenFeign：声明式服务调用

### 3.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | OpenFeign的工作原理？ | ⭐⭐⭐⭐⭐ | 动态代理 + Ribbon/LoadBalancer + HTTP客户端 |
| 2 | OpenFeign如何实现负载均衡？ | ⭐⭐⭐⭐ | 集成LoadBalancer，默认轮询策略 |
| 3 | OpenFeign的超时和重试机制？ | ⭐⭐⭐⭐ | connectTimeout + readTimeout，默认无重试 |
| 4 | OpenFeign如何传递Header？ | ⭐⭐⭐ | @RequestHeader注解 + RequestInterceptor |
| 5 | OpenFeign和Dubbo的区别？ | ⭐⭐⭐⭐ | HTTP vs RPC，轻量级 vs 高性能 |

### 3.2 OpenFeign核心原理

```
@FeignClient("user-service")
public interface UserClient {
    @GetMapping("/user/{id}")
    User getUser(@PathVariable("id") Long id);
}

调用流程：
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│ Controller │ → │  UserClient$Proxy │ → │ LoadBalancer │ → │ user-service │
│ userClient.getUser(1) │     │ (JDK动态代理)      │     │ (选择实例)    │     │ (真实服务)    │
└─────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                        │
                        ↓
                ┌──────────────────┐
                │  RequestTemplate │
                │  (封装HTTP请求)    │
                └──────────────────┘
```

**动态代理创建流程**：
```java
// FeignClientFactoryBean 核心逻辑
public Object getObject() {
    return feign(target);
}

protected <T> T feign(Target<T> target) {
    return builder
        .client(client)                    // HTTP客户端
        .encoder(encoder)                   // 编码器
        .decoder(decoder)                   // 解码器
        .contract(contract)                 // 注解解析
        .options(options)                   // 超时配置
        .target(target);                    // 创建代理对象
}
```

### 3.3 OpenFeign最佳实践

```java
// 1. 基础配置
@FeignClient(
    name = "user-service",
    path = "/api/user",
    fallbackFactory = UserClientFallbackFactory.class,  // 降级工厂
    configuration = FeignConfig.class                    // 自定义配置
)
public interface UserClient {
    
    @GetMapping("/{id}")
    Result<User> getById(@PathVariable("id") Long id);
    
    @PostMapping
    Result<User> create(@RequestBody UserDTO dto);
    
    @GetMapping("/list")
    Result<List<User>> list(@RequestParam("ids") List<Long> ids);
}

// 2. 自定义配置
public class FeignConfig {
    
    @Bean
    public Logger.Level feignLoggerLevel() {
        return Logger.Level.FULL;  // 记录完整请求日志
    }
    
    @Bean
    public Request.Options options() {
        return new Request.Options(
            3, TimeUnit.SECONDS,   // connectTimeout
            5, TimeUnit.SECONDS    // readTimeout
        );
    }
    
    @Bean
    public RequestInterceptor authInterceptor() {
        return template -> {
            // 从上下文获取Token并传递
            String token = SecurityContextHolder.getToken();
            template.header("Authorization", "Bearer " + token);
        };
    }
}

// 3. 降级处理
@Component
public class UserClientFallbackFactory implements FallbackFactory<UserClient> {
    @Override
    public UserClient create(Throwable cause) {
        return new UserClient() {
            @Override
            public Result<User> getById(Long id) {
                log.error("调用user-service失败: {}", cause.getMessage());
                return Result.fail("服务降级：用户服务不可用");
            }
            // ... 其他方法
        };
    }
}
```

---

## 四、Sentinel：服务容错与限流熔断

### 4.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Sentinel和Hystrix的区别？ | ⭐⭐⭐⭐⭐ | Sentinel支持实时监控、规则动态推送、控制台可视化 |
| 2 | Sentinel的限流算法有哪些？ | ⭐⭐⭐⭐⭐ | QPS限流、线程数限流、滑动窗口、漏桶、令牌桶 |
| 3 | 熔断降级的三种策略？ | ⭐⭐⭐⭐ | 慢调用比例、异常比例、异常数 |
| 4 | Sentinel如何实现热点参数限流？ | ⭐⭐⭐⭐ | @SentinelResource + 参数索引配置 |
| 5 | Sentinel集群流控怎么实现？ | ⭐⭐⭐ | Token Server统一管理令牌 |

### 4.2 Sentinel核心概念

```
资源：要保护的对象（接口、方法、代码块）
规则：保护策略（限流、熔断、系统保护、热点参数）
入口：Entry entry = SphU.entry("资源名");

┌─────────────────────────────────────────────────────┐
│                  Sentinel 工作流程                   │
│                                                     │
│  请求 → 创建Entry → 责任链检查 → 业务执行 → 退出Entry  │
│           │              │                          │
│           ↓              ↓                          │
│      NodeSelectorSlot   FlowSlot（限流）             │
│      ClusterBuilderSlot DegradeSlot（熔断）          │
│      StatisticSlot      SystemSlot（系统保护）        │
│      ParamFlowSlot      AuthoritySlot（授权）        │
└─────────────────────────────────────────────────────┘
```

### 4.3 限流规则详解

```java
// 1. QPS限流（每秒请求数）
FlowRule qpsRule = new FlowRule("getUser")
    .setCount(100)                      // QPS阈值
    .setGrade(RuleConstant.FLOW_GRADE_QPS)
    .setStrategy(RuleConstant.STRATEGY_DIRECT)  // 直接拒绝
    .setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_DEFAULT);

// 2. 线程数限流（并发数）
FlowRule threadRule = new FlowRule("getUser")
    .setCount(10)                       // 最大并发线程数
    .setGrade(RuleConstant.FLOW_GRADE_THREAD);

// 3. 关联限流（关联资源触发限流）
FlowRule refRule = new FlowRule("getUser")
    .setCount(100)
    .setStrategy(RuleConstant.STRATEGY_RELATE)
    .setRefResource("updateUser");      // updateUser达到阈值时限流getUser

// 4. 链路限流（入口资源限流）
FlowRule linkRule = new FlowRule("getUser")
    .setCount(50)
    .setStrategy(RuleConstant.STRATEGY_CHAIN)
    .setRefResource("gateway");         // 只对来自gateway的请求限流

// 5. 冷启动（Warm Up）
FlowRule warmupRule = new FlowRule("getUser")
    .setCount(100)
    .setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_WARM_UP)
    .setWarmUpPeriodSec(10);            // 预热时长10秒

// 6. 匀速排队（漏桶）
FlowRule rateRule = new FlowRule("getUser")
    .setCount(100)
    .setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_RATE_LIMITER)
    .setMaxQueueingTimeMs(500);         // 最大排队时长
```

### 4.4 熔断降级规则

```java
// 1. 慢调用比例熔断
DegradeRule slowRule = new DegradeRule("getUser")
    .setGrade(CircuitBreakerStrategy.SLOW_REQUEST_RATIO.getType())
    .setCount(500)                      // 慢调用阈值（ms）
    .setSlowRatioThreshold(0.5)         // 慢调用比例阈值
    .setMinRequestAmount(10)            // 最小请求数
    .setStatIntervalMs(1000)            // 统计时长
    .setTimeWindow(30);                 // 熔断时长（秒）

// 2. 异常比例熔断
DegradeRule errorRatioRule = new DegradeRule("getUser")
    .setGrade(CircuitBreakerStrategy.ERROR_RATIO.getType())
    .setCount(0.3)                      // 异常比例阈值
    .setMinRequestAmount(10)
    .setTimeWindow(30);

// 3. 异常数熔断
DegradeRule errorCountRule = new DegradeRule("getUser")
    .setGrade(CircuitBreakerStrategy.ERROR_COUNT.getType())
    .setCount(5)                        // 异常数阈值
    .setMinRequestAmount(10)
    .setTimeWindow(30);

// 熔断状态机：CLOSED → OPEN → HALF_OPEN → CLOSED/OPEN
```

### 4.5 热点参数限流

```java
@GetMapping("/product/{id}")
@SentinelResource(
    value = "getProduct",
    blockHandler = "handleBlock",
    fallback = "handleFallback"
)
public Product getProduct(@PathVariable Long id) {
    return productService.getById(id);
}

// 热点参数限流规则
ParamFlowRule rule = new ParamFlowRule("getProduct")
    .setCount(100)                      // 全局限流阈值
    .setGrade(RuleConstant.FLOW_GRADE_QPS)
    .setParamIdx(0)                     // 第0个参数（id）
    .setDurationInSec(1);

// 特定参数值例外
ParamFlowItem item = new ParamFlowItem()
    .setObject("1001")                  // 商品ID=1001
    .setClassType(Long.class.getName())
    .setCount(500);                     // 该商品限流500

rule.setParamFlowItemList(Collections.singletonList(item));
```

---

## 五、Spring Cloud Gateway：API网关

### 5.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Gateway的核心组件？ | ⭐⭐⭐⭐⭐ | Route（路由）、Predicate（断言）、Filter（过滤器） |
| 2 | Gateway的工作流程？ | ⭐⭐⭐⭐⭐ | 请求→RoutePredicateHandlerMapping→FilteringWebHandler→Filters→服务 |
| 3 | Gateway如何实现跨域？ | ⭐⭐⭐ | 配置CorsWebFilter或全局Filter |
| 4 | Gateway如何实现统一认证？ | ⭐⭐⭐⭐ | GlobalFilter + JWT验证 |
| 5 | Gateway如何实现限流？ | ⭐⭐⭐⭐ | RequestRateLimiter过滤器 + Redis令牌桶 |

### 5.2 Gateway核心架构

```
                    ┌───────────────────────────────────────┐
                    │          Spring Cloud Gateway         │
                    │                                       │
客户端请求 ────────→│  RoutePredicateHandlerMapping         │
                    │         │                             │
                    │         ↓                             │
                    │  FilteringWebHandler                  │
                    │         │                             │
                    │         ↓                             │
                    │  ┌─────────────────────────────────┐ │
                    │  │ Global Filters (全局过滤器)       │ │
                    │  │ - 认证鉴权                        │ │
                    │  │ - 限流熔断                        │ │
                    │  │ - 日志追踪                        │ │
                    │  └─────────────────────────────────┘ │
                    │         │                             │
                    │         ↓                             │
                    │  ┌─────────────────────────────────┐ │
                    │  │ Gateway Filters (网关过滤器)     │ │
                    │  │ - AddRequestHeader               │ │
                    │  │ - RewritePath                    │ │
                    │  │ - RequestRateLimiter             │ │
                    │  └─────────────────────────────────┘ │
                    │         │                             │
                    └─────────┼─────────────────────────────────┘
                              ↓
                        微服务实例
```

### 5.3 路由配置详解

```yaml
spring:
  cloud:
    gateway:
      routes:
        # 路由1：用户服务
        - id: user-service
          uri: lb://user-service          # 负载均衡
          predicates:
            - Path=/api/user/**           # 路径断言
            - Method=GET,POST             # 方法断言
            - Header=X-Request-Id, \d+    # Header断言（正则）
            - Query=token                 # 查询参数断言
            - After=2024-01-01T00:00:00+08:00  # 时间断言
          filters:
            - StripPrefix=1              # 去掉路径前缀
            - AddRequestHeader=X-Gateway, Gateway
            - name: RequestRateLimiter    # 限流
              args:
                redis-rate-limiter.replenishRate: 100
                redis-rate-limiter.burstCapacity: 200
                key-resolver: "#{@userKeyResolver}"
            - name: Retry                 # 重试
              args:
                retries: 3
                statuses: BAD_GATEWAY,SERVICE_UNAVAILABLE
                methods: GET
                backoff:
                  firstBackoff: 100ms
                  maxBackoff: 500ms
                  factor: 2

        # 路由2：订单服务（权重路由）
        - id: order-service-v1
          uri: lb://order-service-v1
          predicates:
            - Path=/api/order/**
            - Weight=order, 80            # 80%流量

        - id: order-service-v2
          uri: lb://order-service-v2
          predicates:
            - Path=/api/order/**
            - Weight=order, 20            # 20%流量（灰度发布）
```

### 5.4 全局过滤器实现

```java
// 1. 认证过滤器
@Component
public class AuthGlobalFilter implements GlobalFilter, Ordered {
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String token = exchange.getRequest().getHeaders().getFirst("Authorization");
        
        // 白名单路径放行
        String path = exchange.getRequest().getPath().value();
        if (isWhitePath(path)) {
            return chain.filter(exchange);
        }
        
        // 验证Token
        if (StringUtils.isEmpty(token) || !validateToken(token)) {
            exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
            return exchange.getResponse().setComplete();
        }
        
        // 解析用户信息并传递给下游服务
        Long userId = parseUserId(token);
        ServerHttpRequest request = exchange.getRequest().mutate()
            .header("X-User-Id", String.valueOf(userId))
            .build();
        
        return chain.filter(exchange.mutate().request(request).build());
    }
    
    @Override
    public int getOrder() {
        return -100;  // 优先级最高
    }
}

// 2. 限流Key解析器
@Bean
public KeyResolver userKeyResolver() {
    return exchange -> {
        String userId = exchange.getRequest().getHeaders().getFirst("X-User-Id");
        return Mono.just(userId != null ? userId : "anonymous");
    };
}

// 3. 跨域配置
@Bean
public CorsWebFilter corsWebFilter() {
    CorsConfiguration config = new CorsConfiguration();
    config.addAllowedOriginPattern("*");
    config.addAllowedMethod("*");
    config.addAllowedHeader("*");
    config.setAllowCredentials(true);
    
    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/**", config);
    
    return new CorsWebFilter(source);
}
```

---

## 六、微服务架构最佳实践

### 6.1 服务拆分原则

**DDD领域驱动设计**：
- 限界上下文（Bounded Context）：一个上下文对应一个微服务
- 聚合根（Aggregate Root）：数据一致性的边界
- 领域事件（Domain Event）：跨服务通信

**拆分粒度原则**：
- 单一职责：一个服务只做一件事
- 高内聚低耦合：服务内部紧密相关，服务间依赖少
- 独立部署：服务可以独立开发、测试、部署
- 数据隔离：每个服务有独立的数据库

### 6.2 分布式事务处理

> **注意**：分布式事务的完整讲解请参考《分布式系统面试八股文（三）——分布式事务与一致性解决方案》，这里仅针对Spring Cloud场景下的Seata集成进行实战说明。

在微服务场景下，推荐使用 **Seata AT模式**（无侵入、自动回滚）：

```java
// 1. 添加依赖
<dependency>
    <groupId>io.seata</groupId>
    <artifactId>seata-spring-boot-starter</artifactId>
    <version>1.7.0</version>
</dependency>

// 2. 配置
seata:
  tx-service-group: my_tx_group
  service:
    vgroup-mapping:
      my_tx_group: default
  registry:
    type: nacos
    nacos:
      server-addr: 127.0.0.1:8848
      namespace: seata

// 3. 使用（在发起方添加@GlobalTransactional）
@Service
public class OrderService {
    
    @GlobalTransactional(name = "create-order", rollbackFor = Exception.class)
    public void createOrder(OrderDTO dto) {
        // 1. 创建订单（本地事务）
        orderMapper.insert(order);
        
        // 2. 扣减库存（远程调用，Seata自动传播xid）
        storageClient.deduct(dto.getProductId(), dto.getCount());
        
        // 3. 扣减余额（远程调用）
        accountClient.debit(dto.getUserId(), dto.getAmount());
    }
}
```

### 6.3 链路追踪集成

```xml
<!-- 集成SkyWalking Agent -->
<dependency>
    <groupId>org.apache.skywalking</groupId>
    <artifactId>apm-toolkit-trace</artifactId>
    <version>8.16.0</version>
</dependency>
```

```java
// 自定义Span
@Trace
@Tag(key = "order.id", value = "returnedObj.id")
public Order createOrder(OrderDTO dto) {
    // ...
}
```

---

## 七、面试高频综合题

### Q1: 微服务如何保证数据一致性？

**答案要点**：
1. **强一致性**：Seata AT/TCC/Saga（有性能损耗）
2. **最终一致性**：
   - 本地消息表：业务操作 + 写消息表 → 定时任务扫描发送
   - 事务消息：RocketMQ事务消息（半消息 + Commit/Rollback）
   - Saga模式：正向操作 + 补偿操作
3. **最大努力通知**：重试 + 幂等 + 告警

### Q2: 微服务如何设计灰度发布？

**答案要点**：
1. **网关层**：根据Header/Cookie/权重路由到不同版本
2. **注册中心**：Nacos支持服务元数据，结合负载均衡策略
3. **全链路灰度**：透传灰度标识（Header），各服务根据标识调用对应版本

```yaml
# Gateway灰度路由配置示例
spring:
  cloud:
    gateway:
      routes:
        - id: user-service-gray
          uri: lb://user-service-v2
          predicates:
            - Path=/api/user/**
            - Header=X-Gray-Version, v2
```

### Q3: 如何设计一个高可用的微服务架构？

**答案要点**：
1. **注册中心高可用**：Nacos集群（3节点） + MySQL持久化
2. **服务容错**：Sentinel限流熔断 + OpenFeign降级
3. **网关高可用**：多实例部署 + Nginx负载均衡
4. **数据库高可用**：主从复制 + 读写分离
5. **缓存高可用**：Redis Sentinel/Cluster
6. **消息队列高可用**：RocketMQ集群（多Master多Slave）
7. **全链路监控**：SkyWalking/Prometheus + Grafana告警

---

## 八、总结

本文从Spring Cloud Alibaba生态出发，深入解析了：

| 组件 | 核心能力 | 生产实践要点 |
|------|---------|-------------|
| Nacos | 服务注册发现 + 配置中心 | 集群部署、AP/CP切换、配置热更新 |
| OpenFeign | 声明式服务调用 | 超时配置、请求拦截、降级处理 |
| Sentinel | 限流熔断降级 | QPS/线程限流、热点参数、熔断策略 |
| Gateway | API网关 | 路由断言、全局过滤器、限流重试 |

**最佳实践路径**：
1. 注册中心：Nacos集群（生产环境3节点起步）
2. 服务调用：OpenFeign + LoadBalancer + Sentinel
3. 网关：Gateway统一入口，认证、限流、日志
4. 监控：SkyWalking全链路追踪 + Prometheus指标监控

---

> 🎯 **下期预告**：Spring面试八股文（六）——Spring Security安全框架与OAuth2认证授权，将深入解析认证授权流程、JWT实现、OAuth2四种授权模式、单点登录SSO、权限注解等核心知识。

