---
title: "Java设计模式（六）：装饰器模式深入实践"
date: 2026-04-16T10:00:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "装饰器模式", "decorator"]
---

## 前言

前五篇文章我们介绍了单例模式、工厂模式、建造者模式、原型模式和适配器模式，今天继续 Java 设计模式系列。**装饰器模式（Decorator Pattern）** 是结构型模式中的重要成员，用于动态地给对象添加额外职责。

**核心思想**：动态地给一个对象添加一些额外的职责，就增加功能来说，装饰器模式比继承更加灵活。

<!--more-->

## 一、为什么需要装饰器模式

### 1.1 继承的问题

```java
// 传统方式：继承
public class FileOutputStream extends OutputStream {
    // 只添加缓冲功能
}

public class DataOutputStream extends OutputStream {
    // 添加数据加密
}

public class BufferedEncryptedFileOutputStream extends OutputStream {
    // 同时添加缓冲和加密？类爆炸！
}
```

**问题**：
- 类数量爆炸
- 继承层次过深
- 静态扩展，不够灵活

### 1.2 装饰器模式的优势

```java
// 使用装饰器
OutputStream os = new FileOutputStream("file.txt");
os = new BufferedOutputStream(os);        // 添加缓冲
os = new EncryptedOutputStream(os);     // 添加加密
os.write(data);  // 同时具有缓冲和加密功能
```

**优点**：
- 动态组合功能
- 单一职责
- 符合开闭原则

## 二、装饰器模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                   Component (抽象组件)                      │
├─────────────────────────────────────────────────────────────┤
│ + operation()                                             │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴─────────────────────────────────────────────┐
│         ConcreteComponent (具体组件)                        │
├─────────────────────────────────────────────────────────────┤
│ + operation() → 实现基础功能                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 Decorator (抽象装饰器)                        │
├─────────────────────────────────────────────────────────────┤
│ - component: Component                                     │
│ + operation() → 委托给 component 调用                        │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴─────────────────────────────────────────────┐
│           ConcreteDecorator (具体装饰器)                     │
├─────────────────────────────────────────────────────────────┤
│ + operation() → 调用 super.operation() + 添加额外功能        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 咖啡订单系统

```java
// 抽象组件：咖啡
public abstract class Coffee {
    protected String description = "咖啡";
    
    public String getDescription() {
        return description;
    }
    
    public abstract double cost();
}

// 具体组件：浓缩咖啡
public class Espresso extends Coffee {
    
    public Espresso() {
        this.description = "浓缩咖啡";
    }
    
    @Override
    public double cost() {
        return 25.0;
    }
}

// 具体组件：美式咖啡
public class Americano extends Coffee {
    
    public Americano() {
        this.description = "美式咖啡";
    }
    
    @Override
    public double cost() {
        return 22.0;
    }
}

// 抽象装饰器
public abstract class CoffeeDecorator extends Coffee {
    
    // 持有被装饰的对象
    protected Coffee coffee;
    
    public CoffeeDecorator(Coffee coffee) {
        this.coffee = coffee;
    }
    
    @Override
    public String getDescription() {
        return coffee.getDescription();
    }
    
    @Override
    public double cost() {
        return coffee.cost();
    }
}

// 具体装饰器：加牛奶
public class MilkDecorator extends CoffeeDecorator {
    
    public MilkDecorator(Coffee coffee) {
        super(coffee);
    }
    
    @Override
    public String getDescription() {
        return coffee.getDescription() + "，加牛奶";
    }
    
    @Override
    public double cost() {
        return coffee.cost() + 5.0;
    }
}

// 具体装饰器：加糖
public class SugarDecorator extends CoffeeDecorator {
    
    public SugarDecorator(Coffee coffee) {
        super(coffee);
    }
    
    @Override
    public String getDescription() {
        return coffee.getDescription() + "，加糖";
    }
    
    @Override
    public double cost() {
        return coffee.cost() + 2.0;
    }
}

// 具体装饰器：加焦糖
public class CaramelDecorator extends CoffeeDecorator {
    
    public CaramelDecorator(Coffee coffee) {
        super(coffee);
    }
    
    @Override
    public String getDescription() {
        return coffee.getDescription() + "，加焦糖";
    }
    
    @Override
    public double cost() {
        return coffee.cost() + 8.0;
    }
}
```

### 2.3 客户端使用

