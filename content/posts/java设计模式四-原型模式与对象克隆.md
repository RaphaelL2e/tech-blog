---
title: "Java设计模式（四）：原型模式与对象克隆"
date: 2026-04-13T14:30:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "原型模式", "prototype", "clone"]
---

## 前言

前三篇文章我们介绍了单例模式、工厂模式和建造者模式，今天继续 Java 设计模式系列。**原型模式（Prototype Pattern）** 是创建型模式中最直接的一种，通过复制已有对象来创建新对象。

**核心思想**：通过复制现有对象来创建新对象，而无需了解其具体类型。

<!--more-->

## 一、为什么需要原型模式

### 1.1 直接创建对象的问题

```java
// 每次都重新创建
User user1 = new User();
user1.setName("张三");
user1.setAge(25);
// ... 设置大量属性

// 需要另一个类似的用户
User user2 = new User();
user2.setName("李四");
user2.setAge(26);
// ... 再次设置大量属性
```

**问题**：
- 代码重复，繁琐
- 效率低下
- 如果对象创建复杂（如数据库查询、文件读取），开销大

### 1.2 原型模式的优势

```java
// 基于原型复制
User user1 = new User();
user1.setName("张三");
user1.setAge(25);

// 复制 user1 创建 user2
User user2 = user1.clone();
user2.setName("李四");
user2.setAge(26);
```

**优点**：
- 简化对象创建过程
- 减少重复代码
- 提高性能（避免重复初始化）
- 符合开闭原则

## 二、原型模式的实现方式

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                   Prototype (抽象原型)                       │
├─────────────────────────────────────────────────────────────┤
│ + clone()                                                  │
└─────────────────────────────────────────────────────────────┘
                    △
                    │
┌───────────────────┴───────────────────────────────────────┐
│                   ConcretePrototype (具体原型)                │
├─────────────────────────────────────────────────────────────┤
│ + clone() → 返回当前对象的副本                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Cloneable 接口（JDK 原生支持）

```java
// 原型接口
public interface Prototype<T> {
    T clone();
}

// 具体原型
public class User implements Prototype<User> {
    private String name;
    private int age;
    private Address address;  // 引用类型
    
    @Override
    public User clone() {
        try {
            return (User) super.clone();  // 浅拷贝
        } catch (CloneNotSupportedException e) {
            throw new RuntimeException(e);
        }
    }
}
```

## 三、浅拷贝与深拷贝

### 3.1 浅拷贝（Shallow Copy）

**特点**：只复制对象本身，引用类型的字段只复制引用

```java
public class User implements Cloneable {
    private String name;
    private int age;
    private Address address;  // 引用类型
    
    @Override
    protected User clone() throws CloneNotSupportedException {
        return (User) super.clone();  // Object.clone() 是浅拷贝
    }
}

// 测试
public class Client {
    public static void main(String[] args) throws CloneNotSupportedException {
        Address addr = new Address("北京", "朝阳区");
        User user1 = new User("张三", 25, addr);
        
        User user2 = user1.clone();
        user2.setName("李四");
        
        System.out.println("user1: " + user1);  // User{name='张三', age=25, address=Address{...}}
        System.out.println("user2: " + user2);  // User{name='李四', age=25, address=Address{...}}
        
        // ⚠️ 注意：user1 和 user2 的 address 是同一个对象！
        System.out.println(user1.getAddress() == user2.getAddress());  // true
        
        // 修改 user2 的地址，user1 也会变！
        user2.getAddress().setCity("上海");
        System.out.println(user1.getAddress().getCity());  // 上海
    }
}
```

**内存模型**：

```
user1 ─────┬────> name: "张三"
           │
           ├────> age: 25
           │
           ├────> address ──┐
                          │
user2 ─────┬────> name: "李四"
           │
           ├────> age: 25
           │
           └────> address ──┘  (与 user1 共享同一个 Address 对象)
```

### 3.2 深拷贝（Deep Copy）

**特点**：复制对象本身及其所有引用类型字段

**方式一：手动深拷贝**

