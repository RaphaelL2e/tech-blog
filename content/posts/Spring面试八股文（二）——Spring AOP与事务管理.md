---
title: Spring面试八股文（二）——Spring AOP与事务管理
date: 2026-06-24 09:00:00+08:00
updated: '2026-06-24T09:00:00+08:00'
description: 🎯 本文目标：承接上一篇的IoC容器基础，深入剖析Spring AOP的核心机制——JDK动态代理与CGLIB的底层原理及选择策略、切点表达式的完整语法与匹配规则、AOP执行链的责任链模式实现、以及Spring声明式事务的七种传播行为与六大失效场景，构建Spring
  AOP与事务管理的完整知识体系。
topic: java-spring
series: spring-interview
series_order: 2
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Spring
- AOP
- 动态代理
categories:
- Java 与 Spring
draft: false
---

> 🎯 **本文目标**：承接上一篇的IoC容器基础，深入剖析Spring AOP的核心机制——JDK动态代理与CGLIB的底层原理及选择策略、切点表达式的完整语法与匹配规则、AOP执行链的责任链模式实现、以及Spring声明式事务的七种传播行为与六大失效场景，构建Spring AOP与事务管理的完整知识体系。

---

## 一、AOP——面向切面编程

### 1.1 什么是AOP？为什么需要它？

**Q: 没有AOP的代码是什么样的？**

```java
// 没有AOP：横切关注点散落各处，代码臃肿
@Service
public class OrderService {
    
    public Order createOrder(Order order) {
        // 记录日志
        log.info("开始创建订单: {}", order.getId());
        long start = System.currentTimeMillis();
        
        try {
            // 权限校验
            if (!hasPermission("order:create")) {
                throw new AccessDeniedException("无权限");
            }
            
            // 开启事务
            transactionManager.begin();
            
            // ===== 核心业务逻辑（只有这3行！）=====
            orderRepository.save(order);
            inventoryService.deductStock(order);
            notificationService.sendOrderNotice(order);
            // ==================================
            
            transactionManager.commit();
            log.info("订单创建成功, 耗时: {}ms", System.currentTimeMillis() - start);
            return order;
            
        } catch (Exception e) {
            transactionManager.rollback();
            log.error("订单创建失败", e);
            throw e;
        }
    }
}
```

**核心业务逻辑只占3行，剩下80%都是横切关注点代码** → 这就是AOP要解决的问题。

**AOP的核心思想：**

```
横切关注点（Cross-cutting Concerns）：
┌─────────────────────────────────────────────────┐
│  日志    安全    事务    性能监控    异常处理      │  ← 散落在所有方法中
└─────────────────────────────────────────────────┘
         ↓ AOP把它们抽离成"切面"集中管理

┌─────────────────────────────────────────────────┐
│                 业务逻辑（纯粹！）                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ 创建订单  │  │ 取消订单  │  │ 查询订单  │      │
│  └──────────┘  └──────────┘  └──────────┘      │
└─────────────────────────────────────────────────┘
         ↑ 切面在适当的时机织入
┌─────────────────────────────────────────────────┐
│  日志切面    安全切面    事务切面    监控切面       │
└─────────────────────────────────────────────────┘
```

```java
// 有AOP：业务代码前所未有的干净
@Service
public class OrderService {
    
    @Transactional  // 事务切面
    @PreAuthorize("hasRole('USER')") // 安全切面
    public Order createOrder(Order order) {
        orderRepository.save(order);
        inventoryService.deductStock(order);
        notificationService.sendOrderNotice(order);
        return order;
    }
}
// 日志和性能监控通过全局切面统一处理，一行注解都不用加！
```

### 1.2 AOP核心概念

