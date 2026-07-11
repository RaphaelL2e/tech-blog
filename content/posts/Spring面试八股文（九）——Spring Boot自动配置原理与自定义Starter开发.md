---
title: "Spring面试八股文（九）——Spring Boot自动配置原理与自定义Starter开发"
date: 2026-07-11T10:00:00+08:00
draft: false
tags: ["Java", "Spring", "Spring Boot", "面试八股文"]
categories: ["Java"]
keywords: ["Spring Boot", "自动配置", "@EnableAutoConfiguration", "SpringFactoriesLoader", "AutoConfigurationImportSelector", "自定义Starter", "条件装配"]
description: "深入解析Spring Boot自动配置的核心原理：从@EnableAutoConfiguration到底层SpringFactoriesLoader、AutoConfigurationImportSelector的完整链路，以及如何开发企业级自定义Starter。结合高频面试题和源码剖析。"
---

# Spring面试八股文（九）——Spring Boot自动配置原理与自定义Starter开发

## 一、自动配置的核心意义

Spring Boot之所以能够"**零配置**"运行Web应用，核心就在于自动配置（Auto Configuration）机制。自动配置是Spring Boot的灵魂，它根据classpath中的依赖、配置文件中的声明和环境变量等信息，自动推断并注册用户可能需要的Bean，省去了大量繁琐的XML或Java Config代码。

理解自动配置原理，是区分"会用框架"和"理解框架"的分水岭，也是面试中考察Spring深度的不二法门。

## 二、自动配置完整链路：从启动到注册

### 2.1 入口：@SpringBootApplication

我们从主类的`@SpringBootApplication`注解说起：

```java
@SpringBootApplication
public class MyApplication {
    public static void main(String[] args) {
        SpringApplication.run(MyApplication.class, args);
    }
}
```

`@SpringBootApplication`是一个组合注解，其核心等价于三个注解：

| 组合注解 | 作用 |
|---------|------|
| `@Configuration` | 标记为配置类，由CGLIB生成代理 |
| `@EnableAutoConfiguration` | **启用自动配置（核心入口）** |
| `@ComponentScan` | 扫描`@Component`等组件，默认为启动类所在包 |

`@EnableAutoConfiguration`才是真正的自动配置开关，它的定义如下：

```java
@AutoConfigurationPackage
@Import(AutoConfigurationImportSelector.class)
public @interface EnableAutoConfiguration {
    @AliasFor(annotation = AutoConfigurationPackage.class)
    Class<?>[] basePackages() default {};
    String[] value() default {};
}
```

**关键点**：`@Import(AutoConfigurationImportSelector.class)`将`AutoConfigurationImportSelector`注入到Spring容器中，并触发了`Configuration`类的导入流程。

### 2.2 核心链路：AutoConfigurationImportSelector

`AutoConfigurationImportSelector`实现了`DeferredImportSelector`接口，在Spring容器刷新阶段会被调用。其核心方法`selectImports()`的完整流程如下：

```java
public class AutoConfigurationImportSelector
        implements DeferredImportSelector, BeanClassLoaderAware, ResourceLoaderAware {

    @Override
    public String[] selectImports(AnnotationMetadata annotationMetadata) {
        // ① 获取所有候选自动配置类
        List<String> configurations = getCandidateConfigurations(
            annotationMetadata, getAttributes()
        );
        // ② 去重
        configurations = removeDuplicates(configurations);
        // ③ 根据优先级排序
        configurations = sort(configurations);
        // ④ 根据exclude和excludeName排除
        Set<String> exclusions = getExclusions(annotationMetadata);
        configurations.removeAll(exclusions);
        // ⑤ 执行条件过滤（核心！）
        configurations = getConfigurationClassFilter().filter(configurations);
        return configurations.toArray(new String[0]);
    }
}
```

**五大步骤**：获取候选配置 → 去重 → 排序 → 排除 → 条件过滤。其中第⑤步的**条件过滤**是自动配置最精妙的地方。

### 2.3 获取候选配置：SpringFactoriesLoader

在第①步中，`getCandidateConfigurations()`方法调用`SpringFactoriesLoader.loadFactoryNames()`：

```java
private List<String> getCandidateConfigurations(
        AnnotationMetadata annotationMetadata,
        AttributeAttributes attributes) {
    List<String> configurations = SpringFactoriesLoader
        .loadFactoryNames(getConfigurationClassFilter(), classLoader);
    // 校验：确保至少有一个自动配置类被加载
    Assert.notEmpty(configurations, "No auto configuration classes ");
    return configurations;
}
```

