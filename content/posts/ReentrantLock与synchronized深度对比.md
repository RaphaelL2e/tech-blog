---
title: ReentrantLock vs synchronized 深度对比
date: 2026-05-12 09:15:00+08:00
updated: '2026-05-12T09:15:00+08:00'
description: 面试高频问题：ReentrantLock 和 synchronized 的区别？公平锁和非公平锁？Condition 是什么？ ReentrantLock 和 synchronized 是 Java 中两种最常用的锁机制。虽然都能实现互斥访问，但它们的实现原理、功能特性和适用场景差异很大。本文将从源。
topic: java-spring
level: intermediate
status: maintained
tags:
- Java
- lock
- reentrantlock
- synchronized
- aqs
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：ReentrantLock 和 synchronized 的区别？公平锁和非公平锁？Condition 是什么？

## 引言

ReentrantLock 和 synchronized 是 Java 中两种最常用的锁机制。虽然都能实现互斥访问，但它们的实现原理、功能特性和适用场景差异很大。本文将从源码层面深度对比两者。

## 一、synchronized 回顾

### 1.1 基本用法

```java
// 1. 同步实例方法（锁是当前实例）
public synchronized void method() {
    // ...
}

// 2. 同步静态方法（锁是 Class 对象）
public static synchronized void method() {
    // ...
}

// 3. 同步代码块（锁是指定对象）
public void method() {
    synchronized (lock) {
        // ...
    }
}
```

### 1.2 底层原理

**同步代码块**：使用 `monitorenter` 和 `monitorexit` 指令

```java
// 源码
synchronized (lock) {
    // 临界区
}

// 字节码
monitorenter      // 获取 monitor 锁
// 临界区
monitorexit       // 释放 monitor 锁
```

**同步方法**：使用 `ACC_SYNCHRONIZED` 标志

```java
// 源码
public synchronized void method() {}

// 字节码：方法访问标志包含 ACC_SYNCHRONIZED
public synchronized method()V;
    // 方法执行前自动获取 monitor 锁
    // 方法执行后自动释放 monitor 锁
```

### 1.3 锁升级过程

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
 │        │          │           │
 │        │          │           └─ 自旋失败，操作系统互斥量
 │        │          └─ CAS 竞争，自旋等待
 │        └─ 第一个线程获取，记录线程 ID
 └─ 对象刚创建
```

**对象头中的锁状态**：

| 锁状态 | 存储内容 | 适用场景 |
|--------|---------|---------|
| 无锁 | 对象哈希码、GC 分代年龄 | 无竞争 |
| 偏向锁 | 线程 ID | 单线程重复获取 |
| 轻量级锁 | 指向栈中锁记录的指针 | 短时间竞争 |
| 重量级锁 | 指向 Monitor 的指针 | 长时间竞争 |

## 二、ReentrantLock 详解

### 2.1 基本用法

```java
private final ReentrantLock lock = new ReentrantLock();

public void method() {
    lock.lock();        // 加锁
    try {
        // 临界区
    } finally {
        lock.unlock();  // 必须在 finally 中释放锁
    }
}
```

### 2.2 核心特性

```java
// 1. 公平锁（按等待顺序获取）
ReentrantLock fairLock = new ReentrantLock(true);

// 2. 非公平锁（默认，允许插队）
ReentrantLock unfairLock = new ReentrantLock(false);

// 3. 可中断锁
try {
    fairLock.lockInterruptibly();  // 可被 interrupt 打断
} catch (InterruptedException e) {
    // 被中断
}

// 4. 尝试获取锁
if (lock.tryLock()) {       // 立即返回
    try {
        // 获取锁成功
    } finally {
        lock.unlock();
    }
} else {
    // 获取锁失败
}

// 5. 超时获取锁
if (lock.tryLock(3, TimeUnit.SECONDS)) {  // 最多等3秒
    try {
        // 获取锁成功
    } finally {
        lock.unlock();
    }
} else {
    // 超时获取失败
}
```

### 2.3 Condition 条件变量

```java
private final ReentrantLock lock = new ReentrantLock();
private final Condition notEmpty = lock.newCondition();  // 条件：非空
private final Condition notFull = lock.newCondition();   // 条件：非满