| 概念 | 说明 | 生活类比 |
|------|------|---------|
| **切面（Aspect）** | 横切关注点的模块化类 | "安全检查规范手册" |
| **连接点（Join Point）** | 程序执行过程中的某个点 | "进入每个房间的门口" |
| **切入点（Pointcut）** | 匹配连接点的表达式 | "所有VIP房间的门口" |
| **通知（Advice）** | 在切入点执行的动作 | "在VIP门口进行安检" |
| **目标对象（Target）** | 被代理的原始对象 | "VIP房间的客人" |
| **织入（Weaving）** | 将切面应用到目标对象的过程 | "把安检规范应用于每个VIP房间" |

```
一个典型的切面：

@Aspect          ← 这是一个切面
@Component
public class SecurityAspect {
    
    @Before("execution(* com.example.service..*(..))")  ← 切入点是service包下所有方法
    public void checkPermission(JoinPoint joinPoint) {        ← 通知：在方法执行前
        // 检查权限的逻辑
    }
}

织入后的效果：
┌──────────────────────────────────────┐
│  checkPermission()  ← 切面逻辑      │
│  ─────────────────────              │
│  原始业务方法()        ← 目标对象     │
│  ─────────────────────              │
│  记录日志()           ← 另一个切面   │
└──────────────────────────────────────┘
```

---

## 二、代理机制——JDK动态代理 vs CGLIB

### 2.1 JDK动态代理

**Q: JDK动态代理的原理是什么？有什么限制？**

**核心类**：`java.lang.reflect.Proxy` + `InvocationHandler`

```java
// 步骤1：定义接口（JDK代理的前提——必须要有接口！）
public interface UserService {
    void save(User user);
    User findById(Long id);
}

// 步骤2：实现InvocationHandler
public class LogInvocationHandler implements InvocationHandler {
    private final Object target;
    
    public LogInvocationHandler(Object target) {
        this.target = target;
    }
    
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        System.out.println(">>> 调用前: " + method.getName());
        long start = System.currentTimeMillis();
        
        Object result = method.invoke(target, args); // 反射调用原始对象
        
        long time = System.currentTimeMillis() - start;
        System.out.println("<<< 调用后: " + method.getName() + " 耗时: " + time + "ms");
        return result;
    }
}

// 步骤3：创建代理对象
UserService target = new UserServiceImpl();
UserService proxy = (UserService) Proxy.newProxyInstance(
    target.getClass().getClassLoader(),  // 类加载器
    target.getClass().getInterfaces(),   // 必须要有接口！
    new LogInvocationHandler(target)     // 调用处理器
);
proxy.save(new User()); // 实际调用的是invoke()方法
```

**JDK动态代理工作原理：**

```
运行时动态生成代理类（$Proxy0）：

public final class $Proxy0 extends Proxy implements UserService {
    
    public void save(User user) {
        // 调用 InvocationHandler.invoke()
        super.h.invoke(this, m3, new Object[]{user});
    }
    
    // m3 是在静态代码块中通过反射获取的Method对象
    static {
        m3 = Class.forName("com.example.UserService").getMethod("save", User.class);
    }
}
```

**JDK代理的限制**：
- ❌ **必须有接口**（基于接口代理）
- ❌ 只能代理接口中定义的方法
- ✅ JDK自带，无需第三方依赖
- ✅ 代理对象的性能好（直接方法调用）

### 2.2 CGLIB动态代理

**Q: CGLIB和JDK代理有什么区别？Spring如何选择？**

**CGLIB（Code Generation Library）**是基于ASM字节码框架的代理实现，通过**生成目标类的子类**来实现代理。

```java
// CGLIB不需要接口！可以直接代理类
public class UserServiceImpl { // 没有实现接口
    public void save(User user) {
        System.out.println("保存用户: " + user);
    }
}

// CGLIB的MethodInterceptor
public class LogMethodInterceptor implements MethodInterceptor {
    
    @Override
    public Object intercept(Object obj, Method method, Object[] args, 
                            MethodProxy proxy) throws Throwable {
        System.out.println(">>> 调用前: " + method.getName());
        
        // 方式1：反射调用（慢）
        // Object result = method.invoke(target, args);
        
        // 方式2：使用MethodProxy（快！避开了反射）
        Object result = proxy.invokeSuper(obj, args); // ← 推荐方式
        
        System.out.println("<<< 调用后: " + method.getName());
        return result;
    }
}

// 创建代理
Enhancer enhancer = new Enhancer();
enhancer.setSuperclass(UserServiceImpl.class); // 设置父类（目标类）
enhancer.setCallback(new LogMethodInterceptor());
UserServiceImpl proxy = (UserServiceImpl) enhancer.create();
```

