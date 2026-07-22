---
title: Redis面试八股文（二）——持久化、过期策略与内存淘汰
date: 2026-06-21 09:00:00+08:00
updated: '2026-06-21T09:00:00+08:00'
description: '🎯 本文目标：承接上一篇五大数据结构的底层原理，本文将转向Redis数据安全与内存管理两大核心主题——从RDB快照与AOF日志的底层机制对比，到混合持久化的技术演进，再到键过期策略的惰性+定期双管齐下，最终深入八种内存淘汰算法的原理、适用场景与实战选型。
  Q: RDB持久化的原理是什么？ RDB（R。'
topic: database-middleware
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Redis
- RDB
- AOF
categories:
- 数据库与中间件
draft: false
---

> 🎯 **本文目标**：承接上一篇五大数据结构的底层原理，本文将转向Redis数据安全与内存管理两大核心主题——从RDB快照与AOF日志的底层机制对比，到混合持久化的技术演进，再到键过期策略的惰性+定期双管齐下，最终深入八种内存淘汰算法的原理、适用场景与实战选型。

---

## 一、RDB持久化——内存快照

### 1.1 RDB是什么？

**Q: RDB持久化的原理是什么？**

RDB（Redis DataBase）是将某一时刻的内存数据以**二进制快照**的形式保存到磁盘。可以理解为给Redis内存拍了一张"照片"。

| 特性 | 说明 |
|------|------|
| 触发方式 | save（阻塞）/ bgsave（fork子进程） |
| 文件格式 | 二进制压缩dump.rdb |
| 恢复速度 | 快，直接加载到内存 |
| 数据丢失 | 最后一次快照后的数据 |

### 1.2 bgsave的fork原理

**Q: bgsave时Redis还能处理请求吗？为什么？**

bgsave的核心机制是操作系统的**写时复制（Copy-On-Write, COW）**：

```
主进程                    子进程
  │                         │
  │── fork() ──────────────►│
  │                         │── 共享父进程内存页（只读）
  │── 处理客户端请求         │── 遍历所有数据写入RDB
  │                         │
  │── 修改Key A时：         │
  │   复制该内存页           │
  │   在副本上修改           │── 子进程仍读原始页
  │                         │
  │                         │── 写入完成，退出
```

**关键点：**
1. fork()时父子进程共享同一块物理内存
2. 父进程修改数据时，OS会复制被修改的内存页
3. 子进程始终读取fork那一刻的快照数据
4. COW确保bgsave期间不需要锁，不影响读写

### 1.3 RDB的配置与触发

```bash
# redis.conf 配置
save 900 1      # 900秒内至少1个key变化
save 300 10     # 300秒内至少10个key变化
save 60 10000   # 60秒内至少10000个key变化

dbfilename dump.rdb
dir /var/lib/redis
```

**Q: save和bgsave的区别？为什么不推荐用save？**

| 对比维度 | save | bgsave |
|----------|------|--------|
| 是否阻塞 | 阻塞所有客户端请求 | 仅fork时短暂阻塞 |
| 执行方式 | 主进程直接执行 | fork子进程执行 |
| 适用场景 | 关机维护时手动 | 生产环境自动触发 |
| 风险 | 数据量大时可能阻塞数秒 | 内存翻倍风险 |

### 1.4 RDB的优缺点

**优点：**
- 文件紧凑，适合备份和灾难恢复
- 恢复大数据集时比AOF快
- 对性能影响小（fork子进程处理）

**缺点：**
- 数据安全性较低（两次快照间的数据可能丢失）
- fork子进程时内存占用翻倍
- 频繁fork可能影响性能

---

## 二、AOF持久化——命令日志

### 2.1 AOF是什么？

**Q: AOF持久化的原理是什么？**

AOF（Append Only File）记录Redis执行的**每一条写命令**，重启时通过重放命令恢复数据。类似于MySQL的binlog。

