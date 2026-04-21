---
title: "Java设计模式（十二）：迭代器模式深度实践"
date: 2026-04-21T23:10:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "迭代器模式", "iterator"]
---

## 前言

前面系列文章已经覆盖了 11 种设计模式。今天继续 Java 设计模式系列，**迭代器模式（Iterator Pattern）** 是行为型模式中的经典，用于提供一种顺序访问集合元素的方式，而不暴露集合的底层表示。

**核心思想**：将集合的遍历行为抽象为独立的迭代器对象，使得可以在不知道集合内部结构的情况下遍历元素。

<!--more-->

## 一、为什么需要迭代器模式

### 1.1 紧耦合的集合遍历

```java
// ❌ 典型问题：集合和遍历逻辑紧耦合
public class ArrayCollection {
    
    private Object[] items = new Object[100];
    private int count = 0;
    
    // 集合本身提供遍历方法
    public void forEach() {
        for (int i = 0; i < count; i++) {
            System.out.println(items[i]);
        }
    }
    
    // 如果要反向遍历？按条件过滤？就需要新增方法
    public void forEachReverse() {
        for (int i = count - 1; i >= 0; i--) {
            System.out.println(items[i]);
        }
    }
}

// 使用方被迫依赖集合内部结构
public class Client {
    public void process(ArrayCollection collection) {
        // ❌ 直接访问内部数组，破坏了封装
        for (int i = 0; i < collection.count; i++) {
            Object item = collection.items[i];  // 暴露了内部结构！
        }
    }
}
```

**问题**：
- 集合承担了遍历职责，违反单一职责原则
- 暴露了内部结构（数组、链表、树），破坏封装
- 难以更换遍历策略（正序、反序、条件过滤）
- 不同集合（Array、LinkedList、Tree）遍历方式不同

### 1.2 迭代器模式的优势

```java
// ✅ 使用迭代器模式
public interface Iterator<E> {
    boolean hasNext();
    E next();
    void remove();
}

public class ArrayIterator<E> implements Iterator<E> {
    
    private ArrayCollection<E> collection;
    private int position = 0;
    
    public ArrayIterator(ArrayCollection<E> collection) {
        this.collection = collection;
    }
    
    @Override
    public boolean hasNext() {
        return position < collection.size();
    }
    
    @Override
    public E next() {
        return collection.get(position++);
    }
}

// 集合只负责存储，迭代器负责遍历
public class ArrayCollection<E> {
    
    private Object[] items = new Object[100];
    private int count = 0;
    
    public void add(E item) {
        items[count++] = item;
    }
    
    public E get(int index) {
        return (E) items[index];
    }
    
    public int size() {
        return count;
    }
    
    // 创建对应的迭代器
    public Iterator<E> iterator() {
        return new ArrayIterator<>(this);
    }
}

// 使用方完全不依赖集合内部
public class Client {
    public void process(ArrayCollection<?> collection) {
        Iterator<?> it = collection.iterator();
        while (it.hasNext()) {
            Object item = it.next();
            System.out.println(item);
        }
    }
}
```

**优点**：
- 封装集合遍历逻辑，单一职责原则
- 不暴露集合底层结构
- 支持多种遍历策略
- 集合和遍历算法分离，可独立变化

## 二、迭代器模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                   Aggregate (聚合接口)                        │
├─────────────────────────────────────────────────────────────┤
│ + createIterator(): Iterator                                │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴──────────────────────────────┐
▼                                          ▼
┌─────────────────┐               ┌─────────────────┐
│ ConcreteAggregate│               │  ...            │
├─────────────────┤               ├─────────────────┤
│ + createIterator│               │ + createIterator│
└─────────────────┘               └─────────────────┘
              │                             │
              │ creates                      │ creates
              ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Iterator (迭代器接口)                     │
├─────────────────────────────────────────────────────────────┤
│ + hasNext(): boolean                                       │
│ + next(): E                                                 │
│ + remove(): void                                            │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴──────────────────────────────┐
▼                                          ▼
┌─────────────────┐               ┌─────────────────┐
│ ConcreteIterator │               │  ReverseIterator │
├─────────────────┤               ├─────────────────┤
│ - position       │               │ - position       │
│ + hasNext()      │               │ + hasNext()      │
│ + next()         │               │ + next()         │
└─────────────────┘               └─────────────────┘
```

### 2.2 完整代码实现

```java
// ==================== Iterator 接口 ====================
public interface Iterator<E> {
    
    /**
     * 是否还有下一个元素
     */
    boolean hasNext();
    
    /**
     * 返回下一个元素
     */
    E next();
    
    /**
     * 删除当前元素（可选操作）
     */
    default void remove() {
        throw new UnsupportedOperationException("Remove not supported");
    }
    
