---
title: "数据库面试八股文（八）——Redis持久化、集群与缓存问题"
date: 2026-06-04T10:00:00+08:00
draft: false
categories: ["数据库"]
tags: ["面试", "八股文", "Redis", "RDB", "AOF", "主从复制", "哨兵", "Cluster", "缓存穿透", "缓存击穿", "缓存雪崩"]
---

# 数据库面试八股文（八）——Redis持久化、集群与缓存问题

> 面试高频考点：RDB与AOF持久化原理与选择、主从复制与哨兵模式、Cluster集群方案、缓存穿透/击穿/雪崩的解决方案。本文从持久化机制到集群架构再到缓存实战问题，全面覆盖Redis高可用与缓存面试题。

---

## 一、Redis持久化概述

Redis是内存数据库，一旦进程退出数据就会丢失。持久化机制将内存数据保存到磁盘，保证重启后数据恢复。

Redis提供两种持久化方式：

| 方式 | 原理 | 特点 |
|------|------|------|
| RDB | 定时快照 | 文件小、恢复快、可能丢数据 |
| AOF | 追加写日志 | 数据安全、文件大、恢复慢 |
| 混合持久化 | RDB+AOF | 兼顾两者优点（Redis 4.0+） |

---

## 二、RDB持久化

### 2.1 RDB原理

RDB（Redis Database）是将某一时刻的内存数据以二进制形式写入磁盘（dump.rdb文件）。

**触发方式**：

| 类型 | 命令/配置 | 说明 |
|------|----------|------|
| 手动触发 | `SAVE` | 阻塞主进程，不推荐 |
| 手动触发 | `BGSAVE` | fork子进程，推荐 |
| 自动触发 | `save 900 1` | 900秒内至少1次修改 |
| 自动触发 | `save 300 10` | 300秒内至少10次修改 |
| 自动触发 | `save 60 10000` | 60秒内至少10000次修改 |

### 2.2 BGSAVE执行流程

```
客户端发送BGSAVE
       ↓
  主进程fork()子进程
       ↓
┌──────────────┐    ┌──────────────┐
│   主进程      │    │   子进程      │
│ 继续处理请求  │    │ 生成RDB文件   │
│ 写操作→COW   │    │ 写入dump.rdb  │
└──────────────┘    └──────────────┘
                          ↓
                    通知主进程完成
                          ↓
                    替换旧RDB文件
```

**关键点：写时复制（Copy-On-Write）**

fork()使用操作系统的写时复制机制：
1. fork()后子进程共享父进程的内存页（不真正复制）
2. 主进程修改某页时，OS才复制该页给主进程
3. 子进程仍然看到fork时的数据快照

> 💡 **面试重点**：BGSAVE期间如果写操作很多，内存可能翻倍！因为修改的页都需要复制。

### 2.3 RDB文件结构

```
+--------+----------+----------+--------+-----+--------+--------+
|  REDIS | db_version | SELECTDB | key值  | ... | EOF    | check_sum |
|  魔数   | 版本号    | 数据库编号 | type   |     | 结束符  | 校验和   |
+--------+----------+----------+--------+-----+--------+--------+
```

### 2.4 RDB优缺点

**优点**：
- 文件紧凑，体积小，适合备份和传输
- 恢复速度快（直接加载二进制文件）
- fork子进程不影响主进程性能

**缺点**：
- 定时快照，两次快照间的数据可能丢失
- fork()在数据量大时耗时较长（虽然用COW）
- 不适合对数据安全性要求极高的场景

---

## 三、AOF持久化

### 3.1 AOF原理

AOF（Append Only File）以日志形式记录Redis的每一个写命令，追加写入aof文件。

**执行流程**：

```
写命令 → 写入AOF缓冲区 → 根据策略刷盘 → AOF文件
```

### 3.2 AOF刷盘策略

| 策略 | 配置 | 刷盘时机 | 数据安全 | 性能 |
|------|------|---------|---------|------|
| always | appendfsync always | 每条命令都刷盘 | 最多丢1条 | 最差 |
| everysec | appendfsync everysec | 每秒刷盘 | 最多丢1秒 | 折中 |
| no | appendfsync no | OS决定何时刷盘 | 可能丢较多 | 最好 |

