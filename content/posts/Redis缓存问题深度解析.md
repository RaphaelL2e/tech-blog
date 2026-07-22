---
title: Redis 缓存问题深度解析
date: 2026-05-13 18:45:00+08:00
updated: '2026-05-13T18:45:00+08:00'
description: 前面三篇我们分别探讨了 Redis 的数据结构、持久化内存管理、主从复制与高可用架构。在生产环境中使用 Redis 作为缓存时，还会遇到经典的缓存穿透、缓存击穿、缓存雪崩三大问题。这些问题是面试高频考点，也是实际工作中必须掌握的技术方案。
  在讨论缓存问题之前，先明确缓存处理请求的标准流程。 Cach。
topic: database-middleware
level: intermediate
status: maintained
tags:
- Redis
- 缓存穿透
- 缓存击穿
- 缓存雪崩
- 布隆过滤器
categories:
- 数据库与中间件
draft: false
---

## 一、引言

前面三篇我们分别探讨了 Redis 的数据结构、持久化内存管理、主从复制与高可用架构。在生产环境中使用 Redis 作为缓存时，还会遇到经典的**缓存穿透、缓存击穿、缓存雪崩**三大问题。这些问题是面试高频考点，也是实际工作中必须掌握的技术方案。

**本文要点**：
1. 缓存处理请求的完整流程
2. 缓存穿透的原理与解决方案
3. 缓存击穿的原理与解决方案
4. 缓存雪崩的原理与解决方案
5. 缓存预热、更新策略与最佳实践

---

## 二、缓存的基本工作流程

在讨论缓存问题之前，先明确缓存处理请求的标准流程。

### 2.1 缓存读取流程

```
客户端请求数据
       ↓
 缓存中是否存在？
    ↓           ↓
   是           否
    ↓           ↓
 直接返回   查询数据库
    ↓           ↓
   结束    数据库存在？
                ↓        ↓
               是        否
                ↓        ↓
          写入缓存   返回空/报错
                ↓        ↓
           返回数据    结束
```

**代码实现（Java）**：

```java
public User getUserById(Long userId) {
    String key = "user:" + userId;
    
    // 1. 先查缓存
    String value = redis.get(key);
    if (value != null) {
        return JSON.parseObject(value, User.class);
    }
    
    // 2. 缓存未命中，查数据库
    User user = userMapper.selectById(userId);
    if (user != null) {
        // 3. 写入缓存
        redis.setex(key, 3600, JSON.toJSONString(user));
    }
    
    return user;
}
```

### 2.2 缓存更新策略

**常见更新策略对比**：

| 策略 | 描述 | 优缺点 |
|------|------|--------|
| **Cache Aside（旁路缓存）** | 读：先缓存后 DB；写：先更新 DB，再删除缓存 | 最常用，一致性较好 |
| **Read/Write Through** | 缓存层负责同步更新 DB | 缓存层复杂，不常用 |
| **Write Behind** | 异步写 DB，先更新缓存 | 性能高，但可能丢数据 |

**Cache Aside 模式（推荐）**：

```
读操作：
1. 先读缓存，命中直接返回
2. 未命中，读 DB
3. 将 DB 结果写入缓存

写操作：
1. 先更新数据库
2. 再删除缓存（不是更新缓存！）
```

**为什么是删除缓存而不是更新缓存？**

假设两个并发操作：写操作 A、写操作 B

```
时间线：
T1: A 更新 DB → name = "Alice"
T2: B 更新 DB → name = "Bob"
T3: B 更新缓存 → cache = "Bob"
T4: A 更新缓存 → cache = "Alice"  ← 脏数据！
```

如果采用**删除缓存**，则 T4 时 A 删除缓存，下次读请求会从 DB 加载最新值。

---

## 三、缓存穿透（Cache Penetration）

### 3.1 什么是缓存穿透

**定义**：查询一个**数据库也不存在**的数据，缓存和数据库都查不到。每次请求都会打到数据库，缓存完全失效。

**场景举例**：

