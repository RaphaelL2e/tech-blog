---
title: "Java设计模式（三）：建造者模式深度实践"
date: 2026-04-13T14:15:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "建造者模式", "builder"]
---

## 前言

前两篇文章我们介绍了单例模式和工厂模式，今天继续 Java 设计模式系列。**建造者模式（Builder Pattern）** 是创建型模式中的重要成员，特别适合处理复杂对象的创建过程。

**核心思想**：将一个复杂对象的构建与它的表示分离，使得同样的构建过程可以创建不同的表示。

<!--more-->

## 一、为什么需要建造者模式

### 1.1 传统构造函数的问题

**问题一：参数过多**

```java
// 令人恐惧的构造函数
public class User {
    private String firstName;    // 必填
    private String lastName;     // 必填
    private int age;             // 可选
    private String phone;        // 可选
    private String address;      // 可选
    private String email;        // 可选
    
    public User(String firstName, String lastName, int age, 
                String phone, String address, String email) {
        // 16 个构造函数参数...
    }
}

// 调用时完全不知道每个参数是什么意思
new User("John", "Doe", 25, "13800000000", "Beijing", "john@email.com");
```

**问题二：参数类型相同**

```java
// 无法区分参数顺序
public User(String name, String email, int age) {}
public User(String email, String name, int age) {}

// 调用时完全分不清
new User("Zhang San", "zhangsan@email.com", 25);  // 哪个是 name?
```

**问题三：不可变对象与灵活构造的矛盾**

```java
// 为了保持不可变性，所有字段都需要 final
public class User {
    private final String name;
    private final int age;
    // 但构造函数变得极其复杂
}
```

### 1.2 解决方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| 构造函数 | 简单 | 参数多时难以使用 |
| JavaBean | 灵活 | 不是线程安全的 |
| 建造者模式 | 灵活、可读、线程安全 | 代码量多 |

## 二、建造者模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                        Product (产品)                        │
│                    复杂对象，由 Builder 创建                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Builder (抽象建造者)                      │
├─────────────────────────────────────────────────────────────┤
│ + buildPartA()                                             │
│ + buildPartB()                                             │
│ + getResult()                                              │
└─────────────────────────────────────────────────────────────┘
                    △
                    │
┌───────────────────┴───────────────────────────────────────┐
│                    ConcreteBuilder (具体建造者)                │
├─────────────────────────────────────────────────────────────┤
│ + buildPartA()     → 构建 Part A                            │
│ + buildPartB()     → 构建 Part B                            │
│ + getResult()      → 返回构建的产品                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      Director (指挥者)                        │
│                   安排构建顺序，使用 Builder                   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 产品类

```java
public class Computer {
    
    private String cpu;         // 必填
    private String ram;         // 必填
    private String storage;     // 可选
    private String graphicsCard; // 可选
    private String monitor;      // 可选
    private boolean bluetooth;   // 可选
    
    // 私有构造函数，只能通过 Builder 创建
    private Computer(Builder builder) {
        this.cpu = builder.cpu;
        this.ram = builder.ram;
        this.storage = builder.storage;
        this.graphicsCard = builder.graphicsCard;
        this.monitor = builder.monitor;
        this.bluetooth = builder.bluetooth;
    }
    
    // toString 方法
    @Override
    public String toString() {
        return "Computer{" +
            "cpu='" + cpu + '\'' +
            ", ram='" + ram + '\'' +
            ", storage='" + storage + '\'' +
            ", graphicsCard='" + graphicsCard + '\'' +
            ", monitor='" + monitor + '\'' +
            ", bluetooth=" + bluetooth +
            '}';
    }
    
    // 静态内部 Builder 类
    public static class Builder {
        // 必填参数
        private final String cpu;
        private final String ram;
        
        // 可选参数，使用默认值
        private String storage = "256GB SSD";
        private String graphicsCard = "集成显卡";
        private String monitor = "15.6英寸";
        private boolean bluetooth = false;
        
        // 构造函数只接收必填参数
        public Builder(String cpu, String ram) {
            this.cpu = cpu;
            this.ram = ram;
        }
        
        // 可选参数的方法，返回 this 实现链式调用
        public Builder storage(String storage) {
            this.storage = storage;
            return this;
        }
        
        public Builder graphicsCard(String graphicsCard) {
            this.graphicsCard = graphicsCard;
            return this;
        }
        
        public Builder monitor(String monitor) {
            this.monitor = monitor;
            return this;
        }
        
        public Builder bluetooth(boolean bluetooth) {
            this.bluetooth = bluetooth;
            return this;
        }
        
        // 最后调用 build 方法创建对象
        public Computer build() {
            return new Computer(this);
        }
    }
}
```

