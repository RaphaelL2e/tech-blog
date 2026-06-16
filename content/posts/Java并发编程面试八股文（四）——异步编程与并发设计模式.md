---
title: "Java并发编程面试八股文（四）——异步编程与并发设计模式"
date: 2026-06-16T10:00:00+08:00
draft: false
categories: ["java"]
tags: ["面试", "八股文", "Java", "并发", "CompletableFuture", "ForkJoinPool", "设计模式", "异步编程"]
---

# Java并发编程面试八股文（四）——异步编程与并发设计模式

> 面试高频问题：CompletableFuture和Future有什么区别？thenApply和thenCompose的使用场景？ForkJoinPool的工作窃取算法是什么？如何设计线程安全的单例模式？本文带你深入Java异步编程与并发设计模式。

---

## 一、CompletableFuture异步编程深入

### 1.1 Future的局限性

**Q: 传统Future有什么局限性？CompletableFuture如何解决？**

A: 传统`Future`的主要问题：

```java
// Future的痛点
Future<String> future = executor.submit(callable);

// 1. get()阻塞等待，浪费线程
String result = future.get(); // 会一直阻塞

// 2. 无法组合多个异步任务
// 3. 无法链式回调
// 4. 异常处理不优雅
// 5. 不支持手动完成
```

**CompletableFuture的革命性改进：**

```java
// CompletableFuture：异步编程的全新范式
CompletableFuture.supplyAsync(() -> fetchUser(userId))
    .thenApply(user -> enrichUser(user))           // 转换结果
    .thenCompose(user -> fetchOrders(user))         // 扁平化组合
    .thenAccept(orders -> saveOrders(orders))       // 消费结果
    .exceptionally(ex -> {                          // 异常处理
        log.error("处理失败", ex);
        return Collections.emptyList();
    });
```

### 1.2 创建异步任务

**Q: CompletableFuture有哪些创建方式？**

```java
// 方式1：runAsync —— 无返回值
CompletableFuture<Void> future1 = CompletableFuture.runAsync(() -> {
    doSomething();
});

// 方式2：supplyAsync —— 有返回值
CompletableFuture<String> future2 = CompletableFuture.supplyAsync(() -> {
    return fetchData();
});

// 方式3：指定线程池
Executor customPool = Executors.newFixedThreadPool(10);
CompletableFuture<String> future3 = CompletableFuture.supplyAsync(
    () -> fetchData(), customPool);  // 不指定则使用ForkJoinPool.commonPool()

// 方式4：手动创建（用于桥接回调式API）
CompletableFuture<String> future4 = new CompletableFuture<>();
// 在其他线程中完成：
future4.complete("result");
// 或在回调中完成：
callback.onSuccess(result -> future4.complete(result));
```

### 1.3 链式操作详解

**Q: thenApply / thenCompose / thenAccept / thenRun 有什么区别？**

```java
CompletableFuture<String> future = CompletableFuture
    .supplyAsync(() -> "hello");

// thenApply：类型转换 （T -> U）
CompletableFuture<Integer> f1 = future
    .thenApply(s -> s.length()); // String -> Integer

// thenCompose：扁平化组合 （T -> CompletableFuture<U>） 
// 用于需要返回另一个异步结果的场景
CompletableFuture<String> f2 = future
    .thenCompose(s -> fetchUserByName(s));  // 避免嵌套CompletableFuture

// thenAccept：消费结果，无返回 （T -> void）
CompletableFuture<Void> f3 = future
    .thenAccept(s -> System.out.println(s));

// thenRun：不依赖前置结果，仅在前置完成后执行
CompletableFuture<Void> f4 = future
    .thenRun(() -> System.out.println("done"));
```

**thenApply vs thenCompose 的实际差异：**

```java
// ❌ 使用thenApply导致嵌套
CompletableFuture<CompletableFuture<String>> nested =
    supplyAsync(() -> "user")
        .thenApply(user -> fetchOrders(user)); // 返回CompletableFuture<CompletableFuture<...>>

// ✅ 使用thenCompose自动展平
CompletableFuture<String> flat =
    supplyAsync(() -> "user")
        .thenCompose(user -> fetchOrders(user)); // 返回CompletableFuture<String>
```

