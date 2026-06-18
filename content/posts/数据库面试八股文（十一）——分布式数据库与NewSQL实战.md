---
title: "数据库面试八股文（十一）——分布式数据库与NewSQL实战"
date: 2026-06-18T10:00:00+08:00
draft: false
categories: ["数据库"]
tags: ["面试", "八股文", "分布式", "NewSQL", "TiDB", "CockroachDB", "CAP", "分布式事务", "Raft", "HTAP"]
---

# 数据库面试八股文（十一）——分布式数据库与NewSQL实战

> 🎯 **本文目标**：承接本系列前10篇的单机数据库知识，全面转向分布式数据库领域。从CAP理论出发，深入TiDB/CockroachDB等NewSQL架构原理，剖析分布式事务、Raft一致性协议，最终以高频面试题收尾。

---

## 一、分布式理论基础

### 1.1 CAP定理的本质

```
CAP定理: 一个分布式系统最多只能同时满足以下三个特性中的两个：

    C (Consistency)     一致性  —— 所有节点同一时刻看到相同数据
    A (Availability)    可用性  —— 每个请求都能获得非错误的响应
    P (Partition Tolerance) 分区容错性 —— 系统在网络分区时仍能继续工作

    注意：P是客观存在的（网络分区无法避免），所以实际上是CP vs AP的选择
```

**CAP选择的现实含义：**

```
CP系统（优先一致性）:
  发生网络分区时 → 牺牲可用性 → 少数派节点拒绝服务
  代表: Zookeeper, HBase, MongoDB(默认强一致配置)
  适用: 金融交易、配置中心、元数据管理

AP系统（优先可用性）:
  发生网络分区时 → 牺牲一致性 → 允许读到旧数据，最终一致
  代表: Eureka, Cassandra, DynamoDB
  适用: 社交媒体feed、商品展示、用户偏好

⚠️ 澄清误区:
  - CAP不是说三选二，而是发生分区时优先保证哪个
  - 没有分区时，系统可以同时提供C和A
  - "CP"不代表系统不可用，只是强一致场景下等待多数派确认
```

### 1.2 BASE理论

```
BASE = Basically Available（基本可用）+ Soft state（软状态）+ Eventually consistent（最终一致性）

它是AP系统的实践理论，与ACID形成对比：

        ACID                      BASE
    强一致性                   最终一致性
    事务边界清晰                允许中间态
    传统RDBMS                  NoSQL/NewSQL
    "现在就要对"               "过一会儿对也行"
```

### 1.3 一致性模型全览

| 一致性级别 | 说明 | 实现 | 性能 |
|-----------|------|------|------|
| 强一致性 | 写入后立刻对所有读者可见 | Paxos/Raft同步 | 低 |
| 顺序一致性 | 所有节点看到相同操作顺序 | ZAB协议 | 中 |
| 因果一致性 | 有因果关系的操作保持顺序 | 向量时钟 | 中高 |
| 读己之写 | 用户总能读到自己的写入 | 会话粘性 | 中高 |
| 单调读 | 不会读到越来越旧的数据 | 客户端缓存版本 | 中高 |
| 最终一致性 | 停止写入后最终一致 | Gossip协议 | 高 |

**Q1: 为什么大多数互联网公司选择AP而非CP？**
A:
1. **用户体验优先**：宁可看到5秒前的旧数据，也不愿看到500错误
2. **业务可容忍短暂不一致**：微博评论数差几秒没人在意
3. **补偿机制成熟**：可以用对账、消息队列补发等补偿数据不一致
4. **成本考量**：强一致的同步开销远高于最终一致性方案

---

## 二、分布式一致性协议

### 2.1 Paxos核心思想

```
Paxos三个角色:
  Proposer (提议者)  → 发起提案
  Acceptor (接受者)  → 投票表决
  Learner  (学习者)  → 学习已确定的决议

基本Paxos流程:
  Phase 1 (Prepare):
    Proposer → 广播 Prepare(n)  → Acceptors
    Acceptor承诺: "不再接受编号 < n 的提案"
    
  Phase 2 (Accept):
    Proposer → 广播 Accept(n, value) → Acceptors
    多数派接受 → 决议确定

问题: 活锁（两个Proposer交替提更高的n，谁都无法提交）
解决: Multi-Paxos → 选举Leader，只有Leader可以提议
```

