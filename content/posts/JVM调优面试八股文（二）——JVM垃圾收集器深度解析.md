---
title: JVM调优面试八股文（二）——JVM垃圾收集器深度解析
date: 2026-08-10 10:00:00+08:00
updated: '2026-08-10T10:00:00+08:00'
description: '面试高频问题：有哪些垃圾收集器？Serial、Parallel、CMS、G1、ZGC、Shenandoah 各有什么特点？什么时候该选 G1？ZGC 为什么能实现亚秒级停顿？本文作为 JVM 调优面试八股文系列的第二篇，系统梳理所有主流垃圾收集器的架构原理、性能特征与选型策略，帮你构建完整的 GC 知识体系。'
topic: java-spring
series: jvm-tuning-interview
series_order: 2
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- JVM
- GC
- 垃圾收集器
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：有哪些垃圾收集器？Serial、Parallel、CMS、G1、ZGC、Shenandoah 各有什么特点？什么时候该选 G1？ZGC 为什么能实现亚秒级停顿？本文作为 JVM 调优面试八股文系列的第二篇，系统梳理所有主流垃圾收集器的架构原理、性能特征与选型策略，帮你构建完整的 GC 知识体系。

## 引言

上一篇文章我们详细讲解了 JVM 内存模型和三种基础 GC 算法（标记-清除、标记-复制、标记-整理）。然而在生产实践中，JVM 并没有直接使用这些"裸"算法，而是将它们组合封装成了功能强大的**垃圾收集器**。

不同的垃圾收集器在吞吐量、停顿时间、内存占用之间做了不同的权衡，理解它们是做好 JVM 调优的前提。本文将带你逐一拆解所有主流垃圾收集器，并给出实战选型建议。

**本文要点**：
1. 垃圾收集器的分类体系与组合关系
2.  Serial / Parallel 收集器：年轻代与老年代的经典搭档
3.  CMS 收集器：首次实现并发标记的里程碑
4.  G1 收集器：区域化设计的划时代方案
5.  ZGC 和 Shenandoah：面向低延迟的新一代收集器
6.  收集器选型决策树与实战参数配置

---

## 一、垃圾收集器全景图

### 1.1 分类体系

JVM 中的垃圾收集器可以从两个维度分类：

**按垃圾分代划分**：

- **年轻代收集器**：Serial、ParNew、Parallel Scavenge
- **老年代收集器**：Serial Old、Parallel Old、CMS
- **整堆收集器**：G1、ZGC、Shenandoah

**按垃圾回收模式划分**：

| 模式 | 特点 | 代表收集器 |
|------|------|-----------|
| 串行回收 | 单线程执行，简单但停顿长 | Serial、Serial Old |
| 并行回收 | 多线程并发执行，追求高吞吐 | Parallel Scavenge、Parallel Old |
| 并发回收 | GC 线程与应用线程并发执行，追求低停顿 | CMS、G1、ZGC、Shenandoah |

### 1.2 组合关系图

```
                        ┌──────────────┐
                        │  年轻代       │
│  Serial GC ──────────►│  (Eden+S0+S1)│
│  ParNew GC ──────────►│              │
│  Parallel Scavenge ──►│              │
                        └──────┬───────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  老年代       │
│  Serial Old ──────────│              │
│  Parallel Old ────────│              │
│  CMS ─────────────────│              │
└───────────────────────►│              │
                        └──────────────┘

        ┌────────────────────────────────────────┐
        │          G1（独立整堆收集器）             │
        │   将堆划分为多个大小相等的 Region         │
        └────────────────────────────────────────┘

        ┌────────────────────────────────────────┐
        │   ZGC / Shenandoah（独立整堆收集器）     │
        │   不分代，并发标记+着色指针               │
        └────────────────────────────────────────┘
```

### 1.3 默认收集器

```bash
# 查看当前 JVM 默认使用的垃圾收集器
java -XX:+PrintCommandLineFlags -version 2>&1 | grep GC

# JDK 8（未指定收集器时）
# 年轻代：Parallel Scavenge
# 老年代：Parallel Old

# JDK 9+（G1 成为默认）
# 默认使用 G1
```

