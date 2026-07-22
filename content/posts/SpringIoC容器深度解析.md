---
title: Spring IoC 容器深度解析
date: 2026-05-11 16:00:00+08:00
updated: '2026-05-11T16:00:00+08:00'
description: 面试高频问题：什么是 IoC？Bean 的生命周期？@Autowired 如何工作？ Spring 框架的核心是 IoC（Inversion of Control，控制反转） 容器。理解 IoC 容器的工作原理，是掌握
  Spring 框架的关键。本文将从 IoC 概念到源码实现，全面解析 Sprin。
topic: java-spring
level: intermediate
status: maintained
tags:
- Spring
- ioc
- di
- bean
- autowired
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：什么是 IoC？Bean 的生命周期？@Autowired 如何工作？

## 引言

Spring 框架的核心是 **IoC（Inversion of Control，控制反转）** 容器。理解 IoC 容器的工作原理，是掌握 Spring 框架的关键。本文将从 IoC 概念到源码实现，全面解析 Spring IoC 容器。

## 一、IoC 与 DI

### 1.1 什么是 IoC？

**IoC（控制反转）**：将对象的创建、依赖管理交给容器，而不是在代码中硬编码。

```
传统方式（正转）：
┌─────────────────────────────┐
│ 程序员                                  │
│   │                                │
│   ├─ new Object()                  │
│   ├─ 管理依赖关系                   │
│   └─ 处理生命周期                   │
└─────────────────────────────┘

IoC 方式（反转）：
┌─────────────────────────────┐
│ IoC 容器                                 │
│   │                                │
│   ├─ 创建对象                      │
│   ├─ 注入依赖                      │
│   └─ 管理生命周期                   │
│                              │
│ 程序员：只声明依赖                   │
└─────────────────────────────┘
```

### 1.2 什么是 DI？

**DI（Dependency Injection，依赖注入）**：IoC 的一种实现方式，通过构造函数、setter 方法或字段注入依赖。

```java
// 传统方式：自己创建依赖
public class OrderService {
    private OrderDao orderDao = new OrderDaoImpl();  // 硬编码
}

// IoC 方式：容器注入依赖
public class OrderService {
    @Autowired
    private OrderDao orderDao;  // 由容器注入
}
```

### 1.3 IoC 的好处

| 好处 | 说明 |
|------|------|
| **解耦** | 对象之间不直接依赖，通过接口交互 |
| **可测试** | 可以轻松 mock 依赖 |
| **可维护** | 修改实现类不影响调用者 |
| **AOP 支持** | 容器可以创建代理对象 |

## 二、Spring IoC 容器架构

### 2.1 核心接口

```
┌────────────────────────────────────────────────────────┐
│                   BeanFactory                          │
│              （基础容器接口）                            │
│  ├─ getBean()                                        │
│  ├─ containsBean()                                   │
│  └─ isSingleton()                                    │
└────────────────────────────┬─────────────────────────┘
                             │ 继承
┌────────────────────────────▼─────────────────────────┐
│                   ApplicationContext                    │
│            （高级容器，推荐使用）                        │
│  ├─ 国际化（MessageSource）                          │
│  ├─ 事件发布（ApplicationEvent）                      │
│  ├─ 资源加载（ResourceLoader）                        │
│  └─ 环境配置（Environment）                           │
└─────────────────────────────────────────────────────┘
```

**常用实现类**：

| 实现类 | 适用场景 |
|--------|---------|
| `ClassPathXmlApplicationContext` | XML 配置，从 classpath 加载 |
| `FileSystemXmlApplicationContext` | XML 配置，从文件系统加载 |
| `AnnotationConfigApplicationContext` | 注解配置（推荐） |
| `WebApplicationContext` | Web 应用 |

### 2.2 容器启动流程