// 生产者
public void put(Object item) throws InterruptedException {
    lock.lock();
    try {
        while (isFull()) {
            notFull.await();     // 等待"非满"条件
        }
        enqueue(item);
        notEmpty.signal();       // 通知"非空"条件
    } finally {
        lock.unlock();
    }
}

// 消费者
public Object take() throws InterruptedException {
    lock.lock();
    try {
        while (isEmpty()) {
            notEmpty.await();    // 等待"非空"条件
        }
        Object item = dequeue();
        notFull.signal();        // 通知"非满"条件
        return item;
    } finally {
        lock.unlock();
    }
}
```

**Condition vs Object.wait/notify**：

| 特性 | Condition | Object.wait/notify |
|------|-----------|-------------------|
| 条件数量 | 多个 | 单个 |
| 精确唤醒 | `signal()` 指定条件 | `notify()` 随机 |
| 超时 | 支持 | 支持 |
| 不响应中断 | `awaitUninterruptibly()` | 不支持 |

## 三、ReentrantLock 源码解析

### 3.1 AQS（AbstractQueuedSynchronizer）

ReentrantLock 的核心是 AQS：

```
┌────────────────────────────────────────────────────┐
│                    AQS                              │
├────────────────────────────────────────────────────┤
│  state（int）: 锁状态                               │
│    ├─ 0: 未锁定                                    │
│    └─ >0: 锁定（可重入，每次 +1）                    │
│                                                     │
│  exclusiveOwnerThread: 持有锁的线程                  │
│                                                     │
│  CLH 队列: 等待线程的双向链表                        │
│    ┌─────┐    ┌─────┐    ┌─────┐               │
│    │Node │ ←→ │Node │ ←→ │Node │               │
│    └─────┘    └─────┘    └─────┘               │
│     头节点     等待线程    等待线程                  │
└────────────────────────────────────────────────────┘
```

### 3.2 非公平锁加锁流程

```java
// NonfairSync.lock()
final void lock() {
    // 1. CAS 尝试获取锁（插队）
    if (compareAndSetState(0, 1)) {
        setExclusiveOwnerThread(Thread.currentThread());
        return;  // 获取成功
    }
    // 2. CAS 失败，进入 AQS 获取流程
    acquire(1);
}

// AQS.acquire()
public final void acquire(int arg) {
    if (!tryAcquire(arg) &&                    // 再次尝试获取锁
        acquireQueued(addWaiter(Node.EXCLUSIVE), arg))  // 加入等待队列
        selfInterrupt();                       // 设置中断标志
}

// NonfairSync.tryAcquire()
protected final boolean tryAcquire(int acquires) {
    return nonfairTryAcquire(acquires);
}

