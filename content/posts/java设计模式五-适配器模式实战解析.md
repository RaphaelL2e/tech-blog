---
title: "Java设计模式（五）：适配器模式实战解析"
date: 2026-04-13T16:40:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "适配器模式", "adapter"]
---

## 前言

前四篇文章我们介绍了单例模式、工厂模式、建造者模式和原型模式，今天继续 Java 设计模式系列。**适配器模式（Adapter Pattern）** 是结构型模式中的核心成员，用于解决接口不兼容的问题。

**核心思想**：将一个类的接口转换成客户期望的另一个接口，使原本接口不兼容的类可以一起工作。

<!--more-->

## 一、为什么需要适配器模式

### 1.1 接口不兼容问题

```java
// 场景：旧的支付接口
public interface OldPayment {
    void payByCard(String cardNumber, double amount);
}

// 新的支付接口
public interface NewPayment {
    void pay(String userId, double amount);
}

// 第三方支付 SDK
public class ThirdPartyPay {
    public void payWithAli(String token, double amount) {
        // 支付宝支付
    }
}

// 问题：旧系统和新系统接口不一致，无法直接使用
```

### 1.2 解决方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| 修改源代码 | 简单直接 | 破坏开闭原则，可能影响现有功能 |
| 继承转换 | 不修改原类 | 类层次复杂，单继承限制 |
| 适配器模式 | 解耦、灵活、可复用 | 略微增加系统复杂度 |

## 二、适配器模式的三种实现

### 2.1 类适配器（Class Adapter）

**通过继承实现**：

```java
// 目标接口（客户端期望的接口）
public interface Target {
    void request();
}

// 需要适配的类（被适配者）
public class Adaptee {
    public void specificRequest() {
        System.out.println("Adaptee 的特殊方法");
    }
}

// 类适配器：继承 Adaptee，实现 Target
public class ClassAdapter extends Adaptee implements Target {
    
    @Override
    public void request() {
        System.out.println("ClassAdapter: 转换中...");
        // 调用被适配者的方法
        this.specificRequest();
    }
}

// 客户端
public class Client {
    public static void main(String[] args) {
        Target target = new ClassAdapter();
        target.request();
    }
}
```

**UML 图**：

```
┌─────────────────┐         ┌─────────────────┐
│     Client      │         │    <<interface>>│
│                 │────────▶│     Target      │
└─────────────────┘         ├─────────────────┤
                             │ + request()    │
                             └────────┬────────┘
                                      │ implements
                                      │ (implements)
                                      │
┌─────────────────┐                   │
│   Adaptee       │                   │
├─────────────────┤                   │
│ + specific()   │◀─── extends ──────┘
└─────────────────┘
        ▲
        │
        │ extends
        │
┌───────┴─────────┐
│  ClassAdapter   │
├──────────────────┤
│ + request()      │
└──────────────────┘
```

**特点**：
- 使用继承，代码简洁
- 可以重写被适配者的方法
- 但 Java 单继承，限制较大

### 2.2 对象适配器（Object Adapter）

**通过组合实现**：

```java
// 目标接口
public interface Target {
    void request();
}

// 被适配者
public class Adaptee {
    public void specificRequest() {
        System.out.println("Adaptee 的特殊方法");
    }
}

// 对象适配器：组合 Adaptee
public class ObjectAdapter implements Target {
    
    private Adaptee adaptee;
    
    public ObjectAdapter(Adaptee adaptee) {
        this.adaptee = adaptee;
    }
    
    @Override
    public void request() {
        System.out.println("ObjectAdapter: 转换中...");
        // 委托给被适配者
        adaptee.specificRequest();
    }
}

// 客户端
public class Client {
    public static void main(String[] args) {
        Adaptee adaptee = new Adaptee();
        Target target = new ObjectAdapter(adaptee);
        target.request();
    }
}
```

**UML 图**：

