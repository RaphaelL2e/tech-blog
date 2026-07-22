---
title: MySQL 锁机制深入理解
date: 2026-05-12 17:30:00+08:00
updated: '2026-05-12T17:30:00+08:00'
description: 面试高频问题：MySQL 有哪些锁？ InnoDB 和 MyISAM 的锁有什么区别？什么是死锁？如何避免？ 锁是数据库并发控制的核心机制，用于保证事务的隔离性和数据一致性。MySQL 中，不同存储引擎的锁机制差异很大，InnoDB
  采用了细粒度的行锁和 MVCC，相比 MyISAM 的表锁更适合高。
topic: database-middleware
level: intermediate
status: maintained
tags:
- MySQL
- lock
- innodb
- myisam
- deadlock
categories:
- 数据库与中间件
draft: false
---

> 面试高频问题：MySQL 有哪些锁？ InnoDB 和 MyISAM 的锁有什么区别？什么是死锁？如何避免？

## 引言

锁是数据库并发控制的核心机制，用于保证事务的隔离性和数据一致性。MySQL 中，不同存储引擎的锁机制差异很大，InnoDB 采用了细粒度的行锁和 MVCC，相比 MyISAM 的表锁更适合高并发场景。

## 一、锁概述

### 1.1 为什么需要锁？

```
并发问题示例：
                    时间线
事务 A ──────────────────────────────────→
                    │ 读取 balance=1000
                    │                  │ balance=1000+100=1100
                    │                  │ (还没提交)
事务 B ──────────────────────────────────→
                    │ 读取 balance=1000
                    │                  │ balance=1000+200=1200
                    │                  │ (提交)
                    
结果：balance 应该是 1000-100-200=700
     但实际可能是 1100 或 1200（取决于谁先提交）
```

没有锁：并发事务相互干扰，数据不一致

### 1.2 锁的作用

1. **保证数据一致性**：防止并发事务相互干扰
2. **实现事务隔离**：不同隔离级别通过不同锁实现
3. **维护数据完整性**：防止脏读、不可重复读、幻读

## 二、MySQL 锁的分类

### 2.1 按锁粒度划分

```
锁粒度
├── 表锁：锁定整张表
├── 行锁：锁定表中某一行
├── 页锁：锁定某一页（BDB 存储引擎）
└── 意向锁：表级锁，表示事务有意向锁定某行
```

| 锁类型 | 开销 | 冲突概率 | 并发度 | 场景 |
|-------|------|---------|--------|------|
| 表锁 | 小 | 高 | 低 | MyISAM、MongoDB |
| 行锁 | 大 | 低 | 高 | InnoDB |
| 页锁 | 中 | 中 | 中 | BDB |

**InnoDB 与 MyISAM 锁对比**：

| 特性 | InnoDB | MyISAM |
|------|--------|--------|
| 锁类型 | 行锁 + 表锁 | 表锁 |
| 并发度 | 高 | 低 |
| 事务支持 | 支持 | 不支持 |
| 死锁 | 可能 | 不可能 |
| MVCC | 支持 | 不支持 |

### 2.2 按锁属性划分

```
锁属性
├── 共享锁（S 锁）：读锁，可并行读
├── 排他锁（X 锁）：写锁，互斥
├── 意向共享锁（IS）：表级，表示事务将使用 S 锁
└── 意向排他锁（IX）：表级，表示事务将使用 X 锁
```

**S 锁与 X 锁的兼容矩阵**：

| | S 锁 | X 锁 |
|---|------|------|
| **S 锁** | ✅ 兼容 | ❌ 冲突 |
| **X 锁** | ❌ 冲突 | ❌ 冲突 |

```sql
-- S 锁：其他事务可以读，不能写
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;

-- X 锁：其他事务不能读也不能写
SELECT * FROM users WHERE id = 1 FOR UPDATE;
```

### 2.3 意向锁的作用

**问题**：事务 A 对行加 X 锁，事务 B 想对整张表加 S 锁，如何快速判断表有没有行被锁定？

**方案 1**：遍历所有行检查（太慢）

