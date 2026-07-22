---
title: 数据库面试八股文（七）——Redis核心数据结构与应用场景
date: 2026-06-03 11:00:00+08:00
updated: '2026-06-03T11:00:00+08:00'
description: 面试高频考点：Redis五种基本数据结构的底层实现、三种特殊数据结构的应用场景、跳表原理、对象系统。本文从SDS到跳表，从原理到实战，全面覆盖Redis数据结构面试题。 Redis每个键值对都是一个对象： type：对外暴露的类型（STRING,
  LIST, HASH, SET, ZSET） enc。
topic: database-middleware
series: database-interview
series_order: 7
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Redis
- 数据结构
- String
categories:
- 数据库与中间件
draft: false
---

> 面试高频考点：Redis五种基本数据结构的底层实现、三种特殊数据结构的应用场景、跳表原理、对象系统。本文从SDS到跳表，从原理到实战，全面覆盖Redis数据结构面试题。

---

## 一、Redis对象系统

### 1.1 Redis对象结构

Redis每个键值对都是一个对象：

```c
typedef struct redisObject {
    unsigned type:4;        // 类型（4bit）
    unsigned encoding:4;    // 编码（4bit）
    unsigned lru:LRU_BITS;  // LRU时间或LFU数据
    int refcount;           // 引用计数
    void *ptr;              // 指向底层数据结构的指针
} robj;
```

**type**：对外暴露的类型（STRING, LIST, HASH, SET, ZSET）
**encoding**：底层实现的数据结构（同一type可以有多种encoding）

### 1.2 类型与编码对应关系

| 类型 | 编码 | 底层数据结构 |
|------|------|-------------|
| STRING | int | 整数值 |
| STRING | embstr | embstr编码的SDS |
| STRING | raw | SDS |
| LIST | listpack | 紧凑列表（Redis 7.0+） |
| LIST | quicklist | 快速列表 |
| HASH | listpack | 紧凑列表（小数据量） |
| HASH | ht | 字典（大数据量） |
| SET | intset | 整数集合（全整数+小数据量） |
| SET | ht | 字典 |
| SET | listpack | 紧凑列表（Redis 7.2+） |
| ZSET | listpack | 紧凑列表（小数据量） |
| ZSET | skiplist + ht | 跳表 + 字典 |

> 💡 **面试重点**：Redis会根据数据量自动切换编码，这个过程称为**编码转换**

---

## 二、String（字符串）

### 2.1 底层实现：SDS

SDS（Simple Dynamic String）是Redis自己实现的字符串，替代C语言字符串：

```c
struct sdshdr {
    int len;       // 已使用长度
    int free;      // 剩余空间
    char buf[];    // 数据数组
};
```

**SDS vs C字符串**：

| 对比维度 | C字符串 | SDS |
|---------|---------|-----|
| 获取长度 | O(N)遍历 | O(1)直接读len |
| 缓冲区溢出 | 不安全（strcpy等） | 安全（自动扩容） |
| 修改内存重分配 | 每次必重分配 | 预分配+惰性释放 |
| 二进制安全 | 依赖\0结尾 | len判断长度 |

**空间预分配策略**：
- len < 1MB → free = len（总空间 = 2*len+1）
- len ≥ 1MB → free = 1MB（总空间 = len+1MB+1）

**惰性释放**：缩短字符串不释放内存，增加free空间

### 2.2 三种编码

```
┌───────────────────────────────────────────────┐
│                  String对象                     │
├───────────────┬───────────────┬───────────────┤
│     int       │    embstr     │     raw       │
│  整数值       │  短字符串      │  长字符串      │
│  ≤long范围   │  ≤44字节      │  >44字节      │
│  8字节       │  1次内存分配   │  2次内存分配   │
└───────────────┴───────────────┴───────────────┘
```

**embstr vs raw**：
- embstr将redisObject和SDS连续分配在一块内存，只需1次malloc
- raw需要2次malloc（redisObject和SDS分开）
- embstr只读，修改时转为raw

### 2.3 应用场景

