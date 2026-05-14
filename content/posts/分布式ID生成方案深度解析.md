---
title: "分布式 ID 生成方案深度解析"
date: 2026-05-14T11:40:00+08:00
draft: false
categories: ["分布式系统"]
tags: ["分布式ID", "Snowflake", "UUID", "Leaf", "号段模式"]
---

# 分布式 ID 生成方案深度解析

## 一、引言

在分布式系统中，唯一 ID 的生成是一个基础且关键的问题。数据库自增 ID 在分库分表后无法保证全局唯一，UUID 性能差且无序，如何高效生成全局唯一、趋势递增的 ID 是面试高频考点。

**本文要点**：
1. 分布式 ID 的核心要求
2. UUID 方案
3. 数据库自增方案（步长法）
4. 数据库号段模式
5. Snowflake 雪花算法
6. 美团 Leaf 方案
7. 百度 UidGenerator
8. 方案对比与选型
9. 面试高频问题

---

## 二、分布式 ID 的核心要求

### 2.1 基本要求

| 要求 | 描述 | 原因 |
|------|------|------|
| **全局唯一** | ID 在整个分布式系统中唯一 | 分库分表后不能重复 |
| **趋势递增** | ID 整体趋势递增（不要求严格递增） | 数据库索引性能（B+ 树） |
| **高性能** | 生成速度快，低延迟 | 高并发场景 |
| **高可用** | ID 生成服务不能成为瓶颈 | 系统可用性 |

### 2.2 额外要求（加分项）

| 要求 | 描述 |
|------|------|
| **信息安全** | ID 不暴露业务信息（用户量、订单量） |
| **可读性** | ID 有一定含义（时间、类型等） |
| **长度固定** | 方便存储和索引 |
| **无依赖** | 不依赖外部服务（数据库、Redis） |

### 2.3 为什么不用数据库自增 ID

```
单库：
  自增 ID = 1, 2, 3, 4, 5 ... ✅

分库分表后：
  库1: 自增 ID = 1, 2, 3, 4 ...
  库2: 自增 ID = 1, 2, 3, 4 ...  ← 重复！❌
  
解决（步长法）：
  库1: 自增 ID = 1, 3, 5, 7 ...（步长=2，起始=1）
  库2: 自增 ID = 2, 4, 6, 8 ...（步长=2，起始=2）
  
问题：
  - 扩容困难（需要修改步长和起始值）
  - 无法动态调整
```

---

## 三、UUID 方案

### 3.1 UUID 概述

**UUID**（Universally Unique Identifier）是 128 位的唯一标识符。

**版本**：

| 版本 | 生成方式 | 特点 |
|------|---------|------|
| UUID v1 | 基于时间戳 + MAC 地址 | 有序，但暴露 MAC |
| UUID v3 | 基于 MD5 哈希 | 确定性 |
| UUID v4 | 基于随机数 | 最常用，无序 |
| UUID v5 | 基于 SHA-1 哈希 | 确定性 |
| UUID v7 | 基于时间戳（毫秒级） | 有序，新标准 |

### 3.2 UUID v4 示例

```java
String uuid = UUID.randomUUID().toString();
// → "550e8400-e29b-41d4-a716-446655440000"

// 去掉横线
String id = uuid.replace("-", "");
// → "550e8400e29b41d4a716446655440000"（32 位十六进制 = 128 位）
```

### 3.3 UUID 的优缺点

**优点**：
- 全局唯一（几乎不可能重复）
- 无需中心化服务（本地生成）
- 生成速度极快

**缺点**：
- **无序**：不适合做数据库主键（B+ 树频繁分裂）
- **太长**：36 字节（带横线），32 字节（去横线）
- **不可读**：无业务含义
- **索引性能差**：UUID 作为主键，插入性能比自增 ID 低 30%-50%

**UUID 做主键的性能问题**：

```
自增 ID（有序）：
  B+ 树叶子节点顺序追加 → 写入快
  
UUID（无序）：
  B+ 树叶子节点随机插入 → 频繁页分裂 → 写入慢
  聚簇索引（InnoDB）主键无序 → 二级索引存储主键 → 空间浪费
```

### 3.4 UUID v7（新标准）

UUID v7 是 2024 年正式发布的 RFC 9562 标准，解决了无序问题。

**结构**：

```
 48 bit 时间戳（毫秒） | 4 bit 版本 | 12 bit 随机 | 2 bit 变体 | 62 bit 随机
```

**特点**：
- 时间戳在前，保证趋势递增
- 兼容 UUID 格式
- 适合做数据库主键

