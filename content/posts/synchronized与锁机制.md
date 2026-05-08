---
title: "synchronized 与锁机制：从对象头到锁升级"
date: 2026-04-29T18:00:00+08:00
draft: false
categories: ["java"]
tags: ["Java", "面试", "synchronized", "锁", "并发", "JVM"]
---

# synchronized 与锁机制：从对象头到锁升级

`synchronized` 是 Java 中最基础的同步机制，也是面试的高频考点。很多候选人知道「synchronized 是重量级锁」「JDK 6 之后有锁升级」，但真正能说清楚对象头结构、锁升级流程、与 ReentrantLock 区别的却不多。

本文将从 JVM 底层出发，深入剖析 synchronized 的实现原理。

## 一、synchronized 的三种使用方式

### 1.1 修饰实例方法

```java
public class Counter {
    private int count = 0;
    
    // 锁的是 this 对象
    public synchronized void increment() {
        count++;
    }
}

// 等价于
public void increment() {
    synchronized(this) {
        count++;
    }
}
```

### 1.2 修饰静态方法

```java
public class Counter {
    private static int count = 0;
    
    // 锁的是 Class 对象（Counter.class）
    public static synchronized void increment() {
        count++;
    }
}

// 等价于
public static void increment() {
    synchronized(Counter.class) {
        count++;
    }
}
```

### 1.3 修饰代码块

```java
public class Counter {
    private int count = 0;
    private final Object lock = new Object();
    
    public void increment() {
        // 可以指定任意对象作为锁
        synchronized(lock) {
            count++;
        }
    }
}
```

### 1.4 三种方式的对比

| 方式 | 锁对象 | 作用范围 |
|------|--------|----------|
| 实例方法 | this | 当前实例的所有 synchronized 方法 |
| 静态方法 | Class 对象 | 该类的所有静态 synchronized 方法 |
| 代码块 | 指定对象 | 仅该代码块 |

**重要**：不同锁对象之间互不影响！

```java
public class Demo {
    public synchronized void methodA() {
        // 锁 this
    }
    
    public static synchronized void methodB() {
        // 锁 Demo.class
    }
    
    public void methodC() {
        synchronized(new Object()) {
            // 锁一个新对象（每次都不同，完全没意义！）
        }
    }
}

// methodA、methodB、methodC 可以同时被不同线程执行
// 因为它们锁的是不同的对象
```

## 二、对象头与 Mark Word

### 2.1 Java 对象的内存布局

在 HotSpot JVM 中，一个 Java 对象在内存中的布局分为三部分：

```
┌─────────────────────────────────────────────┐
│              Object Header (12 字节)         │
│  ┌───────────────────┬───────────────────┐  │
│  │   Mark Word (8B)   │  Klass Pointer (4B) │  │
│  └───────────────────┴───────────────────┘  │
├─────────────────────────────────────────────┤
│              Instance Data                   │
│            (实例变量，按类型对齐)              │
├─────────────────────────────────────────────┤
│              Padding                         │
│         (填充到 8 字节倍数)                   │
└─────────────────────────────────────────────┘
```

- **Mark Word**：8 字节，存储对象的运行时数据（锁状态、哈希值、GC 年龄等）
- **Klass Pointer**：4 字节（默认开启指针压缩），指向类元数据
- **Instance Data**：实例变量
- **Padding**：对齐填充，保证对象大小是 8 的倍数

### 2.2 Mark Word 的结构

Mark Word 是 synchronized 锁机制的核心。在不同的锁状态下，Mark Word 存储不同的内容：

**64 位 JVM Mark Word 结构**：

```
| 锁状态   | 锁标志位 (2bit) | Mark Word 存储内容                          |
|---------|----------------|--------------------------------------------|
| 无锁     | 01             | 对象哈希码(31) + 分代年龄(4) + 偏向锁标志(1) + 锁标志(2) |
| 偏向锁   | 01             | 线程ID(54) + Epoch(2) + 分代年龄(4) + 偏向标志(1) + 锁标志(2) |
| 轻量级锁 | 00             | 指向栈中 Lock Record 的指针 (62) + 锁标志(2)           |
| 重量级锁 | 10             | 指向堆中 ObjectMonitor 的指针 (62) + 锁标志(2)         |
| GC 标记 | 11             | 空，用于 GC                                  |
```

