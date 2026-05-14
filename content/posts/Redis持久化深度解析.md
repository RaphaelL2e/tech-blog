---
title: "Redis 持久化深度解析"
date: 2026-05-14T19:00:00+08:00
draft: false
categories: ["Redis"]
tags: ["Redis", "持久化", "RDB", "AOF", "混合持久化", "数据恢复"]
---

# Redis 持久化深度解析

## 一、引言

Redis 作为内存数据库，数据存储在内存中。为了在服务器重启后能够恢复数据，Redis 提供了两种持久化机制：**RDB（Redis DataBase）** 和 **AOF（Append Only File）**。理解持久化原理对于生产环境数据安全至关重要，也是面试高频考点。

**本文要点**：
1. RDB 持久化原理与配置
2. AOF 持久化原理与配置
3. RDB 与 AOF 对比与选择
4. 混合持久化策略
5. 数据恢复实战

---

## 二、RDB 持久化

### 2.1 RDB 原理

RDB 持久化会定时将内存中的数据快照保存到磁盘上的 `dump.rdb` 文件中。

**工作机制**：
```
Redis 定期检查 → 生成子进程 → 内存数据写入 RDB 文件 → 替换旧文件
```

**触发机制**：

| 触发方式 | 配置 | 说明 |
|----------|------|------|
| 定时触发 | `save <seconds> <changes>` | 默认 `save 900 1 save 300 10 save 60 10000` |
| 手动触发 | `BGSAVE` | 后台异步执行 |
| 手动触发 | `SAVE` | 阻塞主进程（生产禁用） |
| 关机触发 | `shutdown` | 正常关机时自动触发 |

**配置文件**：

```bash
# redis.conf
# RDB 文件名
dbfilename dump.rdb

# RDB 文件保存目录
dir ./

# 是否压缩 RDB 文件
rdbcompression yes

# 是否校验 RDB 文件
rdbchecksum yes

# 触发规则（满足任一即触发）
save 900 1      # 900 秒内至少 1 次修改
save 300 10     # 300 秒内至少 10 次修改
save 60 10000   # 60 秒内至少 10000 次修改
```

### 2.2 RDB 优缺点

**优点**：
- 文件紧凑，适合备份与灾难恢复
- 恢复速度快（加载 RDB 文件即可）
- 适合做数据镜像备份

**缺点**：
- 定时触发，存在数据丢失风险（丢失最近一段时间的数据）
- fork() 子进程会有内存膨胀
- 数据量大会导致恢复时间较长

---

## 三、AOF 持久化

### 3.1 AOF 原理

AOF 持久化将每个写操作命令追加到日志文件，只记录写操作，不记录读操作。

**工作流程**：
```
客户端发送写命令 → 主进程写入 AOF 缓冲区 → 同步磁盘
```

**配置文件**：

```bash
# redis.conf
# 开启 AOF 持久化
appendonly yes

# AOF 文件名
appendfilename "appendonly.aof"

# AOF 同步策略
appendfsync always     # 每次写命令都同步（最安全，性能最差）
appendfsync everysec # 每秒同步（推荐，默认）
appendfsync no        # 由操作系统决定（性能最好，风险最大）

# AOF 重写压缩
auto-aof-rewrite-percentage 100  # AOF 文件比上次大 100% 时触发重写
auto-aof-rewrite-min-size 64mb  # AOF 文件大于 64MB 时才可能触发重写

# AOF 日志格式
aof-use-rdb-preamble yes  # 混合持久化（推荐）
```

### 3.2 AOF 重写

随着时间推移，AOF 文件会越来越大。Redis 提供重写机制压缩 AOF 文件。

**触发机制**：

| 触发方式 | 说明 |
|----------|------|
| 自动触发 | 满足 `auto-aof-rewrite-percentage` 和 `auto-aof-rewrite-min-size` |
| 手动触发 | `BGREWRITEAOF` |

**重写原理**：
```
读取现有数据状态 → 生成最小写操作 → 写入新 AOF 文件 → 替换旧文件
```

