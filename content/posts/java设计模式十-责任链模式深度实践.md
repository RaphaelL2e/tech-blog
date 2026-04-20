---
title: "Java设计模式（十）：责任链模式深度实践"
date: 2026-04-20T11:20:00+08:00
draft: false
categories: ["JAVA"]
tags: ["java", "设计模式", "责任链", "chain of responsibility"]
---

## 前言

前九篇文章我们覆盖了 4 种创建型模式和 5 种结构/行为型模式。今天继续 Java 设计模式系列，**责任链模式（Chain of Responsibility Pattern）** 是处理请求传递的利器，完美体现了"解耦"和"灵活组合"。

**核心思想**：将请求的发送者和接收者解耦，让多个对象都有机会处理请求，沿着责任链传递请求，直到有一个对象处理它为止。

<!--more-->

## 一、为什么需要责任链模式

### 1.1 if-else 的堆砌

```java
// ❌ 典型的审批系统：层层 if-else
public class ApprovalService {
    
    public String approve(LeaveRequest request) {
        // 1. 主管审批
        if (request.getDays() <= 3) {
            Manager manager = new Manager();
            return manager.approve(request) ? "主管审批通过" : "主管审批拒绝";
        }
        
        // 2. 部门经理审批
        if (request.getDays() <= 7) {
            DeptManager dm = new DeptManager();
            return dm.approve(request) ? "部门经理审批通过" : "部门经理审批拒绝";
        }
        
        // 3. 总监审批
        if (request.getDays() <= 14) {
            Director director = new Director();
            return director.approve(request) ? "总监审批通过" : "总监审批拒绝";
        }
        
        // 4. HR审批
        if (request.getDays() <= 30) {
            HR hr = new HR();
            return hr.approve(request) ? "HR审批通过" : "HR审批拒绝";
        }
        
        // 5. 总经理审批
        return new CEO().approve(request) ? "总经理审批通过" : "总经理审批拒绝";
    }
}
```

**问题**：
- 代码臃肿：所有审批逻辑堆在一个类
- 违反开闭原则：新增审批级别要改代码
- 难以复用：每个审批级别逻辑难以单独测试
- 扩展困难：不能动态组合审批流程

### 1.2 责任链模式的优势

```java
// ✅ 使用责任链模式
public abstract class Approver {
    
    protected Approver nextApprover;
    
    public void setNext(Approver approver) {
        this.nextApprover = approver;
    }
    
    public final String approve(LeaveRequest request) {
        // 尝试处理
        boolean approved = doApprove(request);
        
        if (approved) {
            return getApproverName() + "审批通过";
        }
        
        // 传递到下一个处理者
        if (nextApprover != null) {
            return nextApprover.approve(request);
        }
        
        return "无人能审批";
    }
    
    protected abstract boolean doApprove(LeaveRequest request);
    protected abstract String getApproverName();
}
```

**优点**：
- 消除 if-else
- 每个处理器独立
- 动态组合处理链
- 符合开闭原则

## 二、责任链模式的基本结构

### 2.1 核心角色

```
┌─────────────────────────────────────────────────────────────┐
│                 Handler (抽象处理者)                         │
├─────────────────────────────────────────────────────────────┤
│ + setNext(Handler)                                         │
│ + handleRequest(Request)  ← 处理或传递                       │
│ # successor: Handler                                        │
└─────────────────────────────────────────────────────────────┘
              △
              │
┌─────────────┴──────────────────────────────┐
▼                                          ▼
┌─────────────────┐                ┌─────────────────┐
│ ConcreteHandlerA│                │ ConcreteHandlerB│
├─────────────────┤                ├─────────────────┤
│ + handle()      │                │ + handle()      │
│   if can handle │                │   if can handle │
│     do it       │                │     do it       │
│   else          │                │   else          │
│     pass to next│                │     pass to next│
└─────────────────┘                └─────────────────┘
```

### 2.2 完整代码实现

