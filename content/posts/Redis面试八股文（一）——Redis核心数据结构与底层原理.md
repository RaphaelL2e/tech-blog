---
title: Redis面试八股文（一）——Redis核心数据结构与底层原理
date: 2026-06-20 10:00:00+08:00
updated: '2026-06-20T10:00:00+08:00'
description: '🎯 本文目标：从面试高频问题出发，深入剖析Redis五种核心数据结构的底层实现原理——SDS、链表、字典、跳表、压缩列表，理解Redis为什么快，以及如何选型。 注意：Redis 6.0引入了多线程IO（仅用于网络读写，命令执行仍是单线程）。Redis
  7.0进一步优化了多线程IO。 Q: SDS相。'
topic: database-middleware
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Redis
- 数据结构
- SDS
categories:
- 数据库与中间件
draft: false
---

> 🎯 **本文目标**：从面试高频问题出发，深入剖析Redis五种核心数据结构的底层实现原理——SDS、链表、字典、跳表、压缩列表，理解Redis为什么快，以及如何选型。

---

## 一、Redis为什么这么快？

### 1.1 快的关键因素

| 因素 | 说明 | 具体表现 |
|------|------|----------|
| 内存操作 | 所有数据存储在内存 | 读写速度达10万+ QPS |
| 单线程模型 | 避免上下文切换和锁竞争 | Redis 6.0前核心网络IO单线程 |
| IO多路复用 | epoll/kqueue管理并发连接 | 单线程处理数万并发连接 |
| 高效数据结构 | 为特定场景定制的数据结构 | SDS、压缩列表、跳表 |
| RESP协议 | 简单高效的通信协议 | 解析快，实现简单 |

### 1.2 单线程为什么还这么快？

```
Q: Redis单线程如何支撑高并发？

A: 三板斧：
  1. 纯内存操作 ── 没有磁盘IO的瓶颈
  2. IO多路复用 ── 单线程监听多个socket
  3. 高效数据结构 ── O(1)复杂度的命令占大多数

性能瓶颈不在CPU，在内存和网络带宽。

┌────────────────────────────────────────┐
│         Redis单线程架构                  │
│                                        │
│  ┌──────────────────────────┐          │
│  │  事件循环 (Event Loop)     │          │
│  │                          │          │
│  │   ┌──────┐   ┌────────┐  │          │
│  │   │ epoll │──►│ 命令   │  │          │
│  │   │ 监听  │   │ 处理器  │  │          │
│  │   └──────┘   └────────┘  │          │
│  │        ▲           │      │          │
│  │        │           ▼      │          │
│  │        │     ┌────────┐  │          │
│  │        └─────│ 响应   │  │          │
│  │              │ 发送   │  │          │
│  │              └────────┘  │          │
│  └──────────────────────────┘          │
│                                        │
│  客户端1 ──┬── 客户端2 ──┬── 客户端N    │
│            └── epoll监听多个连接 ──┘     │
└────────────────────────────────────────┘
```

> **注意**：Redis 6.0引入了多线程IO（仅用于网络读写，命令执行仍是单线程）。Redis 7.0进一步优化了多线程IO。

---

## 二、SDS：Redis的字符串

### 2.1 为什么不用C字符串？

```c
// C字符串的问题
char *str = "hello";
// 1. 获取长度需要O(n)遍历
// 2. 字符串拼接容易缓冲区溢出
// 3. 二进制不安全（\0截断）
// 4. 频繁修改导致内存重分配
```

### 2.2 SDS结构

```c
// Redis 3.2前
struct sdshdr {
    int len;    // 已使用长度
    int free;   // 未使用长度
    char buf[]; // 字节数组
};

// Redis 3.2+ 根据长度使用不同header
struct __attribute__ ((__packed__)) sdshdr8 {
    uint8_t len;   // 已使用
    uint8_t alloc; // 总容量（不含header和结束符）
    unsigned char flags; // 低3位标识类型
    char buf[];
};

// 长度范围对应类型：
// sdshdr5  → 0~31    (已废弃)
// sdshdr8  → 0~255
// sdshdr16 → 256~65535
// sdshdr32 → 65536~4G-1
// sdshdr64 → 4G+
```

### 2.3 SDS的优势

**Q: SDS相比C字符串有哪些优势？**

