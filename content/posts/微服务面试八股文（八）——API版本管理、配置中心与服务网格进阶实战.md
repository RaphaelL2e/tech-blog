---
title: "微服务面试八股文（八）——API版本管理、配置中心与服务网格进阶实战"
date: 2026-07-09T11:00:00+08:00
draft: false
categories: ["微服务", "Spring Cloud"]
tags: ["面试", "八股文", "微服务", "API版本管理", "配置中心", "Apollo", "Spring Cloud Config", "服务网格", "Istio", "Gateway", "灰度发布", "A/B测试", "Feature Flag", "金丝雀"]
author: "飞哥"
---

# 微服务面试八股文（八）——API版本管理、配置中心与服务网格进阶实战

> 🎯 **本文目标**：承接微服务部署与容器化实战，聚焦 API 版本管理策略与配置中心的微服务集成、以及服务网格进阶特性。掌握这些内容，你将具备微服务生命周期管理、灰度发布、配置治理的完整工程能力，能够在面试中展现从"能用"到"用好"的微服务工程化深度。

---

## 一、API 版本管理：策略对比与选型

### 1.1 为什么微服务必须考虑 API 版本管理？

```
微服务 API 版本管理的核心挑战：

单体应用：
  一个代码库 → 一个 API → 修改直接向前兼容
  同一时刻只有一个版本在生产运行

微服务架构：
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Gateway │────▶│ Order Svc│────▶│ Stock Svc│
  │          │     │  v1.5.0  │     │  v2.1.0  │
  └──────────┘     └──────────┘     └──────────┘
       │                                    ↑
       │                                    │
  多个客户端（App/Web/小程序）         多个消费者依赖
  
问题场景：
1. Order Service v1.5.0 调用 Stock Service v2.1.0 的 API
   → v2.1.0 改了一个字段名，Order Service 不知道 → 解析失败
2. 需要给 iOS/Android 提供不同格式的响应
   → 同一个接口，客户端版本不同 → 需要版本兼容
3. 一次大版本升级，不能让所有消费者同时升级
   → 新旧版本必须共存 → 需要多版本管理

API 版本管理的本质：管理"向后兼容"与"breaking change"的艺术
```

### 1.2 三大版本管理策略对比

```
┌────────────────────────────────────────────────────────────┐
│                  API 版本管理三大策略                        │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  策略一：URL 路径版本                                        │
│    GET /api/v1/users                                        │
│    GET /api/v2/users                                        │
│  优势：直观、容易测试、人可读                                 │
│  劣势：URL 变了、不RESTful、污染 URL                        │
│                                                            │
│  策略二：Header 版本                                         │
│    GET /api/users                                           │
│    Header: Accept-Version: 2024-01-01                     │
│  优势：URL 不变、语义化版本（如日期）                         │
│  劣势：调试不方便、不直观                                    │
│                                                            │
│  策略三：Content Negotiation（媒体类型）                      │
│    GET /api/users                                           │
│    Header: Accept: application/vnd.company.v2+json          │
│  优势：最RESTful、资源不变、灵活                             │
│  劣势：最复杂、不直观、客户端SDK 处理麻烦                      │
│                                                            │
└────────────────────────────────────────────────────────────┘

企业实践推荐：
- 简单场景（<10个服务）：URL 路径版本（直观易用）
- 中等场景（多客户端兼容）：Header 版本
- 复杂场景（高标准API平台）：Content Negotiation
- 最佳实践：URL 版本 + Header 兜底（渐进迁移）
```

### 1.3 Spring Boot 多版本 API 实现

```java
// ===== 方案1：URL 路径版本（最常用）=====

@RestController
@RequestMapping("/api/v{version}")
public class UserControllerV1 {
    
    @GetMapping("/users/{id}")
    public UserResponse getUserV1(@PathVariable Long id) {
        // V1 返回基础字段
        User user = userService.findById(id);
        return new UserResponse(user.getId(), user.getName());
    }
}

@RestController
@RequestMapping("/api/v{version}")
public class UserControllerV2 {
    
    @GetMapping("/users/{id}")
    public UserResponse getUserV2(@PathVariable Long id) {
        // V2 增加新字段（如头像URL、会员等级）
        User user = userService.findById(id);
        return new UserResponse(
            user.getId(), 
            user.getName(),
            user.getAvatarUrl(),    // 新增
            user.getMemberLevel()   // 新增
        );
    }
}

// Nginx 路由配置
upstream user-v1 {
    server user-service-v1:8080;
}
upstream user-v2 {
    server user-service-v2:8080;
}

server {
    location ~ ^/api/v1/users {
        proxy_pass http://user-v1;
    }
    location ~ ^/api/v2/users {
        proxy_pass http://user-v2;
    }
}

// ===== 方案2：Header 版本（Spring API Versioning）=====

// 配置版本化元数据
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    
    @Bean
    public RequestMappingHandlerMapping versionHandlerMapping() {
        return new CustomRequestMappingHandlerMapping(
            new ApiVersionProperties()
        );
    }
}

@ApiVersion("1.0")
@RestController
@RequestMapping("/users")
public class UserControllerV1 {
    // 匹配 Header: X-API-Version: 1.0
}

@ApiVersion("2.0")
@RestController
@RequestMapping("/users")
public class UserControllerV2 {
    // 匹配 Header: X-API-Version: 2.0
}

// ===== 方案3：接口级别版本（避免重复代码）=====
// 同一 Controller，不同版本的方法

@RestController
@RequestMapping("/users")
public class UserController {
    
    @GetMapping("/{id}")
    @ApiVersion("1.0")
    public UserResponseV1 getUserV1(@PathVariable Long id) {
        User user = userService.findById(id);
        return toV1(user);
    }
    
    @GetMapping("/{id}")
    @ApiVersion("2.0")
    public UserResponseV2 getUserV2(@PathVariable Long id) {
        User user = userService.findById(id);
        return toV2(user);
    }
    
    private UserResponseV1 toV1(User user) {
        return new UserResponseV1(user.getId(), user.getName());
    }
    
    private UserResponseV2 toV2(User user) {
        return new UserResponseV2(
            user.getId(), 
            user.getName(),
            user.getAvatarUrl(),
            user.getMemberLevel()
        );
    }
}
```

