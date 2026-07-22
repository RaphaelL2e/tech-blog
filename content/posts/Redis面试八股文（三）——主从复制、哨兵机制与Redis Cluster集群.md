---
title: Redis面试八股文（三）——主从复制、哨兵机制与Redis Cluster集群
date: 2026-06-22 09:00:00+08:00
updated: '2026-06-22T09:00:00+08:00'
description: 🎯 本文目标：承接上一篇持久化与内存管理的单机视角，本文将上升到分布式架构层面，深入Redis主从复制的全量/部分同步机制、Sentinel哨兵的主观下线与客观下线判定、Redis Cluster的16384槽位分配与MOVED/ASK重定向、Gossip协议节点通信等核心高可用与集群技术，构建完整。
topic: database-middleware
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Redis
- 主从复制
- 哨兵
categories:
- 数据库与中间件
draft: false
---

> 🎯 **本文目标**：承接上一篇持久化与内存管理的单机视角，本文将上升到分布式架构层面，深入Redis主从复制的全量/部分同步机制、Sentinel哨兵的主观下线与客观下线判定、Redis Cluster的16384槽位分配与MOVED/ASK重定向、Gossip协议节点通信等核心高可用与集群技术，构建完整的分布式Redis知识体系。

---

## 一、主从复制——数据冗余的基石

### 1.1 为什么需要主从复制？

**Q: Redis主从复制解决了什么问题？**

| 问题 | 单机瓶颈 | 主从复制方案 |
|------|----------|-------------|
| 数据安全 | 单点故障数据全丢 | 从节点持久化备份 |
| 读压力 | 单机QPS上限10万+ | 读写分离，从节点分担读 |
| 高可用 | 宕机即不可用 | 配合哨兵自动故障转移 |
| 异地容灾 | 无灾备能力 | 跨机房异步复制 |

**主从架构的核心矛盾：**

```
CAP理论在Redis主从中的体现：

        C(强一致性)
       /\
      /  \
     /    \
    /  主从复制 \
   /   (默认异步) \
  A ──────────────── P
(单机可用性)      (主从分区容忍性)

Redis主从默认选择了AP：异步复制牺牲了C
```

### 1.2 主从复制的完整流程

**Q: Redis主从复制的完整流程是怎样的？**

主从复制分为**三个阶段**，不同阶段采用不同的同步策略：

```
第一阶段：建立连接 → 第二阶段：数据同步 → 第三阶段：命令传播

主节点                    从节点
  │                         │
  │     <── SLAVEOF ───    │  1. 发送SYNC/PSYNC命令
  │                         │
  │  2. bgsave生成RDB快照  │
  │  同时记录replication   │
  │  buffer中的写命令      │
  │                         │
  │  ──── 发送RDB ────►   │  3. 清空旧数据，加载RDB
  │                         │
  │  ──── 发送buffer ──►   │  4. 执行buffer中的命令
  │                         │
  │  ──── 持续传播写命令 ─► │  5. 进入命令传播阶段
  │                         │
```

**详细步骤拆解（七步同步法）：**

```
Step 1: 从节点执行 REPLCONF 声明端口和IP
        ↓
Step 2: 从节点发送 PSYNC <replid> <offset>
        ↓ 
Step 3: 主节点判断同步策略：
        ├── 全量同步：replid不同 或 offset不在复制积压缓冲区
        └── 部分同步：replid相同 且 offset在复制积压缓冲区内
        ↓
Step 4: 主节点执行bgsave生成RDB快照
        ↓
Step 5: 主节点发送RDB文件给从节点
        同时将所有新写命令写入client-output-buffer-limit
        ↓
Step 6: 从节点清空旧数据，加载RDB文件
        ↓
Step 7: 主节点发送积压的写命令，完成追齐后进入命令传播阶段
```

### 1.3 全量同步 vs 部分同步

**Q: PSYNC的全量同步和部分同步有什么区别？**

| 对比维度 | 全量同步（Full Resync） | 部分同步（Partial Resync） |
|----------|------------------------|---------------------------|
| 触发条件 | 首次复制 / replid不同 / offset丢失 | 网络闪断恢复，offset在缓冲区内 |
| 数据量 | 全部数据（可能几十GB） | 仅增量数据（几十KB~几MB） |
| 磁盘开销 | 主节点bgsave产生RDB文件 | 仅内存缓冲区读取 |
| CPU开销 | 高（fork子进程生成RDB） | 低（内存操作） |
| 网络带宽 | 大量数据传输 | 少量数据传输 |
| 恢复时间 | 分钟~小时级 | 秒级 |

**复制积压缓冲区（replication backlog）的核心机制：**

