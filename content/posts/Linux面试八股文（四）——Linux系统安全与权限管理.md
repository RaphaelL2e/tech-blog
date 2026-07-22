---
title: Linux面试八股文（四）——Linux系统安全与权限管理
date: 2026-06-14 09:00:00+08:00
updated: '2026-06-14T09:00:00+08:00'
description: '面试高频问题：Linux文件权限怎么管理？SELinux和AppArmor有什么区别？如何检测系统是否被入侵？sudo和su的区别是什么？本文带你系统掌握Linux安全与权限管理的核心知识。 Q: Linux中用户和组的分类？
  主组(Primary Group)：用户创建时自动分配，一个用户只能有一。'
topic: computer-science
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Linux
- 安全
- 权限管理
categories:
- 计算机基础
draft: false
---

> 面试高频问题：Linux文件权限怎么管理？SELinux和AppArmor有什么区别？如何检测系统是否被入侵？sudo和su的区别是什么？本文带你系统掌握Linux安全与权限管理的核心知识。

---

## 一、Linux用户与权限体系

### 1.1 用户与组管理

**Q: Linux中用户和组的分类？**

A: Linux用户分为三类：

| 类型 | UID范围 | 说明 |
|------|---------|------|
| 超级用户(root) | 0 | 最高权限，不受限制 |
| 系统用户 | 1-999(centos7+) | 运行系统服务，不允许登录 |
| 普通用户 | 1000+ | 日常使用，权限受限 |

用户组分为：
- **主组(Primary Group)**：用户创建时自动分配，一个用户只能有一个主组
- **附加组(Supplementary Group)**：用户可加入多个附加组获取额外权限

关键配置文件：

```bash
# 用户信息
/etc/passwd    # 用户名:x:UID:GID:描述:家目录:Shell
/etc/shadow    # 用户名:加密密码:最后修改:最小间隔:最大间隔:警告:不活动:过期
/etc/group     # 组名:x:GID:组成员列表
/etc/gshadow   # 组的影子密码文件
```

**Q: /etc/passwd中每行字段的含义？**

```
root:x:0:0:root:/root:/bin/bash
│    │ │ │  │     │      │
│    │ │ │  │     │      └─ 默认Shell
│    │ │ │  │     └──────── 家目录
│    │ │ │  └────────────── GECOS(用户描述)
│    │ │ └───────────────── GID
│    │ └─────────────────── UID
│    └───────────────────── 密码占位(x表示在shadow中)
└────────────────────────── 用户名
```

### 1.2 用户管理命令

```bash
# 创建用户
useradd -m -s /bin/bash -G docker,wheel username
# -m 创建家目录  -s 指定Shell  -G 附加组

# 修改用户
usermod -aG sudo username    # 追加附加组
usermod -L username          # 锁定账户
usermod -U username          # 解锁账户
usermod -s /sbin/nologin username  # 禁止登录

# 删除用户
userdel -r username    # -r 删除家目录和邮件

# 密码管理
passwd username              # 修改密码
chage -M 90 username         # 密码90天过期
chage -l username            # 查看密码策略

# 组管理
groupadd devteam
gpasswd -a user devteam      # 添加用户到组
gpasswd -d user devteam      # 从组中移除用户
```

### 1.3 文件权限详解

**Q: Linux文件权限的完整体系？**

A: Linux权限由三部分组成：

```
-rwxr-xr-- 1 root root 4096 Jun 14 10:00 file.txt
│├──┤├──┤├──┤
│ │   │   └── 其他用户(other): r--
│ │   └────── 组(group): r-x
│ └────────── 所有者(owner): rwx
└──────────── 文件类型(- 普通文件 d 目录 l 链接)
```

权限的八进制表示：

| 权限 | 二进制 | 八进制 |
|------|--------|--------|
| --- | 000 | 0 |
| --x | 001 | 1 |
| -w- | 010 | 2 |
| -wx | 011 | 3 |
| r-- | 100 | 4 |
| r-x | 101 | 5 |
| rw- | 110 | 6 |
| rwx | 111 | 7 |

