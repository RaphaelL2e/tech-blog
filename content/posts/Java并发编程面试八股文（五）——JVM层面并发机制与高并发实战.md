---
title: "Java并发编程面试八股文（五）——JVM层面并发机制与高并发实战"
date: 2026-06-17T09:00:00+08:00
draft: false
categories: ["java"]
tags: ["面试", "八股文", "Java", "并发", "JVM", "synchronized锁升级", "内存屏障", "JIT", "高并发", "性能调优"]
---

# Java并发编程面试八股文（五）——JVM层面并发机制与高并发实战

> 面试高频问题：synchronized锁升级全过程是怎样的？偏向锁什么时候失效？什么是内存屏障？JIT编译器如何影响并发？高并发场景下如何做架构设计？本文带你从JVM层面深入理解并发机制，并掌握高并发系统的实战设计方法。

---

## 一、synchronized锁升级全流程

### 1.1 锁的四种状态

**Q: synchronized锁升级的全过程是怎样的？**

JDK6之后，synchronized引入了锁升级机制，锁状态从低到高依次为：

| 锁状态 | 存储内容 | 适用场景 | 开销 |
|--------|----------|----------|------|
| 无锁 | 无 | 无竞争 | 无 |
| 偏向锁 | 线程ID | 只有一个线程访问 | 极低 |
| 轻量级锁 | 指向栈中Lock Record的指针 | 交替访问、竞争不激烈 | CAS自旋 |
| 重量级锁 | 指向Monitor对象的指针 | 高竞争 | 系统调用、线程阻塞 |

**锁升级路径：无锁 → 偏向锁 → 轻量级锁 → 重量级锁（单向不可逆）**

```java
// 查看对象头：Mark Word的锁状态
// 使用JOL (Java Object Layout) 打印内存布局
import org.openjdk.jol.info.ClassLayout;

Object obj = new Object();
System.out.println(ClassLayout.parseInstance(obj).toPrintable());
// 输出：偏向锁未启用时默认无锁态（001）
```

### 1.2 偏向锁（Biased Locking）

**Q: 偏向锁的原理是什么？什么时候会被撤销？**

偏向锁的核心思想：**如果一个线程获取了锁，那么锁就进入偏向模式**。当这个线程再次请求锁时，无需任何同步操作，直接进入。

**偏向锁的获取流程：**
1. 检查Mark Word的偏向锁标志位（101）
2. 如果偏向模式且Thread ID匹配当前线程 → 直接获取，零开销
3. 如果Thread ID不匹配 → CAS竞争，竞争成功则修改Thread ID
4. CAS失败 → 到达安全点，撤销偏向锁，升级为轻量级锁

**偏向锁撤销的触发条件：**
- 另一个线程尝试获取锁（发生竞争）
- 调用`Object.hashCode()`（偏向锁状态下无法存储hashCode）
- 调用`System.identityHashCode()`
- 调用偏向锁撤销的JVM参数

```java
// 偏向锁延迟参数
// -XX:BiasedLockingStartupDelay=0  // 取消偏向锁启动延迟
// -XX:-UseBiasedLocking           // 关闭偏向锁
```

> **注意**：JDK15默认关闭了偏向锁，JDK18+已废弃偏向锁。原因是高并发场景下偏向锁撤销的开销超过了其带来的收益。

### 1.3 轻量级锁（Lightweight Locking）

**Q: 轻量级锁的工作原理是什么？**

轻量级锁采用**CAS + 自旋**的方式，不涉及操作系统层面的线程阻塞。

**获取流程：**
1. 在当前线程栈帧中创建Lock Record
2. 将对象头的Mark Word复制到Lock Record中（Displaced Mark Word）
3. CAS尝试将对象头的Mark Word替换为指向Lock Record的指针
4. CAS成功 → 获取轻量级锁
5. CAS失败 → 自旋等待（自适应自旋）

**释放流程：**
1. 将Lock Record中的Displaced Mark Word通过CAS写回对象头
2. CAS成功 → 释放成功
3. CAS失败 → 说明有其他线程在竞争，升级为重量级锁

```java
// 轻量级锁的自旋参数
// -XX:PreBlockSpin=10          // 自旋次数（JDK6之前）
// JDK6之后引入自适应自旋，JVM根据历史自旋成功率动态调整
```

