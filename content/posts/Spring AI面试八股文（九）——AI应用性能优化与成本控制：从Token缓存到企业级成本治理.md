---
title: "Spring AI面试八股文（九）——AI应用性能优化与成本控制：从Token缓存到企业级成本治理"
date: 2026-07-18T10:00:00+08:00
draft: false
categories: ["Spring AI"]
tags: ["Spring AI", "性能优化", "成本控制", "Token缓存", "限流降级", "成本治理", "面试"]
---

> 面试高频问题：AI应用如何降低Token消耗成本？Spring AI有哪些内置缓存机制？如何实现多租户场景下的AI成本分摊？LLM调用失败时如何做熔断降级？在大模型API按Token计费的商业模式下，性能优化与成本控制是AI工程化的核心命题。本文聚焦Spring AI侧的优化策略，从Token缓存、Prompt压缩、限流降级、成本监控到多租户成本归属，构建完整的AI应用成本治理体系。

<!-- more -->

## 一、为什么AI应用性能优化≠传统性能优化

传统的后端性能优化关注点通常是CPU利用率、数据库查询延迟、内存分配效率。对于LLM驱动的应用，这些指标依然重要，但**核心瓶颈已经转移到了Token消耗和网络I/O**：

- **Token是直接成本**：GPT-4o的输入$5/1M Token，输出$15/1M Token，每一次无效的重复调用都是在烧钱。
- **LLM调用延迟远高于普通API**：一次GPT-4o调用端到端延迟通常在1\~3秒，是普通REST API的100\~1000倍。
- **Provider限流是硬墙**：OpenAI的RPM（Requests Per Minute）和TPM（Tokens Per Minute）限制不是性能问题，是商业约束，超限直接返回429。

所以AI应用性能优化本质上是一套**以Token成本为中心、以可靠性为底座**的系统工程。

---

## 二、Token缓存：从重复调用中榨取免费收益

### 2.1 为什么LLM缓存如此重要

大模型对相同或语义相似的输入往往产生相同或高度相似的输出。比如用户在客服场景中反复询问相似问题、文档总结应用中多次处理相同文档片段。这类场景的**缓存命中率可以高达30%\~60%**，直接转化为成本节省。

传统的HTTP缓存（ETag、Last-Modified）对LLM场景无效，因为：
- 相同Prompt的每次API调用都会产生不同的Token序列（采样随机性）
- 语义相似但字面不同的Prompt也可能返回等价结果

Spring AI提供了**多层次Token缓存机制**，专门解决以上问题。

### 2.2 StringCache —— 输入Prompt的精确缓存

`StringCache`是Spring AI最早提供的缓存接口，**基于完整的Prompt字符串进行精确匹配**：

```java
public interface StringCache {
    String get(String prompt);           // 命中则返回缓存的完整回复
    void put(String prompt, String response);  // 存入缓存
}
```

使用方式：

```java
@Bean
public ChatClient chatClient(ChatClient.Builder builder) {
    return builder
        .defaultSystem("你是一个金融顾问")
        .build();
}

// 在application.yml中配置
spring:
  ai:
    openai:
      chat:
        options:
          model: gpt-4o
    cache:
      enabled: true
      provider: simple  # simple | caffeine | redis
```

Spring AI默认提供三种缓存Provider：
- **SimpleCache**：内存Map实现，适合单实例开发环境
- **CaffeineCache**：高性能内存缓存，支持TTL和容量淘汰策略，生产推荐
- **RedisCache**：分布式缓存，适合多实例部署场景，跨实例共享缓存

```java
@Bean
public Cache<String, String> caffeineCache() {
    return Caffeine.newBuilder()
        .expireAfterWrite(Duration.ofMinutes(30))  // 写后30分钟过期
        .maximumSize(10_000)                        // 最多缓存1万条
        .recordStats()                               // 开启统计
        .build();
}
```

**面试追问**：精确缓存的问题在于"相同Prompt"的判定太严格。实际场景中用户问"如何开户"和"开户怎么办理"语义等价但字面不同，精确缓存无法命中。

### 2.3 PromptHashCache —— 基于Hash的模糊缓存

`PromptHashCache`解决了精确匹配过于严格的问题。它的核心思路是：

1. 对输入Prompt计算MD5/SHA-256哈希值
2. 用哈希值作为缓存Key
3. **只要哈希相同（Prompt内容完全相同），就认为可以复用**