**CGLIB生成的代理类结构：**

```
目标类                           CGLIB代理类
UserServiceImpl              UserServiceImpl$$EnhancerByCGLIB$$xxxxx
    ↑                                   ↑
    │                                extends
    │                                   │
实现了业务逻辑                  重写所有非final方法
                                    ├── save() → intercept() → super.save()
                                    └── findById() → intercept() → super.findById()
```

**CGLIB的限制**：
- ❌ 无法代理 `final` 类（无法继承）
- ❌ 无法代理 `final` 方法（无法重写）
- ❌ 无法代理 `private` 方法（无法重写）
- ❌ 需要额外引入CGLIB依赖
- ✅ 代理创建速度慢于JDK代理（但执行速度更快）

### 2.3 Spring的选择策略

**Q: Spring什么时候用JDK代理，什么时候用CGLIB？**

```
Spring AOP代理选择策略（ProxyTargetClass）：

┌─────────────────────────────────────────────────┐
│  目标类是否实现了接口？                            │
│    │                                              │
│    ├── 是 → 默认使用 JDK动态代理                   │
│    │         (proxyTargetClass=false)             │
│    │                                              │
│    └── 否 → 使用 CGLIB代理                        │
│                                                  │
│  Spring Boot 默认行为（@EnableAspectJAutoProxy）： │
│    - 如果没有手动配置，默认 proxyTargetClass=true  │
│    - 也就是说 Spring Boot 默认使用 CGLIB！         │
└─────────────────────────────────────────────────┘
```

```java
// 强制使用CGLIB（Spring Boot中默认行为）
@EnableAspectJAutoProxy(proxyTargetClass = true)
@SpringBootApplication
public class Application { }

// 强制使用JDK代理（需要目标类实现了接口）
@EnableAspectJAutoProxy(proxyTargetClass = false)
@SpringBootApplication
public class Application { }
```

**面试回答关键点：**

| 对比维度 | JDK动态代理 | CGLIB代理 |
|---------|-----------|----------|
| 代理方式 | 基于接口 | 基于继承（生成子类） |
| 生成速度 | 快（反射+字节码拼接） | 慢（ASM生成完整字节码） |
| 执行速度 | 慢（反射调用） | 快（直接方法调用，MethodProxy） |
| 接口要求 | **必须实现接口** | 不需要接口 |
| 限制 | 无法代理未在接口中定义的方法 | 不能代理final类/方法 |
| Spring默认 | Spring Framework默认选择 | **Spring Boot默认选择** |

> ⚠️ **关键记忆点**：Spring Boot 2.x 开始默认使用 CGLIB 代理（`spring.aop.proxy-target-class=true`），即使目标类实现了接口也优先用CGLIB，这是和传统Spring Framework的重要区别。

### 2.4 代理失效的经典场景

**Q: 什么情况下AOP会失效？（高频面试题⭐⭐⭐⭐⭐）**

#### 场景1：内部方法调用（this调用）

```java
@Service
public class OrderService {
    
    @Transactional  // 事务控制doSomething
    public void doSomething() {
        // ...
        this.doInternal(); // ⚠️ this调用，绕过了代理！
    }
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void doInternal() {
        // ⚠️ 这里的事务注解失效！因为是通过this直接调用，没有经过代理
    }
}

// 解决方案1：注入自身（通过ApplicationContext）
@Service
public class OrderService {
    @Autowired
    private ApplicationContext context;
    
    public void doSomething() {
        OrderService proxy = context.getBean(OrderService.class); // 获取代理对象
        proxy.doInternal(); // ✅ 经过代理，AOP生效
    }
}

// 解决方案2：使用@Lazy注入自身
@Service
public class OrderService {
    @Lazy
    @Autowired
    private OrderService self; // 注入代理自身
    
    public void doSomething() {
        self.doInternal(); // ✅ 经过代理
    }
}

// 解决方案3（推荐）：抽到另一个Service
@Service
public class InternalService {
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void doInternal() { ... }
}
```

