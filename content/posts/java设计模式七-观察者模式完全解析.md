---
title: "Java设计模式（七）：观察者模式完全解析"
date: 2026-04-17T18:00:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "观察者模式", "observer"]
---

## 前言

前六篇我们介绍了单例、工厂、建造者、原型、适配器和装饰器模式，今天继续 Java 设计模式系列。**观察者模式（Observer Pattern）** 是行为型模式中最常用的一种，用于建立对象之间的依赖关系——当一个对象状态改变时，所有依赖它的对象都会收到通知并自动更新。

**核心思想**：定义对象间一对多的依赖关系，当一个对象状态改变时，所有依赖于它的对象都会被通知并自动更新。

<!--more-->

## 一、为什么需要观察者模式

### 1.1 场景引入

```java
// ❌ 硬编码方式：订单系统在创建订单后需要通知多个模块
public class OrderService {
    
    public void createOrder(Order order) {
        // 1. 保存订单
        orderDao.save(order);
        
        // 2. 通知库存
        inventoryService.deduct(order);
        
        // 3. 发送短信
        smsService.send(order.getUser(), "订单已创建");
        
        // 4. 发送邮件
        emailService.send(order.getUser(), "订单详情");
        
        // 5. 记录日志
        logService.record(order);
        
        // 6. 积分
        pointService.add(order.getUser(), order.getAmount());
        
        // 每新增一个通知需求就要修改这里...
    }
}
```

**问题**：
- 高耦合：OrderService 必须知道所有依赖模块
- 难扩展：新增通知目标需要修改核心逻辑
- 违反开闭原则

### 1.2 观察者模式的优势

```java
// ✅ 使用观察者模式：解耦通知关系
public class OrderService {
    
    private List<OrderObserver> observers = new ArrayList<>();
    
    public void addObserver(OrderObserver observer) {
        observers.add(observer);
    }
    
    public void createOrder(Order order) {
        orderDao.save(order);
        notifyObservers(order);  // 统一通知，无需关心具体实现
    }
    
    private void notifyObservers(Order order) {
        for (OrderObserver observer : observers) {
            observer.onOrderCreated(order);
        }
    }
}
```

**优点**：
- 松耦合：主题不知道观察者的具体实现
- 动态添加：运行时可以增删观察者
- 符合开闭原则：新增观察者无需修改主题

## 二、观察者模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                   Subject (主题/被观察者)                     │
├─────────────────────────────────────────────────────────────┤
│ - observers: List<Observer>                                │
│ + attach(Observer)                                         │
│ + detach(Observer)                                         │
│ + notifyObservers()                                        │
└─────────────────────────────────────────────────────────────┘
              │ 1..*
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌──────────┐      ┌──────────┐
│Observer A│      │Observer B│
│(观察者)  │      │(观察者)  │
├──────────┤      ├──────────┤
│+update() │      │+update() │
└──────────┘      └──────────┘
```

### 2.2 完整代码实现

```java
// 抽象观察者
public interface Observer {
    void update(String message);
}

// 具体观察者A
public class ConcreteObserverA implements Observer {
    
    private String name;
    
    public ConcreteObserverA(String name) {
        this.name = name;
    }
    
    @Override
    public void update(String message) {
        System.out.println(name + " 收到通知: " + message);
    }
}

// 具体观察者B
public class ConcreteObserverB implements Observer {
    
    private String name;
    
    public ConcreteObserverB(String name) {
        this.name = name;
    }
    
    @Override
    public void update(String message) {
        System.out.println(name + " 收到通知: " + message);
    }
}

// 抽象主题
public abstract class Subject {
    
    protected List<Observer> observers = new ArrayList<>();
    
    public void attach(Observer observer) {
        observers.add(observer);
    }
    
    public void detach(Observer observer) {
        observers.remove(observer);
    }
    
    public void notifyObservers(String message) {
        for (Observer observer : observers) {
            observer.update(message);
        }
    }
}

// 具体主题
public class ConcreteSubject extends Subject {
    
    private String state;
    
    public void changeState(String newState) {
        this.state = newState;
        System.out.println("主题状态变更为: " + newState);
        notifyObservers("状态已变更 → " + newState);
    }
}

