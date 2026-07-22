---
title: "Security Lab"
description: "从低到高完成 DVWA 常见 Web 漏洞的复现、原理分析与防护对照，建立可重复的安全实验流程。"
stack: "Web Security · DVWA · Docker"
tags: ["Security", "DVWA", "OWASP", "Docker"]
weight: 30
---

## 问题背景

安全知识如果只停留在概念层，很难真正影响日常编码决策。这个实验将常见漏洞放入可控环境，通过攻击与修复的对照建立工程直觉。

## 实验方法

- 在 Low、Medium、High 与 Impossible 四个级别下对比攻击面。
- 复现 SQL 注入、XSS、CSRF、文件上传与命令执行等常见问题。
- 把输入校验、输出编码、权限边界与安全响应头映射回日常后端开发。

## 结果

完成全级别实验，形成了从可利用现象、代码根因到防护策略的闭环认知。
