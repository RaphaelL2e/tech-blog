---
title: 数据库面试八股文（五）——MySQL锁机制（行锁、表锁、间隙锁、MVCC）
date: 2026-06-02 23:00:00+08:00
updated: '2026-06-02T23:00:00+08:00'
description: 锁是数据库实现隔离性和一致性的核心机制。上一篇文章我们学习了事务的ACID特性和隔离级别，本文将深入讲解MySQL/InnoDB的各种锁类型、加锁规则、死锁处理，以及锁与MVCC的协作关系。锁机制是面试中区分度高、考察深入的重点。
  全局锁对整个数据库实例加锁，让数据库处于只读状态。 使用场景：全库逻。
topic: database-middleware
series: database-interview
series_order: 5
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- MySQL
- 锁
- 行锁
categories:
- 数据库与中间件
draft: false
---

## 概述

锁是数据库实现**隔离性**和**一致性**的核心机制。上一篇文章我们学习了事务的ACID特性和隔离级别，本文将深入讲解MySQL/InnoDB的**各种锁类型、加锁规则、死锁处理**，以及锁与MVCC的协作关系。锁机制是面试中区分度高、考察深入的重点。

## 锁的分类总览

```
MySQL锁
├── 全局锁
│   └── FTWRL（Flush Tables With Read Lock）
├── 表级锁
│   ├── 表锁（LOCK TABLES）
│   ├── 元数据锁（MDL）
│   ├── 自增锁（AUTO-INC Lock）
│   └── 意向锁（IS/IX）
└── 行级锁（InnoDB特有）
    ├── 记录锁（Record Lock）
    ├── 间隙锁（Gap Lock）
    └── 临键锁（Next-Key Lock = Record + Gap）
```

## 全局锁

**全局锁**对整个数据库实例加锁，让数据库处于**只读状态**。

```sql
-- 加全局锁
FLUSH TABLES WITH READ LOCK;

-- 此时只能读，不能写
SELECT * FROM users;  -- ✅
INSERT INTO users ... ;  -- ❌

-- 释放全局锁
UNLOCK TABLES;
```

**使用场景**：全库逻辑备份（mysqldump --single-transaction使用的是一致性读，不需要全局锁）。

**缺点**：
- 整个库只读，业务停摆
- 如果有长查询，FTWRL会被阻塞
- 如果在主库加锁，从库也无法执行主库同步的写操作

> 💡 **面试建议**：推荐使用 `mysqldump --single-transaction` 做InnoDB备份，利用MVCC实现一致性快照，不需要加全局锁。

## 表级锁

### 表锁（Table Lock）

```sql
-- 加读锁（共享锁）
LOCK TABLES users READ;
-- 其他会话可以读，不能写

-- 加写锁（排他锁）
LOCK TABLES users WRITE;
-- 其他会话不能读也不能写

-- 释放
UNLOCK TABLES;
```

**特点**：锁粒度大，并发度低，MyISAM和InnoDB都支持。

### 元数据锁（MDL, Metadata Lock）

MySQL 5.5引入，**自动加锁**，不需要显式使用。

- 执行DML（SELECT/INSERT/UPDATE/DELETE）时，自动加**MDL读锁**
- 执行DDL（ALTER TABLE等）时，自动加**MDL写锁**

**作用**：防止DML执行期间，表结构被修改。

**常见问题**：DDL被长事务阻塞

```
会话A: BEGIN; SELECT * FROM users;  -- 加MDL读锁，事务未提交
会话B: ALTER TABLE users ADD COLUMN age INT;  -- 需要MDL写锁，被阻塞！
会话C: SELECT * FROM users;  -- 也被阻塞！（等会话B的MDL写锁）
```

> ⚠️ **生产事故常见原因**：长事务持有MDL读锁，导致DDL和后续查询全部阻塞。解决方案：设置 `lock_wait_timeout`，DDL超时自动失败。

```sql
-- 设置DDL锁等待超时（秒）
SET SESSION lock_wait_timeout = 5;
ALTER TABLE users ADD COLUMN age INT;  -- 5秒内拿不到锁就报错
```

### 意向锁（Intention Lock）

意向锁是**表级锁**，用于**快速判断表里是否有行锁**。

| 意向锁 | 说明 |
|--------|------|
| 意向共享锁（IS） | 事务打算给某行加S锁前，先在表级加IS锁 |
| 意向排他锁（IX） | 事务打算给某行加X锁前，先在表级加IX锁 |

**为什么需要意向锁**：

