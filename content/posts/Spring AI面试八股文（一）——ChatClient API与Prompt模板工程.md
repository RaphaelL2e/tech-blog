---
title: "Spring AI面试八股文（一）——ChatClient API与Prompt模板工程"
date: 2026-07-16T09:00:00+08:00
draft: false
categories: ["Spring AI"]
tags: ["Spring AI", "Java", "AI", "ChatClient", "Prompt", "面试"]
keywords: ["Spring AI", "ChatClient", "PromptTemplate", "Model", "AI工程师", "面试八股文"]
description: "深入解析Spring AI框架核心API：ChatClient的同步/响应式调用、Prompt模板工程、多模型配置与切换、Function Calling基础。结合企业级实战案例和面试高频问题，全面掌握Spring AI开发能力。"
---

# Spring AI面试八股文（一）——ChatClient API与Prompt模板工程

> 面试高频问题：Spring AI的ChatClient怎么用？Prompt模板有哪些高级玩法？如何配置多个AI模型？Function Calling在Spring AI中怎么实现？本文带你掌握Spring AI框架的核心API和工程实践。

## 引言

Spring AI 是 Spring 官方推出的 AI 应用开发框架，于2024年初正式GA发布。它将 AI 能力无缝集成到 Spring 生态中，让 Java 开发者可以用熟悉的 Spring 风格开发 AI 应用。相比 LangChain 等框架，Spring AI 的优势在于：**与 Spring Boot/Spring Cloud 天然融合、类型安全、多模型统一抽象**。

本系列聚焦 AI 工程化面试知识点，从 Spring AI 框架核心出发，深入 AI 网关、向量数据库、RAG 实践、Prompt 工程、Function Calling、多模型适配等企业级应用场景。

**本文要点**：
1. ChatClient 同步/响应式调用方式
2. Prompt 模板工程与高级用法
3. 多模型配置与动态切换
4. ChatResponse 结构解析与元数据提取
5. Function Calling 入门（详细原理见后续章节）

---

## 一、ChatClient 核心API

### 1.1 为什么需要 ChatClient？

在 Spring AI 之前，开发者直接调用 AI 厂商 SDK（如 OpenAI SDK），代码分散在业务各处，难以统一管理。Spring AI 通过 `ChatClient` 提供了**统一的编程模型**：

```java
// Spring AI 统一调用方式
ChatClient chatClient = ChatClient.create(chatModel);
String response = chatClient.prompt()
    .user("请用Java实现快速排序")
    .call()
    .content();

// 底层可以是 OpenAI、Anthropic、Azure OpenAI、DeepSeek 等
// 切换模型只需改配置，无需改代码
```

**对比传统 SDK 调用**：

```java
// 传统 OpenAI SDK（分散、难以统一）
OpenAI openAI = new OpenAI("sk-xxx");
List<ChatMessage> messages = new ArrayList<>();
messages.add(new ChatMessage("user", "请用Java实现快速排序"));
ChatCompletion result = openAI.chat().chatCompletions()
    .create(ChatCompletionRequest.builder()
        .model("gpt-4o")
        .messages(messages)
        .build());
String response = result.getChoices().get(0).getMessage().getContent();
```

Spring AI 的优势：
- **统一抽象**：不同的 AI 厂商使用相同的 API
- **类型安全**：编译期检查，减少运行时错误
- **Spring 生态集成**：天然支持 `@ConfigurationProperties`、健康检查、监控
- **响应式支持**：同步和响应式两种模式无缝切换

### 1.2 同步调用：ChatClient.create()

**基本用法**：

```java
@Service
@RequiredArgsConstructor
public class CodeReviewService {
    
    private final ChatClient chatClient;
    
    public String reviewCode(String code) {
        return chatClient.prompt()
            .system("你是一个资深Java架构师，负责代码评审。")
            .user("请评审以下代码，指出问题并给出优化建议：\n" + code)
            .call()
            .content();
    }
}
```

**带选项的调用**：

```java
// 设置温度、top_p、max_tokens等参数
String response = chatClient.prompt()
    .options(ChatOptionsBuilder.builder()
        .temperature(0.7)
        .topP(0.9)
        .maxTokens(2000)
        .build())
    .user("解释什么是依赖注入")
    .call()
    .content();
```

**流式调用（Streaming）**：

