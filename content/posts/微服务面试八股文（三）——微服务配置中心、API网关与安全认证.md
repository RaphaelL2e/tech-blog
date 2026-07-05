---
title: "微服务面试八股文（三）——微服务配置中心、API网关与安全认证"
date: 2026-07-05T11:00:00+08:00
draft: false
categories: ["微服务", "Spring Cloud"]
tags: ["面试", "八股文", "微服务", "Nacos", "配置中心", "灰度发布", "配置回滚", "Spring Cloud Gateway", "Predicate", "Filter", "JWT", "OAuth2", "SSO", "分布式Session", "RBAC", "ABAC", "API鉴权"]
---

# 微服务面试八股文（三）——微服务配置中心、API网关与安全认证

> 🎯 **本文目标**：承接前两篇的微服务架构基础与服务治理，深入微服务的配置与安全两大基础设施——Nacos配置中心的灰度发布与配置回滚机制、Spring Cloud Gateway的Predicate断言工厂与Filter过滤器链的实战开发、JWT vs OAuth2 vs SSO三种认证方案的对比与选型、分布式Session的一致性解决方案（Redis集中存储 vs Token无状态 vs Sticky Session）、以及API鉴权的RBAC与ABAC模型对比与Spring Security落地实战，构建微服务配置与安全的完整能力体系。

---

## 一、配置中心——微服务的「中央集控」

### 1.1 为什么需要配置中心？

**Q: 没有配置中心的时候，微服务配置管理有哪些痛点？**

```
痛苦的场景：
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Order Service│  │ User Service │  │ Pay Service  │
│              │  │              │  │              │
│ application. │  │ application. │  │ application. │
│ yml          │  │ yml          │  │ yml          │
│              │  │              │  │              │
│ redis.host:  │  │ redis.host:  │  │ redis.host:  │
│   10.0.1.100 │  │   10.0.1.100 │  │   10.0.1.100 │
│              │  │              │  │              │
│ db.url: ...  │  │ db.url: ...  │  │ db.url: ...  │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                        │
               Redis迁移了！新地址 10.0.2.200
                        │
              每个服务都要改application.yml
              然后重新打包、部署、重启...
                        │
              运维人员：😫 30个服务要改到什么时候？
```

**配置中心的解决方案：**

```
有了配置中心之后：
┌──────────────────────────────────────┐
│           Nacos Config Center        │
│  ┌──────────────────────────────┐    │
│  │ redis.host = 10.0.1.100      │    │
│  │ db.url = jdbc:mysql://...     │    │
│  │ thread.pool.size = 50        │    │
│  └──────────────────────────────┘    │
│         ↑ 修改一处，全局生效          │
└──────────────────────────────────────┘
         ↓           ↓           ↓
   Order Service   User Service  Pay Service
   (实时监听)      (实时监听)     (实时监听)
   @RefreshScope  @RefreshScope @RefreshScope
```

### 1.2 Nacos配置中心核心概念

**Q: Nacos配置中心的namespace、group、dataId分别是什么？如何组织配置？**

```yaml
# Nacos的三层配置模型
# Namespace(命名空间) → Group(分组) → DataId(配置集)

# 典型的分环境组织方式：
Namespace: prod（生产环境）
  ├── Group: ORDER_SERVICE
  │     ├── DataId: order-service.yaml         # 完整配置
  │     ├── DataId: order-service-dev.yaml     # 开发环境配置
  │     ├── DataId: order-service-datasource.yaml # 数据库配置（共享）
  │     └── DataId: order-service-threadpool.yaml # 线程池配置（共享）
  ├── Group: COMMON
  │     ├── DataId: common-redis.yaml           # 跨服务共享：Redis配置
  │     ├── DataId: common-mq.yaml              # 跨服务共享：MQ配置
  │     └── DataId: common-sentinel.yaml        # 跨服务共享：Sentinel规则
  └── Group: SECURITY
        └── DataId: encryption-key.yaml         # 加密密钥（敏感配置）

# 最佳实践建议
# 开发环境：Namespace=dev
# 测试环境：Namespace=test
# 生产环境：Namespace=prod

# 原则：
# 1. 使用Namespace做环境隔离（强隔离，不可见）
# 2. 使用Group做服务/模块隔离
# 3. DataId = ${prefix}-${spring.profiles.active}.${file-extension}
```

**Spring Boot集成Nacos配置：**

```yaml
# bootstrap.yml (bootstrap上下文，优先于application.yml加载)
spring:
  application:
    name: order-service
  cloud:
    nacos:
      config:
        server-addr: 127.0.0.1:8848
        namespace: dev                    # 命名空间ID
        group: ORDER_SERVICE             # 分组
        file-extension: yaml             # 配置文件格式
        
        # 导入多个配置（共享配置 + 扩展配置）
        shared-configs:
          - data-id: common-redis.yaml
            group: COMMON
            refresh: true                # 支持动态刷新
          - data-id: common-mq.yaml
            group: COMMON
            refresh: true
        
        extension-configs:
          - data-id: order-service-datasource.yaml
            group: ORDER_SERVICE
            refresh: true
```

### 1.3 Nacos动态刷新机制

**Q: Nacos的配置变更是如何通知到应用并实时生效的？**