没有意向锁时，如果要加表锁，必须扫描表中每一行看是否有行锁——效率极低。

有意向锁后：
```
加表锁时，只需检查表上是否有冲突的意向锁：
  表锁S锁 ← 与IX冲突
  表锁X锁 ← 与IS和IX都冲突
```

**兼容性矩阵**：

|  | IS | IX | S | X |
|--|----|----|---|---|
| **IS** | ✅ | ✅ | ✅ | ❌ |
| **IX** | ✅ | ✅ | ❌ | ❌ |
| **S** | ✅ | ❌ | ✅ | ❌ |
| **X** | ❌ | ❌ | ❌ | ❌ |

> 💡 **关键理解**：意向锁之间互不冲突（IS✅IX），意向锁只和表锁冲突。意向锁是**自动加的**，不需要手动操作。

### 自增锁（AUTO-INC Lock）

插入带有AUTO_INCREMENT列的记录时使用。

| 模式 | 说明 | 性能 | 安全性 |
|------|------|------|--------|
| innodb_autoinc_lock_mode=0 | 传统模式，所有INSERT都加表级自增锁 | 低 | 高（自增值连续） |
| innodb_autoinc_lock_mode=1（默认） | 简单INSERT用轻量锁，批量INSERT用表级锁 | 中 | 高 |
| innodb_autoinc_lock_mode=2 | 所有INSERT都用轻量锁，无表级锁 | 高 | 低（binlog statement格式不安全） |

## 行级锁（InnoDB核心）

行级锁是InnoDB的精华，只在**索引**上加锁。

### 记录锁（Record Lock）

**锁定索引上的一条记录**。

```sql
-- 通过唯一索引等值查询，命中记录
SELECT * FROM users WHERE id = 1 FOR UPDATE;
-- 加锁：id索引上id=1的Record Lock（X锁）
```

**特点**：
- 只锁住命中的一条记录
- 必须通过**索引**查询，否则退化为表锁

### 间隙锁（Gap Lock）

**锁定索引记录之间的间隙**，防止其他事务在间隙中插入新记录。

```sql
-- users表中id有：1, 5, 10
SELECT * FROM users WHERE id > 1 AND id < 5 FOR UPDATE;
-- 加锁：(1, 5) 间隙锁，阻止id=2,3,4的插入
```

**间隙锁的特点**：
- 间隙锁之间**不互斥**（多个事务可以同时持有同一间隙的Gap Lock）
- 间隙锁只**阻止插入**，不阻止读取
- 间隙锁只在**RR隔离级别**下生效（RC级别下关闭）
- 目的：**防止幻读**

**间隙的范围**：

```
索引记录：... 5, 10, 15, 20 ...

间隙为：
(-∞, 5), (5, 10), (10, 15), (15, 20), (20, +∞)

临键锁（Next-Key Lock）= 间隙锁 + 记录锁：
(-∞, 5], (5, 10], (10, 15], (15, 20], (20, +∞)
```

### 临键锁（Next-Key Lock）

**记录锁 + 间隙锁的组合**，是InnoDB行锁的**默认加锁方式**。

```sql
SELECT * FROM users WHERE id >= 10 AND id < 15 FOR UPDATE;
-- 加锁：
-- 1. Next-Key Lock (5, 10]  → 锁住id=10的记录和(5,10)的间隙
-- 2. Gap Lock (10, 15)      → 锁住(10,15)的间隙（因为15没有被锁住）
```

> 💡 **面试重点**：InnoDB的行锁实际上加在**索引**上，不是加在数据行上。如果没有用到索引，行锁会退化为表锁！

## InnoDB加锁规则详解

InnoDB的加锁规则（基于丁奇总结，面试必背）：

**规则1**：加锁的基本单位是**Next-Key Lock**

**规则2**：查找过程中**访问到的对象**才会加锁

**规则3**：等值查询中，唯一索引命中记录时，Next-Key Lock退化为**Record Lock**

**规则4**：等值查询中，最后一个不满足条件的值，Next-Key Lock退化为**Gap Lock**

**规则5**：范围查询中，会对扫描到的范围加Next-Key Lock

### 加锁示例

**示例1：唯一索引等值查询，命中记录**

```sql
-- 表users，id为主键，有记录：5, 10, 15, 20
SELECT * FROM users WHERE id = 10 FOR UPDATE;
-- 加锁：Record Lock on id=10
-- （规则3：唯一索引等值命中，退化为Record Lock）
```

**示例2：唯一索引等值查询，未命中记录**