```java
// 流式返回，适用于长文本生成
Flux<String> stream = chatClient.prompt()
    .user("写一个Spring Boot项目的README")
    .stream()
    .content();

stream.subscribe(chunk -> System.out.print(chunk));
```

### 1.3 响应式调用：WebFlux集成

```java
@RestController
@RequiredArgsConstructor
public class AiController {
    
    private final ChatClient chatClient;
    
    // 同步响应
    @PostMapping("/api/chat/sync")
    public String chatSync(@RequestBody ChatRequest request) {
        return chatClient.prompt()
            .user(request.getQuestion())
            .call()
            .content();
    }
    
    // 响应式响应（适用于高并发场景）
    @PostMapping("/api/chat/reactive")
    public Mono<String> chatReactive(@RequestBody ChatRequest request) {
        return chatClient.prompt()
            .user(request.getQuestion())
            .call()
            .contentAsync();  // 返回 Mono<String>
    }
    
    // SSE流式响应（适用于实时输出场景）
    @GetMapping(value = "/api/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> chatStream(@RequestParam String question) {
        return chatClient.prompt()
            .user(question)
            .stream()
            .content();
    }
}
```

### 1.4 ChatResponse 结构解析

```java
// 获取完整响应（包含元数据）
ChatResponse response = chatClient.prompt()
    .user("2024年诺贝尔物理学奖获得者是谁？")
    .call()
    .chatResponse();  // 返回完整响应对象

// 1. 获取文本内容
String content = response.getResult().getOutput().getContent();

// 2. 获取模型名称
String model = response.getResult().getModel();
System.out.println("使用的模型: " + model);  // e.g., gpt-4o

// 3. 获取Token使用量
Integer inputTokens = response.getMetadata().getUsage().getPromptTokens();
Integer outputTokens = response.getMetadata().getUsage().getCompletionTokens();
Integer totalTokens = response.getMetadata().getUsage().getTotalTokens();
System.out.printf("Token消耗: 输入=%d, 输出=%d, 总计=%d%n", 
    inputTokens, outputTokens, totalTokens);

// 4. 获取finishReason
FinishReason reason = response.getResult().getFinishReason();
System.out.println("结束原因: " + reason);  // STOP, LENGTH, CONTENT_FILTER, TOOL_CALLS

// 5. 获取时间戳
Instant created = response.getMetadata().getCreated();
System.out.println("生成时间: " + created);
```

**面试高频问题**：

**Q: Spring AI 的 ChatClient 和 RestClient 有什么区别？**

A: 两者完全不是一个东西：
- `RestClient`：Spring 6.1 推出的 HTTP 客户端，用于调用 REST API
- `ChatClient`：Spring AI 封装的 AI 对话客户端，内部使用 RestClient 调用 AI 厂商 API

简单说：**ChatClient 专门用于 AI 对话，RestClient 是通用 HTTP 客户端**。

---

## 二、Prompt模板工程

### 2.1 PromptTemplate 基础

```java
// 方式一：占位符形式
PromptTemplate template = new PromptTemplate(
    "请将以下中文翻译成{targetLanguage}：\n{content}");
Map<String, Object> variables = Map.of(
    "targetLanguage", "English",
    "content", "依赖注入是控制反转的一种实现方式"
);
Prompt prompt = template.render(variables);
String response = chatClient.prompt(prompt).call().content();
// Output: Dependency Injection is an implementation of Inversion of Control.

 // 方式二：链式API（更直观）
String response = chatClient.prompt()
    .param("targetLanguage", "French")
    .param("content", "依赖注入是控制反转的一种实现方式")
    .template("请将以下中文翻译成{targetLanguage}：\n{content}")
    .call()
    .content();

// 方式三：复用系统Prompt
PromptTemplate systemTemplate = new PromptTemplate(
    "你是一个专业的{domain}翻译专家，要求：\n" +
    "1. 保持专业术语准确\n" +
    "2. 语序符合目标语言习惯\n" +
    "3. 适当添加注释说明");
Prompt systemPrompt = systemTemplate.render(Map.of("domain", "技术"));
```

### 2.2 SystemPromptTemplate 系统角色模板

