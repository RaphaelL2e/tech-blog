---
title: Redis面试八股文（四）——缓存问题解决方案、事务机制与Lua脚本实战
date: 2026-07-14 09:00:00+08:00
updated: '2026-07-14T09:00:00+08:00'
description: 聚焦 Redis 缓存穿透、击穿与雪崩治理，对比事务、Lua 脚本和 Pipeline，并讲解 GEO 等生产场景的实战方案。
topic: database-middleware
level: intermediate
status: maintained
tags:
- Redis
- 缓存穿透
- 缓存击穿
- 缓存雪崩
- Lua脚本
categories:
- 数据库与中间件
draft: false
---

> 面试高频问题：如何解决缓存穿透、击穿、雪崩三大问题？Redis事务和Lua脚本有什么区别？Pipeline和原生批量操作哪个更好用？Redis的GEO功能怎么实现附近的人？本文带你深入理解Redis缓存高级特性与实战技巧。

## 引言

前两篇我们聊了Redis的数据结构与持久化、主从复制与集群，它们是Redis的"内功"。本篇我们聊Redis的"招式"——如何在实战中用好Redis：解决缓存三大经典问题（穿透/击穿/雪崩），用事务和Lua脚本保证操作原子性，用Pipeline提升批量性能，以及GEO地理位置这一杀手级功能。面试中，这些都是高频考点，也是区分"会用Redis"和"精通Redis"的关键。

**本文要点**：
1. 缓存穿透、击穿、雪崩的原理与解决方案
2. Redis事务机制（WATCH/MULTI/EXEC）
3. Lua脚本：原子操作的终极武器
4. Pipeline与Lua脚本的对比选择
5. GEO地理位置功能实战
6. 面试高频问题精讲

---

## 一、缓存三大经典问题

### 1.1 缓存穿透：请求绕过缓存直击数据库

**Q：什么是缓存穿透？有什么危害？**

A：缓存穿透是指查询一个**根本不存在的数据**。由于缓存中没有，每次请求都会穿透到数据库查询。如果攻击者大量构造不存在的数据请求，会导致数据库压力剧增甚至宕机。

```
正常请求：数据库有数据，缓存miss → 查DB → 回填缓存
穿透请求：数据库也没有，缓存miss → 查DB → 再次miss → 缓存无法回填 → 每次都查DB
```

**Q：如何解决缓存穿透？**

**方案一：缓存空值（简单有效）**

当数据库查不到数据时，在缓存中写入一个空值（TTL较短，如60秒）：

```java
public String getProduct(String productId) {
    String cacheKey = "product:" + productId;
    String cached = redis.get(cacheKey);
    
    if (cached != null) {
        return cached;
    }
    
    // 查询数据库
    Product product = productMapper.selectById(productId);
    
    if (product == null) {
        // 缓存空值，防止缓存穿透
        redis.setex(cacheKey, 60, "NULL");
        return null;
    }
    
    redis.setex(cacheKey, 3600, JSON.toJSONString(product));
    return JSON.toJSONString(product);
}
```

**方案二：布隆过滤器（推荐用于海量数据）**

将所有存在的数据key哈希到位数组中，请求时先判断是否可能存在：

```java
// 初始化布隆过滤器（将所有商品ID加入）
RedisBloomFilter<String> bloomFilter = new RedisBloomFilter<>();
List<String> allProductIds = productMapper.selectAllIds();
bloomFilter.addAll("product:", allProductIds);

// 查询时先过布隆过滤器
public Product getProduct(String productId) {
    if (!bloomFilter.mightContain("product:" + productId)) {
        // 布隆过滤器说肯定不存在，直接返回
        return null;
    }
    // 可能存在，继续查缓存和DB
    return getProductFromCacheOrDb(productId);
}
```

**方案对比**：

