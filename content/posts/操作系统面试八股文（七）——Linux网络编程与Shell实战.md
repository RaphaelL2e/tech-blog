---
title: 操作系统面试八股文（七）——Linux网络编程与Shell实战
date: 2026-06-17 10:00:00+08:00
updated: '2026-06-17T10:00:00+08:00'
description: '面试高频问题：Socket编程的基本流程是什么？TCP三次握手在代码中怎么体现？epoll的边缘触发和水平触发有什么区别？awk/sed/grep三剑客怎么用？Shell脚本怎么写才能稳健可靠？本文带你系统掌握Linux网络编程与Shell实战的核心知识。
  Q: TCP Socket编程的基本流程是。'
topic: computer-science
series: operating-system
series_order: 7
level: intermediate
status: maintained
tags:
- 操作系统
- Linux
- 网络编程
- Socket
- TCP
categories:
- 计算机基础
draft: false
---

> 面试高频问题：Socket编程的基本流程是什么？TCP三次握手在代码中怎么体现？epoll的边缘触发和水平触发有什么区别？awk/sed/grep三剑客怎么用？Shell脚本怎么写才能稳健可靠？本文带你系统掌握Linux网络编程与Shell实战的核心知识。

---

## 一、Socket网络编程基础

### 1.1 Socket编程模型

**Q: TCP Socket编程的基本流程是怎样的？**

**服务端流程：**
```
socket() → bind() → listen() → accept() → read()/write() → close()
```

**客户端流程：**
```
socket() → connect() → write()/read() → close()
```

```c
// TCP Server 示例（伪代码）
int server_fd = socket(AF_INET, SOCK_STREAM, 0);

struct sockaddr_in addr;
addr.sin_family = AF_INET;
addr.sin_port = htons(8080);
addr.sin_addr.s_addr = INADDR_ANY;

bind(server_fd, (struct sockaddr*)&addr, sizeof(addr));
listen(server_fd, 128);  // backlog = 128

while (1) {
    int client_fd = accept(server_fd, NULL, NULL);
    // 为每个客户端创建线程/进程处理
    char buf[1024];
    read(client_fd, buf, sizeof(buf));
    write(client_fd, "HTTP/1.1 200 OK\r\n...", ...);
    close(client_fd);
}
```

### 1.2 TCP连接在代码中的体现

**Q: TCP三次握手对应代码的哪些调用？**

| 握手阶段 | 客户端 | 服务端 | 内核行为 |
|----------|--------|--------|----------|
| 第一次握手 | `connect()` | - | 客户端发送SYN |
| 第二次握手 | `connect()` 阻塞等待 | `listen()` → SYN队列 | 服务端回复SYN+ACK |
| 第三次握手 | `connect()` 返回 | `accept()` 从ACCEPT队列取 | 客户端发送ACK |

```c
// listen的backlog参数含义
// backlog = min(backlog, /proc/sys/net/core/somaxconn)
// SYN队列满 → 丢弃新SYN或发送RST
// ACCEPT队列满 → 根据tcp_abort_on_overflow决定

// 查看队列溢出
netstat -s | grep -i "listen"
// 输出示例：times the listen queue of a socket overflowed
```

### 1.3 TCP状态转换与代码对应

```
CLOSED ──socket()──→ (创建socket)
          │
    ┌─────▼──────┐        ┌─────────────┐
    │   LISTEN   │ ←────── bind()+listen()
    └──┬────┬────┘
       │    │
  SYN_RCVD  │              accept()返回
       │    │                 │
       └────┼────ESTABLISHED─┘
            │
    read()返回0 → CLOSE_WAIT → close() → LAST_ACK → CLOSED
    close()     → FIN_WAIT_1 → FIN_WAIT_2 → TIME_WAIT → CLOSED
```

**TIME_WAIT状态（2MSL）：**
- 主动关闭的一方进入
- 持续时间：2 × MSL（Maximum Segment Lifetime，通常60s）
- 目的：确保最后的ACK能到达对端、让旧连接的数据包在网络中消失

### 1.4 UDP Socket编程

