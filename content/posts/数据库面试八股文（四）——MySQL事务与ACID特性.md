---
title: "数据库面试八股文（四）——MySQL事务与ACID特性"
date: 2026-06-02T22:00:00+08:00
draft: false
categories: ["数据库"]
tags: ["面试", "八股文", "MySQL", "事务", "ACID", "隔离级别", "MVCC"]
---

# 数据库面试八股文（四）——MySQL事务与ACID特性

## 概述

事务（Transaction）是数据库最核心的概念之一，也是面试中出现频率最高的考点。上一篇文章我们了解了MySQL的架构和存储引擎，本文将深入讲解**事务的ACID特性、隔离级别、实现原理**，以及InnoDB如何通过**MVCC**实现高并发下的读写不阻塞。

## 什么是事务

**事务（Transaction）** 是一组数据库操作的逻辑单元，这组操作要么全部成功，要么全部失败。

```sql
-- 典型的事务场景：银行转账
START TRANSACTION;
    UPDATE account SET balance = balance - 1000 WHERE id = 1;  -- A扣钱
    UPDATE account SET balance = balance + 1000 WHERE id = 2;  -- B加钱
COMMIT;

-- 如果中间任何一步失败
ROLLBACK;
```

**事务的生命周期**：
```
START TRANSACTION / BEGIN
    → SQL1
    → SQL2
    → SQL3
    → COMMIT（提交）或 ROLLBACK（回滚）
```

> 💡 **注意**：DDL语句（CREATE、ALTER、DROP）会隐式提交事务，无法回滚。

## ACID特性详解

ACID是事务的四大特性，面试必考！

### 原子性（Atomicity）

**定义**：事务中的所有操作要么全部执行成功，要么全部不执行，不存在部分执行的状态。

**实现原理**：**undo log（回滚日志）**

```
事务执行过程：
INSERT → undo log记录DELETE操作
UPDATE → undo log记录反向UPDATE（旧值）
DELETE → undo log记录INSERT操作

回滚时：
按undo log的逆序执行，恢复到事务开始前的状态
```

**面试追问**：如果事务执行到一半MySQL崩溃了怎么办？
→ 重启时，未提交的事务通过undo log回滚，保证原子性。

### 一致性（Consistency）

**定义**：事务执行前后，数据库从一个一致性状态转换到另一个一致性状态。

**理解**：一致性是ACID的**最终目标**，原子性、隔离性、持久性都是为了保证一致性。

**示例**：
```
转账前：A有2000，B有3000，总计5000（一致性状态）
转账后：A有1000，B有4000，总计5000（一致性状态）
如果A扣了钱但B没加钱：A有1000，B有3000，总计4000（不一致状态）→ 违反一致性
```

**一致性的保障**：
- 原子性 → 保证事务不会部分执行
- 隔离性 → 保证并发事务不会互相干扰
- 持久性 → 保证已提交的数据不会丢失
- 业务约束 → 主键、外键、唯一约束、CHECK约束

### 隔离性（Isolation）

**定义**：并发执行的多个事务之间互不干扰，一个事务的中间状态对其他事务不可见。

**实现原理**：**锁 + MVCC**

隔离性是最复杂的特性，后续"隔离级别"和"MVCC"章节会详细讲解。

### 持久性（Durability）

**定义**：事务一旦提交，对数据的修改就是永久的，即使系统崩溃也不会丢失。

**实现原理**：**redo log（重做日志）**

```
事务提交时：
1. 将修改记录写入redo log buffer
2. 根据innodb_flush_log_at_trx_commit配置刷盘
3. 返回提交成功

即使Buffer Pool中的脏页还没刷盘：
→ MySQL崩溃后，通过redo log恢复已提交的数据
```

**关键配置**：
```sql
-- 最安全（默认）：每次提交都刷盘
innodb_flush_log_at_trx_commit = 1

-- 折中：每次提交写OS缓存，每秒刷盘
innodb_flush_log_at_trx_commit = 2

-- 最快：后台每秒刷盘（可能丢失1秒数据）
innodb_flush_log_at_trx_commit = 0
```

> 💡 **面试常问**：为什么不直接写数据文件而要写redo log？
> → redo log是**顺序IO**（追加写入），数据文件是**随机IO**（需要定位页），顺序IO比随机IO快很多。

## 并发事务带来的问题

在没有隔离性的情况下，并发事务会导致以下问题：

### 脏读（Dirty Read）

**一个事务读到了另一个事务未提交的数据**。

