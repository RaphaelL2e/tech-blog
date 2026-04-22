---
title: "Java设计模式（十七）：代理模式深度实践"
date: 2026-04-22T10:30:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "代理模式", "proxy", "动态代理", "AOP"]
---

## 前言

代理模式（Proxy Pattern）是一种结构型设计模式，它的核心思想是：**为其他对象提供一种代理以控制对这个对象的访问**。

**核心思想**：在客户端和目标对象之间增加一层间接层，以控制访问、增强功能或延迟加载。

<!--more-->

## 一、为什么需要代理模式

### 1.1 直接访问的局限

假设我们有一个远程服务接口，直接调用存在以下问题：

- 网络延迟大，需要缓存
- 调用需要权限校验
- 对象创建开销大，需要延迟加载
- 需要记录调用日志

如果直接修改目标对象，会污染业务逻辑。代理模式通过引入代理对象，在不修改目标对象的前提下增强其功能。

### 1.2 代理模式的本质

代理模式的本质是**控制访问**——代理对象控制客户端对目标对象的访问，可以在调用前后添加额外逻辑。

## 二、代理模式的结构

### 2.1 类图

```
┌────────────────────┐
│    Subject (接口)   │
│────────────────────│
│ + request()        │
└────────┬───────────┘
         │
    ┌────┴────┐
    │         │
┌───┴─────┐ ┌─┴──────────┐
│RealSubj │ │   Proxy    │
│(真实对象)│ │  (代理对象) │
│─────────│ │────────────│
│request()│ │ realSubject│
│         │ │ request()  │
└─────────┘ └────────────┘
                 │
                 └───> RealSubject
```

### 2.2 代理类型

| 类型 | 用途 | 示例 |
|------|------|------|
| 远程代理 | 隐藏对象位于不同地址空间的事实 | RPC、RMI |
| 虚拟代理 | 延迟创建开销大的对象 | 图片懒加载 |
| 保护代理 | 控制对原始对象的访问权限 | 权限校验 |
| 智能引用代理 | 在访问对象时执行额外操作 | 引用计数、日志 |
| 缓存代理 | 为开销大的运算结果提供缓存 | API 响应缓存 |

### 2.3 完整实现（静态代理）

```java
// ========== 1. 抽象主题 ==========
public interface Image {
    void display();
    String getName();
}

// ========== 2. 真实主题 ==========
public class RealImage implements Image {
    private final String name;
    
    public RealImage(String name) {
        this.name = name;
        loadFromDisk();  // 构造时加载，开销大
    }
    
    private void loadFromDisk() {
        System.out.println("💾 从磁盘加载图片: " + name + " (耗时操作)");
        try { Thread.sleep(1000); } catch (InterruptedException e) { }
    }
    
    @Override
    public void display() {
        System.out.println("🖼️ 显示图片: " + name);
    }
    
    @Override
    public String getName() { return name; }
}

// ========== 3. 虚拟代理：延迟加载 ==========
public class ImageProxy implements Image {
    private final String name;
    private RealImage realImage;  // 延迟到第一次使用时创建
    
    public ImageProxy(String name) {
        this.name = name;
    }
    
    @Override
    public void display() {
        if (realImage == null) {
            realImage = new RealImage(name);  // 第一次调用时才加载
        }
        realImage.display();
    }
    
    @Override
    public String getName() { return name; }
}

// ========== 4. 保护代理：权限校验 ==========
public class ProtectedImageProxy implements Image {
    private final Image image;
    private final String requiredRole;
    private final String currentUserRole;
    
    public ProtectedImageProxy(Image image, String requiredRole, String currentUserRole) {
        this.image = image;
        this.requiredRole = requiredRole;
        this.currentUserRole = currentUserRole;
    }
    
    @Override
    public void display() {
        if (!requiredRole.equals(currentUserRole)) {
            System.out.println("🚫 权限不足：需要 " + requiredRole + " 角色，当前 " + currentUserRole);
            return;
        }
        image.display();
    }
    
    @Override
    public String getName() { return image.getName(); }
}

// ========== 5. 缓存代理 ==========
public class CachedImageProxy implements Image {
    private final Image image;
    private boolean cached = false;
    
    public CachedImageProxy(Image image) {
        this.image = image;
    }
    
    @Override
    public void display() {
        if (!cached) {
            image.display();
            cached = true;
        } else {
            System.out.println("📦 从缓存显示图片: " + image.getName());
        }
    }
    
    @Override
    public String getName() { return image.getName(); }
}

// ========== 6. 客户端 ==========
public class ImageDemo {
    public static void main(String[] args) {
        // 虚拟代理：延迟加载
        System.out.println("=== 虚拟代理 ===");
        Image image1 = new ImageProxy("photo.jpg");
        System.out.println("图片代理已创建（图片未加载）");
        image1.display();  // 第一次调用，触发加载
        image1.display();  // 第二次调用，直接显示
        
        // 保护代理
        System.out.println("\n=== 保护代理 ===");
        Image realImage = new RealImage("secret.png");
        Image protectedProxy = new ProtectedImageProxy(realImage, "admin", "guest");
        protectedProxy.display();  // 权限不足
        Image adminProxy = new ProtectedImageProxy(realImage, "admin", "admin");
        adminProxy.display();  // 权限通过
        
        // 缓存代理
        System.out.println("\n=== 缓存代理 ===");
        Image cachedProxy = new CachedImageProxy(new ImageProxy("large.jpg"));
        cachedProxy.display();  // 首次：加载+显示
        cachedProxy.display();  // 再次：从缓存
    }
}
```

