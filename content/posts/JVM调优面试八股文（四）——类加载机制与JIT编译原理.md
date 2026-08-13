---
title: JVM调优面试八股文（四）——类加载机制与JIT编译原理
date: 2026-08-13T10:00:00+08:00
updated: '2026-08-13T10:00:00+08:00'
description: '面试高频问题：类加载的三个阶段是什么？双亲委派模型解决了什么问题？如何自定义类加载器？JIT编译的触发条件是什么？C1和C2编译器有什么区别？逃逸分析如何影响对象分配？本文作为JVM调优面试八股文系列的第四篇，系统讲解类加载机制与JIT编译原理，帮你构建完整的运行时优化知识体系。'
topic: java-spring
series: jvm-tuning-interview
series_order: 4
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- JVM
- 类加载
- JIT
- 编译器
categories:
- Java 与 Spring
draft: false
author: 飞哥
---

> 面试高频问题：类加载的三个阶段是什么？双亲委派模型解决了什么问题？如何自定义类加载器？JIT编译的触发条件是什么？C1和C2编译器有什么区别？逃逸分析如何影响对象分配？本文作为JVM调优面试八股文系列的第四篇，系统讲解类加载机制与JIT编译原理，帮你构建完整的运行时优化知识体系。

## 引言

前三篇我们系统梳理了JVM内存模型、GC算法与收集器、调优实战与问题排查。但JVM的运行时优化远不止GC——**类加载机制**和**JIT即时编译**同样是面试中的高频深水区。

很多候选人对这一块了解很浅，只知道"类要被加载"，却说不清加载过程细节、双亲委派的底层逻辑，以及JIT编译器是如何在运行期"偷梁换柱"做性能优化的。本文从类加载全流程、双亲委派模型、打破委派的场景、JIT编译触发机制、分层编译策略、逃逸分析五个维度，帮你彻底打通这块知识盲区。

**本文要点**：
1. 类加载的三个阶段与最终产物
2. 双亲委派模型的原理与设计动机
3. 自定义类加载器的使用场景与实现方式
4. JIT编译触发条件与分层编译策略
5. C1/C2编译器区别与逃逸分析优化

---

## 一、类加载：JVM如何把Class变成可执行代码

### 1.1 类加载的完整生命周期

**Q: 类加载的完整生命周期是怎样的？**

一个类从被加载到卸载，整个生命周期分为七个阶段：

```
加载（Loading）→ 验证（Verification）→ 准备（Preparation）
→ 解析（Resolution）→ 初始化（Initialization）
→ 使用（Using）→ 卸载（Unloading）
```

其中，**验证、准备、解析**三个阶段统称为**链接（Linking）**。重点说明如下：

**加载阶段**，JVM需要完成三件事：
- 通过类的全限定名获取类的二进制字节流
- 将字节流转化为方法区的运行时数据结构
- 在堆区生成一个`java.lang.Class`对象，作为方法区数据的访问入口

**验证阶段**，是JVM的安全防线，确保Class文件的字节流符合JVM规范，不会危害虚拟机的安全。验证包括：
- 文件格式验证（魔数、版本号等）
- 元数据验证（语义分析，如是否继承了final类）
- 字节码验证（数据流和控制流分析）
- 符号引用验证（解析时检查引用的类/方法/字段是否存在）

**准备阶段**，正式为类变量（即static修饰的变量，不包含实例变量）分配内存，并设置初始值。注意：这里的初始值是零值，而不是代码中指定的值。

```java
public static int value = 123;
// 准备阶段 value = 0，而不是 123
// 真正赋值为123是在初始化阶段
```

特殊情况：如果类变量是`static final`且是编译期常量（字面量），则在准备阶段就赋值：

```java
public static final int CONST = 123; // 准备阶段直接赋值为123
public static final String STR = "hello"; // 基本同上
```

**解析阶段**，将符号引用替换为直接引用。符号引用用字符串表示，不受虚拟机限制；直接引用是直接指向目标的指针、相对偏移量或句柄。

**初始化阶段**，是类加载过程中最核心的阶段。这一阶段会执行类的`<clinit>()`方法——注意是`<clinit>`而不是`<init>`。`<clinit>`由编译器自动收集类中的所有**类变量的赋值动作**和**静态代码块**按顺序合并生成。实例的`<init>`是构造函数，这是两者的本质区别。

### 1.2 初始化的触发条件

