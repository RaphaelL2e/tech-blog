---
title: "Spring 循环依赖与三级缓存深度解析"
date: 2026-05-12T10:45:00+08:00
draft: false
categories: ["spring"]
tags: ["spring", "circular-dependency", "three-level-cache", "aop"]
---


# Spring 循环依赖与三级缓存深度解析

> 面试高频问题：Spring 如何解决循环依赖？三级缓存是什么？构造器循环依赖能解决吗？

## 引言

循环依赖是 Spring 容器中常见的问题：Bean A 依赖 Bean B，Bean B 又依赖 Bean A。Spring 通过三级缓存巧妙地解决了字段注入和 setter 注入的循环依赖，但构造器注入的循环依赖无法解决。本文将深度解析 Spring 的三级缓存机制。

## 一、什么是循环依赖？

### 1.1 循环依赖场景

```java
// 场景 1：A → B → A
@Component
public class A {
    @Autowired
    private B b;
}

@Component
public class B {
    @Autowired
    private A a;
}

// 场景 2：A → B → C → A（三角依赖）
@Component
public class A {
    @Autowired
    private B b;
}
@Component
public class B {
    @Autowired
    private C c;
}
@Component
public class C {
    @Autowired
    private A a;
}
```

### 1.2 没有缓存的问题

```
创建 A → 发现需要 B → 创建 B → 发现需要 A → 创建 A → ...
无限循环！
```

## 二、三级缓存

### 2.1 三级缓存定义

```java
// DefaultSingletonBeanRegistry

// 一级缓存：成品 Bean（完全初始化）
private final Map<String, Object> singletonObjects = new ConcurrentHashMap<>(256);

// 二级缓存：半成品 Bean（已实例化，未初始化）
private final Map<String, Object> earlySingletonObjects = new ConcurrentHashMap<>(16);

// 三级缓存：ObjectFactory（Bean 工厂）
private final Map<String, ObjectFactory<?>> singletonFactories = new HashMap<>(16);
```

| 缓存 | 名称 | 存储内容 | 状态 |
|------|------|---------|------|
| 一级 | `singletonObjects` | 完整的 Bean | 成品 |
| 二级 | `earlySingletonObjects` | 早期引用（可能被代理）| 半成品 |
| 三级 | `singletonFactories` | ObjectFactory | 工厂 |

### 2.2 为什么需要三级？

**问题**：如果只有一级缓存，会有什么问题？

```
1. A 实例化，放入一级缓存
2. A 注入 B，发现 B 不存在
3. 创建 B，B 注入 A，从一级缓存获取 A（但 A 还没初始化完！）
4. 结果：B 持有了未初始化的 A → 可能导致空指针
```

**问题**：如果只有两级缓存，会有什么问题？

```
考虑 AOP 场景：
1. A 实例化，创建 A 的 ObjectFactory
2. A 注入 B
3. B 需要 A，通过 ObjectFactory 获取 A 的代理
4. A 初始化时，AOP 又创建了一个代理
5. 结果：B 持有代理 1，容器中是代理 2 → 不一致！
```

**三级缓存解决**：ObjectFactory 可以保证代理对象只创建一次。

### 2.3 三级缓存流程

```
创建 Bean A：
│
├─ 1. 实例化 A（调用构造函数）
│   └─ 将 A 的 ObjectFactory 放入三级缓存
│      singletonFactories.put("a", () -> getEarlyBeanReference("a", beanDefinition, a))
│
├─ 2. 填充属性（注入 B）
│   └─ 发现需要 B
│   │
│   ├─ 3. 创建 Bean B：
│   │   ├─ 3.1 实例化 B
│   │   │   └─ 将 B 的 ObjectFactory 放入三级缓存
│   │   │
│   │   ├─ 3.2 填充属性（注入 A）
│   │   │   └─ 发现需要 A
│   │   │   │
│   │   │   ├─ 查一级缓存：singletonObjects.get("a") → null
│   │   │   ├─ 查二级缓存：earlySingletonObjects.get("a") → null
│   │   │   ├─ 查三级缓存：singletonFactories.get("a") → ObjectFactory
│   │   │   │   └─ 调用 ObjectFactory.getObject()
│   │   │   │       └─ 返回 A 的早期引用（可能是代理）
│   │   │   │
│   │   │   ├─ 将 A 的早期引用放入二级缓存
│   │   │   │   earlySingletonObjects.put("a", earlyA)
│   │   │   │
│   │   │   └─ 从三级缓存移除 A
│   │   │       singletonFactories.remove("a")
│   │   │
│   │   ├─ 3.3 B 初始化
│   │   │
│   │   └─ 3.4 B 创建完成
│   │       ├─ 放入一级缓存：singletonObjects.put("b", b)
│   │       ├─ 清除二级缓存：earlySingletonObjects.remove("b")
│   │       └─ 清除三级缓存：singletonFactories.remove("b")
│   │
│   └─ B 注入成功
│
├─ 4. A 初始化
│
└─ 5. A 创建完成
    ├─ 放入一级缓存：singletonObjects.put("a", a)
    ├─ 清除二级缓存：earlySingletonObjects.remove("a")
    └─ 清除三级缓存：singletonFactories.remove("a")
```