```
时间线    事务A                        事务B
  T1      BEGIN;
  T2      UPDATE account SET balance = balance - 1000 WHERE id = 1;
  T3                                   BEGIN;
  T4                                   SELECT balance FROM account WHERE id = 1;  → 读到-1000后的值（脏数据）
  T5      ROLLBACK;  ← A回滚了，B读到的数据是无效的！
```

### 不可重复读（Non-Repeatable Read）

**一个事务内，两次读取同一行数据的结果不同**（被其他事务修改了）。

```
时间线    事务A                        事务B
  T1      BEGIN;
  T2      SELECT balance FROM account WHERE id = 1;  → 2000
  T3                                   BEGIN;
  T4                                   UPDATE account SET balance = 1000 WHERE id = 1;
  T5                                   COMMIT;
  T6      SELECT balance FROM account WHERE id = 1;  → 1000（两次读的结果不同！）
```

### 幻读（Phantom Read）

**一个事务内，两次执行相同的范围查询，结果集的行数不同**（被其他事务插入或删除了行）。

```
时间线    事务A                        事务B
  T1      BEGIN;
  T2      SELECT * FROM account WHERE balance > 1000;  → 5行
  T3                                   BEGIN;
  T4                                   INSERT INTO account VALUES(6, '新用户', 3000);
  T5                                   COMMIT;
  T6      SELECT * FROM account WHERE balance > 1000;  → 6行（多了一行"幻影"！）
```

### 三者的区别

| 问题 | 原因 | 影响 |
|------|------|------|
| 脏读 | 读到未提交的数据 | 数据可能是错误的 |
| 不可重复读 | 其他事务修改了数据 | 同一事务内前后读取不一致 |
| 幻读 | 其他事务插入/删除了行 | 同一事务内范围查询结果不同 |

> 💡 **记忆技巧**：脏读→读未提交，不可重复读→读已提交但被改，幻读→读已提交但被增删。问题严重程度递减：脏读 > 不可重复读 > 幻读。

## 四大隔离级别

SQL标准定义了四个隔离级别，从低到高：

| 隔离级别 | 脏读 | 不可重复读 | 幻读 | 性能 |
|----------|------|------------|------|------|
| 读未提交（Read Uncommitted） | ❌ 可能 | ❌ 可能 | ❌ 可能 | 最高 |
| 读已提交（Read Committed, RC） | ✅ 避免 | ❌ 可能 | ❌ 可能 | 高 |
| 可重复读（Repeatable Read, RR） | ✅ 避免 | ✅ 避免 | ❌ 可能* | 中 |
| 串行化（Serializable） | ✅ 避免 | ✅ 避免 | ✅ 避免 | 最低 |

*注：InnoDB的RR级别通过**间隙锁（Gap Lock）+ MVCC**在一定程度上避免了幻读。

### 查看和设置隔离级别

```sql
-- 查看全局隔离级别
SELECT @@global.transaction_isolation;

-- 查看当前会话隔离级别
SELECT @@transaction_isolation;

-- 设置隔离级别
SET GLOBAL TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;
```

### 读未提交（Read Uncommitted）

最低的隔离级别，一个事务可以读到另一个事务未提交的数据。

- 实现方式：不加任何锁，直接读最新数据
- 实际项目中**几乎不使用**

### 读已提交（Read Committed, RC）

一个事务只能读到另一个事务**已提交**的数据。

**实现方式：MVCC + 临时读视图**

- 每次SELECT都会创建一个新的Read View
- 所以同一事务内，两次SELECT可能读到不同的数据（不可重复读）

```
RC级别下的Read View生成时机：
SELECT 1 → 创建Read View 1 → 读到某版本
（其他事务提交了修改）
SELECT 2 → 创建Read View 2 → 读到新版本
```

**Oracle和PostgreSQL的默认隔离级别**。

### 可重复读（Repeatable Read, RR）

**MySQL的默认隔离级别**。一个事务内，多次读取同一数据结果相同。

**实现方式：MVCC + 第一次SELECT时创建Read View**

- 事务内第一次SELECT时创建Read View，后续SELECT复用同一个
- 因此同一事务内，多次读取的结果一致

```
RR级别下的Read View生成时机：
BEGIN;
SELECT 1 → 创建Read View（整个事务共用）
（其他事务提交了修改）
SELECT 2 → 复用同一个Read View → 读到的还是旧版本
```

