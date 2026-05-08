---
title: "HashMap 源码全解析：从扰动函数到红黑树"
date: 2026-04-27T22:15:00+08:00
draft: false
categories: ["java"]
tags: ["Java", "面试", "HashMap", "源码解析"]
---

# HashMap 源码全解析：从扰动函数到红黑树

HashMap 是 Java 面试中出现频率最高的集合类，没有之一。无论是校招还是社招，几乎所有 Java 面试都会问到 HashMap 的原理。很多候选人能说出「数组 + 链表 + 红黑树」「扰动函数」「扩容机制」等关键词，但真正能讲清楚源码细节和设计思想的却寥寥无几。

本文将从 JDK 8 源码出发，彻底剖析 HashMap 的底层实现，包括数据结构选择、哈希算法、插入流程、扩容机制、线程安全问题等核心知识点。

## 1. HashMap 的前世今生

### 1.1 JDK 7 vs JDK 8 的区别

在深入源码之前，我们需要了解 HashMap 在 JDK 7 和 JDK 8 之间的重大变化，因为面试官经常喜欢追问两者的区别。

JDK 7 中 HashMap 的核心数据结构是「数组 + 链表」，我们称之为「拉链法」。所有插入到同一个桶（bucket）中的元素会形成一个链表。当链表过长时，查询效率会退化为 O(n)，这是 JDK 7 HashMap 的性能瓶颈。

JDK 8 对此进行了重大优化，引入了红黑树。当链表长度超过 8 且数组长度大于等于 64 时，链表会转换为红黑树，将查询时间复杂度从 O(n) 降低到 O(log n)。

```java
// JDK 8 中的链表转红黑树阈值
static final int TREEIFY_THRESHOLD = 8;

// 红黑树转链表阈值
static final int UNTREEIFY_THRESHOLD = 6;

// 最小树形化阈值
static final int MIN_TREEIFY_CAPACITY = 64;
```

这个 8 和 6 的设计很有意思，为什么不是 7 或者 10 呢？根据泊松分布的计算，当哈希函数分布均匀时，链表长度达到 8 的概率非常低（小于千万分之一）。所以 8 是一个权衡：如果链表真的达到这个长度，说明哈希函数可能有问题，或者正在遭受哈希碰撞攻击，此时转换为红黑树可以保证最坏情况下的性能。

### 1.2 HashMap 的核心成员变量

```java
public class HashMap<K,V> extends AbstractMap<K,V>
    implements Map<K,V>, Cloneable, Serializable {

    // 默认初始容量 - 16
    static final int DEFAULT_INITIAL_CAPACITY = 1 << 4;

    // 最大容量 - 2 的 30 次方
    static final int MAXIMUM_CAPACITY = 1 << 30;

    // 默认负载因子 - 0.75
    static final float DEFAULT_LOAD_FACTOR = 0.75f;

    // 链表转红黑树的阈值
    static final int TREEIFY_THRESHOLD = 8;

    // 红黑树转链表的阈值
    static final int UNTREEIFY_THRESHOLD = 6;

    // 最小树形化阈值
    static final int MIN_TREEIFY_CAPACITY = 64;

    // 哈希表（数组）
    transient Node<K,V>[] table;

    // 键值对数量
    transient int size;

    // 阈值 = 容量 * 负载因子
    int threshold;

    // 负载因子
    final float loadFactor;
}
```

这里有几个关键点需要注意：

1. **容量必须为 2 的幂次方**：这是 HashMap 设计的一个巧妙之处，后面我们会详细讲解。
2. **负载因子默认为 0.75**：这是时间和空间的平衡。如果负载因子太小，例如 0.5，会导致频繁扩容，浪费空间；如果太大，例如 1.0，会导致哈希碰撞增多，链表变长，影响查询性能。
3. **阈值 = 容量 × 负载因子**：当键值对数量超过阈值时，会触发扩容。

## 2. 哈希算法详解

### 2.1 扰动函数的设计

HashMap 通过哈希函数将 Key 转换为数组下标。这个过程看似简单，但 JDK 8 中的实现却经过精心设计。