    /**
     * 反向迭代器标记接口
     */
    interface ReverseIterator<E> extends Iterator<E> {
        boolean hasPrevious();
        E previous();
    }
}

// ==================== Aggregate 接口 ====================
public interface Aggregate<E> {
    
    /**
     * 创建迭代器
     */
    Iterator<E> createIterator();
    
    /**
     * 创建反向迭代器
     */
    default Iterator<E> createReverseIterator() {
        return null;
    }
    
    /**
     * 集合大小
     */
    int size();
    
    /**
     * 获取元素
     */
    E get(int index);
}

// ==================== 具体聚合：数组集合 ====================
public class ArrayCollection<E> implements Aggregate<E> {
    
    private Object[] items;
    private int size = 0;
    private static final int DEFAULT_CAPACITY = 16;
    
    public ArrayCollection() {
        this.items = new Object[DEFAULT_CAPACITY];
    }
    
    public ArrayCollection(int capacity) {
        this.items = new Object[capacity];
    }
    
    public void add(E item) {
        if (size >= items.length) {
            resize(items.length * 2);
        }
        items[size++] = item;
    }
    
    private void resize(int newCapacity) {
        Object[] newItems = new Object[newCapacity];
        System.arraycopy(items, 0, newItems, 0, size);
        items = newItems;
    }
    
    @Override
    public E get(int index) {
        if (index < 0 || index >= size) {
            throw new IndexOutOfBoundsException("Index: " + index);
        }
        return (E) items[index];
    }
    
    @Override
    public int size() {
        return size;
    }
    
    @Override
    public Iterator<E> createIterator() {
        return new ArrayIterator<>(this);
    }
    
    @Override
    public Iterator<E> createReverseIterator() {
        return new ArrayReverseIterator<>(this);
    }
    
    // 内部迭代器类（有权访问聚合内部结构）
    private class ArrayIterator implements Iterator<E> {
        
        private int position = 0;
        
        public ArrayIterator(ArrayCollection<E> collection) {
            // 迭代器可以访问聚合的内部数据
        }
        
        @Override
        public boolean hasNext() {
            return position < ArrayCollection.this.size;
        }
        
        @Override
        public E next() {
            if (!hasNext()) {
                throw new NoSuchElementException();
            }
            return (E) items[position++];
        }
        
        @Override
        public void remove() {
            if (position == 0) {
                throw new IllegalStateException();
            }
            // 移动元素并缩小
            System.arraycopy(items, position, items, position - 1, size - position);
            items[--size] = null;
            position--;
        }
    }
    
    // 反向迭代器
    private class ArrayReverseIterator implements Iterator<E> {
        
        private int position = ArrayCollection.this.size - 1;
        
        @Override
        public boolean hasNext() {
            return position >= 0;
        }
        
        @Override
        public E next() {
            if (position < 0) {
                throw new NoSuchElementException();
            }
            return (E) items[position--];
        }
    }
}

// ==================== 具体聚合：链表集合 ====================
public class LinkedCollection<E> implements Aggregate<E> {
    
    private Node<E> head;
    private Node<E> tail;
    private int size = 0;
    
    private static class Node<E> {
        E data;
        Node<E> next;
        Node<E> prev;
        
        Node(E data) {
            this.data = data;
        }
    }
    
    public void add(E item) {
        Node<E> node = new Node<>(item);
        if (tail == null) {
            head = tail = node;
        } else {
            tail.next = node;
            node.prev = tail;
            tail = node;
        }
        size++;
    }
    
    @Override
    public E get(int index) {
        if (index < 0 || index >= size) {
            throw new IndexOutOfBoundsException();
        }
        Node<E> current = head;
        for (int i = 0; i < index; i++) {
            current = current.next;
        }
        return current.data;
    }
    
    @Override
    public int size() {
        return size;
    }
    
    @Override
    public Iterator<E> createIterator() {
        return new LinkedIterator(head);
    }
    
    private class LinkedIterator implements Iterator<E> {
        
        private Node<E> current;
        private Node<E> lastReturned;
        private int currentIndex = 0;
        
        public LinkedIterator(Node<E> head) {
            this.current = new Node<>(null);  // 哨兵节点
            this.current.next = head;
        }
        
        @Override
        public boolean hasNext() {
            return current.next != null;
        }
        
        @Override
        public E next() {
            if (!hasNext()) {
                throw new NoSuchElementException();
            }
            lastReturned = current;
            current = current.next;
            currentIndex++;
            return current.data;
        }
        
