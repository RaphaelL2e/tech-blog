---
title: Redis 性能优化与实战
date: 2026-05-13 19:00:00+08:00
updated: '2026-05-13T19:00:00+08:00'
description: 本系列前面四篇分别探讨了 Redis 的数据结构、持久化与内存管理、主从复制与高可用、缓存问题（穿透/击穿/雪崩）。作为系列最后一篇，本文将聚焦 Redis 的性能优化技巧、Pipeline 与 Lua 脚本、分布式锁实战、慢查询分析等实战内容，帮助你系统掌握
  Redis 在生产环境中的最佳实践。
topic: database-middleware
level: intermediate
status: maintained
tags:
- Redis
- 性能优化
- Pipeline
- Lua 脚本
- 分布式锁
categories:
- 数据库与中间件
draft: false
---

## 一、引言

本系列前面四篇分别探讨了 Redis 的数据结构、持久化与内存管理、主从复制与高可用、缓存问题（穿透/击穿/雪崩）。作为系列最后一篇，本文将聚焦 Redis 的性能优化技巧、Pipeline 与 Lua 脚本、分布式锁实战、慢查询分析等实战内容，帮助你系统掌握 Redis 在生产环境中的最佳实践。

**本文要点**：
1. 慢查询分析与性能监控
2. 内存优化技巧
3. Pipeline 与批量操作
4. Lua 脚本保证原子性
5. 分布式锁实战（Redlock）
6. Redis 最佳实践总结

---

## 二、慢查询分析与性能监控

### 2.1 慢查询日志

Redis 的慢查询日志用于记录执行时间超过指定阈值的命令。

**配置参数**：

```bash
# redis.conf
slowlog-log-slower-than 10000   # 单位：微秒（μs），默认 10000 = 10 毫秒
slowlog-max-len 128               # 慢查询日志最大长度（FIFO 队列）
```

**动态配置**：

```bash
redis-cli CONFIG SET slowlog-log-slower-than 5000
redis-cli CONFIG SET slowlog-max-len 256
```

**查看慢查询**：

```bash
# 查看所有慢查询
SLOWLOG GET [count]

# 查看慢查询条数
SLOWLOG LEN

# 清空慢查询日志
SLOWLOG RESET
```

**示例输出**：

```
127.0.0.1:6379> SLOWLOG GET 2
1) 1) (integer) 14           # 慢查询 ID
   2) (integer) 1528354123   # 时间戳
   3) (integer) 15000        # 执行时间（微秒）
   4) 1) "KEYS"              # 命令及其参数
      2) "*"
   5) "127.0.0.1:53452"     # 客户端地址
   6) ""
2) 1) (integer) 13
   2) (integer) 1528354000
   3) (integer) 12000
   4) 1) "HGETALL"
      2) "large_hash_key"
   5) "127.0.0.1:53450"
   6) ""
```

**分析要点**：
- `KEYS *` 是典型慢查询命令，生产环境禁止使用
- 大 Key（如大 Hash、大 List）操作会导致慢查询
- 网络延迟、持久化阻塞也可能表现为慢查询

---

### 2.2 性能监控关键指标

**1. 延迟监控**

```bash
# 实时延迟采样
redis-cli --latency -h 127.0.0.1 -p 6379

# 延迟历史（需要开启延迟监控）
redis-cli LATENCY HISTORY command
redis-cli LATENCY LATEST
```

**2. 内存使用**

```bash
redis-cli INFO memory | grep -E "used_memory|mem_fragmentation_ratio"
# used_memory:85846016           → Redis 分配的内存（字节）
# used_memory_human:81.87M       → 人类可读格式
# mem_fragmentation_ratio:1.56   → 内存碎片率（>1.5 需要警惕）
```

**3. 连接数**

```bash
redis-cli INFO stats | grep total_connections_received
# total_connections_received:1000  → 累计连接数

redis-cli INFO clients
# connected_clients:10            → 当前连接数
# client_longest_output_list:0
# client_biggest_input_buf:0
```

**4. 键值数量**

```bash
redis-cli DBSIZE
# (integer) 12345  → 当前数据库键总数

redis-cli INFO keyspace
# keys=12345,expires=123,avg_ttl=987654
```

**5. QPS（每秒查询数）**

