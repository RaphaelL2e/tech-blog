---
title: "ConcurrentHashMap 实现全解析：从分段锁到 CAS"
date: 2026-04-27T23:45:00+08:00
draft: false
categories: ["java"]
tags: ["Java", "面试", "ConcurrentHashMap", "并发", "源码解析"]
---

# ConcurrentHashMap 实现全解析：从分段锁到 CAS

## 一、为什么需要 ConcurrentHashMap

### 1.1 线程安全的 Map 方案对比

| 方案 | 线程安全 | 性能 | 缺点 |
|------|----------|------|------|
| HashMap | ❌ 不安全 | 高 | 并发 put 导致死循环（JDK7）、数据丢失 |
| Hashtable | ✅ 安全 | 极低 | 每个 方法加 synchronized，串行化 |
| Collections.synchronizedMap | ✅ 安全 | 低 | 包装层加锁，粒度同 Hashtable |
| **ConcurrentHashMap** | ✅ 安全 | **高** | 分段锁/CAS，细粒度并发控制 |

### 1.2 HashMap 的并发问题

```java
// JDK7 多线程扩容导致死循环
void transfer(Entry[] newTable) {
    // 头插法导致链表成环
    // 线程A暂停后线程B完成扩容
    // 线程A恢复后形成环形链表
    // get() 时死循环
}

// JDK8 虽然改为尾插法避免死循环，但仍有问题：
// 1. 并发 put 数据丢失（两个线程同时写入同一个桶）
// 2. size 不准确
// 3. 并发扩容数据损坏
```

### 1.3 Hashtable 为什么被淘汰

```java
// Hashtable 每个方法都加 synchronized
public synchronized V get(Object key) { ... }
public synchronized V put(K key, V value) { ... }
public synchronized V remove(Object key) { ... }
public synchronized int size() { ... }

// 问题：100个线程操作不同桶，完全可以并行
// 但 Hashtable 全局锁，完全串行
// 吞吐量 ≈ 单线程
```

## 二、JDK7 实现：分段锁（Segment）

### 2.1 整体架构

```
ConcurrentHashMap
├── Segment[] segments        // 默认16个段
│   ├── Segment 0
│   │   └── HashEntry[] table // 每段独立的Hash表
│   │       ├── HashEntry
│   │       └── HashEntry
│   ├── Segment 1
│   │   └── HashEntry[] table
│   ├── ...
│   └── Segment 15
│       └── HashEntry[] table
```

### 2.2 核心数据结构

```java
// 分段锁
static final class Segment<K,V> extends ReentrantLock {
    transient volatile HashEntry<K,V>[] table;
    transient int count;           // 元素计数
    transient int modCount;        // 修改次数
    transient int threshold;       // 扩容阈值
    final float loadFactor;        // 负载因子
}

// 链表节点
static final class HashEntry<K,V> {
    final int hash;
    final K key;
    volatile V value;
    volatile HashEntry<K,V> next;
}
```

### 2.3 定位流程：两次 Hash

```java
// 第一次 hash → 定位 Segment
int j = (hash >>> segmentShift) & segmentMask;
Segment<K,V> s = segments[j];

// 第二次 hash → 定位 HashEntry
int index = (tab.length - 1) & hash;
HashEntry<K,V> e = tab[index];
```

**为什么两次 Hash？**

- 第一次定位 Segment，确定哪个分段锁
- 第二次定位桶，在 Segment 内部寻址
- 分散 Hash 冲突，避免热点 Segment

### 2.4 put 流程