```java
static final int hash(Object key) {
    int h;
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}
```

这段代码看起来很简单，但其中蕴含的设计思想非常精妙。让我逐步解析：

1. **`key.hashCode()`**：获取 Key 的哈希码，这是一个 32 位整数。
2. **`h >>> 16`**：将哈希码右移 16 位，相当于将高 16 位移到低 16 位的位置。
3. **`h ^ (h >>> 16)`**：将原哈希码与其右移后的结果进行异或运算。

为什么需要这样做？

假设我们的数组容量是 16（`n = 16`，二进制 `10000`），我们需要计算 `(n - 1) & hash`。

如果直接使用 `hashCode()` 的低 16 位作为下标，会出现什么问题？

考虑两个哈希码：`0x11111111` 和 `0x21111111`，它们的低 16 位相同，高 16 位不同。直接用低 16 位作为下标会导致这两个 Key 哈希到同一个位置，尽管它们的哈希码完全不同。

通过扰动函数，我们将哈希码的高 16 位和低 16 位进行异或，这样可以让哈希码的所有 32 位都参与到下标计算中，使得哈希分布更加均匀。

### 2.2 容量为什么必须是 2 的幂次方？

HashMap 要求容量必须是 2 的幂次方（16, 32, 64, 128...），这是为了优化 `index` 的计算。

```java
// 计算数组下标
index = (n - 1) & hash
```

当 `n` 是 2 的幂次方时，`n - 1` 的二进制形式是全 1（例如 16 - 1 = 15 = `0b1111`）。这时 `&` 运算等价于取 hash 值的低几位，等价于 `hash % n`，但 `&` 运算比 `%` 运算快得多。

例如，数组容量为 16 时：

```java
hash = 0b10101010101010101010101010101010
n-1  = 0b00000000000000000000000000001111
----------------------------------------
index= 0b00000000000000000000000000001010  // 即 10
```

如果是普通除法 `hash % 16`，结果相同但效率更低。

这就是 HashMap 选择 2 的幂次方容量的根本原因——用位运算替代取模运算，将 O(n) 的除法转换为 O(1) 的位运算。

## 3. 插入流程源码解析

### 3.1 put 方法的核心逻辑

```java
public V put(K key, V value) {
    return putVal(hash(key), key, value, false, true);
}

final V putVal(int hash, K key, V value, boolean onlyIfAbsent,
               boolean evict) {
    Node<K,V>[] tab;
    Node<K,V> p;
    int n, i;

    // 1. 初始化或扩容
    if ((tab = table) == null || (n = tab.length) == 0)
        n = (tab = resize()).length;

    // 2. 计算下标，判断桶是否为空
    if ((p = tab[i = (n - 1) & hash]) == null)
        tab[i] = newNode(hash, key, value, null);
    else {
        // 3. 桶不为空，处理哈希冲突
        Node<K,V> e; K k;

        // 4. 判断第一个节点是否匹配
        if (p.hash == hash &&
            ((k = p.key) == key || (key != null && key.equals(k))))
            e = p;
        // 5. 判断是否是红黑树
        else if (p instanceof TreeNode)
            e = ((TreeNode<K,V>)p).putTreeVal(this, tab, hash, key, value);
        // 6. 遍历链表
        else {
            for (int binCount = 0; ; ++binCount) {
                if ((e = p.next) == null) {
                    p.next = newNode(hash, key, value, null);
                    // 7. 链表长度超过阈值，转红黑树
                    if (binCount >= TREEIFY_THRESHOLD - 1)
                        treeifyBin(tab, hash);
                    break;
                }
                // 8. 链表中找到相同 Key
                if (e.hash == hash &&
                    ((k = e.key) == key || (key != null && key.equals(k))))
                    break;
                p = e;
            }
        }

        // 9. 替换 Value
        if (e != null) {
            V oldValue = e.value;
            if (!onlyIfAbsent || oldValue == null)
                e.value = value;
            afterNodeAccess(e);
            return oldValue;
        }
    }

    // 10. 更新计数和阈值
    ++modCount;
    if (++size > threshold)
        resize();
    afterNodeInsertion(evict);
    return null;
}
```