**方案 2**：在表上加一个标志位（意向锁）

```sql
-- 事务 A
BEGIN;
SELECT * FROM users WHERE id = 1 FOR UPDATE;  -- IX + X 锁
-- 此时 users 表有 IX 锁

-- 事务 B
BEGIN;
LOCK TABLES users READ;  -- 尝试加 S 锁
-- InnoDB 发现表有 IX 锁 → 阻塞
```

**意向锁的兼容性**：

| | IS 锁 | IX 锁 |
|---|-------|-------|
| **S 锁** | ✅ 兼容 | ❌ 冲突 |
| **X 锁** | ❌ 冲突 | ❌ 冲突 |

| | IS | IX | S | X |
|---|----|----|---|---|
| **IS** | ✅ | ✅ | ✅ | ❌ |
| **IX** | ✅ | ✅ | ❌ | ❌ |
| **S** | ✅ | ❌ | ✅ | ❌ |
| **X** | ❌ | ❌ | ❌ | ❌ |

## 三、InnoDB 行锁详解

### 3.1 记录锁（Record Lock）

锁定索引记录。

```sql
-- 锁定 id = 1 的记录
SELECT * FROM users WHERE id = 1 FOR UPDATE;

-- 等价于（如果 id 是主键）
UPDATE users SET name = '张三' WHERE id = 1;
```

**特点**：
- 只锁定一行
- 如果 id 不是索引，会锁定多行甚至整张表

### 3.2 间隙锁（Gap Lock）

锁定索引记录之间的间隙。

```sql
-- 锁定 id 在 (1, 10) 之间的间隙
SELECT * FROM users WHERE id > 1 AND id < 10 FOR UPDATE;
```

**特点**：
- 不锁定记录本身
- 锁定记录之间的间隙
- 防止其他事务在间隙中插入数据

### 3.3 临键锁（Next-Key Lock）

临键锁 = 记录锁 + 间隙锁，是 InnoDB 在 REPEATABLE READ 下的默认加锁方式。

```sql
-- 锁定 id = 5 的记录，以及 (5, 下一个记录) 的间隙
SELECT * FROM users WHERE id = 5 FOR UPDATE;

-- 如果表中 id 为 1, 5, 10
-- 锁定范围：[5, 10)
```

**临键锁的锁定规则**：

假设表中有 id 为 1, 5, 10 的记录：

| SQL 语句 | 锁定范围 |
|---------|---------|
| `WHERE id = 5` | [1, 5] + (5, 10) = [1, 10) |
| `WHERE id > 5` | (5, 10] + (10, +∞) |
| `WHERE id >= 5` | [5, 10] + (10, +∞) |
| `WHERE id < 5` | (-∞, 1] + (1, 5) |
| `WHERE id <= 5` | (-∞, 1] + (1, 5] |
| `WHERE id BETWEEN 1 AND 5` | (-∞, 1] + [1, 5] + (5, 10) = (-∞, 10) |

### 3.4 插入意向锁（Insert Intention Lock）

INSERT 操作在插入前会加插入意向锁。

```sql
-- 事务 A 插入 id = 6
INSERT INTO users VALUES (6, '小华');

-- 事务 B 插入 id = 7
INSERT INTO users VALUES (7, '小军');

-- 两个插入意向锁不冲突
```

**注意**：插入意向锁是 Gap Lock 的一种，不是 X 锁。

## 四、MyISAM 表锁

### 4.1 表锁加锁方式

```sql
-- 显式加表读锁
LOCK TABLES users READ;

-- 显式加表写锁
LOCK TABLES users WRITE;

-- 解锁
UNLOCK TABLES;
```

### 4.2 锁调度机制

MyISAM 读写是串行的：
- 读请求优先 → 读操作可能长时间等待
- 写请求优先 → 写操作可能阻塞读

```sql
-- 线程 A
LOCK TABLES users WRITE;  -- 获取写锁

-- 线程 B 想读取
SELECT * FROM users;  -- 阻塞，等待写锁释放

-- 线程 C 想写入
INSERT INTO users VALUES (1, '张三');  -- 同样阻塞
```

