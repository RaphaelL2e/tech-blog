---
title: "Java并发编程面试八股文（二）——JUC并发工具类与线程池"
date: 2026-06-15T10:00:00+08:00
draft: false
categories: ["java"]
tags: ["面试", "八股文", "Java", "并发", "线程池", "JUC", "CountDownLatch", "Semaphore", "ThreadPoolExecutor"]
---

# Java并发编程面试八股文（二）——JUC并发工具类与线程池

> 面试高频问题：CountDownLatch和CyclicBarrier有什么区别？线程池的核心参数有哪些？如何设置线程池大小？线程池的拒绝策略有哪些？本文带你系统掌握JUC并发工具类与线程池的核心知识。

---

## 一、原子类

### 1.1 CAS与原子类

**Q: 什么是CAS？Java中有哪些原子类？**

A: CAS(Compare-And-Swap)是比较并交换，是乐观锁的核心：

```java
// CAS伪代码
public boolean compareAndSwap(int expected, int newValue) {
    if (this.value == expected) {
        this.value = newValue;
        return true;
    }
    return false;
}
```

**原子类分类**：

| 类型 | 代表类 | 说明 |
|------|--------|------|
| 基本类型 | AtomicInteger, AtomicLong, AtomicBoolean | 原子更新基本类型 |
| 数组类型 | AtomicIntegerArray, AtomicLongArray | 原子更新数组元素 |
| 引用类型 | AtomicReference, AtomicStampedReference | 原子更新引用 |
| 字段更新器 | AtomicIntegerFieldUpdater | 原子更新对象的字段 |
| 累加器 | LongAdder, DoubleAdder | 高性能累加 |

### 1.2 AtomicInteger原理

**Q: AtomicInteger如何实现线程安全？**

A:

```java
public class AtomicInteger {
    private volatile int value;
    
    public final int getAndIncrement() {
        return unsafe.getAndAddInt(this, valueOffset, 1);
    }
}

// Unsafe中的实现（自旋+CAS）
public final int getAndAddInt(Object o, long offset, int delta) {
    int v;
    do {
        v = getIntVolatile(o, offset);
    } while (!compareAndSwapInt(o, offset, v, v + delta));
    return v;
}
```

### 1.3 LongAdder vs AtomicLong

**Q: LongAdder和AtomicLong有什么区别？**

A:

```java
// AtomicLong：单点竞争
AtomicLong counter = new AtomicLong();
counter.incrementAndGet(); // 所有线程竞争同一个value

// LongAdder：分散热点
LongAdder adder = new LongAdder();
adder.increment(); // 分散到多个Cell，减少竞争
adder.sum();       // 最终一致性读取
```

| 特性 | AtomicLong | LongAdder |
|------|------------|-----------|
| 原理 | 单值CAS | 分散热点+Cell数组 |
| 高并发性能 | 较差（竞争激烈） | 优秀（分散竞争） |
| 空间开销 | 小 | 较大（Cell数组） |
| 适用场景 | 低竞争、需要精确值 | 高竞争、允许最终一致 |

---

## 二、并发容器

### 2.1 ConcurrentHashMap

**Q: ConcurrentHashMap的实现原理？JDK7和JDK8的区别？**

A:

**JDK7实现**（分段锁）：

```
Segment[] segments  // 16个Segment
每个Segment是一个ReentrantLock
每个Segment维护一个HashEntry数组
```

**JDK8实现**（CAS+synchronized）：

```
Node[] table
- 空桶：CAS插入
- 有节点：synchronized锁定链表头/树根
- 链表长度>8：转红黑树
```

| 版本 | 锁粒度 | 并发度 | 数据结构 |
|------|--------|--------|---------|
| JDK7 | Segment级别 | 固定16 | HashEntry数组+链表 |
| JDK8 | Node级别 | 动态 | Node数组+链表+红黑树 |

**核心方法**：

