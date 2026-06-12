---
title: "Linux面试八股文（一）——Linux基础与命令实战"
date: 2026-06-12T11:00:00+08:00
draft: false
categories: ["linux"]
tags: ["面试", "八股文", "Linux", "命令", "文件系统", "权限", "Shell", "管道", "文本处理"]
---

# Linux面试八股文（一）——Linux基础与命令实战

> 本篇开启Linux面试八股文新系列，从Linux基础概念、文件系统、常用命令到Shell编程，全面覆盖Linux面试核心知识点。

---

## 一、Linux体系结构

### 1.1 Linux系统架构

**Q：Linux操作系统的整体架构是怎样的？**

```
Linux体系结构（自底向上）：

┌─────────────────────────────────────┐
│           用户空间 (User Space)       │
├─────────────────────────────────────┤
│  应用程序  │  Shell  │  库函数(glibc) │
├─────────────────────────────────────┤
│           系统调用接口                │
│       (System Call Interface)        │
├─────────────────────────────────────┤
│           内核空间 (Kernel Space)     │
├─────────────────────────────────────┤
│ 进程调度 │ 内存管理 │ 文件系统 │ 网络栈 │
│  VFS    │  驱动模型 │ IPC     │ 设备驱动│
├─────────────────────────────────────┤
│           硬件 (Hardware)            │
│    CPU  │  内存  │  磁盘  │  网卡     │
└─────────────────────────────────────┘
```

用户态与内核态切换：
- **用户态→内核态**：系统调用、中断、异常
- **切换开销**：保存/恢复寄存器、切换地址空间、TLB刷新
- **优化原则**：减少不必要的系统调用（如 buffered I/O）

### 1.2 常见Linux发行版

**Q：Linux有哪些主流发行版？区别是什么？**

| 家族 | 代表发行版 | 包管理器 | 适用场景 |
|------|-----------|---------|---------|
| Red Hat | RHEL/CentOS/Fedora | yum/dnf | 企业服务器 |
| Debian | Debian/Ubuntu | apt | 开发/桌面/云 |
| Arch | Arch/Manjaro | pacman | 滚动更新/定制 |
| SUSE | openSUSE/SLES | zypper | 欧洲企业 |
| Alpine | Alpine | apk | 容器/Docker |

---

## 二、文件系统核心

### 2.1 Linux文件系统层级

**Q：Linux目录结构是怎样的？各目录用途？**

```
/ (根目录)
├── bin/     # 基础命令（所有用户可用）
├── sbin/    # 系统管理命令（root）
├── boot/    # 启动文件（内核、grub）
├── dev/     # 设备文件（一切皆文件）
├── etc/     # 配置文件
├── home/    # 用户主目录
├── root/    # root用户主目录
├── lib/     # 共享库
├── opt/     # 第三方软件
├── proc/    # 虚拟文件系统（内核信息）
├── sys/     # 虚拟文件系统（设备模型）
├── tmp/     # 临时文件
├── var/     # 可变数据（日志、缓存）
├── usr/     # 用户程序
│   ├── bin/ # 用户命令
│   ├── lib/ # 用户库
│   └── local/ # 本地编译安装
└── mnt/     # 挂载点
```

关键虚拟文件系统：
```bash
# /proc - 进程与内核信息
cat /proc/cpuinfo          # CPU信息
cat /proc/meminfo          # 内存信息
cat /proc/<pid>/status     # 进程状态
cat /proc/loadavg          # 系统负载

# /sys - 设备与驱动信息
ls /sys/class/net/         # 网络设备
cat /sys/block/sda/size    # 磁盘大小
```

### 2.2 文件类型与Inode

**Q：Linux有哪些文件类型？Inode是什么？**

```
文件类型（ls -l 首字符）：
-  普通文件
d  目录文件
l  符号链接
b  块设备文件
c  字符设备文件
p  命名管道(FIFO)
s  套接字文件

Inode（索引节点）：
- 存储文件元数据（权限、所有者、大小、时间戳、数据块指针）
- 不存储文件名（文件名存在目录项中）
- 每个文件唯一Inode号
- df -i 查看Inode使用情况

硬链接 vs 软链接：
┌──────────┬──────────────┬──────────────┐
│  特性     │  硬链接       │  软链接       │
├──────────┼──────────────┼──────────────┤
│ Inode    │  相同         │  不同         │
│ 跨文件系统 │  ❌           │  ✅           │
│ 链接目录   │  ❌           │  ✅           │
│ 源文件删除 │  不影响       │  悬空链接     │
│ 创建命令   │  ln src dst  │  ln -s src   │
└──────────┴──────────────┴──────────────┘
```

