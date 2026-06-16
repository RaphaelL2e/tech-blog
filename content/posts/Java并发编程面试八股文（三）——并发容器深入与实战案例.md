---
title: "Java并发编程面试八股文（三）——并发容器深入与实战案例"
date: 2026-06-16T09:00:00+08:00
draft: false
categories: ["java"]
tags: ["面试", "八股文", "Java", "并发", "ConcurrentHashMap", "BlockingQueue", "CopyOnWriteArrayList", "并发容器"]
---

# Java并发编程面试八股文（三）——并发容器深入与实战案例

> 面试高频问题：ConcurrentHashMap在JDK7和JDK8中实现有什么不同？为什么ConcurrentHashMap不允许null键值？BlockingQueue有哪些实现？如何在生产环境选择合适的并发容器？本文带你深入并发容器源码与实战。

---

## 一、ConcurrentHashMap深入

### 1.1 JDK7分段锁机制

**Q: ConcurrentHashMap在JDK7中是如何保证线程安全的？**

A: JDK7使用**分段锁(Segment)**机制，将整个Map分成多个Segment，每个Segment独立加锁：

```java
// JDK7 ConcurrentHashMap结构
// Segment数组，每个Segment继承ReentrantLock
final Segment<K,V>[] segments;
// 默认16个Segment，即支持16个线程并发写入
// 并发级别：concurrencyLevel = 16
```

**核心设计：**
- 每个Segment持有一个HashEntry数组
- put操作：先hash定位Segment，再对该Segment加锁
- get操作：不需要加锁（volatile保证可见性）
- 最大并发度 = Segment数量（默认16）

```java
// JDK7 put简化逻辑
public V put(K key, V value) {
    int hash = hash(key);
    int segIndex = hash >>> segmentShift & segmentMask;
    Segment<K,V> seg = segments[segIndex];
    return seg.put(key, hash, value);
}
```

### 1.2 JDK8 CAS + synchronized 优化

**Q: JDK8对ConcurrentHashMap做了哪些改进？**

A: JDK8抛弃了分段锁，采用**CAS + synchronized + 红黑树**实现：

```java
// JDK8 ConcurrentHashMap核心结构
transient volatile Node<K,V>[] table;  // 与HashMap一样的Node数组
private transient volatile int sizeCtl; // 控制标识符（初始化/扩容）

// put方法核心流程（简化）
final V putVal(K key, V value) {
    for (Node<K,V>[] tab = table; ; ) {
        Node<K,V> f;
        // 1. 数组为空：CAS初始化
        if (tab == null) {
            // CAS设置sizeCtl，只有一个线程能成功初始化
            casTabAt(...);
            continue;
        }
        // 2. 槽位为空：CAS插入
        else if ((f = tabAt(tab, i)) == null) {
            if (casTabAt(tab, i, null, new Node<>(hash, key, value)))
                break;
        }
        // 3. 正在扩容：帮助扩容
        else if (fh == MOVED) {
            tab = helpTransfer(tab, f);
        }
        // 4. 槽位有数据：synchronized锁住头节点
        else {
            synchronized (f) {
                // 链表或红黑树插入
            }
        }
    }
}
```

**JDK7 vs JDK8对比：**

| 维度 | JDK7 | JDK8 |
|------|------|------|
| 数据结构 | Segment + HashEntry | Node + 红黑树 |
| 并发机制 | 分段锁（ReentrantLock） | CAS + synchronized |
| 锁粒度 | Segment级别 | 桶级别（更细） |
| 扩容 | Segment内部扩容 | 多线程协同扩容 |
| 查找性能 | O(n) 链表 | O(log n) 树化 |

### 1.3 为什么不允许null键值？

**Q: ConcurrentHashMap为什么不允许null键和null值？**

A: 核心原因是**二义性问题** —— 在并发环境下无法区分「key不存在」和「value为null」：

```java
// HashMap中：允许null
Map<String, String> hashMap = new HashMap<>();
hashMap.put(null, "a");      // 正常
hashMap.get(null);            // 返回"a"
hashMap.get("不存在的key");   // 返回null → 无法区分

// ConcurrentHashMap中：如果允许null
ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>();
// 线程A: if (map.get("key") == null) → 无法判断是不存在还是值为null
// 线程B: 可能同时正在执行 map.put("key", null)
// → 产生歧义！
```