> 💡 **面试重点**：默认推荐 `everysec`，兼顾安全与性能。

### 3.3 AOF重写（Rewrite）

AOF文件会越来越大，重写机制压缩文件：

**重写原理**：
- 不是读取旧AOF文件，而是直接读取当前数据库状态
- 用最少的命令记录当前状态（如100次INCR → 1次SET）

**触发方式**：

| 类型 | 配置 | 说明 |
|------|------|------|
| 手动 | `BGREWRITEAOF` | 手动触发 |
| 自动 | `auto-aof-rewrite-min-size 64mb` | AOF文件大于64MB时 |
| 自动 | `auto-aof-rewrite-percentage 100` | 当前大小比上次重写后大100% |

**AOF重写流程**：

```
1. 主进程fork()子进程
2. 子进程根据当前内存数据生成新AOF文件
3. 主进程将重写期间的新命令同时写入：
   - 旧AOF文件（保证安全）
   - AOF重写缓冲区
4. 子进程完成重写后，主进程将重写缓冲区追加到新AOF文件
5. 用新AOF文件替换旧AOF文件
```

> ⚠️ **面试陷阱**：重写期间主进程仍处理请求，新命令不会丢失！

### 3.4 AOF优缺点

**优点**：
- 数据安全性高（最多丢1秒）
- AOF文件是追加日志，易于理解和修复
- 支持重写压缩

**缺点**：
- 文件体积比RDB大
- 恢复速度慢（逐条执行命令）
- 每秒fsync对性能有影响

---

## 四、混合持久化（Redis 4.0+）

### 4.1 原理

结合RDB和AOF的优点：
- AOF重写时，前半部分用RDB格式写入（快速加载）
- 后半部分用AOF格式写入（增量命令）

```
+------------------+------------------+
|    RDB格式部分    |    AOF格式部分    |
|  （全量快照数据）  |  （增量写命令）    |
+------------------+------------------+
```

### 4.2 配置

```bash
aof-use-rdb-preamble yes  # 开启混合持久化
```

**加载速度对比**：

| 方式 | 加载1GB数据 |
|------|-----------|
| 纯AOF | ~30秒 |
| 混合持久化 | ~5秒 |
| 纯RDB | ~3秒 |

---

## 五、RDB vs AOF 选择

| 维度 | RDB | AOF | 混合持久化 |
|------|-----|-----|-----------|
| 数据安全 | 可能丢数分钟 | 最多丢1秒 | 最多丢1秒 |
| 文件大小 | 小 | 大 | 中等 |
| 恢复速度 | 快 | 慢 | 较快 |
| 系统资源 | fork时消耗内存 | 每秒fsync | 两者兼具 |
| 适用场景 | 备份/灾备 | 数据安全优先 | 推荐默认 |

> 💡 **面试回答**：生产环境推荐开启混合持久化（RDB+AOF），既保证数据安全又兼顾恢复速度。

---

## 六、Redis主从复制

### 6.1 为什么需要主从复制

- **读写分离**：主节点写，从节点读，分担压力
- **数据冗余**：从节点是热备
- **高可用基础**：哨兵和Cluster的前提

### 6.2 主从复制流程

**全量同步（首次连接）**：

```
从节点                    主节点
  |---PSYNC ? --1------->|     ① 请求全量同步
  |                      |
  |<--FULLRESYNC runid---|     ② 返回runid+offset
  |                      |
  |<--BGSAVE RDB数据----|     ③ 主节点BGSAVE，发送RDB
  |                      |
  |<--发送缓冲区数据------|     ④ 发送BGSAVE期间的新命令
  |                      |
  |  加载RDB+执行缓冲命令  |     ⑤ 从节点恢复数据
```

**增量同步（断线重连）**：

```
从节点                    主节点
  |---PSYNC runid offset->|    ① 携带runid和offset请求
  |                       |
  |<--CONTINUE------------|    ② 判断是否可以增量同步
  |                       |
  |<--发送缺失数据---------|    ③ 从repl_backlog读取并发送
```

### 6.3 关键概念

| 概念 | 说明 |
|------|------|
| runid | 主节点唯一标识，每次重启变化 |
| offset | 复制偏移量，主从各自维护 |
| repl_backlog | 环形缓冲区，默认1MB，存储最近写命令 |