```
┌─────────────────┐         ┌─────────────────┐
│     Client      │         │    <<interface>>│
│                 │────────▶│     Target      │
└─────────────────┘         ├─────────────────┤
                             │ + request()    │
                             └────────┬────────┘
                                      │ implements
                                      │
                             ┌────────┴────────┐
                             │  ObjectAdapter │
                             ├────────────────┤
                             │ - adaptee      │
                             ├────────────────┤
                             │ + request()    │
                             └───────┬────────┘
                                     │ uses
                                     ▼
                             ┌───────────────┐
                             │   Adaptee     │
                             ├───────────────┤
                             │+specific()   │
                             └───────────────┘
```

**特点**：
- 使用组合，灵活度高
- 可以适配被适配者的所有子类
- 更符合组合优先原则

### 2.3 接口适配器（Interface Adapter）

**当接口方法太多，只需使用其中一部分时**：

```java
// 大量方法的接口
public interface FullInterface {
    void method1();
    void method2();
    void method3();
    void method4();
    void method5();
}

// 抽象适配器：空实现所有方法
public abstract class InterfaceAdapter implements FullInterface {
    
    @Override
    public void method1() {}
    
    @Override
    public void method2() {}
    
    @Override
    public void method3() {}
    
    @Override
    public void method4() {}
    
    @Override
    public void method5() {}
}

// 使用：只关心 method2 和 method4
public class MyAdapter extends InterfaceAdapter {
    
    @Override
    public void method2() {
        System.out.println("处理 method2");
    }
    
    @Override
    public void method4() {
        System.out.println("处理 method4");
    }
}
```

**Spring MVC 中的应用**：

```java
// HandlerAdapter 接口
public interface HandlerAdapter {
    boolean supports(Object handler);
    ModelAndView handle(HttpServletRequest request, 
                        HttpServletResponse response, 
                        Object handler) throws Exception;
}

// Spring 提供了多个适配器实现
// - SimpleServletHandlerAdapter
// - HttpRequestHandlerAdapter
// - RequestMappingHandlerAdapter
// - AnnotationMethodHandlerAdapter
```

## 三、实战案例

### 3.1 支付通道适配

