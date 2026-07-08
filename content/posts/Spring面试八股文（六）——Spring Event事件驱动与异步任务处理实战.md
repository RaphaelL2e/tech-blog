---
title: "Spring面试八股文（六）——Spring Event事件驱动与异步任务处理实战"
date: 2026-07-08T11:00:00+08:00
draft: false
categories: ["spring"]
tags: ["Spring", "Spring Event", "ApplicationEvent", "EventListener", "Async", "CompletableFuture", "Scheduled", "TaskExecutor", "Spring Retry", "面试", "八股文"]
---

# Spring面试八股文（六）——Spring Event事件驱动与异步任务处理实战

> 🎯 **本文目标**：在前五篇的基础上，深入解析Spring框架中的事件驱动编程模型——ApplicationEvent机制、@EventListener注解、事务事件监听、@Async异步执行原理、TaskExecutor线程池体系、@Scheduled定时任务、Spring Retry重试机制，构建完整的Spring异步与事件处理知识体系。

---

## 一、Spring Event事件驱动模型

### 1.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Spring事件机制的原理？ | ⭐⭐⭐⭐⭐ | 观察者模式 + ApplicationContext事件发布 |
| 2 | @EventListener和ApplicationListener的区别？ | ⭐⭐⭐⭐ | @EventListener注解更灵活，支持SpEL、条件化 |
| 3 | @TransactionalEventListener的作用？ | ⭐⭐⭐⭐⭐ | 事务提交后执行，支持四种绑定阶段 |
| 4 | Spring事件默认是同步还是异步？ | ⭐⭐⭐⭐ | 默认同步，需配合@Async实现异步事件 |
| 5 | Spring事件机制的应用场景？ | ⭐⭐⭐⭐ | 业务解耦、日志审计、消息通知、数据同步 |

### 1.2 事件机制架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    ApplicationContext                             │
│                                                                   │
│  ┌──────────────┐    publishEvent()    ┌──────────────────────┐  │
│  │  Publisher    │ ──────────────────→ │   ApplicationEvent-   │  │
│  │  (业务代码)    │                      │   Multicaster          │  │
│  └──────────────┘                      │   (事件广播器)          │  │
│                                        │                       │  │
│                                        │  SimpleApplication-   │  │
│                                        │  EventMulticaster     │  │
│                                        │        │              │  │
│                                        │   ┌────┴────┐        │  │
│                                        │   │ Listener列表 │    │  │
│                                        │   └────┬────┘        │  │
│                                        └───────┼──────────────┘  │
│                                                │                 │
│                              ┌─────────────────┼─────────────┐   │
│                              │        │        │              │   │
│                           Listener1  Listener2  Listener3    │   │
│                           (@EventListener/@Order控制顺序)      │   │
└─────────────────────────────────────────────────────────────────┘
```

**核心流程**：
1. `ApplicationContext.publishEvent(event)` → 委托给 `ApplicationEventMulticaster`
2. `ApplicationEventMulticaster.multicastEvent()` → 遍历所有注册的 Listener
3. 判断是否异步（通过 `Executor` 是否为 null）
4. 同步/异步调用每个 Listener 的 `onApplicationEvent()` 方法

### 1.3 Spring Event基础使用

```java
// 1. 定义事件 → 继承 ApplicationEvent
@Getter
@ToString
public class OrderCreatedEvent extends ApplicationEvent {
    
    private final Long orderId;
    private final Long userId;
    private final BigDecimal amount;
    private final LocalDateTime createdAt;
    
    public OrderCreatedEvent(Object source, Long orderId, Long userId, 
                             BigDecimal amount) {
        super(source);
        this.orderId = orderId;
        this.userId = userId;
        this.amount = amount;
        this.createdAt = LocalDateTime.now();
    }
}

// 2. 发布事件 → ApplicationEventPublisher
@Service
@Slf4j
public class OrderService {
    
    @Autowired
    private ApplicationEventPublisher publisher;
    