`SpringFactoriesLoader`是Spring Framework 3.2引入的 SPI（Service Provider Interface）机制，用于从`META-INF/spring.factories`文件中读取配置。

**文件位置**：`spring-boot-autoconfigure-xxx.jar!/META-INF/spring.factories`

**文件格式**（YAML/Properties格式）：

```properties
# spring-boot-autoconfigure-xxx.jar!/META-INF/spring.factories
org.springframework.boot.autoconfigure.AutoConfiguration=\
org.springframework.boot.autoconfigure.aop.AopAutoConfiguration,\
org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,\
org.springframework.boot.autoconfigure.jdbc.JdbcTemplateAutoConfiguration,\
org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration,\
org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration,\
org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration,\
# ... 共计80+个自动配置类
```

Spring Boot 2.7+引入了`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`文件作为新的配置格式（推荐），同时`META-INF/spring.factories`仍然兼容，但Spring Boot 3.x以`imports`文件为主。

### 2.4 条件过滤：@Conditional注解体系

获取到80+个候选配置类后，需要根据当前环境逐一过滤，**只有满足全部条件的配置类才会被注册**。这个过滤机制由`@Conditional`注解族实现。

Spring Boot定义了丰富的条件注解：

| 条件注解 | 作用 |
|---------|------|
| `@ConditionalOnClass` | classpath中存在指定类时才注册 |
| `@ConditionalOnMissingClass` | classpath中不存在指定类时才注册 |
| `@ConditionalOnBean` | 容器中已存在指定Bean时才注册 |
| `@ConditionalOnMissingBean` | 容器中不存在指定Bean时才注册 |
| `@ConditionalOnProperty` | 配置属性满足条件时才注册 |
| `@ConditionalOnResource` | 存在指定资源文件时才注册 |
| `@ConditionalOnWebApplication` | 是Web应用时才注册 |
| `@ConditionalOnNotWebApplication` | 非Web应用时才注册 |

以`DataSourceAutoConfiguration`为例，展示条件注解的典型用法：

```java
@AutoConfiguration(before = DataSourceAutoConfiguration.class)
@ConditionalOnClass({ DataSource.class, EmbeddedDatabaseType.class })
@ConditionalOnMissingBean(type = "io.r2dbc.spi.ConnectionFactory")
@EnableConfigurationProperties(DataSourceProperties.class)
public class DataSourceAutoConfiguration {

    // 存在HikariCP依赖时注册HikariDataSource
    @ConditionalOnClass(HikariDataSource.class)
    @ConditionalOnProperty(name = "spring.datasource.hikari.enabled",
                           havingValue = "true",
                           matchIfMissing = true)
    static class HikaridbcConfiguration {
        @Bean
        @ConfigurationProperties(prefix = "spring.datasource.hikari")
        public DataSource dataSource() {
            return new HikariDataSource();
        }
    }
}
```

### 2.5 完整链路总结

```
@SpringBootApplication
    ↓
@EnableAutoConfiguration
    ↓ (@Import)
AutoConfigurationImportSelector.selectImports()
    ↓
SpringFactoriesLoader.loadFactoryNames()
    ↓ 读取 META-INF/spring.factories 或 AutoConfiguration.imports
获取80+个候选配置类
    ↓
去重 → 排序 → 排除指定类
    ↓
@Conditional条件过滤
    ↓
满足条件的配置类被@Configuration解析
    ↓
@Bean方法执行，Bean注册到容器
```

## 三、源码级解析：自动配置究竟做了什么

### 3.1 AutoConfigurationImportSelector的执行时机

`AutoConfigurationImportSelector`实现的是`DeferredImportSelector`接口，这意味着它的执行时机**晚于普通`@Configuration`类**，这样设计有两个原因：

1. **确保所有Bean都已注册**：此时可以准确判断容器中是否已有某个Bean，从而决定是否需要自动配置
2. **确保classpath已知**：classpath扫描完成后才能判断`@ConditionalOnClass`条件

执行顺序如下：

```
BeanDefinitionRegistryPostProcessor（处理@Configuration）
    ↓
DeferredImportSelector处理阶段 ← AutoConfigurationImportSelector在此执行
    ↓
普通@Bean注册
```

### 3.2 自动配置类的加载顺序

自动配置类通过`@AutoConfiguration`注解的`before`/`after`属性控制加载顺序：

```java
@AutoConfiguration(before = DataSourceAutoConfiguration.class)  // 排在DataSource之前
@AutoConfiguration(after = JdbcTemplateAutoConfiguration.class)   // 排在JdbcTemplate之后
public class MyCustomAutoConfiguration {
    // ...
}
```