**Q: 什么情况下会触发类的初始化？**

有且仅有以下六种情况（主动引用），其他对类的引用均不会触发初始化（被动引用）：

```java
// 场景1：new对象
new MyClass();

// 场景2：访问类的静态变量（final除外）
int v = MyClass.VALUE; // VALUE不是final则触发

// 场景3：调用类的静态方法
MyClass.staticMethod();

// 场景4：反射
Class.forName("com.example.MyClass");

// 场景5：初始化子类时，先初始化父类
class Child extends Parent {} // new Child()时Parent先init

// 场景6：JVM启动时指定的主类（包含main方法的类）
```

特别注意**被动引用**不触发初始化：

```java
// 不会触发初始化的例子
int[] arr = new MyClass[10]; // 只是数组，不触发
System.out.println(Child.count); // 通过子类访问父类静态字段，不触发Child初始化
```

---

## 二、双亲委派模型：JVM的类加载护城河

### 2.1 什么是双亲委派模型

**Q: 什么是双亲委派模型？它解决了什么问题？**

双亲委派模型（Parent Delegation Model）是JVM类加载器的层次结构规范。每个类加载器都有一个父类加载器（除启动类加载器外），类加载请求沿着这个层次向上传递：

```
启动类加载器（Bootstrap ClassLoader）
    ↑ 
扩展类加载器（Extension ClassLoader / Platform ClassLoader）
    ↑
应用程序类加载器（Application ClassLoader）
    ↑
自定义类加载器（User ClassLoader）
```

工作流程：当一个类加载器收到类加载请求时，**它不会自己先去加载，而是把这个请求委派给父类加载器去处理**。只有父加载器反馈自己无法完成这个请求时，子加载器才会尝试自己去加载。

用伪代码表示这个过程：

```java
protected Class<?> loadClass(String name, boolean resolve) throws ClassNotFoundException {
    // 1. 先检查是否已经加载过
    Class<?> c = findLoadedClass(name);
    if (c != null) {
        return c;
    }
    
    // 2. 尝试委派给父类加载器
    try {
        ClassLoader parent = this.parent;
        if (parent != null) {
            c = parent.loadClass(name, false);
        } else {
            // 没有父加载器，委托给启动类加载器
            c = findBootstrapClassOrNull(name);
        }
    } catch (ClassNotFoundException e) {
        // 父类无法加载，子类自己加载
    }
    
    // 3. 父类无法处理，由子类加载
    if (c == null) {
        c = findClass(name);
    }
    
    return c;
}
```

### 2.2 双亲委派的核心价值

**Q: 为什么需要双亲委派模型？它带来了哪些安全保障？**

双亲委派模型解决了一个根本性的**类加载安全问题**：

**场景演示**：假设没有双亲委派，自定义一个`java.lang.String`类：

```java
package java.lang;

public class String {
    public static void main(String[] args) {
        System.out.println("自定义String!");
    }
}
```

如果没有双亲委派，应用程序类加载器会直接加载这个自定义的`java.lang.String`，导致JVM运行混乱。

有了双亲委派模型后，加载请求会逐级向上委派，最终到达启动类加载器。启动类加载器在其负责的核心类库中找不到名为`java.lang.String`的类（因为核心`String`在`rt.jar`中），才会逐级向下尝试加载——最终应用程序类加载器加载核心`String`类，确保了核心API的纯洁性。

这种机制带来的核心价值：
1. **安全性**：防止核心API被篡改，用户自定义的同名类无法覆盖核心类
2. **类隔离**：不同类加载器加载的同名类是不同的类，避免了命名空间冲突
3. **层级统一**：确保每个类只会被加载一次（在一个类加载器范围内）

### 2.3 三种内置类加载器

**Q: JVM内置了哪几种类加载器？各自负责加载哪些内容？**

| 类加载器 | 加载内容 | 实现语言 |
|---------|---------|---------|
| 启动类加载器（Bootstrap） | JAVA_HOME/lib目录下的核心类库 | C++（JVM原生实现） |
| 扩展类加载器（Platform/Extension） | JAVA_HOME/lib/ext目录下的jar包 | Java |
| 应用程序类加载器（AppClassLoader） | classpath下编写的类 | Java |

注意：在JDK 9之后，Extension ClassLoader被改名为Platform ClassLoader，功能略有调整，但委派模型不变。

