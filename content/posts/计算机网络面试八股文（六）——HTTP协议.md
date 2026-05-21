---
title: "计算机网络面试八股文（六）——HTTP协议"
date: 2026-05-22T10:00:00+08:00
draft: false
categories: ["计算机网络"]
tags: ["面试", "八股文", "计算机网络", "HTTP", "HTTPS", "Web"]
---

# 计算机网络面试八股文（六）——HTTP协议

## [](#http概述)HTTP概述

### [](#http的定义)HTTP的定义

HTTP（HyperText Transfer Protocol，超文本传输协议）是Web的核心协议：

- **无状态协议**：每个请求独立，不保存之前的请求信息
- **请求-响应模式**：客户端发送请求，服务器返回响应
- **可靠传输**：基于TCP协议
- **灵活扩展**：通过头部字段扩展功能

### [](#http版本演进)HTTP版本演进

- **HTTP/0.9**：1991年，仅支持GET方法
- **HTTP/1.0**：1996年，新增POST、HEAD方法，支持多媒体
- **HTTP/1.1**：1999年，默认持久连接，管道化
- **HTTP/2**：2015年，多路复用、头部压缩、服务端推送
- **HTTP/3**：2021年，基于QUIC（UDP）

---

## [](#http请求格式)HTTP请求格式

### [](#请求行)请求行

```
GET /index.html HTTP/1.1\r\n
```

格式：`Method URL Version`

### [](#请求方法)请求方法

| 方法 | 说明 | 幂等 |
|------|------|------|
| GET | 请求资源 | 是 |
| POST | 提交数据 | 否 |
| PUT | 上传资源 | 是 |
| DELETE | 删除资源 | 是 |
| HEAD | 仅获取头部 | 是 |
| OPTIONS | 查询支持的选项 | 是 |
| PATCH | 部分修改 | 否 |

> **幂等**：多次执行结果相同

### [](#请求头部)请求头部

```
Host: www.example.com\r\n
User-Agent: Mozilla/5.0\r\n
Accept: text/html,application/json\r\n
Accept-Language: zh-CN,en-US\r\n
Cookie: sessionId=abc123\r\n
\r\n
```

常见头部：
- **Host**：服务器地址
- **User-Agent**：客户端信息
- **Accept**：可接受的媒体类型
- **Cookie**： Cookie信息
- **Content-Type**：请求体类型
- **Content-Length**：请求体长度

---

## [](#http响应格式)HTTP响应格式

### [](#状态行)状态行

```
HTTP/1.1 200 OK\r\n
```

格式：`Version Status-Code Reason-Phrase`

### [](#状态码)状态码

| 状态码 | 含义 | 示例 |
|--------|------|------|
| 1xx | 信息性 | 100 Continue |
| 2xx | 成功 | 200 OK, 204 No Content |
| 3xx | 重定向 | 301 Moved Permanently, 304 Not Modified |
| 4xx | 客户端错误 | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 429 Too Many Requests |
| 5xx | 服务器错误 | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout |

### [](#常见状态码详解)常见状态码详解

**200 OK**：请求成功，响应包含请求的内容

**204 No Content**：请求成功，但不返回内容（用于DELETE操作）

**301 Moved Permanently**：永久重定向，浏览器会缓存新的地址

**302 Found**：临时重定向

**304 Not Modified**：资源未修改，使用缓存（配合ETag/Last-Modified）

**400 Bad Request**：请求语法错误

**401 Unauthorized**：需要认证

**403 Forbidden**：权限不足

**404 Not Found**：资源不存在

**429 Too Many Requests**：请求过于频繁（速率限制）

**500 Internal Server Error**：服务器内部错误

**502 Bad Gateway**：网关错误

**503 Service Unavailable**：服务不可用

**504 Gateway Timeout**：网关超时

### [](#响应头部)响应头部

```
HTTP/1.1 200 OK\r\n
Server: nginx/1.18.0\r\n
Date: Mon, 21 May 2026 10:00:00 GMT\r\n
Content-Type: text/html; charset=utf-8\r\n
Content-Length: 1234\r\n
Set-Cookie: sessionId=xyz789; HttpOnly; Secure\r\n
Cache-Control: max-age=3600\r\n
ETag: "abc123"\r\n
\r\n
```

---

## [](#http长连接与短连接)HTTP长连接与短连接

### [](#短连接)短连接

每次请求都建立TCP连接，请求后关闭：

```
连接1 → 请求1 → 响应1 → 关闭
连接2 → 请求2 → 响应2 → 关闭
```

### [](#长连接)长连接

建立TCP连接后，复用连接发送多个请求：

```
连接 → 请求1 → 响应1
      → 请求2 → 响应2
      → 请求3 → 响应3
```

**HTTP/1.1默认使用长连接**

### [](#请求管道化)请求管道化

在长连接基础上，同时发送多个请求：

```
连接 → 请求1 → 请求2 → 请求3
      ← 响应1 ← 响应2 ← 响应3
```