**重写流程**：
```bash
# 查看 AOF 重写状态
INFO persistence

# 手动触发重写
BGREWRITEAOF
```

### 3.3 AOF 优缺点

**优点**：
- 数据安全性更高（可配置同步策略）
- 文件��读（文本格式）
- 支持混合持久化

**缺点**：
- 文件比 RDB 大
- 写入性能略有影响
- 需要定期重写压缩

---

## 四、RDB vs AOF 对比

| 特性 | RDB | AOF |
|------|-----|-----|
| 文件大小 | 小（紧凑） | 大（包含所有写命令） |
| 恢复速度 | 快 | 慢（需要重放命令） |
| 数据安全性 | 丢失数据多 | 丢失数据少 |
| 性能影响 | 低 | 中 |
| 可读性 | 二进制 | 文本 |
| 支持混合持久化 | - | 是 |

---

## 五、混合持久化（推荐）

Redis 4.0+ 支持混合持久化，结合 RDB 和 AOF 的优点。

**配置**：

```bash
# 开启混合持久化
aof-use-rdb-preamble yes

# 必须先开启 AOF
appendonly yes
```

**原理**：
- 重写时：先以 RDB 格式写入数据，然后追加 AOF 日志
- 恢复时：自动识别 RDB 头，优先加载 RDB 部分

**优势**：
- 恢复速度快（RDB 部分）
- 数据完整（AOF 部分）
- 文件大小适中

**推荐配置**：

```bash
# 推荐生产环境配置
appendonly yes
appendfsync everysec
aof-use-rdb-preamble yes
save 900 1
save 300 10
save 60 10000
```

---

## 六、数据恢复实战

### 6.1 配置 RDB 备份

```bash
# 设置备份目录
dir /data/redis-backup

# 备份脚本（Crontab）
0 2 * * * /usr/local/bin/redis-cli BGSAVE
```

### 6.2 恢复数据

**方式一：从 RDB 文件恢复**

```bash
# 1. 停止 Redis
redis-cli shutdown

# 2. 备份现有文件
cp dump.rdb dump.rdb.bak

# 3. 替换 RDB 文件
cp /path/to/backup/dump.rdb ./

# 4. 启动 Redis
redis-server
```

**方式二：从 AOF 文件恢复**

```bash
# 1. 停止 Redis
redis-cli shutdown

# 2. 确保 AOF 文件存在
ls appendonly.aof

# 3. 启动 Redis（自动加载 AOF）
redis-server
```

### 6.3 检查数据完整性

```bash
# 检查 Redis 数据
redis-cli INFO keyspace

# 检查 key 数量
redis-cli DBSIZE

# 检查大 key
redis-cli --bigkeys
```

---

## 七、总结

**持久化选择建议**：

| 场景 | 推荐策略 |
|------|--------|
| 开发/测试 | RDB |
| 生产环境 | 混合持久化（AOF + RDB） |
| 数据安全要求高 | AOF + 主从 |
| 追求性能 | RDB |

**最佳实践**：
1. 生产环境开启混合持久化
2. 定期备份 RDB 文件到远程存储
3. 主从部署保证高可用
4. 监控 AOF 重写状态
5. 定期检查备份文件可用性

---

**相关文章**：
- [Redis 缓存问题深度解析](/posts/Redis缓存问题深度解析/)
- [Redis 性能优化与实战](/posts/Redis性能优化与实战/)
- [Redis 主从复制与高可用深度解析](/posts/Redis主从复制与高可用深度解析/)

---

**本文重点总结**：

| 持久化方式 | 原理 | 优点 | 缺点 | 适用场景 |
|------------|------|------|------|----------|
| RDB | 定时快照 | 恢复快、文件小 | 可能丢数据 | 开发/备份 |
| AOF | 记录命令 | 数据安全 | 文件大、性能略低 | 生产环境 |
| 混合持久化 | RDB+AOF | 取长补短 | 配置复杂 | 生产推荐 |

---

*你对 Redis 持久化有什么疑问吗？欢迎在评论区交流！* 🦐