| 方案 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 缓存空值 | 数据量一般 | 实现简单 | 浪费缓存空间，短时间内无法感知数据变化 |
| 布隆过滤器 | 海量数据，亿级 | 空间效率极高 | 有误判率（假阳性），无法删除数据 |
| 组合方案 | 最佳实践 | 取长补短 | 实现稍复杂 |

> **面试加分点**：布隆过滤器可以用Redis的`BF.ADD`/`BF.EXISTS`命令实现，底层是多个哈希函数将元素映射到位数组的多个位置。误判率公式：k=ln2×(m/n)，其中m是位数，n是元素数。

---

### 1.2 缓存击穿：热点key失效的瞬间

**Q：什么是缓存击穿？和穿透有什么区别？**

A：缓存击穿是指**某个热点key突然过期**，导致大量并发请求同时击穿到数据库。区别在于：穿透是查不存在的数据，击穿是热点数据缓存失效瞬间被大量访问。

```
正常情况：热点key → 缓存命中 → 快速返回
击穿情况：热点key过期 → 大量请求同时查DB → DB压力激增
```

**Q：如何解决缓存击穿？**

**方案一：互斥锁（Mutex Lock）**

第一个请求去查DB并重建缓存，其他请求等待锁释放后从缓存取：

```java
public String getProduct(String productId) {
    String cacheKey = "product:" + productId;
    String cached = redis.get(cacheKey);
    
    if (cached != null) {
        return cached;
    }
    
    // 获取分布式锁
    String lockKey = "lock:product:" + productId;
    String lockValue = UUID.randomUUID().toString();
    
    boolean locked = redis.set(lockKey, lockValue, "NX", "EX", 10);
    
    if (locked) {
        try {
            // 双重检查
            cached = redis.get(cacheKey);
            if (cached != null) return cached;
            
            // 查询数据库并回填
            Product product = productMapper.selectById(productId);
            if (product != null) {
                redis.setex(cacheKey, 3600, JSON.toJSONString(product));
                return JSON.toJSONString(product);
            }
        } finally {
            // 释放锁（用Lua脚本保证原子性）
            redis.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                "return redis.call('del', KEYS[1]) else return 0 end",
                1, lockKey, lockValue
            );
        }
    } else {
        // 没拿到锁，短暂等待后重试
        Thread.sleep(50);
        return redis.get(cacheKey);
    }
    return null;
}
```

**方案二：逻辑过期（不设置TTL，不真正删除）**

```java
public class LogicalExpireProduct {
    // 逻辑过期时间（如7天）
    private static final int LOGICAL_EXPIRE = 7 * 24 * 3600;
    
    public Product getProduct(String productId) {
        String cacheKey = "product:" + productId;
        String cached = redis.get(cacheKey);
        
        if (cached == null) {
            return productMapper.selectById(productId);
        }
        
        LogicalExpireData data = JSON.parseObject(cached, LogicalExpireData.class);
        
        // 判断是否逻辑过期
        if (data.getExpireTime() < System.currentTimeMillis()) {
            // 已过期，开启后台线程重建缓存
            String lockKey = "lock:product:" + productId;
            boolean locked = redis.set(lockKey, "1", "NX", "EX", 10);
            
            if (locked) {
                // 后台线程重建缓存
                CompletableFuture.runAsync(() -> rebuildCache(productId));
            }
        }
        
        return data.getProduct();
    }
}
```

**方案对比**：

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 互斥锁 | 简单可靠，保证一致性 | 并发低，有等待开销 | 数据一致性要求高的场景 |
| 逻辑过期 | 性能好，无锁等待 | 数据可能短暂不一致 | 对性能要求高的热点数据 |

---

### 1.3 缓存雪崩：大量key同时失效

**Q：什么是缓存雪崩？**

A：缓存雪崩是指**大量缓存key在同一时间失效**，导致大量请求同时击穿到数据库，数据库压力瞬间过大而崩溃。和击穿不同，雪崩是"集体行为"，涉及大量key。

