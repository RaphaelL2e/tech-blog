---
title: "ZooKeeper 深度解析"
date: 2026-05-14T11:10:00+08:00
draft: false
categories: ["分布式系统"]
tags: ["ZooKeeper", "ZAB", "分布式协调", "Watch", "分布式锁"]
---

# ZooKeeper 深度解析

## 一、引言

ZooKeeper 是 Apache 基金会下的开源分布式协调服务，是分布式系统的"管家"。无论是 Hadoop、Kafka、Dubbo 还是 HBase，都依赖 ZooKeeper 做服务发现、配置管理、Leader 选举等工作。理解 ZooKeeper 是掌握分布式系统的关键一步。

**本文要点**：
1. ZooKeeper 的设计目标与架构
2. ZAB 协议详解
3. ZNode 数据模型
4. Watch 机制
5. Session 管理
6. 典型应用场景与实战
7. 面试高频问题

---

## 二、ZooKeeper 概述

### 2.1 设计目标

ZooKeeper 的设计目标可以用四个词概括：**简单、高可用、有序、快速**。

| 目标 | 描述 |
|------|------|
| **简单** | 提供树形命名空间，类似文件系统 |
| **高可用** | 通过复制实现高可用（2f+1 节点容忍 f 个故障）|
| **有序** | 每个更新操作都有全局唯一的 ZXID |
| **快速** | 读操作快（本地读取），写操作通过 Leader |

### 2.2 核心特性

```
1. 顺序一致性：客户端的更新操作按发送顺序应用
2. 原子性：更新操作要么成功要么失败，没有中间状态
3. 单一系统镜像：客户端连接任何节点看到的数据一致
4. 可靠性：已应用的更新不会丢失（除非被新更新覆盖）
5. 及时性：客户端看到的数据在有限时间内是最新的
```

### 2.3 架构

```
                    客户端
                   ↙    ↘
              Client    Client
                ↓         ↓
         ┌──────────────────────┐
         │   ZooKeeper 集群     │
         │                      │
         │  Follower  Leader  Follower
         │    ↓        ↓        ↓
         │  本地数据  本地数据  本地数据
         │                      │
         │   Observer           │
         │    ↓                 │
         │  本地数据（不投票）    │
         └──────────────────────┘
```

**节点角色**：

| 角色 | 职责 | 参与选举 | 参与写投票 |
|------|------|---------|-----------|
| **Leader** | 处理写请求，协调事务 | 不参与（已是 Leader）| - |
| **Follower** | 处理读请求，转发写请求，参与选举和投票 | 是 | 是 |
| **Observer** | 处理读请求，不参与投票 | 否 | 否 |

**为什么需要 Observer**：
- 扩展读性能，不影响写吞吐
- 跨机房部署时减少投票延迟
- 不增加仲裁（Quorum）大小

---

## 三、ZAB 协议详解

### 3.1 ZAB 概述

**ZAB**（ZooKeeper Atomic Broadcast）是 ZooKeeper 专门设计的原子广播协议，用于保证集群中各节点数据一致。

**两种模式**：
1. **消息广播模式**（Broadcast）：Leader 正常工作时
2. **崩溃恢复模式**（Recovery）：Leader 崩溃后重新选举

### 3.2 消息广播模式

**流程**：

```
1. Leader 收到写请求
2. Leader 为该请求生成 ZXID（事务 ID）
3. Leader 将请求放入 FIFO 队列，发送给所有 Follower
4. Follower 收到请求后，以事务方式写入本地日志
5. Follower 返回 ACK 给 Leader
6. Leader 收到超过半数 ACK 后，提交该事务
7. Leader 广播 COMMIT 消息给所有 Follower
8. Follower 收到 COMMIT 后，应用到内存数据库
```

**ZXID 的结构**：

```
ZXID = epoch（32位）+ counter（32位）

epoch：Leader 的任期（每次新 Leader 选举 +1）
counter：该 Leader 任期内的事务计数器

示例：
  epoch=3, counter=0 → ZXID = 0x0000000300000000
  epoch=3, counter=1 → ZXID = 0x0000000300000001
  epoch=4, counter=0 → ZXID = 0x0000000400000000
```

**为什么用半数确认**：
- 类似 Paxos 的多数派机制
- 保证任何两个多数派至少有一个交集
- 交集的节点拥有最新的数据

### 3.3 崩溃恢复模式

**触发条件**：
- Leader 崩溃
- Leader 与过半 Follower 失去联系

