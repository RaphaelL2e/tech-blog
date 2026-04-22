---
title: "Java设计模式（十八）：桥接模式深度实践"
date: 2026-04-22T10:40:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "桥接模式", "bridge", "抽象与实现分离"]
---

## 前言

桥接模式（Bridge Pattern）是一种结构型设计模式，它的核心思想是：**将抽象部分与实现部分分离，使它们都可以独立地变化**。

**核心思想**：用组合替代继承，将两个独立变化的维度解耦。

<!--more-->

## 一、为什么需要桥接模式

### 1.1 继承爆炸问题

假设我们要开发一个图形绘制系统，支持多种形状（圆形、矩形、三角形）和多种颜色（红色、蓝色、绿色）。用继承实现：

```
        Shape
       / | \
    Circle Rectangle Triangle
    / | \     / | \     / | \
 RedCircle BlueCircle GreenCircle
 RedRect   BlueRect   GreenRect
 RedTriangle BlueTriangle GreenTriangle
```

新增一种形状或颜色，子类数量呈指数级增长。这就是**类爆炸**问题。

桥接模式通过将"形状"和"颜色"分离为两个独立的维度，用组合代替继承来解决：

```
Shape ←→ Color (组合关系)
  |         |
Circle    Red
Rectangle Blue
Triangle  Green
```

### 1.2 两个独立变化的维度

桥接模式适用于"两个维度独立变化"的场景：

| 抽象维度 | 实现维度 |
|---------|---------|
| 形状 | 颜色 |
| 消息类型 | 发送方式 |
| 设备类型 | 远程控制协议 |
| 图形 | 渲染引擎 |

## 二、桥接模式的结构

### 2.1 类图

```
┌───────────────────┐        ┌──────────────────┐
│  Abstraction      │        │ Implementor      │
│  (抽象类)         │        │ (实现接口)        │
│───────────────────│        │──────────────────│
│ # impl: Implementor│──────→│ + operationImpl()│
│───────────────────│        └────────┬─────────┘
│ + operation()     │                 │
└────────┬──────────┘          ┌──────┴──────┐
         │                     │             │
    ┌────┴─────┐         ┌─────┴────┐  ┌─────┴────┐
    │RefinedAb-│         │ConcreteIm-│  │ConcreteIm-│
    │ straction│         │  plA      │  │  plB      │
    └──────────┘         └──────────┘  └──────────┘
```

### 2.2 核心角色

| 角色 | 职责 |
|------|------|
| Abstraction（抽象类） | 定义抽象接口，持有 Implementor 引用 |
| RefinedAbstraction | 扩展 Abstraction 的接口 |
| Implementor（实现接口） | 定义实现类的接口 |
| ConcreteImplementor | 具体实现类 |

### 2.3 完整实现

```java
// ========== 1. 实现接口：颜色 ==========
public interface Color {
    String applyColor();
}

// ========== 2. 具体实现：红色 ==========
public class RedColor implements Color {
    @Override
    public String applyColor() {
        return "🔴 红色";
    }
}

// ========== 3. 具体实现：蓝色 ==========
public class BlueColor implements Color {
    @Override
    public String applyColor() {
        return "🔵 蓝色";
    }
}

// ========== 4. 具体实现：绿色 ==========
public class GreenColor implements Color {
    @Override
    public String applyColor() {
        return "🟢 绿色";
    }
}

// ========== 5. 抽象类：形状 ==========
public abstract class Shape {
    protected Color color;  // 桥接：组合而非继承
    
    public Shape(Color color) {
        this.color = color;
    }
    
    public abstract void draw();
    
    public void setColor(Color color) {
        this.color = color;
    }
}

// ========== 6. 扩展抽象：圆形 ==========
public class Circle extends Shape {
    private final int radius;
    
    public Circle(Color color, int radius) {
        super(color);
        this.radius = radius;
    }
    
    @Override
    public void draw() {
        System.out.println("绘制圆形 [半径=" + radius + ", 颜色=" + color.applyColor() + "]");
    }
}

// ========== 7. 扩展抽象：矩形 ==========
public class Rectangle extends Shape {
    private final int width;
    private final int height;
    
    public Rectangle(Color color, int width, int height) {
        super(color);
        this.width = width;
        this.height = height;
    }
    
    @Override
    public void draw() {
        System.out.println("绘制矩形 [宽=" + width + ", 高=" + height + 
            ", 颜色=" + color.applyColor() + "]");
    }
}

// ========== 8. 扩展抽象：三角形 ==========
public class Triangle extends Shape {
    private final int base;
    private final int height;
    
    public Triangle(Color color, int base, int height) {
        super(color);
        this.base = base;
        this.height = height;
    }
    
    @Override
    public void draw() {
        System.out.println("绘制三角形 [底=" + base + ", 高=" + height + 
            ", 颜色=" + color.applyColor() + "]");
    }
}

// ========== 9. 客户端 ==========
public class ShapeDemo {
    public static void main(String[] args) {
        // 任意组合形状和颜色，无类爆炸
        Shape redCircle = new Circle(new RedColor(), 10);
        Shape blueCircle = new Circle(new BlueColor(), 20);
        Shape greenRect = new Rectangle(new GreenColor(), 30, 40);
        Shape redTriangle = new Triangle(new RedColor(), 15, 20);
        
        redCircle.draw();
        blueCircle.draw();
        greenRect.draw();
        redTriangle.draw();
        
        // 运行时切换颜色
        System.out.println("\n--- 切换颜色 ---");
        redCircle.setColor(new BlueColor());
        redCircle.draw();
    }
}
```