| 优势 | C字符串 | SDS | 复杂度 |
|------|---------|-----|--------|
| 获取长度 | O(n) 遍历 | O(1) 读取len字段 | O(1) |
| 缓冲区安全 | 手动检查，易溢出 | 自动检查并扩容 | 安全 |
| 内存重分配 | 每次都重分配 | 预分配+惰性释放 | 减少次数 |
| 二进制安全 | \0截断 | len明确长度 | 可存任意二进制 |

```c
// 空间预分配策略
// 1. 修改后len < 1MB → 分配free = len（2倍）
// 2. 修改后len >= 1MB → 分配free = 1MB

// 惰性空间释放
// 缩短字符串时，不立即回收空间，用free记录
// 真正释放用sdsclear()或sdsRemoveFreeSpace()
```

### 2.4 面试考点

```
Q: Redis的String最大能存多少？
A: 512MB

Q: SDS如何保证二进制安全？
A: 用len字段标记长度，不以\0作为结束判断

Q: Redis用SDS做了哪些优化？
A: 
  - 多种header格式节省内存（小字符串用sdshdr8）
  - 空间预分配减少内存重分配次数
  - 惰性空间释放避免频繁内存回收
  - 兼容C函数（buf末尾自动加\0）
```

---

## 三、链表：List的底层之一

### 3.1 双向无环链表

```c
// 链表节点
typedef struct listNode {
    struct listNode *prev;   // 前驱节点
    struct listNode *next;   // 后继节点
    void *value;             // 节点值
} listNode;

// 链表结构
typedef struct list {
    listNode *head;          // 头节点
    listNode *tail;          // 尾节点
    unsigned long len;       // 节点数量
    void *(*dup)(void *ptr); // 复制函数
    void (*free)(void *ptr); // 释放函数
    int (*match)(void *ptr, void *key); // 匹配函数
} list;
```

**链表特点：**

| 特性 | 实现 |
|------|------|
| 结构 | 双向无环 |
| 获取头/尾 | O(1) |
| 获取长度 | O(1)（有len字段） |
| 查找 | O(n) |
| 多态 | void*指针 + 函数指针 |

**Q: Redis List什么时候用链表？**

```
Redis 3.2之前:
  List的底层实现：
  - 元素少且元素小 → ziplist（压缩列表）
  - 元素多或元素大 → linkedlist（双向链表）

Redis 3.2+:
  List统一使用 quicklist（链表 + ziplist的混合体）
  
  quicklist结构:
  ┌─────────┐   ┌─────────┐   ┌─────────┐
  │ ziplist │◄─►│ ziplist │◄─►│ ziplist │
  │  (节点)  │   │  (节点)  │   │  (节点)  │
  └─────────┘   └─────────┘   └─────────┘
  
  每个quicklist节点包含一个ziplist
  既保留了链表的灵活性，又减少了内存碎片
```

---

## 四、字典：Hash与全局键空间

### 4.1 哈希表结构

```c
// 哈希表
typedef struct dictht {
    dictEntry **table;       // 哈希表数组
    unsigned long size;      // 哈希表大小（2^n）
    unsigned long sizemask;  // 掩码（size - 1）
    unsigned long used;      // 已使用节点数
} dictht;

// 哈希表节点（链地址法）
typedef struct dictEntry {
    void *key;               // 键
    union {
        void *val;
        uint64_t u64;
        int64_t s64;
        double d;
    } v;                     // 值
    struct dictEntry *next;  // 下一个节点（链表）
} dictEntry;

// 字典
typedef struct dict {
    dictType *type;          // 类型特定函数
    void *privdata;          // 私有数据
    dictht ht[2];            // 两个哈希表（rehash用）
    long rehashidx;          // rehash进度（-1表示未进行）
    int16_t pauserehash;     // rehash暂停标志
} dict;
```

### 4.2 渐进式Rehash

**Q: Redis的rehash过程是怎样的？为什么用渐进式？**

```
渐进式Rehash流程:

1. 分配空间
   ht[1] = 分配新哈希表（size = 第一个 >= ht[0].used*2 的 2^n）

2. 设置rehashidx = 0（标记rehash开始）

3. 每次对字典执行增删改查时，顺带迁移一个桶:
   - 将ht[0]的table[rehashidx]迁移到ht[1]
   - rehashidx++
   - 直到ht[0]全部迁移完成

4. 完成：rehashidx = -1，交换ht[0]和ht[1]

为什么渐进式？
  → 避免一次性rehash阻塞服务
  → 将迁移分摊到多次操作中
  → 空闲时也有定时任务(serverCron)协助rehash
```

