---
title: "第二章 Linux基础篇 linux入门"
date: 2019-08-05T15:16:47+08:00
draft: false
categories: ['Linux']
tags: ['linux']
---

# [](#第二章-Linux基础篇-linux入门)第二章 Linux基础篇 linux入门

## [](#2-1-Linux介绍)2.1 Linux介绍

- 一款操作系统，免费、开源、安全、高效、稳定、处理高并发强悍。

- 创始人：linus

- 吉祥物：企鹅 tux

- 主要发行版本： Ubuntu、centOS、Redhat、Suse、红旗Linux

- 主要操作系统：windows、linux、Ios等

## [](#2-2-Linux与Unix的关系)2.2 Linux与Unix的关系

# [](#第三章-Linux基础篇-VM和Linux系统安装)第三章 Linux基础篇 VM和Linux系统安装

qemu的安装和使用

## [](#3-1qumu安装)3.1[qumu安装](https://wiki.qemu.org/Hosts/Linux)

## [](#3-2创建虚拟机并启动)3.2[创建虚拟机并启动](https://my.oschina.net/kelvinxupt/blog/265108)

sudo x86_64-softmmu/qemu-system-x86_64 -m 2048 -enable-kvm centos.img -cdrom ./linux-iso/CentOS-7-x86_64-Minimal-1810.iso

# [](#第四章-Linux基础篇-Linux目录结构)第四章 Linux基础篇 Linux目录结构

## [](#4-１树状目录结构，在结构的最上层是根目录-，在次目录下创建其他目录)4.１树状目录结构，在结构的最上层是根目录　/，在次目录下创建其他目录

经典的话：**在Linux世界中，一切皆文件 **

## [](#4-2目录结构)4.2目录结构

**/bin** 常用指令

**/sbin** 超级管理员指令

**/home** 存放普通用户的目录

**/root** 系统管理员目录

**/lib** 动态库

 **/lost+found** 一般为空，系统非法关机后存放一些文件

**/etc** 配置文件和子目录

**/usr** 用户的应用程序和文件存放目录

**/boot** 启动linux的核心文件 

**/dev** 管理设备

**/media** 设备目录

**不要操作的 目录**

**/proc** 系统内存的映射

**/srv** 存放一些服务启动之后需要提取的数据

**/sys** 该目录安装了2.6内核中新出现的的一个文件系统

**/tmp** 存放临时文件

**/mnt** 让用户临时挂载别的系统

**/opt** 给主机额外安装软件所摆放的目录，默认为空

**/usr/local** 另一个主机额外安装软件所安装的目录

**/var** 存放不断扩充的东西，习惯将经常被修改的目录放这个目录下，日志等

## [](#4-3总结一下)4.3总结一下

- linux的目录只有一个根目录

- linux各个目录存放的内容是规划好的

- linux以文件的形式管理我们的设备的，因此linux一切皆文件

- linux各文件目录下存放内容，有一定认识

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