> ⚠️ **面试重点**：如果从节点断线时间过长，offset已经不在repl_backlog中，就必须全量同步！所以repl_backlog_size要根据网络状况调大。

### 6.4 主从复制延迟问题

- **全量同步阻塞**：主节点BGSAVE时内存开销大
- **网络延迟**：跨机房部署时复制延迟明显
- **从节点过期key**：从节点不会主动删除过期key，等主节点发DEL命令

---

## 七、Redis哨兵模式（Sentinel）

### 7.1 哨兵的作用

当主节点故障时，自动完成故障转移：
1. **监控**：持续检测主从节点是否正常
2. **通知**：故障时通知管理员或应用
3. **自动故障转移**：选举新主节点，通知从节点切换

### 7.2 哨兵集群

至少需要3个哨兵节点（奇数），防止脑裂：

```
    Sentinel1  Sentinel2  Sentinel3
        |          |          |
        +----+-----+-----+---+
             |           |
         Master ---- Slave1
             |
           Slave2
```

### 7.3 故障转移流程

```
1. 主观下线（SDOWN）
   单个Sentinel认为主节点不可达（超时未响应）

2. 客观下线（ODOWN）
   超过quorum个Sentinel认为主节点下线
   quorum = sentinel数量/2 + 1

3. Sentinel领导者选举
   使用Raft算法选出一个Sentinel负责故障转移

4. 选举新主节点
   规则优先级：
   ① repel-priority值最小的（配置优先级）
   ② 复制偏移量最大的（数据最新）
   ③ runid最小的（最稳定）

5. 执行故障转移
   ① 新主节点执行 SLAVEOF NO ONE
   ② 其他从节点复制新主节点
   ③ 旧主节点恢复后变为从节点
```

> 💡 **面试重点**：为什么需要quorum？防止网络分区导致误判（脑裂）。

### 7.4 哨兵配置关键参数

```bash
sentinel monitor mymaster 127.0.0.1 6379 2    # quorum=2
sentinel down-after-milliseconds mymaster 30000 # 30秒无响应判定下线
sentinel failover-timeout mymaster 180000       # 故障转移超时3分钟
sentinel parallel-syncs mymaster 1              # 同时复制新主节点的从节点数
```

---

## 八、Redis Cluster集群

### 8.1 Cluster vs 哨兵

| 维度 | 哨兵模式 | Cluster模式 |
|------|---------|------------|
| 数据分片 | 不支持 | 支持16384个槽 |
| 扩容 | 只能增加从节点 | 可以增加主节点分摊数据 |
| 故障转移 | Sentinel负责 | 节点间Gossip协议 |
| 规模 | 1主多从 | 最大1000节点 |
| 适用 | 中小规模 | 大规模 |

### 8.2 槽位（Slot）机制

Redis Cluster将数据分为16384个槽（0-16383），每个主节点负责一部分槽：

```
Node A: 槽 0 ~ 5460
Node B: 槽 5461 ~ 10922
Node C: 槽 10923 ~ 16383
```

**key路由公式**：`slot = CRC16(key) % 16384`

### 8.3 Gossip协议

节点间通过Gossip协议交换信息：

| 消息类型 | 说明 |
|---------|------|
| PING | 检测节点是否在线 |
| PONG | 回复在线状态 |
| MEET | 加入集群 |
| FAIL | 标记节点下线 |

### 8.4 Cluster故障转移

```
1. 节点A检测到主节点B的从节点不可用
2. 从节点发起选举（类似Raft）
3. 获得多数主节点投票的从节点晋升为主节点
4. 其他从节点开始复制新主节点
5. 集群更新槽位映射
```

### 8.5 常见问题

**MOVED重定向**：
- 客户端请求key不在当前节点
- 返回 `MOVED <slot> <ip>:<port>`
- 客户端重新请求正确节点

**ASK重定向**：
- 槽迁移过程中，key可能在新旧节点
- 返回 `ASK <slot> <ip>:<port>`
- 客户端仅本次重定向

---

## 九、缓存穿透

### 9.1 什么是缓存穿透

查询一个**一定不存在的数据**，缓存中没有，数据库中也没有，每次请求都打到数据库。

