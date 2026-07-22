---
title: "Claude-Go"
description: "用 Go 重构 AI 编程 Agent，把 CLI、流式 API、工具调用、MCP 和成本跟踪收敛为一个可扩展的工程底座。"
stack: "Go · Agent · MCP"
tags: ["Go", "SSE", "MCP", "CLI"]
repo: "https://github.com/RaphaelL2e"
weight: 10
---

## 问题背景

AI 编程工具经常把模型、工具和交互层紧紧绑定。这会让多模型切换、私有化部署和自定义工具接入变得困难。

## 关键决策

- 用 Cobra 组织 CLI 与交互式 REPL。
- 同时支持普通响应与 SSE 流式输出。
- 将文件、Shell、搜索与 Task 等能力抽象为工具。
- 支持 STDIO、HTTP 与 SSE 三种 MCP 传输。
- 把成本、会话历史和终端反馈纳入核心循环。

## 工程结果

已完成 API 客户端、14 个工具、MCP 客户端、会话持久化和流式交互，正在将模型层抽象为可控的多供应商适配器。