```java
public V put(K key, V value) {
    Segment<K,V> s;
    // 1. 定位 Segment（不需加锁，segments 是 volatile）
    int j = (hash >>> segmentShift) & segmentMask;
    
    // 2. 尝试获取 Segment 锁
    if ((s = segments[j]) == null)
        s = ensureSegment(j);
    
    // 3. 在 Segment 内部 put（需要获取 Segment 的 ReentrantLock）
    return s.put(key, hash, value, false);
}

// Segment.put
final V put(K key, int hash, V value, boolean onlyIfAbsent) {
    // tryLock() 尝试获取锁
    // 失败则 scanAndLockForPut() 自旋 + 预创建节点
    HashEntry<K,V> node = tryLock() ? null : scanAndLockForPut(key, hash, value);
    
    try {
        HashEntry<K,V>[] tab = table;
        int index = (tab.length - 1) & hash;
        HashEntry<K,V> first = tab[index];
        
        // 遍历链表查找 key
        for (HashEntry<K,V> e = first;;) {
            if (e != null) {
                if (e.hash == hash && key.equals(e.key)) {
                    // key 存在，更新 value
                    V oldValue = e.value;
                    if (!onlyIfAbsent)
                        e.value = value;
                    return oldValue;
                }
                e = e.next;
            } else {
                // key 不存在，头插法插入
                if (node != null)
                    node.setNext(first);
                else
                    node = new HashEntry<K,V>(hash, key, value, first);
                tab[index] = node;
                
                // 检查是否需要扩容
                if (++count > threshold)
                    rehash(node);
                return null;
            }
        }
    } finally {
        unlock(); // 释放 Segment 锁
    }
}
```

### 2.5 get 流程（不加锁！）

```java
public V get(Object key) {
    Segment<K,V> s;
    HashEntry<K,V>[] tab;
    int h = hash(key);
    
    // 定位 Segment
    long u = (((h >>> segmentShift) & segmentMask) << SSHIFT) + SBASE;
    
    if ((s = (Segment<K,V>)UNSAFE.getObjectVolatile(segments, u)) != null
        && (tab = s.table) != null) {
        // 遍历链表查找（不加锁，依赖 volatile 读）
        for (HashEntry<K,V> e = tab[(tab.length - 1) & h]; e != null; e = e.next) {
            if (e.hash == h && key.equals(e.key))
                return e.value;
        }
    }
    return null;
}
```

**为什么 get 不加锁？**

- `value` 是 volatile 的，保证可见性
- `HashEntry.next` 也是 volatile 的
- volatile 读的语义：总是读到最新写入的值
- **代价**：弱一致性——put 之后不一定立即 get 到

### 2.6 JDK7 的问题

| 问题 | 说明 |
|------|------|
| **Segment 数量固定** | 默认16个，并发度不可动态调整 |
| **内存浪费** | 每个 Segment 预分配 HashEntry[]，大量空桶 |
| **二次 Hash 开销** | 多一次 Hash 计算和寻址 |
| **Segment 粒度仍偏粗** | 同一 Segment 内的所有桶互斥 |
| **扩容粒度大** | 单个 Segment 扩容，不影响其他 Segment |

## 三、JDK8 实现：CAS + synchronized

### 3.1 架构变化

```
JDK7: Segment[] → HashEntry[]  (分段锁)
JDK8: Node[] → 链表/红黑树       (桶级锁)
```

**核心改变**：去掉 Segment，直接在 Node 数组的每个桶上做并发控制。

### 3.2 核心数据结构

```java
// 基础节点
static class Node<K,V> implements Map.Entry<K,V> {
    final int hash;
    final K key;
    volatile V val;    // volatile 保证可见性
    volatile Node<K,V> next;
}

// 转发节点（扩容期间使用）
static final class ForwardingNode<K,V> extends Node<K,V> {
    final Node<K,V>[] nextTable;  // 指向新表
    // hash 固定为 MOVED = -1
}

// 树节点
static final class TreeNode<K,V> extends Node<K,V> {
    TreeNode<K,V> parent, left, right;
    boolean red;
}

// 树桶头节点
static final class TreeBin<K,V> extends Node<K,V> {
    TreeNode<K,V> root;
    volatile TreeNode<K,V> first;
    volatile int waiterStatus;  // 读写锁状态
}
```

