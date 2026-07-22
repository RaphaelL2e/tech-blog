---
title: Linux面试八股文（二）——Shell脚本编程与文本处理
date: 2026-06-13 10:00:00+08:00
updated: '2026-06-13T10:00:00+08:00'
description: 本篇深入Shell脚本编程与文本处理，涵盖Bash语法、流程控制、函数、AWK/SED文本三剑客、正则表达式，以及脚本调试与性能优化，是Linux运维与后端开发的必备技能。 Q：Shell是什么？Bash和其他Shell有什么区别？
  Shell是用户与内核之间的命令解释器，提供命令行交互界面。 数组。
topic: computer-science
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Linux
- Shell
- Bash
categories:
- 计算机基础
draft: false
---

> 本篇深入Shell脚本编程与文本处理，涵盖Bash语法、流程控制、函数、AWK/SED文本三剑客、正则表达式，以及脚本调试与性能优化，是Linux运维与后端开发的必备技能。

---

## 一、Shell脚本基础

### 1.1 Shell与Bash

**Q：Shell是什么？Bash和其他Shell有什么区别？**

Shell是用户与内核之间的命令解释器，提供命令行交互界面。

| Shell类型 | 路径 | 特点 |
|-----------|------|------|
| Bourne Shell (sh) | /bin/sh | 最早的Shell，功能简单 |
| Bash | /bin/bash | 最广泛使用，兼容sh，功能强大 |
| C Shell (csh) | /bin/csh | C语言风格语法 |
| Korn Shell (ksh) | /bin/ksh | 兼容sh，支持高级特性 |
| Z Shell (zsh) | /bin/zsh | 功能最丰富，macOS默认 |
| Fish | /usr/bin/fish | 用户友好，语法不兼容Bash |

**Bash核心优势：**
- 兼容POSIX标准
- 支持命令补全、历史记录、别名
- 丰富的流程控制和函数
- 数组、关联数组（Bash 4+）
- 广泛的社区和脚本生态

```bash
# 查看当前Shell
echo $SHELL
echo $0

# 切换Shell
chsh -s /bin/zsh

# 查看系统支持的Shell
cat /etc/shells
```

### 1.2 脚本执行方式

**Q：Shell脚本有哪几种执行方式？有什么区别？**

| 执行方式 | 命令 | 是否新进程 | 是否需执行权限 | 环境变量影响 |
|----------|------|-----------|---------------|-------------|
| source/. | `source script.sh` | ❌ 当前Shell | ❌ 不需要 | 影响当前Shell |
| bash/sh | `bash script.sh` | ✅ 子进程 | ❌ 不需要 | 不影响当前Shell |
| 路径执行 | `./script.sh` | ✅ 子进程 | ✅ 需要 | 不影响当前Shell |

```bash
# 方式1：source（在当前Shell中执行）
source ./config.sh
. ./config.sh    # 等价写法

# 方式2：显式指定解释器
bash ./script.sh
sh ./script.sh

# 方式3：路径执行（需执行权限）
chmod +x ./script.sh
./script.sh
```

**关键区别：**
- `source`常用于加载环境变量（如`source ~/.bashrc`）
- 子进程方式中的变量修改不会影响父Shell
- 推荐在脚本首行添加Shebang：`#!/bin/bash`

### 1.3 变量与数据类型

**Q：Shell中的变量有哪些类型？作用域如何？**

```bash
# 1. 局部变量（仅当前Shell可见）
local_var="hello"

# 2. 环境变量（子进程可见）
export GLOBAL_VAR="world"

# 3. 只读变量
readonly PI=3.14159

# 4. 特殊变量
echo "脚本名: $0"
echo "第一个参数: $1"
echo "参数个数: $#"
echo "所有参数: $@"
echo "所有参数(字符串): $*"
echo "上一个命令退出码: $?"
echo "当前Shell PID: $$"
echo "后台进程 PID: $!"

# $@ vs $* 区别
set -- "a b" c d
echo '$*:' "$*"    # a b c d（合并为一个字符串）
echo '$@:' "$@"    # a b c d（保持参数分割）

# 5. 变量默认值
echo ${var:-"default"}    # var未设置时返回default，不修改var
echo ${var:="default"}    # var未设置时赋值并返回default
echo ${var:+"set"}        # var已设置时返回set
echo ${var:?"not set"}    # var未设置时报错退出
```

