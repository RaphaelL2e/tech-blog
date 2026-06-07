---
title: "Java AQS 深度解析：并发编程的基石"
date: 2026-06-07T09:00:00+08:00
draft: false
categories: ["java"]
tags: ["java", "AQS", "并发", "ReentrantLock", "CountDownLatch", "源码解析"]
---

# Java AQS 深度解析：并发编程的基石

> 面试高频问题：AQS 的原理是什么？CLH 队列是怎么实现的？独占模式和共享模式有什么区别？为什么 AQS 是并发包的基石？

## 引言

`AbstractQueuedSynchronizer`（AQS）是 Java 并发包（`java.util.concurrent`）中最核心的框架类，ReentrantLock、CountDownLatch、Semaphore、ReentrantReadWriteLock 等常用并发工具类都基于 AQS 实现。理解 AQS 是深入掌握 Java 并发编程的必经之路。

**本文要点**：

- AQS 核心设计思想与架构
- CLH 队列（FIFO 等待队列）的实现
- 独占模式（Exclusive）源码全流程
- 共享模式（Shared）源码全流程
- Condition 条件队列机制
- AQS 在并发工具类中的应用

## 一、AQS 核心设计思想

### 1.1 模板方法模式

AQS 采用**模板方法模式**，将同步状态的管理和线程排队封装在基类中，子类只需实现特定方法来定义获取和释放同步状态的逻辑。

```
┌──────────────────────────────────────────────┐
│                  AQS 基类                     │
│                                              │
│  ┌─ 模板方法（不可重写）────────────────────┐  │
│  │ acquire()       独占获取                  │  │
│  │ release()       独占释放                  │  │
│  │ acquireShared() 共享获取                  │  │
│  │ releaseShared() 共享释放                  │  │
│  └───────────────────────────────────────────┘  │
│  ┌─ 钩子方法（子类重写）────────────────────┐  │
│  │ tryAcquire()    独占式尝试获取            │  │
│  │ tryRelease()    独占式尝试释放            │  │
│  │ tryAcquireShared() 共享式尝试获取         │  │
│  │ tryReleaseShared() 共享式尝试释放         │  │
│  │ isHeldExclusively() 是否被独占持有        │  │
│  └───────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
        ▲           ▲           ▲
        │           │           │
  ReentrantLock  CountDownLatch  Semaphore
```

### 1.2 核心状态变量

AQS 的核心是一个 `volatile int state`，通过 CAS 操作来修改：

```java
public abstract class AbstractQueuedSynchronizer
    extends AbstractOwnableSynchronizer {

    // 同步状态，volatile保证可见性
    private volatile int state;

    // CAS修改state（Unsafe类提供）
    protected final boolean compareAndSetState(int expect, int update) {
        return unsafe.compareAndSwapInt(this, stateOffset, expect, update);
    }
}
```

**不同工具类对 state 的语义**：

| 工具类 | state 含义 | 初始值 |
|--------|-----------|--------|
| ReentrantLock | 锁重入次数 | 0（未锁定） |
| CountDownLatch | 剩余计数 | N（初始计数） |
| Semaphore | 可用许可数 | permits |
| ReentrantReadWriteLock | 高16位=读锁持有数，低16位=写锁重入数 | 0 |

### 1.3 FIFO 等待队列（CLH 变体）

AQS 内部维护一个 **CLH（Craig, Landin, and Hagersten）队列变体**的双向链表：

```
     head          Node          Node          tail
       │             │             │             │
       ▼             ▼             ▼             ▼
  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ sentinel │←→│ Thread-A │←→│ Thread-B │←→│ Thread-C │
  │ (空节点) │  │ SIGNAL   │  │ SIGNAL   │  │ 0       │
  └─────────┘  └─────────┘  └─────────┘  └─────────┘
       ↑
   获取到锁的线程
```

**Node 节点核心字段**：

```java
static final class Node {
    // 等待状态
    volatile int waitStatus;
    // 前驱节点
    volatile Node prev;
    // 后继节点
    volatile Node next;
    // 等待的线程
    volatile Thread thread;
    // 条件队列中的下一个节点
    Node nextWaiter;

    // waitStatus 取值
    static final int CANCELLED  =  1; // 线程已取消
    static final int SIGNAL     = -1; // 后继节点需要被唤醒
    static final int CONDITION  = -2; // 在条件队列中
    static final int PROPAGATE  = -3; // 共享模式传播唤醒
}
```

## 二、独占模式源码全流程

### 2.1 acquire(int arg) — 获取独占锁

这是 ReentrantLock.lock() 的底层实现：

