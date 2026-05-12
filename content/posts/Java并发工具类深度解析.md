---
title: "Java 并发工具类深度解析"
date: 2026-05-12T09:45:00+08:00
draft: false
categories: ["java"]
tags: ["java", "concurrency", "countdownlatch", "cyclicbarrier", "semaphore", "completablefuture"]
---


# Java 并发工具类深度解析

> 面试高频问题：CountDownLatch 和 CyclicBarrier 的区别？Semaphore 的原理？Future 和 CompletableFuture？

## 引言

Java 并发包（java.util.concurrent）提供了丰富的并发工具类，帮助开发者高效地处理多线程协作。本文将深度解析 CountDownLatch、CyclicBarrier、Semaphore、Future/CompletableFuture 等核心工具类。

## 一、CountDownLatch

### 1.1 原理

**CountDownLatch**：倒计时计数器，让一个或多个线程等待其他线程完成操作。

```
┌──────────────────────────────────────────────────┐
│           CountDownLatch (count=3)                │
│                                                   │
│  线程 A ──countDown()──→ 3→2                     │
│  线程 B ──countDown()──→ 2→1                     │
│  线程 C ──countDown()──→ 1→0 ──→ 唤醒等待线程   │
│                                                   │
│  主线程 ──await()────────── 等待 count=0 ────→ 继续│
└──────────────────────────────────────────────────┘
```

### 1.2 基本用法

```java
// 场景：主线程等待所有子任务完成
public class CountDownLatchDemo {
    public static void main(String[] args) throws InterruptedException {
        int taskCount = 5;
        CountDownLatch latch = new CountDownLatch(taskCount);
        
        for (int i = 0; i < taskCount; i++) {
            new Thread(() -> {
                try {
                    // 执行任务
                    Thread.sleep((long) (Math.random() * 1000));
                    System.out.println(Thread.currentThread().getName() + " 完成");
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    latch.countDown();  // 计数 -1
                }
            }, "Task-" + i).start();
        }
        
        // 等待所有任务完成
        latch.await();
        System.out.println("所有任务完成，继续执行");
    }
}
```

### 1.3 超时等待

```java
// 最多等 5 秒
boolean completed = latch.await(5, TimeUnit.SECONDS);
if (!completed) {
    System.out.println("超时，部分任务未完成");
}
```

### 1.4 实际应用

**场景：并行数据加载**

```java
@Service
public class ProductDetailService {
    
    @Autowired
    private ProductService productService;
    @Autowired
    private ReviewService reviewService;
    @Autowired
    private PriceService priceService;
    
    public ProductDetail getProductDetail(Long productId) throws InterruptedException {
        CountDownLatch latch = new CountDownLatch(3);
        
        Product product = new Product();
        
        // 并行加载三个数据源
        new Thread(() -> {
            try {
                product.setInfo(productService.getInfo(productId));
            } finally {
                latch.countDown();
            }
        }).start();
        
        new Thread(() -> {
            try {
                product.setReviews(reviewService.getReviews(productId));
            } finally {
                latch.countDown();
            }
        }).start();
        
        new Thread(() -> {
            try {
                product.setPrice(priceService.getPrice(productId));
            } finally {
                latch.countDown();
            }
        }).start();
        
        latch.await();  // 等待全部完成
        return product;
    }
}
```

## 二、CyclicBarrier

### 2.1 原理

**CyclicBarrier**：循环栅栏，让一组线程互相等待，全部到达后再继续执行。

```
┌──────────────────────────────────────────────────┐
│           CyclicBarrier (parties=3)               │
│                                                   │
│  线程 A ──await()──→ 等待...                      │
│  线程 B ──await()──→ 等待...                      │
│  线程 C ──await()──→ 3个都到了 ──→ 全部继续执行  │
│                                                   │
│  可循环使用（Cyclic）                              │
└──────────────────────────────────────────────────┘
```

### 2.2 基本用法