### 1.4 字符串操作

**Q：Shell中如何进行字符串操作？**

```bash
str="Hello World Shell Programming"

# 长度
echo ${#str}                    # 27

# 子串提取
echo ${str:0:5}                 # Hello（从0开始，取5个）
echo ${str:6}                   # World Shell Programming
echo ${str: -7}                 # gramming（最后7个字符）

# 替换
echo ${str/World/Linux}         # Hello Linux Shell Programming（替换第一个）
echo ${str//l/L}                # HeLLo WorLd SheLL Programming（替换所有）

# 删除（通配符匹配）
file="archive.tar.gz"
echo ${file#*.}                 # tar.gz（从头部删除最短匹配）
echo ${file##*.}                # gz（从头部删除最长匹配）
echo ${file%.*}                 # archive.tar（从尾部删除最短匹配）
echo ${file%%.*}               # archive（从尾部删除最长匹配）

# 大小写转换（Bash 4+）
echo ${str^^}                   # 全部大写
echo ${str,,}                   # 全部小写
echo ${str~~}                   # 大小写互换
```

---

## 二、流程控制

### 2.1 条件判断

**Q：Shell中如何进行条件判断？`test`、`[]`和`[[]]`有什么区别？**

| 特性 | test / [ ] | [[ ]] |
|------|-----------|-------|
| POSIX兼容 | ✅ | ❌ (Bash扩展) |
| 逻辑运算 | `-a` / `-o` | `&&` / `||` |
| 模式匹配 | ❌ | ✅ `[[ $str == pattern* ]]` |
| 正则匹配 | ❌ | ✅ `[[ $str =~ regex ]]` |
| 空格要求 | 严格 | 宽松 |
| 分词问题 | 需引号保护 | 自动处理 |

```bash
# 数值比较
[ $a -eq $b ]    # 等于
[ $a -ne $b ]    # 不等于
[ $a -gt $b ]    # 大于
[ $a -ge $b ]    # 大于等于
[ $a -lt $b ]    # 小于
[ $a -le $b ]    # 小于等于

# 字符串比较
[ -z "$str" ]           # 为空
[ -n "$str" ]           # 非空
[ "$str1" = "$str2" ]   # 相等
[ "$str1" != "$str2" ]  # 不等

# 文件判断
[ -f file ]    # 是否为普通文件
[ -d dir ]     # 是否为目录
[ -e path ]    # 是否存在
[ -r file ]    # 是否可读
[ -w file ]    # 是否可写
[ -x file ]    # 是否可执行
[ -s file ]    # 是否非空文件

# [[ ]] 高级用法
[[ $str == hello* ]]          # 通配符匹配
[[ $str =~ ^[0-9]+$ ]]        # 正则匹配
[[ $a > $b ]]                 # 字典序比较
```

### 2.2 分支语句

```bash
# if-elif-else
if [[ $score -ge 90 ]]; then
    echo "优秀"
elif [[ $score -ge 80 ]]; then
    echo "良好"
elif [[ $score -ge 60 ]]; then
    echo "及格"
else
    echo "不及格"
fi

# case语句
case $os in
    "ubuntu"|"debian")
        apt-get update
        ;;
    "centos"|"rhel")
        yum update
        ;;
    "arch")
        pacman -Syu
        ;;
    *)
        echo "Unsupported OS: $os"
        exit 1
        ;;
esac

# select菜单
select item in "安装" "配置" "启动" "退出"; do
    case $item in
        "安装") make install ;;
        "配置") vim config.ini ;;
        "启动") systemctl start app ;;
        "退出") break ;;
    esac
done
```

### 2.3 循环语句

```bash
# for循环
# 风格1：列表遍历
for i in 1 2 3 4 5; do
    echo $i
done

# 风格2：C语言风格
for ((i=0; i<10; i++)); do
    echo $i
done

# 风格3：遍历文件
for file in /etc/*.conf; do
    echo "Processing: $file"
done

# while循环
count=0
while [[ $count -lt 10 ]]; do
    echo $count
    ((count++))
done

# 读取文件
while IFS= read -r line; do
    echo "$line"
done < input.txt

# until循环（条件为假时执行）
until [[ -f /tmp/done ]]; do
    sleep 1
done
echo "文件已创建"

# 循环控制
for i in {1..100}; do
    [[ $((i % 2)) -ne 0 ]] && continue   # 跳过奇数
    [[ $i -eq 20 ]] && break              # 到20退出
    echo $i
done
```

