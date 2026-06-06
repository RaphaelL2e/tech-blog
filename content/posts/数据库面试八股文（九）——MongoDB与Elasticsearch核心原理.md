---
title: "数据库面试八股文（九）——MongoDB与Elasticsearch核心原理"
date: 2026-06-04T11:00:00+08:00
draft: false
categories: ["数据库"]
tags: ["面试", "八股文", "MongoDB", "Elasticsearch", "NoSQL", "倒排索引", "分片", "副本集", "搜索"]
---

# 数据库面试八股文（九）——MongoDB与Elasticsearch核心原理

> 面试高频考点：MongoDB文档模型与存储引擎、副本集与分片集群、聚合管道；Elasticsearch倒排索引原理、分片与路由、搜索与聚合DSL。本文从NoSQL文档数据库到搜索引擎，全面覆盖MongoDB与ES面试题。

---

## 一、MongoDB概述

### 1.1 MongoDB是什么

MongoDB是面向文档的NoSQL数据库，核心特点：

| 特性 | 说明 |
|------|------|
| 文档模型 | 数据以BSON文档存储，类似JSON |
| 灵活Schema | 同一集合中文档结构可以不同 |
| 水平扩展 | 原生支持分片集群 |
| 丰富查询 | 支持索引、聚合管道、全文搜索 |
| ACID事务 | 4.0+支持多文档事务 |

### 1.2 MongoDB vs MySQL

| 维度 | MongoDB | MySQL |
|------|---------|-------|
| 数据模型 | 文档（BSON） | 表（行与列） |
| Schema | 灵活，可嵌套 | 固定，需DDL |
| 关联方式 | 嵌入文档 / 引用 | 外键JOIN |
| 扩展方式 | 水平分片 | 垂直扩展为主 |
| 事务 | 4.0+支持 | 原生ACID |
| 适用场景 | 非结构化、快速迭代 | 结构化、强一致 |

---

## 二、MongoDB存储引擎

### 2.1 WiredTiger引擎（默认）

MongoDB 3.2+默认使用WiredTiger存储引擎：

| 特性 | 说明 |
|------|------|
| 文档级并发 | 不同文档可并发修改 |
| 压缩 | Snappy（默认）/ Zlib / Zstd |
| 检查点 | 每60秒或日志超过2GB时 |
| 日志 | WAL（Write-Ahead Log）保证持久性 |

**内存管理**：

```
WiredTiger Cache（默认 max(256MB, 50%物理内存 - 1GB)）
       ↓
  ┌────────────────┐
  │  索引缓存       │ ← B树节点
  │  数据缓存       │ ← 文档页
  │  压缩缓存       │ ← 解压后的数据
  └────────────────┘
```

### 2.2 BSON格式

BSON（Binary JSON）是MongoDB的数据序列化格式：

```json
{
  "_id": ObjectId("6507..."),
  "name": "张三",
  "age": 28,
  "skills": ["Java", "Python"],
  "address": {
    "city": "北京",
    "street": "中关村"
  },
  "createdAt": ISODate("2024-01-01")
}
```

**BSON vs JSON**：

| 维度 | JSON | BSON |
|------|------|------|
| 格式 | 文本 | 二进制 |
| 类型 | 少（6种） | 多（Date、ObjectId、Int32等） |
| 遍历 | 需解析 | 有长度前缀，可跳过 |
| 体积 | 小（纯文本） | 略大（有类型和长度信息） |

---

## 三、MongoDB索引

### 3.1 索引类型

| 索引类型 | 说明 | 示例 |
|---------|------|------|
| 单字段索引 | 对单个字段建索引 | `{name: 1}` |
| 复合索引 | 多字段联合索引 | `{name: 1, age: -1}` |
| 多键索引 | 对数组字段建索引 | `{tags: 1}` |
| 地理空间索引 | 2dsphere / 2d | `{location: "2dsphere"}` |
| 文本索引 | 全文搜索 | `{content: "text"}` |
| 哈希索引 | 分片键用 | `{_id: "hashed"}` |
| TTL索引 | 自动过期删除 | `{createdAt: 1}` + expireAfterSeconds |