### 2.2 Raft协议详解

```
Raft的三个子问题:
  ┌─ Leader Election（领导人选举）
  │    随机超时 → 发起投票 → 获得多数票 → 成为Leader
  │    Term（任期）概念，每个Term最多一个Leader
  │
  ├─ Log Replication（日志复制）
  │   客户端写 → Leader日志 → 复制到Followers → 多数确认 → 提交
  │   提交后Apply到状态机
  │
  └─ Safety（安全性）
       Leader只能提交当前Term的日志（间接提交之前Term的日志）
       选举限制：Candidate的日志必须至少和多数节点一样新
```

**Raft vs Paxos：**

| 维度 | Paxos | Raft |
|------|-------|------|
| 理解难度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 工程实现 | 需要大量工程决策 | 设计就是为可实现 |
| 日志 | 不支持连续日志 | 原生支持Log Replication |
| 成员变更 | 复杂 | 联合共识(Joint Consensus) |
| 代表实现 | Chubby(ZooKeeper类似) | etcd, TiKV, Consul |

**Leader选举过程动画：**
```
Term 1:
  Node1: [Follower] timeout→[Candidate]→gets 3 votes→[Leader]
  Node2: [Follower]────────→votes Node1──→[Follower]
  Node3: [Follower]────────→votes Node1──→[Follower]

Term 2 (Node1故障):
  Node2: [Follower] timeout→[Candidate]→gets 2 votes→[Leader]
  Node3: [Follower]────────→votes Node2──→[Follower]
```

### 2.3 2PC vs 3PC vs TCC

```
2PC (两阶段提交):
  Phase 1: Coordinator → 所有参与者: "Prepare"
           参与者锁定资源，回复 Yes/No
  Phase 2: 全部Yes → 发送Commit → 参与者提交
           任何No → 发送Rollback → 参与者回滚

  致命缺陷: Coordinator宕机时，参与者持锁等待，形成阻塞

3PC (三阶段提交):
  增加PreCommit阶段和超时机制
  但网络分区时仍可能不一致（很少实际使用）

TCC (Try-Confirm-Cancel):
  Try:    预留资源（如冻结库存）
  Confirm: 确认执行（如扣减库存）
  Cancel:  释放资源（如解冻库存）
  
  优势: 业务层面控制，不持有数据库锁
  代价: 需实现Confirm/Cancel的幂等逻辑
```

---

## 三、TiDB深度剖析

### 3.1 架构回顾与存储

```
┌────────────────────────────────────────────────┐
│                   TiDB Cluster                  │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ TiDB     │  │ TiDB     │  │ TiDB     │     │
│  │ (SQL层)  │  │ (SQL层)  │  │ (SQL层)  │     │  ← 计算节点
│  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       │              │              │           │
│       └──────────────┼──────────────┘           │
│                      │                           │
│              ┌───────┴───────┐                   │
│              │      PD       │                   │  ← 大脑
│              │ (Placement    │                   │
│              │  Driver)      │                   │
│              └───────┬───────┘                   │
│                      │                           │
│    ┌─────────────────┼─────────────────┐        │
│    │                 │                 │        │
│ ┌──┴───┐        ┌───┴──┐        ┌───┴──┐     │
│ │ TiKV │        │ TiKV │        │ TiKV │     │  ← 行存储
│ │      │        │      │        │      │     │
│ └──────┘        └──────┘        └──────┘     │
│                                                 │
│ ┌──────┐        ┌──────┐         ┌──────┐     │
│ │TiFlash│       │TiFlash│        │TiFlash│    │  ← 列存储(HTAP)
│ └──────┘        └──────┘         └──────┘     │
└────────────────────────────────────────────────┘
```

### 3.2 Key-Value映射与Region分裂

```
从SQL到KV的映射:
  Table: t(id INT PRIMARY KEY, name VARCHAR)
  行: (1, "张三")
  
  ↓ 编码 ↓
  
  Key:   t_1_r    (t{tableID}_1{rowID}_r)
  Value: [name: "张三"]
  
  ↓ Region划分 ↓
  
  Region-1: [t_1_, t_100_)   ← 包含id 1~99的数据
  Region-2: [t_100_, t_200_) ← 包含id 100~199的数据
  Region-3: [t_200_, )       ← 包含id 200+的数据

Region分裂:
  默认96MB自动分裂 → 确保每个Region不会过大
  热点Region自动分裂 → 解决写入热点
  空Region自动合并 → 节省Raft组开销
```