运行结果：

```
绘制圆形 [半径=10, 颜色=🔴 红色]
绘制圆形 [半径=20, 颜色=🔵 蓝色]
绘制矩形 [宽=30, 高=40, 颜色=🟢 绿色]
绘制三角形 [底=15, 高=20, 颜色=🔴 红色]

--- 切换颜色 ---
绘制圆形 [半径=10, 颜色=🔵 蓝色]
```

## 三、桥接模式的高级用法

### 3.1 消息系统桥接

将消息类型与发送方式分离：

```java
// ========== 实现接口：发送方式 ==========
public interface MessageSender {
    void sendMessage(String content, String recipient);
}

// 邮件发送
public class EmailSender implements MessageSender {
    @Override
    public void sendMessage(String content, String recipient) {
        System.out.println("📧 邮件发送给 " + recipient + ": " + content);
    }
}

// 短信发送
public class SmsSender implements MessageSender {
    @Override
    public void sendMessage(String content, String recipient) {
        System.out.println("📱 短信发送给 " + recipient + ": " + content);
    }
}

// 微信发送
public class WeChatSender implements MessageSender {
    @Override
    public void sendMessage(String content, String recipient) {
        System.out.println("💬 微信发送给 " + recipient + ": " + content);
    }
}

// ========== 抽象类：消息类型 ==========
public abstract class Message {
    protected MessageSender sender;
    
    public Message(MessageSender sender) {
        this.sender = sender;
    }
    
    public abstract void send(String recipient);
}

// 普通消息
public class TextMessage extends Message {
    private final String content;
    
    public TextMessage(String content, MessageSender sender) {
        super(sender);
        this.content = content;
    }
    
    @Override
    public void send(String recipient) {
        sender.sendMessage(content, recipient);
    }
}

// 紧急消息（带标记）
public class UrgentMessage extends Message {
    private final String content;
    
    public UrgentMessage(String content, MessageSender sender) {
        super(sender);
        this.content = content;
    }
    
    @Override
    public void send(String recipient) {
        sender.sendMessage("【紧急】" + content, recipient);
    }
}

// 加密消息
public class EncryptedMessage extends Message {
    private final String content;
    
    public EncryptedMessage(String content, MessageSender sender) {
        super(sender);
        this.content = content;
    }
    
    @Override
    public void send(String recipient) {
        String encrypted = "ENC(" + content.hashCode() + ")";
        sender.sendMessage(encrypted, recipient);
    }
}

// ========== 客户端 ==========
public class MessageDemo {
    public static void main(String[] args) {
        // 任意组合消息类型和发送方式
        Message emailText = new TextMessage("你好", new EmailSender());
        Message smsUrgent = new UrgentMessage("服务器宕机", new SmsSender());
        Message wechatEncrypted = new EncryptedMessage("密码:123456", new WeChatSender());
        
        emailText.send("alice@example.com");
        smsUrgent.send("13800138000");
        wechatEncrypted.send("wechat_user_001");
    }
}
```

