---
title: "Spring面试八股文（一）——Spring核心概念与IoC容器"
date: 2026-06-23T09:00:00+08:00
draft: false
categories: ["Spring"]
tags: ["面试", "八股文", "Spring", "IoC", "依赖注入", "DI", "Bean", "ApplicationContext", "BeanFactory", "循环依赖", "三级缓存"]
---

# Spring面试八股文（一）——Spring核心概念与IoC容器

> 🎯 **本文目标**：从Spring框架的设计哲学出发，深入剖析IoC容器的工作机制——包括依赖注入的三种方式、Bean的完整生命周期、ApplicationContext与BeanFactory的本质区别、Spring如何通过三级缓存解决循环依赖等核心面试高频考点，构建Spring基础知识的完整框架。

---

## 一、Spring框架概述——为什么需要Spring？

### 1.1 Spring解决了什么问题？

**Q: 没有Spring的Java开发是什么样的？**

```java
// 没有Spring时：手动管理依赖，代码耦合严重
public class OrderService {
    private OrderRepository repository = new OrderRepositoryImpl(); // 硬编码依赖
    private PaymentService paymentService = new AlipayPaymentService(); // 换支付方式要改代码
    
    public void createOrder(Order order) {
        repository.save(order);
        paymentService.pay(order);
    }
}
```

**Spring的核心价值：**

| 问题 | 传统方式 | Spring方案 |
|------|---------|-----------|
| 对象创建与管理 | `new`关键字硬编码 | IoC容器统一管理 |
| 依赖关系维护 | 手动组装，代码耦合 | 依赖注入（DI），松耦合 |
| 事务管理 | 手动commit/rollback | 声明式事务`@Transactional` |
| AOP横切关注点 | 代码散落各处 | 统一切面，集中管理 |
| 样板代码 | 大量try-catch、JDBC模板 | JdbcTemplate、RestTemplate |

### 1.2 Spring生态全景

```
Spring Framework (核心)
    ├── Spring Boot (自动配置，快速启动)
    │   ├── Spring MVC (Web层)
    │   ├── Spring Data (数据访问)
    │   └── Spring Security (安全)
    ├── Spring Cloud (微服务全家桶)
    │   ├── 服务注册与发现 (Eureka/Nacos/Consul)
    │   ├── 配置中心 (Config/Nacos)
    │   ├── 网关 (Gateway/Zuul)
    │   └── 熔断降级 (Hystrix/Sentinel)
    └── Spring Cloud Alibaba (国产微服务方案)
```

---

## 二、IoC——控制反转的哲学

### 2.1 什么是IoC？

**Q: 如何通俗理解IoC（Inversion of Control）？**

**生活类比**：你去餐厅吃饭

- **传统方式（没有IoC）**：你自己去菜市场买菜、洗菜、切菜、炒菜 → 你控制一切
- **IoC方式**：你只需要点菜（声明需求），厨师做好端上来（容器给你）→ 控制权交给了餐厅

```java
// 传统方式：自己控制对象创建
public class UserService {
    private UserDao userDao = new UserDaoImpl(); // 我控制创建
    // 想换实现？改代码！
}

// IoC方式：容器控制对象创建
public class UserService {
    @Autowired
    private UserDao userDao; // 容器给我什么就用什么
    // 想换实现？改配置！
}
```

**IoC的本质**：**将对象创建和依赖管理的控制权从程序代码转移给外部容器**。

### 2.2 IoC的实现方式——DI（依赖注入）

**Q: IoC和DI是什么关系？**

IoC是思想（控制反转），DI是实现方式（依赖注入）。就像"吃饭"是目标，"用筷子"是实现方式。

Spring支持三种依赖注入方式：

#### 方式一：构造器注入（推荐✅）

```java
@Service
public class OrderService {
    private final OrderRepository orderRepository;
    private final PaymentService paymentService;
    
    // 构造器注入：依赖不可变，有利于单元测试
    public OrderService(OrderRepository orderRepository, 
                        PaymentService paymentService) {
        this.orderRepository = orderRepository;
        this.paymentService = paymentService;
    }
}
```

**优点**：依赖不可变（final）、保证注入完整、方便单元测试（直接new传参）
**缺点**：依赖多时构造器参数多（但Refactor成多个Service是更好的做法）

#### 方式二：Setter注入

```java
@Service
public class OrderService {
    private OrderRepository orderRepository;
    
    @Autowired
    public void setOrderRepository(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }
}
```

**适用场景**：可选依赖、需要运行时重新注入

#### 方式三：字段注入（@Autowired在字段上）

```java
@Service
public class OrderService {
    @Autowired
    private OrderRepository orderRepository; // 字段注入
}
```