```java
// ========== 方式1：@RefreshScope ==========
// 最常用的方式，标注在需要动态刷新的Bean上
@RestController
@RefreshScope  // 配置变更时重建该Bean
public class OrderController {
    
    @Value("${order.timeout:3000}")  // 通过 @Value 注入
    private int timeout;
    
    @Value("${order.max-retry:3}")
    private int maxRetry;
    
    @GetMapping("/config")
    public Map<String, Object> getConfig() {
        return Map.of("timeout", timeout, "maxRetry", maxRetry);
    }
}

// ========== 方式2：@ConfigurationProperties（推荐） ==========
// 支持类型安全 + 自动刷新（无需@RefreshScope）
@Component
@ConfigurationProperties(prefix = "order")
@RefreshScope
public class OrderProperties {
    private int timeout = 3000;
    private int maxRetry = 3;
    private String payUrl;
    // getters/setters...
}

// ========== 方式3：监听配置变更事件 ==========
@Component
public class ConfigChangeListener {
    
    // 监听反射机制收集到的变更
    @EventListener
    public void onRefresh(RefreshScopeRefreshedEvent event) {
        System.out.println("配置已刷新: " + event.getName());
    }
    
    // 监听环境变更
    @EventListener
    public void onEnvironmentChange(EnvironmentChangeEvent event) {
        for (String key : event.getKeys()) {
            System.out.println("配置变更: " + key);
        }
    }
}
```

**Nacos配置刷新的底层原理：**

```
┌────────────────────────────────────────────────────────────────┐
│                      Nacos Server                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 配置变更 → 长轮询(Long Polling)                          │  │
│  │                                                          │  │
│  │ Client发送HTTP请求: /v1/cs/configs/listener               │  │
│  │ 参数: Listening-Configs=dataId^group^md5                  │  │
│  │                                                          │  │
│  │ Nacos Server:                                            │  │
│  │   · 比较MD5 → 相同 → 挂起请求(30s timeout)               │  │
│  │   · MD5变化 → 立即返回新配置                              │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
         │                              ↑
         │ ① 发起长轮询                  │ ④ 返回新配置
         ▼                              │
┌────────────────────────────────────────────────────────────────┐
│                    Nacos Client (应用内)                        │
│                                                                │
│ ② ClientWorker(后台线程)                                       │
│    ├─ LongPollingRunnable 每30s检查一次                        │
│    └─ 收到新配置 → 更新本地缓存                                 │
│                                                                │
│ ③ NacosPropertySource → EnvironmentChangeEvent                 │
│    └─ ContextRefresher.refresh()                               │
│        ├─ 清空 @RefreshScope Bean的缓存                        │
│        └─ 下次访问时重建Bean（懒加载）                          │
│                                                                │
│ ④ @RefreshScope的原理（Scope代理）:                             │
│    ┌─────────────────────────────────────────┐                │
│    │ Spring为@RefreshScope的Bean创建代理       │                │
│    │ 代理对象: ScopedProxyFactoryBean         │                │
│    │ 通过 RefreshScope (继承 GenericScope)    │                │
│    │ 管理Bean的生命周期                       │                │
│    │                                         │                │
│    │ Bean获取流程：                           │                │
│    │ 1. 从RefreshScope缓存中获取              │                │
│    │ 2. 缓存未命中 → 重新创建Bean            │                │
│    │ 3. 配置变更 → 清空缓存 → 下次获取重建    │                │
│    └─────────────────────────────────────────┘                │
└────────────────────────────────────────────────────────────────┘
```

### 1.4 灰度发布与配置回滚

**Q: 如何安全地在生产环境变更配置？灰度发布和配置回滚怎么做？**

```java
// ========== Nacos的灰度发布 ==========

// Nacos提供了"配置灰度发布"功能
// 1. 创建灰度配置（Beta版）
// 2. 指定灰度目标（按IP列表）
// 3. 灰度验证通过后 → 全量发布

// 代码层的灰度实现：
@Component
public class GrayReleaseConfigService {
    
    // 配合Nacos的Beta发布功能
    // Nacos控制台操作：
    //   · 编辑配置 → 发布Beta
    //   · 选择Beta IP（只推送给特定IP的实例）
    //   · 验证OK → 正式发布
    
    // 也可以代码层面实现灰度标签
    @Value("${spring.cloud.nacos.discovery.metadata.version:stable}")
    private String versionTag;
    
    public boolean shouldUseNewConfig() {
        return "beta".equals(versionTag);
    }
}

// ========== 配置回滚 ==========
// Nacos的配置回滚非常简单：
// 1. Nacos控制台 → 配置管理 → 历史版本
// 2. 查看所有历史版本（默认保留30天）
// 3. 点击"回滚" → 选择目标版本 → 确认

// 历史版本记录：
// v5  2026-07-05 10:30  order.timeout=5000        ← 当前
// v4  2026-07-04 18:00  order.timeout=3000        ← 回滚到这里
// v3  2026-07-03 09:00  order.timeout=2000
// v2  2026-07-01 14:00  order.timeout=1000
// v1  2026-06-30 10:00  order.timeout=500         (初始版本)

// 代码实现自动回滚监听：
@Component
public class ConfigRollbackMonitor {
    
    @EventListener
    public void onConfigChange(EnvironmentChangeEvent event) {
        // 检测到配置变更后，开一个定时器
        // 如果在监控时间内(如5分钟)出现异常指标，自动回滚
        ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(1);
        scheduler.schedule(() -> {
            if (isMetricsDegraded()) {
                // 触发自动回滚（调用Nacos API）
                rollbackConfig("order-service", "ORDER_SERVICE", 
                              "order-service.yaml", "v4");
            }
        }, 5, TimeUnit.MINUTES);
    }
    
    private boolean isMetricsDegraded() {
        // 检查错误率、RT等核心指标是否劣化
        return errorRate > 0.05 || avgRT > 1000;
    }
}
```