### 4.3 并发插入

MyISAM 支持并发插入：

```sql
-- 允许并发插入（MyISAM 默认）
SET concurrent_insert = 1;  -- 有空余空间时并发插入

-- 总是并发插入
SET concurrent_insert = 2;

-- 禁用并发插入
SET concurrent_insert = 0;
```

## 五、乐观锁与悲观锁

### 5.1 悲观锁（Pessimistic Lock）

假设并发冲突一定发生，先加锁再操作。

```sql
-- 悲观锁：SELECT ... FOR UPDATE
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- 加 X 锁
-- 业务逻辑...
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;  -- 释放锁
```

**适用场景**：冲突频繁、并发写入多的场景

### 5.2 乐观锁（Optimistic Lock）

假设冲突很少发生，不加锁，通过版本号检查冲突。

```sql
-- 乐观锁：版本号机制
UPDATE accounts 
SET balance = balance - 100, version = version + 1 
WHERE id = 1 AND version = 1;  -- 版本匹配才更新

-- 如果 version 已变（被其他事务更新），影响行数为 0
-- 应用层重新读取、修改、提交
```

**适用场景**：冲突较少、读多写多的场景

### 5.3 两种锁的对比

| 特性 | 悲观锁 | 乐观锁 |
|------|--------|--------|
| 实现方式 | 数据库锁 | 版本号/时间戳 |
| 并发度 | 低 | 高 |
| 冲突处理 | 阻塞等待 | 冲突后重试 |
| 适用场景 | 冲突频繁 | 冲突较少 |
| 开销 | 锁开销 | 重试开销 |

## 六、死锁

### 6.1 什么是死锁？

死锁：两个或多个事务相互等待对方持有的锁，形成循环等待。

```
事务 A：
    锁定 id=1，等待 id=2

事务 B：
    锁定 id=2，等待 id=1

→ 死锁！
```

### 6.2 死锁示例

```sql
-- 事务 A
BEGIN;
UPDATE users SET name = 'A' WHERE id = 1;  -- 锁定 id=1
UPDATE users SET name = 'A' WHERE id = 2;  -- 等待 id=2

-- 事务 B（同时执行）
BEGIN;
UPDATE users SET name = 'B' WHERE id = 2;  -- 锁定 id=2
UPDATE users SET name = 'B' WHERE id = 1;  -- 等待 id=1
-- 死锁！
```

### 6.3 InnoDB 死锁处理

InnoDB 自动检测死锁，选择回滚代价最小的事务：

```sql
-- 死锁发生时，InnoDB 会回滚一个事务
ERROR 1213 (40001): Deadlock found when trying to get lock;
try restarting transaction
```

**InnoDB 死锁检测**：
- 等待图（Wait-for Graph）：检测循环等待
- 超时机制：`innodb_lock_wait_timeout`（默认 50 秒）

### 6.4 避免死锁

**1. 按固定顺序访问数据**

```sql
-- 事务 A
UPDATE users SET name = 'A' WHERE id = 1;  -- 先 id=1
UPDATE users SET name = 'A' WHERE id = 2;  -- 后 id=2

-- 事务 B
UPDATE users SET name = 'B' WHERE id = 1;  -- 先 id=1
UPDATE users SET name = 'B' WHERE id = 2;  -- 后 id=2

-- 不会死锁！顺序一致
```

**2. 减小事务范围**

```sql
-- ❌ 不好：长事务
BEGIN;
SELECT * FROM users;  -- 可能锁定多行
-- 业务逻辑...（花费很长时间）
UPDATE users SET name = 'X' WHERE id = 1;
COMMIT;

-- ✅ 好：短事务
BEGIN;
UPDATE users SET name = 'X' WHERE id = 1;
COMMIT;
```

**3. 降低隔离级别**

```sql
SET transaction isolation level READ COMMITTED;
```

**4. 添加合理索引**

```sql
-- ❌ 不好：无索引，锁定多行
UPDATE users SET name = 'X' WHERE name = '张三';  -- 全表扫描，锁定多行

-- ✅ 好：有索引，只锁定匹配的行
CREATE INDEX idx_name ON users(name);
UPDATE users SET name = 'X' WHERE name = '张三';  -- 索引查询，只锁定匹配行
```

