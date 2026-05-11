---
title: "volatile 与 Happens-Before 规则深度解析"
date: 2026-05-09T15:50:00+08:00
draft: false
categories: ["java"]
tags: ["volatile", "happens-before", "并发", "JMM", "CAS"]
---

# volatile 与 Happens-Before 规则深度解析

> 面试高频问题：volatile 如何保证可见性？synchronized 和 volatile 的区别？happens-before 是什么？

## 引言

在 Java 并发编程中，`volatile` 是一个常被提及却又容易被误解的关键字。很多面试者知道它能"保证可见性"，但追问其底层原理时就答不上来了。本文将从 JVM 内存模型出发，深入解析 volatile 的实现机制和 happens-before 规则。

## 一、JMM 内存模型

### 1.1 为什么要引入 JMM？

计算机的存储结构：
```
┌─────────────────────────────────────────────────────┐
│                      CPU                            │
│  ┌─────┐                                           │
│  │寄存器│ ← 速度极快，容量极小                       │
│  └─────┘                                           │
│      ↑                                              │
│  L1 Cache                                          │
│      ↑                                              │
│  L2 Cache                                          │
│      ↑                                              │
│  L3 Cache (多核共享)                                │
│      ↑                                              │
│  主内存 (RAM) ← 速度慢，容量大                       │
└─────────────────────────────────────────────────────┘
```

**问题**：CPU 缓存导致可见性问题。一个线程修改了变量，其他线程可能看不到。

```java
// 可见性问题示例
boolean flag = false;

Thread A:
    flag = true;  // 修改了主内存的 flag

Thread B:
    while (!flag) {  // B 的 CPU 缓存可能还是 false
        Thread.sleep(1000);
    }
    // 永远不会退出循环
```

### 1.2 JMM 的抽象模型

JMM（Java Memory Model）定义了 Java 线程与主内存之间的抽象关系：

```
┌────────────────────────────────────────────────────────────┐
│                        主内存 (Main Memory)                  │
│   所有变量存储在这里                                          │
└────────────────────────────┬───────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
   ┌─────────┐         ┌─────────┐         ┌─────────┐
   │ Thread 1 │         │ Thread 2 │         │ Thread 3 │
   │ 工作内存  │         │ 工作内存  │         │ 工作内存  │
   │(栈、寄存器)│         │(栈、寄存器)│         │(栈、寄存器)│
   └─────────┘         └─────────┘         └─────────┘

线程间通信：
1. 线程 A 把变量从主内存读到工作内存
2. 线程 A 修改工作内存中的变量
3. 线程 A 把变量写回主内存
4. 线程 B 从主内存读取最新值
```

### 1.3 JMM 的三大特性

| 特性 | 含义 | 实现方式 |
|------|------|---------|
| **原子性** | 操作不可分割 | synchronized |
| **可见性** | 线程修改对其他线程可见 | volatile、synchronized |
| **有序性** | 程序执行顺序符合预期 | volatile、synchronized |

## 二、volatile 关键字

### 2.1 volatile 的作用

`volatile` 是 Java 提供的最轻量级的同步机制：

```java
volatile boolean flag = false;

// 等价于（但不等于）synchronized
synchronized boolean flag = false;
```

**volatile 能保证**：
1. **可见性**：一个线程修改，其他线程立即看到
2. **有序性**：禁止指令重排序

**volatile 不能保证**：
- 原子性（复合操作如 i++）

### 2.2 volatile 保证可见性

**没有 volatile**：
```
线程 A                          线程 B
────────                       ────────
flag = true  ──写入──→  主内存  ──读取──→  while(!flag)
(工作内存)                      (工作内存)
                                   ↑
                               可能还是旧值！
```

**有 volatile**：
```
线程 A                          线程 B
────────                       ────────
                               ┌─────────────────────┐
flag = true  ──写入──→  主内存  │ store barrier       │
(工作内存)                     │ 强制刷新到主内存     │
                               └─────────────────────┘
                                   ↑
                               读取最新值！
                               while(!flag) 退出
```

**关键点**：
- 写 volatile：强制将值刷新到主内存
- 读 volatile：强制从主内存读取最新值

### 2.3 volatile 保证有序性（禁止指令重排序）

**什么是指令重排序**？

编译器、CPU、运行时可能对指令进行重排序以优化性能，前提是结果不变。

```java
// 示例：双重检查锁单例
public class Singleton {
    private static Singleton instance;
    
    public static Singleton getInstance() {
        if (instance == null) {           // 指令 1：检查
            synchronized (Singleton.class) {
                if (instance == null) {   // 指令 2：再检查
                    instance = new Singleton();  // 指令 3：创建
                }
            }
        }
        return instance;
    }
}
```