```c
// UDP Server（无连接）
int sock = socket(AF_INET, SOCK_DGRAM, 0);
bind(sock, ...);

char buf[1024];
struct sockaddr_in client_addr;
socklen_t len = sizeof(client_addr);
recvfrom(sock, buf, sizeof(buf), 0, 
         (struct sockaddr*)&client_addr, &len);
sendto(sock, "ACK", 3, 0, 
       (struct sockaddr*)&client_addr, len);
```

| 特性 | TCP | UDP |
|------|-----|-----|
| 连接 | 面向连接 | 无连接 |
| 可靠性 | 可靠，确认重传 | 不可靠 |
| 顺序 | 有序 | 无序 |
| 边界 | 流式（无边界的字节流） | 数据报（有边界） |
| 场景 | HTTP, 文件传输, SSH | DNS, 视频直播, 游戏 |

---

## 二、高性能I/O多路复用

### 2.1 五种I/O模型

| 模型 | 描述 | 阻塞点 |
|------|------|--------|
| 阻塞I/O | 等待数据就绪时阻塞 | `read()`阻塞 |
| 非阻塞I/O | 轮询检查，立即返回 | 轮询消耗CPU |
| I/O多路复用 | 单线程监听多个fd | `select/poll/epoll` |
| 信号驱动I/O | SIGIO信号通知 | 信号处理复杂 |
| 异步I/O | aio_read通知完成 | 无阻塞 |

### 2.2 select vs poll vs epoll

**Q: select、poll、epoll的区别是什么？**

| 特性 | select | poll | epoll |
|------|--------|------|-------|
| 数据结构 | fd_set（位图） | pollfd数组 | 红黑树+就绪链表 |
| fd上限 | 1024 (FD_SETSIZE) | 无限制 | 无限制 |
| 效率 | O(n) 轮询 | O(n) 轮询 | O(1) 只处理就绪fd |
| fd拷贝 | 每次都需要全量拷贝到内核 | 每次都需要 | 只需注册一次 |
| 触发模式 | 水平触发 | 水平触发 | LT/ET两种模式 |
| 适用场景 | fd少、连接生命周期短 | fd少 | 高并发长连接 |

```c
// select 示例
fd_set readfds;
FD_ZERO(&readfds);
FD_SET(sock_fd, &readfds);
int max_fd = sock_fd;

int ready = select(max_fd + 1, &readfds, NULL, NULL, NULL);
if (FD_ISSET(sock_fd, &readfds)) {
    int client_fd = accept(sock_fd, ...);
}

// epoll 示例
int epfd = epoll_create1(0);
struct epoll_event ev;
ev.events = EPOLLIN;          // 监听读事件
ev.data.fd = sock_fd;
epoll_ctl(epfd, EPOLL_CTL_ADD, sock_fd, &ev);

struct epoll_event events[1024];
int nfds = epoll_wait(epfd, events, 1024, -1);
for (int i = 0; i < nfds; i++) {
    if (events[i].data.fd == sock_fd) {
        int client_fd = accept(sock_fd, ...);
        // 注册新fd
        ev.events = EPOLLIN | EPOLLET;  // 边缘触发
        ev.data.fd = client_fd;
        epoll_ctl(epfd, EPOLL_CTL_ADD, client_fd, &ev);
    }
}
```

### 2.3 水平触发（LT）vs 边缘触发（ET）

**Q: epoll的LT和ET有什么区别？应该怎么选？**

| 特性 | 水平触发（LT） | 边缘触发（ET） |
|------|---------------|---------------|
| 触发条件 | 只要有数据就通知 | 只在状态变化时通知一次 |
| 读取策略 | 可以分段读取 | 必须一次读完直到EAGAIN |
| 编程难度 | 简单 | 复杂 |
| 适用场景 | 通用场景 | 高并发长连接 |
| 惊群效应 | 可能 | 通过EPOLLEXCLUSIVE缓解 |

**ET模式关键要点：**
```c
// ET模式下必须非阻塞 + 循环读取
int flags = fcntl(client_fd, F_GETFL, 0);
fcntl(client_fd, F_SETFL, flags | O_NONBLOCK);

while (1) {
    ssize_t n = read(client_fd, buf, sizeof(buf));
    if (n > 0) {
        // 处理数据
    } else if (n == 0) {
        close(client_fd);  // 对端关闭
        break;
    } else if (n == -1 && errno == EAGAIN) {
        break;  // 数据读完
    }
}
```

