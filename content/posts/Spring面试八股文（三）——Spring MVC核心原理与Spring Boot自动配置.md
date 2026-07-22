---
title: Spring面试八股文（三）——Spring MVC核心原理与Spring Boot自动配置
date: 2026-07-05 10:00:00+08:00
updated: '2026-07-05T10:00:00+08:00'
description: 🎯 本文目标：承接前两篇的IoC容器与AOP基础，深入Spring MVC的核心执行链路——DispatcherServlet的九大组件与请求处理全流程、HandlerMapping与HandlerAdapter的适配器模式实现、拦截器(Interceptor)与过滤器(Filter)的七点本质区别。
topic: java-spring
series: spring-interview
series_order: 3
level: intermediate
status: maintained
tags:
- 面试
- 八股文
- Spring
- Spring MVC
- DispatcherServlet
categories:
- Java 与 Spring
draft: false
---

> 🎯 **本文目标**：承接前两篇的IoC容器与AOP基础，深入Spring MVC的核心执行链路——DispatcherServlet的九大组件与请求处理全流程、HandlerMapping与HandlerAdapter的适配器模式实现、拦截器(Interceptor)与过滤器(Filter)的七点本质区别、Spring Boot的@EnableAutoConfiguration自动配置原理与@Conditional条件装配机制、以及自定义Starter的完整开发流程，构建Spring Web层与自动化配置的完整知识体系。

---

## 一、Spring MVC架构总览

### 1.1 什么是MVC？

**Q: MVC三层架构各自负责什么？**

```
用户请求
    ↓
┌─────────────────────────────────────────────────────────────┐
│                    DispatcherServlet                        │
│                    (前端控制器)                              │
└─────────────────────────────────────────────────────────────┘
    │          │          │
    ↓          ↓          ↓
┌────────┐ ┌────────┐ ┌────────┐
│Handler │ │Handler │ │ View   │
│Mapping │ │Adapter │ │Resolver│
│(处理器  │ │(处理器  │ │(视图   │
│ 映射器) │ │ 适配器) │ │ 解析器) │
└────────┘ └────────┘ └────────┘
    │          │          │
    ↓          ↓          ↓
┌──────────────────────────────────────┐
│         Controller (处理器)          │  ← 开发者写的核心
│          ↓                           │
│         Service                      │
│          ↓                           │
│         Repository                   │
└──────────────────────────────────────┘
    │
    ↓
┌──────────────────────────────────────┐
│         ModelAndView / Response      │
│         → 视图渲染 / JSON序列化       │
└──────────────────────────────────────┘
```

**经典面试回答：**

> MVC是Model-View-Controller的缩写，是表现层架构模式。Model承载业务数据，View负责数据展示，Controller处理用户请求并协调Model和View。Spring MVC在此基础上提供了DispatcherServlet作为前端控制器，统一调度请求处理全流程。

### 1.2 DispatcherServlet的九大组件

**Q: DispatcherServlet初始化了哪些核心组件？这些组件各自的作用是什么？**

DispatcherServlet是Spring MVC的核心，它在`initStrategies()`方法中初始化九大组件：

```java
// org.springframework.web.servlet.DispatcherServlet
protected void initStrategies(ApplicationContext context) {
    initMultipartResolver(context);          // 1. 文件上传解析器
    initLocaleResolver(context);             // 2. 国际化解析器
    initThemeResolver(context);              // 3. 主题解析器
    initHandlerMappings(context);            // 4. 处理器映射器
    initHandlerAdapters(context);            // 5. 处理器适配器
    initHandlerExceptionResolvers(context);  // 6. 异常处理器
    initRequestToViewNameTranslator(context);// 7. 视图名转换器
    initViewResolvers(context);              // 8. 视图解析器
    initFlashMapManager(context);            // 9. Flash属性管理器
}
```

| 组件 | 接口 | 作用 | 默认实现 |
|------|------|------|----------|
| MultipartResolver | `MultipartResolver` | 处理文件上传请求 | 无默认（需手动配置`CommonsMultipartResolver`） |
| LocaleResolver | `LocaleResolver` | 国际化，解析请求的Locale | `AcceptHeaderLocaleResolver` |
| ThemeResolver | `ThemeResolver` | 主题切换 | `FixedThemeResolver` |
| HandlerMapping | `HandlerMapping` | 根据请求URL找到处理器 | `RequestMappingHandlerMapping` |
| HandlerAdapter | `HandlerAdapter` | 调用处理器方法 | `RequestMappingHandlerAdapter` |
| HandlerExceptionResolver | `HandlerExceptionResolver` | 统一异常处理 | `DefaultErrorAttributes` |
| RequestToViewNameTranslator | `RequestToViewNameTranslator` | 无View时自动生成视图名 | `DefaultRequestToViewNameTranslator` |
| ViewResolver | `ViewResolver` | 将视图名解析为View对象 | `InternalResourceViewResolver` |
| FlashMapManager | `FlashMapManager` | 重定向时传递参数 | `SessionFlashMapManager` |

**面试要点：** 面试官常问「DispatcherServlet的初始化流程」——核心就是这九个组件的`init*`方法。而日常开发中最关注的是HandlerMapping、HandlerAdapter、ViewResolver和HandlerExceptionResolver四个。

---

## 二、DispatcherServlet请求处理全流程

### 2.1 一条请求的完整生命周期

