---
title: Java并发编程面试八股文（六）——综合面试题与实战
date: 2026-07-25 10:00:00+08:00
updated: '2026-07-25T10:00:00+08:00'
description: 面试高频问题：如何设计一个高并发系统？线程池参数如何调优？synchronized 和 ReentrantLock 怎么选？本文整合 Java 并发编程前五篇的全部核心知识点，以场景化面试题的形式，系统梳理线程安全、并发工具、性能调优等高频考点，带你完成从"懂原理"到"能实战"的跨越。
topic: java-spring
series: system-design
series_order: 6
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Java
- 并发
- 综合实战
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：如何设计一个高并发系统？线程池参数如何调优？synchronized 和 ReentrantLock 怎么选？本文整合 Java 并发编程前五篇的全部核心知识点，以场景化面试题的形式，系统梳理线程安全、并发工具、性能调优等高频考点，带你完成从"懂原理"到"能实战"的跨越。

---

## 一、线程安全基础：synchronized 深度辨析

### 1.1 synchronized 的底层原理

`synchronized` 是 Java 中最基础的同步关键字，其底层实现经历了从 JDK 1.6 之前的「重量级锁」到 JDK 1.6 引入「偏向锁/轻量级锁/重量级锁」升级的过程：

```java
public class SyncDemo {
    private int count = 0;

    // 同步实例方法——锁对象 this
    public synchronized void increment() {
        count++;
    }

    // 同步静态方法——锁 Class 对象
    public static synchronized void staticIncrement() {
        // ...
    }

    // 同步代码块——显式指定锁对象
    public void blockIncrement() {
        synchronized (this) {
            count++;
        }
    }
}
```

**面试追问 1：synchronized 和 ReentrantLock 有什么区别？**

| 对比维度 | synchronized | ReentrantLock |
|---------|-------------|---------------|
| 锁类型 | 非公平锁（JDK 1.6+ 支持偏向锁） | 支持公平/非公平（构造参数决定） |
| 等待可中断 | 不可中断 | 可中断（`lockInterruptibly()`） |
| 锁超时 | 不支持 | 支持（`tryLock(time, unit)`） |
| 多条件等待 | 不能精确唤醒 | 可绑定多个 `Condition` |
| 手动释放 | 自动释放 | 必须 `unlock()` 手动释放 |
| 锁粒度 | 方法级/代码块级 | 代码块级（更灵活） |

**面试追问 2：为什么 synchronized 效率不断提升？**

- **偏向锁**：在无竞争场景下，第一次获取锁的线程记录在对象头中，后续该线程进入同步块无需任何同步开销。
- **轻量级锁**：当另一个线程尝试获取锁时，JVM 使用 CAS 将锁对象头的 Mark Word 复制到线程栈帧的锁记录中，如果复制成功则获得锁（自旋等待）。
- **自旋锁**：轻量级锁膨胀前，线程会进行有限次自旋（默认 10 次），避免线程切换开销。
- **锁消除**：JIT 编译器在逃逸分析后发现对象不会逃逸出线程，移除不必要的同步。

### 1.2 volatile 的双重语义

`volatile` 只能保证**可见性**，不能保证原子性。其核心机制是通过「内存屏障（Memory Barrier）」实现的：

```java
public class VolatileDemo {
    private volatile boolean flag = false;

    // 线程 A 执行
    public void writer() {
        flag = true;  // 写操作后，强制刷主内存
    }

    // 线程 B 执行
    public void reader() {
        if (flag) {    // 读操作前，强制读主内存
            // 一定能看到 A 的写入
        }
    }
}
```

**适用场景**：一个线程写、多个线程读的场景（如状态标记、配置刷新）。不适合复合操作（`count++`）。

---

## 二、线程池：参数调优与实战策略

### 2.1 线程池核心参数