    @Transactional
    public Order createOrder(CreateOrderRequest request) {
        // 1. 创建订单
        Order order = new Order();
        order.setUserId(request.getUserId());
        order.setAmount(request.getAmount());
        order.setStatus(OrderStatus.CREATED);
        orderMapper.insert(order);
        
        // 2. 发布事件（事务提交前）
        publisher.publishEvent(new OrderCreatedEvent(
            this, order.getId(), order.getUserId(), order.getAmount()
        ));
        
        return order;
    }
}

// 3. 监听事件 → @EventListener
@Component
@Slf4j
public class OrderEventListener {
    
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        log.info("收到订单创建事件: {}", event);
        // 发送短信通知用户
        smsService.sendOrderCreatedSms(event.getUserId(), event.getOrderId());
    }
    
    // 支持通过条件过滤
    @EventListener(condition = "#event.amount >= 1000")
    public void handleLargeOrder(OrderCreatedEvent event) {
        log.info("大额订单创建: {}", event.getAmount());
        // 触发风控审核
        riskService.audit(event.getOrderId());
    }
}
```

### 1.4 @TransactionalEventListener：事务事件

这是面试中的**热点考点**，深入解析：

```java
@Component
@Slf4j
public class TransactionalOrderEventListener {
    
    // AFTER_COMMIT：事务提交后执行（默认值）
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void handleOrderAfterCommit(OrderCreatedEvent event) {
        log.info("事务已提交，执行后续操作: {}", event);
        // ✅ 此时数据库已持久化，可以安全地发送MQ/Kafka/执行外部调用
        mqProducer.send(new OrderMessage(event.getOrderId()));
    }
    
    // AFTER_ROLLBACK：事务回滚后执行
    @TransactionalEventListener(phase = TransactionPhase.AFTER_ROLLBACK)
    public void handleOrderAfterRollback(OrderCreatedEvent event) {
        log.warn("订单创建失败，事务已回滚: {}", event);
        // ✅ 记录失败日志、发送告警
        alertService.sendAlert("订单创建失败", event);
    }
    
    // AFTER_COMPLETION：事务完成（提交或回滚）后执行
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMPLETION)
    public void handleOrderAfterCompletion(OrderCreatedEvent event) {
        log.info("订单事务处理完成: {}", event);
        // ✅ 无论成功失败，都清理线程上下文、更新统计
        metricsService.incrementOrderCount();
    }
    
    // BEFORE_COMMIT：事务提交前执行
    @TransactionalEventListener(phase = TransactionPhase.BEFORE_COMMIT)
    public void handleOrderBeforeCommit(OrderCreatedEvent event) {
        log.info("事务即将提交: {}", event);
        // ✅ 在提交前做最后的检查/补充数据
        // ⚠️ 抛出异常会导致事务回滚
        validateOrder(event.getOrderId());
    }

    // fallbackExecution：无事务时也执行
    @TransactionalEventListener(
        phase = TransactionPhase.AFTER_COMMIT,
        fallbackExecution = true  // 当没有事务上下文时仍然执行
    )
    public void handleOrderWithFallback(OrderCreatedEvent event) {
        // 处理逻辑
    }
}
```

**四个事务阶段对比**：

| 阶段 | 枚举值 | 执行时机 | 典型场景 |
|------|--------|---------|---------|
| BEFORE_COMMIT | TransactionPhase.BEFORE_COMMIT | 事务提交前 | 最后校验、补充数据 |
| AFTER_COMMIT | TransactionPhase.AFTER_COMMIT（默认） | 事务提交后 | 发送消息、通知、异步任务 |
| AFTER_ROLLBACK | TransactionPhase.AFTER_ROLLBACK | 事务回滚后 | 失败日志、告警、补偿操作 |
| AFTER_COMPLETION | TransactionPhase.AFTER_COMPLETION | 事务完成（无论成功/失败） | 清理资源、更新统计 |

### 1.5 源码剖析：如何实现事务绑定？

```java
// TransactionalEventListener 底层原理（简化）
public class ApplicationListenerMethodTransactionalAdapter 
        extends ApplicationListenerMethodAdapter {
    
    private final TransactionPhase transactionPhase;
    
    @Override
    public void onApplicationEvent(ApplicationEvent event) {
        // 判断是否需要事务绑定
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            // 注册事务同步回调
            TransactionSynchronizationManager.registerSynchronization(
                new TransactionSynchronizationAdapter() {
                    @Override
                    public void beforeCommit(boolean readOnly) {
                        if (transactionPhase == TransactionPhase.BEFORE_COMMIT) {
                            invoke(event);
                        }
                    }
                    
                    @Override
                    public void afterCommit() {
                        if (transactionPhase == TransactionPhase.AFTER_COMMIT) {
                            invoke(event);
                        }
                    }
                    
                    @Override
                    public void afterCompletion(int status) {
                        if (transactionPhase == TransactionPhase.AFTER_COMPLETION) {
                            invoke(event);
                        }
                    }
                }
            );
        } else if (fallbackExecution) {
            // 无事务时直接执行
            invoke(event);
        }
    }
}
```

**关键点**：
1. `TransactionSynchronizationManager.isSynchronizationActive()` 判断是否有活跃事务
2. 有事务 → 注册 `TransactionSynchronization` 等待对应阶段触发
3. 无事务 + `fallbackExecution=true` → 直接执行
4. 无事务 + `fallbackExecution=false`（默认） → 不执行

---

## 二、@Async 异步编程

### 2.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | @Async的原理是什么？ | ⭐⭐⭐⭐⭐ | AOP代理 + TaskExecutor异步提交 |
| 2 | @Async失效的常见原因？ | ⭐⭐⭐⭐⭐ | 同类调用、未配置线程池、方法非public、代理问题 |
| 3 | 如何自定义线程池？ | ⭐⭐⭐⭐ | ThreadPoolTaskExecutor配置、@Async指定线程池名 |
| 4 | @Async的方法返回值有哪些？ | ⭐⭐⭐⭐ | void、Future、CompletableFuture |
| 5 | 异步方法中的上下文传递问题？ | ⭐⭐⭐⭐ | ThreadLocal丢失、MDC传递、TransmittableThreadLocal |

### 2.2 @Async 核心原理

```java
// 启用异步支持
@Configuration
@EnableAsync
public class AsyncConfig {
    