```
复制积压缓冲区（默认1MB，由repl-backlog-size配置）：

┌────────────────────────────────────────────────┐
│  复制积压缓冲区 (FIFO环形队列)                    │
│                                                  │
│  offset=1000  offset=2000  offset=3000          │
│  [ SET k1 v1 ][ SET k2 v2 ][ INCR cnt ]...     │
│                                                  │
│  每个字节都有全局唯一的offset编号                │
│  主节点维护 repl_backlog + master_repl_offset    │
│  从节点维护 slave_repl_offset                    │
└────────────────────────────────────────────────┘

判断逻辑：
if (slave_repl_offset >= repl_backlog_first_byte_offset) {
    → 部分同步（Partial Resync）
} else {
    → 全量同步（Full Resync）
}
```

**repl_backlog_size的配置建议：**

```bash
# 计算公式：repl_backlog_size = 主节点每秒写入量 × 断线重连时间(秒)

# 例子：假设QPS=1000，每条命令100字节，允许断线1小时
# 需要：1000 × 100 × 3600 = 360MB

# 配置示例
repl-backlog-size 512mb
repl-backlog-ttl 3600  # 主节点无slave多久后释放backlog
```

### 1.4 replication buffer与client-output-buffer-limit

**Q: 全量同步时主节点的输出缓冲区有什么风险？**

全量同步时，主节点会将生成的RDB和期间的写命令都放入从节点的客户端输出缓冲区。如果RDB生成太慢或网络传输太慢，缓冲区会持续增长：

```
风险场景：
  ├── 大RDB生成慢（如32GB内存的bgsave需数十秒）
  ├── 网络带宽不足，RDB传输慢
  └── 期间写流量大，积压命令多
      ↓
  client-output-buffer-limit 溢出
      ↓
  主节点强制断开从节点连接
      ↓
  从节点重连 → 再次全量同步 → 无限循环

配置硬/软限制：
client-output-buffer-limit slave 256mb 64mb 60
# 硬限制：超过256MB立即断开
# 软限制：超过64MB持续60秒后断开
```

### 1.5 主从复制的三大问题

**问题一：数据不一致**

```
原因：
  ├── 异步复制：主节点写入成功但未同步到从节点即返回客户端
  │   主节点宕机 → 从节点提升为主 → 数据丢失
  │
  └── 脑裂（split-brain）场景：
      主节点网络分区但仍接收写请求
      Sentinel选出新主节点
      旧主恢复 → 数据冲突

缓解方案：
  min-replicas-to-write 1    # 至少1个从节点在线才接受写
  min-replicas-max-lag 10    # 从节点延迟不超过10秒
```

**问题二：复制风暴**

```
场景：一主多从架构中主节点重启
  ├── 所有从节点同时发起全量同步
  ├── 主节点bgsave消耗大量CPU和IO
  └── RDB文件同时传输→网络拥塞

解决方案：
  └── 树形复制拓扑（级联复制）：
       Master
        ├── Slave1
        │    ├── Slave1-1
        │    └── Slave1-2
        └── Slave2
             ├── Slave2-1
             └── Slave2-2
```

**问题三：主从切换的数据丢失**

```
异步复制的数据丢失窗口：
  时间线：
  T1: 主节点写入成功（返回OK给客户端）
  T2: 主节点宕机（尚未同步到从节点）
  T3: Sentinel提升从节点为主
  → 客户端认为写入成功的数据丢失了

这是Redis默认配置下必然存在的风险，本质是AP模型的选择。
```

---

## 二、Sentinel哨兵机制——自动故障转移

### 2.1 Sentinel架构概览

**Q: Sentinel是什么？解决了什么问题？**

| 能力 | Sentinel提供 | 无Sentinel |
|------|-------------|------------|
| 监控 | 持续检查主从节点是否可用 | 手动检查 |
| 通知 | 通过API通知管理员 | 无 |
| 自动故障转移 | 自动提升从节点为主 | 手动操作 |
| 配置提供者 | 客户端通过Sentinel发现主节点 | 硬编码IP |

**Sentinel的分布式架构：**

```
┌─────────────────────────────────────────────────────────┐
│                    Sentinel集群（建议≥3个）                │
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │Sentinel 1│   │Sentinel 2│   │Sentinel 3│            │
│  │ :26379   │   │ :26380   │   │ :26381   │            │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘            │
│       │              │              │                   │
│       └──────────────┼──────────────┘                   │
│                      │                                  │
│              ┌───────┴───────┐                          │
│              │   Redis主节点  │                          │
│              │    :6379      │                          │
│              └───────┬───────┘                          │
│                      │                                  │
│         ┌────────────┼────────────┐                     │
│    ┌────┴─────┐ ┌────┴─────┐ ┌───┴──────┐              │
│    │ Redis从1 │ │ Redis从2 │ │ Redis从3 │              │
│    │ :6380    │ │ :6381    │ │ :6382    │              │
│    └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 主观下线（SDOWN）vs 客观下线（ODOWN）

**Q: Sentinel如何判断节点真正下线了？两步判定机制是什么？**

这是Redis面试高频题，必须理解SDOWN和ODOWN的区别：

```
主观下线（Subjectively Down, SDOWN）：
  └── 单个Sentinel节点通过PING判断目标不可达
      判断条件：PING超时（down-after-milliseconds内无响应）
      此时仅这个Sentinel认为它下线了