## 三、JDK 动态代理

### 3.1 静态代理的局限

静态代理需要为每个接口编写代理类，接口方法增多时维护成本高。JDK 动态代理通过反射在运行时生成代理类，解决了这个问题。

### 3.2 JDK 动态代理核心 API

```java
// 核心：Proxy.newProxyInstance
public static Object newProxyInstance(
    ClassLoader loader,       // 类加载器
    Class<?>[] interfaces,    // 代理接口
    InvocationHandler h       // 调用处理器
)
```

### 3.3 完整实现

```java
// ========== 1. 业务接口 ==========
public interface UserService {
    String getUser(String userId);
    void createUser(String userId, String name);
    void deleteUser(String userId);
}

// ========== 2. 真实对象 ==========
public class UserServiceImpl implements UserService {
    @Override
    public String getUser(String userId) {
        System.out.println("  → 查询用户: " + userId);
        return "User{name='张三', id='" + userId + "'}";
    }
    
    @Override
    public void createUser(String userId, String name) {
        System.out.println("  → 创建用户: " + userId + ", " + name);
    }
    
    @Override
    public void deleteUser(String userId) {
        System.out.println("  → 删除用户: " + userId);
    }
}

// ========== 3. 日志调用处理器 ==========
public class LoggingHandler implements InvocationHandler {
    private final Object target;
    
    public LoggingHandler(Object target) {
        this.target = target;
    }
    
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        // 前置增强
        System.out.println("📝 [LOG] 调用 " + method.getName() + 
            " 参数: " + Arrays.toString(args));
        
        long start = System.currentTimeMillis();
        
        try {
            // 执行目标方法
            Object result = method.invoke(target, args);
            
            // 后置增强
            long elapsed = System.currentTimeMillis() - start;
            System.out.println("📝 [LOG] " + method.getName() + 
                " 返回: " + result + " 耗时: " + elapsed + "ms");
            
            return result;
        } catch (InvocationTargetException e) {
            // 异常增强
            System.out.println("📝 [LOG] " + method.getName() + 
                " 异常: " + e.getTargetException().getMessage());
            throw e.getTargetException();
        }
    }
}

// ========== 4. 权限校验处理器 ==========
public class AuthHandler implements InvocationHandler {
    private final Object target;
    private final String role;
    
    public AuthHandler(Object target, String role) {
        this.target = target;
        this.role = role;
    }
    
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        // 对 delete 方法做权限校验
        if (method.getName().startsWith("delete") && !"admin".equals(role)) {
            throw new SecurityException("只有 admin 才能执行 " + method.getName());
        }
        return method.invoke(target, args);
    }
}

// ========== 5. 代理工厂 ==========
public class ProxyFactory {
    @SuppressWarnings("unchecked")
    public static <T> T createProxy(T target, InvocationHandler handler) {
        return (T) Proxy.newProxyInstance(
            target.getClass().getClassLoader(),
            target.getClass().getInterfaces(),
            handler
        );
    }
    
    // 链式代理：多层代理叠加
    public static <T> T createChainedProxy(T target, InvocationHandler... handlers) {
        Object proxy = target;
        // 从后向前包装
        for (int i = handlers.length - 1; i >= 0; i--) {
            final Object currentTarget = proxy;
            final InvocationHandler handler = handlers[i];
            proxy = Proxy.newProxyInstance(
                target.getClass().getClassLoader(),
                target.getClass().getInterfaces(),
                (proxyObj, method, args) -> {
                    // 委托给 handler，但替换 target
                    Method invokeMethod = handler.getClass().getMethod(
                        "invoke", Object.class, Method.class, Object[].class);
                    return invokeMethod.invoke(handler, 
                        new Object[]{proxyObj, method, args});
                }
            );
        }
        return (T) proxy;
    }
}

// ========== 6. 客户端 ==========
public class DynamicProxyDemo {
    public static void main(String[] args) {
        UserService realService = new UserServiceImpl();
        
        // 日志代理
        UserService loggedService = ProxyFactory.createProxy(
            realService, new LoggingHandler(realService));
        
        loggedService.getUser("001");
        loggedService.createUser("002", "李四");
        
        // 权限代理
        System.out.println("\n=== 权限代理 ===");
        UserService adminService = ProxyFactory.createProxy(
            realService, new AuthHandler(realService, "admin"));
        adminService.deleteUser("001");  // 成功
        
        UserService guestService = ProxyFactory.createProxy(
            realService, new AuthHandler(realService, "guest"));
        try {
            guestService.deleteUser("001");  // 抛异常
        } catch (SecurityException e) {
            System.out.println("🚫 " + e.getMessage());
        }
    }
}
```