---

## 二、Serial 系列：最朴素的收集器

### 2.1 Serial 收集器

Serial 是最经典也是最简单的一种垃圾收集器，其核心特点只有一个：**单线程运行**。

```bash
# 启用 Serial 收集器
-XX:+UseSerialGC
```

**工作原理**：

```
年轻代：标记-复制
[ Eden ] [ S0 ] [ S1 ]
          ↓
     单线程 STW 扫描 → 标记 → 复制 → 清理

老年代：Serial Old，标记-整理
[ Old Gen ]
    ↓
 单线程 STW 扫描 → 标记 → 整理 → 清理
```

**适用场景**：

- **客户端应用**：堆内存小（几十到几百 MB）、停顿几百毫秒无感
- **单核 CPU 环境**：无法利用多线程优势
- **对吞吐量要求不高的桌面应用**

```java
// JVM 参数示例：Serial 收集器的客户端配置
java -Xms256m -Xmx256m \
     -XX:+UseSerialGC \
     -jar client-app.jar
```

### 2.2 Parallel Scavenge：吞吐量优先

Parallel Scavenge（也称 Throughput Collectors）是年轻代收集器，专注于**最大化吞吐量**。

```bash
# 启用 Parallel Scavenge
-XX:+UseParallelGC          # 年轻代
-XX:+UseParallelOldGC       # 老年代
```

**核心参数**：

```bash
# 设置吞吐量目标（0 < target < 1），默认 0.99
# 即目标 99% 的时间用于运行应用代码，1% 用于 GC
-XX:GCTimeRatio=19
# 相当于：GC 时间占比 = 1/(1+19) = 5%

# 设置最大 GC 停顿时间（单位：毫秒）
# 注意：这是一个软目标，JVM 会尽量但不保证达成
-XX:MaxGCPauseMillis=200

# 设置年轻代大小（动态调整）
-XX:+UseAdaptiveSizePolicy
# 开启后，-Xmn、-XX:SurvivorRatio 等参数会成为起始值
# JVM 会自动调整各区大小以满足吞吐量和停顿时间目标

# 设置年轻代与老年代比例（1 个 Eden + 1 个 Survivor）
-XX:SurvivorRatio=8  # 默认 8:1:1，即 Eden:Survivor = 8:2 = 4:1
```

**自适应调优原理**：

AdaptiveSizePolicy 是 Parallel Scavenge 的核心特性。当开启后，JVM 会自动调整以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| NewSize / MaxNewSize | 动态 | 年轻代大小范围 |
| SurvivorRatio | 8 | Eden 与 Survivor 比例 |
| OldSize | 动态 | 老年代大小 |

这使得 Parallel Scavenge 成为少数"不需手动调优就能有不错表现"的收集器。

**适用场景**：

- **后台批处理系统**：如数据导入、报表生成、离线计算
- **对吞吐量要求高，能容忍较长的 GC 停顿**（秒级）
- **不需要低延迟保障的服务器应用**

```bash
# 典型的高吞吐批处理配置
java -Xms4g -Xmx4g \
     -XX:+UseParallelGC \
     -XX:+UseParallelOldGC \
     -XX:GCTimeRatio=19 \
     -XX:MaxGCPauseMillis=500 \
     -XX:+UseAdaptiveSizePolicy \
     -jar batch-processor.jar
```

---

## 三、CMS：首个并发收集器

### 3.1 CMS 的设计目标

CMS（Concurrent Mark Sweep，获取许可证式并发标记清除）是 JVM 历史上第一个实现**并发标记**的收集器。其设计目标非常明确：**最小化停顿时间**，尤其是老年代 GC 造成的长时间停顿。

```bash
# 启用 CMS
-XX:+UseConcMarkSweepGC
```

CMS 只能配合 ParNew（年轻代）或 Serial 使用，不能配合 Parallel Scavenge。

### 3.2 CMS 的四个阶段

CMS 将 GC 过程分为四个阶段：

