---
title: "Redis 集群深度解析"
date: 2026-05-14T19:30:00+08:00
draft: false
categories: ["Redis"]
tags: ["Redis", "集群", "Redis Cluster", "Codis", "数据分片", "高可用"]
---

# Redis 集群深度解析

## 一、引言

当单节点 Redis 无法满足业务需求时，需要构建 Redis 集群来实现**数据分片**和**高可用**。Redis 集群主流方案有 **Redis Cluster** 和 **Codis** 两种，本文将深入解析两种方案的原理、架构与实战。

**本文要点**：
1. 数据分片与哈希槽原理
2. Redis Cluster 架构与实战
3. Codis 架构与实战
4. 集群方案对比与选择
5. 集群运维与故障处理

---

## 二、数据分片基础

### 2.1 为什么要分片

单节点 Redis 的瓶颈：
- 内存容量有限（最大几十GB）
- 单实例无法支撑高并发
- 故障导致服务不可用

**分片解决方案**：
- 数据分散存储到多个节点
- 并行处理请求，提升吞吐量
- 部分节点故障不影响整体服务

### 2.2 分片策略

**客户端分片**：
```java
// 哈希取余
int slot = key.hashCode() % nodeCount;
```

**中间件分片**：
```Codis proxy
请求 → Codis Proxy → Slot 分配 → Redis 节点
```

**服务端分片（Redis Cluster）**：
```
Key → CRC16(key) % 16384 → Slot → 节点
```

---

## 三、Redis Cluster

### 3.1 架构概述

Redis Cluster 是官方提供的分布式解决方案，采用 **去中心化** 设计。

**核心概念**：
- **16384 个哈希槽**：自动分配到多个节点
- **Gossip 协议**：节点间通信传播槽信息
- **故障转移**：主从自动切换

**架构图**：

```
┌─────────────────────────────────────┐
│           Redis Cluster               │
│  ┌─────┐  ┌─────┐  ┌─────┐   │
│  │ M1  │  │ M2  │  │ M3  │   │  ← 主节点（16384 槽）
│  │ S1  │  │ S2  │  │ S3  │   │  ← 从节点
│  └─────┘  └─────┘  └─────┘   │
└─────────────────────────────────────┘
```

### 3.2 哈希槽分配

**slot 计算公式**：

```c
// CRC16 算法
slot = CRC16(key) % 16384
```

**槽分配示例**：
```
节点A：0-5460      (5461 个槽)
节点B：5461-10922  (5462 个槽)
节点C：10923-16383 (5461 个槽)
```

**分配命令**：

```bash
# 为节点分配槽
redis-cli -h 192.168.1.101 -p 7001 ADDSLOTS 0 5460

# 迁移槽
redis-cli -h 192.168.1.101 -p 7001 SETSLOT 516 MIGRATING 192.168.1.102 7002
```

### 3.3 节点通信

**Gossip 协议**：
- 每个节点定期与随机节点交换信息
- 传播：集群拓扑、槽分配、节点状态
- 最终一致性（ eventual consistency）

**节点状态**：

| 状态 | 说明 |
|------|------|
| FAIL | 节点不可用 |
| PFAIL | 疑似故障（需确认） |
| OK | 正常 |

### 3.4 故障转移

**检测流程**：
```
主节点故障 → 从节点 ping 超时 → 从节点发起选举 → 选举成功 → 成为新主节点
```

**选举机制**：
```markdown
1. 从节点向主节点发送 failover
2. 主节点确认投票
3. 获得多数投票的从节点获胜
4. 广播新主节点信息
```

### 3.5 生产环境配置

**配置文件**：

```bash
# redis.conf (每个节点)
# 集群模式开启
cluster-enabled yes

# 节点配置文件
cluster-config-file nodes-7001.conf

# 节点超时时间
cluster-node-timeout 15000

# 故障转���是否执行
cluster-require-full-coverage yes
```

**启动集群**：

```bash
# 方式一：手动启动
redis-server --port 7001 --cluster-enabled yes --daemonize yes
redis-server --port 7002 --cluster-enabled yes --daemonize yes
redis-server --port 7003 --cluster-enabled yes --daemonize yes

# 方式二：ruby 工具
gem install redis-cluster-util
redis-trib.rb create 192.168.1.101:7001 192.168.1.101:7002 192.168.1.101:7003

# 方式三：redis-cli（Redis 5.0+）
redis-cli --cluster create 192.168.1.101:7001,192.168.1.101:7002,192.168.1.101:7003 --cluster-replicas 1
```

### 3.6 客户端连接

**Java 客户端（Jedis）**：

```java
// 方式一：单节点
Jedis jedis = new Jedis("192.168.1.101", 7001);

// 方式二：集群模式
Set<HostAndPort> nodes = new HashSet<>();
nodes.add(new HostAndPort("192.168.1.101", 7001));
nodes.add(new HostAndPort("192.168.1.101", 7002));
nodes.add(new HostAndPort("192.168.1.101", 7003));

JedisCluster jedisCluster = new JedisCluster(nodes);

// 读写分离
JedisClusterPoolConfig poolConfig = new JedisClusterPoolConfig();
poolConfig.setReadFromReplica(true);
JedisCluster jedisCluster = new JedisCluster(nodes, poolConfig);
```

