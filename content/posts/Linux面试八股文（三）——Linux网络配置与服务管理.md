---
title: Linux面试八股文（三）——Linux网络配置与服务管理
date: 2026-06-13 11:00:00+08:00
updated: '2026-06-13T11:00:00+08:00'
description: 本篇聚焦Linux网络配置与服务管理，涵盖网络配置命令、防火墙规则（iptables/firewalld）、systemd服务管理、系统服务监控与故障排查，是运维工程师和后端开发者的必备技能。 Q：Linux网络配置文件在哪里？常用配置项有哪些？
  Q：ip命令和ifconfig命令有什么区别？ Q：。
topic: computer-science
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Linux
- 网络配置
- 防火墙
categories:
- 计算机基础
draft: false
---

> 本篇聚焦Linux网络配置与服务管理，涵盖网络配置命令、防火墙规则（iptables/firewalld）、systemd服务管理、系统服务监控与故障排查，是运维工程师和后端开发者的必备技能。

---

## 一、Linux网络基础

### 1.1 网络配置文件

**Q：Linux网络配置文件在哪里？常用配置项有哪些？**

```bash
# Debian/Ubuntu
/etc/network/interfaces
/etc/netplan/*.yaml          # Ubuntu 18.04+

# RedHat/CentOS/RHEL
/etc/sysconfig/network-scripts/ifcfg-eth0
/etc/NetworkManager/system-connections/

# 通用DNS配置
/etc/resolv.conf

# 主机名配置
/etc/hostname
/etc/hosts

# 查看当前网络配置
ip addr show
ip route show
ip link show

# 查看网络接口状态
ethtool eth0                  # 查看网卡详细信息
mii-tool eth0                # 查看链路状态
```

```bash
# /etc/network/interfaces 示例 (Debian)
auto eth0
iface eth0 inet static
    address 192.168.1.100
    netmask 255.255.255.0
    gateway 192.168.1.1
    dns-nameservers 8.8.8.8 114.114.114.114
    dns-search example.com

# /etc/sysconfig/network-scripts/ifcfg-eth0 示例 (CentOS)
TYPE=Ethernet
BOOTPROTO=static
NAME=eth0
DEVICE=eth0
ONBOOT=yes
IPADDR=192.168.1.100
NETMASK=255.255.255.0
GATEWAY=192.168.1.1
DNS1=8.8.8.8
DNS2=114.114.114.114
```

### 1.2 ip命令详解

**Q：ip命令和ifconfig命令有什么区别？**

| 特性 | ip | ifconfig |
|------|-----|----------|
| 归属 | iproute2工具集 | net-tools工具集 |
| 维护状态 | 活跃维护 | 已废弃 |
| 功能范围 | 网络、路由、链路、VLAN等 | 主要网络接口配置 |
| 语法 | ip [选项] 对象 操作 | ifconfig [接口] [选项] |

```bash
# 1. 查看接口
ip link show                    # 所有接口（简洁）
ip addr show                   # 所有接口及IP地址
ip addr show eth0              # 指定接口

# 2. 启用/禁用接口
ip link set eth0 up            # 启用
ip link set eth0 down          # 禁用

# 3. 配置IP
ip addr add 192.168.1.100/24 dev eth0      # 添加IP
ip addr del 192.168.1.100/24 dev eth0     # 删除IP

# 4. 查看路由表
ip route show                  # 简写
ip route list
ip route                       # 等价

# 5. 添加路由
ip route add default via 192.168.1.1       # 添加默认路由
ip route add 10.0.0.0/8 via 192.168.1.1   # 添加静态路由
ip route del 10.0.0.0/8                   # 删除路由

# 6. 查看邻居表（ARP缓存）
ip neigh show
ip neigh add 192.168.1.1 lladdr aa:bb:cc:dd:ee:ff dev eth0  # 静态ARP
ip neigh del 192.168.1.1 dev eth0                       # 删除ARP

# 7. VLAN配置
ip link add link eth0 name eth0.100 type vlan id 100
ip addr add 192.168.100.1/24 dev eth0.100
```

