---
title: "MySQL 主从复制与分库分表深度解析"
date: 2026-05-12T17:40:00+08:00
draft: false
categories: ["mysql"]
tags: ["mysql", "replication", "sharding", "shardingsphere", "read-write-separation"]
---


# MySQL 主从复制与分库分表深度解析

> 面试高频问题：MySQL 主从复制原理？什么是半同步复制？分库分表如何实现？ShardingSphere 是什么？

## 引言

随着业务增长，单机 MySQL 无法承载海量数据和高并发访问。主从复制和分库分表是 MySQL 扩展的两种核心方案。主从复制解决读写分离和数据备份问题，分库分表解决数据量大的问题。

## 一、主从复制

### 1.1 为什么需要主从复制？

```
主从复制解决的问题：
├── 读写分离：主库写，从库读，分担压力
├── 数据备份：从库可作为实时备份
├── 高可用：主库故障时，从库可切换为主库
└── 异地部署：多地部署，减少访问延迟
```

### 1.2 主从复制架构

```
┌─────────────┐         binlog          ┌─────────────┐
│   主库      │ ──────────────────────→ │   从库      │
│  (Master)   │         I/O Thread      │  (Slave)    │
│             │ ← ───────────────────── │             │
│  写操作     │         SQL Thread      │  读操作     │
└─────────────┘                          └─────────────┘
```

### 1.3 主从复制原理

**核心原理**：主库将数据变更记录到 binlog，从库通过 I/O 线程拉取 binlog，在从库重放（Relay Log）执行。

```
主从复制流程：
┌────────────────────────────────────────────────────────────────┐
│ 主库                                                          │
│ 1. 客户端执行 INSERT/UPDATE/DELETE                           │
│ 2. 写入存储引擎（InnoDB）                                     │
│ 3. 写入 binlog（MySQL Server 层）                            │
│    └── binlog dump 线程：将 binlog 发送给从库                 │
└────────────────────────────────────────────────────────────────┘
                              ↓ binlog
┌────────────────────────────────────────────────────────────────┐
│ 从库                                                          │
│ 4. I/O Thread：接收 binlog，写入 relay log                    │
│ 5. SQL Thread：读取 relay log，执行 SQL                       │
│ 6. 写入存储引擎                                               │
└────────────────────────────────────────────────────────────────┘
```

### 1.4 三种复制方式

**1. 异步复制（Async Replication）**

```
主库 → 提交事务 → 立即返回成功
                    ↓
              从库异步拉取（可能有延迟）
```

- 默认模式，性能最好
- 主库提交后不等待从库确认
- 可能出现主从不一致

**2. 半同步复制（Semi-sync Replication）**

```sql
-- 开启半同步复制
-- 主库安装插件
INSTALL PLUGIN rpl_semi_sync_master SONAME 'semisync_master.so';

-- 从库安装插件
INSTALL PLUGIN rpl_semi_sync_slave SONAME 'semisync_slave.so';

-- 开启半同步
SET GLOBAL rpl_semi_sync_master_enabled = 1;
SET GLOBAL rpl_semi_sync_slave_enabled = 1;
```

```
主库 → 提交事务 → 等待至少一个从库确认
                    ↓
              至少一个从库写入 relay log 后返回成功
```

- 主库等待至少一个从库确认
- 提高数据安全性
- 性能略低于异步复制

**3. 全同步复制（Sync Replication）**

```
主库 → 提交事务 → 等待所有从库执行完成
                    ↓
              所有从库确认后返回成功
```

- 性能最差，但数据最安全
- 实际很少使用

### 1.5 GTID 复制

GTID（Global Transaction Identifier）是 MySQL 5.6+ 引入的全局事务 ID。

```sql
-- GTID 格式
GTID = source_id:transaction_id
-- 例如：3E11FA47-71CA-11E1-9E33-C80AA9429562:23

-- 开启 GTID 模式
[mysqld]
gtid_mode = ON
enforce_gtid_consistency = ON
```

**GTID 优势**：
- 无需指定 binlog 位置，自动定位
- 方便主从切换和故障恢复
- 更容易实现自动化运维

### 1.6 主从复制配置

**主库配置**：