**Q: 目录权限和文件权限的区别？**

| 权限 | 文件含义 | 目录含义 |
|------|---------|---------|
| r | 读取文件内容 | 列出目录下的文件名(ls) |
| w | 修改文件内容 | 在目录中创建/删除/重命名文件 |
| x | 执行文件 | 进入目录(cd)及访问目录内文件的元数据 |

> ⚠️ 重要：要删除目录中的文件，需要目录的**w权限**，而不是文件的w权限！

```bash
# 权限修改
chmod 755 file          # 八进制方式
chmod u+x file          # 符号方式
chmod g-w,o+r file      # 组减写，其他加读
chmod -R 644 directory/ # 递归修改

# 所有者修改
chown user:group file
chown -R www-data:www-data /var/www/

# 默认权限
umask 022   # 文件644 目录755
umask 077   # 文件600 目录700
```

### 1.4 特殊权限位

**Q: SUID、SGID、Sticky Bit是什么？**

| 特殊权限 | 八进制 | 作用 | 常见示例 |
|---------|--------|------|---------|
| SUID | 4xxx | 执行时以**文件所有者**身份运行 | /usr/bin/passwd |
| SGID | 2xxx | 执行时以**文件所属组**身份运行；目录下新建文件继承组 | /usr/bin/wall |
| Sticky | 1xxx | 目录下文件只能被所有者删除 | /tmp |

```bash
# SUID示例：普通用户修改密码
$ ls -l /usr/bin/passwd
-rwsr-xr-x 1 root root ... /usr/bin/passwd
# 注意s位，执行时以root身份运行

# Sticky示例：/tmp目录
$ ls -ld /tmp
drwxrwxrwt 15 root root ... /tmp
# 注意t位，用户只能删除自己的文件

# 设置特殊权限
chmod 4755 file    # 设置SUID
chmod 2755 dir     # 设置SGID
chmod 1777 dir     # 设置Sticky Bit

# 查找SUID文件（安全审计常用）
find / -perm -4000 -type f 2>/dev/null
```

> 🔴 安全风险：SUID是提权攻击的重要目标，必须定期审计！

---

## 二、sudo与权限提升

### 2.1 sudo详解

**Q: sudo和su的区别？**

| 特性 | su | sudo |
|------|-----|------|
| 密码 | 需要目标用户密码 | 只需当前用户密码 |
| 权限粒度 | 完全切换 | 可精确控制命令 |
| 审计 | 无详细记录 | 记录每条命令 |
| 安全性 | 较低 | 较高 |
| 会话 | 持续会话 | 单次授权(可配置超时) |

**Q: sudo的配置原理？**

A: sudo通过`/etc/sudoers`文件配置，推荐使用`visudo`编辑：

```bash
# 基本语法：谁 在哪 = (以谁身份) 执行什么
root    ALL = (ALL:ALL) ALL
%wheel  ALL = (ALL) ALL

# 精细控制示例
# 运维组可以执行所有系统管理命令
%ops    ALL = /usr/sbin/service, /usr/bin/systemctl, /sbin/ifconfig

# 开发组只能重启特定服务
%dev    ALL = /usr/bin/systemctl restart nginx, /usr/bin/systemctl restart redis

# 无需密码执行
username ALL = (ALL) NOPASSWD: ALL

# 只能以特定用户身份执行
admin   ALL = (postgres) /usr/bin/psql
```

sudoers高级特性：

```bash
# 别名定义
User_Alias DBA = alice, bob
Cmnd_Alias DB_CMD = /usr/bin/mysql, /usr/bin/mysqldump, /usr/bin/mysqladmin
Host_Alias PROD = db1, db2, db3

# 使用别名
DBA PROD = (mysql) DB_CMD

# Defaults设置
Defaults env_reset          # 重置环境变量
Defaults logfile="/var/log/sudo.log"  # 日志文件
Defaults timestamp_timeout=15  # 15分钟超时
Defaults !rootpw           # 不需要root密码
```