**Spring Boot 配置**：

```yaml
spring:
  redis:
    cluster:
      nodes: 192.168.1.101:7001,192.168.1.101:7002,192.168.1.101:7003
      max-redirects: 3
```

---

## 四、Codis

### 4.1 架构概述

Codis 是豌豆荚开源的 Redis 集群方案，采用 **中心化** 设计，由 **Proxy** 处理请求。

**核心组件**：
- **Codis Proxy**：请求转发、槽路由
- **Codis Dashboard**：集群管理界面
- **Codis Sentinel**：高可用监控
- **Redis Server**：数据存储节点

**架构图**：

```
┌────────────────────────────────────────┐
│            Client                      │
└──────────────────┬───────────────────┘
                   ↓
┌────────────────────────────────────────┐
│         Codis Proxy (x3)               │ ← 无状态，可扩展
└──────────────────┬───────────────────┘
                   ↓
┌────────────────────────────────────────┐
│         Redis Server (x6)                │ ← 数据节点（主+从）
└────────────────────────────────────────┘
                   ↑
┌────────────────────────────────────────┐
│      Codis Dashboard + Sentinel          │  ← 管理与监控
└────────────────────────────────────────┘
```

### 4.2 槽位管理

**Codis 槽位**：
- 1024 个槽（0-1023）
- 哈希取余：key.hashCode() % 1024

**槽位分配**：

```bash
# 通过 Dashboard 分配
# Web 界面：Slot 范围 → Redis 节点
```

### 4.3 与 Redis Cluster 对比

| 特性 | Redis Cluster | Codis |
|------|------------|-------|
| 架构 | 去中心化 | 中心化（Proxy） |
| 客户端 | 原生支持 | 需要修改客户端 |
| 扩展性 | 受限 | 易于扩展 |
| 管理界面 | 无 | Dashboard |
| 数据迁移 | 在线 | 在线 |
| 成熟度 | 官方稳定 | 社区活跃 |
| 版本兼容 | Redis 3.0+ | Redis 3.2.9+ |

### 4.4 生产环境配置

```bash
# 启动 Codis Proxy
codis-proxy -c config.ini -L /var/log/codis.log --daemon

# 启动 Dashboard
codis-dashboard -c config.ini --daemon

# 添加 Redis 节点
codis-admin -add-server -addr 192.168.1.101:6379 -password 123456

# 槽位迁移
codis-admin -slot-migration -direction left2right -s 192.168.1.101 -d 192.168.1.102
```

---

## 五、集群选择建议

| 场景 | 推荐方案 |
|------|--------|
| 新项目 | Redis Cluster |
| 需兼容老客户端 | Codis |
| 需要管理界面 | Codis |
| 需要大规模集群 | Codis |
| 追求简单 | Redis Cluster |

---

## 六、集群运维

### 6.1 常用命令

```bash
# 查看集群状态
redis-cli -c cluster info

# 查看节点
redis-cli -c cluster nodes

# 查看槽分配
redis-cli -c cluster slots

# 修复集群
redis-cli -c cluster fix

# 手动故障转移
redis-cli -c cluster failover
```

### 6.2 故障处理

**节点宕机**：

```bash
# 检查节点状态
redis-cli -c INFO

# 手动移除节点
redis-cli -c cluster forget <node-id>
```

**槽迁移失败**：

```bash
# 查看迁移状态
redis-cli -c cluster slots

# 取消迁移
redis-cli -c SETSLOT <slot> STABLE
```

### 6.3 监控指标

```bash
# 集群 QPS
redis-cli -c INFO stats | grep instantaneous_ops

# 内存使用
redis-cli -c INFO memory

# 连接数
redis-cli -c INFO clients
```

---

## 七、总结

**Redis Cluster vs Codis 选择**：

| 维度 | Redis Cluster | Codis |
|------|--------------|-------|
| 架构 | 去中心化 | 中心化 |
| 部署 | 简单 | 复杂 |
| 客户端 | 需支持 Cluster | 需 Proxy |
| 管理 | 命令行 | Web 界面 |
| 迁移 | 内置 | 工具支持 |
| 生产推荐 | 中小规模 | 大规模 |

**最佳实践**：
1. 评估业务规模选择方案
2. 每个主节点至少一个从节点
3. 监控集群健康状态
4. 定期备份数据
5. 制定故障应急预案

---

**相关文章**：
- [Redis 主从复制与高可用深度解析](/posts/Redis主从复制与高可用深度解析/)
- [Redis 持久化深度解析](/posts/Redis持久化深度解析/)
- [Redis 性能优化与实战](/posts/Redis性能优化与实战/)

---

**本文重点总结**：

| 特性 | Redis Cluster | Codis |
|------|---------------|------|
| 槽位数 | 16384 | 1024 |
| 架构 | 无中心 | Proxy 中心 |
| 客户端 | JedisCluster | 标准 Redis 客户端 |
| 管理 | CLI | Web Dashboard |
| 推荐 | 新项目 | 老项目/大规模 |

---

*你对 Redis 集群有什么疑问吗？欢迎在评论区交流！* 🦐