    // 自定义线程池
    @Bean("taskExecutor")
    public ThreadPoolTaskExecutor taskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);           // 核心线程数
        executor.setMaxPoolSize(50);            // 最大线程数
        executor.setQueueCapacity(200);         // 队列容量
        executor.setKeepAliveSeconds(60);       // 空闲线程存活时间
        executor.setThreadNamePrefix("async-"); // 线程名前缀
        executor.setRejectedExecutionHandler(   // 拒绝策略
            new ThreadPoolExecutor.CallerRunsPolicy()
        );
        executor.initialize();
        return executor;
    }
    
    // 专门处理IO密集型的线程池
    @Bean("ioTaskExecutor")
    public ThreadPoolTaskExecutor ioTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(20);
        executor.setMaxPoolSize(100);
        executor.setQueueCapacity(500);
        executor.setThreadNamePrefix("io-async-");
        executor.setRejectedExecutionHandler(
            new ThreadPoolExecutor.AbortPolicy() // 直接拒绝并抛异常
        );
        executor.initialize();
        return executor;
    }
}

// 使用异步
@Service
@Slf4j
public class NotificationService {
    
    // 简单异步
    @Async
    public void sendSms(String phone, String content) {
        log.info("异步发送短信: {} -> {}", phone, content);
        // Thread.sleep模拟耗时操作
        Thread.sleep(2000);
        smsApi.send(phone, content);
    }
    
    // 指定线程池的异步
    @Async("ioTaskExecutor")
    public CompletableFuture<String> sendEmail(String email, String content) {
        log.info("异步发送邮件: {}", email);
        boolean success = emailApi.send(email, content);
        return CompletableFuture.completedFuture(
            success ? "邮件发送成功" : "邮件发送失败"
        );
    }
    
    // 批量异步处理
    @Async
    public CompletableFuture<List<User>> batchQueryUser(List<Long> ids) {
        List<User> users = userRepository.findByIdIn(ids);
        return CompletableFuture.completedFuture(users);
    }
}

// 使用CompletableFuture编排
@Service
public class OrderCompletionService {
    
    @Autowired
    private NotificationService notificationService;
    @Autowired
    private InventoryService inventoryService;
    