**`instance = new Singleton()` 的实际执行顺序**：
```
1. 分配内存
2. 调用构造函数
3. 将引用赋值给 instance

但可能被重排序为：
1. 分配内存
2. 将引用赋值给 instance  ← 其他线程可能看到非 null
3. 调用构造函数           ← 但对象还未初始化！
```

**volatile 如何禁止重排序**？

```java
private static volatile Singleton instance;
```

`volatile` 使用内存屏障（Memory Barrier）防止指令重排序：

```
volatile 写操作后：      StoreStore Barrier ──→ 强制所有写完成
volatile 读操作前：      LoadLoad Barrier ──→ 强制所有读完成
volatile 读操作后：      LoadStore Barrier ──→ 强制读取后再写入
```

### 2.4 volatile 的底层实现

在字节码层面，`volatile` 关键字会生成带 `ACC_VOLATILE` 标志的字段：

```java
// 源代码
volatile int x = 10;

// 字节码
// 在字段定义中会有 ACC_VOLATILE 标志
```

在 JVM 层面，HotSpot 实现使用 `Lock` 前缀指令（等价于内存屏障）：

```cpp
// HotSpot 源码（简化）
void OrderAccess::fence() {
    if (os::is_MP()) {
        __asm {
            lock addl [rsp], 0;  // Lock 前缀 = 内存屏障
        }
    }
}
```

**Lock 前缀指令的作用**：
1. 写操作时：强制将值刷新到主内存，并使其他 CPU 缓存失效
2. 读操作时：强制从主内存读取，刷新 CPU 缓存

### 2.5 volatile 的使用场景

**场景 1：状态标志**

```java
// 适合：boolean/引用类型，作为"完成标志"
volatile boolean shutdownRequested = false;

public void shutdown() {
    shutdownRequested = true;
}

public void doWork() {
    while (!shutdownRequested) {
        // 处理任务
    }
}
```

**场景 2：双重检查锁（单例）**

```java
public class Singleton {
    // 关键：volatile 防止重排序
    private static volatile Singleton instance;
    
    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

**场景 3：观察外部状态**

```java
// 适合：作为"观察者"，不涉及复合操作
public class User {
    volatile String name;  // 适合：每次赋值都是完整替换
    
    // 不适合：
    // volatile int counter;
    // counter++;  // 这个不是原子操作！
}
```

### 2.6 volatile 的局限：无法保证原子性

**i++ 不是原子操作**：
```
i++ 实际分为三步：
1. 读取 i 的值
2. i + 1
3. 写回 i

即使 i 是 volatile，多线程下仍会出问题：
```

```java
volatile int i = 0;

Thread 1: read i(0) → i+1(1) → write i(1)
Thread 2: read i(0) → i+1(1) → write i(1)
                                      ↑
                                 最终 i = 1，不是 2！
```

**解决方案：使用原子类**

```java
import java.util.concurrent.atomic.AtomicInteger;

AtomicInteger i = new AtomicInteger(0);

// 线程安全
i.incrementAndGet();  // i++
i.getAndIncrement();  // ++i
```

## 三、Happens-Before 规则

### 3.1 什么是 Happens-Before？

**定义**：如果操作 A happens-before 操作 B，那么 A 的执行结果对 B 可见，且 A 的执行顺序在 B 之前。

> 注意：happens-before **不保证** A 一定在 B 之前执行，它保证的是**可见性和有序性**。

```
A happens-before B：
┌─────────────────────────────────────────┐
│  A    │                                │
│  ↓    │  JMM 保证                       │
│ 执行完成 ───────────────────────────────→ B 可见 A 的结果 │
└─────────────────────────────────────────┘
```

### 3.2 JMM 定义的关键规则

| 规则 | 含义 |
|------|------|
| **程序顺序规则** | 同一个线程中，前面的操作 happens-before 后面的操作 |
| **监视器锁规则** | 解锁 happens-before 加锁 |
| **volatile 规则** | volatile 写 happens-before  volatile 读 |
| **线程启动规则** | Thread.start() happens-before 线程内的第一个操作 |
| **线程终止规则** | 线程内所有操作 happens-before 其他线程检测到终止 |
| **传递性** | A happens-before B，B happens-before C，则 A happens-before C |

### 3.3 程序顺序规则

```java
int a = 1;      // 操作 1
int b = 2;      // 操作 2
a = a + 1;      // 操作 3

// 同一个线程内：
// 操作 1 happens-before 操作 2
// 操作 2 happens-before 操作 3
// 操作 1 happens-before 操作 3（传递性）
```

### 3.4 监视器锁规则

```java
synchronized (lock) {
    x = 10;  // 写
}
synchronized (lock) {
    int y = x;  // 读
}