final boolean nonfairTryAcquire(int acquires) {
    Thread current = Thread.currentThread();
    int c = getState();
    if (c == 0) {
        // 锁空闲，CAS 获取
        if (compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
    } else if (current == getExclusiveOwnerThread()) {
        // 可重入：当前线程持有锁，state +1
        int nextc = c + acquires;
        if (nextc < 0) throw new Error("Maximum lock count exceeded");
        setState(nextc);
        return true;
    }
    return false;
}
```

### 3.3 公平锁加锁流程

```java
// FairSync.lock()
final void lock() {
    acquire(1);  // 不插队，直接进入 AQS 获取流程
}

// FairSync.tryAcquire()
protected final boolean tryAcquire(int acquires) {
    Thread current = Thread.currentThread();
    int c = getState();
    if (c == 0) {
        // 关键区别：先检查队列中是否有等待线程
        if (!hasQueuedPredecessors() &&      // 队列为空才能获取
            compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
    } else if (current == getExclusiveOwnerThread()) {
        int nextc = c + acquires;
        if (nextc < 0) throw new Error("Maximum lock count exceeded");
        setState(nextc);
        return true;
    }
    return false;
}
```

### 3.4 释放锁流程

```java
// ReentrantLock.unlock()
public void unlock() {
    sync.release(1);
}

// AQS.release()
public final boolean release(int arg) {
    if (tryRelease(arg)) {
        Node h = head;
        if (h != null && h.waitStatus != 0)
            unparkSuccessor(h);  // 唤醒后继节点
        return true;
    }
    return false;
}

// Sync.tryRelease()
protected final boolean tryRelease(int releases) {
    int c = getState() - releases;
    if (Thread.currentThread() != getExclusiveOwnerThread())
        throw new IllegalMonitorStateException();
    boolean free = false;
    if (c == 0) {
        // 完全释放
        free = true;
        setExclusiveOwnerThread(null);
    }
    setState(c);  // 可重入：state -1
    return free;
}
```

## 四、核心对比

### 4.1 功能对比

| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| **实现** | JVM 内置 | JDK API（AQS）|
| **加锁方式** | 隐式（自动）| 显式（手动）|
| **可中断** | ❌ | ✅ `lockInterruptibly()` |
| **超时获取** | ❌ | ✅ `tryLock(timeout)` |
| **公平锁** | ❌（只有非公平）| ✅（可选）|
| **条件变量** | 单个（wait/notify）| 多个（Condition）|
| **可重入** | ✅ | ✅ |
| **锁绑定多个条件** | ❌ | ✅ |

### 4.2 性能对比

```
低竞争场景：
┌──────────────────────────────────────────────────────┐
│ synchronized: 偏向锁 → 几乎无开销                      │
│ ReentrantLock: CAS + AQS → 轻微开销                   │
│ 结论: synchronized 稍快                                │
└──────────────────────────────────────────────────────┘

高竞争场景：
┌──────────────────────────────────────────────────────┐
│ synchronized: 重量级锁 → 操作系统互斥量                 │
│ ReentrantLock: CAS + CLH 队列 → 更高效               │
│ 结论: ReentrantLock 更优                               │
└──────────────────────────────────────────────────────┘
```

### 4.3 适用场景

| 场景 | 推荐 | 原因 |
|------|------|------|
| 简单互斥 | synchronized | 简洁、不会忘记释放锁 |
| 需要公平锁 | ReentrantLock | synchronized 不支持 |
| 需要可中断 | ReentrantLock | `lockInterruptibly()` |
| 需要超时 | ReentrantLock | `tryLock(timeout)` |
| 需要多个条件 | ReentrantLock | 多个 Condition |
| 高竞争 | ReentrantLock | AQS 更高效 |

## 五、公平锁 vs 非公平锁

### 5.1 区别

```java
// 非公平锁：新线程直接 CAS 尝试获取，可能插队
lock.lock();  // 不看队列，直接抢

// 公平锁：新线程先看队列，有等待者就排队
lock.lock();  // 先检查队列
```

### 5.2 为什么默认非公平？

```
公平锁的线程切换开销：
┌──────────────────────────────────────────────────┐
│ 线程 A 释放锁                                     │
│   ↓                                              │
│ 唤醒队列中的线程 B                                 │
│   ↓ （线程 B 还没醒来）                           │
│ 线程 C 到达，但公平锁不让 C 获取                   │
│   ↓ （等线程 B 醒来）                             │
│ 线程 B 获取锁                                     │
│                                                   │
│ 结果：有上下文切换延迟                             │
└──────────────────────────────────────────────────┘

非公平锁：
┌──────────────────────────────────────────────────┐
│ 线程 A 释放锁                                     │
│   ↓                                              │
│ 线程 C 刚好到达，CAS 获取成功                      │
│   ↓                                              │
│ 线程 C 立即执行                                   │
│                                                   │
│ 结果：减少上下文切换，吞吐量更高                   │
└──────────────────────────────────────────────────┘
```

**代价**：非公平锁可能导致队列中的线程**饥饿**。

## 六、ReentrantReadWriteLock

### 6.1 读写锁

```java
private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();
private final Lock readLock = rwLock.readLock();    // 读锁（共享）
private final Lock writeLock = rwLock.writeLock();  // 写锁（排他）

// 读操作：多个线程可以同时读
public Object get(String key) {
    readLock.lock();
    try {
        return map.get(key);
    } finally {
        readLock.unlock();
    }
}

// 写操作：独占
public void put(String key, Object value) {
    writeLock.lock();
    try {
        map.put(key, value);
    } finally {
        writeLock.unlock();
    }
}
```

### 6.2 读写锁规则

| 当前状态 | 获取读锁 | 获取写锁 |
|---------|---------|---------|
| 无锁 | ✅ | ✅ |
| 读锁 | ✅ | ❌ |
| 写锁 | ❌（当前线程可降级）| ❌（当前线程可重入）|

### 6.3 锁降级

```java
// 锁降级：写锁 → 读锁（允许）
public void processData() {
    writeLock.lock();
    try {
        // 修改数据
        updateData();
        
        // 降级为读锁（先获取读锁，再释放写锁）
        readLock.lock();
    } finally {
        writeLock.unlock();  // 释放写锁，仍持有读锁
    }
    
    try {
        // 读取数据（其他线程也可以读）
        readData();
    } finally {
        readLock.unlock();   // 释放读锁
    }
}

// 锁升级：读锁 → 写锁（不允许）
public void upgradeLock() {
    readLock.lock();
    try {
        writeLock.lock();  // ❌ 死锁！永远获取不到写锁
    } finally {
        readLock.unlock();
    }
}
```

## 七、面试高频问题

### Q1：ReentrantLock 和 synchronized 的区别？

**答**：
| 特性 | synchronized | ReentrantLock |
|------|-------------|---------------|
| 实现 | JVM 内置 | JDK API（AQS）|
| 加锁 | 隐式（自动）| 显式（手动）|
| 可中断 | ❌ | ✅ |
| 超时获取 | ❌ | ✅ |
| 公平锁 | ❌ | ✅ |
| 条件变量 | 单个 | 多个 |

### Q2：什么是公平锁？什么是非公平锁？

**答**：
- **公平锁**：按等待顺序获取锁（先到先得），吞吐量低
- **非公平锁**：允许插队，吞吐量高，但可能导致饥饿
- ReentrantLock 默认非公平，synchronized 只有非公平

### Q3：AQS 是什么？

**答**：
- **AQS**（AbstractQueuedSynchronizer）：并发工具的基础框架
- 核心是 `state`（同步状态）和 CLH 队列（等待线程队列）
- ReentrantLock、CountDownLatch、Semaphore 都基于 AQS

### Q4：什么是锁降级？为什么需要？

**答**：
- 锁降级：持有写锁时获取读锁，再释放写锁
- 目的：保证数据可见性，写完后立即能读到最新数据
- 锁升级（读锁→写锁）不允许，会死锁

### Q5：synchronized 的锁升级过程？

**答**：
无锁 → 偏向锁（单线程）→ 轻量级锁（CAS 自旋）→ 重量级锁（OS 互斥量）

## 八、总结

**synchronized**：
- JVM 内置，自动加锁/释放
- 锁升级优化（偏向锁 → 轻量级锁 → 重量级锁）
- 简单场景首选

**ReentrantLock**：
- JDK API，手动加锁/释放
- 功能丰富：可中断、超时、公平锁、Condition
- 复杂场景首选

**选择原则**：
1. 简单互斥 → synchronized
2. 需要高级功能 → ReentrantLock
3. 读多写少 → ReentrantReadWriteLock

**最佳实践**：
1. ReentrantLock 必须在 `finally` 中释放锁
2. 避免锁的嵌套（可能死锁）
3. 尽量减小锁的范围
4. 公平锁吞吐量低，默认非公平即可

---

**下一篇预告**：ThreadLocal 深度解析 —— 线程本地变量、内存泄漏、应用场景

**参考资料**：
- 《Java 并发编程的艺术》- 方腾飞
- 《Java 并发编程实战》- Brian Goetz
- JDK 源码：java.util.concurrent.locks.ReentrantLock
