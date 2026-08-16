---
title: 操作系统面试八股文（八）——一次IO悬停故障的排查复盘
date: 2026-08-16 10:00:00+08:00
updated: '2026-08-16T10:00:00+08:00'
description: '面试高频问题：服务器突然IO延迟飙升怎么排查？iostat显示%util 100%但CPU不高是什么情况？磁盘队列深度是什么？线上遇到IO hang该如何定位根因？本文以一次真实生产事故为线索，系统讲解Linux IO子系统的监控、分析与调优方法。
  Q: iostat显示await很高但CPU IO Wait不高，说明什么？'
topic: computer-science
series: operating-system
series_order: 8
level: intermediate
status: maintained
tags:
- 操作系统
- Linux
- IO
- 故障排查
- 性能调优
categories:
- 计算机基础
draft: false
author: 飞哥
---

> 面试高频问题：服务器突然IO延迟飙升怎么排查？iostat显示%util 100%但CPU不高是什么情况？磁盘队列深度是什么？线上遇到IO hang该如何定位根因？本文以一次真实生产故障为线索，系统讲解Linux IO子系统的监控、分析与调优方法。

---

## 一、事故背景：凌晨的告警

凌晨3点，你被值班告警电话叫醒。监控大屏上显示：某台数据库服务器 IO 延迟从平时的 2ms 飙升到 8000ms，业务开始出现超时。SSH 登录上去之后，`top` 显示 CPU us 很低（3%），但 Load Average 飙到了 42——机器几乎失去了响应。

这就是典型的 **IO Hang** 场景。CPU 在等待 IO，系统调度器把大量进程放到了等待队列里。机器没有死，但它比死了还难受——所有依赖这台机器的业务都在超时。

> **面试高频问题：Load Average 很高但 CPU 利用率很低，说明什么？**
> 
> 答案：大量进程处于不可中断睡眠状态（D状态），通常是在等待磁盘、网络文件系统或其他外设 IO。这往往是 IO 瓶颈的信号。

---

## 二、第一现场：iostat 的正确打开方式

排查 IO 问题的标准入口是 `iostat -xz 1`。我们来看看关键指标分别代表什么。

```bash
$ iostat -xz 1
Linux 5.4.0-210-generic (db-server)   08/16/2026     _x86_64_        (32 CPU)

avg-cpu:  %user   %nice %system %iostat %wait   %idle
           2.1     0.0     1.2     5.3     1.4    90.0

Device:   r/s     w/s     rkB/s   wkB/s    avgrq-sz avgqu-sz   await  %util
sda       12.00   245.00  600.00  9800.00  41.23    12.45     48.32  99.80
```

**核心字段解读：**

| 字段 | 含义 | 正常范围 | 告警阈值 |
|------|------|----------|----------|
| `r/s` `w/s` | 每秒读写次数 | 取决于业务 | >1000需关注 |
| `rkB/s` `wkB/s` | 每秒读写KB数 | — | — |
| `avgqu-sz` | 平均队列深度 | <2 | >8 严重 |
| `await` | 平均IO等待时间(ms) | <10ms | >100ms |
| `%util` | 设备利用率 | <60% | >90% 饱和 |

> **面试高频问题：%util 100% 是不是说明磁盘已经彻底满了？**
> 
> 答案：不是。`%util` 表示设备在统计周期内处理 IO 请求的时间比例，100% 意味着设备始终处于忙碌状态——它可能每秒只能处理 200 个 IO 请求，而现在有 300 个在排队。`%util 100%` = **设备饱和**，不是磁盘空间用完了。

回到我们的事故现场，`iostat -xz 1` 显示 `avgqu-sz: 12.45`，`await: 48.32ms`，`%util: 99.80%`——磁盘饱和，IO 全在排队。

---

## 三、根因定位：从设备到分区

### 3.1 确定哪个进程在写盘

光知道磁盘饱和不够，还得找出是谁在疯狂 IO。用 `iotop` 定位：

```bash
$ iotop -b -n 1 -o
Total DISK READ:       0.00 B/s | Total DISK WRITE:    8234.56 K/s
TID  PRIO  USER     DISK READ  DISK WRITE  SwapIn  IO>  COMMAND
1502 BE/4  mysql    0.00 B/s  5621.23 K/s  0.00 %  98.56 % mysqld
1890 BE/2  backup   0.00 B/s  2345.78 K/s  0.00 %  41.23 % tar
```

很快定位到两个可疑进程：
- `mysqld` 写入量最大，但这是正常的数据库行为
- `tar` 备份进程在大量写入——这是一个**夜间备份脚本**，在不应该运行的时间点执行了

### 3.2 深入：dmesg 和内核日志

有时候 IO hang 的根因不是业务进程，而是**内核层面**的问题。检查内核环形缓冲区：