// 客户端
public class ObserverTest {
    public static void main(String[] args) {
        // 创建主题
        ConcreteSubject subject = new ConcreteSubject();
        
        // 创建观察者
        Observer observer1 = new ConcreteObserverA("观察者A");
        Observer observer2 = new ConcreteObserverB("观察者B");
        Observer observer3 = new ConcreteObserverA("观察者C");
        
        // 注册观察者
        subject.attach(observer1);
        subject.attach(observer2);
        subject.attach(observer3);
        
        // 主题状态变更 → 通知所有观察者
        subject.changeState("ONLINE");
        // 主题状态变更为: ONLINE
        // 观察者A 收到通知: 状态已变更 → ONLINE
        // 观察者B 收到通知: 状态已变更 → ONLINE
        // 观察者C 收到通知: 状态已变更 → ONLINE
        
        // 移除一个观察者
        subject.detach(observer2);
        
        // 再次变更
        subject.changeState("OFFLINE");
        // 主题状态变更为: OFFLINE
        // 观察者A 收到通知: 状态已变更 → OFFLINE
        // 观察者C 收到通知: 状态已变更 → OFFLINE
    }
}
```

## 三、推模式 vs 拉模式

### 3.1 推模式（Push）

```java
// 主题主动推送数据给观察者
public interface PushObserver {
    void update(String data1, int data2, boolean flag);
}

public class PushSubject {
    private List<PushObserver> observers = new ArrayList<>();
    
    public void notifyObservers() {
        for (PushObserver observer : observers) {
            // 主动推送具体数据
            observer.update("hello", 42, true);
        }
    }
}
```

**优点**：观察者无需主动查询
**缺点**：不管观察者需不需要，都推送所有数据

### 3.2 拉模式（Pull）

```java
// 观察者主动从主题拉取数据
public interface PullObserver {
    void update(Subject subject);
}

public class PullSubject {
    private String name;
    private int status;
    
    public String getName() { return name; }
    public int getStatus() { return status; }
    
    public void notifyObservers() {
        for (PullObserver observer : observers) {
            // 只传递主题引用，观察者自己决定拉什么
            observer.update(this);
        }
    }
}

public class ConcretePullObserver implements PullObserver {
    
    @Override
    public void update(Subject subject) {
        // 观察者按需拉取
        PullSubject ps = (PullSubject) subject;
        String name = ps.getName();
        // 只取需要的数据
    }
}
```

**优点**：观察者按需获取，灵活性高
**缺点**：观察者必须依赖主题类

### 3.3 对比

| 维度 | 推模式 | 拉模式 |
|------|--------|--------|
| 数据传递 | 主题主动推 | 观察者主动拉 |
| 耦合度 | 观察者不依赖主题 | 观察者依赖主题 |
| 灵活性 | 低（固定数据） | 高（按需获取） |
| 性能 | 可能推送无用数据 | 需要额外查询 |
| 适用场景 | 数据量小、变化少 | 数据量大、按需获取 |

## 四、实战案例

### 4.1 天气监测系统

```java
// 观察者接口
public interface WeatherDisplay {
    void update(float temperature, float humidity, float pressure);
}

// 天气数据（主题）
public class WeatherData {
    private List<WeatherDisplay> displays = new ArrayList<>();
    
    private float temperature;
    private float humidity;
    private float pressure;
    
    public void registerDisplay(WeatherDisplay display) {
        displays.add(display);
    }
    
    public void removeDisplay(WeatherDisplay display) {
        displays.remove(display);
    }
    
    // 数据变化时通知所有显示
    public void measurementsChanged() {
        for (WeatherDisplay display : displays) {
            display.update(temperature, humidity, pressure);
        }
    }
    
    // 模拟气象站更新数据
    public void setMeasurements(float temperature, float humidity, float pressure) {
        this.temperature = temperature;
        this.humidity = humidity;
        this.pressure = pressure;
        measurementsChanged();
    }
}

// 当前状况显示
public class CurrentConditionDisplay implements WeatherDisplay {
    
    @Override
    public void update(float temperature, float humidity, float pressure) {
        System.out.printf("当前状况：温度 %.1f°C，湿度 %.1f%%，气压 %.1f hPa%n",
            temperature, humidity, pressure);
    }
}

// 统计显示
public class StatisticsDisplay implements WeatherDisplay {
    
    private List<Float> temperatures = new ArrayList<>();
    
    @Override
    public void update(float temperature, float humidity, float pressure) {
        temperatures.add(temperature);
        
        float avg = temperatures.stream()
            .reduce(0f, Float::sum) / temperatures.size();
        float max = temperatures.stream()
            .max(Float::compare).orElse(0f);
        float min = temperatures.stream()
            .min(Float::compare).orElse(0f);
        
        System.out.printf("温度统计：最高 %.1f°C，最低 %.1f°C，平均 %.1f°C%n",
            max, min, avg);
    }
}

