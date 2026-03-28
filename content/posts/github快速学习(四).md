---
title: "GitHub快速学习(四)"
date: 2019-06-27T14:37:47+08:00
draft: false
categories: ['GitHub']
tags: ['github']
---

# [](#分支操作)分支操作

## [](#一、分支)一、分支

- 一个仓库有一条主支master，还可以创建多条分支。各个分支互不干扰，独立开发。

- 开发完成后，分支合并

## [](#二、分支操作)二、分支操作

- branch``` 显示分支一览表1
2
3
4
 - 将分支名列出，同时可以确定当前分支（*分支 表示当前分支）
- ```git checkout -b``` 创建、切换分支
- ```git ckeckout -b feature-A``` 创建分支 feature-A 并切换到 feature-A
 - 相当于  ： ```git branch feature-A``` && ```git checkout feature-A

- checkout -``` 切换回上一个分支1
2
## 三、合并分支
-

 git checkout master
 git merge –no-ff feature-A
之后编辑器启动,录入合并提交信息

 1
2
3
4
5
6
### git log -- graph 以图表的形式查看分支

## 四、更改提交的操作
- ```git reset ``` 回溯历史版本
	- ```git reset --hard ```要让仓库的HEAD、暂存区、当前工作树回溯到指定状态
	-  只要提供目标时间点的哈希值

 $ git reset –hard 1283490a918add4baaee2fcd3ab9c28ebade31fd

   HEAD 现在位于 1283490 add line

 1
2
3
4
5
6
7
8
- ```git reflog ``` 查看当前仓库执行过的操作日志
## 五、冲突
两个分支的内容并存于文件中，往往需要删除其中之一。处理冲突时，要务必**仔细分析**冲突的内容后再进行修改。
**冲突解决后，执行git add && git commit 命令**

- ```git commit --amend ``` 修改提交信息
- ```git rebase -i ``` 压缩历史  
	- **当已提交的内容有些许拼写错误，不妨提交一个修改，然后将这个修改包含到之前的提交中，压缩成一个历史记录。**

git rebase -i HEAD~2
pick 1283490 add line
-pick 86d9019 ADD feature-C
+fixup 86d9019 ADD feature-C

#保存，Successfully rebased and updated refs/heads/feature-C.
```

## [](#六、推送到远程仓库)六、推送到远程仓库

- git remote add 添加远程仓库

- git push -u origin master 推送至master分支
-u 在推送的同时，将origin仓库的master分支设置为本地仓库当前分支的upstream(上游),添加这个参数，将来git pulld从远程仓库获取内容时，直接从origin的master分支获取内容，不需要另外添加参数。

- ***推送至master以外的其他分支***
git checkout -b feature-D本地仓库，创建新分支

- git push -u origin feature-D推送至远程仓库，保持分支名不变## [](#七、从远程仓库获取)七、从远程仓库获取

- git clone获取远程仓库，默认本地处于master分支下

- git branch -a 同时查看本地和远程仓库的分支

- **获取远程的feature-D分支**
git checkout -b feature-D origin/feature-D将feature-D分支获取至本地仓库

- git pull 获取最新的远程仓库分支
git pull origin feature-D 获取feature-D分支

  **如果两人同时修改一个部分的代码，为减少不必要的冲突，应多使用push && pull操作**
推荐学习网站：[web学习git操作](http://try.github.io)