```java
public final void acquire(int arg) {
    if (!tryAcquire(arg) &&                    // ① 尝试获取锁
        acquireQueued(addWaiter(Node.EXCLUSIVE), arg))  // ② 获取失败，入队并阻塞
        selfInterrupt();                       // ③ 如果被中断过，恢复中断标志
}
```

**流程图**：

```
tryAcquire(arg)
    │
    ├─ 成功 → 获取到锁，返回
    │
    └─ 失败
        │
        addWaiter(EXCLUSIVE)  ← 将当前线程包装为Node加入队尾
            │
            acquireQueued(node, arg)  ← 在队列中自旋/阻塞等待
                │
                ├─ 前驱是head且tryAcquire成功 → 获取到锁
                │
                ├─ shouldParkAfterFailedAcquire → 判断是否需要阻塞
                │       │
                │       ├─ 前驱waitStatus=SIGNAL → parkAndCheckInterrupt() 阻塞
                │       │
                │       └─ 否则 → 修改前驱状态，继续自旋
                │
                └─ 被唤醒后重试获取锁
```

### 2.2 tryAcquire — 子类实现获取逻辑

以 ReentrantLock 的公平锁为例：

```java
// FairSync.tryAcquire
protected final boolean tryAcquire(int acquires) {
    final Thread current = Thread.currentThread();
    int c = getState();
    if (c == 0) {
        // 公平锁：先检查队列中是否有等待线程
        if (!hasQueuedPredecessors() &&
            compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
    }
    else if (current == getExclusiveOwnerThread()) {
        // 可重入：state+1
        int nextc = c + acquires;
        if (nextc < 0)
            throw new Error("Maximum lock count exceeded");
        setState(nextc);
        return true;
    }
    return false;
}
```

### 2.3 addWaiter — 入队操作

```java
private Node addWaiter(Node mode) {
    Node node = new Node(Thread.currentThread(), mode);
    // 快速尝试在尾部添加
    Node pred = tail;
    if (pred != null) {
        node.prev = pred;
        if (compareAndSetTail(pred, node)) {  // CAS设置尾节点
            pred.next = node;
            return node;
        }
    }
    enq(node);  // CAS失败，自旋入队
    return node;
}

private Node enq(final Node node) {
    for (;;) {  // 自旋
        Node t = tail;
        if (t == null) {  // 队列为空，初始化
            if (compareAndSetHead(new Node()))
                tail = head;
        } else {
            node.prev = t;
            if (compareAndSetTail(t, node)) {
                t.next = node;
                return t;
            }
        }
    }
}
```

**入队过程示意**：

```
初始状态（空队列）：
  head = tail = null

Step 1: 初始化哨兵节点
  head → [sentinel] ← tail

Step 2: Thread-A 入队
  head → [sentinel] ↔ [Thread-A] ← tail

Step 3: Thread-B 入队
  head → [sentinel] ↔ [Thread-A] ↔ [Thread-B] ← tail
```

### 2.4 acquireQueued — 自旋获取与阻塞

```java
final boolean acquireQueued(final Node node, int arg) {
    boolean failed = true;
    try {
        boolean interrupted = false;
        for (;;) {  // 自旋
            final Node p = node.predecessor();  // 获取前驱
            if (p == head && tryAcquire(arg)) { // 前驱是head且获取成功
                setHead(node);    // 设置自己为head
                p.next = null;    // help GC
                failed = false;
                return interrupted;
            }
            // 判断是否需要park
            if (shouldParkAfterFailedAcquire(p, node) &&
                parkAndCheckInterrupt())
                interrupted = true;
        }
    } finally {
        if (failed)
            cancelAcquire(node);
    }
}
```

### 2.5 shouldParkAfterFailedAcquire — 判断是否阻塞

```java
private static boolean shouldParkAfterFailedAcquire(Node pred, Node node) {
    int ws = pred.waitStatus;
    if (ws == Node.SIGNAL)
        // 前驱已经设置了SIGNAL，可以安全park
        return true;
    if (ws > 0) {
        // 前驱已取消，跳过所有取消的节点
        do {
            node.prev = pred = pred.prev;
        } while (pred.waitStatus > 0);
        pred.next = node;
    } else {
        // CAS设置前驱状态为SIGNAL
        compareAndSetWaitStatus(pred, ws, Node.SIGNAL);
    }
    return false;  // 需要重试
}
```

### 2.6 release(int arg) — 释放独占锁