### 3.3 核心常量

```java
// Node 数组最大容量
private static final int MAXIMUM_CAPACITY = 1 << 30;

// 默认初始容量
private static final int DEFAULT_CAPACITY = 16;

// 负载因子
private static final float LOAD_FACTOR = 0.75f;

// 链表转红黑树阈值
static final int TREEIFY_THRESHOLD = 8;

// 红黑树退化链表阈值
static final int UNTREEIFY_THRESHOLD = 6;

// 链表转红黑树的最小表容量
static final int MIN_TREEIFY_CAPACITY = 64;

// 扩容转发标记
static final int MOVED     = -1;  // ForwardingNode
static final int TREEBIN   = -2;  // TreeBin
static final int RESERVED  = -3;  // computeIfAbsent 保留

// 扩容戳
static final int NCPU = Runtime.getRuntime().availableProcessors();
```

### 3.4 put 流程（核心！）

```java
final V putVal(K key, V value, boolean onlyIfAbsent) {
    if (key == null || value == null) throw new NullPointerException();
    int hash = spread(key.hashCode());  // 扰动函数
    int binCount = 0;
    
    for (Node<K,V>[] tab = table;;) {
        Node<K,V> f; int n, i, fh;
        
        // ========== 情况1：表未初始化 ==========
        if (tab == null || (n = tab.length) == 0)
            tab = initTable();
        
        // ========== 情况2：桶为空，CAS 插入 ==========
        else if ((f = tabAt(tab, i = (n - 1) & hash)) == null) {
            if (casTabAt(tab, i, null, new Node<K,V>(hash, key, value, null)))
                break;  // CAS 成功，插入完成
            // CAS 失败，自旋重试
        }
        
        // ========== 情况3：桶正在扩容，协助迁移 ==========
        else if ((fh = f.hash) == MOVED)
            tab = helpTransfer(tab, f);
        
        // ========== 情况4：桶不为空，加锁插入 ==========
        else {
            synchronized (f) {  // 锁住桶头节点
                if (tabAt(tab, i) == f) {  // 双重检查
                    if (fh >= 0) {
                        // 链表处理
                        binCount = 1;
                        for (Node<K,V> e = f;; ++binCount) {
                            if (e.hash == hash && key.equals(e.key)) {
                                // key 存在，更新
                                V oldVal = e.val;
                                if (!onlyIfAbsent)
                                    e.val = value;
                                return oldVal;
                            }
                            Node<K,V> pred = e;
                            if ((e = e.next) == null) {
                                // 尾插法
                                pred.next = new Node<K,V>(hash, key, value, null);
                                break;
                            }
                        }
                    } else if (f instanceof TreeBin) {
                        // 红黑树处理
                        Node<K,V> p;
                        binCount = 2;
                        if ((p = ((TreeBin<K,V>)f).putTreeVal(hash, key, value)) != null) {
                            V oldVal = p.val;
                            if (!onlyIfAbsent)
                                p.val = value;
                            return oldVal;
                        }
                    }
                }
            }
            // 检查是否需要树化
            if (binCount != 0) {
                if (binCount >= TREEIFY_THRESHOLD)
                    treeifyBin(tab, i);
                break;
            }
        }
    }
    
    addCount(1L, binCount);  // 更新计数
    return null;
}
```

**put 四种情况总结**：

| 情况 | 条件 | 操作 | 并发策略 |
|------|------|------|----------|
| 表未初始化 | `tab == null` | initTable() | CAS 设置 sizeCtl |
| 桶为空 | `tabAt(tab, i) == null` | CAS 插入 | 无锁 CAS |
| 桶在扩容 | `f.hash == MOVED` | helpTransfer() | 协助扩容 |
| 桶不为空 | 其他 | synchronized 锁头节点 | 桶级锁 |

### 3.5 CAS 操作详解