```java
// put流程
final V putVal(K key, V value, boolean onlyIfAbsent) {
    // 1. 计算hash
    int hash = spread(key.hashCode());
    for (Node<K,V>[] tab = table;;) {
        Node<K,V> f; int n, i, fh;
        // 2. 空桶，CAS插入
        if (tab == null || (n = tab.length) == 0)
            tab = initTable();
        else if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value, null)))
                break;
        }
        // 3. 正在扩容，帮助迁移
        else if ((fh = f.hash) == MOVED)
            tab = helpTransfer(tab, f);
        // 4. 锁定头节点，插入链表/树
        else {
            synchronized (f) {
                // 插入逻辑
            }
        }
    }
    // 5. 检查是否需要树化
    addCount(1L, binCount);
    return null;
}
```

### 2.2 CopyOnWriteArrayList

**Q: CopyOnWriteArrayList的实现原理？适用场景？**

A:

```java
public class CopyOnWriteArrayList<E> {
    private transient volatile Object[] array;
    
    public boolean add(E e) {
        synchronized (lock) {
            Object[] elements = getArray();
            int len = elements.length;
            // 复制新数组
            Object[] newElements = Arrays.copyOf(elements, len + 1);
            newElements[len] = e;
            // 替换引用
            setArray(newElements);
            return true;
        }
    }
    
    public E get(int index) {
        return elementAt(getArray(), index); // 无锁读取
    }
}
```

**特点**：
- **读无锁**：直接读取volatile数组引用
- **写复制**：修改时复制整个数组
- **适用**：读多写少、遍历操作多

**缺点**：
- 内存占用大（每次写都复制）
- 数据一致性弱（迭代器是弱一致性）
- 不适合写密集场景

### 2.3 BlockingQueue

**Q: BlockingQueue有哪些实现？各自特点？**

A:

| 实现类 | 特点 | 适用场景 |
|--------|------|---------|
| ArrayBlockingQueue | 有界数组、公平可选 | 生产者消费者 |
| LinkedBlockingQueue | 可选有界链表 | 任务队列 |
| PriorityBlockingQueue | 无界优先级队列 | 优先级任务 |
| SynchronousQueue | 零容量、直接传递 | 线程池默认队列 |
| DelayQueue | 延迟获取 | 定时任务 |

```java
// ArrayBlockingQueue实现
public void put(E e) throws InterruptedException {
    final ReentrantLock lock = this.lock;
    lock.lockInterruptibly();
    try {
        while (count == items.length)
            notFull.await();  // 满则等待
        enqueue(e);
    } finally {
        lock.unlock();
    }
}

public E take() throws InterruptedException {
    final ReentrantLock lock = this.lock;
    lock.lockInterruptibly();
    try {
        while (count == 0)
            notEmpty.await();  // 空则等待
        return dequeue();
    } finally {
        lock.unlock();
    }
}
```

---

## 三、并发工具类

### 3.1 CountDownLatch

**Q: CountDownLatch的使用场景？原理？**

A: CountDownLatch是一次性栅栏，等待计数归零：

```java
// 场景：等待多个线程完成
CountDownLatch latch = new CountDownLatch(3);

for (int i = 0; i < 3; i++) {
    new Thread(() -> {
        try {
            // 执行任务
        } finally {
            latch.countDown(); // 计数减1
        }
    }).start();
}

latch.await(); // 阻塞直到计数为0
System.out.println("所有任务完成");
```

**原理**：基于AQS共享模式，state初始为计数器值，countDown减state，await在state>0时阻塞。

### 3.2 CyclicBarrier

**Q: CyclicBarrier和CountDownLatch的区别？**

A:

| 特性 | CountDownLatch | CyclicBarrier |
|------|---------------|---------------|
| 复用性 | 一次性 | 可循环使用 |
| 触发机制 | 计数减到0 | 等待线程数达标 |
| 等待方 | 主线程等N个 | N个线程互相等 |
| 回调 | 无 | 支持barrierAction |