**恢复目标**：
1. **已提交的提案不能丢失**
2. **未提交的提案不能被提交**

**选举过程**：

```
1. 每个 Follower 进入 LOOKING 状态
2. 向所有节点发送投票信息：(self_id, self_zxid)
3. 收到其他节点的投票后，比较 ZXID：
   - ZXID 大的优先（数据更新）
   - ZXID 相同时，myid 大的优先
4. 更新自己的投票为最优的节点
5. 如果某个节点获得过半投票，成为新 Leader
6. 新 Leader 进入 LEADING 状态
7. Follower 进入 FOLLOWING 状态
```

**为什么 ZXID 大的优先**：
- ZXID 大意味着数据更完整
- 保证已提交的事务不会丢失

**选举算法（FastLeaderElection）**：

```
比较规则：
  1. 先比较 epoch（大的优先）
  2. epoch 相同，比较 ZXID（大的优先）
  3. ZXID 相同，比较 myid（大的优先）

示例：
  节点 A：(epoch=3, zxid=0x30000005, myid=1)
  节点 B：(epoch=3, zxid=0x30000008, myid=2)
  节点 C：(epoch=4, zxid=0x40000000, myid=3)

  → C 的 epoch 最大 → C 成为 Leader
```

### 3.4 数据同步

新 Leader 选出后，需要进行数据同步：

```
1. Leader 收集所有 Follower 的最新 ZXID
2. 根据差异程度，选择同步方式：

   a. DIFF（差异同步）：
      Follower 缺少少量日志 → 发送缺失的事务
   
   b. TRUNC（回滚同步）：
      Follower 有未提交的事务 → 先回滚，再 DIFF
   
   c. SNAP（快照同步）：
      Follower 落后太多 → 发送完整快照
```

**同步流程**：

```
Leader                          Follower
  │                                │
  │ ←─ FOLLOWERINFO(lastZxid) ─── │
  │                                │
  │ ── NEWLEADER(leaderZxid) ──→ │
  │                                │
  │ ── DIFF/TRUNC/SNAP ──────→  │
  │                                │
  │ ←─ ACK ───────────────────── │
  │                                │
  │ ── UPTODATE ──────────────→ │
  │                                │
```

---

## 四、ZNode 数据模型

### 4.1 树形命名空间

ZooKeeper 的数据模型类似文件系统，是一棵树：

```
/
├── services
│   ├── order-service
│   │   ├── instance-1  (数据: "192.168.1.1:8080")
│   │   └── instance-2  (数据: "192.168.1.2:8080")
│   └── user-service
│       └── instance-1  (数据: "192.168.1.3:8080")
├── config
│   ├── db-url    (数据: "jdbc:mysql://...")
│   └── db-user   (数据: "root")
└── leaders
    └── election  (数据: "server-1")
```

**与文件系统的区别**：
- 每个 ZNode 都可以存储数据（不仅是叶子节点）
- ZNode 有版本号、ACL、时间戳等元数据
- ZNode 有类型（持久、临时、顺序）

### 4.2 ZNode 类型

| 类型 | 创建方式 | 持久性 | 命名 |
|------|---------|--------|------|
| **持久节点** | `create /path data` | 永久存在，直到删除 | 指定名称 |
| **持久顺序节点** | `create -s /path data` | 永久存在 | 自动追加递增序号 |
| **临时节点** | `create -e /path data` | Session 结束自动删除 | 指定名称 |
| **临时顺序节点** | `create -e -s /path data` | Session 结束自动删除 | 自动追加递增序号 |
| **容器节点** | `create -c /path data` | 最后一个子节点删除后自动删除 | 指定名称 |
| **TTL 节点** | `create -t 1000 /path data` | 超时无子节点自动删除 | 指定名称 |

**临时节点的用途**：
- 服务注册（服务下线自动注销）
- 分布式锁（Session 断开自动释放）
- Leader 选举（争抢创建临时节点）

**顺序节点的用途**：
- 分布式队列（按序号排列）
- Leader 选举（序号最小的为 Leader）
- 唯一 ID 生成

### 4.3 ZNode 的数据结构

```java
public class DataNode {
    byte[] data;           // 节点数据（最大 1MB）
    Stat stat;             // 状态信息
    Set<String> children;  // 子节点列表
}

public class Stat {
    long czxid;      // 创建时的 ZXID
    long mzxid;      // 最后修改的 ZXID
    long pzxid;      // 子节点最后修改的 ZXID
    long ctime;      // 创建时间
    long mtime;      // 最后修改时间
    int version;     // 数据版本号（每次更新 +1）
    int cversion;    // 子节点版本号
    int aversion;    // ACL 版本号
    long ephemeralOwner; // 临时节点的 Session ID（0 = 持久节点）
    int dataLength;  // 数据长度
    int numChildren; // 子节点数量
}
```