---

## 三、数组和函数

### 3.1 数组

**Q：Bash数组有哪些用法？**

```bash
# 索引数组
arr=(apple banana cherry)
arr+=(date)                   # 追加元素
echo ${arr[0]}                # apple
echo ${arr[@]}                # 所有元素
echo ${#arr[@]}               # 元素个数 4
echo ${!arr[@]}               # 所有索引 0 1 2 3

# 遍历数组
for item in "${arr[@]}"; do
    echo "$item"
done

# 切片
echo ${arr[@]:1:2}            # banana cherry

# 关联数组（Bash 4+）
declare -A map
map[name]="张三"
map[age]=25
map[city]="北京"

echo ${map[name]}             # 张三
echo ${!map[@]}               # name age city（所有键）
echo ${map[@]}                # 张三 25 北京（所有值）

# 遍历关联数组
for key in "${!map[@]}"; do
    echo "$key = ${map[$key]}"
done
```

### 3.2 函数

**Q：Shell函数如何定义和使用？参数和返回值怎么处理？**

```bash
# 定义函数
greet() {
    local name="$1"           # local限定作用域
    local greeting="${2:-你好}"
    echo "$greeting, $name!"
    return 0                  # 返回码（0-255）
}

# 调用
greet "飞哥" "早上好"        # 早上好, 飞哥!
echo $?                       # 0（上一个函数的返回码）

# 获取函数输出（命令替换）
result=$(greet "World")
echo "$result"

# 引用传参（通过nameref）
add_item() {
    local -n arr_ref=$1       # nameref
    arr_ref+=("$2")
}

my_list=(a b)
add_item my_list c
echo "${my_list[@]}"          # a b c

# 递归
factorial() {
    local n=$1
    if [[ $n -le 1 ]]; then
        echo 1
    else
        local prev
        prev=$(factorial $((n-1)))
        echo $((n * prev))
    fi
}

result=$(factorial 5)
echo $result                   # 120
```

---

## 四、文本处理三剑客

### 4.1 GREP——文本过滤

**Q：grep有哪些常用技巧？**

```bash
# 基本用法
grep "pattern" file           # 搜索匹配行
grep -i "pattern" file        # 忽略大小写
grep -v "pattern" file        # 反向匹配（排除）
grep -c "pattern" file        # 统计匹配行数
grep -n "pattern" file        # 显示行号
grep -r "pattern" dir/        # 递归搜索目录
grep -l "pattern" *.txt       # 只输出匹配的文件名
grep -w "word" file           # 全词匹配
grep -A 3 "pattern" file      # 匹配行后3行
grep -B 2 "pattern" file      # 匹配行前2行
grep -C 2 "pattern" file      # 匹配行前后各2行

# 扩展正则（egrep / grep -E）
grep -E "cat|dog" file               # 或匹配
grep -E "go{2,4}d" file              # o出现2-4次
grep -E "[0-9]{1,3}\.[0-9]{1,3}" file  # IP地址模式

# 实用场景
# 1. 搜索代码中的TODO
grep -rn "TODO\|FIXME" --include="*.java" src/

# 2. 搜索进程
ps aux | grep nginx | grep -v grep

# 3. 查找大文件中的错误
grep -E "ERROR|FATAL|Exception" app.log | tail -20

# 4. PCRE模式（grep -P）
grep -P '\b\d{1,3}(\.\d{1,3}){3}\b' access.log   # 精确匹配IP
```

### 4.2 SED——流编辑器

**Q：sed的工作原理是什么？常用操作有哪些？**

sed逐行读取输入，将当前行放入模式空间(Pattern Space)，执行命令后输出，再处理下一行。