```
恶意攻击者不断请求 id = -1 或 id = 非常大（如 999999999）的数据
→ 缓存没有（因为 DB 也没有）
→ 每次都查数据库
→ 数据库压力激增，甚至宕机
```

**正常请求**：
```
请求 id=1 → 缓存未命中 → 查 DB → 写入缓存 ✅
```

**穿透请求**：
```
请求 id=-1 → 缓存未命中 → 查 DB（null）→ 不写缓存 ❌
下次再请求 id=-1 → 重复上述流程 ❌
```

---

### 3.2 解决方案一：缓存空值

**思路**：即使 DB 查询结果为空，也缓存一个空值（或特殊标记），并设置较短的过期时间。

**代码实现**：

```java
public User getUserById(Long userId) {
    String key = "user:" + userId;
    
    // 1. 查缓存
    String value = redis.get(key);
    if (value != null) {
        if (value.equals("")) {  // 空值标记
            return null;
        }
        return JSON.parseObject(value, User.class);
    }
    
    // 2. 查数据库
    User user = userMapper.selectById(userId);
    
    if (user != null) {
        // 3. 正常数据，写入缓存
        redis.setex(key, 3600, JSON.toJSONString(user));
    } else {
        // 4. 空值，缓存短过期时间（防止穿透）
        redis.setex(key, 60, "");  // 空值标记，60 秒过期
    }
    
    return user;
}
```

**优点**：
- 实现简单
- 有效拦截重复穿透请求

**缺点**：
- 如果恶意攻击使用大量不同 id，仍然会打穿（内存浪费）
- 短暂的 DB 不一致（空值过期前，DB 中插入了该 id 的数据）

---

### 3.3 解决方案二：布隆过滤器（Bloom Filter）

**思路**：在访问缓存之前，先用布隆过滤器判断数据是否存在。如果布隆过滤器说不存在，直接返回，不打到数据库。

**布隆过滤器原理**：

```
布隆过滤器 = 一个二进制数组 + 多个哈希函数

插入过程：
1. 对 key 进行 k 次哈希，得到 k 个位置
2. 将这 k 个位置的值设为 1

查询过程：
1. 对 key 进行 k 次哈希，得到 k 个位置
2. 如果这 k 个位置全部为 1 → 可能存在（有误判率）
3. 如果有一个位置为 0 → 一定不存在
```

**特性**：
- **不存在时：100% 准确**
- **存在时：可能误判**（实际上不存在，但布隆过滤器说存在）

**代码实现（使用 Redis 的布隆过滤器模块）**：

```bash
# 安装 RedisBloom 模块
docker run -d -p 6379:6379 redislabs/redisbloom

# 使用布隆过滤器
BF.RESERVE user_ids 0.01 1000000
# ↑ 错误率 1%，预计存入 100 万个元素

BF.ADD user_ids 1
BF.ADD user_ids 2
BF.EXISTS user_ids 1   # → 1（存在）
BF.EXISTS user_ids 999 # → 0（不存在）
```

**Java 实现**：

```java
public User getUserById(Long userId) {
    String key = "user:" + userId;
    
    // 1. 先通过布隆过滤器判断
    Boolean mightExist = redis.execute("BF.EXISTS", "user_ids", userId);
    if (mightExist != null && !mightExist) {
        // 一定不存在，直接返回
        return null;
    }
    
    // 2. 布隆过滤器说可能存在，继续查缓存
    String value = redis.get(key);
    if (value != null) {
        return JSON.parseObject(value, User.class);
    }
    
    // 3. 查数据库
    User user = userMapper.selectById(userId);
    if (user != null) {
        redis.setex(key, 3600, JSON.toJSONString(user));
    }
    
    return user;
}
```

**优点**：
- 内存占用极小（100 万元素，1% 误判率，只需约 1.2MB）
- 可以拦截绝大多数穿透请求

**缺点**：
- 有误判率（需要合理配置）
- 布隆过滤器中的数据删除困难（RedisBloom 支持删除，但性能下降）
- 新增数据时，需要同步更新布隆过滤器

