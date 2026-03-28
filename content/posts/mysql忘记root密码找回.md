---
title: "Mysql忘记root密码找回"
date: 2019-10-28T14:43:26+08:00
draft: false
categories: ['Linux']
tags: ['mysql']
---

# [](#忘记密码怎么办？)忘记密码怎么办？

1.kip-grant-tables 指令

数据库登录时跳过权限库，不用验证密码直接登录

在/etc/my.cnf文件中

【mysqld】下面加上上面指令

就跳过密码登录

然后重启mysql服务

2.登录之后，使用指令更改root密码

- use mysql；

- mysql 5.7之前使用 

update user set password=PASSWORD('newPassword') where user = 'root';

- mysql 5.7之后

update mysql.user set authentication_string=password('newPassword') where user='root' 

以上都不行，则使用以下指令来改密：

1
ALTER USER ``'root'``@``'localhost'``IDENTIFIED BY ``'********';

最后刷新权限

1
flush privileges;

去掉/etc/my.cnf中的跳过权限的指令