```java
public ThreadPoolExecutor(
    int corePoolSize,          // 核心线程数
    int maximumPoolSize,        // 最大线程数
    long keepAliveTime,         // 空闲线程存活时间
    TimeUnit unit,              // 时间单位
    BlockingQueue<Runnable> workQueue,  // 任务队列
    ThreadFactory threadFactory, // 线程工厂
    RejectedExecutionHandler handler    // 拒绝策略
)
```

**线程池执行流程**：

1. 线程数 < corePoolSize → 创建核心线程执行任务
2. 线程数 = corePoolSize，队列未满 → 任务入队等待
3. 队列满，线程数 < maximumPoolSize → 创建临时线程执行
4. 线程数 = maximumPoolSize，队列满 → 执行拒绝策略

### 2.2 线程池选择策略

```java
// CPU 密集型：核心线程数 = CPU 核心数 + 1
int cpuCores = Runtime.getRuntime().availableProcessors();
ExecutorService cpuPool = new ThreadPoolExecutor(
    cpuCores + 1, cpuCores + 1,
    0L, TimeUnit.MILLISECONDS,
    new LinkedBlockingQueue<>(100)
);

// IO 密集型：核心线程数 = CPU 核心数 * 2（或根据 IO 等待比调整）
ExecutorService ioPool = new ThreadPoolExecutor(
    cpuCores * 2, cpuCores * 2,
    60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(200)
);

// 推荐使用：阿里巴巴规范强制要求使用 ThreadPoolExecutor，而非 Executors
```

**阿里巴巴 Java 规范警示**：`Executors` 提供的 `newFixedThreadPool`（无限队列 OOM）和 `newCachedThreadPool`（无限线程 OOM）均存在风险，必须使用 `ThreadPoolExecutor` 显式配置参数。

### 2.3 拒绝策略对比

| 策略 | 行为 | 适用场景 |
|-----|------|---------|
| AbortPolicy（默认） | 抛出 `RejectedExecutionException` | 核心业务，不允许丢任务 |
| CallerRunsPolicy | 由调用方线程执行任务 | 流量削峰，保护自身 |
| DiscardPolicy | 直接丢弃，不抛异常 | 无关紧要的任务 |
| DiscardOldestPolicy | 丢弃队列最旧的任务 | 优先级场景 |

---

## 三、JUC 并发工具实战场景

### 3.1 CountDownLatch：等待一组操作完成

```java
public class MultiSystemInit {
    public static void main(String[] args) throws InterruptedException {
        int systemCount = 3;
        CountDownLatch latch = new CountDownLatch(systemCount);

        // 并行启动三个初始化任务
        new Thread(() -> { dbInit(); latch.countDown(); }, "DB-Init").start();
        new Thread(() -> { cacheInit(); latch.countDown(); }, "Cache-Init").start();
        new Thread(() -> { configInit(); latch.countDown(); }, "Config-Init").start();

        // 等待所有系统初始化完成
        latch.await(30, TimeUnit.SECONDS);
        System.out.println("所有系统初始化完成，启动应用...");
    }
}
```

**常见面试追问**：CountDownLatch 和 CyclicBarrier 的区别是什么？

- **CountDownLatch**：计数器只能减，不能重置；await 等待计数归零后不可复用。
- **CyclicBarrier**：计数器归零后重置为初始值，可以复用；适合多线程相互等待。

### 3.2 Semaphore：限流控制

```java
public class RateLimiter {
    private final Semaphore permits;

    public RateLimiter(int maxConcurrent) {
        this.permits = new Semaphore(maxConcurrent);
    }

    public void acquire() throws InterruptedException {
        permits.acquire();
        try {
            // 执行业务逻辑
            doBusiness();
        } finally {
            permits.release();
        }
    }

    // 非阻塞限流
    public boolean tryAcquire(long timeoutMs) throws InterruptedException {
        return permits.tryAcquire(timeoutMs, TimeUnit.MILLISECONDS);
    }
}
```

**典型场景**：数据库连接池限流（连接数固定）、API 接口并发限流、秒杀系统入口限流。

### 3.3 CompletableFuture：异步编排

