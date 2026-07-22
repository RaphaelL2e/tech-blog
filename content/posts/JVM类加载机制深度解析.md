---
title: JVM 类加载机制深度解析
date: 2026-05-08 15:08:00+08:00
updated: '2026-05-08T15:08:00+08:00'
description: 面试高频问题：类加载过程是什么？什么是双亲委派模型？为什么要打破双亲委派？ 在 Java 面试中，JVM 类加载机制是考察候选人底层理解能力的经典题目。从「类加载过程」到「双亲委派模型」，再到「如何打破双亲委派」，这些问题不仅考察理论知识，还涉及实际应用场景如
  Tomcat 类加载、OSGi 模块化。
topic: java-spring
level: intermediate
status: maintained
tags:
- JVM
- 面试
- 类加载
- 双亲委派
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：类加载过程是什么？什么是双亲委派模型？为什么要打破双亲委派？

## 引言

在 Java 面试中，JVM 类加载机制是考察候选人底层理解能力的经典题目。从「类加载过程」到「双亲委派模型」，再到「如何打破双亲委派」，这些问题不仅考察理论知识，还涉及实际应用场景如 Tomcat 类加载、OSGi 模块化等。本文将全面解析 JVM 类加载机制。

## 一、类加载全过程

Java 文件从源码到执行，经历完整的生命周期：

```
.java ──编译──→ .class ──类加载──→ JVM运行时
                    │
    ┌───────────────┼───────────────┐
    │               │               │
  加载           连接           初始化
    │               │               │
    │      ┌────────┼────────┐      │
    │      │        │        │      │
    │    验证     准备     解析    │
    └───────────────┴───────────────┘
                    │
                 使用
                    │
                 卸载
```

### 1.1 加载（Loading）

**加载阶段做什么？**

1. **获取二进制流**：通过类的全限定名获取 .class 文件的二进制字节流
2. **转换为运行时结构**：将字节流代表的静态存储结构转换为方法区的运行时数据结构
3. **生成 Class 对象**：在堆中生成一个代表这个类的 `java.lang.Class` 对象

**谁来加载？**

- 类加载器（ClassLoader）
- 可以是系统提供的，也可以是自定义的

**什么时候加载？**

- 首次主动使用类时（延迟加载）
- 创建对象、访问静态变量、调用静态方法、反射等

### 1.2 连接（Linking）

连接阶段分为三个子阶段：验证、准备、解析。

#### 验证（Verification）

确保 .class 文件字节流符合 JVM 规范，不会危害虚拟机安全。

```
验证内容：
├── 文件格式验证：魔数 0xCAFEBABE、版本号
├── 元数据验证：是否有父类、是否继承 final 类
├── 字节码验证：跳转指令是否指向合法位置
└── 符号引用验证：引用的类是否存在
```

> 💡 **面试题**：验证阶段可以关闭吗？
> 
> 答：可以，使用 `-Xverify:none` 参数跳过验证，加快启动速度（生产环境不推荐）

#### 准备（Preparation）

为类的静态变量分配内存，并设置初始值。

```java
public class PrepareDemo {
    static int value = 123;
    static final int CONSTANT = 456;
}
```

**准备阶段后**：
- `value = 0`（初始值，不是 123）
- `CONSTANT = 456`（final 常量在准备阶段就赋值）

| 类型 | 初始值 |
|------|--------|
| int | 0 |
| long | 0L |
| float | 0.0f |
| double | 0.0d |
| boolean | false |
| char | '\u0000' |
| reference | null |

> 💡 **关键点**：`static final` 常量在准备阶段就赋值，普通静态变量在初始化阶段赋值

#### 解析（Resolution）

将常量池中的符号引用替换为直接引用。

```
符号引用：用字符串描述的目标（如 "java/lang/Object"）
直接引用：指向目标的指针、偏移量或句柄

解析内容：
├── 类或接口解析
├── 字段解析
├── 方法解析
└── 接口方法解析
```