// 第一个 synchronized 的解锁
// happens-before 第二个 synchronized 的加锁
// 所以 y 一定能读到 x = 10
```

### 3.5 volatile 规则（最重要）

```java
volatile boolean ready = false;
int result = 0;

// 线程 A
result = 42;
ready = true;  // volatile 写

// 线程 B
if (ready) {  // volatile 读
    System.out.println(result);  // 一定能读到 42
}
```

**原理**：
```
线程 A                          线程 B
────────                       ────────
result = 42                     if (ready)
   ↓                              ↓
store barrier → 主内存        load barrier ← 主内存
ready = true                     读取 ready = true
   ↓                              ↓
store barrier → 主内存        读取 result = 42 ✓
```

### 3.6 线程启动与终止规则

**线程启动**：

```java
Thread B = new Thread(() -> {
    x = 100;  // 线程 B 的第一个操作
});
x = 50;
B.start();  // start() happens-before 线程 B 的第一个操作

// 所以线程 B 一定能读到 x = 50（如果在线程 B 运行前修改）
```

**线程终止**：

```java
Thread B = new Thread(() -> {
    x = 100;
});
x = 50;
B.start();
B.join();  // join() 返回后，能看到线程 B 对 x 的修改

// join() 返回后，一定能读到 x = 100
```

### 3.7 Happens-Before 与可见性

**没有 happens-before 关系**：

```java
int a = 0;
int b = 0;

Thread 1:        Thread 2:
a = 1;           System.out.println(b);
b = 2;           System.out.println(a);
```

**可能输出**：
- b=2, a=1 ✓（符合程序顺序）
- b=0, a=0 ✓（线程 2 先执行）
- b=2, a=0 ⚠️（a=1 被重排序到 b=2 后面，且对线程 2 不可见）

**为什么会出现 a=0**？

JMM 允许：
```
Thread 1:          Thread 2:
b = 2; ──────→     读取 b = 2
a = 1;             读取 a = 0（还未写入！）
```

**加入 volatile**：

```java
volatile int b = 0;
int a = 0;

Thread 1:        Thread 2:
a = 1;           while (b != 2) {}
b = 2;           System.out.println(a);  // 一定是 1！
```

因为 volatile 规则：volatile 写 happens-before volatile 读。

## 四、volatile 与 synchronized 对比

### 4.1 功能对比

| 特性 | volatile | synchronized |
|------|---------|-------------|
| 原子性 | ❌ 不保证 | ✅ 保证 |
| 可见性 | ✅ 保证 | ✅ 保证 |
| 有序性 | ✅ 保证（单线程）| ✅ 保证（多线程）|
| 性能 | 高（轻量级）| 低（重量级）|

### 4.2 使用场景对比

```java
// volatile：适合作为"通知标志"
volatile boolean initialized = false;

// synchronized：适合需要复合操作
synchronized void increment() {
    counter++;  // 需要读-改-写三部曲
}
```

### 4.3 性能差异

```bash
# 测试代码
volatile long l = 0;
synchronized long sl = 0;

// 10 亿次自增结果：
# volatile: ~2 秒
# synchronized: ~15 秒
```

**原因**：synchronized 涉及锁的获取、释放、上下文切换。

## 五、CAS 与原子类

### 5.1 什么是 CAS？

CAS（Compare-And-Swap）：比较并交换，是一种无锁算法。

```java
// CAS 伪代码
boolean CAS(location, expectedValue, newValue) {
    if (location.value == expectedValue) {
        location.value = newValue;
        return true;
    }
    return false;
}
```

**三条指令完成原子操作**：
```
1. 读取 location.value → old
2. 比较 old == expected
3. 如果相等，location.value = new
```

### 5.2 CAS 的问题

**问题 1：ABA 问题**

```java
// 线程 A：CAS(position, A, C)
// 线程 B：A → B → A（又变回 A）
// 线程 A：发现还是 A，CAS 成功
//          但 position 已经变化过了！
```

**解决方案：AtomicStampedReference**

```java
AtomicStampedReference<Integer> ref = new AtomicStampedReference<>(1, 0);

// CAS 时检查版本号
ref.compareAndSet(1, 2, 1, 2);
```

**问题 2：自旋开销**

```java
// 可能多次重试
do {
    old = value.get();
    new = old + 1;
} while (!value.compareAndSet(old, new));  // 失败就重试
```

### 5.3 原子类家族

```java
// 基础类型
AtomicInteger
AtomicLong
AtomicBoolean

// 数组
AtomicIntegerArray
AtomicLongArray
AtomicReferenceArray