### 3.2 复合索引最左前缀原则

与MySQL类似，MongoDB复合索引也遵循最左前缀原则：

```javascript
// 索引: {name: 1, age: -1, city: 1}

// ✅ 命中索引
db.users.find({name: "张三"})
db.users.find({name: "张三", age: 25})
db.users.find({name: "张三", age: 25, city: "北京"})

// ❌ 不命中索引
db.users.find({age: 25})         // 跳过name
db.users.find({city: "北京"})     // 跳过name和age
```

### 3.3 ESR原则（等值→排序→范围）

复合索引字段排列的最优顺序：

1. **E**quality（等值查询）放最前
2. **S**ort（排序）放中间
3. **R**ange（范围查询）放最后

```javascript
// 查询: {status: "active"} + sort({createdAt: -1}) + {age: {$gte: 18}}
// 最优索引: {status: 1, createdAt: -1, age: 1}
```

### 3.4 explain()分析

```javascript
db.users.find({name: "张三"}).explain("executionStats")
```

| 关键字段 | 含义 |
|---------|------|
| winningPlan.stage | COLLSCAN（全表扫描）/ IXSCAN（索引扫描）/ FETCH（回表） |
| executionStats.totalDocsExamined | 扫描文档数 |
| executionStats.executionTimeMillis | 执行时间 |
| executionStats.nReturned | 返回文档数 |

> 💡 **面试重点**：理想情况 nReturned ≈ totalDocsExamined，差距大说明需要优化索引。

---

## 四、MongoDB副本集

### 4.1 副本集架构

```
     Primary（读写）
    /       \
Secondary   Secondary
（只读）    （只读，可配置隐藏/延迟）
    |
  Arbiter（仲裁者，不存数据，仅投票）
```

### 4.2 副本集选举

**触发条件**：
- 主节点不可达（心跳超时，默认10秒）
- 主节点主动stepDown
- 副本集初始化

**选举规则**：

| 优先级因素 | 说明 |
|-----------|------|
| priority | 优先级高的优先成为主（默认1，可设0-1000） |
| optime | 操作日志最新的优先 |
| 数据新鲜度 | 数据最新的优先 |
| 心跳检测 | 多数节点同意才能当选 |

> ⚠️ **面试重点**：选举需要**多数节点**同意（N/2+1），所以3节点副本集可以容忍1个节点故障，5节点可容忍2个。

### 4.3 写关注（Write Concern）

```javascript
// 确认写操作被几个节点持久化
db.products.insertOne(
  {name: "手机"},
  {writeConcern: {w: "majority", j: true, wtimeout: 5000}}
)
```

| 参数 | 说明 |
|------|------|
| w: 1 | 主节点确认即可（默认） |
| w: "majority" | 多数节点确认 |
| j: true | 等待journal刷盘 |
| wtimeout | 超时时间 |

### 4.4 读偏好（Read Preference）

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| primary | 只从主节点读（默认） | 强一致性 |
| primaryPreferred | 优先主节点 | 一般场景 |
| secondary | 只从从节点读 | 报表/分析 |
| secondaryPreferred | 优先从节点 | 读多写少 |
| nearest | 延迟最低的节点 | 延迟敏感 |

---

## 五、MongoDB分片集群

### 5.1 分片架构

```
 mongos（路由）
   ↓    ↓
Shard1  Shard2  Shard3（数据分片）
   ↓
Config Servers（元数据）
```

| 组件 | 作用 | 最少数量 |
|------|------|---------|
| mongos | 查询路由 | 1（生产建议2+） |
| Config Server | 存储集群元数据 | 3（副本集） |
| Shard | 存储数据 | 1（生产建议3+） |

### 5.2 分片键（Shard Key）

选择分片键是最重要的决策：

**好的分片键**：
- 取值范围大（避免数据倾斜）
- 写操作均匀分布
- 查询经常用到（避免广播查询）

**分片策略**：

