---
title: "算法小练——Excel表列名称"
date: 2019-11-27T20:54:27+08:00
draft: false
categories: ['Algorithms']
tags: ['easy']
---

# [](#Excel表列名称)[Excel表列名称](https://leetcode-cn.com/problems/excel-sheet-column-title/)

### [](#描述)描述

给定一个正整数，返回它在 Excel 表中相对应的列名称。

例如，

```
1 -> A
2 -> B
3 -> C
...
26 -> Z
27 -> AA
28 -> AB 
...
```
### [](#举例)举例

  **示例 1:**

  输入: 1
  输出: “A”

  示例 2:

  输入: 28
  输出: “AB”

  **示例 3:**

  输入: 701
  输出: “ZY”

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
class Solution {
    public String convertToTitle(int n) {
        
		StringBuilder ans =new StringBuilder();
		while(n!=0) {
            n--;
            ans.append((char)('A'+n%26));
            n/=26;
		}
			return ans.reverse().toString();
    }
}

### [](#笔记)笔记

  这道题是一道进制转换题，那么首先要知道什么是进制转换
我们常见的进制 10 、 2进制
10进制 是 满10进1
2进制 是 满2进1
乍一看，以为这道题是满26进1，结果写出来以后发现不对。
**其实，这不是平常的进制转换**
要知道，寻常进制转换都是从0开始，而这里是从1开始。
1->26
 A-Z
‘A’+(0->25)
所以这个26进制 应该是 0-25，输入1应该得到 0 ，输入26得到25才对，
所以n要先减一
