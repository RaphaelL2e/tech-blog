---
title: "MySQL 索引与查询优化深度解析"
date: 2026-05-12T17:20:00+08:00
draft: false
categories: ["mysql"]
tags: ["mysql", "index", "b-plus-tree", "query-optimization"]
---


# MySQL 索引与查询优化深度解析

> 面试高频问题：MySQL 索引底层为什么用 B+ 树？索引失效的场景？如何优化慢查询？

## 引言

MySQL 索引是面试中最常考的知识点之一，也是生产环境优化的重点。理解索引的原理、结构和失效场景，是每个后端工程师的必备技能。

## 一、索引基础

### 1.1 什么是索引？

索引（Index）是数据库表中一种特殊的数据结构，用于加速数据检索。就像书籍的目录一样，索引可以让我们快速找到需要的数据，而不需要扫描全表。

```sql
-- 无索引：全表扫描
SELECT * FROM users WHERE name = '张三';

-- 有索引：索引查找
CREATE INDEX idx_name ON users(name);
SELECT * FROM users WHERE name = '张三';  -- 使用 idx_name
```

### 1.2 索引的分类

```
索引类型
├── 数据结构：B树索引、B+树索引、Hash索引、R树索引、全文索引
├── 存储方式：聚簇索引、非聚簇索引
├── 字段数量：单列索引、组合索引
└── 字段特性：主键索引、唯一索引、普通索引、前缀索引
```

### 1.3 索引的优缺点

**优点**：
- 大幅减少检索的数据量
- 减少 I/O 操作次数
- 加速 ORDER BY 和 GROUP BY
- 加速 JOIN 操作

**缺点**：
- 占用磁盘空间
- 降低写操作性能（INSERT/UPDATE/DELETE 需要维护索引）
- 过多索引会增加优化器的选择成本

## 二、MySQL 索引底层结构

### 2.1 二叉树与红黑树

**二叉查找树（BST）**：
```
        8
       / \
      3   10
     / \    \
    1   6    14

查找 6：8 → 3 → 6，3 步
查找 14：8 → 10 → 14，3 步
```

- 查找效率：O(log₂n)
- 问题：数据有序时退化成链表，退化为 O(n)

**红黑树（自平衡二叉查找树）**：
- 本质：二叉树，自动平衡
- 查找效率：O(log₂n)
- 问题：树高不可控，数据量大时仍然很深，I/O 次数多

### 2.2 B 树（B-Tree）

B 树是一种多路平衡查找树，每个节点可以有多个子节点。

```
B 树（阶数 m=3）
                    [5 | 10 | 15]
                   /    |    \
          [1 | 3]   [6 | 8]   [11 | 13 | 17 | 20]
```

**B 树的特点**：
- 所有节点都存储数据
- 叶子节点在同一层
- 每个节点最多有 m 个子节点
- 每个节点最多存储 m-1 个键

### 2.3 B+ 树（B+ Tree）— MySQL 的选择

```
B+ 树（InnoDB 默认）
                    [5 | 10]
                   /   |   \
          [1 | 3]     [6 | 8]     [11 | 13 | 15 | 20]
           ↓             ↓              ↓
    [1 | 2 | 3 | 4]  [5 | 6 | 7 | 8]  [9 | 10 | 11 | 12 | ...]  ← 叶子节点链表
```

**B+ 树与 B 树的核心区别**：

| 特性 | B 树 | B+ 树 |
|------|------|-------|
| 数据存储 | 所有节点都存储数据 | 只有叶子节点存储数据 |
| 叶子节点 | 叶子节点无链表连接 | 叶子节点通过链表连接 |
| 查找稳定性 | 不稳定 | 稳定（所有查询都要到叶子） |
| 范围查询 | 需要中序遍历 | 链表顺序遍历 |

**为什么 MySQL 选择 B+ 树？**

1. **I/O 次数更少**
   - B 树：每个节点都可能存储数据，树高 = I/O 次数
   - B+ 树：非叶子节点不存数据，可以放更多索引，树高更矮
   - 假设每个节点 16KB，树高 3 层：3 亿条数据只需 3 次 I/O