客观下线（Objectively Down, ODOWN）：
  └── 多个Sentinel（≥quorum个）都认为主节点SDOWN
      通过 is-master-down-by-addr 命令交换意见
      只有达到quorum数量，才执行故障转移
```

**ODOWN的投票机制详解：**

```
场景：5个Sentinel，quorum=3

Sentinel-1: 检测到主节点PING超时
  ├── 标记本地SDOWN
  │
  ├── 向其他Sentinel发送: SENTINEL is-master-down-by-addr <ip> <port>
  │   询问："你们也认为这个主节点挂了吗？"
  │
  ├── Sentinel-2回复: "是，我也认为它SDOWN"
  ├── Sentinel-3回复: "是，我也认为它SDOWN"
  ├── Sentinel-4回复: "不，我刚PING通了"
  └── Sentinel-5回复: "是，我也认为它SDOWN"
  
  → 收集到3票（含自己）= quorum=3
  → 标记ODOWN
  → 启动故障转移流程
```

**down-after-milliseconds参数的含义：**

```
注意：这个参数有两个含义！

对主节点：
  └── 判定SDOWN的超时时间
     PING无响应超过这个时间 → 标记SDOWN

对从节点和其他Sentinel：
  └── 判定SDOWN的超时时间
     同时对从节点，还决定了：
     "主节点ODOWN后，从节点多久没响应也认为不可用"
     → 该从节点不会被选为新的主节点
     
配置示例：
sentinel down-after-milliseconds mymaster 30000  # 30秒
```

### 2.3 故障转移完整流程

**Q: 从ODOWN判定到完成故障切换，Sentinel做了哪些事？**

```
完整故障转移流程（9步）：

第一阶段：选举Leader Sentinel
  Step 1: 发现ODOWN的Sentinel向其他Sentinel发起"我要求成为Leader"
          使用Raft-like协议：先到先得，每个Sentinel只投一票
  Step 2: 获得 ≥ max(quorum, N/2+1) 票的成为Leader
  Step 3: 如果选举失败，等待2秒后重试

第二阶段：选择新主节点
  Step 4: Leader从所有从节点中筛选合格候选者：
          过滤规则：
          ├── 排除：SDOWN、断线超过5秒、INFO回复超时
          ├── 优先级排序（多级排序）：
          │   ① slave-priority（数字越小越优先，0=永不选为master）
          │   ② 复制偏移量（offset越大越优先）
          │   ③ runid（字典序小的优先，作为tie-breaker）
          └── 选出最优从节点
  
  Step 5: 对选中从节点发送 SLAVEOF NO ONE
          从节点变为独立主节点

第三阶段：重新配置拓扑
  Step 6: Leader向其他从节点发送 SLAVEOF <新主IP> <新主端口>
          其他从节点开始复制新主节点
  
  Step 7: Leader将旧主节点（如恢复）降级为从节点
          SLAVEOF <新主IP> <新主端口>
          或记录在sentinel配置中，待旧主上线后执行

第四阶段：通知客户端
  Step 8: 通过Pub/Sub通知所有订阅的客户端
          +switch-master <name> <old-ip> <old-port> <new-ip> <new-port>
  
  Step 9: 更新sentinel.conf配置文件
          记录最新的主节点信息
```

**Sentinel Leader选举的Raft-like协议详解：**

```
为什么需要选举Leader？
  └── 避免多个Sentinel同时执行故障转移导致混乱

选举算法（借鉴Raft的leader election）：
  ┌──────────────────────────────────────────┐
  │ epoch：单调递增的逻辑时钟（类似Raft term） │
  │ 每个Sentinel在每个epoch只能投一次票       │
  └──────────────────────────────────────────┘

投票规则：
1. 每个Sentinel向其他节点请求投票（携带自己的epoch和runid）
2. 收到请求的Sentinel判断：
   - 请求的epoch >= 自己的epoch → 可以投票
   - 自己在这个epoch还没投过票 → 可以投票
   - 先到先得原则
3. 候选者获得:
   - ≥ max(quorum, N/2+1) 票 → 成为Leader
   - 否则 → 等待2秒重试（epoch+1）

特殊规则：
  - 如果Sentinel发现更高的epoch，更新自己的epoch
  - 如果epoch相同但收到多个请求，只投给最先到达的
```

### 2.4 Sentinel的三大定时任务

**Q: Sentinel内部有哪些定时任务？**

```c
// Sentinel的三大核心定时任务