```java
// Java 21+ 支持
UUID uuid = UUID.randomUUID();  // 默认 v4
// 如果使用 v7 生成库
// UUID v7 = UUIDv7.randomUUID();
// → "0190a6a8-7b3c-7d3e-8f4a-5b6c7d8e9f0a"
```

---

## 四、数据库号段模式

### 4.1 基本原理

**号段模式**：每次从数据库获取一批 ID（号段），用完后再获取下一批。减少数据库访问频率。

**数据库表设计**：

```sql
CREATE TABLE id_segment (
    biz_tag    VARCHAR(64) PRIMARY KEY,  -- 业务标识
    max_id     BIGINT NOT NULL,          -- 当前最大 ID
    step       INT NOT NULL,             -- 步长（号段大小）
    version    INT NOT NULL,             -- 乐观锁版本号
    update_time DATETIME DEFAULT NOW()
);

-- 初始化
INSERT INTO id_segment (biz_tag, max_id, step, version) 
VALUES ('order', 0, 1000, 0);
```

### 4.2 号段获取流程

```
1. 查询当前号段：
   SELECT max_id, step, version FROM id_segment WHERE biz_tag = 'order'
   → max_id = 0, step = 1000

2. 更新号段（乐观锁）：
   UPDATE id_segment 
   SET max_id = max_id + step, version = version + 1 
   WHERE biz_tag = 'order' AND version = 0
   → max_id = 1000

3. 获取号段范围：[1, 1000]

4. 在内存中分配 ID：
   1, 2, 3, ..., 1000

5. 用完后，再获取下一个号段：
   UPDATE id_segment 
   SET max_id = max_id + step, version = version + 1 
   WHERE biz_tag = 'order' AND version = 1
   → max_id = 2000
   
6. 获取号段范围：[1001, 2000]
```

### 4.3 号段模式的优化

**双 Buffer 机制**：

```
问题：号段用完时，需要访问数据库获取新号段 → 延迟

解决：预加载
  - 当前号段使用到 10% 时，异步加载下一个号段
  - 保证始终有可用的号段

Buffer A: [1, 1000]    ← 当前使用
Buffer B: [1001, 2000] ← 预加载完成

当 A 用完 → 切换到 B
当 B 使用到 10% → 预加载 Buffer C: [2001, 3000]
```

### 4.4 代码实现

```java
public class SegmentIdGenerator {
    
    private final JdbcTemplate jdbcTemplate;
    private final String bizTag;
    
    private AtomicLong currentId;  // 当前 ID
    private long maxId;             // 号段最大 ID
    private long step;              // 步长
    
    public synchronized long nextId() {
        // 号段用完，获取新号段
        if (currentId == null || currentId.get() > maxId) {
            fetchNewSegment();
        }
        return currentId.getAndIncrement();
    }
    
    private void fetchNewSegment() {
        int retryCount = 0;
        while (retryCount < 3) {
            // 1. 查询当前号段信息
            Map<String, Object> segment = jdbcTemplate.queryForMap(
                "SELECT max_id, step, version FROM id_segment WHERE biz_tag = ?", bizTag);
            long currentMaxId = (Long) segment.get("max_id");
            long segmentStep = (Long) segment.get("step");
            int version = (Integer) segment.get("version");
            
            // 2. 更新号段（乐观锁）
            int updated = jdbcTemplate.update(
                "UPDATE id_segment SET max_id = max_id + step, version = version + 1 " +
                "WHERE biz_tag = ? AND version = ?", bizTag, version);
            
            if (updated > 0) {
                // 3. 设置新号段
                this.currentId = new AtomicLong(currentMaxId + 1);
                this.maxId = currentMaxId + segmentStep;
                this.step = segmentStep;
                return;
            }
            retryCount++;
        }
        throw new RuntimeException("Failed to fetch new segment");
    }
}
```

---

## 五、Snowflake 雪花算法

### 5.1 基本原理

**Snowflake** 是 Twitter 开源的分布式 ID 生成算法，生成 64 位的长整型 ID。

**结构**：

```
0 | 00000000 00000000 00000000 00000000 00000000 0 | 00000 00000 | 000000000000
↑                    ↑                              ↑      ↑            ↑
1 bit            41 bit 时间戳                   10 bit    12 bit
符号位          （毫秒级，约 69 年）            机器 ID    序列号

总计：1 + 41 + 10 + 12 = 64 bit
```

**各部分说明**：

| 部分 | 位数 | 说明 |
|------|------|------|
| **符号位** | 1 bit | 始终为 0（保证正数） |
| **时间戳** | 41 bit | 毫秒级时间戳差值（当前时间 - 自定义纪元） |
| **机器 ID** | 10 bit | 5 bit 数据中心 ID + 5 bit 工作机器 ID（最多 1024 台） |
| **序列号** | 12 bit | 同一毫秒内的序列号（最多 4096 个/毫秒） |