```java
// 请求类
public class LeaveRequest {
    
    private String employeeName;
    private int days;
    private String reason;
    
    public LeaveRequest(String employeeName, int days, String reason) {
        this.employeeName = employeeName;
        this.days = days;
        this.reason = reason;
    }
    
    // getters
    public String getEmployeeName() { return employeeName; }
    public int getDays() { return days; }
    public String getReason() { return reason; }
}

// 审批结果
public class ApprovalResult {
    
    private boolean approved;
    private String approver;
    private String comment;
    
    public static ApprovalResult pass(String approver) {
        ApprovalResult r = new ApprovalResult();
        r.approved = true;
        r.approver = approver;
        return r;
    }
    
    public static ApprovalResult reject(String approver, String reason) {
        ApprovalResult r = new ApprovalResult();
        r.approved = false;
        r.approver = approver;
        r.comment = reason;
        return r;
    }
    
    public boolean isApproved() { return approved; }
    public String getApprover() { return approver; }
    public String getComment() { return comment; }
}

// 抽象处理者
public abstract class Approver {
    
    protected Approver successor;
    
    // 设置继任者
    public void setSuccessor(Approver successor) {
        this.successor = successor;
    }
    
    // 处理请求（模板方法模式）
    public final ApprovalResult handleRequest(LeaveRequest request) {
        // 1. 自己处理
        ApprovalResult result = doApprove(request);
        
        // 2. 如果自己处理不了，传递给下一个
        if (result == null && successor != null) {
            return successor.handleRequest(request);
        }
        
        // 3. 返回处理结果
        return result != null ? result : ApprovalResult.reject("系统", "无审批人");
    }
    
    // 抽象方法：具体审批逻辑
    protected abstract ApprovalResult doApprove(LeaveRequest request);
    
    // 具体处理者名称
    protected abstract String getApproverName();
}

// 主管
public class TeamLeader extends Approver {
    
    @Override
    protected ApprovalResult doApprove(LeaveRequest request) {
        // 主管只能批 3 天以内
        if (request.getDays() <= 3) {
            System.out.println("主管审批：同意 " + request.getEmployeeName() + 
                " 请假 " + request.getDays() + " 天");
            return ApprovalResult.pass(getApproverName());
        }
        return null;  // 不能处理，传递给下一个
    }
    
    @Override
    protected String getApproverName() {
        return "主管";
    }
}

// 部门经理
public class DepartmentManager extends Approver {
    
    @Override
    protected ApprovalResult doApprove(LeaveRequest request) {
        // 部门经理可以批 7 天以内
        if (request.getDays() <= 7) {
            System.out.println("部门经理审批：同意 " + request.getEmployeeName() + 
                " 请假 " + request.getDays() + " 天");
            return ApprovalResult.pass(getApproverName());
        }
        return null;
    }
    
    @Override
    protected String getApproverName() {
        return "部门经理";
    }
}

// 总监
public class Director extends Approver {
    
    @Override
    protected ApprovalResult doApprove(LeaveRequest request) {
        // 总监可以批 14 天以内
        if (request.getDays() <= 14) {
            System.out.println("总监审批：同意 " + request.getEmployeeName() + 
                " 请假 " + request.getDays() + " 天");
            return ApprovalResult.pass(getApproverName());
        }
        return null;
    }
    
    @Override
    protected String getApproverName() {
        return "总监";
    }
}

// HR
public class HRManager extends Approver {
    
    @Override
    protected ApprovalResult doApprove(LeaveRequest request) {
        // HR 可以批 30 天以内
        if (request.getDays() <= 30) {
            System.out.println("HR审批：同意 " + request.getEmployeeName() + 
                " 请假 " + request.getDays() + " 天");
            return ApprovalResult.pass(getApproverName());
        }
        return null;
    }
    
    @Override
    protected String getApproverName() {
        return "HR";
    }
}

// CEO
public class CEO extends Approver {
    
    @Override
    protected ApprovalResult doApprove(LeaveRequest request) {
        // CEO 可以批任何天数
        System.out.println("CEO审批：同意 " + request.getEmployeeName() + 
            " 请假 " + request.getDays() + " 天");
        return ApprovalResult.pass(getApproverName());
    }
    
    @Override
    protected String getApproverName() {
        return "CEO";
    }
}

// 测试
public class ChainTest {
    public static void main(String[] args) {
        // 创建审批链
        TeamLeader leader = new TeamLeader();
        DepartmentManager deptManager = new DepartmentManager();
        Director director = new Director();
        HRManager hr = new HRManager();
        CEO ceo = new CEO();
        
        // 设置责任链
        leader.setSuccessor(deptManager);
        deptManager.setSuccessor(director);
        director.setSuccessor(hr);
        hr.setSuccessor(ceo);
        
        // 测试不同的请假天数
        System.out.println("=== 请假 2 天 ===");
        ApprovalResult r1 = leader.handleRequest(
            new LeaveRequest("张三", 2, "探亲"));
        
        System.out.println("\n=== 请假 5 天 ===");
        ApprovalResult r2 = leader.handleRequest(
            new LeaveRequest("李四", 5, "旅游"));
        
        System.out.println("\n=== 请假 20 天 ===");
        ApprovalResult r3 = leader.handleRequest(
            new LeaveRequest("王五", 20, "出国"));
        
        System.out.println("\n=== 请假 60 天 ===");
        ApprovalResult r4 = leader.handleRequest(
            new LeaveRequest("赵六", 60, "陪产"));
    }
}
```