运行结果：

```
📝 [LOG] 调用 getUser 参数: [001]
  → 查询用户: 001
📝 [LOG] getUser 返回: User{name='张三', id='001'} 耗时: 0ms
📝 [LOG] 调用 createUser 参数: [002, 李四]
  → 创建用户: 002, 李四
📝 [LOG] createUser 返回: null 耗时: 0ms

=== 权限代理 ===
  → 删除用户: 001
🚫 只有 admin 才能执行 deleteUser
```

## 四、CGLIB 动态代理

### 4.1 JDK 动态代理 vs CGLIB

| 维度 | JDK 动态代理 | CGLIB |
|------|-------------|-------|
| 机制 | 基于接口 | 基于继承 |
| 要求 | 目标必须实现接口 | 目标类不能是 final |
| 性能 | 生成快，调用稍慢 | 生成慢，调用快 |
| 使用 | JDK 内置 | 需要额外依赖 |

### 4.2 CGLIB 实现

```java
// CGLIB 代理：不需要接口
public class CGLIBProxyDemo {
    public static void main(String[] args) {
        Enhancer enhancer = new Enhancer();
        enhancer.setSuperclass(UserServiceImpl.class);  // 继承目标类
        enhancer.setCallback(new MethodInterceptor() {
            @Override
            public Object intercept(Object obj, Method method, Object[] args, 
                                    MethodProxy proxy) throws Throwable {
                System.out.println("📝 [CGLIB] 调用: " + method.getName());
                Object result = proxy.invokeSuper(obj, args);  // 调用父类方法
                System.out.println("📝 [CGLIB] 返回: " + result);
                return result;
            }
        });
        
        UserServiceImpl proxy = (UserServiceImpl) enhancer.create();
        proxy.getUser("001");
    }
}
```

## 五、代理模式在 JDK 中的应用

### 5.1 java.lang.reflect.Proxy

JDK 动态代理的核心类：

```java
// Proxy 源码核心
public class Proxy implements Serializable {
    protected InvocationHandler h;
    
    public static Object newProxyInstance(ClassLoader loader,
                                          Class<?>[] interfaces,
                                          InvocationHandler h) {
        // 1. 生成代理类的字节码
        Class<?> cl = getProxyClass0(loader, interfaces);
        
        // 2. 通过反射创建代理实例
        try {
            Constructor<?> cons = cl.getConstructor(InvocationHandler.class);
            return cons.newInstance(h);
        } catch (...) { ... }
    }
}
```

### 5.2 RMI 远程代理

Java RMI 是远程代理的经典实现：