    public void completeOrder(Order order) {
        // 并行执行多个异步任务
        CompletableFuture<String> emailFuture = 
            notificationService.sendEmail(order.getEmail(), "订单创建成功");
        CompletableFuture<String> smsFuture = 
            CompletableFuture.supplyAsync(() -> {
                notificationService.sendSms(order.getPhone(), "订单创建成功");
                return "短信发送成功";
            });
        CompletableFuture<Void> inventoryFuture = 
            CompletableFuture.runAsync(() -> 
                inventoryService.deduct(order.getProductId(), order.getCount())
            );
        
        // 等待所有任务完成
        CompletableFuture.allOf(emailFuture, smsFuture, inventoryFuture)
            .thenRun(() -> log.info("所有异步任务完成"))
            .exceptionally(e -> {
                log.error("异步任务异常: {}", e.getMessage());
                return null;
            });
    }
}
```

### 2.3 @Async 失效的常见场景及解决方案

```java
@Service
public class AsyncFailService {
    
    // ❌ 场景1：同类方法调用（AOP代理不生效）
    public void doSomething() {
        asyncMethod();  // 直接调用，不会走代理，异步不生效
    }
    
    @Async
    public void asyncMethod() {
        log.info("这不会异步执行");
    }
    
    // ✅ 解决方案1：注入自身代理调用
    @Autowired
    private AsyncFailService self;
    
    public void doSomethingV2() {
        self.asyncMethod();  // 通过代理调用，异步生效
    }
    
    // ✅ 解决方案2：分离到不同Service
    public void doSomethingV3() {
        otherService.asyncMethod();  // 不同Service，代理生效
    }
}

// ❌ 场景2：未启用 @EnableAsync
// 需要在 @Configuration 类上添加 @EnableAsync

// ❌ 场景3：方法不是 public
// @Async 基于 AOP 代理，private/protected 方法无效

// ❌ 场景4：返回值处理错误
// 如果声明为 Future，但忘记 return，会返回 null
```

### 2.4 异步上下文传递

```java
// 问题：异步线程中 ThreadLocal/MDC 会丢失
// 解决方案1：自定义 TaskDecorator
@Configuration
@EnableAsync
public class ContextAwareAsyncConfig {
    
    @Bean("contextAwareExecutor")
    public ThreadPoolTaskExecutor contextAwareExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(10);
        executor.setMaxPoolSize(50);
        executor.setTaskDecorator(new ContextAwareTaskDecorator());
        executor.initialize();
        return executor;
    }
    
    // 自定义TaskDecorator：在任务提交时复制上下文
    static class ContextAwareTaskDecorator implements TaskDecorator {
        @Override
        public Runnable decorate(Runnable runnable) {
            // 1. 获取当前线程的上下文
            Map<String, String> mdcContext = MDC.getCopyOfContextMap();
            RequestAttributes attributes = RequestContextHolder.getRequestAttributes();
            String userId = UserContext.getUserId();
            
            return () -> {
                try {
                    // 2. 将上下文设置到异步线程
                    if (mdcContext != null) MDC.setContextMap(mdcContext);
                    if (attributes != null) {
                        RequestContextHolder.setRequestAttributes(attributes, true);
                    }
                    UserContext.setUserId(userId);
                    
                    // 3. 执行原任务
                    runnable.run();
                } finally {
                    // 4. 清理线程上下文
                    MDC.clear();
                    RequestContextHolder.resetRequestAttributes();
                    UserContext.clear();
                }
            };
        }
    }
}

// 解决方案2：使用 TransmittableThreadLocal（Alibaba TTL）
// <dependency>
//     <groupId>com.alibaba</groupId>
//     <artifactId>transmittable-thread-local</artifactId>
// </dependency>

public class UserContext {
    private static final TransmittableThreadLocal<String> USER_ID = 
        new TransmittableThreadLocal<>();
    
    public static void setUserId(String userId) {
        USER_ID.set(userId);
    }
    
    public static String getUserId() {
        return USER_ID.get();
    }
    
    public static void clear() {
        USER_ID.remove();
    }
}