```java
public final boolean release(int arg) {
    if (tryRelease(arg)) {     // ① 尝试释放锁
        Node h = head;
        if (h != null && h.waitStatus != 0)
            unparkSuccessor(h); // ② 唤醒后继节点
        return true;
    }
    return false;
}
```

```java
// ReentrantLock.Sync.tryRelease
protected final boolean tryRelease(int releases) {
    int c = getState() - releases;
    if (Thread.currentThread() != getExclusiveOwnerThread())
        throw new IllegalMonitorStateException();
    boolean free = false;
    if (c == 0) {  // 完全释放
        free = true;
        setExclusiveOwnerThread(null);
    }
    setState(c);  // 不需要CAS，只有持有锁的线程才能释放
    return free;
}
```

```java
private void unparkSuccessor(Node node) {
    int ws = node.waitStatus;
    if (ws < 0)
        compareAndSetWaitStatus(node, ws, 0);  // 清除状态
    Node s = node.next;
    if (s == null || s.waitStatus > 0) {
        // 后继为空或已取消，从尾部向前找
        s = null;
        for (Node t = tail; t != null && t != node; t = t.prev)
            if (t.waitStatus <= 0)
                s = t;
    }
    if (s != null)
        LockSupport.unpark(s.thread);  // 唤醒线程
}
```

**为什么从尾部向前查找？**

因为 `enq()` 中 `node.prev = t` 先于 `t.next = node`，prev 链是完整的而 next 链可能有断点。

## 三、共享模式源码全流程

### 3.1 acquireShared(int arg) — 获取共享锁

```java
public final void acquireShared(int arg) {
    if (tryAcquireShared(arg) < 0)  // 返回负数表示获取失败
        doAcquireShared(arg);
}
```

```java
private void doAcquireShared(int arg) {
    final Node node = addWaiter(Node.SHARED);
    boolean failed = true;
    try {
        boolean interrupted = false;
        for (;;) {
            final Node p = node.predecessor();
            if (p == head) {
                int r = tryAcquireShared(arg);
                if (r >= 0) {
                    // 获取成功，传播唤醒
                    setHeadAndPropagate(node, r);
                    p.next = null;
                    if (interrupted)
                        selfInterrupt();
                    failed = false;
                    return;
                }
            }
            if (shouldParkAfterFailedAcquire(p, node) &&
                parkAndCheckInterrupt())
                interrupted = true;
        }
    } finally {
        if (failed)
            cancelAcquire(node);
    }
}
```

### 3.2 setHeadAndPropagate — 传播唤醒

共享模式的关键特性：一个线程获取锁后，如果还有剩余资源，会**传播唤醒**后续的共享节点。

```java
private void setHeadAndPropagate(Node node, int propagate) {
    Node h = head;
    setHead(node);
    // 传播条件：有剩余资源 或 头节点状态需要传播
    if (propagate > 0 || h == null || h.waitStatus < 0 ||
        (h = head) == null || h.waitStatus < 0) {
        Node s = node.next;
        if (s == null || s.isShared())
            doReleaseShared();  // 唤醒后继共享节点
    }
}
```

### 3.3 Semaphore 中的共享实现

```java
// Semaphore.NonfairSync
protected int tryAcquireShared(int acquires) {
    return nonfairTryAcquireShared(acquires);
}

final int nonfairTryAcquireShared(int acquires) {
    for (;;) {
        int available = getState();
        int remaining = available - acquires;
        if (remaining < 0 ||
            compareAndSetState(available, remaining))
            return remaining;  // 负数=获取失败，非负=获取成功+剩余许可
    }
}
```

### 3.4 CountDownLatch 中的共享实现

```java
// CountDownLatch.Sync
protected int tryAcquireShared(int acquires) {
    return (getState() == 0) ? 1 : -1;  // state=0时才能获取
}

protected boolean tryReleaseShared(int releases) {
    for (;;) {
        int c = getState();
        if (c == 0)
            return false;
        int nextc = c - 1;
        if (compareAndSetState(c, nextc))
            return nextc == 0;  // 减到0时返回true，触发唤醒
    }
}
```

## 四、Condition 条件队列

### 4.1 Condition 与 AQS 的关系

每个 ConditionObject 维护一个独立的**条件队列**（单向链表），与 AQS 的**同步队列**（双向链表）是两个独立的队列。

```
同步队列（AQS queue）：
  head → [sentinel] ↔ [Thread-A] ↔ [Thread-B] ← tail

条件队列（Condition queue）：
  firstWaiter → [Thread-C] → [Thread-D] → null
```

### 4.2 await() — 等待条件

