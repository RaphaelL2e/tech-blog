---
title: "Java设计模式（二）：工厂模式深入详解"
date: 2026-04-13T14:00:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "工厂模式", "factory"]
---

## 前言

上一篇文章我们介绍了单例模式，本期继续 Java 设计模式系列。**工厂模式**是创建型模式中应用最广泛的模式之一，用于封装对象的创建过程，实现解耦。

**核心思想**：定义一个创建对象的接口，让子类决定实例化哪一个类。

<!--more-->

## 一、为什么需要工厂模式

### 1.1 传统创建对象的问题

```java
// 传统方式：直接 new
public class OrderService {
    
    public void createOrder() {
        // 问题：紧耦合，难以扩展
        AlipayPayment payment = new AlipayPayment();
        payment.pay();
    }
}
```

**问题分析**：
- 对象创建逻辑散落在各处
- 切换支付方式需要修改多处代码
- 新增支付方式需要修改已有代码
- 违反开闭原则（对扩展开放，对修改关闭）

### 1.2 工厂模式的优势

```
┌─────────────────────────────────────────────────────────────┐
│                      Client (客户端)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      Factory (工厂)                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  createProduct(type) → 根据类型创建产品              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   Product (产品接口)                         │
│         ▲                ▲                ▲                │
│         │                │                │                │
│    ┌────┴────┐     ┌────┴────┐      ┌────┴────┐           │
│    │ProductA │     │ProductB │      │ProductC │           │
│    └─────────┘     └─────────┘      └─────────┘           │
└─────────────────────────────────────────────────────────────┘
```

## 二、三种工厂模式的演进

### 2.1 简单工厂模式（Simple Factory）

**也叫：静态工厂方法**

```java
// 产品接口
public interface Payment {
    void pay(double amount);
    void refund(double amount);
}

// 具体产品
public class AlipayPayment implements Payment {
    @Override
    public void pay(double amount) {
        System.out.println("支付宝支付：" + amount);
    }
    
    @Override
    public void refund(double amount) {
        System.out.println("支付宝退款：" + amount);
    }
}

public class WechatPayment implements Payment {
    @Override
    public void pay(double amount) {
        System.out.println("微信支付：" + amount);
    }
    
    @Override
    public void refund(double amount) {
        System.out.println("微信退款：" + amount);
    }
}

public class UnionPayPayment implements Payment {
    @Override
    public void pay(double amount) {
        System.out.println("银联支付：" + amount);
    }
    
    @Override
    public void refund(double amount) {
        System.out.println("银联退款：" + amount);
    }
}
```

**简单工厂实现**：

```java
public class PaymentFactory {
    
    // 方式一：静态工厂方法（最常用）
    public static Payment createPayment(String type) {
        if ("alipay".equals(type)) {
            return new AlipayPayment();
        } else if ("wechat".equals(type)) {
            return new WechatPayment();
        } else if ("union".equals(type)) {
            return new UnionPayPayment();
        } else {
            throw new IllegalArgumentException("不支持的支付方式：" + type);
        }
    }
    
    // 方式二：使用 Map 优化（避免 if-else）
    private static final Map<String, Supplier<Payment>> MAP = new HashMap<>();
    
    static {
        MAP.put("alipay", AlipayPayment::new);
        MAP.put("wechat", WechatPayment::new);
        MAP.put("union", UnionPayPayment::new);
    }
    
    public static Payment createPaymentV2(String type) {
        Supplier<Payment> supplier = MAP.get(type);
        if (supplier == null) {
            throw new IllegalArgumentException("不支持的支付方式：" + type);
        }
        return supplier.get();
    }
}
```

**客户端调用**：

```java
public class OrderService {
    
    public void createOrder(String paymentType, double amount) {
        // 客户端只需知道工厂和接口，不需要知道具体实现类
        Payment payment = PaymentFactory.createPayment(paymentType);
        payment.pay(amount);
    }
    
    public static void main(String[] args) {
        OrderService service = new OrderService();
        service.createOrder("alipay", 100.0);
        service.createOrder("wechat", 200.0);
    }
}
```

**UML 图**：