**问题**：无法使用final、难以单元测试（需要反射注入）、依赖隐藏（看不出有多少依赖）
**面试答**：知道但不推荐，构造器注入是最佳实践。

### 2.3 @Autowired vs @Resource

**Q: @Autowired和@Resource有什么区别？**

| 对比维度 | @Autowired | @Resource |
|---------|-----------|-----------|
| 来源 | Spring原生 | JSR-250（Java标准） |
| 默认装配 | byType | byName |
| 可选性 | `required=false` | 不支持 |
| 配合注解 | `@Qualifier` | `name`属性指定 |

```java
// @Autowired：按类型找，配合@Qualifier按名称
@Autowired
@Qualifier("alipayPaymentService")
private PaymentService paymentService;

// @Resource：默认按名称找，找不到按类型
@Resource(name = "alipayPaymentService")
private PaymentService paymentService;
```

### 2.4 @Qualifier vs @Primary

**Q: 多个同类型Bean时，Spring如何选择？**

```java
// 方案1：@Primary - 默认首选
@Service
@Primary  // ← 当存在多个PaymentService时，这个作为默认注入
public class WechatPaymentService implements PaymentService { }

// 方案2：@Qualifier - 按名称指定
@Autowired
@Qualifier("alipayPaymentService")  // ← 精确指定
private PaymentService paymentService;
```

**优先级**：`@Qualifier` > `@Primary` > byName > byType

---

## 三、Bean——Spring世界的原子单位

### 3.1 Bean的作用域（Scope）

**Q: Spring Bean有几种作用域？各自适用什么场景？**

| 作用域 | 说明 | 生命周期 | 典型场景 |
|-------|------|---------|---------|
| **singleton** | 单例（默认） | 容器启动→销毁 | Service、Dao、配置类 |
| **prototype** | 多例 | 每次获取创建新实例 | 有状态的Bean |
| **request** | 每次HTTP请求 | 请求结束销毁 | Web请求参数封装 |
| **session** | 每次HTTP会话 | 会话结束销毁 | 用户登录信息 |
| **application** | ServletContext级别 | 容器关闭销毁 | 全局共享数据 |
| **websocket** | WebSocket级别 | 连接关闭销毁 | WebSocket会话 |

```java
@Component
@Scope("prototype")  // 每次注入都是新对象
public class ShoppingCart {
    // 每个用户应该有独立的购物车，所以不能用单例
}
```

### 3.2 Bean的完整生命周期

**Q: 请描述Spring Bean的生命周期（面试高频题⭐⭐⭐⭐⭐）**

```
┌─────────────────────────────────────────────────────────────┐
│                    Spring Bean生命周期                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 实例化 (Instantiation)                                  │
│     └── 通过反射调用构造器创建对象实例                         │
│                          ↓                                   │
│  2. 属性赋值 (Populate Properties)                           │
│     └── 依赖注入，设置Bean属性值                              │
│                          ↓                                   │
│  3. Aware接口回调                                             │
│     ├── BeanNameAware.setBeanName()                         │
│     ├── BeanFactoryAware.setBeanFactory()                   │
│     └── ApplicationContextAware.setApplicationContext()     │
│                          ↓                                   │
│  4. BeanPostProcessor前置处理                                │
│     └── postProcessBeforeInitialization()                   │
│                          ↓                                   │
│  5. 初始化 (Initialization)                                  │
│     ├── @PostConstruct 标注的方法                             │
│     ├── InitializingBean.afterPropertiesSet()              │
│     └── init-method 指定的方法                                │
│                          ↓                                   │
│  6. BeanPostProcessor后置处理                                │
│     └── postProcessAfterInitialization()                    │
│                          ↓                                   │
│  7. Bean就绪，可以使用                                        │
│                                                             │
│  8. 销毁 (Destruction)                                      │
│     ├── @PreDestroy 标注的方法                                │
│     ├── DisposableBean.destroy()                            │
│     └── destroy-method 指定的方法                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**代码验证**：

```java
@Component
public class LifecycleBean implements InitializingBean, DisposableBean,
        BeanNameAware, ApplicationContextAware {
    
    public LifecycleBean() {
        System.out.println("1. 构造器调用");
    }
    
    @Autowired
    public void setDependency(OtherBean other) {
        System.out.println("2. 属性注入");
    }
    
    @Override
    public void setBeanName(String name) {
        System.out.println("3. BeanNameAware: " + name);
    }
    
    @Override
    public void setApplicationContext(ApplicationContext ctx) {
        System.out.println("3. ApplicationContextAware");
    }
    
    @PostConstruct
    public void init() {
        System.out.println("5. @PostConstruct");
    }
    
    @Override
    public void afterPropertiesSet() {
        System.out.println("5. InitializingBean");
    }
    
    @PreDestroy
    public void preDestroy() {
        System.out.println("8. @PreDestroy");
    }
    
    @Override
    public void destroy() {
        System.out.println("8. DisposableBean");
    }
}
```

---

## 四、ApplicationContext vs BeanFactory

**Q: ApplicationContext和BeanFactory有什么区别？**

| 对比维度 | BeanFactory | ApplicationContext |
|---------|------------|-------------------|
| 定位 | 最底层的IoC容器接口 | BeanFactory的子接口，功能丰富 |
| Bean加载时机 | **延迟加载**（首次getBean） | **预加载**（容器启动时实例化所有单例Bean） |
| 国际化（i18n） | ❌ 不支持 | ✅ MessageSource |
| 事件机制 | ❌ 不支持 | ✅ ApplicationEvent发布/监听 |
| 资源加载 | ❌ 手动 | ✅ ResourceLoader统一加载 |
| 集成AOP | ❌ 手动 | ✅ 自动后处理器 |
| 使用场景 | 内存敏感/移动端 | **99%的正常开发** |

```java
// BeanFactory：手动获取，延迟加载
BeanFactory factory = new XmlBeanFactory(new ClassPathResource("beans.xml"));
UserService service = (UserService) factory.getBean("userService"); // 这时才创建