### 2.4 Reactor与Proactor模式

| 模式 | 通知机制 | I/O执行 | 代表框架 |
|------|----------|---------|----------|
| Reactor | 事件就绪通知 | 应用程序读写 | Netty, Nginx |
| Proactor | 操作完成通知 | 内核异步读写 | IOCP(Windows), Boost.Asio |

**Reactor三种实现：**
1. **单Reactor单线程**：Redis
2. **单Reactor多线程**：处理逻辑多线程，I/O仍在Reactor线程
3. **主从Reactor多线程**：Main Reactor负责accept，Sub Reactor负责读写（Netty采用）

---

## 三、Shell脚本编程实战

### 3.1 Shell基础

**Q: Shell脚本的基本结构和最佳实践是什么？**

```bash
#!/bin/bash
# 严格模式：遇错即停
set -euo pipefail
# -e: 任何命令失败立即退出
# -u: 使用未定义变量报错
# -o pipefail: 管道中任意命令失败都返回失败

# 脚本基本信息
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 日志函数
log_info()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"; }
log_error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; }

# 参数检查
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <input_file> [output_dir]"
    exit 1
fi

readonly INPUT_FILE="$1"
readonly OUTPUT_DIR="${2:-./output}"

# 主逻辑
main() {
    log_info "开始处理: $INPUT_FILE"
    # ...
    log_info "处理完成"
}

main "$@"
```

### 3.2 变量与字符串处理

```bash
# 变量默认值
name="${1:-default}"          # 未设置或空时使用default
name="${1-default}"           # 仅未设置时使用default
name="${1:?必须提供参数}"      # 未设置或空时报错退出

# 字符串长度
str="hello world"
echo ${#str}          # 11

# 字符串截取
echo ${str:0:5}       # hello
echo ${str:6}         # world

# 字符串替换
echo ${str/o/O}       # hellO world  (替换第一个)
echo ${str//o/O}      # hellO wOrld  (替换全部)

# 模式匹配删除
path="/usr/local/bin/script.sh"
echo ${path##*/}      # script.sh   (删除最长前缀匹配)
echo ${path%/*}       # /usr/local/bin (删除最短后缀匹配)
echo ${path#*/}       # usr/local/bin/script.sh (删除最短前缀匹配)
echo ${path%%/*}      # (空) (删除最长后缀匹配)
```

### 3.3 条件判断

```bash
# 文件判断
[[ -f "$file" ]]  # 是普通文件
[[ -d "$dir" ]]   # 是目录
[[ -e "$path" ]]  # 存在
[[ -r "$file" ]]  # 可读
[[ -w "$file" ]]  # 可写
[[ -x "$file" ]]  # 可执行
[[ -s "$file" ]]  # 非空文件

# 字符串判断
[[ -z "$str" ]]   # 字符串为空
[[ -n "$str" ]]   # 字符串非空
[[ "$a" == "$b" ]] # 相等
[[ "$a" != "$b" ]] # 不相等
[[ "$a" =~ ^[0-9]+$ ]]  # 正则匹配

# 数值判断
[[ $num -eq 10 ]]  # 等于
[[ $num -ne 10 ]]  # 不等于
[[ $num -lt 10 ]]  # 小于
[[ $num -gt 10 ]]  # 大于
[[ $num -le 10 ]]  # 小于等于
[[ $num -ge 10 ]]  # 大于等于

# 组合条件
[[ -f "$file" && -s "$file" ]]
[[ "$a" == "yes" || "$b" == "yes" ]]
[[ ! -d "$dir" ]]
```

### 3.4 循环与函数

```bash
# for循环
for i in {1..10}; do
    echo "$i"
done

for file in *.txt; do
    process "$file"
done

# while循环（按行读取文件）
while IFS= read -r line; do
    echo "行: $line"
done < "$input_file"

# 数组遍历
arr=("a" "b" "c")
for item in "${arr[@]}"; do
    echo "$item"
done

# 关联数组
declare -A map
map["key1"]="value1"
map["key2"]="value2"
for key in "${!map[@]}"; do
    echo "$key -> ${map[$key]}"
done

# 函数
my_function() {
    local local_var="内部变量"   # local 限定作用域
    echo "参数1: $1, 参数2: $2, 所有参数: $*, 参数个数: $#"
    return 0  # 0=成功, 非0=失败
}

result=$(my_function "a" "b")  # 函数输出捕获
```