### 1.4 版本兼容性策略

```
Breaking Change vs Non-Breaking Change：

Non-Breaking（可安全添加）：
✅ 新增可选字段（客户端忽略即可）
✅ 新增可选 API 端点
✅ 新增可选 Header 参数
✅ 增加字段枚举值

Breaking（需升级版本）：
❌ 删除或重命名字段
❌ 修改字段类型
❌ 修改字段含义
❌ 删除 API 端点
❌ 移除必填参数
❌ 收紧验证规则（宽松→严格）

版本兼容原则：
1. 永远不要删除字段 → 标记 @Deprecated，客户端忽略
2. 永远不要重命名字段 → 新增字段，逐步废弃旧字段
3. 类型变更 → 新增字段，客户端迁移后再删旧字段
4. 验证规则收紧 → 通过 Header 判断客户端版本

示例：用户名字段改名
Step 1: V1 → V2 新增 nickname，保留 name
Step 2: V2 → V3 标记 name 为 deprecated
Step 3: V3 → V4 确保所有客户端已升级，删除 name
```

### 1.5 API 版本管理面试高频问题

**Q: 如何做到 API 不 down 机的情况下完成大版本升级？**

```
答：大版本升级的核心是"新旧版本共存，逐步迁移"：

升级策略：

Phase 1: 双写双读（并行运行）
  ┌─────────────────────────────────────────────┐
  │  新增 v2 接口，旧 v1 继续服务                  │
  │  新功能写两份：v1 写 v1DB，v2 写 v2DB        │
  │  两个版本都读各自的数据                        │
  │  同时运行 2-4 周，观察 v2 使用情况             │
  └─────────────────────────────────────────────┘

Phase 2: 单写双读（数据回流）
  ┌─────────────────────────────────────────────┐
  │  写入只写 v2，读可以选 v1 或 v2               │
  │  定时同步 v2 数据回写 v1DB                    │
  │  让 v1 消费者逐步切换到 v2                    │
  └─────────────────────────────────────────────┘

Phase 3: 灰度放量
  ┌─────────────────────────────────────────────┐
  │  根据用户 ID 哈希逐步切流量                    │
  │  10% → 30% → 50% → 80% → 100%              │
  │  每阶段观察 1-2 天                            │
  └─────────────────────────────────────────────┘

Phase 4: 废弃 V1
  ┌─────────────────────────────────────────────┐
  │  V1 消费者 < 5% 时                          │
  │  发送 Deprecation Header 提醒               │
  │  设定下线日期，提前通知                      │
  │  下线前最后一次灰度放量                      │
  └─────────────────────────────────────────────┘

Istio 灰度路由示例（V1 → V2 灰度）：
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
spec:
  http:
    - route:
        - destination:
            host: user-service
            subset: v1
          weight: 90
        - destination:
            host: user-service
            subset: v2
          weight: 10  # 10% 灰度到 V2
```

---

## 二、配置中心：微服务配置治理

### 2.1 为什么微服务需要配置中心？

> 📌 **基础知识提示**：配置中心的核心概念（集中化管理、热更新、灰度发布、回滚、审计）、Apollo/Nacos 功能对比、Spring Cloud Config 集成等，已在《分布式系统面试八股文（九）——分布式配置中心与配置治理》中详细覆盖。本文聚焦**微服务视角下**的配置中心最佳实践。

