---
title: "MySQL 日志系统深度解析"
date: 2026-05-12T17:35:00+08:00
draft: false
categories: ["mysql"]
tags: ["mysql", "binlog", "redo-log", "undo-log", "two-phase-commit"]
---


# MySQL 日志系统深度解析

> 面试高频问题：binlog、redo log、undo log 有什么区别？ MySQL 崩溃恢复流程？什么是两阶段提交？

## 引言

MySQL 的日志系统是数据库实现事务、崩溃恢复、数据复制的基础。主要包括 binlog（二进制日志）、redo log（重做日志）和 undo log（回滚日志）。理解这三种日志的原理和作用，是深入理解 MySQL 的关键。

## 一、三种日志概览

### 1.1 日志对比

| 日志 | 存储内容 | 作用 | 引擎 | 物理/逻辑 |
|------|---------|------|------|----------|
| binlog | 变更的 SQL 语句或数据 | 主从复制、数据恢复 | MySQL Server | 逻辑 |
| redo log | 物理页的变更 | 崩溃恢复、事务持久性 | InnoDB | 物理 |
| undo log | 修改前的数据 | MVCC、回滚事务 | InnoDB | 逻辑 |

### 1.2 日志位置

```
MySQL 架构
┌─────────────────────────────────────────────────┐
│ MySQL Server                                    │
│  ┌──────────────┐    ┌──────────────────────┐  │
│  │   binlog     │    │   连接层              │  │
│  │   (bin files)│    │   SQL 接口/解析器     │  │
│  └──────────────┘    └──────────────────────┘  │
└─────────────────────────────────────────────────┘
              │                        │
              ▼                        ▼
┌─────────────────────────────────────────────────┐
│ InnoDB 存储引擎                                  │
│  ┌──────────────────┐  ┌────────────────────┐   │
│  │    redo log      │  │    undo log       │   │
│  │  (ib_logfile)    │  │  (undo tablespace)│   │
│  └──────────────────┘  └────────────────────┘   │
│  ┌──────────────────┐                          │
│  │   数据页缓存     │  ←  →  磁盘数据文件     │
│  │   (Buffer Pool) │       (ibdata)           │
│  └──────────────────┘                          │
└─────────────────────────────────────────────────┘
```

## 二、redo log（重做日志）

### 2.1 为什么需要 redo log？

**问题**：事务提交后，数据必须持久化到磁盘。但磁盘 I/O 很慢，每次事务提交都写磁盘性能很差。

**解决方案**：Write-Ahead Logging（WAL，先写日志）

```
传统方式（慢）：
事务提交 → 写磁盘数据 → 返回成功
                ↓
           I/O 等待时间长

WAL 方式（快）：
事务提交 → 写 redo log（顺序 I/O，很快） → 返回成功
                    ↓
              后台异步刷盘
```

### 2.2 redo log 的结构

```sql
-- redo log 文件
ib_logfile0
ib_logfile1
-- 循环写入
```

**redo log 组成**：
```
redo log
├── LSN（Log Sequence Number）：日志序列号，递增唯一
├── checkpoint：检查点，表示此之前的数据已刷盘
├── 日志内容：物理页的变更
└── write pos：当前写入位置
```

### 2.3 redo log 写入机制

```
ib_logfile0              ib_logfile1
┌─────────────────┐      ┌─────────────────┐
│ write pos →     │ ← c  │                 │
│ [=========>     │  he  │                 │
│                 │  ck  │                 │
│                 │  po  │                 │
└─────────────────┘  s   └─────────────────┘

write pos：当前写入位置
checkpoint：检查点位置
当 write pos 追上 checkpoint 时，需要刷盘
```

**LSN 与 checkpoint**：
- LSN：日志序列号，每条日志递增
- checkpoint：表示 checkpoint 之前的数据都已刷盘
- 如果数据库崩溃，恢复时从 checkpoint 开始

### 2.4 redo log 写入流程