// 结合线程池使用TTL
@Bean("ttlExecutor")
public Executor ttlExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(10);
    executor.setMaxPoolSize(50);
    // 使用 TtlExecutors 包装
    return TtlExecutors.getTtlExecutor(executor);
}
```

---

## 三、Spring TaskExecutor 线程池体系

### 3.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Spring线程池有哪几种？ | ⭐⭐⭐⭐ | SimpleAsyncTaskExecutor、ThreadPoolTaskExecutor、ConcurrentTaskExecutor |
| 2 | ThreadPoolTaskExecutor的核心参数？ | ⭐⭐⭐⭐⭐ | corePoolSize、maxPoolSize、queueCapacity、rejectedExecutionHandler |
| 3 | 如何选择合适的线程池参数？ | ⭐⭐⭐⭐ | CPU密集 vs IO密集、QPS预估、任务时长 |
| 4 | 拒绝策略有哪些？ | ⭐⭐⭐⭐ | AbortPolicy、CallerRunsPolicy、DiscardPolicy、DiscardOldestPolicy |

### 3.2 Spring线程池类型全景

| 类型 | 特点 | 适用场景 |
|------|------|---------|
| **ThreadPoolTaskExecutor** | 基于ThreadPoolExecutor，配置灵活 | **最常用**，生产环境首选 |
| **SimpleAsyncTaskExecutor** | 每次新建线程，不复用 | **仅用于测试**，生产禁用 |
| **ConcurrentTaskExecutor** | 适配器，包装JDK Executor | 需要Spring抽象时使用 |
| **WorkManagerTaskExecutor** | 基于JCA WorkManager | Java EE容器环境 |

### 3.3 线程池参数调优指南

```java
@Bean("optimizedExecutor")
public ThreadPoolTaskExecutor optimizedExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    
    // 1. 核心线程数：根据业务类型设置
    int cpuCores = Runtime.getRuntime().availableProcessors();
    // CPU密集型：corePoolSize = CPU核心数 + 1
    // IO密集型：corePoolSize = CPU核心数 * 2（或更大）
    executor.setCorePoolSize(cpuCores * 2);
    
    // 2. 最大线程数：考虑系统资源上限
    executor.setMaxPoolSize(cpuCores * 4);
    
    // 3. 队列容量：平衡延迟和吞吐
    // QPS=1000, 任务耗时=100ms → 并发=100，队列至少200
    executor.setQueueCapacity(500);
    
    // 4. 拒绝策略选择
    // AbortPolicy：抛异常（需要人工介入的场景）
    // CallerRunsPolicy：调用者线程执行（降级场景）
    // DiscardPolicy：静默丢弃（日志/监控等可丢弃场景）
    executor.setRejectedExecutionHandler(
        new ThreadPoolExecutor.CallerRunsPolicy()
    );
    
    // 5. 优雅关闭
    executor.setWaitForTasksToCompleteOnShutdown(true);
    executor.setAwaitTerminationSeconds(60);
    
    executor.initialize();
    return executor;
}
```

---

## 四、@Scheduled 定时任务

### 4.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | @Scheduled支持哪些表达式？ | ⭐⭐⭐⭐ | cron、fixedDelay、fixedRate、initialDelay |
| 2 | fixedDelay和fixedRate的区别？ | ⭐⭐⭐⭐⭐ | fixedDelay=任务完成间隔，fixedRate=任务开始间隔 |
| 3 | 单机定时任务有什么局限性？ | ⭐⭐⭐⭐ | 不支持集群、无法动态暂停、单点故障 |
| 4 | 如何实现分布式定时任务？ | ⭐⭐⭐⭐ | XXL-Job、Elastic-Job、ShedLock |

### 4.2 @Scheduled基础使用

```java
@Component
@Slf4j
public class ScheduledTasks {
    
    // 1. CRON表达式（最常用）
    @Scheduled(cron = "0 0 2 * * ?")  // 每天凌晨2点
    public void dailyReport() {
        log.info("生成日报");
    }
    
    // 2. fixedDelay：每次执行完固定间隔后执行
    @Scheduled(fixedDelay = 60000)  // 每次执行完60秒后下次执行
    public void syncData() {
        log.info("同步数据");
        // 任务执行时间不影响间隔
    }
    