**关键点**：

1. **锁标志位**：最后 2 位，区分锁状态
2. **偏向锁标志**：倒数第 3 位，与锁标志位组合判断偏向锁
3. **无锁和偏向锁的标志位相同**（都是 01），通过偏向锁标志位区分

### 2.3 使用 JOL 查看对象头

```java
// 添加依赖：org.openjdk.jol:jol-core:0.16
import org.openjdk.jol.vm.VM;

public class ObjectHeaderDemo {
    public static void main(String[] args) {
        Object obj = new Object();
        System.out.println(VM.current().detailsOf(obj));
    }
}

// 输出（无锁状态）：
// java.lang.Object object internals:
//  OFFSET  SIZE   TYPE DESCRIPTION                               VALUE
//       0     4        (object header)                           01 00 00 00
//       4     4        (object header)                           00 00 00 00
//       8     4        (object header)                           e5 01 00 f8
//      12     4        (loss due to the next object alignment)
// Instance size: 16 bytes
```

## 三、锁升级流程

JDK 6 之后，synchronized 引入了「锁升级」机制，从低到高依次为：

```
无锁 → 偏向锁 → 轻量级锁 → 重量级锁
```

锁升级是单向的，只能升级不能降级。

### 3.1 偏向锁（Biased Lock）

**核心思想**：大多数情况下，锁不仅不存在多线程竞争，而且总是由同一个线程多次获得。偏向锁会在对象头中记录获取锁的线程 ID，后续该线程进入同步块时，无需任何同步操作。

**获取偏向锁流程**：

```
1. 检查 Mark Word 是否为可偏向状态（锁标志 01，偏向标志 1）
2. 如果是可偏向状态：
   - 检查线程 ID 是否等于当前线程
   - 相等：直接执行同步块（无需 CAS）
   - 不相等：尝试 CAS 替换线程 ID
3. CAS 成功：获取偏向锁
4. CAS 失败：说明有竞争，撤销偏向锁，升级为轻量级锁
```

**撤销偏向锁**：

偏向锁撤销需要等待全局安全点（SafePoint），步骤如下：

1. 暂停拥有偏向锁的线程
2. 检查持有偏向锁的线程是否存活
3. 如果线程不活跃或已退出同步块，将对象头设置为无锁状态
4. 如果线程还在同步块中，升级为轻量级锁

```java
// 关闭偏向锁延迟（默认 4 秒）
-XX:BiasedLockingStartupDelay=0

// 禁用偏向锁
-XX:-UseBiasedLocking
```

### 3.2 轻量级锁（Lightweight Lock）

**核心思想**：多个线程交替执行同步块，没有真正的竞争。使用 CAS 操作来获取锁，避免重量级锁的开销。

**获取轻量级锁流程**：

```
1. 在当前线程栈帧中创建 Lock Record（锁记录）
2. 将 Mark Word 复制到 Lock Record（称为 Displaced Mark Word）
3. 尝试 CAS 将 Mark Word 替换为指向 Lock Record 的指针
4. CAS 成功：获取轻量级锁
5. CAS 失败：说明有竞争
   - 检查 Mark Word 是否指向当前线程的 Lock Record
   - 是：重入锁，设置 Lock Record 为 null（重入计数）
   - 否：说明存在竞争，升级为重量级锁
```

**释放轻量级锁**：

```
1. 取出 Displaced Mark Word
2. 尝试 CAS 将 Mark Word 恢复为 Displaced Mark Word
3. 成功：释放成功
4. 失败：说明锁已升级为重量级锁，唤醒等待线程
```

### 3.3 重量级锁（Heavyweight Lock）

**核心思想**：存在真正的竞争，依赖操作系统的互斥量（Mutex Lock）实现。涉及用户态和内核态的切换，开销较大。

**ObjectMonitor 结构**：

```cpp
// 简化的 ObjectMonitor 结构
class ObjectMonitor {
    void*       _header;        // 保存原始 Mark Word
    markWord    _object;        // 对象指针
    void*       _owner;         // 持有锁的线程
    ObjectWaiter* _cxq;         // 等待队列（Contention Queue）
    ObjectWaiter* _EntryList;   // 竞争队列
    Thread*     _succ;          // 假设的继任者
    int         _WaitSetLock;   // 等待集锁
    ObjectWaiter* _WaitSet;     // wait() 线程集合
    int         _count;         // 计数器
    int         _recursions;    // 重入次数
};
```