1. 每10秒一次：INFO命令
   目标：主节点和从节点
   目的：
     ├── 发现新加入的从节点
     ├── 获取主从复制状态
     └── 更新各节点的角色信息

2. 每2秒一次：对主节点的Pub/Sub
   频道：__sentinel__:hello
   目的：
     ├── 发现其他Sentinel节点
     ├── 交换对主节点的判断
     └── 传递主节点的IP和配置epoch

3. 每1秒一次：PING命令
   目标：所有已知节点（主/从/Sentinel）
   目的：
     ├── 心跳检测节点存活
     └── 触发SDOWN判定
```

**三大定时任务的协同工作：**

```
时间线示意：
T+0s:   PING所有节点（每秒）
T+1s:   PING所有节点
T+2s:   PING所有节点 + Pub/Sub交换Sentinel信息
T+4s:   PING + Pub/Sub
T+6s:   PING + Pub/Sub
T+8s:   PING + Pub/Sub
T+10s:  PING + Pub/Sub + INFO获取拓扑信息
T+12s:  PING + Pub/Sub
...
T+30s:  某Sentinel发现主节点PING超时（down-after-ms=30000）
        → 标记SDOWN
        → 通过 is-master-down-by-addr 询问其他Sentinel
        → 如果达到quorum → 标记ODOWN → 启动故障转移
```

### 2.5 Sentinel的客户端发现机制

**Q: 客户端如何通过Sentinel发现主节点地址？**

```
客户端连接流程：

1. 客户端配置Sentinel地址列表（不是Redis地址！）
   sentinel://sentinel1:26379,sentinel2:26380,sentinel3:26381

2. 客户端轮询Sentinel列表，发送：
   SENTINEL get-master-addr-by-name mymaster

3. Sentinel返回当前主节点IP:Port

4. 客户端连接到主节点

5. 客户端订阅Sentinel的 +switch-master 频道

6. 主节点故障转移时：
   Sentinel发布 +switch-master 消息
   客户端收到通知 → 断开旧连接 → 重新获取新主节点地址 → 重连

Java客户端示例（Jedis/Lettuce都内置此机制）：
```

```java
// Jedis Sentinel连接池
Set<String> sentinels = new HashSet<>();
sentinels.add("192.168.1.1:26379");
sentinels.add("192.168.1.2:26379");
sentinels.add("192.168.1.3:26379");

JedisSentinelPool pool = new JedisSentinelPool(
    "mymaster", sentinels, 
    new GenericObjectPoolConfig(), 
    2000,  // connectionTimeout
    "password"
);

// 连接池内部会自动：
// 1. 从Sentinel发现主节点
// 2. 订阅+switch-master频道
// 3. 故障转移时自动刷新主节点地址
try (Jedis jedis = pool.getResource()) {
    jedis.set("key", "value");
}
```

---

## 三、Redis Cluster——分片集群

### 3.1 为什么需要Cluster？

**Q: 主从+哨兵架构的局限性是什么？Cluster如何解决？**

| 架构 | 主从+哨兵 | Redis Cluster |
|------|----------|---------------|
| 数据容量 | 受单机内存限制（>512G困难） | 水平扩展，N×单机容量 |
| 写入吞吐 | 单主写入，瓶颈在主节点 | 多主并行写入 |
| 高可用 | 哨兵自动故障转移 | 内置故障转移（去掉Sentinel） |
| 运维复杂度 | 需要独立部署Sentinel | 一体化，节点间自管理 |
| 数据分布 | 所有数据在主节点 | 数据按槽分布到不同主节点 |

**Redis Cluster的核心设计思想：去中心化**

```
传统分布式系统（中心化）：          Redis Cluster（去中心化）：
                                       
┌─────────────┐                   ┌──────┐  ┌──────┐  ┌──────┐
│   中心节点   │                   │ Node1│  │ Node2│  │ Node3│
│(MetaServer)│                    │  ┌──┐│  │  ┌──┐│  │  ┌──┐│
└──────┬──────┘                   │  │槽││  │  │槽││  │  │槽││
       │                          │  │ 0││  │  │ 5││  │  │10││
  ┌────┼────┐                     │  │ 1││  │  │ 6││  │  │11││
  │    │    │                     │  │..││  │  │..││  │  │..││
Node1 Node2 Node3                  │  └──┘│  │  └──┘│  │  └──┘│
                                   │      │  │      │  │      │
                                   └──┬───┘  └──┬───┘  └──┬───┘
                                      │         │         │
                                      └─────────┼─────────┘
                                          Gossip协议通信

无中心节点：每个节点都维护完整的集群拓扑
通过Gossip协议互相传播节点状态变化
```

### 3.2 16384槽位分配机制

**Q: 为什么是16384个槽？怎么计算key属于哪个槽？**

这是Cluster最核心的设计，面试必考：

```
为什么是16384（2^14）？