        @Override
        public void remove() {
            if (lastReturned == current) {
                throw new IllegalStateException();
            }
            Node<E> prev = lastReturned;
            Node<E> next = current;
            prev.next = next;
            if (next != null) {
                next.prev = prev;
            } else {
                tail = prev;
            }
            size--;
            currentIndex--;
            lastReturned = null;
        }
    }
}

// ==================== 测试 ====================
public class IteratorTest {
    
    public static void main(String[] args) {
        // 测试数组集合
        System.out.println("=== 数组集合 ===");
        ArrayCollection<String> array = new ArrayCollection<>();
        array.add("Java");
        array.add("Python");
        array.add("Go");
        array.add("Rust");
        
        System.out.println("正序遍历:");
        Iterator<String> it = array.createIterator();
        while (it.hasNext()) {
            System.out.println("  " + it.next());
        }
        
        System.out.println("\n反向遍历:");
        Iterator<String> revIt = array.createReverseIterator();
        while (revIt.hasNext()) {
            System.out.println("  " + revIt.next());
        }
        
        System.out.println("\n使用 for-each 风格（需要 Iterable）:");
        for (String lang : array) {  // 需要实现 Iterable 接口
            System.out.println("  " + lang);
        }
        
        // 测试链表集合
        System.out.println("\n=== 链表集合 ===");
        LinkedCollection<Integer> linked = new LinkedCollection<>();
        linked.add(1);
        linked.add(2);
        linked.add(3);
        
        Iterator<Integer> lit = linked.createIterator();
        while (lit.hasNext()) {
            System.out.println("  " + lit.next());
        }
    }
}
```

## 三、Java 内置迭代器支持

### 3.1 Iterable 和 Iterator

Java 早就内置了迭代器模式，`for-each` 循环底层就是迭代器：

```java
// Iterable 接口：让集合可以被 for-each 遍历
public interface Iterable<T> {
    Iterator<T> iterator();
    default void forEach(Consumer<? super T> action) {
        Objects.requireNonNull(action);
        for (T t : this) {
            action.accept(t);
        }
    }
    default Spliterator<T> spliterator() {
        return Spliterators.spliteratorUnknownSize(iterator(), 0);
    }
}

// Iterator 接口
public interface Iterator<E> {
    boolean hasNext();
    E next();
    default void remove() {
        throw new UnsupportedOperationException("remove");
    }
    default void forEachRemaining(Consumer<? super E> action) {
        Objects.requireNonNull(action);
        while (hasNext()) {
            action.accept(next());
        }
    }
}

// 让 ArrayCollection 支持 for-each
public class ArrayCollection<E> implements Aggregate<E>, Iterable<E> {
    
    // ... 原有代码 ...
    
    @Override
    public Iterator<E> iterator() {
        return createIterator();
    }
}

// 现在可以直接使用 for-each
for (String item : arrayCollection) {
    System.out.println(item);
}
```

### 3.2 ListIterator

`ListIterator` 是专门为 List 设计的双向迭代器：

```java
public interface ListIterator<E> extends Iterator<E> {
    // 双向移动
    boolean hasNext();
    E next();
    boolean hasPrevious();
    E previous();
    
    // 位置信息
    int nextIndex();
    int previousIndex();
    
    // 修改
    void remove();
    void set(E e);        // 修改最后一个返回的元素
    void add(E e);        // 在当前位置添加元素
}

// ArrayList 的 ListIterator
public class ArrayList<E> extends AbstractList<E> 
        implements List<E>, RandomAccess {
    
    @Override
    public ListIterator<E> listIterator() {
        return new ListItr(0);
    }
    
    @Override
    public ListIterator<E> listIterator(int index) {
        return new ListItr(index);
    }
    
    private class ListItr extends Itr implements ListIterator<E> {
        private int expectedModCount = modCount;
        
        ListItr(int index) {
            cursor = index;
        }
        
        @Override
        public boolean hasPrevious() {
            return cursor != 0;
        }
        
        @Override
        public int nextIndex() {
            return cursor;
        }
        
        @Override
        public int previousIndex() {
            return cursor - 1;
        }
        
        @Override
        public E previous() {
            checkForComodification();
            int i = cursor - 1;
            if (i < 0) {
                throw new NoSuchElementException();
            }
            E element = (E) elementData[i];
            cursor = i;
            lastRet = i;
            return element;
        }
        
        @Override
        public void set(E e) {
            if (lastRet < 0) {
                throw new IllegalStateException();
            }
            checkForComodification();
            try {
                ArrayList.this.set(lastRet, e);
            } catch (IndexOutOfBoundsException ex) {
                throw new ConcurrentModificationException();
            }
        }
        
        @Override
        public void add(E e) {
            checkForComodification();
            try {
                int i = cursor;
                ArrayList.this.add(i, e);
                cursor = i + 1;
                lastRet = -1;
                expectedModCount = modCount;
            } catch (IndexOutOfBoundsException ex) {
                throw new ConcurrentModificationException();
            }
        }
    }
}