```
雪崩原因1：大量key设置了相同的TTL
雪崩原因2：Redis宕机/重启
雪崩原因3：依赖的外部服务不可用
```

**Q：如何防止缓存雪崩？**

**方案一：随机TTL**

不要让所有key在同一时刻失效：

```java
// 给TTL加上随机偏移量
int baseTTL = 3600; // 1小时
int randomTTL = ThreadLocalRandom.current().nextInt(300); // ±5分钟
redis.setex(cacheKey, baseTTL + randomTTL, value);
```

**方案二：多级缓存**

本地缓存（Guava/Caffeine）+ Redis缓存，层层兜底：

```
请求 → 本地缓存(L1) → Redis缓存(L2) → 数据库
     命中率: 60%      命中率: 30%    10%
```

**方案三：Redis高可用（防止Redis宕机）**

使用Redis Cluster/Sentinel，保证Redis本身的高可用性。

**方案四：服务降级与熔断**

当缓存不可用时，优雅降级到数据库直查（带有限流）：

```java
public Product getProduct(String productId) {
    try {
        // 先查缓存
        return getFromCache(productId);
    } catch (CacheException e) {
        // 缓存异常，降级到数据库（有流量限制）
        if (rateLimiter.allow()) {
            return getFromDb(productId);
        }
        throw new ServiceUnavailableException("系统繁忙");
    }
}
```

**三者对比总结**：

| 问题 | 本质 | 关键词 | 核心解决方案 |
|------|------|--------|--------------|
| 缓存穿透 | 查不存在的数据 | 布隆过滤器/空值缓存 | 拦截不存在的数据 |
| 缓存击穿 | 热点key过期 | 互斥锁/逻辑过期 | 保证只有一个请求查DB |
| 缓存雪崩 | 大量key同时失效 | 随机TTL/多级缓存 | 打散失效时间，高可用 |

---

## 二、Redis事务机制

### 2.1 事务的基本命令：WATCH/MULTI/EXEC

**Q：Redis事务和传统数据库事务有什么区别？**

A：Redis事务不支持回滚（Rollback）。如果命令执行失败，后续命令仍会继续执行。Redis事务的定位是"批量执行一批命令"，而非"原子性保证ACID"。

```
WATCH key1 key2   -- 监视key，事务开始前检测这些key是否变化
MULTI             -- 开启事务，之后的命令进入队列
SET key1 value1   -- 队列命令1
INCR counter      -- 队列命令2
GET key1          -- 队列命令3
EXEC              -- 执行所有队列命令（或解锁WATCH）
```

**WATCH的实现原理**：WATCH通过乐观锁实现。它监视一个或多个key，在EXEC时检查这些key自WATCH以来是否被修改过。如果被修改过，事务执行失败（返回null），应用层需要重试。

```python
# Python伪代码演示WATCH机制
while True:
    redis.watch(key)  # 监视key
    old_value = redis.get(key)
    pipe = redis.pipeline()
    pipe.multi()
    pipe.set(key, old_value + 1)
    try:
        pipe.execute()  # 如果key被修改，EXEC会失败
        break
    except WatchError:
        continue  # 重试
```

### 2.2 Redis事务的三个阶段

```
┌──────────┐    ┌────────────┐    ┌────────┐    ┌──────────┐
│  WATCH   │───▶│   MULTI    │───▶│ QUEUE  │───▶│   EXEC   │
│  监视    │    │ 开启事务  │    │ 命令入队│    │ 执行全部 │
└──────────┘    └────────────┘    └────────┘    └──────────┘
    乐观锁        标记事务开始      命令暂存       原子执行
```

### 2.3 事务应用场景：库存扣减

```java
// 错误的做法（并发不安全）
public boolean deductStock(String productId) {
    Stock stock = redis.get("stock:" + productId);
    if (stock.getCount() <= 0) {
        return false;
    }
    // 两个请求可能同时读到count=1，都通过检查
    redis.decr("stock:" + productId);
    return true;
}

// 正确的做法（Lua脚本保证原子性，见下一节）
```