```java
public class ClassLoaderDemo {
    public static void main(String[] args) {
        // 查看各类的类加载器
        System.out.println(String.class.getClassLoader()); // null -> Bootstrap
        System.out.println(com.sun.crypto.provider.DESKeyFactory.class.getClassLoader()); // Ext
        System.out.println(ClassLoaderDemo.class.getClassLoader()); // AppClassLoader
    }
}
```

### 2.4 打破双亲委派的场景

**Q: 有哪些场景需要打破双亲委派模型？**

尽管双亲委派是JVM推荐的模型，但在某些场景下必须打破它：

**场景一：JNDI服务（Java Naming and Directory Interface）**

JNDI需要由启动类加载器加载的类去引用应用程序类加载器加载的SPI实现。这是JDK 1.2引入**线程上下文类加载器**（Thread Context ClassLoader，简称TCCL）的背景。

```java
// 通过线程上下文类加载器加载SPI实现
ClassLoader tccl = Thread.currentThread().getContextClassLoader();
ServiceLoader<Driver> loader = ServiceLoader.load(Driver.class, tccl);
```

**场景二：模块化热部署与OSGi**

在OSGi或JPMS（Java Platform Module System，JDK 9引入）的环境中，每个模块有自己独立的类加载器。当模块更新时，需要卸载旧模块的类加载器并加载新版本。这要求类加载器能够跳过父类委托，直接加载特定版本的类。

**场景三：Tomcat的WebAppClassLoader**

Tomcat为了实现Web应用之间的类隔离，每个Web应用都有自己的类加载器（WebAppClassLoader）。它会先自己加载，委派给父类加载器的比例最低，以保证不同Web应用之间的类不冲突。这是打破双亲委派的典型应用。

```java
// Tomcat WebAppClassLoader 简化逻辑
protected Class<?> loadClass(String name, boolean resolve) {
    Class<?> clazz = null;
    
    // 1. 先在本地缓存中查找
    clazz = findLoadedClass0(name);
    
    // 2. 用系统类加载器检查（保护JDK核心类）
    if (clazz == null && isSystemClass(name)) {
        clazz = super.loadClass(name, false);
    }
    
    // 3. 用当前Web应用的类加载器
    if (clazz == null) {
        clazz = findClass(name);
    }
    
    // ... 返回
}
```

**场景四：Spring、Hibernate等框架的类加载**

这些框架需要在运行时动态生成类（如CGLIB、Javassist生成的代理类），其类加载策略也需要精细控制，通常通过自定义类加载器来实现。

---

## 三、自定义类加载器：打破边界的武器

### 3.1 自定义类加载器的实现方式

**Q: 如何实现一个自定义类加载器？**

自定义类加载器只需要继承`java.lang.ClassLoader`类，并重写`findClass()`方法（推荐）或`loadClass()`方法（会覆盖双亲委派逻辑）。

```java
public class CustomClassLoader extends ClassLoader {
    
    private String basePath;
    
    public CustomClassLoader(String basePath) {
        this.basePath = basePath;
    }
    
    @Override
    protected Class<?> findClass(String name) throws ClassNotFoundException {
        // 将包名转换为路径
        String fileName = name.replace('.', '/') + ".class";
        String fullPath = basePath + "/" + fileName;
        
        try (InputStream is = new FileInputStream(fullPath);
             ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
            
            byte[] buffer = new byte[1024];
            int len;
            while ((len = is.read(buffer)) != -1) {
                bos.write(buffer, 0, len);
            }
            
            byte[] classData = bos.toByteArray();
            // 将字节数组转换为Class对象
            return defineClass(name, classData, 0, classData.length);
            
        } catch (IOException e) {
            throw new ClassNotFoundException(name, e);
        }
    }
    
    public static void main(String[] args) throws Exception {
        CustomClassLoader loader = new CustomClassLoader("/tmp/classes");
        Class<?> clazz = loader.loadClass("com.example.Hello");
        Object obj = clazz.getDeclaredConstructor().newInstance();
        System.out.println("类加载器: " + obj.getClass().getClassLoader());
    }
}
```

### 3.2 常见的自定义类加载器应用场景

**场景一：加密类加载**

对class文件进行加密，运行时通过自定义类加载器解密后加载，防止反编译：

```java
@Override
protected Class<?> findClass(String name) throws ClassNotFoundException {
    String fileName = name.replace('.', '/') + ".class";
    byte[] encrypted = readFile(fileName);
    // 解密操作
    byte[] decrypted = decrypt(encrypted);
    return defineClass(name, decrypted, 0, decrypted.length);
}
```