### 1.3 网络诊断命令

**Q：有哪些常用的网络诊断命令？**

```bash
# 1. ping - 测试连通性
ping -c 4 8.8.8.8              # 发送4个包
ping -i 0.5 8.8.8.8            # 0.5秒间隔
ping -s 1000 8.8.8.8           # 指定数据包大小
ping -f 8.8.8.8                # flood模式（需root）

# 2. traceroute - 路由追踪
traceroute 8.8.8.8             # UDP追踪
traceroute -I 8.8.8.8          # ICMP追踪
traceroute -T 8.8.8.8          # TCP追踪（穿透防火墙）
traceroute -n 8.8.8.8          # 不解析域名

# 3. mtr - traceroute + ping
mtr 8.8.8.8
mtr -r 8.8.8.8                 # 报告模式
mtr -c 20 8.8.8.8              # 发送20个包后退出

# 4. netstat/ss - 查看网络连接
netstat -tulnp                 # TCP监听端口
netstat -anp                   # 所有连接
netstat -r                      # 路由表
netstat -i                      # 接口统计

ss -tulnp                      # 更快速的ss（socket statistics）
ss -s                           # 统计摘要
ss -dst sport = :80            # 过滤特定连接

# 5. nc/netcat - 网络瑞士军刀
nc -zv 192.168.1.1 22          # 端口扫描
nc -l 8080                     # 监听端口
nc 192.168.1.1 8080            # 客户端连接
nc -zv 8.8.8.8 80 443          # 测试多端口

# 6. curl/wget - HTTP测试
curl -v http://example.com      # 详细输出
curl -X POST -d "data=xxx" http://api.example.com
curl -H "Authorization: Bearer xxx" http://api.example.com
curl -I http://example.com     # 只查HEAD

wget http://example.com/file.tar.gz
wget -O - http://example.com   # 输出到标准输出

# 7. nslookup/dig - DNS查询
nslookup example.com
dig example.com A
dig @8.8.8.8 example.com MX    # 指定DNS服务器查MX记录
dig +trace example.com         # 完整追踪

# 8. host - 简单DNS查询
host example.com
host -a example.com            # 详细输出
```

---

## 二、防火墙配置

### 2.1 iptables基础

**Q：iptables的四表五链是什么？数据包处理流程是怎样的？**

**四表（按处理优先级）：**
| 表 | 用途 | 主要链 |
|----|------|--------|
| filter | 过滤数据包 | INPUT, OUTPUT, FORWARD |
| nat | 网络地址转换 | PREROUTING, INPUT, OUTPUT, POSTROUTING |
| mangle | 修改数据包 | 所有链 |
| raw | 跟踪连接 | PREROUTING, OUTPUT |

**五链（数据包流向）：**
```
进入本机: PREROUTING → INPUT → 本机进程
从本机发出: 本机进程 → OUTPUT → POSTROUTING
经本机转发: PREROUTING → FORWARD → POSTROUTING
```