```java
// 注解方式启动
ApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);

// 源码流程（简化）
AnnotationConfigApplicationContext context = new AnnotationConfigApplicationContext();
    │
    ├─ 1. 注册配置类
    │   └─ register(AppConfig.class)
    │
    ├─ 2. 刷新容器（核心）
    │   └─ refresh()
    │       │
    │       ├─ 2.1 准备刷新
    │       │   └─ initPropertySources()
    │       │
    │       ├─ 2.2 获取 BeanFactory
    │       │   └─ obtainFreshBeanFactory()
    │       │
    │       ├─ 2.3 准备 BeanFactory
    │       │   └─ prepareBeanFactory()
    │       │
    │       ├─ 2.4 BeanFactory 后置处理
    │       │   └─ postProcessBeanFactory()
    │       │
    │       ├─ 2.5 执行 BeanFactoryPostProcessor
    │       │   └─ invokeBeanFactoryPostProcessors()
    │       │
    │       ├─ 2.6 注册 BeanPostProcessor
    │       │   └─ registerBeanPostProcessors()
    │       │
    │       ├─ 2.7 初始化消息源
    │       │   └─ initMessageSource()
    │       │
    │       ├─ 2.8 初始化事件广播器
    │       │   └─ initApplicationEventMulticaster()
    │       │
    │       ├─ 2.9 初始化其他特殊 Bean
    │       │   └─ onRefresh()
    │       │
    │       ├─ 2.10 注册监听器
    │       │   └─ registerListeners()
    │       │
    │       ├─ 2.11 实例化所有非懒加载单例
    │       │   └─ finishBeanFactoryInitialization()
    │       │
    │       └─ 2.12 完成刷新
    │           └─ finishRefresh()
    │
    └─ 3. 返回容器
        └─ return context
```

## 三、Bean 的生命周期

### 3.1 生命周期概述

```
Bean 生命周期（简化版）：
┌───────────────────────────────────────────────────────┐
│ 1. 实例化（调用构造函数）                                │
│ 2. 填充属性（依赖注入）                                 │
│ 3. 调用 Aware 接口方法                                 │
│ 4. BeanPostProcessor 前置处理                          │
│ 5. 调用初始化方法                                      │
│ 6. BeanPostProcessor 后置处理                          │
│ 7. Bean 准备就绪                                      │
│ 8. 容器关闭时调用销毁方法                               │
└───────────────────────────────────────────────────────┘
```

### 3.2 详细生命周期

```java
// 1. 实例化
OrderService orderService = new OrderService();

// 2. 依赖注入
orderService.setOrderDao(orderDao);

// 3. Aware 接口回调
if (orderService instanceof BeanNameAware) {
    ((BeanNameAware) orderService).setBeanName("orderService");
}
if (orderService instanceof ApplicationContextAware) {
    ((ApplicationContextAware) orderService).setApplicationContext(context);
}

// 4. BeanPostProcessor 前置处理
for (BeanPostProcessor bpp : beanPostProcessors) {
    orderService = bpp.postProcessBeforeInitialization(orderService, "orderService");
}

// 5. 初始化方法
if (orderService instanceof InitializingBean) {
    ((InitializingBean) orderService).afterPropertiesSet();
}
invokeCustomInitMethod();  // @PostConstruct 或 init-method

// 6. BeanPostProcessor 后置处理（AOP 在此处创建代理）
for (BeanPostProcessor bpp : beanPostProcessors) {
    orderService = bpp.postProcessAfterInitialization(orderService, "orderService");
}

// 7. Bean 就绪，可以被使用
return orderService;

// 8. 容器关闭时
if (orderService instanceof DisposableBean) {
    ((DisposableBean) orderService).destroy();
}
invokeCustomDestroyMethod();  // @PreDestroy 或 destroy-method
```

### 3.3 生命周期接口

| 接口 | 方法 | 调用时机 |
|------|------|---------|
| `BeanNameAware` | `setBeanName()` | Bean 名称注入 |
| `BeanFactoryAware` | `setBeanFactory()` | BeanFactory 注入 |
| `ApplicationContextAware` | `setApplicationContext()` | ApplicationContext 注入 |
| `InitializingBean` | `afterPropertiesSet()` | 初始化方法 |
| `DisposableBean` | `destroy()` | 销毁方法 |

**示例**：
```java
@Component
public class MyBean implements BeanNameAware, InitializingBean, DisposableBean {
    
    @Override
    public void setBeanName(String name) {
        System.out.println("1. BeanNameAware: " + name);
    }
    
    @PostConstruct
    public void init() {
        System.out.println("2. @PostConstruct");
    }
    
    @Override
    public void afterPropertiesSet() {
        System.out.println("3. InitializingBean.afterPropertiesSet()");
    }
    
    @PreDestroy
    public void destroy() {
        System.out.println("4. @PreDestroy");
    }
    
    @Override
    public void destroy() {
        System.out.println("5. DisposableBean.destroy()");
    }
}
```