**Q: 从浏览器输入URL到返回结果，Spring MVC内部经历了什么？**

这是面试中的高频题，需要能画出完整的时序图：

```java
// DispatcherServlet.doDispatch() 核心源码（简化版）
protected void doDispatch(HttpServletRequest request, HttpServletResponse response) {
    HttpServletRequest processedRequest = request;
    HandlerExecutionChain mappedHandler = null;
    
    try {
        // ========== 第1步：检查是否文件上传请求 ==========
        processedRequest = checkMultipart(request);
        
        // ========== 第2步：根据请求获取Handler ==========
        // HandlerMapping遍历所有注册的HandlerMapping，找到能处理当前请求的
        // 返回HandlerExecutionChain（包含Handler + 拦截器链）
        mappedHandler = getHandler(processedRequest);
        if (mappedHandler == null) {
            noHandlerFound(processedRequest, response);
            return;
        }
        
        // ========== 第3步：根据Handler获取HandlerAdapter ==========
        // HandlerAdapter遍历所有注册的HandlerAdapter，找到支持当前Handler的
        // supports()方法判断：判断Handler类型（如HandlerMethod、HttpRequestHandler等）
        HandlerAdapter ha = getHandlerAdapter(mappedHandler.getHandler());
        
        // ========== 第4步：执行拦截器的preHandle ==========
        if (!mappedHandler.applyPreHandle(processedRequest, response)) {
            return; // 拦截器返回false，请求终止
        }
        
        // ========== 第5步：适配器执行Handler ==========
        // 参数解析、数据绑定、调用Controller方法、处理返回值
        mv = ha.handle(processedRequest, response, mappedHandler.getHandler());
        
        // ========== 第6步：视图名转换（如果mv没有view） ==========
        applyDefaultViewName(processedRequest, mv);
        
        // ========== 第7步：执行拦截器的postHandle ==========
        mappedHandler.applyPostHandle(processedRequest, response, mv);
        
    } catch (Exception ex) {
        dispatchException = ex; // 交给异常处理器
    }
    
    // ========== 第8步：处理结果（视图渲染 或 @ResponseBody序列化） ==========
    processDispatchResult(processedRequest, response, mappedHandler, mv, dispatchException);
}
```

**一张图总结全流程：**

```
客户端请求
    │
    ▼
┌──────────────────────────────────────────────────┐
│ DispatcherServlet.doDispatch()                   │
│                                                  │
│ ① checkMultipart(request)                        │
│    判断是否文件上传，是则包装为 MultipartRequest   │
│                                                  │
│ ② getHandler(request)                            │
│    HandlerMapping 匹配 Handler (Controller方法)   │
│    返回 HandlerExecutionChain (Handler+拦截器链)  │
│                                                  │
│ ③ getHandlerAdapter(handler)                     │
│    HandlerAdapter 找到能执行该Handler的适配器      │
│                                                  │
│ ④ mappedHandler.applyPreHandle()                 │
│    按顺序执行所有拦截器的 preHandle()             │
│    任一返回 false 则终止请求                      │
│                                                  │
│ ⑤ ha.handle(request, response, handler)          │
│    ┌──────────────────────────────────┐          │
│    │ HandlerAdapter 内部：             │          │
│    │ · 参数解析(HandlerMethodArgument │          │
│    │   Resolver)                      │          │
│    │ · 数据绑定与校验(DataBinder)      │          │
│    │ · 调用Controller方法              │          │
│    │ · 返回值处理(HandlerMethodReturn │          │
│    │   ValueHandler)                  │          │
│    └──────────────────────────────────┘          │
│                                                  │
│ ⑥ applyDefaultViewName()                         │
│                                                  │
│ ⑦ mappedHandler.applyPostHandle()                │
│    倒序执行所有拦截器的 postHandle()              │
│                                                  │
│ ⑧ processDispatchResult()                        │
│    · 有异常→HandlerExceptionResolver处理         │
│    · @ResponseBody→HttpMessageConverter序列化    │
│    · ModelAndView→ViewResolver视图渲染           │
│                                                  │
│ ⑨ mappedHandler.triggerAfterCompletion()         │
│    倒序执行所有拦截器的 afterCompletion()          │
│    (无论成功/异常都会执行)                        │
└──────────────────────────────────────────────────┘
```

### 2.2 HandlerMapping：请求到处理器的映射

**Q: Spring MVC如何根据URL找到对应的Controller方法？**

```java
// RequestMappingHandlerMapping 的请求匹配流程
public interface HandlerMapping {
    HandlerExecutionChain getHandler(HttpServletRequest request);
}

// RequestMappingHandlerMapping 继承自 AbstractHandlerMethodMapping
// 核心数据结构：
// MappingRegistry 中维护：
// 1. Map<T, AbstractHandlerMethodMapping.MappingRegistration<T>> registry
//    key: RequestMappingInfo (URL匹配条件)
//    value: HandlerMethod (Controller方法)
// 2. 各种查找缓存

// URL匹配流程：
public class RequestMappingInfo {
    // 匹配条件包括：
    private PatternsRequestCondition patternsCondition;       // URL路径模式
    private RequestMethodsRequestCondition methodsCondition;   // GET/POST等
    private ParamsRequestCondition paramsCondition;            // 请求参数
    private HeadersRequestCondition headersCondition;          // 请求头
    private ConsumesRequestCondition consumesCondition;        // Content-Type
    private ProducesRequestCondition producesCondition;        // Accept
    private RequestConditionHolder customConditionHolder;      // 自定义条件
}
```