---

### 3.4 解决方案三：限流与鉴权

**思路**：在接口层增加限流、鉴权、参数校验，防止恶意攻击。

**实现**：

```java
@RateLimiter(permitsPerSecond = 10)  // 每秒最多 10 次请求
@GetMapping("/user/{id}")
public User getUser(@PathVariable Long id) {
    // 参数校验
    if (id <= 0 || id > 999999999) {
        throw new IllegalArgumentException("Invalid user id");
    }
    
    return userService.getUserById(id);
}
```

---

### 3.5 方案对比与组合

| 方案 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| 缓存空值 | 数据量小，空值有限 | 简单 | 内存浪费，可能被攻击 |
| 布隆过滤器 | 数据量大，固定集合 | 内存极小 | 有误判率，删除困难 |
| 限流鉴权 | 防恶意攻击 | 通用 | 无法完全避免内部错误 |

**推荐组合**：布隆过滤器 + 缓存空值 + 限流

---

## 四、缓存击穿（Cache Hotkey Breakdown）

### 4.1 什么是缓存击穿

**定义**：一个**热点 Key** 在缓存过期的瞬间，大量并发请求同时打过来，因为缓存已失效，所有请求都打到数据库，压垮数据库。

**与穿透的区别**：
- **穿透**：查询数据库中也不存在的数据（每次都绕过缓存）
- **击穿**：查询数据库中存在的**热点数据**，但缓存刚好过期（大量请求同时绕过缓存）

**场景举例**：

```
某热门商品的缓存过期时间 = 12:00:00
在 12:00:00 这一刻，有 10000 个请求同时到达
→ 缓存已过期
→ 10000 个请求全部打到数据库
→ 数据库瞬间压力过大
```

---

### 4.2 解决方案一：互斥锁（Mutex）

**思路**：当缓存失效时，不是所有请求都去查数据库，而是只有一个请求去查数据库，其他请求等待，查完后再重新从缓存获取。

**代码实现（Redis 分布式锁）**：

```java
public User getUserById(Long userId) {
    String key = "user:" + userId;
    
    // 1. 先查缓存
    String value = redis.get(key);
    if (value != null) {
        return JSON.parseObject(value, User.class);
    }
    
    // 2. 缓存未命中，尝试获取分布式锁
    String lockKey = "lock:" + key;
    String lockValue = UUID.randomUUID().toString();
    Boolean locked = redis.setnx(lockKey, lockValue, 10);  // 10 秒过期
    
    if (locked != null && locked) {
        // 3. 获取锁成功，查询数据库
        try {
            User user = userMapper.selectById(userId);
            if (user != null) {
                redis.setex(key, 3600, JSON.toJSONString(user));
            }
            return user;
        } finally {
            // 释放锁（需要校验 value，防止误删）
            String script = "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                           "return redis.call('del', KEYS[1]) else return 0 end";
            redis.execute(script, Collections.singletonList(lockKey), lockValue);
        }
    } else {
        // 4. 获取锁失败，等待一小段时间后重试
        try {
            Thread.sleep(50);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return getUserById(userId);  // 递归重试
    }
}
```

**优点**：
- 只有 1 个请求查询数据库，其他请求等待
- 数据库压力小

**缺点**：
- 实现复杂（分布式锁）
- 等待的请求增加响应时间
- 如果获取锁的请求失败，会导致所有等待请求都失败

---

### 4.3 解决方案二：逻辑过期（Logic Expire）

**思路**：不为缓存设置物理过期时间（TTL），而是在 value 中存储逻辑过期时间。当发现逻辑过期时，开启新线程去查询数据库并更新缓存，当前请求仍返回旧数据。

**数据结构中增加逻辑过期时间**：

```java
@Data
public class RedisData {
    private Object data;       // 实际数据
    private Long expireTime;   // 逻辑过期时间（时间戳）
}
```

**代码实现**：