### 2.2 PAM认证框架

**Q: 什么是PAM？它如何工作？**

A: PAM(Pluggable Authentication Modules)是Linux的统一认证框架：

```
应用程序 → PAM-API → PAM模块栈 → 认证结果
                          │
                    ┌─────┴──────┐
                    │ pam_unix   │ 本地密码认证
                    │ pam_ldap   │ LDAP认证
                    │ pam_tally2 │ 登录失败锁定
                    │ pam_limits │ 资源限制
                    │ pam_wheel  │ wheel组控制su
                    └────────────┘
```

PAM配置文件：`/etc/pam.d/`目录下

```bash
# /etc/pam.d/sshd 示例
auth     required   pam_sepermit.so
auth     required   pam_env.so
auth     sufficient pam_unix.so
auth     required   pam_deny.so

account  required   pam_unix.so
account  required   pam_nologin.so

password required   pam_pwquality.so retry=3 minlen=8
password sufficient pam_unix.so sha512 shadow

session  required   pam_limits.so
session  required   pam_unix.so
```

四种控制标志：

| 标志 | 含义 | 失败时 |
|------|------|--------|
| required | 必须通过 | 继续检查后续模块，最终返回失败 |
| sufficient | 通过即够 | 立即返回成功（跳过后续） |
| requisite | 必须通过 | 立即返回失败 |
| optional | 可选 | 不影响结果 |

---

## 三、SELinux与AppArmor

### 3.1 SELinux

**Q: SELinux是什么？它如何增强系统安全？**

A: SELinux(Security-Enhanced Linux)是强制访问控制(MAC)实现，由NSA开发：

**三种运行模式：**

| 模式 | 说明 |
|------|------|
| Enforcing | 强制模式，违反策略会被阻止并记录 |
| Permissive | 宽容模式，违反策略只记录不阻止 |
| Disabled | 禁用SELinux |

```bash
# 查看状态
sestatus
getenforce

# 临时切换模式
setenforce 1    # Enforcing
setenforce 0    # Permissive

# 永久修改
vim /etc/selinux/config
SELINUX=enforcing
# 修改后需重启
```

**核心概念：**

```
SELinux安全上下文格式：
user:role:type:level

示例：
system_u:object_r:httpd_sys_content_t:s0
│       │         │                   │
│       │         │                   └─ MLS/MCS级别
│       │         └───────────────────── 类型(最重要)
│       └─────────────────────────────── 角色
└─────────────────────────────────────── 用户
```

**类型强制(Type Enforcement)是最核心的机制：**

```
进程运行在域(Domain)中
文件有类型(Type)
规则定义：哪个域可以访问哪个类型

例如：
allow httpd_t httpd_sys_content_t : file { read getattr };
│     │        │                     │      │
│     │        │                     │      └─ 允许的操作
│     │        └─────────────────────└─────── 目标类型
│     └────────────────────────────────────── 源域
└───────────────────────────────────────────── 规则类型
```

**常见操作：**

```bash
# 查看文件上下文
ls -Z /var/www/html/

# 修改文件上下文
chcon -t httpd_sys_content_t /var/www/html/index.html
chcon -R -t httpd_sys_content_t /var/www/html/

# 恢复默认上下文
restorecon -Rv /var/www/html/

# 永久设置上下文
semanage fcontext -a -t httpd_sys_content_t "/web(/.*)?"
restorecon -Rv /web

# 查看SELinux日志
ausearch -m avc -ts recent
sealert -a /var/log/audit/audit.log

# 布尔值开关
getsebool -a | grep httpd
setsebool -P httpd_can_network_connect on
```

### 3.2 AppArmor

**Q: AppArmor和SELinux有什么区别？**