```
传统配置 vs 配置中心：

传统配置（配置文件）：
  └── application.yml  →  每个环境一个文件
      ├── application-dev.yml
      ├── application-staging.yml
      └── application-prod.yml
  问题：
  ❌ 改配置要重启服务
  ❌ 多环境不一致（dev改了，prod忘改）
  ❌ 配置分散，无法统一管控
  ❌ 无法追溯谁改了什么

配置中心：
  ┌──────────────────────────────────────────┐
  │           Apollo / Nacos Config          │
  │                                            │
  │  ┌────────┐ ┌────────┐ ┌────────┐        │
  │  │ order  │ │ stock  │ │payment │        │
  │  │ service│ │ service│ │ service│        │
  │  └───┬────┘ └───┬────┘ └───┬────┘        │
  │      │           │           │              │
  │      └───────────┼───────────┘              │
  │                  │                          │
  │         Config Server (Apollo)             │
  │                  │                          │
  │      ┌───────────┼───────────┐             │
  │      │           │           │             │
  │   DEV环境      STAGING      PROD环境       │
  │                                            │
  │  ✅ 配置热更新（不改代码，不重启）          │
  │  ✅ 环境隔离（dev/staging/prod分离）        │
  │  ✅ 权限管控（谁可以改什么环境）            │
  │  ✅ 变更审计（改了什么、什么时候改、谁改的）│
  │  ✅ 版本回滚（一键回滚到上一版本）         │
  └──────────────────────────────────────────┘
```

### 2.2 Apollo 微服务集成实战

```java
// ===== Spring Boot 集成 Apollo =====
// pom.xml
<dependency>
    <groupId>com.ctrip.framework.apollo</groupId>
    <artifactId>apollo-client</artifactId>
    <version>2.2.0</version>
</dependency>

// application.yml
apollo:
  bootstrap:
    enabled: true   # 启动时连接 Apollo
    namespaces: application,redis,mq  # 多 namespace
  config:
    cluster: SHAOYUAN  # 集群配置（机房/区域）
    # 最关键的配置！
    # Apollo APP ID 必须与 portal 中创建的应用一致
    app-id: ${APP_ID:order-service}
    # Apollo Config Server 地址
    meta-server: ${APOLLO_META:http://apollo-config:8080}

# ===== 注解方式获取配置 =====
@Configuration
@EnableApolloConfig
public class ApolloConfig {
}

@Service
public class OrderService {
    
    // 方式1：注解注入（推荐）
    @ApolloConfig
    private Config config;  // application namespace
    
    @ApolloConfig("redis")  // 指定 namespace
    private Config redisConfig;
    
    public void createOrder() {
        // 读取配置
        String value = config.getProperty("order.timeout", "30");
        int timeout = Integer.parseInt(value);
        
        // 配置变更监听
        config.addChangeListener(changeEvent -> {
            log.info("配置变更: {}", changeEvent.getNamespace());
            for (String key : changeEvent.changedKeys()) {
                log.info("  {}: {} -> {}", 
                    key,
                    changeEvent.getChange(key).getOldValue(),
                    changeEvent.getChange(key).getNewValue()
                );
            }
        });
    }
    
    // 方式2：配置注入 POJO
    // @ApolloConfigProperties(prefix = "order", 
    //    names = {"order.timeout", "order.max-items"})
    // 自动将 order.timeout 注入到 OrderProperties.timeout
    
    // 方式3：XML 占位符（与 Spring 整合）
    // @Value("${order.timeout:30}")
    // private int orderTimeout;
}

// ===== 配置类 + 热更新 =====
@ConfigurationProperties(prefix = "ecommerce.order")
@Component
public class OrderProperties {
    
    private int timeoutMinutes = 30;
    private int maxItemsPerOrder = 100;
    private RateLimitConfig rateLimit = new RateLimitConfig();
    
    // Apollo 配置变更自动刷新
    @ApolloConfigChangeListener
    public void onConfigChange(ConfigChangeEvent event) {
        // 重新绑定配置
        binder.bind(Prefix + ".order", 
            PropertySourcesConstants.APOLLO_PROPERTY_SOURCE_NAME);
        log.info("Order 配置已更新: {}", event);
    }
    
    // Getter/Setter...
}

// ===== Apollo 多环境隔离实战 =====
// 场景：不同环境连接不同的数据库

// DEV 环境：Apollo Portal 配置
// application-dev.yml → spring.datasource.url: jdbc:mysql://dev-mysql:3306
// application-staging.yml → spring.datasource.url: jdbc:mysql://staging-mysql:3306
// application-prod.yml → spring.datasource.url: jdbc:mysql://prod-mysql:3306

// Apollo 集群配置
// 默认集群 default
// 北京机房集群 beijing
// 上海机房集群 shanghai

// 服务启动时指定集群
// java -Dapollo.cluster=beijing -jar order-service.jar

// 优先级：机房集群 > 默认集群
// 如果 beijing 集群没有配置，会 fallback 到 default 集群
```

### 2.3 配置热更新：生产环境不重启改配置

