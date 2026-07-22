---
title: Spring Boot 自动配置原理深度解析
date: 2026-05-12 10:30:00+08:00
updated: '2026-05-12T10:30:00+08:00'
description: 面试高频问题：Spring Boot 自动配置的原理？@Conditional 注解如何工作？如何自定义 Starter？ Spring Boot 的核心特性就是"约定优于配置"，通过自动配置大幅减少了样板代码和配置。理解自动配置的原理，是掌握
  Spring Boot 的关键。 Spring Boo。
topic: java-spring
level: intermediate
status: maintained
tags:
- Spring
- springboot
- autoconfiguration
- starter
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：Spring Boot 自动配置的原理？@Conditional 注解如何工作？如何自定义 Starter？

## 引言

Spring Boot 的核心特性就是"约定优于配置"，通过自动配置大幅减少了样板代码和配置。理解自动配置的原理，是掌握 Spring Boot 的关键。

## 一、@SpringBootApplication 注解

### 1.1 注解拆解

```java
@SpringBootApplication
// 等价于：
@SpringBootConfiguration      // 配置类
@EnableAutoConfiguration      // 自动配置（核心）
@ComponentScan                 // 组件扫描
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

### 1.2 @EnableAutoConfiguration

```java
@AutoConfigurationPackage      // 自动配置包
@Import(AutoConfigurationImportSelector.class)  // 导入自动配置类
public @interface EnableAutoConfiguration {
    String ENABLED_OVERRIDE_PROPERTY = "spring.boot.enableautoconfiguration";
    
    Class<?>[] exclude() default {};       // 排除特定配置类
    String[] excludeName() default {};     // 按类名排除
}
```

## 二、自动配置流程

### 2.1 完整流程

```
SpringApplication.run()
    │
    ├─ 1. 创建 SpringApplication
    │   └─ 推断应用类型（Servlet/Reactive/None）
    │   └─ 加载 ApplicationContextInitializer
    │   └─ 加载 ApplicationListener
    │
    ├─ 2. 运行 SpringApplication
    │   ├─ 创建 ApplicationContext
    │   ├─ 准备环境
    │   ├─ 刷新上下文
    │   │   │
    │   │   ├─ @ComponentScan 扫描组件
    │   │   │
    │   │   ├─ AutoConfigurationImportSelector
    │   │   │   ├─ SpringFactoriesLoader.loadFactoryNames()
    │   │   │   │   └─ 读取 META-INF/spring.factories
    │   │   │   │       └─ 获取所有 AutoConfiguration 类
    │   │   │   │
    │   │   │   ├─ 过滤（@ConditionalOnClass 等）
    │   │   │   │   └─ 排除 exclude 列表
    │   │   │   │   └─ 去重
    │   │   │   │   └─ @Conditional 过滤
    │   │   │   │
    │   │   │   └─ 返回有效的自动配置类
    │   │   │
    │   │   └─ 注册 Bean 定义
    │   │
    │   └─ 完成刷新
    │
    └─ 3. 返回 ApplicationContext
```

### 2.2 spring.factories 机制

```properties
# META-INF/spring.factories
org.springframework.boot.autoconfigure.EnableAutoConfiguration=\
  org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration,\
  org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration,\
  org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration,\
  ...
```

**Spring Boot 2.7+ 新增**：`META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`

```
# 每行一个自动配置类
org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration
org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration
```

### 2.3 源码追踪

```java
// AutoConfigurationImportSelector.selectImports()
public String[] selectImports(AnnotationMetadata annotationMetadata) {
    if (!isEnabled(annotationMetadata)) {
        return NO_IMPORTS;
    }
    
    // 1. 获取自动配置条目
    AutoConfigurationEntry autoConfigurationEntry = 
        getAutoConfigurationEntry(annotationMetadata);
    
    return StringUtils.toStringArray(autoConfigurationEntry.getConfigurations());
}