| 策略 | 说明 | 优缺点 |
|------|------|--------|
| 范围分片 | 按值范围划分 | 范围查询高效，但可能热点 |
| 哈希分片 | 按hash值划分 | 数据均匀，但范围查询低效 |
| 区域分片 | 按地理区域 | 数据本地化 |

### 5.3 Chunk与均衡器

- 每个Chunk默认64MB
- 均衡器（Balancer）自动在Shard间迁移Chunk
- Chunk分裂：超过大小时一分为二

```
Shard1: [chunk1] [chunk2]        ← 数据多
Shard2: [chunk3]                 ← 数据少

均衡器自动迁移chunk2到Shard2:

Shard1: [chunk1]                 
Shard2: [chunk3] [chunk2]        ← 数据均匀
```

---

## 六、MongoDB聚合管道

### 6.1 常用阶段

```javascript
db.orders.aggregate([
  // 1. $match - 过滤
  { $match: { status: "completed", year: 2024 } },
  
  // 2. $group - 分组
  { $group: {
      _id: "$categoryId",
      totalSales: { $sum: "$amount" },
      avgPrice: { $avg: "$price" },
      count: { $sum: 1 }
  }},
  
  // 3. $sort - 排序
  { $sort: { totalSales: -1 } },
  
  // 4. $limit - 限制
  { $limit: 10 },
  
  // 5. $project - 投影
  { $project: {
      categoryId: "$_id",
      totalSales: 1,
      avgPrice: { $round: ["$avgPrice", 2] }
  }}
])
```

### 6.2 其他常用操作符

| 操作符 | 说明 |
|--------|------|
| $lookup | 左连接（类似SQL LEFT JOIN） |
| $unwind | 展开数组 |
| $facet | 多管道并行执行 |
| $bucket | 分桶统计 |
| $merge | 结果写入集合 |

### 6.3 $lookup关联查询

```javascript
db.orders.aggregate([
  {
    $lookup: {
      from: "users",           // 关联集合
      localField: "userId",    // 本地字段
      foreignField: "_id",     // 外键字段
      as: "userInfo"           // 输出数组字段
    }
  },
  { $unwind: "$userInfo" }     // 展开数组
])
```

> ⚠️ **面试提醒**：$lookup性能较差，不适合大量数据。设计时应优先考虑嵌入文档。

---

## 七、Elasticsearch概述

### 7.1 Elasticsearch是什么

Elasticsearch是基于Lucene的分布式搜索和分析引擎：

| 特性 | 说明 |
|------|------|
| 全文搜索 | 倒排索引，毫秒级响应 |
| 分布式 | 天然支持集群，PB级数据 |
| 近实时 | 写入后1秒可搜索 |
| RESTful | JSON over HTTP API |
| 聚合分析 | 实时统计分析 |

### 7.2 核心概念对照

| Elasticsearch | MySQL | 说明 |
|--------------|-------|------|
| Index | Database | 索引（数据库） |
| Type（已废弃） | Table | 类型（7.x移除） |
| Document | Row | 文档（行） |
| Field | Column | 字段（列） |
| Mapping | Schema | 映射（表结构） |
| Shard | 分区 | 分片 |
| Replica | 副本 | 副本 |

### 7.3 生命周期

```
写入 → 内存Buffer → Refresh（1秒） → OS Cache（可搜索）
                                     ↓
                              Flush → 磁盘（持久化）
```

**关键参数**：
- `refresh_interval`：默认1秒，可调大提升写入性能
- `translog`：事务日志，保证数据不丢失
- `flush`：将OS Cache中的segment刷到磁盘

---

## 八、Elasticsearch倒排索引

### 8.1 正排索引 vs 倒排索引

**正排索引**（MySQL B+树）：id → 内容
**倒排索引**（ES）：词 → 文档id列表

### 8.2 倒排索引构建过程

**文档**：

| DocID | Content |
|-------|---------|
| 1 | Elasticsearch is a search engine |
| 2 | MongoDB is a document database |
| 3 | Search engine for big data |

**分词 → 倒排表**：