```
┌─────────────────────┐
│    PaymentFactory   │
├─────────────────────┤
│ +createPayment(type)│
└──────────┬──────────┘
           │ creates
           ▼
┌─────────────────────┐     <<interface>>
│      Payment        │
├─────────────────────┤
│ +pay(amount)        │
│ +refund(amount)     │
└──────────┬──────────┘
           │
     ▲─────┴─────▲
     │     │     │
     │     │     │
┌────┐ ┌────┐ ┌────┐
│Ali │ │Wei │ │Uni │
│Pay │ │Pay │ │Pay │
└────┘ └────┘ └────┘
```

**优点**：封装了对象创建逻辑，客户端与具体产品解耦
**缺点**：违反开闭原则，增加新产品需要修改工厂代码

### 2.2 工厂方法模式（Factory Method）

**定义**：定义一个创建对象的接口，但由子类决定要实例化的类是哪一个。

```java
// 抽象工厂
public abstract class PaymentFactory {
    
    // 抽象方法，由子类实现
    public abstract Payment createPayment();
    
    // 模板方法：支付流程
    public void pay(double amount) {
        Payment payment = createPayment();
        payment.pay(amount);
    }
}

// 具体工厂
public class AlipayFactory extends PaymentFactory {
    @Override
    public Payment createPayment() {
        return new AlipayPayment();
    }
}

public class WechatFactory extends PaymentFactory {
    @Override
    public Payment createPayment() {
        return new WechatPayment();
    }
}

public class UnionPayFactory extends PaymentFactory {
    @Override
    public Payment createPayment() {
        return new UnionPayPayment();
    }
}
```

**客户端调用**：

```java
public class OrderService {
    
    public void createOrder(PaymentFactory factory, double amount) {
        factory.pay(amount);
    }
    
    public static void main(String[] args) {
        OrderService service = new OrderService();
        
        // 使用支付宝
        service.createOrder(new AlipayFactory(), 100.0);
        
        // 使用微信
        service.createOrder(new WechatFactory(), 200.0);
    }
}
```

**UML 图**：

```
         ┌─────────────────────┐
         │   PaymentFactory    │
         │     (Abstract)      │
         ├─────────────────────┤
         │ +createPayment()    │
         └──────────┬──────────┘
                    │ creates
         ┌─────────┴─────────┐
         ▼                   ▼
┌─────────────────┐  ┌─────────────────┐
│  AlipayFactory  │  │ WechatFactory   │
├─────────────────┤  ├─────────────────┤
│ +createPayment()│  │ +createPayment()│
└────────┬────────┘  └────────┬────────┘
         │                    │
         └─────────┬──────────┘
                   │ creates
                   ▼
          ┌────────────────┐   <<interface>>
          │    Payment     │
          ├────────────────┤
          │ +pay(amount)   │
          │ +refund(amnt) │
          └───────┬────────┘
                  │
           ▲──────┴──────▲
           │             │
      ┌────┐        ┌────┐
      │Ali │        │Wei │
      │Pay │        │Pay │
      └────┘        └────┘
```

**JDBC 中的工厂方法**：

```java
// DriverManager 是工厂
Connection conn = DriverManager.getConnection(url, user, password);

// DataSource 也是工厂
DataSource ds = new HikariDataSource(config);
Connection conn = ds.getConnection();
```

**优点**：
- 符合开闭原则，新增产品只需新增工厂
- 符合单一职责原则，每个工厂只负责一种产品
- 体现了依赖倒置原则，依赖于抽象而非具体

**缺点**：
- 类数量增加
- 增加系统的复杂度和理解难度

### 2.3 抽象工厂模式（Abstract Factory）

**定义**：提供一个创建一系列相关或相互依赖对象的接口，而无需指定它们具体的类。

**场景**：产品族概念

```
产品族（同一品牌）：
┌────────────────────────────────────────────┐
│           Apple Factory (抽象工厂)           │
├────────────────────────────────────────────┤
│ +createComputer() → Computer               │
│ +createPhone() → Phone                     │
└────────────────────────────────────────────┘
          │                    │
          ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│ MacBookFactory  │  │ IPhoneFactory   │
│ (Mac电脑)       │  │ (苹果手机)       │
└─────────────────┘  └─────────────────┘

产品等级（同一类型）：
Mac电脑、Windows电脑 ← Computer
苹果手机、华为手机 ← Phone
```