### 1.4 重量级锁（Heavyweight Locking）

**Q: 什么时候升级为重量级锁？Monitor对象是什么？**

当自旋等待超过一定次数或等待线程数超过阈值时，轻量级锁膨胀为重量级锁。

**Monitor对象结构：**
- **Entry Set**：等待获取锁的线程集合
- **Wait Set**：调用了`wait()`后等待唤醒的线程集合
- **Owner**：当前持有锁的线程

```java
// 重量级锁涉及内核态切换
// 每个Java对象关联一个ObjectMonitor（C++层面）
// 对象头存储指向ObjectMonitor的指针
```

**重量级锁操作流程：**
1. 未获取到锁的线程进入Entry Set，被阻塞（BLOCKED状态）
2. Owner线程调用`wait()`，释放锁，进入Wait Set（WAITING状态）
3. 其他线程调用`notify()/notifyAll()`，Wait Set中的线程移到Entry Set
4. Entry Set中的线程竞争获取Monitor

### 1.5 锁升级实战案例

```java
// 模拟锁升级场景
public class LockUpgradeDemo {
    private static final Object lock = new Object();
    
    public static void main(String[] args) throws Exception {
        // 阶段1：偏向锁
        synchronized (lock) {
            System.out.println("偏向锁: " + ClassLayout.parseInstance(lock).toPrintable());
        }
        
        // 阶段2：轻量级锁（交替竞争）
        Thread t1 = new Thread(() -> {
            synchronized (lock) {
                System.out.println("轻量级锁: " + ClassLayout.parseInstance(lock).toPrintable());
            }
        });
        t1.start();
        t1.join();
        
        // 阶段3：重量级锁（激烈竞争）
        for (int i = 0; i < 3; i++) {
            new Thread(() -> {
                synchronized (lock) {
                    System.out.println("重量级锁: " + ClassLayout.parseInstance(lock).toPrintable());
                }
            }).start();
        }
        Thread.sleep(1000);
    }
}
```

---

## 二、volatile与内存屏障

### 2.1 volatile的底层实现

**Q: volatile变量读写时JVM做了什么？**

volatile通过**内存屏障（Memory Barrier）**实现可见性和有序性。

| 操作 | 插入的屏障 | 作用 |
|------|-----------|------|
| volatile写 | StoreStore + StoreLoad | 禁止写与之前/之后的读写重排序 |
| volatile读 | LoadLoad + LoadStore | 禁止读与之后/之前的读写重排序 |

**JMM内存屏障分类：**

```
LoadLoad屏障：   Load1; LoadLoad; Load2  → 确保Load1在Load2之前完成
StoreStore屏障： Store1; StoreStore; Store2 → 确保Store1在Store2之前完成
LoadStore屏障：  Load1; LoadStore; Store1 → 确保Load1在Store1之前完成
StoreLoad屏障：  Store1; StoreLoad; Load1 → 确保Store1在Load1之前完成（最重）
```

### 2.2 硬件层面的内存屏障

**Q: 不同CPU架构如何实现内存屏障？**

| 架构 | LoadLoad | StoreStore | LoadStore | StoreLoad |
|------|----------|------------|-----------|-----------|
| x86 | 无需 | 无需 | 无需 | mfence/lock |
| ARM | dmb | dmb st | dmb | dmb/dsb |

> x86是**强内存模型（TSO）**，只允许Store-Load重排序，因此只有StoreLoad需要显式屏障。ARM是弱内存模型，四种屏障都需要。

### 2.3 DCL单例为什么要volatile

```java
public class Singleton {
    // 必须加volatile：禁止指令重排序
    private static volatile Singleton instance;
    
    public static Singleton getInstance() {
        if (instance == null) {                 // 第一次检查
            synchronized (Singleton.class) {
                if (instance == null) {         // 第二次检查
                    instance = new Singleton();  // 可能发生指令重排！
                    // 1. 分配内存空间
                    // 2. 初始化对象 ← 可能重排到3之后
                    // 3. instance指向内存空间 ← 可能重排到2之前
                }
            }
        }
        return instance;
    }
}
```