### 2.3 客户端调用

```java
public class Client {
    public static void main(String[] args) {
        
        // 创建一台高配电脑 - 链式调用
        Computer highEndComputer = new Computer.Builder("Intel i9", "32GB")
            .storage("1TB NVMe SSD")
            .graphicsCard("RTX 4090")
            .monitor("27英寸 4K")
            .bluetooth(true)
            .build();
        
        // 创建一台普通办公电脑 - 只需必填和部分可选参数
        Computer officeComputer = new Computer.Builder("Intel i5", "16GB")
            .storage("512GB SSD")
            .build();
        
        System.out.println(highEndComputer);
        System.out.println(officeComputer);
    }
}
```

**输出**：

```
Computer{cpu='Intel i9', ram='32GB', storage='1TB NVMe SSD', 
       graphicsCard='RTX 4090', monitor='27英寸 4K', bluetooth=true}
Computer{cpu='Intel i5', ram='16GB', storage='512GB SSD', 
       graphicsCard='集成显卡', monitor='15.6英寸', bluetooth=false}
```

## 三、建造者模式的进阶用法

### 3.1 带校验的 Builder

```java
public class User {
    
    private final String firstName;
    private final String lastName;
    private final int age;
    private final String email;
    
    private User(Builder builder) {
        this.firstName = builder.firstName;
        this.lastName = builder.lastName;
        this.age = builder.age;
        this.email = builder.email;
    }
    
    public static class Builder {
        private String firstName;  // 必填
        private String lastName;   // 必填
        private int age = 0;       // 默认值
        private String email;      // 可选
        
        // 必填参数在构造函数中校验
        public Builder(String firstName, String lastName) {
            if (firstName == null || firstName.isEmpty()) {
                throw new IllegalArgumentException("名字不能为空");
            }
            if (lastName == null || lastName.isEmpty()) {
                throw new IllegalArgumentException("姓氏不能为空");
            }
            this.firstName = firstName;
            this.lastName = lastName;
        }
        
        public Builder age(int age) {
            if (age < 0 || age > 150) {
                throw new IllegalArgumentException("年龄不合法");
            }
            this.age = age;
            return this;
        }
        
        public Builder email(String email) {
            // 校验邮箱格式
            if (email != null && !email.matches("^[\\w.-]+@[\\w.-]+\\.\\w+$")) {
                throw new IllegalArgumentException("邮箱格式不正确");
            }
            this.email = email;
            return this;
        }
        
        public User build() {
            return new User(this);
        }
    }
}
```

### 3.2 继承层级中的 Builder

```java
// 基类
public abstract class Animal {
    protected String name;
    protected int age;
    
    public abstract static class Builder<T extends Builder<T>> {
        protected String name;
        protected int age;
        
        @SuppressWarnings("unchecked")
        protected T self() {
            return (T) this;
        }
        
        public T name(String name) {
            this.name = name;
            return self();
        }
        
        public T age(int age) {
            this.age = age;
            return self();
        }
        
        public abstract Animal build();
    }
    
    protected Animal(Builder<?> builder) {
        this.name = builder.name;
        this.age = builder.age;
    }
}

// 子类
public class Dog extends Animal {
    private final String breed;
    
    public static class Builder extends Animal.Builder<Builder> {
        private String breed = "田园犬";
        
        public Builder breed(String breed) {
            this.breed = breed;
            return this;
        }
        
        @Override
        public Dog build() {
            return new Dog(this);
        }
    }
    
    private Dog(Builder builder) {
        super(builder);
        this.breed = builder.breed;
    }
}

// 使用
Dog dog = new Dog.Builder()
    .name("旺财")
    .age(3)
    .breed("金毛")
    .build();
```