### 1.3 初始化（Initialization）

执行类构造器 `<clinit>()` 方法，为静态变量赋值，执行静态代码块。

```java
public class InitDemo {
    static int value = 123;           // 在 <clinit> 中赋值
    static {
        System.out.println("静态块");  // 在 <clinit> 中执行
    }
}
```

**`<clinit>()` 方法特点**：

1. 由编译器自动收集类中的所有静态变量赋值和静态语句块
2. 按源码顺序执行
3. 父类的 `<clinit>` 先执行
4. JVM 保证多线程环境下 `<clinit>` 只执行一次（类初始化锁）

```java
public class Singleton {
    private static Singleton instance = new Singleton();
    
    private Singleton() {}
    
    public static Singleton getInstance() {
        return instance;
    }
}
// 类加载时就会创建实例（饿汉式）
```

### 1.4 类初始化时机

**主动使用（必须初始化）**：

```java
// 1. 创建实例
new MyClass();

// 2. 访问静态变量（除 final 常量）
int x = MyClass.staticField;

// 3. 调用静态方法
MyClass.staticMethod();

// 4. 反射
Class.forName("com.example.MyClass");

// 5. 初始化子类（父类会先初始化）
class Child extends Parent {}

// 6. 主类（包含 main 方法）
public class Main { public static void main(String[] args) {} }
```

**被动使用（不初始化）**：

```java
// 1. 引用父类的静态字段
class Parent {
    static int value = 100;
}
class Child extends Parent {}
System.out.println(Child.value);  // 只初始化 Parent，不初始化 Child

// 2. 通过数组定义引用类
MyClass[] arr = new MyClass[10];  // 不初始化 MyClass

// 3. 引用 final 常量
System.out.println(MyClass.CONSTANT);  // 不初始化 MyClass
```

> 💡 **面试题**：以下代码输出什么？
> 
> ```java
> public class Test {
>     public static void main(String[] args) {
>         System.out.println(Child.value);
>     }
> }
> class Parent {
>     static int value = 100;
>     static { System.out.println("Parent init"); }
> }
> class Child extends Parent {
>     static { System.out.println("Child init"); }
> }
> ```
> 
> **答案**：只输出 "Parent init" 和 100，Child 不会初始化

## 二、类加载器

JVM 提供了三层类加载器架构。

### 2.1 类加载器层次

```
┌─────────────────────────────────────┐
│         Bootstrap ClassLoader        │  ← C++ 实现，加载核心类库
│     (启动类加载器/根加载器)            │    java.*、rt.jar
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│        Extension ClassLoader         │  ← Java 实现，加载扩展类库
│         (扩展类加载器)                │    ext/*.jar
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│        Application ClassLoader       │  ← 加载应用类路径
│        (应用类加载器)                 │    classpath
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│        Custom ClassLoader            │  ← 用户自定义
│        (自定义类加载器)               │
└─────────────────────────────────────┘
```

### 2.2 启动类加载器（Bootstrap ClassLoader）

- **实现**：C++（JVM 的一部分）
- **加载路径**：`JAVA_HOME/lib/rt.jar`、`resources.jar` 等核心类库
- **无法被 Java 程序直接访问**

```java
// 查看 Bootstrap 加载的路径
System.out.println(System.getProperty("sun.boot.class.path"));

String.class.getClassLoader();  // 返回 null（Bootstrap 加载）
```

### 2.3 扩展类加载器（Extension ClassLoader）

- **实现**：Java（`sun.misc.Launcher$ExtClassLoader`）
- **加载路径**：`JAVA_HOME/lib/ext` 目录下的 jar 包
- **父加载器**：Bootstrap ClassLoader

```java
// 查看扩展类加载器加载的路径
System.out.println(System.getProperty("java.ext.dirs"));
```

### 2.4 应用类加载器（Application ClassLoader）