```java
// 目标接口（系统内部使用的支付接口）
public interface PaymentGateway {
    /**
     * 统一支付接口
     * @param userId 用户ID
     * @param amount 金额
     * @param channel 支付渠道（alipay/wechat）
     */
    PayResult pay(String userId, double amount, String channel);
}

// 支付结果
public class PayResult {
    private String orderId;
    private String status;
    private String message;
    
    // getters and setters
}

// 支付宝 SDK（第三方）
public class AlipaySDK {
    public String trade(String token, double amount) {
        // 返回支付链接或 token
        return "alipay://trade?amount=" + amount;
    }
    
    public boolean verify(String token) {
        return true;
    }
}

// 微信支付 SDK（第三方）
public class WechatPaySDK {
    public String unifiedOrder(String openId, int fee) {
        // 返回 prepay_id
        return "wechat://unifiedorder?fee=" + fee;
    }
}

// 支付宝适配器
public class AlipayAdapter implements PaymentGateway {
    
    private AlipaySDK alipaySDK;
    
    public AlipayAdapter(AlipaySDK alipaySDK) {
        this.alipaySDK = alipaySDK;
    }
    
    @Override
    public PayResult pay(String userId, double amount, String channel) {
        if (!"alipay".equals(channel)) {
            return new PayResult(null, "FAILED", "渠道不匹配");
        }
        
        try {
            // 调用支付宝 SDK
            String token = alipaySDK.trade(userId, amount);
            
            // 转换结果
            PayResult result = new PayResult();
            result.setOrderId(token);
            result.setStatus("SUCCESS");
            result.setMessage("支付宝支付成功");
            return result;
        } catch (Exception e) {
            PayResult result = new PayResult();
            result.setStatus("FAILED");
            result.setMessage(e.getMessage());
            return result;
        }
    }
}

// 微信支付适配器
public class WechatPayAdapter implements PaymentGateway {
    
    private WechatPaySDK wechatPaySDK;
    
    public WechatPayAdapter(WechatPaySDK wechatPaySDK) {
        this.wechatPaySDK = wechatPaySDK;
    }
    
    @Override
    public PayResult pay(String userId, double amount, String channel) {
        if (!"wechat".equals(channel)) {
            return new PayResult(null, "FAILED", "渠道不匹配");
        }
        
        try {
            // 金额转换为分
            int feeYuan = (int)(amount * 100);
            
            // 调用微信支付 SDK
            String prepayId = wechatPaySDK.unifiedOrder(userId, feeYuan);
            
            // 转换结果
            PayResult result = new PayResult();
            result.setOrderId(prepayId);
            result.setStatus("SUCCESS");
            result.setMessage("微信支付成功");
            return result;
        } catch (Exception e) {
            PayResult result = new PayResult();
            result.setStatus("FAILED");
            result.setMessage(e.getMessage());
            return result;
        }
    }
}

// 适配器工厂
public class PaymentAdapterFactory {
    
    private static final Map<String, PaymentGateway> ADAPTERS = new HashMap<>();
    
    static {
        ADAPTERS.put("alipay", new AlipayAdapter(new AlipaySDK()));
        ADAPTERS.put("wechat", new WechatPayAdapter(new WechatPaySDK()));
    }
    
    public static PaymentGateway getAdapter(String channel) {
        PaymentGateway adapter = ADAPTERS.get(channel);
        if (adapter == null) {
            throw new IllegalArgumentException("不支持的支付渠道: " + channel);
        }
        return adapter;
    }
}

// 客户端使用
public class OrderService {
    
    public PayResult pay(String userId, double amount, String channel) {
        PaymentGateway gateway = PaymentAdapterFactory.getAdapter(channel);
        return gateway.pay(userId, amount, channel);
    }
    
    public static void main(String[] args) {
        OrderService service = new OrderService();
        
        // 支付宝支付
        PayResult alipayResult = service.pay("user_001", 100.0, "alipay");
        System.out.println("支付宝: " + alipayResult.getStatus());
        
        // 微信支付
        PayResult wechatResult = service.pay("user_002", 200.0, "wechat");
        System.out.println("微信: " + wechatResult.getStatus());
    }
}
```

### 3.2 日志框架适配

```java
// 统一的日志接口
public interface Logger {
    void info(String message);
    void warn(String message);
    void error(String message);
}

// Slf4j（内部使用）
public class Slf4jLogger implements Logger {
    private org.slf4j.Logger logger;
    
    public Slf4jLogger(String name) {
        this.logger = org.slf4j.LoggerFactory.getLogger(name);
    }
    
    @Override
    public void info(String message) {
        logger.info(message);
    }
    
    @Override
    public void warn(String message) {
        logger.warn(message);
    }
    
    @Override
    public void error(String message) {
        logger.error(message);
    }
}

// Log4j 适配器（遗留系统）
public class Log4jAdapter implements Logger {
    private org.apache.log4j.Logger logger;
    
    public Log4jAdapter(String name) {
        this.logger = org.apache.log4j.Logger.getLogger(name);
    }
    
    @Override
    public void info(String message) {
        logger.info(message);
    }
    
    @Override
    public void warn(String message) {
        logger.warn(message);
    }
    
    @Override
    public void error(String message) {
        logger.error(message);
    }
}

// JDK Logging 适配器
public class JdkLogAdapter implements Logger {
    private java.util.logging.Logger logger;
    
    public JdkLogAdapter(String name) {
        this.logger = java.util.logging.Logger.getLogger(name);
    }
    
    @Override
    public void info(String message) {
        logger.log(Level.INFO, message);
    }
    
    @Override
    public void warn(String message) {
        logger.log(Level.WARNING, message);
    }
    
    @Override
    public void error(String message) {
        logger.log(Level.SEVERE, message);
    }
}
```