```java
public User getUserById(Long userId) {
    String key = "user:" + userId;
    
    // 1. 查询缓存
    String value = redis.get(key);
    if (value == null) {
        // 2. 缓存不存在，直接查数据库（首次加载）
        User user = userMapper.selectById(userId);
        if (user != null) {
            RedisData redisData = new RedisData();
            redisData.setData(user);
            redisData.setExpireTime(System.currentTimeMillis() + 3600 * 1000);
            redis.set(key, JSON.toJSONString(redisData));  // 不设物理 TTL
        }
        return user;
    }
    
    // 3. 缓存存在，判断是否逻辑过期
    RedisData redisData = JSON.parseObject(value, RedisData.class);
    if (redisData.getExpireTime() > System.currentTimeMillis()) {
        // 未过期，直接返回
        return (User) redisData.getData();
    }
    
    // 4. 已逻辑过期，尝试获取锁
    String lockKey = "lock:" + key;
    String lockValue = UUID.randomUUID().toString();
    Boolean locked = redis.setnx(lockKey, lockValue, 10);
    
    if (locked != null && locked) {
        // 获取锁成功，开启新线程更新缓存
        new Thread(() -> {
            try {
                User user = userMapper.selectById(userId);
                RedisData newData = new RedisData();
                newData.setData(user);
                newData.setExpireTime(System.currentTimeMillis() + 3600 * 1000);
                redis.set(key, JSON.toJSONString(newData));
            } finally {
                // 释放锁
                String script = "if redis.call('get', KEYS[1]) == ARGV[1] then " +
                               "return redis.call('del', KEYS[1]) else return 0 end";
                redis.execute(script, Collections.singletonList(lockKey), lockValue);
            }
        }).start();
    }
    
    // 5. 无论是否获取锁，都返回旧数据
    return (User) redisData.getData();
}
```

**优点**：
- 用户请求永远不等待（返回旧数据）
- 数据库压力小

**缺点**：
- 实现复杂
- 返回的数据可能不是最新的（短暂不一致）

---

### 4.4 解决方案三：热点 Key 永不过期

**思路**：对于极端热点数据，设置**永不过期**，通过后台任务定期更新。

**实现**：

```java
// 写缓存时，不设 TTL
redis.set("hot:product:1", JSON.toJSONString(product));

// 后台定时任务，定期更新热点数据
@Scheduled(fixedDelay = 60000)  // 每 60 秒执行一次
public void refreshHotProducts() {
    List<Product> hotProducts = productMapper.selectHotProducts();
    for (Product product : hotProducts) {
        redis.set("hot:product:" + product.getId(), JSON.toJSONString(product));
        // 注意：这里不设置 TTL，或者设置很长的 TTL
    }
}
```

---

### 4.5 方案对比

| 方案 | 数据一致性 | 实现复杂度 | 用户体验 |
|------|-----------|------------|---------|
| 互斥锁 | 高 | 高 | 等待锁释放，响应慢 |
| 逻辑过期 | 低（短暂不一致） | 高 | 无需等待，体验好 |
| 永不过期 + 后台更新 | 低（定期更新） | 中 | 无需等待，体验好 |

**推荐选择**：
- 数据一致性要求高 → 互斥锁
- 用户体验要求高 → 逻辑过期 或 永不过期

---

## 五、缓存雪崩（Cache Avalanche）

### 5.1 什么是缓存雪崩

**定义**：**大量缓存同时过期**，或者 **Redis 服务宕机**，导致所有请求瞬间打到数据库，压垮数据库。

**与击穿的区别**：
- **击穿**：单个热点 Key 过期
- **雪崩**：大量 Key 同时过期，或 Redis 整体不可用

**场景举例**：

```
场景一：批量过期
运营在晚上 12:00 批量导入 10000 个商品数据，缓存 TTL 都设为 1 小时
→ 凌晨 1:00，10000 个缓存同时过期
→ 所有请求打到数据库

场景二：Redis 宕机
Redis 机器断电
→ 所有缓存失效
→ 所有请求打到数据库
```

---

### 5.2 解决方案一：过期时间加随机值

