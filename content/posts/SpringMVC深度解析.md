---
title: Spring MVC 深度解析
date: 2026-05-11 17:00:00+08:00
updated: '2026-05-11T17:00:00+08:00'
description: 面试高频问题：Spring MVC 的请求流程？@RequestParam 和 @RequestBody 的区别？拦截器和过滤器的区别？ Spring MVC 是 Spring 框架的 Web 模块，用于构建 Web
  应用。理解 Spring MVC 的请求流程，是掌握 Spring Web 开发的。
topic: java-spring
level: intermediate
status: maintained
tags:
- Spring
- mvc
- controller
- interceptor
categories:
- Java 与 Spring
draft: false
---

> 面试高频问题：Spring MVC 的请求流程？@RequestParam 和 @RequestBody 的区别？拦截器和过滤器的区别？

## 引言

Spring MVC 是 Spring 框架的 Web 模块，用于构建 Web 应用。理解 Spring MVC 的请求流程，是掌握 Spring Web 开发的关键。本文将从请求流程到参数绑定，全面解析 Spring MVC。

## 一、Spring MVC 架构

### 1.1 MVC 模式

```
┌─────────────────────────────────────────────────────┐
│                   MVC 模式                            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐       │
│  │  Model  │◄───│Controller│───►│  View  │       │
│  │ (数据)  │    │ (控制器) │    │ (视图) │       │
│  └─────────┘    └─────────┘    └─────────┘       │
│       ▲               │               ▲              │
│       │               │               │              │
│       └───────────────┴───────────────┘              │
│                 请求 / 响应                           │
└─────────────────────────────────────────────────────┘
```

### 1.2 Spring MVC 核心组件

| 组件 | 作用 |
|------|------|
| `DispatcherServlet` | 前端控制器，统一处理请求 |
| `HandlerMapping` | 映射请求到处理器 |
| `HandlerAdapter` | 适配不同类型的处理器 |
| `Handler` | 处理器（Controller 方法）|
| `ViewResolver` | 解析视图名称到视图 |
| `View` | 视图（JSP、Thymeleaf 等）|

## 二、Spring MVC 请求流程

### 2.1 完整流程

```
浏览器发送请求
    │
    ▼
┌─────────────────┐
│DispatcherServlet │  ← 前端控制器（统一入口）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│HandlerMapping   │  ← 查找 Handler（根据 URL）
└────────┬────────┘
         │ 返回 HandlerExecutionChain
         ▼
┌─────────────────┐
│HandlerAdapter   │  ← 适配调用 Handler
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Handler       │  ← Controller 方法（执行业务逻辑）
└────────┬────────┘
         │ 返回 ModelAndView
         ▼
┌─────────────────┐
│ViewResolver     │  ← 解析视图名称
└────────┬────────┘
         │ 返回 View 对象
         ▼
┌─────────────────┐
│     View       │  ← 渲染视图
└────────┬────────┘
         │
         ▼
    响应浏览器
```

### 2.2 源码流程（简化）

```java
// DispatcherServlet.doDispatch()
protected void doDispatch(HttpServletRequest request, HttpServletResponse response) {
    // 1. 获取 Handler
    HandlerExecutionChain mappedHandler = getHandler(request);
    
    // 2. 获取 HandlerAdapter
    HandlerAdapter ha = getHandlerAdapter(mappedHandler.getHandler());
    
    // 3. 执行拦截器 preHandle()
    if (!mappedHandler.applyPreHandle(request, response)) {
        return;
    }
    
    // 4. 执行 Handler（Controller 方法）
    ModelAndView mv = ha.handle(request, response, mappedHandler.getHandler());
    
    // 5. 执行拦截器 postHandle()
    mappedHandler.applyPostHandle(request, response, mv);
    
    // 6. 解析视图并渲染
    processDispatchResult(request, response, mappedHandler, mv, dispatchException);
    
    // 7. 执行拦截器 afterCompletion()
    mappedHandler.triggerAfterCompletion(request, response, null);
}
```

## 三、注解驱动开发

### 3.1 @Controller 和 @RestController

```java
// @Controller：返回视图名称
@Controller
public class OrderController {
    
    @RequestMapping("/order/{id}")
    public String getOrder(@PathVariable Long id, Model model) {
        Order order = orderService.getOrder(id);
        model.addAttribute("order", order);
        return "order-detail";  // 视图名称
    }
}

// @RestController = @Controller + @ResponseBody
@RestController
public class OrderApiController {
    
    @GetMapping("/api/order/{id}")
    public Order getOrder(@PathVariable Long id) {
        return orderService.getOrder(id);  // 返回 JSON
    }
}
```

