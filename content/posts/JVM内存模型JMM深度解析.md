---
title: "JVM 内存模型（JMM）深度解析"
date: 2026-05-12T10:00:00+08:00
draft: false
categories: ["jvm"]
tags: ["jvm", "jmm", "volatile", "happens-before", "memory-model"]
---


# JVM 内存模型（JMM）深度解析

> 面试高频问题：什么是 JMM？可见性、原子性、有序性？happens-before 规则？

## 引言

Java 内存模型（Java Memory Model，JMM）是 Java 虚拟机规范中定义的一种抽象模型，用于屏蔽各种硬件和操作系统的内存访问差异，实现跨平台的一致性内存访问。理解 JMM 是编写正确并发程序的基础。

## 一、JMM 基础

### 1.1 为什么需要 JMM？

```
不同硬件的内存模型差异：
┌──────────────────────────────────────────────────┐
│ x86 处理器: 强内存模型                            │
│   → 可见性好，重排序少                            │
│                                                   │
│ ARM/Power 处理器: 弱内存模型                      │
│   → 可见性差，重排序多                            │
│                                                   │
│ JMM: 统一抽象模型                                 │
│   → 跨平台一致的并发行为                          │
└──────────────────────────────────────────────────┘
```

### 1.2 JMM 抽象模型

```
┌────────────────────────────────────────────────────┐
│                  线程 A                              │
│  ┌──────────────┐     ┌──────────────────┐        │
│  │ 工作内存      │     │ 工作内存           │        │
│  │ (本地缓存)   │     │ (本地缓存)        │        │
│  │  ├─ 变量副本 │     │  ├─ 变量副本      │        │
│  └──────┬───────┘     └──────┬───────────┘        │
│         │                    │                      │
│  read/write            read/write                  │
│         │                    │                      │
│         ▼                    ▼                      │
│  ┌─────────────────────────────────────────────┐  │
│  │            主内存（Main Memory）              │  │
│  │   ┌────────┐ ┌────────┐ ┌────────┐         │  │
│  │   │ 变量 1 │ │ 变量 2 │ │ 变量 3 │         │  │
│  │   └────────┘ └────────┘ └────────┘         │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│                  线程 B                              │
└────────────────────────────────────────────────────┘
```

**JMM 定义了 8 种原子操作**：

| 操作 | 作用 | 作用于 |
|------|------|--------|
| `lock` | 将变量标识为线程独占 | 主内存 |
| `unlock` | 解除独占 | 主内存 |
| `read` | 读取变量到工作内存 | 主内存 → 工作内存 |
| `load` | 将 read 读到的值放入工作内存副本 | 工作内存 |
| `use` | 将工作内存值传给执行引擎 | 工作内存 |
| `assign` | 将执行引擎值赋给工作内存副本 | 工作内存 |
| `store` | 将工作内存值传到主内存 | 工作内存 → 主内存 |
| `write` | 将 store 传来的值放入主内存变量 | 主内存 |

## 二、三大特性

### 2.1 可见性

**问题**：一个线程修改了共享变量，其他线程不能立即看到。

```java
// 可见性问题
public class VisibilityProblem {
    private static boolean running = true;
    
    public static void main(String[] args) throws InterruptedException {
        new Thread(() -> {
            int count = 0;
            while (running) {  // 可能永远看不到 running = false
                count++;
            }
            System.out.println("停止，count=" + count);
        }).start();
        
        Thread.sleep(1000);
        running = false;  // 主线程修改，但工作线程可能看不到
    }
}
```

**解决**：`volatile`、`synchronized`、`Lock`

```java
// 方式 1：volatile（推荐）
private static volatile boolean running = true;

// 方式 2：synchronized
private static boolean running = true;
// 读取时加锁
synchronized (lock) {
    while (running) { ... }
}
```

### 2.2 原子性

**问题**：一个操作或多个操作，要么全部执行且不被中断，要么都不执行。

```java
// 原子性问题
public class AtomicityProblem {
    private static int count = 0;
    
    public static void main(String[] args) throws InterruptedException {
        Runnable task = () -> {
            for (int i = 0; i < 10000; i++) {
                count++;  // 非原子操作！
            }
        };
        
        Thread t1 = new Thread(task);
        Thread t2 = new Thread(task);
        t1.start();
        t2.start();
        t1.join();
        t2.join();
        
        System.out.println(count);  // 预期 20000，实际可能 < 20000
    }
}
```

**count++ 的字节码**：
```
1. getstatic     # 读取 count
2. iconst_1      # 常量 1
3. iadd          # 加 1
4. putstatic     # 写回 count
```