```bash
# 基本格式
sed [选项] '命令' 文件

# 常用选项
# -n  只输出处理的行
# -i  直接修改文件（原地编辑）
# -e  多条命令
# -r/-E  扩展正则

# 替换（最常用）
sed 's/old/new/' file                # 替换每行第一个
sed 's/old/new/g' file               # 替换所有
sed 's/old/new/2' file               # 替换每行第2个
sed 's/old/new/gi' file              # 忽略大小写替换所有
sed -i 's/old/new/g' file            # 原地修改

# 指定行
sed '3s/old/new/' file               # 只替换第3行
sed '2,5s/old/new/g' file            # 替换2-5行
sed '/pattern/s/old/new/g' file      # 匹配pattern的行才替换
sed '/^#/d' file                     # 删除注释行
sed '/^$/d' file                     # 删除空行

# 增删改
sed '2a\新行内容' file               # 第2行后追加
sed '2i\新行内容' file               # 第2行前插入
sed '2d' file                        # 删除第2行
sed '2c\替换内容' file               # 替换第2行

# 高级用法
# 1. 多命令
sed -e 's/foo/bar/g' -e 's/baz/qux/g' file

# 2. 使用持有空间（Hold Space）
# 将所有匹配行合并为一行
sed -n '/START/,/END/{H;/END/{g;s/\n/ /g;p}}' file

# 3. 反向引用
echo "2024-01-15" | sed -E 's/([0-9]{4})-([0-9]{2})-([0-9]{2})/\2\/\3\/\1/'
# 输出: 01/15/2024

# 4. 删除HTML标签
sed 's/<[^>]*>//g' index.html

# 5. 给行加行号
sed '=' file | sed 'N;s/\n/\t/'
```

### 4.3 AWK——文本分析

**Q：awk的编程模型和常用技巧？**

awk是一种强大的文本处理语言，按行和列处理结构化文本。

```bash
# 基本格式
awk 'BEGIN{初始化} /模式/{动作} END{收尾}' 文件

# 内置变量
# $0      整行
# $1-$NF  各列
# NR      当前行号
# NF      当前列数
# FS      输入列分隔符（默认空格）
# RS      输入行分隔符（默认换行）
# OFS     输出列分隔符
# ORS     输出行分隔符

# 常用操作
# 1. 打印列
awk '{print $1, $3}' file            # 打印第1和3列
awk '{print NR": "$0}' file          # 带行号打印

# 2. 指定分隔符
awk -F: '{print $1}' /etc/passwd     # 以冒号分隔
awk -F'[,\t]' '{print $1,$2}' file   # 逗号或Tab分隔

# 3. 条件过滤
awk '$3 > 100 {print $1, $3}' data.txt     # 第3列>100
awk '/error/ {print}' app.log               # 包含error的行
awk 'NR>=10 && NR<=20' file                 # 第10-20行

# 4. 统计计算
# 求和
awk '{sum+=$1} END{print "Total:", sum}' numbers.txt

# 平均值
awk '{sum+=$1; count++} END{print "Avg:", sum/count}' data.txt

# 最大值/最小值
awk 'NR==1 || $1>max {max=$1} END{print "Max:", max}' data.txt

# 5. 分组统计
# 统计每个IP的访问次数
awk '{count[$1]++} END{for(ip in count) print ip, count[ip]}' access.log | sort -k2 -nr

# 6. 格式化输出
awk -F: 'BEGIN{printf "%-20s %-10s\n", "用户", "Shell"} {printf "%-20s %-10s\n", $1, $7}' /etc/passwd

# 7. 数组与函数
awk '
{
    split($0, parts, "/")
    month = parts[2]
    traffic[month] += $10
}
END {
    for (m in traffic) {
        printf "%s: %.2f GB\n", m, traffic[m]/1024/1024
    }
}' access.log
```

### 4.4 三剑客对比

**Q：grep、sed、awk各自适用什么场景？**

| 工具 | 核心能力 | 适用场景 | 复杂度 |
|------|---------|---------|--------|
| grep | 文本过滤/搜索 | 快速查找、日志过滤 | 低 |
| sed | 流编辑/替换 | 批量替换、行编辑 | 中 |
| awk | 列处理/统计分析 | 报表生成、数据统计 | 高 |

```bash
# 组合使用：统计Nginx访问日志中Top 10 IP
cat access.log \
    | awk '{print $1}' \
    | sort \
    | uniq -c \
    | sort -nr \
    | head -10

# 组合使用：提取日志中的异常信息
grep -E "ERROR|Exception" app.log \
    | sed 's/\[.*\] //' \
    | awk '{count[$0]++} END{for(msg in count) print count[msg], msg}' \
    | sort -nr \
    | head -20
```