```bash
# 基本语法
iptables [-t 表] -[ACD] 链 规则规格 [选项]
iptables [-t 表] -L [链] [选项]

# 查看规则
iptables -L -n -v               # 详细显示
iptables -L INPUT -n --line-numbers   # 带行号
iptables -t nat -L -n -v        # NAT表

# 常用操作
# 1. 清空规则
iptables -F                     # 清空filter表
iptables -X                     # 删除用户自定义链
iptables -Z                     # 计数器归零
iptables -t nat -F              # 清空NAT表

# 2. 默认策略
iptables -P INPUT DROP          # 默认拒绝
iptables -P FORWARD DROP        # 默认拒绝
iptables -P OUTPUT ACCEPT       # 默认允许

# 3. 允许/拒绝
iptables -A INPUT -s 192.168.1.0/24 -j ACCEPT    # 允许网段
iptables -A INPUT -p tcp --dport 22 -j ACCEPT    # 允许22端口
iptables -A INPUT -p tcp --dport 80 -j ACCEPT    # 允许80端口
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT  # 允许ping
iptables -A INPUT -j DROP                         # 拒绝其他

# 4. 常用匹配条件
-p tcp                           # 协议
--dport 80                       # 目标端口
--sport 1024:65535               # 源端口范围
-s 10.0.0.0/8                   # 源地址
-d 192.168.1.1                   # 目标地址
-i eth0                          # 入接口
-o eth1                          # 出接口
-m state --state ESTABLISHED,RELATED  # 连接状态
-m multiport --dports 80,443    # 多端口
-m comment --comment "注释"     # 添加注释

# 5. 连接状态
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -m state --state NEW -p tcp --dport 22 -j ACCEPT

# 6. 保存和恢复
iptables-save > /etc/iptables/rules.v4    # 保存
iptables-restore < /etc/iptables/rules.v4 # 恢复

# CentOS/RHEL
service iptables save          # 保存到 /etc/sysconfig/iptables

# Ubuntu/Debian
apt install iptables-persistent
netfilter-persistent save
```

### 2.2 iptables进阶

```bash
# 1. 端口转发
# 将80端口流量转发到8080
iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080

# 将外部访问转发到内网机器
iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to-destination 192.168.1.100:8080
iptables -t nat -A POSTROUTING -j MASQUERADE

# 2. IP限流/防暴力破解
iptables -A INPUT -p tcp --dport 22 -m state --state NEW \
    -m recent --set --name SSH --rsource
iptables -A INPUT -p tcp --dport 22 -m state --state NEW \
    -m recent --update --seconds 60 --hitcount 4 --name SSH --rsource -j DROP

# 3. 日志记录
iptables -A INPUT -j LOG --log-prefix "IPTables-DROP: " --log-level 4

# 4. 允许ping（区分请求和响应）
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT   # 允许ping请求
iptables -A OUTPUT -p icmp --icmp-type echo-reply -j ACCEPT     # 允许ping响应

# 5. 白名单模式
iptables -P INPUT DROP
iptables -A INPUT -s 10.0.0.0/8 -j ACCEPT     # 允许内网
iptables -A INPUT -s 192.168.0.0/16 -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT             # 允许本地回环
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 6. 端口映射到内网
# 从公网访问公网IP:8888 → 内网192.168.1.100:3389
iptables -t nat -A PREROUTING -p tcp --dport 8888 \
    -j DNAT --to-destination 192.168.1.100:3389
iptables -t nat -A POSTROUTING -j MASQUERADE
```

### 2.3 firewalld

**Q：firewalld和iptables有什么区别？**

| 特性 | iptables | firewalld |
|------|----------|-----------|
| 配置方式 | 规则文件/iptables命令 | zone + service |
| 生效方式 | 即时生效，修改立即生效 | 区域化配置 |
| 动态更新 | 需保存规则 | 支持运行时配置 |
| 默认拒绝 | 是 | 否 |
| 区域概念 | 无 | 有（public, home, dmz等） |

```bash
# 查看状态
firewall-cmd --state
firewall-cmd --list-all

# 区域管理
firewall-cmd --get-default-zone              # 默认区域
firewall-cmd --set-default-zone=public       # 设置默认区域
firewall-cmd --list-all-zones                # 列出所有区域

# 允许服务
firewall-cmd --add-service=http              # 临时允许HTTP
firewall-cmd --permanent --add-service=http  # 永久允许
firewall-cmd --add-service=https
firewall-cmd --add-service=ssh
firewall-cmd --add-service=mysql

# 允许端口
firewall-cmd --add-port=8080/tcp             # 临时
firewall-cmd --permanent --add-port=8080/tcp # 永久
firewall-cmd --permanent --add-port=5000-5100/tcp  # 端口范围

# 禁用服务/端口
firewall-cmd --remove-service=http
firewall-cmd --remove-port=8080/tcp

# 端口转发
firewall-cmd --add-masquerade                # 开启NAT伪装
firewall-cmd --permanent --add-forward-port=port=8888:proto=tcp:toaddr=192.168.1.100:toport=3389

# 富规则（Rich Rules）
firewall-cmd --add-rich-rule='rule family="ipv4" source address="192.168.1.0/24" service name="ssh" accept'
firewall-cmd --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port port="80" protocol="tcp" accept'

# 限制连接数
firewall-cmd --add-rich-rule='rule source limit value="10/s" accept'

# 重新加载配置
firewall-cmd --reload
firewall-cmd --complete-reload               # 完全重载（断开现有连接）

# 直接规则（类似iptables）
firewall-cmd --direct --add-rule ipv4 filter INPUT 0 -p tcp --dport 22 -j ACCEPT
```

