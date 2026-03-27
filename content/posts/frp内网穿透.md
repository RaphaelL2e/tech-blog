---
title: "frp内网穿透"
date: 2019-10-24T21:45:39+08:00
draft: false
categories: ['linux']
tags: ['linux']
---

## [](#安装)安装

下载最新版的frp

[github安装地址](https://github.com/fatedier/frp/releases)

## [](#内网配置-通俗讲本地)内网配置(通俗讲本地)

修改frp.ini文件

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
[common]
server_addr = 127.0.0.1  //服务器地址
server_port = 7000   //服务器端监听frps端口

[ssh]
type = tcp
local_ip = 127.0.0.1  //本地ip
local_port = 22  //本地端口
remote_port = 6000 // 转发端口
[common]

[web]
type = http
local_port =8081
custom_domains = www.yundingshuyuan.com

~

启动命令./frpc -c ./ frpc.ini

## [](#公网配置-通俗讲服务端)公网配置(通俗讲服务端)

修改frps.ini 

1
2
3
4
# frps.ini
[common]
bind_port = 7000  //内网frp监听地址
vhost_http_port = 8080  // 服务端访问地址

启动命令./frps -c ./ frps.ini

      
    
    
    
    

    
  	
    	 
    
        -------------本文结束**感谢阅读-------------
    

        
    
    
      
        
    
    欢迎您扫一扫上面的微信公众号，订阅我的博客！

      
    

    
      
        
  坚持原创技术分享，您的支持将鼓励我继续创作！
  
    打赏
  
  

    
      
        
        微信支付

      
    

    
      
        
        支付宝