```bash
$ dmesg | grep -i "error\|fail\|timeout\|io"
[ 2345.678] sd 0:0:0:0: [sda] tag#0 UNKNOWN status: Result: hostbyte=DID_OK driverbyte=DRIVER_TIMEOUT
[ 2345.678] sd 0:0:0:0: [sda] tag#0 CDB: Write(10) 00 00 00 00 80 00 00 3f 00 00
[ 2345.690]Buffer I/O error on device sda, logical block 123456
```

`DID_OK driverbyte=DRIVER_TIMEOUT` 是关键——**HBA 卡超时**，说明硬件层面出现了问题，可能是：
- SAS/SATA 线路松动
- 硬盘进入异常状态（如 HDD 坏道导致重试）
- RAID 卡缓存失效

> **面试高频问题：磁盘 IO 超时（timeout）的常见原因有哪些？**
> 
> 从外到内依次排查：
> 1. **硬件层**：HBA 卡故障、SAS/SATA 线缆问题、硬盘坏道、RAID 卡缓存失效
> 2. **驱动层**：驱动版本 bug、驱动参数设置不当（如 `nr_requests`）
> 3. **内核层**：IO 调度器策略不适合（SSD 用 `deadline`/`noop` 优于 `cfq`）
> 4. **文件系统层**：fsck 锁定、大量 Journal 写入、ext4 `data=journal` 模式开销
> 5. **应用层**：程序发起大量同步写（`O_SYNC`）、错误使用 `dd`/`tar` 等大 IO 操作

---

## 四、IO 调度器：容易被忽视的幕后黑手

### 4.1 调度器选择与场景适配

Linux 提供了多种 IO 调度器（内核 5.0+ 默认是 `mq-deadline` 和 `bfq`），不同场景选择不同：

```bash
# 查看当前调度器
$ cat /sys/block/sda/queue/scheduler
[mq-deadline] kyber bfq none

# 临时切换（重启失效）
$ echo "bfq" > /sys/block/sda/queue/scheduler

# 永久生效（CentOS/RHEL）
$ grubby --update-kernel=ALL --args="elevator=bfq"

# 永久生效（Ubuntu）
$ vim /etc/default/grub
# GRUB_CMDLINE_LINUX="... elevator=bfq"
$ update-grub
```

| 调度器 | 适用场景 | 原理 |
|--------|----------|------|
| `mq-deadline` | 通用场景，SSD/NVMe | 读写分离队列，保证延迟 |
| `bfq` | 桌面/多媒体，低延迟需求 | 基于权重的公平队列 |
| `noop` | 高端存储阵列，裸设备 | 不排序，减少 CPU 开销 |
| `cfq` | 老旧 HDD（已逐步淘汰） | 完全公平队列，基于时间片 |

> **面试高频问题：为什么 NVMe SSD 推荐用 mq-deadline 而不是 cfq？**
> 
> cfq（Completely Fair Queuing）是基于时间片的调度器，设计初衷是给不同进程公平分配 IO 带宽。但它引入的排序和合并逻辑对 NVMe 来说是不必要的开销——NVMe 有自己的多队列机制（`blk-mq`），`mq-deadline` 直接利用多队列优势，减少了内核层的调度开销，延迟更低。

### 4.2 关键内核参数调优

```bash
# 每请求最大 Sector 数（影响单次 IO 大小上限）
cat /sys/block/sda/queue/max_sectors_kb   # 默认 1280KB，可调大到 5120KB

# 队列深度（每个 CPU 队列的请求数）
cat /sys/block/sda/queue/nr_requests      # 默认 64，可调大到 256

# 合并阈值（相邻扇区是否合并）
cat /sys/block/sda/queue/read_ahead_kb    # 默认 128KB

# 调整示例（生产环境需压测验证）
echo 5120 > /sys/block/sda/queue/max_sectors_kb
echo 256  > /sys/block/sda/queue/nr_requests
```

---

## 五、blktrace：IO 链路全景追踪

当常规工具无法定位时，`blktrace` 可以提供 IO 请求的完整链路分析。

```bash
# 安装
$ apt install blktrace

# 采集 10 秒 IO 事件（需要 root）
$ blktrace -d /dev/sda -o /tmp/blk -w 10

# 分析
$ blkparse -i /tmp/blk -d /tmp/blk.bin | less
  8,0   1        1     0.000000000 1502  Q  WS 123456789 + 8 [mysqld]
  8,0   1        2     0.000001234 1502  G  WS 123456789 + 8 [mysqld]
  8,0   1        3     0.000002567 1502  I  WS 123456789 + 8 [mysqld]
  8,0   1        4     0.000005678 1502  D  WS 123456789 + 8 [mysqld]
  8,0   1        5     0.048901234    0  C  WS 123456789 + 8 [0]
```

