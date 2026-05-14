---
title: "Elasticsearch 深度解析"
date: 2026-05-14T12:20:00+08:00
draft: false
categories: ["分布式系统"]
tags: ["Elasticsearch", "倒排索引", "分片", "深度分页", "BM25"]
---

# Elasticsearch 深度解析

## 一、引言

Elasticsearch 是目前最流行的分布式搜索和分析引擎，广泛应用于日志分析、全文搜索、监控报警等场景。理解 Elasticsearch 的内部原理，对面试和架构设计都极为重要。

**本文要点**：
1. Elasticsearch 核心概念
2. 倒排索引原理
3. 分片与路由机制
4. 写入流程（Primary → Replica）
5. 搜索流程（Query → Fetch）
6. 深度分页问题
7. 调优实践
8. 面试高频问题

---

## 二、核心概念

### 2.1 逻辑概念

| 概念 | 类比 MySQL | 描述 |
|------|-----------|------|
| **Index** | Database | 索引，文档的集合 |
| **Type** | Table | 类型（ES 7.x 已废弃，一个 Index 只有一个 Type） |
| **Document** | Row | 文档，JSON 格式 |
| **Field** | Column | 字段 |
| **Mapping** | Schema | 映射，定义字段类型和索引方式 |

### 2.2 物理概念

| 概念 | 描述 |
|------|------|
| **Node** | ES 实例，一个 JVM 进程 |
| **Cluster** | 多个 Node 组成的集群 |
| **Shard** | 分片，Index 的物理分片 |
| **Primary Shard** | 主分片，处理写请求 |
| **Replica Shard** | 副本分片，处理读请求，容灾 |

### 2.3 Node 角色

| 角色 | 职责 |
|------|------|
| **Master Node** | 管理集群元数据（Index 创建/删除、Node 加入/离开） |
| **Data Node** | 存储数据，执行 CRUD 和搜索 |
| **Coordinating Node** | 路由请求，聚合结果（默认每个 Node 都是） |
| **Ingest Node** | 预处理文档（Pipeline） |

---

## 三、倒排索引

### 3.1 正排索引 vs 倒排索引

**正排索引**（Forward Index）：文档 ID → 文档内容

```
Doc 1: "Elasticsearch is a search engine"
Doc 2: "Search engine for big data"
Doc 3: "Big data analytics platform"
```

**倒排索引**（Inverted Index）：词项 → 文档 ID 列表

```
Term         | Doc IDs | Term Frequency | Position
-------------|---------|----------------|--------
elasticsearch| 1       | 1              | 0
is           | 1       | 1              | 1
a            | 1       | 1              | 2
search       | 1, 2    | 1, 1           | 3, 0
engine       | 1, 2    | 1, 1           | 4, 1
for          | 2       | 1              | 2
big          | 2, 3    | 1, 1           | 3, 0
data         | 2, 3    | 1, 1           | 4, 1
analytics    | 3       | 1              | 2
platform     | 3       | 1              | 3
```

### 3.2 倒排索引的构建流程

```
1. 字符过滤（Character Filter）：去除 HTML 标签等
2. 分词（Tokenizer）：将文本拆分为词项
3. 词项过滤（Token Filter）：小写、去停用词、词干提取
4. 建立倒排索引
```

**Analyzer 示例**：

```
输入: "The Quick Brown Foxes"

1. Character Filter: "The Quick Brown Foxes"（无变化）
2. Tokenizer (Standard): ["The", "Quick", "Brown", "Foxes"]
3. Token Filter:
   - Lowercase: ["the", "quick", "brown", "foxes"]
   - Stopwords: ["quick", "brown", "foxes"]（去除 "the"）
   - Stemmer: ["quick", "brown", "fox"]（词干提取）
4. 倒排索引:
   quick → Doc1
   brown → Doc1
   fox   → Doc1
```

### 3.3 常用 Analyzer