```java
// 服务端
public interface RemoteService extends Remote {
    String hello(String name) throws RemoteException;
}

public class RemoteServiceImpl extends UnicastRemoteObject implements RemoteService {
    @Override
    public String hello(String name) {
        return "Hello, " + name + "!";
    }
}

// 客户端通过代理访问远程对象
RemoteService service = (RemoteService) Naming.lookup("rmi://localhost:1099/RemoteService");
String result = service.hello("World");  // 实际调用远程方法
```

## 六、代理模式在 Spring 中的应用

### 6.1 AOP 代理

Spring AOP 是代理模式最经典的应用：

```java
// 自定义注解
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface LogExecutionTime {
}

// 切面
@Aspect
@Component
public class LoggingAspect {
    
    @Around("@annotation(LogExecutionTime)")
    public Object logExecutionTime(ProceedingJoinPoint joinPoint) throws Throwable {
        long start = System.currentTimeMillis();
        
        Object result = joinPoint.proceed();  // 执行目标方法
        
        long elapsed = System.currentTimeMillis() - start;
        System.out.println("⏱️ " + joinPoint.getSignature() + " 耗时: " + elapsed + "ms");
        return result;
    }
}

// 使用
@Service
public class OrderService {
    @LogExecutionTime
    public Order createOrder(String productId) {
        // 业务逻辑
        return new Order(productId);
    }
}
```

Spring AOP 代理创建过程：

```java
// Spring 内部：根据目标类选择代理策略
public class DefaultAopProxyFactory implements AopProxyFactory {
    @Override
    public AopProxy createAopProxy(AdvisedSupport config) {
        if (config.isOptimize() || config.isProxyTargetClass() || 
            hasNoUserSuppliedProxyInterfaces(config)) {
            Class<?> targetClass = config.getTargetClass();
            if (targetClass.isInterface() || Proxy.isProxyClass(targetClass)) {
                return new JdkDynamicAopProxy(config);   // JDK 动态代理
            }
            return new ObjenesisCglibAopProxy(config);   // CGLIB 代理
        } else {
            return new JdkDynamicAopProxy(config);       // JDK 动态代理
        }
    }
}
```

### 6.2 事务代理

```java
// @Transactional 背后就是代理模式
@Service
public class AccountService {
    @Transactional
    public void transfer(String from, String to, BigDecimal amount) {
        // Spring 代理在方法前后添加：
        // 前置：开启事务
        // 正常返回：提交事务
        // 异常：回滚事务
        accountDao.debit(from, amount);
        accountDao.credit(to, amount);
    }
}
```

### 6.3 缓存代理

```java
// @Cacheable 背后也是代理模式
@Service
public class ProductService {
    @Cacheable(value = "products", key = "#id")
    public Product getProduct(Long id) {
        // 代理先查缓存，命中则直接返回
        // 未命中则执行方法，将结果放入缓存
        return productDao.findById(id);
    }
}
```

## 七、代理模式 vs 其他模式

### 7.1 对比装饰器模式

| 维度 | 代理模式 | 装饰器模式 |
|------|---------|-----------|
| 目的 | 控制访问 | 增强功能 |
| 对象创建 | 代理控制目标对象的创建 | 装饰器由客户端创建 |
| 接口 | 与目标接口相同 | 与被装饰者接口相同 |
| 关系 | 代理知道真实对象 | 装饰器不知道具体被装饰者 |

### 7.2 对比适配器模式

| 维度 | 代理模式 | 适配器模式 |
|------|---------|-----------|
| 接口 | 与目标接口相同 | 转换不同接口 |
| 目的 | 控制访问 | 接口兼容 |
| 对象关系 | 代理和真实对象实现同一接口 | 适配器连接不同接口 |

## 八、代理模式的优缺点

### 优点

1. **职责清晰**：真实对象只负责业务逻辑，代理负责控制逻辑
2. **开闭原则**：可以在不修改真实对象的前提下增强功能
3. **智能引用**：延迟加载、权限校验、日志记录等
4. **远程代理**：隐藏对象位于不同地址空间的事实

### 缺点

1. **增加复杂性**：增加了代理层
2. **性能开销**：代理调用比直接调用慢
3. **静态代理维护难**：接口变化需修改代理类
4. **JDK 代理限制**：只能代理接口，不能代理类