// 使用示例
List<String> list = new ArrayList<>();
list.add("A");
list.add("B");
list.add("C");

ListIterator<String> lit = list.listIterator();
while (lit.hasNext()) {
    System.out.println("next: " + lit.next());
}
while (lit.hasPrevious()) {
    System.out.println("previous: " + lit.previous());
}

// 在迭代中修改
lit = list.listIterator();
while (lit.hasNext()) {
    String s = lit.next();
    if ("B".equals(s)) {
        lit.set("BB");     // 修改
        lit.add("NEW");    // 插入
    }
}
System.out.println(list);  // [A, BB, NEW, C]
```

### 3.3 Enumeration

JDK 1.0 就有的古老迭代器，用于旧API的兼容：

```java
// 古老的迭代器接口
public interface Enumeration<E> {
    boolean hasMoreElements();
    E nextElement();
}

// Vector 的 Enumeration
Vector<String> vector = new Vector<>();
vector.add("One");
vector.add("Two");

Enumeration<String> e = vector.elements();
while (e.hasMoreElements()) {
    System.out.println(e.nextElement());
}

// Collections 的工具方法：Enumeration → Iterator
public static <E> Iterator<E> asIterator(Enumeration<E> e) {
    return new Iterator<E>() {
        @Override
        public boolean hasNext() {
            return e.hasMoreElements();
        }
        
        @Override
        public E next() {
            return e.nextElement();
        }
    };
}
```

## 四、迭代器的变体

### 4.1 过滤迭代器

只返回满足条件的元素：

```java
public class FilterIterator<T> implements Iterator<T> {
    
    private Iterator<T> source;
    private Predicate<T> predicate;
    private T nextElement;
    private boolean hasNext;
    
    public FilterIterator(Iterator<T> source, Predicate<T> predicate) {
        this.source = source;
        this.predicate = predicate;
        advance();
    }
    
    private void advance() {
        hasNext = false;
        nextElement = null;
        while (source.hasNext()) {
            T candidate = source.next();
            if (predicate.test(candidate)) {
                nextElement = candidate;
                hasNext = true;
                break;
            }
        }
    }
    
    @Override
    public boolean hasNext() {
        return hasNext;
    }
    
    @Override
    public T next() {
        if (!hasNext) {
            throw new NoSuchElementException();
        }
        T result = nextElement;
        advance();
        return result;
    }
}

// 使用
List<Integer> numbers = Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
Iterator<Integer> evens = new FilterIterator<>(numbers.iterator(), n -> n % 2 == 0);
while (evens.hasNext()) {
    System.out.println(evens.next());  // 2, 4, 6, 8, 10
}
```

### 4.2 转换迭代器

在遍历过程中转换元素类型：

```java
public class TransformIterator<S, T> implements Iterator<T> {
    
    private Iterator<S> source;
    private Function<S, T> transformer;
    
    public TransformIterator(Iterator<S> source, Function<S, T> transformer) {
        this.source = source;
        this.transformer = transformer;
    }
    
    @Override
    public boolean hasNext() {
        return source.hasNext();
    }
    
    @Override
    public T next() {
        return transformer.apply(source.next());
    }
}

// 使用：将字符串列表转为整数长度
List<String> words = Arrays.asList("Java", "Python", "Go");
Iterator<Integer> lengths = new TransformIterator<>(words.iterator(), String::length);
while (lengths.hasNext()) {
    System.out.println(lengths.next());  // 4, 6, 2
}
```

### 4.3 限制迭代器

只遍历集合的一部分：

```java
public class LimitIterator<T> implements Iterator<T> {
    
    private Iterator<T> source;
    private int limit;
    private int count = 0;
    
    public LimitIterator(Iterator<T> source, int limit) {
        this.source = source;
        this.limit = limit;
    }
    
    @Override
    public boolean hasNext() {
        return count < limit && source.hasNext();
    }
    
    @Override
    public T next() {
        count++;
        return source.next();
    }
}

// 跳过前 N 个元素
public class SkipIterator<T> implements Iterator<T> {
    
    private Iterator<T> source;
    private int skip;
    private int count = 0;
    
    public SkipIterator(Iterator<T> source, int skip) {
        this.source = source;
        this.skip = skip;
        // 先跳过
        while (count < skip && source.hasNext()) {
            source.next();
            count++;
        }
    }
    
    @Override
    public boolean hasNext() {
        return source.hasNext();
    }
    
    @Override
    public T next() {
        return source.next();
    }
}
```

### 4.4 组合迭代器

将多个集合合并为一个序列：

```java
public class CompositeIterator<E> implements Iterator<E> {
    