    // 3. fixedRate：固定频率执行
    @Scheduled(fixedRate = 60000)  // 每60秒执行一次
    public void cleanCache() {
        log.info("清理缓存");
        // 如果任务耗时超过60秒，会等当前任务完成后立即执行
    }
    
    // 4. initialDelay：首次延迟
    @Scheduled(
        initialDelay = 30000,      // 启动后30秒执行首次
        fixedDelay = 600000         // 之后每10分钟执行
    )
    public void startDelayTask() {
        log.info("延迟启动任务");
    }
}

// 自定义线程池（避免共用默认单线程池）
@Configuration
@EnableScheduling
public class SchedulingConfig implements SchedulingConfigurer {
    
    @Override
    public void configureTasks(ScheduledTaskRegistrar taskRegistrar) {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(5);    // 并发执行线程数
        scheduler.setThreadNamePrefix("scheduled-");
        scheduler.initialize();
        
        taskRegistrar.setTaskScheduler(scheduler);
    }
}
```

### 4.3 fixedDelay vs fixedRate 图解

```
fixedDelay = 60s（任务耗时30s）
|--任务(30s)--|--等待60s--|--任务(30s)--|--等待60s--|--任务(30s)--|
                    ↑ 每次间隔一致

fixedRate = 60s（任务耗时30s）
|---任务(30s)---|---任务(30s)---|---任务(30s)---|
   ↑每个整60s时刻启动                             间隔固定

fixedRate = 60s（任务耗时90s，超过间隔）
|------任务(90s)------|立即启动|------任务(90s)------|立即启动|
                       ↑ 任务耗时超过间隔，不会并发，排队执行
```

### 4.4 分布式定时任务方案

> **注意**：分布式定时任务的完整技术方案（XXL-Job、Elastic-Job、Quartz集群等）请参考《分布式系统面试八股文（七）——分布式定时任务与工作流引擎》。这里补充Spring层面的轻量级分布式锁方案 **ShedLock**：

```java
// ShedLock：基于数据库/Redis的分布式锁，保证同一时刻只有一个实例执行
// 1. 添加依赖
<dependency>
    <groupId>net.javacrumbs.shedlock</groupId>
    <artifactId>shedlock-spring</artifactId>
    <version>5.10.0</version>
</dependency>
<dependency>
    <groupId>net.javacrumbs.shedlock</groupId>
    <artifactId>shedlock-provider-jdbc-template</artifactId>
    <version>5.10.0</version>
</dependency>

// 2. 配置
@Configuration
@EnableSchedulerLock(defaultLockAtMostFor = "PT5M")  // 锁默认持有5分钟
public class ShedLockConfig {
    
    @Bean
    public LockProvider lockProvider(DataSource dataSource) {
        return new JdbcTemplateLockProvider(dataSource);
    }
}

// 3. 使用
@Component
public class DistributedTasks {
    
    @Scheduled(cron = "0 0 2 * * ?")
    @SchedulerLock(
        name = "dailyReportTask",           // 锁名称（唯一）
        lockAtMostFor = "PT10M",            // 最长持有时间
        lockAtLeastFor = "PT1M"             // 最短持有时间
    )
    public void dailyReport() {
        log.info("分布式定时任务：生成日报（只有一个实例执行）");
    }
}
```

---

## 五、Spring Retry 重试机制

### 5.1 面试高频问题

| # | 问题 | 重要度 | 核心要点 |
|---|------|--------|---------|
| 1 | Spring Retry的原理？ | ⭐⭐⭐⭐ | AOP + 重试模板（RetryTemplate） |
| 2 | 哪些异常应该重试？ | ⭐⭐⭐⭐ | 瞬时异常（网络超时、连接池满），非业务异常 |
| 3 | 重试策略有哪些？ | ⭐⭐⭐ | 固定间隔、指数退避、随机间隔 |
| 4 | 重试导致幂等性问题怎么处理？ | ⭐⭐⭐⭐ | 唯一约束、幂等Key、分布式锁 |
| 5 | @Retryable和@Async能一起用吗？ | ⭐⭐⭐ | 可以，但要注意线程池隔离 |

### 5.2 核心使用方式

```java
// 1. 启用重试支持
@Configuration
@EnableRetry
public class RetryConfig {
}

// 2. 注解方式使用
@Service
@Slf4j
public class PaymentService {
    