```
┌─────────────────────────────────────────────────┐
│                渐进式Rehash示意图                  │
│                                                 │
│   ht[0] (旧表)          ht[1] (新表)             │
│  ┌───┬───┬───┬───┐     ┌───┬───┬───┬───┬───┐    │
│  │ 0 │ 1 │ 2 │ 3 │     │ 0 │ 1 │ 2 │ 3 │ 4 │    │
│  └─┬─┴─┬─┴───┴───┘     └───┴───┴───┴───┴───┘    │
│    │   │                                          │
│    │   └──── rehashidx = 1 已迁移 ────►           │
│    │                                              │
│    └──── rehashidx = 0 已迁移 ────►               │
│                                                   │
│  查询：先查ht[0]，再查ht[1]                        │
│  新增：只写ht[1]                                  │
│  删除：两个表都删                                 │
└─────────────────────────────────────────────────┘
```

**扩缩容条件：**

| 操作 | 触发条件 | 新大小 |
|------|---------|--------|
| 扩容 | used/size >= 1 (dict_can_resize=1) | 第一个 >= used*2 的 2^n |
| 强制扩容 | used/size > 5 (负载因子超5) | 同上 |
| 缩容 | used/size < 0.1 | 第一个 >= used 的 2^n |

### 4.3 哈希算法与冲突解决

```c
// Redis哈希算法：MurmurHash2
hash = dictType->hashFunction(key);
index = hash & dict->ht[0].sizemask;

// 冲突解决：链地址法（头插法）
// 新节点插入链表头部（O(1)）
entry->next = ht->table[index];
ht->table[index] = entry;
```

---

## 五、跳表：ZSet的核心引擎

### 5.1 为什么用跳表？

```
Q: 为什么ZSet用跳表而不用平衡树（如红黑树）？

A: 四个理由：
  1. 跳表实现简单（约200行 vs 红黑树500+行）
  2. 支持范围查询（ZRANGE），红黑树需要中序遍历
  3. 跳表在概率上性能与平衡树持平（O(log n)）
  4. 跳表天然适合并发（Redis 6.0+多线程IO）
```

### 5.2 跳表结构

```c
// 跳表节点
typedef struct zskiplistNode {
    sds ele;                     // 成员对象（字符串）
    double score;                // 分值（排序依据）
    struct zskiplistNode *backward; // 后退指针
    struct zskiplistLevel {
        struct zskiplistNode *forward; // 前进指针
        unsigned long span;           // 跨度（两节点间距离）
    } level[];                   // 层级数组（柔性数组）
} zskiplistNode;

// 跳表
typedef struct zskiplist {
    struct zskiplistNode *header, *tail;
    unsigned long length;        // 节点数量
    int level;                   // 当前最大层数
} zskiplist;
```

```
跳表示意图:

Level 3: [HEAD]────────────────────► [node4] ──► NULL
Level 2: [HEAD]────────► [node2]───► [node4] ──► NULL
Level 1: [HEAD]──► [node1]──► [node2]──► [node3]──► [node4] ──► NULL
                  │          │          │          │
                score:1    score:3    score:5    score:7
                ele:"a"    ele:"b"    ele:"c"    ele:"d"

查询score=5（查找路径）：
  从高层开始 → L3: node4(7) 太大 → 回退到L2 → node2(3) 可以 → 
  L1: node3(5) 找到！

时间: O(log n)
空间: 平均每个节点 1/(1-p) 层 (p=0.25，约1.33层/节点)
```

### 5.3 跳表层数生成

```c
// Redis跳表层数生成（幂次定律）
int zslRandomLevel(void) {
    int level = 1;
    // p = 1/4 (ZSKIPLIST_P = 0.25)
    while ((random() & 0xFFFF) < (ZSKIPLIST_P * 0xFFFF)) {
        level++;
    }
    return (level < ZSKIPLIST_MAXLEVEL) ? level : ZSKIPLIST_MAXLEVEL;
    // 最大64层
}

// 期望层数分布：
// level=1: 75%     (1-p = 0.75)
// level=2: 18.75%  (p*(1-p))
// level=3: 4.69%   (p^2*(1-p))
// level=4: 1.17%   ...
```