- **实现**：Java（`sun.misc.Launcher$AppClassLoader`）
- **加载路径**：`CLASSPATH` 环境变量、`-classpath` 参数
- **父加载器**：Extension ClassLoader
- **默认类加载器**：用户代码默认使用此类加载器

```java
// 获取应用类加载器
ClassLoader appClassLoader = ClassLoader.getSystemClassLoader();

// 查看加载路径
System.out.println(System.getProperty("java.class.path"));
```

### 2.5 类加载器代码示例

```java
public class ClassLoaderDemo {
    public static void main(String[] args) {
        // 获取类加载器
        ClassLoader loader = ClassLoaderDemo.class.getClassLoader();
        
        System.out.println("当前类加载器: " + loader);
        System.out.println("父加载器: " + loader.getParent());
        System.out.println("祖父加载器: " + loader.getParent().getParent());
        // 输出：
        // 当前类加载器: sun.misc.Launcher$AppClassLoader@...
        // 父加载器: sun.misc.Launcher$ExtClassLoader@...
        // 祖父加载器: null（Bootstrap）
    }
}
```

## 三、双亲委派模型

### 3.1 什么是双亲委派？

当一个类加载器收到类加载请求时，它首先把这个请求委托给父加载器处理，只有当父加载器无法完成加载时，才自己尝试加载。

```
加载请求
    │
    ▼
Application ClassLoader
    │
    │ 委派给父加载器
    ▼
Extension ClassLoader
    │
    │ 委派给父加载器
    ▼
Bootstrap ClassLoader
    │
    ├── 找到了 → 加载成功
    └── 没找到 → 返回给子加载器尝试
```

### 3.2 源码分析

```java
// ClassLoader.loadClass() 源码（简化版）
protected Class<?> loadClass(String name, boolean resolve) {
    synchronized (getClassLoadingLock(name)) {
        // 1. 检查是否已加载
        Class<?> c = findLoadedClass(name);
        
        if (c == null) {
            try {
                if (parent != null) {
                    // 2. 有父加载器，委托给父加载器
                    c = parent.loadClass(name, false);
                } else {
                    // 3. 无父加载器，委托给 Bootstrap
                    c = findBootstrapClassOrNull(name);
                }
            } catch (ClassNotFoundException e) {
                // 父加载器无法加载，捕获异常
            }
            
            if (c == null) {
                // 4. 父加载器都加载不了，自己尝试加载
                c = findClass(name);
            }
        }
        
        if (resolve) {
            resolveClass(c);
        }
        return c;
    }
}
```

### 3.3 双亲委派的好处

**1. 保证核心类安全**

假设没有双亲委派，用户可以自定义一个 `java.lang.String`：

```java
package java.lang;

public class String {
    public String() {
        // 恶意代码
        Runtime.getRuntime().exec("rm -rf /");
    }
}
```

有了双亲委派，Bootstrap ClassLoader 会先加载 JDK 的 `java.lang.String`，用户自定义的同名类不会被加载。

**2. 避免类重复加载**

同一个类只会被加载一次，父加载器加载过的类，子加载器不会再加载。

**3. 保证全局唯一性**

同一个类由同一个加载器加载，保证类型一致性。

```java
// 不同加载器加载的同名类是不同的类型
Class<?> c1 = customLoader.loadClass("com.example.MyClass");
Class<?> c2 = appClassLoader.loadClass("com.example.MyClass");
System.out.println(c1 == c2);  // false
```

### 3.4 双亲委派的问题

**无法满足某些场景需求**：

1. **SPI 机制**：JDBC 接口在 rt.jar（Bootstrap 加载），实现类在 classpath（AppClassLoader 加载），Bootstrap 无法加载子加载器的类
2. **热部署**：需要重新加载类，但不能用原来的加载器
3. **Web 容器**：Tomcat 需要隔离不同 WebApp，每个应用用自己的类加载器

## 四、打破双亲委派

