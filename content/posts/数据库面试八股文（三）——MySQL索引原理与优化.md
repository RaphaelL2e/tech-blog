---
title: "数据库面试八股文（三）——MySQL索引原理与优化"
date: 2026-05-25T09:00:00+08:00
draft: false
categories: ["数据库"]
tags: ["面试", "八股文", "MySQL", "索引", "B+树", "覆盖索引", "最左前缀"]
---

# 数据库面试八股文（三）——MySQL索引原理与优化

## [](#概述)概述

索引是MySQL面试中**最高频**的考点。本文深入讲解B+树原理、聚簇索引vs非聚簇索引、覆盖索引、最左前缀原则、索引优化实战等核心内容。

## [](#索引的基本概念)索引的基本概念

### [](#什么是索引)什么是索引

**索引（Index）** 是帮助MySQL**高效获取数据**的**排好序的数据结构**。

> 类比：书籍目录 —— 通过目录快速找到章节，而不是逐页翻阅。

**优点**：
- 大幅**提高查询速度**（从O(N)到O(logN)）
- 保证数据的**唯一性**（唯一索引）
- 加速表连接（JOIN）

**缺点**：
- **占用磁盘空间**
- **降低写操作速度**（INSERT/UPDATE/DELETE需要维护索引）
- 索引需要**定期维护**（碎片整理）

### [](#索引的存储结构)索引的存储结构

MySQL的InnoDB引擎使用 **B+树** 作为索引结构（而非二叉搜索树、红黑树、B树）。

**为什么不用二叉搜索树？**
- 树的高度太大（100万数据 → 树高20），每次查询需要多次磁盘IO

**为什么不用红黑树？**
- 本质还是二叉树，树高问题依然存在

**为什么不用B树？**
- B树的非叶子节点也存储数据，导致单个节点能存储的索引键更少
- 范围查询不如B+树高效

## [](#B树详解)B+树详解

### [](#B树的结构)B+树的结构

```
B+树（m=3，即3阶B+树）
                    [10, 20]
                   /     |      \
              [1,5]   [11,15]   [21,25]
             /  |  \   /  |  \   /  |  \
[1,2,3] [4,5,6] [11,12] [15,16] [21,22] [25,26]
         (叶子节点通过指针连接)
```

**B+树的特点**：
1. **非叶子节点只存储键**（不存储数据）
2. **所有数据都存储在叶子节点**
3. **叶子节点通过双向链表连接**（支持范围查询）
4. **树高度很低**（通常2-4层，可存储千万级数据）

### [](#为什么B树高度低)为什么B+树高度低？

假设：
- InnoDB页大小 = 16KB
- 主键bigint = 8B
- 指针 = 6B


- 单个索引节点可存储：16KB/(8B+6B) ≈ 1170个键
- 树高为3时：1170 × 1170 × 16 = **约2千万**条数据

## [](#聚簇索引与非聚簇索引)聚簇索引与非聚簇索引

### [](#聚簇索引Clustered-Index)聚簇索引（Clustered Index）

**定义**：索引键值的**逻辑顺序**与表中相应行的**物理顺序**相同。

InnoDB中，**主键索引是聚簇索引**：
- 叶子节点存储**完整的数据行**
- 一张表**只能有一个**聚簇索引

```
主键索引（聚簇索引）B+树
             [id=10]
            /         \
      [id=5]         [id=20]
      /      \         /      \
[id=1,数据行] [id=5,数据行] [id=10,数据行] [id=20,数据行]
```

### [](#非聚簇索引Secondary-Index)非聚簇索引（Secondary Index）

**定义**：叶子节点**不存储完整数据**，只存储**索引键 + 主键值**。

InnoDB中，**非主键索引都是非聚簇索引**：
- 叶子节点存储：索引键 + 主键值
- 通过主键值**回表**到聚簇索引取完整数据

```
非聚簇索引（例如：name索引）B+树
             [name='li']
            /             \
      [name='a']         [name='z']
      /          \         /          \
[name='a',id=1] [name='l',id=5] [name='l',id=10] [name='z',id=20]
                                         ↓ 回表
                            到主键索引取完整数据行
```

### [](#聚簇-vs-非聚簇对比)聚簇 vs 非聚簇对比

| 特性 | 聚簇索引（InnoDB主键） | 非聚簇索引（MyISAM） |
|------|------------------------|--------------------------|
| 叶子节点存储 | 完整数据行 | 数据行的地址（指针） |
| 索引数量 | 一张表只能有一个 | 一张表可以有多个 |
| 回表 | 不需要（主键查询） | 需要（通过指针找数据） |
| 范围查询 | 快（叶子节点链表） | 慢（需要多次随机IO） |

## [](#索引的类型)索引的类型

### [](#主键索引PRIMARY-KEY)主键索引（PRIMARY KEY）

```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,  -- 主键索引
    name VARCHAR(50)
);
```

- 唯一、非空
- InnoDB自动创建聚簇索引

### [](#唯一索引UNIQUE-INDEX)唯一索引（UNIQUE INDEX）

```sql
CREATE UNIQUE INDEX idx_email ON users(email);
-- 或
ALTER TABLE users ADD UNIQUE INDEX idx_email (email);
```

- 值唯一，但允许**多个NULL**（NULL不等于NULL）

### [](#普通索引NORMAL-INDEX)普通索引（NORMAL INDEX）

```sql
CREATE INDEX idx_name ON users(name);
-- 或
ALTER TABLE users ADD INDEX idx_name (name);
```

- 最常用，无唯一性约束

### [](#全文索引FULLTEXT-INDEX)全文索引（FULLTEXT INDEX）