```sql
SELECT * FROM users WHERE id = 12 FOR UPDATE;
-- 加锁：Gap Lock on (10, 15)
-- （规则4：等值查询未命中，退化为Gap Lock）
```

**示例3：普通索引等值查询**

```sql
-- 表users，age上有普通索引，有记录：age=10(id=5), age=20(id=10), age=20(id=15), age=30(id=20)
SELECT * FROM users WHERE age = 20 FOR UPDATE;
-- 加锁：
-- 1. age索引上：Next-Key Lock (10, 20] + Gap Lock (20, 30)
-- 2. 主键索引上：Record Lock on id=10, id=15
```

**示例4：范围查询**

```sql
SELECT * FROM users WHERE id >= 10 AND id < 15 FOR UPDATE;
-- 加锁：
-- 1. Next-Key Lock (5, 10]  → id=10命中
-- 2. Next-Key Lock (10, 15] → id=15命中（15 < 15为false，但范围扫描会扫到15）
```

> ⚠️ **注意**：范围查询中，即使边界值不满足条件，也可能被锁住！

### 无索引时的加锁

```sql
-- age字段没有索引
SELECT * FROM users WHERE age = 20 FOR UPDATE;
-- 结果：所有行和所有间隙都被锁住 → 等同于表锁！
```

**原因**：没有索引时，InnoDB只能做全表扫描，每一条记录都会被访问到，都会加锁。

> 💡 **面试关键**：一定要在查询条件上建索引！否则行锁变表锁，并发性能暴跌。

## 锁的查看

### 查看当前锁

```sql
-- MySQL 8.0+
SELECT * FROM performance_schema.data_locks;  -- 查看当前锁
SELECT * FROM performance_schema.data_lock_waits;  -- 查看锁等待

-- MySQL 5.7
SELECT * FROM information_schema.INNODB_LOCKS;
SELECT * FROM information_schema.INNODB_LOCK_WAITS;
```

### 查看锁等待超时

```sql
-- 查看当前锁等待超时时间（默认50秒）
SHOW VARIABLES LIKE 'innodb_lock_wait_timeout';

-- 设置锁等待超时
SET innodb_lock_wait_timeout = 10;
```

### 查看死锁日志

```sql
-- 查看最近一次死锁信息
SHOW ENGINE INNODB STATUS;
```

## 死锁

### 什么是死锁

两个或多个事务互相等待对方持有的锁，导致都无法继续执行。

```
事务A                      事务B
LOCK X on row1             LOCK X on row2
等待LOCK X on row2 ←→      等待LOCK X on row1
         ↓
       死锁！
```

### 死锁检测

InnoDB默认开启死锁检测（`innodb_deadlock_detect=ON`）：

1. 检测到死锁后，自动回滚**代价较小**的事务
2. 返回错误：`ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction`

### 死锁示例

```sql
-- 事务A
BEGIN;
UPDATE account SET balance = balance - 100 WHERE id = 1;  -- 锁住id=1
-- 此时事务B...
UPDATE account SET balance = balance + 100 WHERE id = 2;  -- 等待id=2的锁...

-- 事务B
BEGIN;
UPDATE account SET balance = balance - 200 WHERE id = 2;  -- 锁住id=2
-- 此时事务A...
UPDATE account SET balance = balance + 200 WHERE id = 1;  -- 等待id=1的锁... 死锁！
```

### 死锁的预防

| 策略 | 说明 |
|------|------|
| 按固定顺序访问表和行 | 最有效，所有事务按同一顺序加锁 |
| 保持事务简短 | 减少锁持有时间 |
| 使用低隔离级别 | RC比RR锁更少（没有间隙锁） |
| 合理使用索引 | 避免行锁退化为表锁 |
| 设置锁等待超时 | `innodb_lock_wait_timeout` |

### 死锁的处理

```sql
-- 1. 查看死锁日志
SHOW ENGINE INNODB STATUS;

-- 2. 手动杀掉阻塞的事务
KILL <thread_id>;

-- 3. 查看当前事务
SELECT * FROM information_schema.INNODB_TRX;
```

## 锁与MVCC的协作

### 快照读不加锁

普通SELECT通过MVCC读取历史版本，不需要加任何锁：

```sql
-- RR级别下的普通SELECT
SELECT * FROM users WHERE id = 1;  -- 不加锁，读快照
```

### 当前读加锁

加锁的SELECT和写操作需要读最新数据并加锁：

