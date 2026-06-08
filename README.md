# Hugo 技术博客

基于 Hugo 构建的静态博客站点。

## 快速开始

```bash
# 安装 Hugo
brew install hugo

# 本地预览
hugo server -D

# 构建
hugo

# 部署到 GitHub Pages
./deploy.sh
```

## 财富系统加密导出

`/wealth/` 页面只加载加密后的静态 JSON，解密在浏览器本地完成。密码不要提交到 Git，也不要写进 GitHub Actions。

```bash
# 交互输入密码并生成 static/wealth/wealth-data.enc.json
python3 scripts/export_wealth_payload.py

# 或者使用环境变量，适合本机自动化
WEALTH_PASSWORD='your-long-password' python3 scripts/export_wealth_payload.py
```

生成后提交 `static/wealth/wealth-data.enc.json` 即可随 Hugo 一起部署；源数据仍保留在 `wealth-os` 仓库。

## 目录结构

- `content/posts/` - 博客文章
- `static/images/` - 图片资源
- `themes/` - 主题目录
- `config.toml` - 站点配置
