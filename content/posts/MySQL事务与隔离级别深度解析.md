---
title: MySQL 事务与隔离级别深度解析
date: 2026-05-12 17:25:00+08:00
updated: '2026-05-12T17:25:00+08:00'
description: 面试高频问题：MySQL 的事务隔离级别有哪些？脏读、不可重复读、幻读是什么？InnoDB 如何解决幻读？ 事务是数据库的核心特性之一，用于保证数据的一致性和完整性。MySQL 通过事务隔离级别来平衡并发性能和数据一致性，不同的隔离级别会出现不同的问题，需要根据业务场景选择。
  事务（Transact。
topic: database-middleware
level: intermediate
status: maintained
tags:
- MySQL
- transaction
- acid
- mvcc
- isolation-level
categories:
- 数据库与中间件
draft: false
---

> 面试高频问题：MySQL 的事务隔离级别有哪些？脏读、不可重复读、幻读是什么？InnoDB 如何解决幻读？

## 引言

事务是数据库的核心特性之一，用于保证数据的一致性和完整性。MySQL 通过事务隔离级别来平衡并发性能和数据一致性，不同的隔离级别会出现不同的问题，需要根据业务场景选择。

## 一、事务基础

### 1.1 什么是事务？

事务（Transaction）是数据库操作的基本单位，一个事务包含一组 SQL 语句，这些语句要么全部成功，要么全部失败。

```sql
-- 转账场景：从小明账户转 100 元到小红账户
BEGIN;  -- 开启事务

UPDATE accounts SET balance = balance - 100 WHERE name = '小明';
UPDATE accounts SET balance = balance + 100 WHERE name = '小红';

COMMIT;  -- 提交事务
```

### 1.2 事务的 ACID 特性

```
事务特性
├── Atomic（原子性）：事务是最小执行单位，不可分割
├── Consistency（一致性）：事务执行前后，数据保持一致
├── Isolation（隔离性）：并发事务相互隔离，互不干扰
└── Durability（持久性）：事务提交后，结果永久保存
```

**原子性**：事务中的操作要么全部成功，要么全部失败回滚。

```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE name = '小明';
-- 如果这里出错，前面的操作会回滚
UPDATE accounts SET balance = balance + 100 WHERE name = '小红';
COMMIT;
```

**一致性**：事务执行前后，数据库状态保持一致。

```sql
-- 转账前后，总金额不变
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE name = '小明';  -- 1000 → 900
UPDATE accounts SET balance = balance + 100 WHERE name = '小红';  -- 500 → 600
COMMIT;
-- 总金额：900 + 600 = 1500（与事务前一致）
```

**隔离性**：并发事务之间相互隔离，不互相干扰。

**持久性**：事务提交后，即使系统崩溃，数据也不会丢失。

### 1.3 事务控制语句

```sql
-- 开启事务
BEGIN;  -- 或 START TRANSACTION;

-- 提交事务
COMMIT;

-- 回滚事务
ROLLBACK;

-- 保存点（部分回滚）
SAVEPOINT savepoint_name;

-- 回滚到保存点
ROLLBACK TO SAVEPOINT savepoint_name;

-- 释放保存点
RELEASE SAVEPOINT savepoint_name;

-- 设置事务自动提交（MySQL 默认开启）
SET autocommit = 0;  -- 关闭自动提交
SET autocommit = 1;  -- 开启自动提交
```

## 二、并发问题

### 2.1 三大并发问题

```
并发事务问题
├── 脏读（Dirty Read）：读取到未提交的数据
├── 不可重复读（Non-repeatable Read）：同一事务中，两次读取结果不同
└── 幻读（Phantom Read）：同一事务中，两次查询结果集不同（多了或少了行）
```

### 2.2 脏读

**场景**：事务 A 读取了事务 B 未提交的数据

```sql
-- 事务 A
BEGIN;
SELECT balance FROM accounts WHERE name = '小明';  -- 读取到 900（事务 B 未提交）
-- 事务 B 回滚了...

-- 事务 B
BEGIN;
UPDATE accounts SET balance = 900 WHERE name = '小明';  -- 余额从 1000 改为 900
-- 还没提交...
ROLLBACK;  -- 回滚，余额恢复到 1000
```

**问题**：事务 A 读取了"脏"数据（未提交的修改），如果事务 B 回滚，事务 A 的操作就是基于错误的数据。

### 2.3 不可重复读

**场景**：同一事务中，两次读取同一行数据，结果不同

