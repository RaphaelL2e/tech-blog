---
title: "Redis 主从复制与高可用深度解析"
date: 2026-05-13T18:35:00+08:00
draft: false
categories: ["Redis"]
tags: ["Redis", "主从复制", "哨兵", "Redis Cluster", "高可用"]
---

# Redis 主从复制与高可用深度解析

## 一、引言

前面两篇我们分别深入探讨了 Redis 的数据结构、持久化机制和内存管理策略。在生产环境中，单节点 Redis 往往面临单点故障风险，无法满足高可用需求。本文将深入解析 Redis 的主从复制机制、哨兵高可用方案以及 Redis Cluster 分布式集群，帮助你在面试中系统回答 Redis 高可用相关问题。

**本文要点**：
1. 主从复制的原理与实现
2. 哨兵（Sentinel）机制详解
3. Redis Cluster 分布式方案
4. 高可用架构选型与实践

---

## 二、主从复制（Master-Slave Replication）

### 2.1 为什么需要主从复制

**单节点 Redis 的问题**：
- **单点故障**：主节点宕机，服务完全不可用
- **性能瓶颈**：单节点读写压力大，QPS 有限
- **数据安全**：无数据冗余，磁盘损坏导致数据丢失

**主从复制的价值**：
```
主节点（Master）  →  负责写操作
       ↓ 复制
从节点（Slave）   →  负责读操作（分担压力）
```

**核心作用**：
1. **数据冗余**：从节点备份主节点数据
2. **读写分离**：主写从读，提升整体性能
3. **高可用基础**：主节点故障，从节点可提升为主节点
4. **负载均衡**：多个从节点分担读请求

---

### 2.2 主从复制原理

#### 2.2.1 复制流程

Redis 主从复制分为两个阶段：

**阶段一：全量复制（Full Resynchronization）**

```
从节点启动 → 发送 PSYNC ? -1 → 主节点回复 FULLRESYNC <runid> <offset>
       ↓
主节点执行 BGSAVE → 生成 RDB 文件
       ↓
主节点将 RDB 文件发送给从节点
       ↓
从节点清空旧数据 → 加载 RDB 文件
       ↓
主节点将缓冲区（replication buffer）中的写命令发送给从节点
       ↓
从节点执行这些写命令，完成同步
```

**阶段二：部分复制（Partial Resynchronization）**

```
主从连接断开 → 从节点重连 → 发送 PSYNC <runid> <offset>
       ↓
主节点检查复制积压缓冲区（replication backlog）
       ↓
如果 offset 在 backlog 范围内 → 发送 +CONTINUE，只同步断开期间的增量数据
       ↓
如果 offset 不在 backlog 范围内 → 发送 +FULLRESYNC，触发全量复制
```

#### 2.2.2 核心概念

**1. runid（运行 ID）**

- 每个 Redis 节点启动时会生成一个 40 位的随机字符串作为 runid
- 从节点通过 runid 识别主节点是否发生变化
- 如果主节点重启，runid 变化，触发全量复制

**查看 runid**：
```bash
redis-cli INFO server | grep run_id
# run_id: e7b1b9e3f8a5c6d7e8f9a0b1c2d3e4f5a6b7c8
```

**2. 复制偏移量（replication offset）**

- 主节点和从节点都维护一个复制偏移量
- 主节点每次向从节点发送 N 字节数据，offset +N
- 从节点每次接收 N 字节数据，offset +N
- 通过对比 offset 判断主从数据是否一致

**查看 offset**：
```bash
# 主节点
redis-cli INFO replication | grep master_repl_offset
# master_repl_offset: 12345

# 从节点
redis-cli INFO replication | grep master_repl_offset
# master_repl_offset: 12345  （应该相同）
```

**3. 复制积压缓冲区（replication backlog）**

- 主节点维护的一个固定长度（默认 1MB）的 FIFO 队列
- 保存最近传播的写命令
- 用于支持部分复制（PSYNC）

**配置**：
```bash
# redis.conf
repl-backlog-size 10mb    # 积压缓冲区大小
repl-backlog-ttl 3600     # 所有从节点断开后，backlog 保留时间（秒）
```

