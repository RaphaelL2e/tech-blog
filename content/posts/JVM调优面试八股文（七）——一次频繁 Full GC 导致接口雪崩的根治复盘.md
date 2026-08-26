---
title: JVM调优面试八股文（七）——一次频繁 Full GC 导致接口雪崩的根治复盘
date: 2026-08-26T10:00:00+08:00
updated: '2026-08-26T10:00:00+08:00'
description: '面试高频问题：线上接口突然大面积超时、TP99 飙到几秒，监控里 Full GC 每分钟好几次，每次停顿几百毫秒却回收不掉多少内存——这到底是谁的锅？本文作为 JVM 调优面试八股文系列的第七篇，用一次真实的"接口雪崩"故障，串起前五篇的内存模型、GC 算法、收集器、类加载/JIT、GraalVM，以及第六篇的工具链，教你把"看得到现象"变成"定位到根因"的完整闭环。'
topic: java-spring
series: jvm-tuning-interview
series_order: 7
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- JVM
- Full GC
- 内存泄漏
- 故障排查
- 性能调优
categories:
- Java 与 Spring
draft: false
author: 飞哥
---

> 面试高频问题：线上接口突然大面积超时、TP99 飙到几秒，监控里 Full GC 每分钟好几次，每次停顿几百毫秒却回收不掉多少内存——这到底是谁的锅？本文作为 JVM 调优面试八股文系列的第七篇，用一次真实的"接口雪崩"故障，串起前五篇的内存模型、GC 算法、收集器、类加载/JIT、GraalVM，以及第六篇的工具链，教你把"看得到现象"变成"定位到根因"的完整闭环。

## 引言

前六篇我们分别啃下了 JVM 内存模型与 GC 算法、垃圾收集器选型、线上调优实战、类加载与 JIT 编译原理、GraalVM 与 AOT，以及监控诊断工具链。理论攒了一肚子，但真实世界的故障从来不会按教科书出牌。

今天这篇，我想带你打一场"实战仗"：一个平稳运行了半年的订单服务，毫无预兆地在某天下午接口超时率从 0.1% 蹿到 30%，TP99 从 80ms 涨到 3s 以上，而监控大盘上最扎眼的一条曲线是——**Full GC 频率从几分钟一次，变成了一分钟七八次，且每次停顿 300~500ms，回收的内存却越来越少**。

这篇文章不会给你一堆"背下来"的结论，而是还原一个真实的排查链路：从现象到怀疑点，从工具到根因，从临时止血到长期根治。读完后你会发现，所谓"Full GC 调优"，本质是一套**可复用的定位方法论**，而不是调几个 -XX 参数那么简单。

**本文要点**：
1. 频繁 Full GC 的六大典型诱因（含元空间、直接内存、显式 System.gc 等容易被忽略的坑）
2. 一套可在 15 分钟内落地的"GC 故障四步定位法"
3. 真实案例：无界缓存 + ThreadLocal 误用如何引发连锁雪崩
4. 从止血（参数）→ 治本（代码）→ 加固（架构）的三层根治方案
5. 面试高频追问：如何向面试官讲清楚一次 GC 故障

---

## 一、故障现场：一次接口的"雪崩"

先还原现场，方便你代入。服务是一个典型的 Spring Boot 订单查询接口，单机 4C8G，堆内存 `-Xmx4g -Xms4g`，使用 G1 收集器。日常表现：

- QPS：约 800
- TP99：80ms 左右
- Full GC：平均 5~10 分钟一次，停顿 < 200ms
- 老年代占用：稳定在 60%~70%

故障当天下午 14:32 开始，曲线突变：

- TP99：在 10 分钟内从 80ms 涨到 3200ms
- 超时率：从 0.1% 涨到 32%
- Full GC：频率飙到 **每分钟 6~9 次**，单次停顿 300~500ms
- 老年代占用：始终在 92%~98% 高位，且每次 Full GC 后只下降一点点
- 应用线程：大量线程处于 `Waiting`/`Blocked` 状态

