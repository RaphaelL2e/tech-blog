---
title: "maven学习"
date: 2019-06-27T14:45:38+08:00
draft: false
categories: ['JAVA']
tags: ['java', 'maven']
---

# [](#一、为什么使用maven)一、为什么使用maven?

### [](#1-一般的一个项目就是一个工程)1.一般的一个项目就是一个工程

当一个项目非常庞大，可以借助maven拆分成一个个工程。

### [](#2-项目中使用到的jar包，需要复制粘贴到lib目录下)2.项目中使用到的jar包，需要复制粘贴到lib目录下

借助maven可以将jar保存在仓库，直接引用就行。不用累赘的一个个导包。

### [](#3-jar的下载与使用)3.jar的下载与使用

借助maven可以更加便捷快捷，规范化的使用jar包

### [](#4-jar包的版本不一致有风险)4.jar包的版本不一致有风险

借助maven所有jar存放在仓库，所有项目使用仓库中的一份jar包

### [](#5-jar包中如果依赖其他jar需要手动导入)5. jar包中如果依赖其他jar需要手动导入

借助maven会自动的导入相关依赖包

# [](#二、什么是maven)二、什么是maven?

[Apache Maven is a software project management and comprehension tool. Based on the concept of a project object model (POM), Maven can manage a project’s build, reporting and documentation from a central piece of information.](https://maven.apache.org/)
**是一个软件项目管理和理解工具。基于项目对象模型（POM）的概念，Maven可以从一个中心信息管理项目的构建，报告和文档**。

### [](#构建：)构建：

- 定义：把动态的web工程通过编译得到的编译结果部署到服务器上的过程
a.编译：java源文件–>编译–>Class字节码文件

- b.部署：最终在servlet容器中部署的是编译后的文件

- 构建的各个环节：
clean [清理] ：将之前编译的文件删除

- compile [编译] ： 将java源文件编译成字节码文件

- test [测试] ：自动测试，自动调用junit程序

- report [报告] ：测试程序的执行结果

- package [打包] ： 将动态web打包成war,将java工程打包成jar

- install [安装] ：Maven特定的概念——将打包好的文件复制到仓库的指定的位置

- deploy [部署] ：将动态web工程war包复制到servlet容器下，并运行# [](#三、maven的安装)三、maven的安装

### [](#1-安装java环境，配置环境变量。)1.安装java环境，配置环境变量。

### [](#2-下载maven-并安装)2.[下载maven](https://maven.apache.org/download.cgi),并[安装](https://maven.apache.org/install.html)

### [](#3)3.-v ```查验mvn版本1
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
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43

# 四、构建一个maven项目从0到1
### 约定目录结构
根目录:工程名
|——src： 源码
|——|——main ： 存放主程序
|——|——|——java: java源码文件
|——|——|——|——|——com
|——|——|——|——|——|——lee
|——|——|——|——|——|——|——maven
|——|——|——|——|——|——|——|——Hello.java
|——|——|——resource： 存放框架配置文件
|——|——test: 存放测试文件
|——pom.xml: maven的核心配置文件

### 按照目录结构搭建项目
**pop.xml文件**
```xml
 <?xml version="1.0" ?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
<modelVersion>4.0.0</modelVersion>
<groupId>com.lee.maven</groupId>
<artifactId>Hello</artifactId>
<version>0.0.1-SNAPSHOT</version>

<name>Hello</name>

<properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
</properties>
<dependencies>
    <dependency>
	    <groupId>junit</groupId>
		<artifactId>junit</artifactId>
		<version>4.0</version>
		<scope>test</scope>
	</dependency>
</dependencies>
</project>

#### [](#1-进入-xml目录下，执行)1.进入.xml目录下，执行 compile```1
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
24
25
26
```linux
leeyf@leeyf-PC:~/java/project/maven-hello$ mvn compile
WARNING: An illegal reflective access operation has occurred
WARNING: Illegal reflective access by com.google.inject.internal.cglib.core.$ReflectUtils$1 (file:/usr/share/maven/lib/guice.jar) to method java.lang.ClassLoader.defineClass(java.lang.String,byte[],int,int,java.security.ProtectionDomain)
WARNING: Please consider reporting this to the maintainers of com.google.inject.internal.cglib.core.$ReflectUtils$1
WARNING: Use --illegal-access=warn to enable warnings of further illegal reflective access operations
WARNING: All illegal access operations will be denied in a future release
[INFO] Scanning for projects...
[INFO] 
[INFO] ------------------------< com.lee.maven:Hello >-------------------------
[INFO] Building Hello 0.0.1-SNAPSHOT
[INFO] --------------------------------[ jar ]---------------------------------
[INFO] 
[INFO] --- maven-resources-plugin:2.6:resources (default-resources) @ Hello ---
[INFO] Using 'UTF-8' encoding to copy filtered resources.
[INFO] Copying 0 resource
[INFO] 
[INFO] --- maven-compiler-plugin:3.1:compile (default-compile) @ Hello ---
[INFO] Changes detected - recompiling the module!
[INFO] Compiling 1 source file to /home/leeyf/java/project/maven-hello/target/classes
[INFO] ------------------------------------------------------------------------
[INFO] BUILD SUCCESS
[INFO] ------------------------------------------------------------------------
[INFO] Total time:  1.072 s
[INFO] Finished at: 2019-06-29T10:45:31+08:00
[INFO] ------------------------------------------------------------------------

在pom.xml同级目录下，多了一个target文件夹，里面是编译以后的字节码
|——target
|——|——classes
|——|——|——com
|——|——|——|——lee
|——|——|——|——|——maven
|——|——|——|——|——|——Hello.class
|——|——maven-status
|——|——|——maven-compiler-plugin
|——|——|——|——compile
|——|——|——|——|——default-compile
|——|——|——|——|——|——createdFiles.lst
|——|——|——|——|——|——inputFiles.lst
|——|——generated-sources
|——|——|——annotations

#### [](#2-运行)2.运行test-compile```,target 文件夹下多了一个test-class文件夹1
2
3
```linux
leeyf@leeyf-PC:~/java/project/maven-hello$ ls target/
classes  generated-sources  maven-status  test-classes

#### [](#3-运行)3.运行package``` ,target 文件夹下多了一个jar包1
2
3
```linux
leeyf@leeyf-PC:~/java/project/maven-hello$ ls target/
classes  generated-sources  Hello-0.0.1-SNAPSHOT.jar  maven-archiver  maven-status  test-classes

#### [](#4-运行)4.运行clean ``` target整个被清理掉1
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

# 五、仓库&&坐标
- **pom.xml**: **Project Object Model 项目对象模型**。它是maven的核心配置文件，所有的构建的配置都在这里设置。
- **坐标**： 使用三个向量确定仓库内唯一一个maven工程
```xml
	<!-- 1.公司或组织域名倒序+项目名-->
	<groupId>junit</groupId>
	<!--2.模块名-->
	<artifactId>junit</artifactId>
	<!--3.版本-->
	<version>4.0</version>

- **maven工程坐标**：

本项目坐标 

  1
2
3
<groupId>com.lee.maven</groupId>
<artifactId>Hello</artifactId>
<version>0.0.1-SNAPSHOT</version>

- 依赖项目坐标

  1
2
3
4
5
6
<dependency>
   		<groupId>junit</groupId>
	<artifactId>junit</artifactId>
	<version>4.0</version>
	<scope>test</scope>
</dependency>

**maven坐标和仓库对应的映射关系：[groupId][artifactId][version][artifactId]-[version].jar**

- **仓库**

1.本地仓库：.m2

- 2.远程仓库：
a. 私服：个人搭建的，常见的搭建工具：nexus

- b. 中心仓库# [](#六、依赖)六、依赖

- maven解析依赖信息会到本地仓库中查取被依赖的jar包

当本地仓库中未找到，会去中心仓库查找maven坐标来获取jar包，然后下载到本地仓库

- 若中心仓库未查取到依赖的jar包时，编译失败

- 若依赖的jar包是自己OR自己团队开发的maven,需要先install``` 把所依赖的工程jar包安装到本地maven仓库中1
2
3
4
5
6
7
> 举例：现在我再创建第二个maven工程HelloFriend，其中用到了第一个Hello工程里类的sayHello(String name)方法
> 我们在给HelloFriend项目使用 mvn compile命令进行编译的时候，会提示缺少依赖Hello的jar包。怎么办呢？
> 到第一个maven工程中执行 mvn install后，你再去看一下本地仓库，你会发现有了Hello项目的jar包
> 一旦本地仓库有了依赖的maven工程的jar包后，你再到HelloFriend项目中使用 mvn compile命令的时候，可以成功编译
- 依赖范围：
	```xml
	<scope>compile</scope>

compile :默认值，本jar包会一直存在

- provided :只有开发、测试阶段使用，目的是不让Servlet容器和你本地仓库的jar包冲突 。如servlet.jar。 

- runtime : 只在运行时使用，比如JDBC驱动，适用运行和测试阶段

- test : 只在测试时适用，用于编译和测试代码。不随项目发布

- system : 类似provided，需要显式提供包含依赖的jar，Maven不会在Repository中查找它。# [](#七、生命周期)七、生命周期

#### [](#Maven-有三套相互独立的生命周期)Maven 有三套相互独立的生命周期

- **Clean LifeCycle** 在进行正式构建前进行的一些清理工作

- **Default Lifecycle** 构建的核心部分，编译，测试，打包，部署

1、validate
2、generate-sources
3、process-sources
4、generate-resources
5、process-resources     复制并处理资源文件，至目标目录，准备打包
6、compile     编译项目的源代码
7、process-classes
8、generate-test-sources
9、process-test-sources
10、generate-test-resources
11、process-test-resources     复制并处理资源文件，至目标测试目录
12、test-compile     编译测试源代码
13、process-test-classes
14、test     使用合适的单元测试框架运行测试。这些测试代码不会被打包或部署
15、prepare-package
16、package     接受编译好的代码，打包成可发布的格式，如 JAR
17、pre-integration-test
18、integration-test
19、post-integration-test
20、verify
21、install     将包安装至本地仓库，以让其它项目依赖。
22、deploy     将最终的包复制到远程的仓库，以让其它开发人员与项目共享

**不论执行哪个生命周期，一定会经过这个周期。**

- **插件：每个阶段都有插件（plugin），插件的职责就是执行它对应的命令。**

- **Site Lifecycle** 生成项目报告、站点、发布站点

**pre-site** 执行一些需要在生成站点前完成的工作

- **site** 生成项目的站点文档

- **post-site** 执行一些需要在生成文档之后的任务，并且给部署做准备

- **site-deploy** 将生成的站点文档部署到特定服务器上

部分内容，网络转载，侵权删～