```bash
redis-cli --stat
# ------- data ------ --------------------- load -------------------- - child -
# keys       mem      clients blocked requests            connections
# 12345      81.87M   10       0       10000 (+10)         1000
#                                         ↑ 最近 1 秒 QPS
```

---

### 2.3 Redis 基准测试

**redis-benchmark 工具**：

```bash
# 基础测试（默认 50 个客户端，100000 个请求）
redis-benchmark -h 127.0.0.1 -p 6379 -c 50 -n 100000

# 测试特定命令
redis-benchmark -h 127.0.0.1 -p 6379 -t SET,GET -n 100000

# 测试特定数据大小
redis-benchmark -h 127.0.0.1 -p 6379 -d 1024  # 值大小为 1KB

# 仅测试 PING（心跳）
redis-benchmark -h 127.0.0.1 -p 6379 -t PING_INLINE -q
```

**输出示例**：

```
====== SET ======
  100000 requests completed in 1.23 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

99.99% <= 1 milliseconds
100.00% <= 2 milliseconds
81400.00 requests per second

====== GET ======
  100000 requests completed in 1.18 seconds
  50 parallel clients
  3 bytes payload
  keep alive: 1

100.00% <= 1 milliseconds
84700.00 requests per second
```

---

## 三、内存优化技巧

### 3.1 优化数据结构

**1. 使用合适的数据类型**

```
错误示例：用 String 存储对象（序列化后占用大）
正确示例：用 Hash 存储对象（field-value 对，节省内存）
```

**对比**：

```bash
# 方案 A：String 存储（JSON 序列化）
SET user:1 "{\"id\":1,\"name\":\"Alice\",\"age\":30}"
# 内存占用：约 45 字节

# 方案 B：Hash 存储
HSET user:1 id 1 name "Alice" age 30
# 内存占用：约 25 字节（节省 ~44%）
```

**2. 控制 Hash 的编码方式**

```
当 Hash 满足以下条件时，使用 ziplist 编码（节省内存）：
  hash-max-ziplist-entries 512   → field 数量 ≤ 512
  hash-max-ziplist-value 64      → 每个 value 长度 ≤ 64 字节

超过则转为 hashtable 编码
```

**配置建议**：

```bash
# redis.conf
hash-max-ziplist-entries 512
hash-max-ziplist-value 64

list-max-ziplist-size -2        # -2 表示每个 ziplist 节点 8KB
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
set-max-intset-entries 512       # 小整数集合用 intset 编码
```

---

### 3.2 键名设计优化

**1. 使用简短的键名**

```
错误：user:information:user_id:1001
正确：u:1001
```

**2. 使用 Hash Tag 减少键数量**

```
错误：1000 个键
  user:1001:name
  user:1001:age
  user:1002:name
  ...

正确：1 个 Hash
  HSET user:1001 name "Alice" age 30
```

**3. 控制键的过期时间**

```bash
# 避免大量 Key 同时过期（雪崩）
SETEX key 3600 random(0, 300)  # TTL = 3600 ~ 3900 秒
```

---

### 3.3 内存淘汰策略

当内存达到 `maxmemory` 上限时，Redis 会根据配置的策略淘汰键。

**配置**：

```bash
# redis.conf
maxmemory 2gb                         # 最大内存限制
maxmemory-policy allkeys-lru            # 内存淘汰策略
```

**淘汰策略对比**：

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| `noeviction` | 不淘汰，写操作报错 | 保证数据不丢失 |
| `allkeys-lru` | 全局 LRU 淘汰 | 最常用，通用场景 |
| `volatile-lru` | 仅设置过期时间的键中 LRU 淘汰 | 部分键有 TTL |
| `allkeys-random` | 全局随机淘汰 | 数据均匀分布 |
| `volatile-random` | 仅 TTL 键中随机淘汰 | 随机场景 |
| `volatile-ttl` | 优先淘汰 TTL 短的键 | TTL 差异大 |
| `allkeys-lfu`（Redis 4.0+） | 全局 LFU 淘汰 | 考虑访问频率 |
| `volatile-lfu`（Redis 4.0+） | 仅 TTL 键中 LFU 淘汰 | 考虑访问频率 |

**LRU vs LFU**：

- **LRU（Least Recently Used）**：淘汰最久未访问的键
- **LFU（Least Frequently Used）**：淘汰访问频率最低的键（考虑访问次数）

---

## 四、Pipeline 与批量操作