**版本号的作用**：
- 实现乐观锁（CAS）
- `setData("/config", newData, expectedVersion)`
- 如果 version 不匹配，操作失败

---

## 五、Watch 机制

### 5.1 Watch 是什么

**Watch** 是 ZooKeeper 的事件通知机制。客户端可以在 ZNode 上注册 Watch，当 ZNode 发生变化时，ZooKeeper 会通知客户端。

**特点**：
1. **一次性触发**：触发一次后失效，需要重新注册
2. **轻量级**：只通知事件类型，不传数据
3. **顺序性**：Watch 通知按事件发生顺序发送

### 5.2 Watch 事件类型

| 事件类型 | 触发条件 | 注册方式 |
|---------|---------|---------|
| `NodeCreated` | ZNode 被创建 | `exists(path, watch=true)` |
| `NodeDeleted` | ZNode 被删除 | `exists(path, watch=true)` / `getChildren(path, watch=true)` |
| `NodeDataChanged` | ZNode 数据被修改 | `getData(path, watch=true)` / `exists(path, watch=true)` |
| `NodeChildrenChanged` | 子节点列表变化 | `getChildren(path, watch=true)` |

### 5.3 Watch 的使用示例

**Java API**：

```java
// 注册 Watch
ZooKeeper zk = new ZooKeeper("localhost:2181", 3000, null);

// 监听节点数据变化
zk.getData("/config", event -> {
    System.out.println("数据变化: " + event.getType());
    // 重新注册 Watch（一次性触发）
    try {
        zk.getData("/config", this, null);
    } catch (Exception e) {
        e.printStackTrace();
    }
}, null);

// 监听子节点变化
zk.getChildren("/services", event -> {
    System.out.println("子节点变化: " + event.getType());
    // 重新注册 Watch
    try {
        zk.getChildren("/services", this, null);
    } catch (Exception e) {
        e.printStackTrace();
    }
}, null);
```

**Curator 框架**（推荐）：

```java
CuratorFramework client = CuratorFrameworkFactory.newClient("localhost:2181", new ExponentialBackoffRetry(1000, 3));
client.start();

// PathChildrenCache：监听子节点变化
PathChildrenCache cache = new PathChildrenCache(client, "/services", true);
cache.getListenable().addListener((c, event) -> {
    switch (event.getType()) {
        case CHILD_ADDED:
            System.out.println("服务上线: " + event.getData().getPath());
            break;
        case CHILD_REMOVED:
            System.out.println("服务下线: " + event.getData().getPath());
            break;
        case CHILD_UPDATED:
            System.out.println("服务更新: " + event.getData().getPath());
            break;
    }
});
cache.start();

// NodeCache：监听节点数据变化
NodeCache nodeCache = new NodeCache(client, "/config/db-url");
nodeCache.getListenable().addListener(() -> {
    byte[] data = nodeCache.getCurrentData().getData();
    System.out.println("配置更新: " + new String(data));
});
nodeCache.start();
```

### 5.4 Watch 的注意事项

1. **一次性触发**：Watch 触发后失效，需要在回调中重新注册
2. **消息延迟**：Watch 通知有网络延迟，可能不是实时的
3. **丢失风险**：如果重新注册前又发生了变化，会丢失中间的变更
4. **内存压力**：大量 Watch 会占用服务端内存

---

## 六、Session 管理

### 6.1 Session 概述

**Session** 是客户端与 ZooKeeper 服务器之间的连接会话。

**Session 的生命周期**：

```
CONNECTING → CONNECTED → CLOSED
                ↓
            (连接断开)
                ↓
           CONNECTING → CONNECTED (重连成功)
                ↓
           EXPIRED (Session 过期)
```

### 6.2 Session 的关键参数

| 参数 | 描述 |
|------|------|
| **sessionTimeout** | 会话超时时间（客户端请求） |
| **minSessionTimeout** | 服务端允许的最小超时 |
| **maxSessionTimeout** | 服务端允许的最大超时 |
| **tickTime** | 服务端心跳间隔（默认 2000ms） |

**实际超时时间**：

```
实际 sessionTimeout = max(minSessionTimeout, min(sessionTimeout, maxSessionTimeout))

默认：min = 2 × tickTime, max = 20 × tickTime
```