**InnoDB如何在一定程度上避免幻读**：
1. **快照读**（普通SELECT）：通过MVCC的Read View，始终读到事务开始时的快照
2. **当前读**（SELECT ... FOR UPDATE / INSERT / UPDATE / DELETE）：通过**间隙锁（Gap Lock）** 阻止其他事务在范围内插入新行

> ⚠️ **注意**：RR级别下，先快照读后当前读，仍可能出现幻读！因为当前读读的是最新数据，不是快照。

### 串行化（Serializable）

最高的隔离级别，所有事务串行执行。

- 实现方式：所有SELECT自动加**共享锁**（LOCK IN SHARE MODE）
- 性能最差，实际项目中**几乎不使用**

## MVCC深度解析

**MVCC（Multi-Version Concurrency Control，多版本并发控制）** 是InnoDB实现高并发的核心机制，让**读不阻塞写，写不阻塞读**。

### 隐藏列

每行数据有两个隐藏列：

| 隐藏列 | 大小 | 说明 |
|--------|------|------|
| DB_TRX_ID | 6字节 | 最后修改该行的事务ID |
| DB_ROLL_PTR | 7字节 | 回滚指针，指向undo log中的上一个版本 |

### undo log版本链

每次修改数据时，旧版本存入undo log，通过DB_ROLL_PTR形成版本链：

```
当前行：{id=1, name='王五', DB_TRX_ID=300, DB_ROLL_PTR→undo2}

undo2：{id=1, name='李四', DB_TRX_ID=200, DB_ROLL_PTR→undo1}

undo1：{id=1, name='张三', DB_TRX_ID=100, DB_ROLL_PTR→NULL}
```

### Read View

Read View是事务在进行**快照读**时创建的"可见性判断规则"。

**Read View的四个核心字段**：

| 字段 | 说明 |
|------|------|
| m_ids | 创建Read View时，当前所有活跃（未提交）事务的ID列表 |
| min_trx_id | m_ids中的最小值 |
| max_trx_id | 创建Read View时系统应该分配给下一个事务的ID |
| creator_trx_id | 创建该Read View的事务ID |

**可见性判断规则**：

```
对于版本链中的某个版本（其DB_TRX_ID = trx_id）：

1. trx_id == creator_trx_id → 可见（自己修改的）
2. trx_id < min_trx_id → 可见（在Read View创建前已提交）
3. trx_id >= max_trx_id → 不可见（在Read View创建后才开始的事务）
4. min_trx_id <= trx_id < max_trx_id：
   - 如果trx_id在m_ids中 → 不可见（事务还未提交）
   - 如果trx_id不在m_ids中 → 可见（事务已提交）
5. 如果不可见，沿DB_ROLL_PTR找上一个版本，重复判断
```

### RC和RR的区别

| 隔离级别 | Read View生成时机 | 效果 |
|----------|-------------------|------|
| RC | 每次SELECT都生成新的 | 能看到其他事务已提交的最新数据 |
| RR | 事务内第一次SELECT时生成 | 始终看到事务开始时的快照 |

### MVCC完整示例

```
假设事务ID递增：100, 200, 300...

初始数据：
  {id=1, balance=1000, DB_TRX_ID=100, DB_ROLL_PTR=NULL}

T1: 事务A (trx_id=200) BEGIN
T2: 事务B (trx_id=300) BEGIN
T3: 事务B UPDATE account SET balance=500 WHERE id=1
    → 当前行：{balance=500, DB_TRX_ID=300, DB_ROLL_PTR→undo}
    → undo：{balance=1000, DB_TRX_ID=100, DB_ROLL_PTR=NULL}
T4: 事务A SELECT balance FROM account WHERE id=1

  RR级别：事务A创建Read View
    m_ids = [200, 300]（A和B都未提交）
    min_trx_id = 200
    max_trx_id = 301

  判断当前行（DB_TRX_ID=300）：
    300在m_ids中 → 不可见
  沿ROLL_PTR找到undo版本（DB_TRX_ID=100）：
    100 < min_trx_id(200) → 可见！
  
  → 事务A读到 balance=1000 ✅

T5: 事务B COMMIT
T6: 事务A 再次 SELECT balance FROM account WHERE id=1

  RR级别：复用同一个Read View
  → 还是读到 balance=1000 ✅（可重复读）

  RC级别：创建新的Read View
    m_ids = [200]（B已提交，只有A活跃）
  判断当前行（DB_TRX_ID=300）：
    300不在m_ids中 → 可见！
  → 事务A读到 balance=500 ✅（不可重复读，但避免了脏读）
```