```java
// 获取桶引用（volatile 语义）
static final <K,V> Node<K,V> tabAt(Node<K,V>[] tab, int i) {
    return (Node<K,V>)U.getObjectVolatile(tab, ((long)i << ASHIFT) + ABASE);
}

// CAS 设置桶引用
static final <K,V> boolean casTabAt(Node<K,V>[] tab, int i,
                                     Node<K,V> c, Node<K,V> v) {
    return U.compareAndSwapObject(tab, ((long)i << ASHIFT) + ABASE, c, v);
}

// volatile 设置桶引用
static final <K,V> void setTabAt(Node<K,V>[] tab, int i, Node<K,V> v) {
    U.putObjectVolatile(tab, ((long)i << ASHIFT) + ABASE, v);
}
```

**为什么用 `getObjectVolatile` 而不直接 `tab[i]`？**

- 数组元素的可见性不被 `volatile Node[]` 保证
- `volatile` 只保证数组引用的可见性，不保证元素
- 必须使用 Unsafe 的 `getObjectVolatile` 确保读到最新值

### 3.6 initTable：安全初始化

```java
private final Node<K,V>[] initTable() {
    Node<K,V>[] tab; int sc;
    while ((tab = table) == null || tab.length == 0) {
        // sizeCtl < 0 说明其他线程正在初始化
        if ((sc = sizeCtl) < 0)
            Thread.yield();  // 让出 CPU，等待初始化完成
        
        // CAS 将 sizeCtl 设为 -1，获取初始化权
        else if (U.compareAndSwapInt(this, SIZECTL, sc, -1)) {
            try {
                if ((tab = table) == null || tab.length == 0) {
                    int n = (sc > 0) ? sc : DEFAULT_CAPACITY;
                    Node<K,V>[] nt = new Node[n];
                    table = tab = nt;
                    sc = n - (n >>> 2);  // 0.75n
                }
            } finally {
                sizeCtl = sc;  // 初始化完成，设为扩容阈值
            }
            break;
        }
    }
    return tab;
}
```

**sizeCtl 状态含义**：

| 值 | 含义 |
|-----|------|
| -1 | 正在初始化 |
| -(1 + nThreads) | 正在扩容，nThreads 为参与线程数 |
| 0 | 未初始化 |
| > 0 | 扩容阈值（初始化后 = 容量 × 0.75） |

### 3.7 get 流程（完全无锁）

```java
public V get(Object key) {
    Node<K,V>[] tab; Node<K,V> e, p; int n, eh; K ek;
    int h = spread(key.hashCode());
    
    if ((tab = table) != null && (n = tab.length) > 0
        && (e = tabAt(tab, (n - 1) & h)) != null) {
        
        if ((eh = e.hash) == h) {
            // 桶头就是目标
            if ((ek = e.key) == key || (ek != null && key.equals(ek)))
                return e.val;
        }
        else if (eh < 0)
            // hash < 0 的特殊情况
            // ForwardingNode: 去 nextTable 找
            // TreeBin: 调用 find 遍历红黑树
            return (p = e.find(h, key)) != null ? p.val : null;
        
        // 遍历链表
        while ((e = e.next) != null) {
            if (e.hash == h &&
                ((ek = e.key) == key || (ek != null && key.equals(ek))))
                return e.val;
        }
    }
    return null;
}
```

**get 无锁的保证**：

1. `tabAt()` — volatile 读桶引用
2. `Node.val` — volatile，保证值可见性
3. `Node.next` — volatile，保证链表可见性
4. **弱一致性**：get 可能读到旧值，但不会读到非法状态

## 四、扩容机制：多线程协作迁移

### 4.1 扩容触发条件

