---
title: "Raphael Lab"
description: "把 250+ 篇时间流文章重构为有品牌首页、学习路径、全文搜索与长文阅读器的静态知识库。"
stack: "Hugo · Search · Content Design"
tags: ["Hugo", "SEO", "Accessibility", "Performance"]
repo: "https://github.com/RaphaelL2e/tech-blog"
weight: 20
---

## 问题背景

当内容超过 250 篇后，单纯的时间流已无法承载查找、系统学习和长文阅读。大量重复标签页还把构建产物放大到数百 MB。

## 关键决策

- 首页从全量列表改为品牌与内容分发页。
- 用明确顺序的系列替代噪音标签导航。
- 在保持 GitHub Pages 静态架构的前提下实现中文全文搜索。
- 把 SEO、无障碍、移动端与内容可信度放在同一套模板中维护。

## 工程结果

站点继续使用 Hugo 单仓库构建，但具备了可编排的知识结构、可缓存的资产、可搜索的内容索引和更稳定的阅读体验。