### 4.1 JDBC SPI —— 线程上下文类加载器

**问题**：

```java
// JDBC 接口在 rt.jar，由 Bootstrap 加载
Connection conn = DriverManager.getConnection(url);

// 但具体实现（如 MySQL Driver）在 classpath，由 AppClassLoader 加载
// Bootstrap ClassLoader 无法加载 AppClassLoader 的类
```

**解决方案**：线程上下文类加载器（Thread Context ClassLoader）

```java
// DriverManager 初始化时
public class DriverManager {
    static {
        // 使用线程上下文类加载器加载驱动
        AccessController.doPrivileged((PrivilegedAction<Void>) () -> {
            ServiceLoader<Driver> loadedDrivers = ServiceLoader.load(Driver.class);
            // ...
            return null;
        });
    }
}

// ServiceLoader.load() 源码
public static <S> ServiceLoader<S> load(Class<S> service) {
    // 获取当前线程的上下文类加载器
    ClassLoader cl = Thread.currentThread().getContextClassLoader();
    return ServiceLoader.load(service, cl);
}
```

**使用方式**：

```java
// 设置线程上下文类加载器
Thread.currentThread().setContextClassLoader(customClassLoader);

// 获取
ClassLoader loader = Thread.currentThread().getContextClassLoader();
```

### 4.2 Tomcat 类加载器

**问题**：

- 多个 WebApp 需要隔离，各自使用不同版本的类库
- WebApp 优先加载自己的类，而不是父加载器的类

**解决方案**：自定义类加载器，打破双亲委派

```
┌─────────────────────────────────────────────────────────────┐
│                      Bootstrap                               │
│                  (JRE 核心)                                   │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                       System                                 │
│                  (Tomcat 核心)                               │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                   CommonClassLoader                          │
│                  (Tomcat 公共类)                              │
└────────────────────────────┬────────────────────────────────┘
              ┌──────────────┴──────────────┐
              │                             │
┌─────────────▼────────────┐   ┌────────────▼─────────────┐
│   CatalinaClassLoader    │   │   SharedClassLoader      │
│   (Tomcat 内部类)         │   │   (WebApp 共享类)         │
└──────────────────────────┘   └────────────┬──────────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │                           │
                 ┌────────────▼──────────┐  ┌────────────▼──────────┐
                 │  WebAppClassLoader    │  │  WebAppClassLoader    │
                 │    (/webapp1)          │  │    (/webapp2)          │
                 └───────────────────────┘  └───────────────────────┘
```

**WebAppClassLoader 打破双亲委派**：

```java
// Tomcat WebAppClassLoader.loadClass() 简化逻辑
public Class<?> loadClass(String name) {
    // 1. 先检查是否已加载
    
    // 2. JVM 核心类，委托给父加载器（安全）
    if (name.startsWith("java.")) {
        return super.loadClass(name);
    }
    
    // 3. WebApp 自己的类，优先自己加载（打破双亲委派）
    Class<?> clazz = findClass(name);
    if (clazz != null) {
        return clazz;
    }
    
    // 4. 自己加载不了，委托给父加载器
    return super.loadClass(name);
}
```

### 4.3 自定义类加载器

**场景**：

- 加密解密：Class 文件加密，运行时解密加载
- 热部署：不重启应用，动态替换类
- 隔离加载：同一应用加载不同版本的类库

**实现步骤**：