2. **范围查询更高效**
   - B 树：区间查询需要中序遍历，复杂
   - B+ 树：叶子节点链表，顺序访问，O(1)

3. **查询更稳定**
   - B 树：最好情况 O(1)，最坏 O(log₂n)
   - B+ 树：所有查询都到叶子节点，O(log₂n)

### 2.4 MyISAM 与 InnoDB 索引对比

**MyISAM（非聚簇索引）**：
```
主键索引：
    [1, 指针1] → [2, 指针2] → [3, 指针3]
        ↓            ↓            ↓
    data1          data2         data3

普通索引：
    [name: 张三, 指针1] → [name: 李四, 指针2]
        ↓                    ↓
    data1                  data2
```

**InnoDB（聚簇索引）**：
```
主键索引（B+ 树，叶子节点存完整行数据）：
    [1] → [完整行数据1]
    [2] → [完整行数据2]
    [3] → [完整行数据3]

普通索引（B+ 树，叶子节点存主键值）：
    [name: 张三, 1] → [name: 李四, 2]
         ↓                ↓
    主键 1 的完整数据    主键 2 的完整数据
```

**关键区别**：
- 聚簇索引：数据和索引在一起，叶子节点就是数据
- 非聚簇索引：数据和索引分开，索引指向数据的物理位置

## 三、聚簇索引与辅助索引

### 3.1 聚簇索引（Clustered Index）

InnoDB 中，聚簇索引就是主键索引：
- 数据按主键顺序存储
- 每个表只能有一个聚簇索引
- 如果没有主键，选择第一个唯一索引
- 如果没有唯一索引，InnoDB 生成隐藏的 row_id

### 3.2 辅助索引（Secondary Index）

非主键索引都是辅助索引：
- 叶子节点存储主键值
- 查找数据需要"回表"

```sql
CREATE TABLE users (
    id INT PRIMARY KEY,      -- 聚簇索引
    name VARCHAR(20),
    age INT,
    INDEX idx_name (name),   -- 辅助索引
    INDEX idx_age (age)      -- 辅助索引
);
```

### 3.3 回表查询

```sql
SELECT * FROM users WHERE name = '张三';
```

```
1. 查询辅助索引 idx_name
   找到 name='张三' 的主键 id=1

2. 回表查询聚簇索引
   根据 id=1 找到完整行数据

3. 返回结果
```

**如何避免回表？**

使用**覆盖索引**：需要的数据都在索引中，不需要回表。

```sql
-- 需要回表
SELECT * FROM users WHERE name = '张三';

-- 覆盖索引，不需要回表
SELECT name, age FROM users WHERE name = '张三';
```

## 四、组合索引与最左前缀原则

### 4.1 组合索引

```sql
CREATE INDEX idx_name_age ON users(name, age);
```

组合索引的 B+ 树结构（按 name, age 排序）：

```
                    [name | age]
                    /    |    \
            [张三 | 20]  [李四 | 25]  [王五 | 30]
                ↓           ↓           ↓
            [指针]        [指针]      [指针]
```

**存储顺序**：先按 name 排序，name 相同再按 age 排序

### 4.2 最左前缀原则（Leftmost Prefix）

**核心规则**：从组合索引的最左边开始，连续使用索引。

```sql
CREATE INDEX idx_name_age_gender ON users(name, age, gender);
```

| SQL 语句 | 使用索引情况 |
|---------|------------|
| `WHERE name = '张三'` | ✅ 使用（最左列） |
| `WHERE name = '张三' AND age = 20` | ✅ 使用（连续） |
| `WHERE name = '张三' AND age = 20 AND gender = '男'` | ✅ 使用（全列） |
| `WHERE age = 20` | ❌ 不使用（跳过最左列） |
| `WHERE gender = '男'` | ❌ 不使用（跳过最左列） |
| `WHERE name = '张三' AND gender = '男'` | ⚠️ 部分使用（只用了 name） |
| `WHERE name LIKE '张%'` | ✅ 使用（前缀匹配） |
| `WHERE name LIKE '%三'` | ❌ 不使用（不是前缀） |