### 2.4 nftables

**Q：nftables是什么？和iptables有什么区别？**

nftables是Linux新一代防火墙框架，替代iptables/netfilter。

```bash
# nftables vs iptables 区别
# 1. 语法更简洁
# 2. 同一规则可同时匹配IPv4/IPv6
# 3. 内置集合、字典、映射
# 4. 支持增量更新，无需重建规则
# 5. 更高效的规则查找

# 基本操作
nft list ruleset                    # 查看所有规则
nft add table ip filter            # 创建表
nft add chain ip filter input '{ type filter hook input priority 0; policy drop; }'
nft add rule ip filter input ct state established,related accept
nft add rule ip filter input tcp dport ssh accept
nft add rule ip filter input tcp dport {80, 443} accept

# 使用集合
nft add set ip filter blocked_ips '{ type ipv4_addr; flags interval; elements = { 1.2.3.4, 5.6.7.8 }; }'
nft add rule ip filter input ip saddr @blocked_ips drop

# iptables转换nftables
iptables-save > /tmp/rules.txt
nft -f /tmp/rules.txt
```

---

## 三、systemd服务管理

### 3.1 systemd基础

**Q：systemd是什么？为什么Linux要引入systemd？**

systemd是Linux系统和服务管理器，替代传统SysV init系统。

**解决的问题：**
- 串行启动 → 并行启动（加快开机速度）
- 脚本复杂 → 单元文件简洁
- 缺乏依赖管理 → 自动解决依赖
- 无资源控制 → cgroup资源隔离
- 缺乏日志管理 → journald统一日志

```bash
# systemd核心概念
# Unit（单元）- 系统管理的资源单位
# Unit File - 单元配置文件
# Target - 单元分组（类似运行级别）

# 查看systemd版本
systemd --version

# 查看单元类型
systemctl -t help
# Available unit types: service, socket, target, device, mount, 
#                        automount, swap, timer, path, slice, scope
```

### 3.2 服务管理命令

```bash
# 启动/停止/重启
systemctl start nginx              # 启动
systemctl stop nginx              # 停止
systemctl restart nginx           # 重启
systemctl reload nginx            # 重新加载配置（不中断服务）

# 查看状态
systemctl status nginx            # 详细状态
systemctl is-active nginx         # 是否运行（active/inactive）
systemctl is-enabled nginx        # 是否开机自启（enabled/disabled）

# 开机自启
systemctl enable nginx            # 启用
systemctl disable nginx           # 禁用
systemctl enable --now nginx      # 启用并立即启动
systemctl disable --now nginx     # 禁用并立即停止

# 查看所有单元
systemctl list-units --type=service
systemctl list-units --type=service --state=running
systemctl list-unit-files         # 查看所有单元文件
systemctl list-dependencies nginx # 查看依赖

# 强制终止
systemctl kill nginx              # 发送信号
systemctl kill -s SIGKILL nginx   # 发送SIGKILL

# 查看日志
journalctl -u nginx              # 查看nginx日志
journalctl -u nginx -f            # 实时跟踪
journalctl -u nginx --since "1 hour ago"
journalctl -u nginx -p err       # 错误级别以上
journalctl --disk-usage           # 日志占用空间
journalctl --vacuum-size=500M    # 清理旧日志
```