### 6.3 心跳机制

```
客户端 → 服务器：PING（心跳包）
服务器 → 客户端：PONG

心跳间隔 = sessionTimeout / 3

示例：
sessionTimeout = 30000ms
心跳间隔 = 10000ms（每 10 秒发一次心跳）
```

### 6.4 Session 过期的影响

**Session 过期后**：
1. 该 Session 创建的所有临时节点被删除
2. 所有注册的 Watch 被清除
3. 客户端需要重新创建连接

**对分布式锁的影响**：
```
客户端 A 获取锁 → 创建临时节点 /lock
客户端 A 的 Session 过期（网络故障）→ 临时节点被删除
客户端 B 获取锁 → 创建临时节点 /lock
客户端 A 恢复连接 → 发现锁已丢失！
```

**解决方案**：
- 使用较长的 sessionTimeout
- 在获取锁后，定期发送心跳
- 使用可重入锁（记录锁持有者信息）

---

## 七、典型应用场景

### 7.1 分布式锁

**实现方式一：临时节点**

```
1. 所有客户端尝试创建临时节点 /lock
2. 创建成功的客户端获得锁
3. 其他客户端 Watch /lock 节点
4. 锁持有者释放锁（删除 /lock）→ 通知其他客户端
5. 其他客户端重新尝试创建
```

**问题**：羊群效应（Herd Effect）—— 锁释放时所有等待客户端同时竞争。

**实现方式二：临时顺序节点（推荐）**

```
1. 客户端在 /lock 下创建临时顺序节点
   → /lock/lock-0000000001
   → /lock/lock-0000000002
   → /lock/lock-0000000003

2. 获取 /lock 下所有子节点，判断自己是否序号最小
   → lock-0000000001 的持有者获得锁

3. 如果自己不是最小的，Watch 前一个节点
   → lock-0000000002 Watch lock-0000000001
   → lock-0000000003 Watch lock-0000000002

4. 前一个节点删除时，收到通知，重新检查自己是否最小
```

**代码实现（Curator）**：

```java
InterProcessMutex lock = new InterProcessMutex(client, "/lock");

try {
    if (lock.acquire(30, TimeUnit.SECONDS)) {
        try {
            // 执行业务逻辑
            doBusiness();
        } finally {
            lock.release();
        }
    }
} catch (Exception e) {
    e.printStackTrace();
}
```

### 7.2 Leader 选举

**实现方式一：临时节点**

```
1. 所有候选人尝试创建临时节点 /election/leader
2. 创建成功的成为 Leader
3. 其他候选人 Watch /election/leader
4. Leader 故障 → 临时节点删除 → 其他候选人重新竞选
```

**问题**：同样是羊群效应。

**实现方式二：临时顺序节点（推荐）**

```
1. 每个候选人在 /election 下创建临时顺序节点
   → /election/candidate-0000000001
   → /election/candidate-0000000002

2. 获取所有子节点，序号最小的成为 Leader

3. 非 Leader 的候选人 Watch 前一个节点

4. 前一个节点删除 → 收到通知 → 检查自己是否成为最小的 → 成为新 Leader
```

**代码实现（Curator）**：

```java
LeaderSelector selector = new LeaderSelector(client, "/election", new LeaderSelectorListener() {
    @Override
    public void takeLeadership(CuratorFramework client) throws Exception {
        // 成为 Leader 后执行
        System.out.println("I am the leader!");
        try {
            // 持续作为 Leader，直到方法返回
            Thread.sleep(Long.MAX_VALUE);
        } finally {
            // 释放 Leadership
        }
    }
});
selector.start();
```

### 7.3 服务注册与发现

```
服务提供者：
1. 启动时在 /services/order-service 下创建临时节点
   → /services/order-service/instance-1 (数据: "192.168.1.1:8080")

2. 保持心跳，维持 Session

服务消费者：
1. 读取 /services/order-service 下所有子节点
2. Watch 子节点变化
3. 子节点变化时更新本地服务列表
```

### 7.4 配置中心

```
1. 配置写入 ZooKeeper：
   /config/db-url → "jdbc:mysql://master:3306/db"
   /config/db-user → "root"
   /config/db-password → "xxx"

2. 应用启动时读取配置，并注册 Watch

3. 配置变更时，ZooKeeper 通知所有 Watch 的应用

4. 应用收到通知后重新读取配置
```

---

## 八、ZooKeeper 集群部署

### 8.1 集群规划

**推荐配置**：3 节点或 5 节点