```java
public class MyClassLoader extends ClassLoader {
    private String classPath;
    
    public MyClassLoader(String classPath) {
        this.classPath = classPath;
    }
    
    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        try {
            byte[] data = loadClassData(name);
            return defineClass(name, data, 0, data.length);
        } catch (IOException e) {
            throw new ClassNotFoundException(name, e);
        }
    }
    
    private byte[] loadClassData(String className) throws IOException {
        String path = classPath + "/" + className.replace('.', '/') + ".class";
        try (InputStream is = new FileInputStream(path);
             ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int len;
            while ((len = is.read(buffer)) != -1) {
                baos.write(buffer, 0, len);
            }
            return baos.toByteArray();
        }
    }
    
    // 打破双亲委派：重写 loadClass
    @Override
    protected Class<?> loadClass(String name, boolean resolve) {
        // 1. 检查是否已加载
        Class<?> c = findLoadedClass(name);
        
        if (c == null) {
            // 2. JVM 核心类，委托给父加载器
            if (name.startsWith("java.")) {
                c = super.loadClass(name, resolve);
            } else {
                // 3. 非核心类，自己加载
                c = findClass(name);
            }
        }
        
        if (resolve) {
            resolveClass(c);
        }
        return c;
    }
}
```

**使用示例**：

```java
public class CustomLoaderDemo {
    public static void main(String[] args) throws Exception {
        MyClassLoader loader = new MyClassLoader("/path/to/classes");
        Class<?> clazz = loader.loadClass("com.example.MyClass");
        Object obj = clazz.newInstance();
        System.out.println(obj);
    }
}
```

## 五、面试高频问题

### Q1：类加载过程是什么？

**答**：加载 → 连接（验证、准备、解析）→ 初始化 → 使用 → 卸载

- **加载**：读取 .class 文件，生成 Class 对象
- **验证**：确保字节流符合 JVM 规范
- **准备**：为静态变量分配内存，设初始值
- **解析**：符号引用替换为直接引用
- **初始化**：执行 `<clinit>()` 方法

### Q2：什么是双亲委派模型？

**答**：类加载器收到加载请求时，先委托给父加载器处理，只有父加载器无法完成时，才自己尝试加载。

**好处**：
1. 保证核心类安全（防止伪造 java.lang.String）
2. 避免类重复加载
3. 保证类全局唯一

### Q3：为什么要打破双亲委派？

**答**：某些场景需要子加载器优先加载类：

1. **SPI 机制**：JDBC 接口（Bootstrap）需要加载实现类（AppClassLoader）
2. **热部署**：不重启应用，动态替换类
3. **Web 容器**：Tomcat 需要隔离不同 WebApp 的类库版本

### Q4：如何打破双亲委派？

**答**：

1. **线程上下文类加载器**：ServiceLoader 机制
2. **自定义类加载器**：重写 `loadClass()` 方法
3. **OSGi**：模块化加载，每个模块有自己的类加载器

### Q5：哪些情况会触发类初始化？

**答**：主动使用类时：

1. new 创建实例
2. 访问静态变量（除 final 常量）
3. 调用静态方法
4. 反射 `Class.forName()`
5. 初始化子类（父类先初始化）
6. 主类（包含 main）

### Q6：类加载器有哪些？

**答**：

| 加载器 | 加载范围 | 父加载器 |
|--------|---------|---------|
| Bootstrap | JAVA_HOME/lib | 无（C++） |
| Extension | JAVA_HOME/lib/ext | Bootstrap |
| Application | classpath | Extension |
| Custom | 自定义 | Application |

## 六、总结

类加载机制是 JVM 的核心知识，掌握它有助于：

1. **理解框架原理**：Spring、Tomcat 的类加载策略
2. **解决加载问题**：ClassNotFoundException、NoClassDefFoundError
3. **实现高级功能**：热部署、加密加载、模块化

**核心要点**：
- 类加载过程：加载 → 连接 → 初始化
- 双亲委派：委托父加载器，保证安全与唯一
- 打破双亲委派：SPI、热部署、Web 容器隔离
- 自定义类加载器：继承 ClassLoader，重写 findClass/loadClass

---

**下一篇预告**：JVM 垃圾回收算法与收集器深度解析 —— CMS、G1、ZGC 全对比

**参考资料**：
- 《深入理解 Java 虚拟机》- 周志明
- JSR-000335 Java SE 7 Specification
- OpenJDK ClassLoader 源码