**为什么this调用失效？**

```
外部调用：
  caller → proxy.doInternal() → AOP切面 → target.doInternal() ✅ 经过代理

内部this调用：
  target.doSomething() → this.doInternal() ❌ 直接调用原始对象，绕过代理
```

---

## 三、切点表达式——精确匹配的艺术

### 3.1 execution表达式全解

**Q: 如何写出精准的切点表达式？**

`execution` 是最常用的切点指示器，语法如下：

```
execution(modifiers-pattern? ret-type-pattern declaring-type-pattern?
          name-pattern(param-pattern) throws-pattern?)
```

```
execution(* com.example.service.OrderService.createOrder(..))

┌─────────┬──────────────────────────────────────┬─────────────────┬────┐
│ 修饰符   │         返回类型 + 全限定类名          │   方法名          │ 参数│
│   *     │  com.example.service.OrderService    │  createOrder     │ .. │
│ (任意)   │  (OrderService类)                    │  (方法名精确匹配)  │(任意参数)│
└─────────┴──────────────────────────────────────┴─────────────────┴────┘
```

**常用切点表达式汇总：**

```java
// 1. 匹配特定包下所有类的所有方法
@Pointcut("execution(* com.example.service.*.*(..))")
//         ↑返回类型        ↑包      ↑类  ↑方法 ↑参数

// 2. 匹配特定包及子包下所有public方法
@Pointcut("execution(public * com.example.service..*.*(..))")
//                  ↑修饰符     ↑包+子包(两个点)

// 3. 匹配所有save开头的方法
@Pointcut("execution(* com.example..*.save*(..))")
//                           ↑包    ↑类 ↑方法名

// 4. 匹配指定参数类型的方法
@Pointcut("execution(* com.example.service.*.*(Long, ..))")
//                                         ↑第一个参数Long，后面任意

// 5. 匹配无参方法
@Pointcut("execution(* com.example..*.*())")

// 6. 匹配带@Transactional注解的方法（常用！）
@Pointcut("@annotation(org.springframework.transaction.annotation.Transactional)")

// 7. 匹配带@RestController注解的类中所有方法
@Pointcut("@within(org.springframework.web.bind.annotation.RestController)")

// 8. 匹配指定包但不包含某个子包
@Pointcut("execution(* com.example.service.*.*(..)) "
        + "&& !execution(* com.example.service.internal.*.*(..))")
```

### 3.2 切点表达式的组合

```java
@Aspect
@Component
public class CombinedAspect {
    
    // 定义可复用的切点
    @Pointcut("execution(* com.example.service..*.*(..))")
    public void serviceLayer() {}
    
    @Pointcut("@annotation(org.springframework.transaction.annotation.Transactional)")
    public void transactionalMethods() {}
    
    @Pointcut("execution(* com.example.service.UserService.*(..))")
    public void userServiceMethods() {}
    
    // 组合切点：service层的非事务方法
    @Pointcut("serviceLayer() && !transactionalMethods()")
    public void nonTransactionalServiceMethods() {}
    
    // 组合切点：UserService中的事务方法
    @Before("userServiceMethods() && transactionalMethods()")
    public void beforeUserTransactionalMethod(JoinPoint joinPoint) {
        log.info("即将执行UserService的事务方法: {}", joinPoint.getSignature().getName());
    }
}
```

---

## 四、通知类型与执行链

### 4.1 五种通知类型

**Q: Spring AOP有哪些通知类型？执行顺序是怎样的？**