### 1.4 组合多个CompletableFuture

**Q: 如何组合多个CompletableFuture的结果？**

```java
// 1. thenCombine：合并两个独立任务的结果
CompletableFuture<String> userFuture = fetchUser();
CompletableFuture<String> orderFuture = fetchOrders();
CompletableFuture<String> combined = userFuture
    .thenCombine(orderFuture, (user, orders) ->
        "用户: " + user + ", 订单: " + orders);

// 2. allOf：等待所有任务完成（返回Void）
CompletableFuture<Void> allDone = CompletableFuture.allOf(
    fetchUser(), fetchOrders(), fetchAddress());
// 典型用法：获取所有结果
CompletableFuture<List<String>> allResults = allDone
    .thenApply(v -> Stream.of(
        userFuture.join(),    // 此刻所有任务已完成，join()不阻塞
        orderFuture.join())
        .collect(Collectors.toList()));

// 3. anyOf：任一任务完成即返回
CompletableFuture<Object> first = CompletableFuture.anyOf(
    fetchFromSourceA(), fetchFromSourceB());
// 竞速查询：哪个数据源先返回就用哪个

// 4. thenAcceptBoth：消费两个任务结果
CompletableFuture<Void> consumer = userFuture
    .thenAcceptBoth(orderFuture, (user, orders) ->
        saveToDatabase(user, orders));
```

### 1.5 异常处理

**Q: CompletableFuture如何处理异常？**

```java
CompletableFuture<String> future = CompletableFuture
    .supplyAsync(() -> {
        if (Math.random() > 0.5) throw new RuntimeException("模拟异常");
        return "success";
    })
    // 异常恢复（兜底值）
    .exceptionally(ex -> {
        log.error("任务失败: {}", ex.getMessage());
        return "fallback";  // 提供降级结果
    });

// handle：无论成功失败都执行（类似finally+map）
CompletableFuture<String> handled = future
    .handle((result, ex) -> {
        if (ex != null) {
            return "异常处理: " + ex.getMessage();
        }
        return "正常结果: " + result;
    });

// whenComplete：监控/记录，不改变结果
CompletableFuture<String> monitored = future
    .whenComplete((result, ex) -> {
        if (ex != null) metrics.recordError();
        else metrics.recordSuccess();
    });
```

---

## 二、ForkJoinPool分治框架

### 2.1 ForkJoinPool核心设计

**Q: ForkJoinPool的核心设计思想是什么？**

A: ForkJoinPool基于**分治(Divide-and-Conquer)**和**工作窃取(Work-Stealing)**：

```java
// ForkJoinPool常量定义
ForkJoinPool commonPool = ForkJoinPool.commonPool(); // 公共池（CPU核心数-1个线程）

// 自定义线程池
ForkJoinPool pool = new ForkJoinPool(
    Runtime.getRuntime().availableProcessors(), // 并行度
    ForkJoinPool.defaultForkJoinWorkerThreadFactory,
    null,  // 异常处理器
    false  // 异步模式
);
```

### 2.2 工作窃取算法

**Q: 什么是工作窃取(Work-Stealing)算法？**

A: 工作窃取是ForkJoinPool的核心调度算法：

```
线程A: [任务1][任务2][任务3][任务4] → 双端队列（自己的任务从栈顶取）
线程B: [任务5]                       → 空闲时从别的线程队列底部窃取任务

流程：
1. 每个工作线程维护一个双端队列（deque）
2. 自己产生的任务push到队列头部，从头部pop执行（LIFO）
3. 空闲线程从其他线程队列尾部steal任务（FIFO）
4. 窃取的大任务可能被继续分解
```

**优势：**
- 减少任务分配开销（不需要统一调度器）
- 充分利用CPU，避免线程闲置
- 窃取大任务能有效减少窃取次数

### 2.3 RecursiveTask与RecursiveAction

**Q: RecursiveTask和RecursiveAction的区别？如何使用？**