```sql
-- 当前读（加锁读）
SELECT * FROM users WHERE id = 1 FOR UPDATE;  -- 加X锁
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;  -- 加S锁（MySQL 8.0: FOR SHARE）

-- 写操作
UPDATE users SET name = 'new' WHERE id = 1;  -- 加X锁
DELETE FROM users WHERE id = 1;  -- 加X锁
INSERT INTO users VALUES(...);  -- 加插入意向锁
```

### 插入意向锁

**插入意向锁**是一种特殊的Gap Lock，在INSERT操作时使用。

- 插入前，先检查插入位置是否有Gap Lock
- 如果没有阻塞的Gap Lock，加插入意向锁（不冲突）
- 如果有阻塞的Gap Lock，等待

**特点**：多个事务在同一间隙的不同位置插入，互不冲突。

```
间隙(5, 10)：
  事务A插入id=6 → 加插入意向锁
  事务B插入id=8 → 加插入意向锁
  → 不冲突，可以并发插入 ✅

  事务C执行了 SELECT ... WHERE id > 5 AND id < 10 FOR UPDATE → 加Gap Lock (5, 10)
  事务A插入id=6 → 被事务C的Gap Lock阻塞 ❌
```

## RC vs RR锁的差异

| 差异 | RC（读已提交） | RR（可重复读） |
|------|----------------|----------------|
| 间隙锁 | ❌ 不使用 | ✅ 使用 |
| 临键锁 | ❌ 不使用 | ✅ 使用 |
| 加锁范围 | 只锁命中记录 | 锁记录+间隙 |
| 幻读防护 | ❌ | ✅（部分） |
| 死锁概率 | 低 | 相对高 |
| 并发度 | 高 | 相对低 |

## 常见面试题

### Q1: 为什么InnoDB选择RC隔离级别时没有间隙锁？

RC级别下，每次SELECT都创建新的Read View，可以读到其他事务已提交的最新数据，所以不需要防止幻读（因为本来就不保证可重复读），也就不需要间隙锁。

### Q2: 行锁一定比表锁好吗？

不一定。
- **高并发且只操作少量行**：行锁更好（锁粒度小，并发高）
- **全表操作（如批量更新）**：表锁更好（行锁开销大，可能死锁）
- InnoDB的行锁是通过索引实现的，**没有索引时行锁退化为表锁**

### Q3: 乐观锁和悲观锁的区别？

| 对比 | 悲观锁 | 乐观锁 |
|------|--------|--------|
| 思想 | 假设一定冲突，先加锁 | 假设不冲突，提交时检查 |
| 实现 | SELECT FOR UPDATE | 版本号/CAS |
| 适用 | 写多读少 | 读多写少 |
| 性能 | 低（锁等待） | 高（无锁等待） |
| 缺点 | 死锁、锁等待 | 冲突时重试成本高 |

**乐观锁实现示例**：
```sql
-- 通过版本号实现乐观锁
UPDATE products SET stock = stock - 1, version = version + 1 
WHERE id = 1 AND version = 5;  -- version不匹配则更新失败
```

### Q4: 如何分析和解决线上锁等待问题？

```sql
-- 1. 查看当前锁等待
SELECT * FROM performance_schema.data_lock_waits;

-- 2. 查看阻塞的事务
SELECT trx_id, trx_state, trx_started, trx_query 
FROM information_schema.INNODB_TRX 
ORDER BY trx_started;

-- 3. 杀掉阻塞的事务
KILL <thread_id>;

-- 4. 查看死锁日志
SHOW ENGINE INNODB STATUS;
```

**常见解决方案**：
1. 添加合适的索引（避免行锁变表锁）
2. 缩小事务范围
3. 按固定顺序访问资源
4. 调整隔离级别（RR → RC）
5. 设置合理的锁等待超时

## 总结

本文深入讲解了MySQL/InnoDB的锁机制：

1. **锁分类**：全局锁、表级锁（表锁、MDL、意向锁、自增锁）、行级锁（记录锁、间隙锁、临键锁）
2. **意向锁**：快速判断表中是否有行锁，意向锁之间互不冲突
3. **行锁加锁规则**：Next-Key Lock + 五条退化规则
4. **死锁**：检测、预防、处理
5. **锁与MVCC**：快照读不加锁，当前读加锁，插入意向锁
6. **RC vs RR**：RC没有间隙锁，并发更高；RR有间隙锁，防幻读

下期预告：
- 数据库面试八股文（六）——MySQL日志系统与主从复制
- 数据库面试八股文（七）——Redis核心数据结构与应用场景