**4 步操作不是原子的！** 可能在第 1 步后被其他线程抢占。

**解决**：`synchronized`、`Lock`、`AtomicInteger`

```java
// 方式 1：synchronized
synchronized (lock) {
    count++;
}

// 方式 2：AtomicInteger（推荐）
private static AtomicInteger count = new AtomicInteger(0);
count.incrementAndGet();  // 原子操作

// 方式 3：ReentrantLock
lock.lock();
try {
    count++;
} finally {
    lock.unlock();
}
```

### 2.3 有序性

**问题**：编译器和处理器可能对指令重排序。

```java
// 有序性问题
public class OrderingProblem {
    private static int x = 0;
    private static int y = 0;
    private static int a = 0;
    private static int b = 0;
    
    public static void main(String[] args) throws InterruptedException {
        for (int i = 0; i < 100000; i++) {
            x = 0; y = 0; a = 0; b = 0;
            
            Thread t1 = new Thread(() -> {
                a = 1;   // 可能被重排序到 x = b 之后
                x = b;
            });
            
            Thread t2 = new Thread(() -> {
                b = 1;   // 可能被重排序到 y = a 之后
                y = a;
            });
            
            t1.start();
            t2.start();
            t1.join();
            t2.join();
            
            // 正常情况不可能 x=0, y=0
            // 但重排序可能导致 x=0, y=0
            if (x == 0 && y == 0) {
                System.out.println("重排序发生！");
            }
        }
    }
}
```

**解决**：`volatile`（禁止重排序）、`synchronized`

### 2.4 三大特性总结

| 特性 | volatile | synchronized | Lock | Atomic |
|------|----------|-------------|------|--------|
| 可见性 | ✅ | ✅ | ✅ | ✅ |
| 原子性 | ❌ | ✅ | ✅ | ✅ |
| 有序性 | ✅（部分）| ✅ | ✅ | ✅ |

## 三、happens-before 规则

### 3.1 什么是 happens-before？

**happens-before**：如果操作 A happens-before 操作 B，则 A 的结果对 B 可见。

**注意**：happens-before 不是"时间上先发生"，而是"前一个操作的结果对后一个操作可见"。

### 3.2 八大规则

| 规则 | 说明 |
|------|------|
| **1. 程序顺序规则** | 同一线程中，按代码顺序，前面的操作 happens-before 后面的 |
| **2. 监视器锁规则** | unlock 操作 happens-before 后续对同一锁的 lock |
| **3. volatile 规则** | volatile 写 happens-before 后续对同一变量的读 |
| **4. 线程启动规则** | Thread.start() happens-before 该线程的所有操作 |
| **5. 线程终止规则** | 线程的所有操作 happens-before Thread.join() 返回 |
| **6. 线程中断规则** | interrupt() happens-before 被中断线程检测到中断 |
| **7. 对象终结规则** | 构造函数执行 happens-before finalize() |
| **8. 传递性** | A happens-before B，B happens-before C → A happens-before C |

### 3.3 规则示例

```java
// 规则 1：程序顺序
int a = 1;    // A
int b = a;    // B
// A happens-before B（同一线程）

// 规则 2：监视器锁
synchronized (lock) {
    // 修改共享变量
}  // unlock happens-before 后续 lock

// 规则 3：volatile
volatile boolean flag = false;
// 线程 A
flag = true;           // volatile 写
// 线程 B
if (flag) { ... }     // volatile 读，能看到 flag = true

// 规则 4 + 规则 3 + 规则 8（经典 DCL）
public class Singleton {
    private static volatile Singleton instance;
    
    public static Singleton getInstance() {
        if (instance == null) {                  // 读
            synchronized (Singleton.class) {
                if (instance == null) {
                    instance = new Singleton();  // volatile 写
                }
            }
        }
        return instance;
    }
}
```

## 四、as-if-serial 语义

### 4.1 什么是 as-if-serial？

**as-if-serial**：不管怎么重排序，单线程的执行结果不能改变。

```java
// 以下代码在单线程下可以重排序（不影响结果）
int a = 1;    // A
int b = 2;    // B
int c = a + b; // C

// A 和 B 可以重排序（没有数据依赖）
// 但 C 不能在 A、B 之前（数据依赖）
```

**数据依赖**：如果两个操作访问同一个变量，且其中一个是写，则存在数据依赖。

### 4.2 重排序类型

| 重排序 | 说明 |
|--------|------|
| 编译器重排序 | 编译器优化 |
| 指令级并行重排序 | 处理器优化 |
| 内存系统重排序 | 缓存一致性 |

## 五、volatile 深度解析