```
客户端: SET name "zhangsan"
   │
   ▼
Redis Server:
   │── 执行命令，修改内存数据
   │── 将命令追加到AOF缓冲区
   │── 根据fsync策略刷盘
```

### 2.2 AOF的三种刷盘策略

**Q: AOF的fsync策略有哪些？各自优缺点是什么？**

| 策略 | 配置值 | 行为 | 数据安全 | 性能 |
|------|--------|------|----------|------|
| 每次刷盘 | always | 每个写命令后fsync | 最高，最多丢1条 | 最低 |
| 每秒刷盘 | everysec | 每秒fsync一次 | 较高，最多丢1秒 | 平衡 |
| 不主动刷盘 | no | 交给OS决定 | 最低 | 最高 |

```bash
# redis.conf
appendonly yes
appendfsync everysec    # 推荐配置
```

**always vs everysec的选择场景：**
- **always**：对数据安全性要求极高（金融交易核心数据）
- **everysec**：绝大多数场景的推荐配置，性能与安全的平衡点
- **no**：纯缓存场景，数据可丢失

### 2.3 AOF重写机制

**Q: AOF文件为什么越来越大？如何解决？**

随着运行时间增长，AOF文件会包含大量冗余命令。例如：

```
SET counter 1   ← 第一条
INCR counter    ← 冗余
INCR counter    ← 冗余
INCR counter    ← 冗余
DEL counter     ← 最终counter已不存在
```

AOF重写（Rewrite）将冗余命令合并为最精简的形式：
```
# 重写后：counter已被删除，不再写入
```

**重写原理（BGREWRITEAOF）：**

```
主进程                    子进程
  │                         │
  │── fork() ──────────────►│
  │                         │── 根据当前内存数据生成新AOF
  │── 处理写入请求           │
  │── 写入AOF重写缓冲区 ◄────│
  │                         │── 新AOF生成完毕
  │── 追加缓冲区到新AOF      │
  │── 原子rename替换旧AOF   │
```

**AOF重写触发条件：**
```bash
auto-aof-rewrite-percentage 100   # 比上次重写时增长100%
auto-aof-rewrite-min-size 64mb    # 最小64MB才触发
```

### 2.4 RDB vs AOF 如何选择？

**面试高频问题：生产环境用RDB还是AOF？**

| 维度 | RDB | AOF |
|------|-----|-----|
| 数据安全性 | 可能丢失几分钟 | 最多丢失1秒 |
| 恢复速度 | 快 | 慢（重放命令） |
| 文件大小 | 小 | 大 |
| IO性能影响 | fork时短暂影响 | 持续写入影响 |
| 可读性 | 二进制不可读 | 文本可读 |

**最佳实践（大多数场景）：两者同时开启，AOF优先恢复。**

---

## 三、混合持久化——Redis 4.0的进化

### 3.1 混合持久化原理

**Q: Redis 4.0的混合持久化是什么？解决了什么问题？**

混合持久化是RDB和AOF的结合体：AOF重写时，将重写时刻的内存数据以RDB格式写入AOF文件头部，后续的增量命令以AOF格式追加。

**文件结构：**
```
┌─────────────────────────────────────┐
│           RDB格式（全量数据）          │  ← 重写时的内存快照
├─────────────────────────────────────┤
│           AOF格式（增量命令）          │  ← 重写后的写操作
└─────────────────────────────────────┘
```

**优势：**
1. 兼具RDB的快速恢复和AOF的数据安全
2. 重写后的AOF文件前半部分是RDB，体积更小
3. 恢复时前半部分直接加载RDB，后半部分重放AOF

```bash
# redis.conf（Redis 5.0+默认开启）
aof-use-rdb-preamble yes
```

### 3.2 面试总结：持久化演进路线

```
Redis 1.0   → 仅支持内存，无持久化
Redis 1.1   → 引入RDB（bgsave）
Redis 1.1   → 引入AOF
Redis 2.4   → 引入AOF Rewrite的增量缓冲
Redis 4.0   → 引入混合持久化（RDB+AOF融合）
Redis 7.0   → AOF多部分文件（Multi-Part AOF）
```