### 1.4 扩容机制（多线程协同）

**Q: ConcurrentHashMap如何实现多线程协同扩容？**

A: JDK8引入**transfer**机制，多个线程共同参与扩容：

```java
// 扩容核心机制
// 1. 从右向左分配迁移区间（stride步长至少16个槽）
// 2. 每个线程处理一个区间
// 3. 迁移完成后节点标记为ForwardingNode（hash=MOVED）
// 4. 读请求遇到ForwardingNode自动转发到新表

// 关键标识
static final int MOVED = -1;  // ForwardingNode的hash值
// 遇到ForwardingNode → 说明该桶已迁移 → 去新表查找
```

---

## 二、CopyOnWriteArrayList

### 2.1 写时复制机制

**Q: CopyOnWriteArrayList的实现原理是什么？**

A: **写时复制(Copy-On-Write)**：写操作时复制整个底层数组，在新数组上修改，修改完成后替换引用：

```java
// CopyOnWriteArrayList核心源码
private transient volatile Object[] array;

public boolean add(E e) {
    final ReentrantLock lock = this.lock;
    lock.lock();
    try {
        Object[] elements = getArray();
        int len = elements.length;
        // 1. 复制新数组（长度+1）
        Object[] newElements = Arrays.copyOf(elements, len + 1);
        // 2. 在新数组上写入
        newElements[len] = e;
        // 3. 原子替换引用
        setArray(newElements);
        return true;
    } finally {
        lock.unlock();
    }
}

public E get(int index) {
    // 读操作无锁，直接读取当前array引用
    return get(getArray(), index);
}
```

### 2.2 适用场景与弱点

**Q: CopyOnWriteArrayList适用于什么场景？有什么弱点？**

| 特点 | 说明 |
|------|------|
| ✅ 读多写少 | 读写分离，读无锁，适合配置类数据、监听器列表 |
| ✅ 弱一致性 | 读可能读到旧数据，适用于容忍短暂不一致的场景 |
| ✅ 迭代安全 | 迭代器是快照版本，遍历过程中不会抛ConcurrentModificationException |
| ❌ 内存开销 | 每次写都复制整个数组，数据量大时内存压力大 |
| ❌ 写性能差 | 写需要copy数组 + 加锁，不适合高并发写入 |

```java
// 典型案例：消息监听器管理
CopyOnWriteArrayList<MessageListener> listeners = new CopyOnWriteArrayList<>();
// 大部分操作：遍历（读多）
listeners.forEach(l -> l.onMessage(msg));
// 偶尔操作：注册/注销（写少）
listeners.add(newListener);
```

---

## 三、BlockingQueue阻塞队列

### 3.1 BlockingQueue体系概览

**Q: BlockingQueue有哪些实现？各自特点是什么？**

```java
// BlockingQueue核心方法
// 入队：put(阻塞) / offer(非阻塞+超时) / add(抛异常)
// 出队：take(阻塞) / poll(非阻塞+超时) / remove(抛异常)
```

| 实现类 | 底层结构 | 容量 | 锁机制 | 典型场景 |
|--------|----------|------|--------|----------|
| ArrayBlockingQueue | 数组 | 有界（必须指定） | 单锁（put/take共用） | 有界缓冲区 |
| LinkedBlockingQueue | 链表 | 有界/无界（默认Integer.MAX） | 双锁（put/take分离） | 高吞吐任务队列 |
| SynchronousQueue | 无存储 | 0 | 直接传递 | 线程间直接交付 |
| PriorityBlockingQueue | 数组（堆） | 无界 | 单锁 | 按优先级处理 |
| DelayQueue | PriorityQueue | 无界 | 单锁 | 定时任务调度 |
| LinkedTransferQueue | 链表 | 无界 | CAS+自旋 | 高性能场景 |

### 3.2 ArrayBlockingQueue vs LinkedBlockingQueue

**Q: ArrayBlockingQueue和LinkedBlockingQueue的区别？如何选择？**