**不加volatile的问题：**
- 线程A执行`new Singleton()`，先执行步骤3（赋值引用），再执行步骤2（初始化）
- 线程B在第一次检查时发现`instance != null`，直接返回
- 线程B获取到的对象尚未初始化完成 → **拿到半成品对象**

### 2.4 happens-before规则总结

| 规则 | 说明 |
|------|------|
| 程序次序规则 | 同一线程内，前面的操作happens-before后面的操作 |
| volatile变量规则 | volatile写happens-before volatile读 |
| 锁规则 | unlock happens-before lock |
| 传递性 | A hb B, B hb C → A hb C |
| 线程启动规则 | start() hb 线程内所有操作 |
| 线程终止规则 | 线程所有操作 hb join()返回 |
| 线程中断规则 | interrupt() hb 被中断线程检测到中断 |
| 对象终结规则 | 构造函数结束 hb finalize() |

---

## 三、JIT编译器对并发的影响

### 3.1 JIT优化技术

**Q: JIT编译做了哪些可能影响并发的优化？**

JIT（Just-In-Time）编译器在运行时将热点代码编译为本地机器码，其优化可能改变代码执行顺序：

| 优化技术 | 描述 | 并发影响 |
|----------|------|----------|
| 逃逸分析 | 分析对象作用域，栈上分配 | 消除不必要的同步 |
| 锁消除 | 消除不可能存在竞争的锁 | 提升性能 |
| 锁粗化 | 合并相邻的加锁/解锁操作 | 减少锁开销 |
| 标量替换 | 将对象拆分为基本类型 | 减少堆分配 |
| 内联展开 | 将方法调用替换为方法体 | 改变执行路径 |

### 3.2 锁消除（Lock Elision）

```java
// JIT可能消除这种无意义的锁
public String concat(String s1, String s2) {
    // StringBuffer是线程安全的，但这里是局部变量
    // 不可能被其他线程访问 → JIT会消除synchronized
    StringBuffer sb = new StringBuffer();
    sb.append(s1);
    sb.append(s2);
    return sb.toString();
}

// 编译参数：-XX:+EliminateLocks  (默认开启)
```

### 3.3 锁粗化（Lock Coarsening）

```java
// 原始代码：频繁加锁解锁
public void process() {
    for (int i = 0; i < 100; i++) {
        synchronized (this) {  // 每次循环都加锁
            doSomething(i);
        }
    }
}

// JIT优化后：将锁范围扩大（锁粗化）
public void process() {
    synchronized (this) {      // 只加一次锁
        for (int i = 0; i < 100; i++) {
            doSomething(i);
        }
    }
}
```

### 3.4 逃逸分析（Escape Analysis）

```java
// 对象不逃逸 → 栈上分配 + 锁消除
public int calculate() {
    // cal对象不会逃逸出calculate方法
    Calculator cal = new Calculator();
    synchronized (cal) {
        return cal.compute();
    }
}
// JIT：1. 栈上分配cal对象（不分配在堆上）
//      2. 消除synchronized（无竞争可能）

// 编译参数：
// -XX:+DoEscapeAnalysis  (默认开启)
// -XX:+EliminateAllocations  (配合Tiered Compilation)
```

### 3.5 分层编译与并发性能

**C1 vs C2编译器：**

| 编译器 | 特点 | 启动速度 | 峰值性能 | 优化程度 |
|--------|------|----------|----------|----------|
| C1（Client） | 快速编译，简单优化 | 快 | 低 | 低 |
| C2（Server） | 深度优化，激进内联 | 慢 | 高 | 高 |

JDK8+默认开启分层编译：先用C1快速编译，热点代码升级到C2深度优化。

```bash
# 查看编译情况
java -XX:+PrintCompilation MyApp

# 禁用分层编译
java -XX:-TieredCompilation MyApp
```

---

## 四、高并发系统架构设计

### 4.1 高并发系统设计原则

**Q: 设计高并发系统需要遵循哪些原则？**