**路径匹配的Ant风格模式：**

```
/user/{id}          → /user/123        ✅
/user/{id}/orders   → /user/123/orders ✅
/user/**            → /user/a/b/c      ✅
/user/*/detail      → /user/123/detail ✅
/user/??            → /user/ab         ✅ (匹配两个字符)
```

**面试关键点：**
- `RequestMappingHandlerMapping` 在容器启动时扫描所有`@Controller`和`@RequestMapping`注解，构建URL到HandlerMethod的映射表
- 多个HandlerMapping同时存在时，按order排序，返回第一个非null结果
- `SimpleUrlHandlerMapping` 可以直接配置URL到Handler的映射，常用于静态资源

---

## 三、HandlerAdapter的适配器模式

### 3.1 为什么要用适配器模式？

**Q: Spring MVC的HandlerAdapter为什么采用适配器模式？有什么好处？**

```java
// 问题：不同类型的Handler，调用方式完全不同
// 如果没有适配器模式，只能这样写：

Object handler = getHandler(request);
if (handler instanceof HandlerMethod) {
    // 调用Controller方法：需要参数解析、数据绑定
    ((HandlerMethod) handler).invoke(args...);
} else if (handler instanceof HttpRequestHandler) {
    // 直接处理请求响应
    ((HttpRequestHandler) handler).handleRequest(request, response);
} else if (handler instanceof Servlet) {
    // 原生Servlet
    ((Servlet) handler).service(request, response);
} else if (handler instanceof Controller) { // 老式Controller接口
    ((Controller) handler).handleRequest(request, response);
}
// 每次增加新类型Handler，都要改这里的if-else —— 违反开闭原则！
```

**适配器模式解法：**

```java
// Spring MVC的HandlerAdapter接口
public interface HandlerAdapter {
    boolean supports(Object handler);  // 判断是否支持该Handler类型
    ModelAndView handle(HttpServletRequest request, 
                        HttpServletResponse response, 
                        Object handler); // 执行Handler
    long getLastModified(HttpServletRequest request, Object handler);
}

// 四个内置实现：
// 1. RequestMappingHandlerAdapter  → 支持 HandlerMethod (@RequestMapping方法)
// 2. HttpRequestHandlerAdapter     → 支持 HttpRequestHandler
// 3. SimpleControllerHandlerAdapter → 支持 Controller (老式接口)
// 4. SimpleServletHandlerAdapter   → 支持 Servlet

// DispatcherServlet获取适配器的逻辑：
protected HandlerAdapter getHandlerAdapter(Object handler) {
    for (HandlerAdapter ha : this.handlerAdapters) {
        if (ha.supports(handler)) {
            return ha;  // 遍历找到第一个支持该Handler的适配器
        }
    }
    throw new ServletException("No adapter for handler");
}
```

### 3.2 RequestMappingHandlerAdapter的深层机制

**Q: @RequestMapping方法的参数是如何自动注入的？返回值是如何处理的？**

```java
// RequestMappingHandlerAdapter.invokeHandlerMethod() 的核心流程
protected ModelAndView invokeHandlerMethod(HttpServletRequest request,
        HttpServletResponse response, HandlerMethod handlerMethod) {
    
    // 1. 创建 ServletInvocableHandlerMethod（可调用的HandlerMethod封装）
    ServletInvocableHandlerMethod invocableMethod = 
        createInvocableHandlerMethod(handlerMethod);
    
    // 2. 设置参数解析器（HandlerMethodArgumentResolver）
    invocableMethod.setHandlerMethodArgumentResolvers(
        this.argumentResolvers.getResolvers());
    
    // 3. 设置返回值处理器（HandlerMethodReturnValueHandler）
    invocableMethod.setHandlerMethodReturnValueHandlers(
        this.returnValueHandlers.getHandlers());
    
    // 4. 创建数据绑定工厂
    // 5. 创建ModelFactory（处理@ModelAttribute方法）
    // 6. 异步处理（如果返回Callable/DeferredResult/WebAsyncTask）
    
    // 7. 调用Controller方法
    invocableMethod.invokeAndHandle(webRequest, mavContainer);
    
    // 8. 返回ModelAndView
    return getModelAndView(mavContainer, modelFactory, webRequest);
}
```

**内置的30+参数解析器（部分核心）：**

```java
// 常用参数解析器一览：
RequestParamMethodArgumentResolver    // @RequestParam 参数
PathVariableMethodArgumentResolver    // @PathVariable 参数  
RequestHeaderMethodArgumentResolver   // @RequestHeader 参数
ServletRequestMethodArgumentResolver  // HttpServletRequest/Response
ModelAttributeMethodProcessor         // @ModelAttribute 参数
RequestBodyAdviceArgumentResolver     // @RequestBody 参数
RequestPartMethodArgumentResolver     // @RequestPart (文件上传)
SessionAttributeMethodArgumentResolver// @SessionAttribute
ExpressionValueMethodArgumentResolver // @Value 参数
ServletCookieValueMethodArgumentResolver // @CookieValue
```

**返回值处理器（部分核心）：**