一个关键观察：**Full GC 这么频繁，老年代却始终压不下去**。这几乎注定不是"堆太小"的问题——如果是单纯空间不足，调大堆通常能缓解；但这里回收效率极低，说明老年代里"住着"一批**回收不掉的对象**。这就是内存泄漏（或准泄漏）的典型特征。

> 记住第一个判断原则：**Full GC 频繁 + 回收效率低 + 老年代降不下来 = 大概率存在不断产生、且无法回收的对象**。下一步要做的，是找出这些"钉子户"是谁。

---

## 二、定位思路：从监控指标到怀疑点

很多人一看到 Full GC 频繁，第一反应是"加内存、换收集器"。这往往是南辕北辙。正确的顺序是：**先确认 Full GC 的触发原因，再决定动哪里**。

### 2.1 用 jstat 看 GC 原因

第六篇讲过 `jstat` 的用法。这里直接上排查命令：

```bash
# 每 1 秒采样一次，关注 GC 原因列（最后两列）
jstat -gccause <pid> 1000
```

`jstat -gccause` 比 `jstat -gcutil` 多输出两列：

- `LGCC`：上一次 GC 的原因
- `GCC`：当前正在进行的 GC 原因

常见的 Full GC 原因有：`Allocation Failure`（晋升失败）、`Metadata GC Threshold`（元空间触顶）、`System.gc()`（显式调用）、`G1 Evacuation Failure`、`Ergonomics`（自适应策略触发）等。

本例中 `LGCC` 持续显示为 `Allocation Failure`，且老年代 `OU`（Old Used）几乎不降，说明对象源源不断地晋升到老年代，而老年代又清不掉——**晋升速率 >> 回收速率**。

### 2.2 三个核心怀疑点

结合现象，我把怀疑范围收敛到三类：

1. **老年代存在内存泄漏**：有对象被长生命周期容器（静态 Map、单例缓存、ThreadLocal）持有，永远进不了回收集合。
2. **短时间产生大量大对象/短命大对象**：大对象直接进入老年代（G1 中超过 `Region` 一半大小的对象会被视为大对象放入 humongous 区），频繁触发 Mixed/Full GC。
3. **元空间或堆外内存触顶**：元空间不足会触发 Full GC；直接内存（Netty、NIO）泄漏也可能表现为 GC 异常。

下一段，我们逐一对着根因拆解。

---

## 三、根因分析：为什么 Full GC 停不下来

频繁 Full GC 看似一个现象，背后可能是完全不同的病因。把你脑子里关于"Full GC 诱因"的清单补全，是面试和实战都绕不开的基本功。

### 3.1 老年代空间不足 + 晋升失败

对象先在年轻代分配，经过多次 Young GC 仍存活就晋升到老年代。如果**老年代碎片化严重**或**剩余连续空间不足**，即使总空闲够，也可能晋升失败，进而触发 Full GC。G1 下对应的是 `Evacuation Failure`——收集时找不到空 Region 安置存活对象。

### 3.2 内存泄漏：被"遗忘"的引用

这是本文案例的真正元凶。典型模式：

- **无界缓存**：`Map` 当缓存用，只 put 不淘汰，key 永远可达。
- **ThreadLocal 误用**：在线程池场景下，ThreadLocal 里的对象会随线程存活，若不及时 `remove`，且线程被复用，对象就一直挂着。
- **监听器/回调未注销**：注册了观察者却从不反注册，引用链一直存在。
- **静态集合累积**：`static List/Map` 只增不减。

> 内存泄漏和"内存溢出"不同：泄漏是对象无谓地长期存活，慢慢吃掉内存；溢出是某一刻分配超过上限直接 OOM。但**长期泄漏最终都会演变成 Full GC 频繁甚至 OOM**。

### 3.3 元空间（Metaspace）触顶