```
阶段 1：初始标记（Initial Mark）—— STW
  ↓
阶段 2：并发标记（Concurrent Mark）—— 并发
  ↓
阶段 3：重新标记（Remark）—— STW
  ↓
阶段 4：并发清除（Concurrent Sweep）—— 并发
```

**阶段详解**：

| 阶段 | 是否 STW | 时间 | 说明 |
|------|----------|------|------|
| 初始标记 | ✅ | 短 | 仅标记 GC Roots 直接引用的对象，会Stop the World |
| 并发标记 | ❌ | 长 | 从 GC Roots 出发，遍历整个对象图，应用线程并发运行 |
| 重新标记 | ✅ | 短~中 | 修正并发标记期间因用户线程运行导致的对象变化（白色→灰色→黑色） |
| 并发清除 | ❌ | 长 | 清理死亡对象，不移动存活对象，应用线程并发运行 |

**并发标记期间的问题**：

并发标记最大的难题是"浮动垃圾"（Floating Garbage）：

```
用户线程在并发标记过程中新分配的对象 → 标记为白色（死亡）→ 成为浮动垃圾
并发清除时无法回收 → 只能留到下一次 GC

用户线程在标记过程中对象引用变化：
  A.b = null  （A 原本引用 B，B 已被标记为存活）
  A.c = new C()  （C 未被标记，引用丢失）
  重新标记阶段修正
```

### 3.3 CMS 的致命缺陷

CMS 并不是完美的收集器，它有两大致命缺陷：

**缺陷一：内存碎片**

CMS 采用标记-清除算法，不进行内存整理。这会导致老年代中出现大量内存碎片，最终触发 **Full GC（Promotion Failed）** 或 **Concurrent Mode Failure**。

```bash
# 内存碎片导致的两种失败模式：

# 1. Promotion Failed（晋升失败）
# 年轻代对象晋升到老年代时，老年代空间不足
# 触发原因：老年代有足够空间但不连续
# 处理方式：退化为 Serial Old（单线程整理），停顿很长

# 2. Concurrent Mode Failure（并发模式失败）
# 并发标记未完成，老年代已满
# 触发原因：浮动垃圾过多或内存分配速率过高
# 处理方式：立即触发 Full GC（Serial Old）
```

**解决方案**：`-XX:+UseCMSCompactAtFullCollection`（默认开启）和 `-XX:CMSFullGCsBeforeCompaction=N`（默认 0）。

```bash
# 内存碎片参数
# 每 N 次 Full GC 后进行一次内存整理（压缩）
-XX:CMSFullGCsBeforeCompaction=5

# 触发 Full GC 的老年代使用率阈值（默认 92%）
-XX:CMSInitiatingOccupancyFraction=75
```

**缺陷二：浮动垃圾占用内存**

由于并发清除阶段用户线程持续运行，CMS 必须预留足够的老年代空间来容纳浮动垃圾。默认阈值 92% 意味着老年代使用率达到 92% 就开始 GC，如果 GC 期间分配速度超过预期，极易触发 Concurrent Mode Failure。

```bash
# 降低阈值，留更多空间给浮动垃圾
-XX:CMSInitiatingOccupancyFraction=70

# 或者更激进
-XX:CMSInitiatingOccupancyFraction=60
```

### 3.4 CMS 参数配置参考

```bash
java -Xms4g -Xmx4g \
     -XX:+UseConcMarkSweepGC \
     -XX:ParalleGCThreads=4 \
     -XX:CMSInitiatingOccupancyFraction=70 \
     -XX:+UseCMSCompactAtFullCollection \
     -XX:CMSFullGCsBeforeCompaction=5 \
     -XX:+CMSScavengeBeforeRemark \
     -jar webapp.jar
```

参数说明：

- `ParalleGCThreads`：CMS 并行线程数，默认 = `(CPU数量 + 3) / 4`
- `CMSScavengeBeforeRemark`：在重新标记前先执行一次年轻代 GC，减少浮动垃圾和扫描范围
- 适合：延迟敏感的互联网应用

---

## 四、G1：区域化收集器

### 4.1 G1 的设计思想

G1（Garbage First）从 JDK 7u4 开始引入，JDK 9 成为默认收集器。它的核心创新是**区域化（Region）设计**：