### 3.3 Unit文件详解

**Q：如何编写systemd服务单元文件？**

```bash
# Unit文件位置
/etc/systemd/system/              # 系统级（优先级最高）
/run/systemd/system/             # 运行时
/usr/lib/systemd/system/          # 软件包提供

# 服务单元文件示例
cat > /etc/systemd/system/myapp.service << 'EOF'
[Unit]
Description=My Application          # 描述
Documentation=https://example.com  # 文档链接
After=network.target mysql.service  # 依赖（网络和MySQL启动后）
Wants=network-online.target         # 弱依赖
Requires=mysql.service             # 强依赖

[Service]
Type=simple                        # 启动类型
User=appuser                       # 运行用户
Group=appgroup                     # 运行组
WorkingDirectory=/opt/myapp        # 工作目录
Environment="JAVA_HOME=/opt/java"  # 环境变量
EnvironmentFile=-/etc/sysconfig/myapp  # 环境变量文件（-表示可选）

ExecStart=/opt/myapp/bin/start.sh  # 启动命令（必须）
ExecStartPre=/opt/myapp/bin/check.sh  # 启动前执行
ExecStartPost=/opt/myapp/bin/notify.sh  # 启动后执行
ExecStop=/opt/myapp/bin/stop.sh    # 停止命令
ExecReload=/bin/kill -SIGUSR1 $MAINPID  # 重载信号

Restart=on-failure                 # 重启策略
RestartSec=5                       # 重启前等待秒数
TimeoutStartSec=30                # 启动超时
TimeoutStopSec=60                  # 停止超时

LimitNOFILE=65535                  # 文件描述符限制
LimitNPROC=4096                   # 进程数限制
MemoryMax=512M                     # 内存限制

StandardOutput=journal            # 输出重定向
StandardError=journal
SyslogIdentifier=myapp

[Install]
WantedBy=multi-user.target         # 哪个target下启用
EOF

# Type选项说明
# simple    - 主进程（默认）
# exec      - 类似simple，但exec后执行
# forking   - fork后父进程退出（如传统守护进程）
# oneshot   - 执行一次退出（如cloud-init）
# dbus      - 依赖D-Bus总线名称
# notify    - 启动完成发送sd_notify
# idle      - 等待所有任务完成

# Restart选项说明
# no        - 不重启
# always    - 总是重启
# on-success - 仅正常退出时重启
# on-failure - 仅异常退出时重启
# on-abnormal - 非正常退出（信号/超时）重启
```

### 3.4 定时任务（Timer）

```bash
# 定时器单元示例
cat > /etc/systemd/system/backup.timer << 'EOF'
[Unit]
Description=Backup Timer
Requires=backup.service

[Timer]
OnCalendar=*-*-* 02:00:00          # 每天02:00
OnBootSec=5min                    # 启动5分钟后
OnUnitActiveSec=1day              # 上次执行后1天

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/backup.service << 'EOF'
[Unit]
Description=Backup Service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/backup.sh
PrivateTmp=true
EOF

# 管理定时器
systemctl enable backup.timer
systemctl start backup.timer
systemctl list-timers
systemctl list-timers --all
```

---

## 四、系统监控与故障排查

### 4.1 进程监控

**Q：如何监控Linux系统进程？**