```java
ModelAndViewMethodReturnValueHandler      // ModelAndView
ModelMethodProcessor                      // Model
ViewMethodReturnValueHandler              // View
ResponseBodyAdviceReturnValueHandler      // @ResponseBody → JSON
HttpEntityMethodProcessor                 // ResponseEntity / HttpEntity
CallableMethodReturnValueHandler          // Callable (异步)
DeferredResultMethodReturnValueHandler    // DeferredResult (异步)
StreamingResponseBodyReturnValueHandler   // StreamingResponseBody
```

---

## 四、拦截器(Interceptor) vs 过滤器(Filter)

### 4.1 七点本质区别

**Q: 拦截器(Interceptor)和过滤器(Filter)有什么区别？分别适用于什么场景？**

这是面试高频对比题，需要从多个维度回答：

| 维度 | Filter（过滤器） | Interceptor（拦截器） |
|------|------------------|----------------------|
| **规范来源** | Servlet规范（javax.servlet） | Spring框架（Spring MVC） |
| **容器管理** | Servlet容器管理（如Tomcat） | Spring IoC容器管理 |
| **执行顺序** | Filter → Interceptor → Controller | 在Filter之后执行 |
| **作用范围** | 所有进入Servlet的请求（包括静态资源） | 只对经过DispatcherServlet的请求有效 |
| **依赖注入** | 不能直接注入Spring Bean（需通过DelegatingFilterProxy） | 可直接注入Spring Bean |
| **执行时机** | 在Servlet之前/之后 | 在HandlerAdapter执行Handler之前/之后 |
| **生命周期** | init() → doFilter() → destroy() | preHandle() → postHandle() → afterCompletion() |

**完整调用链示意图：**

```
HTTP Request
    │
    ▼
┌───────────────────────┐
│    FilterChain        │
│  ┌─────────────────┐  │
│  │ Filter1.doFilter │  │
│  │  ┌────────────┐  │  │
│  │  │Filter2     │  │  │
│  │  │ ┌────────┐ │  │  │
│  │  │ │Filter3 │ │  │  │
│  │  │ │  ↓     │ │  │  │
│  │  │ └────────┘ │  │  │  ← Filter链结束
│  │  └────────────┘  │  │
│  └─────────────────┘  │
└───────────────────────┘
            │
            ▼
┌───────────────────────────────────────────┐
│         DispatcherServlet                 │
│                                           │
│  ┌─────────────────────────────────────┐ │
│  │ HandlerExecutionChain               │ │
│  │                                     │ │
│  │ Interceptor1.preHandle() ───────┐   │ │
│  │   Interceptor2.preHandle() ──┐  │   │ │
│  │     Interceptor3.preHandle()─┐│  │   │ │
│  │       ↓                      ││  │   │ │
│  │    Controller.handle()       ││  │   │ │  ← 执行业务方法
│  │       ↓                      ││  │   │ │
│  │     Interceptor3.postHandle()┘│  │   │ │
│  │   Interceptor2.postHandle() ──┘  │   │ │
│  │ Interceptor1.postHandle() ───────┘   │ │
│  │                                     │ │
│  │ // 视图渲染后                        │ │
│  │ Interceptor3.afterCompletion()      │ │
│  │ Interceptor2.afterCompletion()      │ │
│  │ Interceptor1.afterCompletion()      │ │
│  └─────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

### 4.2 代码对比实现

**Filter实现：**

```java
// 日志Filter（记录请求耗时）
@WebFilter(urlPatterns = "/*")
public class RequestLoggingFilter implements Filter {
    
    @Override
    public void init(FilterConfig filterConfig) {
        // 初始化（只执行一次）
    }
    
    @Override
    public void doFilter(ServletRequest request, ServletResponse response, 
                         FilterChain chain) throws IOException, ServletException {
        long start = System.currentTimeMillis();
        
        // ===== 前置处理 =====
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        System.out.println("Request URL: " + httpRequest.getRequestURI());
        
        // ===== 放行到下一个Filter或Servlet =====
        chain.doFilter(request, response);
        
        // ===== 后置处理 =====
        long duration = System.currentTimeMillis() - start;
        System.out.println("Request completed in " + duration + "ms");
    }
    
    @Override
    public void destroy() {
        // 销毁（只执行一次）
    }
}
```

**Interceptor实现：**

```java
// 认证拦截器（检查Token）
@Component
public class AuthInterceptor implements HandlerInterceptor {
    
    @Autowired
    private TokenService tokenService;  // 可以直接注入Spring Bean！
    
    @Override
    public boolean preHandle(HttpServletRequest request, 
            HttpServletResponse response, Object handler) {
        String token = request.getHeader("Authorization");
        if (token == null || !tokenService.validate(token)) {
            response.setStatus(401);
            response.getWriter().write("Unauthorized");
            return false;  // 返回false终止请求
        }
        // 将用户信息存入request，方便后续使用
        UserInfo user = tokenService.parseUser(token);
        request.setAttribute("currentUser", user);
        return true;
    }
    
    @Override
    public void postHandle(HttpServletRequest request, 
            HttpServletResponse response, Object handler,
            ModelAndView modelAndView) {
        // 在Controller执行后、视图渲染前执行
        // 可以修改ModelAndView
    }
    
    @Override
    public void afterCompletion(HttpServletRequest request,
            HttpServletResponse response, Object handler, Exception ex) {
        // 请求完成后的清理工作
        // 无论是否有异常都会执行（类似finally）
        // 适合清理ThreadLocal、记录审计日志等
    }
}

// 注册Interceptor
@Configuration
public class WebConfig implements WebMvcConfigurer {
    