**性能**：
- 单机每毫秒最多生成 4096 个 ID
- 单机每秒最多生成 **409.6 万** 个 ID

### 5.2 Snowflake 代码实现

```java
public class SnowflakeIdGenerator {
    
    // 起始时间戳（2024-01-01 00:00:00）
    private final long epoch = 1704067200000L;
    
    // 各部分占用的位数
    private final long workerIdBits = 5L;
    private final long datacenterIdBits = 5L;
    private final long sequenceBits = 12L;
    
    // 各部分最大值
    private final long maxWorkerId = ~(-1L << workerIdBits);        // 31
    private final long maxDatacenterId = ~(-1L << datacenterIdBits); // 31
    private final long maxSequence = ~(-1L << sequenceBits);          // 4095
    
    // 各部分左移位数
    private final long workerIdShift = sequenceBits;                          // 12
    private final long datacenterIdShift = sequenceBits + workerIdBits;       // 17
    private final long timestampShift = sequenceBits + workerIdBits + datacenterIdBits; // 22
    
    private final long workerId;
    private final long datacenterId;
    private long sequence = 0L;
    private long lastTimestamp = -1L;
    
    public SnowflakeIdGenerator(long workerId, long datacenterId) {
        if (workerId > maxWorkerId || workerId < 0) {
            throw new IllegalArgumentException("workerId out of range");
        }
        if (datacenterId > maxDatacenterId || datacenterId < 0) {
            throw new IllegalArgumentException("datacenterId out of range");
        }
        this.workerId = workerId;
        this.datacenterId = datacenterId;
    }
    
    public synchronized long nextId() {
        long timestamp = System.currentTimeMillis();
        
        // 时钟回拨检测
        if (timestamp < lastTimestamp) {
            throw new RuntimeException(
                String.format("Clock moved backwards. Refusing to generate id for %d milliseconds",
                    lastTimestamp - timestamp));
        }
        
        if (timestamp == lastTimestamp) {
            // 同一毫秒内，序列号自增
            sequence = (sequence + 1) & maxSequence;
            if (sequence == 0) {
                // 序列号溢出，等待下一毫秒
                timestamp = waitNextMillis(lastTimestamp);
            }
        } else {
            // 不同毫秒，序列号从 0 开始
            sequence = 0L;
        }
        
        lastTimestamp = timestamp;
        
        // 组装 ID
        return ((timestamp - epoch) << timestampShift)
             | (datacenterId << datacenterIdShift)
             | (workerId << workerIdShift)
             | sequence;
    }
    
    private long waitNextMillis(long lastTimestamp) {
        long timestamp = System.currentTimeMillis();
        while (timestamp <= lastTimestamp) {
            timestamp = System.currentTimeMillis();
        }
        return timestamp;
    }
}
```

### 5.3 Snowflake 的时钟回拨问题

**问题**：如果系统时钟被回拨，可能生成重复 ID。

**原因**：
```
T1: 生成 ID（时间戳 = 1000）
T2: 时钟被回拨到 990
T3: 生成 ID（时间戳 = 990）← 可能与之前重复！
```

**解决方案**：

| 方案 | 描述 | 优缺点 |
|------|------|--------|
| **直接报错** | 检测到回拨就抛异常 | 简单，但影响可用性 |
| **等待追回** | 等待时钟追回到上次时间 | 适合小幅回拨（< 5ms） |
| **预生成缓存** | 提前生成一批 ID 缓存 | 复杂，但有缓冲 |
| **多 Worker 位** | 回拨时切换 Worker ID | 百度 UidGenerator 方案 |

**等待追回实现**：

```java
public synchronized long nextId() {
    long timestamp = System.currentTimeMillis();
    
    if (timestamp < lastTimestamp) {
        long offset = lastTimestamp - timestamp;
        if (offset <= 5) {
            // 小幅回拨，等待追回
            try {
                Thread.sleep(offset);
            } catch (InterruptedException e) {
                throw new RuntimeException("Interrupted while waiting for clock to catch up");
            }
            timestamp = System.currentTimeMillis();
        } else {
            // 大幅回拨，报错
            throw new RuntimeException("Clock moved backwards by " + offset + "ms");
        }
    }
    // ... 后续逻辑同上
}
```

---

## 六、美团 Leaf

### 6.1 Leaf 概述

**Leaf** 是美团开源的分布式 ID 生成系统，提供两种模式：

