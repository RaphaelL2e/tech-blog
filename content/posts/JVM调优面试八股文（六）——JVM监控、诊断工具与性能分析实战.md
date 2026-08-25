---
title: JVM调优面试八股文（六）——JVM监控、诊断工具与性能分析实战
date: 2026-08-25T10:00:00+08:00
updated: '2026-08-25T10:00:00+08:00'
description: '面试高频问题：线上JVM进程突然CPU 100%怎么排查？内存泄漏怎么定位？GC频繁怎么办？JVM有哪些必知的监控诊断工具？Arthas和async-profiler怎么用？本文作为JVM调优面试八股文系列的第六篇，系统讲解JVM监控诊断工具链与性能分析实战，帮你构建完整的生产问题排查能力。'
topic: java-spring
series: jvm-tuning-interview
series_order: 6
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- JVM
- 监控
- 诊断
- 性能分析
- Arthas
categories:
- Java 与 Spring
draft: false
author: 飞哥
---

> 面试高频问题：线上JVM进程突然CPU 100%怎么排查？内存泄漏怎么定位？GC频繁怎么办？JVM有哪些必知的监控诊断工具？Arthas和async-profiler怎么用？本文作为JVM调优面试八股文系列的第六篇，系统讲解JVM监控诊断工具链与性能分析实战，帮你构建完整的生产问题排查能力。

## 引言

前五篇我们系统梳理了JVM内存模型、GC算法与收集器、调优实战、类加载与JIT编译原理，以及GraalVM与AOT编译。但光有理论不够——**能不能在生产环境中快速定位问题**，才是衡量一个工程师真正掌握JVM的标准。

很多候选人对JVM调优停留在"改-Xmx"和"选G1"的层面，一旦遇到线上OOM、CPU飙高、GC频繁，却无从下手。本文从**监控工具、诊断工具、性能分析**三个层次，讲解JVM排查的完整工具链，配合真实案例，帮你构建"看得见、摸得着"的JVM实战能力。

**本文要点**：
1. JVM自带监控工具：jstat、jinfo、jmap、jstack的核心用法
2. 图形化诊断工具：JConsole、VisualVM、JMC的使用场景
3. 线上神器Arthas：从入门到高级用法
4. 性能分析利器：async-profiler与火焰图
5. 常见生产故障的排查思路与实战案例

---

## 一、JVM自带命令行工具

JDK自带了一系列命令行工具，全部位于`$JAVA_HOME/bin/`目录下，不需要额外安装，是最基础的JVM监控诊断手段。

### 1.1 jstat——GC与类加载统计

`jstat`是查看JVM统计信息最常用的工具，尤其适合观察GC趋势。

**常用命令格式：**

```bash
# 查看GC统计信息，每250ms刷新一次，共10次
jstat -gcutil <pid> 250 10

# 查看具体GC容量（字节单位）
jstat -gccapacity <pid>

# 查看编译统计
jstat -compiler <pid>

# 查看类加载统计
jstat -class <pid>
```

**输出字段解读（`-gcutil`）：**

| 字段 | 含义 |
|------|------|
| S0/S1 | Survivor区0/1使用率 |
| E | Eden区使用率 |
| O | Old区（老年代）使用率 |
| M | Metaspace使用率 |
| CCS | 压缩类空间使用率 |
| YGC/YGCT | Young GC次数/总耗时 |
| FGC/FGCT | Full GC次数/总耗时 |
| GCT | GC总耗时 |

**面试关注点：**
- YGC频繁但回收快 → Eden区可能太小
- FGC频繁且FGCT增长快 → 对象进入老年代太快，考虑调优或换GC
- M持续增长 → 可能有反射/动态代理导致的元空间问题

### 1.2 jinfo——运行时配置查看与修改

```bash
# 查看进程完整JVM参数
jinfo -flags <pid>

# 查看指定参数值
jinfo -flag MaxHeapSize <pid>
jinfo -flag PrintGCDetails <pid>

# 动态启用参数（生产慎用）
jinfo -flag +PrintGCTimeStamps <pid>
```

**面试关注点：** jinfo可以实时查看哪些参数生效，哪些是默认值。结合`jstat`一起用，可以快速判断当前GC策略是否符合预期。

### 1.3 jmap——内存映射与堆转储

`jmap`是最重要的堆内存分析工具，可以生成堆快照（heap dump）用于后续分析。

```bash
# 查看堆内存布局摘要
jmap -heap <pid>

# 查看类直方图（对象统计）
jmap -histo <pid> | head -30

# 生成堆转储文件（排查OOM必备）
jmap -dump:format=b,file=heap.hprof <pid>
```