```java
// ArrayBlockingQueue：单锁，公平性可选
public ArrayBlockingQueue(int capacity, boolean fair) {
    // 单锁设计：入队和出队竞争同一把锁
    lock = new ReentrantLock(fair);
    notEmpty = lock.newCondition();
    notFull = lock.newCondition();
}

// LinkedBlockingQueue：双锁，吞吐量更高
public LinkedBlockingQueue(int capacity) {
    // 双锁设计：入队和出队使用不同的锁
    takeLock = new ReentrantLock();
    putLock = new ReentrantLock();
}
```

**选择建议：**
- **ArrayBlockingQueue**：CPU缓存友好（数组连续存储），适合小容量固定场景
- **LinkedBlockingQueue**：吞吐量更高（双锁），适合高并发场景。但要注意默认容量是Integer.MAX_VALUE，可能导致OOM
- 线程池中：FixedThreadPool / SingleThreadPool 使用 LinkedBlockingQueue（无界），CachedThreadPool 使用 SynchronousQueue

### 3.3 SynchronousQueue 公平与非公平

**Q: SynchronousQueue的公平模式和非公平模式如何实现？**

```java
// SynchronousQueue没有容量，数据直接在生产者和消费者之间传递
// 公平模式：使用TransferQueue（FIFO队列）
SynchronousQueue<String> fair = new SynchronousQueue<>(true);

// 非公平模式：使用TransferStack（LIFO栈），默认
SynchronousQueue<String> unfair = new SynchronousQueue<>();

// 典型使用：CachedThreadPool
// newCachedThreadPool使用SynchronousQueue
// → 每来一个任务如果没有空闲线程就创建新线程
```

### 3.4 DelayQueue 延迟队列

**Q: DelayQueue的实现原理是什么？有哪些应用场景？**

```java
// DelayQueue：元素必须实现Delayed接口
public class DelayTask implements Delayed {
    private long executeTime; // 到期时间
    private String taskName;

    @Override
    public long getDelay(TimeUnit unit) {
        return unit.convert(executeTime - System.currentTimeMillis(),
                            TimeUnit.MILLISECONDS);
    }

    @Override
    public int compareTo(Delayed o) {
        return Long.compare(this.getDelay(TimeUnit.NANOSECONDS),
                           o.getDelay(TimeUnit.NANOSECONDS));
    }
}

// 应用场景
// 1. 定时任务调度（到期自动执行）
// 2. 缓存过期清理（TTL淘汰）
// 3. 订单超时取消（30分钟未支付）
DelayQueue<DelayTask> queue = new DelayQueue<>();
queue.put(new DelayTask("订单超时检查", 30 * 60 * 1000));
new Thread(() -> {
    while (true) {
        DelayTask task = queue.take();  // 阻塞直到有任务到期
        task.execute();
    }
}).start();
```

---

## 四、并发容器实战案例

### 4.1 场景一：多线程计数

**Q: 多线程场景下如何安全计数？**

```java
// ❌ 错误做法：普通int + synchronized
int count = 0;
synchronized void increment() { count++; } // 锁竞争严重

// ❌ 不够好：AtomicInteger
AtomicInteger count = new AtomicInteger(0);
count.incrementAndGet(); // 高并发下CAS自旋严重

// ✅ 最佳方案：LongAdder（JDK8+）
LongAdder adder = new LongAdder();
adder.increment();          // 热点分散，极高吞吐
long total = adder.sum();   // 最终汇总
// 原理：内部维护多个Cell，每个Cell独立累加，减少CAS竞争
```

### 4.2 场景二：缓存设计

**Q: 如何用ConcurrentHashMap实现线程安全的本地缓存？**