### 3.3 数据格式适配

```java
// 系统内部使用的数据格式
public interface DataProcessor {
    UserData process(String jsonData);
}

// 用户数据
public class UserData {
    private String userId;
    private String userName;
    private int age;
    // getters and setters
}

// 第三方 API 返回的 XML 格式
public class ThirdPartyXMLAPI {
    public String getUserXML(String userId) {
        return "<?xml version=\"1.0\"?>" +
               "<user>" +
               "<uid>" + userId + "</uid>" +
               "<name>张三</name>" +
               "<age>25</age>" +
               "</user>";
    }
}

// XML 适配器
public class XMLDataAdapter implements DataProcessor {
    
    private ThirdPartyXMLAPI xmlAPI;
    
    public XMLDataAdapter(ThirdPartyXMLAPI xmlAPI) {
        this.xmlAPI = xmlAPI;
    }
    
    @Override
    public UserData process(String userId) {
        // 调用第三方 API
        String xml = xmlAPI.getUserXML(userId);
        
        // 解析 XML
        return parseXML(xml);
    }
    
    private UserData parseXML(String xml) {
        UserData user = new UserData();
        // 简化解析逻辑
        user.setUserId(extract(xml, "uid"));
        user.setUserName(extract(xml, "name"));
        user.setAge(Integer.parseInt(extract(xml, "age")));
        return user;
    }
    
    private String extract(String xml, String tag) {
        String startTag = "<" + tag + ">";
        String endTag = "</" + tag + ">";
        int start = xml.indexOf(startTag) + startTag.length();
        int end = xml.indexOf(endTag);
        return xml.substring(start, end);
    }
}
```

## 四、JDK/框架中的适配器模式

### 4.1 JDK 中的适配器

**InputStreamReader**：

```java
// InputStreamReader 是字节流到字符流的适配器
InputStreamReader reader = new InputStreamReader(
    new FileInputStream("file.txt"),
    "UTF-8"
);

// 底层原理
public class InputStreamReader extends Reader {
    private final StreamDecoder sd;  // 适配器
    
    public InputStreamReader(InputStream in, Charset charset) {
        super(sd = StreamDecoder.getDecoder(charset, -1));
        // 将 InputStream 适配为 Reader
    }
    
    @Override
    public int read() throws IOException {
        return sd.read();
    }
}
```

**OutputStreamWriter**：

```java
// OutputStreamWriter 是字符流到字节流的适配器
OutputStreamWriter writer = new OutputStreamWriter(
    new FileOutputStream("file.txt"),
    "UTF-8"
);
```

**Arrays.asList()**：

```java
// Arrays.asList 是数组到 List 的适配
String[] array = {"A", "B", "C"};
List<String> list = Arrays.asList(array);

// 内部返回的是 Arrays 的内部类 ArrayList
// 而不是 java.util.ArrayList
```

### 4.2 Spring 中的适配器

**HandlerAdapter**：

```java
// Spring MVC 的核心适配器接口
public interface HandlerAdapter {
    boolean supports(Object handler);
    ModelAndView handle(HttpServletRequest request, 
                        HttpServletResponse response, 
                        Object handler) throws Exception;
}

// 具体适配器实现
public class RequestMappingHandlerAdapter implements HandlerAdapter {
    
    @Override
    public boolean supports(Object handler) {
        return handler instanceof HandlerMethod;
    }
    
    @Override
    public ModelAndView handle(HttpServletRequest request, 
                               HttpServletResponse response,
                               Object handler) throws Exception {
        HandlerMethod handlerMethod = (HandlerMethod) handler;
        // 执行控制器方法
        return invokeHandlerMethod(request, response, handlerMethod);
    }
}
```

**Spring Security 的认证适配器**：

