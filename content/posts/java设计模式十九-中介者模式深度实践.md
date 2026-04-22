---
title: "Java设计模式（十九）：中介者模式深度实践"
date: 2026-04-22T10:50:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "中介者模式", "mediator", "同事间解耦"]
---

## 前言

中介者模式（Mediator Pattern）是一种行为型设计模式，它的核心思想是：**用一个中介对象来封装一系列的对象交互，使各对象不需要显式地相互引用，从而使其耦合松散**。

**核心思想**：将多对多的交互转化为一对多，通过中介者集中协调。

<!--more-->

## 一、为什么需要中介者模式

### 1.1 对象间的网状依赖

假设我们有一个聊天室系统，用户之间直接通信：

```
UserA ←→ UserB
  ↕    ×    ↕
UserD ←→ UserC
```

每个用户需要知道其他所有用户的存在，形成网状依赖。新增或移除一个用户，所有相关用户都要修改。

中介者模式将网状依赖变为星状：

```
      UserA
        |
UserD - Mediator - UserB
        |
      UserC
```

### 1.2 迪米特法则的体现

中介者模式符合迪米特法则：每个同事对象只与中介者交互，不需要了解其他同事的细节。

## 二、中介者模式的结构

### 2.1 类图

```
┌──────────────────────┐
│    Mediator (抽象)    │
│──────────────────────│
│ + colleagueChanged() │
└──────────┬───────────┘
           │
     ┌─────┴──────┐
     │            │
┌────┴────┐  ┌────┴──────┐
│Concrete-│  │ Colleague  │
│Mediator │  │  (抽象同事) │
│─────────│  │───────────│
│colleague│  │ mediator  │
│changed()│  │ changed() │
└─────────┘  └─────┬─────┘
                   │
            ┌──────┼──────┐
            │      │      │
       ┌────┴──┐ ┌─┴──┐ ┌┴─────┐
       │ColA  │ │ColB│ │ColC  │
       └──────┘ └────┘ └──────┘
```

### 2.2 完整实现：聊天室

```java
// ========== 1. 抽象中介者 ==========
public interface ChatMediator {
    void sendMessage(String message, User sender);
    void addUser(User user);
}

// ========== 2. 抽象同事 ==========
public abstract class User {
    protected ChatMediator mediator;
    protected String name;
    
    public User(ChatMediator mediator, String name) {
        this.mediator = mediator;
        this.name = name;
    }
    
    public String getName() { return name; }
    
    public abstract void send(String message);
    public abstract void receive(String message, String from);
}

// ========== 3. 具体同事 ==========
public class ChatUser extends User {
    public ChatUser(ChatMediator mediator, String name) {
        super(mediator, name);
    }
    
    @Override
    public void send(String message) {
        System.out.println(this.name + " 发送: " + message);
        mediator.sendMessage(message, this);
    }
    
    @Override
    public void receive(String message, String from) {
        System.out.println("  → " + this.name + " 收到来自 " + from + " 的消息: " + message);
    }
}

// ========== 4. 具体中介者：聊天室 ==========
public class ChatRoom implements ChatMediator {
    private final List<User> users = new ArrayList<>();
    
    @Override
    public void addUser(User user) {
        users.add(user);
    }
    
    @Override
    public void sendMessage(String message, User sender) {
        for (User user : users) {
            if (user != sender) {  // 不发给自己
                user.receive(message, sender.getName());
            }
        }
    }
}

// ========== 5. 客户端 ==========
public class ChatDemo {
    public static void main(String[] args) {
        ChatMediator chatRoom = new ChatRoom();
        
        User alice = new ChatUser(chatRoom, "Alice");
        User bob = new ChatUser(chatRoom, "Bob");
        User charlie = new ChatUser(chatRoom, "Charlie");
        
        chatRoom.addUser(alice);
        chatRoom.addUser(bob);
        chatRoom.addUser(charlie);
        
        alice.send("大家好！");
        bob.send("你好 Alice！");
    }
}
```

运行结果：