```java
// putVal 最后调用 addCount
addCount(1L, binCount);

private final void addCount(long x, int check) {
    // ... 计数逻辑 ...
    
    // 检查是否需要扩容
    while (s >= (long)(sc = sizeCtl) && (tab = table) != null) {
        int rs = resizeStamp(n);  // 扩容戳
        
        if (sc < 0) {
            // 正在扩容，是否需要协助
            if (... ) break;  // 各种不需要协助的条件
            if (U.compareAndSwapInt(this, SIZECTL, sc, sc + 1))
                transfer(tab, nextTab);  // 协助扩容
        } else {
            // 触发扩容
            if (U.compareAndSwapInt(this, SIZECTL, sc,
                                     (rs << RESIZE_STAMP_SHIFT) + 2))
                transfer(tab, null);  // 发起扩容
        }
    }
}
```

### 4.2 扩容戳（resizeStamp）

```java
static final int resizeStamp(int n) {
    // n = 16 时：
    // Integer.numberOfLeadingZeros(16) = 27
    // (1 << (RESIZE_STAMP_BITS - 1)) = 1 << 15 = 32768
    // 27 | 32768 = 32795
    return Integer.numberOfLeadingZeros(n) | (1 << (RESIZE_STAMP_BITS - 1));
}
```

**扩容戳编码**：高16位标记容量，低16位标记并发线程数。

### 4.3 transfer：分片迁移

```java
private final void transfer(Node<K,V>[] tab, Node<K,V>[] nextTab) {
    int n = tab.length, stride;
    
    // 1. 计算每个线程迁移的桶数（最少16个）
    if ((stride = (NCPU > 1) ? (n >>> 3) / NCPU : n) < MIN_TRANSFER_STRIDE)
        stride = MIN_TRANSFER_STRIDE;
    
    // 2. 首次扩容，创建新表（2倍容量）
    if (nextTab == null) {
        Node<K,V>[] nt = new Node[n << 1];
        nextTab = nt;
    }
    int nextn = nextTab.length;
    ForwardingNode<K,V> fwd = new ForwardingNode<K,V>(nextTab);
    
    // 3. 分片迁移（advance 从后往前分配桶）
    boolean advancing = true;
    for (int i = 0, bound = 0;;) {
        // 分配迁移区间 [bound, i]
        if (advancing) {
            if (--i >= bound || finishing)
                advancing = false;
            else if (nextIndex <= 0) {
                i = -1; advancing = false;
            }
            else if (U.compareAndSwapInt(this, TRANSFERINDEX, nextIndex,
                      nextBound = (nextIndex > stride ? nextIndex - stride : 0)))
                bound = nextBound; i = nextIndex - 1; advancing = false;
        }
        
        // 4. 迁移单个桶
        synchronized (f) {  // 锁住旧桶头节点
            // 拆分链表：低位桶 + 高位桶
            // hash & n == 0 → 低位（原位置）
            // hash & n != 0 → 高位（原位置 + n）
            // ... 迁移逻辑 ...
            
            // 设置 ForwardingNode 标记已迁移
            setTabAt(tab, i, fwd);
        }
    }
}
```

### 4.4 链表拆分（高低位）

```java
// 扩容时链表拆分的核心逻辑
// n = 旧表容量，hash & n 区分高低位
Node<K,V> loHead = null, loTail = null;  // 低位链表
Node<K,V> hiHead = null, hiTail = null;  // 高位链表

for (Node<K,V> e = f; e != null; e = e.next) {
    int h = e.hash;
    if ((h & n) == 0) {
        // 低位：新表位置 = 旧表位置
        if (loTail == null) loHead = e; else loTail.next = e;
        loTail = e;
    } else {
        // 高位：新表位置 = 旧表位置 + n
        if (hiTail == null) hiHead = e; else hiTail.next = e;
        hiTail = e;
    }
}

// 低位放原位置
if (loTail != null) { loTail.next = null; setTabAt(nextTab, i, loHead); }
// 高位放原位置 + n
if (hiTail != null) { hiTail.next = null; setTabAt(nextTab, i + n, hiHead); }
```

**为什么 hash & n 能拆分？**

