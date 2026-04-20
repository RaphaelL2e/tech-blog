---
title: "Java设计模式（一）：单例模式完全指南"
date: 2026-04-13T13:30:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "单例模式", "singleton"]
---

## 前言

设计模式是软件开发中经过验证的解决方案模板，是前辈们智慧的结晶。从本期开始，我们将开启 Java 设计模式系列文章，系统讲解 23 种经典设计模式。

**第一篇：单例模式（Singleton Pattern）**

单例模式是最简单也是最常用的设计模式之一，确保一个类只有一个实例，并提供一个全局访问点。

<!--more-->

## 一、什么是单例模式

### 1.1 定义

> 确保某一个类只有一个实例，并且提供一个全局的访问点。

### 1.2 解决的问题

- 避免重复创建对象，节省资源
- 避免多个实例导致数据不一致
- 全局共享同一个配置或状态

### 1.3 常见应用场景

| 场景 | 示例 |
|------|------|
| 配置管理器 | 全局配置文件 |
| 连接池 | 数据库连接池 |
| 日志管理器 | 统一日志输出 |
| 缓存 | 全局缓存实例 |
| 计数器 | 全局访问计数器 |

## 二、单例模式的实现方式

### 2.1 饿汉式（静态常量）

```java
public class SingletonHunger {
    
    // 类加载时就创建实例
    private static final SingletonHunger INSTANCE = new SingletonHunger();
    
    // 私有构造函数
    private SingletonHunger() {}
    
    // 对外提供访问点
    public static SingletonHunger getInstance() {
        return INSTANCE;
    }
}
```

**优点**：线程安全，类加载时创建，无同步开销
**缺点**：类加载时就创建，可能造成资源浪费

### 2.2 饿汉式（静态代码块）

```java
public class SingletonHungerBlock {
    
    private static final SingletonHungerBlock INSTANCE;
    
    static {
        INSTANCE = new SingletonHungerBlock();
    }
    
    private SingletonHungerBlock() {}
    
    public static SingletonHungerBlock getInstance() {
        return INSTANCE;
    }
}
```

### 2.3 懒汉式（线程不安全）

```java
public class SingletonLazy {
    
    private static SingletonLazy instance;
    
    private SingletonLazy() {}
    
    public static SingletonLazy getInstance() {
        if (instance == null) {
            instance = new SingletonLazy();
        }
        return instance;
    }
}
```

**优点**：延迟加载，按需创建
**缺点**：线程不安全，多线程下可能创建多个实例

### 2.4 懒汉式（线程安全 - synchronized）

```java
public class SingletonLazySync {
    
    private static SingletonLazySync instance;
    
    private SingletonLazySync() {}
    
    // 使用 synchronized 保证线程安全
    public static synchronized SingletonLazySync getInstance() {
        if (instance == null) {
            instance = new SingletonLazySync();
        }
        return instance;
    }
}
```

**优点**：线程安全
**缺点**：每次获取实例都需要同步，性能开销大

### 2.5 双重检查锁定（DCL）

```java
public class SingletonDCL {
    
    // volatile 防止指令重排序
    private static volatile SingletonDCL instance;
    
    private SingletonDCL() {}
    
    public static SingletonDCL getInstance() {
        // 第一次检查：避免不必要的同步
        if (instance == null) {
            synchronized (SingletonDCL.class) {
                // 第二次检查：防止多线程重复创建
                if (instance == null) {
                    instance = new SingletonDCL();
                }
            }
        }
        return instance;
    }
}
```

**优点**：延迟加载，线程安全，性能优秀
**注意**：必须使用 `volatile` 修饰，否则可能出现指令重排序问题

### 2.6 静态内部类

```java
public class SingletonStaticInner {
    
    private SingletonStaticInner() {}
    
    // 静态内部类，延迟加载
    private static class SingletonHolder {
        private static final SingletonStaticInner INSTANCE = 
            new SingletonStaticInner();
    }
    
    public static SingletonStaticInner getInstance() {
        return SingletonHolder.INSTANCE;
    }
}
```

**优点**：延迟加载，线程安全，无需同步
**原理**：JVM 保证类的初始化阶段的线程安全性

### 2.7 枚举单例

```java
public enum SingletonEnum {
    
    INSTANCE;
    
    // 可以添加业务方法
    public void doSomething() {
        System.out.println("枚举单例方法执行");
    }
    
    // 使用方式
    public static void main(String[] args) {
        SingletonEnum instance = SingletonEnum.INSTANCE;
        instance.doSomething();
    }
}
```

**优点**：
- 线程安全
- 防止反射攻击
- 防止反序列化创建新实例
- 简洁优雅

**推荐指数**：⭐⭐⭐⭐⭐

## 三、单例模式的破坏与防护

### 3.1 反射攻击

通过反射调用私有构造函数创建新实例：

```java
// 攻击代码
Constructor<SingletonDCL> constructor = SingletonDCL.class
    .getDeclaredConstructor();
constructor.setAccessible(true);
SingletonDCL s1 = constructor.newInstance();
SingletonDCL s2 = constructor.newInstance();
System.out.println(s1 == s2); // false
```