**场景二：热部署**

在不停服的情况下加载新版本的类。关键是每次加载都生成新的类加载器实例，旧类连同旧类加载器一起被GC回收：

```java
public class HotDeployLoader {
    private URLClassLoader classLoader;
    
    public void reload(String jarPath) throws Exception {
        // 关闭旧的类加载器
        if (classLoader != null) {
            classLoader.close();
        }
        // 创建新的类加载器
        classLoader = new URLClassLoader(new URL[]{new URL(jarPath)});
    }
    
    public Class<?> loadClass(String className) throws Exception {
        return classLoader.loadClass(className);
    }
}
```

**场景三：隔离不同版本的同名类**

在同一个JVM进程中加载两个不同版本的同一类（如同时运行多个插件）：

```java
// 不同版本的类用不同的类加载器加载
URLClassLoader loader1 = new URLClassLoader(new URL[]{url1}); // v1.0
URLClassLoader loader2 = new URLClassLoader(new URL[]{url2}); // v2.0

Class<?> clazz1 = loader1.loadClass("com.plugin.Api"); // v1.0的Api
Class<?> clazz2 = loader2.loadClass("com.plugin.Api"); // v2.0的Api

// clazz1 != clazz2，两个是不同的类！
```

---

## 四、JIT编译：运行期的性能加速器

### 4.1 为什么需要JIT编译

**Q: JVM为什么需要JIT编译器？它和AOT编译有什么区别？**

Java程序首先被编译为字节码（.class文件），然后由JVM解释执行。解释执行的优点是启动快、跨平台，但缺点是执行效率低——每条字节码指令都需要被翻译为机器码后才能执行，同一段代码可能被反复解释。

JIT（Just-In-Time）即时编译器的核心思想是：**把热点代码（Hot Spot Code）在运行期编译为本地机器码**，直接执行机器码，跳过解释环节，从而大幅提升执行效率。

这带来一个经典的 tradeoff：**预编译（AOT）** 的启动快但无法针对运行时信息优化，而 **JIT** 牺牲了启动性能，但在运行时能根据真实执行情况做激进优化。

### 4.2 热点代码检测：HotSpot的计数魔法

**Q: JVM如何判断哪些代码是热点代码？**

JIT编译器不会编译所有代码，而是只编译"热点代码"。HotSpot使用两种热点检测方式：

**方法级别的热点**：基于方法调用计数器，统计方法被调用次数。当计数器超过阈值（默认C1为1500，C2为10000，可以通过`-XX:CompileThreshold`调整），就触发JIT编译。

```java
// 方法调用计数器的默认阈值
-XX:CompileThreshold=10000  // 触发C2编译的调用次数阈值
```

**循环体的热点**：基于回边计数器（Back Edge Counter），统计循环体执行的次数。回边计数器和方法计数器加和超过阈值时触发编译。

HotSpot采用**逆优化**（Deoptimization）机制：当JIT编译后的代码在特殊情况下失效时（如类继承结构变化），会回退到解释执行，保证程序正确性。

### 4.3 分层编译：JIT的成长之路

**Q: 什么是分层编译？C1和C2编译器有什么区别？**

从JDK 7开始，HotSpot引入了**分层编译（Tiered Compilation）**机制，将编译过程分为多个层次：

| 层级 | 编译器 | 优化级别 | 特点 |
|-----|-------|---------|------|
| Tier 0 | 解释执行 | 无 | 程序启动最快 |
| Tier 1 | C1编译器（Client Compiler） | 中等 | 编译速度快，启动性能好 |
| Tier 2 | C1编译器+不完整profiling | 中高 | 收集更多运行数据 |
| Tier 3 | C1编译器+完整profiling | 高 | 收集最完整数据 |
| Tier 4 | C2编译器（Server Compiler） | 最高 | 激进优化，编译耗时长 |

**C1编译器（Client Compiler）**：编译速度快，优化程度中等，适合对启动性能敏感的场景。启用方式：`-client`（JDK 32位默认，64位JDK已移除此选项）。

**C2编译器（Server Compiler）**：采用激进优化策略（如逃逸分析、标量替换、条件分析等），编译速度慢但生成代码质量极高，执行效率最优。C2编译后的代码性能接近甚至超过C++编译的本地代码。