| 通知类型 | 注解 | 执行时机 | 典型用途 |
|---------|------|---------|---------|
| **前置通知** | `@Before` | 目标方法执行前 | 权限校验、参数日志 |
| **后置返回** | `@AfterReturning` | 方法正常返回后 | 结果缓存、返回值处理 |
| **后置异常** | `@AfterThrowing` | 方法抛出异常后 | 异常日志、告警通知 |
| **最终通知** | `@After` | 方法执行后（≥finally） | 资源释放、计时统计 |
| **环绕通知** | `@Around` | 包围目标方法 | 事务管理、性能监控、分布式锁 |

```java
@Aspect
@Component
public class OrderAspect {
    
    // 前置通知：方法执行前
    @Before("execution(* com.example.service.OrderService.*(..))")
    public void before(JoinPoint joinPoint) {
        log.info("调用方法: {}", joinPoint.getSignature());
    }
    
    // 后置返回：正常返回后
    @AfterReturning(pointcut = "execution(* com.example.service.OrderService.*(..))", 
                    returning = "result")
    public void afterReturning(JoinPoint joinPoint, Object result) {
        log.info("方法返回: {}, 结果: {}", joinPoint.getSignature(), result);
    }
    
    // 后置异常：抛出异常后
    @AfterThrowing(pointcut = "execution(* com.example.service.OrderService.*(..))", 
                   throwing = "ex")
    public void afterThrowing(JoinPoint joinPoint, Exception ex) {
        log.error("方法异常: {}, 异常: {}", joinPoint.getSignature(), ex.getMessage());
    }
    
    // 最终通知：类似finally
    @After("execution(* com.example.service.OrderService.*(..))")
    public void after(JoinPoint joinPoint) {
        log.info("方法结束: {}", joinPoint.getSignature());
    }
    
    // 环绕通知：最强大——可以控制方法是否执行、何时执行
    @Around("@annotation(logExecution)")
    public Object around(ProceedingJoinPoint joinPoint, LogExecution logExecution) 
            throws Throwable {
        String methodName = joinPoint.getSignature().getName();
        log.info(">>> {} 开始执行", methodName);
        long start = System.currentTimeMillis();
        
        try {
            Object result = joinPoint.proceed(); // ← 决定何时执行目标方法
            long time = System.currentTimeMillis() - start;
            log.info("<<< {} 执行成功, 耗时: {}ms", methodName, time);
            return result;
            
        } catch (Exception e) {
            log.error("<<< {} 执行失败, 异常: {}", methodName, e.getMessage());
            throw e; // 决定是否重新抛出
        }
    }
}
```

### 4.2 同一切面内通知的执行顺序

```java
@Aspect
@Component
public class AuditAspect {
    
    @Before("pointcut()")
    public void doBefore() { System.out.println("1. @Before"); }
    
    @AfterReturning("pointcut()")
    public void doAfterReturning() { System.out.println("3. @AfterReturning"); }
    
    @After("pointcut()")
    public void doAfter() { System.out.println("2. @After"); }
    
    @AfterThrowing("pointcut()")
    public void doAfterThrowing() { System.out.println("3. @AfterThrowing"); }
}

// 正常情况执行顺序：
// 1. @Before → 2. 目标方法 → 3. @AfterReturning → 4. @After

// 异常情况执行顺序：
// 1. @Before → 2. 目标方法(抛异常) → 3. @AfterThrowing → 4. @After
```

### 4.3 多个切面的执行顺序

**Q: 多个切面同时作用于同一个方法，执行顺序如何确定？**

```
多个切面的执行顺序（洋葱模型）：

┌─────────────────────────────────────────┐
│           Aspect-A @Before              │
│  ┌─────────────────────────────────┐    │
│  │       Aspect-B @Before          │    │
│  │  ┌─────────────────────────┐    │    │
│  │  │      目标方法              │    │    │
│  │  └─────────────────────────┘    │    │
│  │       Aspect-B @After           │    │
│  └─────────────────────────────────┘    │
│           Aspect-A @After               │
└─────────────────────────────────────────┘

执行顺序：A-Before → B-Before → 目标方法 → B-After → A-After
```

