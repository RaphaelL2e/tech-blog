---
title: "GitHub快速学习(三)"
date: 2019-06-27T14:34:28+08:00
draft: false
categories: ['GitHub']
tags: ['github']
---

# [](#常用指令学习)常用指令学习

- **git init** 初始化仓库

1
2
3
4
mkdir git-tutorial  #创建git文件夹
cd git-tutorial
git init #执行成功在该目录下生成 .git目录
初始化成～～～～～～

- **git status** 查看仓库状态

1
2
3
4
5
$ git status
位于分支 master
您的分支与上游分支 'origin/master' 一致。

无文件要提交，干净的工作区

- **git add** 向暂存区添加文件

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
$ git add a.class
$ git status 
位于分支 master
您的分支与上游分支 'origin/master' 一致。

未跟踪的文件:
  （使用 "git add <文件>..." 以包含要提交的内容）

	a.class

提交为空，但是存在尚未跟踪的文件（使用 "git add" 建立跟踪）

- **git commit** 保存仓库的历史记录

将暂存区的文件添加到仓库的历史记录中。

- 通过这些记录，我们可以在工作树中复原文件

- 记述一行提交信息

commit -m "First commit"```1
2
- 记述详细提交信息
``` git commit #不加 -m 执行后编辑器会启动

一般格式：

- 第一行:简述

- 第二行：空行

- 第三行之后：记录更改原因和详细内容

- 查看提交后状态

status```1
2
3
4
- **git log** 查看提交日志
	- 查看以往仓库中的提交日志
	- 只显示提交信息的第一行
	``` git log --prettt=short

- 只显示指定目录、文件的日志

log README.md```1
2
- 显示文件的改动
``` git log -p README.md

- **git diff** 查看更改前后的差别

- 查看工作树和最新提交的差别

git diff HEAD

  **养成好习惯：git commit 之前 git diff HEAD 查看本次提交与上次提交的差别，确认后再提交**