**输出**：
```
=== 请假 2 天 ===
主管审批：同意 张三 请假 2 天

=== 请假 5 天 ===
部门经理审批：同意 李四 请假 5 天

=== 请假 20 天 ===
HR审批：同意 王五 请假 20 天

=== 请假 60 天 ===
CEO审批：同意 赵六 请假 60 天
```

## 三、责任链的两种实现

### 3.1 纯责任链 vs 非纯责任链

```
┌─────────────────────────────────────────────────────────────┐
│                   纯责任链模式                                │
├─────────────────────────────────────────────────────────────┤
│ • 每个处理者要么处理请求，要么传递给下一个                     │
│ • 不能同时处理和传递                                         │
│ • 每个请求必须被处理                                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   非纯责任链模式                              │
├─────────────────────────────────────────────────────────────┤
│ • 处理者可以处理一部分，然后传递给下一个                       │
│ • 处理者可以不处理也不传递（直接返回）                         │
│ • 请求可能不被处理                                            │
│ • 更灵活，常用                                               │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 链表实现

```java
// 链表式责任链
public class HandlerChain {
    
    private Handler first;
    private Handler last;
    
    public void addHandler(Handler handler) {
        handler.setSuccessor(last);
        if (first == null) {
            first = handler;
        }
        last = handler;
    }
    
    public void handle(Object request) {
        if (first != null) {
            first.handle(request);
        }
    }
}

public abstract class Handler {
    
    protected Handler successor;
    
    public void setSuccessor(Handler successor) {
        this.successor = successor;
    }
    
    public abstract void handle(Object request);
}

// 使用
public class ChainDemo {
    public static void main(String[] args) {
        HandlerChain chain = new HandlerChain();
        chain.addHandler(new HandlerA());
        chain.addHandler(new HandlerB());
        chain.addHandler(new HandlerC());
        
        chain.handle("request");
    }
}
```

### 3.3 过滤器链实现

```java
// 过滤器链（类似 Servlet Filter）
public interface Filter {
    void doFilter(Request request, Response response, FilterChain chain);
}

public class FilterChain {
    
    private List<Filter> filters = new ArrayList<>();
    private int index = 0;
    
    public void addFilter(Filter filter) {
        filters.add(filter);
    }
    
    public void doFilter(Request request, Response response) {
        if (index >= filters.size()) {
            return;
        }
        
        Filter filter = filters.get(index++);
        filter.doFilter(request, response, this);
    }
}

// 使用
public class Main {
    public static void main(String[] args) {
        FilterChain chain = new FilterChain();
        chain.addFilter(new AuthFilter());
        chain.addFilter(new LogFilter());
        chain.addFilter(new EncodingFilter());
        
        Request request = new Request();
        Response response = new Response();
        
        chain.doFilter(request, response);
    }
}
```

## 四、实战案例

### 4.1 敏感词过滤系统

```java
// 敏感词过滤器
public abstract class SensitiveWordFilter {
    
    protected SensitiveWordFilter next;
    
    public void setNext(SensitiveWordFilter next) {
        this.next = next;
    }
    