```java
// 创建系统角色模板
SystemPromptTemplate systemPromptTemplate = new SystemPromptTemplate(
    """
    你是一个资深的{role}，拥有{yearsOfExperience}年的行业经验。
    你的专长领域包括：
    {expertiseAreas}
    
    请用专业但不晦涩的语言回答用户的问题。
    """
);

Map<String, Object> params = Map.of(
    "role", "Java后端架构师",
    "yearsOfExperience", "10",
    "expertiseAreas", "1. 微服务架构设计\n2. 高并发系统优化\n3. 分布式事务处理"
);

// 构建完整Prompt（系统+用户）
UserParams userParams = new UserParams("解释什么是CAP定理");
Prompt prompt = systemPromptTemplate.create(params, userParams);

String response = chatClient.prompt(prompt).call().content();
```

### 2.3 多轮对话管理

```java
@Service
public class ChatSessionService {
    
    private final ChatModel chatModel;
    
    public String chat(List<ChatMessage> history, String newMessage) {
        // 使用 MessageChatMemory 管理对话历史
        ChatMemory chatMemory = new MessageChatHistory().addUserMessage(newMessage);
        
        ChatClient chatClient = ChatClient.builder(chatModel)
            .defaultSystem("你是AI助手。")
            .build();
        
        return chatClient.prompt()
            .messages(chatMemory.getMessages())  // 传入历史消息
            .user(newMessage)
            .call()
            .content();
    }
}

// 或者手动管理消息列表
public String chatManual(List<ChatMessage> history, String newMessage) {
    List<ChatMessage> messages = new ArrayList<>(history);
    messages.add(new UserMessage(newMessage));
    
    return chatClient.prompt()
        .messages(messages)
        .call()
        .content();
}
```

### 2.4 高级：动态Prompt组装

```java
// 根据用户意图动态组装Prompt
@Service
@RequiredArgsConstructor
public class DynamicPromptService {
    
    private final ChatClient chatClient;
    
    public String buildAndChat(String userInput) {
        PromptTemplate template = determineTemplate(userInput);
        
        Map<String, Object> params = extractParams(userInput);
        
        return chatClient.prompt()
            .param("input", userInput)
            .params(params)
            .template(template.getTemplate())
            .call()
            .content();
    }
    
    private PromptTemplate determineTemplate(String input) {
        if (input.contains("代码") || input.contains("实现")) {
            return new PromptTemplate(
                "请为以下需求提供实现代码：\n{input}\n" +
                "要求：\n1. 遵循SOLID原则\n2. 添加必要注释\n3. 考虑异常处理");
        } else if (input.contains("解释") || input.contains("概念")) {
            return new PromptTemplate(
                "请通俗易懂地解释以下概念：\n{input}\n" +
                "要求：\n1. 举生活实例说明\n2. 对比相关概念\n3. 列出使用场景");
        } else {
            return new PromptTemplate("请回答：\n{input}");
        }
    }
    
    private Map<String, Object> extractParams(String input) {
        return Map.of("input", input);
    }
}
```

---

## 三、多模型配置与动态切换

### 3.1 application.yml 配置

```yaml
spring:
  ai:
    # OpenAI 配置
    openai:
      api-key: ${OPENAI_API_KEY}
      base-url: https://api.openai.com/v1
      chat:
        options:
          model: gpt-4o
          temperature: 0.7
          max-tokens: 4096
    
    # DeepSeek 配置（国产模型，性价比高）
    deepseek:
      api-key: ${DEEPSEEK_API_KEY}
      base-url: https://api.deepseek.com/v1
      chat:
        options:
          model: deepseek-chat
          temperature: 0.7
    
    # Azure OpenAI 配置（企业内网场景）
    azure:
      openai:
        api-key: ${AZURE_OPENAI_KEY}
        endpoint: ${AZURE_OPENAI_ENDPOINT}
        chat:
          deployment-name: gpt-4o
          options:
            temperature: 0.7
```

### 3.2 多模型 Bean 定义

```java
@Configuration
public class MultiModelConfig {
    
    @Bean
    @Primary  // 默认使用的模型
    public ChatModel openAiChatModel(OpenAiApi openAiApi) {
        return OpenAiChatModel.builder()
            .openAiApi(openAiApi)
            .defaultOptions(OpenAiChatOptions.builder()
                .model("gpt-4o")
                .temperature(0.7)
                .build())
            .build();
    }
    
    @Bean
    public ChatModel deepseekChatModel(DeepSeekApi deepSeekApi) {
        return DeepSeekChatModel.builder()
            .deepSeekApi(deepSeekApi)
            .defaultOptions(DeepSeekChatOptions.builder()
                .model("deepseek-chat")
                .temperature(0.7)
                .build())
            .build();
    }
    
    @Bean
    public ChatModel azureChatModel(AzureOpenAiChatModel azureChatModel) {
        return azureChatModel;
    }
}
```