| 模式 | 原理 | 特点 |
|------|------|------|
| **Leaf-segment** | 数据库号段模式 | 简单可靠，趋势递增 |
| **Leaf-snowflake** | Snowflake + ZooKeeper | 无依赖数据库，严格递增 |

### 6.2 Leaf-segment（号段模式）

**数据库表**：

```sql
CREATE TABLE leaf_alloc (
    biz_tag     VARCHAR(128) PRIMARY KEY,
    max_id      BIGINT NOT NULL,
    step        INT NOT NULL,
    description VARCHAR(256),
    update_time DATETIME DEFAULT NOW()
);
```

**双 Buffer 优化**：

```
               ┌──────────────────────────────────────┐
               │           Leaf-segment               │
               │                                      │
               │   Segment A (current)  Segment B     │
               │   [1, 1000]          [1001, 2000]   │
               │   ↑ 当前分配          ↑ 预加载完成    │
               │                                      │
               │   当 A 使用到 10% → 预加载 C          │
               │   当 A 用完 → 切换到 B               │
               └──────────────────────────────────────┘
```

**关键特性**：
- 双 Buffer 保证 ID 生成的连续性
- 号段用完前异步加载下一号段
- 数据库挂掉仍可用一段时间（Buffer 中还有 ID）

### 6.3 Leaf-snowflake

**优化点**：
1. **Worker ID 由 ZooKeeper 分配**（不需要手动配置）
2. **时钟回拨检测**（ZooKeeper 记录上次时间戳）

**Worker ID 分配**：

```
1. 启动时在 ZooKeeper 创建持久顺序节点：
   /leaf/snowflake/{ip}:{port}:{index}
   
2. 节点的序号就是 Worker ID

3. 启动时检查 ZooKeeper 中记录的上次时间戳
   → 如果当前时间 < 记录时间 → 时钟回拨 → 报错
```

**架构**：

```
应用服务 → Leaf SDK → ZooKeeper（分配 Worker ID + 时钟检测）
```

---

## 七、百度 UidGenerator

### 7.1 UidGenerator 概述

**UidGenerator** 是百度开源的分布式 ID 生成器，基于 Snowflake 算法改进。

**两种模式**：

| 模式 | 描述 | QPS |
|------|------|-----|
| **DefaultUidGenerator** | 标准Snowflake，时间戳秒级 | ~600万/秒 |
| **CachedUidGenerator** | RingBuffer 预生成 + 缓存 | **~2000万/秒** |

### 7.2 CachedUidGenerator 原理

**核心思想**：预生成一批 ID 放入 RingBuffer，消费和生成并行。

**RingBuffer 结构**：

```
RingBuffer（环形数组）
  slots[]: 存储 ID
  flags[]: 存储标志（是否可消费/可填充）
  
  tail: 消费指针
  head: 填充指针

  ┌───┬───┬───┬───┬───┬───┬───┬───┐
  │ 1 │ 2 │ 3 │ 4 │ 5 │   │   │   │
  └───┴───┴───┴───┴───┴───┴───┴───┘
    ↑                   ↑
   tail                head
  (消费)              (填充)
```

**工作流程**：

```
1. 初始化时，预填满 RingBuffer
2. 消费者从 tail 取 ID，tail 后移
3. 填充线程从 head 填充新 ID，head 后移
4. 当 RingBuffer 剩余量 < 阈值 → 触发异步填充
5. 并行消费和填充，QPS 极高
```

### 7.3 UidGenerator 的位分配

```
DefaultUidGenerator:
  sign(1) + deltaSeconds(28) + workerId(22) + sequence(13)
  
  时间戳 28 bit（秒级，约 8.5 年）
  机器 ID 22 bit（约 420 万台）
  序列号 13 bit（每秒 8192 个）

CachedUidGenerator:
  sign(1) + deltaSeconds(28) + workerId(22) + sequence(13)
  （位分配相同，但预生成缓存提升性能）
```

---

## 八、方案对比

### 8.1 全面对比

| 方案 | 唯一性 | 有序性 | 性能 | 依赖 | 时钟回拨 |
|------|--------|--------|------|------|---------|
| **UUID** | ✅ | ❌ | 高 | 无 | 无影响 |
| **数据库自增** | ✅ | ✅ 严格 | 低 | DB | 无影响 |
| **号段模式** | ✅ | ✅ 趋势 | 中 | DB | 无影响 |
| **Snowflake** | ✅ | ✅ 趋势 | 高 | 无 | ⚠️ 需处理 |
| **Leaf-segment** | ✅ | ✅ 趋势 | 中 | DB | 无影响 |
| **Leaf-snowflake** | ✅ | ✅ 趋势 | 高 | ZK | ⚠️ 需处理 |
| **UidGenerator** | ✅ | ✅ 趋势 | 极高 | DB/ZK | ⚠️ 需处理 |