```sql
-- 事务 A
BEGIN;
SELECT balance FROM accounts WHERE name = '小明';  -- 第一次读取：1000

-- 事务 B（此时发生）
BEGIN;
UPDATE accounts SET balance = 900 WHERE name = '小明';
COMMIT;  -- 提交修改

SELECT balance FROM accounts WHERE name = '小明';  -- 第二次读取：900
COMMIT;
```

**问题**：同一事务中，相同的查询返回不同结果，因为其他事务修改了数据并提交。

### 2.4 幻读

**场景**：同一事务中，两次查询结果集不同（像出现"幻影"一样）

```sql
-- 事务 A
BEGIN;
SELECT * FROM accounts WHERE id > 0;  -- 第一次查询：5 行

-- 事务 B（此时发生）
BEGIN;
INSERT INTO accounts VALUES (6, '小华', 1000);
COMMIT;  -- 插入新行并提交

SELECT * FROM accounts WHERE id > 0;  -- 第二次查询：6 行（多了"幻影"行）
COMMIT;
```

**问题**：同一事务中，相同的查询条件，结果集行数不同，好像出现了"幻影"行。

**不可重复读 vs 幻读的区别**：
- **不可重复读**：同一行数据被修改或删除
- **幻读**：结果集多了或少了行（INSERT 或 DELETE）

## 三、事务隔离级别

### 3.1 四种隔离级别

MySQL 定义了 4 种事务隔离级别：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 说明 |
|---------|------|-----------|------|------|
| READ UNCOMMITTED（读未提交） | ✅ 可能 | ✅ 可能 | ✅ 可能 | 最低隔离级别，性能最高 |
| READ COMMITTED（读已提交） | ❌ 不可能 | ✅ 可能 | ✅ 可能 | Oracle 默认 |
| REPEATABLE READ（可重复读） | ❌ 不可能 | ❌ 不可能 | ✅ 可能 | MySQL 默认 |
| SERIALIZABLE（串行化） | ❌ 不可能 | ❌ 不可能 | ❌ 不可能 | 最高隔离级别，性能最低 |

```
隔离级别越高，数据越安全，但性能越差
隔离级别越低，并发性能越好，但可能出现并发问题

READ UNCOMMITTED < READ COMMITTED < REPEATABLE READ < SERIALIZABLE
     ↑ 低 ──────────────────────────────────────────── 高 ↑
     ← ─────────────────── 性能 ────────────────────── →
```

### 3.2 设置隔离级别

```sql
-- 查看当前会话隔离级别
SELECT @@transaction_isolation;

-- 查看全局隔离级别
SELECT @@global.transaction_isolation;

-- 设置当前会话隔离级别
SET session transaction isolation level READ COMMITTED;

-- 设置全局隔离级别
SET global transaction isolation level READ COMMITTED;

-- 开启事务时指定
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
START TRANSACTION;
```

### 3.3 各隔离级别详解

**READ UNCOMMITTED（读未提交）**：
- 允许读取其他事务未提交的数据
- 脏读、不可重复读、幻读都可能发生
- 几乎不加锁，性能最好
- 适合对数据一致性要求极低的场景

**READ COMMITTED（读已提交）**：
- 只能读取其他事务已提交的数据
- 解决脏读问题
- 不可重复读、幻读可能发生
- 每次 SELECT 生成新的 Read View

**REPEATABLE READ（可重复读）**：
- MySQL InnoDB 默认隔离级别
- 同一事务中，多次读取同一数据结果相同
- 解决脏读、不可重复读问题
- InnoDB 通过 MVCC + Next-Key Lock 解决幻读

**SERIALIZABLE（串行化）**：
- 所有事务串行执行
- 完全避免并发问题
- 性能最差
- 实际很少使用

## 四、MVCC 机制

### 4.1 什么是 MVCC？

MVCC（Multi-Version Concurrency Control，多版本并发控制）是一种并发控制机制，通过保存数据的多个版本，实现读写并发，提高数据库性能。

**核心思想**：
- 每次修改数据时，不直接覆盖旧数据
- 创建新版本，旧版本保留
- 读写操作互不阻塞

### 4.2 InnoDB 的 MVCC 实现

InnoDB 在每行数据上添加两个隐藏列：

```sql
-- 实际的表结构（简化）
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(20),
    balance DECIMAL(10,2),
    -- 隐藏列
    DB_TRX_ID,  -- 最近修改的事务 ID
    DB_ROLL_PTR,  -- 回滚指针，指向 undo log
    DELETE_BIT  -- 删除标志
);
```

**版本链**：
```
事务 A 修改数据
        │
        ▼
┌─────────────────────────────────────────────┐
│ undo log                                     │
│  ┌─────────────────────────────────────┐    │
│  │ trx_id=1, balance=1000 (旧版本)    │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
        │ DB_ROLL_PTR 指向
        ▼
┌─────────────────────────────────────────────┐
│ 当前数据（最新版本）                         │
│ id=1, name=小明, balance=900, trx_id=2      │
└─────────────────────────────────────────────┘
```