### 3.2 设备与遥控器桥接

将设备与遥控器分离：

```java
// ========== 实现接口：设备 ==========
public interface Device {
    void turnOn();
    void turnOff();
    void setVolume(int volume);
    String getStatus();
}

// 电视
public class TV implements Device {
    private boolean on = false;
    private int volume = 30;
    
    @Override
    public void turnOn() { on = true; System.out.println("📺 电视已开启"); }
    @Override
    public void turnOff() { on = false; System.out.println("📺 电视已关闭"); }
    @Override
    public void setVolume(int volume) { this.volume = volume; System.out.println("📺 音量: " + volume); }
    @Override
    public String getStatus() { return "📺 电视 " + (on ? "开启" : "关闭") + " 音量=" + volume; }
}

// 收音机
public class Radio implements Device {
    private boolean on = false;
    private int volume = 20;
    
    @Override
    public void turnOn() { on = true; System.out.println("📻 收音机已开启"); }
    @Override
    public void turnOff() { on = false; System.out.println("📻 收音机已关闭"); }
    @Override
    public void setVolume(int volume) { this.volume = volume; System.out.println("📻 音量: " + volume); }
    @Override
    public String getStatus() { return "📻 收音机 " + (on ? "开启" : "关闭") + " 音量=" + volume; }
}

// ========== 抽象类：遥控器 ==========
public abstract class RemoteControl {
    protected Device device;
    
    public RemoteControl(Device device) {
        this.device = device;
    }
    
    public void turnOn() { device.turnOn(); }
    public void turnOff() { device.turnOff(); }
    public void volumeUp() { device.setVolume(getCurrentVolume() + 10); }
    public void volumeDown() { device.setVolume(Math.max(0, getCurrentVolume() - 10)); }
    
    protected abstract int getCurrentVolume();
}

// 基础遥控器
public class BasicRemote extends RemoteControl {
    public BasicRemote(Device device) { super(device); }
    
    @Override
    protected int getCurrentVolume() { return 30; }  // 简化
}

// 高级遥控器（带静音功能）
public class AdvancedRemote extends RemoteControl {
    private boolean muted = false;
    private int previousVolume;
    
    public AdvancedRemote(Device device) { super(device); }
    
    public void mute() {
        if (!muted) {
            previousVolume = getCurrentVolume();
            device.setVolume(0);
            muted = true;
        } else {
            device.setVolume(previousVolume);
            muted = false;
        }
    }
    
    @Override
    protected int getCurrentVolume() { return 30; }
}

// 客户端
RemoteControl tvRemote = new AdvancedRemote(new TV());
tvRemote.turnOn();
tvRemote.volumeUp();
((AdvancedRemote) tvRemote).mute();
```

## 四、桥接模式在 JDK 中的应用

### 4.1 JDBC 驱动

JDBC 是桥接模式的经典应用：

```java
// Abstraction: java.sql.Connection（抽象接口）
// Implementor: 数据库驱动（具体实现）
// Bridge: DriverManager 桥接两者

// 切换实现只需更换驱动，应用代码不变
Connection conn1 = DriverManager.getConnection("jdbc:mysql://localhost/db");
Connection conn2 = DriverManager.getConnection("jdbc:postgresql://localhost/db");
Connection conn3 = DriverManager.getConnection("jdbc:oracle://localhost/db");

// 同一套 API，不同的底层实现
PreparedStatement ps = conn.prepareStatement("SELECT * FROM users");
ResultSet rs = ps.executeQuery();
```

### 4.2 AWT 组件与 Peer

Java AWT 将组件（Button、Label）与平台实现（Peer）分离：

```java
// Abstraction: java.awt.Button
// Implementor: java.awt.peer.ButtonPeer (平台特定实现)
// 每个平台有不同的 Peer 实现（Windows、macOS、Linux）
```

## 五、桥接模式 vs 其他模式

### 5.1 对比策略模式