```java
public class AsyncService {
    private final ExecutorService executor = Executors.newFixedThreadPool(10);

    public CompletableFuture<String> getUserInfo(Long userId) {
        return CompletableFuture.supplyAsync(() -> {
            // 模拟查询数据库
            return queryFromDB(userId);
        }, executor);
    }

    // thenApply：异步结果转换
    public CompletableFuture<String> enrichUser(String userId) {
        return getUserInfo(1L)
            .thenApply(user -> enrich(user))      // 继续处理
            .thenCompose(user -> getPermission(user)) // flatMap：返回另一个 Future
            .exceptionally(ex -> {                 // 异常处理
                log.error("获取用户信息失败", ex);
                return "GUEST";
            });
    }

    // 并行执行多个 Future
    public CompletableFuture<User> aggregateUser(Long userId) {
        CompletableFuture<User> userFuture = getUserInfo(userId);
        CompletableFuture<List<Order>> orderFuture = getOrders(userId);
        CompletableFuture<Permission> permFuture = getPermission(userId);

        return CompletableFuture.allOf(userFuture, orderFuture, permFuture)
            .thenApply(v -> {
                User user = userFuture.join();
                user.setOrders(orderFuture.join());
                user.setPermission(permFuture.join());
                return user;
            });
    }
}
```

---

## 四、高并发设计模式与实战

### 4.1 单例模式的线程安全写法

```java
// 方案一：饿汉式（类加载时即创建，无线程安全问题，但浪费资源）
public class HungrySingleton {
    private static final HungrySingleton INSTANCE = new HungrySingleton();
    private HungrySingleton() {}
    public static HungrySingleton getInstance() { return INSTANCE; }
}

// 方案二：懒汉式 + DCL（双重检查锁定）
public class LazySingleton {
    private static volatile LazySingleton instance;  // volatile 必须加！
    private LazySingleton() {}

    public static LazySingleton getInstance() {
        if (instance == null) {               // 第一次检查：减少加锁开销
            synchronized (LazySingleton.class) {
                if (instance == null) {       // 第二次检查：防止重复创建
                    instance = new LazySingleton();
                    // 字节码层面实际分为三步：
                    // 1. 分配内存  2. 初始化对象  3. 赋值给引用
                    // volatile 防止指令重排序，保证 1-2-3 顺序执行
                }
            }
        }
        return instance;
    }
}

// 方案三：静态内部类（推荐，JVM 保证线程安全）
public class InnerClassSingleton {
    private InnerClassSingleton() {}

    private static class Holder {
        private static final InnerClassSingleton INSTANCE = new InnerClassSingleton();
    }

    public static InnerClassSingleton getInstance() {
        return Holder.INSTANCE;  // 第一次加载 Holder 时创建，无懒加载问题
    }
}
```

### 4.2 生产者-消费者模式

```java
public class ProducerConsumer {
    private final BlockingQueue<Integer> queue = new LinkedBlockingQueue<>(100);

    // 生产者
    public void produce(int taskId) {
        try {
            queue.put(taskId);  // 队列满则阻塞
            System.out.println("生产: " + taskId);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    // 消费者
    public void consume() {
        try {
            Integer task = queue.take();  // 队列空则阻塞
            System.out.println("消费: " + task);
            process(task);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    public void process(Integer task) { /* 业务处理 */ }
}
```

### 4.3 读多写少场景：ReentrantReadWriteLock

```java
public class CacheService {
    private final Map<String, Object> cache = new HashMap<>();
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();

    // 读操作：允许多线程并发读
    public Object get(String key) {
        rwLock.readLock().lock();
        try {
            return cache.get(key);
        } finally {
            rwLock.readLock().unlock();
        }
    }

    // 写操作：独占锁，同一时间只允许一个线程写
    public void put(String key, Object value) {
        rwLock.writeLock().lock();
        try {
            cache.put(key, value);
        } finally {
            rwLock.writeLock().unlock();
        }
    }
}
```

**注意**：ReentrantReadWriteLock 支持锁降级（写锁→读锁），但不支持锁升级（读锁→写锁，会导致死锁）。