```bash
# 1. top - 实时进程监控
top                              # 默认视图
top -d 1                         # 每秒刷新
top -p 1234                      # 监控指定PID
top -u nginx                     # 指定用户进程
top -H                           # 显示线程
top -b -n 10 > /tmp/top.log     # 批处理模式输出

# top内部命令
# P - 按CPU排序
# M - 按内存排序
# N - 按PID排序
# T - 按时间排序
# k - 终止进程
# r - 重新设置优先级
# 1 - 显示所有CPU核心

# 2. htop - 更友好的top
htop
htop -u nginx                    # 过滤用户
htop --tree                      # 树形视图

# 3. glances - 全方位监控
glances                          # 默认
glances --percpu                 # 显示每核心
glances -t 2                     # 2秒刷新

# 4. 进程详情
ps aux                          # BSD风格
ps -ef                          # 标准风格
ps -ef --forest                # 树形显示进程关系
ps -eo pid,ppid,user,%cpu,%mem,cmd  # 自定义列
ps -eo pid,ppid,cmd --sort=-%cpu | head -20  # Top CPU

# 5. 进程树
pstree                          # 显示进程树
pstree -u nginx                # 某用户的进程树

# 6. 进程文件描述符
ls -l /proc/1234/fd            # 查看某进程fd
lsof -p 1234                   # 查看进程打开的文件
lsof -i :80                    # 查看端口占用
```

### 4.2 系统资源监控

```bash
# 1. CPU
top -bn1 | head -1             # CPU概述
vmstat 1 5                    # 每秒1次，共5次
mpstat -P ALL 1               # 每核心详细
sar -u 1 3                    # 系统活动报告

# 2. 内存
free -h                        # 人类可读格式
free -m                        # MB为单位
cat /proc/meminfo              # 详细内存信息
vmstat -s                      # 内存统计

# 3. 磁盘I/O
iostat -xz 1                   # 每秒I/O统计
iotop                          # 按进程I/O排序
iotop -b                       # 批处理
pidstat -d 1                  # 进程I/O统计

# 4. 网络带宽
iftop                          # 实时带宽（需安装）
nethogs                        # 按进程显示带宽
sar -n DEV 1 3                # 网络设备统计

# 5. 综合监控脚本
#!/bin/bash
echo "===== $(date) ====="
echo "--- CPU ---"
uptime
echo "--- Memory ---"
free -h
echo "--- Disk ---"
df -h | grep -v tmpfs
echo "--- Top 5 CPU ---"
ps -eo pid,user,%cpu,%mem,cmd --sort=-%cpu | head -6
```

### 4.3 网络连接监控

```bash
# 1. 查看连接状态
ss -tunapl                    # 所有TCP/UDP连接
ss -tunapl | grep ESTAB       # 只看已建立
ss -s                         # 统计摘要

# 2. 实时连接监控
watch -n 1 'ss -tunapl | grep ESTAB'

# 3. 端口监控
netstat -tulnp                # 监听端口
netstat -anp | grep :80       # 特定端口

# 4. 网络流量统计
cat /proc/net/dev             # 每个接口流量
iftop -i eth0                 # 实时流量

# 5. 连接数统计
ss -tan state established | wc -l   # ESTABLISHED连接数
ss -tan state listen | wc -l         # LISTEN连接数
ss -tan | awk '{print $1}' | sort | uniq -c  # 按状态分组

# 6. 高并发连接数优化
# /etc/security/limits.conf
* soft nofile 1000000
* hard nofile 1000000

# /etc/sysctl.conf
fs.file-max = 1000000
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
```

### 4.4 故障排查流程

```bash
# 1. 系统层面
uptime                          # 运行时间、负载
dmesg | tail                    # 内核日志
cat /var/log/messages | tail    # 系统日志
journalctl -xe                  # 最近的系统日志

# 2. 进程层面
ps auxf | head -50             # 进程快照
top -bn1                       # CPU/内存
pstree -p                      # 进程树
lsof -p <PID>                  # 进程打开的文件

# 3. 资源层面
df -h                          # 磁盘空间
free -m                        # 内存
cat /proc/loadavg             # 负载

# 4. 网络层面
ping 8.8.8.8                  # 基础连通性
telnet host 80                # 端口连通性
traceroute host               # 路由
netstat -an | grep ESTABLISHED | wc -l  # 并发连接数

# 5. 服务层面
systemctl status nginx        # 服务状态
systemctl restart nginx       # 重启服务
journalctl -u nginx -n 50     # 服务日志

# 6. 常用排查脚本
#!/bin/bash
echo "=== 系统概览 ==="
echo "时间: $(date)"
echo "运行时间: $(uptime -p)"
echo "负载: $(cat /proc/loadavg)"
echo "=== CPU & 内存 ==="
echo "CPU使用: $(top -bn1 | head -1)"
free -h
echo "=== 磁盘 ==="
df -h | grep -E "^/dev"
echo "=== TOP 10 进程 ==="
ps aux --sort=-%cpu | head -11
echo "=== 网络连接 ==="
echo "总连接数: $(ss -tunapl | wc -l)"
echo "ESTABLISHED: $(ss -tunapl | grep ESTAB | wc -l)"
echo "LISTEN: $(ss -tunapl | grep LISTEN | wc -l)"
echo "=== 服务状态 ==="
systemctl list-units --type=service --state=failed
```