### 3.2 请求映射注解

| 注解 | 说明 |
|------|------|
| `@RequestMapping` | 通用映射 |
| `@GetMapping` | GET 请求 |
| `@PostMapping` | POST 请求 |
| `@PutMapping` | PUT 请求 |
| `@DeleteMapping` | DELETE 请求 |
| `@PatchMapping` | PATCH 请求 |

```java
@RestController
@RequestMapping("/api/orders")
public class OrderController {
    
    @GetMapping("/{id}")        // GET /api/orders/1
    public Order getOrder(@PathVariable Long id) {
        return orderService.getOrder(id);
    }
    
    @PostMapping             // POST /api/orders
    public Order createOrder(@RequestBody Order order) {
        return orderService.createOrder(order);
    }
    
    @PutMapping("/{id}")    // PUT /api/orders/1
    public Order updateOrder(@PathVariable Long id, @RequestBody Order order) {
        return orderService.updateOrder(id, order);
    }
    
    @DeleteMapping("/{id}") // DELETE /api/orders/1
    public void deleteOrder(@PathVariable Long id) {
        orderService.deleteOrder(id);
    }
}
```

## 四、参数绑定

### 4.1 常用参数注解

| 注解 | 说明 | 示例 |
|------|------|------|
| `@PathVariable` | URL 路径参数 | `/order/{id}` → `@PathVariable Long id` |
| `@RequestParam` | 查询参数 | `?name=John` → `@RequestParam String name` |
| `@RequestBody` | 请求体（JSON）| POST JSON → `@RequestBody Order order` |
| `@RequestHeader` | 请求头 | `@RequestHeader("User-Agent") String ua` |
| `@CookieValue` | Cookie 值 | `@CookieValue("JSESSIONID") String sessionId` |

### 4.2 @RequestParam vs @RequestBody

```java
// @RequestParam：从查询参数获取（?name=John&age=20）
@GetMapping("/users")
public List<User> getUsers(
    @RequestParam String name,
    @RequestParam Integer age) {
    return userService.findUsers(name, age);
}

// @RequestBody：从请求体获取（JSON）
@PostMapping("/users")
public User createUser(@RequestBody User user) {
    return userService.createUser(user);
}
```

**区别**：

| 特性 | @RequestParam | @RequestBody |
|------|--------------|---------------|
| 数据位置 | URL 查询参数 | 请求体（Body）|
| 数据格式 | `key=value` | JSON/XML |
| 适用场景 | GET 请求、简单参数 | POST/PUT 请求、复杂对象 |
| 支持重复 | 是（`?id=1&id=2`）| 否 |

### 4.3 参数绑定原理

```java
// Spring 使用 HandlerMethodArgumentResolver 解析参数
// 常见实现：
// - PathVariableMethodArgumentResolver：解析 @PathVariable
// - RequestParamMethodArgumentResolver：解析 @RequestParam
// - RequestResponseBodyMethodProcessor：解析 @RequestBody
```

**源码流程（简化）**：
```java
// InvocableHandlerMethod.invokeForRequest()
public Object invokeForRequest(HttpServletRequest request, 
                               HttpServletResponse response,
                               Object... providedArgs) {
    // 1. 解析参数
    Object[] args = getMethodArgumentValues(request, response, providedArgs);
    
    // 2. 调用方法
    return doInvoke(args);
}

// 解析参数
private Object[] getMethodArgumentValues(HttpServletRequest request,
                                        HttpServletResponse response,
                                        Object... providedArgs) {
    MethodParameter[] parameters = getMethodParameters();
    Object[] args = new Object[parameters.length];
    
    for (int i = 0; i < parameters.length; i++) {
        // 使用对应的 Resolver 解析参数
        args[i] = resolvers.resolveArgument(parameters[i], request, response);
    }
    
    return args;
}
```

## 五、视图解析

### 5.1 视图解析器

```java
// 配置视图解析器（XML 方式）
<bean class="org.springframework.web.servlet.view.InternalResourceViewResolver">
    <property name="prefix" value="/WEB-INF/views/" />
    <property name="suffix" value=".jsp" />
</bean>

// 使用：返回 "order-detail"
// 解析为：/WEB-INF/views/order-detail.jsp
```

### 5.2 常用视图技术