---

## 三、文件权限与用户管理

### 3.1 权限模型

**Q：Linux文件权限如何工作？什么是SUID/SGID/Sticky Bit？**

```bash
# 权限表示法
-rwxr-xr-- 1 root root 4096 Jun 12 10:00 script.sh
│├──┤├──┤├──┤
│ │   │   └── 其他用户: r-- (4)
│ │   └────── 所属组: r-x (5)
│ └────────── 所有者: rwx (7)
└──────────── 文件类型: -

# 数字表示法
r=4, w=2, x=1
chmod 755 script.sh  # rwxr-xr-x
chmod 644 config.ini # rw-r--r--

# 特殊权限
┌────────────┬──────┬──────────────────────────────┐
│  特殊权限    │ 数字 │  作用                         │
├────────────┼──────┼──────────────────────────────┤
│ SUID        │ 4    │  执行时以文件所有者身份运行     │
│ SGID        │ 2    │  执行时以文件所属组身份运行     │
│ Sticky Bit  │ 1    │  只有所有者能删除目录中的文件   │
└────────────┴──────┴──────────────────────────────┘

# SUID经典案例：passwd命令
ls -l /usr/bin/passwd
-rwsr-xr-x 1 root root ... /usr/bin/passwd
# 普通用户执行passwd时，临时获得root权限修改/etc/shadow

# Sticky Bit经典案例：/tmp目录
ls -ld /tmp
drwxrwxrwt 10 root root ... /tmp
# 任何用户可写，但只能删除自己创建的文件
```

### 3.2 用户与用户组

**Q：用户和用户组管理的常用命令？**

```bash
# 用户管理
useradd -m -s /bin/bash newuser  # 创建用户（-m创建家目录，-s指定Shell）
usermod -aG docker newuser       # 添加到docker组
userdel -r olduser               # 删除用户及家目录
passwd newuser                   # 设置密码

# 用户组管理
groupadd devteam                 # 创建组
gpasswd -a user1 devteam         # 添加用户到组
gpasswd -d user1 devteam         # 从组中移除用户

# 查看信息
id username                      # 查看用户UID/GID/组
groups username                  # 查看用户所属组
w / who                          # 查看登录用户
last                             # 查看登录历史

# 切换用户
su - username                    # 切换用户（加载环境变量）
sudo command                     # 以root权限执行（需配置/etc/sudoers）
```

---

## 四、高频命令实战

### 4.1 文本处理三剑客

**Q：grep/sed/awk的常用场景？**

```bash
# ===== grep - 文本搜索 =====
grep -r "error" /var/log/        # 递归搜索
grep -i "warning" app.log        # 忽略大小写
grep -n "TODO" *.java            # 显示行号
grep -c "exception" app.log      # 统计匹配行数
grep -v "debug" app.log          # 排除匹配行
grep -E "err|fail|exception" log # 正则匹配（多关键词）
grep -A 5 "NullPointerException" # 显示匹配行后5行

# ===== sed - 流编辑器 =====
sed 's/old/new/g' file.txt       # 全局替换
sed -i 's/old/new/g' file.txt    # 直接修改文件
sed -n '10,20p' file.txt         # 打印10-20行
sed '/^$/d' file.txt             # 删除空行
sed '1,3d' file.txt              # 删除1-3行

# ===== awk - 文本分析 =====
awk '{print $1, $3}' file.txt           # 打印第1、3列
awk -F: '{print $1}' /etc/passwd        # 指定分隔符
awk '$3 > 100 {print $0}' data.txt      # 条件过滤
awk '{sum+=$1} END{print sum}' nums.txt # 求和
awk '{count[$1]++} END{for(k in count) print k, count[k]}' access.log  # 统计频次
```

### 4.2 进程管理

**Q：如何查看和管理进程？**

