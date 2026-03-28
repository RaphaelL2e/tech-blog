---
title: "GitHub快速学习(二)"
date: 2019-06-26T19:23:49+08:00
draft: false
categories: ['GitHub']
tags: ['github']
---

# [](#设置SSH-Key)设置SSH Key

### [](#一、创建秘钥)一、[创建秘钥](/秘钥链接.md)

### [](#二、在github中添加公开秘钥)二、在github中添加公开秘钥

```
账号设置内-> SSH & GPG keys -> 添加公钥
```
### [](#三、社区功能-Follow-关注其他用户)三、社区功能　Follow 关注其他用户

# [](#创建仓库)创建仓库

- **New repository**
repository name 仓库名

- description 仓库说明

- Public Or Private 仓库是否公开

- Initialize this repository with a README 自动初始化仓库并且设置README文件

- Add .gitignore 这个设定帮助我们把不需要在Git仓库中进行版本管理的文件记录在 .gitignore文件中

- Add a license 添加许可协议

- **Create repository** 完成仓库创建

## [](#README-md)README.md

一般添加本仓库中所包含的

- 软件的概要

- 使用流程

- 许可协议等

# [](#公开代码)公开代码

### [](#clone已有仓库)clone已有仓库

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
git clone https://github.com/leeyf888/MyNote.git

正克隆到 'MyNote'...
remote: Enumerating objects: 34, done.
remote: Counting objects: 100% (34/34), done.
remote: Compressing objects: 100% (28/28), done.
remote: Total 34 (delta 6), reused 0 (delta 0), pack-reused 0
接收对象中: 100% (34/34), 703.11 KiB | 95.00 KiB/s, 完成.
处理 delta 中: 100% (6/6), 完成.

cd MyNote

### [](#添加代码)添加代码

1
vim a.class

### [](#查看仓库状态)查看仓库状态

1
git status

### [](#提交)提交

1
2
3
4
5
git add a.class #将文件加入到暂存区
git commit -m "提交说明"
# 提交成功后可以
git log 
# 查看提交日志

### [](#Push)Push

1
git push #将本地代码更新到Github仓库