---

## 五、线程安全与并发容器

### 5.1 ConcurrentHashMap vs Hashtable vs Collections.synchronizedMap

```java
// Hashtable：全局锁，并发性能差
Hashtable<String, Object> hashTable = new Hashtable<>();

// Collections.synchronizedMap：全局锁，效率低
Map<String, Object> syncMap = Collections.synchronizedMap(new HashMap<>());

// ConcurrentHashMap：分段锁（JDK 1.7）/ CAS + synchronized（JDK 1.8+）
ConcurrentHashMap<String, Object> concurrentMap = new ConcurrentHashMap<>();

// JDK 1.8+ 核心改进：数组 + 链表/红黑树，使用 CAS 和 synchronized
// putIfAbsent / computeIfAbsent / merge 等原子操作方法
concurrentMap.putIfAbsent("key", "value");
```

### 5.2 并发容器选择决策树

```
需要线程安全容器？
├── 只需要安全发布（可见性）→ volatile + 普通容器
├── 需要原子计数器 → Atomic* 类（AtomicInteger/LongAdder）
├── 需要高效并发读写 → ConcurrentHashMap
├── 需要阻塞读取/写入 → BlockingQueue（ArrayBlockingQueue/LinkedBlockingQueue）
├── 需要按 key 分组 → ConcurrentHashMap<String, List<T>> / ConcurrentSkipListMap
└── 需要高并发无序遍历 → ConcurrentLinkedQueue / ConcurrentLinkedDeque
```

### 5.3 LongAdder vs AtomicLong

```java
// AtomicLong：竞争激烈时 CAS 自旋开销大
AtomicLong counter = new AtomicLong(0);
counter.incrementAndGet();  // 高并发下大量线程竞争同一地址

// LongAdder：分段计数，减少 CAS 冲突
LongAdder longAdder = new LongAdder();
longAdder.increment();  // 分散到不同 cell，减少冲突

// LongAdder 适用场景：计数器累加（如接口访问量）
// AtomicLong 适用场景：需要强一致性保证（如库存扣减）
```

---

## 六、综合实战：设计一个线程安全的订单服务

### 6.1 需求分析

设计一个高并发电商订单服务，需要满足：

- 支持多线程并发下单
- 库存扣减不能超卖
- 订单号全局唯一
- 下单失败时库存回滚
- 支持异步通知下游系统

### 6.2 核心实现

```java
@Service
public class OrderService {
    private final ConcurrentHashMap<Long, ReentrantReadWriteLock> orderLocks = new ConcurrentHashMap<>();
    private final BlockingQueue<OrderMessage> orderQueue = new LinkedBlockingQueue<>(10000);

    @Autowired private InventoryService inventoryService;
    @Autowired private PaymentService paymentService;

    public Order createOrder(OrderRequest request) throws Exception {
        // 1. 幂等检查：防止重复下单
        if (checkDuplicate(request.getRequestId())) {
            throw new BizException("重复请求");
        }

        // 2. 获取商品库存（乐观锁）
        Stock stock = inventoryService.getStock(request.getProductId());
        if (stock.getQuantity() < request.getQuantity()) {
            throw new BizException("库存不足");
        }

        // 3. 扣减库存（使用乐观锁 CAS）
        boolean deducted = inventoryService.deductStock(
            request.getProductId(),
            request.getQuantity(),
            stock.getVersion()
        );
        if (!deducted) {
            throw new BizException("库存扣减失败，请重试");
        }

        try {
            // 4. 创建订单
            Order order = new Order();
            order.setOrderNo(generateOrderNo());
            order.setProductId(request.getProductId());
            order.setQuantity(request.getQuantity());
            order.setAmount(calculateAmount(request));
            order.setStatus(OrderStatus.PENDING);

            order = orderRepository.save(order);

            // 5. 异步通知下游（不阻塞主流程）
            CompletableFuture.runAsync(() -> notifyDownstream(order));

            return order;
        } catch (Exception e) {
            // 6. 失败时回滚库存
            inventoryService.rollbackStock(request.getProductId(), request.getQuantity());
            throw e;
        }
    }

    // 乐观锁 CAS 扣减库存
    public boolean deductStock(Long productId, int quantity, Long version) {
        String sql = "UPDATE stock SET quantity = quantity - ?, version = version + 1 " +
                     "WHERE product_id = ? AND version = ? AND quantity >= ?";
        int rows = jdbcTemplate.update(sql, quantity, productId, version, quantity);
        return rows > 0;
    }

    // 生成唯一订单号（时间戳 + 机器ID + 序列号）
    private String generateOrderNo() {
        return String.format("%s%02d%010d",
            LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss")),
            1,  // 机器ID
            orderSequence.incrementAndGet()
        );
    }
}
```