├── 心跳包大小考虑：
│   └── 槽位信息用bitmap表示：16384 bits = 2KB
│       心跳包含完整槽信息，2KB可以接受
│       如果是65536个槽：8KB，心跳包太大
│
├── 节点数考虑：
│   └── 建议节点数不超过1000个
│       16384 / 1000 ≈ 每个节点16个槽，粒度适中
│
└── CRC16的天然限制：
    └── CRC16算法的输出范围就是0~16383（2^16=65536，取高14位）
        HASH_SLOT = CRC16(key) & 16383
        恰好映射到16384个槽
```

**槽位计算的源码级理解：**

```c
// Redis源码 (cluster.c)
unsigned int keyHashSlot(char *key, int keylen) {
    int s, e; // start, end of hash tag
    
    // 支持hash tags: {user1000}.following → 只对user1000做hash
    for (s = 0; s < keylen; s++)
        if (key[s] == '{') break;
    
    if (s == keylen) {
        // 没有hash tag → 对整个key做CRC16
        return crc16(key, keylen) & 0x3FFF; // 0x3FFF = 16383
    }
    
    // 有hash tag → 只对{}内的内容做hash
    for (e = s+1; e < keylen; e++)
        if (key[e] == '}') break;
    
    if (e == keylen || e == s+1) {
        // 没有闭合的} 或 {}内为空 → 对整个key做hash
        return crc16(key, keylen) & 0x3FFF;
    }
    
    // 对{}内的内容做hash
    return crc16(key+s+1, e-s-1) & 0x3FFF;
}
```

**Hash Tags的妙用：**

```
通过{}可以控制不同key落到同一个槽：

不带hash tag：
  user:1000:name   → slot 3456
  user:1000:email  → slot 7890  ← 不同槽！无法用事务/管道

带hash tag：
  {user:1000}:name  → slot 5432
  {user:1000}:email → slot 5432  ← 相同槽！可以批量操作

用途：
  ├── 多key事务（MULTI/EXEC）
  ├── 批量操作（MGET/MSET）
  ├── Lua脚本中的多key操作
  └── 某些需要key在同一个节点的场景
```

**槽位重分配（Resharding）流程：**

```
在线迁移不中断服务：

节点A（迁移源：slot 1000）   →   节点B（迁移目标：slot 1000）

Step 1: 目标节点B执行：CLUSTER SETSLOT 1000 IMPORTING <nodeA-id>
        → 节点B准备接收slot 1000的数据

Step 2: 源节点A执行：CLUSTER SETSLOT 1000 MIGRATING <nodeB-id>
        → 节点A告知slot 1000正在迁移

Step 3: 通过 MIGRATE 命令逐个迁移key
        对slot 1000中的每个key：
        CLUSTER GETKEYSINSLOT 1000 <count>
        MIGRATE <host> <port> <key> 0 <timeout>

Step 4: 迁移完成，向所有节点广播：
        CLUSTER SETSLOT 1000 NODE <nodeB-id>
        → 更新整个集群的路由表

ASKING重定向机制（迁移过程中）：
  客户端请求slot 1000的key → 节点A
  ├── key还在节点A → 正常返回
  └── key已迁移到节点B → 返回 ASK 1000 <nodeB-ip>:<nodeB-port>
      客户端发送 ASKING + 重新请求 → 节点B返回数据
```

### 3.3 MOVED重定向 vs ASK重定向

**Q: MOVED和ASK有什么区别？面试高频！**

这是Cluster中最容易混淆的两个概念：

| 对比维度 | MOVED重定向 | ASK重定向 |
|----------|------------|----------|
| 含义 | 槽位**永久**迁移完成 | 槽位**正在**迁移中 |
| 时机 | 槽归属已变更 | 迁移过程中key已被移走 |
| 客户端行为 | 更新本地槽位映射表 | 仅本次重定向（不更新映射表） |
| 命令前缀 | 直接重新发送命令 | 先发送 ASKING，再发送命令 |
| 后续请求 | 直接请求新节点 | 仍请求原节点（绝大多数key还在） |

```
MOVED场景（槽迁移已完成）：
  CLIENT                         NodeA(旧)           NodeB(新)
    │                              │                    │
    │── GET user:1000 ────────────►│                    │
    │                              │ slot已分配给NodeB  │
    │◄── MOVED 5432 10.0.0.2:6379 │                    │
    │                              │                    │
    │  客户端更新本地slot映射：    │                    │
    │  slot 5432 → 10.0.0.2:6379 │                    │
    │                              │                    │
    │── GET user:1000 ────────────────────────────────►│
    │◄── "value" ─────────────────────────────────────│