### 3.3 动态模型选择

```java
@Service
@RequiredArgsConstructor
public class ModelRouterService {
    
    private final ChatClient openAiClient;
    private final ChatClient deepseekClient;
    private final ChatClient azureClient;
    
    // 根据任务类型选择模型
    public String routeAndChat(String taskType, String prompt) {
        return switch (taskType) {
            case "creative" -> openAiClient.prompt().user(prompt)
                .options(OpenAiChatOptions.builder().temperature(0.9).build())
                .call().content();
            case "code" -> deepseekClient.prompt().user(prompt)
                .options(DeepSeekChatOptions.builder().temperature(0.2).build())
                .call().content();
            case "formal" -> azureClient.prompt().user(prompt)
                .options(AzureOpenAiChatOptions.builder().temperature(0.5).build())
                .call().content();
            default -> openAiClient.prompt().user(prompt).call().content();
        };
    }
    
    // 根据Token预算选择模型
    public String chatByBudget(String prompt, int maxBudget) {
        if (maxBudget < 1000) {
            // 低预算：使用便宜模型
            return deepseekClient.prompt().user(prompt).call().content();
        } else if (maxBudget < 5000) {
            // 中预算：使用中等模型
            return openAiClient.prompt()
                .options(OpenAiChatOptions.builder().model("gpt-4o-mini").build())
                .user(prompt).call().content();
        } else {
            // 高预算：使用最强模型
            return openAiClient.prompt()
                .options(OpenAiChatOptions.builder().model("gpt-4o").build())
                .user(prompt).call().content();
        }
    }
}
```

### 3.4 模型成本与性能对比

| 模型 | 上下文 | 特点 | 适用场景 | 成本 |
|------|--------|------|----------|------|
| GPT-4o | 128K | 综合最强，多模态 | 复杂推理、创意写作 | 高 |
| GPT-4o-mini | 128K | 性价比之王 | 日常对话、代码生成 | 中 |
| DeepSeek-Chat | 64K | 推理能力强，中文好 | 中文场景、代码 | 低 |
| Claude-3.5 | 200K | 长上下文、安全 | 长文本分析、写作 | 高 |
| GLM-4 | 128K | 中文优化 | 中文对话 | 低 |

---

## 四、Function Calling 入门

> **提示**：Function Calling 详细原理、工具注册、复杂场景实战将在后续章节深入讲解。本节先介绍 Spring AI 中 Function Calling 的基本用法。

### 4.1 定义工具函数

```java
// 方式一：使用 @Tool 注解
public class WeatherTools {
    
    @Tool(description = "获取指定城市的当前天气")
    public String getWeather(@ToolParam(description = "城市名称，如北京、上海") String city) {
        // 调用天气API
        return "北京今天晴，26°C，空气质量良好";
    }
    
    @Tool(description = "查询航班信息")
    public String searchFlights(
            @ToolParam(description = "出发城市") String from,
            @ToolParam(description = "目的城市") String to,
            @ToolParam(description = "出发日期 YYYY-MM-DD") String date) {
        return "MU1234 10:00出发，12:30到达，票价980元";
    }
}
```

### 4.2 注册与调用

```java
@Configuration
public class FunctionCallingConfig {
    
    @Bean
    public ChatModel chatModelWithFunctions(OpenAiApi openAiApi) {
        return OpenAiChatModel.builder()
            .openAiApi(openAiApi)
            .defaultOptions(OpenAiChatOptions.builder()
                .model("gpt-4o")
                .function("weather", new WeatherTools())  // 注册工具
                .build())
            .build();
    }
}

// 使用
@RestController
@RequiredArgsConstructor
public class AiChatController {
    
    private final ChatClient chatClient;
    
    @GetMapping("/chat")
    public String chat(@RequestParam String question) {
        return chatClient.prompt()
            .user(question)
            .call()
            .content();
        // 问题"北京今天天气如何？"会自动调用getWeather("北京")
    }
}
```

---

## 五、企业级实战案例