**最佳实践——配置变更 checklist：**

```
配置变更安全流程：
1. ☐ 确认变更内容：改了什么？影响哪些服务？
2. ☐ 灰度发布：先推Beta版到1-2个实例
3. ☐ 监控验证：观察5分钟，检查错误率/RT无异常
4. ☐ 全量发布：确认灰度OK后，全量推送到所有实例
5. ☐ 持续监控：发布后持续观察30分钟
6. ☐ 准备回滚：确认回滚到哪个历史版本（提前记录）
```

---

## 二、Spring Cloud Gateway——微服务流量入口

### 2.1 Gateway核心架构

**Q: Spring Cloud Gateway的架构是怎样的？与Zuul有什么区别？**

```java
// Gateway的三大核心概念：
// 1. Route(路由) — 包含ID、目标URI、Predicate集合、Filter集合
// 2. Predicate(断言) — 匹配HTTP请求的条件（路径、Header、参数等）
// 3. Filter(过滤器) — 对请求/响应进行修改处理

// Gateway基于WebFlux（Reactive），非阻塞IO
// Zuul 1.x基于Servlet（阻塞IO），Zuul 2.x也是Reactive但生态不如Gateway
```

**Gateway请求处理流程：**

```
Client Request
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│              Spring Cloud Gateway                           │
│                                                             │
│  ① Netty Server (Reactor Netty)                             │
│     └─ 接收HTTP请求，封装为 ServerHttpRequest/Response       │
│                                                             │
│  ② RoutePredicateHandlerMapping                              │
│     └─ 遍历所有Route的Predicate，找到匹配的Route              │
│                                                             │
│  ③ FilteringWebHandler                                       │
│     └─ 构建 Filter Chain                                    │
│         每个Route有一组GlobalFilter + GatewayFilter           │
│                                                             │
│  ④ Filter Chain 执行流程（责任链模式）:                       │
│                                                             │
│     ┌──────────────────────────────────────┐                │
│     │  请求到达                             │                │
│     │    ↓                                  │                │
│     │  [pre filters]                        │                │
│     │  order值从小到大执行                   │                │
│     │  如: 限流→认证→日志→路由               │                │
│     │    ↓                                  │                │
│     │  Proxy Filter (实际转发请求)          │                │
│     │  通过 NettyRoutingFilter 转发         │                │
│     │  到下游服务                            │                │
│     │    ↓                                  │                │
│     │  [post filters]                       │                │
│     │  order值从大到小执行                   │                │
│     │  如: 路由→日志→加密→返回               │                │
│     │    ↓                                  │                │
│     │  响应返回客户端                        │                │
│     └──────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Predicate断言工厂实战

**Q: Gateway有哪些内置Predicate？如何自定义Predicate？**

```yaml
# ===== Spring Cloud Gateway 配置式路由 =====
spring:
  cloud:
    gateway:
      routes:
        # 路由1：订单服务
        - id: order-service
          uri: lb://order-service          # lb:// 表示负载均衡
          predicates:
            - Path=/api/orders/**          # 路径匹配
            - Method=GET,POST               # 方法匹配
            - Header=X-API-Version, v2      # Header匹配
          filters:
            - StripPrefix=1                 # 去掉 /api 前缀
            - AddRequestHeader=X-Gateway, true
        
        # 路由2：用户服务（按时间灰度的例子）
        - id: user-service-v2
          uri: lb://user-service-v2
          predicates:
            - Path=/api/users/**
            - Between=2026-07-05T00:00:00+08:00, 2026-07-06T00:00:00+08:00
            - Weight=user-service, 90           # 权重路由
        
        - id: user-service-v1
          uri: lb://user-service
          predicates:
            - Path=/api/users/**
            - Weight=user-service, 10           # 灰度10%流量到v1
        
        # 路由3：支付服务（带限流）
        - id: pay-service
          uri: lb://pay-service
          predicates:
            - Path=/api/pay/**
            - Header=Content-Type, application/json
            - RemoteAddr=192.168.0.0/16        # 内网IP段
            - Query=token, .+                   # 必须带token参数
          filters:
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 10
                redis-rate-limiter.burstCapacity: 20
        
        # 路由4：兜底/降级路由
        - id: fallback
          uri: forward:/fallback
          predicates:
            - Path=/**
          filters:
            - name: CircuitBreaker
              args:
                name: fallbackCmd
                fallbackUri: forward:/fallback
```

**内置的11种Predicate工厂：**

```java
// 1. Path — 路径匹配（支持Ant风格）
// 2. Method — HTTP方法匹配
// 3. Header — 请求头匹配
// 4. Query — 参数匹配
// 5. Cookie — Cookie匹配
// 6. Host — 主机名匹配
// 7. RemoteAddr — 远程地址匹配
// 8. Weight — 按权重路由（灰度发布）
// 9. Before/After/Between — 按时间路由
// 10. XForwardedRemoteAddr — X-Forwarded-For地址匹配
// 11. CloudFoundryRoute — CloudFoundry路由

// 自定义Predicate（Java DSL方式）：
@Bean
public RouteLocator customRoutes(RouteLocatorBuilder builder) {
    return builder.routes()
        .route("custom-route", r -> r
            .predicate(exchange -> {
                // 自定义断言逻辑：比如只有VIP用户才能访问
                String userId = exchange.getRequest()
                    .getHeaders().getFirst("X-User-Id");
                return userService.isVip(userId);
            })
            .uri("lb://vip-service")
        )
        .build();
}
```

### 2.3 Filter过滤器链实战

**Q: Gateway有哪些全局Filter？如何实现自定义Filter？**

```java
// ========== Gateway内置的34种GatewayFilter ==========
// 经常用到的主要有：

// 请求修改类：
AddRequestHeader      // 添加请求头
AddRequestParameter   // 添加请求参数
SetRequestHeader      // 设置请求头
RemoveRequestHeader   // 移除请求头
RewritePath           // 重写路径
PrefixPath            // 添加路径前缀
StripPrefix           // 去除路径前缀（最常用）
SetPath               // 设置路径

// 响应修改类：
AddResponseHeader     // 添加响应头
SetResponseHeader     // 设置响应头
RemoveResponseHeader  // 移除响应头
RewriteResponseHeader // 重写响应头
DedupeResponseHeader  // 去重响应头

// 功能类：
RequestRateLimiter    // 限流（令牌桶算法）
Retry                 // 重试
CircuitBreaker        // 熔断
RequestSize           // 请求大小限制
CacheRequestBody      // 缓存请求体
ModifyRequestBody     // 修改请求体
ModifyResponseBody    // 修改响应体

// ========== 自定义全局Filter ==========
@Component
@Order(-1)  // order越小越先执行，-1是最高优先级
public class RequestLoggingGlobalFilter implements GlobalFilter, Ordered {
    
    private static final Logger log = LoggerFactory.getLogger(
        RequestLoggingGlobalFilter.class);
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, 
                             GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        
        // ===== 前置处理：记录请求信息 =====
        long startTime = System.currentTimeMillis();
        String requestId = UUID.randomUUID().toString();
        String path = request.getURI().getPath();
        String method = request.getMethodValue();
        
        log.info("[{}] {} {} from {}", requestId, method, path, 
                 request.getRemoteAddress());
        
        // 添加追踪ID到请求头，方便链路追踪
        ServerHttpRequest mutatedRequest = request.mutate()
            .header("X-Request-Id", requestId)
            .build();
        ServerWebExchange mutatedExchange = exchange.mutate()
            .request(mutatedRequest)
            .build();
        
        // ===== 跳过特定路径的日志 =====
        if (path.startsWith("/actuator") || path.startsWith("/health")) {
            return chain.filter(mutatedExchange);
        }
        
        // ===== 执行过滤器链 =====
        return chain.filter(mutatedExchange)
            .then(Mono.fromRunnable(() -> {
                // ===== 后置处理：记录响应信息 =====
                long duration = System.currentTimeMillis() - startTime;
                HttpStatus status = exchange.getResponse().getStatusCode();
                log.info("[{}] {} {} → {} ({}ms)", 
                    requestId, method, path, 
                    status != null ? status.value() : "???",
                    duration);
                
                // 慢请求告警
                if (duration > 3000) {
                    log.warn("[{}] SLOW REQUEST: {} {} took {}ms", 
                        requestId, method, path, duration);
                }
            }));
    }
    
    @Override
    public int getOrder() {
        return -1;  // 最高优先级，确保最先拦截
    }
}

// ========== 自定义GatewayFilter工厂 ==========
// 创建可配置的过滤器（可在yml中配置使用）
@Component
public class ValidateTokenGatewayFilterFactory 
        extends AbstractGatewayFilterFactory<ValidateTokenGatewayFilterFactory.Config> {
    
    public ValidateTokenGatewayFilterFactory() {
        super(Config.class);
    }
    
    @Override
    public GatewayFilter apply(Config config) {
        return (exchange, chain) -> {
            String token = exchange.getRequest()
                .getHeaders().getFirst("Authorization");
            
            if (token == null || !token.startsWith("Bearer ")) {
                // 未授权，直接返回401
                exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
                return exchange.getResponse().setComplete();
            }
            
            // 验证token并解析用户信息
            String actualToken = token.substring(7);
            if (!validateToken(actualToken)) {
                exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
                return exchange.getResponse().setComplete();
            }
            
            // 放行
            return chain.filter(exchange);
        };
    }
    
    public static class Config {
        // 可配置参数（在yml中传入）
        private String excludeUrls;
        // getters/setters...
    }
    
    private boolean validateToken(String token) {
        // JWT解析验证逻辑
        return true;
    }
}

// yml中使用自定义Filter：
// spring:
//   cloud:
//     gateway:
//       routes:
//         - id: secure-route
//           uri: lb://user-service
//           predicates:
//             - Path=/api/users/**
//           filters:
//             - ValidateToken=excludeUrls: /api/login,/api/register
```

### 2.4 Gateway vs Zuul vs Nginx——网关选型对比

| 对比维度 | Spring Cloud Gateway | Zuul 1.x | Nginx / Kong |
|----------|---------------------|----------|--------------|
| **IO模型** | 非阻塞(Netty) | 阻塞(Tomcat) | 非阻塞(epoll) |
| **性能** | 高（Reactive） | 低（Servlet阻塞） | 极高（C语言） |
| **扩展性** | Filter机制，Java生态 | Filter机制 | Lua脚本(Kong) / Nginx模块 |
| **与Spring Cloud集成** | 原生完美集成 | Spring Cloud支持 | 需要额外集成 |
| **动态路由** | 支持（配合配置中心） | 需要重启 | Nginx需reload / Kong支持API |
| **限流** | 内置RequestRateLimiter | 需自定义 | 内置limit_req |
| **适用场景** | Spring Cloud微服务 | 遗留项目 | 通用网关/API网关 |

---

## 三、微服务安全认证

### 3.1 认证方案全景对比

**Q: JWT、OAuth2、SSO三种方案有什么区别？各自适用什么场景？**

```
┌────────────────────────────────────────────────────────────────────────┐
│                      三种认证方案对比                                    │
├──────────┬─────────────────┬─────────────────┬─────────────────────────┤
│   维度   │      JWT        │     OAuth2      │        SSO              │
├──────────┼─────────────────┼─────────────────┼─────────────────────────┤
│ 核心思路 │ 无状态Token      │ 授权码协议       │ 统一认证中心              │
│         │ 服务端不存Session │ 第三方授权       │ 一次登录，多系统互通       │
├──────────┼─────────────────┼─────────────────┼─────────────────────────┤
│ 认证信息 │ Token自包含       │ Access Token + │ 集中Session(Ticket)     │
│ 存储位置 │ (Header+Payload+ │ Refresh Token   │ 认证中心维护             │
│         │  Signature)      │ (服务端存储)     │                         │
├──────────┼─────────────────┼─────────────────┼─────────────────────────┤
│ 状态     │ 无状态            │ 有状态           │ 有状态                   │
│         │ (服务端不存)       │ (需Token存储)    │ (认证中心存Session)      │
├──────────┼─────────────────┼─────────────────┼─────────────────────────┤
│ 优点     │ · 高性能，不查库   │ · 安全的第三方授权│ · 一次登录全系统          │
│         │ · 天然分布式友好   │ · Token可撤回     │ · 统一的登出              │
│         │ · 跨语言通用      │ · 权限粒度精细     │ · 企业级标配              │
├──────────┼─────────────────┼─────────────────┼─────────────────────────┤
│ 缺点     │ · 无法主动撤销    │ · 实现复杂        │ · 单点故障风险            │
│         │ · Token体积大     │ · 额外网络开销    │ · 依赖认证中心            │
│         │ · Payload明文    │ · 内部调用也需Token│ · 登出需广播              │
├──────────┼─────────────────┼─────────────────┼─────────────────────────┤
│ 适用场景 │ 微服务间无状态API │ 第三方登录        │ 企业内部多系统            │
│         │ 前后端分离应用     │ (微信/GitHub登录) │ 办公套件统一登录          │
│         │ 移动端App API    │ 开放平台API       │                         │
└──────────┴─────────────────┴─────────────────┴─────────────────────────┘
```

### 3.2 JWT深度解析

**Q: JWT的结构是什么？为什么说JWT「无状态」但「无法撤销」？**

```java
// JWT的结构：Header.Payload.Signature
// eyJhbGciOiJIUzI1NiJ9.eyJ1c2VySWQiOjEyMywicm9sZSI6IkFETUlOIn0.xxx

// ===== Header（算法声明）=====
{
  "alg": "HS256",    // 签名算法：HMAC-SHA256
  "typ": "JWT"       // 类型
}
// → Base64编码 → eyJhbGciOiJIUzI1NiJ9

// ===== Payload（数据载荷）=====
{
  "sub": "123",           // 主体（用户ID）
  "name": "张三",
  "role": "ADMIN",
  "iat": 1625472000,      // 签发时间
  "exp": 1625558400       // 过期时间（24小时后）
}
// → Base64编码 → eyJ1c2VySWQiOjEyMywicm9sZSI6IkFETUlOIn0

// ===== Signature（签名）=====
// HMACSHA256(
//   base64UrlEncode(header) + "." + base64UrlEncode(payload),
//   secret
// )

// ========== JWT安全注意事项 ==========
// ❌ 错误做法：
{
  "userId": 123,
  "password": "123456",  // 绝对不要在JWT里放密码！
  "creditCard": "..."    // 不要放敏感信息！Payload是Base64不是加密
}

// ✅ 正确做法（Payload只放最小必要信息）：
{
  "sub": "123",          // 用户ID
  "roles": ["USER"],     // 角色（简化版）
  "iat": 1625472000,     // 签发时间
  "exp": 1625558400,     // 过期时间
  "jti": "uuid-xxx"      // Token唯一ID（用于黑名单机制）
}
```

**JWT Spring Boot实战：**

```java
// ========== JWT工具类 ==========
@Component
public class JwtTokenProvider {
    
    @Value("${jwt.secret:MySecretKeyForJWTGeneration2026!}")
    private String secret;
    
    @Value("${jwt.expiration:86400000}")  // 默认24小时
    private long expirationMs;
    
    // 生成Token
    public String generateToken(UserDetails userDetails) {
        Date now = new Date();
        Date expiryDate = new Date(now.getTime() + expirationMs);
        
        return Jwts.builder()
            .setSubject(userDetails.getUsername())
            .claim("userId", userDetails.getId())
            .claim("roles", userDetails.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .collect(Collectors.toList()))
            .setIssuedAt(now)
            .setExpiration(expiryDate)
            .setId(UUID.randomUUID().toString())  // jti
            .signWith(Keys.hmacShaKeyFor(secret.getBytes()))
            .compact();
    }
    
    // 验证Token
    public boolean validateToken(String token) {
        try {
            Jwts.parserBuilder()
                .setSigningKey(Keys.hmacShaKeyFor(secret.getBytes()))
                .build()
                .parseClaimsJws(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            // ExpiredJwtException - 过期
            // MalformedJwtException - 格式错误
            // SignatureException - 签名错误
            // UnsupportedJwtException - 不支持的JWT
            return false;
        }
    }
    
    // 从Token中获取用户ID
    public String getUserIdFromToken(String token) {
        Claims claims = Jwts.parserBuilder()
            .setSigningKey(Keys.hmacShaKeyFor(secret.getBytes()))
            .build()
            .parseClaimsJws(token)
            .getBody();
        return claims.getSubject();
    }
}

// ========== JWT认证过滤器 ==========
@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {
    
    @Autowired
    private JwtTokenProvider tokenProvider;
    
    @Override
    protected void doFilterInternal(HttpServletRequest request,
            HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        
        // 1. 从Header中获取Token
        String token = getTokenFromRequest(request);
        
        // 2. 验证Token
        if (StringUtils.hasText(token) && tokenProvider.validateToken(token)) {
            // 3. 从Token中解析用户信息
            String userId = tokenProvider.getUserIdFromToken(token);
            
            // 4. 设置SecurityContext
            UsernamePasswordAuthenticationToken authentication = 
                new UsernamePasswordAuthenticationToken(
                    userId, null, Collections.emptyList());
            authentication.setDetails(
                new WebAuthenticationDetailsSource().buildDetails(request));
            SecurityContextHolder.getContext()
                .setAuthentication(authentication);
        }
        
        filterChain.doFilter(request, response);
    }
    
    private String getTokenFromRequest(HttpServletRequest request) {
        String bearerToken = request.getHeader("Authorization");
        if (StringUtils.hasText(bearerToken) && bearerToken.startsWith("Bearer ")) {
            return bearerToken.substring(7);
        }
        return null;
    }
}
```

### 3.3 OAuth2授权码流程

**Q: OAuth2的四种授权模式是什么？授权码模式为什么最安全？**

```
OAuth2的四种授权模式：

1. 授权码模式(Authorization Code) — 最安全，推荐
   适用：有后端的Web应用（第三方登录）
   流程：授权码先回到后端 → 后端用授权码换Access Token

2. 隐式模式(Implicit) — 已废弃！
   适用：无后端的纯前端应用（曾经）
   问题：Token直接暴露在URL中

3. 密码模式(Password Credentials) — 仅限自家应用
   适用：自家App/前端直接传用户名密码
   注意：绝不给第三方用

4. 客户端模式(Client Credentials) — 服务间调用
   适用：机器对机器（无用户参与）
   场景：微服务A调用微服务B的API

授权码模式详细流程：

   User              Client(App)        Auth Server     Resource Server
    │                    │                   │               │
    │ ① 点击"微信登录"    │                   │               │
    │───────────────────→│                   │               │
    │                    │ ② 重定向到授权页    │               │
    │                    │──────────────────→│               │
    │ ③ 用户确认授权      │                   │               │
    │──────────────────────────────────────→│               │
    │                    │ ④ 返回授权码(code)  │               │
    │                    │←──────────────────│               │
    │                    │ ⑤ code + client   │               │
    │                    │   _secret 换Token  │               │
    │                    │──────────────────→│               │
    │                    │ ⑥ 返回Access Token │               │
    │                    │   + Refresh Token  │               │
    │                    │←──────────────────│               │
    │                    │ ⑦ Access Token    │               │
    │                    │─────────────────────────────────→│
    │                    │ ⑧ 返回用户数据      │               │
    │                    │←─────────────────────────────────│
    │ ⑨ 登录成功          │                   │               │
    │←───────────────────│                   │               │
    
关键安全设计：
- code是一次性的（用完即失效）
- code通过后端传输（不会暴露在浏览器URL）
- client_secret只在后端使用（前端拿不到）
- Access Token不经过浏览器
```

---

## 四、分布式Session的四种解决方案

### 4.1 为什么Session在分布式环境下有问题？

**Q: 单体应用迁移到微服务后，Session为什么失效了？**

```
问题场景：

客户端 (Cookie: JSESSIONID=ABC123)
    │
    │ 第1次请求
    ▼
┌───────────────────┐
│  负载均衡器(Nginx)  │
└───────────────────┘
    │            │
    ▼            │
┌─────────┐      │
│ Server A │      │     第2次请求被分到Server B
│          │      │     Server B上没有Session ABC123
│ Session: │      ▼     → 认证失败，需要重新登录！
│ ABC123 → │  ┌─────────┐
│ {user:张 │  │ Server B │
│  三, ...}│  │          │
└─────────┘  │ Session: │    😡 用户：我怎么又要登录？
             │ (空的)   │
             └─────────┘
```

### 4.2 四种解决方案对比

```
方案1：Sticky Session（粘性会话）
┌─────────────────┐
│ IP Hash / Cookie │  同一客户端始终路由到同一服务器
└─────────────────┘
优点：最简单，无需改代码
缺点：服务器故障Session丢失，负载不均衡
适用：小规模/过渡期方案

方案2：Session复制（Tomcat Cluster）
┌────────┐  ┌────────┐  ┌────────┐
│Server A│←→│Server B│←→│Server C│  组播复制Session
└────────┘  └────────┘  └────────┘
优点：应用无感知
缺点：带宽消耗大，节点越多越慢，有延迟
适用：小型集群(<5个节点)

方案3：Redis集中存储（推荐！）
┌────────┐  ┌────────┐  ┌────────┐
│Server A│  │Server B│  │Server C│
└───┬────┘  └───┬────┘  └───┬────┘
    │           │           │
    └───────────┴───────────┘
                │
         ┌──────┴──────┐
         │    Redis    │  所有Session存Redis
         │  (集群)     │
         └─────────────┘
优点：高性能、高可用、无单点故障
缺点：引入Redis依赖，需要处理Redis故障
适用：绝大多数场景（首选方案）

方案4：Token无状态（JWT）
服务端完全不存Session，信息都在Token里
优点：天然分布式友好，服务端无状态
缺点：Token无法主动撤销，体积大
适用：前后端分离、移动端API
```

### 4.3 Spring Session + Redis实战

```java
// ========== 依赖配置 ==========
// pom.xml
// spring-session-data-redis + spring-boot-starter-data-redis

// ========== application.yml ==========
spring:
  session:
    store-type: redis               # 指定Session存储类型
    redis:
      namespace: spring:session     # Redis Key前缀
      flush-mode: on_save           # 保存模式
    timeout: 1800s                  # Session过期时间(30分钟)
  
  redis:
    host: localhost
    port: 6379
    password: 
    timeout: 3000ms

// ========== 配置类 ==========
@Configuration
@EnableRedisHttpSession(maxInactiveIntervalInSeconds = 1800)
public class SessionConfig {
    
    @Bean
    public RedisSerializer<Object> springSessionDefaultRedisSerializer() {
        // 使用JSON序列化（替代JDK序列化，便于调试查看）
        return new GenericJackson2JsonRedisSerializer();
    }
    
    @Bean
    public CookieSerializer cookieSerializer() {
        DefaultCookieSerializer serializer = new DefaultCookieSerializer();
        serializer.setCookieName("SESSIONID");      // Cookie名称
        serializer.setCookiePath("/");              // Cookie路径
        serializer.setDomainNamePattern("^.+?\\.(\\w+\\.[a-z]+)$"); // 跨子域
        serializer.setUseHttpOnlyCookie(true);       // 防止JS读取
        serializer.setUseSecureCookie(false);        // HTTPS时才设为true
        return serializer;
    }
}

// ========== 使用（和普通HttpSession一样！） ==========
@RestController
public class LoginController {
    
    @PostMapping("/login")
    public Result login(@RequestBody LoginRequest request,
                        HttpSession session) {
        // 验证用户名密码...
        User user = userService.authenticate(request.getUsername(), 
                                             request.getPassword());
        if (user != null) {
            // 存Session（自动存入Redis）
            session.setAttribute("currentUser", user);
            session.setAttribute("loginTime", System.currentTimeMillis());
            return Result.success("登录成功");
        }
        return Result.error("用户名或密码错误");
    }
    
    @GetMapping("/user/info")
    public Result userInfo(HttpSession session) {
        // 取Session（自动从Redis读取）
        User user = (User) session.getAttribute("currentUser");
        if (user == null) {
            return Result.error(401, "未登录");
        }
        return Result.success(user);
    }
    
    @PostMapping("/logout")
    public Result logout(HttpSession session) {
        // 销毁Session（自动删除Redis中的Key）
        session.invalidate();
        return Result.success("已退出");
    }
}

// Redis中存储的Session数据示例：
// Key:   spring:session:sessions:expires:abc-123-def
// Type:  String (JSON)
// Value: {
//   "creationTime": 1625472000000,
//   "lastAccessedTime": 1625473800000,
//   "maxInactiveInterval": 1800,
//   "sessionAttrs": {
//     "currentUser": {"id": 123, "name": "张三", "role": "ADMIN"},
//     "loginTime": 1625472000000
//   }
// }
```

---

## 五、API鉴权——RBAC与ABAC

### 5.1 RBAC（基于角色的访问控制）

**Q: 什么是RBAC？核心数据模型是怎样的？**

```
RBAC核心模型（5张表）：

┌──────────┐         ┌──────────────┐         ┌──────────┐
│   User   │────────→│  User_Role   │←────────│   Role   │
│ 用户表    │   N:M    │  用户角色关联  │   N:M   │  角色表   │
└──────────┘         └──────────────┘         └──────────┘
                                                      │
                                                      │ N:M
                                                      ↓
┌──────────────┐         ┌──────────────┐         ┌──────────┐
│ Permission   │←────────│ Role_Perm    │         │  Menu    │
│  权限表       │   N:M   │ 角色权限关联   │         │  菜单表   │
└──────────────┘         └──────────────┘         └──────────┘

常见设计：
User    → id, username, password, status
Role    → id, role_name, role_code, description
Menu    → id, parent_id, menu_name, path, component
Perm    → id, perm_name, perm_code (如 order:create)
```

**Spring Security + RBAC代码实战：**

```java
// ========== 权限注解方式 ==========
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    
    @PreAuthorize("hasRole('ADMIN')")  // 只有ADMIN角色可以
    @GetMapping("/all")
    public Result getAllOrders() { ... }
    
    @PreAuthorize("hasAnyRole('ADMIN', 'SALES')")  // ADMIN或SALES
    @GetMapping("/{id}")
    public Result getOrder(@PathVariable Long id) { ... }
    
    @PreAuthorize("hasAuthority('order:create')")  // 权限字符串
    @PostMapping
    public Result createOrder(@RequestBody Order order) { ... }
    
    @PreAuthorize("hasAuthority('order:delete') or hasRole('ADMIN')")
    @DeleteMapping("/{id}")
    public Result deleteOrder(@PathVariable Long id) { ... }
    
    // SpEL表达式高级用法
    @PreAuthorize("@orderService.isOwner(#id, authentication.principal.username)")
    @PutMapping("/{id}")
    public Result updateOrder(@PathVariable Long id, @RequestBody Order order) {
        // 只能修改自己的订单
        ...
    }
}

// ========== 数据库动态权限加载 ==========
@Component
public class DynamicPermissionEvaluator {
    
    @Autowired
    private MenuService menuService;
    
    // 从数据库加载权限配置
    @PostConstruct
    public void loadPermissions() {
        // SELECT m.path, r.role_code 
        // FROM menu m 
        // JOIN role_menu rm ON m.id = rm.menu_id 
        // JOIN role r ON rm.role_id = r.id
        List<MenuPermission> permissions = menuService.loadAllMenuPermissions();
        
        // 构建权限映射：/api/orders/** → [ADMIN, SALES]
        Map<String, Set<String>> permissionMap = new HashMap<>();
        for (MenuPermission perm : permissions) {
            permissionMap.computeIfAbsent(perm.getPath(), 
                k -> new HashSet<>()).add(perm.getRoleCode());
        }
        // 缓存到本地或Redis，用于Token拦截器校验
    }
}
```

### 5.2 RBAC vs ABAC 对比

**Q: RBAC和ABAC有什么区别？什么时候用ABAC？**

```
┌─────────────────────────────────────────────────────────────────┐
│                    RBAC vs ABAC 对比                              │
├──────────────┬──────────────────────┬────────────────────────────┤
│    维度      │        RBAC          │          ABAC              │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 核心思想     │ "什么人有什么角色"     │ "在什么条件下可以做什么"    │
│             │ 角色 = 权限集合       │ 属性 = 访问控制的判断依据   │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 判断逻辑     │ 用户.角色 IN {允许角色}│ 评估用户属性+资源属性+      │
│             │                      │ 环境属性+操作属性          │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 灵活性       │ 中（增角色需改代码）   │ 高（规则引擎动态评估）      │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 粒度         │ 粗粒度（角色级别）     │ 细粒度（属性级别）          │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 维护成本     │ 低（角色少时）         │ 高（策略规则复杂）          │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 适用场景     │ 企业内部管理系统       │ 多租户SaaS平台              │
│             │ 菜单/按钮权限控制      │ 数据级别权限控制            │
│             │                      │ 合规要求的细粒度控制         │
├──────────────┼──────────────────────┼────────────────────────────┤
│ 实例         │ "张三是管理员，        │ "允许财务部门的用户         │
│             │  可以访问所有功能"      │  在工作时间(9-18点)         │
│             │                      │  从公司IP访问工资数据"      │
└──────────────┴──────────────────────┴────────────────────────────┘

ABAC的四类属性：
1. 主体属性(Subject)：用户ID、部门、职级、安全等级
2. 资源属性(Resource)：数据类型、密级、所属部门
3. 操作属性(Action)：读/写/删除/审批
4. 环境属性(Environment)：时间、IP、设备类型、网络区域
```

**实际建议：RBAC做大框架，ABAC做精细化补充**

```
推荐组合方案：
├── RBAC：控制菜单/页面/按钮的可见性
│   例：管理员 → 可见所有菜单，普通用户 → 只看到自己的
│
├── ABAC/数据权限：控制数据的可操作范围
│   例：部门经理 → 只看本部门数据
│        销售 → 只看自己客户的数据
│        区域总监 → 看本区域数据
│
└── 动态规则引擎（如Drools）处理复杂策略
    例：金额>100万的订单 → 需要总监审批
        跨部门数据访问 → 需要合规审批
```

---

## 六、面试高频题总结

```
配置中心 5连问：
1. Nacos配置中心的三层模型（namespace/group/dataId）？
2. Nacos配置变更是如何实时推送到应用的？
3. @RefreshScope的原理是什么？和@ConfigurationProperties有什么区别？
4. 如何实现配置的灰度发布？出现问题时如何快速回滚？
5. Nacos和Apollo的区别？各有什么优劣？

API网关 5连问：
6. Spring Cloud Gateway的工作原理？三大核心组件是什么？
7. Gateway的Filter和GlobalFilter有什么区别？执行顺序是怎样的？
8. 如何在Gateway中实现限流？内置的RequestRateLimiter用的是什么算法？
9. Gateway如何实现灰度发布和金丝雀部署？
10. Gateway vs Zuul vs Kong/APISIX，选型依据是什么？

安全认证 5连问：
11. JWT的结构是什么？为什么说它「无状态」但「无法主动撤销」？
12. OAuth2的四种授权模式？为什么授权码模式最安全？
13. 分布式Session有哪几种解决方案？各有什么优缺点？
14. Spring Session + Redis的原理是什么？
15. RBAC和ABAC有什么区别？实际项目中怎么选型？
```

---

## 七、下期预告

下一篇将深入 **微服务数据架构与分布式数据库实战**——分库分表的垂直拆分与水平拆分策略、ShardingSphere的Sharding-JDBC和Sharding-Proxy两种模式的对比与实战、分布式ID生成的六种方案（UUID/雪花算法/号段模式/美团Leaf/滴滴TinyID/百度UidGenerator）、读写分离与数据源动态路由的实现、以及跨库事务与Seata AT/TCC/Saga三种模式的深度对比，构建微服务数据架构的完整能力体系。敬请期待！🦐

---

*本系列持续更新中，欢迎关注公众号获取最新文章。*