```java
public final void await() throws InterruptedException {
    if (Thread.interrupted())
        throw new InterruptedException();
    Node node = addConditionWaiter();     // ① 加入条件队列
    int savedState = fullyRelease(node);  // ② 完全释放锁
    int interruptMode = 0;
    while (!isOnSyncQueue(node)) {        // ③ 不在同步队列就park
        LockSupport.park(this);
        if ((interruptMode = checkInterruptWhileWaiting(node)) != 0)
            break;
    }
    if (acquireQueued(node, savedState) && // ④ 重新获取锁
        interruptMode != THROW_IE)
        interruptMode = REINTERRUPT;
    if (node.nextWaiter != null)
        unlinkCancelledWaiters();          // ⑤ 清理取消节点
    if (interruptMode != 0)
        reportInterruptAfterWait(interruptMode);
}
```

### 4.3 signal() — 唤醒等待线程

```java
public final void signal() {
    if (!isHeldExclusively())
        throw new IllegalMonitorStateException();
    Node first = firstWaiter;
    if (first != null)
        doSignal(first);  // 将条件队列首节点转移到同步队列
}

private void doSignal(Node first) {
    do {
        if ((firstWaiter = first.nextWaiter) == null)
            lastWaiter = null;
        first.nextWaiter = null;
    } while (!transferForSignal(first) &&  // CAS+unpark
             (first = firstWaiter) != null);
}
```

**await/signal 流程图**：

```
初始：Thread-A 持有锁

1. Thread-A 调用 condition.await()
   → 释放锁(state=0)
   → Thread-A 移入条件队列
   → Thread-B 获取到锁

2. Thread-B 调用 condition.signal()
   → Thread-A 从条件队列移到同步队列
   → Thread-B 继续执行

3. Thread-B 释放锁
   → 唤醒同步队列中的 Thread-A
   → Thread-A 重新获取锁并继续执行
```

## 五、取消与中断处理

### 5.1 cancelAcquire — 取消节点

```java
private void cancelAcquire(Node node) {
    if (node == null) return;
    node.thread = null;

    // 跳过已取消的前驱
    Node pred = node.prev;
    while (pred.waitStatus > 0) {
        node.prev = pred = pred.prev;
    }

    Node predNext = pred.next;
    node.waitStatus = Node.CANCELLED;  // 设置取消状态

    // 如果是尾节点，直接移除
    if (node == tail && compareAndSetTail(node, pred)) {
        compareAndSetNext(pred, predNext, null);
    } else {
        // 如果前驱是head或不是SIGNAL，需要唤醒后继
        int ws;
        if (pred != head &&
            ((ws = pred.waitStatus) == Node.SIGNAL ||
             (ws <= 0 && compareAndSetWaitStatus(pred, ws, Node.SIGNAL))) &&
            pred.thread != null) {
            Node next = node.next;
            if (next != null && next.waitStatus <= 0)
                compareAndSetNext(pred, predNext, next);
        } else {
            unparkSuccessor(node);  // 唤醒后继节点
        }
    }
    node.next = node;  // help GC
}
```

### 5.2 中断的处理策略

AQS 对中断有两种处理方式：

| 方法 | 中断处理 | 使用场景 |
|------|---------|---------|
| `acquire()` | 忽略中断，获取锁后恢复中断标志 | ReentrantLock.lock() |
| `acquireInterruptibly()` | 立即响应中断，抛出 InterruptedException | ReentrantLock.lockInterruptibly() |

## 六、公平与非公平锁对比

### 6.1 FairSync vs NonfairSync

```java
// 公平锁
static final class FairSync extends Sync {
    protected final boolean tryAcquire(int acquires) {
        if (c == 0) {
            // 关键区别：检查队列中是否有等待线程
            if (!hasQueuedPredecessors() && compareAndSetState(0, acquires)) {
                setExclusiveOwnerThread(current);
                return true;
            }
        }
        ...
    }
}

// 非公平锁
static final class NonfairSync extends Sync {
    protected final boolean tryAcquire(int acquires) {
        // 直接尝试CAS抢锁，不检查队列
        if (compareAndSetState(0, acquires)) {
            setExclusiveOwnerThread(current);
            return true;
        }
        ...
    }
}
```

### 6.2 hasQueuedPredecessors

```java
public final boolean hasQueuedPredecessors() {
    Node t = tail;
    Node h = head;
    Node s;
    return h != t &&
        ((s = h.next) == null || s.thread != Thread.currentThread());
}
```

**公平与非公平对比**：