**控制切面顺序：**

```java
// 方式1：@Order注解（值越小越先执行）
@Aspect
@Component
@Order(1)  // 先执行
public class SecurityAspect { }

@Aspect
@Component
@Order(2)  // 后执行
public class LoggingAspect { }

// 方式2：实现Ordered接口
@Aspect
@Component
public class TransactionAspect implements Ordered {
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE; // Integer.MIN_VALUE，最先执行
    }
}
```

---

## 五、Spring声明式事务

### 5.1 事务的核心ACID特性

**Q: 什么是事务？ACID是什么？**

> 事务是一组不可分割的操作单元，要么全部成功，要么全部失败。

| 特性 | 说明 | 银行转账例子 |
|------|------|------------|
| **A-原子性** | 操作不可分割 | 转出+转入要么都成功，要么都失败 |
| **C-一致性** | 事务前后数据一致 | 转账前后总金额不变 |
| **I-隔离性** | 并发事务互不干扰 | 同时转账互不影响 |
| **D-持久性** | 提交后永久保存 | 转账成功后，重启服务器数据仍在 |

### 5.2 @Transactional核心属性

```java
@Transactional(
    propagation = Propagation.REQUIRED,      // 传播行为
    isolation = Isolation.READ_COMMITTED,    // 隔离级别
    timeout = 30,                            // 超时秒数
    readOnly = false,                        // 是否只读
    rollbackFor = Exception.class,           // 哪些异常回滚
    noRollbackFor = {IllegalArgumentException.class} // 哪些异常不回滚
)
```

### 5.3 事务传播行为（面试高频⭐⭐⭐⭐⭐）

**Q: Spring事务的七种传播行为是什么？**

| 传播行为 | 当前有事务 | 当前无事务 | 典型场景 |
|---------|-----------|-----------|---------|
| **REQUIRED**（默认） | 加入当前事务 | 新建事务 | 大多数业务方法 |
| **REQUIRES_NEW** | 挂起当前事务，新建 | 新建事务 | 日志记录（独立提交，不受外层影响） |
| **SUPPORTS** | 加入当前事务 | 不开启事务 | 查询方法 |
| **NOT_SUPPORTED** | 挂起当前事务，非事务运行 | 不开启事务 | 不需要事务的数据导出 |
| **MANDATORY** | 加入当前事务 | 抛异常 | 必须在事务中执行的方法 |
| **NEVER** | 抛异常 | 不开启事务 | 禁止在事务中运行 |
| **NESTED** | 创建保存点（嵌套事务） | 新建事务 | 部分回滚场景 |

```java
// 最常用场景：日志记录需要独立事务
@Service
public class OrderService {
    
    @Autowired
    private OrderLogService orderLogService;
    
    @Transactional  // REQUIRED（默认）
    public void createOrder(Order order) {
        orderRepository.save(order);        // ← 核心业务
        inventoryService.deductStock(order); // ← 核心业务
        
        try {
            orderLogService.saveLog(order);  // ← 日志：独立事务
        } catch (Exception e) {
            // 日志失败不影响主业务
            log.warn("日志记录失败，但订单创建成功", e);
        }
    }
}

@Service
public class OrderLogService {
    
    @Transactional(propagation = Propagation.REQUIRES_NEW) // ← 关键！
    public void saveLog(Order order) {
        logRepository.save(new OrderLog(order));
        // 即使这里抛异常，也不会回滚外层事务！
    }
}
```

**REQUIRED vs REQUIRES_NEW vs NESTED 本质区别：**

```
REQUIRED（加入）：
  ServiceA.method() ───── 事务1 ─────
    ServiceB.method() ───── 还是事务1 ─────
  ↓ B回滚 → A也回滚（共享同一事务）

REQUIRES_NEW（独立）：
  ServiceA.method() ───── 事务1 ─────
    ServiceB.method() ───── 事务2（独立）─────
  ↓ B回滚 → 只回滚事务2，A的事务1不受影响

NESTED（嵌套+保存点）：
  ServiceA.method() ───── 事务1 ─────
    savepoint1
    ServiceB.method() ───── 嵌套在事务1 ─────
  ↓ B回滚 → 回滚到savepoint1，AI继续执行
```

