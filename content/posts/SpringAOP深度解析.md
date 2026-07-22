---
title: Spring AOP 深度解析
date: 2026-05-11 16:30:00+08:00
updated: '2026-05-11T16:30:00+08:00'
description: 面试高频问题：什么是 AOP？JDK 动态代理和 CGLIB 的区别？@Transactional 原理？ AOP（Aspect-Oriented Programming，面向切面编程）是 Spring 框架的另一大核心。它通过将横切关注点（如日志、事务、安全）与业务逻辑分离，提高了代码的模块化。本。
topic: java-spring
level: intermediate
status: maintained
tags:
- Spring
- aop
- proxy
- transaction
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：什么是 AOP？JDK 动态代理和 CGLIB 的区别？@Transactional 原理？

## 引言

AOP（Aspect-Oriented Programming，面向切面编程）是 Spring 框架的另一大核心。它通过将横切关注点（如日志、事务、安全）与业务逻辑分离，提高了代码的模块化。本文将从代理机制到事务管理，全面解析 Spring AOP。

## 一、AOP 核心概念

### 1.1 什么是 AOP？

**AOP**：面向切面编程，将横切关注点与业务逻辑分离。

```
传统方式（代码冗余）：
┌─────────────────────────────┐
│ 业务逻辑                        │
│  ├─ 权限检查                  │
│  ├─ 记录日志                  │
│  ├─ 业务逻辑                  │
│  ├─ 提交事务                  │
│  └─ 异常处理                  │
└─────────────────────────────┘

AOP 方式（切面分离）：
┌─────────────────────────────┐
│ 切面（Aspect）                 │
│  ├─ 权限检查                  │
│  ├─ 记录日志                  │
│  └─ 事务管理                  │
└─────────────────────────────┘
          ↓ 织入（Weaving）
┌─────────────────────────────┐
│ 业务逻辑（纯净）                │
│  └─ 核心业务                  │
└─────────────────────────────┘
```

### 1.2 AOP 术语

| 术语 | 说明 | 示例 |
|------|------|------|
| **Aspect** | 切面，横切关注点的模块化 | 日志切面、事务切面 |
| **Join Point** | 连接点，程序执行点 | 方法调用、异常抛出 |
| **Pointcut** | 切点，匹配连接点的表达式 | `execution(* com.example.*.*(..))` |
| **Advice** | 通知，切面在特定连接点的动作 | `@Before`、`@After` |
| **Target** | 目标对象，被代理的对象 | `OrderService` |
| **Proxy** | 代理对象，AOP 创建的代理 | JDK 动态代理 / CGLIB 代理 |
| **Weaving** | 织入，将切面应用到目标对象 | 运行时织入 |

## 二、Spring AOP 的使用

### 2.1 启用 AOP

```java
@Configuration
@EnableAspectJAutoProxy  // 启用 AOP
public class AppConfig {
}
```

### 2.2 定义切面

```java
@Aspect
@Component
public class LoggingAspect {
    
    // 切点：匹配所有 Service 的方法
    @Pointcut("execution(* com.example.service.*.*(..))")
    public void serviceLayer() {}
    
    // 前置通知
    @Before("serviceLayer()")
    public void logBefore(JoinPoint joinPoint) {
        System.out.println("Before: " + joinPoint.getSignature().getName());
    }
    
    // 返回后通知
    @AfterReturning(pointcut = "serviceLayer()", returning = "result")
    public void logAfterReturning(JoinPoint joinPoint, Object result) {
        System.out.println("After: " + result);
    }
    
    // 异常通知
    @AfterThrowing(pointcut = "serviceLayer()", throwing = "ex")
    public void logAfterThrowing(JoinPoint joinPoint, Exception ex) {
        System.out.println("Exception: " + ex.getMessage());
    }
    
    // 后置通知（finally）
    @After("serviceLayer()")
    public void logAfter(JoinPoint joinPoint) {
        System.out.println("After (finally)");
    }
    
    // 环绕通知（功能最强）
    @Around("serviceLayer()")
    public Object logAround(ProceedingJoinPoint joinPoint) throws Throwable {
        System.out.println("Around: Before");
        Object result = joinPoint.proceed();  // 执行目标方法
        System.out.println("Around: After");
        return result;
    }
}
```

### 2.3 切点表达式

**execution 表达式**：