```java
public class CyclicBarrierDemo {
    public static void main(String[] args) {
        int parties = 3;
        CyclicBarrier barrier = new CyclicBarrier(parties, () -> {
            // 所有线程到达后执行（可选的 barrierAction）
            System.out.println("所有玩家准备就绪，游戏开始！");
        });
        
        for (int i = 0; i < parties; i++) {
            new Thread(() -> {
                try {
                    System.out.println(Thread.currentThread().getName() + " 准备中...");
                    Thread.sleep((long) (Math.random() * 1000));
                    System.out.println(Thread.currentThread().getName() + " 准备完成");
                    
                    barrier.await();  // 等待其他线程
                    
                    System.out.println(Thread.currentThread().getName() + " 开始执行");
                } catch (Exception e) {
                    Thread.currentThread().interrupt();
                }
            }, "Player-" + i).start();
        }
    }
}
```

### 2.3 循环使用

```java
// CyclicBarrier 可以重复使用
CyclicBarrier barrier = new CyclicBarrier(3);

// 第一轮
barrier.await();  // 全部到达后继续

// 第二轮（自动重置）
barrier.await();  // 可以再次使用
```

### 2.4 实际应用

**场景：多阶段并行计算**

```java
public class ParallelComputation {
    private static final int PARTIES = 4;
    private static final CyclicBarrier barrier = new CyclicBarrier(PARTIES, () -> {
        System.out.println("阶段完成，汇总结果");
    });
    
    public static void main(String[] args) {
        for (int i = 0; i < PARTIES; i++) {
            new Thread(() -> {
                try {
                    // 阶段 1
                    computePhase1();
                    barrier.await();
                    
                    // 阶段 2
                    computePhase2();
                    barrier.await();
                    
                    // 阶段 3
                    computePhase3();
                    barrier.await();
                } catch (Exception e) {
                    Thread.currentThread().interrupt();
                }
            }).start();
        }
    }
}
```

## 三、CountDownLatch vs CyclicBarrier

| 特性 | CountDownLatch | CyclicBarrier |
|------|---------------|---------------|
| **计数方式** | 递减计数 | 等待线程数 |
| **可重用** | ❌ 一次性 | ✅ 可循环 |
| **等待方式** | 一个线程等 N 个 | N 个线程互相等 |
| **回调** | 无 | 支持 barrierAction |
| **异常** | 不影响其他线程 | 一个中断，全部BrokenBarrier |

**选择**：
- 主线程等待子任务完成 → CountDownLatch
- 多线程互相等待、可循环 → CyclicBarrier

## 四、Semaphore

### 4.1 原理

**Semaphore**：信号量，控制同时访问的线程数量。

```
┌──────────────────────────────────────────────────┐
│           Semaphore (permits=3)                   │
│                                                   │
│  线程 1 ──acquire()──→ 获取许可 (permits=2)      │
│  线程 2 ──acquire()──→ 获取许可 (permits=1)      │
│  线程 3 ──acquire()──→ 获取许可 (permits=0)      │
│  线程 4 ──acquire()──→ 阻塞等待...               │
│  线程 1 ──release()──→ 释放许可 (permits=1)      │
│  线程 4 ──acquire()──→ 获取许可 (permits=0) ✅   │
└──────────────────────────────────────────────────┘
```

### 4.2 基本用法

```java
public class SemaphoreDemo {
    // 限制最多 3 个线程同时访问
    private static final Semaphore semaphore = new Semaphore(3);
    
    public static void main(String[] args) {
        for (int i = 0; i < 10; i++) {
            new Thread(() -> {
                try {
                    semaphore.acquire();  // 获取许可
                    System.out.println(Thread.currentThread().getName() + " 进入");
                    Thread.sleep(2000);   // 模拟操作
                    System.out.println(Thread.currentThread().getName() + " 离开");
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                } finally {
                    semaphore.release();  // 释放许可
                }
            }, "Thread-" + i).start();
        }
    }
}
```

### 4.3 实际应用

**场景：数据库连接池**