ASK场景（槽迁移进行中）：
  CLIENT                         NodeA(迁移源)         NodeB(迁移目标)
    │                              │                    │
    │── GET user:1000 ────────────►│                    │
    │                              │ key已migrate到B    │
    │◄── ASK 5432 10.0.0.2:6379 ──│                    │
    │                              │                    │
    │  ！！！重要：不更新slot映射  │                    │
    │  因为大部分key还在NodeA     │                    │
    │                              │                    │
    │── ASKING ───────────────────────────────────────►│
    │── GET user:1000 ─────────────────────────────────►│
    │◄── "value" ──────────────────────────────────────│
    
    ASKING作用：绕过NodeB的MOVED检查
    通常NodeB收到不属于自己slot的请求会返回MOVED
    ASKING告诉NodeB："我知道这个key不属于我，但它在迁移中，帮我查一下"
    ASKING只生效一次，下次请求需要重新发送
```

### 3.4 Gossip协议——去中心化的核心

**Q: Redis Cluster节点间如何通信？Gossip协议的原理是什么？**

```
Gossip协议的本质：
  └── 每个节点定期随机选择其他节点，交换各自知道的信息
      类似病毒传播 → 最终所有节点收敛到一致状态

Redis Cluster的Gossip消息类型：

  MEET：
  └── 新节点加入集群时发送
      "你好，请把我加入你的节点列表"

  PING：
  └── 定期向其他节点发送心跳
      携带自身状态 + 已知的部分节点信息

  PONG：
  └── 响应PING/MEET
      同样携带自身状态 + 已知的部分节点信息

  FAIL：
  └── 确认某个节点已经下线
      需要半数以上主节点同意才广播

  PUBLISH：
  └── 发布/订阅消息在集群中的传播
```

**Gossip协议的消息传播机制：**

```
PING消息的节点选择策略（clusterCron定时器每秒10次）：

随机选取5个节点发送PING，其中：
  ├── 1个节点：从"最久未PING"的节点中选择
  │           （确保每个节点最终都能收到消息）
  └── 4个节点：随机选择
              （利用Gossip的随机性实现快速传播）

消息传播时间估算：
  假设N个节点，每个节点每100ms随机发1条消息
  ├── 一条消息传遍全集群：O(log N)轮
  │   类似传染病模型，第二轮就有N/2个节点知道
  └── 实际传播延迟：通常 < 1秒

Gossip的最终一致性保证：
  ├── 事件最终传播：每条消息最终传播到所有节点
  ├── ϕ-accrual故障检测：基于心跳间隔的动态阈值
  │   （自适应故障检测算法，比固定超时更准确）
  └── 反熵（Anti-Entropy）：定期全量同步节点信息
      即使Gossip丢失了某些更新，反熵过程也能修复
```

**Gossip消息的带宽估算：**

```
单个PING消息大小 ≈ 104字节（头部）+ N × 104字节（N个随机节点信息）

配置：cluster-node-timeout = 15000ms
      每秒10次PING

场景1：小集群（10个节点）
  每个PING携带全部节点信息：104 + 10×104 ≈ 1.1KB
  每秒发送：10次 × 1.1KB ≈ 11KB/s ← 可忽略

场景2：大集群（1000个节点）  
  每个PING携带部分节点信息（如10个）
  104 + 10×104 ≈ 1.1KB
  每秒发送：10次 × 1.1KB ≈ 11KB/s ← 仍可忽略

Redis Cluster之所以能扩展到1000节点，
核心原因就是Gossip的带宽消耗几乎不随节点数增长！
```

### 3.5 Cluster的故障检测与自动故障转移

**Q: Cluster如何检测和转移故障？和Sentinel有什么不同？**

```
故障检测的两阶段：

阶段一：PFail（Possible Failure - 疑似下线）
  └── 节点A向节点B发送PING，超过cluster-node-timeout未收到PONG
      → 节点A将节点B标记为PFail
      → 这相当于Sentinel的SDOWN

阶段二：Fail（确认下线）
  └── 节点A通过Gossip传播"节点B PFail"
      当半数以上主节点都认为节点B PFail
      → 某个主节点将节点B标记为Fail
      → 广播FAIL消息给所有节点
      → 所有收到FAIL的节点立即将B标记为下线
      → 这相当于Sentinel的ODOWN

与Sentinel的关键差异：
  Sentinel ODOWN：quorum个Sentinel投票（可能<半数）
  Cluster ODOWN：必须半数以上主节点同意（保证安全性）
```

**Cluster的自动故障转移流程：**

```
主节点B下线后的自动切换：

Step 1: B的从节点发现B已FAIL
        从节点通过clusterCron定时检查主节点状态

Step 2: 从节点等待 cluster-node-timeout × 2 后开始选举
        目的：等待Gossip传播，确保所有节点都知道B已下线