```java
public class User implements Cloneable {
    private String name;
    private int age;
    private Address address;  // 引用类型，需要单独拷贝
    
    @Override
    protected User clone() {
        try {
            User cloned = (User) super.clone();
            // 深拷贝：创建新的 Address 对象
            cloned.address = this.address.clone();
            return cloned;
        } catch (CloneNotSupportedException e) {
            throw new RuntimeException(e);
        }
    }
}

public class Address implements Cloneable {
    private String city;
    private String district;
    
    @Override
    protected Address clone() {
        try {
            return (Address) super.clone();
        } catch (CloneNotSupportedException e) {
            throw new RuntimeException(e);
        }
    }
}
```

**方式二：序列化深拷贝（推荐）**

```java
import java.io.*;

public class DeepCloneUtil {
    
    /**
     * 使用序列化实现深拷贝
     * 优点：支持任意复杂对象
     * 缺点：性能稍低，需要类实现 Serializable
     */
    @SuppressWarnings("unchecked")
    public static <T extends Serializable> T deepClone(T object) {
        try {
            // 写入字节数组
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ObjectOutputStream oos = new ObjectOutputStream(baos);
            oos.writeObject(object);
            
            // 读出对象
            ByteArrayInputStream bais = new ByteArrayInputStream(baos.toByteArray());
            ObjectInputStream ois = new ObjectInputStream(bais);
            return (T) ois.readObject();
        } catch (IOException | ClassNotFoundException e) {
            throw new RuntimeException("深拷贝失败", e);
        }
    }
}

// 使用
public class Client {
    public static void main(String[] args) {
        Address addr = new Address("北京", "朝阳区");
        User user1 = new User("张三", 25, addr);
        
        // 深拷贝
        User user2 = DeepCloneUtil.deepClone(user1);
        
        // 验证
        System.out.println(user1.getAddress() == user2.getAddress());  // false
        
        user2.getAddress().setCity("上海");
        System.out.println(user1.getAddress().getCity());  // 北京（未改变）
    }
}
```

**方式三：JSON 序列化（推荐，简洁）**

```java
import com.fasterxml.jackson.databind.ObjectMapper;

public class JsonCloneUtil {
    
    private static final ObjectMapper mapper = new ObjectMapper();
    
    @SuppressWarnings("unchecked")
    public static <T> T deepClone(T object, Class<T> clazz) {
        try {
            String json = mapper.writeValueAsString(object);
            return mapper.readValue(json, clazz);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("JSON深拷贝失败", e);
        }
    }
}

// 使用
User user2 = JsonCloneUtil.deepClone(user1, User.class);
```

**方式四：构造方法拷贝**

```java
public class User implements Cloneable {
    private String name;
    private int age;
    private Address address;
    
    // 拷贝构造方法
    public User(User other) {
        this.name = other.name;
        this.age = other.age;
        this.address = new Address(other.address);  // 深拷贝
    }
    
    @Override
    protected User clone() {
        return new User(this);
    }
}
```

**内存模型（深拷贝）**：

```
user1 ─────┬────> name: "张三"
           │
           ├────> age: 25
           │
           └────> address ──┐
                          │
user2 ─────┬────> name: "李四"
           │
           ├────> age: 25
           │
           └────> address ──┐  (新的 Address 对象)
                          │
                          ▼
                      Address{ city: "上海", district: "朝阳区" }
```

## 四、原型管理器（Prototype Manager）

### 4.1 使用场景

当需要创建的对象种类繁多，且创建成本较高时，可以使用原型管理器缓存常用对象。