**堆转储格式说明：**
- `format=b` 表示二进制格式
- `.hprof`文件可以用MAT、VisualVM、JProfiler等工具分析
- 生产环境dump大堆（>4GB）可能造成服务卡顿，建议在低峰期或使用`jmap -dump:live,format=b,file=xxx.hprof <pid>`只dump存活对象

**面试关注点：**
- 如果`jmap -histo`显示某个类的实例数量异常多，那就是内存泄漏的线索
- 常见泄漏对象：HashMap被不断put但从不clear、集合类作为静态变量持有大量对象、监听器未注销

### 1.4 jstack——线程快照与死锁检测

```bash
# 打印线程堆栈信息
jstack <pid>

# 打印带锁信息的线程堆栈
jstack -l <pid>

# 强制打印（即使jstack自己被阻塞）
jstack -F <pid>
```

**输出结构解读：**
```
"http-nio-8080-exec-10" #50 daemon prio=5 os_prio=0 tid=0x00007f8a4c0d1800
  nid=0x7d2a waiting for monitor entry [0x00007f89d7aef000]
   java.lang.Thread.State: BLOCKED
  - waiting to lock <0x00000000d00917d8> (a java.lang.String)
   owned by "http-nio-8080-exec-5" #45
```

**面试关注点：**
- `waiting for monitor entry` → 线程竞争锁，可能死锁或锁竞争激烈
- `waiting on condition` → 线程在等待I/O、Sleep或自定义条件
- `RUNNABLE`在native代码中 → 可能是在JNI调用或系统调用
- jstack输出最底部会自动检测死锁：`Found one Java-level deadlock`

### 1.5 实战：CPU 100%的排查流程

```bash
# 第一步：找到CPU高的Java进程
top -c

# 第二步：确认是Java进程，拿到PID

# 第三步：查看该进程的线程CPU占用
top -Hp <pid>

# 第四步：将线程ID转为十六进制
printf "%x\n" <线程PID>

# 第五步：用jstack抓线程堆栈，对比十六进制线程ID
jstack <pid> | grep -A 50 <十六进制线程ID>
```

---

## 二、图形化诊断工具

### 2.1 JConsole——最基础的JMX客户端

JConsole是JDK自带的JMX图形化客户端，可以连接本地或远程JVM进程。

**启动方式：**
```bash
jconsole
# 或
jconsole <pid>
```

**核心Tab：**
- **内存**：实时展示堆/非堆各区域使用量，有"执行GC"按钮
- **线程**：查看所有线程状态，有"检测死锁"按钮
- **类**：已加载类数量和类加载总数
- **VM摘要**：JVM参数、系统属性、运行时间

**适用场景：** 快速查看JVM概况，适合开发测试环境。

### 2.2 VisualVM——功能更全面的分析工具

VisualVM是JConsole的增强版，提供了更丰富的性能分析能力。

```bash
# 启动
jvisualvm
```

**核心功能：**
1. **线程dump**：比jstack更直观，支持保存和对比
2. **CPU Profiler**：采样分析CPU热点方法（需要JDK开发包）
3. **Heapdump分析**：支持查看对象引用链
4. **Sampler**：对CPU和内存进行采样，不影响应用运行

**面试关注点：** VisualVM可以同时监控多个JVM进程，适合对比测试不同GC策略下的表现。

### 2.3 JMC（Java Mission Control）——商业级诊断工具

JMC是Oracle官方提供的商业级诊断工具（从JDK 11开始随JDK免费提供），功能比VisualVM更强大。

**核心功能：**

1. **JFR（Java Flight Recorder）**：低开销的持续运行时数据记录
   ```bash
   # 启动30秒的JFR录制
   jcmd <pid> JFR.start duration=30s filename=recording.jfr
   
   # 检查录制状态
   jcmd <pid> JFR.name
   
   # 转储录制
   jcmd <pid> JFR.dump name=recording name=recording.jfr
   ```

2. **JFR事件类型：** GC停顿、类加载、CPU负载、内存分配、异常抛出、锁竞争等

**面试关注点：** JFR是JVM性能分析的"黑匣子"，开启后对应用影响<1%，但能记录大量有价值的事件。生产环境建议默认开启。JMC打开.jfr文件后可以直观看到各事件的时间线和火焰图。

---

## 三、Arthas——线上诊断神器

Arthas（阿尔萨斯）是阿里巴巴开源的Java诊断工具，是目前生产环境使用最广泛的JVM诊断利器。相比jstat/jstack，Arthas提供了交互式界面和更多高级功能。

### 3.1 安装与启动

```bash
# 方式一：一键启动
java -jar arthas-boot.jar

# 方式二：交互式选择进程
java -jar arthas-boot.jar <pid>

# 方式三：非交互式
as.sh <pid>
```