| 场景 | 命令 | 说明 |
|------|------|------|
| 缓存 | SET/GET | 最基本用法 |
| 计数器 | INCR/INCRBY | 原子操作，阅读量、点赞数 |
| 分布式锁 | SET NX EX | 互斥 + 过期 |
| 限速器 | INCR + EXPIRE | API限流 |
| 共享Session | SET/GET | 登录态 |

**分布式锁示例**：
```redis
SET lock:order:123 "unique_id" NX EX 30
-- 释放锁（Lua保证原子性）
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

---

## 三、List（列表）

### 3.1 底层实现：quicklist

quicklist = 双向链表 + listpack（替代ziplist）

```
quicklist
┌──────────┐    ┌──────────┐    ┌──────────┐
│ listpack │◄──→│ listpack │◄──→│ listpack │
│ [a,b,c]  │    │ [d,e,f]  │    │ [g,h]    │
└──────────┘    └──────────┘    └──────────┘
```

**设计原因**：
- 纯链表：每个节点单独分配，内存碎片多
- 纯ziplist：连续内存，但插入/删除要realloc，大数据量性能差
- quicklist折中：每个节点是一个小ziplist/listpack，兼顾内存和性能

**压缩配置**：
- `list-compress-depth`：首尾不压缩，中间节点LZF压缩
- `list-max-listpack-size`：每个节点的大小限制

### 3.2 应用场景

| 场景 | 命令 | 说明 |
|------|------|------|
| 消息队列 | LPUSH + BRPOP | 阻塞队列 |
| 最新列表 | LPUSH + LRANGE | 最新N条消息/动态 |
| 栈 | LPUSH + LPOP | 先进后出 |
| 队列 | LPUSH + RPOP | 先进先出 |

---

## 四、Hash（哈希）

### 4.1 底层实现

**小数据量 → listpack**（紧凑列表）：
- 连续内存，省空间
- 元素少时查找也快

**大数据量 → ht**（字典/哈希表）：
- 链地址法解决冲突
- 渐进式rehash

**编码转换阈值**：
- `hash-max-listpack-entries`：默认128
- `hash-max-listpack-value`：默认64字节

### 4.2 渐进式rehash

当哈希表负载因子过高时需要扩容，但不能一次性迁移（会阻塞服务），所以采用渐进式方式：

```c
// Redis有两个哈希表 ht[0] 和 ht[1]
// rehash期间，每次CRUD操作顺带迁移一个bucket

dictFind(key) {
    // 先查ht[0]，再查ht[1]
    // 同时将ht[0]的一个bucket迁移到ht[1]
}
```

**rehash触发条件**：
- 扩容：负载因子 ≥ 1（无BGSAVE/BGREWRITEAOF）或 ≥ 5（有后台进程）
- 缩容：负载因子 < 0.1

**负载因子** = 已保存节点数 / 哈希表大小

### 4.3 应用场景

| 场景 | 命令 | 说明 |
|------|------|------|
| 对象缓存 | HSET/HGETALL | 存储用户信息、商品信息 |
| 购物车 | HSET cart:uid pid count | 商品ID为field，数量为value |
| 计数器组 | HINCRBY | 多维计数 |

**Hash vs String存对象**：

```redis
-- String方式（需序列化）
SET user:1 '{"name":"张三","age":25}'

-- Hash方式（可部分读写）
HMSET user:1 name "张三" age 25
HGET user:1 name     -- 只读一个字段
HINCRBY user:1 age 1 -- 只改一个字段
```

> Hash方式更灵活，但嵌套对象处理不如String方便

---

## 五、Set（集合）

### 5.1 底层实现

**intset**（整数集合）：
- 条件：所有元素都是整数 + 元素数量 ≤ `set-max-intset-entries`（默认512）
- 有序数组，二分查找
- 升级机制：int16 → int32 → int64

**ht**（字典）：
- 所有value为NULL的字典
- O(1)查找

### 5.2 应用场景

| 场景 | 命令 | 说明 |
|------|------|------|
| 去重 | SADD | 唯一性保证 |
| 标签 | SADD | 用户标签、文章标签 |
| 共同关注 | SINTER | 交集运算 |
| 可能认识 | SDIFF/SUNION | 差集/并集 |
| 抽奖 | SRANDMEMBER/SPOP | 随机取元素 |

```redis
-- 共同关注
SINTER follow:用户A follow:用户B

