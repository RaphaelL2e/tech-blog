---
title: "Oralce创建与操作"
date: 2020-01-01T15:54:18+08:00
draft: false
categories: ['Oracle']
---

# [](#创建新用户)创建新用户

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
CREATE USER username
IDENTIFIED BY password
[DEFAULT TABLESPACE tablespace]
[TEMPORARY TABLESPACE tablespace];

CREATE USER MARTIN
IDENTIFIED BY martinpwd
DEFAULT TABLESPACE USERS
TEMPORARY TABLESPACE TEMP;

如果账户被锁定，则需管理员给帐户解锁
sql> alter user martin  account unlock;

## [](#授予权限)授予权限

1
2
3
4
grant 权限/角色 to 用户

CONNECT角色允许用户连接至数据库，并创建数据库对象
GRANT CONNECT TO MARTIN;

## [](#更改用户)更改用户

1
ALTER USER MARTIN IDENTIFIED BY martinpass;

## [](#删除用户)删除用户

1
2
DROP USER MARTIN CASCADE; 
CASCADE 级联删除

# [](#SQL-Plus的连接命令)SQL*Plus的连接命令

## [](#conn-ect)conn[ect]

用法: conn 用户名/密码@网络服务名 [as sysdba/sysoper]
当用特权用户身份连接时，必须带上 as sysdba 或是 as sysoper

## [](#disc-onnect)disc[onnect]

说明:该命令用来断开与当前数据库的连接，但不退出sql*plus环境

## [](#exit或者quit命令)exit或者quit命令

说明：该命令会断开与数据库的连接，同时会退出sql*plus

## [](#基础命令)基础命令

*

## [](#其他命令)其他命令

（1 ）help命令：可以得到联机的命令帮助信息

（2） desc[ribe]命令：一是列出表的结构，二是列出相关函数、过程以及包的信息

（3）显示当前连接用户：SQL>SHOW USER

（4）显示所有：SQL> SHOW ALL

（5）设置一行可以容纳的字符数  SQL> SET LINESIZE 200;

（6）设置一页可以容纳的行数
      SQL> SET PAGESIZE 40;

# [](#创建表)创建表

1
2
3
4
5
6
7
8
9
CREATE TABLE语句，基本的语法格式为：
CREATE TABLE [<用户方案名>.] <表名>
(
	<列名1>  <数据类型>  [DEFAULT <默认值>]  [<列约束>]	
	<列名2>  <数据类型>  [DEFAULT <默认值>]  [<列约束>]	
[,…n]
	<表约束>[,…n]
)
	[AS <子查询>]

## [](#修改表)修改表

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
ALTER TABLE [<用户方案名>.] <表名>
	[ ADD(<新列名> <数据类型> [DEFAULT <默认值>][列约束],…n) ]		/*增加新列*/
	[ MODIFY([ <列名> [<数据类型>] [DEFAULT <默认值>][列约束],…n) ] 	/*修改已有列属性*/
	[<DROP子句> ]	/*删除列或约束条件*/
            
             
    DROP {
	COLUMN <列名>
	∣PRIMARY [KEY]
	∣UNIQUE (<列名>,…n) 
	∣CONSTRAINT <约束名>
	∣[ CASCADE ]
}

## [](#删除表)删除表

1
DROP TABLE [<用户方案名>.] <表名>