**完整示例**：

```java
// 产品等级：Computer
public interface Computer {
    void display();
}

public class MacComputer implements Computer {
    @Override
    public void display() {
        System.out.println("Mac电脑显示");
    }
}

public class WindowsComputer implements Computer {
    @Override
    public void display() {
        System.out.println("Windows电脑显示");
    }
}

// 产品等级：Phone
public interface Phone {
    void call();
}

public class IPhone implements Phone {
    @Override
    public void call() {
        System.out.println("iPhone打电话");
    }
}

public class HuaweiPhone implements Phone {
    @Override
    public void call() {
        System.out.println("华为手机打电话");
    }
}
```

**抽象工厂**：

```java
// 抽象工厂接口
public interface ElectronicFactory {
    Computer createComputer();
    Phone createPhone();
}

// 苹果工厂
public class AppleFactory implements ElectronicFactory {
    @Override
    public Computer createComputer() {
        return new MacComputer();
    }
    
    @Override
    public Phone createPhone() {
        return new IPhone();
    }
}

// 华为工厂
public class HuaweiFactory implements ElectronicFactory {
    @Override
    public Computer createComputer() {
        return new WindowsComputer();
    }
    
    @Override
    public Phone createPhone() {
        return new HuaweiPhone();
    }
}
```

**客户端使用**：

```java
public class Store {
    
    private ElectronicFactory factory;
    
    public Store(ElectronicFactory factory) {
        this.factory = factory;
    }
    
    public void sellComputer() {
        Computer computer = factory.createComputer();
        computer.display();
    }
    
    public void sellPhone() {
        Phone phone = factory.createPhone();
        phone.call();
    }
    
    public static void main(String[] args) {
        // 苹果店
        Store appleStore = new Store(new AppleFactory());
        appleStore.sellComputer();  // Mac电脑显示
        appleStore.sellPhone();     // iPhone打电话
        
        // 华为店
        Store huaweiStore = new Store(new HuaweiFactory());
        huaweiStore.sellComputer();  // Windows电脑显示
        huaweiStore.sellPhone();     // 华为手机打电话
    }
}
```

**UML 图**：

```
         ┌────────────────────────┐
         │  ElectronicFactory     │
         │    (Abstract)          │
         ├────────────────────────┤
         │ +createComputer()      │
         │ +createPhone()         │
         └───────────┬────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐      ┌─────────────────┐
│  AppleFactory   │      │ HuaweiFactory  │
├─────────────────┤      ├─────────────────┤
│ +createComputer │      │ +createComputer │
│ +createPhone    │      │ +createPhone    │
└────────┬────────┘      └────────┬────────┘
         │                         │
         │ creates                 │ creates
         ▼                         ▼
┌─────────────────┐      ┌─────────────────┐
│   <<interface>> │      │   <<interface>> │
│   Computer      │      │   Phone         │
├─────────────────┤      ├─────────────────┤
│ +display()      │      │ +call()         │
└────────┬────────┘      └────────┬────────┘
         │                         │
    ┌────┴────┐                ┌────┴────┐
    │         │                │         │
┌───┐     ┌───┐            ┌───┐     ┌───┐
│Mac│     │Win│            │IP │     │HW │
│   │     │   │            │   │     │   │
└───┘     └───┘            └───┘     └───┘
```

## 三、工厂模式在源码中的应用

### 3.1 JDK 中的工厂模式

**Calendar.getInstance()**：

```java
// 工厂方法模式
Calendar cal = Calendar.getInstance();

// 内部实现
public static Calendar getInstance() {
    return createCalendar(TimeZone.getDefault(), Locale.getDefault(Locale.Category.FORMAT));
}

private static Calendar createCalendar(TimeZone zone, Locale aLocale) {
    // 根据系统配置创建不同的 Calendar 实现
    CalendarProvider provider = 
        AccessController.doPrivileged(new PrivilegedAction<CalendarProvider>() {
            public CalendarProvider run() {
                String providerName = System.getProperty("java.util.calendar.provider");
                if (providerName == null) {
                    return null;
                } else {
                    return (CalendarProvider) Class.forName(providerName)
                        .getDeclaredConstructor().newInstance();
                }
            }
        });
    // ...
}
```