```java
// 场景：多线程分阶段执行
CyclicBarrier barrier = new CyclicBarrier(3, () -> {
    System.out.println("阶段完成，继续下一阶段");
});

for (int i = 0; i < 3; i++) {
    new Thread(() -> {
        while (true) {
            // 阶段1
            barrier.await();
            // 阶段2
            barrier.await();
            // ...
        }
    }).start();
}
```

### 3.3 Semaphore

**Q: Semaphore的使用场景？**

A: Semaphore控制同时访问的线程数：

```java
// 场景：限流，最多3个线程同时访问
Semaphore semaphore = new Semaphore(3);

public void access() throws InterruptedException {
    semaphore.acquire(); // 获取许可
    try {
        // 访问资源
    } finally {
        semaphore.release(); // 释放许可
    }
}
```

**公平性**：

```java
// 非公平（默认）
Semaphore unfair = new Semaphore(3);
// 公平
Semaphore fair = new Semaphore(3, true);
```

### 3.4 Exchanger

**Q: Exchanger的作用是什么？**

A: 用于两个线程之间交换数据：

```java
Exchanger<List<String>> exchanger = new Exchanger<>();

// 线程1：生产数据
List<String> buffer1 = new ArrayList<>();
buffer1.add("data1");
buffer1 = exchanger.exchange(buffer1); // 交换并清空

// 线程2：消费数据
List<String> buffer2 = new ArrayList<>();
buffer2 = exchanger.exchange(buffer2); // 获取数据
for (String s : buffer2) {
    System.out.println(s);
}
```

---

## 四、线程池

### 4.1 ThreadPoolExecutor核心参数

**Q: 线程池有哪些核心参数？**

A:

```java
public ThreadPoolExecutor(
    int corePoolSize,        // 核心线程数
    int maximumPoolSize,     // 最大线程数
    long keepAliveTime,      // 非核心线程空闲存活时间
    TimeUnit unit,           // 时间单位
    BlockingQueue<Runnable> workQueue, // 任务队列
    ThreadFactory threadFactory,        // 线程工厂
    RejectedExecutionHandler handler    // 拒绝策略
)
```

**参数详解**：

| 参数 | 说明 |
|------|------|
| corePoolSize | 核心线程数，常驻线程 |
| maximumPoolSize | 最大线程数，包含核心+临时线程 |
| keepAliveTime | 临时线程空闲存活时间 |
| workQueue | 任务队列，存储待执行任务 |
| threadFactory | 创建线程的工厂 |
| handler | 拒绝策略 |

### 4.2 任务执行流程

**Q: 线程池如何执行任务？**

A:

```
提交任务
    │
    ├─ 核心线程数未满？
    │     └─ 是 → 创建核心线程执行
    │
    ├─ 队列未满？
    │     └─ 是 → 加入队列等待
    │
    ├─ 最大线程数未满？
    │     └─ 是 → 创建临时线程执行
    │
    └─ 执行拒绝策略
```

```java
public void execute(Runnable command) {
    if (workerCountOf(ctl.get()) < corePoolSize) {
        if (addWorker(command, true))  // 创建核心线程
            return;
    }
    if (workQueue.offer(command)) {    // 加入队列
        if (workerCountOf(ctl.get()) == 0)
            addWorker(null, false);
        return;
    }
    if (!addWorker(command, false))    // 创建临时线程
        reject(command);               // 拒绝
}
```

### 4.3 四种预定义线程池

**Q: Executors提供的线程池有什么问题？**

A:

```java
// 1. FixedThreadPool - 固定线程数
// 问题：使用无界队列，可能OOM
Executors.newFixedThreadPool(10);

// 2. CachedThreadPool - 可缓存线程池
// 问题：最大线程数Integer.MAX_VALUE，可能创建过多线程
Executors.newCachedThreadPool();

// 3. SingleThreadExecutor - 单线程
// 问题：无界队列，可能OOM
Executors.newSingleThreadExecutor();

// 4. ScheduledThreadPool - 定时任务
// 问题：最大线程数Integer.MAX_VALUE
Executors.newScheduledThreadPool(10);
```

**推荐做法**：