### 4.1 为什么需要 Pipeline

**问题**：每次 Redis 命令都是**往返时延（RTT）**：

```
客户端 → 发送命令 → 网络 RTT → Redis 执行 → 网络 RTT → 返回结果 → 客户端
```

如果执行 1000 次 `SET` 命令：

```
1000 次 RTT ≈ 1000 × 1ms = 1000ms = 1 秒
```

**Pipeline 原理**：将多条命令**一次性发送**给 Redis，减少 RTT。

```
客户端 → [SET k1 v1, SET k2 v2, ..., SET k1000 v1000] → Redis
       ← [OK, OK, ..., OK] ← 客户端
       
1000 次命令只需要 1 次 RTT
```

---

### 4.2 Pipeline 使用示例

**Java（Jedis）**：

```java
Jedis jedis = new Jedis("127.0.0.1", 6379);

// 不使用 Pipeline（1000 次 RTT）
for (int i = 0; i < 1000; i++) {
    jedis.set("key:" + i, "value:" + i);
}
// 耗时：~1000ms

// 使用 Pipeline（1 次 RTT）
Pipeline pipeline = jedis.pipelined();
for (int i = 0; i < 1000; i++) {
    pipeline.set("key:" + i, "value:" + i);
}
pipeline.sync();  // 一次性发送
// 耗时：~10ms（性能提升 100 倍！）
```

**Java（Lettuce）**：

```java
RedisAsyncCommands<String, String> async = client.connect().async();

// 开启 Pipeline
async.setAutoFlushCommands(false);

List<RedisFuture<?>> futures = new ArrayList<>();
for (int i = 0; i < 1000; i++) {
    futures.add(async.set("key:" + i, "value:" + i));
}

// 一次性 flush
async.flushCommands();

// 等待所有命令完成
for (RedisFuture<?> future : futures) {
    future.get();
}
```

**Python（redis-py）**：

```python
import redis

r = redis.Redis(host='127.0.0.1', port=6379)

# 使用 Pipeline
pipe = r.pipeline()
for i in range(1000):
    pipe.set(f'key:{i}', f'value:{i}')
pipe.execute()  # 一次性发送
```

---

### 4.3 Pipeline 注意事项

**1. Pipeline 不是事务**

```
Pipeline：批量发送命令，不保证原子性（命令可能穿插其他客户端的命令）
事务（MULTI/EXEC）：保证原子性（所有命令一起执行）
```

**2. Pipeline 不宜过大**

```
建议：每次 Pipeline 不超过 1000 条命令
原因：一次发送过多命令会阻塞 Redis（Redis 是单线程）
```

**3. Pipeline 与事务可以结合**

```java
Pipeline pipeline = jedis.pipelined();
pipeline.multi();   // 开启事务
pipeline.set("k1", "v1");
pipeline.set("k2", "v2");
pipeline.exec();     // 提交事务
pipeline.sync();
```

---

## 五、Lua 脚本保证原子性

### 5.1 为什么需要 Lua 脚本

**问题**：多个 Redis 命令需要原子性执行，但 Redis 的单条命令是原子的，多条命令组合起来不是原子的。

**场景举例**：实现限流

```java
// 错误示例：非原子操作
Long count = redis.incr("rate:" + userId);
if (count == 1) {
    redis.expire("rate:" + userId, 60);  // 如果这里宕机，Key 永不过期！
}
if (count > 100) {
    throw new RuntimeException("限流");
}
```

**Lua 脚本解决方案**：

```lua
-- 限流 Lua 脚本（原子操作）
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, ttl)
end

if count > limit then
    return 0  -- 被限流
else
    return 1  -- 允许
end
```

---

### 5.2 Lua 脚本基础

**执行 Lua 脚本**：

```bash
# 方法一：直接执行脚本内容
redis-cli EVAL "return redis.call('SET', KEYS[1], ARGV[1])" 1 mykey myvalue
#             ↑ Lua 脚本               ↑ KEYS 数量 ↑ KEYS   ↑ ARGV

# 方法二：执行脚本文件
redis-cli EVALSHA <sha1> 1 mykey myvalue

# 加载脚本并获取 sha1
redis-cli SCRIPT LOAD "return redis.call('GET', KEYS[1])"
# → "4e29d5d5efa51f7e38a8a7c6b6f0cdb9d36f8f"

# 通过 sha1 执行（避免重复传输脚本）
redis-cli EVALSHA 4e29d5d5efa51f7e38a8a7c6b6f0cdb9d36f8f 1 mykey
```