// ApplicationContext：启动即创建所有单例Bean
ApplicationContext ctx = new ClassPathXmlApplicationContext("beans.xml");
UserService service = ctx.getBean(UserService.class); // 已经创建好了
```

**面试关键点**：`ApplicationContext`在启动时就实例化所有**非懒加载**的单例Bean，这样做的好处是**尽早发现配置错误**（fail-fast），缺点可能**延长启动时间**。

---

## 五、循环依赖——Spring的三级缓存机制

### 5.1 什么是循环依赖？

**Q: 什么是循环依赖？Spring如何解决？**

```java
@Service
public class A {
    @Autowired
    private B b;  // A依赖B
}

@Service
public class B {
    @Autowired
    private A a;  // B依赖A → 形成循环！
}
```

### 5.2 Spring三级缓存详解

```
Spring三级缓存（DefaultSingletonBeanRegistry中）：

┌──────────────────────────────────────────────────────┐
│ 一级缓存：singletonObjects                           │
│   Map<String, Object>                                │
│   存放：完全初始化好的单例Bean                         │
│   "成品仓库"                                          │
├──────────────────────────────────────────────────────┤
│ 二级缓存：earlySingletonObjects                       │
│   Map<String, Object>                                │
│   存放：实例化但未属性注入的早期引用                     │
│   "半成品中转站"                                       │
├──────────────────────────────────────────────────────┤
│ 三级缓存：singletonFactories                          │
│   Map<String, ObjectFactory<?>>                      │
│   存放：能生成早期引用的工厂                            │
│   "加工厂"                                            │
└──────────────────────────────────────────────────────┘
```

### 5.3 解决流程（以A和B的循环依赖为例）

```
步骤 1: 创建 A
  ├── 实例化 A（通过构造器）→ 此时A对象已存在但属性为空
  ├── 将 A 的 ObjectFactory 放入三级缓存
  │   └── ObjectFactory的作用：生成A的早期引用（可能会被AOP代理包装）
  ├── 开始注入 A 的属性 → 发现需要 B
  │
步骤 2: 创建 B（A的依赖）
  ├── 实例化 B
  ├── 开始注入 B 的属性 → 发现需要 A
  │   └── 去缓存找 A：
  │       一级缓存：❌ 没有（A还没初始化完）
  │       二级缓存：❌ 没有
  │       三级缓存：✅ 找到了A的ObjectFactory！
  │   └── 从三级缓存取出 → 生成A的早期引用 → 放入二级缓存
  │   └── 将A的早期引用注入B ✅
  ├── B的其他属性注入完毕
  ├── B的后置处理、初始化
  └── B存入一级缓存（完全初始化好的Bean）
  │
步骤 3: 继续创建 A（回到A的初始化流程）
  ├── 将B注入A（从一级缓存取到完整的B）
  ├── A的后置处理、初始化
  └── A存入一级缓存，清除二三级缓存中的A
```

### 5.4 为什么需要三级缓存？

**Q: 为什么是三级缓存而不是二级？**

**核心原因：AOP代理**

```java
@Component
public class A {
    @Autowired
    private B b;
    