### 3.4 @PostConstruct 和 @PreDestroy

```java
@Component
public class OrderService {
    
    @PostConstruct
    public void init() {
        // 初始化资源
        System.out.println("Bean 初始化");
    }
    
    @PreDestroy
    public void cleanup() {
        // 清理资源
        System.out.println("Bean 销毁");
    }
}
```

**执行顺序**：
```
构造器 → @PostConstruct → InitializingBean.afterPropertiesSet() → init-method

@PreDestroy → DisposableBean.destroy() → destroy-method
```

## 四、依赖注入（DI）

### 4.1 注入方式

**方式 1：构造函数注入（推荐）**

```java
@Service
public class OrderService {
    private final OrderDao orderDao;
    
    // 推荐：构造函数注入（不可变、强制依赖）
    public OrderService(OrderDao orderDao) {
        this.orderDao = orderDao;
    }
}
```

**方式 2：Setter 注入**

```java
@Service
public class OrderService {
    private OrderDao orderDao;
    
    // 可选依赖
    @Autowired(required = false)
    public void setOrderDao(OrderDao orderDao) {
        this.orderDao = orderDao;
    }
}
```

**方式 3：字段注入（不推荐）**

```java
@Service
public class OrderService {
    @Autowired
    private OrderDao orderDao;  // 不推荐：无法 mock、不可变
}
```

### 4.2 @Autowired 原理

**@Autowired 注入流程**：

```
1. 解析 @Autowired 注解
   └─ AutowiredAnnotationBeanPostProcessor

2. 查找匹配的 Bean
   └─ 按类型（byType）查找
   └─ 如果有多个，按名称（byName）过滤

3. 注入依赖
   └─ 反射注入（字段或方法）
```

**源码解析（简化）**：
```java
// AutowiredAnnotationBeanPostProcessor.postProcessProperties()
public PropertyValues postProcessProperties(Object bean, String beanName) {
    // 1. 查找 @Autowired 注解的字段和方法
    InjectionMetadata metadata = findAutowiringMetadata(beanName, bean.getClass());
    
    // 2. 注入
    metadata.inject(bean, beanName, null);
    
    return null;
}

// 注入具体实现
private class AutowiredFieldElement extends InjectionMetadata.InjectedElement {
    protected void inject(Object bean, String beanName, PropertyValues pvs) {
        Field field = (Field) this.member;
        
        // 1. 解析依赖
        Object value = resolveFieldValue(field, bean, beanName);
        
        // 2. 反射设置字段
        ReflectionUtils.makeAccessible(field);
        field.set(bean, value);
    }
}
```

### 4.3 @Qualifier 指定 Bean

```java
// 问题：多个同类型 Bean
@Repository
public class OrderDaoImpl1 implements OrderDao {}

@Repository
public class OrderDaoImpl2 implements OrderDao {}

// 解决：使用 @Qualifier
@Service
public class OrderService {
    @Autowired
    @Qualifier("orderDaoImpl1")  // 指定 Bean 名称
    private OrderDao orderDao;
}
```

### 4.4 @Primary 优先注入

```java
@Repository
@Primary  // 优先注入此 Bean
public class OrderDaoImpl1 implements OrderDao {}

@Repository
public class OrderDaoImpl2 implements OrderDao {}

@Service
public class OrderService {
    @Autowired
    private OrderDao orderDao;  // 注入 OrderDaoImpl1（@Primary）
}
```

### 4.5 可选依赖

```java
@Service
public class OrderService {
    @Autowired(required = false)  // 可选依赖：没有也不报错
    private OrderDao orderDao;
}
```

## 五、Bean 的作用域

### 5.1 六种作用域

| 作用域 | 说明 | 适用场景 |
|--------|------|---------|
| `singleton` | 单例（默认） | 无状态 Bean |
| `prototype` | 每次新实例 | 有状态 Bean |
| `request` | 每次 HTTP 请求 | Web 应用 |
| `session` | 每个 Session | 用户会话 |
| `application` | 每个 ServletContext | 全局数据 |
| `websocket` | 每个 WebSocket | WebSocket 会话 |

### 5.2 singleton 和 prototype 对比