**Lua 脚本语法要点**：

```lua
-- 1. 调用 Redis 命令
redis.call('SET', 'key', 'value')   -- 出错抛异常
redis.pcall('SET', 'key', 'value')  -- 出错返回错误，不抛异常

-- 2. 返回值
return 1           -- 返回整数
return 'hello'    -- 返回字符串
return {1, 2, 3} -- 返回数组

-- 3. 获取 KEYS 和 ARGV
local key = KEYS[1]
local value = ARGV[1]

-- 4. 逻辑判断
if (redis.call('GET', KEYS[1]) == ARGV[1]) then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
```

---

### 5.3 Lua 脚本实战：分布式锁

**分布式锁的要求**：
1. 互斥性：同一时刻只有一个客户端持有锁
2. 防死锁：持有锁的客户端宕机，锁自动释放
3. 解铃还须系铃人：只能由加锁的客户端解锁

**Redis 分布式锁（Lua 脚本版）**：

```lua
-- 加锁脚本（SET key value NX PX timeout 的 Lua 实现）
-- KEYS[1] = 锁名
-- ARGV[1] = 锁值（UUID）
-- ARGV[2] = 过期时间（毫秒）
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then
    return 1
else
    return 0
end

-- 解锁脚本（先比较 value，再删除）
-- KEYS[1] = 锁名
-- ARGV[1] = 锁值（UUID）
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
```

**Java 实现**：

```java
public class RedisDistributedLock {
    private static final String LOCK_SCRIPT =
        "if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then " +
        "    return 1 " +
        "else " +
        "    return 0 " +
        "end";
    
    private static final String UNLOCK_SCRIPT =
        "if redis.call('GET', KEYS[1]) == ARGV[1] then " +
        "    return redis.call('DEL', KEYS[1]) " +
        "else " +
        "    return 0 " +
        "end";
    
    private Jedis jedis;
    private String lockName;
    private String lockValue;  // UUID
    
    public boolean lock(long timeoutMs) {
        lockValue = UUID.randomUUID().toString();
        Object result = jedis.eval(
            LOCK_SCRIPT,
            Collections.singletonList(lockName),
            Arrays.asList(lockValue, String.valueOf(timeoutMs))
        );
        return "1".equals(result.toString());
    }
    
    public boolean unlock() {
        Object result = jedis.eval(
            UNLOCK_SCRIPT,
            Collections.singletonList(lockName),
            Collections.singletonList(lockValue)
        );
        return "1".equals(result.toString());
    }
}
```

---

### 5.4 Redlock 算法

**问题**：单节点 Redis 加锁，节点故障会导致锁丢失。

**Redlock 算法**（Redis 官方分布式锁算法）：

```
1. 获取当前时间戳（毫秒）
2. 依次向 N 个独立的 Redis 节点发送加锁请求（SET key value NX PX timeout）
   - 使用相同的 key 和 value
   - 设置超时时间（防止单个节点阻塞）
3. 计算加锁耗时 = 当前时间 - 步骤 1 的时间戳
   - 如果耗时超过锁的 TTL，视为加锁失败
4. 如果成功在 >= N/2 + 1 个节点上加锁，且总耗时 < TTL，则加锁成功
5. 如果加锁失败，向所有节点发送解锁请求（Lua 脚本）
```

**Redlock 缺点**（争议）：

- Martin Kleppmann 指出：Redlock 依赖系统时钟，时钟漂移会导致锁失效
- 推荐方案：使用 ZooKeeper 或 etcd 实现分布式锁（CP 系统）

---

## 六、Redis 最佳实践总结

### 6.1 键设计

✅ **推荐**：
```
1. 键名简短且有意义：u:1001 而非 user:information:user_id:1001
2. 使用 : 分隔层级：user:1001:name
3. 控制键名长度：不超过 44 字节（Redis 对小键有特殊优化）
```

❌ **避免**：
```
1. 特殊字符：空格、换行、转义字符
2. 过长的键名：降低内存效率
3. 大 Key：单个 Key 超过 10KB（用 Hash 分片）
```

---

### 6.2 值设计

