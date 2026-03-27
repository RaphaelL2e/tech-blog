#!/bin/bash
# 部署到 GitHub Pages

echo "🚀 构建站点..."
hugo --minify

echo "📦 复制到 RaphaelL2e.github.io..."
rm -rf ../RaphaelL2e.github.io/*
cp -r public/* ../RaphaelL2e.github.io/

echo "✅ 部署完成！"
echo "请进入 RaphaelL2e.github.io 目录提交更改"