    // 处理文本
    public final String filter(String text) {
        // 1. 先过滤
        String result = doFilter(text);
        
        // 2. 传递给下一个
        if (next != null && result != null) {
            return next.filter(result);
        }
        
        return result;
    }
    
    protected abstract String doFilter(String text);
}

// 政治敏感词过滤
public class PoliticalFilter extends SensitiveWordFilter {
    
    private static final Set<String> WORDS = new HashSet<>(
        Arrays.asList("敏感词1", "敏感词2", "政治")
    );
    
    @Override
    protected String doFilter(String text) {
        String result = text;
        for (String word : WORDS) {
            result = result.replace(word, "***");
        }
        System.out.println("政治敏感词过滤完成");
        return result;
    }
}

// 广告过滤
public class AdFilter extends SensitiveWordFilter {
    
    private static final Set<String> WORDS = new HashSet<>(
        Arrays.asList("广告", "推销", "微商", "加V")
    );
    
    @Override
    protected String doFilter(String text) {
        String result = text;
        for (String word : WORDS) {
            result = result.replace(word, "[广告]");
        }
        System.out.println("广告过滤完成");
        return result;
    }
}

// 色情过滤
public class PornFilter extends SensitiveWordFilter {
    
    private static final Set<String> WORDS = new HashSet<>(
        Arrays.asList("色情", "赌博", "毒品")
    );
    
    @Override
    protected String doFilter(String text) {
        String result = text;
        for (String word : WORDS) {
            result = result.replace(word, "***");
        }
        System.out.println("色情过滤完成");
        return result;
    }
}

// 侮辱性语言过滤
public class AbuseFilter extends SensitiveWordFilter {
    
    private static final Set<String> WORDS = new HashSet<>(
        Arrays.asList("傻子", "白痴", "智障")
    );
    
    @Override
    protected String doFilter(String text) {
        String result = text;
        for (String word : WORDS) {
            result = result.replace(word, "***");
        }
        System.out.println("侮辱性语言过滤完成");
        return result;
    }
}

// 使用
public class FilterTest {
    public static void main(String[] args) {
        // 创建过滤器链
        PoliticalFilter political = new PoliticalFilter();
        AdFilter ad = new AdFilter();
        PornFilter porn = new PornFilter();
        AbuseFilter abuse = new AbuseFilter();
        
        // 设置责任链
        political.setNext(ad);
        ad.setNext(porn);
        porn.setNext(abuse);
        
        // 测试
        String text = "这是一段测试广告文本，包含政治敏感词和政治，还有微商推销";
        String result = political.filter(text);
        System.out.println("最终结果：" + result);
    }
}
```

### 4.2 统一日志记录

```java
// 日志级别
public enum LogLevel {
    DEBUG, INFO, WARN, ERROR
}

// 日志记录器
public abstract class Logger {
    
    protected Logger nextLogger;
    protected LogLevel level;
    
    public void setNext(Logger next) {
        this.nextLogger = next;
    }
    
    public void log(LogLevel level, String message) {
        // 如果当前级别能处理
        if (canHandle(level)) {
            write(message);
        }
        
        // 传递给下一个
        if (nextLogger != null) {
            nextLogger.log(level, message);
        }
    }
    
    protected abstract boolean canHandle(LogLevel level);
    protected abstract void write(String message);
}

// 控制台日志
public class ConsoleLogger extends Logger {
    
    public ConsoleLogger(LogLevel level) {
        this.level = level;
    }
    
    @Override
    protected boolean canHandle(LogLevel level) {
        return level.ordinal() >= this.level.ordinal();
    }
    
    @Override
    protected void write(String message) {
        System.out.println("[控制台] " + message);
    }
}

// 文件日志
public class FileLogger extends Logger {
    
    public FileLogger(LogLevel level) {
        this.level = level;
    }
    
    @Override
    protected boolean canHandle(LogLevel level) {
        return level.ordinal() >= this.level.ordinal();
    }
    
    @Override
    protected void write(String message) {
        System.out.println("[文件] " + message);
    }
}

// 邮件日志
public class EmailLogger extends Logger {
    
    public EmailLogger(LogLevel level) {
        this.level = level;
    }
    
    @Override
    protected boolean canHandle(LogLevel level) {
        return level == LogLevel.ERROR;  // 只有 ERROR 才发邮件
    }
    