```sql
[mysqld]
server-id = 1  -- 必须唯一
log-bin = mysql-bin  -- 开启 binlog
binlog_format = ROW  -- 推荐使用 ROW 格式

-- 创建复制账号
CREATE USER 'repl'@'%' IDENTIFIED BY 'password';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';

-- 查看 binlog 状态
SHOW MASTER STATUS;
-- 输出：File: mysql-bin.000001, Position: 154
```

**从库配置**：

```sql
[mysqld]
server-id = 2  -- 必须唯一
relay-log = relay-bin  -- relay log
read_only = ON  -- 只读（可选）
super_read_only = ON  -- 禁止 super 权限写入

-- 设置主库信息
CHANGE MASTER TO
    MASTER_HOST = 'master_host',
    MASTER_USER = 'repl',
    MASTER_PASSWORD = 'password',
    MASTER_LOG_FILE = 'mysql-bin.000001',
    MASTER_LOG_POS = 154;

-- 启动复制
START SLAVE;

-- 查看复制状态
SHOW SLAVE STATUS\G;
```

### 1.7 主从延迟与解决方案

**延迟原因**：
1. 从库 I/O 线程拉取 binlog 慢
2. 从库 SQL 线程重放慢
3. 大事务：一个事务变更大量数据
4. 从库硬件性能差

**优化方案**：

```sql
-- 1. 开启并行复制（从库多线程重放）
SET GLOBAL slave_parallel_workers = 8;  -- 8 个 worker 线程
SET GLOBAL slave_parallel_type = LOGICAL_CLOCK;  -- 按事务并行

-- 2. 配置 relay log 同步到磁盘
SET GLOBAL sync_relay_log = 1;

-- 3. 监控主从延迟
SHOW SLAVE STATUS\G;
-- Seconds_Behind_Master：延迟秒数
```

### 1.8 主从切换

```sql
-- 1. 停止主库写入
SET GLOBAL read_only = ON;
-- 等待所有应用断开连接

-- 2. 确认从库追上主库
SHOW SLAVE STATUS\G;
-- 确保 Seconds_Behind_Master = 0

-- 3. 停止从库复制
STOP SLAVE;
RESET SLAVE ALL;

-- 4. 将从库提升为主库
SET GLOBAL read_only = OFF;
-- 切换应用连接新主库
```

## 二、数据分库分表

### 2.1 什么时候需要分库分表？

| 指标 | 单机 MySQL 上限 | 分库分表后 |
|------|----------------|-----------|
| 数据量 | 千万级 | 百亿级 |
| QPS | 1 万 | 10 万+ |
| 存储 | 1-2 TB | 数十 TB |

**何时分库分表**：
1. 单表数据超过 2000 万行
2. 单库数据超过 1TB
3. 读写性能明显下降
4. 备份和恢复时间过长

### 2.2 垂直拆分

**垂直分库**：按业务将不同的表分到不同的数据库。

```
原架构：
┌─────────────────────────┐
│      应用               │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│      订单库              │
│  - orders               │
│  - order_items          │
│  - payments             │
└─────────────────────────┘

垂直分库后：
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   用户库      │  │   订单库      │  │   商品库     │
│  - users      │  │  - orders    │  │  - products  │
│  - addresses  │  │  - order_items│  │  - inventory │
└──────────────┘  └──────────────┘  └──────────────┘
```

**垂直分表**：将大表按字段拆分。

```sql
-- 原表：users（100 个字段，2MB/行）
-- 分表后：
users_main：id, name, email, password, ...（常用字段，200KB/行）
users_extra：id, bio, avatar, hobbies, ...（大字段）
```

### 2.3 水平拆分

**水平分库**：将数据按行拆分到不同的数据库。

```sql
-- 按 user_id % 2 分库
user_id % 2 == 0 → users_db0
user_id % 2 == 1 → users_db1
```

```
┌──────────────┐  ┌──────────────┐
│   users_db0  │  │   users_db1  │
│  user_id 偶数│  │  user_id 奇数 │
└──────────────┘  └──────────────┘
```

**水平分表**：将数据按行拆分到同一库的多张表。

```sql
-- 按 user_id % 4 分表
user_id % 4 == 0 → users_0
user_id % 4 == 1 → users_1
user_id % 4 == 2 → users_2
user_id % 4 == 3 → users_3
```