// 引用
AtomicReference
AtomicStampedReference
AtomicMarkableReference

// 字段更新
AtomicIntegerFieldUpdater
AtomicLongFieldUpdater
AtomicReferenceFieldUpdater
```

### 5.4 LongAdder（JDK 8+）

```java
// 高并发下的 Long
LongAdder adder = new LongAdder();
adder.increment();      // 线程安全
adder.add(100);
long sum = adder.sum();

// 原理：分段 CAS，减少竞争
// 不同线程更新不同 cell，最后求和
```

```java
// LongAdder vs AtomicLong
// 并发度低：两者性能相近
// 并发度高：LongAdder 性能更好

// LongAdder.sum() 非线程安全，需要同步
```

## 六、实战案例

### 案例 1：订单状态更新

```java
// 问题：状态更新可能丢失
private boolean orderCompleted = false;

public void completeOrder() {
    if (!orderCompleted) {  // 检查
        // ...
        orderCompleted = true;  // 设置
    }
}

// 多线程下可能多次执行

// 解决：volatile + double check
private volatile boolean orderCompleted = false;

public void completeOrder() {
    if (!orderCompleted) {  // 第一次检查
        synchronized (this) {
            if (!orderCompleted) {  // 第二次检查
                // 执行订单完成逻辑
                orderCompleted = true;
            }
        }
    }
}
```

### 案例 2：配置加载

```java
// 问题：配置可能被缓存
private Config config;

public Config getConfig() {
    if (config == null) {
        config = loadConfig();  // 多个线程可能同时加载
    }
    return config;
}

// 解决：volatile + double check
private volatile Config config;

public Config getConfig() {
    if (config == null) {
        synchronized (this) {
            if (config == null) {
                config = loadConfig();
            }
        }
    }
    return config;
}
```

### 案例 3：单例模式

```java
// 推荐：双重检查锁 + volatile
public class Singleton {
    private static volatile Singleton instance;
    
    private Singleton() {}
    
    public static Singleton getInstance() {
        if (instance == null) {
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();
                }
            }
        }
        return instance;
    }
}
```

## 七、面试高频问题

### Q1：volatile 和 synchronized 的区别？

**答**：
| 特性 | volatile | synchronized |
|------|---------|-------------|
| 原子性 | 不保证 | 保证 |
| 可见性 | 保证 | 保证 |
| 有序性 | 保证（单线程）| 保证（多线程）|
| 性能 | 高 | 低 |
| 使用场景 | 状态标志、观察者 | 复合操作 |

### Q2：volatile 如何保证可见性？

**答**：
- 写操作后：强制将值刷新到主内存
- 读操作前：强制从主内存读取最新值
- 底层实现：Lock 前缀指令，使 CPU 缓存失效

### Q3：volatile 如何禁止指令重排序？

**答**：通过内存屏障：
- StoreStore Barrier：volatile 写之前
- LoadLoad Barrier：volatile 读之后
- StoreLoad Barrier：volatile 读写之间

### Q4：happens-before 是什么？

**答**：一种可见性保证规则。如果 A happens-before B，那么 A 的结果对 B 可见。

**核心规则**：
1. 程序顺序规则：同一个线程内，前 happens-before 后
2. 监视器锁规则：解锁 happens-before 加锁
3. volatile 规则：volatile 写 happens-before 读
4. 线程启动/终止规则

### Q5：CAS 有什么问题？

**答**：
- **ABA 问题**：值从 A→B→A，但 CAS 无法检测
  - 解决：使用 `AtomicStampedReference`
- **自旋开销**：高竞争下重试频繁
  - 解决：使用 `LongAdder`

### Q6：什么是内存屏障？

**答**：CPU 级别的指令，用于：
1. 阻止 CPU 重排序
2. 强制刷新缓存

**volatile 的内存屏障**：
- 写后：StoreStore + StoreLoad
- 读后：LoadLoad + LoadStore

## 八、总结

**volatile 核心要点**：
- 保证可见性和有序性
- 不保证原子性
- 适用于状态标志、观察者模式
- 底层通过 Lock 前缀指令实现

**happens-before 核心规则**：
- 程序顺序、监视器锁、volatile
- 线程启动/终止/中断
- 传递性

**并发编程最佳实践**：
1. 优先使用 volatile（简单场景）
2. 需要原子性时使用原子类
3. 复合操作使用 synchronized
4. 避免过度同步

---

**下一篇预告**：Spring IoC 容器深度解析 —— Bean 生命周期、依赖注入、作用域

**参考资料**：
- 《深入理解 Java 虚拟机》- 周志明
- 《Java 并发编程实战》- Brian Goetz
- JSR-133: Java Memory Model and Thread Specification