| 特性 | SELinux | AppArmor |
|------|---------|----------|
| 策略语言 | 基于类型(TE) | 基于路径 |
| 配置难度 | 较复杂 | 较简单 |
| 默认发行版 | RHEL/CentOS | Ubuntu/SUSE |
| 粒度 | 更细(基于inode) | 较粗(基于路径) |
| 学习曲线 | 陡峭 | 平缓 |
| 文件移动 | 安全(跟随inode) | 可能失效(路径变化) |

AppArmor配置示例：

```bash
# 查看状态
aa-status
sudo apparmor_status

# 配置文件位置
/etc/apparmor.d/

# 示例：Nginx AppArmor配置
# /etc/apparmor.d/usr.sbin.nginx
#include <tunables/global>

/usr/sbin/nginx {
  #include <abstractions/base>
  #include <abstractions/nameservice>

  /usr/sbin/nginx mr,
  /etc/nginx/** r,
  /var/log/nginx/* rw,
  /var/www/html/** r,
  /tmp/** rw,

  deny /etc/shadow r,
  deny /root/** rw,
}

# 操作命令
aa-complain /etc/apparmor.d/usr.sbin.nginx  # 宽容模式
aa-enforce /etc/apparmor.d/usr.sbin.nginx   # 强制模式
aa-disable /etc/apparmor.d/usr.sbin.nginx   # 禁用
```

---

## 四、SSH安全加固

### 4.1 SSH服务安全配置

**Q: 如何加固SSH服务？**

A: SSH加固是系统安全的基础操作：

```bash
# /etc/ssh/sshd_config 安全配置

# 1. 禁用root登录
PermitRootLogin no

# 2. 仅允许密钥认证
PubkeyAuthentication yes
PasswordAuthentication no
ChallengeResponseAuthentication no

# 3. 限制可登录用户
AllowUsers deploy@10.0.0.0/24 admin
AllowGroups ssh-users

# 4. 修改默认端口(防扫描)
Port 2222

# 5. 空闲超时
ClientAliveInterval 300
ClientAliveCountMax 2

# 6. 限制认证尝试
MaxAuthTries 3

# 7. 禁用不必要的功能
X11Forwarding no
AllowTcpForwarding no
PermitEmptyPasswords no

# 8. 使用强加密算法
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
KexAlgorithms curve25519-sha256@libssh.org
```

### 4.2 SSH密钥管理

```bash
# 生成密钥对(推荐ed25519)
ssh-keygen -t ed25519 -C "deploy@server"
# 或RSA(兼容性好)
ssh-keygen -t rsa -b 4096 -C "deploy@server"

# 分发公钥
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server

# 使用ssh-agent管理密钥
eval $(ssh-agent -s)
ssh-add ~/.ssh/id_ed25519
ssh-add -l    # 列出已加载的密钥

# SSH跳板机配置 ~/.ssh/config
Host bastion
    HostName 1.2.3.4
    User deploy
    IdentityFile ~/.ssh/id_ed25519

Host prod-*
    ProxyJump bastion
    User admin
    IdentityFile ~/.ssh/id_ed25519

# 双因素认证(结合PAM)
# 安装libpam-google-authenticator
apt install libpam-google-authenticator
# /etc/pam.d/sshd 添加
auth required pam_google_authenticator.so
# /etc/ssh/sshd_config 修改
AuthenticationMethods publickey,keyboard-interactive
```

---

## 五、文件系统安全

### 5.1 文件系统挂载选项

**Q: 如何通过挂载选项增强文件系统安全？**

A: `/etc/fstab`中可以设置安全相关的挂载选项：

```bash
# /etc/fstab 安全挂载示例

# /tmp - 防止执行和suid
/dev/sda3  /tmp  ext4  defaults,nosuid,noexec,nodev  0 0

# /home - 防止suid和设备文件
/dev/sda4  /home  ext4  defaults,nosuid,nodev  0 0

# /var - 防止suid
/dev/sda5  /var  ext4  defaults,nosuid  0 0

# /boot - 只读(减少被篡改风险)
/dev/sda1  /boot  ext4  defaults,ro  0 0

# /dev/shm - 共享内存安全
tmpfs  /dev/shm  tmpfs  defaults,nosuid,noexec,nodev  0 0
```