这段源码体现了 HashMap 插入的完整流程：

1. **初始化或扩容**：如果数组为空，先调用 `resize()` 初始化。
2. **计算下标**：通过 `(n - 1) & hash` 计算桶的位置。
3. **空桶处理**：如果桶为空，直接插入新节点。
4. **非空桶处理**：
   - 先比较第一个节点的 Key 是否匹配
   - 如果是红黑树节点，调用 `putTreeVal()` 插入
   - 如果是链表，遍历并插入到尾部
5. **链表转红黑树**：当链表长度达到 8 时，调用 `treeifyBin()`。
6. **替换 Value**：如果找到相同 Key，替换 Value 并返回旧值。
7. **检查扩容**：如果键值对数量超过阈值，触发扩容。

### 3.2 equals 和 hashCode 的关系

面试中经常被问到的一个问题是：为什么重写 `equals()` 方法时必须重写 `hashCode()` 方法？

这是因为 HashMap 在查找元素时，首先通过 `hashCode()` 定位到桶，然后通过 `equals()` 在链表或红黑树中查找具体元素。

如果两个对象 `equals()` 返回 true，但 `hashCode()` 返回不同的值，会出现以下问题：

```java
String s1 = new String("通话");
String s2 = new String("重地");

// 两个字符串的 hashCode 不同
System.out.println(s1.hashCode());  // 1179395
System.out.println(s2.hashCode());  // 1179395
System.out.println(s1.equals(s2));  // false

// 如果 HashMap 使用 s1 作为 Key
HashMap<String, Object> map = new HashMap<>();
map.put(s1, "value");

// 使用 s2 查询会失败（虽然 equals 为 false，但 hashCode 不同）
map.get(s2);  // null - 错误！
```

正确的做法是：当两个对象 `equals()` 返回 true 时，它们的 `hashCode()` 必须返回相同的值。这就是 `equals()` 和 `hashCode()` 的契约关系。

## 4. 扩容机制深度解析

### 4.1 扩容触发条件

HashMap 的扩容触发条件有两个：

1. **键值对数量超过阈值**：`size > threshold`
2. **链表长度达到 8 但数组长度小于 64**：`treeifyBin()` 中的逻辑

```java
final Node<K,V>[] resize() {
    Node<K,V>[] oldTab = table;
    int oldCap = (oldTab == null) ? 0 : oldTab.length;
    int oldThr = threshold;
    int newCap, newThr = 0;

    // 计算新的容量和阈值
    if (oldCap > 0) {
        if (oldCap >= MAXIMUM_CAPACITY) {
            threshold = Integer.MAX_VALUE;
            return oldTab;
        }
        newCap = oldCap << 1;  // 容量翻倍
        newThr = oldThr << 1;  // 阈值翻倍
    } else if (oldThr > 0) {
        newCap = oldThr;
    } else {
        newCap = DEFAULT_INITIAL_CAPACITY;  // 16
        newThr = (int)(DEFAULT_LOAD_FACTOR * DEFAULT_INITIAL_CAPACITY);  // 12
    }

    if (newThr == 0) {
        float ft = (float)newCap * loadFactor;
        newThr = (newCap < MAXIMUM_CAPACITY && ft < (float)MAXIMUM_CAPACITY ?
                  (int)ft : Integer.MAX_VALUE);
    }
    threshold = newThr;

    // 创建新数组并迁移元素
    @SuppressWarnings({"rawtypes","unchecked"})
    Node<K,V>[] newTab = (Node<K,V>[])new Node[newCap];
    table = newTab;

    if (oldTab != null) {
        for (int j = 0; j < oldCap; ++j) {
            Node<K,V> e;
            if ((e = oldTab[j]) != null) {
                oldTab[j] = null;
                if (e.next == null)
                    newTab[e.hash & (newCap - 1)] = e;
                else if (e instanceof TreeNode)
                    ((TreeNode<K,V>)e).split(this, newTab, j, oldCap);
                else {
                    // 链表优化：分为高位链和低位链
                    Node<K,V> loHead = null, loTail = null;
                    Node<K,V> hiHead = null, hiTail = null;
                    Node<K,V> next;
                    do {
                        next = e.next;
                        if ((e.hash & oldCap) == 0) {
                            if (loTail == null)
                                loHead = e;
                            else
                                loTail.next = e;
                            loTail = e;
                        } else {
                            if (hiTail == null)
                                hiHead = e;
                            else
                                hiTail.next = e;
                            hiTail = e;
                        }
                    } while ((e = next) != null);
                    if (loTail != null) {
                        loTail.next = null;
                        newTab[j] = loHead;
                    }
                    if (hiTail != null) {
                        hiTail.next = null;
                        newTab[j + oldCap] = hiHead;
                    }
                }
            }
        }
    }
    return newTab;
}
```