---

## 三、Lua脚本：原子操作的终极武器

### 3.1 为什么需要Lua脚本？

**Redis事务的局限性**：

1. **不支持条件判断**：无法在事务内根据前一个命令结果决定后续行为
2. **无回滚机制**：中间某条命令失败，后续命令仍执行
3. **不保证隔离性**：EXEC执行期间其他命令可以插入

**Lua脚本完美解决了这些问题**：

1. **原子性**：Redis执行Lua脚本时，不会在执行中途切换到其他命令
2. **可编程性**：支持变量、条件判断、循环
3. **一次网络往返**：多个Redis命令打包成一个Lua脚本，一次RTT完成

### 3.2 Lua脚本基础语法

Redis中运行的Lua脚本必须返回Redis数据类型（number/string/table等）：

```lua
-- 示例1：简单的SET IF NOT EXIST
local key = KEYS[1]
local value = ARGV[1]
local ttl = ARGV[2]

if redis.call('EXISTS', key) == 0 then
    redis.call('SET', key, value, 'EX', ttl)
    return 1  -- 设置成功
else
    return 0  -- 已存在
end
```

```lua
-- 示例2：库存扣减（完整版）
local stock_key = KEYS[1]
local stock = tonumber(redis.call('GET', stock_key) or 0)

if stock <= 0 then
    return -1  -- 库存不足
end

redis.call('DECR', stock_key)
return stock - 1  -- 返回扣减后的库存
```

### 3.3 实战场景一：库存扣减

```java
// 库存扣减Lua脚本
public class StockLuaScript {
    private static final String DEDUCT_STOCK_LUA = 
        "local stock = tonumber(redis.call('GET', KEYS[1]) or 0)\n" +
        "if stock <= 0 then\n" +
        "    return -1\n" +
        "elseif stock < tonumber(ARGV[1]) then\n" +
        "    return -2\n" +
        "else\n" +
        "    redis.call('DECRBY', KEYS[1], ARGV[1])\n" +
        "    return stock - tonumber(ARGV[1])\n" +
        "end";
    
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    public int deductStock(String productId, int count) {
        String key = "stock:" + productId;
        String[] keys = {key};
        String[] args = {String.valueOf(count)};
        
        Object result = redisTemplate.execute(
            new DefaultRedisScript<>(DEDUCT_STOCK_LUA, Long.class),
            Arrays.asList(key), String.valueOf(count)
        );
        
        return result != null ? ((Long) result).intValue() : -1;
    }
}
```

### 3.4 实战场景二：分布式限流

```lua
-- 滑动窗口限流Lua脚本
-- KEYS[1] = 限流key, ARGV[1] = 窗口大小(秒), ARGV[2] = 最大请求数
local key = KEYS[1]
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])

local now = redis.call('TIME')
local current_time = now[1] + now[2] / 1000000

-- 删除窗口外的记录
redis.call('ZREMRANGEBYSCORE', key, 0, current_time - window)

-- 统计当前窗口请求数
local request_count = redis.call('ZCARD', key)

if request_count < limit then
    redis.call('ZADD', key, current_time, current_time .. '-' .. math.random())
    redis.call('EXPIRE', key, window)
    return 1  -- 允许通过
else
    return 0  -- 限流拒绝
end
```

### 3.5 实战场景三：抢红包

```lua
-- 模拟红包金额随机分配
-- KEYS[1] = 红包剩余金额key, KEYS[2] = 红包剩余数量key
-- ARGV[1] = 最小红包金额, ARGV[2] = 活动ID
local remain_money = tonumber(redis.call('GET', KEYS[1]) or 0)
local remain_count = tonumber(redis.call('GET', KEYS[2]) or 0)

if remain_count <= 0 or remain_money <= 0 then
    return -1
end

-- 最后一个红包，拿走所有剩余
if remain_count == 1 then
    redis.call('DECRBY', KEYS[1], remain_money)
    redis.call('DECR', KEYS[2])
    return remain_money
end

-- 随机金额：最小为0.01，最大为剩余平均值的2倍
local avg = remain_money / remain_count
local money = math.random(math.ceil(avg * 0.01), math.floor(avg * 2))
money = math.max(1, math.min(money, remain_money - remain_count + 1))

redis.call('DECRBY', KEYS[1], money)
redis.call('DECR', KEYS[2])
return money
```