关键安全选项：

| 选项 | 作用 | 适用场景 |
|------|------|---------|
| nosuid | 忽略SUID/SGID位 | /tmp, /home, /var |
| noexec | 禁止执行程序 | /tmp, /dev/shm |
| nodev | 忽略设备文件 | /tmp, /home |
| ro | 只读挂载 | /boot |

### 5.2 文件完整性校验

```bash
# AIDE(Advanced Intrusion Detection Environment)

# 初始化数据库
aideinit
# 数据库位置 /var/lib/aide/aide.db.new

# 复制为基准数据库
cp /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# 检查文件变化
aide --check

# 更新数据库
aide --update
cp /var/lib/aide/aide.db.new /var/lib/aide/aide.db

# 配置文件 /etc/aide/aide.conf
# 监控关键目录
/etc p+i+n+u+g+s+m+c+sha256
/bin p+i+n+u+g+s+m+c+sha256
/sbin p+i+n+u+g+s+m+c+sha256
/usr/bin p+i+n+u+g+s+m+c+sha256

# 忽略日志变化
/var/log p+i+n+u+g
```

### 5.3 加密与安全删除

```bash
# LUKS磁盘加密
cryptsetup luksFormat /dev/sdb1
cryptsetup luksOpen /dev/sdb1 secure_data
mkfs.ext4 /dev/mapper/secure_data
mount /dev/mapper/secure_data /secure

# 安全删除文件
shred -vfz -n 5 secret_file    # 覆盖5次+零填充
shred -vfz -n 3 /dev/sdb1      # 整盘安全擦除

# 加密目录(ecryptfs)
apt install ecryptfs-utils
ecryptfs-setup-private          # 设置加密家目录
mount -t ecryptfs /secret /secret  # 手动挂载
```

---

## 六、入侵检测与安全审计

### 6.1 系统入侵检测

**Q: 如何检测Linux系统是否被入侵？**

A: 入侵检测需要从多维度排查：

```bash
# 1. 检查异常用户
awk -F: '$3 == 0 {print $1}' /etc/passwd     # UID=0的用户
awk -F: '$7 != "/sbin/nologin" && $7 != "/bin/false" {print $1, $7}' /etc/passwd  # 可登录用户
grep -v "nologin\|false" /etc/passwd           # 有Shell的用户

# 2. 检查异常进程
ps auxf                     # 查看进程树
lsof -i -P -n              # 查看网络连接
netstat -tunlp             # 监听端口
ss -tunlp                  # 同上(更现代)

# 3. 检查定时任务
crontab -l                 # 当前用户
cat /etc/crontab           # 系统定时任务
ls -la /etc/cron.*         # cron目录
for user in $(cut -d: -f1 /etc/passwd); do echo "---$user---"; crontab -u $user -l 2>/dev/null; done

# 4. 检查SSH登录
last                       # 登录历史
lastb                      # 失败登录
cat /var/log/auth.log | grep "Failed password"   # Debian/Ubuntu
cat /var/log/secure | grep "Failed password"      # RHEL/CentOS

# 5. 检查SUID/SGID文件
find / -perm -4000 -type f 2>/dev/null     # SUID文件
find / -perm -2000 -type f 2>/dev/null     # SGID文件

# 6. 检查最近修改的文件
find / -mtime -1 -type f 2>/dev/null       # 24h内修改
find / -ctime -1 -type f 2>/dev/null       # 24h内属性变化

# 7. 检查隐藏文件
find / -name ".*" -type f 2>/dev/null | grep -v "^\./\."

# 8. 检查异常网络连接
ss -antp | grep ESTAB       # 已建立连接
lsof -i -P -n | grep ESTABLISHED
```