```
Alice 发送: 大家好！
  → Bob 收到来自 Alice 的消息: 大家好！
  → Charlie 收到来自 Alice 的消息: 大家好！
Bob 发送: 你好 Alice！
  → Alice 收到来自 Bob 的消息: 你好 Alice！
  → Charlie 收到来自 Bob 的消息: 你好 Alice！
```

## 三、中介者模式的高级用法

### 3.1 带权限的聊天中介者

```java
public class PrivateChatMediator implements ChatMediator {
    private final List<User> users = new ArrayList<>();
    private final Map<String, Set<String>> blocked = new HashMap<>();
    
    @Override
    public void addUser(User user) {
        users.add(user);
    }
    
    public void block(String blocker, String blockedUser) {
        blocked.computeIfAbsent(blocker, k -> new HashSet<>()).add(blockedUser);
    }
    
    @Override
    public void sendMessage(String message, User sender) {
        for (User user : users) {
            if (user != sender) {
                Set<String> blockedList = blocked.get(user.getName());
                if (blockedList == null || !blockedList.contains(sender.getName())) {
                    user.receive(message, sender.getName());
                }
            }
        }
    }
}
```

### 3.2 UI 组件中介者

用中介者模式协调 UI 组件之间的交互：

```java
// ========== 抽象中介者 ==========
public interface UIMediator {
    void notify(Component sender, String event);
}

// ========== UI 组件基类 ==========
public abstract class Component {
    protected UIMediator mediator;
    
    public void setMediator(UIMediator mediator) {
        this.mediator = mediator;
    }
    
    public abstract void update();
}

// ========== 具体组件 ==========
public class CheckBox extends Component {
    private boolean checked = false;
    
    public void toggle() {
        checked = !checked;
        System.out.println("☑️ 复选框 " + (checked ? "选中" : "取消"));
        mediator.notify(this, checked ? "checked" : "unchecked");
    }
    
    public boolean isChecked() { return checked; }
    
    @Override
    public void update() { }
}

public class TextBox extends Component {
    private String text = "";
    private boolean enabled = true;
    
    public void input(String text) {
        this.text = text;
        System.out.println("📝 输入框内容: " + text);
        mediator.notify(this, "input");
    }
    
    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
        System.out.println("📝 输入框 " + (enabled ? "启用" : "禁用"));
    }
    
    @Override
    public void update() { }
}

public class Button extends Component {
    private boolean enabled = false;
    
    public void click() {
        if (enabled) {
            System.out.println("🔘 按钮被点击！");
        } else {
            System.out.println("🔘 按钮被禁用，无法点击");
        }
    }
    
    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
        System.out.println("🔘 按钮 " + (enabled ? "启用" : "禁用"));
    }
    
    @Override
    public void update() { }
}

// ========== 具体中介者 ==========
public class FormMediator implements UIMediator {
    private CheckBox agreeCheckbox;
    private TextBox nameTextBox;
    private Button submitButton;
    
    public void setAgreeCheckbox(CheckBox cb) { this.agreeCheckbox = cb; }
    public void setNameTextBox(TextBox tb) { this.nameTextBox = tb; }
    public void setSubmitButton(Button btn) { this.submitButton = btn; }
    
    @Override
    public void notify(Component sender, String event) {
        if (sender == agreeCheckbox) {
            // 复选框变化 → 更新按钮状态
            boolean canSubmit = agreeCheckbox.isChecked();
            submitButton.setEnabled(canSubmit);
        } else if (sender == nameTextBox) {
            // 输入变化 → 也可以联动
            System.out.println("📋 表单数据已更新");
        }
    }
}

// 客户端
FormMediator mediator = new FormMediator();
CheckBox agree = new CheckBox(); agree.setMediator(mediator);
TextBox name = new TextBox(); name.setMediator(mediator);
Button submit = new Button(); submit.setMediator(mediator);

mediator.setAgreeCheckbox(agree);
mediator.setNameTextBox(name);
mediator.setSubmitButton(submit);

submit.click();       // 禁用
agree.toggle();       // 选中 → 按钮启用
submit.click();       // 可以点击
```

## 四、中介者模式在 JDK 中的应用

### 4.1 Timer 与 TimerTask