```java
// Spring AI内部实现逻辑（简化）
public class PromptHashCache {
    private final Cache<String, String> innerCache;
    
    public String cacheablePrompt(String prompt) {
        String hash = Hashing.sha256()
            .hashString(prompt, StandardCharsets.UTF_8)
            .toString();
        
        String cached = innerCache.getIfPresent(hash);
        if (cached != null) {
            return cached;  // 直接返回，不调LLM
        }
        return prompt;  // 未命中，继续正常流程
    }
}
```

**使用配置**：

```yaml
spring:
  ai:
    cache:
      enabled: true
      type: prompt-hash  # 启用Hash缓存
      prompt-hash:
        ttl-minutes: 60
```

**注意**：Hash缓存有隐患——如果Prompt中包含动态变量（如用户ID、时间戳），每次请求的哈希值都不同，缓存完全失效。所以Hash缓存**适用于Prompt模板稳定、变量在变量槽中传入的场景**。

### 2.4 Embedding缓存 —— 向量检索场景的加速

在RAG场景中，同一个文档片段会被反复嵌入（embedding）计算，消耗大量Token和计算资源：

```java
@Bean
public EmbeddingClient embeddingClient(EmbeddingModel embeddingModel) {
    // Embedding模型同样支持缓存
    return new WeaviateEmbeddingModel(
        embeddingModel,
        CacheMode.ENABLED,  // 启用嵌入缓存
        Duration.ofDays(7)
    );
}
```

在`VectorStore`操作中，Spring Data MongoDB/Pgvector等实现也支持对**已嵌入的文档**做去重检查：

```java
// 检查文档是否已存在（基于内容Hash）
boolean exists = vectorStore.isPresent(document.getId());
if (!exists) {
    vectorStore.add(List.of(document));
}
```

---

## 三、Prompt压缩与上下文管理：少说废话，多省Token

### 3.1 静态压缩：让Prompt"减肥"

**删除冗余表述**是最直接的成本控制手段：

```
❌ 不推荐：
"请注意，你现在的任务是根据我提供的上下文信息来回答用户的问题。
上下文信息包含在下面的XML标签<context></context>之间，请仔细阅读后回答。"

✅ 推荐：
"<context>{{context}}</context>\n用户问题：{{question}}"
```

**面试重点**：Prompt的System Prompt部分也会消耗输入Token。大型System Prompt（如上百行的角色定义）每次调用都全额计费。解决方案是：
- 将角色定义抽取为**独立Prompt片段**，在需要时动态组装
- 使用`ChatMemory`等Spring AI组件管理对话历史，自动截断超出上下文的旧消息

### 3.2 动态上下文压缩：智能截断对话历史

对话历史是Token消耗的主要来源之一。Spring AI的`ChatMemory`接口提供了多种实现策略：

```java
// 使用MessageChatMemoryAdvisor + 滑动窗口策略
MessageChatMemoryAdvisor chatMemory = MessageChatMemoryAdvisor
    .builder(InMemoryChatMemory.create())
    .windowSize(10)  // 只保留最近10条消息
    .build();

// 将Advisor附加到ChatClient
ChatClient chatClient = ChatClient.builder(deductiveOperator)
    .defaultAdvisors(chatMemory)
    .build();

String response = chatClient.prompt()
    .user(userMessage)
    .call()
    .content();
```

`windowSize`策略有几种常见实现：

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `windowSize` | 保留最近N条消息，超出则丢弃最旧的 | 长对话、固定Token预算 |
| `tokenWindow` | 按Token数量而非消息数管理上下文 | 精确控制Token消耗 |
| `summaryWindow` | 用LLM将旧消息压缩为摘要，再保留 | 超长对话但需要保留历史语义 |

```java
// Token窗口策略（按Token数管理上下文）
TokenWindowChatMemoryAdvisor tokenMemory = TokenWindowChatMemoryAdvisor
    .builder(InMemoryChatMemory.create())
    .maxTokens(8000)  // 总Token数不超过8000
    .build();
```

**面试加分点**：实际生产中推荐使用`SummaryMessageChatMemoryAdvisor`，它会用一个小模型（如GPT-3.5-Turbo）将对话历史压缩为语义摘要，保留核心信息同时大幅减少Token消耗。

### 3.3 RAG场景的上下文精简

RAG（检索增强生成）是最容易产生Token浪费的场景——将大量检索到的文档一股脑塞入Prompt，检索质量不高时尤其浪费：