### 6.2 审计系统(auditd)

**Q: 如何使用auditd进行安全审计？**

```bash
# 安装和启动
yum install audit    # RHEL
apt install auditd   # Debian

systemctl enable auditd
systemctl start auditd

# 添加审计规则
# 监控关键文件修改
auditctl -w /etc/passwd -p wa -k passwd_changes
auditctl -w /etc/sudoers -p wa -k sudoers_changes
auditctl -w /etc/ssh/sshd_config -p wa -k sshd_config

# 监控命令执行
auditctl -a exit,always -F arch=b64 -S execve -k command_exec

# 监控特定用户操作
auditctl -a always,exit -F uid=1001 -k user_actions

# 查看审计日志
ausearch -k passwd_changes       # 按key搜索
ausearch -ua 1001 -ts today     # 某用户今天的操作
aureport -x                     # 可执行文件报告
aureport -u                     # 用户活动报告

# 持久化规则 /etc/audit/rules.d/audit.rules
-w /etc/passwd -p wa -k identity
-w /etc/sudoers -p wa -k sudoers
-w /etc/ssh/sshd_config -p wa -k ssh
-a always,exit -F arch=b64 -S chmod -S chown -S chgrp -k perm_mod
```

### 6.3 日志安全

```bash
# rsyslog配置 /etc/rsyslog.conf
# 远程日志服务器(防篡改)
*.* @@log-server:514    # TCP发送到远程

# journalctl查询
journalctl -u sshd --since "2026-06-14" --no-pager
journalctl -p err -b           # 本次启动的错误日志
journalctl -f                  # 实时跟踪

# 日志轮转 /etc/logrotate.d/
/var/log/secure {
    weekly
    rotate 12
    compress
    missingok
    notifempty
    create 0600 root root
}

# 防篡改：设置日志文件为append-only
chattr +a /var/log/secure    # 只能追加
lsattr /var/log/secure       # 查看属性
chattr -a /var/log/secure    # 解除(需root)
```

---

## 七、防火墙与网络安全

### 7.1 iptables安全规则

```bash
# 默认拒绝策略
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# 允许已建立的连接
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 允许回环接口
iptables -A INPUT -i lo -j ACCEPT

# 允许SSH(限制速率防暴力)
iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --set --name ssh
iptables -A INPUT -p tcp --dport 22 -m state --state NEW -m recent --update --seconds 60 --hitcount 4 --name ssh -j DROP
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# 允许HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# 允许ICMP(限制速率)
iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 1/s -j ACCEPT

# 记录被拒绝的包
iptables -A INPUT -j LOG --log-prefix "IPTables-Dropped: " --log-level 4
```

### 7.2 端口安全扫描与防护

```bash
# 端口扫描检测
nmap -sS -sV -O target_host     # SYN扫描+版本+OS检测
nmap -sU -p 53,161 target       # UDP扫描

# 检测本机开放端口
ss -tunlp
netstat -tunlp

# 关闭不需要的服务
systemctl list-unit-files --state=enabled    # 查看开机自启服务
systemctl disable avahi-daemon               # 关闭不需要的
systemctl stop cups                          # 关闭打印服务(服务器不需要)

# TCP Wrappers(简单访问控制)
# /etc/hosts.allow
sshd: 10.0.0.0/24, 192.168.1.0/24
vsftpd: 10.0.0.0/24

# /etc/hosts.deny
sshd: ALL    # 拒绝其他所有
```

---

## 八、内核安全与资源限制

### 8.1 内核安全参数

**Q: 常用的内核安全参数有哪些？**