```
传统分代模型：                      G1 区域化模型：
┌─────────────────┐                ┌────┬────┬────┬────┐
│      年轻代      │ 连续的固定空间   │ E1 │ S  │ E2 │ S  │
└─────────────────┘                ├────┼────┼────┼────┤
┌─────────────────┐                │ H1 │ E3 │ H2 │ E4 │
│      老年代      │                ├────┼────┼────┼────┤
└─────────────────┘                │ E5 │ H3 │ S  │ H4 │
                                   └────┴────┴────┴────┘
                                          动态大小，逻辑连续
```

**Region 的划分**：
- 堆内存被划分为多个大小相等的 Region（默认 1MB，可配置 1MB/2MB/4MB/8MB/16MB/32MB）
- 每个 Region 逻辑上属于 Eden、Survivor 或 Humongous（大对象区）
- Humongous Region 专门存储超过 Region 容量 50% 的大对象

**G1 的核心思想**：
> 优先回收垃圾最多的 Region。

G1 维护一个**优先列表**（Remembered Set），记录每个 Region 中对象被外部 Region 引用的情况。GC 时，G1 根据各 Region 的回收价值（回收获得的空间 + 回收所需的时间）排序，优先回收价值最高的 Region。这就是 "Garbage First" 的含义。

### 4.2 G1 的回收过程

G1 的年轻代收集（Young GC）：

```
阶段 1：初始标记（Initial Mark）—— 通常是 Young GC 的前奏，STW
阶段 2：并发标记（Concurrent Marking）—— 跨 Region 遍历
阶段 3：最终标记（Final Mark）—— 修正并发期间的引用变化，STW
阶段 4：筛选回收（Live Data Counting & Cleanup）—— 计算各 Region 回收价值，STW
阶段 5：复制/清理（Evacuation）—— 将存活对象复制到目标 Region，STW
```

G1 的完整回收周期（Mixed GC）同时覆盖年轻代和老年代的 Region。

**Remembered Set（记忆集）**：

G1 的关键数据结构。每个 Region 都有一个 RSet，记录了"哪些其他 Region 引用了本 Region 中的对象"。

```
Region A (Eden)         Region B (Old)
┌─────────────┐         ┌─────────────┐
│ 对象 o1  ────┼────────►│  对象 o2     │
│ 对象 o2      │         │             │
│ RSet: {B}   │         │             │
└─────────────┘         └─────────────┘
```

RSet 使得 G1 可以在不扫描整个堆的情况下完成 GC Roots 的可达性分析，显著降低了 STW 时间。

### 4.3 G1 的关键参数

```bash
# 启用 G1
-XX:+UseG1GC

# 目标停顿时间（软目标）
-XX:MaxGCPauseMillis=200

# Region 大小（2的幂次方）
-XX:G1HeapRegionSize=4m

# 触发 Mixed GC 的老年代占用阈值
-XX:InitiatingHeapOccupancyPercent=45

# 每个 GC 周期中 Mixed GC 最多包含的 Region 数
-XX:G1MixedGCLiveThresholdPercent=85
```

### 4.4 G1 vs CMS 对比

| 对比维度 | CMS | G1 |
|---------|-----|-----|
| 分代模型 | 物理分代 | 逻辑分代（Region） |
| 内存整理 | 不整理（碎片问题） | 每次回收都整理（无碎片） |
| 停顿模型 | 两次短 STW（初始标记+重新标记） | 可预测停顿（Pause Time Goal） |
| 吞吐量 | 较低（并发阶段消耗 CPU） | 较高（优化复制算法） |
| 内存占用 | 较低 | 略高（需要额外空间做 RSet） |
| 大对象处理 | 直接进入老年代 | Humongous Region |
| 最低支持版本 | JDK 5 | JDK 7u4 |
| 默认版本 | — | JDK 9+ |

**什么时候选 G1？**