    @Retryable(
        value = {RemoteServiceException.class, TimeoutException.class},
        maxAttempts = 3,                          // 最大重试次数
        backoff = @Backoff(
            delay = 1000,                         // 首次重试延迟1s
            multiplier = 2.0,                     // 每次延迟翻倍
            maxDelay = 10000                      // 最大延迟10s
        ),
        recover = "paymentRecover"                // 降级方法
    )
    public PaymentResult pay(PaymentRequest request) {
        log.info("发起支付请求: {}", request);
        // 调用第三方支付接口
        return remotePaymentClient.pay(request);
    }
    
    // 降级方法（参数必须与重试方法一致，并增加异常参数）
    @Recover
    public PaymentResult paymentRecover(
            RemoteServiceException e, 
            PaymentRequest request) {
        log.error("支付重试3次后仍失败: {}", e.getMessage());
        return PaymentResult.fail("支付服务暂时不可用，请稍后重试");
    }
    
    @Recover
    public PaymentResult paymentRecover(
            TimeoutException e, 
            PaymentRequest request) {
        log.error("支付超时: {}", e.getMessage());
        return PaymentResult.pending("支付处理中，请稍后查询结果");
    }
}

// 3. 模板方式使用（更灵活）
@Service
public class TemplateRetryService {
    
    @Autowired
    private RetryTemplate retryTemplate;
    
    public String callThirdParty() {
        return retryTemplate.execute(context -> {
            log.info("重试次数: {}", context.getRetryCount());
            // 调用第三方接口
            return httpClient.get("https://api.example.com/data");
        }, context -> {
            // 所有重试失败后的回调
            log.error("调用第三方接口最终失败");
            return "fallback_value";
        });
    }
}

// 4. 自定义RetryTemplate
@Configuration
public class RetryTemplateConfig {
    
    @Bean
    public RetryTemplate retryTemplate() {
        RetryTemplate retryTemplate = new RetryTemplate();
        
        // 重试策略：最多重试3次
        SimpleRetryPolicy retryPolicy = new SimpleRetryPolicy(
            3,
            Collections.singletonMap(RemoteServiceException.class, true),
            false  // retryableClassifier为false表示使用"白名单"模式
        );
        retryTemplate.setRetryPolicy(retryPolicy);
        
        // 退避策略：指数退避（1s, 2s, 4s...）
        ExponentialBackOffPolicy backOffPolicy = new ExponentialBackOffPolicy();
        backOffPolicy.setInitialInterval(1000);   // 初始间隔1s
        backOffPolicy.setMultiplier(2.0);         // 翻倍因子
        backOffPolicy.setMaxInterval(10000);      // 最大间隔10s
        retryTemplate.setBackOffPolicy(backOffPolicy);
        
        return retryTemplate;
    }
}
```

### 5.3 重试的幂等性处理

```java
@Service
public class IdempotentPaymentService {
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    @Retryable(
        value = RemoteServiceException.class,
        maxAttempts = 3,
        backoff = @Backoff(delay = 1000, multiplier = 2.0)
    )
    public void deductBalance(String bizId, Long userId, BigDecimal amount) {
        // 幂等性保证：使用唯一业务ID做分布式锁
        String lockKey = "payment:deduct:" + bizId;
        
        // 尝试获取锁（如果已处理过，直接返回）
        if (!redisTemplate.opsForValue()
                .setIfAbsent(lockKey, "processing", 5, TimeUnit.MINUTES)) {
            log.info("该支付请求已处理: {}", bizId);
            return;  // 幂等返回，不重复执行
        }
        
        try {
            // 执行扣款
            remotePaymentService.deduct(bizId, userId, amount);
        } catch (Exception e) {
            // 失败时释放锁，允许重试
            redisTemplate.delete(lockKey);
            throw e;
        }
    }
}
```

---

## 六、实战案例：订单创建全链路

综合运用事件驱动、异步处理和重试机制：

```java
@Service
@Slf4j
public class OrderCreateOrchestrator {
    
    @Autowired
    private OrderRepository orderRepository;
    @Autowired
    private ApplicationEventPublisher eventPublisher;
    @Autowired
    private InventoryService inventoryService;
    @Autowired
    private CouponService couponService;
    