### 4.5 systemd日志分析

```bash
# journalctl基础
journalctl                       # 全部日志
journalctl -n 50                 # 最近50行
journalctl -f                    # 实时跟踪
journalctl --since "2026-06-13 10:00:00"
journalctl --since "1 hour ago"
journalctl --since yesterday
journalctl --until "2026-06-13 12:00:00"

# 过滤
journalctl -u nginx             # 指定服务
journalctl -u nginx -u mysql     # 多个服务
journalctl -p err               # 错误级别
journalctl -p warning
journalctl -b                   # 本次启动日志
journalctl -b -1                # 上次启动
journalctl -k                   # 内核日志

# 日志级别
# 0: emerg (系统不可用)
# 1: alert (需立即处理)
# 2: crit (严重)
# 3: err (错误)
# 4: warning (警告)
# 5: notice (注意)
# 6: info (信息)
# 7: debug (调试)

# 高级过滤
journalctl _PID=1234            # 指定PID
journalctl _UID=1000           # 指定UID
journalctl _SYSTEMD_UNIT=nginx.service
journalctl _COMM=sshd
journalctl _HOSTNAME=server1

# 统计日志条目
journalctl --no-pager | cut -d' ' -f5 | sort | uniq -c | sort -nr | head -20

# 紧急情况
journalctl --force --boot=-1   # 查看旧启动日志
journalctl --vacuum-time=7d    # 保留7天
journalctl --vacuum-size=500M  # 最多500MB
```

---

## 五、网络高级特性

### 5.1 网络命名空间

**Q：什么是网络命名空间？有什么用途？**

网络命名空间允许在同一Linux主机上创建隔离的网络栈。

```bash
# 创建网络命名空间
ip netns add ns1
ip netns add ns2

# 在命名空间中执行命令
ip netns exec ns1 ip addr
ip netns exec ns1 ping 8.8.8.8

# 创建veth对（连接命名空间）
ip link add veth0 type veth peer name veth1
ip link set veth1 netns ns1

# 配置
ip addr add 192.168.1.1/24 dev veth0
ip netns exec ns1 ip addr add 192.168.1.2/24 dev veth1
ip link set veth0 up
ip netns exec ns1 ip link set veth1 up

# 查看
ip netns list
ip netns exec ns1 ip link

# 应用场景
# 1. 容器网络隔离
# 2. 测试环境隔离
# 3. VPN隔离
# 4. 网络协议栈开发

# 清理
ip link delete veth0
ip netns del ns1
```

### 5.2 链路聚合（Bonding）

```bash
# 查看bonding模块
modprobe bonding

# 创建bond接口
ip link add bond0 type bond mode 802.3ad
ip link set eth0 master bond0
ip link set eth1 master bond0

# 配置bond
ip link set bond0 up
ip addr add 192.168.1.100/24 dev bond0

# Bonding模式
# 0: balance-rr (轮询)
# 1: active-backup (主备)
# 2: balance-xor (基于hash)
# 3: broadcast (广播)
# 4: 802.3ad (LACP)
# 5: balance-tlb (发送负载均衡)
# 6: balance-alb (全部负载均衡)

# 查看bond状态
cat /proc/net/bonding/bond0
```