```bash
# 推荐 G1 的场景
# 1. 堆内存 >= 6GB
# 2. 需要可控的停顿时间（< 500ms）
# 3. 希望自动平衡吞吐量和延迟
# 4. JDK 9+ 的新项目
java -Xms8g -Xmx8g \
     -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=200 \
     -XX:InitiatingHeapOccupancyPercent=45 \
     -jar myapp.jar
```

---

## 五、新一代收集器：ZGC 和 Shenandoah

### 5.1 为什么需要新一代收集器

在 G1 之后，JVM 社区追求的目标是：**停顿时间不超过 10ms**，并且**停顿时间不随堆大小增加而增加**。G1 虽然优秀，但在超大堆（100GB+）场景下仍难以做到亚毫秒级停顿。

### 5.2 ZGC

ZGC（Z Garbage Collector）从 JDK 11 作为实验特性引入，JDK 15 成为生产就绪。

```bash
# JDK 11+ 启用 ZGC
-XX:+UseZGC

# JDK 8/9/10 需要实验性参数
-XX:+UnlockExperimentalVMOptions -XX:+UseZGC
```

**ZGC 的核心技术：着色指针（Colored Pointers）**

ZGC 在对象头中使用了 64 位地址空间的低 42 位存储真实的内存地址，高 4 位（4 个标志位）存储对象的 GC 状态信息：

```
┌──────────┬──────────────────────────────────────────────┐
│ 4 bits   │ 42 bits（低42位）                            │
│ 标志位    │ 真实对象地址                                 │
└──────────┴──────────────────────────────────────────────┘

标志位含义（ZGC 使用其中 4 个）：
- Marked0 / Marked1：并发标记阶段的对象标记
- Remapped：对象是否已迁移到新地址
```

通过着色指针，GC 线程可以在不访问对象本身的情况下判断对象的存活状态。这使得 ZGC 实现了**读屏障（Load Barrier）**而非传统意义上的 STW 阶段。

**ZGC 的工作过程**：

```
1. 初始标记（Initial Mark）—— STW，只标记 GC Roots
2. 并发标记（Concurrent Mark）—— 遍历对象图，着色指针记录
3. 再标记（Relocate）—— STW，处理并发标记期间的变化
4. 并发重定位（Concurrent Relocate）—— 迁移存活对象，更新引用
5. 并发映射（Concurrent Remap）—— 清理旧地址引用
```

**ZGC 的优势**：

```bash
# ZGC 典型配置
java -Xms64g -Xmx64g \
     -XX:+UseZGC \
     -XX:MaxGCPauseMillis=10 \
     -XX:+ZCollectionInterval=5 \
     -jar huge-memory-app.jar

# ZGC 的特点：
# - 停顿时间 < 10ms（JDK 13+ 可做到 < 1ms）
# - 停顿时间与堆大小无关（理论上支持 16TB 堆）
# - 并发执行，不影响吞吐量
# - 支持 NUMA 架构优化（-XX:+UseNUMA）
```

### 5.3 Shenandoah

Shenandoah 由 Red Hat 开发，在 JDK 8u 中作为独立构建发布（JDK 12+ 进入 OpenJDK）。

```bash
# 启用 Shenandoah
-XX:+UseShenandoahGC
```

**Shenandoah vs ZGC 的区别**：

| 对比维度 | ZGC | Shenandoah |
|---------|-----|-----------|
| 着色指针位数 | 使用高 4 位（需 46 位地址空间以上） | 使用低几位（兼容 32 位） |
| 读屏障开销 | 仅在读取对象时触发 | 同样仅在读取时触发 |
| 内存占用 | 额外内存用于转发指针 | 额外内存用于转发指针 |
| JDK 版本 | JDK 11+ | JDK 12+（稳定） |
| 商业支持 | OpenJDK / Oracle JDK | OpenJDK（Red Hat 主导） |

两者本质上非常相似，都是基于并发迁移和着色指针的"不 STW"收集器。选型时主要看 JDK 版本和厂商支持情况。

### 5.4 性能数据对比（来自官方 benchmarks）