---

### 2.3 主从复制配置

#### 2.3.1 从节点配置

**方法一：配置文件**

```bash
# 从节点 redis.conf
replicaof 192.168.1.100 6379   # 指定主节点 IP 和端口
masterauth yourpassword          # 如果主节点有密码
replica-read-only yes            # 从节点只读（默认开启）
```

**方法二：命令行动态配置**

```bash
# 在从节点执行
SLAVEOF 192.168.1.100 6379

# 取消复制（不会清空数据）
SLAVEOF NO ONE
```

#### 2.3.2 主节点配置

```bash
# redis.conf
requirepass yourpassword     # 设置密码
masterauth yourpassword      # 从节点连接时需要的密码

# 限制从节点数量（可选）
repl-diskless-sync no       # 是否启用无盘复制（直接通过网络发送 RDB）
repl-diskless-sync-delay 5  # 无盘复制延迟（等待更多从节点连接）
```

---

### 2.4 主从复制的演进

#### 2.4.1 Redis 2.8 之前（SYNC 命令）

**问题**：每次重连都触发全量复制，效率低。

```
从节点发送 SYNC → 主节点 BGSAVE → 传输 RDB → 传输缓冲区命令
```

**缺点**：
- 无论网络断开多久，都全量复制
- 主节点频繁 BGSAVE，消耗 CPU 和内存
- 网络闪断也会导致全量复制

#### 2.4.2 Redis 2.8+（PSYNC 命令）

引入 `PSYNC` 命令，支持部分复制：

```
PSYNC <runid> <offset>

# 首次复制：PSYNC ? -1
# 断线重连：PSYNC <runid> <offset>
```

**核心改进**：
- 通过 runid + offset 判断是否支持部分复制
- 利用 replication backlog 缓冲区实现增量同步
- 只有 offset 不在 backlog 中时才触发全量复制

---

### 2.5 主从复制的问题

**1. 手动故障转移**

- 主节点故障后，需要手动将一个从节点提升为主节点
- 需要修改应用侧的连接配置
- 故障恢复时间长

**2. 写能力受限**

- 主从复制只有主节点可写
- 写 QPS 受限于单节点性能

**3. 存储容量受限**

- 所有节点存储相同的数据
- 无法扩展存储容量

**解决方案**：引入哨兵机制实现自动故障转移，引入 Redis Cluster 实现分布式存储。

---

## 三、哨兵机制（Redis Sentinel）

### 3.1 为什么需要哨兵

主从复制解决了数据冗余和读写分离，但**无法实现自动故障转移**。哨兵（Sentinel）是 Redis 官方提供的高可用方案。

**哨兵的核心功能**：
1. **监控（Monitoring）**：定期检查主从节点是否正常运行
2. **通知（Notification）**：当节点故障时，发送通知
3. **自动故障转移（Automatic Failover）**：主节点故障时，自动提升从节点为主节点
4. **配置提供者（Configuration Provider）**：客户端通过哨兵获取当前主节点地址

---

### 3.2 哨兵架构

```
                ┌─────────┐
                │ Sentinel │
                │  集群   │
                └────┬────┘
                     │ 监控
         ┌───────────┼───────────┐
         ↓           ↓           ↓
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ Master  │ │ Slave 1 │ │ Slave 2 │
    │  (主)   │ │  (从)   │ │  (从)   │
    └─────────┘ └─────────┘ └─────────┘
```

**关键点**：
- 哨兵本身也是一个分布式系统，通常部署 **3 个或奇数个**节点
- 哨兵之间也会互相监控，形成哨兵集群
- 客户端不直接连接 Redis，而是先连接哨兵获取主节点地址

---

### 3.3 哨兵核心原理

#### 3.3.1 主观下线与客观下线

**主观下线（Subjectively Down, SDOWN）**：

- 单个哨兵认为主节点不可用
- 哨兵每秒向主节点发送 PING 命令
- 如果 `down-after-milliseconds` 毫秒内未收到有效回复，标记为主观下线