    @Override
    protected void write(String message) {
        System.out.println("[邮件] 发送错误邮件: " + message);
    }
}

// 测试
public class LoggerTest {
    public static void main(String[] args) {
        // 创建日志链：控制台 -> 文件 -> 邮件
        Logger console = new ConsoleLogger(LogLevel.DEBUG);
        Logger file = new FileLogger(LogLevel.INFO);
        Logger email = new EmailLogger(LogLevel.ERROR);
        
        console.setNext(file);
        file.setNext(email);
        
        // 测试
        console.log(LogLevel.DEBUG, "调试信息");
        console.log(LogLevel.INFO, "普通信息");
        console.log(LogLevel.WARN, "警告信息");
        console.log(LogLevel.ERROR, "错误信息");
    }
}
```

### 4.3 请求拦截器

```java
// HTTP 请求包装
public class HttpRequest {
    private String url;
    private Map<String, String> headers = new HashMap<>();
    private String body;
    
    public HttpRequest(String url) {
        this.url = url;
    }
    
    public String getUrl() { return url; }
    public Map<String, String> getHeaders() { return headers; }
    public String getBody() { return body; }
    
    public void addHeader(String key, String value) {
        headers.put(key, value);
    }
}

// HTTP 响应
public class HttpResponse {
    private int statusCode;
    private String body;
    
    public void setStatusCode(int code) { this.statusCode = code; }
    public void setBody(String body) { this.body = body; }
    public int getStatusCode() { return statusCode; }
    public String getBody() { return body; }
}

// 拦截器
public abstract class Interceptor {
    
    protected Interceptor next;
    
    public void setNext(Interceptor next) {
        this.next = next;
    }
    
    public final HttpResponse intercept(HttpRequest request) {
        // 1. 前置处理
        preHandle(request);
        
        // 2. 执行下一个
        HttpResponse response;
        if (next != null) {
            response = next.intercept(request);
        } else {
            response = doRequest(request);
        }
        
        // 3. 后置处理
        postHandle(request, response);
        
        return response;
    }
    
    protected abstract void preHandle(HttpRequest request);
    protected abstract void postHandle(HttpRequest request, HttpResponse response);
    protected abstract HttpResponse doRequest(HttpRequest request);
}

// 认证拦截器
public class AuthInterceptor extends Interceptor {
    
    @Override
    protected void preHandle(HttpRequest request) {
        String token = request.getHeaders().get("Authorization");
        if (token == null || !token.startsWith("Bearer ")) {
            throw new SecurityException("未授权");
        }
        System.out.println("认证通过");
    }
    
    @Override
    protected void postHandle(HttpRequest request, HttpResponse response) {
        response.addHeader("X-Auth", "verified");
    }
    
    @Override
    protected HttpResponse doRequest(HttpRequest request) {
        return null;
    }
}

// 日志拦截器
public class LogInterceptor extends Interceptor {
    
    private long startTime;
    
    @Override
    protected void preHandle(HttpRequest request) {
        startTime = System.currentTimeMillis();
        System.out.println("开始处理请求: " + request.getUrl());
    }
    
    @Override
    protected void postHandle(HttpRequest request, HttpResponse response) {
        long duration = System.currentTimeMillis() - startTime;
        System.out.println("请求处理完成，耗时: " + duration + "ms");
    }
    
    @Override
    protected HttpResponse doRequest(HttpRequest request) {
        return null;
    }
}
```

## 五、Spring 中的责任链

### 5.1 FilterChain

```java
// Spring Security 的过滤器链
// WebSecurityConfigurerAdapter 配置多个过滤器

@Configuration
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .addFilterBefore(new CsrfFilter(), BasicAuthenticationFilter.class)
            .addFilterBefore(new SessionFilter(), BasicAuthenticationFilter.class)
            .addFilterBefore(new AuthFilter(), BasicAuthenticationFilter.class)
            .addFilterBefore(new LoggingFilter(), BasicAuthenticationFilter.class);
    }
}

// 自定义过滤器链
@Component
public class MyFilterChain {
    
    private List<MyFilter> filters = Arrays.asList(
        new AuthFilter(),
        new RateLimitFilter(),
        new ValidateFilter(),
        new LogFilter()
    );
    