```
配置热更新三大场景：

场景1：业务参数调整（无需重启）
  - 活动开关（是否开启秒杀）
  - 限流阈值（QPS 从 1000 → 2000）
  - 熔断阈值（错误率 50% → 60%）
  
场景2：连接池调整（需要应用配合）
  - Redis 连接池大小
  - 数据库连接池大小
  - 需要应用监听配置变更，重新初始化连接池

场景3：应用级别配置（必须重启）
  - JVM 参数（Xmx/Xms）
  - 线程池核心参数
  - 数据库用户名密码

配置热更新实现：
┌──────────────────────────────────────────────────────────┐
│  Apollo 配置变更 → Spring PropertySource 刷新           │
│                    ↓                                     │
│  @ApolloConfigChangeListener 感知变更                   │
│                    ↓                                     │
│  更新 @ConfigurationProperties Bean                     │
│                    ↓                                     │
│  应用代码读取新值（下次使用时生效）                        │
│                                                          │
│  注意事项：                                              │
│  ⚠️ Bean 必须是 prototype 作用域，每次获取新实例         │
│  ⚠️ 静态字段无法热更新                                   │
│  ⚠️ 敏感配置（密码）建议加密存储                         │
└──────────────────────────────────────────────────────────┘
```

```java
// ===== 热更新：限流配置示例 =====

@Configuration
public class RateLimitConfig {
    
    private volatile int maxRequestsPerSecond = 1000;
    private volatile int maxConcurrentRequests = 500;
    
    @ApolloConfigChangeListener(interestedKeyPrefixes = {"rate-limit."})
    public void onRateLimitChange(ConfigChangeEvent event) {
        for (String key : event.changedKeys()) {
            if ("rate-limit.max-requests-per-second".equals(key)) {
                this.maxRequestsPerSecond = 
                    Integer.parseInt(event.getChange(key).getNewValue());
            }
            if ("rate-limit.max-concurrent-requests".equals(key)) {
                this.maxConcurrentRequests = 
                    Integer.parseInt(event.getChange(key).getNewValue());
            }
        }
        log.info("限流配置已更新: QPS={}, 并发={}", 
            maxRequestsPerSecond, maxConcurrentRequests);
    }
}

// 限流器使用最新配置
public class RateLimiter {
    
    private final RateLimitConfig config;
    private volatile RateLimiter instance; // 每次获取最新配置
    
    public boolean tryAcquire(String key) {
        // 读取热更新后的配置
        int limit = config.getMaxRequestsPerSecond();
        // ... 限流逻辑
        return true;
    }
}
```

### 2.4 配置中心面试高频问题

**Q: 配置中心挂了怎么办？应用能否正常启动？**

```
答：这是生产级别的重要问题，需要从两个方面考虑：

1. 启动时配置中心挂了：
   
   方案1：本地缓存降级
   - Apollo 客户端启动时会拉取配置并缓存在本地
   - meta-server 配置：
     apollo.cache.dir=/opt/data/apollo-config-cache
   - 服务启动时先读本地缓存 → 能启动，但用的是旧配置
   
   方案2：启动参数默认值
   - @Value("${order.timeout:30}")  // 冒号后是默认值
   - 如果 Apollo 不可用，使用默认值 30
   
   方案3：本地配置文件兜底
   - application-local.yml 作为本地配置
   - Apollo 配置优先级高于本地配置

2. 运行中配置中心挂了：
   
   - 已经启动的服务不依赖配置中心继续运行
   - 配置中心恢复后自动同步最新配置
   - 热更新功能在配置中心恢复后自动生效

生产最佳实践：
✅ 配置中心高可用部署（至少3节点）
✅ 本地缓存文件（防止配置中心不可用时丢配置）
✅ 启动参数默认值兜底
✅ 配置变更监控告警（配置中心挂了要告警）
✅ 配置回滚能力（一键回滚）
```

---

## 三、服务网格进阶：流量管理与安全

### 3.1 高级流量管理：渐进式灰度

```
灰度发布的演进路径：

V1.0 简单灰度（按比例）：
  ┌──────────────────────────────────────────────────┐
  │  100% 用户                                            │
  │    │                                                 │
  │  ┌─┴──────────────────────┐                        │
  │  │    10% → V2 版本      │                        │
  │  │    90% → V1 版本      │                        │
  │  └────────────────────────┘                        │
  │  缺点：无法按用户特征区分                            │
  └──────────────────────────────────────────────────┘

V2.0 特征灰度（按用户群）：
  ┌──────────────────────────────────────────────────┐
  │  Header: X-User-Type: VIP → V2                   │
  │  Header: X-User-Type: 普通 → V1                   │
  │                                                      │
  │  Header: X-Canary: true → V2                      │
  │  其他 → V1                                         │
  │                                                      │
  │  优点：VIP用户优先体验新版本                         │
  └──────────────────────────────────────────────────┘

V3.0 金丝雀 + 监控（数据驱动灰度）：
  ┌──────────────────────────────────────────────────┐
  │                                                      │
  │  灰度10% → 监控P99延迟、错误率                      │
  │    ├── 指标正常 → 扩量到30%                        │
  │    ├── 指标恶化 → 回滚到0%                         │
  │    └── 指标稳定 → 继续扩量 → 50% → 100%            │
  │                                                      │
  │  Prometheus 告警规则：                               │
  │  - order-service-v2 错误率 > 1% → 自动回滚         │
  │  - order-service-v2 P99延迟 > 500ms → 暂停灰度     │
  │                                                      │
  └──────────────────────────────────────────────────┘

V4.0 流量镜像（Shadow Mode）：
  ┌──────────────────────────────────────────────────┐
  │                                                      │
  │  100% 流量 → V1                                    │
  │    + 复制10% → V2（镜像，不影响用户）               │
  │                                                      │
  │  V2 的响应被丢弃，不返回给用户                       │
  │  V2 的指标被采集和分析                              │
  │                                                      │
  │  优点：生产环境验证新版本，不影响用户                │
  └──────────────────────────────────────────────────┘
```

