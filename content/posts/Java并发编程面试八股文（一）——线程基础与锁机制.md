---
title: "Java并发编程面试八股文（一）——线程基础与锁机制"
date: 2026-06-15T09:00:00+08:00
draft: false
categories: ["java"]
tags: ["面试", "八股文", "Java", "并发", "线程", "synchronized", "AQS", "volatile", "锁"]
---

# Java并发编程面试八股文（一）——线程基础与锁机制

> 面试高频问题：Java线程有几种创建方式？synchronized底层原理是什么？ReentrantLock和synchronized有什么区别？volatile能保证原子性吗？本文带你系统掌握Java并发编程基础与锁机制的核心知识。

---

## 一、线程基础

### 1.1 线程创建方式

**Q: Java中创建线程有几种方式？**

A: 常见的创建方式有以下几种：

| 方式 | 特点 | 适用场景 |
|------|------|---------|
| 继承Thread类 | 简单直接，但无法继承其他类 | 简单场景 |
| 实现Runnable接口 | 更灵活，避免单继承限制 | 推荐，大多数场景 |
| 实现Callable接口 | 可返回结果、可抛出异常 | 需要返回值的场景 |
| 线程池 | 复用线程、控制并发数 | 生产环境推荐 |

```java
// 方式1：继承Thread
public class MyThread extends Thread {
    @Override
    public void run() {
        System.out.println("Thread running");
    }
}

// 方式2：实现Runnable
public class MyRunnable implements Runnable {
    @Override
    public void run() {
        System.out.println("Runnable running");
    }
}

// 方式3：实现Callable
public class MyCallable implements Callable<String> {
    @Override
    public String call() throws Exception {
        return "Callable result";
    }
}

// 方式4：线程池
ExecutorService executor = Executors.newFixedThreadPool(10);
executor.submit(() -> System.out.println("ThreadPool running"));
```

### 1.2 线程生命周期

**Q: 线程有几种状态？状态如何转换？**

A: Java线程有6种状态（Thread.State枚举）：

```
NEW ──start()──> RUNNABLE ──获取锁失败──> BLOCKED
                     │                        │
                     │                    获取锁
                     │                        ↓
                     │ <─────── notify ──── WAITING
                     │                        ↑
                     │ wait()/join()          │
                     │                        │
                     ↓ 超时                TIMED_WAITING
                 (sleep/wait超时)
                     │
                     ↓
                TERMINATED
```

| 状态 | 说明 |
|------|------|
| NEW | 新建，未调用start() |
| RUNNABLE | 可运行（就绪或运行中） |
| BLOCKED | 阻塞，等待锁 |
| WAITING | 等待，需要其他线程唤醒 |
| TIMED_WAITING | 超时等待 |
| TERMINATED | 终止 |

### 1.3 线程优先级

**Q: 线程优先级有用吗？**

A: 线程优先级范围为1-10，默认为5：

```java
thread.setPriority(Thread.MAX_PRIORITY); // 10
thread.setPriority(Thread.MIN_PRIORITY); // 1
thread.setPriority(Thread.NORM_PRIORITY); // 5
```

**注意事项**：
- 优先级只是给调度器的建议，不保证执行顺序
- 不同操作系统实现不同，可能被忽略
- 不要依赖优先级设计程序逻辑

---

## 二、synchronized关键字

### 2.1 基本用法

**Q: synchronized有几种使用方式？**

A: 三种使用方式：

```java
public class SynchronizedDemo {
    private final Object lock = new Object();
    
    // 1. 同步实例方法 - 锁的是this对象
    public synchronized void instanceMethod() {
        // 临界区
    }
    
    // 2. 同步静态方法 - 锁的是Class对象
    public static synchronized void staticMethod() {
        // 临界区
    }
    
    // 3. 同步代码块 - 锁指定对象
    public void blockMethod() {
        synchronized (lock) {
            // 临界区
        }
    }
}
```

### 2.2 锁升级机制

**Q: synchronized底层原理是什么？什么是锁升级？**