---

## 四、Pipeline与Lua脚本的对比

**Q：Pipeline和Lua脚本都能批量执行命令，什么时候用哪个？**

A：两者有本质区别：

| 特性 | Pipeline | Lua脚本 |
|------|----------|--------|
| 原子性 | 不保证，各命令独立执行 | 原子执行，不会被其他命令插入 |
| 逻辑性 | 不支持条件判断 | 支持完整Lua语法 |
| 网络 | 多次命令一次RTT（不原子） | 多次命令一次RTT（原子） |
| 用途 | 批量读取/写入，逻辑简单 | 需要原子性判断和复杂逻辑 |

**Pipeline使用场景**：

```java
// 场景：批量获取100个用户的头像URL
// 不用Pipeline：100次网络往返（网络耗时100ms+）
// 用Pipeline：1次网络往返（网络耗时1ms）
List<Object> results = redisTemplate.executePipelined(new SessionCallback<Object>() {
    @Override
    public Object execute(RedisOperations operations) throws DataAccessException {
        for (String userId : userIds) {
            operations.opsForValue().get("avatar:" + userId);
        }
        return null;
    }
});
```

**选择建议**：

- **简单的批量读写** → Pipeline
- **需要原子性+条件判断** → Lua脚本
- **跨多个key的复杂业务逻辑** → Lua脚本

---

## 五、GEO地理位置功能

### 5.1 GEO命令全家桶

Redis从3.2开始支持GEO功能，基于**GeoHash算法**将经纬度编码为有序字符串，实现附近位置检索。

```bash
# 添加地理位置（经度、纬度、成员）
GEOADD restaurants:beijing 116.397128 39.916527 "全聚德-王府井"
GEOADD restaurants:beijing 116.481033 39.948652 "全聚德-五道口"
GEOADD restaurants:beijing 116.234567 39.123456 "某餐厅"

# 查询两个位置的距离
GEODIST restaurants:beijing "全聚德-王府井" "全聚德-五道口" km
# -> "9.7662" (km)

# 查询某经纬度的附近餐厅（20km内，最近3个）
GEORADIUS restaurants:beijing 116.397128 39.916527 20 km COUNT 3 ASC
# -> 返回距离和位置信息

# 查询某成员附近（无需知道经纬度）
GEORADIUSBYMEMBER restaurants:beijing "全聚德-王府井" 5 km
```

### 5.2 实战：附近的人功能

```java
public class NearbyService {
    @Autowired
    private RedisTemplate<String, String> redisTemplate;
    
    /**
     * 上报用户位置
     */
    public void updateLocation(String userId, double longitude, double latitude) {
        redisTemplate.opsForGeo().add(
            "geo:users",  // key
            new Point(longitude, latitude),  // 经度、纬度
            userId
        );
    }
    
    /**
     * 查询附近的人
     * @param userId 当前用户ID
     * @param radiusKm 搜索半径（公里）
     * @param limit 返回数量上限
     */
    public List<NearbyUser> findNearbyUsers(String userId, double radiusKm, int limit) {
        // 获取用户当前位置
        List<Point> positions = redisTemplate.opsForGeo().position("geo:users", userId);
        if (positions == null || positions.isEmpty() || positions.get(0) == null) {
            return Collections.emptyList();
        }
        
        Point myLocation = positions.get(0);
        
        // 搜索附近用户
        Distance distance = new Distance(radiusKm, Metrics.KILOMETERS);
        Circle within = new Circle(myLocation, distance);
        GeoResults<RedisGeoCommands.GeoLocation<String>> results = 
            redisTemplate.opsForGeo().radius("geo:users", within,
                RedisGeoCommands.GeoRadiusCommandArgs.newGeoRadiusArgs()
                    .includeDistance()
                    .includeCoordinates()
                    .sortAscending()
                    .limit(limit)
            );
        
        return results.getContent().stream()
            .filter(r -> !r.getContent().getName().equals(userId)) // 排除自己
            .map(r -> new NearbyUser(
                r.getContent().getName(),
                r.getDistance().getValue(),
                r.getContent().getPoint().getX(),
                r.getContent().getPoint().getY()
            ))
            .collect(Collectors.toList());
    }
}
```