    private List<Iterator<E>> iterators = new ArrayList<>();
    private int currentIndex = 0;
    
    public CompositeIterator(Iterator<E>... iterators) {
        for (Iterator<E> it : iterators) {
            this.iterators.add(it);
        }
    }
    
    @Override
    public boolean hasNext() {
        // 清理已耗尽的迭代器
        while (currentIndex < iterators.size()) {
            if (iterators.get(currentIndex).hasNext()) {
                return true;
            }
            currentIndex++;
        }
        return false;
    }
    
    @Override
    public E next() {
        if (!hasNext()) {
            throw new NoSuchElementException();
        }
        return iterators.get(currentIndex).next();
    }
}

// 使用
List<Integer> list1 = Arrays.asList(1, 2, 3);
List<Integer> list2 = Arrays.asList(4, 5, 6);
List<Integer> list3 = Arrays.asList(7, 8, 9);

CompositeIterator<Integer> composite = new CompositeIterator<>(
    list1.iterator(),
    list2.iterator(),
    list3.iterator()
);

while (composite.hasNext()) {
    System.out.print(composite.next() + " ");  // 1 2 3 4 5 6 7 8 9
}
```

## 五、实战案例

### 5.1 文件系统遍历

```java
// 文件节点
public abstract class FileNode {
    protected String name;
    
    public FileNode(String name) {
        this.name = name;
    }
    
    public abstract String getPath();
    public abstract Iterator<FileNode> createIterator();
}

public class File extends FileNode {
    private long size;
    
    public File(String name, long size) {
        super(name);
        this.size = size;
    }
    
    public long getSize() {
        return size;
    }
    
    @Override
    public String getPath() {
        return name;
    }
    
    @Override
    public Iterator<FileNode> createIterator() {
        // 文件没有子节点，返回空迭代器
        return Collections.emptyIterator();
    }
}

public class Directory extends FileNode {
    private List<FileNode> children = new ArrayList<>();
    
    public Directory(String name) {
        super(name);
    }
    
    public void add(FileNode node) {
        children.add(node);
    }
    
    @Override
    public String getPath() {
        return name;
    }
    
    @Override
    public Iterator<FileNode> createIterator() {
        return new FileIterator(this);
    }
    
    // 深度优先迭代器
    private class FileIterator implements Iterator<FileNode> {
        
        private Directory currentDir;
        private Iterator<FileNode> currentIterator;
        private Stack<Iterator<FileNode>> stack = new Stack<>();
        
        public FileIterator(Directory root) {
            this.currentDir = root;
            this.currentIterator = root.children.iterator();
        }
        
        @Override
        public boolean hasNext() {
            // 当前目录迭代器有元素
            if (currentIterator.hasNext()) {
                return true;
            }
            // 弹出父目录，继续
            while (!stack.isEmpty()) {
                currentIterator = stack.pop();
                if (currentIterator.hasNext()) {
                    return true;
                }
            }
            return false;
        }
        
        @Override
        public FileNode next() {
            if (!hasNext()) {
                throw new NoSuchElementException();
            }
            
            FileNode node = currentIterator.next();
            
            // 如果是目录，深入
            if (node instanceof Directory) {
                stack.push(currentIterator);        // 保存当前位置
                currentDir = (Directory) node;
                currentIterator = currentDir.children.iterator();
            }
            
            return node;
        }
    }
}

// 测试
Directory root = new Directory("project");
Directory src = new Directory("src");
src.add(new File("Main.java", 1024));
src.add(new File("Utils.java", 512));

Directory test = new Directory("test");
test.add(new File("MainTest.java", 256));

root.add(src);
root.add(test);
root.add(new File("README.md", 128));

System.out.println("=== 文件系统遍历 ===");
Iterator<FileNode> it = root.createIterator();
long totalSize = 0;
while (it.hasNext()) {
    FileNode node = it.next();
    System.out.println(node.getClass().getSimpleName() + ": " + node.name);
    if (node instanceof File) {
        totalSize += ((File) node).getSize();
    }
}
System.out.println("总大小: " + totalSize + " bytes");
```

### 5.2 社交网络好友遍历

```java
// 社交网络好友集合
public class SocialNetwork implements Iterable<User> {
    
    private Map<String, List<String>> friendships = new HashMap<>();
    
    public void addFriendship(String user, String friend) {
        friendships.computeIfAbsent(user, k -> new ArrayList<>()).add(friend);
        friendships.computeIfAbsent(friend, k -> new ArrayList<>()).add(user);
    }
    
    public List<String> getFriends(String user) {
        return friendships.getOrDefault(user, Collections.emptyList());
    }
    