```
3 节点：容忍 1 个节点故障
5 节点：容忍 2 个节点故障

公式：可用节点数 > N/2（N 为总节点数）
3 节点：3/2 = 1.5 → 需要至少 2 个节点可用
5 节点：5/2 = 2.5 → 需要至少 3 个节点可用
```

### 8.2 配置文件

**zoo.cfg**：

```properties
# 基本配置
tickTime=2000
initLimit=10
syncLimit=5
dataDir=/var/lib/zookeeper
clientPort=2181

# 集群配置
server.1=zk1:2888:3888
server.2=zk2:2888:3888
server.3=zk3:2888:3888

# 日志配置
autopurge.snapRetainCount=3
autopurge.purgeInterval=1
```

**参数说明**：

| 参数 | 描述 | 推荐值 |
|------|------|--------|
| tickTime | 心跳间隔 | 2000ms |
| initLimit | Follower 初始化连接 Leader 的最长心跳数 | 10（20s）|
| syncLimit | Follower 与 Leader 同步的最长心跳数 | 5（10s）|
| dataDir | 数据存储目录 | 独立磁盘 |
| clientPort | 客户端连接端口 | 2181 |

**myid 文件**：

```bash
# 每个节点的 dataDir 下创建 myid 文件
# zk1
echo "1" > /var/lib/zookeeper/myid

# zk2
echo "2" > /var/lib/zookeeper/myid

# zk3
echo "3" > /var/lib/zookeeper/myid
```

### 8.3 常用运维命令

```bash
# 查看节点状态
echo ruok | nc localhost 2181
# → imok

# 查看节点角色
echo srvr | nc localhost 2181

# 查看连接数
echo cons | nc localhost 2181

# 查看Watch数量
echo wchs | nc localhost 2181

# 查看环境变量
echo envi | nc localhost 2181
```

---

## 九、面试高频问题

### Q1: ZooKeeper 的 ZAB 协议是什么？

**答案要点**：
- ZAB = ZooKeeper Atomic Broadcast
- 两种模式：消息广播、崩溃恢复
- 消息广播：Leader 生成 ZXID → 发送给 Follower → 过半 ACK → 提交
- 崩溃恢复：选举新 Leader → 数据同步 → 恢复广播
- ZXID = epoch + counter，保证全局有序

### Q2: ZooKeeper 的临时节点有什么用？

**答案要点**：
- Session 结束自动删除
- 用途：服务注册、分布式锁、Leader 选举
- 好处：客户端故障自动释放资源（不需要手动清理）

### Q3: ZooKeeper 的 Watch 机制有什么注意事项？

**答案要点**：
- 一次性触发（触发后需重新注册）
- 轻量级（只通知事件类型，不传数据）
- 可能丢失中间变更
- 大量 Watch 占用内存

### Q4: ZooKeeper 如何实现分布式锁？

**答案要点**：
- 方案一：临时节点（有羊群效应）
- 方案二：临时顺序节点（推荐，避免羊群效应）
- 流程：创建顺序节点 → 判断是否最小 → 不是则 Watch 前一个
- 临时节点保证故障自动释放

### Q5: ZooKeeper 集群为什么推荐奇数节点？

**答案要点**：
- 写操作需要过半确认
- 3 节点容忍 1 个故障，4 节点也容忍 1 个故障（4/2+1=3）
- 5 节点容忍 2 个故障，6 节点也容忍 2 个故障（6/2+1=4）
- 奇数节点更经济（相同容错能力，节省机器）

---

## 十、总结

本文深入分析了 ZooKeeper 的核心原理：

1. **ZAB 协议**：消息广播（过半确认）+ 崩溃恢复（ZXID 优先选举）
2. **ZNode 模型**：持久/临时/顺序节点，版本号实现 CAS
3. **Watch 机制**：一次性触发，轻量级通知
4. **Session 管理**：心跳维持，过期清理临时节点
5. **应用场景**：分布式锁、Leader 选举、服务发现、配置中心

**核心记忆**：
- ZAB 选举：ZXID 大的优先（数据更完整）
- 临时节点：Session 过期自动删除
- Watch：一次性触发，需要重新注册
- 分布式锁：临时顺序节点避免羊群效应
- 集群规模：奇数节点更经济

下一篇将深入 **分布式锁实现**，对比 Redis、ZooKeeper、etcd 三种方案的优缺点与最佳实践，敬请期待。

---

*作者：亚飞的技术笔记 | 公众号：亚飞的技术笔记*
