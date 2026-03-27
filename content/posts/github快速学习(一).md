---
title: "GitHub快速学习(一)"
date: 2019-06-26T19:06:32+08:00
draft: false
categories: ['GitHub']
tags: ['github']
---

# [](#First-git-amp-amp-github-区别)First git && github 区别

Git 是代码仓库，存储在本地的。
GitHub 是**网络**上提供的一个Git仓库服务

#### [](#社会化编程)社会化编程

让所有人拥有修改源码的权利

## [](#GitHub功能)GitHub功能

- **Git仓库** 只有有网路就能访问的git仓库

- **ISSUE** 是将一个任务OR问题分配给一个Issue进行追踪与管理的功能
每个功能的修改与更正都对应一个Issue,只有查看Issue,就能知道与这个更改相关的一切信息

- **Wiki** 通过wiki每个人可以随时对一篇文章进行更改并保存，so可以多人协作完成一篇文章

- **Pull Request** 开发者向仓库推送更改或者添加功能后，可以通过其来请求合并到其仓库
```
- github提供了pull request 和源代码前后差别的讨论功能
```

# [](#Git-初始化设置)Git 初始化设置

1
2
3
# 首先，设置姓名跟邮箱
git config --global user.name "Your Name" 
git config --global user.email "Your_email@example.com"

#### [](#提高代码可读性)提高代码可读性

1
git config --global color.ui auto

这些config 会在 ~/.gitconfig 中形成输出文件

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