### 5.3 VLAN配置

```bash
# 使用ip命令
ip link add link eth0 name eth0.100 type vlan id 100
ip addr add 192.168.100.1/24 dev eth0.100
ip link set eth0.100 up

# 查看VLAN
ip -d link show
cat /proc/net/vlan/config

# 持久化配置 (CentOS)
/etc/sysconfig/network-scripts/ifcfg-eth0.100
DEVICE=eth0.100
BOOTPROTO=static
ONBOOT=yes
VLAN=yes
IPADDR=192.168.100.1
NETMASK=255.255.255.0
```

---

## 六、面试高频问题

### Q1：如何排查服务器无法连接的问题？

```bash
# 排查流程（从近到远）
# 1. 本地检查
ping localhost                    # 确认本地网络栈正常
ip addr show                     # IP配置
ip route show                    # 路由表

# 2. 本地服务检查
ss -tulnp | grep :22             # SSH服务是否监听
systemctl status sshd            # 服务状态
journalctl -u sshd -n 20         # 最近的日志

# 3. 本地防火墙
iptables -L -n | head -20        # 是否有DROP规则
firewall-cmd --list-all          # firewalld规则

# 4. 对方可达性
ping -c 3 <目标IP>              # ICMP
traceroute <目标IP>             # 路由
mtr <目标IP>                    # 持续路由

# 5. 端口连通性
telnet <目标IP> <端口>          # 手动测试
nc -zv <目标IP> <端口>          # netcat测试
curl -v telnet://<目标IP>:<端口>  # HTTP测试

# 6. 网络设备
# 检查路由器、交换机配置
# 检查ISP是否有丢包

# 7. 抓包分析
tcpdump -i eth0 host <目标IP> -w /tmp/capture.pcap
tcpdump -i eth0 port 80 -n -v

# 8. 系统限制
cat /proc/sys/net/core/somaxconn     # 最大连接数
cat /proc/sys/net/ipv4/tcp_max_syn_backlog  # SYN队列
ulimits -n                             # 文件描述符
```

### Q2：如何设置Linux服务器的安全策略？

```bash
# 1. 用户权限
# /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535
root soft nofile unlimited

# 2. 内核参数
# /etc/sysctl.conf
net.ipv4.ip_forward = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1

# 3. SSH安全
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300

# 4. 防火墙规则
iptables -F
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Q3：systemd和init脚本的优缺点？

| 方面 | systemd | init脚本 |
|------|---------|---------|
| 启动速度 | 并行启动，快 | 串行启动，慢 |
| 管理方式 | 统一（systemctl） | 分散（各服务独立） |
| 依赖管理 | 自动解析 | 手动编写LSB头 |
| 日志 | journald统一管理 | 分散到不同日志 |
| 资源限制 | 内置cgroup | 需手工配置 |
| 激活方式 | 按需/套接字/Socket | 开机自启 |
| 配置方式 | 单元文件 | Shell脚本 |
| 兼容性 | 现代系统 | 传统系统 |

---

## 七、总结

| 主题 | 核心要点 |
|------|---------|
| 网络基础 | ip命令、网络配置、诊断工具（ping/traceroute/ss/netstat） |
| 防火墙 | iptables四表五链、firewalld区域、nftables新特性 |
| systemd | 服务管理、Unit文件编写、定时器、Socket激活 |
| 系统监控 | top/htop/glances、进程监控、资源监控、日志分析 |
| 故障排查 | 分层排查法、网络连接、服务状态、资源瓶颈 |
| 高级特性 | 网络命名空间、链路聚合、VLAN配置 |

> 🔗 **Linux面试八股文系列即将完结！** 下期预告：**Linux面试八股文（四）——Linux系统安全与权限管理**，将深入讲解用户权限、SELinux/AppArmor、文件系统安全与入侵检测，敬请期待！
