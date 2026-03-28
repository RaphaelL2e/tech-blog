---
title: "算法小练——实现 strStr()"
date: 2019-11-07T19:39:48+08:00
draft: false
categories: ['Algorithms']
tags: ['easy']
---

# [](#实现-strStr)[实现 strStr()](https://leetcode-cn.com/problems/implement-strstr/)

### [](#描述)描述

给定一个 haystack 字符串和一个 needle 字符串，在 haystack 字符串中找出 needle 字符串出现的第一个位置 (从0开始)。如果不存在，则返回  -1。

### [](#示例)示例

#### [](#示例-1)示例 1:

输入: haystack = “hello”, needle = “ll”
输出: 2

#### [](#示例-2)示例 2:

输入: haystack = “aaaaa”, needle = “bba”
输出: -1
说明:

当 needle 是空字符串时，我们应当返回什么值呢？这是一个在面试中很好的问题。

对于本题而言，当 needle 是空字符串时我们应当返回 0 。这与C语言的 strstr() 以及 Java的 indexOf() 定义相符。

### [](#代码)代码

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
25
26
27
/**
     * 实现strstr()
     * https://leetcode-cn.com/problems/implement-strstr/
     * @param haystack 字符串
     * @param needle 字符串
     * @return 找出 needle 字符串出现的第一个位置 (从0开始)。如果不存在，则返回  -1。
     */
    public int strStr(String haystack, String needle) {
        for (int i = 0; i < haystack.length()-needle.length()+1; i++) {
            int time = 0;
            for (int j = 0; j < needle.length(); j++) {
                if(needle.charAt(j)!=haystack.charAt(i+j)){
                    break;
                }
                time++;
            }
            if(time==needle.length()){
                return i;
            }

        }
        if(haystack.equals(needle)){
            return 0;
        }
        return -1;

    }

### [](#笔记)笔记

一如既往的暴力法。代码未优化

### [](#KPM)KPM