**分层编译的典型流程**：
1. 程序启动 → 解释执行（Tier 0）
2. 热点方法出现 → C1快速编译（Tier 1/2/3）
3. 收集足够profiling数据 → C2深度优化编译（Tier 4）

在JDK 8中，分层编译默认开启（`-XX:+TieredCompilation`）。可以通过参数控制各层级的启用状态。

### 4.4 逃逸分析：JIT的杀手锏优化

**Q: JIT编译器有哪些核心优化手段？逃逸分析是什么？**

逃逸分析（Escape Analysis）是JIT编译器最强大的优化手段之一。它分析对象的动态作用域（是否"逃逸"出方法或线程），从而决定是否可以进行激进的优化。

**逃逸的三种程度**：

```java
public class EscapeDemo {
    
    // 不逃逸：对象只在方法内部使用
    void noEscape() {
        Object obj = new Object();
        obj.process(); // 只在方法内使用
        // JIT可能：1. 栈上分配 2. 标量替换
    }
    
    // 方法逃逸：作为返回值传出
    Object methodEscape() {
        Object obj = new Object();
        return obj; // 逃逸到方法外部
    }
    
    // 线程逃逸：被其他线程引用
    static Object shared; // 被类变量引用，线程逃逸
    
    void threadEscape() {
        shared = new Object(); // 逃逸到线程级别
    }
}
```

**逃逸分析的三大优化**：

**1. 栈上分配（Stack Allocation）**

在Java中，对象默认在堆上分配（由GC管理）。但如果逃逸分析确定对象不逃逸，则可以直接在栈上分配——随着方法结束自动回收，无需GC介入，减少了GC压力。

```java
void process() {
    // 如果这个User对象不逃逸，JIT会将其分配在栈上
    User user = new User();
    user.setName("test");
    user.compute();
}
```

**注意**：JDK 11的ZGC和JDK 15后的G1实际上已经不再支持栈上分配（HotSpot移除了这个优化），因为它带来的收益被GC的进步所超越。但逃逸分析的其他优化仍然有效。

**2. 标量替换（Scalar Replacement）**

标量（Scalar）指无法再分解的基本类型和引用类型。能分解的叫聚合量（Aggregate）。如果对象不逃逸且其成员变量只需要部分，JIT会将对象拆解为其成员变量，直接使用这些"标量"代替对象：

```java
// 原代码
void process() {
    Point p = new Point(1, 2);
    return p.x + p.y;
}

// 逃逸分析后，JIT可能优化为：
void process() {
    int x = 1;
    int y = 2;
    return x + y; // 对象完全被消除
}
```

这个优化可以彻底消除对象分配开销。

**3. 同步消除（Lock Elision）**

如果逃逸分析确定对象只在一个线程中使用，那么对它的加锁操作就是多余的，JIT编译器可以直接消除这个锁：

```java
void process() {
    synchronized (lock) {
        // 如果lock对象不逃逸，JIT消除这个锁
        doWork();
    }
}
```

这个优化在JDK 6之后默认开启，效果显著——很多单线程代码中看似有锁的代码实际上被完全消除了同步开销。

### 4.5 JIT日志与诊断

**Q: 如何查看JIT编译日志？如何判断JIT是否生效？**

通过JVM参数开启JIT编译日志：

```bash
# 打印编译活动日志
-XX:+PrintCompilation

# 打印更详细的编译日志（包含内联信息）
-XX:+PrintInlining

# 打印GC前后详细信息
-XX:+PrintGCDetails -XX:+PrintGCDateStamps

# 输出到文件
-Xlog:compilation=info:file=hotspot.log:time,uptime
```

示例输出：

```
11,234 |  3 |  1 | java.lang.String::charAt (29 bytes)
  1.5%     4 |  2 |  0 | java.lang.String::charAt @ 10 (29 bytes)
```

这表示`String.charAt`方法在23000次调用后被触发编译，编译耗时1.5毫秒，产生了1个优化建议（内联）。

---

## 五、实战：类加载与JIT在生产中的常见问题

### 5.1 类加载导致的Full GC

**Q: 类加载过多会导致GC问题吗？**

会的。当大量类被动态加载（如通过反射、CGLIB、OSGi等），Metaspace（元空间）会被持续消耗。如果Metaspace不足，会触发Full GC来尝试卸载不需要的类。