## 当前读 vs 快照读

| 类型 | SQL | 说明 |
|------|-----|------|
| 快照读 | 普通SELECT | 读MVCC快照，不加锁 |
| 当前读 | SELECT ... FOR UPDATE | 读最新数据，加X锁 |
| 当前读 | SELECT ... LOCK IN SHARE MODE | 读最新数据，加S锁 |
| 当前读 | INSERT / UPDATE / DELETE | 操作最新数据，加锁 |

**当前读为什么不使用MVCC**：
- 修改数据必须基于最新版本，否则会覆盖其他事务的修改
- 通过加锁保证当前读的正确性

## 事务的传播行为（Spring）

在Spring框架中，事务还有传播行为的概念（面试常问）：

| 传播行为 | 说明 |
|----------|------|
| REQUIRED（默认） | 有事务就加入，没有就新建 |
| REQUIRES_NEW | 总是新建事务，挂起当前事务 |
| NESTED | 嵌套事务（保存点），外层回滚内层也回滚 |
| SUPPORTS | 有事务就加入，没有就非事务执行 |
| NOT_SUPPORTED | 总是非事务执行，挂起当前事务 |
| MANDATORY | 必须在事务中，否则抛异常 |
| NEVER | 必须不在事务中，否则抛异常 |

```java
@Service
public class OrderService {
    
    @Transactional(propagation = Propagation.REQUIRED)
    public void createOrder() {
        // 主事务
        orderMapper.insert(order);
        pointService.addPoints();  // 加入当前事务
    }
    
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void addPoints() {
        // 新事务：即使主事务回滚，积分也不回滚
        pointMapper.insert(point);
    }
}
```

## 常见面试题

### Q1: MySQL的RR级别能完全避免幻读吗？

**不能完全避免**。以下场景仍会出现幻读：

```sql
-- 事务A
BEGIN;
SELECT * FROM users WHERE age > 20;  -- 快照读，读到3行
-- 事务B在此插入了一条age=25的记录并提交
UPDATE users SET name = 'new' WHERE age > 20;  -- 当前读，更新了4行！
SELECT * FROM users WHERE age > 20;  -- 现在能看到4行（包括自己更新的）
COMMIT;
```

原因：UPDATE是当前读，会读取最新数据并加锁，导致事务A"看到"了新插入的行。

### Q2: 为什么MySQL默认用RR而不是RC？

1. **数据一致性**：RR保证同一事务内读取一致，更安全
2. **binlog格式**：RR配合binlog_format=ROW是安全的；RC必须用ROW格式
3. **主从复制**：RC级别下statement格式的binlog可能导致主从不一致

### Q3: 事务太大有什么问题？

1. **undo log膨胀**：大量修改产生大量undo log
2. **锁持有时间长**：阻塞其他事务
3. **Buffer Pool压力**：脏页积累
4. **长事务增加崩溃恢复时间**

```sql
-- 查看长事务
SELECT * FROM information_schema.INNODB_TRX 
WHERE TIME_TO_SEC(TIMEDIFF(NOW(), trx_started)) > 60;
```

### Q4: 分布式事务如何保证ACID？

分布式事务通常无法严格保证ACID，而是追求**最终一致性**：

- **2PC（两阶段提交）**：协调者→参与者，强一致性但性能差
- **3PC（三阶段提交）**：增加CanCommit阶段，减少阻塞
- **TCC（Try-Confirm-Cancel）**：业务层面的补偿事务
- **Saga模式**：长事务拆分为多个本地事务，失败时执行补偿操作
- **Seata**：阿里开源的分布式事务框架

## 总结

本文深入讲解了MySQL事务与ACID特性：

1. **ACID特性**：原子性（undo log）、一致性（目标）、隔离性（锁+MVCC）、持久性（redo log）
2. **并发问题**：脏读 → 不可重复读 → 幻读（严重程度递减）
3. **隔离级别**：读未提交 → 读已提交 → 可重复读 → 串行化（隔离强度递增，性能递减）
4. **MVCC**：隐藏列 + undo log版本链 + Read View，实现读写不阻塞
5. **RC vs RR**：Read View生成时机不同，导致可见性不同
6. **当前读 vs 快照读**：普通SELECT是快照读，加锁SELECT/写操作是当前读

下期预告：
- 数据库面试八股文（五）——MySQL锁机制（行锁、表锁、间隙锁、MVCC）
- 数据库面试八股文（六）——MySQL日志系统与主从复制
