---
title: "Java设计模式（二十一）：状态模式深度实践"
date: 2026-04-22T11:10:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "状态模式", "state", "状态机", "有限状态机"]
---

## 前言

状态模式（State Pattern）是一种行为型设计模式，它的核心思想是：**允许对象在其内部状态改变时改变它的行为，对象看起来似乎修改了它的类**。

**核心思想**：用类表示状态，将状态转换逻辑封装在状态类中。

<!--more-->

## 一、为什么需要状态模式

### 1.1 大量 if-else 的状态判断

假设我们开发一个自动售货机，有投币、选择商品、出货等操作：

```java
// 不用状态模式：大量条件判断
public class VendingMachine {
    private static final int READY = 0;
    private static final int HAS_COIN = 1;
    private static final int SOLD = 2;
    private static final int SOLD_OUT = 3;
    
    private int state = READY;
    
    public void insertCoin() {
        if (state == READY) {
            System.out.println("投币成功");
            state = HAS_COIN;
        } else if (state == HAS_COIN) {
            System.out.println("已有硬币，不能再投");
        } else if (state == SOLD) {
            System.out.println("正在出货，请稍等");
        } else if (state == SOLD_OUT) {
            System.out.println("已售罄");
        }
    }
    
    public void ejectCoin() {
        if (state == READY) {
            System.out.println("没有硬币可退");
        } else if (state == HAS_COIN) {
            System.out.println("退币成功");
            state = READY;
        } else if (state == SOLD) {
            System.out.println("已出货，无法退币");
        } else if (state == SOLD_OUT) {
            System.out.println("没有硬币可退");
        }
    }
    // 更多方法...每个方法都有大量 if-else
}
```

每新增一个状态或操作，所有方法都要修改，违反开闭原则。状态模式将每种状态封装为独立的类来解决这个问题。

## 二、状态模式的结构

### 2.1 类图

```
┌──────────────────────┐      ┌──────────────────────┐
│     Context          │      │     State (抽象)      │
│──────────────────────│      │──────────────────────│
│ - state: State       │─────>│ + handle()           │
│──────────────────────│      │ + insertCoin()       │
│ + setState()         │      │ + ejectCoin()        │
│ + request()          │      │ + dispense()         │
└──────────────────────┘      └──────────┬───────────┘
                                         │
                    ┌──────────┬─────────┼─────────┬──────────┐
                    │          │         │         │          │
              ┌─────┴────┐ ┌───┴───┐ ┌───┴───┐ ┌───┴────┐ ┌──┴─────┐
              │ReadyState│ │HasCoin│ │Sold   │ │SoldOut │ │ ...    │
              └──────────┘ └───────┘ └───────┘ └────────┘ └────────┘
```

### 2.2 完整实现：自动售货机

```java
// ========== 1. 抽象状态 ==========
public interface VendingState {
    void insertCoin(VendingMachine machine);
    void ejectCoin(VendingMachine machine);
    void selectProduct(VendingMachine machine);
    void dispense(VendingMachine machine);
}

// ========== 2. 具体状态：就绪 ==========
public class ReadyState implements VendingState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("💰 投币成功");
        machine.setState(new HasCoinState());
    }
    
    @Override
    public void ejectCoin(VendingMachine machine) {
        System.out.println("❌ 还没投币，无法退币");
    }
    
    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("❌ 请先投币");
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("❌ 请先投币再选择商品");
    }
}

// ========== 3. 具体状态：已投币 ==========
public class HasCoinState implements VendingState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("⚠️ 已有硬币，不能重复投币");
    }
    
    @Override
    public void ejectCoin(VendingMachine machine) {
        System.out.println("🔙 退币成功");
        machine.setState(new ReadyState());
    }
    
    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("🛒 正在出货...");
        machine.setState(new SoldState());
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("❌ 请先选择商品");
    }
}

// ========== 4. 具体状态：出货中 ==========
public class SoldState implements VendingState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("⚠️ 正在出货，请稍等");
    }
    
    @Override
    public void ejectCoin(VendingMachine machine) {
        System.out.println("❌ 已选择商品，无法退币");
    }
    
    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("⚠️ 正在出货，请稍等");
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        machine.releaseProduct();
        if (machine.getCount() > 0) {
            machine.setState(new ReadyState());
        } else {
            System.out.println("📢 商品已售罄");
            machine.setState(new SoldOutState());
        }
    }
}

// ========== 5. 具体状态：售罄 ==========
public class SoldOutState implements VendingState {
    @Override
    public void insertCoin(VendingMachine machine) {
        System.out.println("❌ 商品已售罄");
    }
    
    @Override
    public void ejectCoin(VendingMachine machine) {
        System.out.println("❌ 没有硬币可退");
    }
    
    @Override
    public void selectProduct(VendingMachine machine) {
        System.out.println("❌ 商品已售罄");
    }
    
    @Override
    public void dispense(VendingMachine machine) {
        System.out.println("❌ 商品已售罄");
    }
}

// ========== 6. 上下文：售货机 ==========
public class VendingMachine {
    private VendingState state;
    private int count;
    
    public VendingMachine(int count) {
        this.count = count;
        this.state = count > 0 ? new ReadyState() : new SoldOutState();
    }
    
    public void setState(VendingState state) {
        this.state = state;
    }
    
    public void insertCoin() { state.insertCoin(this); }
    public void ejectCoin() { state.ejectCoin(this); }
    public void selectProduct() { state.selectProduct(this); }
    public void dispense() { state.dispense(this); }
    
    public void releaseProduct() {
        System.out.println("🎁 商品已出货！");
        count--;
    }
    
    public int getCount() { return count; }
    
    public void printState() {
        System.out.println("📊 当前库存: " + count + ", 状态: " + 
            state.getClass().getSimpleName());
    }
}

// ========== 7. 客户端 ==========
public class VendingDemo {
    public static void main(String[] args) {
        VendingMachine machine = new VendingMachine(3);
        
        machine.insertCoin();
        machine.selectProduct();
        machine.dispense();
        machine.printState();
        
        System.out.println();
        machine.insertCoin();
        machine.ejectCoin();  // 退币
        
        System.out.println();
        machine.insertCoin();
        machine.selectProduct();
        machine.dispense();
        machine.printState();
    }
}
```