    public void doFilter(ServletRequest request, ServletResponse response) {
        doFilter(request, response, 0);
    }
    
    private void doFilter(ServletRequest request, ServletResponse response, int index) {
        if (index >= filters.size()) {
            // 执行实际的 Servlet
            return;
        }
        
        MyFilter filter = filters.get(index);
        filter.doFilter(request, response, () -> doFilter(request, response, index + 1));
    }
}
```

### 5.2 HandlerInterceptor

```java
// Spring MVC 的拦截器
public class LoggingInterceptor implements HandlerInterceptor {
    
    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, 
            Object handler) {
        System.out.println("前置处理");
        return true;  // 返回 true 继续执行，返回 false 终止
    }
    
    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response,
            Object handler, ModelAndView modelAndView) {
        System.out.println("后置处理");
    }
    
    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
            Object handler, Exception ex) {
        System.out.println("完成处理");
    }
}

// 配置拦截器
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {
    
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new LoggingInterceptor())
            .addPathPatterns("/api/**")
            .excludePathPatterns("/api/public/**");
    }
}
```

### 5.3 MyBatis 插件机制

```java
// MyBatis 插件就是责任链模式
@Intercepts({
    @Signature(type = Executor.class, method = "query", 
        args = {MappedStatement.class, Object.class, RowBounds.class, 
                ResultHandler.class}),
    @Signature(type = Executor.class, method = "update", 
        args = {MappedStatement.class, Object.class})
})
public class MyInterceptor implements Interceptor {
    
    @Override
    public Object intercept(Invocation invocation) throws Throwable {
        // 前置处理
        System.out.println("SQL 执行前...");
        
        // 执行下一个插件
        Object result = invocation.proceed();
        
        // 后置处理
        System.out.println("SQL 执行后...");
        
        return result;
    }
}

// 配置多个插件形成责任链
@Configuration
public class MyBatisConfig {
    
    @Bean
    public Interceptor[] plugins() {
        return new Interceptor[]{
            new MyInterceptor(),
            new PerformanceInterceptor(),
            new CacheInterceptor()
        };
    }
}
```

## 六、责任链 vs 其他模式

### 6.1 对比

| 维度 | 责任链 | 策略模式 | 装饰器模式 |
|------|--------|---------|-----------|
| **目的** | 请求传递 | 算法替换 | 动态增强 |
| **调用方式** | 链式传递 | 上下文选择 | 层层包装 |
| **处理方式** | 一个处理或传递 | 完全替换 | 增强后传递 |
| **顺序** | 固定/可配置 | 无顺序 | 外层先执行 |

### 6.2 选择指南

```
┌─────────────────────────────────────────────────────────────┐
│                        选择指南                              │
├─────────────────────────────────────────────────────────────┤
│ • 请求需要多个对象处理 → 责任链                               │
│ • 需要运行时选择算法 → 策略模式                               │
│ • 需要动态增强功能 → 装饰器模式                              │
│ • 需要组合多个功能 → 可以组合使用                            │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 组合使用

```java
// 责任链 + 策略模式
public class SmartChain {
    
    private List<Handler> handlers = new ArrayList<>();
    private Strategy strategy;
    
    public void addHandler(Handler handler) {
        handlers.add(handler);
    }
    
    public void setStrategy(Strategy strategy) {
        this.strategy = strategy;
    }
    
    public void handle(Request request) {
        // 使用策略选择处理器
        Handler handler = strategy.select(handlers, request);
        if (handler != null) {
            handler.handle(request);
        }
    }
}
```

## 七、责任链的优缺点

### 7.1 优点

1. **解耦发送者和接收者**
2. **简化对象**：对象不需要知道链的结构
3. **增强灵活性**：可以动态改变链的顺序
4. **单一职责**：每个处理者只负责自己的逻辑
5. **开闭原则**：新增处理者不需要修改现有代码

### 7.2 缺点

1. **性能影响**：请求可能遍历整个链
2. **调试困难**：链长时难以追踪
3. **请求可能无人处理**：链不完整时

### 7.3 最佳实践