**获取重量级锁流程**：

```
1. 尝试 CAS 将 ObjectMonitor 的 owner 设置为当前线程
2. 成功：获取锁
3. 失败：
   - 如果 owner 是当前线程：重入计数 +1
   - 否则：进入 cxq 等待队列，线程阻塞（park）
```

**重量级锁的开销**：

1. 用户态 → 内核态切换
2. 线程阻塞/唤醒（涉及线程调度）
3. 缓存一致性开销（多个 CPU 核心竞争锁）

### 3.4 锁升级流程图

```
        线程 A 首次访问同步块
                │
                ▼
        ┌──────────────┐
        │   无锁状态    │  Mark Word: hashcode + age + 0 + 01
        └──────────────┘
                │
                ▼
        ┌──────────────┐
        │   偏向锁      │  Mark Word: threadID + epoch + age + 1 + 01
        │  (线程A获取)   │  无 CAS，直接执行
        └──────────────┘
                │
                │ 线程 B 尝试获取
                ▼
        ┌──────────────┐
        │  轻量级锁     │  Mark Word: 指向 Lock Record 的指针 + 00
        │  (CAS竞争)    │  线程自旋尝试获取
        └──────────────┘
                │
                │ 自旋失败/竞争激烈
                ▼
        ┌──────────────┐
        │  重量级锁     │  Mark Word: 指向 ObjectMonitor 的指针 + 10
        │  (OS Mutex)   │  线程阻塞等待
        └──────────────┘
```

### 3.5 自适应自旋

在轻量级锁升级为重量级锁之前，JVM 会尝试自旋获取锁，避免线程阻塞的开销。

```java
// JDK 6+ 自适应自旋
// 自旋次数根据前一次在同一锁上的自旋成功情况动态调整
// 如果上次自旋成功获取锁，本次允许更多自旋
// 如果总是自旋失败，则减少自旋次数甚至取消自旋
```

```java
// 相关参数
-XX:+UseSpinning          // 启用自旋（JDK 6 默认开启）
-XX:PreBlockSpin=10       // 自旋次数（JDK 6 默认 10）
// JDK 7+ 改为自适应自旋，不再使用固定次数
```

## 四、synchronized 的字节码实现

### 4.1 代码块的字节码

```java
public void method() {
    synchronized(this) {
        // do something
    }
}
```

编译后的字节码：

```
public void method();
    Code:
       0: aload_0               // 加载 this
       1: dup                   // 复制引用
       2: astore_1              // 存储到局部变量表 slot 1
       3: monitorenter          // 进入监视器（获取锁）
       4: aload_1               // 加载锁对象
       5: monitorexit            // 退出监视器（释放锁）
       6: goto 14               // 跳到方法结束
       7: astore_2              // 异常处理：存储异常
       8: aload_1               // 加载锁对象
       9: monitorexit            // 退出监视器（异常时也要释放）
      10: aload_2               // 加载异常
      11: athrow                // 抛出异常
      12: goto 14               // 正常退出
      14: return
    Exception table:
       from    to  target type
           4     6     7   any   // 任何异常都跳到 7
```

**关键点**：

1. `monitorenter`：获取对象监视器，计数器 +1
2. `monitorexit`：释放对象监视器，计数器 -1
3. **两个 monitorexit**：一个正常退出，一个异常退出（保证锁一定释放）

### 4.2 方法的字节码

```java
public synchronized void method();
    Code:
       0: return
    
    // 没有 monitorenter/monitorexit
    // 而是通过方法常量池的 ACC_SYNCHRONIZED 标志
```

方法级的 synchronized 通过 `ACC_SYNCHRONIZED` 标志实现，JVM 检测到该标志后自动获取/释放锁。

## 五、synchronized 与 ReentrantLock 对比

### 5.1 核心区别