```java
// 原型接口
public interface OrderPrototype extends Cloneable {
    OrderPrototype clone();
    String getProductName();
}

// 具体原型
public class ProductOrder implements OrderPrototype {
    private String productName;
    private int quantity;
    private double price;
    
    public ProductOrder(String productName, int quantity, double price) {
        this.productName = productName;
        this.quantity = quantity;
        this.price = price;
    }
    
    @Override
    public OrderPrototype clone() {
        return new ProductOrder(productName, quantity, price);
    }
    
    @Override
    public String getProductName() {
        return productName;
    }
    
    // 计算总价
    public double getTotalPrice() {
        return quantity * price;
    }
}

// 原型管理器
public class PrototypeManager {
    
    private static final Map<String, OrderPrototype> PROTOTYPES = 
        new HashMap<>();
    
    static {
        // 初始化常用订单模板
        PROTOTYPES.put("standard", 
            new ProductOrder("标准产品", 1, 99.0));
        PROTOTYPES.put("premium", 
            new ProductOrder("高级产品", 1, 299.0));
        PROTOTYPES.put("bundle", 
            new ProductOrder("套餐产品", 5, 399.0));
    }
    
    public static void register(String key, OrderPrototype prototype) {
        PROTOTYPES.put(key, prototype);
    }
    
    public static OrderPrototype get(String key) {
        OrderPrototype prototype = PROTOTYPES.get(key);
        if (prototype == null) {
            throw new IllegalArgumentException("未知的原型: " + key);
        }
        return prototype.clone();
    }
    
    public static void main(String[] args) {
        // 快速创建订单
        OrderPrototype standardOrder = PrototypeManager.get("standard");
        System.out.println("标准订单: " + standardOrder.getProductName());
        
        OrderPrototype premiumOrder = PrototypeManager.get("premium");
        System.out.println("高级订单: " + premiumOrder.getProductName());
    }
}
```

### 4.2 动态注册

```java
public class ShapeManager {
    
    private Map<String, Shape> shapes = new HashMap<>();
    
    public void registerShape(String key, Shape shape) {
        shapes.put(key, shape);
    }
    
    public Shape createShape(String key) {
        Shape shape = shapes.get(key);
        if (shape == null) {
            throw new IllegalArgumentException("Shape not found: " + key);
        }
        return shape.clone();
    }
}

// 使用
ShapeManager manager = new ShapeManager();
manager.registerShape("circle", new Circle(10));
manager.registerShape("rectangle", new Rectangle(10, 20));

Shape circle = manager.createShape("circle");
```

## 五、JDK 中的原型模式

### 5.1 ArrayList.clone()

```java
// ArrayList 实现了 Cloneable 接口
ArrayList<String> list1 = new ArrayList<>();
list1.add("A");
list1.add("B");

// 克隆
ArrayList<String> list2 = (ArrayList<String>) list1.clone();

// ⚠️ 注意：ArrayList.clone() 是浅拷贝
list2.add("C");
System.out.println(list1);  // [A, B]  不受影响
System.out.println(list2);  // [A, B, C]

// 但如果是引用类型
ArrayList<User> users1 = new ArrayList<>();
users1.add(new User("张三"));

ArrayList<User> users2 = (ArrayList<User>) users1.clone();
users2.get(0).setName("李四");

System.out.println(users1.get(0).getName());  // 李四  被影响了！
```

### 5.2 HashMap.clone()

```java
// HashMap.clone() 也是浅拷贝
Map<String, Object> map1 = new HashMap<>();
map1.put("key", new User("张三"));

Map<String, Object> map2 = (Map<String, Object>) ((HashMap<String, Object>) map1).clone();

// ⚠️ map1 和 map2 的值对象是同一个引用
```

### 5.3 原型模式在集合中的应用

```java
// 复制列表
List<String> original = Arrays.asList("A", "B", "C");
List<String> copy = new ArrayList<>(original);

// 或者使用 Java 10+ 的 copyOf
List<String> immutableCopy = List.copyOf(original);

// 复制 Map
Map<String, Integer> originalMap = new HashMap<>();
originalMap.put("A", 1);
originalMap.put("B", 2);

Map<String, Integer> copyMap = new HashMap<>(originalMap);
```

## 六、Spring 中的原型模式

### 6.1 scope="prototype"

```xml
<!-- Spring 配置 -->
<bean id="userService" class="com.example.UserService" scope="prototype">
    <property name="name" value="test"/>
</bean>
```