| Term | DocIDs | 词频 |
|------|--------|------|
| elasticsearch | [1] | 1 |
| search | [1, 3] | 2 |
| engine | [1, 3] | 2 |
| mongodb | [2] | 1 |
| document | [2] | 1 |
| database | [2] | 1 |
| big | [3] | 1 |
| data | [3] | 1 |

### 8.3 分词器（Analyzer）

```
文本 → Character Filters → Tokenizer → Token Filters → 词项(Terms)
```

| 分词器 | 说明 | 示例 |
|--------|------|------|
| standard | 默认，按词分割，小写 | "Hello World" → ["hello", "world"] |
| simple | 非字母分割，小写 | "Hello, World!" → ["hello", "world"] |
| whitespace | 按空格分割 | "Hello World" → ["Hello", "World"] |
| ik_max_word | 中文最细粒度 | "中华人民共和国" → ["中华人民共和国", "中华人民", "中华", "华人", "人民共和国", "人民", "共和国", "共和", "国"] |
| ik_smart | 中文智能切分 | "中华人民共和国" → ["中华人民共和国"] |

> 💡 **面试重点**：中文搜索必须安装IK分词器！默认standard分词器对中文按单字切分。

### 8.4 倒排索引不可变

ES的segment是不可变的：
- **优点**：不需要锁、常驻缓存、过滤快
- **缺点**：更新=标记删除+新建、需段合并（merge）

---

## 九、Elasticsearch分片与路由

### 9.1 分片机制

```
Index: products (3主分片，每分片1副本)
                    
  Shard0(P)  Shard1(P)  Shard2(P)    ← 主分片
  Shard0(R)  Shard1(R)  Shard2(R)    ← 副本分片
```

**分片数**：创建索引时指定，不可修改（需reindex）
**副本数**：可动态调整

### 9.2 文档路由

文档写入哪个分片由路由公式决定：

```
shard = hash(routing) % number_of_primary_shards
```

默认routing = `_id`

> ⚠️ **面试陷阱**：这就是为什么主分片数创建后不能修改！改了路由公式对不上。

### 9.3 写入流程

```
客户端 → 协调节点(Node1)
              ↓
    根据路由计算目标分片(Shard0)
              ↓
    转发到主分片所在节点(Node2)
              ↓
    主分片写入 → 同步到副本分片
              ↓
    等待确认（根据consistency设置）
              ↓
    返回客户端成功
```

### 9.4 查询流程

**查询阶段**：

```
1. 协调节点将查询转发到所有分片（主或副本）
2. 每个分片返回匹配文档的id和排序值
3. 协调节点合并排序，取前N个id

取回阶段：

4. 协调节点根据id到对应分片取完整文档
5. 返回客户端
```

---

## 十、Elasticsearch搜索DSL

### 10.1 查询分类

| 类型 | 说明 | 示例 |
|------|------|------|
| 全文查询 | 对文本字段分词搜索 | match, multi_match |
| 精确查询 | 不分词精确匹配 | term, terms, range |
| 复合查询 | 组合多个查询 | bool, boosting |
| 嵌套查询 | 嵌套对象查询 | nested |
| 聚合查询 | 统计分析 | terms, avg, histogram |

### 10.2 match vs term

```json
// match：全文检索，会分词
GET /products/_search
{
  "query": {
    "match": {
      "title": "华为手机"
    }
  }
}
// 搜索词 "华为手机" 被分词为 "华为" 和 "手机"，匹配包含任一词的文档

// term：精确匹配，不分词
GET /products/_search
{
  "query": {
    "term": {
      "status": "active"
    }
  }
}
// 精确匹配status为"active"的文档
```

> ⚠️ **面试陷阱**：不要对text字段用term查询！text字段存储时已分词，term不分词去匹配，几乎匹配不上。

### 10.3 bool复合查询

```json
GET /products/_search
{
  "query": {
    "bool": {
      "must": [
        { "match": { "title": "手机" } }
      ],
      "should": [
        { "term": { "brand": "华为" } },
        { "term": { "brand": "小米" } }
      ],
      "must_not": [
        { "term": { "status": "下架" } }
      ],
      "filter": [
        { "range": { "price": { "gte": 1000, "lte": 5000 } } }
      ]
    }
  }
}
```