### 5.4 事务隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 并发性能 |
|---------|------|-----------|------|---------|
| **READ_UNCOMMITTED** | ❌ 可能 | ❌ 可能 | ❌ 可能 | 最高 |
| **READ_COMMITTED** | ✅ 避免 | ❌ 可能 | ❌ 可能 | 高 |
| **REPEATABLE_READ** | ✅ 避免 | ✅ 避免 | ❌ 可能（MySQL通过间隙锁解决） | 中 |
| **SERIALIZABLE** | ✅ 避免 | ✅ 避免 | ✅ 避免 | 最低 |

```java
@Transactional(isolation = Isolation.READ_COMMITTED)
public void transfer(Long fromId, Long toId, BigDecimal amount) {
    // MySQL默认REPEATABLE_READ，但这个场景READ_COMMITTED就够了
    accountDao.debit(fromId, amount); // 扣款
    accountDao.credit(toId, amount);  // 入账
}
```

---

## 六、事务失效的六大经典场景

**Q: @Transactional什么情况下会失效？（面试必考⭐⭐⭐⭐⭐）**

### 场景1：方法非public

```java
@Service
public class OrderService {
    
    @Transactional
    protected void createOrder(Order order) { // ❌ 非public，事务失效！
        orderRepository.save(order);
    }
    
    @Transactional
    private void createOrderInternal(Order order) { // ❌ 非public，事务失效！
        // Spring AOP基于动态代理，只能拦截public方法
    }
}
```

### 场景2：内部方法调用（this调用）

```java
@Service
public class OrderService {
    
    public void processOrder(Order order) {
        this.createOrder(order); // ❌ this调用，绕过了代理，事务失效！
    }
    
    @Transactional
    public void createOrder(Order order) {
        orderRepository.save(order);
    }
}
```

### 场景3：异常被吞掉

```java
@Transactional
public void createOrder(Order order) {
    try {
        orderRepository.save(order);
        paymentService.pay(order); // 这里抛了异常
    } catch (Exception e) {
        log.error("支付失败", e);
        // ❌ catch后没有重新抛出，Spring感知不到异常，不会回滚！
    }
}

// 正确做法：
@Transactional(rollbackFor = Exception.class)
public void createOrder(Order order) {
    try {
        orderRepository.save(order);
        paymentService.pay(order);
    } catch (Exception e) {
        log.error("支付失败", e);
        TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
        throw new RuntimeException("支付失败，订单回滚", e); // ✅ 重新抛出
    }
}
```

### 场景4：rollbackFor设置不当

```java
@Transactional  // 默认只回滚RuntimeException和Error
public void createOrder(Order order) throws Exception {
    orderRepository.save(order);
    throw new Exception("业务异常"); // ❌ 受检异常，默认不回滚！
}

// 正确做法：
@Transactional(rollbackFor = Exception.class) // ✅ 所有异常都回滚
public void createOrder(Order order) throws Exception {
    orderRepository.save(order);
    throw new Exception("业务异常");
}
```

### 场景5：方法用final修饰

```java
@Service
public class OrderService {
    
    @Transactional
    public final void createOrder(Order order) { // ❌ final方法无法被代理
        orderRepository.save(order);
    }
}

// Spring Boot默认使用CGLIB（基于继承），final方法无法重写 → AOP失效
```

### 场景6：多线程环境

```java
@Service
public class OrderService {
    
    @Transactional
    public void createOrder(Order order) {
        orderRepository.save(order); // ← 在主线程的事务中
        
        new Thread(() -> {
            // ❌ 新线程！事务不会传播到新线程
            inventoryService.deductStock(order);
        }).start();
    }
    // 主线程事务提交了，但子线程的库存扣减不在事务中
}
```