```java
// 每次获取都创建新实例
ApplicationContext ctx = new ClassPathXmlApplicationContext("beans.xml");
UserService service1 = ctx.getBean("userService", UserService.class);
UserService service2 = ctx.getBean("userService", UserService.class);
System.out.println(service1 == service2);  // false
```

### 6.2 ObjectFactory.createPrototype()

```java
// 创建原型 Bean
@Autowired
private ObjectFactory<MyPrototypeBean> myPrototypeBeanFactory;

public void usePrototype() {
    // 每次调用都创建新实例
    MyPrototypeBean bean = myPrototypeBeanFactory.getObject();
}
```

## 七、实战案例

### 7.1 简历克隆系统

```java
// 可克隆的简历
public class Resume implements Cloneable {
    private String name;
    private String gender;
    private int age;
    private String timeArea;
    private String company;
    
    // 构造函数
    public Resume(String name) {
        this.name = name;
    }
    
    // 设置个人信息
    public void setPersonalInfo(String gender, int age) {
        this.gender = gender;
        this.age = age;
    }
    
    // 设置工作经历
    public void setWorkExperience(String timeArea, String company) {
        this.timeArea = timeArea;
        this.company = company;
    }
    
    // 显示
    public void display() {
        System.out.println(this.name + " - " + this.gender + " - " + this.age);
        System.out.println("工作经历: " + this.timeArea + " - " + this.company);
    }
    
    // 克隆
    @Override
    protected Resume clone() {
        return new Resume(this.name);  // 深拷贝
    }
}

// 使用
public class Client {
    public static void main(String[] args) {
        // 创建原始简历
        Resume resume1 = new Resume("张三");
        resume1.setPersonalInfo("男", 28);
        resume1.setWorkExperience("2020-2024", "阿里巴巴");
        
        // 克隆多份简历
        Resume resume2 = resume1.clone();
        resume2.setWorkExperience("2018-2020", "字节跳动");
        
        Resume resume3 = resume1.clone();
        resume3.setWorkExperience("2016-2018", "腾讯");
        
        // 显示
        resume1.display();
        resume2.display();
        resume3.display();
    }
}
```

### 7.2 游戏怪物生成

```java
// 怪物原型
public abstract class Monster implements Cloneable {
    protected String name;
    protected int attack;
    protected int defense;
    protected int health;
    
    public abstract Monster clone();
    
    @Override
    protected Monster clone() {
        try {
            return (Monster) super.clone();
        } catch (CloneNotSupportedException e) {
            throw new RuntimeException(e);
        }
    }
}

// 具体怪物
public class Slime extends Monster {
    public Slime() {
        this.name = "史莱姆";
        this.attack = 5;
        this.defense = 2;
        this.health = 20;
    }
    
    @Override
    public Monster clone() {
        return new Slime();  // 深拷贝
    }
}

public class Dragon extends Monster {
    public Dragon() {
        this.name = "巨龙";
        this.attack = 100;
        this.defense = 80;
        this.health = 1000;
    }
    
    @Override
    public Monster clone() {
        return new Dragon();
    }
}

// 怪物工厂（使用原型模式）
public class MonsterFactory {
    
    private Map<String, Monster> prototypes = new HashMap<>();
    
    public MonsterFactory() {
        register("slime", new Slime());
        register("dragon", new Dragon());
    }
    
    public void register(String type, Monster monster) {
        prototypes.put(type, monster);
    }
    
    public Monster create(String type) {
        Monster monster = prototypes.get(type);
        if (monster == null) {
            throw new IllegalArgumentException("Unknown monster type: " + type);
        }
        return monster.clone();
    }
    
    // 批量生成
    public List<Monster> createBatch(String type, int count) {
        List<Monster> monsters = new ArrayList<>();
        Monster prototype = prototypes.get(type);
        if (prototype == null) {
            throw new IllegalArgumentException("Unknown monster type: " + type);
        }
        for (int i = 0; i < count; i++) {
            monsters.add(prototype.clone());
        }
        return monsters;
    }
}

// 使用
public class Game {
    public static void main(String[] args) {
        MonsterFactory factory = new MonsterFactory();
        
        // 生成单个怪物
        Monster slime = factory.create("slime");
        
        // 批量生成
        List<Monster> dragonArmy = factory.createBatch("dragon", 10);
        
        System.out.println("生成了 " + dragonArmy.size() + " 条龙");
    }
}
```