A: synchronized在JVM层面通过Monitor实现，在Java 6后引入了锁升级机制：

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
        ↑          ↑          ↑
    单线程访问  多线程交替  竞争激烈
```

| 锁类型 | 特点 | 适用场景 |
|--------|------|---------|
| 无锁 | 没有锁竞争 | 单线程访问 |
| 偏向锁 | 锁偏向第一个获取的线程 | 同一线程重复获取 |
| 轻量级锁 | CAS自旋获取 | 短时间竞争 |
| 重量级锁 | Monitor阻塞等待 | 长时间竞争 |

**锁升级过程**：

```
1. 偏向锁：在对象头Mark Word中记录线程ID
2. 偏向锁失败 → 升级为轻量级锁
3. 轻量级锁：通过CAS将Mark Word替换为指向栈中Lock Record的指针
4. CAS自旋失败 → 升级为重量级锁
5. 重量级锁：基于Monitor，线程阻塞
```

**对象头结构**：

```
|--------------------------------|--------------------|
| Mark Word (64 bits)            | Class Pointer      |
|--------------------------------|--------------------|
| 无锁: hashcode + age + 01                            |
| 偏向锁: threadID + epoch + age + 01                  |
| 轻量级锁: 指向Lock Record的指针 + 00                  |
| 重量级锁: 指向Monitor的指针 + 10                      |
|--------------------------------|--------------------|
```

### 2.3 锁优化

**Q: JVM对synchronized做了哪些优化？**

A: 主要优化包括：

| 优化技术 | 说明 |
|---------|------|
| 锁消除 | JIT检测到不可能被共享的对象，消除同步 |
| 锁粗化 | 将多次连续的加锁解锁合并为一次 |
| 自适应自旋 | 根据历史自旋成功率动态调整自旋次数 |
| 偏向锁 | 消除无竞争情况下的同步原语 |

```java
// 锁消除示例
public void method() {
    // StringBuffer是线程安全的，但sb是局部变量
    // JIT会消除这里的锁
    StringBuffer sb = new StringBuffer();
    sb.append("a").append("b");
}

// 锁粗化示例
public void loopMethod() {
    for (int i = 0; i < 100; i++) {
        synchronized (lock) { // 每次循环都加锁解锁
            // ...
        }
    }
    // 优化后：锁粗化到循环外
    synchronized (lock) {
        for (int i = 0; i < 100; i++) {
            // ...
        }
    }
}
```

---

## 三、Lock接口与ReentrantLock

### 3.1 ReentrantLock基本使用

**Q: ReentrantLock和synchronized有什么区别？**

A:

| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| 锁类型 | 隐式锁 | 显式锁 |
| 获取方式 | JVM自动获取释放 | 手动lock/unlock |
| 公平性 | 非公平 | 可公平可非公平 |
| 中断响应 | 不支持 | 支持lockInterruptibly |
| 超时获取 | 不支持 | 支持tryLock超时 |
| 条件变量 | 单一条件 | 多条件Condition |
| 性能 | JDK6后差异不大 | 高竞争时略优 |

```java
public class ReentrantLockDemo {
    private final ReentrantLock lock = new ReentrantLock();
    
    public void safeMethod() {
        lock.lock();
        try {
            // 临界区
        } finally {
            lock.unlock(); // 必须在finally中释放
        }
    }
    
    // 可中断锁
    public void interruptibleMethod() throws InterruptedException {
        lock.lockInterruptibly();
        try {
            // 临界区
        } finally {
            lock.unlock();
        }
    }
    
    // 超时获取锁
    public boolean tryLockWithTimeout() {
        try {
            return lock.tryLock(100, TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            return false;
        }
    }
}
```

### 3.2 公平锁与非公平锁

**Q: 公平锁和非公平锁的区别？**

A:

```java
// 非公平锁（默认，性能更好）
ReentrantLock unfairLock = new ReentrantLock();
// 公平锁（按等待顺序获取）
ReentrantLock fairLock = new ReentrantLock(true);
```

| 类型 | 特点 | 优缺点 |
|------|------|--------|
| 非公平锁 | 允许插队 | 吞吐量高，但可能导致饥饿 |
| 公平锁 | 按先来后到 | 保证公平，但性能较低 |

### 3.3 Condition条件变量

**Q: Condition相比wait/notify有什么优势？**

A: Condition支持多条件队列：

```java
public class BoundedBuffer {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();
    