### 3.5 常见陷阱与解决方案

| 陷阱 | 错误写法 | 正确写法 |
|------|----------|----------|
| 变量引用未加引号 | `if [ $a = "x" ]` | `if [ "$a" = "x" ]` |
| 路径空格 | `cat $file` | `cat "$file"` |
| 管道中的错误检查 | `cat f \| grep x` | `set -o pipefail` |
| 临时文件清理 | 手动删除 | `trap 'rm -f "$tmp"' EXIT` |
| 子shell变量丢失 | `cat f \| while read l` | `while read l; done < f` |

```bash
# trap 确保清理
cleanup() {
    rm -rf "$TEMP_DIR"
    log_info "清理完成"
}
trap cleanup EXIT INT TERM
```

---

## 四、文本处理三剑客

### 4.1 grep

```bash
# 基本用法
grep "pattern" file.txt                    # 查找包含pattern的行
grep -i "pattern" file.txt                 # 忽略大小写
grep -v "pattern" file.txt                 # 反向匹配
grep -r "pattern" /path/                   # 递归搜索
grep -n "pattern" file.txt                 # 显示行号
grep -c "pattern" file.txt                 # 统计匹配行数
grep -A 3 "pattern" file.txt               # 显示匹配行及后3行
grep -B 3 "pattern" file.txt               # 显示匹配行及前3行
grep -C 3 "pattern" file.txt               # 显示匹配行及前后3行
grep -l "pattern" *.txt                    # 只显示文件名
grep -w "word" file.txt                    # 精确匹配单词
grep -E "pattern1|pattern2" file.txt       # 扩展正则(多模式)

# 实用场景
# 查找Java异常
grep -r "NullPointerException" logs/ --include="*.log"

# 统计ERROR出现次数
grep -c "ERROR" app.log

# 查看ERROR上下文
grep -n -C 5 "ERROR" app.log
```

### 4.2 sed

```bash
# 替换
sed 's/old/new/' file.txt          # 替换每行第一个匹配
sed 's/old/new/g' file.txt         # 全局替换
sed 's/old/new/2' file.txt         # 替换第2个匹配
sed -i 's/old/new/g' file.txt      # 直接修改文件

# 删除
sed '/pattern/d' file.txt          # 删除匹配行
sed '2,5d' file.txt                # 删除2-5行
sed '/^$/d' file.txt               # 删除空行

# 插入/追加
sed '1i\HEADER' file.txt           # 第1行前插入
sed '$a\FOOTER' file.txt           # 最后一行后追加
sed '/pattern/a\NEW LINE' file.txt # 匹配行后追加

# 提取
sed -n '5,10p' file.txt            # 打印5-10行
sed -n '/start/,/end/p' file.txt   # 打印匹配范围

# 实用场景
# 去除行首尾空格
sed 's/^[[:space:]]*//;s/[[:space:]]*$//' file.txt

# 删除注释行
sed '/^#/d;/^$/d' config.conf

# 在第2行后插入
sed '2a\insert text' file.txt
```

### 4.3 awk

```bash
# 基本用法
awk '{print $1, $3}' file.txt             # 打印第1、3列
awk -F':' '{print $1, $NF}' /etc/passwd   # 指定分隔符，$NF是最后一列
awk '/pattern/ {print $0}' file.txt       # 匹配行

# 条件过滤
awk '$3 > 100 {print $1, $3}' data.txt    # 第3列 > 100
awk '$1 ~ /^start/ {print}' file.txt      # 第1列匹配正则
awk 'NR>=5 && NR<=10 {print}' file.txt    # 行号5-10

# 计算
awk '{sum += $3} END {print "总计:", sum}' data.txt
awk '{count[$1]++} END {for(k in count) print k, count[k]}' data.txt

# 内置变量
awk '{print NR, NF, $0}' file.txt
# NR: 当前行号   NF: 当前行列数
# FS: 输入分隔符  OFS: 输出分隔符

# 实用场景
# 统计日志中每个IP的访问次数
awk '{ip[$1]++} END {for(i in ip) print i, ip[i]}' access.log | sort -k2 -nr

# 计算响应时间平均值
awk '{sum+=$NF; count++} END {print sum/count}' logs.txt

# 按分隔符提取JSON中的某个字段
echo '{"name":"test","status":200}' | awk -F'"status":' '{print $2}' | awk -F'[,}]' '{print $1}'
```