| 视图技术 | 特点 |
|---------|------|
| **JSP** | 传统，功能强大 |
| **Thymeleaf** | 现代，自然语言模板 |
| **FreeMarker** | 轻量，性能高 |
| **JSON** | REST API（@ResponseBody）|

```java
// Thymeleaf 配置
@Configuration
public class WebConfig implements WebMvcConfigurer {
    
    @Bean
    public SpringTemplateEngine templateEngine() {
        SpringTemplateEngine engine = new SpringTemplateEngine();
        engine.setTemplateResolver(templateResolver());
        return engine;
    }
    
    @Bean
    public ThymeleafViewResolver viewResolver() {
        ThymeleafViewResolver resolver = new ThymeleafViewResolver();
        resolver.setTemplateEngine(templateEngine());
        return resolver;
    }
}
```

## 六、拦截器（Interceptor）

### 6.1 拦截器接口

```java
@Component
public class LoggingInterceptor implements HandlerInterceptor {
    
    // 在 Handler 执行前
    @Override
    public boolean preHandle(HttpServletRequest request, 
                             HttpServletResponse response, 
                             Object handler) {
        System.out.println("1. preHandle");
        return true;  // 继续执行
    }
    
    // 在 Handler 执行后，视图渲染前
    @Override
    public void postHandle(HttpServletRequest request, 
                           HttpServletResponse response, 
                           Object handler,
                           ModelAndView modelAndView) {
        System.out.println("3. postHandle");
    }
    
    // 在视图渲染后（异常也会执行）
    @Override
    public void afterCompletion(HttpServletRequest request, 
                                HttpServletResponse response, 
                                Object handler,
                                Exception ex) {
        System.out.println("5. afterCompletion");
    }
}
```

### 6.2 拦截器配置

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {
    
    @Autowired
    private LoggingInterceptor loggingInterceptor;
    
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(loggingInterceptor)
                .addPathPatterns("/api/**")   // 拦截路径
                .excludePathPatterns("/api/public/**");  // 排除路径
    }
}
```

### 6.3 拦截器执行顺序

```
请求 → preHandle 1 → preHandle 2 → Handler → postHandle 2 → postHandle 1 → afterCompletion 2 → afterCompletion 1 → 响应
```

**多个拦截器**：
```java
registry.addInterceptor(interceptor1).order(1);
registry.addInterceptor(interceptor2).order(2);
// 执行顺序：preHandle 1 → preHandle 2 → Handler → postHandle 2 → postHandle 1
```

## 七、拦截器 vs 过滤器

### 7.1 区别对比

| 特性 | 过滤器（Filter）| 拦截器（Interceptor）|
|------|-----------------|---------------------|
| **规范** | Servlet 规范 | Spring MVC 规范 |
| **作用范围** | 所有请求（包括静态资源）| 只拦截 MVC 请求 |
| **依赖** | 不依赖 Spring | 依赖 Spring |
| **执行时机** | DispatcherServlet 前 | DispatcherServlet 后 |
| **访问上下文** | 只能访问 Servlet API | 可访问 Spring 上下文 |

### 7.2 使用场景

```java
// 过滤器：全局处理（字符编码、CORS、XSS 防护）
@Component
public class EncodingFilter implements Filter {
    
    @Override
    public void doFilter(ServletRequest request, 
                          ServletResponse response, 
                          FilterChain chain) {
        request.setCharacterEncoding("UTF-8");
        response.setCharacterEncoding("UTF-8");
        chain.doFilter(request, response);
    }
}

// 拦截器：Spring MVC 特有逻辑（权限校验、日志记录）
@Component
public class AuthInterceptor implements HandlerInterceptor {
    
    @Override
    public boolean preHandle(HttpServletRequest request, 
                             HttpServletResponse response, 
                             Object handler) {
        // 校验登录状态
        if (request.getSession().getAttribute("user") == null) {
            response.sendRedirect("/login");
            return false;
        }
        return true;
    }
}
```

## 八、全局异常处理

### 8.1 @ControllerAdvice

```java
@ControllerAdvice
public class GlobalExceptionHandler {
    
    // 处理所有 Exception
    @ExceptionHandler(Exception.class)
    @ResponseBody
    public Result handleException(Exception e) {
        return Result.error(500, e.getMessage());
    }
    
    // 处理业务异常
    @ExceptionHandler(BusinessException.class)
    @ResponseBody
    public Result handleBusinessException(BusinessException e) {
        return Result.error(e.getCode(), e.getMessage());
    }
    