### 5.1 volatile 的内存语义

**写**：
- 刷新工作内存到主内存
- 禁止之前的写操作重排序到 volatile 写之后

**读**：
- 从主内存读取最新值
- 禁止之后的读操作重排序到 volatile 读之前

### 5.2 volatile 底层实现

**volatile 写**：
```java
// 字节码：ACC_VOLATILE 标志
// 汇编层面：Lock 前缀指令
// Lock 前缀指令会：
// 1. 将当前 CPU 缓存行数据写回主内存
// 2. 使其他 CPU 缓存行失效（缓存一致性协议 MESI）
```

**内存屏障**：

| 屏障类型 | 说明 |
|---------|------|
| LoadLoad | Load1; LoadLoad; Load2 → Load1 先于 Load2 |
| StoreStore | Store1; StoreStore; Store2 → Store1 先于 Store2 |
| LoadStore | Load; LoadStore; Store → Load 先于 Store |
| StoreLoad | Store; StoreLoad; Load → Store 先于 Load（开销最大）|

**JMM 的 volatile 插入策略**：
```
volatile 写前：插入 StoreStore 屏障
volatile 写后：插入 StoreLoad 屏障
volatile 读后：插入 LoadLoad 屏障 + LoadStore 屏障
```

### 5.3 volatile 的局限

```java
// ❌ volatile 不能保证复合操作的原子性
private volatile int count = 0;

public void increment() {
    count++;  // 读 → 改 → 写，非原子
}

// ✅ 使用 AtomicInteger
private AtomicInteger count = new AtomicInteger(0);

public void increment() {
    count.incrementAndGet();  // 原子操作
}
```

## 六、long 和 double 的特殊规则

### 6.1 非原子性协定

JMM 允许虚拟机对 64 位数据类型（long、double）的读写分为两次 32 位操作。

```java
// 可能的问题（32 位 JVM）
private static long value = 0L;

// 线程 A：写入 0xFFFFFFFFFFFFFFFF
// 线程 B 可能读到：0x00000000FFFFFFFF（高 32 位旧值 + 低 32 位新值）
```

**解决**：`volatile`

```java
private static volatile long value = 0L;  // 保证 64 位读写的原子性
```

**注意**：现代 64 位 JVM 通常已经保证 long/double 读写原子性。

## 七、面试高频问题

### Q1：什么是 JMM？

**答**：
- Java 内存模型，屏蔽硬件差异，定义并发行为的规范
- 核心是三大特性：可见性、原子性、有序性
- 通过 happens-before 规则保证跨线程的可见性

### Q2：happens-before 规则有哪些？

**答**：
1. 程序顺序规则
2. 监视器锁规则
3. volatile 规则
4. 线程启动规则
5. 线程终止规则
6. 线程中断规则
7. 对象终结规则
8. 传递性

### Q3：volatile 的作用？

**答**：
- 保证可见性（刷新工作内存到主内存）
- 禁止指令重排序（内存屏障）
- 不保证原子性（count++ 仍然不安全）

### Q4：为什么 DCL 单例需要 volatile？

**答**：
- `new Singleton()` 不是原子操作（分配内存 → 初始化 → 赋值引用）
- 可能重排序为（分配内存 → 赋值引用 → 初始化）
- 其他线程可能拿到未初始化的对象
- volatile 禁止重排序，保证安全

### Q5：JMM 的三大特性？

**答**：
- **可见性**：一个线程的修改对其他线程可见
- **原子性**：操作不可被中断
- **有序性**：程序执行顺序符合预期

## 八、总结

**JMM 核心要点**：
- **JMM**：Java 内存模型，定义并发行为规范
- **三大特性**：可见性、原子性、有序性
- **happens-before**：8 大规则保证跨线程可见性

**可见性解决方案**：
| 方案 | 可见性 | 原子性 | 有序性 |
|------|--------|--------|--------|
| volatile | ✅ | ❌ | ✅（部分）|
| synchronized | ✅ | ✅ | ✅ |
| Lock | ✅ | ✅ | ✅ |
| Atomic | ✅ | ✅ | ✅ |

**最佳实践**：
1. 共享变量使用 `volatile` 或更高级同步机制
2. 复合操作用 `synchronized` 或 `Atomic` 类
3. 理解 happens-before，避免错误推理
4. long/double 在 32 位 JVM 上用 `volatile`

---

**下一篇预告**：JVM 类文件结构与字节码深度解析

**参考资料**：
- 《Java 虚拟机规范》- James Gosling
- 《深入理解 Java 虚拟机》- 周志明
- JSR-133: Java Memory Model