```
execution(modifiers-pattern? ret-type-pattern declaring-type-pattern? name-pattern(param-pattern) throws-pattern?)

示例：
execution(* com.example.service.*.*(..))
         │    │                  │   │   │
         │    │                  │   │   └─ 任意参数
         │    │                  │   └─ 任意方法名
         │    │                  └─ 任意类
         │    └─ 任意返回类型
         └─ 任意访问修饰符
```

**常用切点表达式**：

```java
// 1. 匹配所有 public 方法
execution(public * *(..))

// 2. 匹配所有 Service 层方法
execution(* com.example.service.*.*(..))

// 3. 匹配 UserService 的所有方法
execution(* com.example.service.UserService.*(..))

// 4. 匹配所有带 @Transactional 的方法
@annotation(org.springframework.transaction.annotation.Transactional)

// 5. 匹配所有 Controller
within(@org.springframework.stereotype.Controller *)

// 6. Bean 名称匹配
bean(*Service)
```

### 2.4 通知执行顺序

```java
// 正常流程：
Around.Before → Before → 目标方法 → AfterReturning → After → Around.After

// 异常流程：
Around.Before → Before → 目标方法 → AfterThrowing → After
```

**示例**：
```java
@Around("serviceLayer()")
public Object around(ProceedingJoinPoint pjp) throws Throwable {
    System.out.println("1. Around Before");
    try {
        System.out.println("2. Before");
        Object result = pjp.proceed();
        System.out.println("4. AfterReturning");
        return result;
    } catch (Exception e) {
        System.out.println("4. AfterThrowing");
        throw e;
    } finally {
        System.out.println("5. After");
    }
}  // 输出 "6. Around After"
```

## 三、Spring AOP 的底层实现

### 3.1 代理机制

Spring AOP 使用**代理模式**实现切面织入：

```
┌─────────────────────────────────────────────────────┐
│ 客户端代码                                           │
│   │                                                │
│   └─ 调用代理对象  ────────────────────┐           │
│                                             ↓       │
│                                   ┌─────────────┐   │
│                                   │  代理对象     │   │
│                                   │  ├─ 前置通知  │   │
│                                   │  ├─ 目标方法  │   │
│                                   │  └─ 后置通知  │   │
│                                   └─────────────┘   │
│                                             ↓       │
│                                   ┌─────────────┐   │
│                                   │  目标对象     │   │
│                                   │  (Target)    │   │
│                                   └─────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 3.2 JDK 动态代理 vs CGLIB

Spring AOP 根据情况选择不同的代理方式：

| 特性 | JDK 动态代理 | CGLIB |
|------|--------------|--------|
| **条件** | 目标类实现接口 | 目标类无接口 / proxyTargetClass=true |
| **原理** | 实现接口，创建接口代理 | 继承目标类，创建子类 |
| **性能** | 创建快，执行慢 | 创建慢，执行快 |
| **限制** | 只能代理接口方法 | 不能代理 final 方法 |

**JDK 动态代理**：
```java
// 目标类实现接口
public class OrderServiceImpl implements OrderService {
    public void createOrder() { ... }
}

// Spring 使用 JDK 动态代理
OrderService proxy = (OrderService) Proxy.newProxyInstance(
    loader,
    new Class[]{OrderService.class},
    new InvocationHandler() {
        @Override
        public Object invoke(Object proxy, Method method, Object[] args) {
            // 前置逻辑
            Object result = method.invoke(target, args);
            // 后置逻辑
            return result;
        }
    }
);
```

**CGLIB 代理**：
```java
// 目标类无接口
public class OrderService {
    public void createOrder() { ... }
}

// Spring 使用 CGLIB
Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(OrderService.class);
enhancer.setCallback(new MethodInterceptor() {
    @Override
    public Object intercept(Object obj, Method method, Object[] args, MethodProxy proxy) {
        // 前置逻辑
        Object result = proxy.invokeSuper(obj, args);
        // 后置逻辑
        return result;
    }
});
OrderService proxy = (OrderService) enhancer.create();
```

### 3.3 强制使用 CGLIB

```java
@Configuration
@EnableAspectJAutoProxy(proxyTargetClass = true)  // 强制 CGLIB
public class AppConfig {
}
```

或

```xml
<aop:aspectj-autoproxy proxy-target-class="true" />
```

## 四、Spring 事务管理

### 4.1 声明式事务（@Transactional）

```java
@Service
public class OrderService {
    
