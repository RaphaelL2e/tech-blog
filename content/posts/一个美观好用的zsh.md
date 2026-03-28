---
title: "一个美观好用的zsh"
date: 2020-01-11T17:10:50+08:00
draft: false
categories: ['linux']
tags: ['linux']
---

终于有时间来写文章了～

今天介绍一款linux必备的shell

话不多说直接上图

*

这个shelld的特点

- 美观

- 功能强大，可以添加各类插件（一键解压、压缩、历史命令等）

- 适合初学者用来掌握命令

那么直接上安装过程：

- centos系统：yum install zsh

ubuntu系统：apt-get install ubuntu

注：如果是要全系统使用，则使用root帐号执行该指令

- 启用zsh chsh -s /bin/zsh

- sh -c "$(wget https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh -O -)"

- 设置主题

  **安装完毕后，我们就可以使用了，先来简单配置一下，Oh My Zsh 提供了很多主题风格，我们可以根据自己的喜好，设置主题风格**

  终端输入命令open ~/.zshrc。找到 **ZSH_THEME ，ZSH_THEME=”robbyrussell” ，robbyrussell** ，是默认的主题，修改 **ZSH_THEME=”样式名称”**

  保存这个文件文件，重新打开终端。

设置随机主题

**我们还可以随机设置主题：**

- 步骤同上

- **ZSH_THEME=”random”**

- 每次打开终端主题是随机的。

- 终端输出：

接下来安装一些很好用的插件

## [](#zsh-syntax-highlighting（命令语法高亮）)zsh-syntax-highlighting（命令语法高亮）

安装方法如下（oh-my-zsh 插件管理的方式安装）：

1.Clone项目到$ZSH_CUSTOM/plugins文件夹下 (默认为 ~/.oh-my-zsh/custom/plugins)

1
git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting

2.在 **Oh My Zsh** 的配置文件 (~/.zshrc)中设置:

1
plugins=(其他插件 zsh-syntax-highlighting)

3.运行 source ~/.zshrc 更新配置后重启

## [](#zsh-autosuggestions-命令自动补全)zsh-autosuggestions(命令自动补全)

1.Clone项目到$ZSH_CUSTOM/plugins文件夹下 (默认为 ~/.oh-my-zsh/custom/plugins)

1
git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/zsh-autosuggestions

2.在 **Oh My Zsh** 的配置文件 (~/.zshrc)中设置:

1
plugins=(其他插件 zsh-autosuggestions)

3.运行 source ~/.zshrc 更新配置后重启

## [](#extract（一键解压）)extract（一键解压）

x 会替代tar unzip等指令
