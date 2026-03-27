---
title: "算法小练——x 的平方根"
date: 2019-11-11T20:50:44+08:00
draft: false
categories: ['Algorithms']
tags: ['easy']
---

# [](#x-的平方根)[ x 的平方根](https://leetcode-cn.com/problems/sqrtx/)

### [](#描述)描述

实现 int sqrt(int x) 函数。

计算并返回 x 的平方根，其中 x 是非负整数。

由于返回类型是整数，结果只保留整数的部分，小数部分将被舍去。

### [](#示例)示例

#### [](#示例-1)示例 1:

输入: 4
输出: 2

#### [](#示例-2)示例 2:

输入: 8
输出: 2

### [](#说明)说明

 8 的平方根是 2.82842…, 由于返回类型是整数，小数部分将被舍去。

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
/**
     * x 的平方根
     * https://leetcode-cn.com/problems/sqrtx/
     *
     * @param x
     * @return
     */
    public int mySqrt(int x) {
        for (long i = 0; i < 100000; i++) {
            if ((i - 1) * (i - 1) < x && (i + 1) * (i + 1) > x) {
                return (int) i;
            } else if (x == 0) {

                return 0;
            }
        }
        return 0;
    }

### [](#笔记)笔记

最简单的暴力法

### [](#代码优化)代码优化

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
public int mySqrt2(int x) {
        // 注意：针对特殊测试用例，例如 2147395599
        // 要把搜索的范围设置成长整型
        // 为了照顾到 0 把左边界设置为 0
        long left = 0;
        // # 为了照顾到 1 把右边界设置为 x // 2 + 1
        long right = x / 2 + 1;
        while (left < right) {
            // 注意：这里一定取右中位数，如果取左中位数，代码会进入死循环
            // long mid = left + (right - left + 1) / 2;
            long mid = (left + right + 1) >>> 1;
            long square = mid * mid;
            if (square > x) {
                right = mid - 1;
            } else {
                left = mid;
            }
        }
        // 因为一定存在，因此无需后处理
        return (int) left;

    }

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