```java
// singleton（默认）：容器启动时创建，整个容器共享
@Component
@Scope("singleton")  // 可省略
public class OrderService {
    // 容器中只有一个实例
}

// prototype：每次获取都创建新实例
@Component
@Scope("prototype")
public class OrderService {
    // 每次 getBean() 都创建新对象
}
```

**示例**：
```java
ApplicationContext context = new AnnotationConfigApplicationContext(AppConfig.class);

OrderService s1 = context.getBean(OrderService.class);
OrderService s2 = context.getBean(OrderService.class);

System.out.println(s1 == s2);  
// singleton: true（同一个对象）
// prototype: false（不同对象）
```

### 5.3 Web 作用域

```java
@Controller
public class OrderController {
    @Autowired
    private Cart cart;  // 需要正确配置作用域
}

// 错误：singleton Bean 依赖 prototype Bean
// 解决：使用代理
@Scope(value = "session", proxyMode = ScopedProxyMode.TARGET_CLASS)
public class Cart {
    // ...
}
```

## 六、Bean 的懒加载

### 6.1 @Lazy 注解

```java
// 默认：容器启动时创建（eager initialization）
@Component
public class OrderService {
    public OrderService() {
        System.out.println("OrderService 创建了");
    }
}

// 懒加载：第一次使用时才创建
@Component
@Lazy
public class OrderService {
    public OrderService() {
        System.out.println("OrderService 创建了（懒加载）");
    }
}
```

### 6.2 配置类级别的懒加载

```java
@Configuration
@Lazy  // 所有 @Bean 都懒加载
public class AppConfig {
    
    @Bean
    public OrderService orderService() {
        return new OrderService();
    }
}
```

## 七、条件化配置（@Conditional）

### 7.1 @Conditional 注解

```java
// 根据条件决定是否创建 Bean
@Configuration
public class AppConfig {
    
    @Bean
    @Conditional(OnProductionCondition.class)
    public DataSource productionDataSource() {
        return new HikariDataSource();
    }
    
    @Bean
    @Conditional(OnTestCondition.class)
    public DataSource testDataSource() {
        return new EmbeddedDatabaseBuilder().build();
    }
}

// 条件类
public class OnProductionCondition implements Condition {
    @Override
    public boolean matches(ConditionContext context, AnnotatedTypeMetadata metadata) {
        return "production".equals(context.getEnvironment().getProperty("env"));
    }
}
```

### 7.2 Spring Boot 的 @ConditionalOnXXX

| 注解 | 说明 |
|------|------|
| `@ConditionalOnClass` | 类路径存在指定类 |
| `@ConditionalOnMissingClass` | 类路径不存在指定类 |
| `@ConditionalOnBean` | 容器存在指定 Bean |
| `@ConditionalOnMissingBean` | 容器不存在指定 Bean |
| `@ConditionalOnProperty` | 配置属性满足条件 |
| `@ConditionalOnWebApplication` | Web 应用 |

```java
@Configuration
public class MyAutoConfiguration {
    
    @Bean
    @ConditionalOnClass(name = "com.mysql.cj.jdbc.Driver")
    public DataSource mysqlDataSource() {
        return new HikariDataSource();
    }
    
    @Bean
    @ConditionalOnProperty(name = "app.feature.enabled", havingValue = "true")
    public FeatureService featureService() {
        return new FeatureService();
    }
}
```

## 八、BeanFactoryPostProcessor 和 BeanPostProcessor

### 8.1 BeanFactoryPostProcessor

**作用**：在 Bean 定义加载后、实例化前，修改 Bean 定义。

```java
@Component
public class MyBeanFactoryPostProcessor implements BeanFactoryPostProcessor {
    @Override
    public void postProcessBeanFactory(ConfigurableListableBeanFactory beanFactory) {
        // 修改 Bean 定义
        BeanDefinition bd = beanFactory.getBeanDefinition("orderService");
        bd.setPropertyValues(new MutablePropertyValues());
    }
}
```

**常见应用**：
- `PropertySourcesPlaceholderConfigurer`：解析 `${...}` 占位符
- `ConfigurationClassPostProcessor`：处理 `@Configuration` 类

### 8.2 BeanPostProcessor

**作用**：在 Bean 初始化前后，对 Bean 进行增强（AOP 就靠这个）。