### 3.3 复杂对象的多 Builder

```java
public class Pizza {
    private final String name;       // 必填
    private final String dough;       // 必填
    private final String sauce;       // 必填
    private final List<String> toppings; // 可选
    
    private Pizza(Builder builder) {
        this.name = builder.name;
        this.dough = builder.dough;
        this.sauce = builder.sauce;
        this.toppings = builder.toppings;
    }
    
    public static class Builder {
        // 必填参数
        private final String name;
        private final String dough;
        private final String sauce;
        
        // 可选参数
        private List<String> toppings = new ArrayList<>();
        
        public Builder(String name, String dough, String sauce) {
            this.name = name;
            this.dough = dough;
            this.sauce = sauce;
        }
        
        public Builder toppings(List<String> toppings) {
            this.toppings = toppings;
            return this;
        }
        
        public Pizza build() {
            return new Pizza(this);
        }
    }
}

// 预设的 Builder
public class PizzaBuilder {
    
    // 玛格丽特披萨
    public static Pizza margherita() {
        return new Pizza.Builder("玛格丽特", "薄底", "番茄酱")
            .toppings(Arrays.asList(" mozzarella", " 番茄", " 罗勒"))
            .build();
    }
    
    // 海鲜披萨
    public static Pizza seafood() {
        return new Pizza.Builder("海鲜披萨", "厚底", "白酱")
            .toppings(Arrays.asList(" 虾", " 鱿鱼", " 蟹棒"))
            .build();
    }
    
    // 自定义披萨
    public static Pizza custom(String name, String dough, String sauce) {
        return new Pizza.Builder(name, dough, sauce).build();
    }
}
```

## 四、JDK 中的建造者模式

### 4.1 StringBuilder

```java
// StringBuilder 就是经典的建造者模式
StringBuilder sb = new StringBuilder();
sb.append("Hello")
  .append(" ")
  .append("World")
  .append("!")
  .toString();

// 底层实现
public final class StringBuilder {
    private char[] value;
    private int count;
    
    public StringBuilder append(String str) {
        toStringCache = null;
        super.append(str);
        return this;  // 返回 this 实现链式调用
    }
    
    @Override
    public String toString() {
        return new String(value, 0, count);
    }
}
```

### 4.2 StringBuffer

```java
// StringBuffer 是线程安全的 StringBuilder
StringBuffer sb = new StringBuffer();
sb.append("Hello")
  .append(" ")
  .append("World")
  .synchronized(this) {
      // 线程安全操作
  }
```

### 4.3 Stream.Builder

```java
// Java 9 引入的 Stream.Builder
Stream.Builder<String> builder = Stream.builder();
builder.add("A")
       .add("B")
       .add("C");
Stream<String> stream = builder.build();
```

### 4.4 Locale.Builder

```java
// Locale 的构建器
Locale locale = new Locale.Builder()
    .setLanguage("zh")
    .setScript("Hans")
    .setRegion("CN")
    .setVariant("posix")
    .build();
```

## 五、知名框架中的建造者模式

### 5.1 OkHttp 的 Request.Builder

```java
// OkHttp 是网络请求库，使用建造者模式构建请求
Request request = new Request.Builder()
    .url("https://api.example.com/users")
    .post(body)
    .addHeader("Content-Type", "application/json")
    .addHeader("Authorization", "Bearer token")
    .build();

// 底层实现
public static class Builder {
    private HttpUrl url;
    private String method;
    private Headers.Builder headersBuilder;
    private RequestBody body;
    
    public Builder() {
        this.method = "GET";
        this.headersBuilder = new Headers.Builder();
    }
    
    public Builder url(HttpUrl url) {
        this.url = url;
        return this;
    }
    
    public Request build() {
        if (url == null) {
            throw new IllegalStateException("url == null");
        }
        return new Request(this);
    }
}
```