// 预报显示
public class ForecastDisplay implements WeatherDisplay {
    
    private float lastPressure;
    private static final float THRESHOLD = 0.5f;
    
    @Override
    public void update(float temperature, float humidity, float pressure) {
        String trend;
        if (lastPressure == 0) {
            trend = "尚无历史数据";
        } else if (pressure > lastPressure + THRESHOLD) {
            trend = "天气转好，气温上升 ↑";
        } else if (pressure < lastPressure - THRESHOLD) {
            trend = "天气转阴，可能下雨 ↓";
        } else {
            trend = "天气平稳 →";
        }
        lastPressure = pressure;
        System.out.println("天气预报：" + trend);
    }
}

// 使用
public class WeatherStation {
    public static void main(String[] args) {
        WeatherData weatherData = new WeatherData();
        
        // 注册显示面板
        weatherData.registerDisplay(new CurrentConditionDisplay());
        weatherData.registerDisplay(new StatisticsDisplay());
        weatherData.registerDisplay(new ForecastDisplay());
        
        // 气象站数据更新
        System.out.println("=== 第1次测量 ===");
        weatherData.setMeasurements(26.5f, 65.0f, 1013.2f);
        
        System.out.println("\n=== 第2次测量 ===");
        weatherData.setMeasurements(27.1f, 63.0f, 1014.5f);
        
        System.out.println("\n=== 第3次测量 ===");
        weatherData.setMeasurements(24.8f, 78.0f, 1010.8f);
    }
}
```

**输出**：
```
=== 第1次测量 ===
当前状况：温度 26.5°C，湿度 65.0%，气压 1013.2 hPa
温度统计：最高 26.5°C，最低 26.5°C，平均 26.5°C
天气预报：尚无历史数据

=== 第2次测量 ===
当前状况：温度 27.1°C，湿度 63.0%，气压 1014.5 hPa
温度统计：最高 27.1°C，最低 26.5°C，平均 26.8°C
天气预报：天气转好，气温上升 ↑

=== 第3次测量 ===
当前状况：温度 24.8°C，湿度 78.0%，气压 1010.8 hPa
温度统计：最高 27.1°C，最低 24.8°C，平均 26.1°C
天气预报：天气转阴，可能下雨 ↓
```

### 4.2 事件总线实现

```java
// 事件接口
public interface Event {
    String getType();
}

// 事件处理器
@FunctionalInterface
public interface EventHandler<T extends Event> {
    void handle(T event);
}

// 类型安全的事件总线
public class EventBus {
    
    // 事件类型 → 处理器列表
    private Map<String, List<EventHandler<?>>> handlers = new ConcurrentHashMap<>();
    
    // 注册事件处理器
    public <T extends Event> void subscribe(String eventType, EventHandler<T> handler) {
        handlers.computeIfAbsent(eventType, k -> new CopyOnWriteArrayList<>())
                .add(handler);
    }
    
    // 取消注册
    public <T extends Event> void unsubscribe(String eventType, EventHandler<T> handler) {
        List<EventHandler<?>> list = handlers.get(eventType);
        if (list != null) {
            list.remove(handler);
        }
    }
    
    // 发布事件
    @SuppressWarnings("unchecked")
    public <T extends Event> void publish(T event) {
        List<EventHandler<?>> list = handlers.get(event.getType());
        if (list != null) {
            for (EventHandler<?> handler : list) {
                try {
                    ((EventHandler<T>) handler).handle(event);
                } catch (Exception e) {
                    System.err.println("事件处理异常: " + e.getMessage());
                }
            }
        }
    }
}

// 具体事件
public class OrderCreatedEvent implements Event {
    
    private String orderId;
    private String userId;
    private double amount;
    
    public OrderCreatedEvent(String orderId, String userId, double amount) {
        this.orderId = orderId;
        this.userId = userId;
        this.amount = amount;
    }
    
    @Override
    public String getType() { return "ORDER_CREATED"; }
    
    // getters...
    public String getOrderId() { return orderId; }
    public String getUserId() { return userId; }
    public double getAmount() { return amount; }
}

public class UserRegisteredEvent implements Event {
    
    private String userId;
    private String username;
    
    public UserRegisteredEvent(String userId, String username) {
        this.userId = userId;
        this.username = username;
    }
    
    @Override
    public String getType() { return "USER_REGISTERED"; }
    
    public String getUserId() { return userId; }
    public String getUsername() { return username; }
}