| Analyzer | 描述 | 示例 |
|----------|------|------|
| **standard** | 默认，基于 Unicode 分词 | "Hello World" → ["hello", "world"] |
| **simple** | 按非字母分割，小写 | "Hello, World!" → ["hello", "world"] |
| **whitespace** | 按空格分割 | "Hello World" → ["Hello", "World"] |
| **keyword** | 不分词，整体作为一个词项 | "Hello World" → ["Hello World"] |
| **ik_max_word** | 中文最细粒度分词 | "中华人民共和国" → ["中华人民共和国", "中华人民", "中华", "华人", "人民共和国", "人民", "共和国", "共和", "国"] |
| **ik_smart** | 中文智能分词 | "中华人民共和国" → ["中华人民共和国"] |

### 3.4 倒排索引的更新

```
ES 的倒排索引是不可变的（Immutable）

更新文档的流程：
1. 标记旧文档为删除（逻辑删除）
2. 创建新文档，建立新的倒排索引
3. 搜索时跳过已删除的文档

物理删除：
  Segment Merge 时合并，真正删除旧文档
```

---

## 四、分片与路由

### 4.1 分片机制

```
Index: products（3 Primary Shard, 1 Replica）

Node 1              Node 2              Node 3
┌──────────┐      ┌──────────┐      ┌──────────┐
│ P0       │      │ P1       │      │ P2       │
│ R1       │      │ R2       │      │ R0       │
└──────────┘      └──────────┘      └──────────┘

P = Primary Shard, R = Replica Shard
每个 Primary Shard 的 Replica 在不同 Node 上
```

### 4.2 路由公式

```
shard = hash(routing) % number_of_primary_shards

默认 routing = _id（文档 ID）

自定义 routing：
  PUT /products/_doc/1?routing=user123
  → 同一 routing 的文档在同一分片
  → 适合按用户查询的场景
```

### 4.3 分片数选择

```
公式：分片数 = 期望的数据量 / 单分片容量

单分片容量建议：30-50GB
  - 太小：分片过多，集群管理开销大
  - 太大：搜索慢，Merge 慢

示例：
  数据量 = 1TB = 1024GB
  单分片 = 40GB
  分片数 = 1024 / 40 ≈ 25 个 Primary Shard

注意：
  - 分片数创建后不能修改（需要 Reindex）
  - 可以提前规划，适当多创建一些
```

---

## 五、写入流程

### 5.1 单文档写入

```
Client → Coordinating Node → Primary Shard → Replica Shard

详细流程：
1. Client 发送写入请求到 Coordinating Node
2. Coordinating Node 根据路由公式确定 Primary Shard
3. 请求转发到 Primary Shard 所在的 Node
4. Primary Node 执行写入：
   a. 写入 Index Buffer（内存缓冲区）
   b. 写入 Translog（事务日志，持久化到磁盘）
   c. 返回成功给 Coordinating Node
5. Primary Node 并行写入 Replica Shard
6. 等待所有 Replica 写入成功（或超时）
7. Coordinating Node 返回成功给 Client
```

### 5.2 Index Buffer → Segment

```
Index Buffer 不是直接生成倒排索引的

流程：
1. 文档先写入 Index Buffer
2. 每隔 refresh_interval（默认 1 秒）：
   → Index Buffer 中的文档生成一个新的 Segment
   → Segment 写入文件系统缓存（OS Cache）
   → 文档可被搜索
3. 每隔一段时间：
   → Segment 刷入磁盘（fsync）
   → Translog 清理

关键参数：
  refresh_interval: 默认 1s（可以调大以提高写入性能）
  → 设为 -1 可关闭自动 refresh（批量导入场景）
```

### 5.3 Segment Merge

```
Segment 不断生成，数量越来越多 → 搜索需要扫描多个 Segment

Segment Merge：
1. 后台线程选择大小相近的 Segment 进行合并
2. 合并成更大的 Segment
3. 删除旧 Segment（包括已逻辑删除的文档）

合并策略：
  - Tiered Merge Policy（默认）：分层合并
  - Log Byte Size Merge Policy：按大小合并

优化：
  - force_merge API：手动触发合并（适合索引不再更新时）
  - max_merge_count：限制并发合并数
```