**DriverManager.getConnection()**：

```java
// 简单工厂模式
Connection conn = DriverManager.getConnection(url, user, password);

// 内部使用工厂思想创建连接
```

### 3.2 Spring 中的工厂模式

**BeanFactory**：

```java
// 抽象工厂
public interface BeanFactory {
    Object getBean(String name) throws BeansException;
    <T> T getBean(String name, Class<T> requiredType) throws BeansException;
}

// 核心实现
public class DefaultListableBeanFactory {
    
    @Override
    public <T> T getBean(String name, Class<T> requiredType) {
        // 工厂方法创建 Bean
        BeanWrapper instanceWrapper = createBeanInstance(beanName, mbd, args);
        // ...
        return (T) instanceWrapper.getWrappedInstance();
    }
}
```

**FactoryBean**：

```java
// 工厂 Bean 接口
public interface FactoryBean<T> {
    // 返回创建的对象
    T getObject() throws Exception;
    // 返回对象类型
    Class<?> getObjectType();
    // 是否单例
    default boolean isSingleton() {
        return true;
    }
}

// 使用示例：MyBatis 的 SqlSessionFactory
public class SqlSessionFactoryBean implements FactoryBean<SqlSessionFactory> {
    
    @Override
    public SqlSessionFactory getObject() throws Exception {
        // 创建 SqlSessionFactory
        return buildSqlSessionFactory();
    }
    
    @Override
    public Class<?> getObjectType() {
        return SqlSessionFactory.class;
    }
}
```

### 3.3 MyBatis 中的工厂模式

**SqlSessionFactoryBuilder**：

```java
// 建造者 + 工厂
public class SqlSessionFactoryBuilder {
    
    public SqlSessionFactory build(InputStream inputStream) {
        // 使用 XMLConfigBuilder 解析配置
        XMLConfigBuilder parser = new XMLConfigBuilder(inputStream);
        // 构建 SqlSessionFactory
        return build(parser.parse());
    }
    
    public SqlSessionFactory build(Configuration config) {
        return new DefaultSqlSessionFactory(config);
    }
}
```

### 3.4 SLF4J 中的工厂模式

```java
// LoggerFactory 获取 Logger
public class LoggerFactory {
    
    public static Logger getLogger(Class<?> clazz) {
        // 工厂方法
        return getLogger(clazz.getName());
    }
    
    public static Logger getLogger(String name) {
        // 获取 ILoggerFactory 创建 Logger
        ILoggerFactory loggerFactory = getILoggerFactory();
        return loggerFactory.getLogger(name);
    }
}
```

## 四、工厂模式的选择策略

### 4.1 三种工厂的使用场景

| 模式 | 适用场景 | 产品复杂度 |
|------|----------|-----------|
| 简单工厂 | 产品种类少，不会频繁扩展 | 低 |
| 工厂方法 | 需要扩展产品，需要解耦 | 中 |
| 抽象工厂 | 产品族，产品线固定 | 高 |

### 4.2 简单工厂 vs 工厂方法

```
简单工厂适用条件：
✓ 产品种类相对稳定
✓ 不会频繁添加新产品
✓ 类数量有限

工厂方法适用条件：
✓ 需要频繁扩展新产品
✓ 强调开闭原则
✓ 产品有明显的分类
```

### 4.3 抽象工厂的优缺点

**优点**：
- 确保同一产品族的对象兼容性
- 符合开闭原则
- 抽取共性，集中管理

**缺点**：
- 产品族扩展困难（需要修改所有工厂）
- 难以支持新种类产品（需要修改抽象层）

## 五、实战案例

### 5.1 日志框架的工厂模式

```java
// 日志接口
public interface Logger {
    void info(String message);
    void error(String message);
    void debug(String message);
}

// 具体实现
public class Log4jLogger implements Logger {
    private org.apache.log4j.Logger logger;
    // ...
}

public class SlfjLogger implements Logger {
    private org.slf4j.Logger logger;
    // ...
}

public class JdkLogger implements Logger {
    private java.util.logging.Logger logger;
    // ...
}

// 日志工厂
public class LoggerFactory {
    
    private static final String LOG_IMPL = 
        System.getProperty("logger.impl", "jdk");
    
    public static Logger create() {
        switch (LOG_IMPL.toLowerCase()) {
            case "log4j":
                return new Log4jLogger();
            case "slfj":
                return new SlfjLogger();
            case "jdk":
            default:
                return new JdkLogger();
        }
    }
}
```