**客观下线（Objectively Down, ODOWN）**：

- 多个哨兵（达到 `quorum` 配置）都认为主节点不可用
- 哨兵之间通过 `SENTINEL is-master-down-by-addr` 命令互相确认
- 只有达到客观下线，才会触发故障转移

**配置示例**：
```bash
# sentinel.conf
sentinel monitor mymaster 192.168.1.100 6379 2
# ↑ 监控名为 mymaster 的主节点，2 表示 quorum=2（至少 2 个哨兵确认才能客观下线）

sentinel down-after-milliseconds mymaster 5000
# ↑ 5 秒无响应判定为下线
```

#### 3.3.2 哨兵领导者选举

当主节点被判定为客观下线后，哨兵集群需要选举一个**领导者（Leader）**来执行故障转移。

**选举算法：Raft 协议**

```
1. 每个哨兵都有资格成为 Leader
2. 哨兵 A 向其他哨兵发送 `is-master-down-by-addr` 命令，要求投票
3. 每个哨兵只能投一次票（先到先得）
4. 获得多数票（majority）的哨兵成为 Leader
5. 如果没有哨兵获得多数票，等待随机时间后重新选举
```

**majority 计算**：
```
哨兵总数 = 3，majority = 2
哨兵总数 = 4，majority = 3
哨兵总数 = 5，majority = 3
```

#### 3.3.3 故障转移流程

```
1. 哨兵 Leader 从从节点中选出一个作为新主节点
   选择优先级：
   a. 排除不健康的从节点（下线、断线）
   b. 选择 replication offset 最大的从节点（数据最新）
   c. 如果 offset 相同，选择 runid 字典序最小的

2. Leader 向选中的从节点发送 SLAVEOF NO ONE 命令，使其成为主节点

3. Leader 向其他从节点发送 SLAVEOF <new-master-ip> <new-master-port>

4. Leader 更新哨兵配置，将旧主节点标记为从节点（旧主恢复后可自动同步新主）

5. Leader 通过 Pub/Sub 通知客户端主节点变更
```

---

### 3.4 哨兵配置与实践

#### 3.4.1 哨兵配置文件

```bash
# sentinel.conf
port 26379                               # 哨兵默认端口
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel auth-pass mymaster yourpassword  # 主节点密码
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000  # 故障转移超时时间
sentinel parallel-syncs mymaster 1       # 故障转移时，同时对新主进行同步的从节点数
```

**参数说明**：

- `sentinel monitor <master-name> <ip> <port> <quorum>`
  - quorum：确认主节点下线的哨兵最小数量
  - 注意：quorum 只用于判定下线，故障转移需要 majority

- `sentinel parallel-syncs <master-name> <num>`
  - 故障转移后，同时从新主同步数据的从节点数
  - 设为 1：一个一个同步，对主节点压力小
  - 设为较大值：并行同步，从节点恢复更快，但主节点压力更大

#### 3.4.2 启动哨兵

```bash
# 方法一：直接使用 redis-sentinel 可执行文件
redis-sentinel /path/to/sentinel.conf

# 方法二：使用 redis-server 的 sentinel 模式
redis-server /path/to/sentinel.conf --sentinel
```

#### 3.4.3 哨兵命令行操作

```bash
# 连接哨兵
redis-cli -p 26379

# 查看主节点信息
SENTINEL master mymaster

# 查看从节点列表
SENTINEL slaves mymaster

# 查看哨兵列表
SENTINEL sentinels mymaster

# 获取当前主节点地址
SENTINEL get-master-addr-by-name mymaster
# → "127.0.0.1" "6379"

# 强制故障转移（无需主节点真实故障）
SENTINEL failover mymaster
```

---

### 3.5 哨兵机制的不足

**1. 写能力受限**

- 仍然只有单个主节点处理写请求
- 写 QPS 有上限

**2. 存储容量受限**

- 所有节点存储全量数据
- 数据量受限于单节点内存

**3. 客户端需要支持哨兵协议**

- 客户端需要连接哨兵获取主节点地址
- 部分老旧客户端不支持