元空间存放类元数据。如果应用**频繁加载类**（如大量使用动态代理、Groovy/JS 脚本引擎、热部署、自定义类加载器且不回收），元空间会持续增长。当达到 `-XX:MaxMetaspaceSize` 上限（或没设置时逼近系统限制），会触发 Full GC 尝试卸载类。若类加载器无法被回收（仍有引用），Full GC 也清不掉，于是反复触发。

### 3.4 显式 System.gc()

代码或第三方库里调用 `System.gc()`，会建议 JVM 进行一次 Full GC。某些框架（老版本 RMI、某些序列化库、管控端点）会周期性调用它。频繁显式 GC 是"人为制造"的 Full GC 高峰，典型特征是在固定周期出现。可用 `-XX:+DisableExplicitGC` 禁用（注意：Netty 等依赖直接内存释放的场景要谨慎，因其靠 `System.gc()` 触发 `Cleaner` 回收堆外内存，此时应改用 `-XX:+ExplicitGCInvokesConcurrent`）。

### 3.5 堆外/直接内存泄漏

使用 NIO、`ByteBuffer.allocateDirect`、Netty 时，内存分配在堆外，由 `DirectByteBuffer` 的 `Cleaner` 在 GC 时回收。如果直接内存使用量持续增长且对象迟迟不被 GC，会表现为**堆很闲、但进程 RSS 飙升、GC 异常**。可用 `-XX:MaxDirectMemorySize` 限制，并通过 NMT（Native Memory Tracking）观察。

### 3.6 大对象 / 大数组冲击波

一次性加载大文件、大结果集（如 `SELECT *` 返回几十万行）、超大序列化对象，会在堆里制造"巨无霸"。G1 中超过 Region 半大的对象走 humongous 分配，会优先且频繁地触发回收，甚至 `Evacuation Failure`。

---

## 四、排查四步法实战

回到案例。有了上面的"病因清单"，我用一套四步法在 15 分钟内锁定了根因。

### 第一步：开 GC 日志，看清每次 GC 在干什么

如果没开 GC 日志，先补上（JDK 9+ 用统一日志参数）：

```bash
# JDK 8 及之前
-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:/path/gc.log

# JDK 9+ 推荐用统一日志框架
-Xlog:gc*,gc+heap=debug,gc+age=trace:file=/path/gc.log:time,uptime,level,tags
```

日志里我们重点关注：每次 Full GC 前后老年代 `used` 的变化、晋升大小（`Promotion`）、GC 原因、停顿时长。本例日志显示每次 Full GC 后老年代只回落 1%~2%，印证"有清不掉的对象"。

### 第二步：jstat 确认趋势与原因

如第二章，`jstat -gccause` 持续显示 `Allocation Failure`，且 `OU` 不降。此时基本可以排除"堆太小"（堆小会表现为每次 GC 后明显下降），锁定"持续产生不可回收对象"。

### 第三步：抓堆转储，用工具找"钉子户"

在故障窗口抓一份堆转储（注意对大堆用在线 dump 有 STW 风险，生产建议结合 `-XX:+HeapDumpOnOutOfMemoryError` 自动留证，或用 Arthas `heapdump` 限流）：

```bash
# 方式一：jmap（会造成较长停顿，大堆慎用）
jmap -dump:live,format=b,file=/path/heap.hprof <pid>

# 方式二：Arthas（对运行影响相对小，可先 histo 粗看）
heapdump /path/heap.hprof
```

把 `heap.hprof` 拖进 MAT（Memory Analyzer）或 JProfiler，按 **Retained Size（保留大小）** 排序。本例 Top 1 是：

```
com.xxx.order.cache.OrderSnapshotCache
  └─ HashMap (size ≈ 2,300,000)
       └─ OrderSnapshot 对象，每个约 1.2KB
```