```java
// 优化方案1：限制每条检索结果的文本长度
List<Document> docs = vectorStore.similaritySearch(
    new SimilaritySearchRequest(query, 10)  // 最多10条
        .withTopK(3)                        // 每条最多取前3个chunk
        .withFilterExpression(filter)
);

// 优化方案2：自定义文档截断
docs.forEach(doc -> {
    String text = doc.getText();
    if (text.length() > 2000) {  // 单条不超过2000字符
        doc.setText(text.substring(0, 2000));
    }
});

// 优化方案3：使用Mixtral等支持更长上下文的模型处理大量上下文
ChatOptions options = ChatOptions.builder()
    .withModel("gpt-4o-32k")  // 32k上下文窗口
    .withTemperature(0.3)     // 降低随机性，提高缓存命中率
    .build();
```

**面试加分项**：使用**Contextual Compression**（上下文压缩）技术，用一个轻量级模型（如GPT-3.5-Turbo）从检索到的文档中提取与问题最相关的片段，再送入大模型。这是RAG精炼的标准工业实践。

---

## 四、限流降级：保护系统的最后一道防线

### 4.1 为什么AI限流不能只用普通限流器

普通的API限流器（如Guava RateLimiter）关注的是QPS（Queries Per Second），但LLM Provider的限流是**二维的**：

| 维度 | 说明 | 典型值（OpenAI） |
|------|------|----------------|
| RPM | 每分钟请求数 | 500（GPT-4o） |
| TPM | 每分钟Token数 | 120,000（GPT-4o） |

Token维度的限流（RPM满足但TPM超限）普通限流器检测不到，需要**专门Token感知的限流器**。

### 4.2 Resilience4j + Spring AI集成

Spring AI推荐使用Resilience4j作为AI调用的容错层：

```java
// 方式1：使用@Retryable重试（推荐用于限流429响应）
@Bean
public ChatClient chatClient(ChatClient.Builder builder) {
    return builder
        .defaultAdvisors(
            new RetryChatAdvisor(
                Retry.builder()
                    .maxAttempts(3)
                    .intervalFunction(IntervalFunction.ofExponentialBackoff(
                        Duration.ofSeconds(2), 2.0))
                    .retryExceptions(
                        RateLimitException.class,   // 429
                        ResourceNotFoundException.class)  // 429
                    .build()
            )
        )
        .build();
}

// 方式2：使用@CircuitBreaker防止级联故障
@CircuitBreaker(
    name = "aiService",
    fallbackMethod = "fallbackResponse",
    slidingWindowType = SlidingWindowType.COUNT_BASED,
    slidingWindowSize = 10,
    failureRateThreshold = 50,
    waitDurationInOpenState = Duration.ofSeconds(30)
)
public String callAI(String prompt) {
    return chatClient.prompt()
        .user(prompt)
        .call()
        .content();
}

// 降级方案
public String fallbackResponse(String prompt, Exception e) {
    log.warn("AI服务不可用，降级返回: {}", e.getMessage());
    return "当前服务繁忙，请稍后重试。";
}
```

**面试核心**：限流处理的正确策略顺序是：
1. **重试**（429 / 503）：指数退避后重试，适用于瞬时限流
2. **降级**（持续超时 / 熔断打开）：返回降级结果，保证服务可用
3. **限流**（主动控制）：在调用侧控制QPS，避免触发Provider限流

### 4.3 多模型降级：最实用的企业级降级策略

企业级AI应用通常配置**多个模型作为降级链**，当主模型不可用或超时时自动切换：

```java
@Configuration
public class MultiModelFallbackConfig {
    
    @Bean
    public ChatClient chatClient(
            OpenAiApi openAiApi,
            AzureOpenAiApi azureOpenAiApi) {
        
        // 优先级：GPT-4o → GPT-4o-mini → Azure GPT-4
        var primary = new OpenAiChatModel(openAiApi, 
            ChatOptions.builder().withModel("gpt-4o").build());
        var secondary = new OpenAiChatModel(openAiApi,
            ChatOptions.builder().withModel("gpt-4o-mini").build());
        var tertiary = new AzureOpenAiChatModel(azureOpenAiApi);
        
        // 使用Spring AI的模型选择器实现自动降级
        return ChatClient.builder(new SelectiveChatModel(
            List.of(primary, secondary, tertiary),
            new LatencyBasedSelector()  // 按延迟选择
        )).build();
    }
}
```

---

## 五、成本监控与多租户成本治理

### 5.1 Token消耗的监控体系

没有监控的成本控制是盲目的。Spring AI与Micrometer/Metrics完美集成：