```java
// UserDetailsService 是适配器的目标接口
public interface UserDetailsService {
    UserDetails loadUserByUsername(String username) 
        throws UsernameNotFoundException;
}

// 自定义适配器
public class CustomUserDetailsAdapter implements UserDetailsService {
    
    private UserService userService;
    
    @Override
    public UserDetails loadUserByUsername(String username) {
        CustomUser user = userService.findByUsername(username);
        // 转换并返回 Spring Security 需要的 UserDetails
        return new org.springframework.security.core.userdetails.User(
            user.getUsername(),
            user.getPassword(),
            authorities
        );
    }
}
```

### 4.3 MyBatis 中的适配器

**Log 适配器**：

```java
// MyBatis 支持多种日志框架，通过适配器统一
public interface Log {
    boolean isDebugEnabled();
    void error(String s, Throwable e);
    void debug(String s);
}

// Log4j2 适配器
public class Log4j2Impl implements Log {
    private org.apache.logging.log4j.Logger logger;
    
    public Log4j2Impl(String logger) {
        this.logger = org.apache.logging.log4j.LogManager.getLogger(logger);
    }
    
    @Override
    public boolean isDebugEnabled() {
        return logger.isDebugEnabled();
    }
    
    @Override
    public void error(String s, Throwable e) {
        logger.error(s, e);
    }
    
    @Override
    public void debug(String s) {
        logger.debug(s);
    }
}
```

## 五、适配器模式 vs 装饰器模式 vs 代理模式

### 5.1 区别对比

| 维度 | 适配器模式 | 装饰器模式 | 代理模式 |
|------|-----------|-----------|----------|
| **目的** | 接口转换 | 功能增强 | 访问控制 |
| **接口变化** | 转换已有接口 | 保持接口一致 | 保持接口一致 |
| **时机** | 事后适配 | 运行时装饰 | 编译时确定 |
| **新接口** | 暴露目标接口 | 增强原接口 | 代理原接口 |
| **典型应用** | 兼容旧接口 | IO 流包装 | AOP、延迟加载 |

### 5.2 UML 对比

```
适配器模式：
Client ──▶ Target ──▶ Adapter ──▶ Adaptee
                        (转换)

装饰器模式：
Client ──▶ Component ◀──Decorator◀──ConcreteDecorator
                     ▲
               ──────┘
              (包装)

代理模式：
Client ──▶ Subject ◀──Proxy◀──RealSubject
                     (委托)
```

### 5.3 代码对比

```java
// 适配器：接口转换
public class Adapter implements Target {
    private Adaptee adaptee;
    
    public void request() {
        // 转换调用
        adaptee.specificRequest();
    }
}

// 装饰器：功能增强
public class Decorator implements Component {
    private Component component;
    
    public Decorator(Component component) {
        this.component = component;
    }
    
    public void operation() {
        // 增强功能
        beforeOperation();
        component.operation();
        afterOperation();
    }
}

// 代理：访问控制
public class Proxy implements Subject {
    private RealSubject realSubject;
    
    public void request() {
        if (checkAccess()) {
            realSubject.request();
        }
    }
}
```

## 六、双向适配器

### 6.1 概念

同时实现两个接口，可以在两个方向上进行适配：

```java
// 目标接口 A
public interface TargetA {
    void methodA();
}

// 目标接口 B
public interface TargetB {
    void methodB();
}

// 被适配者
public class Adaptee {
    public void specificMethod() {
        System.out.println("Adaptee 的方法");
    }
}

// 双向适配器
public class BidirectionalAdapter implements TargetA, TargetB {
    
    private Adaptee adaptee;
    
    public BidirectionalAdapter(Adaptee adaptee) {
        this.adaptee = adaptee;
    }
    
    // 适配 TargetA -> Adaptee
    @Override
    public void methodA() {
        System.out.println("适配 methodA -> specificMethod");
        adaptee.specificMethod();
    }
    
    // 适配 TargetB -> Adaptee
    @Override
    public void methodB() {
        System.out.println("适配 methodB -> specificMethod");
        adaptee.specificMethod();
    }
}

// 使用
public class Client {
    public static void main(String[] args) {
        Adaptee adaptee = new Adaptee();
        BidirectionalAdapter adapter = new BidirectionalAdapter(adaptee);
        
        // 当作 TargetA 使用
        TargetA targetA = adapter;
        targetA.methodA();
        
        // 当作 TargetB 使用
        TargetB targetB = adapter;
        targetB.methodB();
    }
}
```