**解决方案**：Redis Cluster 分布式集群。

---

## 四、Redis Cluster 分布式集群

### 4.1 为什么需要 Redis Cluster

哨兵机制解决了高可用问题，但无法解决**水平扩展**问题。Redis Cluster 是 Redis 官方提供的分布式解决方案。

**Redis Cluster 的核心目标**：
1. **数据分片**：数据分散到多个节点，突破单节点内存限制
2. **高可用**：主节点故障自动切换
3. **性能提升**：多个主节点同时处理写请求，提升整体写能力

---

### 4.2 Redis Cluster 架构

```
            ┌────────────────────────────────────┐
            │       Redis Cluster (去中心化)      │
            └────────────────────────────────────┘
                     ↓ Gossip 协议通信
    ┌───────────────┬───────────────┬───────────────┐
    │   Master A    │   Master B    │   Master C    │
    │  Slot 0-5460 │  Slot 5461-   │  Slot 10923-  │
    │               │  10922        │  16383        │
    ├───────────────┼───────────────┼───────────────┤
    │   Slave A1    │   Slave B1    │   Slave C1    │
    │  (A 的备份)   │  (B 的备份)   │  (C 的备份)   │
    └───────────────┴───────────────┴───────────────┘
```

**核心特点**：
- **去中心化**：无中心节点，每个节点平等
- **数据分片**：16384 个槽位（slot），分布到多个主节点
- **Gossip 协议**：节点之间互相通信，传播集群状态
- **客户端直连**：客户端直接连接任意节点，节点会转发请求到正确节点

---

### 4.3 数据分片原理

#### 4.3.1 槽位（Slot）分配

Redis Cluster 有 **16384 个哈希槽**（0 ~ 16383）。

**分配规则**：
```
每个键通过 CRC16 算法计算哈希值，再对 16384 取模：
slot = CRC16(key) % 16384

每个主节点负责一部分槽位。
例如：3 个主节点
  - Master A: Slot 0 ~ 5460
  - Master B: Slot 5461 ~ 10922
  - Master C: Slot 10923 ~ 16383
```

**查看槽位分配**：
```bash
redis-cli CLUSTER SLOTS
# 1) 1) (integer) 0          ← 起始槽位
#    2) (integer) 5460       ← 结束槽位
#    3) 1) "127.0.0.1"      ← 主节点 IP
#       2) (integer) 7000    ← 主节点端口
#       3) "e7b1b9e3..."     ← 节点 runid
#    4) 1) "127.0.0.1"      ← 从节点 IP
#       2) (integer) 7003
#       3) "f8c2d0a1..."
```

#### 4.3.2 键与槽位的映射

**普通键**：
```
SET key1 value1
→ CRC16("key1") % 16384 = 1252
→ Slot 1252 属于 Master A → 存储在 Master A
```

**哈希标签（Hash Tag）**：

为了确保相关键在同一个槽位（支持多键操作），可以使用哈希标签：

```
SET user:{1001}:name "Alice"    → 只对 {1001} 计算 slot
SET user:{1001}:age 30          → 只对 {1001} 计算 slot
HGETALL user:{1001}:*           → 多键操作，确保在同一个节点

# 花括号 {} 中的内容用于计算 slot
# 上面两个键都会映射到同一个 slot
```

---

### 4.4 请求路由与重定向

#### 4.4.1 MOVED 重定向

```
客户端请求 → 连接 Node A
    ↓
Node A 计算键对应的 Slot
    ↓
如果 Slot 属于 Node A → 直接处理
如果 Slot 属于 Node B → 返回 MOVED 错误，告知客户端正确的节点地址
    ↓
客户端收到 MOVED 后，重新向 Node B 发送请求
```

**示例**：
```bash
# 客户端连接 127.0.0.1:7000
127.0.0.1:7000> SET key1 value1
(error) MOVED 1252 127.0.0.1:7001
# ↑ 键 key1 属于 Slot 1252，应该存储在 127.0.0.1:7001

# 客户端重新连接 127.0.0.1:7001
127.0.0.1:7001> SET key1 value1
OK
```