    @Override
    public Iterator<User> iterator() {
        return new SocialNetworkIterator(this);
    }
    
    // 不同类型的迭代器
    public Iterator<User> friendsIterator(String user) {
        return new FriendsIterator(this, user);
    }
    
    public Iterator<User> friendsOfFriendsIterator(String user) {
        return new FriendsOfFriendsIterator(this, user);
    }
    
    public Iterator<User> mutualFriendsIterator(String user1, String user2) {
        return new MutualFriendsIterator(this, user1, user2);
    }
}

// 一度好友迭代器
class FriendsIterator implements Iterator<User> {
    
    private SocialNetwork network;
    private Iterator<String> friendIds;
    
    public FriendsIterator(SocialNetwork network, String userId) {
        this.network = network;
        this.friendIds = network.getFriends(userId).iterator();
    }
    
    @Override
    public boolean hasNext() {
        return friendIds.hasNext();
    }
    
    @Override
    public User next() {
        return new User(friendIds.next());
    }
}

// 二度好友（朋友的朋友）迭代器
class FriendsOfFriendsIterator implements Iterator<User> {
    
    private SocialNetwork network;
    private String userId;
    private Iterator<String> friendsOfCurrent;
    private Iterator<String> friends;
    private Set<String> visited = new HashSet<>();
    private User nextUser;
    
    public FriendsOfFriendsIterator(SocialNetwork network, String userId) {
        this.network = network;
        this.userId = userId;
        this.friends = network.getFriends(userId).iterator();
        this.visited.add(userId);
        advance();
    }
    
    private void advance() {
        nextUser = null;
        
        while (nextUser == null) {
            // 当前好友的迭代器有元素
            if (friendsOfCurrent != null && friendsOfCurrent.hasNext()) {
                String candidate = friendsOfCurrent.next();
                if (!visited.contains(candidate)) {
                    visited.add(candidate);
                    nextUser = new User(candidate);
                    return;
                }
            }
            
            // 获取下一个好友
            if (friends.hasNext()) {
                String friendId = friends.next();
                friendsOfCurrent = network.getFriends(friendId).iterator();
            } else {
                return;  // 没有更多了
            }
        }
    }
    
    @Override
    public boolean hasNext() {
        return nextUser != null;
    }
    
    @Override
    public User next() {
        if (nextUser == null) {
            throw new NoSuchElementException();
        }
        User result = nextUser;
        advance();
        return result;
    }
}

// 共同好友迭代器
class MutualFriendsIterator implements Iterator<User> {
    
    private Iterator<String> friends1;
    private Set<String> set2;
    private User nextUser;
    
    public MutualFriendsIterator(SocialNetwork network, String user1, String user2) {
        this.friends1 = network.getFriends(user1).iterator();
        this.set2 = new HashSet<>(network.getFriends(user2));
        advance();
    }
    
    private void advance() {
        nextUser = null;
        while (friends1.hasNext()) {
            String friendId = friends1.next();
            if (set2.contains(friendId)) {
                nextUser = new User(friendId);
                return;
            }
        }
    }
    
    @Override
    public boolean hasNext() {
        return nextUser != null;
    }
    
    @Override
    public User next() {
        if (nextUser == null) {
            throw new NoSuchElementException();
        }
        User result = nextUser;
        advance();
        return result;
    }
}

// User 类
public class User {
    private String id;
    
    public User(String id) {
        this.id = id;
    }
    
    public String getId() {
        return id;
    }
}

// 测试
SocialNetwork network = new SocialNetwork();
network.addFriendship("Alice", "Bob");
network.addFriendship("Alice", "Charlie");
network.addFriendship("Bob", "David");
network.addFriendship("Bob", "Eve");
network.addFriendship("Charlie", "Eve");

System.out.println("Alice 的一度好友:");
for (User friend : network.getFriends("Alice")) {
    System.out.println("  " + friend.getId());
}

System.out.println("\nAlice 的二度好友:");
Iterator<User> fof = network.friendsOfFriendsIterator("Alice");
while (fof.hasNext()) {
    System.out.println("  " + fof.next().getId());
}

System.out.println("\nBob 和 Charlie 的共同好友:");
Iterator<User> mutual = network.mutualFriendsIterator("Bob", "Charlie");
while (mutual.hasNext()) {
    System.out.println("  " + mutual.next().getId());
}
```

### 5.3 分页迭代器

```java
// 分页迭代器
public class PageIterator<T> implements Iterator<List<T>> {
    
    private Iterator<T> source;
    private int pageSize;
    
    public PageIterator(Iterator<T> source, int pageSize) {
        this.source = source;
        this.pageSize = pageSize;
    }
    
    @Override
    public boolean hasNext() {
        return source.hasNext();
    }
    