```sql
CREATE FULLTEXT INDEX idx_content ON posts(content);
-- 使用
SELECT * FROM posts WHERE MATCH(content) AGAINST('MySQL索引');
```

- 支持中文需要ngram解析器（MySQL 5.7+）

### [](#前缀索引PREFIX-INDEX)前缀索引（PREFIX INDEX）

```sql
-- 对长文本，只索引前N个字符
CREATE INDEX idx_content_prefix ON posts(content(100));
```

- 节省索引空间
- 选择性降低（可能冲突）

## [](#覆盖索引)覆盖索引

**定义**：查询的**所有列**都包含在索引中，不需要**回表**。

```sql
-- 有联合索引：(name, age)
EXPLAIN SELECT name, age FROM users WHERE name = 'zhangsan';
-- Extra: Using index  ← 覆盖索引，不需要回表！
```

**优点**：
- 避免回表（减少磁盘IO）
- 提高查询速度

**如何设计覆盖索引**？
- 将查询中使用的列都加入联合索引
- 例如：`SELECT name, age FROM users WHERE name = ?` → 联合索引 `(name, age)`

## [](#最左前缀原则)最左前缀原则

联合索引遵循**最左前缀原则**：查询必须从索引的**最左列开始**，不能跳过。

假设有联合索引 `(a, b, c)`：

| 查询条件 | 是否使用索引 | 说明 |
|----------|--------------|------|
| `WHERE a = 1` | ✅ 使用索引 | 使用a |
| `WHERE a = 1 AND b = 2` | ✅ 使用索引 | 使用a、b |
| `WHERE a = 1 AND b = 2 AND c = 3` | ✅ 使用索引 | 使用a、b、c |
| `WHERE b = 2` | ❌ 不使用索引 | 跳过a |
| `WHERE a = 1 AND c = 3` | ⚠️ 部分使用 | 使用a，c失效 |
| `WHERE a > 1 AND b = 2` | ⚠️ 部分使用 | a用范围查询，b失效 |

**索引下推（Index Condition Pushdown，ICP）**：
- MySQL 5.6+ 支持
- 将WHERE条件**下推到存储引擎层过滤**，减少回表次数

## [](#索引优化实战)索引优化实战

### [](#EXPLAIN执行计划)EXPLAIN执行计划

```sql
EXPLAIN SELECT * FROM users WHERE name = 'zhangsan';
```

**关键字段解读**：

| 字段 | 说明 |
|------|------|
| `id` | 查询序号 |
| `select_type` | 查询类型（SIMPLE、PRIMARY、SUBQUERY） |
| `table` | 访问的表 |
| `type` | 访问类型（**重要！**） |
| `possible_keys` | 可能使用的索引 |
| `key` | 实际使用的索引 |
| `rows` | 预估扫描行数 |
| `Extra` | 额外信息 |

**type字段（从好到坏）**：
```
system > const > eq_ref > ref > range > index > ALL
```

- `const`：主键或唯一索引的等值查询
- `ref`：非唯一索引的等值查询
- `range`：范围查询（BETWEEN、IN、>、<）
- `index`：全索引扫描
- `ALL`：全表扫描（**最差，需优化**）

**Extra字段**：
- `Using index`：覆盖索引
- `Using where`：Server层过滤
- `Using temporary`：使用临时表（需优化）
- `Using filesort`：使用文件排序（需优化）

### [](#常见索引失效场景)常见索引失效场景

```sql
-- 1. 使用函数或表达式
WHERE YEAR(create_time) = 2024   -- ❌ 索引失效
WHERE create_time >= '2024-01-01'  -- ✅ 索引生效

-- 2. 隐式类型转换
WHERE phone = 13800138000   -- ❌ phone是VARCHAR，索引失效
WHERE phone = '13800138000'  -- ✅ 索引生效

-- 3. OR连接（部分情况）
WHERE name = 'zhang' OR age = 25  -- ❌ 索引失效（除非age也有索引）
WHERE name = 'zhang' OR id = 1    -- ✅ 索引生效（id是主键）

-- 4. LIKE左模糊
WHERE name LIKE 'zhang%'   -- ✅ 索引生效
WHERE name LIKE '%zhang'   -- ❌ 索引失效

-- 5. 不等于
WHERE age != 25   -- ❌ 索引失效
WHERE age > 25     -- ✅ 索引生效（范围查询）

-- 6. IS NULL / IS NOT NULL
WHERE name IS NULL       -- ✅ 索引生效（MySQL 5.7+）
WHERE name IS NOT NULL   -- ⚠️ 取决于NULL值比例
```

### [](#索引设计原则)索引设计原则

1. **单列索引 vs 联合索引**：优先使用联合索引（覆盖索引）
2. **索引列顺序**：选择性高的列放前面（区分度大的列）
3. **避免过多索引**：每张表索引不超过5-7个
4. **使用前缀索引**：对TEXT/BLOB类型
5. **删除不使用的索引**：通过`sys.schema_unused_indexes`查看

## [](#总结)总结

本文深入讲解了MySQL索引的核心知识：

1. **索引的本质**：排好序的B+树数据结构
2. **B+树原理**：非叶子节点只存键，叶子节点存数据并通过链表连接
3. **聚簇索引**：主键索引，叶子节点存完整数据行
4. **非聚簇索引**：二级索引，叶子节点存主键值，需要回表
5. **覆盖索引**：所有查询列都在索引中，避免回表
6. **最左前缀原则**：联合索引必须从最左列开始
7. **索引优化**：EXPLAIN分析、避免索引失效、合理设计索引

下期预告：
- 数据库面试八股文（四）——MySQL事务与ACID特性
- 数据库面试八股文（五）——MySQL锁机制（行锁、表锁、间隙锁、MVCC）