```sql
BEGIN;
UPDATE users SET balance = 900 WHERE id = 1;
COMMIT;
```

```
1. 事务开始
2. 修改 Buffer Pool 中的数据页
3. 生成 redo log entry（包含数据页的变更）
4. 将 redo log 写入 redo log buffer
5. commit 时，将 redo log buffer 刷盘（fsync）
6. 返回客户端"提交成功"
```

### 2.5 redo log 配置

```sql
-- 查看 redo log 配置
SHOW VARIABLES LIKE 'innodb_log%';

-- innodb_log_file_size：每个 redo log 文件大小（默认 48MB）
-- innodb_log_files_in_group：redo log 文件数量（默认 2）
-- innodb_log_buffer_size：redo log buffer 大小（默认 16MB）
```

### 2.6 redo log 的作用

1. **崩溃恢复**：数据库崩溃后，从 checkpoint 恢复未刷盘的数据
2. **事务持久性**：保证提交的事务不会丢失
3. **组提交**：多个事务的 redo log 可以一起刷盘，提高性能

## 三、undo log（回滚日志）

### 3.1 为什么需要 undo log？

**作用**：记录数据修改前的值，用于回滚和 MVCC。

```sql
BEGIN;
UPDATE users SET balance = 900 WHERE id = 1;  -- 原来的 balance = 1000
-- undo log 记录：balance = 1000

-- 如果需要回滚：
-- 从 undo log 读取旧值：balance = 1000
-- 恢复数据：UPDATE users SET balance = 1000 WHERE id = 1;
```

### 3.2 undo log 的存储

InnoDB 使用回滚段（Rollback Segment）存储 undo log：

```
undo tablespace（系统表空间或独立表空间）
  └── rollback segment（回滚段）
        └── undo log slot（undo 页）
              └── undo log record（undo 日志记录）
```

**undo log 页面类型**：
- `INSERT_UNDO`：插入操作的 undo（INSERT 无需保留旧值）
- `UPDATE_UNDO`：更新/删除操作的 undo（用于回滚和 MVCC）

### 3.3 undo log 与 MVCC

undo log 是 MVCC 的基础：

```
事务 A（id=1）修改 id=1 的行
        │
        ▼
┌─────────────────────────────────────────────┐
│ undo log                                    │
│  ┌─────────────────────────────────────┐    │
│  │ trx_id=1, balance=1000 (旧版本)    │    │
│  └─────────────────────────────────────┘    │
│         │ DB_ROLL_PTR 指向                  │
└─────────┼─────────────────────────────────────┘
          ▼
┌─────────────────────────────────────────────┐
│ 当前数据（最新版本）                        │
│ id=1, name=小明, balance=900, trx_id=1      │
└─────────────────────────────────────────────┘
```

### 3.4 undo log 的清理

undo log 不能无限增长，InnoDB 有 purge 线程清理：

```sql
-- 查看 purge 配置
SHOW VARIABLES LIKE 'innodb_purge%';

-- innodb_purge_threads：purge 线程数（默认 4）
-- innodb_max_purge_lag：最大 purge 延迟
```

## 四、binlog（二进制日志）

### 4.1 binlog 的作用

1. **主从复制**：将主库的数据变更同步到从库
2. **数据恢复**：通过 binlog 恢复指定时间段的数据
3. **审计**：记录所有数据变更操作

### 4.2 binlog 的内容

binlog 记录两种格式：

**1. STATEMENT 格式（语句）**
```sql
UPDATE users SET balance = balance - 100 WHERE id = 1;
```

**2. ROW 格式（行）**
```sql
Table: users
WHERE: id = 1
BEFORE: balance = 1000
AFTER: balance = 900
```

**3. MIXED 格式（混合）**
- 默认使用 STATEMENT
- 遇到不确定结果的语句（如 NOW()）自动切换到 ROW

### 4.3 binlog 配置