    @Override
    public List<T> next() {
        List<T> page = new ArrayList<>(pageSize);
        int count = 0;
        while (count < pageSize && source.hasNext()) {
            page.add(source.next());
            count++;
        }
        return page;
    }
}

// 使用
List<Integer> bigList = IntStream.range(1, 101)
    .boxed()
    .collect(Collectors.toList());

System.out.println("=== 分页遍历 ===");
PageIterator<Integer> pageIt = new PageIterator<>(bigList.iterator(), 10);
int pageNum = 1;
while (pageIt.hasNext()) {
    List<Integer> page = pageIt.next();
    System.out.println("第 " + pageNum++ + " 页: " + page);
}
```

## 六、迭代器模式 vs for 循环

### 6.1 何时使用迭代器

```java
// 简单场景：for 循环更直接
List<Integer> list = Arrays.asList(1, 2, 3);
for (int i = 0; i < list.size(); i++) {  // ✅ 简单清晰
    System.out.println(list.get(i));
}

// 需要抽象遍历逻辑时：迭代器更好
// 1. 集合被封装，不能直接访问下标
void printAll(Iterable<String> collection) {
    for (String item : collection) {  // ✅ 用迭代器
        System.out.println(item);
    }
}

// 2. 需要多种遍历策略
void printReverse(List<String> list) {
    ListIterator<String> it = list.listIterator(list.size());
    while (it.hasPrevious()) {  // ✅ 反向遍历
        System.out.println(it.previous());
    }
}

// 3. 遍历中需要删除元素
void removeEvens(List<Integer> list) {
    ListIterator<Integer> it = list.listIterator();
    while (it.hasNext()) {
        if (it.next() % 2 == 0) {
            it.remove();  // ✅ 安全删除
        }
    }
}

// 4. 延迟计算（懒加载）
Iterator<Integer> fibonacci() {
    return new Iterator<Integer>() {
        private int a = 0, b = 1;
        
        @Override
        public boolean hasNext() {
            return true;  // 无限序列
        }
        
        @Override
        public Integer next() {
            int next = a;
            a = b;
            b = a + next;
            return next;
        }
    };
}
```

### 6.2 性能对比

| 场景 | for 循环 | 迭代器 | 原因 |
|------|---------|--------|------|
| ArrayList 遍历 | ✅ 快（随机访问 O(1)） | ✅ 快 | RandomAccess 接口优化 |
| LinkedList 遍历 | ❌ 慢（O(n²)） | ✅ 快（O(n)） | 迭代器记录当前位置 |
| 需要删除元素 | ❌ 需额外处理 | ✅ 安全 | 迭代器自带 remove() |
| 遍历中修改 | ❌ 危险 | ❌ 并发修改异常 | fail-fast 机制 |

```java
// LinkedList 性能陷阱
List<String> list = new LinkedList<>();
// ❌ 错误的遍历方式
for (int i = 0; i < list.size(); i++) {
    // 每次 get(i) 都要从头遍历
    String s = list.get(i);  // O(n) 每次，总共 O(n²)
}

// ✅ 正确方式
for (String s : list) {
    // for-each 底层使用迭代器
}

// ✅ 显式迭代器
Iterator<String> it = list.iterator();
while (it.hasNext()) {
    String s = it.next();
}
```

## 七、源码中的应用

### 7.1 JDK 集合框架

```
Iterator hierarchy in JDK:
─────────────────────────────────────────────────────────────
Iterable<T>
  │
  ├── Collection<E>
  │     │
  │     ├── List<E>
  │     │     │
  │     │     ├── ArrayList ──→ Itr (implements Iterator)
  │     │     ├── LinkedList ──→ ListItr (implements ListIterator)
  │     │     ├── Vector ──────→ VectorItr / ListItr
  │     │     └── Stack
  │     │
  │     ├── Set<E>
  │     │     ├── HashSet ────→ HashIterator
  │     │     ├── TreeSet ────→ TreeMap.NavigableSubMap.Iterator
  │     │     └── LinkedHashSet → LinkedHashIterator
  │     │
  │     └── Queue<E>
  │           ├── LinkedList
  │           ├── PriorityQueue → Itr
  │           └── Deque
  │
  └── Map<K, V>
        ├── HashMap ─────────→ HashIterator (EntrySet/KeySet/ValueSet)
        ├── TreeMap ─────────→ NavigableSubMap.Iterator
        └── LinkedHashMap ──→ LinkedHashIterator
─────────────────────────────────────────────────────────────
```

### 7.2 MyBatis Cursor

```java
// MyBatis 的游标也是迭代器模式
public interface Cursor<T> extends Closeable, Iterable<T> {
    boolean isOpen();
    boolean isConsumed();
    int getCurrentIndex();
}