    private final Object[] items = new Object[100];
    private int putIndex, takeIndex, count;
    
    public void put(Object x) throws InterruptedException {
        lock.lock();
        try {
            while (count == items.length)
                notFull.await();  // 队列满，等待notFull条件
            items[putIndex] = x;
            if (++putIndex == items.length) putIndex = 0;
            count++;
            notEmpty.signal();  // 唤醒等待notEmpty的线程
        } finally {
            lock.unlock();
        }
    }
    
    public Object take() throws InterruptedException {
        lock.lock();
        try {
            while (count == 0)
                notEmpty.await();  // 队列空，等待notEmpty条件
            Object x = items[takeIndex];
            if (++takeIndex == items.length) takeIndex = 0;
            count--;
            notFull.signal();  // 唤醒等待notFull的线程
        } finally {
            lock.unlock();
        }
        return x;
    }
}
```

---

## 四、AQS框架原理

### 4.1 AQS核心设计

**Q: 什么是AQS？它是如何实现的？**

A: AQS(AbstractQueuedSynchronizer)是JUC的核心基类：

```
┌─────────────────────────────────────────┐
│              AQS核心结构                 │
├─────────────────────────────────────────┤
│  state (volatile int) - 同步状态        │
│  CLH队列 - 等待线程的双向链表            │
│  Node: head → ... → tail               │
│       (waitStatus, prev, next, thread)  │
└─────────────────────────────────────────┘
```

**核心要素**：

| 组件 | 说明 |
|------|------|
| state | 同步状态，CAS修改 |
| CLH队列 | 等待线程的双向链表 |
| Node | 队列节点，包含线程引用和等待状态 |
| 独占模式 | 同时只有一个线程获取锁（ReentrantLock） |
| 共享模式 | 多个线程同时获取（CountDownLatch） |

### 4.2 获取锁流程

**Q: AQS获取锁的流程是什么？**

A:

```
tryAcquire(state=0?)
    │
    ├─ 成功 → 获取锁
    │
    └─ 失败 → addWaiter()加入队列
                  │
                  acquireQueued()
                  │
                  ├─ 前驱是head → 再次tryAcquire
                  │       │
                  │       ├─ 成功 → setHead, 返回
                  │       │
                  │       └─ 失败 → shouldParkAfterFailingAcquire
                  │                     │
                  │                     └─ parkAndCheckInterrupt
                  │                              │
                  └─ 否则 → shouldParkAfterFailingAcquire
                                  │
                                  └─ 阻塞等待
```

### 4.3 模板方法模式

**Q: AQS如何支持不同同步器？**

A: AQS使用模板方法模式，子类只需实现：

```java
// 独占模式需要实现
protected boolean tryAcquire(int arg);      // 尝试获取
protected boolean tryRelease(int arg);      // 尝试释放

// 共享模式需要实现
protected int tryAcquireShared(int arg);    // 尝试获取
protected boolean tryReleaseShared(int arg);// 尝试释放

// 示例：简单互斥锁
class Mutex extends AbstractQueuedSynchronizer {
    @Override
    protected boolean tryAcquire(int arg) {
        return compareAndSetState(0, 1);
    }
    
    @Override
    protected boolean tryRelease(int arg) {
        setState(0);
        return true;
    }
}
```

---

## 五、volatile关键字

### 5.1 可见性与有序性

**Q: volatile有什么作用？**

A: volatile保证可见性和有序性，但不保证原子性：

| 特性 | 说明 |
|------|------|
| 可见性 | 写操作立即刷新到主内存，读操作从主内存读取 |
| 有序性 | 禁止指令重排序 |
| 原子性 | 不保证（i++不是原子操作） |

```java
public class VolatileDemo {
    private volatile boolean running = true;
    