```java
// RecursiveTask：有返回值
// 经典案例：大数组求和（分治）
public class SumTask extends RecursiveTask<Long> {
    private static final int THRESHOLD = 1000;
    private final long[] array;
    private final int start, end;

    public SumTask(long[] array, int start, int end) {
        this.array = array;
        this.start = start;
        this.end = end;
    }

    @Override
    protected Long compute() {
        if (end - start <= THRESHOLD) {
            // 任务足够小：直接计算
            long sum = 0;
            for (int i = start; i < end; i++) sum += array[i];
            return sum;
        }
        // 任务太大：二分拆解
        int mid = (start + end) / 2;
        SumTask left = new SumTask(array, start, mid);
        SumTask right = new SumTask(array, mid, end);
        left.fork();        // 异步执行左子任务
        right.fork();       // 异步执行右子任务
        return left.join() + right.join(); // 等待子任务完成并合并结果
    }
}

// RecursiveAction：无返回值
public class PrintTask extends RecursiveAction {
    @Override
    protected void compute() {
        // 类似逻辑，但compute()无返回值
    }
}

// 使用
ForkJoinPool pool = new ForkJoinPool();
long[] data = new long[10_000_000];
Long sum = pool.invoke(new SumTask(data, 0, data.length));
```

### 2.4 CompletableFuture与ForkJoinPool的关系

**Q: CompletableFuture默认使用哪个线程池？**

A: 默认使用`ForkJoinPool.commonPool()`，线程数 = CPU核心数 - 1。

```java
// ❌ 常见问题：commonPool被阻塞导致所有CompletableFuture卡死
CompletableFuture.supplyAsync(() -> {
    Thread.sleep(10000); // 阻塞commonPool线程
    return "result";
});

// ✅ 解决方案：使用自定义线程池
Executor pool = Executors.newFixedThreadPool(20);
CompletableFuture.supplyAsync(() -> {
    Thread.sleep(10000); // 阻塞自定义池，不影响commonPool
    return "result";
}, pool);  // ← 指定线程池
```

---

## 三、并发设计模式

### 3.1 生产者-消费者模式

**Q: 生产者-消费者模式的实现方式和注意事项？**

```java
// 经典实现：BlockingQueue
public class ProducerConsumerPattern<T> {
    private final BlockingQueue<T> buffer;
    private final int producers, consumers;

    // 1. 有界缓冲区 → 背压(backpressure)
    public ProducerConsumerPattern(int bufferSize, int producers, int consumers) {
        this.buffer = new ArrayBlockingQueue<>(bufferSize);
        this.producers = producers;
        this.consumers = consumers;
    }

    public void start() {
        // 启动生产者
        for (int i = 0; i < producers; i++) {
            new Thread(() -> {
                while (!Thread.currentThread().isInterrupted()) {
                    T item = produce();
                    buffer.put(item);  // 满时阻塞 → 天然背压
                }
            }).start();
        }
        // 启动消费者
        for (int i = 0; i < consumers; i++) {
            new Thread(() -> {
                while (!Thread.currentThread().isInterrupted()) {
                    T item = buffer.take();
                    consume(item);
                }
            }).start();
        }
    }
}

// 2. 使用drainTo批量操作（减少锁竞争）
buffer.drainTo(batch, 100); // 一次取100个，只加锁一次
```

### 3.2 读写锁模式

**Q: ReentrantReadWriteLock的使用场景和实现原理？**

```java
public class CachedData {
    private volatile Object cache;
    private final ReadWriteLock rwl = new ReentrantReadWriteLock();

    public Object getData() {
        rwl.readLock().lock();
        try {
            if (cache != null) return cache;
        } finally {
            rwl.readLock().unlock();
        }

        // 缓存未命中，升级为写锁
        rwl.writeLock().lock();
        try {
            // 双重检查：可能其他线程已经填充了缓存
            if (cache == null) {
                cache = loadFromDB();
            }
            return cache;
        } finally {
            rwl.writeLock().unlock();
        }
    }
}
```

**锁降级（写锁→读锁，保证可见性）：**

```java
rwl.writeLock().lock();
try {
    cache = loadFromDB();
    // 获取读锁后再释放写锁 → 锁降级
    rwl.readLock().lock();
} finally {
    rwl.writeLock().unlock(); // 释放写锁，仍持有读锁
}
// 此时数据已可见，继续持有读锁
try {
    return processData(cache);
} finally {
    rwl.readLock().unlock();
}
```

> **注意**：ReentrantReadWriteLock**不支持锁升级**（读锁→写锁）。如果读锁未释放就尝试获取写锁，会导致死锁。

