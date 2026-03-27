---
title: "Mysqldump的使用——备份与恢复"
date: 2019-10-28T15:15:38+08:00
draft: false
categories: ['Linux']
tags: ['Mysql']
---

## [](#常用的使用指令)常用的使用指令

- 导出整个数据库(包括整个数据库中的数据)

mysqldump -u username -p **dbname** > dbname.sql   

- 导出数据库的结构（不含数据）

mysqldump -u username -p **-d** **dbname** > dbname.sql

- 导出数据库的某个表（包含数据）

mysqldump -u username -p **dbname tablename** > tablename.sql

- 导出数据库中的某张数据表的表结构（不含数据）

mysqldump -u username -p **-d dbname tablename** > tablename.sql

## [](#数据库的恢复（导入）)数据库的恢复（导入）

- mysqldump常用于数据库的备份与还原，在备份的过程中我们可以根据自己的实际情况添加以上任何参数，假设有数据库test_db，执行以下命令，即可完成对整个数据库的备份
mysqldump -u root -p test_db < test_db.sql   

- mysql> sourcetest_db.sql  

## [](#每日备份)每日备份

mysqldump结合crontab的使用

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
//创建存放备份sql文件的文件夹
mkdir ~/backup
//创建.sh文件
touch db_mysql.sh

#db_mysql.sh
mysqldump -uyunding -pPassword db_mysql > /root/backup/db_mysql$(date +%Y%m%d_%H%M%S).sql

//创建定时任务
crontab -e
0 1 * * * ~/backup/db_mysql.sh   #这个是每天1点执行备份指令的意思
：wq保存

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