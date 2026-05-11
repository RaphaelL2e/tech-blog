---
title: "JVM 调优实战：从 OOM 到 GC 优化"
date: 2026-05-11T14:20:00+08:00
draft: false
categories: ["java"]
tags: ["jvm", "调优", "OOM", "GC", "G1", "ZGC"]
---

# JVM 调优实战：从 OOM 到 GC 优化

> 面试高频问题：如何排查 OOM？常用 JVM 参数有哪些？G1 和 ZGC 怎么选型？

## 引言

JVM 调优是 Java 高级工程师的必备技能。一个未经调优的 JVM 应用，在生产环境中可能面临 OOM、频繁 GC、停顿过长等问题。本文将从问题排查到参数调优，全面解析 JVM 调优实战。

## 一、OOM 问题排查

### 1.1 OOM 类型一览

| OOM 类型 | 触发原因 | 解决方案 |
|---------|---------|---------|
| `Java heap space` | 堆内存不足 | 增大 `-Xmx`，排查内存泄漏 |
| `GC overhead limit exceeded` | GC 占用 98% 时间却回收 <2% 堆 | 优化代码，增大堆 |
| `Metaspace` | 元空间不足 | 增大 `-XX:MaxMetaspaceSize` |
| `Unable to create new native thread` | 线程数超限 | 减小栈大小 `-Xss`，调整系统限制 |
| `Direct buffer memory` | 堆外内存不足 | 增大 `-XX:MaxDirectMemorySize` |
| `Requested array size exceeds VM limit` | 数组大小超过限制 | 拆分大数组 |

### 1.2 堆溢出（Java heap space）

**现象**：
```bash
java.lang.OutOfMemoryError: Java heap space
    at java.util.Arrays.copyOf(Arrays.java:3210)
    at java.util.ArrayList.grow(ArrayList.java:265)
```

**排查步骤**：

```bash
# 1. 设置 OOM 时自动 dump 堆
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/path/to/dumps

# 2. 手动 dump 堆（在线）
jmap -dump:live,format=b,file=heap.hprof <pid>

# 3. 使用 MAT 分析
# 下载：https://www.eclipse.org/mat/
# 打开 heap.hprof，查看 Dominator Tree
```

**常见原因**：
```java
// 原因 1：内存泄漏
static List<Object> list = new ArrayList<>();
void leak() {
    while (true) {
        list.add(new Object());  // 静态集合持有对象
    }
}

// 原因 2：缓存无上限
Map<Key, Value> cache = new HashMap<>();
void addToCache(Key k, Value v) {
    cache.put(k, v);  // 无淘汰策略
}

// 解决：使用 WeakHashMap 或 LRU 缓存
Map<Key, Value> cache = new LinkedHashMap<>(16, 0.75f, true) {
    protected boolean removeEldestEntry(Map.Entry<Key, Value> eldest) {
        return size() > 1000;  // 限制大小
    }
};
```

### 1.3 GC 开销过大（GC overhead limit exceeded）

**现象**：
```bash
java.lang.OutOfMemoryError: GC overhead limit exceeded
```

**原因**：GC 时间超过 98%，但只回收了 <2% 的堆内存。

**排查**：
```bash
# 1. 开启 GC 日志
-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:gc.log

# 2. 分析 GC 频率
grep "Full GC" gc.log | wc -l  # 频繁 Full GC？

# 3. 查看每次 GC 后的堆剩余
grep -A1 "Full GC" gc.log
```

**解决**：
```bash
# 增大堆
-Xmx4g -Xms4g

# 优化代码：减少临时对象
// 错误示例
String s = "";
for (int i = 0; i < 100000; i++) {
    s += i;  // 每次循环创建新 String
}

// 正确示例
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 100000; i++) {
    sb.append(i);
}
String s = sb.toString();
```

### 1.4 元空间溢出（Metaspace）

**现象**：
```bash
java.lang.OutOfMemoryError: Metaspace
```

**原因**：
- 加载了太多类（动态代理、反射生成类）
- 元空间大小未限制

**排查**：
```bash
# 查看元空间使用
jstat -gcmetacapacity <pid>

# 输出示例
   MCMN       MCMX        MCN         ECX         ECU
     0.0   1048576.0    1048576.0    1048576.0    984560.0
# ECU = 已使用，接近 ECX = 容量 → 溢出
```

**解决**：
```bash
# 增大元空间
-XX:MetaspaceSize=256m
-XX:MaxMetaspaceSize=512m

# 排查类加载泄漏
# 使用 -verbose:class 查看类加载
java -verbose:class MyApp
```