```java
public class CoffeeShop {
    public static void main(String[] args) {
        
        // 点一杯美式咖啡
        Coffee coffee1 = new Americano();
        System.out.println(coffee1.getDescription() + " = ¥" + coffee1.cost());
        // 输出：美式咖啡 = ¥22.0
        
        // 美式 + 牛奶 + 糖
        Coffee coffee2 = new SugarDecorator(
                            new MilkDecorator(
                                new Americano()));
        System.out.println(coffee2.getDescription() + " = ¥" + coffee2.cost());
        // 输出：美式咖啡，加牛奶，加糖 = ¥29.0
        
        // 浓缩 + 牛奶 + 焦糖
        Coffee coffee3 = new CaramelDecorator(
                            new MilkDecorator(
                                new Espresso()));
        System.out.println(coffee3.getDescription() + " = ¥" + coffee3.cost());
        // 输出：浓缩咖啡，加牛奶，加焦糖 = ¥38.0
        
        // 任意组合！
        Coffee coffee4 = new CaramelDecorator(
                            new SugarDecorator(
                                new MilkDecorator(
                                    new Espresso())));
        System.out.println(coffee4.getDescription() + " = ¥" + coffee4.cost());
        // 输出：浓缩咖啡，加牛奶，加糖，加焦糖 = ¥40.0
    }
}
```

## 三、IO 流中的装饰器模式

### 3.1 Java IO 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    OutputStream (抽象组件)                    │
├─────────────────────────────────────────────────────────────┤
│ + write(int b)                                             │
│ + write(byte[] b)                                          │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴─────────────────────────────────────────────┐
│              FileOutputStream (具体组件)                     │
├─────────────────────────────────────────────────────────────┤
│ + write() → 文件输出                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              FilterOutputStream (装饰器)                      │
├─────────────────────────────────────────────────────────────┤
│ - out: OutputStream                                         │
│ + write() → 委托给 out 调用                                 │
└─────────────────────────────────────────────────────────────┘
              △
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌─────────┐        ┌─────────┐
│Buffered│        │Data    │
│Output  │        │Output  │
│Stream  │        │Stream  │
├─────────┤        ├─────────┤
│+缓冲  │        │+数据类型│
└─────────┘        └─────────┘
```

### 3.2 经典用法

```java
// BufferedInputStream 装饰 FileInputStream
FileInputStream fis = new FileInputStream("file.txt");
BufferedInputStream bis = new BufferedInputStream(fis);

// 缓冲 + 数据类型转换
DataInputStream dis = new DataInputStream(
    new BufferedInputStream(
        new FileInputStream("file.txt")));

// 缓冲输出
BufferedOutputStream bos = new BufferedOutputStream(
    new FileOutputStream("output.txt"));

// 装饰器组合
ObjectOutputStream oos = new ObjectOutputStream(
    new BufferedOutputStream(
        new FileOutputStream("object.dat")));
```

### 3.3 自定义装饰器

```java
// 大写转换装饰器
public class UpperCaseOutputStream extends FilterOutputStream {
    
    public UpperCaseOutputStream(OutputStream out) {
        super(out);
    }
    
    @Override
    public void write(int b) throws IOException {
        // 转换为大写
        int upper = Character.toUpperCase((char) b);
        super.write(upper);
    }
    
    @Override
    public void write(byte[] b, int off, int len) throws IOException {
        // 转换整个数组
        byte[] upper = new byte[len];
        for (int i = 0; i < len; i++) {
            upper[i] = (byte) Character.toUpperCase((char) b[off + i]);
        }
        super.write(upper, 0, len);
    }
}

// 使用
OutputStream out = new UpperCaseOutputStream(
    new BufferedOutputStream(
        new FileOutputStream("output.txt")));
out.write("hello world".getBytes());
// 写入文件的内容是：HELLO WORLD
```

## 四、实战案例

### 4.1 日志装饰器

```java
// 日志接口
public interface Logger {
    void log(String message);
}

// 控制台日志
public class ConsoleLogger implements Logger {
    
    @Override
    public void log(String message) {
        System.out.println("[CONSOLE] " + message);
    }
}

// 抽象日志装饰器
public abstract class LoggerDecorator implements Logger {
    
    protected Logger logger;
    
    public LoggerDecorator(Logger logger) {
        this.logger = logger;
    }
    
    @Override
    public void log(String message) {
        logger.log(message);
    }
}

// 时间戳装饰器
public class TimestampLogger extends LoggerDecorator {
    
    private SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    
    public TimestampLogger(Logger logger) {
        super(logger);
    }
    
    @Override
    public void log(String message) {
        String timestamp = sdf.format(new Date());
        super.log("[" + timestamp + "] " + message);
    }
}

// 级别装饰器
public class LevelLogger extends LoggerDecorator {
    