// 使用
try (Cursor<User> users = mapper.fetchUsersAsCursor()) {
    for (User user : users) {
        // 流式处理，大数据集不用一次性加载到内存
        process(user);
    }
}
```

### 7.3 Spring Data MongoDB

```java
// Spring Data MongoDB 的 Stream 也是迭代器
@Query
Stream<User> findAllByName(String name);

// 使用
try (Stream<User> stream = repository.findAllByName("Alice")) {
    stream.forEach(System.out::println);  // 懒加载流式处理
}
```

### 7.4 MyBatis-Plus 的 LambdaQueryIterator

```java
// MyBatis-Plus 提供了分页迭代器
IPage<User> page = new Page<>(1, 100);
while (true) {
    IPage<User> result = userMapper.selectPage(page, null);
    for (User user : result.getRecords()) {
        process(user);
    }
    if (!result.hasNext()) {
        break;
    }
    page = page.nextPage();
}
```

## 八、面试常见问题

### Q1：迭代器模式的优点是什么？

1. **单一职责原则**：集合只负责存储，遍历逻辑由迭代器负责
2. **开闭原则**：新增集合类型无需修改遍历代码
3. **封装遍历逻辑**：使用者不需要知道集合的内部结构
4. **支持多种遍历**：同一个集合可以有多种迭代器

### Q2：迭代器模式的缺点？

1. **增加类数量**：每个聚合需要对应的迭代器
2. **简单场景略显繁琐**：简单的 for 循环更直接
3. **迭代器开销**：对于 ArrayList，for 循环可能更快（随机访问）

### Q3：fail-fast 机制是什么？

```java
// ArrayList 的迭代器会检测并发修改
private class Itr implements Iterator<E> {
    int expectedModCount = modCount;  // 创建时记录修改次数
    
    final void checkForComodification() {
        if (modCount != expectedModCount) {
            throw new ConcurrentModificationException();
        }
    }
    
    @Override
    public E next() {
        checkForComodification();  // 每次 next 前检查
        // ...
    }
}

// ❌ 错误做法：迭代器遍历时修改集合
List<String> list = new ArrayList<>();
list.add("A");
Iterator<String> it = list.iterator();
list.add("B");  // 直接修改集合
it.next();      // 抛出 ConcurrentModificationException

// ✅ 正确做法：用迭代器删除
Iterator<String> it2 = list.iterator();
while (it2.hasNext()) {
    if ("A".equals(it2.next())) {
        it2.remove();  // 通过迭代器删除，安全
    }
}
```

### Q4：Iterator 和 Enumeration 的区别？

| 维度 | Iterator | Enumeration |
|------|---------|-------------|
| **出现版本** | JDK 1.2 | JDK 1.0 |
| **删除元素** | ✅ 支持 remove() | ❌ 不支持 |
| **命名** | 更短，更现代 | 较冗长 |
| **继承** | 没有子接口 | 没有子接口 |
| **使用场景** | 现代代码 | 遗留 API 兼容 |

### Q5：内部迭代器 vs 外部迭代器？

```java
// 外部迭代器：由调用方控制
Iterator<String> it = list.iterator();
while (it.hasNext()) {
    process(it.next());  // 调用方控制节奏
}

// 内部迭代器：由集合内部控制（Java 8+ forEach）
list.forEach(process);  // JVM 内部控制
// 或使用 Stream
list.stream().filter(x -> x > 0).forEach(process);
```

## 九、总结

### 核心要点

```
迭代器模式：
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Client ──→ Aggregate.createIterator() ──→ Iterator        │
│                   (创建)                      │             │
│                                             │ hasNext()     │
│                                             │ next()       │
│  Iterable<T> ←────────────── for-each 循环  │ remove()     │
│                                                             │
│  关键点：                                                    │
│  • 封装集合遍历逻辑                                          │
│  • 不暴露底层数据结构                                        │
│  • 支持多种遍历策略                                          │
│  • 支持惰性计算                                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 与其他模式对比

| 模式 | 目的 | 遍历支持 |
|------|------|---------|
| 迭代器模式 | 顺序访问元素 | ✅ |
| 组合模式 | 统一处理树形结构 | ✅（组合迭代器） |
| 工厂方法 | 创建对象 | ❌ |
| 备忘录 | 保存状态 | ❌ |

## 结语

迭代器模式在 Java 中应用极其广泛，从 JDK 集合框架到各种第三方库都能看到它的身影。掌握迭代器模式，不仅能写出更优雅的代码，更能深入理解 Java 集合框架的设计思想。

**下期预告**：组合模式（Composite Pattern）

> 记住：**迭代器让集合的遍历变得优雅而可控**。