### 3.2 Istio 灰度发布完整配置

```yaml
# ===== Istio 灰度发布完整配置 =====

# Step 1: DestinationRule 定义版本子集
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: order-service
spec:
  host: order-service
  subsets:
    - name: v1       # 稳定版本
      labels:
        version: v1.5.0
    - name: v2       # 灰度版本
      labels:
        version: v1.6.0
    - name: stable    # 金丝雀
      labels:
        version: v1.6.0-beta.1

---
# Step 2: VirtualService 路由规则

# 基础路由（无灰度时100%走V1）
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-service-default
spec:
  hosts:
    - order-service
  http:
    - route:
        - destination:
            host: order-service
            subset: v1
          weight: 100

---
# 灰度V2版本（10%流量）
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-service-canary
spec:
  hosts:
    - order-service
  http:
    # 规则1：VIP用户走V2
    - match:
        - headers:
            x-user-type:
              exact: vip
      route:
        - destination:
            host: order-service
            subset: v2
          weight: 100
    
    # 规则2：测试流量走V2
    - match:
        - headers:
            x-canary:
              exact: "true"
      route:
        - destination:
            host: order-service
            subset: v2
          weight: 100
    
    # 规则3：按权重分流（10% V2）
    - route:
        - destination:
            host: order-service
            subset: v1
          weight: 90
        - destination:
            host: order-service
            subset: v2
          weight: 10

---
# Step 3: 流量镜像（Shadow Mode）
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-service-shadow
spec:
  hosts:
    - order-service
  http:
    - route:
        - destination:
            host: order-service
            subset: v1
          weight: 100
      # 流量镜像配置
      mirror:
        host: order-service
        subset: v2
      mirrorPercentage:
        value: 10.0  # 10% 流量镜像到 V2
      # 镜像流量的响应被丢弃，不返回给客户端
```

### 3.3 A/B 测试与服务发现联动

```
微服务场景下的 A/B 测试架构：

┌─────────────────────────────────────────────────────────┐
│                  A/B 测试完整链路                         │
│                                                          │
│  用户请求                                                 │
│     │                                                   │
│     ▼                                                   │
│  ┌──────────────┐                                       │
│  │ API Gateway  │                                       │
│  │ 解析 Cookie  │ → 提取 user_id                        │
│  │ 或 Header    │                                       │
│  └──────┬───────┘                                       │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐                                       │
│  │  A/B 决策引擎 │  ← user_id % 100 → 落在哪个桶        │
│  │              │                                       │
│  │  Bucket A: 0-49 (50%)                                │
│  │  Bucket B: 50-99 (50%)                              │
│  └──────┬───────┘                                       │
│         │                                                │
│         ├─────── Bucket A ──→ Service V1                │
│         │                                                │
│         └─────── Bucket B ──→ Service V2                │
│                                                   │
│  关键指标采集：                                         │
│  - V1: 转化率 3.2%, 平均订单金额 ¥128                   │
│  - V2: 转化率 3.8%, 平均订单金额 ¥142  ← V2更好！       │
└─────────────────────────────────────────────────────────┘

Gateway A/B 路由实现：
@Configuration
public class AbTestingConfig {
    
    @Bean
    public GlobalFilter abTestingFilter() {
        return (exchange, chain) -> {
            // 获取用户标识（优先用登录用户ID，未登录用SessionID）
            String userId = getUserId(exchange);
            
            // 计算用户落在哪个桶
            int bucket = Math.abs(userId.hashCode() % 100);
            
            // 决定路由到哪个版本
            String targetVersion = bucket < 50 ? "v1" : "v2";
            
            // 在请求头中传递版本信息
            ServerHttpRequest mutated = exchange.getRequest().mutate()
                .header("X-Service-Version", targetVersion)
                .header("X-Ab-Bucket", String.valueOf(bucket))
                .build();
            
            return chain.filter(exchange.mutate().request(mutated).build());
        };
    }
}

// Istio 根据 Header 路由
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: order-service-ab
spec:
  http:
    - match:
        - headers:
            x-service-version:
              exact: v2
      route:
        - destination:
            host: order-service
            subset: v2
    - route:
        - destination:
            host: order-service
            subset: v1
```

### 3.4 服务网格安全：mTLS 与零信任