`OrderSnapshotCache` 是一个**静态单例 Map**，用作订单快照缓存，代码里只有 `put` 没有淘汰策略——典型的无界缓存泄漏。结合业务，下午刚好有大促预热，订单量陡增，缓存以每天百万级速度膨胀。

### 第四步：用 Arthas / async-profiler 看"谁在往里塞"

知道是 `OrderSnapshotCache` 在涨还不够，得确认**是谁、在什么调用链上往里塞**，避免只修一处别处又漏。用 Arthas 追踪：

```bash
#  watch 这个类的方法入参/返回，确认调用频率与来源
watch com.xxx.order.cache.OrderSnapshotCache put '{params,returnObj}' -x 3

# 用 profiler 生成火焰图，看内存分配热点（allocation profile）
profiler start --event alloc
# 跑一段时间
profiler stop --format flamegraph -f /path/alloc.html
```

火焰图里 `OrderSnapshotCache.put` 的调用方指向一个"订单详情聚合"接口——它每次查询都把完整快照写进缓存，且缓存 key 用了会变化的请求参数，导致**相同业务对象被反复写入不同 key，永远命中不了、也淘汰不掉**。同时我们在代码里发现该接口还用了 `ThreadLocal` 暂存上下文，但异常分支下忘了 `remove`，少量线程的 ThreadLocal 也成了泄漏帮凶。

到这一步，根因完全清晰：**无界缓存（主因）+ ThreadLocal 未清理（次因）+ 大促流量放大 = 老年代被撑爆 → 频繁 Full GC → STW 累积 → 接口雪崩**。

---

## 五、根治方案：止血、治本、加固三层法

定位清楚后，修复要分层，避免"头痛医头"。

### 5.1 第一层：止血（参数与兜底，分钟级）

先让服务恢复可用，争取排查时间：

- 临时调大堆：` -Xmx6g -Xms6g`（缓解但不解决，仅争取时间）。
- 限制元空间，避免连带雪崩：`-XX:MaxMetaspaceSize=256m`。
- 对直接内存敏感服务，把显式 GC 改为并发而非禁用：`-XX:+ExplicitGCInvokesConcurrent`（本例不涉及，但属常见加固）。
- 加 JVM 兜底自动留证：`-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/path/heap.hprof`。

> 注意：止血参数只是买时间，绝不能当成"修复"。把 `-Xmx` 从 4g 调到 16g 掩盖泄漏，是生产环境最常见的伪修复。

### 5.2 第二层：治本（代码，根因修复）

针对本案：

1. **把无界缓存换成有界缓存**：用 Caffeine 或 Guava Cache，设置 `maximumSize` 和 `expireAfterWrite`，从"只进不出"变成"LRU + TTL 自动淘汰"。

   ```java
   Cache<String, OrderSnapshot> cache = Caffeine.newBuilder()
           .maximumSize(50_000)
           .expireAfterWrite(10, TimeUnit.MINUTES)
           .recordStats()
           .build();
   ```

2. **修复缓存 key 设计**：用稳定的业务主键（订单 ID）而非易变请求参数作 key，避免"同对象多 key"的伪命中。

3. **ThreadLocal 必须配对 remove**：用 `try-finally` 保证清理，或改用 Java 9+ 的 `cleaner`/资源化写法。

   ```java
   private static final ThreadLocal<Context> CTX = new ThreadLocal<>();
   try {
       CTX.set(ctx);
       // ... 业务
   } finally {
       CTX.remove();   // 关键：线程池复用前必须清理
   }
   ```

4. **大结果集分页**：订单聚合接口对大单做流式/分页读取，杜绝一次性几 MB 的对象驻留。

### 5.3 第三层：加固（架构与监控，防复发）