```
请求 → 缓存（miss）→ 数据库（miss）→ 返回空
  ↑                                    |
  └────────── 下次还是miss ──────────────┘
```

### 9.2 解决方案

**方案一：缓存空值/缺省值**

```java
public Object getProduct(Long id) {
    String key = "product:" + id;
    String value = redis.get(key);
    
    if (value != null) {
        return "NULL".equals(value) ? null : deserialize(value);
    }
    
    Object result = db.query(id);
    if (result == null) {
        // 缓存空值，设置短过期时间
        redis.set(key, "NULL", 300, TimeUnit.SECONDS);
    } else {
        redis.set(key, serialize(result), 3600, TimeUnit.SECONDS);
    }
    return result;
}
```

**方案二：布隆过滤器（Bloom Filter）**

在缓存前加一层布隆过滤器，快速判断数据是否可能存在：

```
请求 → 布隆过滤器 → 不存在 → 直接返回
                → 可能存在 → 缓存 → 数据库
```

```java
// 初始化布隆过滤器
BloomFilter<Long> bloomFilter = BloomFilter.create(
    Funnels.longFunnel(), 1000000, 0.01  // 预计100万元素，误判率1%
);

// 写入数据时加入布隆过滤器
public void addProduct(Product product) {
    db.insert(product);
    bloomFilter.put(product.getId());
    redis.set("product:" + product.getId(), serialize(product));
}

// 查询时先检查布隆过滤器
public Product getProduct(Long id) {
    if (!bloomFilter.mightContain(id)) {
        return null;  // 一定不存在，直接返回
    }
    // 继续查缓存和数据库...
}
```

**方案三：请求参数校验**

在入口层拦截非法请求（如id为负数）。

### 9.3 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 缓存空值 | 实现简单 | 浪费内存、需设短过期 | 空值少且固定 |
| 布隆过滤器 | 省内存、高效 | 有误判率、不支持删除 | 数据集固定 |
| 参数校验 | 成本最低 | 只能拦截明显非法请求 | 所有场景兜底 |

---

## 十、缓存击穿

### 10.1 什么是缓存击穿

一个**热点key过期**的瞬间，大量并发请求同时打到数据库。

```
热点key过期
  ↓
大量并发请求同时miss
  ↓
全部打到数据库
  ↓
数据库压力骤增
```

### 10.2 解决方案

**方案一：互斥锁（Mutex Lock）**

只允许一个线程查数据库，其他线程等待：

```java
public Product getHotProduct(Long id) {
    String key = "product:" + id;
    String value = redis.get(key);
    
    if (value != null) {
        return deserialize(value);
    }
    
    String lockKey = "lock:" + id;
    try {
        // 尝试获取互斥锁
        boolean locked = redis.setnx(lockKey, "1", 10, TimeUnit.SECONDS);
        if (locked) {
            // 获得锁，查数据库
            Product product = db.query(id);
            redis.set(key, serialize(product), 3600, TimeUnit.SECONDS);
            return product;
        } else {
            // 未获得锁，短暂等待后重试
            Thread.sleep(100);
            return getHotProduct(id);
        }
    } finally {
        redis.del(lockKey);
    }
}
```

**方案二：逻辑过期**

不设置TTL，在数据中嵌入逻辑过期时间，发现过期时异步更新：

```java
public Product getHotProduct(Long id) {
    String key = "product:" + id;
    String value = redis.get(key);
    
    if (value == null) return null;
    
    RedisData redisData = deserialize(value);
    if (redisData.getExpireTime().isBefore(LocalDateTime.now())) {
        // 逻辑过期，异步更新
        if (tryLock(id)) {
            EXECUTOR.submit(() -> {
                try {
                    Product newProduct = db.query(id);
                    RedisData newData = new RedisData(newProduct, 
                        LocalDateTime.now().plusHours(1));
                    redis.set(key, serialize(newData));
                } finally {
                    unlock(id);
                }
            });
        }
        // 返回旧数据（保证可用性）
        return redisData.getData();
    }
    return redisData.getData();
}
```

**方案三：热点key永不过期**

设置热点key永不过期，通过后台任务定期刷新。