---

## 四、过期删除策略——键的生命周期管理

### 4.1 三种过期删除策略对比

**Q: Redis如何删除过期键？**

| 策略 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 定时删除 | 每个key设一个定时器 | 内存友好 | CPU不友好，定时器开销大 |
| 惰性删除 | 访问时检查是否过期 | CPU友好 | 内存不友好 |
| 定期删除 | 每隔一段时间抽样删除 | 折中方案 | 实现复杂 |

**Redis的组合策略：惰性删除 + 定期删除**

### 4.2 惰性删除

```c
// 伪代码：每次读写命令前检查key是否过期
int expireIfNeeded(redisDb *db, robj *key) {
    if (!keyIsExpired(db, key)) return 0;
    // 惰性删除
    if (server.masterhost == NULL) {
        deleteKey(db, key);
        return 1;  // key已删除
    }
    return 1;  // 从节点只返回过期，不主动删除
}
```

**惰性删除触发时机：**
- 执行任何读写命令前（GET, SET, HGET, LPUSH等）
- `expireIfNeeded()` 会被所有命令调用

### 4.3 定期删除

**Q: 定期删除的具体流程是怎样的？**

```c
// 简化版定期删除流程
void activeExpireCycle(int type) {
    // 每个周期检查多个数据库
    for (each database) {
        // 随机抽取20个带过期时间的key
        // 删除其中已过期的key
        // 如果过期比例 > 25%，继续循环该数据库
        // 如果过期比例 < 25%，切换到下一个数据库
    }
    // 限制总执行时间不超过CPU时间的25%
}
```

**定期删除的关键设计：**
1. **随机抽取**：不遍历全部，每次随机取20个key
2. **自适应循环**：过期比例高时继续处理，低时切换DB
3. **CPU时间限制**：单次执行不超过25ms（hz配置影响频率）
4. **模式区分**：快速模式（FAST）和慢速模式（SLOW）

### 4.4 主从架构下的过期策略

**Q: Redis主从模式下过期键怎么处理？**

```
主节点：
  1. 惰性删除：发现过期 → 删除Key → 向从节点发送DEL命令
  2. 定期删除：发现过期 → 删除Key → 向从节点发送DEL命令

从节点：
  1. 惰性删除：发现过期 → 不删除 → 返回客户端（逻辑过期）
  2. 等待主节点的DEL命令才真正删除
```

**核心规则：从节点不主动删除过期键，一切以主节点为准。**

---

## 五、内存淘汰策略——内存不够怎么办？

### 5.1 八种内存淘汰策略全景

**Q: Redis内存满了怎么办？有哪些淘汰策略？**

| 策略 | 配置值 | 行为 | 适用场景 |
|------|--------|------|----------|
| 不淘汰 | noeviction | 拒绝写入，返回错误 | 不允许数据丢失的核心数据 |
| 全局LRU | allkeys-lru | 淘汰最近最少使用的key | 通用缓存场景 |
| 全局LFU | allkeys-lfu | 淘汰最近最不频繁使用的key | 热点数据缓存 |
| 全局随机 | allkeys-random | 随机淘汰 | 数据访问无规律 |
| 过期LRU | volatile-lru | 有过期时间的key中LRU淘汰 | 混合场景（缓存+持久） |
| 过期LFU | volatile-lfu | 有过期时间的key中LFU淘汰 | 过期缓存优化 |
| 过期随机 | volatile-random | 有过期时间的key中随机淘汰 | 简单场景 |
| 过期TTL | volatile-ttl | 淘汰最快过期的key | 临时数据缓存 |

### 5.2 LRU算法深入

**Q: Redis的LRU和标准LRU有什么不同？**

**标准LRU：**
```
双向链表 + HashMap，O(1)淘汰最久未使用的节点。
缺点：每个key需要额外指针开销。
```