| 收集器 | 堆大小 | 停顿时间 | 吞吐量 | 并发线程 |
|--------|--------|---------|--------|---------|
| Serial GC | 4GB | ~400ms | ~75% | 1 |
| Parallel GC | 4GB | ~150ms | ~90% | CPU 核数 |
| CMS | 4GB | ~80ms（Young） | ~85% | ~CPU 核数 |
| G1 | 4GB | ~50ms | ~88% | ~CPU 核数 |
| ZGC | 100GB | <1ms | ~92% | ~20 |
| Shenandoah | 100GB | <2ms | ~90% | ~CPU 核数 |

> 注：以上数据为近似参考值，实际性能受应用特征、GC 参数配置影响显著。

---

## 六、收集器选型决策树

### 6.1 决策流程

```
应用类型判断
     │
     ▼
┌────────────────────────────┐
│ 是否需要低延迟？             │
│ (< 200ms 停顿要求)          │
└──────────┬─────────────────┘
           │
      是    │    否
      ▼     │     ▼
┌──────────┴──┐  ┌──────────────────┐
│堆大小判断   │  │ 是否是批处理/吞吐优先？│
└─────┬──────┘  └────────┬─────────┘
      │                  │
 < 6GB │ >= 6GB          │ 是    │ 否
  ▼    │   ▼             │  ▼     │ ▼
 CMS   │  G1         Parallel  关注停顿时间
(老CMS)│(或ZGC)          GC     CMS/G1
```

### 6.2 场景化选型推荐

**场景一：小型 Web 应用，堆 512MB，延迟不敏感**

```bash
# 客户端模式，Serial GC 足够
java -Xms512m -Xmx512m \
     -XX:+UseSerialGC \
     -jar webapp.jar
```

**场景二：数据处理批任务，追求高吞吐**

```bash
# 并行 GC，4 核机器，堆 8GB
java -Xms8g -Xmx8g \
     -XX:+UseParallelGC \
     -XX:+UseParallelOldGC \
     -XX:ParallelGCThreads=8 \
     -XX:GCTimeRatio=19 \
     -XX:MaxGCPauseMillis=500 \
     -XX:+UseAdaptiveSizePolicy \
     -jar batch.jar
```

**场景三：互联网 API 服务，关注延迟，P99 < 100ms**

```bash
# JDK 11+，G1 是很好的折中选择
java -Xms4g -Xmx4g \
     -XX:+UseG1GC \
     -XX:MaxGCPauseMillis=100 \
     -XX:InitiatingHeapOccupancyPercent=45 \
     -XX:G1HeapRegionSize=4m \
     -jar api-service.jar
```

**场景四：大数据平台，堆 128GB，需要亚秒级停顿**

```bash
# ZGC，追求极致低延迟
java -Xms128g -Xmx128g \
     -XX:+UseZGC \
     -XX:MaxGCPauseMillis=10 \
     -XX:+UseNUMA \
     -jar bigdata-platform.jar

# 或者 Shenandoah（JDK 12+）
java -Xms128g -Xmx128g \
     -XX:+UseShenandoahGC \
     -XX:MaxGCPauseMillis=10 \
     -jar bigdata-platform.jar
```

**场景五：JDK 8 遗留系统，不换 JDK，想减少停顿**

```bash
# JDK 8 下的最优解：CMS + 适当参数
java -Xms4g -Xmx4g \
     -XX:+UseConcMarkSweepGC \
     -XX:ParalleGCThreads=4 \
     -XX:CMSInitiatingOccupancyFraction=70 \
     -XX:+UseCMSCompactAtFullCollection \
     -XX:CMSFullGCsBeforeCompaction=5 \
     -XX:+CMSScavengeBeforeRemark \
     -jar legacy-app.jar
```

---

## 七、GC 日志分析与调优实战

### 7.1 开启 GC 日志

```bash
# 推荐格式：带时间戳 + 详细 GC 原因
java -Xms4g -Xmx4g \
     -XX:+UseG1GC \
     -Xlog:gc*=info:file=gc.log:time,uptime,level,tags \
     -jar app.jar
```

### 7.2 读懂 G1 GC 日志