```
┌─────────────────────────────────┐
│           users_db             │
│  ┌─────────┐  ┌─────────┐     │
│  │users_0 │  │users_1 │     │
│  └─────────┘  └─────────┘     │
│  ┌─────────┐  ┌─────────┐     │
│  │users_2 │  │users_3 │     │
│  └─────────┘  └─────────┘     │
└─────────────────────────────────┘
```

### 2.4 分片策略

**1. 哈希分片**

```sql
-- 取模分片
shard_key = user_id % 4

-- 优点：数据分布均匀
-- 缺点：扩容困难（需要迁移大量数据）
```

**2. 范围分片**

```sql
-- 按时间分片
2024-01: orders_202401
2024-02: orders_202402
...

-- 优点：适合按时间查询
-- 缺点：可能产生热点（当前月数据多）
```

**3. 一致性哈希**

```sql
-- 一致性哈希环
                    ┌─────────────┐
                    │   节点 A     │
                    └─────────────┘
                           ↑
                    ┌──────┴──────┐
                    │   哈希环    │
                    └─────────────┘
         ┌───────────────┬───────────────┐
         ↑               ↑               ↑
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │  节点 B  │    │  节点 C  │    │  节点 D  │
    └─────────┘    └─────────┘    └─────────┘
```

- 优点：扩容时只需迁移部分数据
- 缺点：实现复杂

### 2.5 分库分表的问题

**1. 跨分片查询**

```sql
-- 问题：查询所有用户的订单（分布在多表）
-- 解决：多次查询 + 合并，或使用 ES

-- 单分片查询
SELECT * FROM orders_0 WHERE user_id = 123;
SELECT * FROM orders_1 WHERE user_id = 123;
-- 合并结果
```

**2. 跨分片 JOIN**

```sql
-- 问题：orders 和 products 在不同库
-- 解决方案：
-- 1. 字段冗余（denormalization）
-- 2. 多次查询 + 应用层 JOIN
-- 3. 使用 ES/Hive 做 OLAP
```

**3. 分片键选择**

```sql
-- 好的分片键
user_id：查询经常按用户维度
order_id + time：适合按时间范围查询

-- 避免的分片键
status：分布不均
create_time + user_id：查询维度固定，不够灵活
```

**4. 分页问题**

```sql
-- 问题：需要从多表获取第 100 页
-- 解决：使用游标分页，或增加全局序号表
SELECT * FROM orders 
WHERE id > #{cursor} 
ORDER BY id 
LIMIT 20;
```

### 2.6 分库分表中间件

**ShardingSphere**：

```xml
<!-- Maven 依赖 -->
<dependency>
    <groupId>org.apache.shardingsphere</groupId>
    <artifactId>shardingsphere-jdbc-core</artifactId>
    <version>5.4.0</version>
</dependency>
```

```yaml
# ShardingSphere 配置
schemaName: sharding_db

dataSources:
  ds_0:
    dataSourceClassName: com.zaxxer.hikari.HikariDataSource
    driverClassName: com.mysql.cj.jdbc.Driver
    jdbcUrl: jdbc:mysql://localhost:3306/ds_0
    username: root
    password: 

rules:
  - !SHARDING
    tables:
      orders:
        actualDataNodes: ds_${0..1}.orders_${0..3}
        tableStrategy:
          standard:
            shardingColumn: user_id
            shardingAlgorithmName: orders_inline
        keyGenerateStrategy:
          column: order_id
          keyGeneratorName: snowflake
    bindingTables:
      - orders,order_items
    defaultDatabaseStrategy:
      standard:
        shardingColumn: user_id
        shardingAlgorithmName: database_inline
```

```java
// Java 代码
@DataSource("ds_0")
public Order selectById(Long orderId) {
    return jdbcTemplate.queryForObject(
        "SELECT * FROM orders WHERE order_id = ?", 
        orderId
    );
}
```

## 三、读写分离

### 3.1 读写分离架构

```
┌─────────────────────────────────────────┐
│              应用层                     │
│    (配置主从数据源，自动路由读写)        │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        ↓                   ↓
┌───────────────┐     ┌───────────────┐
│    主库        │     │    从库       │
│  (写操作)      │     │  (读操作)      │
└───────────────┘     └───────────────┘
```