    // 处理参数校验异常
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseBody
    public Result handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldError().getDefaultMessage();
        return Result.error(400, message);
    }
}
```

### 8.2 响应状态

```java
@ControllerAdvice
public class GlobalExceptionHandler {
    
    @ExceptionHandler(NotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)  // 返回 404
    @ResponseBody
    public Result handleNotFound(NotFoundException e) {
        return Result.error(404, "资源不存在");
    }
}
```

## 九、文件上传

### 9.1 配置文件上传

```java
@Configuration
public class WebConfig implements WebMvcConfigurer {
    
    @Bean
    public MultipartResolver multipartResolver() {
        CommonsMultipartResolver resolver = new CommonsMultipartResolver();
        resolver.setDefaultEncoding("UTF-8");
        resolver.setMaxUploadSize(10 * 1024 * 1024);  // 10MB
        return resolver;
    }
}
```

### 9.2 处理文件上传

```java
@RestController
@RequestMapping("/api/files")
public class FileController {
    
    @PostMapping("/upload")
    public String upload(@RequestParam("file") MultipartFile file) {
        // 获取文件名
        String fileName = file.getOriginalFilename();
        
        // 获取文件大小
        long size = file.getSize();
        
        // 保存文件
        file.transferTo(new File("/path/to/save/" + fileName));
        
        return "上传成功";
    }
}
```

## 十、面试高频问题

### Q1：Spring MVC 的请求流程？

**答**：
1. 浏览器发送请求到 `DispatcherServlet`
2. `DispatcherServlet` 通过 `HandlerMapping` 找到 `Handler`
3. `HandlerAdapter` 适配调用 `Handler`（Controller 方法）
4. `Handler` 执行业务逻辑，返回 `ModelAndView`
5. `ViewResolver` 解析视图名称
6. `View` 渲染视图
7. 响应浏览器

### Q2：@RequestParam 和 @RequestBody 的区别？

**答**：
| 特性 | @RequestParam | @RequestBody |
|------|--------------|---------------|
| 数据位置 | URL 查询参数 | 请求体（Body）|
| 数据格式 | `key=value` | JSON/XML |
| 适用场景 | GET 请求、简单参数 | POST/PUT 请求、复杂对象 |

### Q3：拦截器和过滤器的区别？

**答**：
| 特性 | 过滤器 | 拦截器 |
|------|--------|----------|
| 规范 | Servlet 规范 | Spring MVC 规范 |
| 作用范围 | 所有请求 | 只拦截 MVC 请求 |
| 依赖 | 不依赖 Spring | 依赖 Spring |

### Q4：Spring MVC 的返回值处理？

**答**：
- 返回 `String`：视图名称
- 返回 `ModelAndView`：视图 + 模型
- 返回 `ResponseEntity`：完整响应（状态码、头、体）
- `@ResponseBody`：将返回值序列化为 JSON

### Q5：如何统一处理异常？

**答**：使用 `@ControllerAdvice` + `@ExceptionHandler`
```java
@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(Exception.class)
    @ResponseBody
    public Result handleException(Exception e) {
        return Result.error(500, e.getMessage());
    }
}
```

## 十一、总结

**Spring MVC 核心要点**：
- **DispatcherServlet**：前端控制器
- **请求流程**：DispatcherServlet → HandlerMapping → HandlerAdapter → Handler → ViewResolver → View
- **参数绑定**：`@PathVariable`、`@RequestParam`、`@RequestBody`
- **拦截器**：`preHandle` → `postHandle` → `afterCompletion`

**常用注解**：
- `@Controller` / `@RestController`
- `@RequestMapping` / `@GetMapping` / `@PostMapping`
- `@PathVariable` / `@RequestParam` / `@RequestBody`

**拦截器 vs 过滤器**：
- 过滤器：Servlet 规范，全局处理
- 拦截器：Spring MVC 规范，MVC 请求处理

**最佳实践**：
1. REST API 使用 `@RestController`
2. 统一异常处理 `@ControllerAdvice`
3. 合理使用拦截器（权限、日志）
4. 文件上传限制大小

---

**下一篇预告**：MySQL 索引与查询优化 —— B+ 树、索引类型、EXPLAIN 分析

**参考资料**：
- 《Spring 实战》- Craig Walls
- Spring 官方文档：https://docs.spring.io/spring-framework/docs/current/reference/html/web.html
- 《Spring MVC 学习指南》- 林信良