### 4.3 Read View

Read View（读视图）是快照的核心，用于判断当前事务能看到哪些版本的数据。

```sql
-- Read View 结构
struct ReadView {
    m_ids;           //活跃事务 ID 列表
    min_trx_id;       //最小活跃事务 ID
    max_trx_id;       //创建 Read View 时最大事务 ID + 1
    creator_trx_id;   //当前事务 ID
}
```

**可见性判断规则**：
```
1. trx_id == creator_trx_id → 可见（自己的修改）
2. trx_id < min_trx_id → 可见（已提交事务）
3. trx_id >= max_trx_id → 不可见（Read View 创建后启动的事务）
4. trx_id in m_ids → 不可见（活跃事务的修改）
```

### 4.4 READ COMMITTED vs REPEATABLE READ

**READ COMMITTED**：每次 SELECT 都生成新的 Read View

```sql
-- 事务 A（READ COMMITTED）
BEGIN;
SELECT balance FROM users WHERE id = 1;  -- Read View 1：trx_id=2 已提交，可见 balance=900

-- 事务 B
BEGIN;
UPDATE users SET balance = 800 WHERE id = 1;
COMMIT;

SELECT balance FROM users WHERE id = 1;  -- Read View 2：trx_id=3 已提交，可见 balance=800
COMMIT;
```

**REPEATABLE READ**：同一事务中，使用同一个 Read View

```sql
-- 事务 A（REPEATABLE READ）
BEGIN;
SELECT balance FROM users WHERE id = 1;  -- Read View 1：trx_id=2 已提交，可见 balance=900

-- 事务 B
BEGIN;
UPDATE users SET balance = 800 WHERE id = 1;
COMMIT;

SELECT balance FROM users WHERE id = 1;  -- Read View 1：trx_id=3 已提交，但不在 Read View 可见范围内
                                        -- 仍可见 balance=900（读的是快照）
COMMIT;
```

## 五、InnoDB 锁机制

### 5.1 锁的分类

```
InnoDB 锁
├── 按操作：读锁（S 锁）、写锁（X 锁）
├── 按粒度：行锁、表锁
├── 按方式：记录锁、间隙锁、临键锁、意向锁
└── 按特性：共享锁、排他锁
```

### 5.2 共享锁与排他锁

```sql
-- 共享锁（S 锁）：读锁，其他事务可以读，不能写
SELECT * FROM users WHERE id = 1 LOCK IN SHARE MODE;

-- 排他锁（X 锁）：写锁，其他事务不能读也不能写
SELECT * FROM users WHERE id = 1 FOR UPDATE;
```

### 5.3 记录锁（Record Lock）

锁定索引记录，而非物理记录。

```sql
-- 锁定 id = 1 的记录
SELECT * FROM users WHERE id = 1 FOR UPDATE;
-- 其他事务不能修改 id = 1 的记录
```

### 5.4 间隙锁（Gap Lock）

锁定索引记录之间的间隙，防止幻读。

```sql
-- 锁定 id 在 (1, 10) 之间的间隙
SELECT * FROM users WHERE id BETWEEN 2 AND 9 FOR UPDATE;
-- 其他事务不能插入 id 在 (1, 10) 之间的记录
```

### 5.5 临键锁（Next-Key Lock）

临键锁 = 记录锁 + 间隙锁，是 InnoDB 在 REPEATABLE READ 下的默认加锁方式。

```sql
-- 锁定 id = 1 的记录，以及 (1, 下一个记录) 的间隙
SELECT * FROM users WHERE id >= 1 FOR UPDATE;
-- 锁定：id=1 的记录 + (1, +∞) 的间隙
```

### 5.6 意向锁（Intention Lock）

表级锁，表示事务有意向对表中的某行加锁。

```sql
-- 意向共享锁（IS）：事务有意向对表加 S 锁
LOCK IN SHARE MODE;  -- 自动加 IS

-- 意向排他锁（IX）：事务有意向对表加 X 锁
FOR UPDATE;  -- 自动加 IX
```

### 5.7 InnoDB 如何解决幻读？

**MVCC + Next-Key Lock**：

1. **快照读**（普通 SELECT）：使用 MVCC，避免脏读和不可重复读
2. **当前读**（SELECT ... FOR UPDATE/LOCK IN SHARE MODE、INSERT/UPDATE/DELETE）：使用 Next-Key Lock，防止幻读