-- 我关注的人关注了他（可能认识）
SDIFF follow:用户A follow:用户B  -- A关注但B没关注
```

---

## 六、ZSet（有序集合）

### 6.1 底层实现：跳表 + 字典

**为什么用跳表而不用红黑树？**

| 维度 | 跳表 | 红黑树 |
|------|------|--------|
| 范围查询 | O(logN + M)，链表遍历 | O(logN + M)，中序遍历（实现复杂） |
| 实现难度 | 简单 | 复杂 |
| 并发友好 | 局部修改，易加锁 | 旋转操作，难加锁 |
| 内存占用 | 指针多，略大 | 更紧凑 |
| 插入/删除 | O(logN) | O(logN) |

> 💡 **面试回答**：跳表实现简单、范围查询方便、并发友好。Redis是单线程所以并发不是主因，**范围查询和实现简单**是核心原因。

### 6.2 跳表原理

```
Level 4:  1 ────────────────────────────────→ 21
Level 3:  1 ────────────── 11 ──────────────→ 21
Level 2:  1 ──── 4 ──── 7 ──── 11 ──── 17 ─→ 21
Level 1:  1 → 3 → 4 → 6 → 7 → 9 → 11 → 14 → 17 → 19 → 21
```

**查找过程**：从最高层开始，向右比较，大于目标则下移一层
**插入过程**：先查找位置，随机决定层数（层数越高概率越低）
**层数计算**：每层50%概率继续向上，最大32层

**时间复杂度**：查找/插入/删除均为O(logN)

### 6.3 编码转换

- 元素数量 ≤ `zset-max-listpack-entries`（默认128）且每个元素 ≤ `zset-max-listpack-value`（默认64字节）→ listpack
- 否则 → skiplist + ht

### 6.4 应用场景

| 场景 | 命令 | 说明 |
|------|------|------|
| 排行榜 | ZADD + ZREVRANGE | 游戏排名、热搜榜 |
| 延迟队列 | ZADD + ZRANGEBYSCORE | 时间戳作为score |
| 滑动窗口限流 | ZADD + ZREMRANGEBYSCORE + ZCARD | 时间窗口计数 |
| 优先级队列 | ZADD + ZPOPMIN | score作为优先级 |

**排行榜示例**：
```redis
-- 添加/更新分数
ZADD rank:game 95 "玩家A" 88 "玩家B" 92 "玩家C"

-- Top 10（降序）
ZREVRANGE rank:game 0 9 WITHSCORES

-- 查询排名
ZREVRANK rank:game "玩家A"

-- 加分
ZINCRBY rank:game 5 "玩家B"
```

**滑动窗口限流**：
```redis
-- 当前时间戳作为score
ZADD limit:user:123 1717400000 "req_1"

-- 移除窗口外的请求
ZREMRANGEBYSCORE limit:user:123 0 1717396400

-- 统计窗口内请求数
ZCARD limit:user:123

-- 如果数量超限则拒绝
```

---

## 七、三种特殊数据结构

### 7.1 HyperLogLog

**用途**：基数统计（去重计数），如UV统计

| 命令 | 说明 |
|------|------|
| PFADD | 添加元素 |
| PFCOUNT | 获取基数估计值 |
| PFMERGE | 合并多个HyperLogLog |

**特点**：
- 12KB固定内存，无论多少元素
- 0.81%标准误差
- 不存储元素本身，只做计数

**原理**：伯努利试验 + 调和平均数

```
输入 → Hash → 二进制位 → 统计前导零最大长度 → 估计基数
```

### 7.2 Bitmap

**用途**：位运算，布尔型数据存储

| 命令 | 说明 |
|------|------|
| SETBIT | 设置某位 |
| GETBIT | 获取某位 |
| BITCOUNT | 统计1的个数 |
| BITOP | 位运算（AND/OR/XOR） |

**应用场景**：

```redis
-- 签到
SETBIT sign:uid:123:202606 2 1   -- 6月3日签到（offset从0开始）

-- 统计本月签到天数
BITCOUNT sign:uid:123:202606