### 4.3 索引失效的场景

**1. 使用 OR 连接非索引列**

```sql
-- 失效
SELECT * FROM users WHERE name = '张三' OR age = 20;

-- 生效（or 两边都是索引列）
SELECT * FROM users WHERE name = '张三' OR id = 1;
```

**2. 使用函数或运算**

```sql
-- 失效
SELECT * FROM users WHERE YEAR(create_time) = 2024;
SELECT * FROM users WHERE age + 1 = 21;

-- 生效
SELECT * FROM users WHERE create_time >= '2024-01-01';
SELECT * FROM users WHERE age = 20;
```

**3. 类型转换**

```sql
-- 失效（name 是 VARCHAR，参数是 INT）
SELECT * FROM users WHERE name = 123;

-- 生效
SELECT * FROM users WHERE name = '123';
```

**4. LIKE 模糊查询以 % 开头**

```sql
-- 失效
SELECT * FROM users WHERE name LIKE '%三';

-- 生效
SELECT * FROM users WHERE name LIKE '三%';
```

**5. 索引列参与比较**

```sql
-- 失效
SELECT * FROM users WHERE age > 18;

-- 生效
SELECT * FROM users WHERE age >= 18;
```

**6. NOT IN / NOT EXISTS**

```sql
-- 失效
SELECT * FROM users WHERE age NOT IN (18, 20, 25);

-- 生效（改用范围）
SELECT * FROM users WHERE age < 18 OR age > 18;
```

**7. ORDER BY 的坑**

```sql
-- 失效（ORDER BY 的列不在索引中）
CREATE INDEX idx_name ON users(age);
SELECT * FROM users ORDER BY name;

-- 生效
SELECT * FROM users ORDER BY age;

-- 部分失效（ORDER BY 和 WHERE 不一致）
SELECT * FROM users WHERE age = 20 ORDER BY name;

-- 生效（组合索引中，ORDER BY 顺序符合最左前缀）
CREATE INDEX idx_age_name ON users(age, name);
SELECT * FROM users WHERE age = 20 ORDER BY name;
```

## 五、索引优化实战

### 5.1 慢查询分析

```sql
-- 查看慢查询日志配置
SHOW VARIABLES LIKE 'slow_query%';
SHOW VARIABLES LIKE 'long_query_time';

-- 开启慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;

-- 查看慢查询日志
SHOW GLOBAL STATUS LIKE 'Slow_queries';
```

### 5.2 EXPLAIN 分析执行计划

```sql
EXPLAIN SELECT * FROM users WHERE name = '张三';
```

**关键字段解析**：

| 字段 | 含义 | 优化目标 |
|------|------|---------|
| type | 访问类型 | 最好 const/ref/range，避免 ALL |
| key | 实际使用的索引 | 应有值 |
| rows | 预计扫描行数 | 越少越好 |
| Extra | 附加信息 | 避免 Using filesort/Using temporary |

**type 字段值（从好到差）**：
```
const    → 主键或唯一索引等值查询（最优）
ref      → 普通索引等值查询
range    → 索引范围查询
index    → 全索引扫描
ALL      → 全表扫描（最差）
```

**Extra 字段**：
```
Using index     → 覆盖索引，性能好
Using where      → 需要回表检查
Using filesort   → 需要额外排序，差
Using temporary  → 需要临时表，差
```

### 5.3 索引优化技巧

**1. 覆盖索引优化**

```sql
-- 优化前：回表查询
SELECT id, name, age FROM users WHERE name = '张三';

-- 优化后：覆盖索引
CREATE INDEX idx_name_age ON users(name, age);  -- id 是主键，会自动包含
```

**2. 前缀索引**

```sql
-- 对长字符串建立前缀索引
ALTER TABLE users ADD INDEX idx_email (email(10));
```

**3. 索引下推（Index Condition Pushdown, ICP）**