```
[2026-08-10T10:00:01.234+0800][info][gc] GC(12) Pause Young (Normal) (G1 Evacuation Pause)
GC(12) 524M->156M(4096M) 45.6ms

解读：
- GC(12)：第 12 次 GC
- Pause Young (Normal)：正常年轻代 GC
- 524M->156M：GC 前 524MB，GC 后 156MB（年轻代）
- (4096M)：总堆 4096MB
- 45.6ms：停顿时间
```

### 7.3 常见 GC 问题与排查

**问题一：GC 频率过高**

```
现象：每分钟多次 Young GC，停顿时间虽然短但累积影响大
原因：
  - 年轻代太小（Eden 区分配速率 > GC 回收速率）
  - 对象朝生夕死率高
  - Survivor Ratio 设置不合理

排查：jstat -gc <pid> 1000
诊断：Eden 区占用率在 GC 后仍然很高
解决：
  - 增大年轻代：-XX:NewSize=1g -XX:MaxNewSize=1g（固定大小）
  - 调整 Survivor Ratio：-XX:SurvivorRatio=4（减少晋升压力）
  - 减少对象分配：检查代码中是否有大量临时对象
```

**问题二：Full GC 频繁**

```
现象：老年代 GC 频繁，停顿时间很长
原因：
  - CMS：内存碎片（Promotion Failed）
  - G1：Mixed GC 跟不上对象晋升速率
  - 所有收集器：老年代空间不足

排查：jstat -gc <pid> 1000，关注 Old Gen 占用率
诊断：CMS 日志中出现 "concurrent mode failure" 或 "promotion failed"

解决（CMS）：
  - 降低 CMS 触发阈值：-XX:CMSInitiatingOccupancyFraction=70
  - 增加 Full GC 整理频率：-XX:CMSFullGCsBeforeCompaction=3

解决（G1）：
  - 增大堆：-Xms / -Xmx
  - 降低 Mixed GC 触发阈值：-XX:InitiatingHeapOccupancyPercent=40
  - 增加 Mixed GC 的 Region 数上限：-XX:G1MixedGCLiveThresholdPercent=75
```

**问题三：GC 停顿时间超标**

```
现象：GC 停顿时间超过 MaxGCPauseMillis 设置
原因：
  - G1：Region 回收价值计算不准确
  - 堆太大，年轻代 GC 变慢
  - 跨 Region 引用多，RSet 扫描慢

解决：
  - 设置更合理的停顿目标（不要设置过小）：-XX:MaxGCPauseMillis=300
  - 使用 ZGC：-XX:+UseZGC（超大堆场景）
  - 减少大对象分配（G1 Humongous 回收代价高）
  - 升级到更新的 JDK 版本（GC 算法持续优化）
```

---

## 八、总结

| 收集器 | 分代 | 停顿时间 | 吞吐量 | 内存整理 | 推荐场景 |
|--------|------|---------|--------|---------|---------|
| Serial | 物理分代 | 长（~400ms） | 低 | 无 | 客户端、小堆 |
| Parallel | 物理分代 | 中（~150ms） | 高 | 无 | 批处理、高吞吐 |
| CMS | 物理分代 | 短（~80ms） | 中 | 无 | 低延迟（已淘汰） |
| G1 | 逻辑分代 | 可控（~50ms） | 高 | 每次整理 | JDK 8+ 推荐 |
| ZGC | 不分代 | <1ms | 高 | 并发整理 | 超大堆（>=64GB）|
| Shenandoah | 不分代 | <2ms | 高 | 并发整理 | JDK 12+，低延迟 |

**选型口诀**：

- 小堆单核 → Serial
- 吞吐优先 → Parallel
- 延迟敏感（<=6GB）→ G1
- 超大堆 + 极致低延迟 → ZGC / Shenandoah
- JDK 8 遗留系统 → CMS + 参数调优

---

## 下期预告

本系列第三篇将聚焦 **JVM 调优实战与线上问题排查**，涵盖 Arthas 工具使用、GC 日志分析、堆内存 Dump 分析、MAT 使用技巧，以及典型 OOM 场景的定位与解决方案。敬请期待。

---

*如果你觉得这篇文章有帮助，欢迎订阅、点赞、在看，把知识分享给更多需要的人。*