```yaml
# ===== Istio 零信任安全配置 =====

# 1. PeerAuthentication：强制 mTLS
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: production
spec:
  mtls:
    mode: STRICT  # 强制所有流量使用 mTLS，禁止明文

---
# 2. AuthorizationPolicy：默认拒绝，按需放行
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  # 默认拒绝所有
  {}  

---
# 3. 网关允许公网访问
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: allow-ingress
  namespace: production
spec:
  selector:
    matchLabels:
      app: istio-ingressgateway
  action: ALLOW
  rules:
    - to:
        - operation:
            ports: ["80", "443"]

---
# 4. 内部服务间最小权限
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: order-service-access
  namespace: production
spec:
  selector:
    matchLabels:
      app: order-service
  action: ALLOW
  rules:
    # 只允许 gateway 调用
    - from:
        - source:
            principals: ["cluster.local/ns/production/sa/istio-ingressgateway"]
      to:
        - operation:
            methods: ["GET", "POST"]
            paths: ["/api/orders/*"]
    # 只允许内部服务调用
    - from:
        - source:
            namespaces: ["production"]
      to:
        - operation:
            methods: ["GET", "POST", "PUT", "DELETE"]
            paths: ["/internal/*"]

# 5. JWT 认证（保护外部 API）
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata:
  name: jwt-auth
  namespace: production
spec:
  selector:
    matchLabels:
      app: order-service
  jwtRules:
    - issuer: "company.com"
      audiences:
        - "order-service"
      forwardOriginalToken: true
      # 从 Authorization Header 提取 JWT
      # 验证签名、过期时间、Issuer
      # 验证通过后，将 claims 注入到 request.headers
```

---

## 四、微服务网关高级特性

### 4.1 Spring Cloud Gateway 完整路由配置

```yaml
# application.yml
spring:
  cloud:
    gateway:
      # 全局默认过滤器
      default-filters:
        - name: RequestSize
          args:
            maxSize: 10MB
        - name: Retry
          args:
            retries: 3
            methods: GET
            exceptions: IOException, TimeoutException
        - StripPrefix=1  # 去掉第一层路径
      
      # 路由配置
      routes:
        # ===== 订单服务 =====
        - id: order-service
          uri: http://order-service:8080
          predicates:
            - Path=/api/orders/**
            - Method=GET,POST,PUT,DELETE
            # 请求时间范围（如促销时间段）
            - After=2026-07-09T00:00:00+08:00[Asia/Shanghai]
          filters:
            # 路径重写：/api/orders/123 → /orders/123
            - RewritePath=/api(?<segment>/?.*), $\{segment}
            # 请求限流（Redis + Lua）
            - name: RequestRateLimiter
              args:
                redis-rate-limiter.replenishRate: 1000
                redis-rate-limiter.burstCapacity: 2000
                redis-rate-limiter.requestedTokens: 1
            # 重试配置
            - name: Retry
              args:
                retries: 3
                statuses: BAD_GATEWAY, SERVICE_UNAVAILABLE
                methods: GET
                backoff:
                  firstBackoff: 100ms
                  maxBackoff: 500ms
                  factor: 2
            # 添加请求头
            - AddRequestHeader=X-Gateway, order-gateway
            # 降级响应（服务不可用时）
            - name: CircuitBreaker
              args:
                name: orderCircuitBreaker
                fallbackUri: forward:/fallback/order

        # ===== 商品服务（支持 websocket）=====
        - id: product-service
          uri: http://product-service:8080
          predicates:
            - Path=/api/products/**
          filters:
            - RewritePath=/api(?<segment>/?.*), $\{segment}
        
        # ===== 静态资源（CDN 回源）=====
        - id: static-resources
          uri: https://cdn.example.com
          predicates:
            - Path=/static/**
        
        # ===== 登录页（不需要认证）=====
        - id: auth-service
          uri: http://auth-service:8080
          predicates:
            - Path=/api/auth/**
        
        # ===== SockJS（WebSocket）=====
        - id: ws-service
          uri: http://ws-service:8080
          predicates:
            - Path=/ws/**
          filters:
            - SetPath=/

---
# 全局限流 Redis Lua 脚本
# resources/lua/rateLimit.lua
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local current = tonumber(redis.call('get', key) or '0')

if current + 1 > limit then
    return 0  -- 拒绝
else
    redis.call('incr', key)
    if current == 0 then
        redis.call('expire', key, window)
    end
    return 1  -- 放行
end
```

### 4.2 Gateway 全局过滤器：认证与鉴权

