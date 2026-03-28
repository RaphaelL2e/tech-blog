---
title: "html基础"
date: 2020-01-12T21:37:35+08:00
draft: false
categories: ['前端']
tags: ['html']
---

﻿## 基础标签

<h1></h1>:标题
<p></p> 段落
<hr>水平线
<br>换行
<span></span>分区，可多标签一行
<div></div>分区，每个标签一行

## [](#文本格式化标签)文本格式化标签

<b></b> <strong></strong>加粗
<i></i> <em></em>斜体
<s></s> <del></del>删除
<u></u> <ins></ins 下划线

## [](#图像标签)图像标签

<img src="图片url">
<img/>属性 

- alt 图片不能显示时的替代文本

- title 鼠标悬停时显示

- height 图像高度

- width 图像宽度

- border 图像边框宽度

## [](#链接标签)链接标签

<a href="URL" target ="打开方式"></a>
<a>属性
target  _blank 新窗口打开

## [](#拓展)拓展

<base> <base target="_blank">
<pre></pre> 预格式化文本
保留空格与换行

### [](#特殊字符)特殊字符

```
空字符        &nbsp;
注册商标    &reg;
<                       &lt;
>                       &gt;    
&                   &amp;
```

## [](#表格)表格

### [](#展示表格式数据)展示表格式数据

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
<body>
<!-- 表格标签-->
	<table border="1">
		<!--表格标题标签-->
		<caption>表格标题</caption>
		<!--行标签-->
		<tr>
			<!--表头单元格,文字居中且加粗-->
			<th></th>
		</tr>
		<tr>
		<!--单元格标签-->
			<td></td>
		</tr>
	</table>
</body>

### [](#表格属性)表格属性

border 边框
width 宽度
height 高度
align 设置表格在网页中水平对齐方式

- left

- center

- right

- cellspacing 单元格与单元格之间距离

- cellpadding 单元格内容与边框的距离

### [](#合并单元格)合并单元格

#### [](#跨行合并)跨行合并

rowspan="合并单元格的个数 "

#### [](#跨列合并)跨列合并

colspan="合并单元格个数"

#### [](#合并三部曲)合并三部曲

- 先确认跨行还是跨列

- 根据 先上 后下 先左 后右的原则找到目标单元格 ，然后写上合并方式 和合并数量

- 删除多余的单元格

### [](#表格结构划分)表格结构划分

<thead></thead> 内部必须拥有<tr>标签
<tbody></tbody>
<tfoot></tfoot>

## [](#列表标签)列表标签

### [](#无序列表)无序列表

1
2
3
4
5
<ul>
	<!--ul内只能嵌套li-->
	<li>列表项1 </li>
	<li>列表项2</li>
</ul>

**效果：**

    
    - 列表项1 

    - 列表项2

### [](#有序列表)有序列表

1
2
3
4
<ol>
	<li>列表项</li>
	<li>列表项</li>
</ol>

**效果：**

    - 列表项

    - 列表项

### [](#自定义列表)自定义列表

1
2
3
4
5
6
7
<dl>
	<dt>名词</dt>
	<dd>名词的解释1</dd>
	<dd>名词的解释2</dd>
	<dt>名词2</dt>
	<dd>名词2的解释2<dd>
</dl>

**效果：**

    名词
    名词的解释1
    名词的解释2
    名词2
    名词2的解释2

## [](#表单)表单

### [](#表单标签)表单标签

#### [](#lt-input-gt-控件)<input/>控件

- 语法
  <input type="属性值"/>

- 属性值
type 
```
- `text` 单行文本输入框
- `password ` 密码输入框
- `radio` 单选按钮    
- `checkbox` 复选框
- `button` 普通按钮
- `submit` 提交按钮
- `reset` 重置按钮
- `image` 图像形式的提交按钮
- `file` 文件域
```

- name 控件的名称

- value input控件中的默认文本值

- size   input控件在页面中的显示宽度

- checked 表示默认选中状态

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
	<body>
		用户名： <input type="text" value="请输入用户名" name="username"/> <br/>
		密码：     <input type="password" name="password" /><br/>
		性别：
		男 <input type="radio" name="sex"/>
		女 <input type="radio" name="sex"/>
		未知<input type="radio" name="sex" checked="checked"/> <br/>
		爱好：
				睡觉<input type="checkbox" name="nobby" checked="checked"/>
				游泳<input type="checkbox" name="nobby"/>
				游戏<input type="checkbox" name="nobby"/>
				看书<input type="checkbox" name="nobby"/>
				<br/>
			<input type="button"  value="普通按钮"/>
			<input type="submit"  value="提交按钮"/>
			<input type="reset"  value="重置按钮"/>
			<!--图片提交按钮-->
			<input type="image" src="图片地址" /><br/>
			<!--文件域-->
		上传头像: <input type="file"/>		
</body>

#### [](#lt-label-gt-lt-label-gt-标签)<label></label>标签

**作用:** 用于绑定一个表单元素，当点击label标签时，被绑定的表单元素会获得输入焦点
**绑定元素:**

- 直接包含 

1
<label>用户名：<input type="text"/></label>

- 通过for 和 id

1
<label for="username">用户名：</label>     <input type="text" id="username"/>

#### [](#lt-textarea-gt-lt-textarea-gt-文本域)<textarea></textarea>文本域

可显示多行文本
**效果：**

可显示多行文本1
可显示多行文本2
可显示多行文本3

#### [](#select下拉列表)select下拉列表

1
2
3
4
5
6
<select>
	<option>--请选择--</option>
	<!--添加默认选中项-->
	<option　 selected="selected">选项１</option>
	<option>选项２</option>
</select>

## [](#lt-form-gt-表单域)<form>表单域

**语法：**

1
2
3
4
<body>
	<form action="" method="" name="" >
	</form>
<body/>

**属性：**

- action url地址

- method 表单提交方式

- name 指定表单名称

**示例：**

1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
<body>
	<form action="" method="">
		用户名： <input type="text" value="请输入用户名" name="username"/> <br/>
		密码：     <input type="password" name="password" /><br/>
		性别：
		男 <input type="radio" name="sex"/>
		女 <input type="radio" name="sex"/>
		未知<input type="radio" name="sex" checked="checked"/> <br/>
		爱好：
				睡觉<input type="checkbox" name="nobby" checked="checked"/>
				游泳<input type="checkbox" name="nobby"/>
				游戏<input type="checkbox" name="nobby"/>
				看书<input type="checkbox" name="nobby"/>
				<br/>
			<input type="button"  value="普通按钮"/>
			<input type="submit"  value="提交按钮"/>
			<input type="reset"  value="重置按钮"/>
			<!--图片提交按钮-->
			<input type="image" src="图片地址" /><br/>
			<!--文件域-->
		上传头像: <input type="file"/>		
	</form>
<body/>