```java
// 方式1：自动Metrics（开箱即用）
// spring.ai.metrics.enabled=true 时自动暴露以下指标：
// - ai.chat.tokens.total        (counter, label: model, prompt_type)
// - ai.chat.latency.seconds      (timer, label: model)
// - ai.chat.requests.total       (counter, label: model, status)
// - ai.chat.errors.total          (counter, label: model, error_type)
// - ai.cache.hits.total           (counter)
// - ai.cache.misses.total        (counter)

// 方式2：自定义Token计数器
@Aspect
@Component
public class TokenCostAspect {
    
    @Autowired
    private MeterRegistry meterRegistry;
    
    @Around("execution(* org.springframework.ai.chat.ChatModel.call(..))")
    public Object trackTokenCost(ProceedingJoinPoint pjp) throws Throwable {
        TokenUsage usage = null;
        long start = System.currentTimeMillis();
        
        try {
            Object result = pjp.proceed();
            
            // 从响应中提取Token使用量
            if (result instanceof ChatResponse resp) {
                usage = resp.getMetadata().getUsage();
                meterRegistry.counter("ai.tokens.input", 
                    "model", getModelName()).increment(usage.getPromptTokens());
                meterRegistry.counter("ai.tokens.output",
                    "model", getModelName()).increment(usage.getCompletionTokens());
                
                // 成本计算
                double cost = calculateCost(usage);
                meterRegistry.gauge("ai.cost.total", cost);
            }
            return result;
        } finally {
            long latency = System.currentTimeMillis() - start;
            meterRegistry.timer("ai.latency", "model", getModelName())
                .record(Duration.ofMillis(latency));
        }
    }
    
    private double calculateCost(TokenUsage usage) {
        // GPT-4o定价: $5/1M输入, $15/1M输出
        double inputCost = usage.getPromptTokens() * 5.0 / 1_000_000;
        double outputCost = usage.getCompletionTokens() * 15.0 / 1_000_000;
        return inputCost + outputCost;
    }
}
```

配合Prometheus + Grafana，可以搭建**实时Token消耗大屏**，展示：
- 当前QPS和Token速率
- 缓存命中率
- 按用户/租户的Token消耗排名
- 成本趋势与预算告警

### 5.2 多租户成本分摊

SaaS/多租户场景下，精确追踪每个租户的AI成本至关重要：

```java
// 方式1：基于请求上下文的成本追踪
@Service
public class TenantAwareAIService {
    
    @Autowired
    private TokenUsageService tokenUsageService;
    
    public String answer(String tenantId, String userId, String question) {
        String response = chatClient.prompt()
            .user(question)
            .advisors(new TenantContextAdvisor(tenantId))  // 注入租户上下文
            .call()
            .content();
        
        // 提取并记录Token使用量（从响应metadata）
        // 实际生产中通过拦截器自动完成
        return response;
    }
}

// 方式2：按租户维度的成本报表
@RestController
public class CostReportController {
    
    @GetMapping("/api/admin/costs/by-tenant")
    public List<TenantCost> getTenantCosts(
            @RequestParam(defaultValue = "30") int days) {
        
        return tokenUsageService.aggregateByTenant(
            Duration.ofDays(days)
        ).stream()
         .map(record -> new TenantCost(
             record.getTenantId(),
             record.getTotalInputTokens(),
             record.getTotalOutputTokens(),
             calculateCost(record)
         ))
         .sorted(Comparator.comparing(TenantCost::getCost).reversed())
         .collect(Collectors.toList());
    }
}
```

**面试加分项**：成本归因的粒度要足够细——不仅要按租户分摊，还要按**调用场景**（客服、文档总结、代码审查等）分摊，便于定位异常消耗的来源。

### 5.3 预算告警与自动熔断

```java
// 使用Spring Boot Actuator + 自定义BudgetAlertService
@Component
public class BudgetAlertService {
    
    @Autowired
    private MeterRegistry meterRegistry;
    @Autowired
    private AlertNotificationService alertService;
    
    @EventListener
    public void onTokenUsage(TokenUsageEvent event) {
        double dailyCost = meterRegistry.get("ai.cost.daily").gauge().value();
        double monthlyBudget = getMonthlyBudget(event.getTenantId());
        
        double usagePercent = dailyCost / monthlyBudget * 100;
        
        if (usagePercent >= 100) {
            alertService.sendCritical(event.getTenantId(), 
                "月度AI预算已耗尽，已暂停AI服务");
            disableAIService(event.getTenantId());  // 自动暂停服务
        } else if (usagePercent >= 80) {
            alertService.sendWarning(event.getTenantId(),
                String.format("月度AI预算使用已达%.0f%%", usagePercent));
        }
    }
}
```