```sql
-- 事务 A（REPEATABLE READ）
BEGIN;

-- 快照读：MVCC 保证可重复
SELECT * FROM users WHERE id > 0;  -- 读取的是 Read View

-- 当前读：Next-Key Lock 防止幻读
SELECT * FROM users WHERE id > 0 FOR UPDATE;  -- 锁定 id > 0 的所有记录和间隙
-- 此时其他事务无法插入 id > 0 的记录
COMMIT;
```

## 六、事务隔离级别实践

### 6.1 设置隔离级别

```sql
-- MySQL 配置文件中设置
[mysqld]
transaction-isolation = REPEATABLE-READ
```

### 6.2 隔离级别与锁的关系

```sql
-- READ COMMITTED：使用记录锁
-- 锁定 id = 1 的记录，不锁间隙

-- REPEATABLE READ：使用 Next-Key Lock
-- 锁定 id = 1 的记录 + (1, 下一个记录) 的间隙

-- SERIALIZABLE：所有 SELECT 自动加 LOCK IN SHARE MODE
```

### 6.3 死锁与处理

```sql
-- 事务 A
BEGIN;
UPDATE users SET balance = 900 WHERE id = 1;  -- 锁定 id=1
UPDATE users SET balance = 900 WHERE id = 2;  -- 等待 id=2

-- 事务 B（同时执行）
BEGIN;
UPDATE users SET balance = 900 WHERE id = 2;  -- 锁定 id=2
UPDATE users SET balance = 900 WHERE id = 1;  -- 等待 id=1
-- 死锁！

-- InnoDB 自动检测死锁，回滚代价最小的事务
-- ERROR 1213: Deadlock found when trying to get lock
```

**避免死锁**：
1. 按固定顺序访问数据
2. 减小事务范围
3. 使用低隔离级别
4. 添加合理索引，减少锁的范围

## 七、面试高频问题

### Q1：MySQL 有哪些事务隔离级别？

**答**：
1. READ UNCOMMITTED（读未提交）
2. READ COMMITTED（读已提交）
3. REPEATABLE READ（可重复读，MySQL 默认）
4. SERIALIZABLE（串行化）

### Q2：脏读、不可重复读、幻读的区别？

**答**：
- 脏读：读取到其他事务未提交的数据
- 不可重复读：同一事务中，两次读取同一行数据结果不同
- 幻读：同一事务中，两次查询结果集行数不同（多了或少了行）

### Q3：MVCC 是什么？如何实现？

**答**：多版本并发控制，通过版本链 + Read View 实现：
- 每行数据有 DB_TRX_ID 和 DB_ROLL_PTR
- 修改数据时创建 undo log，形成版本链
- Read View 判断哪些版本对当前事务可见

### Q4：REPEATABLE READ 如何解决幻读？

**答**：
- 快照读（普通 SELECT）：MVCC 保证不出现幻读
- 当前读（SELECT ... FOR UPDATE）：Next-Key Lock 锁住记录和间隙

### Q5：InnoDB 锁有哪些类型？

**答**：
- 共享锁（S 锁）和排他锁（X 锁）
- 记录锁、间隙锁、临键锁
- 意向锁（IS 锁、IX 锁）

### Q6：Next-Key Lock 是什么？

**答**：临键锁 = 记录锁 + 间隙锁，锁定一个范围，包括记录本身和前后间隙，防止幻读。

## 八、总结

**事务核心要点**：
- **ACID**：原子性、一致性、隔离性、持久性
- **隔离级别**：READ UNCOMMITTED < READ COMMITTED < REPEATABLE READ < SERIALIZABLE
- **MVCC**：多版本并发控制，通过版本链和 Read View 实现
- **InnoDB 锁**：记录锁、间隙锁、临键锁、意向锁

**隔离级别与问题**：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---------|------|-----------|------|
| 读未提交 | ✅ | ✅ | ✅ |
| 读已提交 | ❌ | ✅ | ✅ |
| 可重复读 | ❌ | ❌ | ✅（InnoDB 可解决）|
| 串行化 | ❌ | ❌ | ❌ |

**最佳实践**：
- MySQL 默认 REPEATABLE READ，适合大多数场景
- 高并发写场景考虑 READ COMMITTED
- 避免长事务，减少锁竞争
- 合理使用索引，减少锁范围

---

**本系列进度：22/30 篇 (73%)**

**下一篇预告**：MySQL 锁机制深入理解

**参考资料**：
- MySQL 官方文档：https://dev.mysql.com/doc/refman/8.0/en/
- 《高性能 MySQL》- Baron Schwartz
- 《MySQL 技术内幕：InnoDB 存储引擎》- 姜承尧