### 5.2 Retrofit 的 RequestBuilder

```java
// Retrofit 网络请求构建
Retrofit retrofit = new Retrofit.Builder()
    .baseUrl("https://api.example.com/")
    .addConverterFactory(GsonConverterFactory.create())
    .build();

ApiService api = retrofit.create(ApiService.class);
```

### 5.3 Lombok @Builder

```java
import lombok.Builder;
import lombok.Singular;
import java.util.List;

// Lombok 自动生成 Builder
@Builder
public class User {
    private String name;
    private int age;
    @Singular
    private List<String> hobbies;
}

// 自动生成
User user = User.builder()
    .name("张三")
    .age(25)
    .hobby("读书")
    .hobby("游泳")
    .build();
```

### 5.4 Spock Framework 的 Data Table

```java
// Spock 测试框架使用建造者模式
expect:
calculator.calculate(a, b) == result

where:
a | b | result
1 | 2 | 3
5 | 7 | 12
```

### 5.5 Protocol Buffers 的 Builder

```java
// Protocol Buffers 使用建造者模式
UserProto.User user = UserProto.User.newBuilder()
    .setId(1)
    .setName("张三")
    .addHobbies("读书")
    .addHobbies("游泳")
    .build();
```

## 六、建造者模式 vs 工厂模式

### 6.1 核心区别

| 维度 | 建造者模式 | 工厂模式 |
|------|-----------|-----------|
| **目的** | 构建复杂对象 | 创建产品对象 |
| **产品复杂度** | 复杂对象，多部件 | 通常是单一对象 |
| **创建过程** | 分步骤构建 | 一次性创建 |
| **侧重点** | 构建过程 | 产品本身 |
| **返回方式** | 链式调用 | 直接返回对象 |

### 6.2 选择指南

```
创建简单对象，产品单一            创建复杂对象，多个部件
         │                                │
         ▼                                ▼
    ┌─────────┐                    ┌─────────────┐
    │ 工厂模式 │                    │ 建造者模式  │
    └─────────┘                    └─────────────┘
         │                                │
         ▼                                ▼
    new Product()              product.partA()
                                  .partB()
                                  .partC()
                                  .build()
```

### 6.3 组合使用

```java
// 工厂创建 Builder，Builder 构建复杂对象
public class ProductFactory {
    
    public static Product createProduct(String type) {
        switch (type) {
            case "computer":
                return new Computer.Builder("i7", "16GB")
                    .storage("512GB")
                    .build();
            case "server":
                return Server.builder()
                    .cpu("Xeon")
                    .ram("64GB")
                    .build();
            default:
                throw new IllegalArgumentException();
        }
    }
}
```

## 七、建造者模式的变体

### 7.1 流式 Builder（链式调用）

```java
// 最常见的变体
public class Query {
    private String table;
    private List<String> columns;
    private String where;
    private String orderBy;
    
    public static Builder builder() {
        return new Builder();
    }
    
    public static class Builder {
        private Query query = new Query();
        
        public Builder from(String table) {
            query.table = table;
            return this;
        }
        
        public Builder select(String... columns) {
            query.columns = Arrays.asList(columns);
            return this;
        }
        
        public Builder where(String condition) {
            query.where = condition;
            return this;
        }
        
        public Builder orderBy(String column) {
            query.orderBy = column;
            return this;
        }
        
        public Query build() {
            return query;
        }
    }
}

// 使用
Query query = Query.builder()
    .from("users")
    .select("id", "name", "email")
    .where("age > 18")
    .orderBy("name")
    .build();
```

### 7.2 验证型 Builder