| 维度 | 桥接模式 | 策略模式 |
|------|---------|---------|
| 目的 | 分离两个独立变化的维度 | 选择算法/策略 |
| 关系 | 抽象和实现是长期组合 | 策略可以随时替换 |
| 结构 | 抽象持有实现引用 | 上下文持有策略引用 |
| 设计 | 正向设计 | 行为模式 |

### 5.2 对比适配器模式

| 维度 | 桥接模式 | 适配器模式 |
|------|---------|-----------|
| 目的 | 分离抽象和实现 | 接口转换 |
| 设计阶段 | 设计初期 | 事后补救 |
| 结构 | 双向设计 | 单向适配 |

## 六、桥接模式的优缺点

### 优点

1. **分离抽象和实现**：两个维度独立变化
2. **开闭原则**：新增抽象或实现无需修改另一方
3. **组合替代继承**：避免类爆炸
4. **运行时切换**：可以在运行时切换实现

### 缺点

1. **增加复杂性**：需要正确识别独立变化的维度
2. **聚合关系**：增加了对象间的间接关系
3. **设计难度**：需要前期就识别出需要桥接的维度

### 适用场景

- 两个维度独立变化的场景
- 需要在运行时切换实现
- 不希望使用继承导致类爆炸
- 需要在多个维度上扩展一个类

## 七、实战：跨平台 UI 渲染

用桥接模式实现跨平台 UI 渲染引擎：

```java
// ========== 实现接口：渲染引擎 ==========
public interface RenderEngine {
    void drawCircle(int x, int y, int radius);
    void drawRectangle(int x, int y, int width, int height);
    void drawText(int x, int y, String text);
}

// DirectX 渲染
public class DirectXRenderer implements RenderEngine {
    @Override
    public void drawCircle(int x, int y, int radius) {
        System.out.println("🎮 DirectX: 绘制圆形 @ (" + x + "," + y + ") 半径=" + radius);
    }
    
    @Override
    public void drawRectangle(int x, int y, int width, int height) {
        System.out.println("🎮 DirectX: 绘制矩形 @ (" + x + "," + y + ") 宽=" + width + " 高=" + height);
    }
    
    @Override
    public void drawText(int x, int y, String text) {
        System.out.println("🎮 DirectX: 绘制文字 @ (" + x + "," + y + ") '" + text + "'");
    }
}

// OpenGL 渲染
public class OpenGLRenderer implements RenderEngine {
    @Override
    public void drawCircle(int x, int y, int radius) {
        System.out.println("🔺 OpenGL: 绘制圆形 @ (" + x + "," + y + ") 半径=" + radius);
    }
    
    @Override
    public void drawRectangle(int x, int y, int width, int height) {
        System.out.println("🔺 OpenGL: 绘制矩形 @ (" + x + "," + y + ") 宽=" + width + " 高=" + height);
    }
    
    @Override
    public void drawText(int x, int y, String text) {
        System.out.println("🔺 OpenGL: 绘制文字 @ (" + x + "," + y + ") '" + text + "'");
    }
}

// SVG 渲染
public class SVGRenderer implements RenderEngine {
    @Override
    public void drawCircle(int x, int y, int radius) {
        System.out.println("📐 SVG: <circle cx=\"" + x + "\" cy=\"" + y + "\" r=\"" + radius + "\"/>");
    }
    
    @Override
    public void drawRectangle(int x, int y, int width, int height) {
        System.out.println("📐 SVG: <rect x=\"" + x + "\" y=\"" + y + "\" width=\"" + width + "\" height=\"" + height + "\"/>");
    }
    
    @Override
    public void drawText(int x, int y, String text) {
        System.out.println("📐 SVG: <text x=\"" + x + "\" y=\"" + y + "\">" + text + "</text>");
    }
}

// ========== 抽象类：UI 组件 ==========
public abstract class UIComponent {
    protected RenderEngine engine;
    protected int x, y;
    
    public UIComponent(RenderEngine engine, int x, int y) {
        this.engine = engine;
        this.x = x;
        this.y = y;
    }
    
    public abstract void render();
    
    public void setEngine(RenderEngine engine) {
        this.engine = engine;
    }
}

// 按钮
public class Button extends UIComponent {
    private String label;
    private int width = 100;
    private int height = 30;
    
    public Button(RenderEngine engine, int x, int y, String label) {
        super(engine, x, y);
        this.label = label;
    }
    
    @Override
    public void render() {
        engine.drawRectangle(x, y, width, height);
        engine.drawText(x + 10, y + 20, label);
    }
}

// 图标
public class Icon extends UIComponent {
    private int radius = 20;
    
    public Icon(RenderEngine engine, int x, int y) {
        super(engine, x, y);
    }
    
    @Override
    public void render() {
        engine.drawCircle(x, y, radius);
    }
}

// ========== 客户端 ==========
public class UIDemo {
    public static void main(String[] args) {
        System.out.println("=== DirectX 渲染 ===");
        RenderEngine directX = new DirectXRenderer();
        Button btn1 = new Button(directX, 10, 10, "Click Me");
        Icon icon1 = new Icon(directX, 200, 30);
        btn1.render();
        icon1.render();
        
        System.out.println("\n=== OpenGL 渲染 ===");
        RenderEngine opengl = new OpenGLRenderer();
        Button btn2 = new Button(opengl, 10, 10, "Click Me");
        Icon icon2 = new Icon(opengl, 200, 30);
        btn2.render();
        icon2.render();
        
        System.out.println("\n=== 运行时切换渲染引擎 ===");
        btn2.setEngine(new SVGRenderer());
        btn2.render();
    }
}
```