    @Autowired
    private AuthInterceptor authInterceptor;
    
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(authInterceptor)
                .addPathPatterns("/api/**")      // 拦截所有API
                .excludePathPatterns("/api/login", "/api/register");  // 排除登录注册
    }
}
```

### 4.3 选择策略

**面试时如何回答「什么时候用Filter，什么时候用Interceptor」：**

```
用Filter的场景：
├── 字符编码过滤 (CharacterEncodingFilter)
├── CORS跨域处理 (CorsFilter)
├── XSS/SQL注入安全过滤
├── 请求内容压缩 (GzipFilter)
└── 不与Spring业务逻辑耦合的通用处理

用Interceptor的场景：
├── 用户认证与权限校验（需要查数据库/Redis）
├── 操作日志记录（需要获取当前用户信息、操作方法等）
├── 接口防刷/限流（需要结合业务数据）
├── 国际化语言切换
└── 敏感词过滤（需要业务上下文）
```

---

## 五、Spring Boot自动配置原理

### 5.1 @SpringBootApplication背后的秘密

**Q: Spring Boot如何实现「开箱即用」的自动配置？**

```java
// @SpringBootApplication 是一个组合注解
@SpringBootConfiguration     // 标识这是一个配置类（本质是@Configuration）
@EnableAutoConfiguration     // 开启自动配置（核心）
@ComponentScan(              // 组件扫描
    excludeFilters = { @Filter(type = FilterType.CUSTOM, 
        classes = TypeExcludeFilter.class) }
)
public @interface SpringBootApplication { ... }

// @EnableAutoConfiguration 又组合了：
@AutoConfigurationPackage    // 将主类所在包注册为自动配置包
@Import(AutoConfigurationImportSelector.class)  // 导入自动配置选择器
public @interface EnableAutoConfiguration { ... }
```

**AutoConfigurationImportSelector的工作流程：**

```java
public class AutoConfigurationImportSelector 
        implements DeferredImportSelector {
    
    @Override
    public String[] selectImports(AnnotationMetadata annotationMetadata) {
        // 1. 判断是否启用自动配置
        if (!isEnabled(annotationMetadata)) {
            return NO_IMPORTS;
        }
        
        // 2. 加载 spring.factories 中配置的自动配置类
        AutoConfigurationEntry entry = getAutoConfigurationEntry(annotationMetadata);
        
        // 3. 返回要导入的配置类全限定名
        return StringUtils.toStringArray(entry.getConfigurations());
    }
    
    protected AutoConfigurationEntry getAutoConfigurationEntry(
            AnnotationMetadata annotationMetadata) {
        // 步骤①：从 META-INF/spring/org.springframework.boot.autoconfigure.
        //        AutoConfiguration.imports 加载所有候选配置类
        List<String> configurations = getCandidateConfigurations(annotationMetadata, attributes);
        
        // 步骤②：去重
        configurations = removeDuplicates(configurations);
        
        // 步骤③：排除 @SpringBootApplication(exclude=...) 指定的类
        Set<String> exclusions = getExclusions(annotationMetadata, attributes);
        configurations.removeAll(exclusions);
        
        // 步骤④：通过 @Conditional 过滤 —— 这是关键！
        configurations = filter(configurations, autoConfigurationMetadata);
        
        // 步骤⑤：触发导入事件
        fireAutoConfigurationImportEvents(configurations, exclusions);
        
        return new AutoConfigurationEntry(configurations, exclusions);
    }
}
```

**配置文件中的自动配置声明：**

Spring Boot 2.7+ 之后用 `.imports` 文件：

```
# META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports
org.springframework.boot.autoconfigure.web.servlet.DispatcherServletAutoConfiguration
org.springframework.boot.autoconfigure.web.servlet.WebMvcAutoConfiguration
org.springframework.boot.autoconfigure.web.servlet.HttpEncodingAutoConfiguration
org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration
org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration
org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration
# ... 总共 140+ 个自动配置类
```

**以 DataSourceAutoConfiguration 为例看完整流程：**

```java
@AutoConfiguration  // Spring Boot 2.7+ 新注解，替代 @Configuration
@ConditionalOnClass({ DataSource.class, EmbeddedDatabaseType.class })
@EnableConfigurationProperties(DataSourceProperties.class)
@Import({ DataSourcePoolMetadataProvidersConfiguration.class,
          DataSourceInitializationConfiguration.class })
public class DataSourceAutoConfiguration {

    @Configuration(proxyBeanMethods = false)
    @Conditional(PooledDataSourceCondition.class)      // PooledDataSourceCondition条件
    @ConditionalOnMissingBean({ DataSource.class, XADataSource.class })
    @Import({ DataSourceConfiguration.Hikari.class,    // HikariCP连接池
              DataSourceConfiguration.Tomcat.class,    // Tomcat连接池
              DataSourceConfiguration.Dbcp2.class,     // DBCP2连接池
              DataSourceConfiguration.OracleUcp.class }) // Oracle UCP
    static class PooledDataSourceConfiguration {
        // 综合多层@Conditional推断使用哪个连接池
    }
}
```

**自问自答：为什么Spring Boot能知道要用HikariCP？**

```
判断链路：
1. @ConditionalOnClass({DataSource.class}) 
   → classpath上有 javax.sql.DataSource ✅ 
   