### 3.2 核心命令详解

#### dashboard——全局仪表盘

```bash
dashboard
```

实时展示：线程状态、内存使用、GC情况、运行时信息，每5秒刷新。

**输出结构：**
```
ID   NAME              STATE  %CPU  DELTA_T  TIME
58   http-nio-8080-e   RUNNABLE 45.2  0.452   12:34
63   C2 CompilerThread 0        0.0   0.000   0:0
     ...                   ...

Memory          used  total  max    GC    GC
heap            456M  512M   2048M  #52   #12
non-heap        120M  128M   -1   
```

#### thread——线程分析

```bash
# 查看所有线程
thread

# 查看CPU占用最高的线程
thread -n 5

# 查看阻塞中的线程
thread -b

# 查看指定线程的堆栈
thread <tid>
```

**面试关注点：** `thread -b`是排查死锁的首选，比jstack的死锁检测更详细，能直接定位到具体的代码行。

#### sc/sm——类与方法搜索

```bash
# 搜索已加载的类
sc *.Controller
sc -d com.example.UserService

# 查看类的方法
sm -d com.example.UserService
```

#### jad——反编译

```bash
# 反编译类
jad com.example.UserService

# 反编译方法
jad com.example.UserService login
```

**使用场景：** 生产环境需要临时看某个类/方法的源码，不需要拉代码再grep，直接jad定位。

#### watch——方法调用观测

```bash
# 观察方法入参和返回值
watch com.example.UserService login {params, returnObj}

# 只看返回值
watch com.example.UserService login {returnObj}

# 观察异常
watch com.example.UserService login {throwExp}

# 只看第一次调用
watch com.example.UserService login "{params, returnObj}" -x 1
```

**面试关注点：** watch是Arthas最强大的功能之一，可以在不修改代码、不重启应用的情况下，观察方法的调用参数、返回值、异常和执行时间。

#### trace——调用链路追踪

```bash
# 追踪方法调用链路和耗时
trace com.example.OrderService createOrder

# 只显示耗时>100ms的调用
trace com.example.OrderService createOrder '#cost > 100'

# 追踪多层调用
trace com.example.* * -n 5
```

**输出示例：**
```
`---[36ms] com.example.OrderService:createOrder()
    +---[5ms] com.example.InventoryService:checkStock()
    +---[28ms] com.example.PaymentService:processPayment()
    `---[2ms] com.example.OrderRepository:save()
```

**面试关注点：** trace可以清晰看到每个调用层级的时间和占比，是排查性能瓶颈的利器。`-n 5`表示只抓5次调用，防止输出过多。

#### monitor——方法调用统计

```bash
# 每60秒统计一次方法调用
monitor -c 60 com.example.OrderService createOrder
```

**输出：**
```
 timestamp         class          method       total  success  fail  avg-rt(ms)  fail-rate
 2026-08-25 10:00  OrderService   createOrder   1523   1501     22     45.3        1.44%
```

#### stack——方法调用栈

```bash
# 查看方法被哪些调用点调用
stack com.example.PaymentService:processPayment
```

#### ognl——动态执行表达式

```bash
# 查看静态字段
ognl '@com.example.Config@MAX_RETRY_COUNT'

# 修改静态字段（生产慎用）
ognl '@com.example.Config@MAX_RETRY_COUNT=5'

# 调用静态方法
ognl '@java.lang.System@gc()'
```

### 3.3 实战案例：线上OOM排查

```bash
# 1. 用dashboard确认内存持续增长
dashboard

# 2. 抓个堆快照
heapdump /tmp/heap.hprof

# 3. 下载到本地用MAT分析（需要配置arthas web console端口）

# 4. 用sc找到可疑的类
sc -d com.example.* | grep classLoader

# 5. 用watch观察对象创建
watch com.example.OrderService createOrder '{params[0].getClass().getName()}'
```

---

## 四、async-profiler与火焰图

### 4.1 简介

async-profiler是 uber 开源的低开销采样分析器，相比JMC/VisualVM的CPU Profiler，对应用影响更小，适合生产环境持续分析。

### 4.2 安装

```bash
# 下载
wget https://github.com/async-profiler/async-profiler/releases/download/v2.9/async-profiler-2.9-linux-x64.tar.gz

# 解压
tar -xzf async-profiler-2.9-linux-x64.tar.gz
```

### 4.3 核心用法

```bash
# CPU采样（30秒）
./profiler.sh -d 30 -f cpu.html <pid>

# 内存分配采样（30秒）
./profiler.sh -d 30 -e alloc -f memory.html <pid>

# 锁竞争采样
./profiler.sh -d 30 -e lock -f lock.html <pid>

# 生成火焰图（需要火焰图脚本）
./profiler.sh -d 30 --fdtransfer -f profile.svg <pid>
```