#### 4.4.2 ASK 重定向

**场景**：槽位迁移过程中（重新分片），部分数据已经迁移到新节点，部分还在旧节点。

```
客户端请求 → Node A（正在迁出 Slot）
    ↓
如果键还在 Node A → 直接返回
如果键已经迁移到 Node B → 返回 ASK 重定向
    ↓
客户端收到 ASK 后，先向 Node B 发送 ASKING 命令，再发送原命令
```

**ASK vs MOVED**：

| 重定向类型 | 含义 | 客户端行为 |
|-----------|------|-----------|
| MOVED | 槽位已经永久迁移到新节点 | 更新本地槽位映射缓存，后续直接访问新节点 |
| ASK | 槽位正在迁移中，本次请求需要去新节点 | 只本次重定向，不更新本地缓存 |

---

### 4.5 集群管理

#### 4.5.1 创建集群

**方法一：使用 redis-cli（推荐）**

```bash
# 1. 启动 6 个 Redis 节点（3 主 3 从）
# 每个节点的 redis.conf 需要开启集群模式：
# cluster-enabled yes
# cluster-config-file nodes.conf
# cluster-node-timeout 5000

# 2. 创建集群
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1
# ↑ --cluster-replicas 1 表示每个主节点有 1 个从节点

# 3. 检查集群状态
redis-cli --cluster check 127.0.0.1:7000
```

**方法二：手动分配槽位**

```bash
# 1. 启动所有节点（cluster-enabled yes）
# 2. 为每个主节点分配槽位
redis-cli -p 7000 CLUSTER ADDSLOTS {0..5460}
redis-cli -p 7001 CLUSTER ADDSLOTS {5461..10922}
redis-cli -p 7002 CLUSTER ADDSLOTS {10923..16383}

# 3. 设置从节点（在从节点执行）
CLUSTER REPLICATE <master-node-id>
```

#### 4.5.2 扩缩容

**添加新节点**：

```bash
# 1. 启动新节点
redis-server /path/to/redis-7006.conf

# 2. 将新节点加入集群
redis-cli --cluster add-node 127.0.0.1:7006 127.0.0.1:7000
# ↑ 第一个参数：新节点地址  第二个参数：集群中任意节点地址

# 3. 重新分片（将数据迁移一部分到新节点）
redis-cli --cluster reshard 127.0.0.1:7000
# 交互式询问：
# How many slots do you want to move? 1000
# What is the receiving node ID? <new-node-id>
# Source node #1: all   （从所有主节点抽取槽位）
```

**删除节点**：

```bash
# 1. 如果是从节点，直接删除
redis-cli --cluster del-node 127.0.0.1:7000 <node-id>

# 2. 如果是主节点，先迁移槽位
redis-cli --cluster reshard 127.0.0.1:7000
# 将槽位全部分配给其他主节点

# 3. 再删除节点
redis-cli --cluster del-node 127.0.0.1:7000 <node-id>
```

---

### 4.6 故障转移

Redis Cluster 也使用哨兵类似的思想实现高可用，但**不需要单独的哨兵进程**。

**故障检测**：

```
1. 节点 A 向节点 B 发送 PING
2. 如果节点 B 在 node-timeout 时间内未回复，节点 A 标记节点 B 为 PFAIL（可能失败）
3. 节点 A 通过 Gossip 协议将节点 B 的 PFAIL 状态传播给其他节点
4. 当超过半数主节点都认为节点 B 是 PFAIL，标记为 FAIL（确定失败）
```

**故障转移**：

```
1. 从节点检测到主节点 FAIL
2. 从节点发起选举（类似哨兵选举）
3. 获得多数主节点投票的从节点成为新主节点
4. 其他从节点开始复制新主节点
```

---

### 4.7 Redis Cluster 的限制

**1. 不支持多键操作（除非使用 Hash Tag）**

```bash
# 错误示例：key1 和 key2 可能不在同一个节点
MSET key1 value1 key2 value2   # 报错：(error) CROSSSLOT

# 正确做法：使用 Hash Tag
MSET user:{1001}:name "Alice" user:{1001}:age 30
```