2. @Conditional(PooledDataSourceCondition.class)
   → application.properties 中 spring.datasource.type 未指定 
   → 进入"自动选择"模式

3. @Import 中的顺序决定了优先级：
   Hikari.class → Tomcat.class → Dbcp2.class → OracleUcp.class
   
4. 依次判断：
   HikariCP判断：classpath上有 com.zaxxer.hikari.HikariDataSource? 
   → 有（spring-boot-starter-data-jdbc 默认引入） ✅
   → 使用 HikariCP！
```

### 5.2 @Conditional条件装配全家桶

**Q: Spring Boot通过哪些条件注解来控制自动配置的生效与否？**

```java
// ===== 第一梯队：最常用的四个 =====
@ConditionalOnClass(RedisConnectionFactory.class)
// classpath中存在指定类时生效（最常用，100+自动配置类都在用）

@ConditionalOnMissingBean(DataSource.class)
// 容器中不存在指定Bean时生效（"兜底"机制，用户可以自己定义覆盖）

@ConditionalOnProperty(prefix = "spring.redis", name = "enabled", 
                       havingValue = "true", matchIfMissing = true)
// 配置文件中有指定属性且值匹配时生效

@ConditionalOnBean(DataSource.class)
// 容器中存在指定Bean时生效

// ===== 第二梯队：特定场景 =====
@ConditionalOnMissingClass("org.springframework.web.servlet.DispatcherServlet")
// classpath中不存在指定类时生效

@ConditionalOnResource(resources = "classpath:mybatis-config.xml")
// 指定资源存在时生效

@ConditionalOnExpression("${app.cache.enabled} and ${app.cache.type} == 'redis'")
// SpEL表达式为true时生效

@ConditionalOnWebApplication(type = Type.SERVLET)
// 是否Web应用（SERVLET / REACTIVE / ANY）

@ConditionalOnSingleCandidate(DataSource.class)
// 容器中有且仅有一个指定类型Bean时生效

@ConditionalOnJava(range = Range.EQUAL_OR_NEWER, value = JavaVersion.SEVENTEEN)
// Java版本条件

@ConditionalOnCloudPlatform(CloudPlatform.KUBERNETES)
// 运行在特定云平台上时生效
```

**条件装配的精妙示例：**

```java
// WebFlux vs WebMVC的自动选择
@ConditionalOnWebApplication  // 是Web应用
@ConditionalOnClass({ DispatcherServlet.class })  // classpath有Spring MVC
static class WebMvcCondition { }  // → 开启Spring MVC

@ConditionalOnWebApplication
@ConditionalOnClass({ org.springframework.web.reactive.DispatcherHandler.class })
static class WebFluxCondition { }  // → 开启WebFlux

// 两者互斥：同时存在时，WebMVC优先（先注册的Condition先匹配到）
```

---

## 六、自定义Starter开发

### 6.1 Starter的命名规范与结构

**Q: 如何开发一个自定义Spring Boot Starter？步骤是什么？**

**命名规范：**
- 官方Starter：`spring-boot-starter-{模块名}` 如 `spring-boot-starter-data-redis`
- 第三方Starter：`{模块名}-spring-boot-starter` 如 `mybatis-spring-boot-starter`

**标准目录结构：**

```
my-starter-spring-boot-starter/
├── pom.xml
├── src/main/java/com/example/starter/
│   ├── MyStarterAutoConfiguration.java      // 自动配置类
│   ├── MyStarterProperties.java             // 属性配置类
│   └── core/
│       ├── MyService.java                    // 核心业务类
│       └── MyTemplate.java                   // 模板类
└── src/main/resources/
    └── META-INF/
        └── spring/
            └── org.springframework.boot.autoconfigure.AutoConfiguration.imports
```

### 6.2 实战：开发一个「操作日志」Starter

**第1步：定义属性配置类**

```java
// 用 @ConfigurationProperties 绑定配置文件
@ConfigurationProperties(prefix = "operation.log")
public class OperationLogProperties {
    
    /** 是否启用操作日志 */
    private boolean enabled = true;  // 默认开启
    
    /** 日志存储方式：db(数据库) / file(文件) / redis(Redis) */
    private StorageType storage = StorageType.DB;
    
    /** 审计日志是否异步写入 */
    private boolean async = true;
    
    /** 异步线程池核心线程数 */
    private int corePoolSize = 5;
    
    /** 排除不需要记录日志的URL */
    private List<String> excludeUrls = new ArrayList<>();
    
    public enum StorageType { DB, FILE, REDIS }
    
    // getters and setters...
}
```

**第2步：写自动配置类**

```java
@AutoConfiguration  // 标记为自动配置类
@ConditionalOnProperty(prefix = "operation.log", name = "enabled", 
                       havingValue = "true", matchIfMissing = true)
@EnableConfigurationProperties(OperationLogProperties.class)
public class OperationLogAutoConfiguration {
    
    // ===== 数据库存储实现 =====
    @Bean
    @ConditionalOnMissingBean(OperationLogService.class)
    @ConditionalOnProperty(prefix = "operation.log", name = "storage", 
                           havingValue = "DB", matchIfMissing = true)
    public OperationLogService dbOperationLogService(
            OperationLogMapper logMapper,
            OperationLogProperties properties) {
        return new DbOperationLogService(logMapper, properties);
    }
    