### 5.1 智能代码审查系统

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class CodeReviewSystem {
    
    private final ChatClient chatClient;
    
    public CodeReviewResult review(String code, String language) {
        String systemPrompt = """
            你是一个专业的代码审查员，负责审查{language}代码。
            请从以下维度进行审查：
            1. 代码安全性（SQL注入、XSS、敏感信息泄露等）
            2. 性能问题（N+1查询、循环中的数据库操作等）
            3. 代码可读性（命名、注释、结构）
            4. 最佳实践（设计模式、框架使用）
            5. 潜在Bug（空指针、并发问题等）
            
            输出格式（JSON）：
            {
              "security": [{"severity": "HIGH/MEDIUM/LOW", "line": 10, "issue": "...", "suggestion": "..."}],
              "performance": [...],
              "readability": [...],
              "bestPractices": [...],
              "bugs": [...],
              "overallScore": 85,
              "summary": "总体评价..."
            }
            """;
        
        String userPrompt = "请审查以下{language}代码：\n```\n{code}\n```";
        
        Map<String, Object> params = Map.of(
            "language", language,
            "code", code
        );
        
        String response = chatClient.prompt()
            .system(sp -> sp.text(systemPrompt).param("language", language))
            .user(u -> u.text(userPrompt).param("code", code))
            .options(OpenAiChatOptions.builder()
                .temperature(0.3)  // 代码审查需要稳定性
                .responseFormat(ChatOptions.ResponseFormat.JSON)
                .build())
            .call()
            .content();
        
        return parseReviewResult(response);
    }
}

@Data
public class CodeReviewResult {
    private List<Issue> security;
    private List<Issue> performance;
    private List<Issue> readability;
    private List<Issue> bestPractices;
    private List<Issue> bugs;
    private int overallScore;
    private String summary;
    
    @Data
    public static class Issue {
        private String severity;
        private Integer line;
        private String issue;
        private String suggestion;
    }
}
```

### 5.2 多租户AI服务

```java
@Service
@RequiredArgsConstructor
public class TenantAwareChatService {
    
    private final Map<String, ChatClient> tenantClients;
    private final TenantConfigService tenantConfigService;
    
    public String chatForTenant(String tenantId, String prompt) {
        // 1. 获取租户配置（模型、Token限制等）
        TenantConfig config = tenantConfigService.getConfig(tenantId);
        
        // 2. 获取该租户的ChatClient
        ChatClient client = tenantClients.get(config.getModelType());
        
        // 3. 检查Token配额
        if (config.getUsedTokens() + estimateTokens(prompt) > config.getMaxTokens()) {
            throw new TokenQuotaExceededException("Token配额已用完，请联系管理员");
        }
        
        // 4. 执行调用
        String response = client.prompt()
            .system(sp -> sp.text(config.getSystemPrompt()))
            .user(prompt)
            .options(ChatOptionsBuilder.builder()
                .temperature(config.getTemperature())
                .maxTokens(config.getMaxResponseTokens())
                .build())
            .call()
            .content();
        
        // 5. 更新使用量
        tenantConfigService.updateUsage(tenantId, estimateTokens(prompt), estimateTokens(response));
        
        return response;
    }
}
```

---

## 六、面试高频问题汇总

### Q1: Spring AI 和 LangChain4j 有什么区别？如何选择？

| 维度 | Spring AI | LangChain4j |
|------|-----------|-------------|
| 生态集成 | Spring全家桶无缝集成 | 独立框架，也可与Spring配合 |
| 学习曲线 | Spring开发者友好 | 概念抽象更纯粹 |
| 模型支持 | 官方维护，模型覆盖广 | 社区活跃，模型覆盖广 |
| Function Calling | 支持（通过@Tool） | 支持（更灵活） |
| 适用场景 | Spring项目集成 | 轻量级/多框架项目 |

**选择建议**：
- 已有 Spring Boot 项目 → **Spring AI**
- 需要快速原型/多框架支持 → **LangChain4j**
- 需要强类型安全 → **Spring AI**

### Q2: Spring AI 如何保证调用稳定性？

**策略一：重试机制**

```java
@Bean
public ChatModel resilientChatModel(OpenAiApi openAiApi) {
    return OpenAiChatModel.builder()
        .openAiApi(openAiApi)
        .retryTemplate(retryTemplate())  // 配置重试
        .build();
}

@Bean
public RetryTemplate retryTemplate() {
    SimpleRetryPolicy policy = new SimpleRetryPolicy(3);
    ExponentialBackoffPolicy backoff = new ExponentialBackoffPolicy();
    backoff.setInitialInterval(1000);
    backoff.setMultiplier(2.0);
    
    return RetryTemplate.builder()
        .retryPolicy(policy)
        .backoffPolicy(backoff)
        .build();
}
```

**策略二：降级方案**

```java
@Service
public class FallbackChatService {
    