### 适用场景

- 需要延迟创建开销大的对象（虚拟代理）
- 需要控制对对象的访问权限（保护代理）
- 需要为对象添加额外行为（智能引用代理）
- 需要访问远程对象（远程代理）
- AOP、事务、缓存等横切关注点

## 八、实战：RPC 客户端代理

用动态代理实现一个简单的 RPC 客户端：

```java
// ========== 1. 远程服务接口 ==========
public interface OrderService {
    Order getOrder(Long orderId);
    List<Order> getOrders(String userId);
    Order createOrder(String userId, String productId, int quantity);
}

public class Order {
    private Long id;
    private String userId;
    private String productId;
    private int quantity;
    
    // constructor, getters, setters...
    @Override
    public String toString() {
        return "Order{id=" + id + ", userId=" + userId + 
            ", product=" + productId + ", qty=" + quantity + "}";
    }
}

// ========== 2. RPC 请求/响应 ==========
public class RpcRequest implements Serializable {
    private String interfaceName;
    private String methodName;
    private Class<?>[] parameterTypes;
    private Object[] args;
    
    // getters, setters...
}

public class RpcResponse implements Serializable {
    private boolean success;
    private Object result;
    private String error;
    
    // getters, setters...
}

// ========== 3. RPC 代理处理器 ==========
public class RpcInvocationHandler implements InvocationHandler {
    private final String host;
    private final int port;
    
    public RpcInvocationHandler(String host, int port) {
        this.host = host;
        this.port = port;
    }
    
    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        // 构建请求
        RpcRequest request = new RpcRequest();
        request.setInterfaceName(method.getDeclaringClass().getName());
        request.setMethodName(method.getName());
        request.setParameterTypes(method.getParameterTypes());
        request.setArgs(args);
        
        System.out.println("🌐 RPC 调用: " + method.getDeclaringClass().getSimpleName() + 
            "." + method.getName() + "(" + Arrays.toString(args) + ")");
        
        // 模拟网络调用
        // 实际场景：Socket / HTTP 连接远程服务器，发送序列化请求
        RpcResponse response = sendRequest(request);
        
        if (response.isSuccess()) {
            return response.getResult();
        } else {
            throw new RuntimeException("RPC 调用失败: " + response.getError());
        }
    }
    
    private RpcResponse sendRequest(RpcRequest request) {
        // 模拟远程调用
        RpcResponse response = new RpcResponse();
        response.setSuccess(true);
        
        if ("getOrder".equals(request.getMethodName())) {
            Order order = new Order();
            order.setId((Long) request.getArgs()[0]);
            order.setUserId("user001");
            order.setProductId("PROD-001");
            order.setQuantity(2);
            response.setResult(order);
        } else if ("getOrders".equals(request.getMethodName())) {
            response.setResult(new ArrayList<>());
        }
        
        return response;
    }
}

// ========== 4. RPC 客户端工厂 ==========
public class RpcClient {
    @SuppressWarnings("unchecked")
    public static <T> T createProxy(Class<T> interfaceClass, String host, int port) {
        return (T) Proxy.newProxyInstance(
            interfaceClass.getClassLoader(),
            new Class<?>[]{interfaceClass},
            new RpcInvocationHandler(host, port)
        );
    }
}

// ========== 5. 客户端 ==========
public class RpcDemo {
    public static void main(String[] args) {
        // 像调用本地方法一样调用远程服务
        OrderService orderService = RpcClient.createProxy(
            OrderService.class, "localhost", 8080);
        
        Order order = orderService.getOrder(1L);
        System.out.println("📦 订单: " + order);
    }
}
```

运行结果：

```
🌐 RPC 调用: OrderService.getOrder([1])
📦 订单: Order{id=1, userId=user001, product=PROD-001, qty=2}
```

## 九、面试常见问题

### Q1: 代理模式的核心思想是什么？

代理模式为对象提供一个替身或占位符，以控制对这个对象的访问。代理对象在客户端和目标对象之间起到中介作用，可以在不修改目标对象的前提下添加额外的控制逻辑（如延迟加载、权限校验、日志记录等）。

### Q2: JDK 动态代理和 CGLIB 有什么区别？