### 8.2 性能对比

```
UUID:           ~1000万/秒（本地生成，无 IO）
Snowflake:      ~400万/秒（单机）
Leaf-segment:   ~10万/秒（受数据库影响）
Leaf-snowflake: ~400万/秒（单机）
UidGenerator:   ~2000万/秒（RingBuffer 缓存）
```

### 8.3 选型建议

```
场景一：小规模系统，简单快速
→ 数据库号段模式（最简单，够用）

场景二：中等规模，需要高性能
→ Snowflake（无外部依赖，性能高）

场景三：大规模系统，需要高可用
→ Leaf-segment + Leaf-snowflake 双模式
→ 正常用 Leaf-segment，数据库挂了用 Leaf-snowflake

场景四：极致性能
→ UidGenerator CachedUidGenerator

场景五：对安全性要求高（不暴露业务量）
→ Snowflake（趋势递增但不连续，难以推算业务量）
```

---

## 九、分布式 ID 最佳实践

### 9.1 ID 长度选择

```
64 bit（long）: 最推荐
  - Java/Go/Python 原生支持
  - 数据库 BIGINT 存储
  - Snowflake/Leaf/UidGenerator 都是 64 bit

128 bit（UUID）: 不推荐做主键
  - 索引性能差
  - 存储空间大
  - 适合做外部标识（traceId、requestId）
```

### 9.2 ID 生成策略选择

```
内部 ID（数据库主键）→ Snowflake / 号段模式
外部 ID（暴露给用户）→ 加密/编码后的 ID
  - 避免暴露业务量
  - 例如：Base62 编码 + 加密
```

### 9.3 多机房部署

```
方案一：Snowflake + 不同数据中心 ID
  机房 A: datacenterId = 1
  机房 B: datacenterId = 2
  → ID 全局唯一

方案二：号段模式 + 不同号段起始值
  机房 A: 起始 = 0, 步长 = 2
  机房 B: 起始 = 1, 步长 = 2
  → ID 全局唯一
```

---

## 十、面试高频问题

### Q1: Snowflake 算法的原理？

**答案要点**：
- 64 bit：1 符号 + 41 时间戳 + 10 机器 ID + 12 序列号
- 单机每毫秒最多 4096 个 ID
- 趋势递增（同一毫秒内严格递增，跨毫秒可能不连续）
- 时钟回拨需要特殊处理

### Q2: Snowflake 的时钟回拨如何解决？

**答案要点**：
1. 小幅回拨（< 5ms）：等待追回
2. 大幅回拨：报错或切换 Worker ID
3. ZooKeeper 记录上次时间戳，启动时检测

### Q3: 号段模式的原理？

**答案要点**：
- 数据库存储当前最大 ID 和步长
- 每次更新 max_id += step，获取一个号段
- 双 Buffer 预加载，保证高可用
- 数据库挂掉仍可用一段时间

### Q4: UUID 为什么不适合做数据库主键？

**答案要点**：
- 无序：B+ 树频繁页分裂
- 太长：36 字节，索引空间浪费
- InnoDB 聚簇索引：主键无序导致二级索引存储大量主键值

### Q5: Leaf 和 UidGenerator 的区别？

**答案要点**：
- Leaf：双模式（号段 + Snowflake），美团生产验证
- UidGenerator：CachedUidGenerator 用 RingBuffer，性能更高
- Leaf 更成熟（美团内部大规模使用）
- UidGenerator 性能更优（2000 万/秒）

---

## 十一、总结

本文系统梳理了分布式 ID 的主流生成方案：

1. **UUID**：简单无依赖，但无序不适合做主键
2. **数据库号段模式**：简单可靠，双 Buffer 优化
3. **Snowflake**：高性能无依赖，需处理时钟回拨
4. **Leaf**：美团开源，号段 + Snowflake 双模式
5. **UidGenerator**：百度开源，RingBuffer 缓存性能极高

**核心记忆**：
- Snowflake：1 + 41 + 10 + 12 = 64 bit
- 号段模式：数据库存储 max_id + step，预加载双 Buffer
- 时钟回拨：小幅等待，大幅报错或切换 Worker
- 选型：小规模用号段，大规模用 Snowflake/Leaf

下一篇将深入 **分布式缓存与一致性哈希**，包括缓存策略、一致性哈希原理、虚拟节点等，敬请期待。

---

*作者：亚飞的技术笔记 | 公众号：亚飞的技术笔记*