- **监控告警**：对 Full GC 频率（如 > 5 次/分钟）、老年代占用（> 85%）、GC 停顿累计时长设告警，别等超时率爆了才发现。
- **限流降级**：对订单聚合这类重接口加限流与熔断，流量洪峰时优先保核心链路。
- **压测验证**：用生产流量回放做容量压测，观察堆与 GC 曲线是否随 QPS 线性、缓存是否稳定。
- **代码规范卡点**：静态扫描禁止裸 `static Map` 当缓存、强制 `ThreadLocal.remove`，把坑挡在合入前。

修复后压测对比（同机型、同 QPS）：Full GC 从每分钟 7 次降到约每 20 分钟 1 次，TP99 回到 90ms，超时率归零。

---

## 六、验证与复盘

好的排查要能"复现—修复—验证"闭环：

1. **复现**：在预发环境用流量回放 + 注入泄漏代码，复刻 Full GC 曲线，确认定位手段可重复。
2. **修复**：上线第二、三层方案。
3. **验证**：压测 + 灰度 5% 流量观察 24h，GC 指标与 TP99 恢复基线，再全量。
4. **复盘文档**：把这次的 GC 日志片段、堆转储 Top 对象、修复 PR、监控口径沉淀为案例库，下次同类问题可秒级对照。

复盘中最有价值的，不是"这次怎么修的"，而是"下次怎么在 5 分钟内发现"。所以我们把 Full GC 频率、老年代占用、元空间占用、直接内存四项做成标准看板，纳入每日巡检。

---

## 七、面试高频追问

这一篇的考点很容易在面试里被深挖，提前备好答案：

- **Full GC 和 Young GC 的区别？什么会触发 Full GC？**
  答：Young GC 只回收年轻代，频率高、停顿短；Full GC 回收整个堆（含老年代、元空间），停顿长。触发点包括老年代空间不足、元空间触顶、显式 `System.gc()`、G1 的 Evacuation/Concurrent Mode Failure 等。

- **内存泄漏和内存溢出有什么关系？**
  答：泄漏是对象无谓长期存活、持续累积；溢出是某次分配超过上限直接 OOM。长期泄漏会演变成频繁 GC 乃至 OOM，二者是渐进与爆发的关系。

- **怎么定位内存泄漏？**
  答：GC 日志看回收效率 → `jstat -gccause` 看原因与趋势 → 抓堆转储用 MAT 按 Retained Size 找 Top 对象 → Arthas/async-profiler 追分配调用链。

- **G1 下大对象（humongous）有什么讲究？**
  答：超过 Region 一半大小的对象走 humongous 分配，会优先触发回收且易 Evacuation Failure，应尽量避免短命大对象。

- **-XX:+DisableExplicitGC 有什么坑？**
  答：它会禁掉 `System.gc()`，但 Netty 等依赖 `Cleaner` 在 GC 时回收直接内存，禁用后可能造成堆外内存堆积；此时应改用 `-XX:+ExplicitGCInvokesConcurrent`。

---

## 总结

频繁 Full GC 不是"加内存"就能解决的信号，而是 JVM 在替你报警：**有对象在偷偷堆积，或者有人在错误的时间制造了 GC 压力**。本文用一次接口雪崩，串起了整套定位方法论：

- 看现象先判断"回收效率"，区分堆小 vs 泄漏；
- 用 `jstat -gccause` 锁定 GC 原因；
- 用堆转储 + MAT 找"钉子户"对象；
- 用 Arthas/火焰图追分配调用链；
- 最后用"止血—治本—加固"三层法根治并防复发。

当你能把工具、原理、业务代码串成一条线，JVM 调优就从"背参数"变成了"解问题"。

**下一期预告**：本系列已写到第七篇，内存模型、GC 算法、收集器、调优实战、类加载/JIT、GraalVM、工具链与故障复盘都已覆盖。下一篇（八）我们将收官——**《JVM 调优面试八股文（八）——面试通关：JVM 调优知识地图与高频题串讲》**，把整个系列浓缩成一张可背诵、可临场发挥的知识地图，帮你把七篇内容在面试 30 分钟内讲出节奏感。敬请期待。