// 使用
public class EventBusDemo {
    public static void main(String[] args) {
        EventBus eventBus = new EventBus();
        
        // 注册订单事件处理器
        eventBus.subscribe("ORDER_CREATED", (OrderCreatedEvent e) -> {
            System.out.println("[库存] 扣减库存，订单: " + e.getOrderId());
        });
        
        eventBus.subscribe("ORDER_CREATED", (OrderCreatedEvent e) -> {
            System.out.println("[短信] 发送短信给用户: " + e.getUserId());
        });
        
        eventBus.subscribe("ORDER_CREATED", (OrderCreatedEvent e) -> {
            System.out.printf("[积分] 用户 %s 增加 %.0f 积分%n", 
                e.getUserId(), e.getAmount());
        });
        
        // 注册用户事件处理器
        eventBus.subscribe("USER_REGISTERED", (UserRegisteredEvent e) -> {
            System.out.println("[欢迎] 发送欢迎邮件给: " + e.getUsername());
        });
        
        // 发布事件
        System.out.println("=== 创建订单 ===");
        eventBus.publish(new OrderCreatedEvent("ORD001", "user123", 100.0));
        
        System.out.println("\n=== 用户注册 ===");
        eventBus.publish(new UserRegisteredEvent("user456", "张三"));
    }
}
```

### 4.3 JDK Observable（已废弃）

> JDK 自带的 `java.util.Observable` 和 `java.util.Observer` 在 Java 9 中被标记为废弃（@Deprecated），推荐使用 `java.beans.PropertyChangeListener` 或自定义实现。

```java
// JDK 旧式写法（不推荐）
public class MyObservable extends Observable {
    
    private int value;
    
    public void setValue(int newValue) {
        this.value = newValue;
        setChanged();        // 必须调用，标记状态已变化
        notifyObservers();   // 通知所有观察者
    }
    
    public int getValue() { return value; }
}

public class MyObserver implements Observer {
    
    @Override
    public void update(Observable o, Object arg) {
        MyObservable mo = (MyObservable) o;
        System.out.println("值变化为: " + mo.getValue());
    }
}
```

## 五、JDK/框架中的应用

### 5.1 Spring 事件机制

```java
// 定义事件（继承 ApplicationEvent）
public class OrderCreatedEvent extends ApplicationEvent {
    
    private String orderId;
    
    public OrderCreatedEvent(Object source, String orderId) {
        super(source);
        this.orderId = orderId;
    }
    
    public String getOrderId() { return orderId; }
}

// 事件发布者
@Service
public class OrderService {
    
    @Autowired
    private ApplicationEventPublisher eventPublisher;
    
    public void createOrder(String orderId) {
        // 业务逻辑...
        
        // 发布事件
        eventPublisher.publishEvent(new OrderCreatedEvent(this, orderId));
    }
}

// 事件监听者（注解方式）
@Component
public class OrderEventListener {
    
    @EventListener
    public void handleOrderCreated(OrderCreatedEvent event) {
        System.out.println("订单已创建: " + event.getOrderId());
    }
    
    @Async
    @EventListener
    public void sendNotification(OrderCreatedEvent event) {
        // 异步处理，不阻塞主流程
    }
    
    // 条件监听
    @EventListener(condition = "#event.orderId.startsWith('VIP')")
    public void handleVipOrder(OrderCreatedEvent event) {
        System.out.println("VIP订单特殊处理: " + event.getOrderId());
    }
}

// 事务绑定事件
@TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
public void handleAfterCommit(OrderCreatedEvent event) {
    // 事务提交后执行
}
```

### 5.2 Spring 事件处理流程

```
┌─────────────────────────────────────────────────────────────┐
│                  Spring 事件机制架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ApplicationEventPublisher                                  │
│         │                                                   │
│         ▼                                                   │
│  AbstractApplicationContext                                │
│         │                                                   │
│         ├─── publishEvent()                                 │
│         │                                                   │
│         ▼                                                   │
│  SimpleApplicationEventMulticaster                         │
│         │                                                   │
│         ├─── invokeListener()                               │
│         │       │                                           │
│         │       ├── @EventListener 同步执行                  │
│         │       ├── @Async @EventListener 异步执行           │
│         │       └── @TransactionalEventListener 事务绑定     │
│         │                                                   │
│         ▼                                                   │
│  具体的 Listener / @EventListener 方法                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Guava EventBus