JDK 动态代理基于接口，目标类必须实现接口，代理类实现相同接口并委托给 InvocationHandler。CGLIB 基于继承，通过生成目标类的子类实现代理，目标类不能是 final 类，目标方法不能是 final 方法。Spring AOP 默认使用 JDK 代理（如果有接口），否则使用 CGLIB。

### Q3: 代理模式和装饰器模式有什么区别？

代理模式关注"控制访问"，代理对象控制对真实对象的访问，客户端通常不知道真实对象的存在。装饰器模式关注"增强功能"，装饰器由客户端组合使用，客户端知道被装饰者。代理控制创建，装饰器增强行为。

### Q4: Spring AOP 是怎么使用代理模式的？

Spring AOP 在 Bean 初始化后，根据配置创建代理对象替代原始 Bean。如果目标类实现了接口，默认使用 JDK 动态代理；否则使用 CGLIB 生成子类代理。切面（@Around、@Before、@After 等）的逻辑封装在代理的 InvocationHandler/MethodInterceptor 中。

### Q5: 动态代理的性能如何？

JDK 动态代理的创建速度较快（生成字节码简单），但每次方法调用需要经过反射，性能略低于直接调用。CGLIB 的创建速度较慢（生成子类字节码复杂），但方法调用通过 FastClass 机制直接调用，性能优于 JDK 代理。对于高频调用场景，CGLIB 更有优势。

### Q6: 如何选择 JDK 代理还是 CGLIB？

- 目标类实现了接口 → 优先 JDK 代理
- 目标类没有实现接口 → 必须用 CGLIB
- 需要代理具体类的方法 → CGLIB
- Spring Boot 2.x 默认使用 CGLIB（spring.aop.proxy-target-class=true）

## 十、总结

代理模式是 Java 生态中最重要的模式之一，Spring 的 AOP、事务、缓存等核心特性都基于代理模式实现。

**核心要点**：

1. **控制访问**：代理在客户端和目标之间增加控制层
2. **多种代理**：虚拟代理、保护代理、智能引用代理各有用途
3. **动态代理**：JDK 动态代理和 CGLIB 是 Java 两大代理实现
4. **Spring AOP**：代理模式是 Spring AOP 的基石
5. **横切关注点**：日志、事务、缓存、权限等最适合用代理实现

理解代理模式，是理解 Spring 框架核心原理的钥匙。从动态代理到 AOP，从 RMI 到 RPC，代理模式无处不在。

---

**相关设计模式系列**：
- [Java设计模式（一）：单例模式完全指南](/posts/java设计模式一-单例模式完全指南/)
- [Java设计模式（二）：工厂模式深入详解](/posts/java设计模式二-工厂模式深入详解/)
- [Java设计模式（三）：建造者模式深度实践](/posts/java设计模式三-建造者模式深度实践/)
- [Java设计模式（四）：原型模式与对象克隆](/posts/java设计模式四-原型模式与对象克隆/)
- [Java设计模式（五）：适配器模式实战解析](/posts/java设计模式五-适配器模式实战解析/)
- [Java设计模式（六）：装饰器模式深入实践](/posts/java设计模式六-装饰器模式深入实践/)
- [Java设计模式（七）：观察者模式完全解析](/posts/java设计模式七-观察者模式完全解析/)
- [Java设计模式（八）：策略模式深度实践](/posts/java设计模式八-策略模式深度实践/)
- [Java设计模式（九）：模板方法模式完全指南](/posts/java设计模式九-模板方法模式完全指南/)
- [Java设计模式（十）：责任链模式深度实践](/posts/java设计模式十-责任链模式深度实践/)
- [Java设计模式（十一）：命令模式完全解析](/posts/java设计模式十一-命令模式完全解析/)
- [Java设计模式（十二）：迭代器模式深度实践](/posts/java设计模式十二-迭代器模式深度实践/)
- [Java设计模式（十三）：访问者模式深度实践](/posts/java设计模式十三-访问者模式深度实践/)
- [Java设计模式（十四）：组合模式深度实践](/posts/java设计模式十四-组合模式深度实践/)
- [Java设计模式（十五）：享元模式深度实践](/posts/java设计模式十五-享元模式深度实践/)
- [Java设计模式（十六）：外观模式实战解析](/posts/java设计模式十六-外观模式实战解析/)