```java
// ===== 全局认证过滤器 =====
@Component
@Order(-100)  // 优先执行
public class AuthenticationFilter implements GlobalFilter {
    
    private final JwtService jwtService;
    private final AntPathMatcher pathMatcher = new AntPathMatcher();
    
    // 不需要认证的路径
    private static final List<String> WHITE_LIST = Arrays.asList(
        "/api/auth/**",
        "/api/health",
        "/actuator/health"
    );
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getPath().value();
        
        // 白名单跳过认证
        if (isWhiteList(path)) {
            return chain.filter(exchange);
        }
        
        // 获取 Token
        String token = extractToken(exchange.getRequest());
        if (token == null) {
            return unauthorized(exchange, "Missing token");
        }
        
        // 验证 Token
        try {
            JwtClaims claims = jwtService.validate(token);
            
            // 注入用户信息到请求属性
            ServerHttpRequest mutated = exchange.getRequest().mutate()
                .header("X-User-Id", claims.getUserId())
                .header("X-User-Type", claims.getUserType())
                .header("X-User-Roles", String.join(",", claims.getRoles()))
                .build();
            
            return chain.filter(exchange.mutate().request(mutated).build());
            
        } catch (ExpiredTokenException e) {
            return unauthorized(exchange, "Token expired");
        } catch (InvalidTokenException e) {
            return unauthorized(exchange, "Invalid token");
        }
    }
    
    // ===== 权限校验过滤器 =====
    @Component
    @Order(-99)
    public class AuthorizationFilter implements GlobalFilter {
        
        @Override
        public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
            String path = exchange.getRequest().getPath().value();
            String method = exchange.getRequest().getMethod().name();
            String userId = exchange.getRequest().getHeaders().getFirst("X-User-Id");
            
            // 权限映射（实际应从数据库/配置中心读取）
            String requiredRole = getRequiredRole(path, method);
            
            if (requiredRole != null) {
                String userRoles = exchange.getRequest().getHeaders()
                    .getFirst("X-User-Roles");
                
                if (!hasRole(userRoles, requiredRole)) {
                    return forbidden(exchange, "Insufficient permission");
                }
            }
            
            return chain.filter(exchange);
        }
    }
    
    private Mono<Void> unauthorized(ServerWebExchange exchange, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.UNAUTHORIZED);
        response.getHeaders().add("Content-Type", "application/json");
        String body = String.format("{\"code\":401,\"message\":\"%s\"}", message);
        return response.writeWith(Mono.just(response.bufferFactory().wrap(body.getBytes())));
    }
}
```

### 4.3 请求缓存与聚合

```java
// ===== 请求缓存过滤器 =====
// 场景：热点数据（商品详情）缓存到 Redis，减少后端压力

@Component
@Order(50)
public class CacheFilter implements GlobalFilter {
    
    private final RedisTemplate<String, Object> redis;
    private final ObjectMapper objectMapper;
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        // 只有 GET 请求缓存
        if (!"GET".equals(exchange.getRequest().getMethod().name())) {
            return chain.filter(exchange);
        }
        
        String cacheKey = buildCacheKey(exchange);
        
        return Mono.fromCallable(() -> redis.opsForValue().get(cacheKey))
            .flatMap(cached -> {
                if (cached != null) {
                    // 命中缓存，直接返回
                    ServerHttpResponse response = exchange.getResponse();
                    response.getHeaders().add("X-Cache", "HIT");
                    response.getHeaders().add("Content-Type", "application/json");
                    byte[] bytes = objectMapper.writeValueAsBytes(cached);
                    return response.writeWith(Mono.just(
                        response.bufferFactory().wrap(bytes)
                    ));
                }
                // 未命中，继续请求后端
                return chain.filter(exchange)
                    .then(Mono.fromRunnable(() -> {
                        // 后端响应后缓存（异步，不阻塞）
                        // 注意：实际实现需要拦截响应体，这里简化处理
                    }));
            })
            .switchIfEmpty(chain.filter(exchange));
    }
}

// ===== 聚合请求：一次返回多个服务的数据 =====
// 场景：首页需要用户信息 + 订单列表 + 推荐商品

@RestController
@RequestMapping("/api")
public class Gateway聚合Controller {
    
    @GetMapping("/home")
    public Mono<HomeResponse> getHome(
            @RequestHeader("X-User-Id") String userId) {
        
        // 并行调用三个服务
        Mono<User> userMono = userClient.getUser(userId);
        Mono<List<Order>> ordersMono = orderClient.getRecentOrders(userId);
        Mono<List<Product>> recommendMono = productClient.getRecommendations(userId);
        
        // 聚合结果
        return Mono.zip(userMono, ordersMono, recommendMono)
            .map(tuple -> {
                User user = tuple.getT1();
                List<Order> orders = tuple.getT2();
                List<Product> products = tuple.getT3();
                
                return new HomeResponse(user, orders, products);
            })
            .timeout(Duration.ofSeconds(2))
            .onErrorResume(e -> {
                // 降级：部分数据不可用也返回
                return Mono.just(HomeResponse.degraded());
            });
    }
}
```

---

## 五、综合实战：微服务网关 + 配置中心 + 服务网格联动