```java
// Guava 的事件总线
public class GuavaEventBusDemo {
    
    public static void main(String[] args) {
        EventBus eventBus = new EventBus();
        
        // 注册订阅者
        eventBus.register(new OrderSubscriber());
        eventBus.register(new LogSubscriber());
        
        // 发布事件
        eventBus.post(new OrderEvent("ORD001", 100.0));
    }
}

// 订阅者
public class OrderSubscriber {
    
    @Subscribe
    public void handleOrder(OrderEvent event) {
        System.out.println("处理订单: " + event.getOrderId());
    }
    
    @Subscribe
    @AllowConcurrentEvents  // 允许并发处理
    public void handleAsync(OrderEvent event) {
        // 并发安全的事件处理
    }
}

public class LogSubscriber {
    
    @Subscribe
    public void logOrder(OrderEvent event) {
        System.out.println("记录日志: " + event.getOrderId());
    }
}
```

### 5.4 Vue.js / React 中的观察者

```javascript
// Vue 3 中的响应式（观察者模式）
const state = reactive({ count: 0 });

// 订阅变化（watch）
watch(() => state.count, (newVal, oldVal) => {
    console.log(`count 从 ${oldVal} 变为 ${newVal}`);
});

// 触发变化
state.count = 1;  // 自动通知 watch
```

## 六、观察者模式 vs 发布订阅模式

### 6.1 核心区别

```
观察者模式（Observer）：
┌──────────────────────────────────────┐
│                                      │
│  Subject ────直接通知───→ Observer   │
│  (知道观察者的存在)                   │
│                                      │
└──────────────────────────────────────┘

发布订阅模式（Pub/Sub）：
┌──────────────────────────────────────────────┐
│                                              │
│  Publisher ──→ EventChannel ──→ Subscriber   │
│             (事件总线/消息中间件)              │
│  (发布者不知道订阅者的存在)                     │
│                                              │
└──────────────────────────────────────────────┘
```

### 6.2 详细对比

| 维度 | 观察者模式 | 发布订阅模式 |
|------|-----------|-------------|
| **耦合度** | 较高（Subject 知道 Observer） | 低（通过事件总线解耦） |
| **通信方式** | 直接调用 | 间接（消息中间件） |
| **参与者** | 两个角色 | 三个角色 |
| **异步** | 通常同步 | 天然支持异步 |
| **跨进程** | 不支持 | 支持（MQ） |
| **典型实现** | JDK Observable、Spring Event | Kafka、RabbitMQ、Redis Pub/Sub |

### 6.3 代码对比

```java
// 观察者模式：Subject 直接调用 Observer
public class Subject {
    private List<Observer> observers;
    
    public void notify() {
        for (Observer o : observers) {
            o.update();  // 直接调用
        }
    }
}

// 发布订阅模式：通过消息中间件
public class Publisher {
    private MessageQueue mq;
    
    public void publish(String topic, Object message) {
        mq.publish(topic, message);  // 发布到消息队列
    }
}

public class Subscriber {
    private MessageQueue mq;
    
    public void subscribe(String topic) {
        mq.subscribe(topic, this::handle);  // 订阅消息队列
    }
}
```

## 七、观察者模式的优缺点

### 7.1 优点

1. **解耦**：被观察者和观察者之间松耦合
2. **动态**：运行时可以动态增删观察者
3. **广播**：一对多的通知机制
4. **符合开闭原则**：新增观察者无需修改被观察者

### 7.2 缺点

1. **性能**：大量观察者可能影响性能
2. **顺序**：通知顺序不可控
3. **内存泄漏**：观察者未注销可能导致内存泄漏
4. **循环依赖**：观察者互相引用可能造成循环通知

### 7.3 解决方案

```java
// 1. 异步通知避免阻塞
public void notifyObservers() {
    executorService.submit(() -> {
        for (Observer o : observers) {
            o.update();
        }
    });
}

// 2. 防止内存泄漏（弱引用）
public class WeakSubject {
    // 使用弱引用避免内存泄漏
    private List<WeakReference<Observer>> observers = new ArrayList<>();
    
    public void attach(Observer observer) {
        observers.add(new WeakReference<>(observer));
    }
    
    public void notifyObservers() {
        // 遍历时清理失效的弱引用
        observers.removeIf(ref -> ref.get() == null);
        
        for (WeakReference<Observer> ref : observers) {
            Observer observer = ref.get();
            if (observer != null) {
                observer.update();
            }
        }
    }
}

// 3. 有序通知
public class OrderedSubject {
    private Map<Observer, Integer> priorities = new ConcurrentHashMap<>();
    
    public void attach(Observer observer, int priority) {
        priorities.put(observer, priority);
    }
    
    public void notifyObservers() {
        priorities.entrySet().stream()
            .sorted(Map.Entry.comparingByValue())
            .forEach(entry -> entry.getKey().update());
    }
}
```