    private String level;
    
    public LevelLogger(Logger logger, String level) {
        super(logger);
        this.level = level;
    }
    
    @Override
    public void log(String message) {
        super.log("[" + level + "] " + message);
    }
}

// 文件装饰器
public class FileLogger extends LoggerDecorator {
    
    private PrintWriter writer;
    
    public FileLogger(Logger logger, String filename) throws FileNotFoundException {
        super(logger);
        this.writer = new PrintWriter(new FileWriter(filename, true));
    }
    
    @Override
    public void log(String message) {
        writer.println(message);
        writer.flush();
        super.log(message);
    }
    
    public void close() {
        writer.close();
    }
}

// 使用
public class LoggerTest {
    public static void main(String[] args) throws Exception {
        
        // 基本日志
        Logger logger1 = new ConsoleLogger();
        logger1.log("简单消息");
        
        // 带时间戳的日志
        Logger logger2 = new TimestampLogger(new ConsoleLogger());
        logger2.log("带时间戳的消息");
        
        // 多层装饰：时间戳 + 级别 + 文件
        Logger logger3 = new FileLogger(
            new LevelLogger(
                new TimestampLogger(
                    new ConsoleLogger()),
                "INFO"),
            "app.log");
        logger3.log("完整日志：INFO 级别带时间戳");
    }
}
```

### 4.2 缓存装饰器

```java
// 数据服务接口
public interface DataService {
    String getData(String key);
    void putData(String key, String value);
}

// 基础数据服务
public class BasicDataService implements DataService {
    
    @Override
    public String getData(String key) {
        // 模拟从数据库读取
        System.out.println("从数据库读取: " + key);
        return "data_" + key;
    }
    
    @Override
    public void putData(String key, String value) {
        System.out.println("写入数据库: " + key + " = " + value);
    }
}

// 缓存装饰器
public class CacheDecorator implements DataService {
    
    private DataService delegate;
    private Map<String, String> cache = new ConcurrentHashMap<>();
    
    public CacheDecorator(DataService delegate) {
        this.delegate = delegate;
    }
    
    @Override
    public String getData(String key) {
        // 先查缓存
        String cached = cache.get(key);
        if (cached != null) {
            System.out.println("从缓存读取: " + key);
            return cached;
        }
        
        // 缓存未命中，从原始服务获取
        String data = delegate.getData(key);
        // 存入缓存
        cache.put(key, data);
        return data;
    }
    
    @Override
    public void putData(String key, String value) {
        // 写入原始服务
        delegate.putData(key, value);
        // 更新缓存
        cache.put(key, value);
    }
    
    // 获取缓存命中率
    public double getHitRate() {
        return 0.0; // 简化实现
    }
}

// 使用
public class CacheTest {
    public static void main(String[] args) {
        // 原始服务
        DataService basicService = new BasicDataService();
        
        // 包装缓存
        DataService cachedService = new CacheDecorator(basicService);
        
        // 第一次读取（未命中）
        String data1 = cachedService.getData("user:1");
        System.out.println("结果: " + data1);
        
        // 第二次读取（命中缓存）
        String data2 = cachedService.getData("user:1");
        System.out.println("结果: " + data2);
    }
}
```

### 4.3 限流装饰器

```java
// 限流接口
public interface RateLimiter {
    boolean allow();
}

// 滑动窗口限流器
public class SlidingWindowRateLimiter implements RateLimiter {
    
    private int maxRequests;
    private Window window;
    
    public SlidingWindowRateLimiter(int maxRequests, long windowSizeMs) {
        this.maxRequests = maxRequests;
        this.window = new Window(windowSizeMs);
    }
    
    @Override
    public boolean allow() {
        long now = System.currentTimeMillis();
        window.cleanup(now);
        
        if (window.size() < maxRequests) {
            window.add(now);
            return true;
        }
        return false;
    }
}

// 限流装饰器
public class RateLimitDecorator implements DataService {
    
    private DataService delegate;
    private RateLimiter rateLimiter;
    
    public RateLimitDecorator(DataService delegate, RateLimiter rateLimiter) {
        this.delegate = delegate;
        this.rateLimiter = rateLimiter;
    }
    
    @Override
    public String getData(String key) {
        if (!rateLimiter.allow()) {
            throw new RateLimitException("请求过于频繁，请稍后重试");
        }
        return delegate.getData(key);
    }
    
    @Override
    public void putData(String key, String value) {
        if (!rateLimiter.allow()) {
            throw new RateLimitException("请求过于频繁，请稍后重试");
        }
        delegate.putData(key, value);
    }
}