### 4.2 扩容优化：高位链和低位链

这是 JDK 8 对扩容的重大优化。JDK 7 中，每次扩容都需要重新计算每个元素的哈希值，并将它们移动到新的数组位置，这是一个 O(n) 的操作。

JDK 8 通过观察发现：当容量翻倍时，元素的新位置要么在原位置，要么在原位置 + 旧容量。判断依据是 `hash & oldCap`：

- 如果结果为 0，说明元素应该留在原位置（下标不变）
- 如果结果为 1，说明元素应该移动到「原位置 + 旧容量」

以容量从 16 扩容到 32 为例：

```
原数组下标计算：(n - 1) & hash = 15 & hash = 0b1111 & hash
新数组下标计算：(2n - 1) & hash = 31 & hash = 0b11111 & hash

hash & 16 (oldCap) = 0b10000 & hash
```

通过 `hash & oldCap` 的结果，我们可以判断元素的最高位是 0 还是 1，从而决定它应该留在原位置还是移动到新位置。

这个优化的效果：
- **时间复杂度**：从 O(n) 降低到 O(n)
- **但实际效率提升显著**：因为不需要重新计算哈希值，只需要判断一位

### 4.3 为什么 HashMap 不是线程安全的？

HashMap 在并发环境下存在以下问题：

1. **数据覆盖**：两个线程同时 `put()`，可能导致数据覆盖。
2. **扩容死循环**：JDK 7 中，并发扩容可能导致链表形成环形，造成死循环（**JDK 8 已修复红黑树，但仍有数据覆盖问题**）。
3. **modCount 不一致**：`fail-fast` 机制可能误触发。

```java
// JDK 7 扩容死循环的核心问题
void transfer(Entry[] newTable, boolean rehash) {
    Entry[] src = table;
    int newCapacity = newTable.length;
    for (int j = 0; j < src.length; j++) {
        Entry<K,V> e = src[j];
        if (e != null) {
            src[j] = null;
            do {
                Entry<K,V> next = e.next;
                int i = indexFor(e.hash, newCapacity);
                e.next = newTable[i];
                newTable[i] = e;
                e = next;
            } while (e != null);
        }
    }
}
```

JDK 7 中，如果两个线程同时扩容，链表节点的 `next` 指针可能被错误地指向，形成环形。当遍历这个环形链表时，就会发生死循环。

JDK 8 虽然用红黑树替代了链表，避免了环形链表的问题，但仍然不是线程安全的。在并发环境下，应该使用 `ConcurrentHashMap`。

## 5. 红黑树详解

### 5.1 链表转红黑树的时机

```java
final void treeifyBin(Node<K,V>[] tab, int hash) {
    int n, index; Node<K,V> e;
    if (tab == null || (n = tab.length) < MIN_TREEIFY_CAPACITY)
        resize();  // 数组小于 64，先扩容
    else if ((e = tab[index = (n - 1) & hash]) != null) {
        hd = tl = null;
        do {
            e.hash = hash;
            e.key = k;
            e.value = v;
            e.next = null;
            if ((p = e.prev) == null)
                hd = p;
            else
                p.next = hd;
            hd = p;
        } while ((e = e.next) != null);
        if ((tab[index] = hd) != null)
            ((TreeNode<K,V>)hd).treeify(tab);
    }
}
```