## 三、状态模式的高级用法

### 3.1 状态模式实现订单状态机

```java
// ========== 状态接口 ==========
public interface OrderState {
    void confirm(OrderContext order);
    void pay(OrderContext order);
    void ship(OrderContext order);
    void deliver(OrderContext order);
    void cancel(OrderContext order);
    String getName();
}

// ========== 具体状态 ==========
public class CreatedState implements OrderState {
    @Override public void confirm(OrderContext order) {
        System.out.println("✅ 订单已确认");
        order.setState(new ConfirmedState());
    }
    @Override public void pay(OrderContext order) { System.out.println("❌ 请先确认订单"); }
    @Override public void ship(OrderContext order) { System.out.println("❌ 订单未支付"); }
    @Override public void deliver(OrderContext order) { System.out.println("❌ 订单未支付"); }
    @Override public void cancel(OrderContext order) {
        System.out.println("✅ 订单已取消");
        order.setState(new CancelledState());
    }
    @Override public String getName() { return "已创建"; }
}

public class ConfirmedState implements OrderState {
    @Override public void confirm(OrderContext order) { System.out.println("⚠️ 订单已确认"); }
    @Override public void pay(OrderContext order) {
        System.out.println("💰 支付成功");
        order.setState(new PaidState());
    }
    @Override public void ship(OrderContext order) { System.out.println("❌ 请先支付"); }
    @Override public void deliver(OrderContext order) { System.out.println("❌ 请先支付"); }
    @Override public void cancel(OrderContext order) {
        System.out.println("✅ 订单已取消");
        order.setState(new CancelledState());
    }
    @Override public String getName() { return "已确认"; }
}

public class PaidState implements OrderState {
    @Override public void confirm(OrderContext order) { System.out.println("⚠️ 已确认"); }
    @Override public void pay(OrderContext order) { System.out.println("⚠️ 已支付"); }
    @Override public void ship(OrderContext order) {
        System.out.println("📦 已发货");
        order.setState(new ShippedState());
    }
    @Override public void deliver(OrderContext order) { System.out.println("❌ 未发货"); }
    @Override public void cancel(OrderContext order) {
        System.out.println("💰 退款中...");
        order.setState(new CancelledState());
    }
    @Override public String getName() { return "已支付"; }
}

public class ShippedState implements OrderState {
    @Override public void confirm(OrderContext order) { System.out.println("⚠️ 已确认"); }
    @Override public void pay(OrderContext order) { System.out.println("⚠️ 已支付"); }
    @Override public void ship(OrderContext order) { System.out.println("⚠️ 已发货"); }
    @Override public void deliver(OrderContext order) {
        System.out.println("📬 已签收");
        order.setState(new DeliveredState());
    }
    @Override public void cancel(OrderContext order) { System.out.println("❌ 已发货无法取消"); }
    @Override public String getName() { return "已发货"; }
}

public class DeliveredState implements OrderState {
    @Override public void confirm(OrderContext order) { System.out.println("⚠️ 订单已完成"); }
    @Override public void pay(OrderContext order) { System.out.println("⚠️ 已支付"); }
    @Override public void ship(OrderContext order) { System.out.println("⚠️ 已签收"); }
    @Override public void deliver(OrderContext order) { System.out.println("⚠️ 已签收"); }
    @Override public void cancel(OrderContext order) { System.out.println("❌ 已签收无法取消"); }
    @Override public String getName() { return "已签收"; }
}

public class CancelledState implements OrderState {
    @Override public void confirm(OrderContext order) { System.out.println("❌ 订单已取消"); }
    @Override public void pay(OrderContext order) { System.out.println("❌ 订单已取消"); }
    @Override public void ship(OrderContext order) { System.out.println("❌ 订单已取消"); }
    @Override public void deliver(OrderContext order) { System.out.println("❌ 订单已取消"); }
    @Override public void cancel(OrderContext order) { System.out.println("⚠️ 已取消"); }
    @Override public String getName() { return "已取消"; }
}

// ========== 上下文 ==========
public class OrderContext {
    private OrderState state;
    private final String orderId;
    
    public OrderContext(String orderId) {
        this.orderId = orderId;
        this.state = new CreatedState();
    }
    
    public void setState(OrderState state) { this.state = state; }
    public void confirm() { state.confirm(this); }
    public void pay() { state.pay(this); }
    public void ship() { state.ship(this); }
    public void deliver() { state.deliver(this); }
    public void cancel() { state.cancel(this); }
    
    public void printStatus() {
        System.out.println("📋 订单 " + orderId + " 状态: " + state.getName());
    }
}

// 客户端
OrderContext order = new OrderContext("ORD-001");
order.printStatus();
order.confirm();
order.pay();
order.ship();
order.deliver();
order.printStatus();
```

