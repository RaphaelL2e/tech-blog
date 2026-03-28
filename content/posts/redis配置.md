---
title: "redis配置"
date: 2020-01-11T20:03:57+08:00
draft: false
description: "Redis 安装配置完整指南，包括下载、解压、编译安装和基础配置。"
categories: ['linux']
tags: ['redis']
---

## [](#下载)下载

wget https://github.com/microsoftarchive/redis/archive/win-3.2.100.tar.gz

## [](#解压)解压

tar -zxvf win-3.2.100.tar.gz

cd   Redis-x64-3.2.100/

cd utlis

## [](#安装)安装

./install_server.sh

默认安装就一直回车就可以

*

## [](#配置redis)配置redis

vi  /etc/redis/6379.conf

requirepass password 设置新密码

修改bind 为 0.0.0.0则可以被外网所访问

## [](#设置开机启动)设置开机启动

 cp redis_init_script /etc/init.d/redisd

vi /etc/init.d/redisd

将路径修改 为之前自动安装的配置

## [](#启动)启动

service redisd start