| 子句 | 是否计算分数 | 说明 |
|------|------------|------|
| must | 是 | 必须匹配 |
| should | 是 | 至少匹配一个（或提升分数） |
| must_not | 否 | 必须不匹配 |
| filter | 否 | 必须匹配，但不计分（可缓存） |

> 💡 **面试重点**：filter不计算相关性分数，性能更好，尽量用filter替代must做过滤。

### 10.4 聚合查询

```json
GET /products/_search
{
  "size": 0,
  "aggs": {
    "brand_count": {
      "terms": { "field": "brand", "size": 10 }
    },
    "price_stats": {
      "stats": { "field": "price" }
    },
    "price_histogram": {
      "histogram": {
        "field": "price",
        "interval": 1000
      }
    }
  }
}
```

---

## 十一、Elasticsearch性能优化

### 11.1 写入优化

| 优化项 | 方法 |
|--------|------|
| 批量写入 | 使用Bulk API |
| 调大refresh间隔 | `refresh_interval: 30s` |
| 关闭副本 | 初始导入时 `number_of_replicas: 0` |
| 预分配分片 | 根据数据量合理规划 |
| 段合并 | 控制merge线程数 |

### 11.2 查询优化

| 优化项 | 方法 |
|--------|------|
| 用filter替代query | 不计分，可缓存 |
| 避免深分页 | 用search_after替代from/size |
| 避免通配符开头 | `*abc` 无法走索引 |
| 使用路由 | 相关数据路由到同一分片 |
| 控制返回字段 | `_source: ["field1", "field2"]` |

### 11.3 深分页问题

**from + size**：深度分页时，每个分片返回from+size条数据到协调节点，内存爆炸。

```
from=10000, size=10, 5个分片
→ 协调节点需要处理 5 × 10010 = 50050 条数据
```

**解决方案**：

| 方案 | 原理 | 适用场景 |
|------|------|---------|
| scroll | 快照遍历 | 导出数据 |
| search_after | 基于排序值翻页 | 实时分页 |
| index.max_result_window | 调大限制（不推荐） | 临时方案 |

```json
// search_after示例
GET /products/_search
{
  "size": 10,
  "query": { "match_all": {} },
  "sort": [
    { "price": "desc" },
    { "_id": "asc" }
  ],
  "search_after": [5999, "product_123"]
}
```

---

## 十二、MongoDB与Elasticsearch对比

| 维度 | MongoDB | Elasticsearch |
|------|---------|--------------|
| 定位 | 文档数据库 | 搜索引擎 |
| 主索引 | B树 | 倒排索引 |
| 写入性能 | 较高 | 较低（需建倒排） |
| 搜索能力 | 有限（文本索引） | 强大（全文搜索+聚合） |
| 事务 | 4.0+支持 | 不支持 |
| 一致性 | 强一致/最终一致 | 最终一致（近实时） |
| 典型场景 | 主数据库 | 搜索/日志分析 |

**最佳实践**：MySQL/MongoDB做主存储，ES做搜索层，通过Canal/Change Stream同步。

---

## 总结

| 主题 | 核心要点 |
|------|---------|
| MongoDB文档模型 | BSON格式、灵活Schema、嵌入式关联 |
| MongoDB索引 | 复合索引ESR原则、explain分析 |
| 副本集 | 选举机制、写关注、读偏好 |
| 分片集群 | 分片键选择、Chunk均衡 |
| 聚合管道 | $match→$group→$sort→$limit |
| ES倒排索引 | 分词→词项→倒排表，segment不可变 |
| ES分片路由 | hash(routing) % primary_shards，分片数不可改 |
| ES查询DSL | match vs term，bool组合，filter优化 |
| ES深分页 | search_after替代from/size |
| 配合使用 | 主库+ES搜索层，Change Stream同步 |

下期预告：
- 数据库面试八股文（十）——数据库综合面试题与实战
