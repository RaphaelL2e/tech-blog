---
title: "算法小练——二叉树的层次遍历II"
date: 2019-11-24T19:59:03+08:00
draft: false
categories: ['Algorithms']
tags: ['easy']
---

# [](#二叉树的层次遍历-II)[二叉树的层次遍历 II](https://leetcode-cn.com/problems/binary-tree-level-order-traversal-ii/)

### [](#描述)描述

给定一个二叉树，返回其节点值自底向上的层次遍历。 （即按从叶子节点所在层到根节点所在的层，逐层从左向右遍历）

### [](#示例)示例

例如：
给定二叉树 [3,9,20,null,null,15,7],

```
    3 
    / \
  9  20
       /  \
     15   7
返回其自底向上的层次遍历为：
```

  [
    [15,7],
    [9,20],
    [3]
  ]

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
28
29
30
31
/**
 * Definition for a binary tree node.
 * public class TreeNode {
 *     int val;
 *     TreeNode left;
 *     TreeNode right;
 *     TreeNode(int x) { val = x; }
 * }
 */
class Solution {
   List<List<Integer>> lists1 = new ArrayList<>();
	public List<List<Integer>> levelOrderBottom(TreeNode root) {
		if(root==null){
			return lists1;
		}
		helper2(root,0,lists1);
		return lists1;
	}
	public void helper2(TreeNode treeNode,int level,List<List<Integer>> lists) {
		if(lists1.size()==level){
			lists1.add(0,new ArrayList<>());
		}
		lists1.get(lists.size()-1-level).add(treeNode.val);
		if(treeNode.left!=null){
			helper2(treeNode.left,level+1,lists1);
		}
		if(treeNode.right!=null){
			helper2(treeNode.right,level+1,lists1);
		}
	}
}

### [](#笔记)笔记

[二叉树的层次遍历](https://leetcode-cn.com/problems/binary-tree-level-order-traversal/)

   参考这个，总的来说还是BFS，只是存的时候反着存。

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