### 3.3 分布式事务：Percolator模型

```
Percolator事务流程（乐观事务）:

预写阶段 (Prewrite):
  Client → TiDB: BEGIN
  TiDB → PD: 分配start_ts(事务开始时间戳)
  
  对每个涉及的行:
    1. 写入Lock:     key_lock = {primary, start_ts}
    2. 写入Data:     key_data = value (此时版本=start_ts, 不可见)
    3. 检查冲突:     是否有其他事务锁定了这些行
  
  全部Prewrite成功 → 进入Commit阶段
  任何Prewrite失败 → 回滚（清理锁和data）

提交阶段 (Commit):
  TiDB → PD: 分配commit_ts
  写入Write记录: key_write = {start_ts, commit_ts}
  清理Lock
  
事务可见性判断:
  读取时找到最新的 commit_ts <= read_ts 的版本
  如果遇到未提交的Lock → 等待或回滚

Percolator的核心优势:
  ✅ 无中心化事务管理器（消除了2PC的Coordinator瓶颈）
  ✅ 快照隔离(SI)级别
  ✅ 写入不会阻塞读取（MVCC机制）
```

**Q2: Percolator模型如何处理冲突？**
A:
1. **写-写冲突**：Prewrite阶段检测，后事务检测到Lock → Abort
2. **读-写冲突**：快照隔离，读不阻塞写，写不阻塞读
3. **锁超时**：TTL机制，超时的锁可被其他事务清理（防止死锁）
4. **锁残留**：`ResolveLocks`协程定期扫描并清理残留锁

### 3.4 TiFlash与HTAP

```
HTAP = Hybrid Transactional/Analytical Processing

传统架构:
  OLTP(MySQL) ──ETL──→ OLAP(Hive/ClickHouse)
  问题: 延迟高(T+1)、数据不一致、维护两套

TiDB HTAP:
  TiKV(行存)     ——→  实时同步  ——→  TiFlash(列存)
  (TP查询)        (Raft Learner)      (AP查询)
  
  TiDB自动路由:
    SELECT * FROM orders WHERE id = 123   → TiKV(点查)
    SELECT SUM(amount) FROM orders        → TiFlash(聚合)
```

---

## 四、CockroachDB深度剖析

### 4.1 核心特色

```
CockroachDB vs TiDB 差异:

CockroachDB特色:
  1. 多区域部署原生支持
     CREATE TABLE users (
       id INT PRIMARY KEY,
       name STRING,
       region STRING
     ) LOCALITY REGIONAL BY TABLE IN "us-east";
     
  2. 数据属地性(Data Domiciling)
     德国用户数据 → 永远存储在德国数据中心
     满足GDPR合规要求
     
  3. Follow-the-Work
     数据跟随访问者自动迁移到最近区域
     
  4. PostgreSQL兼容
     使用PG协议和语法，而非MySQL
```

### 4.2 CRDB的Range与Leaseholder

```
Range结构:
  ┌─────────────────────────┐
  │       Range [a, m)      │
  │                         │
  │  Replica 1 (Node A)     │  ← Leaseholder (负责读写协调)
  │  Replica 2 (Node B)     │
  │  Replica 3 (Node C)     │
  └─────────────────────────┘

Leaseholder类似Raft Leader:
  - 持有时间租约(Lease)，到期需续约
  - 所有写请求通过Leaseholder
  - 读请求根据一致性要求可能走Follower

Region vs Range:
  TiDB的Region ≈ CockroachDB的Range
  都是数据分片的基本单位
```

### 4.3 CRDB的分布式事务

```
CRDB事务流程（并行提交优化）:

传统:  
  BEGIN → Writes → COMMIT(等待2轮Raft) → 完成
  
并行提交(Parallel Commit):
  BEGIN → Writes → Staging Record(同时并行写入) → COMMIT(1轮Raft) → 完成
  
  Staging Record: 提前告诉系统"这些Write我打算提交"
  如果事务失败: Staging Records被垃圾回收
  
性能对比:
  普通事务: 2轮Raft共识延迟
  并行提交: 1轮Raft共识延迟 (近50%提升)
```

---

## 五、其他NewSQL方案概览