### 3.3 Future模式

**Q: Future模式的使用场景和注意事项？**

```java
// 典型场景：并行调用多个独立服务
ExecutorService executor = Executors.newFixedThreadPool(5);

Future<User> userFuture = executor.submit(() -> userService.getUser(id));
Future<Order> orderFuture = executor.submit(() -> orderService.getOrders(id));
Future<Address> addrFuture = executor.submit(() -> addressService.getAddress(id));

// 等待所有结果
User user = userFuture.get(3, TimeUnit.SECONDS);
Order order = orderFuture.get(3, TimeUnit.SECONDS);
Address addr = addrFuture.get(3, TimeUnit.SECONDS);

// ✅ 更优雅的方式：CompletableFuture
CompletableFuture<User> uf = CompletableFuture.supplyAsync(() -> userService.getUser(id));
CompletableFuture<Order> of = CompletableFuture.supplyAsync(() -> orderService.getOrders(id));
CompletableFuture<Address> af = CompletableFuture.supplyAsync(() -> addressService.getAddress(id));

UserInfo info = CompletableFuture.allOf(uf, of, af)
    .thenApply(v -> new UserInfo(uf.join(), of.join(), af.join()))
    .get(3, TimeUnit.SECONDS);
```

### 3.4 单例模式（线程安全版）

**Q: 如何实现线程安全的单例模式？有哪些实现方式？**

```java
// 方式1：饿汉式（类加载时创建，天生线程安全）
public class EagerSingleton {
    private static final EagerSingleton INSTANCE = new EagerSingleton();
    private EagerSingleton() {}
    public static EagerSingleton getInstance() { return INSTANCE; }
}

// 方式2：双重检查锁定（DCL）+ volatile
public class DCLSingleton {
    private volatile static DCLSingleton instance; // volatile防止指令重排

    private DCLSingleton() {}

    public static DCLSingleton getInstance() {
        if (instance == null) {                    // 第一次检查（无锁）
            synchronized (DCLSingleton.class) {
                if (instance == null) {            // 第二次检查（加锁）
                    instance = new DCLSingleton(); // 三步：分配内存→初始化→赋值引用
                }
            }
        }
        return instance;
    }
}
// volatile作用：防止new对象时的指令重排
// 没有volatile → 线程A看到instance != null → 但对象可能未初始化完成

// 方式3：静态内部类（推荐，懒加载 + 线程安全）
public class HolderSingleton {
    private HolderSingleton() {}

    private static class Holder {
        private static final HolderSingleton INSTANCE = new HolderSingleton();
    }

    public static HolderSingleton getInstance() {
        return Holder.INSTANCE; // 首次访问Holder时触发类加载，JVM保证线程安全
    }
}

// 方式4：枚举（最安全，防反射/序列化攻击）
public enum EnumSingleton {
    INSTANCE;
    public void doSomething() { /* ... */ }
}
```

---

## 四、并发编程最佳实践

### 4.1 线程池选型指南

**Q: 如何根据业务场景选择线程池？**

| 场景 | 推荐方案 | 原因 |
|------|----------|------|
| CPU密集型 | `N+1` 个线程（N=CPU核心数） | 减少线程切换开销 |
| IO密集型 | `2N` 或更多个线程 | 线程大多数时间阻塞等待IO |
| 混合型 | 拆分CPU和IO任务，分别用不同线程池 | 避免CPU任务阻塞IO任务 |
| 快速响应用户请求 | `CachedThreadPool` | 无界线程，快速响应用峰 |
| 限流保护资源 | `FixedThreadPool` + `有界队列` | 任务缓冲 + 拒绝策略保护 |

```java
// 生产环境线程池最佳实践：显式创建（不用Executors工厂方法）
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    corePoolSize,        // 核心线程数（CPU密集型=N+1, IO密集型=2N）
    maxPoolSize,         // 最大线程数
    60L, TimeUnit.SECONDS, // 空闲线程存活时间
    new LinkedBlockingQueue<>(capacity), // 有界队列！防止OOM
    new ThreadPoolExecutor.CallerRunsPolicy() // 拒绝策略：让调用者执行
    // 拒绝策略选择：
    // CallerRunsPolicy → 让提交任务的线程执行（温和降级）
    // AbortPolicy → 抛RejectedExecutionException（默认，需自行处理）
    // DiscardPolicy → 静默丢弃（数据丢失风险！不推荐）
    // DiscardOldestPolicy → 丢弃最老任务（可能丢失重要任务）
);
```