```java
public class ConnectionPool {
    private final Semaphore semaphore;
    private final List<Connection> pool;
    
    public ConnectionPool(int poolSize) {
        this.semaphore = new Semaphore(poolSize);
        this.pool = new ArrayList<>(poolSize);
        for (int i = 0; i < poolSize; i++) {
            pool.add(createConnection());
        }
    }
    
    public Connection getConnection() throws InterruptedException {
        semaphore.acquire();  // 获取许可
        synchronized (pool) {
            return pool.remove(0);
        }
    }
    
    public void releaseConnection(Connection conn) {
        synchronized (pool) {
            pool.add(conn);
        }
        semaphore.release();  // 释放许可
    }
}
```

### 4.4 公平信号量

```java
// 公平信号量：按等待顺序获取
Semaphore fairSemaphore = new Semaphore(3, true);

// 非公平信号量（默认）
Semaphore unfairSemaphore = new Semaphore(3);
```

## 五、Exchanger

### 5.1 原理

**Exchanger**：线程间交换数据。两个线程到达交换点后互相交换数据。

```java
public class ExchangerDemo {
    private static final Exchanger<String> exchanger = new Exchanger<>();
    
    public static void main(String[] args) {
        new Thread(() -> {
            try {
                String data = "来自线程A的数据";
                String received = exchanger.exchange(data);
                System.out.println("线程A收到: " + received);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }).start();
        
        new Thread(() -> {
            try {
                String data = "来自线程B的数据";
                String received = exchanger.exchange(data);
                System.out.println("线程B收到: " + received);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }).start();
    }
}
// 输出：
// 线程A收到: 来自线程B的数据
// 线程B收到: 来自线程A的数据
```

## 六、Future 和 CompletableFuture

### 6.1 Future

```java
ExecutorService executor = Executors.newFixedThreadPool(3);

// 提交异步任务
Future<String> future = executor.submit(() -> {
    Thread.sleep(1000);
    return "任务结果";
});

// 做其他事情...

// 获取结果（阻塞）
String result = future.get();

// 超时获取
String result2 = future.get(3, TimeUnit.SECONDS);

// 检查是否完成
boolean done = future.isDone();

// 取消任务
future.cancel(true);
```

**Future 的局限性**：
- `get()` 阻塞
- 无法手动完成
- 无法链式调用
- 无法组合多个 Future

### 6.2 CompletableFuture

**创建 CompletableFuture**：

```java
// 1. supplyAsync：有返回值
CompletableFuture<String> future1 = CompletableFuture.supplyAsync(() -> {
    return "Hello";
});

// 2. runAsync：无返回值
CompletableFuture<Void> future2 = CompletableFuture.runAsync(() -> {
    System.out.println("执行任务");
});

// 3. 指定线程池
ExecutorService executor = Executors.newFixedThreadPool(5);
CompletableFuture<String> future3 = CompletableFuture.supplyAsync(() -> {
    return "Hello";
}, executor);
```

**链式调用**：

```java
CompletableFuture<String> result = CompletableFuture
    .supplyAsync(() -> "Hello")
    .thenApply(s -> s + " World")         // 转换结果
    .thenApply(String::toUpperCase)        // 再次转换
    .thenAccept(System.out::println);      // 消费结果

// thenApply:   有入参，有返回值（转换）
// thenAccept:  有入参，无返回值（消费）
// thenRun:     无入参，无返回值（执行）
```

**组合多个 CompletableFuture**：

```java
// 1. thenCompose：串联两个异步操作
CompletableFuture<String> result1 = getUserId()
    .thenCompose(userId -> getUserName(userId));

// 2. thenCombine：合并两个异步结果
CompletableFuture<String> result2 = getPrice()
    .thenCombine(getDiscount(), (price, discount) -> 
        "价格: " + price * discount);

// 3. allOf：等待所有完成
CompletableFuture<Void> all = CompletableFuture.allOf(future1, future2, future3);
all.join();  // 等待全部完成

// 4. anyOf：任一完成
CompletableFuture<Object> any = CompletableFuture.anyOf(future1, future2, future3);
Object result = any.join();  // 最先完成的结果
```