**防护方法**：在构造函数中抛出异常

```java
private SingletonDCL() {
    if (instance != null) {
        throw new RuntimeException("单例模式禁止反射调用");
    }
}
```

### 3.2 序列化攻击

反序列化时可能创建新实例：

```java
// 序列化
SingletonDCL s1 = SingletonDCL.getInstance();
ObjectOutputStream oos = new ObjectOutputStream(
    new FileOutputStream("singleton.obj"));
oos.writeObject(s1);

// 反序列化
ObjectInputStream ois = new ObjectInputStream(
    new FileInputStream("singleton.obj"));
SingletonDCL s2 = (SingletonDCL) ois.readObject();
System.out.println(s1 == s2); // false
```

**防护方法**：添加 `readResolve` 方法

```java
private Object readResolve() {
    return instance;
}
```

### 3.3 枚举单例天然防护

```java
// 序列化
SingletonEnum s1 = SingletonEnum.INSTANCE;

// 反序列化
SingletonEnum s2 = Enum.valueOf(SingletonEnum.class, "INSTANCE");
System.out.println(s1 == s2); // true
```

枚举单例自动防护反射和序列化攻击。

## 四、单例模式在源码中的应用

### 4.1 Spring 中的单例

```java
// org.springframework.beans.factory.support.DefaultSingletonBeanRegistry
public class DefaultSingletonBeanRegistry ... {
    // 使用 ConcurrentHashMap 存储单例
    private final Map<String, Object> singletonObjects = 
        new ConcurrentHashMap<>(256);
    
    protected void addSingleton(String beanName, Object singletonObject) {
        synchronized (this.singletonObjects) {
            this.singletonObjects.put(beanName, singletonObject);
        }
    }
}
```

### 4.2 MyBatis 中的单例

```java
// org.apache.ibatis.executor.ErrorContext
public class ErrorContext {
    // 线程本地存储，确保线程隔离
    private static final ThreadLocal<ErrorContext> LOCAL = 
        new ThreadLocal<>();
    
    public static ErrorContext instance() {
        ErrorContext context = LOCAL.get();
        if (context == null) {
            context = new ErrorContext();
            LOCAL.set(context);
        }
        return context;
    }
}
```

### 4.3 JDK 中的单例

```java
// java.lang.Runtime
public class Runtime {
    private static Runtime currentRuntime;
    
    public static Runtime getRuntime() {
        if (currentRuntime == null) {
            synchronized (Runtime.class) {
                if (currentRuntime == null) {
                    currentRuntime = new Runtime();
                }
            }
        }
        return currentRuntime;
    }
}
```

```java
// java.lang.System
public final class System {
    private static volatile SecurityManager securityManager;
    
    private static SecurityManager getSecurityManager() {
        return securityManager;
    }
}
```

## 五、单例模式最佳实践

### 5.1 推荐实现方式

| 场景 | 推荐方式 |
|------|----------|
| 一般情况 | 枚举单例 |
| 需要延迟加载 | 静态内部类 |
| 追求极致性能 | DCL |
| 简单场景 | 饿汉式 |

### 5.2 单例模式的优缺点

**优点**：
- 减少内存开销
- 避免资源的多重占用
- 提供全局访问点
- 便于代码维护

**缺点**：
- 不符合单一职责原则
- 可能导致代码耦合度增加
- 难以进行单元测试
- 扩展困难

### 5.3 使用建议

1. **优先使用枚举单例**，安全又简洁
2. **避免滥用单例**，不是所有场景都需要
3. **注意线程安全**，确保单例的唯一性
4. **考虑生命周期**，确定单例的销毁时机

## 六、面试常见问题

### Q1：单例模式有几种实现方式？

常见的有 7 种：饿汉式（静态常量和静态代码块）、懒汉式（线程不安全+synchronized）、双重检查锁定、静态内部类、枚举。

### Q2：为什么要用 volatile 修饰？

防止指令重排序。`instance = new SingletonDCL()` 实际上包含三个步骤：
1. 分配内存
2. 执行构造函数
3. 将引用指向内存

volatile 可以防止步骤 2 和 3 的重排序，确保对象完全初始化后再赋值。

### Q3：静态内部类实现单例的原理？

JVM 在类的初始化阶段会加锁，同一时间只有一个线程可以执行类的初始化方法。静态内部类只有在被调用时才会加载，实现了延迟加载。

### Q4：枚举单例为什么是线程安全的？

枚举类的初始化由 JVM 在类加载阶段保证线程安全，且枚举实例的创建是原子性的。

## 结语

单例模式虽然简单，但在实际开发中应用广泛。选择合适的实现方式，考虑线程安全和资源利用，才能用好这一经典模式。

**下期预告**：工厂模式（Factory Pattern）

> 记住：**模式是指导，不是束缚**。根据实际场景灵活运用，才能写出优雅的代码。