| 原则 | 说明 | 技术手段 |
|------|------|----------|
| 无状态化 | 服务节点不存储会话状态 | Token/JWT, 分布式Session |
| 异步化 | 非核心流程异步处理 | MQ, CompletableFuture, 事件驱动 |
| 缓存化 | 多级缓存减少DB压力 | 本地缓存, Redis, CDN |
| 分库分表 | 水平拆分降低单库压力 | ShardingSphere, MyCat |
| 读写分离 | 读多写少场景优化 | MySQL主从, Redis Cluster |
| 限流降级 | 保护系统不过载 | Sentinel, Hystrix, RateLimiter |
| 削峰填谷 | 平滑流量冲击 | MQ消峰, 排队, 预热 |

### 4.2 秒杀系统架构设计

**Q: 如何设计一个秒杀系统？**

```
                        ┌─────────────┐
                        │   CDN/静态化  │ ← 秒杀页面静态化
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   网关层     │ ← 限流、验证码、IP黑名单
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   业务层     │ ← Redis预减库存，异步下单
                        └──────┬──────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
              ┌─────▼──┐ ┌───▼───┐ ┌───▼────┐
              │ Redis  │ │  MQ   │ │ MySQL  │
              │ 库存   │ │ 削峰  │ │ 兜底   │
              └─────────┘ └───────┘ └────────┘
```

**核心流程：**
1. **前端限流**：按钮置灰、验证码、答题
2. **网关限流**：令牌桶/漏桶，拒绝超出QPS的请求
3. **Redis预减库存**：`decr`原子操作，减到0直接拒绝
4. **MQ异步下单**：抢购成功的请求进入MQ队列
5. **DB异步写入**：消费MQ消息，写入订单表
6. **定时对账**：Redis与DB库存对账，防止超卖

```java
// Redis预减库存
public boolean deductStock(String productId) {
    String key = "stock:" + productId;
    // Lua脚本保证原子性
    String script = """
        local stock = redis.call('get', KEYS[1])
        if stock and tonumber(stock) > 0 then
            redis.call('decr', KEYS[1])
            return 1
        end
        return 0
        """;
    Long result = redisTemplate.execute(
        new DefaultRedisScript<>(script, Long.class), 
        Collections.singletonList(key));
    return result == 1;
}
```

### 4.3 高并发场景下的缓存策略

| 策略 | 描述 | 适用场景 | 注意事项 |
|------|------|----------|----------|
| 缓存预热 | 启动时加载热点数据到缓存 | 秒杀、大促 | 避免冷启动击穿 |
| 缓存穿透 | 查询不存在的数据穿透到DB | 恶意攻击 | 布隆过滤器或缓存空值 |
| 缓存击穿 | 热点key过期瞬间大量请求打DB | 热点商品 | 互斥锁或永不过期 |
| 缓存雪崩 | 大量key同时过期 | 批量缓存 | 过期时间加随机值、多级缓存 |
| 热点Key | 单个key被大量请求 | 爆款商品 | 本地缓存、读写分离 |

### 4.4 限流算法对比

| 算法 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 计数器 | 固定窗口计数 | 实现简单 | 临界问题 |
| 滑动窗口 | 细分窗口平滑计数 | 精度高 | 内存占用 |
| 漏桶 | 固定速率流出 | 流量平滑 | 无法应对突发 |
| 令牌桶 | 固定速率生成令牌 | 允许突发 | 实现稍复杂 |

```java
// Guava RateLimiter（令牌桶）
RateLimiter limiter = RateLimiter.create(100.0); // 100 QPS
if (limiter.tryAcquire(100, TimeUnit.MILLISECONDS)) {
    // 处理请求
} else {
    // 限流拒绝
}
```

---

## 五、并发性能调优实战

### 5.1 线程池调优

```java
// CPU密集型：corePoolSize = N_CPU + 1
int cpuCores = Runtime.getRuntime().availableProcessors();
ThreadPoolExecutor cpuPool = new ThreadPoolExecutor(
    cpuCores + 1, cpuCores + 1,
    60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),
    new ThreadPoolExecutor.CallerRunsPolicy()
);

// IO密集型：corePoolSize = 2 * N_CPU
ThreadPoolExecutor ioPool = new ThreadPoolExecutor(
    cpuCores * 2, cpuCores * 2,
    60L, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(10000),
    new ThreadPoolExecutor.CallerRunsPolicy()
);
```

### 5.2 GC调优与并发