### 4.4 三剑客组合实战

```bash
# 统计Nginx日志中状态码为500的URL TOP10
grep ' 500 ' access.log | awk '{print $7}' | sort | uniq -c | sort -nr | head -10

# 分析CPU占用TOP5进程
ps aux | sort -k3 -nr | head -5 | awk '{printf "PID=%s CPU=%.1f%% CMD=%s\n", $2, $3, $11}'

# 批量重命名文件（下划线改连字符）
ls *.txt | sed 's/_/-/g' | while read new; do
    old=$(echo "$new" | sed 's/-/_/g')
    mv "$old" "$new"
done

# 统计代码行数（排除空行和注释）
find . -name "*.java" | xargs cat | grep -v '^\s*$' | grep -v '^\s*//' | wc -l
```

---

## 五、网络诊断工具

### 5.1 常用网络命令速查

| 命令 | 用途 | 常用参数 |
|------|------|----------|
| `netstat` | 查看网络连接、路由表 | -tlnp(TCP监听) -an(所有连接) |
| `ss` | 比netstat更快 | -tlnp -s(统计) -m(内存) |
| `lsof` | 查看进程打开的文件/socket | -i:8080, -p PID |
| `tcpdump` | 抓包分析 | -i eth0 port 80 -w file.pcap |
| `nc` | 网络调试"瑞士军刀" | -l 8080(监听) -vz(端口检测) |
| `curl` | HTTP客户端 | -v(详细) -X POST -H -d |
| `ping` | 连通性检测 | -c 10 -i 0.2 |
| `traceroute` | 路由追踪 | -n -m 30 |
| `mtr` | ping+traceroute | -r(报告模式) |

### 5.2 端口与连接排查

```bash
# 查看某个端口被谁占用
lsof -i :8080
ss -tlnp | grep :8080

# 查看所有ESTABLISHED连接
ss -tn state established

# 查看TIME_WAIT连接数
ss -tan state time-wait | wc -l

# 查看TCP连接状态分布
ss -tan | awk '{print $1}' | sort | uniq -c | sort -nr

# 测试端口是否可达
nc -vz 192.168.1.1 8080
timeout 2 bash -c '</dev/tcp/192.168.1.1/8080' && echo "OPEN" || echo "CLOSED"
```

### 5.3 tcpdump实战

```bash
# 抓取指定端口的HTTP流量
tcpdump -i any -A -s 0 port 80

# 抓取特定主机的流量
tcpdump -i eth0 host 192.168.1.100

# 抓取SYN包（查看连接建立）
tcpdump -i eth0 'tcp[tcpflags] & tcp-syn != 0'

# 保存到文件供Wireshark分析
tcpdump -i eth0 -w capture.pcap port 443

# 实时查看HTTP请求头
tcpdump -A -s 0 'tcp port 80 and (((ip[2:2] - ((ip[0]&0xf)<<2)) - ((tcp[12]&0xf0)>>2)) != 0)'
```

---

## 六、性能分析与调优

### 6.1 strace系统调用追踪

```bash
# 追踪进程的系统调用
strace -p <pid>

# 统计系统调用耗时
strace -c -p <pid>

# 过滤特定调用
strace -e trace=read,write -p <pid>

# 追踪子进程
strace -f -p <pid>

# 追踪网络相关调用
strace -e trace=network -p <pid>

# 输出时间戳
strace -tt -T -p <pid>
```

### 6.2 perf性能分析

```bash
# CPU采样（默认99Hz）
perf record -p <pid> -g -- sleep 30

# 生成火焰图数据
perf script | stackcollapse-perf.pl | flamegraph.pl > flame.svg

# 实时查看性能统计
perf top -p <pid>

# 按事件统计
perf stat -p <pid> -- sleep 10

# 查看缓存未命中
perf stat -e cache-misses,cache-references -p <pid> -- sleep 5
```