### 5.3 GEO原理：GeoHash算法

GeoHash的核心思想是：将二维的经纬度坐标，通过二分法投影到一维的字符串上。相近的坐标对应相近的字符串前缀。

```
地球纬度范围: [-90, 90]
经度范围: [-180, 180]

编码过程（以纬度为例）：
1. 判断在左侧还是右侧 → 0或1
2. 继续二分 → 持续5次得到5位二进制
3. 经纬度交叉编码 → 最终得到一串二进制
4. 每5位转换为一个Base32字符 → 得到GeoHash字符串

示例：北京(39.9, 116.4)的GeoHash：wx4g0e
"wx4g0e"的前缀"wx4g"覆盖的区域就是一个网格区域
同一网格内的所有点，GeoHash前缀相同 → 相近！
```

---

## 六、面试高频问题

**Q1：缓存穿透、击穿、雪崩的区别和解决方案？**

A：穿透是查不存在的数据，用布隆过滤器拦截；击穿是热点key过期，用互斥锁或逻辑过期；雪崩是大量key同时失效，用随机TTL+多级缓存+HLA保证高可用。

**Q2：Redis事务和Lua脚本怎么选？**

A：Pipeline适合批量读写且无需原子性的场景；Lua脚本适合需要原子性+条件判断的复杂业务（如扣库存、限流）。

**Q3：Redis GEO的底层原理是什么？**

A：基于GeoHash算法，将经纬度编码为有序字符串。相近位置有相同前缀，通过ZSET的有序集合实现范围查询。

**Q4：布隆过滤器为什么不能删除数据？**

A：布隆过滤器每个key通过多个哈希函数映射到位数组的多个位置。删除时如果该位还被其他key使用，会导致其他key被误判为不存在。解决方案：Counting BloomFilter（计数布隆过滤器）或布谷鸟过滤器（支持删除）。

**Q5：Redis分布式锁和Zookeeper分布式锁各有什么优劣？**

A：Redis分布式锁实现简单，性能高，但依赖TTL，有超时风险（Redisson的watchdog机制可缓解）。Zookeeper分布式锁基于临时有序节点，不依赖超时，安全性更高，但性能比Redis低。在JAVA生态中，Redisson已经封装得很完善，实际生产用Redis锁更多。

---

## 七、总结

本文梳理了Redis缓存高级特性的四大核心领域：

1. **缓存三大问题**：穿透（布隆过滤/空值）、击穿（互斥锁/逻辑过期）、雪崩（随机TTL/多级缓存）
2. **Redis事务**：WATCH乐观锁+MULTI/EXEC批量执行，适合简单场景
3. **Lua脚本**：Redis原子操作的终极武器，适合复杂业务逻辑（扣库存、限流、抢红包）
4. **GEO地理位置**：GeoHash+有序集合，实现附近的人、附近餐厅等LBS功能

下期预告：Redis面试八股文（五）——Stream消息流、HyperLogLog、Bitmap与Redis性能监控实战

---

*本文涉及的前置知识：Redis核心数据结构（详见《Redis面试八股文（一）》）、Redis持久化与淘汰策略（详见《Redis面试八股文（二）》）。*