## 三、源码解析

### 3.1 getSingleton（获取 Bean）

```java
// DefaultSingletonBeanRegistry.getSingleton()
public Object getSingleton(String beanName) {
    // 1. 查一级缓存
    Object singletonObject = this.singletonObjects.get(beanName);
    
    if (singletonObject == null && isSingletonCurrentlyInCreation(beanName)) {
        // 2. 查二级缓存
        singletonObject = this.earlySingletonObjects.get(beanName);
        
        if (singletonObject == null) {
            // 3. 查三级缓存
            ObjectFactory<?> singletonFactory = this.singletonFactories.get(beanName);
            
            if (singletonFactory != null) {
                // 调用 ObjectFactory 获取早期引用
                singletonObject = singletonFactory.getObject();
                
                // 放入二级缓存
                this.earlySingletonObjects.put(beanName, singletonObject);
                
                // 从三级缓存移除
                this.singletonFactories.remove(beanName);
            }
        }
    }
    
    return singletonObject;
}
```

### 3.2 doCreateBean（创建 Bean）

```java
// AbstractAutowireCapableBeanFactory.doCreateBean()
protected Object doCreateBean(String beanName, RootBeanDefinition mbd, Object[] args) {
    // 1. 实例化 Bean（调用构造函数）
    BeanWrapper instanceWrapper = createBeanInstance(beanName, mbd, args);
    Object bean = instanceWrapper.getWrappedInstance();
    
    // 2. 提前暴露：将 ObjectFactory 放入三级缓存
    boolean earlySingletonExposure = mbd.isSingleton() && 
        this.allowCircularReferences &&  // 允许循环依赖
        isSingletonCurrentlyInCreation(beanName);
    
    if (earlySingletonExposure) {
        addSingletonFactory(beanName, 
            () -> getEarlyBeanReference(beanName, mbd, bean));  // 三级缓存
    }
    
    // 3. 填充属性（依赖注入，可能触发循环依赖）
    populateBean(beanName, mbd, instanceWrapper);
    
    // 4. 初始化
    Object exposedObject = initializeBean(beanName, bean, mbd);
    
    return exposedObject;
}
```

### 3.3 getEarlyBeanReference（早期引用）

```java
// AbstractAutowireCapableBeanFactory.getEarlyBeanReference()
protected Object getEarlyBeanReference(String beanName, RootBeanDefinition mbd, Object bean) {
    Object exposedObject = bean;
    
    // AOP 代理创建
    for (SmartInstantiationAwareBeanPostProcessor bp : getBeanPostProcessorCache().smartInstantiationAware) {
        exposedObject = bp.getEarlyBeanReference(exposedObject, beanName);
    }
    
    return exposedObject;
}
```

**关键**：`getEarlyBeanReference` 是 AOP 代理的提前创建入口。

### 3.4 AOP 与循环依赖

```
没有循环依赖时：
  实例化 → 注入 → 初始化 → BeanPostProcessor 创建代理

有循环依赖时：
  实例化 → 提前暴露 ObjectFactory → 注入时触发代理创建 → 初始化

关键：AbstractAutoProxyCreator
  - 正常：postProcessAfterInitialization() 创建代理
  - 循环依赖：getEarlyBeanReference() 提前创建代理
  - 通过 earlyProxyReferences 缓存保证只创建一次
```

```java
// AbstractAutoProxyCreator
public Object getEarlyBeanReference(Object bean, String beanName) {
    Object cacheKey = getCacheKey(bean.getClass(), beanName);
    this.earlyProxyReferences.put(cacheKey, bean);  // 标记已提前创建代理
    return wrapIfNecessary(bean, beanName, cacheKey);  // 创建代理
}

public Object postProcessAfterInitialization(Object bean, String beanName) {
    Object cacheKey = getCacheKey(bean.getClass(), beanName);
    if (this.earlyProxyReferences.remove(cacheKey) != bean) {
        // 没有提前创建代理，正常创建
        return wrapIfNecessary(bean, beanName, cacheKey);
    }
    // 已提前创建代理，直接返回
    return bean;
}
```