**Redis近似LRU：**
```c
// Redis在每个对象中维护一个24位的lru时钟
typedef struct redisObject {
    unsigned type:4;
    unsigned encoding:4;
    unsigned lru:LRU_BITS;  // 24位，记录最近访问时间
    int refcount;
    void *ptr;
} robj;

// 淘汰时随机采样N个key，淘汰其中最久未访问的
// N由 maxmemory-samples 配置（默认5）
```

**面试重点：Redis为什么不实现标准LRU？**

| 对比 | 标准LRU | Redis 近似LRU |
|------|---------|--------------|
| 内存开销 | 高（双向链表指针） | 低（24位时钟） |
| 精度 | 精确 | 近似（采样越多越准） |
| 性能 | O(1)淘汰，但维护成本高 | O(N)采样，但N很小 |
| 实现复杂度 | 高 | 低 |

```bash
# 精度配置
maxmemory-policy allkeys-lru
maxmemory-samples 10   # 越大越精确，但越耗CPU（默认5）
```

### 5.3 LFU算法深入

**Q: LFU和LRU的区别？Redis如何实现LFU？**

**LRU vs LFU：**

| 维度 | LRU | LFU |
|------|-----|-----|
| 核心思想 | 最近没用的淘汰 | 最不频繁用的淘汰 |
| 计数方式 | 最近访问时间 | 访问频率 |
| 适用场景 | 热点随时间变化 | 热点相对稳定 |
| 典型问题 | 偶发大量访问的key不会被淘汰 | 历史高频key难以淘汰 |

**Redis LFU的实现：**

Redis复用了24位lru字段来实现LFU：
```
24位分为两部分：
┌──────────────┬──────────────┐
│  16位 ldt    │   8位 logc   │
│ (最近访问时间) │  (对数计数器)  │
└──────────────┴──────────────┘

- ldt（Last Decrement Time）：上次衰减时间
- logc（Logarithmic Counter）：对数访问计数器（0-255）
```

**LFU计数规则：**
1. 每次访问，logc增加（不是线性增长，是对数增长）
2. 随着时间推移，logc会衰减（防止历史高频key永不淘汰）
3. 淘汰时选择logc最小的key

```c
// 伪代码：LFU计数增长
void LFULogIncr(uint8_t *counter) {
    double r = (double)rand() / RAND_MAX;
    double baseval = *counter - LFU_INIT_VAL;
    double p = 1.0 / (baseval * lfu_log_factor + 1);
    if (r < p) (*counter)++;
}

// LFU衰减
unsigned long LFUDecrAndReturn(robj *o) {
    unsigned long ldt = o->lru >> 8;          // 上次衰减时间
    unsigned long counter = o->lru & 0xFF;     // 当前计数器
    unsigned long num_periods = server.lfu_decay_time ?
        (minutes_diff / server.lfu_decay_time) : 0;
    if (num_periods)
        counter = (num_periods > counter) ? 0 : counter - num_periods;
    return counter;
}
```

```bash
# LFU相关配置
lfu-log-factor 10       # 对数因子，越大增长越慢（默认10）
lfu-decay-time 1        # 衰减周期（分钟），默认1
```

### 5.4 内存淘汰策略选择指南

```
你的Redis用途是什么？
  │
  ├── 纯缓存（数据可丢失）
  │   ├── 热点随时间变化 → allkeys-lru（推荐）
  │   └── 热点相对稳定 → allkeys-lfu
  │
  ├── 既有缓存又有持久化数据
  │   ├── 热点随时间变化 → volatile-lru
  │   └── 热点相对稳定 → volatile-lfu
  │
  └── 不能丢失数据（消息队列、计数器等）
      └── noeviction + 监控告警
```

---

## 六、实战场景分析

### 6.1 场景一：缓存雪崩

**问题：** 大量key同时过期，请求全部打到数据库。

**方案：** 过期时间加随机因子