### 5.2 数据库连接的工厂模式

```java
// 连接池工厂
public class DataSourceFactory {
    
    public static DataSource createDataSource(String type, Map<String, String> config) {
        switch (type.toLowerCase()) {
            case "hikari":
                return createHikariCP(config);
            case "druid":
                return createDruid(config);
            case "c3p0":
                return createC3P0(config);
            default:
                throw new IllegalArgumentException("不支持的连接池：" + type);
        }
    }
    
    private static DataSource createHikariCP(Map<String, String> config) {
        HikariConfig hc = new HikariConfig();
        hc.setJdbcUrl(config.get("url"));
        hc.setUsername(config.get("username"));
        hc.setPassword(config.get("password"));
        return new HikariDataSource(hc);
    }
    
    // ...
}
```

## 六、面试常见问题

### Q1：简单工厂、工厂方法、抽象工厂的区别？

| 维度 | 简单工厂 | 工厂方法 | 抽象工厂 |
|------|---------|---------|---------|
| 产品 | 一种产品 | 一种产品 | 产品族 |
| 工厂 | 一个工厂 | 多个工厂 | 一个工厂接口 |
| 扩展 | 修改工厂 | 增加工厂 | 增加产品族困难 |
| 复杂度 | 低 | 中 | 高 |

### Q2：工厂方法与抽象工厂如何选择？

- 只需要一种产品 → 工厂方法
- 多个相关产品（产品族） → 抽象工厂
- 产品种类经常变化 → 工厂方法
- 产品族稳定 → 抽象工厂

### Q3：工厂方法为什么返回接口而不是具体类？

遵循**依赖倒置原则**：高层模块不应该依赖低层模块，两者都应该依赖抽象。

```java
// 正确：依赖抽象
public class OrderService {
    private PaymentFactory factory;  // 依赖抽象
}

// 错误：依赖具体
public class OrderService {
    private AlipayFactory factory;  // 紧耦合
}
```

### Q4：Spring 的 BeanFactory 和 FactoryBean 有什么区别？

- **BeanFactory**：容器的根接口，管理 Bean 的生命周期
- **FactoryBean**：用于创建复杂 Bean 的工厂 Bean

```java
// BeanFactory - IoC 容器的标准工厂
BeanFactory bf = new ClassPathXmlApplicationContext("beans.xml");
Object bean = bf.getBean("myBean");

// FactoryBean - 创建特定 Bean 的工厂
// 如果 Bean 名以 & 开头，返回 FactoryBean 本身
SqlSessionFactory factory = (SqlSessionFactory) bf.getBean("&sqlSessionFactory");
```

## 七、总结

### 7.1 模式对比

```
创建型模式对比：
┌──────────┬────────────┬────────────┬─────────────────┐
│ 模式      │ 封装程度   │ 复杂度     │ 扩展性          │
├──────────┼────────────┼────────────┼─────────────────┤
│ 单例     │ 单一实例   │ ★          │ 扩展困难        │
│ 简单工厂  │ 产品创建   │ ★★         │ 修改工厂        │
│ 工厂方法  │ 产品创建   │ ★★★        │ 增加工厂        │
│ 抽象工厂  │ 产品族创建 │ ★★★★       │ 增加产品族困难  │
└──────────┴────────────┴────────────┴─────────────────┘
```

### 7.2 使用建议

1. **简单场景用简单工厂**：产品种类少，扩展不频繁
2. **需要扩展用工厂方法**：遵循开闭原则
3. **产品族用抽象工厂**：确保产品兼容性
4. **结合使用**：根据实际情况灵活组合

## 结语

工厂模式是创建型模式中最核心、最实用的模式之一。理解三种工厂的适用场景，在实际开发中灵活运用，能写出更优雅、更易维护的代码。

**下期预告**：建造者模式（Builder Pattern）

> 记住：**没有最好的模式，只有最合适的场景**。