---

## 五、正则表达式

### 5.1 基础正则(BRE)与扩展正则(ERE)

**Q：BRE和ERE有什么区别？**

| 特性 | BRE | ERE |
|------|-----|-----|
| `+` 量词 | 需转义 `\+` | 直接使用 `+` |
| `?` 量词 | 需转义 `\?` | 直接使用 `?` |
| `{n,m}` | 需转义 `\{n,m\}` | 直接使用 `{n,m}` |
| `()` 分组 | 需转义 `\(\)` | 直接使用 `()` |
| `\|` 或 | 需转义 `\|` | 直接使用 `\|` |

### 5.2 常用正则模式

```bash
# 1. 数字
[0-9]+                        # 一个或多个数字
^[0-9]+$                      # 纯数字字符串
^-?[0-9]+\.?[0-9]*$          # 可选负号的小数

# 2. 邮箱
^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$

# 3. IP地址
^([0-9]{1,3}\.){3}[0-9]{1,3}$

# 4. 日期
^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$

# 5. 中文字符
[\u4e00-\u9fa5]+

# 6. 常见日志模式
# 提取时间戳
grep -oP '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}' app.log

# 提取HTTP状态码
grep -oP 'HTTP/\d\.\d" \K\d{3}' access.log
```

---

## 六、脚本调试与优化

### 6.1 调试技巧

**Q：Shell脚本有哪些调试方法？**

```bash
# 1. 使用-x选项（跟踪执行）
bash -x script.sh             # 执行时打印每条命令
# 在脚本中局部启用
set -x                        # 开启跟踪
# ... 需要调试的代码
set +x                        # 关闭跟踪

# 2. 使用-n选项（语法检查）
bash -n script.sh             # 只检查语法，不执行

# 3. 使用-v选项（显示读取的行）
bash -v script.sh

# 4. trap调试
trap 'echo "LINE $LINENO: $BASH_COMMAND"' DEBUG

# 5. 错误处理
set -e                        # 命令失败即退出
set -u                        # 使用未定义变量即退出
set -o pipefail               # 管道中任一命令失败即退出

# 推荐组合（脚本开头）
#!/bin/bash
set -euo pipefail

# 6. 日志函数
log() {
    local level=$1; shift
    local msg="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $msg"
}

log INFO "开始处理数据"
log WARN "磁盘空间不足"
log ERROR "连接数据库失败"
```

### 6.2 性能优化

**Q：Shell脚本如何优化性能？**

```bash
# 1. 减少外部命令调用
# 慢：每次调用外部命令
for i in {1..1000}; do
    result=$(echo "$i * 2" | bc)
done

# 快：使用内置算术
for i in {1..1000}; do
    result=$((i * 2))
done

# 2. 减少管道和子Shell
# 慢：子Shell + 管道
while read line; do
    echo "$line"
done < <(cat file)

# 快：直接重定向
while IFS= read -r line; do
    echo "$line"
done < file

# 3. 使用内置字符串操作代替sed
# 慢
result=$(echo "$str" | sed 's/old/new/g')

# 快
result="${str//old/new}"

# 4. 批量处理代替循环
# 慢：逐个处理
for f in *.txt; do
    process "$f"
done

# 快：xargs并行
find . -name "*.txt" -print0 | xargs -0 -P4 -I{} process "{}"

# 5. 避免重复计算
# 缓存结果
cached_date=$(date +%Y%m%d)
for i in {1..100}; do
    echo "$cached_date-$i"
done
```

### 6.3 最佳实践