```java
// 在基础过期时间上增加随机值
int baseExpire = 3600;  // 1小时
int randomOffset = new Random().nextInt(300);  // 0-5分钟
jedis.setex("hot:data:" + id, baseExpire + randomOffset, value);
```

### 6.2 场景二：大Key的过期删除

**Q: Redis删除大Key会阻塞吗？如何解决？**

**问题：** 删除包含百万元素的List/Hash/Set/ZSet时，单线程执行DEL会阻塞。

**解决方案：Redis 4.0+引入的UNLINK（异步删除）**

```
DEL bigkey     → 阻塞主线程，stalled
UNLINK bigkey  → 后台线程异步回收内存，主线程不阻塞
```

```bash
# 配置：自动将DEL转为UNLINK
lazyfree-lazy-eviction yes      # 内存淘汰时异步删除
lazyfree-lazy-expire yes         # 过期键异步删除
lazyfree-lazy-server-del yes     # 隐式DEL（rename等）异步删除
```

### 6.3 场景三：内存淘汰与过期策略的配合

**生产环境推荐配置：**

```bash
# Redis作为缓存层
maxmemory 4gb                      # 根据机器内存设定
maxmemory-policy allkeys-lru       # 通用缓存策略
maxmemory-samples 10               # 提高LRU精度

# 持久化配置
save 900 1                         # RDB备份
save 300 10
appendonly yes                     # 开启AOF
appendfsync everysec               # 每秒刷盘
aof-use-rdb-preamble yes           # 混合持久化

# 惰性删除优化
lazyfree-lazy-eviction yes         # 淘汰异步删除
lazyfree-lazy-expire yes           # 过期异步删除
```

### 6.4 场景四：内存使用率监控

```bash
# 查看内存使用详情
INFO memory

# 关键指标：
# used_memory: 当前使用内存
# used_memory_rss: 操作系统分配内存（含碎片）
# mem_fragmentation_ratio: 内存碎片率 = rss/used_memory
#   - > 1.5: 碎片较多，考虑重启或启用activedefrag
#   - < 1: 使用了swap，性能会下降
# maxmemory: 最大内存限制

# 查看大Key
redis-cli --bigkeys

# 查看过期key统计
INFO stats | grep expired
```

---

## 七、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| RDB | bgsave + COW，fork子进程写快照 | save/bgsave, COW, dump.rdb |
| AOF | 命令日志，三种刷盘策略，AOF重写 | always/everysec/no, BGREWRITEAOF |
| 混合持久化 | RDB头部 + AOF增量，Redis 4.0+ | aof-use-rdb-preamble |
| 过期策略 | 惰性删除 + 定期删除双管齐下 | expireIfNeeded, activeExpireCycle |
| 内存淘汰 | 八种策略，近似LRU，LFU对数计数 | allkeys-lru, volatile-lfu, maxmemory-policy |
| 异步删除 | UNLINK解决大Key删除阻塞 | lazyfree, UNLINK vs DEL |

**Redis持久化+内存管理三大心法：**
1. **持久化选型**：AOF（everysec）保证安全，RDB辅助备份，混合持久化是未来
2. **过期策略**：惰性+定期的折中哲学，适用于Redis所有时间相关设计
3. **内存淘汰**：LRU适合热点变化的缓存，LFU适合热点稳定的缓存，noeviction适合持久数据

> 🎯 **Redis面试八股文系列第二篇！** 本文从RDB/AOF/混合持久化的底层机制出发，深入过期删除的惰性+定期双策略、八种内存淘汰算法的原理与选型，以及大Key异步删除、缓存雪崩等生产实战场景，构建了Redis数据安全与内存管理的完整知识体系。

> 📌 **下期预告**：《Redis面试八股文（三）——主从复制、哨兵机制与Redis Cluster集群》将深入全量复制/部分复制的底层协议、sentinel的主观下线和客观下线判定、Redis Cluster的16384槽位分配与MOVED/ASK重定向机制，以及节点间Gossip协议通信原理，敬请期待！