    @Transactional
    public OrderResult createOrder(CreateOrderRequest request) {
        // 1. 参数校验 & 业务校验
        validateRequest(request);
        
        // 2. 创建订单主记录
        Order order = new Order();
        order.setOrderNo(generateOrderNo());
        order.setUserId(request.getUserId());
        order.setStatus(OrderStatus.CREATED);
        order.setAmount(request.getAmount());
        orderRepository.save(order);
        
        // 3. 扣减库存（同步，需要保证一致性）
        inventoryService.deduct(request.getItems());
        
        // 4. 使用优惠券（同步）
        if (request.getCouponId() != null) {
            couponService.use(request.getCouponId());
        }
        
        // 5. 发布事件 → 后续步骤异步执行
        eventPublisher.publishEvent(new OrderCreatedEvent(
            this, order.getId(), request.getUserId(), request.getAmount()
        ));
        
        return OrderResult.success(order.getOrderNo());
    }
}

// 事件处理器 → 异步处理后续步骤
@Component
@Slf4j
public class OrderCreatedProcessor {
    
    @Autowired
    private PointService pointService;
    @Autowired
    private NotificationService notificationService;
    @Autowired
    private RecommendationService recommendationService;
    
    @TransactionalEventListener(
        phase = TransactionPhase.AFTER_COMMIT,  // 事务提交后执行
        fallbackExecution = false
    )
    public void handleOrderCreated(OrderCreatedEvent event) {
        log.info("订单事务已提交，启动后续处理: orderId={}", event.getOrderId());
        
        // 并行处理多个后续任务
        CompletableFuture<Void> pointFuture = CompletableFuture.runAsync(() -> 
            pointService.grantPoints(event.getUserId(), event.getAmount())
        );
        
        CompletableFuture<Void> notifyFuture = CompletableFuture.runAsync(() ->
            notificationService.sendOrderConfirmAsync(event.getUserId(), event.getOrderId())
        );
        
        CompletableFuture<Void> recommendFuture = CompletableFuture.runAsync(() ->
            recommendationService.updateUserPreference(event.getUserId(), event.getAmount())
        );
        
        // 等待所有任务完成
        CompletableFuture.allOf(pointFuture, notifyFuture, recommendFuture)
            .orTimeout(10, TimeUnit.SECONDS)
            .exceptionally(e -> {
                log.error("订单后续处理失败: {}", e.getMessage());
                return null;
            });
    }
}
```

---

## 七、总结

| 组件 | 核心价值 | 关键注意点 |
|------|---------|-----------|
| **Spring Event** | 业务解耦，模块间松耦合 | 默认同步执行，注意性能；@TransactionalEventListener是精髓 |
| **@Async** | 异步非阻塞，提升吞吐 | 同类调用失效是头号陷阱；注意上下文传递 |
| **TaskExecutor** | 统一线程池管理 | 避免使用默认线程池；根据业务分池配置 |
| **@Scheduled** | 轻量级定时任务 | 默认单线程，多任务需自定义线程池 |
| **Spring Retry** | 优雅处理瞬时故障 | 重试必须保证幂等；降级兜底方案不可少 |

**面试一句话总结套路**：
- **事件驱动**："Spring Event基于观察者模式，通过ApplicationEventMulticaster广播事件。我的项目里用@TransactionalEventListener在订单提交后异步发送消息、赠送积分，实现了核心流程与非核心流程的解耦。"
- **异步编程**："@Async通过AOP将方法提交到TaskExecutor异步执行。生产上我会为CPU密集和IO密集任务分别配置线程池，并通过TaskDecorator传递MDC/ThreadLocal上下文。"
- **重试机制**："Spring Retry是基于AOP的重试框架，我主要用它处理第三方接口的超时问题。关键是要保证幂等，我在业务层用分布式锁+唯一Key来防止重复执行。"

> 🎯 **下期预告**：Spring面试八股文（七）——Spring Cache缓存抽象与Redis集成实战，将深入解析@Cacheable/@CacheEvict注解原理、多级缓存策略（本地Caffeine+远程Redis）、缓存穿透/击穿/雪崩的Spring层解决方案等核心知识。