```bash
# /etc/sysctl.conf 安全参数

# 禁用IP转发(非路由器)
net.ipv4.ip_forward = 0

# 防SYN Flood
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2

# 禁用ICMP重定向
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# 禁用源路由
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0

# 忽略ICMP广播
net.ipv4.icmp_echo_ignore_broadcasts = 1

# 记录可疑包
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1

# 地址空间随机化
kernel.randomize_va_space = 2

# 禁用core dump
fs.suid_dumpable = 0

# 限制ptrace(防调试)
kernel.yama.ptrace_scope = 1

# 生效
sysctl -p
```

### 8.2 资源限制(ulimits)

```bash
# /etc/security/limits.conf

# 限制最大进程数
*    soft  nproc  4096
*    hard  nproc  8192

# 限制打开文件数
*    soft  nofile  65536
*    hard  nofile  131072

# 限制core dump大小
*    soft  core  0
*    hard  core  0

# 限制内存(防fork炸弹)
*    hard  as  8388608    # 8GB

# 限制特定用户
deploy soft  nofile  100000
deploy hard  nofile  200000

# cgroup资源限制
# /etc/systemd/system/myservice.service
[Service]
MemoryMax=2G
CPUQuota=200%
TasksMax=100
```

---

## 九、安全加固检查清单

**Q: 生产服务器安全加固的完整checklist？**

| 类别 | 加固项 | 命令/配置 |
|------|--------|----------|
| 账户 | 禁用root SSH | `PermitRootLogin no` |
| 账户 | 删除无用账户 | `userdel -r username` |
| 账户 | 密码策略 | `chage -M 90 username` |
| 账户 | 锁定系统账户 | `passwd -l daemon` |
| 认证 | 密钥登录 | `PasswordAuthentication no` |
| 认证 | 禁用空密码 | `PermitEmptyPasswords no` |
| 认证 | 双因素认证 | Google Authenticator |
| 网络 | 修改SSH端口 | `Port 2222` |
| 网络 | 防火墙规则 | iptables/firewalld |
| 网络 | 禁用IP转发 | `net.ipv4.ip_forward=0` |
| 文件 | 关键文件权限 | `/etc/passwd 644` |
| 文件 | SUID审计 | `find / -perm -4000` |
| 文件 | 挂载选项 | `nosuid,noexec,nodev` |
| 服务 | 关闭不必要服务 | `systemctl disable` |
| 服务 | SELinux/AppArmor | Enforcing模式 |
| 监控 | 日志审计 | auditd + rsyslog |
| 监控 | 入侵检测 | AIDE + ClamAV |
| 监控 | 文件完整性 | `aide --check` |

### 自动化安全扫描工具

```bash
# Lynis - 全面安全扫描
apt install lynis
lynis audit system

# OpenSCAP - 安全合规检查
yum install scap-security-guide
oscap xccdf eval --profile stig-rhel8-disa --results scan.xml /usr/share/xml/scap/ssg/content/ssg-rhel8-ds.xml

# chkrootkit - rootkit检测
chkrootkit

# rkhunter - 另一个rootkit检测
rkhunter --check
```

---

## 十、总结

| 主题 | 核心要点 |
|------|---------|
| 用户权限 | 三类用户、rwx权限、SUID/SGID/Sticky |
| sudo | visudo配置、精细权限控制、审计 |
| SELinux | MAC机制、类型强制、上下文管理 |
| AppArmor | 基于路径的MAC、配置简单 |
| SSH加固 | 密钥认证、禁用root、速率限制 |
| 文件安全 | 挂载选项、完整性校验、加密 |
| 入侵检测 | 多维排查、auditd审计、日志分析 |
| 防火墙 | iptables规则、端口扫描防护 |
| 内核安全 | sysctl参数、资源限制、ASLR |

> 🎯 **Linux面试八股文系列完结！** 本系列从基础命令、Shell编程、网络服务到安全权限管理，覆盖了Linux面试的核心知识点。
> 
> 📌 **下期预告**：《Java并发编程面试八股文（一）——线程基础与锁机制》将深入Java线程模型、synchronized原理、Lock接口、AQS框架等并发编程核心话题，开启全新的面试八股文系列，敬请期待！