// 使用
public class RateLimitTest {
    public static void main(String[] args) {
        DataService service = new BasicDataService();
        
        // 添加缓存
        service = new CacheDecorator(service);
        
        // 添加限流
        service = new RateLimitDecorator(
            service, 
            new SlidingWindowRateLimiter(100, 1000)); // 1秒最多100次
        
        // 使用服务
        for (int i = 0; i < 10; i++) {
            try {
                String data = service.getData("key");
                System.out.println("成功: " + data);
            } catch (RateLimitException e) {
                System.out.println("限流: " + e.getMessage());
            }
        }
    }
}
```

## 五、装饰器模式 vs 继承 vs 代理

### 5.1 对比

| 维度 | 装饰器模式 | 继承 | 代理模式 |
|------|-----------|------|---------|
| **功能** | 增强功能 | 增加功能 | 控制访问 |
| **运行时** | 动态组合 | 编译时确定 | 编译时确定 |
| **接口** | 保持一致 | 可能改变 | 保持一致 |
| **对象数量** | 多个对象 | 一个对象 | 一个对象 |
| **灵活性** | 高 | 低 | 中 |

### 5.2 选择指南

```
需要增强单个对象的功能        需要增强多个对象的功能
         │                            │
         ▼                            ▼
      装饰器模式                   装饰器模式

需要控制访问                   需要在访问前后做处理
（如权限检查）                   （如事务管理）
         │                            │
         ▼                            ▼
       代理模式                    装饰器模式

功能变化频繁                   功能相对固定
需要动态组合                    编译时确定
         │                            │
         ▼                            ▼
      装饰器模式                    继承
```

### 5.3 装饰器 vs 代理的代码区别

```java
// 代理模式：通常在代理类中直接调用真实对象
public class UserServiceProxy implements UserService {
    private UserService realService;
    
    public UserServiceProxy() {
        this.realService = new UserServiceImpl();
    }
    
    @Override
    public void save(User user) {
        // 权限检查
        if (!hasPermission()) {
            throw new SecurityException("无权限");
        }
        realService.save(user);  // 直接调用
    }
}

// 装饰器模式：持有组件接口，可以继续包装
public class UserServiceDecorator implements UserService {
    protected UserService delegate;
    
    public UserServiceDecorator(UserService delegate) {
        this.delegate = delegate;
    }
    
    @Override
    public void save(User user) {
        delegate.save(user);  // 委托给被包装对象
    }
}

// 装饰器可以无限叠加
UserService service = new CacheDecorator(
    new TransactionDecorator(
        new LoggingDecorator(
            new UserServiceImpl())));
```

## 六、装饰器模式的优缺点

### 6.1 优点

1. **动态扩展**：可以在运行时动态添加功能
2. **单一职责**：每个装饰器只关注一个功能
3. **开闭原则**：无需修改现有类即可扩展
4. **灵活组合**：可以任意组合装饰器

### 6.2 缺点

1. **复杂度**：增加系统复杂度
2. **调试困难**：多层装饰可能难以追踪
3. **顺序敏感**：装饰器的顺序可能影响结果

### 6.3 注意事项

```java
// 正确：先装饰再使用
BufferedOutputStream bos = new BufferedOutputStream(
    new FileOutputStream("file.txt"));

// 注意顺序：先缓冲后加密 vs 先加密后缓冲效果不同
// 方案1：先缓冲后压缩
OutputStream out1 = new GzipOutputStream(
    new BufferedOutputStream(
        new FileOutputStream("file1.txt")));

// 方案2：先压缩后缓冲
OutputStream out2 = new BufferedOutputStream(
    new GzipOutputStream(
        new FileOutputStream("file2.txt")));
```

## 七、JDK/框架中的应用

### 7.1 Java IO 流

```java
// 经典组合
BufferedReader reader = new BufferedReader(
    new InputStreamReader(
        new FileInputStream("file.txt")));

// NIO 中的装饰器
FileChannel channel = FileChannel.open(Paths.get("file.txt"));
ReadableByteChannel readableChannel = Channels.newChannel(channel);
```

### 7.2 Spring 中的装饰器

**TransactionAwareDataSourceProxy**：

```java
// 事务感知的 DataSource 装饰器
DataSource original = ...;
DataSource transactionAware = new TransactionAwareDataSourceProxy(original);