```java
// 手动创建，明确参数
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    Runtime.getRuntime().availableProcessors(),      // 核心线程 = CPU核数
    Runtime.getRuntime().availableProcessors() * 2,  // 最大线程
    60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),                 // 有界队列
    new ThreadPoolExecutor.CallerRunsPolicy()        // 拒绝策略
);
```

### 4.4 拒绝策略

**Q: 线程池有哪些拒绝策略？**

A:

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| AbortPolicy | 抛RejectedExecutionException | 默认，需要处理异常 |
| CallerRunsPolicy | 调用者线程执行 | 降级，不丢失任务 |
| DiscardPolicy | 静默丢弃 | 允许丢失任务 |
| DiscardOldestPolicy | 丢弃最老任务 | 优先处理新任务 |

```java
// 自定义拒绝策略
executor.setRejectedExecutionHandler((r, e) -> {
    log.warn("任务被拒绝，记录日志或持久化");
    // 可以存储到MQ或数据库稍后重试
});
```

### 4.5 线程池大小设置

**Q: 如何设置线程池大小？**

A:

**CPU密集型**：

```
线程数 = CPU核数 + 1
```

**IO密集型**：

```
线程数 = CPU核数 × (1 + 平均等待时间/平均工作时间)
```

```java
// CPU密集型
int cpuCount = Runtime.getRuntime().availableProcessors();
ThreadPoolExecutor cpuPool = new ThreadPoolExecutor(
    cpuCount + 1, cpuCount + 1,
    0L, TimeUnit.MILLISECONDS,
    new LinkedBlockingQueue<>()
);

// IO密集型
ThreadPoolExecutor ioPool = new ThreadPoolExecutor(
    cpuCount * 2, cpuCount * 4,
    60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000)
);
```

### 4.6 线程池监控

**Q: 如何监控线程池状态？**

A:

```java
ThreadPoolExecutor executor = ...;

// 监控指标
int activeCount = executor.getActiveCount();      // 活跃线程数
long completedTasks = executor.getCompletedTaskCount(); // 完成任务数
int queueSize = executor.getQueue().size();       // 队列大小
int poolSize = executor.getPoolSize();            // 当前线程数
long taskCount = executor.getTaskCount();         // 总任务数

// 定时监控
ScheduledExecutorService monitor = Executors.newScheduledThreadPool(1);
monitor.scheduleAtFixedRate(() -> {
    log.info("活跃线程: {}, 队列大小: {}, 完成任务: {}",
        activeCount, queueSize, completedTasks);
}, 0, 1, TimeUnit.SECONDS);
```

---

## 五、ScheduledThreadPoolExecutor

### 5.1 定时任务

**Q: 如何实现定时任务？**

A:

```java
ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);

// 延迟执行
scheduler.schedule(() -> {
    System.out.println("延迟3秒执行");
}, 3, TimeUnit.SECONDS);

// 固定延迟（任务完成后开始计时）
scheduler.scheduleWithFixedDelay(() -> {
    System.out.println("每次完成后延迟2秒");
}, 0, 2, TimeUnit.SECONDS);

// 固定频率（不管任务是否完成）
scheduler.scheduleAtFixedRate(() -> {
    System.out.println("每3秒执行一次");
}, 0, 3, TimeUnit.SECONDS);
```

### 5.2 DelayedWorkQueue原理

**Q: ScheduledThreadPoolExecutor如何实现延迟？**

A: 使用DelayQueue，基于堆实现：

```java
// 任务实现Delayed接口
class ScheduledFutureTask<V> implements RunnableScheduledFuture<V> {
    private long time;  // 执行时间
    
    public long getDelay(TimeUnit unit) {
        return unit.convert(time - now(), NANOSECONDS);
    }
    
    public int compareTo(Delayed other) {
        return Long.compare(time, ((ScheduledFutureTask)other).time);
    }
}
```

---

## 六、ForkJoinPool

### 6.1 工作窃取算法

**Q: ForkJoinPool的特点？什么是工作窃取？**

A:

```
Thread1: [Task1][Task2][Task3]
Thread2: [Task4]         ↑
              └─────────┘
              窃取Thread1的任务
```

**特点**：
- 分治任务，大任务拆分为小任务
- 每个线程维护自己的双端队列
- 空闲线程从其他线程队列尾部窃取任务

```java
public class ForkJoinDemo {
    static class SumTask extends RecursiveTask<Long> {
        private final long[] array;
        private final int start, end;
        private static final int THRESHOLD = 1000;
        
        @Override
        protected Long compute() {
            if (end - start <= THRESHOLD) {
                // 直接计算
                long sum = 0;
                for (int i = start; i < end; i++)
                    sum += array[i];
                return sum;
            }
            // 分割任务
            int mid = (start + end) >>> 1;
            SumTask left = new SumTask(array, start, mid);
            SumTask right = new SumTask(array, mid, end);
            left.fork();  // 异步执行
            return right.compute() + left.join();
        }
    }
    
    public static void main(String[] args) {
        ForkJoinPool pool = new ForkJoinPool();
        Long result = pool.invoke(new SumTask(array, 0, array.length));
    }
}
```

### 6.2 并行流

**Q: parallelStream使用什么线程池？**

A: parallelStream默认使用ForkJoinPool.commonPool()：

```java
// 默认使用公共池
list.parallelStream().forEach(System.out::println);

// 指定自定义线程池
ForkJoinPool customPool = new ForkJoinPool(4);
customPool.submit(() -> 
    list.parallelStream().forEach(System.out::println)
).get();
```

---

## 七、CompletableFuture

### 7.1 异步编程

**Q: CompletableFuture如何实现异步编排？**

A:

```java
// 异步执行
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    return "Hello";
});

// 链式调用
CompletableFuture<String> result = future
    .thenApply(s -> s + " World")      // 同步转换
    .thenApplyAsync(String::toUpperCase) // 异步转换
    .thenCompose(s -> CompletableFuture.supplyAsync(() -> s + "!")); // 扁平化

// 组合多个Future
CompletableFuture<String> future1 = CompletableFuture.supplyAsync(() -> "A");
CompletableFuture<String> future2 = CompletableFuture.supplyAsync(() -> "B");

// 两个都完成
CompletableFuture<String> combined = future1.thenCombine(future2, (a, b) -> a + b);

// 任一完成
CompletableFuture<Object> anyOf = CompletableFuture.anyOf(future1, future2);

// 全部完成
CompletableFuture<Void> allOf = CompletableFuture.allOf(future1, future2);
```

### 7.2 异常处理

**Q: CompletableFuture如何处理异常？**

A:

```java
CompletableFuture<String> future = CompletableFuture.supplyAsync(() -> {
    if (Math.random() > 0.5) throw new RuntimeException("error");
    return "success";
})
.exceptionally(ex -> "fallback")  // 异常时返回默认值
.handle((result, ex) -> {         // 统一处理
    if (ex != null) return "error";
    return result;
});
```

---

## 八、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| 原子类 | CAS、LongAdder、AtomicReference | compareAndSet, 分散热点 |
| ConcurrentHashMap | JDK7分段锁、JDK8 CAS+synchronized | sizeCtl, treeify |
| CopyOnWrite | 写复制、弱一致性 | volatile array, 读多写少 |
| CountDownLatch | 一次性栅栏、等待N个任务 | await, countDown |
| CyclicBarrier | 可循环栅栏、互相等待 | barrierAction, reset |
| Semaphore | 信号量限流 | acquire, release, 公平 |
| 线程池 | 7参数、执行流程、拒绝策略 | corePoolSize, workQueue |
| ForkJoin | 分治、工作窃取 | RecursiveTask, commonPool |
| CompletableFuture | 异步编排、链式调用 | thenApply, thenCompose, handle |

---

> 🎯 **下期预告**：《Java并发编程面试八股文（三）——并发容器深入与实战案例》将深入ConcurrentHashMap源码、阻塞队列实现原理、并发场景最佳实践等高级话题，敬请期待！