// 获取自动配置条目
protected AutoConfigurationEntry getAutoConfigurationEntry(AnnotationMetadata metadata) {
    // 1. 获取候选配置类
    List<String> configurations = getCandidateConfigurations(metadata, attributes);
    
    // 2. 去重
    configurations = removeDuplicates(configurations);
    
    // 3. 排除
    Set<String> exclusions = getExclusions(annotationMetadata, attributes);
    checkExcludedClasses(configurations, exclusions);
    configurations.removeAll(exclusions);
    
    // 4. 过滤（@Conditional）
    configurations = getConfigurationClassFilter().filter(configurations);
    
    // 5. 触发事件
    fireAutoConfigurationImportEvents(configurations, exclusions);
    
    return new AutoConfigurationEntry(configurations, exclusions);
}

// 获取候选配置类
protected List<String> getCandidateConfigurations(AnnotationMetadata metadata, 
                                                   AnnotationAttributes attributes) {
    // 从 spring.factories 加载
    List<String> configurations = SpringFactoriesLoader.loadFactoryNames(
        getSpringFactoriesLoaderFactoryClass(), getBeanClassLoader());
    
    // 从 AutoConfiguration.imports 加载（2.7+）
    ImportCandidates.load(AutoConfiguration.class, getBeanClassLoader())
        .forEach(configurations::add);
    
    return configurations;
}
```

## 三、条件注解

### 3.1 @ConditionalOnClass

```java
// 只有类路径存在 HikariDataSource 时才配置
@AutoConfiguration
@ConditionalOnClass(HikariDataSource.class)
public class DataSourceAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean(DataSource.class)  // 容器中没有 DataSource 才创建
    public DataSource dataSource(DataSourceProperties properties) {
        return DataSourceBuilder.create().build();
    }
}
```

### 3.2 常用条件注解

| 注解 | 说明 |
|------|------|
| `@ConditionalOnClass` | 类路径存在指定类 |
| `@ConditionalOnMissingClass` | 类路径不存在指定类 |
| `@ConditionalOnBean` | 容器中存在指定 Bean |
| `@ConditionalOnMissingBean` | 容器中不存在指定 Bean |
| `@ConditionalOnProperty` | 配置属性满足条件 |
| `@ConditionalOnWebApplication` | Web 应用 |
| `@ConditionalOnNotWebApplication` | 非 Web 应用 |
| `@ConditionalOnExpression` | SpEL 表达式为 true |

### 3.3 @ConditionalOnProperty 详解

```java
@Bean
@ConditionalOnProperty(
    prefix = "spring.datasource",     // 前缀
    name = "url",                      // 属性名
    havingValue = "",                  // 期望值
    matchIfMissing = false             // 属性不存在时是否匹配
)
public DataSource dataSource() {
    return new HikariDataSource();
}

// application.yml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb  # 有 url 才创建
```

### 3.4 条件注解的执行顺序

```
1. @ConditionalOnClass / @ConditionalOnMissingClass（类路径检查，最早）
2. @ConditionalOnWebApplication / @ConditionalOnNotWebApplication
3. @ConditionalOnBean / @ConditionalOnMissingBean（容器检查）
4. @ConditionalOnProperty（配置检查）
5. @ConditionalOnExpression（最灵活，最后）
```

## 四、自动配置示例分析

### 4.1 Redis 自动配置

```java
@AutoConfiguration
@ConditionalOnClass(RedisOperations.class)        // 有 Redis 依赖
@EnableConfigurationProperties(RedisProperties.class)  // 绑定配置
public class RedisAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean(name = "redisTemplate")  // 没有 redisTemplate 才创建
    @ConditionalOnSingleCandidate(RedisConnectionFactory.class)
    public RedisTemplate<Object, Object> redisTemplate(
            RedisConnectionFactory redisConnectionFactory) {
        RedisTemplate<Object, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(redisConnectionFactory);
        return template;
    }
    
    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnSingleCandidate(RedisConnectionFactory.class)
    public StringRedisTemplate stringRedisTemplate(
            RedisConnectionFactory redisConnectionFactory) {
        return new StringRedisTemplate(redisConnectionFactory);
    }
}