### 1.5 无法创建线程（Unable to create new native thread）

**现象**：
```bash
java.lang.OutOfMemoryError: Unable to create new native thread
```

**原因**：
- 线程数达到系统限制
- 每个线程的栈空间过大

**排查**：
```bash
# 查看系统线程限制
ulimit -u

# 查看当前线程数
ps -eLf | grep java | wc -l
```

**解决**：
```bash
# 减小栈大小（默认 1MB）
-Xss256k

# 增大系统限制
ulimit -u 65535

# 使用线程池，避免无限制创建线程
ExecutorService pool = Executors.newFixedThreadPool(100);
```

## 二、GC 日志分析

### 2.1 开启 GC 日志

```bash
# JDK 8 及之前
-XX:+PrintGCDetails
-XX:+PrintGCDateStamps
-Xloggc:/path/to/gc.log
-XX:+UseGCLogFileRotation
-XX:NumberOfGCLogFiles=5
-XX:GCLogFileSize=10M

# JDK 9+（统一日志）
-Xlog:gc*:file=/path/to/gc.log:time,uptime,level,tags
```

### 2.2 解读 GC 日志

**Minor GC 日志**：
```bash
[GC (Allocation Failure) [PSYoungGen: 33280K->4376K(38400K)] 33280K->4384K(125952K), 0.0064567 secs] [Times: user=0.02 sys=0.00, real=0.01 secs]
```

**解读**：
```
[GC 类型] [收集器: 回收前->回收后(总容量)] 堆回收前->回收后(堆总容量), 耗时
         [CPU 时间: user=用户态 sys=内核态 real=实际]
```

**Full GC 日志**：
```bash
[Full GC (Ergonomics) [PSYoungGen: 0K->0K(38400K)] [ParOldGen: 4376K->4296K(87552K)] 4376K->4296K(125952K), [Metaspace: 2647K->2647K(1056768K)], 0.0123456 secs] [Times: user=0.05 sys=0.00, real=0.01 secs]
```

### 2.3 GC 日志分析工具

| 工具 | 特点 |
|------|------|
| **GCViewer** | 开源，图形化展示 GC 事件 |
| **GCEasy** | 在线工具，https://gceasy.io |
| **GCPlot** | 在线，实时分析 |
| **JClarity** | 商业工具，AI 分析 |

```bash
# 使用 GCViewer
java -jar gcviewer-1.36.jar gc.log
```

## 三、JVM 参数调优

### 3.1 基础参数

```bash
# 堆大小（必须设置相等，避免动态调整）
-Xms4g
-Xmx4g

# 新生代大小
-Xmn2g              # 或 -XX:NewSize=2g -XX:MaxNewSize=2g

# 元空间
-XX:MetaspaceSize=256m
-XX:MaxMetaspaceSize=512m

# 栈大小
-Xss256k            # 减少栈大小，允许更多线程
```

### 3.2 收集器选择

**场景 1：吞吐量优先（后台批处理）**
```bash
-XX:+UseParallelGC
-XX:MaxGCPauseMillis=200    # 目标停顿时间
-XX:GCTimeRatio=19           # GC 时间占比 1/(1+19) = 5%
```

**场景 2：低停顿（Web 应用）**
```bash
# JDK 8：CMS（已废弃）
-XX:+UseConcMarkSweepGC
-XX:CMSInitiatingOccupancyFraction=70
-XX:+UseCMSInitiatingOccupancyOnly

# JDK 9+：G1
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
```

**场景 3：超大堆（> 16GB）**
```bash
-XX:+UseZGC
-XX:ZAllocationSpikeTolerance=5   # 分配尖峰容忍度
```

### 3.3 G1 调优参数

```bash
# 启用 G1
-XX:+UseG1GC

# 堆大小
-Xms4g -Xmx4g

# 目标停顿时间（核心参数）
-XX:MaxGCPauseMillis=200   # 默认 200ms

# Region 大小（1MB-32MB，必须是 2 的幂）
-XX:G1HeapRegionSize=4m

# 并发标记周期触发阈值
-XX:InitiatingHeapOccupancyPercent=45  # 默认 45%

# 年轻代大小（不推荐手动设置）
# -XX:G1NewSizePercent=5      # 最小年轻代占比
# -XX:G1MaxNewSizePercent=60  # 最大年轻代占比

# 避免 Full GC
-XX:G1MixedGCLiveThresholdPercent=85  # 存活对象占比阈值
-XX:G1HeapWastePercent=5             # 允许浪费的堆比例
```