### 5.4 写入一致性

```
consistency 参数：
  one     : 只要 Primary 写入成功就返回（默认）
  quorum  : 大多数 Shard 写入成功才返回
  all     : 所有 Shard 写入成功才返回

wait_for_active_shards 参数：
  指定写入前至少有多少个活跃 Shard
  默认 1（只有 Primary）
  设为 all 等待所有 Replica
```

---

## 六、搜索流程

### 6.1 Query Then Fetch

```
搜索流程分两个阶段：

阶段一：Query（查询）
  1. Coordinating Node 将查询请求发送到所有相关 Shard
  2. 每个 Shard 执行查询，返回匹配文档的 ID 和分数
  3. Coordinating Node 合并所有 Shard 的结果
  4. 根据分数排序，取 Top N 的文档 ID

阶段二：Fetch（获取）
  1. Coordinating Node 根据 Top N 的文档 ID
  2. 向对应 Shard 请求完整文档内容
  3. 合并返回给 Client
```

### 6.2 相关性评分（BM25）

```
BM25 公式：
score(D, Q) = Σ IDF(qi) × (f(qi, D) × (k1 + 1)) / (f(qi, D) + k1 × (1 - b + b × |D| / avgdl))

简化理解：
  - IDF(qi)：词项的逆文档频率（越稀有越重要）
  - f(qi, D)：词项在文档中的词频
  - |D|：文档长度
  - avgdl：平均文档长度
  - k1：词频饱和参数（默认 1.2）
  - b：文档长度归一化参数（默认 0.75）

关键特点：
  - 词频越高，分数越高（但有上限，不会无限增长）
  - 文档越长，分数越低（归一化）
  - 稀有词项比常见词项权重更高
```

### 6.3 DFS Query Then Fetch

```
问题：每个 Shard 独立计算分数 → 分布式评分不准确
  → 文档在 Shard 1 中是稀有的，但在全局可能是常见的

解决：DFS Query Then Fetch
  1. DFS 阶段：收集所有 Shard 的词频和文档频率
  2. Query 阶段：使用全局统计信息计算分数
  3. Fetch 阶段：获取完整文档

代价：多一次 RPC（DFS 阶段），性能略低
适用：对评分精确度要求高的场景
```

---

## 七、深度分页问题

### 7.1 from + size 的问题

```
请求：from=10000, size=10

Coordinating Node 行为：
  → 向每个 Shard 请求 10010 条数据
  → 合并所有 Shard 的结果（5 个 Shard × 10010 = 50050 条）
  → 排序取第 10001~10010 条
  → 丢弃其余 50040 条

问题：
  - 深度分页时内存和 CPU 消耗巨大
  - 结果不准确（每个 Shard 独立排序）
```

### 7.2 解决方案

**方案一：scroll**

```
// 第一次请求，建立快照
GET /products/_search?scroll=5m
{
  "size": 100,
  "query": { "match_all": {} }
}

// 后续请求
GET /_search/scroll
{
  "scroll": "5m",
  "scroll_id": "xxx"
}

特点：
  - 建立数据快照，适合批量导出
  - 不适合实时查询（数据不是最新的）
  - 长时间占用资源
```

**方案二：search_after**

```
// 第一页
GET /products/_search
{
  "size": 10,
  "query": { "match_all": {} },
  "sort": [{ "price": "asc" }, { "_id": "asc" }]
}

// 下一页（使用上一页最后一条的排序值）
GET /products/_search
{
  "size": 10,
  "query": { "match_all": {} },
  "sort": [{ "price": "asc" }, { "_id": "asc" }],
  "search_after": [99.9, "product_10"]
}

特点：
  - 实时性高（不需要快照）
  - 只能向后翻页
  - 适合无限滚动加载
```

**方案三：限制 from + size**