## 四、构造器循环依赖

### 4.1 为什么不能解决？

```java
@Component
public class A {
    private final B b;
    
    @Autowired
    public A(B b) {  // 构造器注入
        this.b = b;
    }
}

@Component
public class B {
    private final A a;
    
    @Autowired
    public B(A a) {  // 构造器注入
        this.a = a;
    }
}
```

**原因**：
- 三级缓存在**实例化之后**才暴露
- 构造器注入在**实例化时**就需要依赖
- 此时 ObjectFactory 还没放入三级缓存

```
创建 A → 构造函数需要 B → 创建 B → 构造函数需要 A → 一级缓存没有 → 二级缓存没有 → 三级缓存没有
→ 抛出 BeanCurrentlyInCreationException
```

### 4.2 解决方案

**方案 1：改用字段注入或 setter 注入**

```java
@Component
public class A {
    @Autowired
    private B b;  // 字段注入，可以解决
}
```

**方案 2：使用 @Lazy 延迟注入**

```java
@Component
public class A {
    private final B b;
    
    @Autowired
    public A(@Lazy B b) {  // 延迟注入代理
        this.b = b;
    }
}
```

**@Lazy 原理**：注入的是 B 的代理对象，只有真正调用 B 的方法时才会创建 B。

## 五、Spring Boot 2.6+ 的变化

### 5.1 默认禁止循环依赖

```yaml
# Spring Boot 2.6+ 默认禁止循环依赖
spring:
  main:
    allow-circular-references: false  # 默认 false

# 如需开启
spring:
  main:
    allow-circular-references: true
```

### 5.2 为什么默认禁止？

- 循环依赖是设计问题
- 表明组件职责不清晰
- 建议通过重构解决

## 六、面试高频问题

### Q1：Spring 如何解决循环依赖？

**答**：通过三级缓存：
1. **一级缓存**：`singletonObjects`（成品 Bean）
2. **二级缓存**：`earlySingletonObjects`（半成品 Bean）
3. **三级缓存**：`singletonFactories`（ObjectFactory）

流程：实例化 → 放入三级缓存 → 注入时从三级缓存获取 → 放入二级缓存 → 初始化完成 → 放入一级缓存

### Q2：为什么需要三级缓存？两级不行吗？

**答**：
- 如果没有 AOP，两级缓存就够了
- 有 AOP 时，三级缓存保证代理对象只创建一次
- ObjectFactory 可以延迟决定是否创建代理

### Q3：构造器循环依赖能解决吗？

**答**：不能。因为三级缓存在实例化后才暴露，而构造器注入在实例化时就需要依赖。解决方式：`@Lazy` 或改用字段/Setter 注入。

### Q4：@Lazy 如何解决构造器循环依赖？

**答**：注入的是代理对象，不立即创建真实 Bean，调用时才创建。

### Q5：Spring Boot 2.6 为什么要默认禁止循环依赖？

**答**：
- 循环依赖是设计缺陷
- 建议通过重构解耦
- 而不是依赖 Spring 的三级缓存

## 七、总结

**三级缓存核心要点**：
- **一级缓存**：完整 Bean
- **二级缓存**：早期引用（处理代理）
- **三级缓存**：ObjectFactory（延迟创建代理）

**循环依赖解决范围**：
| 注入方式 | 能否解决 |
|---------|---------|
| 字段注入 | ✅ |
| Setter 注入 | ✅ |
| 构造器注入 | ❌ |

**最佳实践**：
1. 避免循环依赖（重构代码）
2. 构造器注入 + `@Lazy` 解决
3. Spring Boot 2.6+ 默认禁止循环依赖
4. 理解三级缓存原理，但不要依赖它

---

**本系列 Java 面试八股文 Spring 模块完结 ✅**

**下一篇预告**：MySQL 索引与查询优化深度解析

**参考资料**：
- Spring 官方文档：https://docs.spring.io/spring-framework/docs/current/reference/html/core.html
- 《Spring 源码深度解析》- 郝佳
- Spring 源码：org.springframework.beans.factory.support.DefaultSingletonBeanRegistry
