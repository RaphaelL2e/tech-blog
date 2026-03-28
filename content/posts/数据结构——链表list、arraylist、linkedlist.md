---
title: "数据结构——链表List、ArrayList、LinkedList"
date: 2019-11-16T10:42:41+08:00
draft: false
categories: ['数据结构']
tags: ['数据结构', '链表']
---

# [](#抽象数据类型ADT)抽象数据类型ADT

- 是带有一组操作的一些对象的集合

## [](#一种特别的抽象类型——表ADT)一种特别的抽象类型——表ADT

什么是一个表呢？

最简单的一个整数表 -> 由一群整数构成的一个数组，可以看做是一张表

1
2
3
4
5
6
7
8
9
//表的简单数组实现
int[] arr = new int[10];
...
//对一个表的扩容
int[] newArr = new int[arr.length*2];
for(int i=0;i<arr.length;i++){
    newArr[i] = arr[i];
}
arr =newArr;

数组的实现是线性执行的，对其中的查找操作也是常数时间，但是插入和删除却潜藏着昂贵的开销。两种情况最坏的情况都是O(N)

## [](#简单链表)简单链表

于是为了避免插入和删除的开销就有了，链表的出现。链表是由一个个节点组成的，并且不限制需要存储在一段连续的内存中。

### [](#节点)节点

每一个节点均含有一个表元素、一个包含了后继节点的链Link。

1
2
3
4
5
//链表节点
LinkNode class{
    Object var;
    LinkNode next;
}

对于链表中节点的删除与插入，只需要常数时间。

首先找到要删除的节点位置或者要插入的节点位置

删除 该节点的前一个节点，指向该节点的后继节点就可以了

插入 找到插入节点的前一个节点，将前一个节点的后继节点用该节点指向，将前一个节点指向该节点

#### [](#双链表)双链表

对于单链表的不足之处在于，对尾节点的删除，需要先找到最后节点的项，把他改为next链改为null，然后再更新持有最后节点的链。但是在经典链表中，每个节点均存储的是下一个节点，并不提供最后一个节点的前驱节点的任何信息。

==单链表的删除需要靠辅助节点，而双向链表则可以直接删除==

对于此，就想到了双向链表，让每一个节点持有一个指向它在表中的前驱节点的链。

## [](#JAVA中-Collections-API中的表)JAVA中 Collections API中的表

集合的概念在java中用Collection接口来抽象，它存储一组类型相同的对象

1
2
3
4
5
6
7
8
9
//源码参考
public interface Collection<E> extends Iterable<E> {
 	int size();
     boolean isEmpty();
    boolean contains(Object o);
    Iterator<E> iterator(); //该方法继承于Iterable接口内的Iterator方法
    boolean add(E e);
    boolean remove(Object o);
}

Collection接口对Iterator接口进行了扩展，实现Iterator接口中那些类拥有增强的for循环。

1
2
3
4
5
6
7
8
9
10
11
12
13
//Iterator接口
public interface Iterator<E> {
    boolean hasNext(); 
    E next();
    default void remove() {
        throw new UnsupportedOperationException("remove");
    }
    default void forEachRemaining(Consumer<? super E> action) {
        Objects.requireNonNull(action);
        while (hasNext())
            action.accept(next());
    }
}

## [](#List接口、ArrayList类、LinkedList类)List接口、ArrayList类、LinkedList类

### [](#List接口-既是表的抽象，他继承了Collection)List接口 既是表的抽象，他继承了Collection

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
public interface List<E> extends Collection<E> {
     int size();
    boolean isEmpty();
    boolean contains(Object o);
    Iterator<E> iterator(); 
    Object[] toArray();

    
    E get(int index);
    E set(int index, E element);
    void add(int index, E element);
    E remove(int index);
    