```sql
-- 开启 binlog（需要重启 MySQL）
[mysqld]
log-bin = mysql-bin
binlog_format = ROW
expire_logs_days = 7
max_binlog_size = 100M

-- 查看 binlog 状态
SHOW MASTER STATUS;
SHOW BINARY LOGS;
```

### 4.4 binlog 写入机制

binlog 采用 sync_binlog 参数控制刷盘：

```sql
-- sync_binlog = 1：每次事务提交都刷盘（最安全，性能最差）
-- sync_binlog = 0：依赖操作系统刷盘（性能最好，安全性差）
-- sync_binlog = N：每 N 次事务提交刷盘一次

SET GLOBAL sync_binlog = 1;  -- 默认值
```

### 4.5 binlog 查看

```sql
-- 查看 binlog 文件列表
SHOW BINARY LOGS;

-- 查看当前 binlog 文件
SHOW MASTER STATUS;

-- 查看 binlog 内容
SHOW BINLOG EVENTS IN 'mysql-bin.000001';

-- 使用 mysqlbinlog 工具
mysqlbinlog mysql-bin.000001 --start-datetime='2024-01-01 00:00:00'
mysqlbinlog mysql-bin.000001 --start-position=100 --stop-position=500
```

## 五、两阶段提交

### 5.1 什么是两阶段提交？

两阶段提交（Two-Phase Commit）保证 binlog 和 redo log 的一致性。

**问题**：如果只写 binlog 或只写 redo log，崩溃时可能导致数据不一致：

```
场景 1：只写 binlog，不写 redo log
- 事务提交时，先写 binlog
- binlog 写完后崩溃，redo log 没写
- 从库根据 binlog 同步了数据，但主库实际没数据
- 主从不一致！

场景 2：只写 redo log，不写 binlog
- 事务提交时，先写 redo log
- redo log 写完后崩溃，binlog 没写
- 主库数据已变更，但无法恢复或同步到从库
- 主从不一致！
```

### 5.2 两阶段提交流程

```
事务提交
    │
    ▼
┌─────────────────────────────────────────────────┐
│ 1. 写入 redo log（prepare 阶段）                  │
│    redo log: "事务修改，准备提交"                 │
│    ────────────────────────────────────────────│
│    此时 redo log 状态：prepare                   │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ 2. 写入 binlog                                  │
│    binlog: "事务的所有修改"                      │
│    fsync(binlog)                                │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ 3. 写入 redo log（commit 阶段）                  │
│    redo log: "事务提交完成"                      │
│    ────────────────────────────────────────────│
│    此时 redo log 状态：commit                    │
└─────────────────────────────────────────────────┘
    │
    ▼
事务提交完成
```

### 5.3 崩溃恢复流程

```
MySQL 崩溃重启
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 1. 扫描 redo log，查找 prepare 状态的日志        │
│    找到 prepare 的事务 X                         │
└─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│ 2. 查询 binlog，确认事务 X 是否已写入            │
│    ├── binlog 有事务 X → 提交事务（commit）     │
│    └── binlog 没有事务 X → 回滚事务              │
└─────────────────────────────────────────────────┘
        │
        ▼
恢复完成
```

**核心原则**：事务 X 只有同时满足以下条件才提交：
1. redo log 处于 prepare 状态
2. binlog 中有事务 X 的记录

### 5.4 两阶段提交保证一致性

```
情况 1：prepare 后崩溃
- redo log prepare，binlog 没写
- 恢复时发现 redo log prepare + binlog 无记录 → 回滚
- 主库和从库都没有数据 ✓

情况 2：binlog 后崩溃
- redo log prepare，binlog 写完
- 恢复时发现 redo log prepare + binlog 有记录 → 提交
- 主库和从库都有数据 ✓

情况 3：commit 后崩溃
- redo log commit 写完
- 恢复时发现 redo log commit → 无需处理
- 主库和从库都有数据 ✓
```

## 六、日志相关配置

### 6.1 redo log 配置