```
完整架构联动图：

┌────────────────────────────────────────────────────────────────┐
│                     微服务工程化完整架构                         │
│                                                                 │
│  客户端请求                                                      │
│       │                                                        │
│       ▼                                                        │
│  ┌─────────────────────────┐                                   │
│  │     API Gateway          │ ← Spring Cloud Gateway             │
│  │  • 认证/鉴权            │ ← JWT + 权限表                     │
│  │  • 限流/熔断            │ ← Redis + Sentinel                │
│  │  • 路由/重写            │ ← 动态路由配置（Apollo）           │
│  │  • A/B 测试             │ ← Header 路由                      │
│  └───────────┬─────────────┘                                   │
│              │                                                  │
│              │ mTLS 加密                                        │
│              ▼                                                  │
│  ┌─────────────────────────┐                                   │
│  │     Istio Sidecar       │ ← Envoy 代理                       │
│  │  • 流量管理             │ ← 金丝雀/蓝绿/权重分流              │
│  │  • 可观测性             │ ← 指标/日志/追踪自动采集            │
│  │  • 安全策略             │ ← mTLS + AuthorizationPolicy       │
│  │  • 故障注入             │ ← 测试混沌能力                      │
│  └───────────┬─────────────┘                                   │
│              │                                                  │
│              ▼                                                  │
│  ┌─────────────────────────┐                                   │
│  │   Spring Boot Service   │ ← Order Service                   │
│  │                         │                                   │
│  │  配置来自 Apollo         │ ← 热更新、灰度生效                 │
│  │  • order.timeout        │ ← 无需重启                         │
│  │  • rate.limit.qps       │ ← 实时调整                        │
│  │  • feature.xxx          │ ← 功能开关                        │
│  └─────────────────────────┘                                   │
│                                                                 │
└────────────────────────────────────────────────────────────────┘

典型场景演示：

场景1：配置中心灰度生效
1. Apollo 调整 order.timeout: 30 → 60
2. Apollo ConfigChangeEvent 推送通知
3. @ApolloConfigChangeListener 感知变更
4. OrderProperties 对象刷新
5. 新请求使用 timeout=60，无需重启

场景2：服务网格灰度发布
1. 新版本 v1.6.0 部署，label: version=v1.6.0
2. Istio DestinationRule 新增 subset: v1.6.0
3. VirtualService 权重调整：v1.5.0=90%, v1.6.0=10%
4. 10% 用户流量自动路由到新版本
5. Prometheus 监控指标差异
6. 指标正常 → 继续扩量 → 100%

场景3：Gateway + Mesh 联动 A/B
1. Gateway Header: X-User-Type=VIP → 路由到 gateway-v2
2. Istio 接收 Header，自动路由到 service-v2
3. VIP 用户体验新功能
4. 普通用户继续使用 v1
```

---

## 六、面试高频问答

**Q1: API 版本管理和配置中心如何配合灰度发布？**

```
答：这是微服务工程化的经典问题，涉及三层灰度：

第一层：Gateway 灰度（入口层）
- 按用户群/比例路由到不同版本的网关
- 网关决定后续路由策略

第二层：服务网格灰度（流量层）
- Istio VirtualService 按权重/Header 路由
- 流量级别灰度，不影响服务部署

第三层：配置中心灰度（配置层）
- 不同版本服务读取不同配置
- 新功能开关（Feature Flag）

三者配合：
✅ 新版本部署 → 先配置中心灰度（功能开关关闭）
✅ 流量开始灰度 → 配置中心逐步开启功能
✅ 功能稳定 → 配置中心完全开启，旧版本下线
✅ 出现问题 → 一键关闭功能开关，不回滚代码
```

**Q2: 如何设计一套配置变更的安全管控流程？**

```
答：配置变更需要和代码变更一样严格管控：

配置变更审批流：
┌─────────────────────────────────────────────────────┐
│  1. 开发环境 → 任意开发者可改，实时生效              │
│  2. 测试环境 → 开发负责人审批，24小时生效            │
│  3. 预发环境 → 运维/技术负责人审批，48小时生效       │
│  4. 生产环境 → 技术委员会审批 + Change Advisory Board│
│              变更窗口（如周二、周四 10:00-11:00）   │
└─────────────────────────────────────────────────────┘

变更前检查清单：
- [ ] 是否会影响其他服务？
- [ ] 是否有回滚方案？
- [ ] 是否需要通知下游消费者？
- [ ] 是否需要更新文档？
- [ ] 监控告警是否就位？

变更后验证：
- [ ] 健康检查通过
- [ ] 关键指标无异常
- [ ] 变更审计日志已记录

禁止的配置变更：
- ❌ 生产环境直接修改密码
- ❌ 直接删除配置项（应标记废弃）
- ❌ 紧急变更跳过审批（允许，但必须事后补审批）
```

---

## 七、下期预告

经过八篇文章的系统学习，微服务面试八股文系列即将迎来收官之作！**下期将汇总整个微服务系列的知识精华**，以面试综合题的形式串联所有核心概念——从架构设计到服务治理，从数据管理到可观测性，从容器化部署到服务网格，形成完整的微服务知识体系。同时精选 30 道高频微服务综合面试题，帮助你系统化地备战面试，敬请期待！🦐

---

*本系列持续更新中，欢迎关注获取最新文章。*