| GC收集器 | 并发特征 | 适用场景 | STW时间 |
|----------|----------|----------|---------|
| Serial | 单线程GC | 小堆、Client模式 | 长 |
| Parallel | 多线程GC | 吞吐量优先 | 中等 |
| CMS | 并发标记清除 | 低延迟 | 短 |
| G1 | 并发+分区 | 大堆、低延迟 | 可控 |
| ZGC | 全并发 | 超低延迟、大堆 | <1ms |
| Shenandoah | 全并发 | 低延迟 | 极短 |

```bash
# 低延迟场景推荐
-XX:+UseZGC -Xms4g -Xmx4g

# 吞吐量优先场景推荐
-XX:+UseG1GC -XX:MaxGCPauseMillis=200
```

### 5.3 常见并发问题诊断工具

| 工具 | 用途 | 命令示例 |
|------|------|----------|
| jstack | 线程堆栈、死锁检测 | `jstack -l <pid>` |
| jstat | GC统计 | `jstat -gc <pid> 1000 10` |
| jmap | 堆转储 | `jmap -dump:live,file=dump.hprof <pid>` |
| jcmd | 综合诊断 | `jcmd <pid> VM.flags` |
| Arthas | 在线诊断 | `thread -b`(死锁), `monitor`(方法监控) |

```bash
# 快速检测死锁
jstack <pid> | grep -A 10 "deadlock"

# Arthas检测死锁
thread -b

# 查看热点方法
monitor -c 5 com.example.Service methodName
```

---

## 六、面试高频问题速答

**Q1: synchronized锁升级会降级吗？**
A: 不会。锁升级是单向的：无锁→偏向锁→轻量级锁→重量级锁。不会从重量级降级回轻量级。

**Q2: volatile能保证原子性吗？**
A: 不能。volatile只保证可见性和有序性，不保证原子性。如`i++`这种复合操作，即使i是volatile也无法保证原子性。

**Q3: CAS的ABA问题如何解决？**
A: 使用`AtomicStampedReference`或`AtomicMarkableReference`，通过版本号/标记位区分不同状态。

**Q4: 为什么wait/notify要在synchronized块中调用？**
A: wait/notify依赖于Monitor机制，需要先获取对象的Monitor锁。不在synchronized中调用会抛出`IllegalMonitorStateException`。

**Q5: LongAdder为什么比AtomicLong快？**
A: LongAdder采用**分段累加**（Cell数组），将热点分散到多个Cell，减少CAS自旋冲突。最终求和时再汇总所有Cell的值。

**Q6: 如何排查生产环境死锁？**
A: 
1. `jstack -l <pid>` 查看线程堆栈，搜索"deadlock"
2. Arthas `thread -b` 一键检测
3. JMX MBean `ThreadMXBean.findDeadlockedThreads()`
4. 定期抓取线程dump进行离线分析

---

## 七、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| 锁升级 | 无锁→偏向→轻量级→重量级，单向不可逆 | Mark Word, 偏向锁撤销, CAS自旋 |
| 内存屏障 | LoadLoad/StoreStore/LoadStore/StoreLoad | volatile, DCL, 指令重排序 |
| JIT优化 | 锁消除、锁粗化、逃逸分析、分层编译 | C1/C2, 内联展开, 栈上分配 |
| 高并发架构 | 无状态化、异步化、缓存化、限流降级 | 秒杀, 削峰填谷, 读写分离 |
| 性能调优 | 线程池选型、GC调优、诊断工具 | CPU密集/IO密集, ZGC, Arthas |

**高并发面试三板斧：**
1. **缓存是银弹**：能用缓存解决的，不要硬扛DB
2. **异步是利剑**：非核心流程全部异步化
3. **限流是底线**：任何系统都要有自我保护机制

---

> 🎯 **Java并发编程面试八股文系列完结！** 本系列从线程基础、锁机制、JUC并发工具类、并发容器、异步编程到JVM层面并发机制与高并发实战，全面覆盖了Java并发编程面试的核心知识点。
>
> 📌 **下期预告**：《高性能MySQL实战——从索引优化到分布式数据库》将深入B+树索引原理、慢查询优化、分库分表策略、读写分离架构以及TiDB等NewSQL技术选型，敬请期待！