## 七、适配器模式的优缺点

### 7.1 优点

1. **单一职责**：将接口转换逻辑分离
2. **开闭原则**：可以在不修改原有代码的情况下添加适配器
3. **复用性**：现有的类无需修改即可复用
4. **解耦**：客户端与被适配者解耦

### 7.2 缺点

1. **增加复杂度**：引入适配器会增加系统复杂度
2. **性能损失**：每次调用都经过适配器，可能有少量性能损失
3. **过度使用**：滥用适配器可能导致系统难以理解

## 八、最佳实践

### 8.1 何时使用适配器

- 需要使用已有类，但接口不兼容
- 需要统一多个类的接口
- 需要使用第三方类库，但不想修改源代码
- 系统需要支持多种数据源或服务

### 8.2 模式选择建议

```
接口不兼容，需要转换          接口一致，需要增强
        │                            │
        ▼                            ▼
   适配器模式                  装饰器模式

需要访问控制或延迟加载
        │
        ▼
   代理模式
```

### 8.3 命名建议

```java
// 适配器命名规范
public class XxxAdapter implements TargetInterface {
    // Adapter 后缀表示这是适配器
}

public class XxxWrapper implements TargetInterface {
    // Wrapper 后缀表示这是包装类
}

// 组合使用
public class XxxAdapterWrapper extends Adaptee implements TargetInterface {
    // 既适配又增强
}
```

## 九、面试常见问题

### Q1：适配器模式和装饰器模式的区别？

- **适配器**：改变接口，使不兼容变得兼容
- **装饰器**：保持接口，增加功能

### Q2：类适配器和对象适配器如何选择？

| 场景 | 推荐方式 |
|------|----------|
| 需要重写被适配者的方法 | 类适配器 |
| 需要适配被适配者的子类 | 对象适配器 |
| Java 单继承限制 | 对象适配器 |

### Q3：适配器模式在 Spring 中有哪些应用？

- **HandlerAdapter**：适配不同的处理器
- **DataSource**：适配不同的数据库连接
- **ViewResolver**：适配不同的视图模板
- **MessageConverter**：适配不同的消息格式

### Q4：适配器模式的实际应用场景？

1. 集成第三方 SDK
2. 兼容遗留系统
3. 统一不同数据源接口
4. 日志框架统一
5. 支付通道集成

## 十、总结

### 10.1 模式对比

```
结构型模式对比：
┌────────────┬──────────────────────────────────────┐
│   模式      │ 目的                                  │
├────────────┼──────────────────────────────────────┤
│ 适配器模式  │ 接口转换，使不兼容变兼容              │
│ 装饰器模式  │ 功能增强，保持接口一致                │
│ 代理模式   │ 访问控制，不改变接口                   │
│ 外观模式   │ 简化接口，提供统一入口                  │
│ 组合模式   │ 树形结构，统一对待个体和整体           │
└────────────┴──────────────────────────────────────┘
```

### 10.2 核心要点

1. **适配器**：转换接口，不是改变功能
2. **对象适配器**更灵活，类适配器更简洁
3. **适配器工厂**可以统一管理多种适配器
4. **适配器**是一种"事后补救"的模式

## 结语

适配器模式是解决接口不兼容问题的利器，在集成第三方库、兼容遗留系统、统一不同接口等场景中广泛应用。掌握适配器模式，能够让我们的系统更加灵活和可扩展。

**下期预告**：装饰器模式（Decorator Pattern）

> 记住：**适配器不是改造，是适配**。