**思路**：在设置 TTL 时，增加一个随机值，避免大量 Key 同时过期。

**代码实现**：

```java
public void cacheUser(User user) {
    String key = "user:" + user.getId();
    int baseTTL = 3600;  // 基础 TTL = 1 小时
    int randomTTL = new Random().nextInt(300);  // 0 ~ 300 秒的随机值
    redis.setex(key, baseTTL + randomTTL, JSON.toJSONString(user));
}
```

**效果**：
```
原本：10000 个 Key 都在 1:00:00 过期
修改后：10000 个 Key 在 1:00:00 ~ 1:05:00 之间分散过期
→ 数据库压力被分散
```

---

### 5.3 解决方案二：多级缓存

**思路**：不仅仅依赖 Redis，而是使用**本地缓存 + Redis 缓存**的多级架构。

**架构**：

```
请求 → 本地缓存（Caffeine/Guava Cache）
         ↓ 未命中
       Redis 缓存
         ↓ 未命中
         数据库
```

**代码实现（Caffeine）**：

```java
// 本地缓存
Cache<Long, User> localCache = Caffeine.newBuilder()
    .maximumSize(10000)
    .expireAfterWrite(30, TimeUnit.SECONDS)
    .build();

public User getUserById(Long userId) {
    String key = "user:" + userId;
    
    // 1. 先查本地缓存
    User user = localCache.getIfPresent(userId);
    if (user != null) {
        return user;
    }
    
    // 2. 本地缓存未命中，查 Redis
    String value = redis.get(key);
    if (value != null) {
        user = JSON.parseObject(value, User.class);
        localCache.put(userId, user);  // 写入本地缓存
        return user;
    }
    
    // 3. Redis 未命中，查数据库
    user = userMapper.selectById(userId);
    if (user != null) {
        redis.setex(key, 3600, JSON.toJSONString(user));
        localCache.put(userId, user);
    }
    
    return user;
}
```

**优点**：
- Redis 宕机时，本地缓存仍可提供服务
- 减少 Redis 压力

**缺点**：
- 本地缓存和 Redis 缓存可能存在不一致
- 多节点部署时，本地缓存无法同步

---

### 5.4 解决方案三：Redis 集群高可用

**思路**：通过 Redis Sentinel 或 Redis Cluster 保证 Redis 服务的高可用，避免 Redis 整体宕机。

**架构**：

```
        Sentinel 集群
             ↓
    ┌────────┼────────┐
    ↓        ↓        ↓
 Master   Slave1   Slave2
  (写)    (读)     (读)
```

**配置示例**（已在上一篇中详述）：
- 3 个哨兵节点监控 Master
- Master 故障，哨兵自动切换 Slave 为 Master
- 客户端通过哨兵获取当前 Master 地址

---

### 5.5 解决方案四：限流与熔断

**思路**：在数据库层增加限流和熔断机制，防止数据库被打垮。

**限流（Rate Limiter）**：

```java
@RateLimiter(permitsPerSecond = 100)  // 每秒最多 100 个数据库查询
public User getUserByIdFromDB(Long userId) {
    return userMapper.selectById(userId);
}
```

**熔断（Circuit Breaker）**：

```java
@CircuitBreaker(name = "userService", fallbackMethod = "fallbackGetUser")
public User getUserById(Long userId) {
    return userMapper.selectById(userId);
}

public User fallbackGetUser(Long userId, Exception ex) {
    // 熔断时返回默认值或缓存的旧值
    return User.getDefaultUser();
}
```

---

### 5.6 解决方案五：缓存预热

**思路**：在缓存大面积失效之前，提前将热点数据加载到缓存中。

**实现**：

```java
@Scheduled(cron = "0 55 * * * ?")  // 每小时的 55 分执行
public void preloadHotData() {
    // 1. 查询热点数据（如即将开始的秒杀商品）
    List<Product> hotProducts = productMapper.selectHotProducts();
    
    // 2. 批量写入 Redis
    for (Product product : hotProducts) {
        String key = "product:" + product.getId();
        redis.setex(key, 3600 + new Random().nextInt(300), 
                    JSON.toJSONString(product));
    }
}
```