注意：响应必须按请求顺序返回

---

## [](#https)HTTPS

### [](#https简介)HTTPS简介

HTTPS = HTTP + TLS/SSL，提供加密传输：

- **加密**：防止数据被窃听
- **完整性验证**：防止数据被篡改
- **身份认证**：验证服务器身份
- **信任链**：证书链验证

### [](#https工作原理)HTTPS工作原理

1. 客户端发送ClientHello
2. 服务器返回证书和ServerHello
3. 客户端验证证书，生成随机密钥
4. 使用服务器公钥加密密钥，发送给服务器
5. 双发使用对称密钥加密通信

### [](# ssl和tls的区别)SSL和TLS的区别

- SSL（Secure Sockets Layer）：早期版本（SSL 1.0/2.0/3.0）
- TLS（Transport Layer Security）：SSL的后继（TLS 1.0/1.1/1.2/1.3）
- TLS是标准化版本，更安全

### [](#https证书)HTTPS证书

证书包含：
- 公钥
- 域名信息
- 颁发机构信息
- 过期时间
- 数字签名

证书类型：
- **DV**：域名验证（免费，如Let's Encrypt）
- **OV**：组织验证
- **EV**：扩展验证（绿色地址栏）

---

## [](#http缓存机制)HTTP缓存机制

### [](#缓存控制)缓存控制

| 指令 | 说明 |
|------|------|
| max-age=秒 | 缓存有效期 |
| no-cache | 需验证后使用 |
| no-store | 不缓存 |
| private | 仅浏览器缓存 |
| public | 代理也可缓存 |

### [](#etag与last-modified)ETag与Last-Modified

**Last-Modified**：最后修改时间

**ETag**：资源的唯一标识（通常为哈希值）

### [](#协商缓存)协商缓存

1. 首访问时，服务器返回资源和ETag/Last-Modified
2. 下次访问时，客户端发送If-None-Match或If-Modified-Since
3. 未变化返回304，使用缓存；变化返回新资源

---

## [](#http各版本对比)HTTP各版本对比

| 特性 | HTTP/1.0 | HTTP/1.1 | HTTP/2 | HTTP/3 |
|------|-----------|----------|--------|--------|
| 长连接 | 需要声明 | 默认开启 | 默认开启 | 默认开启 |
| 管道化 | 不支持 | 支持 | 不支持（有替代） | 不支持 |
| 多路复用 | 不支持 | 不支持 | 支持 | 支持 |
| 头部压缩 | 不支持 | 不支持 | HPACK | QPACK |
| 服务端推送 | 不支持 | 不支持 | 支持 | 支持 |
| 传输协议 | TCP | TCP | TCP | QUIC(UDP) |
| 队头阻塞 | 无 | 有 | 无 | 无 |

> **队头阻塞**：一个请求阻塞，后面的请求都要等待

---

## [](#http面试高频问题)HTTP面试高频问题

### [](#问题1：http和https的区别)问题1：HTTP和HTTPS的区别？

**答案**：
- HTTP明文传输，HTTPS加密传输
- HTTP端口80，HTTPS端口443
- HTTPS需要证书，提供身份认证
- HTTPS比HTTP更安全

### [](#问题2：http是无状态的吗)问题2：HTTP是无状态的吗？

**答案**：是的，HTTP不保存请求间的状态。需要用Session/Cookie维持会话状态。

### [](#问题3：http1.1有哪些改进)问题3：HTTP/1.1有哪些改进？

**答案**：
- 默认长连接
- 支���管道化
- 增加缓存控制头部
- 支持分块传输

### [](#问题4：http2和http1.1的区别)问题4：HTTP/2和HTTP/1.1的区别？

**答案**：
- 多路复用：二进制分帧，无队头阻塞
- 头部压缩：HPACK算法
- 服务端推送：服务器主动推送资源
- 流优先级：控制资源优先级

### [](#问题5：GET和POST的区别)问题5：GET和POST的区别？

**答案**：
- GET幂等，POST不幂等
- GET参数在URL，POST在请求体
- GET可缓存，POST一般不缓存
- GET长度受限于URL长度

### [](#问题6：常见的HTTP状态码)问题6：常见的HTTP状态码？

**答案**：
- 2xx：200成功，204无内容
- 3xx：301永久重定向，302临时重定向，304 Not Modified
- 4xx：400语法错误，401未授权，403禁止，404未找到
- 5xx：500服务器错误，502网关错误，503服务不可用

---

## [](#总结)总结

HTTP是互联网的核心协议：

1. **请求-响应模式**：简单易用
2. **版本演进**：从HTTP/1.0到HTTP/3
3. **长连接**：提高性能
4. **HTTPS**：安全传输
5. **缓存机制**：减少重复请求
6. **面试重点**：状态码、缓存、HTTPS原理

掌握HTTP协议对于Web开发和网络面试都非常重要。