---

## 六、并发优化：批量处理与异步调用

### 6.1 批量请求合并

多个用户请求相同问题时，可以**合并为一次批量调用**，显著降低开销：

```java
// 使用CompletableFuture实现请求合并（请求合并模式）
@Service
public class MergingChatService {
    
    private final ConcurrentMap<String, CompletableFuture<String>> pending = 
        new ConcurrentHashMap<>();
    
    public CompletableFuture<String> chat(String prompt) {
        String key = prompt.hashCode() + "_" + Instant.now().getEpochSecond() / 5;  // 5秒窗口内相同Prompt合并
        
        return pending.computeIfAbsent(key, k -> {
            CompletableFuture<String> future = new CompletableFuture<>();
            // 延迟执行，等待5秒看是否有其他请求进来
            ScheduledExecutorService scheduler = 
                Executors.newSingleThreadScheduledExecutor();
            scheduler.schedule(() -> {
                pending.remove(k);
                executeBatchAndComplete(prompt, future);
            }, 5, TimeUnit.SECONDS);
            return future;
        });
    }
    
    private void executeBatchAndComplete(String prompt, 
            CompletableFuture<String> future) {
        try {
            String response = chatClient.prompt()
                .user(prompt)
                .call()
                .content();
            future.complete(response);
        } catch (Exception e) {
            future.completeExceptionally(e);
        }
    }
}
```

### 6.2 Streaming响应的正确处理

对于长时间生成的响应，使用流式API可以**显著改善用户体验**，同时不对系统造成额外负担：

```java
// Spring AI流式调用
@Service
public class StreamingChatService {
    
    public Flux<String> streamChat(String prompt) {
        return chatClient.prompt()
            .user(prompt)
            .stream()  // 流式调用
            .content()  // 逐字 yield
            .onErrorResume(e -> Flux.just("处理失败: " + e.getMessage()));
    }
}

// Controller层处理流式响应
@RestController
public class ChatController {
    
    @GetMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> streamChat(@RequestParam String prompt) {
        return streamingChatService.streamChat(prompt);
    }
}
```

流式响应的核心优势在于：用户可以**立即看到首个字**，而不必等待2\~3秒才有输出。在用户体验和服务器负载上都是最优解。

---

## 七、总结：AI成本治理的核心公式

AI应用的成本优化不是单一技术问题，而是**技术+业务+运营**的综合工程：

```
最优成本 = (缓存命中率 × 缓存节省) 
         + (Prompt精简率 × Token节省)
         + (限流正确率 × 避免超限损失)
         - (监控运维成本)
```

面试时回答这类问题的最佳框架：
1. **分层优化**：先上缓存（零成本），再优化Prompt（改代码），最后考虑限流降级
2. **可观测性优先**：没有监控就不知道瓶颈在哪
3. **降级优于限流**：让用户能用到降级结果，比直接拒绝要好
4. **成本归属到业务**：每个功能模块的AI成本必须可追溯，才能持续优化

---

## 下期预告

《Spring AI面试八股文（十）——AI应用安全与合规：从Prompt注入到数据治理》

在大模型API广泛应用于生产环境的背景下，AI应用的安全问题日益突出：用户输入可能被恶意构造为Prompt注入攻击；对话数据可能涉及隐私合规；模型输出可能包含有害内容。本系列最后一篇，我们将深入AI应用安全与合规的核心议题：**Prompt注入的防御策略、输入输出过滤机制、对话数据的合规存储、以及企业级AI安全治理框架**。

> **系列导航**
> - [（一）ChatClient API与Prompt模板工程](/spring-ai-interview-1-chatclient)
> - [（二）Embedding模型与向量数据库集成](/spring-ai-interview-2-embedding)
> - [（三）Function Calling与Tool Calling深入](/spring-ai-interview-3-function-calling)
> - [（四）RAG企业级实践](/spring-ai-interview-4-rag)
> - [（五）AI Agent开发实战](/spring-ai-interview-5-agent)
> - [（六）AI网关与企业级集成](/spring-ai-interview-6-gateway)
> - [（七）多模型适配与切换](/spring-ai-interview-7-multi-model)
> - [（八）Prompt工程与管理](/spring-ai-interview-8-prompt)
> - [（九）AI应用性能优化与成本控制](/spring-ai-interview-9-perf)