### 10.3 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| 互斥锁 | 保证强一致 | 有死锁风险、吞吐低 | 一致性要求高 |
| 逻辑过期 | 高可用、吞吐高 | 可能返回旧数据 | 可接受短期不一致 |
| 永不过期 | 简单 | 占内存、需额外刷新 | 超热点key |

---

## 十一、缓存雪崩

### 11.1 什么是缓存雪崩

大量key**同时过期**或Redis**整体宕机**，请求全部打到数据库。

### 11.2 大量key同时过期的解决方案

**方案一：过期时间加随机值**

```java
// 避免大量key同一时间过期
int expire = 3600 + new Random().nextInt(600); // 3600~4200秒
redis.set(key, value, expire, TimeUnit.SECONDS);
```

**方案二：多级缓存**

```
请求 → 本地缓存(Caffeine) → Redis → 数据库
```

**方案三：缓存预热**

系统启动时提前加载热点数据到缓存。

### 11.3 Redis宕机的解决方案

**方案一：Redis高可用集群**

- 主从复制 + 哨兵自动故障转移
- Redis Cluster集群

**方案二：降级与限流**

```java
// Sentinel限流
@SentinelResource(value = "getProduct", fallback = "getProductFallback")
public Product getProduct(Long id) {
    return productService.getById(id);
}

public Product getProductFallback(Long id) {
    return Product.defaultProduct(); // 返回默认值
}
```

**方案三：熔断机制**

当数据库压力过大时，直接熔断返回兜底数据，保护数据库。

### 11.4 三大缓存问题对比

| 问题 | 原因 | 核心方案 |
|------|------|---------|
| 缓存穿透 | 查询不存在的数据 | 布隆过滤器 + 缓存空值 |
| 缓存击穿 | 热点key过期 | 互斥锁 + 逻辑过期 |
| 缓存雪崩 | 大量key同时过期/宕机 | 随机过期 + 高可用 + 降级 |

> 💡 **面试速记**：穿透是"不存在"，击穿是"热点过期"，雪崩是"大面积失效"。

---

## 十二、Redis与数据库一致性

### 12.1 常见策略

| 策略 | 一致性 | 性能 | 问题 |
|------|--------|------|------|
| 先更新DB再删缓存 | 较强 | 高 | 极端情况不一致 |
| 先删缓存再更新DB | 较弱 | 高 | 并发时缓存读到旧值 |
| 延迟双删 | 较强 | 中 | 延迟时间不好确定 |
| 订阅binlog | 强 | 高 | 架构复杂 |

### 12.2 推荐方案：先更新DB + 延迟双删

```java
public void updateProduct(Product product) {
    // 1. 先删除缓存
    redis.del("product:" + product.getId());
    
    // 2. 更新数据库
    db.update(product);
    
    // 3. 延迟再删一次（防止并发时旧数据回填缓存）
    CompletableFuture.delayedExecutor(500, TimeUnit.MILLISECONDS)
        .execute(() -> redis.del("product:" + product.getId()));
}
```

### 12.3 终极方案：订阅binlog异步更新缓存

```
MySQL → binlog → Canal → MQ → 消费者更新Redis
```

保证最终一致性，适合对一致性要求高的场景。

---

## 总结

| 主题 | 核心要点 |
|------|---------|
| RDB持久化 | BGSAVE + COW，文件小恢复快，可能丢数据 |
| AOF持久化 | 追加日志 + 三种fsync策略 + AOF重写 |
| 混合持久化 | RDB头部 + AOF尾部，推荐默认开启 |
| 主从复制 | 全量同步(RDB) + 增量同步(repl_backlog) |
| 哨兵模式 | 监控 + 通知 + 自动故障转移，需quorum |
| Cluster集群 | 16384槽 + Gossip协议 + 自动故障转移 |
| 缓存穿透 | 布隆过滤器 + 缓存空值 |
| 缓存击穿 | 互斥锁 + 逻辑过期 |
| 缓存雪崩 | 随机过期 + 高可用 + 降级限流 |
| 数据一致性 | 先更新DB再删缓存 + 延迟双删 / binlog |

下期预告：
- 数据库面试八股文（九）——MongoDB与Elasticsearch核心原理
- 数据库面试八股文（十）——数据库综合面试题与实战