```
Metaspace: used=78M, capacity=96M, max= unbounded
Allocation Failed. Triggered Full GC.
```

**解决方案**：合理设置Metaspace大小，监控类加载数量：

```bash
# 设置Metaspace上限（推荐）
-XX:MaxMetaspaceSize=256m

# 监控类加载
-verbose:class
```

### 5.2 JIT热身与预热

**Q: JIT编译导致的性能曲线是什么样的？如何预热？**

JIT编译导致程序性能随时间变化的经典曲线：

```
性能
  |         ╭──────── JIT编译完成，性能达到峰值
  |        /
  |      /
  |     /  ← JIT编译中
  |    /
  |───/───── 解释执行
  └────────────── 时间
   0   预热期  稳定期
```

**预热策略**：

```java
// Warmup工具类示例
public class JITWarmup {
    public static void main(String[] args) {
        // 先预热：执行1000次让JIT触发编译
        for (int i = 0; i < 1000; i++) {
            hotMethod();
        }
        // 预热完成后，真正的基准测试/流量开始
        long start = System.nanoTime();
        // ...
    }
    
    // 使用@Warmup注解（JMH框架）
    @Warmup(iterations = 10)
    public void benchmark() {
        hotMethod();
    }
}
```

**JMH（Java Microbenchmark Harness）** 是官方推荐的微基准测试工具，能够自动处理JIT预热、多次测量、统计验证等问题，是评估JIT优化效果的标准工具。

### 5.3 类加载器泄漏的排查

**Q: 什么是类加载器泄漏？如何排查？**

类加载器泄漏（ClassLoader Leak）是指类的元数据（Class对象）被某个类加载器加载后，由于引用链的存在，该类加载器无法被GC，导致其加载的所有类都无法卸载。这是生产环境中内存泄漏的重要原因之一。

**典型场景**：
- 自定义类加载器加载的类被`static`集合持有引用
- ThreadLocal持有业务类引用，而线程未结束
- JDBC驱动的类加载器注册到DriverManager后未注销

**排查工具**：Eclipse MAT的"Class Loader Explorer"、JProfiler、Arthas的`classloader`命令。

```bash
# Arthas查看类加载器
 Arthas> classloader -l
 Arthas> classloader -t  // 查看类加载器层级
 Arthas> sc -d com.example.MyClass  // 查看类的加载器
```

---

## 六、知识全景图与面试核心要点

### 6.1 本系列知识脉络

经过四篇文章的梳理，JVM调优面试八股文系列已经覆盖了以下核心知识域：

| 维度 | 内容 | 覆盖 |
|-----|------|-----|
| 内存模型 | 运行时数据区、堆/栈/元空间 | ✅ 第一篇 |
| GC算法 | 标记-清除/复制/整理、分代假说 | ✅ 第一篇 |
| 垃圾收集器 | Serial/Parallel/CMS/G1/ZGC/Shenandoah | ✅ 第二篇 |
| 调优实战 | 参数设置、GC日志、Arthas、Dump分析 | ✅ 第三篇 |
| 类加载 | 双亲委派、生命周期、自定义加载器 | ✅ 本文 |
| JIT编译 | 分层编译、C1/C2、逃逸分析 | ✅ 本文 |

### 6.2 面试高频问题清单

以下是本主题在面试中出现的典型问题，按难度分级：

**初级**：
- 类加载的三个阶段是什么？
- 双亲委派模型是什么？
- 有哪些内置类加载器？
- JIT是什么？和AOT有什么区别？

**中级**：
- 为什么需要双亲委派模型？
- 什么情况下需要打破双亲委派？举三个例子
- 如何自定义一个类加载器？
- C1和C2编译器各有什么特点？
- 什么是逃逸分析？它能带来哪些优化？

**高级**：
- 线程上下文类加载器解决了什么问题？
- 描述类加载器泄漏的成因与排查思路
- 分层编译各层级的区别是什么？
- JIT热身的原理是什么？如何做性能预热？

---

## 下一期预告

JVM调优面试八股文系列即将迎来尾声。**第五篇**我们将聚焦最后一个核心主题：**JVM问题排查综合实战与最新版本特性**。内容包括：

- JDK 11+新特性对JVM的影响（ZGC、Shenandoah、Epsilon GC）
- G1调优的关键参数与最佳实践
- 生产环境JVM配置推荐模板
- 常见OOM场景的终极排查路径

敬请期待！