**blktrace 事件代码解析：**

| 代码 | 含义 |
|------|------|
| `Q` | IO 请求进入块层队列 |
| `G` | 请求被重新映射（DM/LVM） |
| `I` | 请求被放入调度器队列 |
| `D` | 请求下发到硬件 |
| `C` | 请求完成 |

通过 `Q→D` 时间差可以精确测量**调度器排队延迟**，`D→C` 时间差则是**实际磁盘处理时间**。

---

## 六、生产环境 IO 监控实战

### 6.1 prometheus-node-exporter 关键指标

生产环境通常用 Prometheus + node_exporter 采集系统指标，以下是 IO 相关的关键指标：

```promql
# 平均 IO 延迟（毫秒）
rate(node_disk_io_time_seconds_total[5m]) * 1000

# 磁盘队列深度
rate(node_disk_io_now[1m])

# 每秒读写次数
rate(node_disk_reads_completed_total[5m])
rate(node_disk_writes_completed_total[5m])

# 磁盘使用率告警（>80%持续5分钟）
rate(node_disk_io_time_seconds_total[5m]) > 0.8
```

### 6.2 常见故障场景与应对

| 症状 | 可能原因 | 快速处理 |
|------|----------|----------|
| `%util` 100%，`await` 很高 | 磁盘饱和 | 限流/分流/扩容 |
| `%util` 不高但 `avgqu-sz` 很高 | 调度器瓶颈 | 换调度器/调参 |
| `dmesg` 大量 `timeout` | 硬件问题 | 检查线缆/RAID/更换硬盘 |
| `iowait` 高但 `r/s`/`w/s` 不高 | NFS/网络存储延迟 | 检查网络/挂载参数 |
| `IO Wait` 高且 CPU `sy` 高 | 内核 IO 路径瓶颈 | 升级内核/换调度器 |

---

## 七、面试核心问题速记

### Q1: 如何排查 Linux 系统 IO 瓶颈？

**标准排查路径（从外到内）：**

```
1. iostat -xz 1  →  确认是否磁盘饱和（%util/avgqu-sz）
2. iotop -b -n 1 -o  →  定位到具体进程
3. pidstat -d 1  →  看进程的 IO 速率
4. dmesg | tail  →  查内核是否有 IO 错误
5. blktrace（深度分析） →  精确测量 Q→D 和 D→C 延迟
6. lsof -p <pid>  →  看进程打开了哪些文件
```

### Q2: 磁盘队列深度（queue depth）是什么？为什么重要？

磁盘队列深度是**设备一次能接受的未完成 IO 请求数**。现代 NVMe SSD 通常支持 32-256 的队列深度。如果应用发的 IO 速率超过队列深度，请求就会在驱动层排队，导致延迟增加。

- 机械 HDD 队列深度通常为 1（一次只能处理一个请求）
- SATA SSD 通常为 32
- NVMe 可达 65536（64K 队列 × 64K 深度）

### Q3: SSD 用什么 IO 调度器？为什么不用 cfq？

现代 Linux（5.0+）默认使用 `mq-deadline`（多队列 deadline），原因：
1. **硬件原生支持多队列**：`blk-mq` 机制直接利用 NVMe 的多队列硬件特性
2. **延迟更低**：`mq-deadline` 读写分离，保证延迟敏感型请求优先
3. **CPU 开销更小**：`cfq` 基于时间片和权重计算，开销较大，不适合高性能存储

### Q4: `O_DIRECT` 和 `O_SYNC` 的区别？

| 标志 | 作用 | 使用场景 |
|------|------|----------|
| `O_DIRECT` | 绕过页缓存，直接与硬件交互 | 数据库（InnoDB）、追求精确控制的场景 |
| `O_SYNC` | 每次 write() 同步到磁盘（通过页缓存刷盘） | 日志、需要强一致性的场景 |

---

## 八、总结

IO Hang 是生产环境中常见但排查链路较长的故障类型。本文的排查思路总结为一句话：**从外到内、从现象到根因、从监控到追踪**。

1. `iostat` 定性（是不是 IO 问题）
2. `iotop` 定位进程（是谁在 IO）
3. `dmesg` 排查硬件（是不是硬件故障）
4. `blktrace` 精确定位（调度器延迟 vs 磁盘处理延迟）
5. 调度器选择和内核参数调优（从根本上减少 IO 延迟）

下次凌晨3点告警响起时，希望你能够胸有成竹，5分钟内定位到根因。

---

**下期预告**

操作系统系列已经覆盖了进程管理、线程同步、死锁、内存管理、文件系统、Linux 内核等核心主题。下一期我们将开启**计算机网络系列**的系统化面试八股文，从物理层到应用层，完整梳理面试中必考的网络知识点。敬请期待。