```java
// 1. 设置合理的链长度
// 一般不超过 10 个处理器

// 2. 防止链断裂
public void buildChain() {
    Handler handler1 = new HandlerA();
    Handler handler2 = new HandlerB();
    Handler handler3 = new HandlerC();
    
    handler1.setNext(handler2);
    handler2.setNext(handler3);
    // 确保链完整
}

// 3. 异步处理优化性能
public abstract class AsyncHandler extends Handler {
    
    private ExecutorService executor = Executors.newFixedThreadPool(10);
    
    @Override
    public void handleAsync(Request request) {
        executor.submit(() -> handle(request));
    }
}

// 4. 使用配置管理链
@Configuration
public class ChainConfig {
    
    @Bean
    public Handler approvalChain() {
        return new ChainBuilder()
            .add(new TeamLeader())
            .add(new DeptManager())
            .add(new Director())
            .add(new CEO())
            .build();
    }
}
```

## 八、源码中的应用

### 8.1 JDK - Logger

```java
// JDK Logging 的责任链
public abstract class Handler {
    protected Handler next;
    
    public abstract void publish(LogRecord record);
    public abstract void flush();
    public abstract void close();
    
    // 责任链传递
    protected void publishNext(LogRecord record) {
        if (next != null) {
            next.publish(record);
        }
    }
}

// ConsoleHandler -> StreamHandler -> SocketHandler
```

### 8.2 Spring Security

```java
// Spring Security FilterChain
public class FilterChainProxy {
    
    private List<SecurityFilterChain> chains;
    
    public void doFilter(ServletRequest request, ServletResponse response) {
        doFilter(request, response, 0);
    }
    
    private void doFilter(ServletRequest request, ServletResponse response, int position) {
        if (position >= chains.size()) {
            return;
        }
        
        SecurityFilterChain chain = chains.get(position);
        chain.doFilter(request, response, () -> 
            doFilter(request, response, position + 1));
    }
}
```

### 8.3 Tomcat Valve

```java
// Tomcat 的 Valve 机制
public interface Valve {
    void invoke(Request request, Response response, ValveContext context);
    ValveContext getNext();
    void setNext(Valve valve);
}

public interface ValveContext {
    void invokeNext(Request request, Response response);
}

// Pipeline 包含多个 Valve
public class StandardPipeline {
    protected Valve basic;
    protected Container container;
    
    public void invoke(Request request, Response response) {
        // 从第一个 Valve 开始
        new StandardContextValveContext().invokeNext(request, response);
    }
}
```

## 九、面试常见问题

### Q1：责任链模式和 if-else 的区别？

| 维度 | if-else | 责任链 |
|------|---------|--------|
| 扩展性 | 改代码 | 新增处理类 |
| 复用性 | 差 | 好 |
| 顺序控制 | 硬编码 | 动态配置 |
| 测试性 | 困难 | 单元测试 |

### Q2：责任链有哪些变体？

1. **纯责任链**：要么处理，要么传递
2. **非纯责任链**：可以处理一部分然后传递
3. **混合链**：结合多种模式
4. **并行链**：多个处理器并行处理

### Q3：如何防止责任链过长？

1. 设置链的最大长度
2. 使用计数器限制
3. 合理的职责划分
4. 监控和告警

### Q4：请求没人处理怎么办？

1. 在链尾添加默认处理器
2. 抛异常
3. 返回空结果

## 十、总结

### 核心要点

```
责任链模式：
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Request ──→ Handler1 ──→ Handler2 ──→ Handler3 ──→ ...  │
│                    │                │                │       │
│                  处理              处理              处理   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

关键点：
• 发送者和接收者解耦
• 链式传递
• 可动态配置
• 单一职责
```

### 与其他模式对比

| 模式 | 目的 | 关系 |
|------|------|------|
| 策略模式 | 替换算法 | 可组合 |
| 装饰器模式 | 增强功能 | 可组合 |
| 命令模式 | 封装请求 | 可组合 |

## 结语

责任链模式是处理请求传递的利器，特别适合审批流程、过滤器链、拦截器等场景。掌握责任链模式，能够设计出更解耦、更易扩展的系统。

**下期预告**：命令模式（Command Pattern）

> 记住：**请求沿着链走，直到有人处理**。
