---
title: "算法小练——杨辉三角 II"
date: 2019-11-14T18:39:08+08:00
draft: false
categories: ['Algorithms']
tags: ['easy']
---

# [](#杨辉三角-II)[杨辉三角 II](https://leetcode-cn.com/problems/pascals-triangle-ii/)

### [](#描述)描述

给定一个非负索引 *k*，其中 *k* ≤ 33，返回杨辉三角的第 *k* 行。

*

在杨辉三角中，每个数是它左上方和右上方的数的和。

### [](#示例)**示例:**

1
2
输入: 3
输出: [1,3,3,1]

### [](#进阶：)**进阶：**

你可以优化你的算法到 *O*(*k*) 空间复杂度吗？

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
class Solution {
    public List<Integer> getRow(int rowIndex) {
       
        List<Integer> ans = new ArrayList<>();
        if(rowIndex==0){
            ans.add(1);
            return ans;
        }
        if(rowIndex>=1){
            int time =rowIndex;
            List<Integer> alist =getRow(--rowIndex);
            List<Integer> blist = new ArrayList<>();
            blist.add(1);
            for (int i = 1; i < time; i++) {
                blist.add(alist.get(i-1)+alist.get(i));
            }
            blist.add(1);
            return blist;
        }else {
            return ans;
        }
    }
}

### [](#笔记)笔记

递归算法，实现的