```java
@Component
public class MyBeanPostProcessor implements BeanPostProcessor {
    
    // 初始化前
    @Override
    public Object postProcessBeforeInitialization(Object bean, String beanName) {
        System.out.println("Before init: " + beanName);
        return bean;  // 可以返回原始 Bean 或包装后的 Bean
    }
    
    // 初始化后（AOP 在此处创建代理）
    @Override
    public Object postProcessAfterInitialization(Object bean, String beanName) {
        System.out.println("After init: " + beanName);
        
        // 创建代理（AOP）
        if (bean instanceof OrderService) {
            return Proxy.newProxyInstance(...);
        }
        
        return bean;
    }
}
```

**常见应用**：
- `AutowiredAnnotationBeanPostProcessor`：处理 `@Autowired`
- `CommonAnnotationBeanPostProcessor`：处理 `@PostConstruct`、`@PreDestroy`
- `AnnotationAwareAspectJAutoProxyCreator`：创建 AOP 代理

## 九、面试高频问题

### Q1：@Autowired 和 @Resource 的区别？

**答**：
| 特性 | @Autowired | @Resource |
|------|------------|----------|
| 来源 | Spring | JSR-250（Java 标准） |
| 默认按 | 类型（byType） | 名称（byName） |
| required | 支持 | 不支持 |
| 指定名称 | @Qualifier | name 属性 |

```java
// @Autowired：按类型注入
@Autowired
private OrderDao orderDao;

// @Resource：按名称注入
@Resource(name = "orderDaoImpl1")
private OrderDao orderDao;
```

### Q2：Bean 的生命周期？

**答**：
1. 实例化
2. 依赖注入
3. Aware 接口回调
4. BeanPostProcessor 前置处理
5. 初始化方法（`@PostConstruct`、`afterPropertiesSet()`）
6. BeanPostProcessor 后置处理（AOP 代理）
7. Bean 就绪
8. 容器关闭时调用销毁方法

### Q3：singleton 和 prototype 的区别？

**答**：
- **singleton**：容器只有一个实例，容器启动时创建（默认）
- **prototype**：每次 `getBean()` 都创建新实例

### Q4：@Component 和 @Bean 的区别？

**答**：
| 特性 | @Component | @Bean |
|------|------------|-------|
| 作用 | 类级别 | 方法级别 |
| 适用 | 自定义类 | 第三方类 |
| 方式 | 类扫描 | 方法返回对象 |

```java
// @Component：注解在类上
@Component
public class OrderService {}

// @Bean：注解在方法上，方法返回对象
@Configuration
public class AppConfig {
    @Bean
    public DataSource dataSource() {
        return new HikariDataSource();  // 第三方类
    }
}
```

### Q5：什么是循环依赖？Spring 如何解决？

**答**：
- **循环依赖**：A 依赖 B，B 依赖 A
- **Spring 解决方式**：三级缓存
  - 一级缓存：`singletonObjects`（成品 Bean）
  - 二级缓存：`earlySingletonObjects`（半成品 Bean）
  - 三级缓存：`singletonFactories`（ObjectFactory）

**限制**：
- 构造器循环依赖无法解决（抛 `BeanCurrentlyInCreationException`）
- 字段注入、setter 注入可以解决

## 十、总结

**IoC 核心要点**：
- **IoC**：控制反转，将对象创建交给容器
- **DI**：依赖注入，IoC 的实现方式
- **Bean 生命周期**：实例化 → 依赖注入 → 初始化 → 销毁
- **作用域**：singleton（默认）、prototype、request、session

**依赖注入方式**：
1. 构造函数注入（推荐）
2. Setter 注入（可选依赖）
3. 字段注入（不推荐）

**Best Practices**：
1. 使用构造函数注入（不可变、强制依赖）
2. 优先使用 `@Component` 扫描
3. 合理使用 `@Lazy` 提升启动速度
4. 避免在 singleton Bean 中依赖 prototype Bean

---

**下一篇预告**：Spring AOP 深度解析 —— 代理机制、切面编程、事务管理

**参考资料**：
- 《Spring 实战》- Craig Walls
- Spring 官方文档：https://docs.spring.io/spring-framework/docs/current/reference/html/core.html
- 《Spring 源码深度解析》- 郝佳