| 特性 | synchronized | ReentrantLock |
|------|-------------|----------------|
| 实现层面 | JVM 关键字，底层依赖对象头 | JDK API，依赖 AQS |
| 锁获取/释放 | 自动（代码块结束自动释放） | 手动（lock/unlock，需在 finally 中释放） |
| 是否可中断 | 不可中断 | lockInterruptibly() 可中断 |
| 是否可超时 | 不可超时 | tryLock(timeout) 支持超时 |
| 是否公平 | 非公平 | 可选公平/非公平 |
| 条件变量 | 单一条件（wait/notify） | 多条件（newCondition） |
| 锁状态 | 无法获取状态 | 可获取锁状态（isLocked、getQueueLength） |
| 性能 | JDK 6+ 优化后差距不大 | 高竞争下略优 |

### 5.2 ReentrantLock 使用示例

```java
import java.util.concurrent.locks.ReentrantLock;

public class Counter {
    private final ReentrantLock lock = new ReentrantLock(true); // 公平锁
    private int count = 0;
    
    public void increment() {
        lock.lock();
        try {
            count++;
        } finally {
            lock.unlock();  // 必须在 finally 中释放
        }
    }
    
    // 可中断获取锁
    public void incrementInterruptibly() throws InterruptedException {
        lock.lockInterruptibly();
        try {
            count++;
        } finally {
            lock.unlock();
        }
    }
    
    // 超时获取锁
    public boolean tryIncrement() {
        if (lock.tryLock(1, TimeUnit.SECONDS)) {
            try {
                count++;
                return true;
            } finally {
                lock.unlock();
            }
        }
        return false;
    }
    
    // 多条件变量
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();
    
    public void put(Object item) throws InterruptedException {
        lock.lock();
        try {
            while (isFull()) {
                notFull.await();  // 等待非满条件
            }
            // 放入元素
            notEmpty.signal();  // 通知非空条件
        } finally {
            lock.unlock();
        }
    }
}
```

### 5.3 选择建议

**使用 synchronized 的场景**：

- 简单的同步需求
- 不需要高级特性（超时、中断、公平锁）
- 代码简洁性优先

**使用 ReentrantLock 的场景**：

- 需要超时获取锁（避免死锁）
- 需要响应中断
- 需要公平锁
- 需要多个条件变量
- 需要精细控制锁状态

## 六、常见面试问题

### Q1：synchronized 是可重入锁吗？如何实现？

**是的**，synchronized 是可重入锁。

```java
public class Demo {
    public synchronized void methodA() {
        methodB();  // 可以再次获取同一把锁
    }
    
    public synchronized void methodB() {
        // 正常执行
    }
}
```

**实现原理**：

- 偏向锁：检查 Mark Word 中的线程 ID 是否为当前线程
- 轻量级锁：检查 Lock Record 栈帧中是否有当前线程的记录
- 重量级锁：ObjectMonitor 的 `_recursions` 字段记录重入次数

### Q2：synchronized 锁对象 null 会怎样？

```java
Object lock = null;
synchronized(lock) {  // NullPointerException
    // ...
}
```

**会抛出 NullPointerException**，因为锁必须是对象，null 没有对象头。

### Q3：为什么偏向锁有延迟？

JVM 启动时会有很多初始化操作，这些操作涉及同步。如果一开始就启用偏向锁，会有大量偏向锁撤销操作，影响启动速度。

```java
// 默认延迟 4 秒
-XX:BiasedLockingStartupDelay=4000

// 可以关闭延迟（用于测试）
-XX:BiasedLockingStartupDelay=0
```

### Q4：锁升级后还能降级吗？

**不能**，锁升级是单向的。原因：

1. 降级需要全局安全点，开销大
2. 一旦升级为重量级锁，说明竞争激烈，降级意义不大
3. 降级时机难以确定

### Q5：synchronized 和 Lock 哪个性能更好？

**JDK 6 之后差距很小**。

早期 synchronized 没有锁优化，性能远低于 ReentrantLock。但 JDK 6 引入偏向锁、轻量级锁、自适应自旋后，两者性能差距很小。

**实际选择依据**：功能需求而非性能（除非极端高竞争场景）。

### Q6：对象哈希码对锁的影响？

当一个对象计算过哈希码后，Mark Word 会存储哈希值，无法再进入偏向锁状态，只能从轻量级锁开始。

```java
Object obj = new Object();
obj.hashCode();  // 计算哈希码，Mark Word 存储哈希值
synchronized(obj) {
    // 直接从轻量级锁开始，跳过偏向锁
}
```

### Q7：wait/notify 为什么必须在 synchronized 中调用？