    // 这个方法被切面增强了
    @Transactional  // ← AOP代理！
    public void doSomething() { }
}
```

如果只有二级缓存：
- A的早期引用是**原始对象**
- B被注入了原始对象（没有AOP增强的）
- A初始化完成后变成了**代理对象**（有AOP增强的）
- **问题**：B持有的A是原始对象，无法使用AOP增强 → 不一致！

有了三级缓存（ObjectFactory）：
- ObjectFactory在生成早期引用时，会经过`SmartInstantiationAwareBeanPostProcessor`
- 可以**提前返回代理对象**而非原始对象
- 保证：从哪里取都是同一个代理对象 → 一致！

```java
// 简化版三级缓存源码逻辑
protected Object getSingleton(String beanName, boolean allowEarlyReference) {
    Object singletonObject = this.singletonObjects.get(beanName);  // 一级
    if (singletonObject == null && isSingletonCurrentlyInCreation(beanName)) {
        singletonObject = this.earlySingletonObjects.get(beanName); // 二级
        if (singletonObject == null && allowEarlyReference) {
            ObjectFactory<?> singletonFactory = this.singletonFactories.get(beanName); // 三级
            if (singletonFactory != null) {
                singletonObject = singletonFactory.getObject(); // 通过工厂获取（可能返回代理）
                this.earlySingletonObjects.put(beanName, singletonObject); // 放入二级
                this.singletonFactories.remove(beanName); // 移出三级
            }
        }
    }
    return singletonObject;
}
```

### 5.5 循环依赖的边界条件

**Q: 哪些情况的循环依赖Spring无法解决？**

| 情况 | 能否解决 | 原因 |
|------|---------|------|
| 单例Bean的Setter注入循环 | ✅ 可以 | 三级缓存机制 |
| 单例Bean的构造器注入循环 | ❌ 不行 | 构造器调用时对象还未暴露到缓存 |
| prototype Bean的循环 | ❌ 不行 | 原型Bean不缓存 |
| @Async + 循环依赖 | ❌ 可能不行 | @Async代理时机不同 |

```java
// ❌ 构造器注入的循环依赖——Spring无法解决
@Service
public class A {
    private final B b;
    public A(B b) { this.b = b; } // 构造器注入
}

@Service
public class B {
    private final A a;
    public B(A a) { this.a = a; } // 构造器注入
}
// 报错：BeanCurrentlyInCreationException
```

**解决方案**：
```java
// 方案1：改用Setter/字段注入
// 方案2：使用@Lazy打破创建链
@Component
public class A {
    private final B b;
    public A(@Lazy B b) { this.b = b; } // @Lazy生成代理，打破循环
}
// 方案3：重构设计，消除循环依赖（最推荐）
```

---

## 六、面试高频真题

### Q1: Spring中Bean是线程安全的吗？

**答案**：**默认不是**。Spring不保证Bean的线程安全。

- **无状态Bean**（Service/Dao）：线程安全（没有可变状态）
- **有状态Bean**（如prototype的购物车）：需要注意线程安全

```java
@Service
public class UnsafeService {
    private int counter = 0;  // ⚠️ 共享可变状态！并发下不安全
    
    public int increment() {
        return ++counter; // 非原子操作
    }
}
```

### Q2: @Component和@Bean有什么区别？

| 对比 | @Component | @Bean |
|------|-----------|-------|
| 作用位置 | 类上 | 方法上（@Configuration类中） |
| 自动检测 | 组件扫描自动发现 | 方法显式声明 |
| 适用场景 | 自己写的类 | 第三方库类、需要自定义初始化的Bean |

```java
@Configuration
public class AppConfig {
    @Bean  // 将第三方类PooledDataSource注册为Bean
    public DataSource dataSource() {
        PooledDataSource ds = new PooledDataSource();
        ds.setMaxConnections(50);
        return ds;
    }
}
```

### Q3: Spring容器启动流程简述

```
1. 读取配置文件/注解 → BeanDefinition（Bean的元数据定义）
2. BeanFactoryPostProcessor处理（如PropertyPlaceholderConfigurer替换${}占位符）
3. 实例化BeanPostProcessor（注册Bean的后置处理器）
4. 按BeanDefinition依次创建Bean（走完整生命周期）
5. 发布ContextRefreshedEvent（容器启动完成事件）
```

---

## 七、下期预告

下一篇将深入 **Spring AOP** 的核心原理——JDK动态代理与CGLIB的区别、切点表达式的匹配规则、AOP的执行链（责任链模式）、Spring事务的传播行为与失效场景等，构建Spring AOP的完整知识体系。敬请期待！🦐

---

*本系列持续更新中，欢迎关注公众号获取最新文章。*