**异常处理**：

```java
CompletableFuture<String> result = CompletableFuture
    .supplyAsync(() -> {
        if (true) throw new RuntimeException("出错了");
        return "OK";
    })
    .exceptionally(ex -> "默认值")          // 异常时返回默认值
    .handle((result, ex) -> {               // 处理结果或异常
        if (ex != null) return "错误: " + ex.getMessage();
        return result;
    });
```

### 6.3 实际应用

**场景：电商商品详情页并行加载**

```java
@Service
public class ProductDetailService {
    
    public ProductDetail getProductDetail(Long productId) {
        // 并行加载
        CompletableFuture<ProductInfo> infoFuture = CompletableFuture
            .supplyAsync(() -> productService.getInfo(productId));
        
        CompletableFuture<List<Review>> reviewFuture = CompletableFuture
            .supplyAsync(() -> reviewService.getReviews(productId));
        
        CompletableFuture<Price> priceFuture = CompletableFuture
            .supplyAsync(() -> priceService.getPrice(productId));
        
        // 等待全部完成并组装
        try {
            return CompletableFuture.allOf(infoFuture, reviewFuture, priceFuture)
                .thenApply(v -> new ProductDetail(
                    infoFuture.join(),
                    reviewFuture.join(),
                    priceFuture.join()
                ))
                .get(5, TimeUnit.SECONDS);  // 最多等5秒
        } catch (Exception e) {
            throw new RuntimeException("加载商品详情失败", e);
        }
    }
}
```

## 七、面试高频问题

### Q1：CountDownLatch 和 CyclicBarrier 的区别？

**答**：
| 特性 | CountDownLatch | CyclicBarrier |
|------|---------------|---------------|
| 计数方式 | 递减 | 等待线程数 |
| 可重用 | ❌ | ✅ |
| 等待方式 | 一个等 N 个 | N 个互相等 |
| 回调 | 无 | barrierAction |

### Q2：Semaphore 的原理？

**答**：
- 基于 AQS 实现
- `acquire()` 获取许可（permits - 1）
- `release()` 释放许可（permits + 1）
- permits 为 0 时阻塞等待

### Q3：CompletableFuture 和 Future 的区别？

**答**：
| 特性 | Future | CompletableFuture |
|------|--------|-------------------|
| 链式调用 | ❌ | ✅ |
| 组合 | ❌ | ✅ allOf/anyOf |
| 异常处理 | ❌ | ✅ exceptionally/handle |
| 手动完成 | ❌ | ✅ complete() |
| 非阻塞 | ❌ | ✅ 回调式 |

### Q4：CountDownLatch 的实际应用？

**答**：
- 主线程等待多个子任务完成
- 并行数据加载后汇总
- 多服务健康检查

### Q5：Semaphore 的实际应用？

**答**：
- 限流（接口限流）
- 数据库连接池
- 资源池

## 八、总结

**并发工具类核心要点**：

| 工具类 | 用途 |
|--------|------|
| CountDownLatch | 一个线程等待 N 个线程完成 |
| CyclicBarrier | N 个线程互相等待 |
| Semaphore | 控制并发访问数量 |
| Exchanger | 两个线程交换数据 |
| CompletableFuture | 异步编程（链式、组合、异常处理）|

**最佳实践**：
1. CountDownLatch 用于"等待完成"，CyclicBarrier 用于"同步屏障"
2. Semaphore 用于限流和资源池
3. 优先使用 CompletableFuture 替代 Future
4. 注意异常处理（`exceptionally`/`handle`）
5. 指定合适的线程池（避免使用 ForkJoinPool.commonPool）

---

**下一篇预告**：JVM 内存模型（JMM）深度解析 —— 可见性、原子性、有序性

**参考资料**：
- 《Java 并发编程的艺术》- 方腾飞
- 《Java 并发编程实战》- Brian Goetz
- JDK 源码：java.util.concurrent