    public void stop() {
        running = false; // 立即对其他线程可见
    }
    
    public void doWork() {
        while (running) {
            // 工作逻辑
        }
    }
}
```

### 5.2 内存屏障

**Q: volatile如何保证可见性和有序性？**

A: 通过内存屏障（Memory Barrier）：

```
StoreStore屏障
volatile写
StoreLoad屏障

LoadLoad屏障
volatile读
LoadStore屏障
```

| 屏障类型 | 作用 |
|---------|------|
| LoadLoad | 禁止Load1和Load2重排序 |
| StoreStore | 禁止Store1和Store2重排序 |
| LoadStore | 禁止Load和Store重排序 |
| StoreLoad | 禁止Store和Load重排序 |

### 5.3 volatile应用场景

**Q: 什么时候应该使用volatile？**

A:

```java
// 1. 状态标志位
volatile boolean shutdownRequested;

// 2. 单例双重检查
public class Singleton {
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

// 3. 开销较低的读-写锁
public class CheesyCounter {
    private volatile int value;
    
    public int getValue() { return value; } // 无锁读
    
    public synchronized void increment() { value++; } // 同步写
}
```

---

## 六、线程通信

### 6.1 wait/notify机制

**Q: wait/notify为什么要在同步块中使用？**

A:

```java
synchronized (lock) {
    while (condition不满足) {
        lock.wait(); // 释放锁并等待
    }
    // 条件满足，执行操作
}

synchronized (lock) {
    // 改变条件
    lock.notify(); // 或 lock.notifyAll()
}
```

**原因**：
- wait/notify基于对象的Monitor实现
- 必须先获取Monitor（synchronized）才能调用
- 避免"信号丢失"和"虚假唤醒"

**wait vs sleep**：

| wait | sleep |
|------|-------|
| Object方法 | Thread方法 |
| 释放锁 | 不释放锁 |
| 需要notify唤醒 | 超时自动唤醒 |
| 必须在同步块 | 任意位置 |

### 6.2 join方法

**Q: join方法的作用是什么？**

A: join让当前线程等待目标线程结束：

```java
public static void main(String[] args) throws InterruptedException {
    Thread t = new Thread(() -> {
        // 耗时操作
    });
    t.start();
    t.join(); // 主线程等待t结束
    System.out.println("t已完成");
}
```

**原理**：join内部调用wait，线程结束时JVM自动调用notifyAll。

### 6.3 线程中断

**Q: 如何正确中断线程？**

A: 使用interrupt机制：

```java
public void run() {
    while (!Thread.currentThread().isInterrupted()) {
        try {
            // 工作
            Thread.sleep(1000);
        } catch (InterruptedException e) {
            // sleep/wait被中断会清除中断状态
            Thread.currentThread().interrupt(); // 恢复中断状态
            break;
        }
    }
}

// 调用方
thread.interrupt(); // 发送中断信号
```

---

## 七、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| 线程基础 | 6种状态、创建方式、生命周期 | NEW, RUNNABLE, BLOCKED, WAITING |
| synchronized | 锁升级、Monitor、偏向锁/轻量级/重量级 | Mark Word, CAS, 自旋锁 |
| ReentrantLock | 公平/非公平、Condition、可中断 | tryLock, lockInterruptibly |
| AQS | state变量、CLH队列、模板方法 | acquire, release, Node |
| volatile | 可见性、有序性、内存屏障 | JMM, happens-before, StoreLoad |
| 线程通信 | wait/notify、join、interrupt | Monitor, 虚假唤醒, 中断状态 |

---

> 🎯 **下期预告**：《Java并发编程面试八股文（二）——JUC并发工具类与线程池》将深入CountDownLatch、CyclicBarrier、Semaphore、线程池核心参数、拒绝策略等面试高频话题，敬请期待！