- 扩容后 n 变为 2n，新 hash 桶索引 = hash & (2n - 1)
- 原索引 = hash & (n - 1)，新索引只多了 hash 的第 n 位
- `hash & n == 0`：第 n 位为 0，索引不变
- `hash & n != 0`：第 n 位为 1，索引 = 原位置 + n

### 4.5 协助扩容

```java
// putVal 发现桶头是 ForwardingNode（hash == MOVED）
else if ((fh = f.hash) == MOVED)
    tab = helpTransfer(tab, f);

final Node<K,V>[] helpTransfer(Node<K,V>[] tab, Node<K,V> f) {
    // 检查是否仍在扩容
    // CAS 增加 sizeCtl（线程计数 +1）
    // 调用 transfer 协助迁移
    // 完成后 CAS 减少 sizeCtl
}
```

**设计精髓**：扩容不是单线程完成的，而是所有发现扩容的线程都来帮忙，每个线程负责一段桶的迁移。

## 五、计数机制：CounterCell + CAS

### 5.1 为什么不用 AtomicLong

```java
// 高并发下，所有线程 CAS 竞争同一个 AtomicLong
// 大量 CAS 失败 → 自旋 → CPU 飙升
// 典型的伪共享问题
AtomicLong baseCount;  // ❌ 单点竞争
```

### 5.2 分散计数

```java
// 类似 LongAdder 的思路
private transient volatile CounterCell[] counterCells;
private transient volatile long baseCount;

@sun.misc.Contended static final class CounterCell {
    volatile long value;
    CounterCell(long x) { value = x; }
}
```

### 5.3 计数流程

```java
private final void addCount(long x, int check) {
    CounterCell[] as; long b, v; int m; CounterCell a;
    
    // 1. 优先 CAS 更新 baseCount
    if ((as = counterCells) != null ||
        !U.compareAndSwapLong(this, BASECOUNT, b = baseCount, s = b + x)) {
        
        // 2. CAS 失败，尝试更新 CounterCell
        boolean uncontended = true;
        if (as == null || (m = as.length - 1) < 0 ||
            (a = as[ThreadLocalRandom.getProbe() & m]) == null ||
            !(uncontended = U.compareAndSwapLong(a, CELLVALUE, v = a.value, v + x))) {
            
            // 3. Cell 也没命中或 CAS 失败，fullAddCount
            fullAddCount(x, uncontended);
            return;
        }
    }
    
    // 检查是否需要扩容
    if (check >= 0) { ... }
}
```

**计数优先级**：`baseCount CAS` → `CounterCell CAS` → `fullAddCount（创建/扩容 Cell）`

### 5.4 size 统计

```java
public int size() {
    long n = sumCount();
    return (n < 0L) ? 0 : (n > Integer.MAX_VALUE) ? Integer.MAX_VALUE : (int)n;
}

final long sumCount() {
    CounterCell[] as = counterCells;
    long sum = baseCount;  // 基础值
    if (as != null) {
        for (CounterCell a : as) {
            if (a != null)
                sum += a.value;  // 累加所有 Cell
        }
    }
    return sum;
}
```

**注意**：size() 是近似值，遍历 CounterCell 期间可能有并发修改。

## 六、红黑树转换

### 6.1 链表 → 红黑树

```java
private final void treeifyBin(Node<K,V>[] tab, int index) {
    Node<K,V> b; int n, sc;
    if (tab != null) {
        // 前置条件：表容量 < 64 时优先扩容，不树化
        if ((n = tab.length) < MIN_TREEIFY_CAPACITY)
            tryPresize(n << 1);  // 扩容而非树化
        
        else if ((b = tabAt(tab, index)) != null && b.hash >= 0) {
            synchronized (b) {  // 锁住桶头
                // 链表转红黑树
                // ... TreeNode 构建与平衡 ...
                // 设置 TreeBin 头节点（hash = TREEBIN = -2）
                setTabAt(tab, index, new TreeBin<K,V>(first));
            }
        }
    }
}
```