```java
public class ThreadSafeCache<K, V> {
    private final ConcurrentHashMap<K, V> cache = new ConcurrentHashMap<>();

    // 方案一：computeIfAbsent（原子操作）
    public V getOrCompute(K key, Function<K, V> loader) {
        return cache.computeIfAbsent(key, loader);
    }

    // 方案二：带过期时间的缓存
    private final ConcurrentHashMap<K, CacheEntry<V>> cache =
        new ConcurrentHashMap<>();

    static class CacheEntry<V> {
        final V value;
        final long expireTime;

        boolean isExpired() {
            return System.currentTimeMillis() > expireTime;
        }
    }

    public V get(K key, Function<K, V> loader, long ttlMs) {
        CacheEntry<V> entry = cache.get(key);
        if (entry == null || entry.isExpired()) {
            // 使用compute防止缓存击穿（单key只计算一次）
            entry = cache.compute(key, (k, old) -> {
                if (old != null && !old.isExpired()) return old;
                V value = loader.apply(k);
                return new CacheEntry<>(value,
                          System.currentTimeMillis() + ttlMs);
            });
        }
        return entry.value;
    }
}
```

### 4.3 场景三：生产者-消费者模式

**Q: 如何使用BlockingQueue实现生产者-消费者模式？**

```java
public class ProducerConsumer<T> {
    private final BlockingQueue<T> queue;
    private volatile boolean running = true;

    // 生产者
    class Producer implements Runnable {
        @Override
        public void run() {
            while (running) {
                T item = produce();
                queue.put(item);  // 队列满时阻塞
            }
        }
    }

    // 消费者（批量处理）
    class BatchConsumer implements Runnable {
        private final List<T> batch = new ArrayList<>(100);

        @Override
        public void run() {
            while (running) {
                // 使用drainTo批量消费，减少加锁次数
                queue.drainTo(batch, 100);
                batch.forEach(this::process);
                batch.clear();
            }
        }
    }

    // 优雅关闭
    public void shutdown() {
        running = false;
        queue.offer(poisonPill); // 毒丸对象通知消费者停止
    }
}
```

---

## 五、面试高频追问

**Q1: ConcurrentHashMap的size()方法如何实现？**

A: JDK8中，size()通过`sumCount()`统计每个CounterCell的累加值：
- 有竞争时使用`CounterCell`数组分散计数（类似LongAdder）
- 无竞争时直接在`baseCount`上CAS累加
- 获取总数时对baseCount + 所有CounterCell求和

**Q2: ConcurrentHashMap的get()方法需要加锁吗？**

A: **不需要加锁**。get()通过Node.val的volatile语义保证可见性，读操作总是看到最新的值。这是JDK8的优化之一。

**Q3: LinkedBlockingQueue默认容量是多少？为什么是危险的？**

A: 默认`Integer.MAX_VALUE`（约21亿），等于**无界队列**。在高并发场景下，如果生产者持续快于消费者，队列会无限膨胀直到OOM。**建议生产环境显式指定有界容量。**

---

## 六、总结

| 并发容器 | 核心机制 | 适用场景 | 注意事项 |
|----------|----------|----------|----------|
| ConcurrentHashMap | CAS+synchronized+红黑树 | 高并发KV存储 | 不允许null |
| CopyOnWriteArrayList | 写时复制+volatile | 读多写少（配置、监听器） | 内存开销大 |
| ArrayBlockingQueue | 数组+单锁 | 有界缓冲区 | 吞吐量受限 |
| LinkedBlockingQueue | 链表+双锁 | 高吞吐任务队列 | 默认容量危险 |
| SynchronousQueue | 直接交付 | 手把手传递 | 必须有配对线程 |
| PriorityBlockingQueue | 堆+排序 | 优先级调度 | 元素需实现Comparable |
| DelayQueue | 延迟到期 | 定时任务 | 元素需实现Delayed |
| ConcurrentSkipListMap | 跳表 | 高并发有序Map | 代替TreeMap |

**核心要点：**
1. **ConcurrentHashMap**：JDK8弃用分段锁，采用CAS+synchronized，桶级锁粒度更细
2. **CopyOnWriteArrayList**：读写分离，写时复制，适合读多写少场景
3. **BlockingQueue**：双锁Linked优于单锁Array（吞吐），但要指定有界容量
4. **选型原则**：先确定读写比例，再看是否需要排序，最后考虑内存与吞吐权衡

---

> 🎯 **下期预告**：《Java并发编程面试八股文（四）——异步编程与并发设计模式》将深入CompletableFuture异步编排、ForkJoinPool分治框架、生产者消费者等并发设计模式以及海量并发下的性能调优实战，敬请期待！