### 6.3 面试总结：订单服务并发安全要点

| 问题 | 解决方案 |
|-----|---------|
| 超卖 | 乐观锁（CAS + version） + 数据库唯一约束 |
| 重复下单 | 请求幂等号（requestId） + Redis 去重 |
| 死锁 | 按固定顺序获取锁，避免交叉依赖 |
| 库存回滚 | try-catch 包裹，finally 或 catch 中回滚 |
| 订单号重复 | 时间戳 + 机器ID + 原子序列号 |
| 下游系统失败 | 异步通知 + 消息队列 + 重试机制 |

---

## 七、常见面试陷阱题

### 陷阱题 1：以下代码输出什么？

```java
public class SyncTrap {
    public synchronized void a() {
        System.out.println("a");
        try { Thread.sleep(1000); } catch (InterruptedException e) {}
    }

    public synchronized void b() {
        System.out.println("b");
        try { Thread.sleep(1000); } catch (InterruptedException e) {}
    }

    public static void main(String[] args) {
        SyncTrap t = new SyncTrap();
        new Thread(t::a).start();
        new Thread(t::b).start();
    }
}
```

**答案**：`a` 和 `b` 按顺序输出。`a` 先拿到 `this` 锁并持有 1 秒，期间 `b` 在锁上阻塞，`a` 释放锁后 `b` 才能进入。**线程安全，串行执行。**

### 陷阱题 2：下面的 `list` 是线程安全的吗？

```java
List<String> list = new ArrayList<>();
list.add("a");
list.get(0);
```

**答案**：不是。`ArrayList` 本身不是线程安全的，但这段代码在没有并发访问的情况下不会出现数据错误。"线程安全"指的是**并发场景下**的正确性。单个线程操作 `ArrayList` 不需要加锁。

### 陷阱题 3：volatile 能保证原子性吗？

```java
private volatile int count = 0;

public void increment() {
    count++;  // 看似一行，实际是三条字节码指令：
              // 1. getstatic 读取
              // 2. iconst_1 + iadd  加1
              // 3. putstatic 写回
              // volatile 只保证可见性，不保证原子性！
}
```

**答案**：不能。`count++` 是复合操作，需要用 `synchronized` 或 `AtomicInteger`。

---

## 下期预告

Java 并发编程系列到此告一段落。从线程基础、锁机制、JUC 工具类、并发容器、线程池到综合实战，我们覆盖了 Java 并发编程的全景知识图谱。下期开始，我们把目光转向另一个面试高频领域——**JVM 调优与故障排查**系列，详解 JVM 内存模型、GC 算法、垃圾收集器选型、 Arthas 实战诊断以及线上 OOM 问题排查，让你在 JVM 层面真正"看得清、调得动"。

敬请期待：**JVM 调优实战（一）——内存模型与 GC 算法深度解析**

---

*系列导航：*
- *（一）线程基础与锁机制*
- *（二）JUC 并发工具类与线程池*
- *（三）并发容器深入与实战案例*
- *（四）异步编程与并发设计模式*
- *（五）JVM 层面并发机制与高并发实战*
- ***（六）综合面试题与实战*** ← 当前