### 4.4 火焰图阅读

火焰图是一种直观的性能分析可视化方式：

- **横轴**：宽度代表采样比例，越宽=占用越多
- **纵轴**：调用栈层级，从下到上是调用链路
- **颜色区分：** CPU（红）、内存（黄）、锁（橙）

**阅读原则：**
1. 找最宽的尖峰——这是最大的瓶颈
2. 从顶部向下追——先看最高层级是哪个方法
3. 对比优化前后的火焰图——看"山头"是否降低

**面试关注点：** 火焰图是当今最流行的性能分析可视化方式，很多公司（如Netflix、Uber）都用它做性能优化分享。面试时能说出"看火焰图找热点"比"用profiler"专业得多。

---

## 五、常见生产故障排查思路

### 5.1 CPU飙高排查

**排查步骤：**
1. `top -Hp <pid>` 确认CPU高是不是Java进程
2. `jstack <pid>` 抓线程堆栈，看BLOCKED/WAITING线程比例
3. 如果是RUNNABLE，看native调用在做什么（I/O? 正则? 加密?）
4. 用Arthas `thread -n 10` 找CPU热点线程
5. 用async-profiler抓CPU火焰图定位具体方法

**常见原因：**
- 死循环（业务逻辑bug）
- 正则表达式回溯（ReDoS）
- 频繁GC（内存分配过快）
- 加密/解密、压缩/解压等CPU密集操作

### 5.2 内存泄漏排查

**排查步骤：**
1. `jstat -gcutil <pid> 1000` 观察内存持续增长不回落
2. `jmap -histo <pid>` 看对象数量排行，找异常多的类
3. `jmap -dump:format=b,file=heap.hprof <pid>` 生成堆快照
4. 用MAT打开，分析`Leak Suspects`报告
5. 找到泄漏对象后，通过GC Roots路径追引用链

**常见泄漏源：**
- 静态集合（HashMap、List）持续添加对象
- 未关闭的连接（数据库、HTTP）
- 监听器/回调未注销
- ThreadLocal未清理
- 动态类加载过多导致元空间泄漏

### 5.3 GC频繁排查

**排查步骤：**
1. `jstat -gcutil <pid> 1000` 看YGC/FGC频率和耗时
2. `jstat -gccapacity <pid>` 看各区容量配置
3. `jstat -gcold <pid>` 看老年代对象增长速率
4. 如果对象年龄频繁进入老年代 → 检查Minor GC存活对象大小

**常见原因：**
- Eden区太小（频繁Minor GC）
- 大对象直接进老年代（`-XX:PretenureSizeThreshold`）
- 内存分配速率过高（代码中有批量创建对象逻辑）
- 老年代空间不足（频繁Full GC）

### 5.4 死锁/线程阻塞排查

**排查步骤：**
1. `jstack -l <pid>` 看底部是否有死锁报告
2. `Arthas thread -b` 找阻塞其他线程的线程
3. 看BLOCKED线程在等哪把锁，持有锁的线程在做什么
4. 分析锁竞争热点代码

---

## 六、工具选型建议

| 场景 | 推荐工具 | 原因 |
|------|----------|------|
| 快速查看GC概况 | jstat | 无需额外安装，最快 |
| CPU/内存实时监控 | Arthas dashboard | 功能全，交互友好 |
| 生产性能分析 | async-profiler + 火焰图 | 低开销，可持续采样 |
| 堆快照分析 | MAT / JProfiler | 可视化好，引用链清晰 |
| 持续生产监控 | JMC + JFR | 内核级低开销录制 |
| 方法级调用分析 | Arthas watch/trace | 不重启，动态观测 |
| 死锁/阻塞排查 | Arthas thread -b | 比jstack更准 |

---

## 总结

JVM监控诊断是工程能力的硬通货——能快速定位线上问题的工程师，在团队中永远是稀缺资源。

本文从**命令行工具（jstat/jinfo/jmap/jstack）→ 图形化工具（JConsole/VisualVM/JMC）→ Arthas → async-profiler**，构建了一套从浅到深的工具链，配合CPU高、内存泄漏、GC频繁、死锁四种典型场景的排查思路，帮你把JVM知识从"理论"变成"实战"。

**下期预告：** JVM调优面试八股文系列最后一篇，我们将综合运用本系列学到的所有知识，进行30道高频面试真题的串讲，帮你做最后的冲刺复习。

---

> 如果觉得有收获，欢迎在评论区交流你使用这些工具的经验和踩坑经历。