```bash
# 查看进程
ps aux                           # 查看所有进程（BSD格式）
ps -ef                           # 查看所有进程（System V格式）
ps aux --sort=-%mem              # 按内存排序
pgrep -f "java.*app"             # 按命令模式查找PID

# 实时监控
top                              # 交互式进程监控
htop                             # 增强版top（需安装）

# 终止进程
kill PID                         # 发送SIGTERM（优雅终止）
kill -9 PID                      # 发送SIGKILL（强制终止）
killall nginx                    # 按名称终止
pkill -f "python.*server"        # 按模式终止

# 后台任务
command &                        # 后台运行
nohup command &                  # 退出终端后继续运行
jobs                             # 查看后台任务
fg %1                            # 调到前台
bg %1                            # 继续后台运行
Ctrl+Z                           # 暂停当前任务
```

### 4.3 磁盘与内存

**Q：如何查看磁盘和内存使用情况？**

```bash
# 磁盘
df -h                            # 文件系统磁盘使用
du -sh /var/log/                 # 目录大小
du -h --max-depth=1 /            # 一级目录大小
lsblk                            # 块设备信息
fdisk -l                         # 磁盘分区信息

# 内存
free -h                          # 内存使用
cat /proc/meminfo                # 详细内存信息

# 关键指标解读
# free命令输出：
#              total    used    free   shared  buff/cache  available
# Mem:        16G      8G      2G     256M    6G          12G
#
# available = free + 可回收的buff/cache
# 实际可用内存看available，不看free！

# I/O监控
iostat -x 1                      # 每秒IO统计
iotop                            # IO使用排行
```

### 4.4 网络命令

**Q：Linux网络排查常用命令？**

```bash
# 连接与端口
netstat -tlnp                    # 查看监听端口
ss -tlnp                         # 更快的替代（推荐）
lsof -i :8080                    # 查看端口占用

# 连通性
ping 8.8.8.8                     # 测试连通性
traceroute google.com            # 路由追踪
telnet host 3306                 # 端口连通测试
nc -zv host 3306                 # 端口扫描

# DNS
nslookup domain.com              # DNS查询
dig domain.com                   # 详细DNS查询
host domain.com                  # 简单DNS查询

# 抓包
tcpdump -i eth0 port 80          # 抓HTTP包
tcpdump -i eth0 host 10.0.0.1    # 抓指定IP
tcpdump -w capture.pcap          # 保存到文件
```

---

## 五、Shell编程基础

### 5.1 Shell脚本模板

**Q：如何编写规范的Shell脚本？**

```bash
#!/bin/bash
# Description: 规范的Shell脚本模板
# Author: Raphael
# Date: 2026-06-12

set -euo pipefail  # 严格模式：遇错退出、未定义变量报错、管道错误传递

# 常量定义
readonly SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
readonly LOG_FILE="${SCRIPT_DIR}/app.log"

# 日志函数
log() {
    local level=$1; shift
    local msg="$*"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [${level}] ${msg}" | tee -a "${LOG_FILE}"
}

# 错误处理
cleanup() {
    log INFO "清理临时资源..."
    rm -f "${TMP_FILE:-}"
}
trap cleanup EXIT

# 参数处理
usage() {
    echo "Usage: $0 [-e ENV] [-p PORT] <command>"
    exit 1
}

ENV="dev"
PORT=8080

while getopts "e:p:h" opt; do
    case $opt in
        e) ENV="$OPTARG" ;;
        p) PORT="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))

# 主逻辑
main() {
    log INFO "启动服务 env=${ENV} port=${PORT}"
    # 业务逻辑...
}

main "$@"
```

### 5.2 常用Shell技巧

```bash
# 变量与字符串
name="Linux"
echo "Hello ${name}"              # 双引号：变量展开
echo 'Hello ${name}'              # 单引号：原样输出
echo ${#name}                     # 字符串长度: 5
echo ${name:0:3}                  # 子串: Lin
echo ${name/Linux/Unix}           # 替换: Unix

# 数组
arr=(a b c d)
echo ${arr[0]}                    # 第一个元素
echo ${arr[@]}                    # 所有元素
echo ${#arr[@]}                   # 数组长度

# 条件判断
if [ -f "/etc/passwd" ]; then    # 文件存在且为普通文件
    echo "file exists"
fi

# 文件判断选项
# -f 普通文件  -d 目录  -e 存在  -r 可读
# -w 可写     -x 可执行 -s 非空  -L 符号链接

# 循环
for i in {1..10}; do
    echo $i
done

while read line; do
    echo "$line"
done < input.txt

# 命令替换
files=$(ls *.log)
today=$(date +%Y%m%d)
pid=$(pgrep -f "myapp")
```