```bash
#!/bin/bash
# 脚本模板

set -euo pipefail

# 常量定义
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly LOG_FILE="/var/log/${SCRIPT_NAME%.*}.log"

# 帮助信息
usage() {
    cat <<EOF
用法: $SCRIPT_NAME [选项] <参数>

选项:
    -h, --help      显示帮助信息
    -v, --verbose   详细输出模式
    -d, --dry-run   试运行模式

示例:
    $SCRIPT_NAME -v input.txt
EOF
    exit 0
}

# 参数解析
VERBOSE=0
DRY_RUN=0
INPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)    usage ;;
        -v|--verbose) VERBOSE=1; shift ;;
        -d|--dry-run) DRY_RUN=1; shift ;;
        -*)           echo "未知选项: $1"; usage ;;
        *)            INPUT_FILE="$1"; shift ;;
    esac
done

# 主逻辑
main() {
    [[ -z "$INPUT_FILE" ]] && { echo "错误: 请指定输入文件"; usage; }
    [[ ! -f "$INPUT_FILE" ]] && { echo "错误: 文件不存在: $INPUT_FILE"; exit 1; }
    
    log INFO "开始处理: $INPUT_FILE"
    # ... 业务逻辑
    log INFO "处理完成"
}

main "$@"
```

---

## 七、实战场景

### 7.1 日志分析脚本

```bash
#!/bin/bash
# analyze_log.sh - Nginx日志分析

set -euo pipefail

LOG_FILE="${1:-access.log}"

echo "===== Nginx日志分析报告 ====="
echo "分析文件: $LOG_FILE"
echo "分析时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "--- 1. 总请求量 ---"
total=$(wc -l < "$LOG_FILE")
echo "总请求: $total"

echo ""
echo "--- 2. TOP 10 访问IP ---"
awk '{print $1}' "$LOG_FILE" | sort | uniq -c | sort -nr | head -10

echo ""
echo "--- 3. HTTP状态码分布 ---"
awk '{print $9}' "$LOG_FILE" | sort | uniq -c | sort -nr

echo ""
echo "--- 4. TOP 10 访问路径 ---"
awk '{print $7}' "$LOG_FILE" | sort | uniq -c | sort -nr | head -10

echo ""
echo "--- 5. 每小时请求量 ---"
awk -F'[' '{print substr($2,1,13)}' "$LOG_FILE" | sort | uniq -c

echo ""
echo "--- 6. 平均响应时间 ---"
awk '{sum+=$NF; count++} END{printf "%.2f ms\n", sum/count}' "$LOG_FILE"

echo ""
echo "--- 7. 4xx/5xx错误 ---"
awk '$9>=400 {print $9, $7}' "$LOG_FILE" | sort | uniq -c | sort -nr | head -20
```

### 7.2 自动化部署脚本

```bash
#!/bin/bash
# deploy.sh - 自动化部署脚本

set -euo pipefail

APP_NAME="myapp"
DEPLOY_DIR="/opt/$APP_NAME"
BACKUP_DIR="/opt/backups/$APP_NAME"
REPO_URL="git@github.com:org/$APP_NAME.git"
BRANCH="${1:-main}"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# 1. 备份当前版本
backup() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    if [[ -d "$DEPLOY_DIR" ]]; then
        mkdir -p "$BACKUP_DIR"
        cp -r "$DEPLOY_DIR" "$BACKUP_DIR/$timestamp"
        log "备份完成: $BACKUP_DIR/$timestamp"
    fi
}

# 2. 拉取代码
pull_code() {
    if [[ -d "$DEPLOY_DIR/.git" ]]; then
        cd "$DEPLOY_DIR"
        git fetch origin
        git reset --hard "origin/$BRANCH"
    else
        git clone -b "$BRANCH" "$REPO_URL" "$DEPLOY_DIR"
        cd "$DEPLOY_DIR"
    fi
    log "代码更新完成: $(git rev-parse --short HEAD)"
}

# 3. 构建
build() {
    cd "$DEPLOY_DIR"
    mvn clean package -DskipTests -q
    log "构建完成"
}

# 4. 重启服务
restart() {
    sudo systemctl restart "$APP_NAME"
    sleep 5
    if sudo systemctl is-active --quiet "$APP_NAME"; then
        log "服务启动成功 ✓"
    else
        log "服务启动失败 ✗"
        log "回滚到上一版本..."
        # 回滚逻辑
        exit 1
    fi
}

# 5. 健康检查
health_check() {
    local max_retries=10
    local retry=0
    while [[ $retry -lt $max_retries ]]; do
        if curl -sf http://localhost:8080/actuator/health > /dev/null; then
            log "健康检查通过 ✓"
            return 0
        fi
        ((retry++))
        log "等待服务就绪... ($retry/$max_retries)"
        sleep 3
    done
    log "健康检查失败 ✗"
    return 1
}

# 主流程
main() {
    log "===== 开始部署 $APP_NAME ====="
    backup
    pull_code
    build
    restart
    health_check
    log "===== 部署完成 ====="
}

main "$@"
```