MySQL 5.6+ 引入，减少回表次数。

```sql
SELECT * FROM users WHERE name LIKE '张%' AND age = 20;
```

- **优化前**：先根据 name 找到所有主键，再回表检查 age
- **优化后**：在索引中直接过滤 age，减少回表次数

**4. 强制索引**

```sql
SELECT * FROM users FORCE INDEX(idx_name) WHERE name = '张三';
```

### 5.4 索引设计原则

1. **WHERE 子句中的列建立索引**
   - 出现在 WHERE、JOIN、ON 的列优先建索引

2. **区分度高的列优先**
   ```sql
   -- 区分度：COUNT(DISTINCT col) / COUNT(*)
   -- 性别（区分度 0.5）< 手机号（区分度 ≈ 1）
   ```

3. **组合索引优于多个单列索引**
   ```sql
   -- 推荐
   CREATE INDEX idx_name_age ON users(name, age);
   
   -- 不推荐（除非有特殊查询）
   CREATE INDEX idx_name ON users(name);
   CREATE INDEX idx_age ON users(age);
   ```

4. **控制索引数量**
   - 单表索引不超过 5 个
   - 过多索引影响写性能

5. **利用自增主键**
   - InnoDB 推荐使用自增主键
   - 插入数据时不需要移动其他数据

## 六、面试高频问题

### Q1：为什么 MySQL 索引用 B+ 树而不是 B 树？

**答**：
1. B+ 树非叶子节点不存储数据，可以放更多索引，降低树高，减少 I/O
2. B+ 树叶子节点链表连接，适合范围查询
3. 所有查询都要到叶子节点，查询更稳定

### Q2：B+ 树索引一次能读多少数据？

**答**：
- InnoDB 默认页大小 16KB
- 假设主键 BIGINT 8 字节 + 指针 6 字节 = 14 字节
- 每页可存 16KB / 14 ≈ 1170 个索引
- 3 层 B+ 树：1170 × 1170 × 1170 ≈ 16 亿条数据

### Q3：聚簇索引和非聚簇索引的区别？

**答**：
- 聚簇索引：数据和索引在一起，叶子节点就是数据，每个表一个
- 非聚簇索引：数据和索引分开，索引指向数据位置

### Q4：什么是回表？如何避免？

**答**：
- 回表：查询辅助索引，先拿到主键，再回表查聚簇索引
- 避免方法：使用覆盖索引，需要的字段都在索引中

### Q5：最左前缀原则是什么？

**答**：组合索引从最左边开始连续使用。例如 (name, age, gender)：
- ✅ WHERE name = 'x' AND age = 10
- ✅ WHERE name = 'x'
- ❌ WHERE age = 10
- ❌ WHERE gender = 'x'

### Q6：哪些情况会导致索引失效？

**答**：
1. OR 连接非索引列
2. 索引列使用函数或运算
3. 类型转换
4. LIKE 以 % 开头
5. NOT IN / NOT EXISTS
6. ORDER BY 列不在索引中

## 七、总结

**索引核心要点**：
- **B+ 树**：MySQL 默认索引结构，低 I/O、稳定、适合范围查询
- **聚簇索引**：数据按主键存储，每个表一个
- **辅助索引**：叶子节点存主键，需要回表
- **覆盖索引**：避免回表，性能最优
- **最左前缀**：组合索引的连续使用规则
- **索引失效**：OR、函数、类型转换、%开头、NOT IN

**优化实践**：
- 善用 EXPLAIN 分析执行计划
- 避免 SELECT *，使用覆盖索引
- 区分度高的列优先建索引
- 单表索引不超过 5 个
- 利用 ICP 减少回表

---

**本系列进度：21/30 篇 (70%)**

**下一篇预告**：MySQL 事务与隔离级别深度解析

**参考资料**：
- MySQL 官方文档：https://dev.mysql.com/doc/refman/8.0/en/
- 《高性能 MySQL》- Baron Schwartz
- MySQL Internals Manual：https://dev.mysql.com/doc/internals/en/