Spring Boot还定义了`AutoConfigureOrder`注解用于更细粒度的顺序控制：

```java
@AutoConfigureOrder(Ordered.HIGHEST_PRECEDENCE + 10)
public class MyAutoConfiguration {
    // 最高优先级 + 10
}
```

### 3.3 用户配置优先原则

**自动配置永远不能覆盖用户手写的配置**。Spring Boot通过以下机制保证：

- `@ConditionalOnMissingBean`：只有当容器中没有用户注册的同名Bean时才注册自动配置的Bean
- `@ConditionalOnMissingClass`：只有当classpath没有用户引入的某个依赖时才注册
- 加载顺序：用户`@Configuration`优先于自动配置类加载

例如，`WebMvcAutoConfiguration`中的`ViewResolver`配置：

```java
@Configuration(proxyBeanMethods = false)
@ConditionalOnMissingBean(ViewResolver.class)
public class WebMvcAutoConfiguration {
    @Bean
    public InternalResourceViewResolver defaultViewResolver() {
        return new InternalResourceViewResolver();
    }
}
```

只要用户在任何一个`@Configuration`类中手动注册了`ViewResolver`，自动配置的ViewResolver就不会被注册。

## 四、自定义Starter开发实战

### 4.1 Starter的设计理念

Spring Boot Starter遵循"**一个starter负责一个功能域**"的原则，包含两个模块：

| 模块 | 命名规范 | 职责 |
|-----|---------|------|
| autoconfigure模块 | `xxx-spring-boot-autoconfigure` | 自动配置类、条件逻辑 |
| starter模块 | `xxx-spring-boot-starter` | 仅声明依赖，无代码 |

### 4.2 完整开发步骤

**Step 1: 创建autoconfigure模块**

```
greeting-spring-boot-autoconfigure/
├── src/main/java/com/example/greeting/
│   ├── GreetingAutoConfiguration.java
│   ├── GreetingProperties.java
│   └── GreetingService.java
├── src/main/resources/META-INF/
│   └── spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
└── pom.xml
```

**Step 2: 定义配置属性类（使用@ConfigurationProperties）**

```java
// GreetingProperties.java
@ConfigurationProperties(prefix = "app.greeting")
public class GreetingProperties {
    private String template = "Hello, %s!";
    private String defaultName = "World";
    private boolean enabled = true;
    // getter/setter省略
}
```

**Step 3: 编写自动配置类**

```java
// GreetingAutoConfiguration.java
@AutoConfiguration
@EnableConfigurationProperties(GreetingProperties.class)
@ConditionalOnClass(GreetingService.class)
@ConditionalOnProperty(prefix = "app.greeting", name = "enabled",
                        havingValue = "true", matchIfMissing = true)
public class GreetingAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean(GreetingService.class)
    public GreetingService greetingService(GreetingProperties properties) {
        return new GreetingService(properties.getTemplate(),
                                     properties.getDefaultName());
    }
}
```

**Step 4: 注册自动配置（Spring Boot 2.7+推荐方式）**

```
# src/main/resources/META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
com.example.greeting.GreetingAutoConfiguration
```

（**注意**：Spring Boot 3.x中必须使用`imports`文件格式，不再支持`spring.factories`格式。）

**Step 5: 创建starter模块的pom.xml**

```xml
<!-- greeting-spring-boot-starter/pom.xml -->
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter</artifactId>
</dependency>
```

用户只需引入starter依赖，无需任何额外配置即可使用：

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>greeting-spring-boot-starter</artifactId>
    <version>1.0.0</version>
</dependency>
```

```yaml
# application.yml
app:
  greeting:
    enabled: true
    template: "欢迎光临, %s!"
    default-name: "尊贵用户"
```

## 五、自动配置高级技巧

### 5.1 排除特定自动配置

有多种方式可以排除不需要的自动配置：

```yaml
# 方式1：application.yml排除
spring:
  autoconfigure:
    exclude:
      - org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration
      - org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration
```

```java
// 方式2：@SpringBootApplication注解中排除
@SpringBootApplication(exclude = {
    RedisAutoConfiguration.class,
    DataSourceAutoConfiguration.class
})
```

```java
// 方式3：@EnableAutoConfiguration属性排除
@EnableAutoConfiguration(exclude = { RedisAutoConfiguration.class })
```

### 5.2 自定义自动配置的条件优先级

默认情况下，自动配置以`Ordered.LOWEST_PRECEDENCE - 1`优先级加载。如果希望用户的`@Configuration`始终优先，可以设置：

```java
@AutoConfiguration
@AutoConfigureBefore(UserConfiguration.class)  // 在UserConfiguration之前
@AutoConfigureAfter(WebMvcAutoConfiguration.class)
public class MyAutoConfiguration {
    // ...
}
```

### 5.3 调试自动配置

启用自动配置报告可以查看详细的生效情况：

```properties
# application.properties
debug=true
# 或命令行
java -jar app.jar --debug
```

会在`META-INF/spring-boot-actuate-info/autoConfigurationInfo.txt`中输出详细的生效配置列表，包含每个配置类的条件评估结果。

## 六、高频面试题

### 面试题1：Spring Boot自动配置的原理是什么？

**参考答案**：
Spring Boot自动配置的核心是`@EnableAutoConfiguration`注解，它通过`@Import(AutoConfigurationImportSelector.class)`将所有`META-INF/spring.factories`（或`AutoConfiguration.imports`）中声明的自动配置类注册为Spring Bean。`AutoConfigurationImportSelector`会加载约80+个候选配置类，通过`@Conditional`条件注解体系，根据当前classpath依赖、容器中已有的Bean以及配置文件属性，逐一生效条件过滤，最终只有满足全部条件的配置类才会被解析和注册。这个机制保证了"约定由于配置"的开箱即用特性，同时允许用户通过排除、覆盖等方式自定义行为。

### 面试题2：@ConditionalOnBean和@ConditionalOnMissingBean的区别是什么？

**参考答案**：
`@ConditionalOnBean`要求容器中**已存在**指定类型的Bean时才注册当前Bean；`@ConditionalOnMissingBean`则相反，要求容器中**不存在**指定类型的Bean时才注册。这两个注解是Spring Boot实现"**用户配置优先**"机制的核心手段。例如`WebMvcAutoConfiguration`中的所有`@Bean`方法都标注了`@ConditionalOnMissingBean`，确保用户自行定义的`ViewResolver`、`WebMvcConfigurer`等会覆盖自动配置的默认实现。

### 面试题3：自定义Starter的开发流程是什么？

**参考答案**：
需要两个模块：autoconfigure模块负责自动配置逻辑，starter模块仅声明依赖。首先在autoconfigure模块中定义`@ConfigurationProperties`属性类封装配置属性，然后编写自动配置类，使用`@ConditionalOnClass`、`@ConditionalOnProperty`等注解定义生效条件，最后在`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`文件中注册。用户只需引入starter依赖，配置对应的属性前缀即可使用。设计原则是starter模块零代码，仅传递依赖；autoconfigure模块包含所有配置逻辑。

### 面试题4：Spring Boot 2.7之后自动配置有什么变化？

**参考答案**：
Spring Boot 2.7废弃了`META-INF/spring.factories`中的`EnableAutoConfiguration`配置，推荐使用`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`文件替代。两者的格式不同：旧格式使用Properties/键值对格式，新格式使用每行一个全类名的纯文本格式。Spring Boot 3.x（基于Spring Framework 6）则**完全移除**了对`spring.factories`的支持，必须使用`imports`文件格式。这一变化使自动配置的声明更加简洁，也更易于维护和IDE支持。

### 面试题5：自动配置和手动配置哪个优先级更高？

**参考答案**：
**用户手动配置优先级更高**。Spring Boot自动配置的设计哲学就是"**约定优于配置，可覆盖不可盲从**"。自动配置类中使用`@ConditionalOnMissingBean`、`@ConditionalOnMissingClass`等注解确保：如果用户已经通过`@Bean`、`@Component`等方式手动注册了某个Bean，自动配置就不会注册同名Bean。从加载顺序看，用户`@Configuration`类的加载优先级也高于自动配置类。需要精确控制时，可以通过`@AutoConfigureBefore`/`@AutoConfigureAfter`调整自动配置类之间的相对顺序。

## 七、总结与下期预告

本文系统剖析了Spring Boot自动配置的完整链路：从`@SpringBootApplication`的组合注解结构，到`AutoConfigurationImportSelector`的五大处理步骤，再到`SpringFactoriesLoader`的SPI加载机制和`@Conditional`条件过滤体系，最后通过企业级自定义Starter的开发实践将理论与代码结合。

**下期预告**：下一篇文章《Spring面试八股文（十）——Spring Boot条件装配深度解析与@ConfigurationProperties最佳实践》将深入讲解`@Conditional`注解族的12种变体及使用场景、`@Profile`多环境隔离的底层原理、`@ConfigurationProperties`的松散绑定与元数据生成，以及如何在生产环境中设计一套规范的条件配置体系。敬请期待！