// RedisProperties
@ConfigurationProperties(prefix = "spring.redis")
public class RedisProperties {
    private String host = "localhost";
    private int port = 6379;
    private String password;
    private int database = 0;
    // ...
}
```

### 4.2 内嵌 Tomcat 自动配置

```java
@AutoConfiguration
@ConditionalOnClass(ServletRequest.class)  // Servlet API 存在
@ConditionalOnWebApplication(type = Type.SERVLET)  // Servlet Web 应用
public class ServletWebServerFactoryAutoConfiguration {
    
    @Bean
    @ConditionalOnClass(Tomcat.class)  // 有 Tomcat 依赖
    public ServletWebServerFactory tomcatServletWebServerFactory() {
        return new TomcatServletWebServerFactory();
    }
    
    @Bean
    @ConditionalOnClass(Jetty.class)  // 有 Jetty 依赖
    public ServletWebServerFactory jettyServletWebServerFactory() {
        return new JettyServletWebServerFactory();
    }
}
```

## 五、自定义 Starter

### 5.1 Starter 命名规范

| 类型 | 命名规范 | 示例 |
|------|---------|------|
| 官方 | `spring-boot-starter-*` | `spring-boot-starter-web` |
| 第三方 | `*-spring-boot-starter` | `mybatis-spring-boot-starter` |

### 5.2 创建自定义 Starter

**步骤 1：创建自动配置模块**

```java
// 配置属性类
@ConfigurationProperties(prefix = "my.feature")
public class MyFeatureProperties {
    private boolean enabled = true;
    private String name = "default";
    private int timeout = 3000;
    // getter/setter
}

// 自动配置类
@AutoConfiguration
@ConditionalOnClass(MyFeatureService.class)
@EnableConfigurationProperties(MyFeatureProperties.class)
public class MyFeatureAutoConfiguration {
    
    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnProperty(prefix = "my.feature", name = "enabled", 
                           havingValue = "true", matchIfMissing = true)
    public MyFeatureService myFeatureService(MyFeatureProperties properties) {
        return new MyFeatureService(properties.getName(), properties.getTimeout());
    }
}
```

**步骤 2：注册自动配置**

```properties
# META-INF/spring.factories
org.springframework.boot.autoconfigure.EnableAutoConfiguration=\
  com.example.MyFeatureAutoConfiguration
```

或（Spring Boot 2.7+）：

```
# META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
com.example.MyFeatureAutoConfiguration
```

**步骤 3：创建 Starter 模块**

```xml
<!-- pom.xml -->
<dependency>
    <groupId>com.example</groupId>
    <artifactId>my-feature-spring-boot-autoconfigure</artifactId>
</dependency>
<dependency>
    <groupId>com.example</groupId>
    <artifactId>my-feature-core</artifactId>
</dependency>
```

**步骤 4：使用 Starter**

```xml
<dependency>
    <groupId>com.example</groupId>
    <artifactId>my-feature-spring-boot-starter</artifactId>
</dependency>
```

```yaml
# application.yml
my:
  feature:
    enabled: true
    name: my-app
    timeout: 5000
```

### 5.3 自定义 Starter 最佳实践

1. **提供默认值**：`matchIfMissing = true`
2. **使用 @ConditionalOnMissingBean**：允许用户覆盖
3. **提供配置属性**：`@ConfigurationProperties`
4. **提供默认配置**：合理默认值
5. **文档**：META-INF/spring-configuration-metadata.json

## 六、自动配置的调试

### 6.1 查看自动配置报告

```bash
# 启动时打印自动配置报告
java -jar app.jar --debug

# 或在 application.yml 中
debug: true
```

**输出**：
```
============================
CONDITIONS EVALUATION REPORT
============================