### 5.4 ZSet为什么还用了字典？

```
ZSet = 跳表 + 字典的复合结构

  跳表：按score排序，支持范围查询（ZRANGE, ZRANK）
  字典：O(1)获取元素的score（ZSCORE）

  Q: 为什么两个数据结构？
  A: 
    - 按成员查分数 → 字典 O(1)
    - 按分数范围查 → 跳表 O(log n)
    - 两者结合覆盖所有操作场景

  内存成本：共享节点，指针开销约2倍，但功能翻倍
```

---

## 六、压缩列表：小数据的紧凑表示

### 6.1 结构

```
压缩列表（ziplist）结构：

  ┌────────┬────────┬────────┬──────┬───┬──────┬────────┐
  │zlbytes │zltail  │zllen   │entry1│...│entryN│zlend   │
  │ 4字节  │ 4字节  │ 2字节  │      │   │      │ 1字节  │
  └────────┴────────┴────────┴──────┴───┴──────┴────────┘

  zlbytes: 整个ziplist占用内存字节数
  zltail:  最后一个entry距离起始的偏移量（实现O(1)尾部操作）
  zllen:   entry数量（>65535时需要遍历计算）
  zlend:   结束标记（0xFF）
```

### 6.2 节点编码

```c
// 压缩列表节点（entry）编码方式：

// 1. 前一个节点长度（prevlen）
//    - < 254字节：1字节存储
//    - >= 254字节：5字节存储（0xFE + 4字节长度）

// 2. 当前节点编码（encoding）
//    - 字节数组：|00|aaaaaa| → 长度<=63字节
//              |01|aaaaaa|bbbbbbbb| → 长度<=16383
//              |10|____|aaaaaaaa|bbbbbbbb|cccccccc|dddddddd|eeeeeeee| → 更大
//    - 整数：  |11000000| → int16_t
//              |11010000| → int32_t
//              |11100000| → int64_t
//              |11111110| → int8_t
//              |1111xxxx| → 小整数 (0-12)，xxxx=实际值-1

// 3. 实际数据（content）
```

### 6.3 连锁更新问题

```
Q: 压缩列表的连锁更新是什么？

触发条件：ziplist中有多个连续的长度在250~253字节的节点

过程：
  初始: [entry1:253B] [entry2:253B] [entry3:253B] ...
  
  在entry1前插入一个254+字节的节点：
  → entry1的prevlen从1字节变成5字节
  → entry1长度变成253+4=257字节
  → entry2的prevlen也要从1字节变成5字节
  → entry2长度变成253+4=257
  → ...连锁反应！

解决方案：
  1. 控制单个ziplist的节点数量（< 512个）
  2. 控制单个节点大小（避免在250-253字节边界）
  3. Redis 7.0引入listpack替代ziplist
```

### 6.4 Listpack：ziplist的继任者

```
Redis 7.0引入listpack，解决连锁更新：

  ziplist: [prevlen] [encoding] [data]
           ↑ 可变长，引发连锁更新

  listpack: [encoding+data] [backlen]
            ↑ 编码和数据放一起   ↑ 反向长度（存储本节点长度）

listpack优势：
  - 每个节点记录自己的长度而非前一个节点的长度
  - 避免了连锁更新问题
  - 与ziplist类似的内存紧凑特性
```

---

## 七、五种数据结构底层实现总览

### 7.1 实现对照表

| 数据类型 | Redis 3.2前 | Redis 3.2 ~ 6.x | Redis 7.0+ |
|----------|------------|-----------------|------------|
| String | SDS + int/embstr/raw | 同前 | 同前 |
| List | ziplist + linkedlist | quicklist | quicklist |
| Hash | ziplist + hashtable | ziplist + hashtable | listpack + hashtable |
| Set | intset + hashtable | 同前 | listpack + hashtable |
| ZSet | ziplist + skiplist+dict | 同前 | listpack + skiplist+dict |

### 7.2 编码转换条件