```java
// 构建时验证参数合法性
public class Config {
    private final String host;
    private final int port;
    private final String username;
    private final String password;
    
    private Config(Builder builder) {
        this.host = builder.host;
        this.port = builder.port;
        this.username = builder.username;
        this.password = builder.password;
    }
    
    public static Builder builder() {
        return new Builder();
    }
    
    public static class Builder {
        private String host;
        private int port = 80;
        private String username;
        private String password;
        
        public Builder host(String host) {
            if (host == null || host.isEmpty()) {
                throw new IllegalArgumentException("host 不能为空");
            }
            this.host = host;
            return this;
        }
        
        public Builder port(int port) {
            if (port < 1 || port > 65535) {
                throw new IllegalArgumentException("port 必须在 1-65535 之间");
            }
            this.port = port;
            return this;
        }
        
        public Config build() {
            // 最终验证
            if (username != null && password == null) {
                throw new IllegalStateException("密码不能为空");
            }
            return new Config(this);
        }
    }
}
```

## 八、面试常见问题

### Q1：建造者模式的优点？

1. **良好的封装性**：构建逻辑封装在 Builder 中，客户端不需要知道产品内部细节
2. **良好的扩展性**：可以方便地扩展新的 Builder 实现
3. **精细控制构建过程**：可以控制构建的步骤和顺序
4. **链式调用**：代码简洁、可读性强
5. **不可变对象**：可以在 Builder 中设置默认值，创建不可变对象

### Q2：建造者模式与工厂模式如何选择？

- **产品构造简单** → 工厂模式
- **产品构造复杂，多个部件** → 建造者模式
- **需要链式调用** → 建造者模式
- **需要验证逻辑** → 建造者模式

### Q3：Lombok @Builder 的原理？

Lombok 在编译期通过注解处理器自动生成 Builder 类：
1. 生成 `ClassNameBuilder` 内部类
2. 为每个字段生成对应的 setter 方法（返回 Builder）
3. 生成 `build()` 方法
4. 修改构造函数接收 Builder 参数

### Q4：建造者模式的缺点？

1. 代码量增加，需要创建额外的 Builder 类
2. 对于简单对象，可能过度设计
3. 需要考虑线程安全问题（如果对象不是不可变的）

## 九、最佳实践

### 9.1 建议

1. **必填参数在构造函数中**：清晰明确
2. **可选参数用链式调用**：可读性强
3. **保持 Builder 与产品类的同步**：字段变更时及时更新
4. **在 build() 中进行校验**：确保对象合法性
5. **考虑使用 Lombok**：减少样板代码

### 9.2 Lombok @Builder 示例

```java
@Builder
public class Order {
    private Long orderId;
    private String customerName;
    private List<OrderItem> items;
    private BigDecimal totalAmount;
    private OrderStatus status;
}

// 使用
Order order = Order.builder()
    .orderId(1001L)
    .customerName("张三")
    .items(items)
    .totalAmount(new BigDecimal("999.99"))
    .status(OrderStatus.PENDING)
    .build();
```

### 9.3 Builder vs Setter

| 场景 | 推荐方式 |
|------|----------|
| 对象不可变 | Builder |
| 构造函数参数多（>4个） | Builder |
| 需要校验逻辑 | Builder |
| 简单 POJO，IDE 自动生成 | Setter |
| 需要频繁修改字段 | Setter |

## 十、总结

### 10.1 模式对比

```
创建型模式适用场景：
┌────────────┬──────────────────────────────────────┐
│   模式      │ 适用场景                              │
├────────────┼──────────────────────────────────────┤
│ 单例模式   │ 需要唯一实例，全局共享                 │
│ 工厂方法   │ 产品单一，需要扩展                     │
│ 抽象工厂   │ 产品族，需要保证兼容性                 │
│ 建造者模式  │ 复杂对象，多部件，需要链式调用        │
└────────────┴──────────────────────────────────────┘
```

### 10.2 核心要点

1. **Builder 是 Product 的静态内部类**
2. **必填参数在 Builder 构造函数中**
3. **可选参数用链式 setter**
4. **build() 方法负责创建 Product**
5. **可以在 build() 中进行最终校验**

## 结语

建造者模式是处理复杂对象创建的利器，特别是在需要大量可选参数、需要链式调用、需要保证对象不可变性等场景下。配合 Lombok 使用，可以大大减少样板代码，提高开发效率。

**下期预告**：原型模式（Prototype Pattern）

> 记住：**模式是工具，不是教条**。根据实际场景选择合适的解决方案，才能写出优雅的代码。