    // ===== 文件存储实现 =====
    @Bean
    @ConditionalOnMissingBean(OperationLogService.class)
    @ConditionalOnProperty(prefix = "operation.log", name = "storage", 
                           havingValue = "FILE")
    public OperationLogService fileOperationLogService(
            OperationLogProperties properties) {
        return new FileOperationLogService(properties);
    }
    
    // ===== 注册AOP切面 =====
    @Bean
    @ConditionalOnBean(OperationLogService.class)
    public OperationLogAspect operationLogAspect(
            OperationLogService operationLogService) {
        return new OperationLogAspect(operationLogService);
    }
    
    // ===== 异步线程池 =====
    @Bean("operationLogExecutor")
    @ConditionalOnProperty(prefix = "operation.log", name = "async", 
                           havingValue = "true", matchIfMissing = true)
    public ThreadPoolTaskExecutor operationLogExecutor(
            OperationLogProperties properties) {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(properties.getCorePoolSize());
        executor.setMaxPoolSize(properties.getCorePoolSize() * 2);
        executor.setQueueCapacity(1000);
        executor.setThreadNamePrefix("operation-log-");
        executor.setRejectedExecutionHandler(new CallerRunsPolicy());
        return executor;
    }
}
```

**第3步：注册自动配置**

```
# src/main/resources/META-INF/spring/
# org.springframework.boot.autoconfigure.AutoConfiguration.imports