```
ES 默认限制：from + size ≤ 10000（index.max_result_window）

如果确实需要深度分页：
  PUT /products/_settings
  {
    "index.max_result_window": 50000
  }

不推荐：深度分页性能差
```

---

## 八、调优实践

### 8.1 写入优化

```
1. 批量写入（Bulk API）
   → 每批 5-15MB
   → 批量大小不超过 100MB

2. 增大 refresh_interval
   → 默认 1s → 批量导入时设为 30s 或 -1

3. 增大 Index Buffer
   → indices.memory.index_buffer_size: 默认 10% JVM Heap

4. 关闭 Replica（批量导入时）
   → number_of_replicas=0
   → 导入完成后再开启

5. 使用自动生成的 ID
   → 避免版本检查开销
```

### 8.2 搜索优化

```
1. 使用 Filter 代替 Query
   → Filter 不计算分数，可缓存
   → Query 计算分数，不缓存

2. 避免深度分页
   → 使用 search_after 替代 from + size

3. 使用路由（routing）
   → 同一类数据在同一分片
   → 减少跨分片查询

4. 预索引（Index Sorting）
   → 按常用排序字段预排序
   → 减少搜索时的排序开销

5. 控制返回字段
   → 使用 _source filtering
   → 只返回需要的字段
```

### 8.3 集群优化

```
1. 分离 Master 和 Data Node
   → Master Node 不存数据，配置低
   → Data Node 存数据，配置高

2. 合理设置 JVM Heap
   → 不超过物理内存的 50%
   → 不超过 32GB（压缩指针阈值）
   → 预留一半给 Lucene 文件缓存

3. SSD 磁盘
   → ES 大量随机 IO
   → SSD 性能远超 HDD

4. 避免热索引过大
   → 单分片 30-50GB
   → 按时间滚动索引（rollover）
```

---

## 九、面试高频问题

### Q1: Elasticsearch 的倒排索引是什么？

**答案要点**：
- 词项 → 文档 ID 列表的映射
- 通过 Analyzer 构建分词 → 词项
- 存储词频、位置信息
- 不可变，更新时标记删除 + 新建

### Q2: Elasticsearch 的写入流程？

**答案要点**：
1. 路由到 Primary Shard
2. 写入 Index Buffer + Translog
3. refresh 生成 Segment（可搜索）
4. 并行写入 Replica
5. Segment Merge 后台合并

### Q3: 深度分页怎么解决？

**答案要点**：
- scroll：建立快照，适合批量导出
- search_after：实时翻页，只能向后
- 限制 from + size ≤ 10000

### Q4: ES 和 MySQL 的区别？

**答案要点**：
- ES：倒排索引，全文搜索快，弱事务
- MySQL：B+ 树，精确查找快，强事务
- ES 适合搜索、日志分析
- MySQL 适合业务数据存储

### Q5: 如何提高 ES 的写入性能？

**答案要点**：
- 批量写入（Bulk API）
- 增大 refresh_interval
- 批量导入时关闭 Replica
- 使用自动生成 ID
- 增大 Index Buffer

---

## 十、总结

本文深入分析了 Elasticsearch 的核心原理：

1. **倒排索引**：词项 → 文档 ID，Analyzer 分词构建
2. **分片路由**：hash(routing) % primary_shards
3. **写入流程**：Index Buffer → Translog → Refresh → Segment → Merge
4. **搜索流程**：Query（各分片查询）→ Fetch（获取完整文档）
5. **深度分页**：search_after 实时翻页，scroll 批量导出

**核心记忆**：
- 倒排索引：不可变，更新 = 逻辑删除 + 新建
- Refresh 间隔 1s（文档延迟可见 1 秒）
- 深度分页：search_after > scroll > from+size
- BM25 评分：词频 + 逆文档频率 + 文档长度归一化
- 写入优化：Bulk + 大 refresh_interval + 关 Replica

下一篇将深入 **分布式限流与熔断**，包括限流算法、熔断器模式、Sentinel 实战等，敬请期待。

---

*作者：亚飞的技术笔记 | 公众号：亚飞的技术笔记*