## 八、桥接模式在 Spring 中的应用

### 8.1 PlatformTransactionManager

Spring 的事务管理器是桥接模式的体现：

```java
// Abstraction: @Transactional 注解 / TransactionTemplate
// Implementor: PlatformTransactionManager（不同实现）
// Bridge: Spring 事务基础设施桥接两者

// 切换实现只需更换 TransactionManager Bean
@Bean
public PlatformTransactionManager transactionManager(DataSource dataSource) {
    // JDBC/Hibernate/JTA 不同的实现
    return new DataSourceTransactionManager(dataSource);
}
```

### 8.2 ViewResolver

Spring MVC 的视图解析也是桥接：

```java
// Abstraction: Controller 返回视图名
// Implementor: ViewResolver（不同实现：JSP、Thymeleaf、Freemarker）
// 同一个视图名，可以用不同的 ViewResolver 渲染
```

## 九、面试常见问题

### Q1: 桥接模式的核心思想是什么？

桥接模式将抽象部分与实现部分分离，使它们可以独立变化。通过组合关系代替继承关系，避免在两个独立变化的维度上出现类爆炸问题。核心是"解耦两个维度"。

### Q2: 桥接模式和策略模式有什么区别？

策略模式的目的是在运行时选择不同的算法/策略，强调"可替换"。桥接模式的目的是分离两个独立变化的维度，强调"独立扩展"。策略模式通常只有一个变化维度，桥接模式有两个。

### Q3: 什么场景下应该使用桥接模式？

- 两个维度独立变化（如形状+颜色、消息类型+发送方式）
- 不希望使用多层继承导致类爆炸
- 需要在运行时切换实现
- 需要跨多个维度扩展一个类

### Q4: 如何识别需要桥接的维度？

如果继承层次中出现"Cartesian 积"——即子类数量 = 维度1数量 × 维度2数量 × ...，就应该考虑桥接模式。例如 3种形状 × 3种颜色 = 9个子类，这就是一个信号。

### Q5: 桥接模式中抽象和实现的关系是什么？

抽象持有实现的引用，通过组合关系连接。抽象定义高层接口，实现定义底层操作。两者可以独立扩展——新增抽象子类不需要修改实现，新增实现子类也不需要修改抽象。

## 十、总结

桥接模式是解决"多维度变化"问题的利器，它用组合替代继承，将两个独立变化的维度解耦。

**核心要点**：

1. **分离维度**：抽象和实现独立变化
2. **组合优于继承**：避免类爆炸
3. **运行时切换**：可以动态更换实现
4. **JDBC 经典**：JDBC 是最经典的桥接模式应用
5. **识别信号**：继承层次出现 Cartesian 积时考虑桥接

桥接模式的精髓在于"找到变化的维度，然后分离它们"。正确识别独立变化的维度是使用桥接模式的关键。

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
- [Java设计模式（十七）：代理模式深度实践](/posts/java设计模式十七-代理模式深度实践/)