    private final ChatClient primaryClient;
    private final ChatClient fallbackClient;
    
    public String chatWithFallback(String prompt) {
        try {
            return primaryClient.prompt().user(prompt).call().content();
        } catch (Exception e) {
            log.warn("主模型调用失败，切换到降级模型: {}", e.getMessage());
            return fallbackClient.prompt().user(prompt).call().content();
        }
    }
}
```

### Q3: 如何处理 AI 响应的 Token 成本？

```java
@Service
@RequiredArgsConstructor
public class TokenCostService {
    
    private final ChatClient chatClient;
    
    public CostAwareResponse chatWithCost(String prompt) {
        long start = System.currentTimeMillis();
        
        ChatResponse response = chatClient.prompt()
            .user(prompt)
            .call()
            .chatResponse();
        
        long duration = System.currentTimeMillis() - start;
        
        Usage usage = response.getMetadata().getUsage();
        int totalTokens = usage.getTotalTokens();
        
        // 计算成本（以GPT-4o为例）
        double cost = calculateCost(totalTokens, "gpt-4o");
        
        return new CostAwareResponse(
            response.getResult().getOutput().getContent(),
            totalTokens,
            cost,
            duration
        );
    }
    
    private double calculateCost(int tokens, String model) {
        // GPT-4o: $2.5/1M input, $10/1M output
        return tokens * (2.5 / 1_000_000);  // 简化计算
    }
    
    public record CostAwareResponse(
        String content,
        int tokens,
        double costUsd,
        long durationMs
    ) {}
}
```

### Q4: Spring AI 如何实现结构化输出（JSON Schema）？

```java
@Service
public class StructuredOutputService {
    
    private final ChatClient chatClient;
    
    public Person parsePerson(String text) {
        // 方式一：通过Prompt指定JSON Schema
        String prompt = """
            解析以下文本，提取人物信息，返回JSON：
            输入：{text}
            
            JSON Schema:
            {
              "name": "string (姓名)",
              "age": "number (年龄)",
              "occupation": "string (职业)",
              "email": "string (邮箱，可选)"
            }
            """;
        
        String response = chatClient.prompt()
            .user(prompt)
            .options(ChatOptionsBuilder.builder()
                .responseFormat(ChatOptions.ResponseFormat.JSON)
                .build())
            .call()
            .content();
        
        return parseJson(response, Person.class);
    }
    
    // 方式二：使用阿里云的函数调用（结构更稳定）
    public Person parsePersonWithFunction(String text) {
        return chatClient.prompt()
            .user(text)
            .functions("personParser")  // 注册PersonParser函数
            .call()
            .entity(Person.class);  // 直接返回对象
    }
}
```

---

## 总结

本文深入解析了 Spring AI 框架的核心 API 和工程实践：

| 知识点 | 核心要点 |
|--------|----------|
| **ChatClient** | 统一抽象、同步/响应式/流式三种模式、ChatResponse完整元数据 |
| **Prompt模板** | 占位符变量、SystemPromptTemplate、多轮对话、动态组装 |
| **多模型配置** | application.yml配置、多Bean注册、动态路由、成本优化 |
| **Function Calling** | @Tool注解、工具注册（详细原理见后续章节） |
| **企业实战** | 代码审查、多租户、Token成本控制 |

**下期预告**：《Spring AI面试八股文（二）——Embedding模型与向量数据库集成》，我们将深入探讨：
- Embedding模型配置与使用
- VectorStore抽象与实现
- 主流向量数据库对比（Milvus、Pgvector、Chroma、Weaviate）
- 相似度搜索与向量索引优化
- 企业级RAG第一步：文档向量化

---

> **推荐阅读**
> - [AI大模型面试八股文（四）——大模型应用开发与Agent框架](/posts/AI大模型面试八股文（四）——大模型应用开发与Agent框架/)：了解RAG、Function Calling基础原理
> - [Spring Boot自动配置原理与自定义Starter开发](/posts/Spring面试八股文（九）——Spring-Boot自动配置原理与自定义Starter开发/)：Spring Boot条件装配机制（Spring AI自动配置基于此实现）
> - [AI大模型系统设计与工程实践](/posts/AI大模型面试八股文（六）——大模型系统设计与工程实践/)：RAG系统完整架构