**2. 不支持多数据库（只有 db 0）**

```bash
# 在 Cluster 模式下，以下命令无效
SELECT 1   # 报错
```

**3. 事务支持有限**

- 只有在同一个槽位中的键才能使用事务（MULTI/EXEC）
- 跨槽位无法使用事务

**4. 客户端复杂度增加**

- 客户端需要维护槽位映射关系
- 需要处理 MOVED / ASK 重定向
- 部分客户端对 Cluster 支持不完善

---

## 五、高可用架构选型

### 5.1 主从复制 + 哨兵 vs Redis Cluster

| 维度 | 主从 + 哨兵 | Redis Cluster |
|------|------------|---------------|
| **数据分片** | ❌ 无（全量存储） | ✅ 有（16384 槽位） |
| **写能力扩展** | ❌ 单主节点写 | ✅ 多主节点写 |
| **存储容量** | ❌ 受限于单节点 | ✅ 水平扩展 |
| **复杂度** | 低 | 高 |
| **客户端支持** | 广泛 | 需要支持 Cluster 协议 |
| **适用场景** | 数据量小、高可用需求 | 大数据量、高写 QPS |

### 5.2 实践建议

**场景一：小型应用（数据 < 10GB）**

```
方案：主从复制 + 哨兵（3 个哨兵）
主节点：写请求
从节点：读请求 + 备份
```

**场景二：中型应用（10GB < 数据 < 50GB）**

```
方案：Redis Cluster（3 主 3 从）
每个主节点约 10-15GB 数据
```

**场景三：大型应用（数据 > 50GB）**

```
方案：Redis Cluster（6 主 6 从或更多）
结合客户端分片（应用层分片 + Cluster 分片）
```

---

## 六、面试高频问题

### Q1: 主从复制和哨兵的区别？

**答案要点**：
- 主从复制：数据冗余 + 读写分离，无法自动故障转移
- 哨兵：基于主从复制，提供自动故障转移和高可用
- 两者结合：主从复制负责数据同步，哨兵负责高可用

### Q2: 哨兵选举 Leader 的过程？

**答案要点**：
- 使用 Raft 协议
- 每个哨兵都可以成为 Leader
- 先到先得，每个哨兵只能投一票
- 获得 majority（多数票）的哨兵成为 Leader

### Q3: Redis Cluster 的槽位为什么是 16384？

**答案要点**：
- 2^14 = 16384，方便位运算
- 16384 足够分散数据，同时不会太多导致元数据过大
- Gossip 协议传播槽位信息，16384 个槽位的位图（bitmap）只有 2KB

### Q4: MOVED 和 ASK 的区别？

**答案要点**：
- MOVED：槽位已经永久迁移，客户端应更新本地缓存
- ASK：槽位正在迁移中，仅本次请求重定向，不更新缓存

### Q5: Redis Cluster 为什么不支持多键操作？

**答案要点**：
- 多键可能分布在不同的槽位，不同的槽位属于不同的节点
- 跨节点操作需要 Move 重定向，无法在一个节点完成
- 解决方案：使用 Hash Tag 确保相关键在同一个槽位

---

## 七、总结

本文深入探讨了 Redis 的高可用架构：

1. **主从复制**：数据冗余 + 读写分离，通过 PSYNC 实现部分复制
2. **哨兵机制**：监控 + 自动故障转移，基于 Raft 协议选举 Leader
3. **Redis Cluster**：分布式集群，16384 槽位分片，支持水平扩展
4. **架构选型**：小数据用哨兵，大数据用 Cluster

**关键数字记忆**：
- 哨兵端口：26379
- 复制积压缓冲区：默认 1MB
- Cluster 槽位：16384
- 哨兵 quorum：确认下线的哨兵数
- 哨兵 majority：选举 Leader 需要的票数

下一篇我们将探讨 **Redis 缓存问题（穿透、击穿、雪崩）与解决方案**，这是面试中极高概率的问题，敬请期待。

---

*作者：亚飞的技术笔记 | 公众号：亚飞的技术笔记*