### 3.2 读写分离配置

**Spring Boot 配置**：

```yaml
# application.yml
spring:
  datasource:
    master:
      jdbc-url: jdbc:mysql://master:3306/db
      username: root
    slave1:
      jdbc-url: jdbc:mysql://slave1:3306/db
      username: root
    slave2:
      jdbc-url: jdbc:mysql://slave2:3306/db
      username: root
```

```java
// 使用 AbstractRoutingDataSource 实现读写分离
@Bean
public DataSource dataSource() {
    Map<Object, Object> targetDataSources = new HashMap<>();
    targetDataSources.put("master", masterDataSource());
    targetDataSources.put("slave", slaveDataSource());
    
    RoutingDataSource routingDataSource = new RoutingDataSource();
    routingDataSource.setTargetDataSources(targetDataSources);
    routingDataSource.setDefaultTargetDataSource(masterDataSource());
    
    return routingDataSource;
}

// 切换数据源
public class RoutingDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return "master".equals(DbContextHolder.get()) ? "master" : "slave";
    }
}
```

### 3.3 读写分离问题

**主从延迟问题**：

```java
// 问题：写入后立即查询，可能查到旧数据
orderService.create(order);  // 写主库
orderService.findById(order.getId());  // 可能读从库，返回 null

// 解决方案 1：强制读主库
@ReadOnly(skip = false)  // 或配置
public Order findById(Long id) {
    return jdbcTemplate.queryForObject(
        "SELECT * FROM orders WHERE id = ?", 
        id
    );
}

// 解决方案 2：延迟感知（GTID 或 Seconds_Behind_Master）
```

## 四、面试高频问题

### Q1：MySQL 主从复制的原理？

**答**：主库将数据变更写入 binlog，从库的 I/O 线程拉取 binlog 写入 relay log，SQL 线程读取 relay log 执行 SQL。核心是 binlog 的传输和应用。

### Q2：主从延迟的原因？如何优化？

**答**：
- 原因：大事务、网络延迟、从库性能差
- 优化：并行复制、减少大事务、使用半同步

### Q3：分库分表有哪几种方式？

**答**：
- 垂直分库：按业务分到不同库
- 垂直分表：按字段拆成多张表
- 水平分库：按行分到不同库
- 水平分表：按行分到同一库的多张表

### Q4：分片键如何选择？

**答**：选择查询最频繁、分布均匀的字段。避免选择有热点的字段。常用策略：哈希分片、范围分片、一致性哈希。

### Q5：分库分表后有哪些问题？

**答**：
- 跨分片查询和 JOIN
- 分页问题
- 分布式事务
- 扩容迁移

### Q6：ShardingSphere 是什么？

**答**：Apache 顶级的数据分片中间件，支持分库分表、读写分离、数据加密等功能。

## 五、总结

**主从复制核心要点**：
- **原理**：binlog 传输 + relay log 重放
- **复制方式**：异步、半同步、全同步
- **GTID**：全局事务 ID，简化主从管理
- **延迟优化**：并行复制、减少大事务

**分库分表核心要点**：
- **拆分方式**：垂直分库/分表、水平分库/分表
- **分片策略**：哈希、范围、一致性哈希
- **常见问题**：跨分片查询/JOIN、分页、扩容
- **工具**：ShardingSphere

**架构演进**：
```
单机 MySQL
    ↓ 垂直分库
按业务拆分的多个库
    ↓ 水平分库
分库分表集群
    ↓ 主从复制
读写分离 + 分库分表
```

**最佳实践**：
1. 先考虑优化：加索引、缓存、读写分离
2. 确实需要时才分库分表
3. 选择合适的分片键
4. 预留扩容空间

---

**本系列进度：25/30 篇 (83%)**

**MySQL 5 篇全部完成 ✅**

**下一篇预告**：Redis 数据结构与底层实现

**参考资料**：
- MySQL 官方文档：https://dev.mysql.com/doc/refman/8.0/en/
- 《高性能 MySQL》- Baron Schwartz
- ShardingSphere 官方文档：https://shardingsphere.apache.org/