### 3.4 ZGC 调优参数

```bash
# 启用 ZGC（JDK 11+）
-XX:+UseZGC

# 堆大小（ZGC 对大堆更友好）
-Xms16g -Xmx16g

# 并发 GC 线程数
-XX:ConcGCThreads=4

# 分配尖峰容忍度
-XX:ZAllocationSpikeTolerance=5

# 未提交内存延迟回收
-XX:ZUncommitDelay=300    # 默认 300 秒
```

## 四、实战调优案例

### 案例 1：电商网站频繁 Full GC

**现象**：
- 高峰期每分钟 2-3 次 Full GC
- 每次 Full GC 停顿 1-2 秒
- 用户投诉响应慢

**排查**：
```bash
# 1. 查看 GC 日志
grep "Full GC" gc.log | tail -20

# 2. 分析老年代占用
jstat -gc <pid> 1000 10

# 输出：
# S0C    S1C    S0U    S1U      EC       EU        OC         OU       MC
# 0.0    0.0    0.0    0.0    33280.0  33280.0   87552.0    87400.0   2647.0
#                                      ↑ 老年代几乎满
```

**原因**：
- 大对象直接进入老年代
- 年轻代过小，对象过早晋升

**解决**：
```bash
# 1. 增大年轻代
-Xmn4g   # 原 1g → 4g

# 2. 设置大对象阈值（只对 Serial/ParNew 有效）
-XX:PretenureSizeThreshold=1m

# 3. 优化代码：避免大对象
// 原代码：一次性加载所有数据
List<Order> orders = orderDao.findAll();

// 优化：分页查询
int pageSize = 1000;
for (int page = 0; ; page++) {
    List<Order> orders = orderDao.findPage(page, pageSize);
    if (orders.isEmpty()) break;
    process(orders);
}
```

**效果**：
- Full GC 频率：2-3 次/分钟 → 1 次/小时
- 停顿时间：1-2 秒 → 200ms 以内

### 案例 2：接口超时（GC 停顿过长）

**现象**：
- P99 响应时间 5 秒
- GC 日志显示长停顿

**排查**：
```bash
# 使用 GCEasy 分析
# 上传 gc.log 到 https://gceasy.io

# 结果：
# - Max GC Pause: 3200ms
# - Average GC Pause: 800ms
# - Throughput: 85%
```

**原因**：
- 使用 CMS 收集器，并发模式失败
- 堆内存不足

**解决**：
```bash
# 1. 切换到 G1
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200

# 2. 增大堆
-Xms8g -Xmx8g

# 3. 调整并发标记阈值
-XX:InitiatingHeapOccupancyPercent=35  # 更早启动并发标记
```

**效果**：
- Max GC Pause: 3200ms → 250ms
- P99 响应时间：5 秒 → 500ms
- Throughput: 85% → 98%

### 案例 3：内存泄漏（ slowly growing heap ）

**现象**：
- 堆内存使用率缓慢增长
- 几天后触发 OOM

**排查**：
```bash
# 1. 定期 dump 堆
jmap -dump:live,format=b,file=heap1.hprof <pid>
# 等待 1 小时
jmap -dump:live,format=b,file=heap2.hprof <pid>

# 2. 使用 MAT 对比两个堆 dump
# 打开 MAT → Compare Bug Report → 选择两个 hprof 文件

# 3. 查看 Dominator Tree
# 发现：com.example.Cache 持有 80% 的堆
```

**原因**：
```java
// 错误的缓存实现
static Map<String, Object> cache = new HashMap<>();

void addToCache(String key, Object value) {
    cache.put(key, value);  // 无淘汰策略，无限增长
}
```

**解决**：
```java
// 使用 Guava Cache
Cache<String, Object> cache = CacheBuilder.newBuilder()
    .maximumSize(10000)           // 最大条目
    .expireAfterWrite(10, TimeUnit.MINUTES)  // 过期时间
    .build();

void addToCache(String key, Object value) {
    cache.put(key, value);
}
```

## 五、JVM 监控工具

### 5.1 命令行工具

| 工具 | 功能 |
|------|------|
| `jps` | 查看 Java 进程 |
| `jstat` | 查看 GC、类加载统计 |
| `jmap` | 查看堆内存、dump 堆 |
| `jhat` | 分析堆 dump（已废弃，推荐 MAT） |
| `jstack` | 查看线程栈 |
| `jinfo` | 查看/修改 JVM 参数 |
| `jcmd` | 综合工具（JDK 7+） |