`java.util.Timer` 可以看作中介者，协调多个 TimerTask 的调度：

```java
Timer timer = new Timer();  // 中介者
timer.schedule(task1, 1000);
timer.schedule(task2, 2000);
timer.schedule(task3, 3000);
```

### 4.2 ExecutorService

线程池是中介者模式的变体——任务提交者不需要知道哪个线程执行任务：

```java
ExecutorService executor = Executors.newFixedThreadPool(4);  // 中介者
executor.submit(task1);  // 不需要知道哪个线程执行
executor.submit(task2);
```

## 五、中介者模式 vs 其他模式

### 5.1 对比观察者模式

| 维度 | 中介者模式 | 观察者模式 |
|------|---------|-----------|
| 交互方式 | 双向（同事↔中介者） | 单向（主题→观察者） |
| 目的 | 消除同事间直接依赖 | 一对多通知 |
| 中心化 | 有中心（中介者） | 有中心（主题） |
| 复杂度 | 中介者可能变得复杂 | 相对简单 |

### 5.2 对比外观模式

| 维度 | 中介者模式 | 外观模式 |
|------|---------|---------|
| 交互 | 双向 | 单向 |
| 目的 | 解耦同事间交互 | 简化子系统接口 |
| 子系统 | 知道中介者 | 不知道外观 |

## 六、中介者模式的优缺点

### 优点

1. **减少依赖**：同事对象之间不再直接引用
2. **集中控制**：交互逻辑集中在中介者
3. **松耦合**：同事可以独立变化
4. **简化维护**：修改交互逻辑只改中介者

### 缺点

1. **中介者膨胀**：交互复杂时中介者变得臃肿
2. **单点问题**：中介者成为系统的瓶颈
3. **调试困难**：交互逻辑集中，调试时需要跟踪中介者

### 适用场景

- 对象间存在复杂的网状引用关系
- 多个对象按某种方式交互，但交互逻辑复杂
- 想要定制分布在多个类中的行为

## 七、实战：空中交通管制

用中介者模式模拟空中交通管制系统：