    / ** 
        *从列表中的指定位置开始，以正确的
        *顺序返回列表中元素的列表迭代器。
        *指定的索引表示首次调用{@link ListIterator＃next next}将返回的第一个元素。 
        *初次调用{@link ListIterator＃previous previous}将
        *返回具有指定索引减一的元素。 
        * * @param index从列表迭代器返回的第一个元素的索引（通过调用{@link ListIterator＃next next}）
        * @在此列表中的元素上返回列表迭代器（按适当的顺序） ，从列表中的指定位置开始
        * @throws IndexOutOfBoundsException如果索引超出范围
        *（{@code index <0 || index> size（）}）* /
    ListIterator<E> listIterator(int index);

### [](#ArrayList和LinkedList是对List的两种实现)ArrayList和LinkedList是对List的两种实现

#### [](#ArrayList-单链表)ArrayList 单链表

- 是一种可增长的数组实现

- 优点在于，对get和set的调用花费常数时间

- 缺点是add和remove的代价昂贵

[](#实现)实现1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
57
58
59
60
61
62
63
64
65
66
67
68
69
70
71
72
73
74
75
76
77
78
79
80
81
82
83
84
85
86
87
88
89
90
91
92
93
94
95
96
97
98
99
100
101
102
103
104
105
106
107
108
109
110
111
112
113
114
115
116
117
118
119
120
121
122
123
package com.leeyf.myarraylist;

import java.util.Iterator;

public abstract class MyArrayList<T> implements Iterable<T> {
    //初始化容器容量
    private static final int DEFAULT_CAPACITY = 10;
    //当前项数
    private int theSize;
    //基础数组
    private T[] theItems;

    public MyArrayList() {
        doClear();
    }

    //清空链表
    public void clear() {
        doClear();
    }

    private void doClear() {
        theSize = 0;
        ensureCapacity(DEFAULT_CAPACITY);
    }

    //返回当前项数
    public int size() {
        return theSize;
    }

    public boolean isEmpty() {
        return theSize == 0;
    }

    //缩减容器大小
    public void trimToSize() {
        ensureCapacity(size());
    }

    public T get(int index) {
        if (index < 0 || index >= size()) {
            throw new ArrayIndexOutOfBoundsException();
        }
        return theItems[index];
    }

    public T set(int index, T newVal) {
        if (index < 0 || index >= size()) {
            throw new ArrayIndexOutOfBoundsException();
        }
        T old = theItems[index];
        theItems[index] = newVal;
        return old;
    }

    public void ensureCapacity(int newCapacity) {
        //如果新设置的大小比当前容器大小小，则不执行
        if (newCapacity < size()) {
            return;
        }

        T[] old = theItems;
        theItems = (T[]) new Object[newCapacity]; //泛型数组的创建是非法的.这里创建一个泛型类型界限的数组,然后使用一个数组进行类型转换来实现.
        for (int i = 0; i < size(); i++) {
            theItems[i] = old[i];
        }
    }

    public boolean add(T x) {

        add(size(), x);
        return true;
    }

    public void add(int index, T x) {
        //如果链表已满,则扩容
        if (theItems.length == size()) {
            ensureCapacity(size() * 2 + 1);
        }
        //从最后一项开始到index，后移一位
        for (int i = theSize; i > index; i--) {
            theItems[i] = theItems[i - 1];
        }
        theItems[index] = x;
        theSize++;
    }

    public T remove(int index) {
        T removeItem = theItems[index];
        //从index到最后一项，前移一位
        for (int i = index; i < size() - 1; i++) {
            theItems[i] = theItems[i + 1];
        }
        theSize--;
        return removeItem;
    }

    public java.util.Iterator<T> iterator() {
        return new ArrayListIterator();
    }

    private class ArrayListIterator implements java.util.Iterator<T> {
        private int current = 0;

        public boolean hasNext() {
            return current < size();
        }

        public T next() {
            if (!hasNext()) {
                throw new java.util.NoSuchElementException();
            }
            return theItems[current++];
        }

        public void remove() {
            MyArrayList.this.remove(--current);
        }
    }

}

[](#分析)分析
- **ensureCapacity**是对容器大小的调整,既可以用来容器扩容,也可做收缩基础数组,只不过当指定容器至少和原大小一样时才适用.

- 第64行中,因为**泛型数组**的创建是非法的,所以我们用一个数组来类型转换

- 两个**add**方法,第一个add是添加到表的末端的并通过调用来添加到指定位置的.第二个则是添加到指定位置.

- **remove**与**add**相似,只是在指定位置后的元素,前移一位.

- **ArrayListIterator**内部类则是对Iterator接口的实现类.**ArrayListIterator**存储当前位置的概念,并提供了**hasNext**,**next**和**remove**的实现.

当前位置表示要被查看的下一元素的数组下标,所以初始值为0\

[](#迭代器、JAVA嵌套类和内部类)迭代器、JAVA嵌套类和内部类ArrayListIterator作为一个**内部类**是如何工作的

未完待续。。。

#### [](#LinkedList-双链表)LinkedList 双链表

- 是一种双链表的实现

- 优点在于，add和remove的开销小

- 并且提供了addFirst、removeFirst、addLast、removeLast、getFirst、getLast等方法

- 缺点则是他不容易进行索引，对get的调用则是昂贵的

### [](#关于ListIterator接口)关于ListIterator接口

1
2
3
4
5
6
public interface ListIterator<E> extends Iterator<E>{
    boolen hasPrevious();
    E previous();
    void add(E x);
    void set(E newVal);
}

- ListIterator是对List的Iterator的一个扩展。

- 方法previous和hasPrevious对应着next与hasNext，对表从后 向前的遍历。

- add方法将一个新的项以当前位置放入表中。当前项则是对next和previous的返回值的一个抽象表述

- set改变被迭代器看到的最后一个值。

- 对于LinkedList来说，add方法是常数操作，但是ArrayList的代价昂贵。

未完待续。。。