// 使用时自动加入当前事务
Connection conn = transactionAware.getConnection();
```

**WebRequestDecorator**：

```java
// Spring MVC 中的请求装饰器
public class LocaleContextHolder {
    public static void wrap(WebRequest request) {
        if (!(request instanceof LocaleContextAware)) {
            request = new LocaleContext HolderRequestAttributes(request);
        }
    }
}
```

### 7.3 MyBatis 中的装饰器

```java
// Cache 接口就是装饰器模式
public interface Cache {
    String getId();
    void putObject(Object key, Object value);
    Object getObject(Object key);
    Object removeObject(Object key);
}

// 装饰器实现
public class SerializedCache implements Cache {
    private final Cache delegate;
    
    public SerializedCache(Cache delegate) {
        this.delegate = delegate;
    }
    
    @Override
    public void putObject(Object key, Object value) {
        delegate.putObject(key, serialize(value));
    }
    
    @Override
    public Object getObject(Object key) {
        return deserialize(delegate.getObject(key));
    }
}

// 缓存组合
Cache cache = new SerializedCache(       // 序列化
              new LruCache(               // LRU 淘汰
                new PerpetualCache()));   // 永久缓存
```

## 八、最佳实践

### 8.1 保持组件接口一致

```java
// 装饰器必须实现组件接口
public class Decorator implements Component {
    protected Component component;
    
    public Decorator(Component component) {
        this.component = component;
    }
    
    // 默认实现：委托给被装饰对象
    @Override
    public void operation() {
        component.operation();
    }
}
```

### 8.2 避免过度装饰

```java
// ❌ 过度装饰，难以维护
DataService service = new CacheDecorator(
    new RateLimitDecorator(
        new TransactionDecorator(
            new LoggingDecorator(
                new RetryDecorator(
                    new CircuitBreakerDecorator(
                        new BasicDataService())))));

// ✓ 适度抽象
DataService service = new SmartDataService(
    new BasicDataService());
```

### 8.3 使用 Builder 简化

```java
// 装饰器 Builder
public class DataServiceBuilder {
    private DataService service = new BasicDataService();
    
    public DataServiceBuilder withCache() {
        service = new CacheDecorator(service);
        return this;
    }
    
    public DataServiceBuilder withRateLimit(int limit) {
        service = new RateLimitDecorator(service, 
            new SlidingWindowRateLimiter(limit, 1000));
        return this;
    }
    
    public DataServiceBuilder withLogging() {
        service = new LoggingDecorator(service);
        return this;
    }
    
    public DataService build() {
        return service;
    }
}

// 使用
DataService service = new DataServiceBuilder()
    .withCache()
    .withRateLimit(100)
    .withLogging()
    .build();
```

## 九、面试常见问题

### Q1：装饰器模式和继承的区别？

| 维度 | 装饰器模式 | 继承 |
|------|-----------|------|
| 扩展方式 | 运行时动态 | 编译时静态 |
| 类数量 | 不增加 | 类数量爆炸 |
| 灵活性 | 高 | 低 |
| 组合 | 任意组合 | 固定 |

### Q2：装饰器模式和代理模式的区别？

- **装饰器**：增强功能，组合多个装饰器
- **代理**：控制访问，通常一对一

### Q3：装饰器模式的注意事项？

1. 保持组件接口一致
2. 装饰器顺序可能影响结果
3. 避免过度装饰
4. 调试时注意调用链路

### Q4：Java IO 流的装饰器有哪些？

- `BufferedInputStream/BufferedOutputStream`：缓冲
- `DataInputStream/DataOutputStream`：数据类型
- `GZIPInputStream/GZIPOutputStream`：压缩
- `ObjectInputStream/ObjectOutputStream`：对象序列化

## 十、总结

### 10.1 模式对比

```
结构型模式对比：
┌────────────┬──────────────────────────────────────┐
│   模式      │ 目的                                  │
├────────────┼──────────────────────────────────────┤
│ 装饰器模式  │ 动态增强功能，保持接口一致              │
│ 适配器模式  │ 接口转换，使不兼容变兼容              │
│ 代理模式   │ 控制访问，不改变接口                   │
│ 外观模式   │ 简化接口，提供统一入口                  │
└────────────┴──────────────────────────────────────┘
```

### 10.2 核心要点

1. **装饰器持有组件引用**：通过组合实现
2. **接口保持一致**：客户端无感知
3. **可以无限叠加**：灵活组合
4. **顺序敏感**：注意装饰器顺序

## 结语

装饰器模式是给对象动态添加职责的利器，特别是在需要灵活组合多个功能、处理继承层次过深等问题时。掌握装饰器模式，能够设计出更灵活、更易扩展的系统。

**下期预告**：观察者模式（Observer Pattern）

> 记住：**装饰器是包装，不是替换**。