### 3.2 使用枚举简化状态

```java
public enum LightState {
    RED {
        @Override public LightState next() { return GREEN; }
        @Override public String action() { return "🔴 停止"; }
    },
    GREEN {
        @Override public LightState next() { return YELLOW; }
        @Override public String action() { return "🟢 通行"; }
    },
    YELLOW {
        @Override public LightState next() { return RED; }
        @Override public String action() { return "🟡 注意"; }
    };
    
    public abstract LightState next();
    public abstract String action();
}
```

## 四、状态模式在 JDK 中的应用

### 4.1 Thread 状态

Java Thread 的状态转换是状态模式的体现：

```java
// Thread.State 枚举
public enum State {
    NEW,           // 新建
    RUNNABLE,      // 可运行
    BLOCKED,       // 阻塞
    WAITING,       // 等待
    TIMED_WAITING, // 超时等待
    TERMINATED     // 终止
}
```

## 五、状态模式 vs 其他模式

### 5.1 对比策略模式

| 维度 | 状态模式 | 策略模式 |
|------|---------|---------|
| 状态切换 | 状态对象自己触发 | 客户端选择 |
| 行为 | 同一操作在不同状态下行为不同 | 不同策略执行不同算法 |
| 客户端 | 不知道当前状态 | 知道选择了哪个策略 |
| 关系 | 状态之间有转换关系 | 策略之间相互独立 |

### 5.2 对比命令模式

状态模式关注"不同状态下行为不同"，命令模式关注"请求的封装和排队"。

## 六、状态模式的优缺点

### 优点

1. **消除条件判断**：用类代替 if-else/switch
2. **开闭原则**：新增状态无需修改已有状态类
3. **集中状态逻辑**：每个状态的行为封装在对应类中
4. **状态转换明确**：状态转换逻辑可见

### 缺点

1. **类数量增多**：每个状态一个类
2. **状态耦合**：状态类之间可能相互引用
3. **过度设计**：简单状态机不值得用状态模式

### 适用场景

- 对象行为取决于其状态
- 大量条件判断与状态相关
- 状态转换逻辑复杂
- 需要状态机（订单、工作流、游戏）

## 七、面试常见问题

### Q1: 状态模式的核心思想是什么？

状态模式将对象的不同状态封装为独立的类，当对象状态改变时，行为也随之改变。通过将状态相关的行为分散到各个状态类中，消除大量条件判断。

### Q2: 状态模式和策略模式有什么区别？

最大的区别在于：状态模式中状态对象自己决定何时切换到下一个状态，状态之间有转换关系；策略模式中由客户端选择策略，策略之间相互独立。状态模式是"状态的自动切换"，策略模式是"算法的手动选择"。

### Q3: 什么时候应该用状态模式？

当对象有多个状态，且不同状态下对同一消息的行为不同时，应该使用状态模式。典型信号：代码中有大量基于状态的 if-else 或 switch 语句。

### Q4: 如何避免状态类之间的循环依赖？

可以将状态转换逻辑放在上下文中，状态类只返回目标状态（而不是直接设置），由上下文统一管理状态转换。

## 八、总结

状态模式将"状态+行为"封装为独立类，消除了大量条件判断，让状态转换清晰可控。

**核心要点**：

1. **消除 if-else**：用类代替条件判断
2. **状态即类**：每种状态封装为独立类
3. **自动切换**：状态对象决定何时转换
4. **适用场景**：状态机、订单流程、工作流
5. **注意粒度**：简单状态机不需要状态模式

状态模式告诉我们：当行为随状态变化时，不要用条件判断来区分，而是让状态自己决定行为。

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
- [Java设计模式（十九）：中介者模式深度实践](/posts/java设计模式十九-中介者模式深度实践/)
- [Java设计模式（二十）：备忘录模式深度实践](/posts/java设计模式二十-备忘录模式深度实践/)