    @Autowired
    private OrderDao orderDao;
    
    @Transactional
    public void createOrder(Order order) {
        orderDao.insert(order);
        // 如果这里抛异常，事务回滚
        updateInventory(order);
    }
}
```

**@Transactional 属性**：

| 属性 | 说明 | 默认值 |
|------|------|--------|
| `propagation` | 传播行为 | `REQUIRED` |
| `isolation` | 隔离级别 | `DEFAULT`（数据库默认）|
| `readOnly` | 是否只读 | `false` |
| `timeout` | 超时时间（秒）| `-1`（无限制）|
| `rollbackFor` | 指定回滚异常 | `RuntimeException` |
| `noRollbackFor` | 指定不回滚异常 | 无 |

### 4.2 事务传播行为

| 传播行为 | 说明 |
|---------|------|
| `REQUIRED`（默认）| 当前有事务就加入，没有就新建 |
| `REQUIRES_NEW` | 新建事务，挂起当前事务 |
| `SUPPORTS` | 当前有事务就加入，没有就以非事务执行 |
| `NOT_SUPPORTED` | 以非事务执行，挂起当前事务 |
| `MANDATORY` | 当前有事务就加入，没有就抛异常 |
| `NEVER` | 以非事务执行，当前有事务就抛异常 |
| `NESTED` | 嵌套事务（保存点） |

**示例**：
```java
@Service
public class OrderService {
    
    @Autowired
    private PaymentService paymentService;
    
    @Transactional
    public void createOrder() {
        // 事务 A
        orderDao.insert();
        
        // 事务 B（新事务，不受 A 影响）
        paymentService.pay();  // @Transactional(propagation = Propagation.REQUIRES_NEW)
        
        // 如果这里抛异常，事务 A 回滚，事务 B 已提交
        throw new RuntimeException();
    }
}

@Service
public class PaymentService {
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void pay() {
        // 新事务，独立于 createOrder 的事务
    }
}
```

### 4.3 事务隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| `READ_UNCOMMITTED` | ❌ | ❌ | ❌ |
| `READ_COMMITTED` | ✅ | ❌ | ❌ |
| `REPEATABLE_READ` | ✅ | ✅ | ❌ |
| `SERIALIZABLE` | ✅ | ✅ | ✅ |

```java
@Transactional(isolation = Isolation.SERIALIZABLE)
public void criticalOperation() {
    // 最高隔离级别，性能最差
}
```

### 4.4 @Transactional 失效场景

**失效场景 1：非 public 方法**

```java
@Transactional
private void createOrder() {  // ❌ private 方法不生效
    // ...
}
```

**失效场景 2：自调用问题**

```java
@Service
public class OrderService {
    
    public void createOrder() {
        this.addOrderLog();  // ❌ 自调用，@Transactional 失效
    }
    
    @Transactional
    public void addOrderLog() {
        // ...
    }
}
```

**原因**：Spring 事务通过代理实现，自调用绕过了代理。

**解决**：
```java
// 方案 1：通过代理调用
@Autowired
private OrderService self;  // 注入自己（代理）

public void createOrder() {
    self.addOrderLog();  // ✅ 通过代理调用
}

// 方案 2：拆分到另一个 Service
```

**失效场景 3：异常被捕获**

```java
@Transactional
public void createOrder() {
    try {
        orderDao.insert();
    } catch (Exception e) {
        // ❌ 异常被捕获，事务不回滚
    }
}
```

**解决**：重新抛出异常
```java
@Transactional
public void createOrder() {
    try {
        orderDao.insert();
    } catch (Exception e) {
        throw e;  // ✅ 抛出异常，事务回滚
    }
}
```

**失效场景 4：异常类型不匹配**

```java
@Transactional(rollbackFor = RuntimeException.class)
public void createOrder() throws Exception {
    throw new Exception();  // ❌ Exception 不回滚
}
```

**解决**：指定正确的回滚异常
```java
@Transactional(rollbackFor = Exception.class)  // ✅
public void createOrder() throws Exception {
    throw new Exception();
}
```

## 五、AOP 实战案例

### 案例 1：性能监控

```java
@Aspect
@Component
public class PerformanceAspect {
    