## 八、最佳实践

### 8.1 使用注解简化

```java
// 自定义注解
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface Subscribe {
    String topic() default "";
    int priority() default 0;
}

// 事件总线 + 注解驱动
public class AnnotationEventBus {
    
    private Map<String, List<Method>> subscribers = new ConcurrentHashMap<>();
    
    public void register(Object listener) {
        for (Method method : listener.getClass().getDeclaredMethods()) {
            Subscribe annotation = method.getAnnotation(Subscribe.class);
            if (annotation != null) {
                method.setAccessible(true);
                String topic = annotation.topic();
                subscribers.computeIfAbsent(topic, k -> new ArrayList<>())
                          .add(method);
            }
        }
    }
    
    public void publish(String topic, Object event) {
        List<Method> methods = subscribers.getOrDefault(topic, Collections.emptyList());
        for (Method method : methods) {
            try {
                method.invoke(event);
            } catch (Exception e) {
                // 异常处理
            }
        }
    }
}

// 使用
public class OrderListener {
    
    @Subscribe(topic = "order.created")
    public void onOrderCreated(OrderEvent event) {
        System.out.println("订单创建: " + event.getOrderId());
    }
    
    @Subscribe(topic = "order.cancelled")
    public void onOrderCancelled(OrderEvent event) {
        System.out.println("订单取消: " + event.getOrderId());
    }
}
```

### 8.2 线程安全

```java
// 线程安全的主题
public class ThreadSafeSubject {
    
    // CopyOnWriteArrayList 保证遍历安全
    private final List<Observer> observers = new CopyOnWriteArrayList<>();
    
    // ReadWriteLock 读写分离
    private final ReadWriteLock lock = new ReentrantReadWriteLock();
    
    public void attach(Observer observer) {
        lock.writeLock().lock();
        try {
            observers.add(observer);
        } finally {
            lock.writeLock().unlock();
        }
    }
    
    public void notifyObservers() {
        lock.readLock().lock();
        try {
            for (Observer observer : observers) {
                observer.update();
            }
        } finally {
            lock.readLock().unlock();
        }
    }
}
```

## 九、面试常见问题

### Q1：观察者模式和发布订阅模式的区别？

**核心区别**：观察者模式中 Subject 直接持有 Observer 的引用，耦合度较高；发布订阅模式通过事件总线/消息中间件解耦，发布者和订阅者互不知道对方的存在。

### Q2：Spring 中 @EventListener 和 @TransactionalEventListener 的区别？

- `@EventListener`：默认同步执行，在事务内处理
- `@TransactionalEventListener`：绑定事务阶段执行（AFTER_COMMIT、BEFORE_COMMIT、AFTER_ROLLBACK、AFTER_COMPLETION），确保数据一致性

### Q3：观察者模式如何避免内存泄漏？

1. **弱引用**：使用 WeakReference 持有观察者
2. **生命周期管理**：在对象销毁时主动注销
3. **Spring 管理**：让 Spring 容器管理 Bean 生命周期

### Q4：如何保证观察者的执行顺序？

1. **优先级**：为观察者设置 priority，按优先级排序
2. **有序集合**：使用 TreeSet 或 TreeMap 存储
3. **Spring @Order**：使用 @Order 注解控制 Bean 加载顺序

## 十、总结

### 模式对比

| 维度 | 观察者 | 发布订阅 | 策略 | 模板方法 |
|------|--------|---------|------|---------|
| **类型** | 行为型 | 行为型 | 行为型 | 行为型 |
| **目的** | 通知变化 | 解耦通信 | 算法替换 | 流程控制 |
| **变化点** | 依赖数量 | 消息类型 | 算法实现 | 步骤实现 |

### 核心要点

1. **一对多依赖**：一个主题，多个观察者
2. **松耦合**：主题不知道观察者的具体实现
3. **动态组合**：运行时增删观察者
4. **通知机制**：推模式 vs 拉模式

## 结语

观察者模式是处理对象间通信的利器，特别是在事件驱动架构中。Spring 的事件机制、Vue 的响应式、消息队列都是观察者模式的延伸。掌握观察者模式，是构建解耦、可扩展系统的关键。

**下期预告**：策略模式（Strategy Pattern）

> 记住：**观察者是解耦神器，发布订阅是分布式基础**。