### 6.3 系统性能排查清单

| 资源 | 检查命令 | 正常值 | 告警阈值 |
|------|----------|--------|----------|
| CPU | `top`, `mpstat` | <70% | >90% |
| 内存 | `free -h` | available>20% | available<10% |
| 磁盘 | `iostat -x 1` | await<5ms | await>20ms, util>80% |
| 网络 | `sar -n DEV 1` | 带宽充足 | 接近带宽上限 |
| 文件描述符 | `lsof \| wc -l` | <10万 | 接近ulimit |
| 上下文切换 | `vmstat 1` | cs<10万/s | cs>50万/s |
| Load | `uptime` | <CPU核数 | >CPU核数×2 |
| TCP连接 | `ss -s` | - | TIME_WAIT>数万 |

---

## 七、面试高频问题速答

**Q1: epoll为什么比select快？**
A: select每次调用都需要把所有fd从用户态拷贝到内核态，且需要遍历所有fd检查状态。epoll通过红黑树维护fd，只返回就绪的fd，且通过mmap减少拷贝。

**Q2: 什么是C10K问题？如何解决？**
A: C10K是指单机同时处理1万个并发连接。解决方案：I/O多路复用（epoll）+ 非阻塞I/O + 线程池/协程。Nginx、Redis、Netty都是经典实现。

**Q3: TIME_WAIT过多怎么办？**
A: 
1. 调整内核参数：`net.ipv4.tcp_tw_reuse = 1`（客户端复用TIME_WAIT连接）
2. 减少MSL：`net.ipv4.tcp_fin_timeout`（谨慎）
3. 应用层优化：长连接、连接池、服务端主动关闭改为客户端关闭

**Q4: Shell脚本中`[ ]`和`[[ ]]`有什么区别？**
A: `[[ ]]`是bash扩展，功能更强：支持`&&`/`||`逻辑运算、`=~`正则匹配、不需要对变量加引号（不会做单词分割）。`[ ]`是POSIX兼容，兼容性更好。

**Q5: grep、sed、awk各适合什么场景？**
A: grep适合行过滤和选择，sed适合行编辑和替换，awk适合按列处理和数据统计。简单过滤用grep，文本替换用sed，数据分析和报表用awk。

**Q6: Linux如何排查CPU 100%问题？**
A:
1. `top` 找到高CPU的PID
2. `top -H -p <PID>` 找到高CPU的线程TID
3. `printf '%x\n' <TID>` 转16进制
4. `jstack <PID> | grep -A 20 <hex_tid>` 定位到具体代码

---

## 八、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| Socket编程 | TCP/UDP编程模型、三次握手代码体现 | socket/bind/listen/accept, TIME_WAIT |
| I/O多路复用 | select/poll/epoll对比、LT/ET模式 | epoll, Reactor, 红黑树, 就绪链表 |
| Shell脚本 | 严格模式、字符串处理、陷阱避免 | set -euo pipefail, trap, local |
| 三剑客 | grep行过滤、sed文本编辑、awk数据分析 | 正则匹配, 分隔符处理, NR/NF |
| 网络诊断 | ss/lsof/tcpdump/strace | 端口排查, 抓包, 系统调用 |
| 性能调优 | perf/strace/火焰图 | CPU分析, 系统调用追踪 |

**运维开发三大金刚：**
1. **Shell是基本功**：能用脚本自动化的绝不用手工
2. **三剑客是瑞士军刀**：组合使用威力无穷
3. **理解内核是关键**：排查问题不能只停留在应用层

---

> 🎯 **操作系统面试八股文系列完结！** 本系列从进程管理、线程同步、死锁、内存管理、文件系统、Linux内核到网络编程与Shell实战，全面覆盖了操作系统面试的核心知识点。建议结合前六篇系统复习，形成完整的操作系统知识体系。
>
> 📌 **下期预告**：《数据库面试八股文（十一）——分布式数据库与NewSQL实战》将深入探讨分布式CAP理论、TiDB架构原理、CockroachDB实战、以及传统RDBMS向NewSQL的演进路线，敬请期待！