---

## 六、缓存最佳实践

### 6.1 缓存更新策略总结

| 策略 | 描述 | 一致性 | 复杂度 |
|------|------|--------|--------|
| Cache Aside（推荐） | 读：先缓存后 DB；写：先 DB 后删除缓存 | 最终一致 | 低 |
| Read/Write Through | 缓存层同步更新 DB | 强一致 | 高 |
| Write Behind | 异步写 DB | 可能丢数据 | 高 |

### 6.2 缓存过期策略

- **热点数据**：TTL 设长一些（1 小时 ~ 数小时），或永不过期 + 后台更新
- **普通数据**：TTL 适中（30 分钟 ~ 1 小时）
- **冷数据**：TTL 设短一些（5 ~ 10 分钟），或自动淘汰

### 6.3 缓存监控指标

```
1. 缓存命中率 = 命中次数 / (命中次数 + 未命中次数)
   → 低于 80% 需要优化

2. 缓存穿透次数 = 查询 DB 为 null 的次数
   → 需要增加布隆过滤器或缓存空值

3. 缓存击穿次数 = 热点 Key 过期瞬间的并发数
   → 需要增加互斥锁或逻辑过期

4. 缓存雪崩风险 = 同一时刻过期的 Key 数量
   → 需要增加随机 TTL
```

---

## 七、面试高频问题

### Q1: 缓存穿透、击穿、雪崩的区别？

**答案要点**：
- **穿透**：查询数据库中也不存在的数据，缓存完全失效
- **击穿**：热点 Key 过期瞬间，大量并发请求打到数据库
- **雪崩**：大量缓存同时过期，或 Redis 宕机，所有请求打到数据库

### Q2: 缓存穿透的解决方案？

**答案要点**：
1. 缓存空值（简单，但有内存浪费）
2. 布隆过滤器（内存极小，但有误判率）
3. 限流鉴权（防恶意攻击）

### Q3: 缓存击穿的解决方案？

**答案要点**：
1. 互斥锁（数据一致性强，但用户体验差）
2. 逻辑过期（用户体验好，但数据可能短暂不一致）
3. 热点 Key 永不过期 + 后台更新

### Q4: 缓存雪崩的解决方案？

**答案要点**：
1. TTL 加随机值（避免同时过期）
2. 多级缓存（本地缓存 + Redis）
3. Redis 高可用集群
4. 限流与熔断
5. 缓存预热

### Q5: 为什么是删除缓存而不是更新缓存？

**答案要点**：
- 防止并发写导致脏数据
- 删除缓存后，下次读请求会自动加载最新数据
- 写多读少的场景，更新缓存浪费性能

---

## 八、总结

本文深入探讨了 Redis 缓存的三大经典问题：

1. **缓存穿透**：查询不存在的数据 → 解决：布隆过滤器 + 缓存空值
2. **缓存击穿**：热点 Key 过期 → 解决：互斥锁 或 逻辑过期
3. **缓存雪崩**：大量 Key 同时过期 或 Redis 宕机 → 解决：随机 TTL + 多级缓存 + 高可用

**最佳实践记忆**：
- 写操作：先更新 DB，再删除缓存（Cache Aside）
- 防穿透：布隆过滤器 + 缓存空值
- 防击穿：互斥锁 或 逻辑过期
- 防雪崩：随机 TTL + 多级缓存 + 高可用集群

**关键数字**：
- 布隆过滤器误判率：1%（可配置）
- 缓存空值 TTL：60 秒（较短）
- 热点数据 TTL：1 小时 + 随机 300 秒
- 本地缓存 TTL：30 秒 ~ 5 分钟（比 Redis 短）

下一篇将是 **Redis 性能优化与实战**，包括慢查询分析、内存优化、Pipeline 与 Lua 脚本、分布式锁实战等，完成 Redis 5 篇系列，敬请期待。

---

*作者：李亚飞 · Raphael Lab*