---

## 六、管道与重定向

### 6.1 重定向

**Q：Linux重定向有哪些用法？**

```bash
# 标准流
# stdin(0)  stdout(1)  stderr(2)

# 输出重定向
command > file.txt       # stdout → 文件（覆盖）
command >> file.txt      # stdout → 文件（追加）
command 2> error.log     # stderr → 文件
command &> all.log       # stdout+stderr → 文件
command > out.log 2>&1   # 等价于 &>（POSIX写法）

# 输入重定向
command < input.txt      # 从文件读取stdin

# Here Document
cat << EOF
多行文本
变量展开: ${HOME}
EOF

# Here String
grep "pattern" <<< "search in this string"

# /dev/null 黑洞
command > /dev/null 2>&1  # 丢弃所有输出
```

### 6.2 管道与管道符

**Q：管道的工作原理？如何处理管道中的错误？**

```
管道原理：
  command1 | command2 | command3
  
  command1的stdout → command2的stdin
  command2的stdout → command3的stdin

  注意：管道只传递stdout，stderr不经过管道！

管道错误处理：
  # 方法1：set -o pipefail（管道任一命令失败则整体失败）
  set -o pipefail
  command1 | command2 | command3
  echo $?  # 返回最右侧失败的命令的退出码

  # 方法2：PIPESTATUS数组
  command1 | command2
  echo ${PIPESTATUS[@]}  # 各命令退出码

  # 方法3：合并stderr到stdout
  command1 2>&1 | command2

常用管道组合：
  # 统计日志中HTTP状态码分布
  awk '{print $9}' access.log | sort | uniq -c | sort -rn | head

  # 查找最大的10个文件
  find / -type f -exec du -h {} + 2>/dev/null | sort -rh | head -10

  # 批量杀进程
  ps aux | grep "python" | grep -v grep | awk '{print $2}' | xargs kill

  # 统计代码行数
  find . -name "*.java" | xargs wc -l | tail -1
```

---

## 七、面试高频易错点

### 7.1 常见陷阱

| 陷阱 | 错误写法 | 正确写法 |
|------|---------|---------|
| 变量比较 | `[ $var = "hello" ]` | `[[ "$var" == "hello" ]]` |
| 空变量 | `[ $empty = "x" ]` | `[ "$empty" = "x" ]` |
| rm误删 | `rm -rf / $dir`(空变量) | `[[ -n "$dir" ]] && rm -rf "$dir"` |
| 通配符无匹配 | `ls *.log`(无文件时) | `ls *.log 2>/dev/null` |
| cp覆盖 | `cp file dir/`(无斜杠) | 确保dir是目录加`/` |
| 权限问题 | `./script.sh`(无执行权限) | `chmod +x script.sh` |

### 7.2 性能分析速查

```bash
# 快速性能诊断三板斧
# 1. CPU
uptime                            # 负载（1/5/15分钟）
top -bn1 | head -20               # CPU使用Top

# 2. 内存
free -h                           # 内存使用
vmstat 1 5                        # 虚拟内存统计

# 3. 磁盘IO
iostat -x 1 5                     # IO统计
df -h                             # 磁盘空间
```

---

## 总结

| 主题 | 核心要点 |
|------|---------|
| 体系结构 | 用户态/内核态、系统调用、发行版差异 |
| 文件系统 | FHS目录规范、Inode、硬链接/软链接 |
| 权限管理 | rwx模型、SUID/SGID/Sticky Bit、用户组管理 |
| 高频命令 | grep/sed/awk三剑客、进程管理、磁盘内存、网络排查 |
| Shell编程 | 严格模式、参数处理、数组、条件判断 |
| 管道重定向 | stdin/stdout/stderr、pipefail、常用管道组合 |
| 面试陷阱 | 变量引号、空值检查、权限问题 |

下期预告：
- Linux面试八股文（二）——Linux系统管理与服务配置