**树化条件**：
1. 链表长度 ≥ 8（TREEIFY_THRESHOLD）
2. 表容量 ≥ 64（MIN_TREEIFY_CAPACITY）
3. 不满足条件2时，先扩容

### 6.2 红黑树 → 链表

```java
// 扩容后红黑树节点太少，退化链表
// UNTREEIFY_THRESHOLD = 6
final Node<K,V> untreeify(Node<K,V>[] tab) {
    Node<K,V> hd = null, tl = null;
    for (Node<K,V> q = this; q != null; q = q.next) {
        Node<K,V> p = new Node<K,V>(q.hash, q.key, q.val, null);
        if (tl == null) hd = p; else tl.next = p;
        tl = p;
    }
    return hd;
}
```

### 6.3 TreeBin 的读写锁

```java
static final class TreeBin<K,V> extends Node<K,V> {
    // waiterStatus 状态：
    // 0        - 无等待者
    // WAITER    - 有读线程等待（1）
    // SIGNAL    - 有写线程等待（-1）
    // READER    - 读锁计数（> 0）
    
    // 读操作：乐观锁 + 查找
    // 写操作（put/remove）：synchronized + 写锁
    // 比链表遍历更复杂，但在 O(log n) 查找
}
```

## 七、JDK7 vs JDK8 核心对比

| 维度 | JDK7 | JDK8 |
|------|------|------|
| **锁粒度** | Segment（默认16段） | 桶（Node 级别） |
| **锁类型** | ReentrantLock | CAS + synchronized |
| **并发度** | 固定16 | 与桶数相同 |
| **数据结构** | HashEntry 链表 | 链表 + 红黑树 |
| **计数** | 遍历 Segment.count | CounterCell 分散计数 |
| **扩容** | 单线程 per Segment | 多线程协作迁移 |
| **null key/value** | 允许 | 禁止 |
| **查询复杂度** | O(n) 链表 | O(log n) 红黑树 |

## 八、面试高频问题

### Q1：为什么 JDK8 用 synchronized 替代 ReentrantLock？

**答案**：

1. **锁粒度更细**：JDK8 锁的是单个桶，锁持有时间极短
2. **synchronized 优化**：JDK6+ 引入偏向锁、轻量级锁、锁升级，短时间锁 synchronized 性能不输 ReentrantLock
3. **内存开销**：每个 Segment 都是一个 ReentrantLock 对象，16个 Segment = 16个 Lock 对象 + 16个 AQS。桶级锁不需要预分配 Lock 对象
4. **API 简洁**：synchronized 自动释放，不需要 try-finally

### Q2：ConcurrentHashMap 为什么不允许 null key/value？

```java
if (key == null || value == null) throw new NullPointerException();
```

**答案**：

如果 `get(key)` 返回 null，在并发场景下无法区分：
- key 不存在 → null
- key 存在但 value 是 null → null

HashMap 单线程可以用 `containsKey()` 先判断，但 ConcurrentHashMap 是并发的：
- `containsKey()` 和 `get()` 之间可能有其他线程修改
- **二义性问题**：永远无法确认 null 的含义

### Q3：ConcurrentHashMap 是强一致性还是弱一致性？

**弱一致性**，体现在：

1. **get 弱一致性**：遍历期间其他线程的修改可能看不到
2. **size 弱一致性**：sumCount 累加期间有并发修改
3. **迭代器弱一致性**：不会抛 ConcurrentModificationException
4. **clear 弱一致性**：逐桶清空，不是原子操作

```java
// 迭代器创建时不锁整个表
// 遍历到某个桶时才获取该桶的快照
// 其他桶可能正在被修改
```

### Q4：ConcurrentHashMap 如何保证 size 的准确性？

**不能保证完全准确**，但保证最终一致：