**使用示例**：
```bash
# 查看 GC 统计（每 1 秒刷新）
jstat -gc <pid> 1000

# dump 堆
jmap -dump:live,format=b,file=heap.hprof <pid>

# 查看线程栈（排查死锁）
jstack <pid> > thread.txt

# 综合命令（JDK 7+）
jcmd <pid> GC.heap_dump /tmp/heap.hprof
jcmd <pid> Thread.print
jcmd <pid> VM.flags
```

### 5.2 图形化工具

| 工具 | 特点 |
|------|------|
| **JVisualVM** | JDK 自带，基本监控 |
| **JProfiler** | 商业工具，功能强大 |
| **Java Mission Control (JMC)** | Oracle 官方，低开销 |
| **MAT (Memory Analyzer)** | Eclipse 基金会，内存分析 |

**JVisualVM 使用**：
```bash
# 启动
jvisualvm

# 功能：
# - 监视 CPU、内存、类、线程
# - 线程 dump
# - 堆 dump
# - 采样器（CPU、内存）
```

### 5.3 在线监控

```bash
# Prometheus + Grafana
# 1. 启用 JMX Exporter
java -javaagent:jmx_exporter.jar=8080:config.yaml MyApp

# 2. Prometheus 配置
scrape_configs:
  - job_name: 'java'
    static_configs:
      - targets: ['localhost:8080']

# 3. Grafana 导入 JVM 仪表盘
# 模板 ID: 8563
```

## 六、面试高频问题

### Q1：如何排查 OOM？

**答**：
1. 设置 `-XX:+HeapDumpOnOutOfMemoryError` 自动 dump
2. 使用 MAT 分析堆 dump，找占用最大的对象
3. 检查是否存在内存泄漏（集合持有、缓存无上限）
4. 调整 `-Xmx` 或优化代码

### Q2：Minor GC 和 Full GC 的区别？

**答**：
- **Minor GC**：新生代 GC，频繁但停顿短
- **Full GC**：整堆 GC，停顿长，应尽量避免

### Q3：G1 和 CMS 的区别？

**答**：
| 特性 | CMS | G1 |
|------|-----|-----|
| 算法 | 标记-清除 | 标记-整理 |
| 内存管理 | 固定新生代/老年代 | Region 动态划分 |
| 碎片 | 有 | 无（整理） |
| 停顿 | 不可预测 | 可预测 |
| JDK 版本 | 已废弃 | 9+ 默认 |

### Q4：常用 JVM 调优参数？

**答**：
```bash
-Xms4g -Xmx4g          # 堆大小
-Xmn2g                  # 新生代
-XX:MetaspaceSize=256m  # 元空间初始大小
-XX:+UseG1GC            # 使用 G1
-XX:MaxGCPauseMillis=200 # 目标停顿时间
```

### Q5：如何选择合适的收集器？

**答**：
- 吞吐量优先 → Parallel GC
- 低停顿（堆 < 6GB）→ CMS（JDK 8）或 G1
- 低停顿（堆 > 6GB）→ G1 或 ZGC
- 超大堆（> 16GB）→ ZGC

## 七、总结

**JVM 调优核心步骤**：
1. **监控**：GC 日志、JVisualVM、Prometheus
2. **分析**：MAT、GCViewer、GCEasy
3. **调优**：调整参数、优化代码
4. **验证**：压测、监控指标

**调优原则**：
- 优先使用 G1/ZGC（低停顿）
- 设置合理的堆大小（`-Xms` = `-Xmx`）
- 避免频繁 Full GC
- 定期监控，防患未然

**常用参数速查**：
```bash
# 基础
-Xms4g -Xmx4g -Xmn2g -Xss256k

# GC 日志
-XX:+PrintGCDetails -XX:+PrintGCDateStamps -Xloggc:gc.log

# OOM 诊断
-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp

# 收集器
-XX:+UseG1GC -XX:MaxGCPauseMillis=200
```

---

**下一篇预告**：Spring IoC 容器深度解析 —— Bean 生命周期、依赖注入原理

**参考资料**：
- 《深入理解 Java 虚拟机》- 周志明
- 《Java 性能优化权威指南》- Charlie Hunt
- Oracle 官方文档：https://docs.oracle.com/javase/8/docs/technotes/tools/