| 特性 | 公平锁 | 非公平锁 |
|------|--------|---------|
| 获取顺序 | 严格FIFO | 可能插队 |
| 吞吐量 | 较低 | 较高（约10倍） |
| 饥饿问题 | 不会饥饿 | 可能饥饿 |
| 线程切换 | 频繁 | 较少 |
| 默认选择 | - | ✅ ReentrantLock默认 |

## 七、AQS 应用全景

```
                    ┌─────────────────────────────────────────────┐
                    │               AQS (state + CLH queue)        │
                    └──────────────────┬──────────────────────────┘
                                       │
           ┌───────────┬───────────┬───┴────┬────────────┬──────────────┐
           │           │           │        │            │              │
     ReentrantLock  CountDownLatch  Semaphore  ReentrantReadWriteLock  CyclicBarrier
     (独占)          (共享)          (共享)     (独占+共享)              (不直接用AQS)
           │           │           │        │
     state=重入数   state=计数    state=许可  state=高16读+低16写
```

### 7.1 各工具类使用 AQS 的方式

| 工具类 | 模式 | state 语义 | 自定义方法 |
|--------|------|-----------|-----------|
| ReentrantLock | 独占 | 重入次数 | tryAcquire/tryRelease |
| CountDownLatch | 共享 | 剩余计数 | tryAcquireShared/tryReleaseShared |
| Semaphore | 共享 | 可用许可 | tryAcquireShared/tryReleaseShared |
| ReentrantReadWriteLock | 独占+共享 | 读写锁计数 | 全部4个方法 |

### 7.2 基于 AQS 自定义同步器

```java
// 不可重入互斥锁
class Mutex implements Lock {
    private static class Sync extends AbstractQueuedSynchronizer {
        @Override
        protected boolean tryAcquire(int arg) {
            return compareAndSetState(0, 1);
        }

        @Override
        protected boolean tryRelease(int arg) {
            setState(0);
            return true;
        }

        @Override
        protected boolean isHeldExclusively() {
            return getState() == 1;
        }
    }

    private final Sync sync = new Sync();

    public void lock()     { sync.acquire(1); }
    public void unlock()   { sync.release(1); }
    public boolean tryLock() { return sync.tryAcquire(1); }
    // ... 其他方法
}
```

## 八、常见面试题

### Q1: AQS 为什么用 CLH 队列而不是普通队列？

CLH 队列基于**前驱节点的状态**来判断是否应该阻塞，只需要检查前驱节点的 `waitStatus`，避免了对整个队列的遍历。而且 CLH 队列天然支持**取消操作**和**公平性**保证。

### Q2: AQS 的 state 为什么用 volatile + CAS 而不是直接用锁？

- volatile 保证可见性
- CAS 保证原子性
- 无锁操作比加锁性能更高
- state 的修改场景简单（加/减），适合 CAS

### Q3: 独占模式和共享模式的本质区别？

- 独占模式：同一时刻只有一个线程能获取（如 ReentrantLock）
- 共享模式：同一时刻可以有多个线程获取（如 Semaphore、CountDownLatch）
- 核心区别：共享模式获取成功后会**传播唤醒**后续共享节点

### Q4: 为什么 unparkSuccessor 要从尾部向前查找？

在 `enq()` 入队操作中：
1. `node.prev = t` — 先设置 prev
2. `compareAndSetTail(t, node)` — CAS 设置 tail
3. `t.next = node` — 最后设置 next

如果步骤2完成但步骤3还未执行，next 链是断的，但 prev 链始终完整。所以从尾部向前遍历是安全的。

### Q5: 公平锁一定比非公平锁慢吗？

是的，公平锁吞吐量通常只有非公平锁的 1/10 左右，原因：
- 公平锁需要检查 `hasQueuedPredecessors()`，多一次队列遍历
- 公平锁严格排队，导致线程切换频繁
- 非公平锁允许刚释放锁的线程立即重新获取，减少了上下文切换

## 九、总结

| 概念 | 关键点 |
|------|--------|
| 设计模式 | 模板方法模式，子类实现 tryAcquire/tryRelease |
| 核心状态 | volatile int state + CAS |
| 等待队列 | CLH 变体双向链表，FIFO 公平 |
| 独占模式 | 单线程获取，如 ReentrantLock |
| 共享模式 | 多线程获取 + 传播唤醒，如 Semaphore |
| Condition | 条件队列（单向链表）与同步队列的转移 |
| 公平性 | 公平锁检查队列，非公平锁直接 CAS |

> **下期预告**：《Java 原子类与 CAS 深度解析》—— AtomicInteger 的实现原理是什么？LongAdder 为什么比 AtomicLong 快？ABA 问题如何解决？敬请期待！