1. `baseCount`：无竞争时 CAS 更新
2. `CounterCell[]`：有竞争时分散到不同 Cell
3. `sumCount()`：累加 baseCount + 所有 CounterCell
4. 结果是**近似值**，但误差很小

### Q5：扩容期间如何保证并发安全？

1. **ForwardingNode**：已迁移的桶设为 ForwardingNode（hash = MOVED）
2. **协助扩容**：put 时发现 MOVED，先帮忙扩容
3. **分片迁移**：每个线程负责一段桶，用 CAS 分配区间
4. **synchronized**：迁移桶时锁住旧桶头节点
5. **双重检查**：加锁后再次检查桶头是否变化

### Q6：computeIfAbsent 的 ReservationNode 是什么？

```java
// computeIfAbsent 中，占位用
// 防止多个线程重复计算 value
static final class ReservationNode<K,V> extends Node<K,V> {
    // hash = RESERVED = -3
    // value = null
    // 作为一个占位标记
}
```

### Q7：ConcurrentHashMap 的 Key 为什么需要是不可变对象？

```java
// 如果 key 可变，hashCode 变化后：
// 1. get() 找不到（hash 变了，定位到错误桶）
// 2. 永远无法 remove（equals 和 hash 都不匹配）
// 3. 内存泄漏

// String、Integer 等不可变对象是安全的
// 自定义对象需确保 hashCode/equals 不变
```

## 九、最佳实践

### 9.1 正确使用姿势

```java
// ✅ 推荐：computeIfAbsent 原子操作
map.computeIfAbsent(key, k -> new ArrayList<>()).add(value);

// ❌ 错误：check-then-act 非原子
if (!map.containsKey(key)) {
    map.put(key, new ArrayList<>());  // 可能有其他线程已放入
}
map.get(key).add(value);

// ✅ 推荐：merge 原子操作
map.merge(key, 1, Integer::sum);

// ❌ 错误：非原子更新
map.put(key, map.getOrDefault(key, 0) + 1);
```

### 9.2 并发度调优

```java
// 预估并发线程数，设置初始容量减少扩容
// 初始容量 = (预计元素数 / 0.75) + 1
int expectedThreads = 32;
int expectedElements = 1000;
ConcurrentHashMap<String, String> map = new ConcurrentHashMap<>(
    (int)(expectedElements / 0.75) + 1
);

// JDK7 可以设置并发度
// new ConcurrentHashMap<>(initialCapacity, loadFactor, concurrencyLevel)
// JDK8 的 concurrencyLevel 仅影响初始容量
```

### 9.3 避免长时间持有桶锁

```java
// ❌ 在 compute 中做耗时操作
map.compute(key, (k, v) -> {
    try { Thread.sleep(1000); } catch (Exception e) {}  // 阻塞其他线程
    return newValue;
});

// ✅ 先计算，再写入
Value newValue = expensiveCompute();
map.put(key, newValue);
```

## 十、总结

### ConcurrentHashMap 的设计哲学

1. **锁粒度最小化**：从全局锁（Hashtable）→ 分段锁（JDK7）→ 桶级锁（JDK8）
2. **乐观并发**：CAS 优先，synchronized 兜底
3. **协作式扩容**：多线程共同完成迁移，而非阻塞等待
4. **分散计数**：CounterCell 避免单点竞争
5. **弱一致性换取高并发**：get 无锁，但可能读到旧值

### 面试回答模板

> JDK7 的 ConcurrentHashMap 使用分段锁（Segment + ReentrantLock），默认16个段，每个段是独立的 Hash 表，不同段可以并发操作。get 操作不加锁，依赖 volatile 保证可见性。
>
> JDK8 做了重大改进：去掉 Segment，直接在 Node 数组桶级别做并发控制。空桶用 CAS 插入，非空桶用 synchronized 锁头节点。引入红黑树优化查询性能，使用 CounterCell 分散计数，扩容时多线程协作迁移。整体并发度从固定16提升到与桶数相同，性能大幅提升。