```java
// 错误示例
Object obj = new Object();
obj.wait();  // IllegalMonitorStateException
```

**原因**：

1. `wait()` 会释放锁，如果没有持有锁，无法释放
2. `wait()` 需要将线程加入 ObjectMonitor 的 WaitSet，需要访问 Monitor
3. `notify()` 需要从 WaitSet 中唤醒线程，同样需要访问 Monitor

```java
// 正确用法
synchronized(obj) {
    while (condition) {
        obj.wait();  // 释放锁，等待被唤醒
    }
    // 被唤醒后重新获取锁，继续执行
}

synchronized(obj) {
    obj.notify();  // 或 notifyAll()
}
```

### Q8：如何避免死锁？

```java
// 死锁示例
public void transfer(Account from, Account to, int amount) {
    synchronized(from) {
        synchronized(to) {
            from.debit(amount);
            to.credit(amount);
        }
    }
}

// 线程 A: transfer(a, b, 100)
// 线程 B: transfer(b, a, 50)
// A 持有 a 锁，等待 b 锁
// B 持有 b 锁，等待 a 锁
// 死锁！
```

**解决方案**：

1. **固定加锁顺序**：

```java
public void transfer(Account from, Account to, int amount) {
    Account first = from.getId() < to.getId() ? from : to;
    Account second = from.getId() < to.getId() ? to : from;
    
    synchronized(first) {
        synchronized(second) {
            from.debit(amount);
            to.credit(amount);
        }
    }
}
```

2. **使用 tryLock 超时**：

```java
if (from.lock.tryLock(1, TimeUnit.SECONDS)) {
    try {
        if (to.lock.tryLock(1, TimeUnit.SECONDS)) {
            try {
                // 转账操作
            } finally {
                to.lock.unlock();
            }
        }
    } finally {
        from.lock.unlock();
    }
}
```

3. **使用 Lock 的 lockInterruptibly**：

```java
try {
    from.lock.lockInterruptibly();
    to.lock.lockInterruptibly();
    // 转账操作
} catch (InterruptedException e) {
    // 被中断，放弃获取锁
} finally {
    from.lock.unlock();
    to.lock.unlock();
}
```

## 七、最佳实践

### 7.1 锁对象选择

```java
// ❌ 锁 String 常量（可能被其他代码引用）
synchronized("lock") { }

// ❌ 锁 Integer 缓存（-128~127 会被缓存）
Integer lock = 127;
synchronized(lock) { }

// ❌ 锁 Class 对象（影响范围太大）
synchronized(String.class) { }

// ✅ 锁私有 final 对象
private final Object lock = new Object();
synchronized(lock) { }

// ✅ 锁 this（实例方法，明确语义）
synchronized(this) { }
```

### 7.2 同步块范围

```java
// ❌ 同步范围过大
public synchronized void process() {
    validate();      // 无需同步
    transform();     // 无需同步
    synchronized(this) {
        save();      // 需要同步
    }
    notify();        // 无需同步
}

// ✅ 只同步必要部分
public void process() {
    validate();
    transform();
    synchronized(this) {
        save();
    }
    notify();
}
```

### 7.3 避免在同步块中调用外部方法

```java
// ❌ 外部方法可能导致死锁或性能问题
public synchronized void process() {
    externalService.call();  // 外部调用，可能很慢或阻塞
}

// ✅ 将外部调用移出同步块
public void process() {
    Object data;
    synchronized(this) {
        data = getData();
    }
    externalService.call(data);  // 外部调用在同步块外
}
```

## 八、总结

本文深入剖析了 synchronized 的实现原理：

1. **三种使用方式**：实例方法、静态方法、代码块，锁对象各不相同
2. **Mark Word 结构**：存储锁状态、线程 ID、哈希值等信息
3. **锁升级流程**：无锁 → 偏向锁 → 轻量级锁 → 重量级锁，单向不可逆
4. **字节码实现**：`monitorenter`/`monitorexit` 或 `ACC_SYNCHRONIZED`
5. **与 ReentrantLock 对比**：功能、性能、使用场景
6. **常见陷阱**：死锁、锁对象选择、同步范围

掌握 synchronized 的关键在于理解其底层实现，而非死记概念。在实际开发中，根据具体需求选择合适的同步机制，避免过度同步或同步不当导致的问题。