### 4.2 并发编程常见陷阱

| 陷阱 | 描述 | 解决方案 |
|------|------|----------|
| **死锁** | 线程互相等待对方释放锁 | 统一加锁顺序、设置超时(`tryLock`) |
| **活锁** | 线程不断重试但始终无法继续 | 随机退避 + 限制重试次数 |
| **线程饥饿** | 某些线程永远拿不到CPU时间 | 公平锁、合理设置优先级 |
| **伪共享** | CPU缓存行导致的false sharing | `@Contended`注解或填充(padding) |
| **ABA问题** | CAS中的值被改过又改回来 | `AtomicStampedReference`版本号 |
| **OOM** | 线程池无界队列导致内存溢出 | 始终使用有界队列 |

### 4.3 并发编程总结

```java
// 金句：并发编程的核心就三个字：「有序性、可见性、原子性」

// 1. 可见性 —— volatile / synchronized / Lock
// 2. 原子性 —— synchronized / Lock / CAS / 原子类
// 3. 有序性 —— volatile（禁止指令重排）/ synchronized / happens-before

// 实战检查清单：
// □ 共享变量是否有volatile保护？
// □ 复合操作(先检查后执行)是否原子？
// □ 锁的粒度是否合适（不粗不细）？
// □ 是否使用了有界队列？
// □ 异常处理后能否正确恢复？
// □ 是否有合理的超时和降级策略？
```

---

## 五、面试高频追问

**Q1: CompletableFuture的get()和join()有什么区别？**

A: 两者都会阻塞等待结果，区别在于异常处理：
- `get()` 抛出**受检查异常** `ExecutionException` 和 `InterruptedException`，调用者必须处理
- `join()` 抛出**非受检查异常** `CompletionException`，代码更简洁
- 语义相同，推荐在链式调用中使用`join()`

**Q2: 为什么DCL单例需要volatile？**

A: `instance = new DCLSingleton()` 不是原子操作，分为三步：
1. 分配内存空间
2. 初始化对象（执行构造方法）
3. 将引用指向内存地址

JVM可能**指令重排**为 1→3→2：此时`instance != null`但对象还未初始化。另一个线程在第一次检查看到非null，直接返回半初始化对象 → 灾难。`volatile`禁止这种重排。

**Q3: ForkJoinPool和ThreadPoolExecutor如何选择？**

A: 
- **ForkJoinPool**：适合**分治任务**（任务可递归分解为小任务），如并行排序、大数据计算
- **ThreadPoolExecutor**：适合**独立任务**，如Web请求处理、消息处理
- ForkJoinPool的work-stealing适合任务大小不均的场景，能更好利用CPU

---

## 六、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| CompletableFuture | 异步编排、链式调用、异常处理 | thenApply, thenCompose, allOf, exceptionally |
| ForkJoinPool | 分治+工作窃取 | RecursiveTask, Work-Stealing, commonPool |
| 生产者消费者 | BlockingQueue + 有界缓冲区 | put/take, drainTo, 背压 |
| 读写锁 | 读共享、写互斥、锁降级 | ReentrantReadWriteLock |
| DCL单例 | 双重检查+volatile+禁止指令重排 | volatile, synchronized, Holder |
| 线程池选型 | CPU密集型N+1/IO密集型2N | corePoolSize, 有界队列 |

**并发编程四大口诀：**
1. **写操作用锁保护**：所有修改共享状态的操作必须加锁或原子
2. **读操作用volatile**：共享变量的读取需volatile保证可见性
3. **资源要限流**：线程池、队列都要设置上限，防止OOM
4. **异步优先同步**：能用CompletableFuture就不用Future.get()

---

> 🎯 **下期预告**：《Java并发编程面试八股文（五）——JVM层面并发机制与高并发实战》将深入synchronized锁升级全流程、JIT编译器对并发的优化、内存屏障、以及真实高并发场景的架构设计与性能调优案例，敬请期待！