Step 3: 从节点增加自己的currentEpoch
        向所有主节点请求投票（FAILOVER_AUTH_REQUEST）

Step 4: 主节点投票规则：
        ├── 每个主节点在每个epoch只投一票
        ├── 只投给从节点（slave不能投票）
        └── 先到先得

Step 5: 获得 ≥ N/2+1（半数以上主节点）票数的从节点
        执行故障转移：
        ├── 提升自己为主节点
        ├── 接管原主节点的所有槽位
        └── 广播PONG消息通知所有节点

关键差异 vs Sentinel：
  ├── Sentinel有独立的Sentinel节点和Raft-like选举
  └── Cluster的选举内嵌在Redis节点中，投票者是所有主节点
```

### 3.6 集群伸缩——节点的添加与移除

**Q: 如何在线添加和移除节点？**

```
添加新节点的完整流程：

1. 启动新节点
   redis-server --port 6385 --cluster-enabled yes

2. 将新节点加入集群
   CLUSTER MEET <existing-node-ip> <existing-node-port>
   
   新节点通过Gossip获取完整集群信息

3. 重新分配槽位
   redis-cli --cluster reshard <new-node-ip>:<new-node-port>
   
   ├── 选择迁移哪些槽位到新节点
   ├── 源节点发送槽位数据（MIGRATE）
   └── 所有节点更新路由表

4. 如果需要高可用，为新节点添加从节点
   CLUSTER REPLICATE <master-node-id>

移除节点的流程：

1. 如果是主节点，先迁移走所有槽位
   redis-cli --cluster reshard <target-node-ip>:<target-node-port>
   将待删除节点的槽全部迁移到其他节点

2. 执行删除
   CLUSTER FORGET <node-id>
   在每个节点上执行（或等待60秒自动过期）
```

---

## 四、Cluster实战与避坑指南

### 4.1 常见陷阱

**陷阱一：多Key操作限制**

```
Cluster模式下，多key操作要求所有key在同一slot：

✗ MGET user:1 user:2 user:3           ← 不同hash tag可能不同slot
✗ SINTER set:followers:1 set:followers:2
✗ MULTI/EXEC 跨slot操作

解决方案：
  ✓ 使用Hash Tags：{user:group}:1 {user:group}:2
  ✓ 拆分为多个单key命令
  ✓ 使用Lua脚本限制在单slot
  ✓ pipeline发送多个单key命令（无需同slot）
```

**陷阱二：Big Key带来的问题**

```
大Key：单个Key的value过大（如>10MB的hash/list/set等）

隐患：
  ├── 迁移阻塞：MIGRATE大Key时阻塞源节点
  ├── 删除阻塞：DEL大Key阻塞Redis（6.0前）
  ├── 网卡打满：大Key迁移/同步打满带宽
  └── 内存不均：少数大Key导致节点间内存倾斜

检测命令：
  redis-cli --bigkeys
  MEMORY USAGE <key>

解决方案：
  ├── 业务层面拆分大Key
  ├── Redis 4.0+: UNLINK异步删除
  └── Redis 6.0+: lazyfree-lazy-user-del配置
```

**陷阱三：带宽问题**

```
集群中的带宽杀手：
  ├── 主从全量同步（RDB传输）
  ├── 频繁的reshard（大量MIGRATE）
  ├── 大量从节点 + 高频写入
  └── Pub/Sub消息泛滥

监控指标：
  instantaneous_output_kbps
  instantaneous_input_kbps
  sync_full: 全量同步次数
```

### 4.2 性能优化最佳实践

**连接管理：**

```
连接池配置建议：
  ├── 使用连接池（JedisPool/Lettuce）
  ├── 连接数 = (QPS / 单连接吞吐) × 1.2
  │   一般情况：30-50个连接足够
  ├── 避免连接泄漏：设置testOnBorrow/testOnReturn
  └── Lettuce（Netty异步）> Jedis（同步）在高并发场景
```

**Pipeline批量操作：**

```
Pipeline vs 多Key命令：
  ├── MGET/MSET → 所有key必须在同一个slot
  └── Pipeline → 无slot限制！
      客户端批量发送命令，Redis批量回复
      
Cluster模式下的Pipeline优化：
  客户端按slot分组 → 每个slot一个pipeline → 并行发送
```

**数据分布优化：**

```
避免热点Key：
  ✗ 微博热搜：hot:today → 所有请求打到一个节点
  ✓ 拆分热点：hot:today:0, hot:today:1, ..., hot:today:9
    客户端随机读取其中一个

避免大Key：
  ✗ user:followers → 一个Set存百万粉丝
  ✓ user:followers:0, user:followers:1, ...
    按用户ID取模分散到多个Key

前缀路由：
  根据业务前缀设计Hash Tag：
  order:{userId} → 同一用户的所有订单在同一slot
  事务操作直接在单slot内完成