### 5.1 OceanBase

```
OceanBase (蚂蚁集团):
  架构: 对等节点，每个节点同时承担计算和存储
  特色:
    - 准内存数据库（数据主要在内存，磁盘是备份）
    - 多租户架构（资源隔离）
    - TPC-C跑分冠军(2020年)
    - 金融级高可用（RPO=0, RTO<30s）
  适用: 金融核心系统
```

### 5.2 YugabyteDB

```
YugabyteDB:
  存储: 基于DocDB（RocksDB增强版）
  分片: Tablet分片（Hash/Range）
  一致性: Raft
  SQL: PostgreSQL兼容
  特色:
    - 真正的多区域主-主部署
    - 支持Redis兼容API(YEDIS)
    - 每个Tablet是独立的Raft组
```

### 5.3 Google Spanner

```
Google Spanner (NewSQL鼻祖):
  核心创新: TrueTime API
    - 通过原子钟+GPS提供全局时钟
    - 时间误差范围控制在[ε, +ε]（通常<7ms）
    - 外部分布式事务无锁等待时间 = 2ε
  
  外部一致性:
    如果T1在T2之前提交 → T1的时间戳 < T2的时间戳
    这是分布式数据库的最强一致性保证
    
  影响:
    TiDB的TSO(PD分配时间戳) → 类Spanner方案
    CRDB的HLC(混合逻辑时钟) → Spanner的简化版
```

---

## 六、分布式数据库选型指南

### 6.1 选型决策树

```
你的需求是什么？
├── 极致OLTP性能 + 简单架构
│   └── → 单机MySQL/PostgreSQL（未到瓶颈）
│
├── 单机开始触达瓶颈，团队有DBA
│   └── → MySQL分库分表 + ShardingSphere
│
├── 业务快速发展，不希望管理分片
│   ├── MySQL技术栈 → TiDB
│   └── PostgreSQL技术栈 → CockroachDB
│
├── 金融核心系统 + Oracle替代
│   └── → OceanBase
│
├── 全球化多区域部署
│   └── → CockroachDB（原生多区域支持）
│
├── 需要HTAP混合负载
│   └── → TiDB（TiFlash列存引擎）
│
└── 公有云/K8s原生
    ├── AWS → Aurora
    ├── GCP → Spanner
    └── K8s → Vitess + MySQL
```

### 6.2 迁移风险清单

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| SQL不兼容 | 某些SQL语法/函数不支持 | 全面测试，建立兼容性清单 |
| 性能回退 | 单行查询可能慢于MySQL | POC压测，评估核心场景 |
| 运维能力 | NewSQL运维要求高 | 优先使用云服务版本(TiDB Cloud) |
| 生态成熟度 | 周边工具不如MySQL丰富 | 评估监控/备份/迁移工具链 |
| 成本 | 至少3节点起步 | TCO对比（含分库分表运维人力） |

**Q3: TiDB能否完全替代MySQL？**
A: **大多数场景可以，但不是全部。**
- ✅ 替代：常规OLTP、分库分表场景、需要弹性扩缩
- ⚠️ 谨慎：极致延迟敏感（<1ms）、存储过程重度使用
- ❌ 不适合：嵌入式/单机部署（IoT设备）、某些特殊SQL语法

---

## 七、面试高频题精选

**Q4: Raft协议如何保证Leader切换时数据不丢失？**
A:
1. **选举限制**：Candidate的日志必须至少和多数节点一样新
2. **只提交当前Term的日志**：Leader只能提交自己Term内的日志，之前的日志通过"间接提交"
3. **Commitment规则**：一条日志被复制到多数节点后才认为Committed
4. **Leader Append-Only**：Leader永远不会删除或覆盖自己的日志

**Q5: TiDB为什么需要PD？PD挂掉会怎样？**
A:
- **PD的作用**：TSO分配、Region调度、元数据管理
- **PD挂掉影响**：
  - TSO无法分配 → 新的事务无法开始（已有事务可继续）
  - Region调度停止（但不影响正常读写）
  - 元数据变更停止（但缓存可继续使用）
- **高可用**：3节点PD集群，Raft保证一致性
- **脑裂处理**：TSO基于时间戳，分配前会检查Leader身份