```sql
-- 查看 redo log 配置
SHOW VARIABLES LIKE 'innodb_log%';

-- 推荐配置（高可靠场景）
innodb_log_file_size = 1G        -- 日志文件大小
innodb_log_files_in_group = 3    -- 日志文件数量
innodb_log_buffer_size = 64M     -- 日志缓冲区
innodb_flush_log_at_trx_commit = 1  -- 每次提交都刷盘（最安全）
```

### 6.2 binlog 配置

```sql
-- 推荐配置
log-bin = /var/lib/mysql/mysql-bin  -- binlog 文件路径
binlog_format = ROW                  -- 使用 ROW 格式
expire_logs_days = 7                  -- 保留 7 天
max_binlog_size = 1G                  -- 单个 binlog 文件大小
sync_binlog = 1                       -- 每次提交都刷盘
```

### 6.3 刷盘策略对比

| innodb_flush_log_at_trx_commit | 含义 | 性能 | 可靠性 |
|--------------------------------|------|------|--------|
| 0 | 每秒刷盘一次 | 最高 | 可能丢失 1 秒数据 |
| 1 | 每次提交都刷盘（默认）| 最低 | 最可靠 |
| 2 | 提交时写系统缓存 | 中等 | 可能丢失 1 秒数据 |

## 七、面试高频问题

### Q1：binlog、redo log、undo log 有什么区别？

**答**：
- **binlog**：MySQL Server 层，记录所有数据变更，用于主从复制和数据恢复，逻辑日志
- **redo log**：InnoDB 独有，记录物理页变更，保证事务持久性，物理日志
- **undo log**：InnoDB 独有，记录修改前的值，用于回滚和 MVCC，逻辑日志

### Q2：为什么需要 redo log？

**答**：
1. 保证事务的持久性
2. WAL 机制：先写日志再写磁盘，提高 I/O 性能
3. 崩溃恢复：根据 redo log 恢复未刷盘的数据

### Q3：为什么需要 undo log？

**答**：
1. 回滚事务
2. MVCC 的基础，实现快照读
3. 实现读一致性

### Q4：什么是两阶段提交？

**答**：两阶段提交保证 binlog 和 redo log 的一致性：
1. prepare：写 redo log，状态为 prepare
2. commit：写 binlog，然后 redo log 状态改为 commit
崩溃恢复时，根据 redo log prepare + binlog 是否有记录来决定是否提交。

### Q5：binlog 格式有哪些？

**答**：
- **STATEMENT**：记录执行的 SQL 语句
- **ROW**：记录每行的变更（最安全，推荐）
- **MIXED**：混合模式，自动切换

### Q6：redo log 是循环写的吗？

**答**：是的。redo log 是固定大小的环形缓冲区，写满后需要等待 checkpoint 推进才能继续写。

## 八、总结

**日志核心要点**：
- **redo log**：物理日志，保证持久性，支持崩溃恢复
- **undo log**：逻辑日志，支持回滚和 MVCC
- **binlog**：逻辑日志，支持主从复制和数据恢复
- **两阶段提交**：保证 binlog 和 redo log 一致性

**日志与事务**：

| 事务阶段 | binlog | redo log | undo log |
|---------|--------|----------|----------|
| BEGIN | - | - | - |
| 修改数据 | - | 写入 Buffer | 记录旧值 |
| COMMIT | 写入 | 写入（commit） | 清理 |

**最佳实践**：
1. 生产环境 innodb_flush_log_at_trx_commit = 1
2. 生产环境 sync_binlog = 1
3. 使用 ROW 格式的 binlog
4. 合理配置 redo log 文件大小

---

**本系列进度：24/30 篇 (80%)**

**下一篇预告**：MySQL 主从复制与分库分表

**参考资料**：
- MySQL 官方文档：https://dev.mysql.com/doc/refman/8.0/en/
- 《高性能 MySQL》- Baron Schwartz
- 《MySQL 技术内幕：InnoDB 存储引擎》- 姜承尧