## 八、克隆的注意事项

### 8.1 final 字段问题

```java
public class User implements Cloneable {
    private final String id;  // final 字段无法在 clone 后重新赋值
    
    public User(String id) {
        this.id = id;
    }
    
    @Override
    protected User clone() throws CloneNotSupportedException {
        // 解决方案：调用 super.clone() 后手动设置
        User cloned = (User) super.clone();
        // 注意：id 已经是正确的值，因为是基本类型或不可变类型
        return cloned;
    }
}
```

### 8.2 构造函数中的业务逻辑

```java
public class User implements Cloneable {
    private String name;
    private List<String> logs = new ArrayList<>();
    
    public User(String name) {
        this.name = name;
        System.out.println("User 构造函数被调用");
        logs.add("用户 " + name + " 被创建");
    }
    
    @Override
    protected User clone() {
        // 注意：不会调用构造函数！
        User cloned = new User(this.name);  // 手动调用
        cloned.logs = new ArrayList<>(this.logs);  // 深拷贝列表
        return cloned;
    }
}
```

### 8.3 克隆与不可变对象

```java
// 不可变对象不需要克隆
public final class ImmutableUser {
    private final String name;
    private final int age;
    
    // clone 没有意义，因为对象不可变
    // 直接复用即可
}
```

## 九、面试常见问题

### Q1：深拷贝和浅拷贝的区别？

- **浅拷贝**：只复制对象本身，引用类型字段共享同一个引用
- **深拷贝**：递归复制所有引用类型字段，新旧对象完全独立

### Q2：Object.clone() 的特点？

1. 是 native 方法，性能高
2. 默认是浅拷贝
3. 需要类实现 Cloneable 接口
4. 不会调用构造函数

### Q3：克隆失败的原因？

1. 类没有实现 Cloneable 接口
2. 存在 final 字段无法赋值
3. 引用类型字段没有正确深拷贝

### Q4：如何选择深拷贝方式？

| 场景 | 推荐方式 |
|------|----------|
| 对象简单，嵌套少 | 手动 clone |
| 对象复杂，嵌套多 | 序列化或 JSON |
| 需要高性能 | 手动 clone |
| 需要通用解决方案 | 序列化 |

### Q5：原型模式与工厂模式的区别？

| 维度 | 原型模式 | 工厂模式 |
|------|---------|---------|
| 创建方式 | 复制已有对象 | 创建新对象 |
| 复杂度 | 简单 | 复杂 |
| 性能 | 好（避免重复初始化） | 一般 |
| 依赖 | 不需要知道具体类 | 需要知道具体类 |

## 十、总结

### 10.1 模式对比

```
创建型模式对比：
┌──────────┬────────────────────────────────────┐
│   模式    │ 适用场景                            │
├──────────┼────────────────────────────────────┤
│ 单例模式  │ 全局唯一实例                        │
│ 工厂模式  │ 创建同系列产品                      │
│ 建造者模式│ 构建复杂对象                        │
│ 原型模式  │ 复制已有对象，性能敏感              │
└──────────┴────────────────────────────────────┘
```

### 10.2 使用建议

1. **优先使用浅拷贝**：如果对象没有嵌套引用类型
2. **使用深拷贝**：如果对象有嵌套的引用类型
3. **推荐序列化方式**：代码简洁，支持任意复杂对象
4. **注意线程安全**：克隆后的对象是独立的

## 结语

原型模式是创建型模式中最直接的一种，通过复制已有对象来创建新对象。掌握浅拷贝与深拷贝的区别，理解不同的实现方式，能够在实际开发中灵活运用。

**下期预告**：适配器模式（Adapter Pattern）

> 记住：**clone() 是 Object 的方法，但需要正确实现**。