注意这里的关键点：**当数组长度小于 64 时，优先扩容而不是树化**。这是因为在数组较小的情况下，扩容比树化更能解决哈希碰撞问题。

### 5.2 红黑树的特性

红黑树是一种自平衡的二叉搜索树，它保证：

1. 每个节点要么是红色，要么是黑色。
2. 根节点是黑色。
3. 所有叶子节点（NIL）是黑色。
4. 红色节点的子节点必须是黑色（不能有两个连续的红色节点）。
5. 从任一节点到其每个叶子的路径上，黑色节点的数量相同。

这些约束保证了红黑树的高度大致为 `log(n)`，因此查询、插入、删除的时间复杂度都是 O(log n)。

## 6. 常见面试问题

### 6.1 HashMap 的默认容量是 16，为什么？

16 是一个经验值，2 的 4 次方。选择 16 是因为：
- 2 的幂次方便于位运算计算下标
- 16 是一个适中的值，兼顾内存占用和哈希分布
- 负载因子 0.75 意味着默认情况下可以存储 12 个元素而不扩容

### 6.2 为什么 String 类型适合作为 HashMap 的 Key？

String 类型适合作为 HashMap 的 Key 的原因：

1. **不可变性**：String 是不可变类，一旦创建就不能修改，保证了 Key 的哈希值不会改变。
2. **已经重写了 hashCode 和 equals**：String 已经正确实现了 `hashCode()` 和 `equals()` 方法，满足哈希表的契约。
3. **哈希算法高效**：String 的 `hashCode()` 实现经过优化，分布均匀。

### 6.3 HashMap、Hashtable、ConcurrentHashMap 的区别？

| 特性 | HashMap | Hashtable | ConcurrentHashMap |
|------|---------|-----------|-------------------|
| 线程安全 | 否 | 是（synchronized） | 是（CAS + synchronized） |
| 性能 | 高 | 低（全局锁） | 高（分段锁/桶锁） |
| null Key | 支持一个 | 不支持 | 不支持 |
| null Value | 支持 | 不支持 | 支持 |
| 数据结构 | 数组+链表+红黑树 | 数组+链表 | 数组+链表+红黑树 |
| 迭代器 | fail-fast | fail-fast | fail-safe |

### 6.4 如何解决 HashMap 的线程安全问题？

有几种方案：

1. **使用 Collections.synchronizedMap()**：将 HashMap 包装为同步集合，但性能较低。
2. **使用 Hashtable**：全局锁，并发性能差。
3. **使用 ConcurrentHashMap**：推荐方案，使用 CAS 和 synchronized 实现细粒度锁。
4. **使用 JDK 8 的 ConcurrentHashMap**：桶锁 + CAS，性能最优。

### 6.5 HashMap 的容量为什么必须是 2 的幂次方？

因为 `(n - 1) & hash` 等价于 `hash % n`，但 `&` 运算比 `%` 快得多。这是用空间换时间的经典设计。

### 6.6 扰动函数的作用是什么？

将哈希码的高 16 位和低 16 位进行异或，让哈希码的所有位都参与下标计算，使哈希分布更加均匀，减少哈希碰撞。

## 7. 总结

HashMap 是 Java 集合框架中最复杂的类之一，它的设计体现了众多优秀的编程思想：

1. **空间换时间**：通过控制负载因子，在时间和空间之间取得平衡。
2. **位运算优化**：用 `&` 运算替代 `%` 运算，提升计算效率。
3. **红黑树优化**：当链表过长时，转换为红黑树，保证最坏情况下的性能。
4. **扩容优化**：JDK 8 的高位链低位链设计，避免了重新计算哈希值。

理解 HashMap 的源码，不仅是为了应对面试，更是为了培养对数据结构、算法、并发编程的深入理解。希望本文能帮助你彻底掌握 HashMap，在面试和工作中都能游刃有余。

---

**推荐阅读**：
- [Java 面试二 ConcurrentHashMap 实现原理](/categories/java/)
- [Java 设计模式系列](/categories/java/)
- [JVM 调优实战](/tags/jvm/)