✅ **推荐**：
```
1. 选择合适的数据结构：对象用 Hash，列表用 List，集合用 Set
2. 控制值大小：单个值不超过 1MB
3. 为大 Key 设置较短 TTL：防止长时间占用内存
```

❌ **避免**：
```
1. 用 String 存储大对象（JSON 序列化后很大）
2. 大 Hash（field 数 > 1000）→ 用 Hash Tag 分片
3. 大 List（元素数 > 10000）→ 分批查询（LRANGE）
```

---

### 6.3 命令使用

✅ **推荐**：
```
1. 使用 Pipeline 批量操作
2. 使用 Lua 脚本保证原子性
3. 为键设置 TTL（防止内存泄漏）
4. 使用 SCAN 代替 KEYS（避免阻塞）
5. 使用 SSCAN/HSCAN/ZSCAN 遍历集合
```

❌ **避免**：
```
1. KEYS *（生产环境禁止使用）
2. FLUSHALL / FLUSHDB（清空数据，危险！）
3. 大 Key 的 HGETALL / LRANGE 0 -1（分批查询）
4. 长时间执行的 Lua 脚本（会阻塞 Redis）
```

---

### 6.4 内存优化

```
1. 设置 maxmemory + 淘汰策略（allkeys-lru）
2. 控制 Hash/List/Set/ZSet 的编码方式（ziplist、intset）
3. 关闭持久化（如果允许数据丢失）或改用 AOF always
4. 使用 32 位 Redis（内存 < 3GB 时）
5. 启用内存碎片整理：activedefrag yes
```

---

### 6.5 高可用

```
1. 主从复制 + 哨兵（小数据量）
2. Redis Cluster（大数据量）
3. 多机房部署（跨机房同步）
4. 定期备份 RDB 文件
5. 监控内存、QPS、慢查询
```

---

## 七、面试高频问题

### Q1: Pipeline 和事务的区别？

**答案要点**：
- Pipeline：批量发送命令，不保证原子性，性能高
- 事务（MULTI/EXEC）：保证原子性，但一次发送所有命令，可能阻塞 Redis

### Q2: Lua 脚本的用途？

**答案要点**：
- 保证多条命令的原子性
- 实现复杂逻辑（如限流、分布式锁）
- 减少网络 RTT（多条命令一次发送）

### Q3: Redis 分布式锁的实现？

**答案要点**：
- 加锁：SET key value NX PX timeout
- 解锁：Lua 脚本（先比较 value，再删除）
- 问题：单节点故障 → Redlock（但 Redlock 有争议）

### Q4: 如何避免大 Key 问题？

**答案要点**：
- 用 Hash 分片（将大 Key 拆成多个小 Key）
- 用 SCAN 分批查询
- 控制数据结构大小（Hash field 数、List 元素数）

### Q5: Redis 性能优化技巧？

**答案要点**：
1. 使用 Pipeline 批量操作
2. 优化数据结构（用 Hash 代替 String）
3. 控制键名和值大小
4. 设置合理的淘汰策略
5. 使用 Lua 脚本减少 RTT

---

## 八、总结

本文作为 Redis 5 篇系列的收官之作，系统总结了 Redis 性能优化与实战技巧：

1. **慢查询分析**：通过 `SLOWLOG` 定位性能瓶颈
2. **内存优化**：合适的数据结构 + 键名设计 + 淘汰策略
3. **Pipeline**：批量操作，减少 RTT，性能提升 100 倍
4. **Lua 脚本**：保证原子性，实现分布式锁、限流等复杂逻辑
5. **最佳实践**：键设计、值设计、命令使用、内存优化、高可用

**Redis 5 篇系列回顾**：
1. ✅ Redis 数据结构深度解析
2. ✅ Redis 持久化与内存管理深度解析
3. ✅ Redis 主从复制与高可用深度解析
4. ✅ Redis 缓存问题深度解析（穿透/击穿/雪崩）
5. ✅ Redis 性能优化与实战（本文）

**关键数字记忆**：
- 慢查询阈值：10000 微秒（10 毫秒）
- Pipeline 批次：不超过 1000 条命令
- 大 Key 阈值：单个 Key > 10KB
- 内存碎片率：> 1.5 需要警惕
- 分布式锁超时时间：获取锁的超时 + 业务执行时间

至此，Java 面试八股文 30 篇系列全部完成！🎉

---

*作者：李亚飞 · Raphael Lab*