com.example.starter.OperationLogAutoConfiguration
```

**第4步：让使用者配置**

```yaml
# 使用者的 application.yml
operation:
  log:
    enabled: true
    storage: DB          # 数据库存储
    async: true          # 异步写入
    core-pool-size: 5
    exclude-urls:
      - /actuator/**
      - /health
```

### 6.3 Starter开发避坑指南

```
常见坑点：

1. ❌ 在Starter里定义了@RequestMapping
   → 会被使用者的DispatcherServlet扫描到，造成冲突
   ✅ 让使用者通过 @Import 手动导入Controller，不要自动注册

2. ❌ @ConditionalOnMissingBean 放错了位置
   → 可能永远无法被用户自定义Bean覆盖
   ✅ @ConditionalOnMissingBean 放在@Bean方法上，而非类上

3. ❌ 忘记处理「使用者未配置数据源」的情况
   → 如果Starter需要DataSource，但没有@ConditionalOnBean(DataSource.class)
     使用者没有数据源时会启动失败
   ✅ 加上 @ConditionalOnBean(DataSource.class) 保护

4. ❌ 属性类忘记加 @EnableConfigurationProperties
   → @ConfigurationProperties扫描只对@Component扫描的Bean生效
   ✅ 在自动配置类上显式加 @EnableConfigurationProperties(XXXProperties.class)

5. ❌ properties文件中有中文注释，编译后乱码
   → Maven默认编码可能不是UTF-8
   ✅ pom.xml加上 <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
```

---

## 七、Spring Boot启动流程

### 7.1 SpringApplication.run()到底做了什么？

**Q: Spring Boot应用的启动流程是怎样的？**

```java
public SpringApplication(Class<?>... primarySources) {
    // ① 推断应用类型
    this.webApplicationType = WebApplicationType.deduceFromClasspath();
    // SERVLET / REACTIVE / NONE
    
    // ② 通过SPI加载 BootstrapRegistryInitializer
    this.bootstrapRegistryInitializers = 
        getSpringFactoriesInstances(BootstrapRegistryInitializer.class);
    
    // ③ 通过SPI加载 ApplicationContextInitializer
    setInitializers(getSpringFactoriesInstances(ApplicationContextInitializer.class));
    
    // ④ 通过SPI加载 ApplicationListener
    setListeners(getSpringFactoriesInstances(ApplicationListener.class));
    
    // ⑤ 推断主类（通过堆栈追踪找到main方法所在的类）
    this.mainApplicationClass = deduceMainApplicationClass();
}

// run()核心流程
public ConfigurableApplicationContext run(String... args) {
    long startTime = System.nanoTime();
    
    // ① 创建引导上下文，启动BootstrapRegistryInitializer
    DefaultBootstrapContext bootstrapContext = createBootstrapContext();
    ConfigurableApplicationContext context = null;
    
    // ② 设置 java.awt.headless 属性
    configureHeadlessProperty();
    
    // ③ 获取 SpringApplicationRunListeners
    //    通过SPI加载，默认是 EventPublishingRunListener
    SpringApplicationRunListeners listeners = getRunListeners(args);
    listeners.starting(bootstrapContext);  // 发布 ApplicationStartingEvent
    
    try {
        // ④ 封装命令行参数
        ApplicationArguments applicationArguments = 
            new DefaultApplicationArguments(args);
        
        // ⑤ 准备环境（加载配置）
        ConfigurableEnvironment environment = 
            prepareEnvironment(listeners, bootstrapContext, applicationArguments);
        //   → 发布 ApplicationEnvironmentPreparedEvent
        //   → ConfigFileApplicationListener 监听该事件，加载 application.yml
        
        // ⑥ 打印Banner
        Banner printedBanner = printBanner(environment);
        
        // ⑦ 创建 ApplicationContext
        //    Servlet → AnnotationConfigServletWebServerApplicationContext
        //    Reactive → AnnotationConfigReactiveWebServerApplicationContext
        context = createApplicationContext();
        context.setApplicationStartup(this.applicationStartup);
        
        // ⑧ 准备上下文
        prepareContext(bootstrapContext, context, environment,
                       listeners, applicationArguments, printedBanner);
        //   → 执行所有 ApplicationContextInitializer
        //   → 加载主类为配置源
        //   → 发布 ApplicationContextInitializedEvent
        //   → 注册启动参数为Bean
        
        // ⑨ 刷新上下文（核心！）
        refreshContext(context);
        //   → AbstractApplicationContext.refresh() 的13个步骤
        
        // ⑩ 刷新后处理
        afterRefresh(context, applicationArguments);
        
        Duration timeTakenToStartup = Duration.ofNanos(System.nanoTime() - startTime);
        
        // ⑪ 发布 ApplicationStartedEvent
        listeners.started(context, timeTakenToStartup);
        
        // ⑫ 执行 Runner
        callRunners(context, applicationArguments);
        //   → ApplicationRunner.run()
        //   → CommandLineRunner.run()
        
        // ⑬ 发布 ApplicationReadyEvent（应用完全就绪！）
        Duration timeTakenToReady = Duration.ofNanos(System.nanoTime() - startTime);
        listeners.ready(context, timeTakenToReady);
        
    } catch (Throwable ex) {
        // 发布 ApplicationFailedEvent
        handleRunFailure(context, ex, listeners);
        throw new IllegalStateException(ex);
    }
    
    return context;
}
```

**一张图看懂启动全流程：**

```
SpringApplication.run()
    │
    ├─ ① 推断应用类型 (SERVLET/REACTIVE/NONE)
    ├─ ②~③ 加载 Initializer & Listener (SPI机制)
    ├─ ④ 创建BootstrapContext
    │
    ├─ ─ ─ listeners.starting() ─ ─ ─ → ApplicationStartingEvent
    │
    ├─ ⑤ prepareEnvironment()
    │     ├─ 创建 Environment
    │     ├─ 加载 application.properties/yml
    │     └─ ─ → ApplicationEnvironmentPreparedEvent
    │
    ├─ ⑥ 打印 Banner
    ├─ ⑦ 创建 ApplicationContext
    │     └─ AnnotationConfigServletWebServerApplicationContext
    │
    ├─ ⑧ prepareContext()
    │     ├─ 执行所有 ApplicationContextInitializer
    │     ├─ 加载主类Bean定义
    │     └─ ─ → ApplicationContextInitializedEvent
    │
    ├─ ⑨ refreshContext() ──────────── 最核心步骤！
    │     ├─ prepareRefresh()
    │     ├─ obtainFreshBeanFactory() (读取Bean定义)
    │     ├─ prepareBeanFactory()
    │     ├─ postProcessBeanFactory()
    │     ├─ invokeBeanFactoryPostProcessors()
    │     │   └─ ConfigurationClassPostProcessor
    │     │       └─ 处理 @Configuration、@Import、@ComponentScan
    │     │       └─ AutoConfigurationImportSelector
    │     │           └─ 加载所有自动配置类！
    │     ├─ registerBeanPostProcessors()
    │     ├─ initMessageSource()
    │     ├─ initApplicationEventMulticaster()
    │     ├─ onRefresh() 
    │     │   └─ createWebServer() → 启动内嵌Tomcat！
    │     ├─ registerListeners()
    │     ├─ finishBeanFactoryInitialization()
    │     │   └─ 实例化所有单例Bean（非懒加载）
    │     └─ finishRefresh()
    │         └─ startWebServer() → Tomcat开始接受请求
    │
    ├─ ⑩ afterRefresh()
    ├─ ─ → listeners.started() ─ ─ → ApplicationStartedEvent
    ├─ ⑫ callRunners() (ApplicationRunner & CommandLineRunner)
    └─ ─ → listeners.ready() ─ ─ → ApplicationReadyEvent
            ↓
         应用就绪，可以接受请求！
```

---

## 八、面试高频题总结

**Q: Spring MVC面试中最常被问到的问题有哪些？**

```
Spring MVC核心 5连问：
1. DispatcherServlet的请求处理流程（doDispatch源码）
2. HandlerMapping和HandlerAdapter的职责与区别
3. @RequestMapping如何映射到具体方法？
4. 拦截器(Interceptor)和过滤器(Filter)的区别
5. Spring MVC如何实现RESTful API？

Spring Boot核心 5连问：
6. @SpringBootApplication注解包含哪几个注解？
7. Spring Boot自动配置的原理（AutoConfigurationImportSelector）
8. @Conditional系列注解有哪些？各自怎么用？
9. Spring Boot的启动流程（SpringApplication.run()）
10. 如何自定义Starter？需要注意什么？

参数绑定 3连问：
11. @RequestBody和@RequestParam的区别
12. @ModelAttribute的工作流程
13. @Valid校验注解的实现原理

异常处理 2连问：
14. @ControllerAdvice + @ExceptionHandler的实现原理
15. Spring Boot的 /error 端点如何自定义？
```

---

## 九、下期预告

下一篇将深入 **Spring Boot监控与运维**——Actuator的四大端点类型（Health/Info/Metrics/Env）及其安全配置、Micrometer指标采集体系与Prometheus+Grafana监控大盘搭建、Spring Boot Admin可视化运维平台、优雅停机的Shutdown机制与Graceful Shutdown原理、以及Spring Boot应用调优的十大实践，构建Spring Boot运维监控的完整能力体系。敬请期待！🦐

---

*本系列持续更新中，欢迎关注公众号获取最新文章。*