Positive matches:（生效的自动配置）
-----------------
   RedisAutoConfiguration matched:
      - @ConditionalOnClass found required class 'org.springframework.data.redis.core.RedisOperations' (OnClassCondition)

Negative matches:（未生效的自动配置）
-----------------
   ActiveMQAutoConfiguration:
      Did not match:
         - @ConditionalOnClass did not find required class 'javax.jms.ConnectionFactory' (OnClassCondition)
```

### 6.2 查看已注册的 Bean

```java
@Autowired
private ApplicationContext context;

public void printBeans() {
    String[] beans = context.getBeanDefinitionNames();
    Arrays.sort(beans);
    for (String bean : beans) {
        System.out.println(bean);
    }
}
```

### 6.3 排除自动配置

```java
// 方式 1：@SpringBootApplication 排除
@SpringBootApplication(exclude = {DataSourceAutoConfiguration.class})

// 方式 2：@EnableAutoConfiguration 排除
@EnableAutoConfiguration(exclude = {DataSourceAutoConfiguration.class})

// 方式 3：配置文件排除
spring:
  autoconfigure:
    exclude: org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration
```

## 七、面试高频问题

### Q1：Spring Boot 自动配置的原理？

**答**：
1. `@EnableAutoConfiguration` 通过 `@Import` 导入 `AutoConfigurationImportSelector`
2. `AutoConfigurationImportSelector` 从 `spring.factories` 加载所有自动配置类
3. 通过 `@ConditionalOnXXX` 条件注解过滤
4. 满足条件的配置类生效，注册 Bean

### Q2：@ConditionalOnMissingBean 的作用？

**答**：当容器中不存在指定 Bean 时才创建。允许用户自定义 Bean 覆盖默认配置。

### Q3：如何自定义 Starter？

**答**：
1. 创建自动配置类 + `@ConfigurationProperties`
2. 在 `spring.factories` 注册
3. 创建 Starter 模块依赖自动配置模块
4. 使用时引入 Starter 即可

### Q4：spring.factories 和 AutoConfiguration.imports 的区别？

**答**：
| 特性 | spring.factories | AutoConfiguration.imports |
|------|-----------------|--------------------------|
| 版本 | 所有版本 | 2.7+ |
| 格式 | key=value（多行）| 每行一个类 |
| 用途 | SPI 扩展 | 专用自动配置 |

### Q5：如何排除特定的自动配置？

**答**：
1. `@SpringBootApplication(exclude = {...})`
2. `spring.autoconfigure.exclude` 配置
3. `@EnableAutoConfiguration(exclude = {...})`

## 八、总结

**自动配置核心要点**：
- **入口**：`@EnableAutoConfiguration`
- **加载**：`spring.factories` / `AutoConfiguration.imports`
- **过滤**：`@ConditionalOnXXX` 条件注解
- **覆盖**：`@ConditionalOnMissingBean` 允许用户覆盖

**自动配置流程**：
1. `@SpringBootApplication` → `@EnableAutoConfiguration`
2. `AutoConfigurationImportSelector` 加载配置类
3. `@Conditional` 条件过滤
4. 满足条件的配置类注册 Bean

**自定义 Starter 步骤**：
1. 创建 `@AutoConfiguration` 类
2. 使用 `@ConfigurationProperties` 绑定配置
3. 在 `spring.factories` 注册
4. 创建 Starter 依赖模块

**最佳实践**：
1. 使用 `--debug` 查看自动配置报告
2. 用 `@ConditionalOnMissingBean` 允许覆盖
3. 提供合理的默认值
4. 遵循 Starter 命名规范

---

**下一篇预告**：Spring 循环依赖与三级缓存深度解析

**参考资料**：
- Spring Boot 官方文档：https://docs.spring.io/spring-boot/docs/current/reference/html/features.html
- 《Spring Boot 实战》- Craig Walls
- Spring Boot 源码：org.springframework.boot.autoconfigure