**事务失效六大场景速查表：**

| 场景 | 原因 | 解决方案 |
|------|------|---------|
| 方法非public | AOP只能拦截public方法 | 改为public |
| this调用 | 绕过代理对象 | 注入自身/getBean/抽出新Service |
| 异常被吞 | Spring感知不到异常 | 重新抛出或手动setRollbackOnly |
| rollbackFor不当 | 默认为RuntimeException | 设置`rollbackFor = Exception.class` |
| final方法 | CGLIB无法重写 | 去掉final或改用接口代理 |
| 多线程 | 事务在线程间不传播 | 使用分布式事务或单独事务管理 |

---

## 七、面试高频真题

### Q1: Spring AOP和AspectJ有什么区别？

| 对比维度 | Spring AOP | AspectJ |
|---------|-----------|---------|
| 实现方式 | 运行时动态代理 | 编译时/类加载时字节码修改（织入） |
| 织入时机 | 运行时 | 编译期 / 类加载期 / 编译后 |
| 性能 | 稍慢（代理开销） | 更快（无代理，直接修改字节码） |
| 功能完整度 | 仅支持方法级连接点 | 支持字段、构造器、静态初始化等 |
| 使用复杂度 | 简单，注解即可 | 复杂，需要特殊编译器或agent |
| 依赖 | spring-aop | aspectjweaver.jar |

### Q2: Spring AOP的底层实现原理简述

```
1. @EnableAspectJAutoProxy 注册了 AnnotationAwareAspectJAutoProxyCreator
2. 这是一个 BeanPostProcessor，在每个Bean初始化后进行处理
3. 检查Bean是否匹配任何切面（通过切点表达式）
4. 如果匹配，创建代理对象（JDK或CGLIB）
5. 将代理对象替换原始Bean放入容器
6. 后续调用时，通过代理对象执行切面逻辑链
```

### Q3: Spring事务和数据库事务是什么关系？

```
Spring事务（逻辑层）:
    @Transactional
    ↓
    通过 PlatformTransactionManager 管理
    ↓
数据库事务（物理层）:
    conn.setAutoCommit(false);  // 开启
    执行SQL...
    conn.commit(); / conn.rollback();  // 提交或回滚

关键：Spring事务本质是对JDBC事务的封装，通过AOP在方法前后
      调用conn.setAutoCommit/commit/rollback
```

### Q4: 大事务有什么问题？如何优化？

```java
// ❌ 大事务——锁持有时间长、回滚代价大
@Transactional
public void processOrder(Order order) {
    // 1. 远程调用（耗时2s）
    User user = userService.getUser(order.getUserId());
    // 2. 发送短信（耗时500ms）
    smsService.sendSms(user.getPhone(), "下单成功");
    // 3. 写数据库（耗时10ms）
    orderRepository.save(order);
    // 4. 发送MQ消息（耗时100ms）
    rocketMQTemplate.send("order-topic", order);
    // 整个事务持续3秒+，数据库连接一直被占用！
}

// ✅ 优化方案
public void processOrder(Order order) {
    // 非事务操作移出事务
    User user = userService.getUser(order.getUserId()); // 查询不需要事务
    
    // 只有数据库写操作在事务内
    doCreateOrder(order);
    
    // 发送通知移出事务
    smsService.sendSms(user.getPhone(), "下单成功");
    rocketMQTemplate.send("order-topic", order);
}

@Transactional
public void doCreateOrder(Order order) {
    orderRepository.save(order); // 只有核心写操作需要事务
}
```

---

## 八、下期预告

下一篇将深入 **Spring MVC核心原理**——DispatcherServlet的完整请求处理链路、HandlerMapping与HandlerAdapter的适配器模式、拦截器(Interceptor)与过滤器(Filter)的区别、Spring Boot自动配置原理与@Conditional条件装配、自定义Starter的开发流程等，构建Spring Web层的完整知识体系。敬请期待！🦐

---

*本系列持续更新中，欢迎关注公众号获取最新文章。*