    @Around("execution(* com.example.service.*.*(..))")
    public Object measureTime(ProceedingJoinPoint joinPoint) throws Throwable {
        long start = System.currentTimeMillis();
        Object result = joinPoint.proceed();
        long elapsed = System.currentTimeMillis() - start;
        
        System.out.println(joinPoint.getSignature() + " 耗时: " + elapsed + "ms");
        
        if (elapsed > 1000) {
            System.err.println("警告：方法执行超时！");
        }
        
        return result;
    }
}
```

### 案例 2：安全校验

```java
@Aspect
@Component
public class SecurityAspect {
    
    @Before("@annotation(RequiresPermission)")
    public void checkPermission(JoinPoint joinPoint) {
        // 获取当前用户
        User user = SecurityContext.getCurrentUser();
        
        // 检查权限
        if (!user.hasPermission("ADMIN")) {
            throw new SecurityException("无权限");
        }
    }
}

// 自定义注解
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface RequiresPermission {
    String value() default "";
}

// 使用
@Service
public class AdminService {
    
    @RequiresPermission("admin:delete")
    public void deleteUser(Long userId) {
        // ...
    }
}
```

### 案例 3：缓存切面

```java
@Aspect
@Component
public class CacheAspect {
    
    private Map<String, Object> cache = new ConcurrentHashMap<>();
    
    @Around("@annotation(Cachable)")
    public Object cache(ProceedingJoinPoint joinPoint) throws Throwable {
        // 生成缓存 key
        String key = generateKey(joinPoint);
        
        // 查缓存
        Object cached = cache.get(key);
        if (cached != null) {
            return cached;
        }
        
        // 执行方法
        Object result = joinPoint.proceed();
        
        // 存入缓存
        cache.put(key, result);
        
        return result;
    }
    
    private String generateKey(ProceedingJoinPoint joinPoint) {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        Object[] args = joinPoint.getArgs();
        
        return method.getDeclaringClass().getName() + "." 
               + method.getName() + Arrays.toString(args);
    }
}
```

## 六、面试高频问题

### Q1：JDK 动态代理和 CGLIB 的区别？

**答**：
| 特性 | JDK 动态代理 | CGLIB |
|------|--------------|--------|
| **条件** | 目标类实现接口 | 任意类（无 final） |
| **原理** | 实现接口 | 继承目标类 |
| **性能** | 创建快，执行慢 | 创建慢，执行快 |
| **限制** | 只能代理接口方法 | 不能代理 final 方法 |

### Q2：@Transactional 的原理？

**答**：
- Spring 事务通过 AOP 实现
- 创建代理对象，在方法调用前后添加事务逻辑
- 底层使用 `PlatformTransactionManager` 管理事务

### Q3：@Transactional 失效的场景？

**答**：
1. 非 public 方法
2. 自调用（绕过了代理）
3. 异常被捕获
4. 异常类型不匹配 `rollbackFor`

### Q4：事务传播行为有哪些？

**答**：
- `REQUIRED`（默认）：当前有事务就加入，没有就新建
- `REQUIRES_NEW`：新建事务，挂起当前事务
- `SUPPORTS`：有事务就加入，没有就以非事务执行
- `NOT_SUPPORTED`：以非事务执行，挂起当前事务
- ...（共 7 种）

### Q5：AOP 的应用场景？

**答**：
- 事务管理（`@Transactional`）
- 日志管理
- 安全校验
- 性能监控
- 缓存

## 七、总结

**AOP 核心要点**：
- **AOP**：面向切面编程，将横切关注点与业务逻辑分离
- **代理机制**：JDK 动态代理（接口）、CGLIB（类）
- **事务管理**：`@Transactional` 基于 AOP 实现

**通知类型**：
1. `@Before`：前置通知
2. `@AfterReturning`：返回后通知
3. `@AfterThrowing`：异常通知
4. `@After`：后置通知（finally）
5. `@Around`：环绕通知（最强）

**@Transactional 失效场景**：
1. 非 public 方法
2. 自调用
3. 异常被捕获
4. 异常类型不匹配

**最佳实践**：
1. 事务方法必须是 public
2. 避免在事务方法中执行耗时操作
3. 指定合适的 `rollbackFor`
4. 避免自调用（通过代理调用）

---

**下一篇预告**：Spring MVC 深度解析 —— 请求流程、参数绑定、拦截器

**参考资料**：
- 《Spring 实战》- Craig Walls
- Spring 官方文档：https://docs.spring.io/spring-framework/docs/current/reference/html/core.html
- 《Spring 源码深度解析》- 郝佳