---

## 八、面试高频问题

### Q1：如何实现多进程并发？

```bash
#!/bin/bash
# 并发处理示例

process_task() {
    local task_id=$1
    echo "开始任务 $task_id (PID: $$)"
    sleep $((RANDOM % 5 + 1))
    echo "完成任务 $task_id"
}

# 方式1：后台进程 + wait
for i in {1..10}; do
    process_task $i &
done
wait    # 等待所有后台任务完成
echo "所有任务完成"

# 方式2：控制并发数
MAX_PARALLEL=4
running=0
for i in {1..20}; do
    process_task $i &
    ((running++))
    if [[ $running -ge $MAX_PARALLEL ]]; then
        wait -n    # 等待任意一个完成
        ((running--))
    fi
done
wait

# 方式3：使用GNU parallel
# parallel -j 4 process_task ::: {1..20}

# 方式4：文件描述符控制
MAX_JOBS=4
mkfifo /tmp/fifo_$$
exec 6<>/tmp/fifo_$$
rm /tmp/fifo_$$

for ((i=0; i<MAX_JOBS; i++)); do
    echo >&6    # 写入MAX_JOBS个令牌
done

for item in $(seq 1 20); do
    read -u 6   # 获取令牌
    {
        process_task $item
        echo >&6 # 归还令牌
    } &
done
wait
exec 6>&-      # 关闭文件描述符
```

### Q2：`$@`和`$*`有什么区别？

```bash
show_args() {
    echo "使用 \"\$*\":"
    for arg in "$*"; do
        echo "  [$arg]"
    done
    echo ""
    echo "使用 \"\$@\":"
    for arg in "$@"; do
        echo "  [$arg]"
    done
}

show_args "hello world" "foo bar" "baz"

# 输出:
# 使用 "$*":
#   [hello world foo bar baz]     # 所有参数合并为一个字符串
#
# 使用 "$@":
#   [hello world]                  # 保持原始参数分割
#   [foo bar]
#   [baz]
```

**关键点：** 在双引号中使用时，`"$@"`保持每个参数独立，`"$*"`合并为一个字符串。**推荐始终使用`"$@"`**。

### Q3：如何捕获和处理信号？

```bash
#!/bin/bash
# 信号处理

cleanup() {
    echo ""
    echo "收到信号，正在清理..."
    rm -f /tmp/myapp_*.tmp
    echo "清理完成，退出"
    exit 0
}

# 捕获SIGINT(2), SIGTERM(15), EXIT
trap cleanup SIGINT SIGTERM

echo "进程PID: $$"
echo "按 Ctrl+C 触发信号处理..."

while true; do
    echo "运行中... $(date '+%H:%M:%S')"
    sleep 2
done
```

### Q4：如何实现进度条？

```bash
#!/bin/bash
# 进度条实现

progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local percent=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))
    
    printf "\r["
    printf "%${filled}s" | tr ' ' '='
    printf "%${empty}s" | tr ' ' ' '
    printf "] %3d%% (%d/%d)" "$percent" "$current" "$total"
}

total=100
for i in $(seq 1 $total); do
    progress_bar $i $total
    sleep 0.05
done
echo ""
echo "完成！"
```

---

## 九、总结

| 主题 | 核心要点 |
|------|---------|
| Shell基础 | 变量类型、作用域、特殊变量、字符串操作 |
| 流程控制 | `[[]]`优于`[]`、for/while/until循环 |
| 数组函数 | 索引数组/关联数组、local变量、nameref |
| 文本三剑客 | grep过滤、sed替换、awk统计分析 |
| 正则表达式 | BRE vs ERE、常用模式、PCRE |
| 调试优化 | set -euo pipefail、减少外部命令、xargs并行 |
| 实战场景 | 日志分析、自动化部署、并发控制 |

> 🔗 下一篇：**Linux面试八股文（三）——Linux网络配置与服务管理**，将深入Linux网络配置、防火墙、系统服务管理、性能监控与故障排查，敬请期待！