-- 连续签到检查
BITOP AND result sign:uid:123:202605 sign:uid:123:202606
```

**内存优势**：1亿用户签到，Bitmap仅需约12MB

### 7.3 GeoSpatial

**用途**：地理位置信息

| 命令 | 说明 |
|------|------|
| GEOADD | 添加经纬度 |
| GEODIST | 计算两点距离 |
| GEORADIUS | 查询指定半径内的点 |
| GEOHASH | 获取GeoHash编码 |

**底层**：ZSet + GeoHash编码

```redis
-- 添加商户位置
GEOADD shops:beijing 116.397128 39.916527 "天安门"

-- 查找3公里内的商户
GEORADIUS shops:beijing 116.397128 39.916527 3 km WITHDIST
```

---

## 八、Stream（流）

Redis 5.0引入，是最完整的消息队列实现：

| 特性 | 说明 |
|------|------|
| 消费者组 | 支持多消费者分组消费 |
| 消息确认 | ACK机制 |
| 持久化 | 消息持久化到AOF/RDB |
| 消息ID | 时间戳+序号，严格有序 |
| 历史消息 | 可回溯已消费消息 |

```redis
-- 生产消息
XADD mystream * name "张三" action "login"

-- 消费者组读取
XREADGROUP GROUP mygroup consumer1 COUNT 1 BLOCK 2000 STREAMS mystream >

-- 确认消息
XACK mystream mygroup 1717400000000-0
```

---

## 九、面试高频题

### Q1：Redis为什么单线程还这么快？

1. **纯内存操作**：数据在内存中，读写极快
2. **IO多路复用**：epoll/kqueue，单线程处理大量连接
3. **高效数据结构**：SDS、跳表、listpack等优化
4. **避免上下文切换**：无需加锁，无线程切换开销
5. **单线程无竞争**：无锁无死锁，无并发安全问题

> ⚠️ Redis 6.0+引入多线程IO，但命令执行仍是单线程

### Q2：Redis数据过期策略和内存淘汰策略？

**过期策略**：惰性删除 + 定期删除
- 惰性删除：访问key时检查是否过期
- 定期删除：每100ms随机检查一批key，删除过期的

**内存淘汰策略**（`maxmemory-policy`）：

| 策略 | 说明 |
|------|------|
| noeviction | 不淘汰，写入报错（默认） |
| allkeys-lru | 所有key中淘汰最久未使用的 |
| allkeys-lfu | 所有key中淘汰使用频率最低的 |
| allkeys-random | 所有key中随机淘汰 |
| volatile-lru | 过期key中淘汰最久未使用的 |
| volatile-lfu | 过期key中淘汰使用频率最低的 |
| volatile-random | 过期key中随机淘汰 |
| volatile-ttl | 过期key中淘汰TTL最短的 |

### Q3：缓存穿透、缓存击穿、缓存雪崩？

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 缓存穿透 | 查不存在的数据 | 布隆过滤器 / 缓存空值 |
| 缓存击穿 | 热点key过期 | 互斥锁 / 永不过期 |
| 缓存雪崩 | 大量key同时过期 | 随机过期时间 / 多级缓存 |

### Q4：如何选择Redis数据结构？

| 需求 | 推荐 | 原因 |
|------|------|------|
| 简单KV | String | 直接存取 |
| 对象属性 | Hash | 部分读写 |
| 去重 | Set | 天然去重 |
| 排序 | ZSet | score排序 |
| 时间线 | List | 有序队列 |
| UV计数 | HyperLogLog | 省内存 |
| 签到 | Bitmap | 位操作 |
| 附近的人 | Geo | 地理计算 |

---

## 总结

| 数据结构 | 底层实现 | 核心特点 | 典型场景 |
|---------|---------|---------|---------|
| String | SDS | 三种编码自动切换 | 缓存/计数器/分布式锁 |
| List | quicklist | 链表+压缩节点 | 消息队列/最新列表 |
| Hash | listpack/ht | 渐进式rehash | 对象缓存/购物车 |
| Set | intset/ht | 自动编码转换 | 去重/标签/交集 |
| ZSet | listpack/skiplist+ht | 跳表O(logN) | 排行榜/延迟队列 |

下期预告：
- 数据库面试八股文（八）——Redis持久化、集群与缓存问题
- 数据库面试八股文（九）——MongoDB与ES核心原理