```

### 4.3 监控关键指标

```
必须监控的Redis Cluster指标：

集群健康：
  ├── cluster_state: ok/fail
  ├── cluster_slots_assigned: 应=16384
  ├── cluster_slots_ok: 应=16384
  ├── cluster_slots_pfail: 应=0
  └── cluster_slots_fail: 应=0

节点状态：
  ├── cluster_known_nodes: 节点总数
  ├── cluster_size: 主节点数
  ├── connected_clients: 客户端连接数
  └── blocked_clients: 阻塞客户端数

复制状态：
  ├── master_repl_offset vs slave_repl_offset
  ├── master_link_status: up/down
  └── master_last_io_seconds_ago

内存：
  ├── used_memory_rss
  ├── mem_fragmentation_ratio (1~1.5健康)
  └── maxmemory_policy

性能：
  ├── instantaneous_ops_per_sec
  ├── instantaneous_input_kbps / output_kbps
  └── rejected_connections
```

---

## 五、面试高频面试题速查

**Q1: Redis主从复制过程中，从节点会阻塞吗？**

```
Redis 3.2之前：会阻塞
  └── 从节点加载RDB期间阻塞所有命令

Redis 3.2之后：默认不会阻塞（无盘复制）
  从节点加载RDB时，继续处理旧数据（如有）
  加载完成后切换到新数据
```

**Q2: 哨兵集群中如果有半数以上Sentinel宕机，还能故障转移吗？**

```
不能。Leader选举需要 ≥ max(quorum, N/2+1)票。
如果5个Sentinel挂掉3个，只剩2个，无法达到N/2+1=3票 → 选举失败。

这就是为什么生产建议≥3个且奇数个Sentinel的原因。
```

**Q3: Cluster模式下，如果某个主节点和它所有从节点同时宕机，集群会怎样？**

```
取决于 cluster-require-full-coverage 配置：

yes（默认）:
  集群进入FAIL状态，拒绝所有写入
  因为16384个槽中有一部分不可用

no:
  集群继续服务，但缺失槽位的请求返回CLUSTERDOWN错误
  其他槽位正常服务
```

**Q4: 为什么Sentinel至少需要3个？**

```
3个Sentinel，quorum=2：
  ├── 即使1个Sentinel宕机，仍有2个可以投票
  ├── 满足N/2+1=2的最小配置
  └── 2个Sentinel情况下，挂1个就无法选举

公式化结论：
  N个Sentinel，可容忍⌊(N-1)/2⌋个宕机
  3个→容忍1个  5个→容忍2个  7个→容忍3个
```

---

## 六、总结

### 核心知识框架

| 层面 | 核心技术 | 关键要点 |
|------|----------|----------|
| 主从复制 | PSYNC全量/部分同步、复制积压缓冲区 | replid+offset判定、COW、复制缓冲区 |
| Sentinel哨兵 | SDOWN/ODOWN、Raft-like选举、故障转移 | 3节点quorum=2、down-after-ms、9步故障转移 |
| Cluster集群 | 16384槽位、Gossip协议、内置容错 | CRC16、MOVED/ASK、半数次主节点投票 |
| 分片路由 | Hash Tags、Smart Client | {}强制同slot、本地维护slot映射表 |
| 实战配置 | client-output-buffer-limit、cluster-node-timeout | 防止复制风暴、防止带宽打满 |

**Redis分布式架构四大心法：**
1. **异步复制不可怕**：理解CAP的选择，接受异步复制的数据丢失窗口
2. **SDOWN是怀疑，ODOWN是确诊**：Sentinel和Cluster都遵循二阶段判定
3. **16384不是魔法数字**：是心跳包大小、节点规模和CRC16之间的精确权衡
4. **Gossip的精妙**：用极小的带宽成本实现大规模集群的去中心化自治

> 🎯 **Redis面试八股文系列第三篇！** 本文从主从复制的PSYNC协议、全量/部分同步的底层差异，到Sentinel九步故障转移、Raft-like Leader选举，再到Cluster核心的16384槽位分配、Gossip协议通信、MOVED/ASK重定向机制，构建了完整的Redis分布式架构知识体系。

> 📌 **下期预告**：《Redis面试八股文（四）——缓存穿透、缓存击穿、缓存雪崩与Redis实战场景》将深入缓存三大经典问题的根因分析与多层解决方案（布隆过滤器、互斥锁、逻辑过期、缓存预热、多级缓存），以及Redis在分布式锁、延时队列、计数器限流、排行榜等经典场景的工程实践，敬请期待！

---

*本系列文章链接：*
- Redis面试八股文（一）——Redis核心数据结构与底层原理
- Redis面试八股文（二）——持久化、过期策略与内存淘汰
- Redis面试八股文（三）——主从复制、哨兵机制与Redis Cluster集群 ← 本文