```java
// ========== 抽象中介者 ==========
public interface AirTrafficControl {
    void requestLanding(Airplane airplane);
    void requestTakeoff(Airplane airplane);
    void notifyPosition(Airplane airplane);
    void register(Airplane airplane);
}

// ========== 同事：飞机 ==========
public class Airplane {
    private final String flightId;
    private final AirTrafficControl atc;
    private int altitude;
    private String status = "巡航";
    
    public Airplane(String flightId, AirTrafficControl atc) {
        this.flightId = flightId;
        this.atc = atc;
        atc.register(this);
    }
    
    public void requestLanding() {
        System.out.println("✈️ " + flightId + " 请求降落");
        atc.requestLanding(this);
    }
    
    public void requestTakeoff() {
        System.out.println("✈️ " + flightId + " 请求起飞");
        atc.requestTakeoff(this);
    }
    
    public void reportPosition() {
        atc.notifyPosition(this);
    }
    
    public void setAltitude(int altitude) {
        this.altitude = altitude;
        System.out.println("  ✈️ " + flightId + " 高度调整为 " + altitude + "ft");
    }
    
    public void setStatus(String status) { this.status = status; }
    public String getFlightId() { return flightId; }
    public int getAltitude() { return altitude; }
    public String getStatus() { return status; }
}

// ========== 具体中介者：塔台 ==========
public class ControlTower implements AirTrafficControl {
    private final List<Airplane> airplanes = new ArrayList<>();
    private final Queue<Airplane> landingQueue = new LinkedList<>();
    private final Queue<Airplane> takeoffQueue = new LinkedList<>();
    private boolean runwayBusy = false;
    
    @Override
    public void register(Airplane airplane) {
        airplanes.add(airplane);
    }
    
    @Override
    public void requestLanding(Airplane airplane) {
        if (runwayBusy) {
            System.out.println("  🏗️ 塔台: 跑道繁忙，" + airplane.getFlightId() + " 进入等待");
            landingQueue.add(airplane);
            airplane.setAltitude(airplane.getAltitude());  // 保持高度
        } else {
            grantLanding(airplane);
        }
    }
    
    @Override
    public void requestTakeoff(Airplane airplane) {
        if (runwayBusy) {
            System.out.println("  🏗️ 塔台: 跑道繁忙，" + airplane.getFlightId() + " 等待起飞");
            takeoffQueue.add(airplane);
        } else {
            grantTakeoff(airplane);
        }
    }
    
    @Override
    public void notifyPosition(Airplane airplane) {
        System.out.println("  🏗️ 塔台: " + airplane.getFlightId() + 
            " 位置报告 - 高度: " + airplane.getAltitude() + "ft 状态: " + airplane.getStatus());
    }
    
    private void grantLanding(Airplane airplane) {
        runwayBusy = true;
        airplane.setStatus("降落中");
        airplane.setAltitude(0);
        System.out.println("  🏗️ 塔台: " + airplane.getFlightId() + " 允许降落 ✅");
        runwayBusy = false;
        processNext();
    }
    
    private void grantTakeoff(Airplane airplane) {
        runwayBusy = true;
        airplane.setStatus("起飞中");
        airplane.setAltitude(10000);
        System.out.println("  🏗️ 塔台: " + airplane.getFlightId() + " 允许起飞 ✅");
        runwayBusy = false;
        processNext();
    }
    
    private void processNext() {
        if (!landingQueue.isEmpty()) {
            grantLanding(landingQueue.poll());
        } else if (!takeoffQueue.isEmpty()) {
            grantTakeoff(takeoffQueue.poll());
        }
    }
}

// ========== 客户端 ==========
public class AirportDemo {
    public static void main(String[] args) {
        AirTrafficControl tower = new ControlTower();
        
        Airplane flight1 = new Airplane("CA1234", tower);
        Airplane flight2 = new Airplane("MU5678", tower);
        Airplane flight3 = new Airplane("CZ9012", tower);
        
        flight1.setAltitude(30000);
        flight2.setAltitude(25000);
        flight3.setAltitude(0);
        
        flight1.requestLanding();
        flight2.requestLanding();
        flight3.requestTakeoff();
    }
}
```

## 八、面试常见问题

### Q1: 中介者模式的核心思想是什么？

中介者模式用一个中介对象来封装一组对象的交互，使对象之间不需要显式相互引用。将多对多的网状交互转化为一对多的星状交互，降低对象间的耦合度。

### Q2: 中介者模式和外观模式有什么区别？

外观模式是单向的——客户端通过外观调用子系统，子系统不知道外观存在。中介者模式是双向的——同事对象知道中介者并主动与中介者交互。外观简化接口，中介者解耦同事间交互。

### Q3: 中介者模式的缺点是什么？

最大的缺点是中介者可能变得非常复杂，集中了所有交互逻辑，成为一个"上帝对象"。当系统交互非常复杂时，需要考虑将中介者拆分，或结合其他模式使用。

### Q4: 什么场景下应该使用中介者模式？

- 对象间存在复杂的网状依赖关系
- 一个对象引用很多其他对象，导致难以复用
- 想要定制分布在多个类中的行为，又不想生成太多子类
- UI 组件间的交互协调

### Q5: 中介者模式和观察者模式有什么关系？

观察者模式是中介者模式的基础——中介者通常使用观察者模式与同事通信。中介者强调"协调多个对象间的交互"，观察者强调"一对多的依赖通知"。两者经常配合使用。

## 九、总结

中介者模式通过引入中介对象，将网状的对象交互转化为星状结构，有效降低了对象间的耦合。

**核心要点**：

1. **星状替代网状**：所有交互通过中介者协调
2. **同事不知同事**：同事对象只与中介者交互
3. **集中控制**：交互逻辑集中在中介者
4. **双向通信**：同事↔中介者双向交互
5. **注意膨胀**：中介者可能变得过于复杂

中介者模式的精髓在于"让对象不再互相直接对话，而是通过一个中间人来协调"。

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
- [Java设计模式（十八）：桥接模式深度实践](/posts/java设计模式十八-桥接模式深度实践/)