**Q6: 分库分表后如何进行跨分片分页查询？**
A:
```sql
-- 原始需求：全库查询订单列表，按时间排序，第3页
SELECT * FROM orders ORDER BY create_time DESC LIMIT 20, 10;

-- 分片后无法直接执行！解决方案：

方案1: 全局查询（性能差，仅适合小数据量）
  各分片执行 LIMIT 30 → 中间件汇总排序 → 取第20-30条

方案2: 二次查询法（ShardingSphere方案）
  第1次: 各分片取前30条（含排序列+主键）
  第2次: 汇总确定全局位置后，按主键精确取第20-30条

方案3: ES/HBase二级索引（推荐）
  搜索条件走ES → 拿到主键ID列表 → 按ID批量查询MySQL分片
  
方案4: 禁止跳页
  只支持"加载更多"（基于游标分页）
```

**Q7: 什么是HTAP？为什么以前不能实现？**
A:
```
HTAP = Hybrid Transactional/Analytical Processing
同一套数据，同时支持OLTP(事务)和OLAP(分析)

以前不能的原因:
  1. 行存适合OLTP，列存适合OLAP → 互相矛盾
  2. TP和AP查询会互相争夺资源
  3. 数据同步延迟（ETL需要T+1）

现在的实现:
  1. Raft Learner复制 → 实时同步行存→列存（秒级延迟）
  2. 资源隔离 → TP和AP使用不同节点
  3. TiDB: TiKV(行存) + TiFlash(列存)，自动路由
```

**Q8: 分布式事务的隔离级别能到Serializable吗？**
A:
- **TiDB**：默认Snapshot Isolation(SI)，可通过`SET TRANSACTION ISOLATION LEVEL SERIALIZABLE`升级到SSI（Serializable Snapshot Isolation），但性能会有损耗
- **CockroachDB**：默认Serializable！通过串行化冲突检测实现
- **为什么大多数选择SI**：SI已能防止脏读、不可重复读、幻读（基于MVCC快照），写偏斜(Write Skew)等极端场景才需要Serializable

---

## 八、未来趋势

### NewSQL的发展方向

```
1. Serverless数据库
   - TiDB Cloud Serverless Tier
   - CockroachDB Serverless
   - Neon (Serverless PostgreSQL)
   趋势: 按需付费，零运维，适合中小项目

2. AI + 数据库
   - 智能索引推荐
   - SQL自动优化（AI生成执行计划）
   - 自然语言查询（Text-to-SQL）
   
3. 多模数据库
   - 一份数据多种访问方式（SQL + KV + Graph + 文档）
   - TiDB融入向量搜索能力

4. 边缘数据库
   - SQLite + CRDT = 本地优先的分布式
   - 离线可用 + 在线同步

5. 区块链数据库
   - 可验证的SQL查询
   - 防篡改的审计日志
```

---

## 九、总结

| 层次 | 核心技术 | 面试关键词 |
|------|---------|-----------|
| 理论基础 | CAP/BASE、一致性模型 | 强一致、最终一致、因果一致 |
| 一致性协议 | Paxos/Raft/2PC/TCC | Leader选举、日志复制、多数派 |
| NewSQL架构 | TiDB/CockroachDB/OceanBase | Region/Range、Percolator、HTAP |
| 分布式事务 | 2PC/Percolator/并行提交 | TSO、MVCC、写偏斜 |
| 工程选型 | 分库分表 vs NewSQL | 迁移风险评估、TCO对比 |

**分布式数据库面试三条线：**

1. **理论线**：CAP → BASE → 一致性模型 → 2PC → Paxos/Raft
2. **架构线**：分库分表 → 中间件 → TiDB → HTAP
3. **实践线**：SQL优化 → 分片策略 → 分布式事务 → 性能调优

---

> 🎯 **数据库面试八股文系列第（十一）篇完结！** 本文从CAP理论出发，系统讲解了Paxos/Raft一致性协议、TiDB/CockroachDB/OceanBase等NewSQL架构核心原理、分布式事务实现，以及面试高频考点。结合前10篇的单机数据库知识，你现在已经具备从MySQL到NewSQL的完整知识体系。
>
> 📌 **下期预告**：《数据库面试八股文（十二）——数据库安全与审计实战》将深入探讨SQL注入防御、数据加密（传输加密TLS/存储加密TDE）、审计日志与合规、权限管理最佳实践，以及GDPR对数据库设计的影响，敬请期待！