```
String的三种编码：
  int:     能解析为整数且 <= LONG_MAX
  embstr:  长度 <= 44字节（一次内存分配，只读）
  raw:     长度 > 44字节或embstr被修改后

Hash的编码转换（Redis 6.x）：
  ziplist条件（可配置）：
    hash-max-ziplist-entries: 512   # 元素数 <= 512
    hash-max-ziplist-value: 64       # 单个值 <= 64字节
  不满足任一条件 → hashtable

ZSet的编码转换：
  ziplist条件：
    zset-max-ziplist-entries: 128
    zset-max-ziplist-value: 64

Set的编码转换：
  intset条件：所有元素都是整数 && 元素数 <= 512
  否则 → hashtable
```

```java
// 查看编码
redis> SET key "hello"
OK
redis> OBJECT ENCODING key
"embstr"

redis> SET key "a very long string that exceeds the embstr limit"
OK
redis> OBJECT ENCODING key
"raw"

redis> SET key 12345
OK
redis> OBJECT ENCODING key
"int"
```

---

## 八、面试高频问题速答

**Q1: Redis的String是直接用的C字符串吗？**
A: 不是。Redis封装了SDS（简单动态字符串），解决了C字符串获取长度O(n)、缓冲区溢出、二进制不安全等问题。

**Q2: 字典的rehash是阻塞的吗？**
A: 不是。Redis采用渐进式rehash，将rehash操作分摊到每次增删改查中，避免一次性阻塞服务。空闲时也有定时任务协助。

**Q3: 跳表查询的复杂度是多少？**
A: 平均O(log n)。每个节点随机生成层数（期望1.33层），查询时从高层开始跳跃，跳过大量节点。

**Q4: 压缩列表有什么优缺点？**
A: 优点是内存紧凑（连续存储，无指针开销），适合小数据量。缺点是连锁更新问题和查询/修改需要遍历。Redis 7.0用listpack替代。

**Q5: List的quicklist是什么？**
A: quicklist是双向链表和ziplist的结合体。每个链表节点包含一个ziplist。既保留了链表的插入/删除灵活性，又通过ziplist减少了内存碎片和指针开销。

**Q6: ZSet的score可以重复吗？如何排序？**
A: score可以重复。相同score时，按成员字符串的字典序排序。底层跳表在score相同时比较ele（SDS字符串）。

**Q7: Hash什么情况下用ziplist（listpack）？**
A: 字段数 <= 512 且 所有值的长度 <= 64字节时使用ziplist/listpack。超过阈值自动转为hashtable。ziplist内存紧凑但操作O(n)，hashtable查询O(1)但内存开销大。

**Q8: Redis 7.0为何用listpack替代ziplist？**
A: 主要解决连锁更新问题。listpack每个节点记录自己的长度而非前一个节点的长度，从根本上消除了连锁更新。同时保持了内存紧凑的特性。

---

## 九、总结

| 底层结构 | 用途 | 时间复杂度 | 内存效率 | 核心技巧 |
|----------|------|-----------|---------|---------|
| SDS | String | O(1)长度 | 高 | 多种header、预分配、惰性释放 |
| 字典 | Hash, Set, 全局键空间 | O(1)查询 | 中 | 渐进式rehash、链地址法 |
| 跳表 | ZSet | O(log n) | 中 | 随机层数、跨度字段 |
| 压缩列表 | 小集合/Hash/ZSet | O(n) | 极高 | 连续内存、变长编码 |
| quicklist | List | 双向操作O(1) | 高 | ziplist节点 + 链表 |

**Redis快的内功心法：**
1. **空间换时间**：预分配、冗余存储（跳表+字典）
2. **编码自适应**：小数据用紧凑编码（ziplist/intset），大数据用高性能结构（hashtable/skiplist）
3. **内存极致**：变长编码、柔性数组、共享对象

> 🎯 **Redis面试八股文系列开篇！** 本文从五种核心数据结构的底层原理出发，深入SDS、字典渐进式rehash、跳表、压缩列表等面试高频考点，为后续Redis高级特性（持久化、集群、缓存策略）打下坚实基础。

> 📌 **下期预告**：《Redis面试八股文（二）——持久化、过期策略与内存淘汰》将深入RDB快照与AOF日志的原理对比、混合持久化机制、键的过期删除策略（惰性+定期）、以及八种内存淘汰算法的适用场景与实战选择，敬请期待！