**5. 使用悲观锁时加锁范围尽量小**

```sql
-- ❌ 不好：锁定整张表
BEGIN;
SELECT * FROM users FOR UPDATE;  -- 锁定所有行

-- ✅ 好：只锁定需要的行
BEGIN;
SELECT * FROM users WHERE id = 1 FOR UPDATE;  -- 只锁定 id=1
```

## 七、锁问题与监控

### 7.1 常见锁问题

**1. 锁等待超时**

```sql
-- 设置锁等待超时
SET innodb_lock_wait_timeout = 5;  -- 5 秒

-- 超过时间会报错
ERROR 1205 (HY000): Lock wait timeout exceeded; try restarting transaction
```

**2. 锁表**

```sql
-- 查看锁状态
SHOW ENGINE INNODB STATUS;

-- 查看当前锁
SELECT * FROM information_schema.INNODB_LOCKS;

-- 查看锁等待
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
```

**3. 长事务导致锁堆积**

```sql
-- 查看长时间运行的事务
SELECT * FROM information_schema.INNODB_TRX 
WHERE trx_started < NOW() - INTERVAL 10 MINUTE;
```

### 7.2 锁监控

```sql
-- 查看锁信息
SHOW STATUS LIKE 'Innodb_row_lock%';

-- 查看事务
SELECT * FROM information_schema.INNODB_TRX;

-- 查看锁等待
SELECT 
    r.trx_id,
    r.trx_mysql_thread_id,
    r.trx_query,
    b.lock_mode,
    b.lock_type,
    b.lock_table
FROM information_schema.INNODB_TRX r
JOIN information_schema.INNODB_LOCKS b ON r.trx_id = b.lock_trx_id;
```

## 八、面试高频问题

### Q1：InnoDB 和 MyISAM 的锁有什么区别？

**答**：
- InnoDB：行锁 + 表锁，支持事务和 MVCC，高并发
- MyISAM：纯表锁，不支持事务，并发性能差

### Q2：什么是临键锁（Next-Key Lock）？

**答**：临键锁 = 记录锁 + 间隙锁，是 InnoDB 在 REPEATABLE READ 下的默认锁。可以防止幻读，锁定记录本身和前后间隙。

### Q3：什么是死锁？如何避免？

**答**：
- 死锁：两个或多个事务相互等待对方持有的锁
- 避免方法：按固定顺序访问、加合理索引、减小事务范围、降低隔离级别

### Q4：乐观锁和悲观锁的区别？

**答**：
- 悲观锁：先加锁再操作，适合冲突频繁的场景
- 乐观锁：通过版本号检查冲突，适合冲突较少的场景

### Q5：InnoDB 如何解决幻读？

**答**：
- 快照读：MVCC 保证不出现幻读
- 当前读：Next-Key Lock 锁住记录和间隙

### Q6：锁等待超时参数是什么？

**答**：`innodb_lock_wait_timeout`，默认 50 秒。

## 九、总结

**锁核心要点**：
- **锁粒度**：表锁 vs 行锁，InnoDB 以行锁为主
- **锁类型**：S 锁、X 锁、IS 锁、IX 锁
- **行锁细分**：记录锁、间隙锁、临键锁
- **悲观锁 vs 乐观锁**：先锁 vs 版本检查
- **死锁**：循环等待，自动检测回滚

**锁优化建议**：
1. 合理使用索引，减少锁范围
2. 控制事务大小，避免长事务
3. 按固定顺序访问数据
4. 监控锁状态，及时发现问题

---

**本系列进度：23/30 篇 (77%)**

**下一篇预告**：MySQL 日志系统（binlog、redo log、undo log）

**参考资料**：
- MySQL 官方文档：https://dev.mysql.com/doc/refman/8.0/en/innodb-locking.html
- 《高性能 MySQL》- Baron Schwartz
- 《MySQL 技术内幕：InnoDB 存储引擎》- 姜承尧
