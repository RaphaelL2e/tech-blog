---
title: "Spring AI面试八股文（五）——AI Agent开发实战"
date: 2026-07-18T10:00:00+08:00
draft: false
categories: ["Spring AI"]
tags: ["Spring AI", "Java", "AI", "Agent", "ReAct", "ChatMemory", "HITL", "多Agent", "人工智能", "面试"]
keywords: ["Spring AI", "AI Agent", "ReAct", "ChatMemory", "ToolAgent", "Specification", "Executor", "HITL", "面试八股文"]
description: "深入解析Spring AI Agent开发：从ReAct循环、ChatMemory多轮记忆、ToolAgent工具编排到多Agent协作与人工接管（HITL）模式。结合企业级实战代码和面试高频问题，掌握用Spring AI构建生产级自主Agent的核心能力。"
---

# Spring AI面试八股文（五）——AI Agent开发实战

> 面试高频问题：Spring AI中Agent的核心架构是什么？ReAct循环怎么实现？ChatMemory多轮对话怎么管理？ToolAgent怎么编排多个工具？人工接管（HITL）怎么实现？多Agent如何协作？本文带你从"能回答"升级为"能行动"。

## 引言

前面四篇解决了 AI 应用的核心能力问题：
- **（一）** ChatClient 统一了对话 API
- **（二）** Embedding + VectorStore 解决了知识检索
- **（三）** Function Calling / Tool Calling 解决了工具调用
- **（四）** RAG 解决了知识增强

但这些能力是**原子级**的——每个请求独立响应，没有"规划—执行—反思—迭代"的自主行为能力。把原子能力串成**闭环自主系统**，就是 **AI Agent（人工智能代理）**。

AI Agent 的通用概念（ReAct、规划、记忆、工具调用）在《AI大模型面试八股文（四）——大模型应用开发与Agent框架》中有完整阐述（超过3000字），本文**不再重复**那些理论，重点聚焦 **Spring AI 自己怎么把 Agent 工程化**——它提供了一套类型安全、可组合、可观测的 Agent 框架。

**本文要点**：
1. Spring AI Agent 核心架构：`Agent / Specification / Executor` 三件套
2. ReAct 循环的 Spring AI 实现
3. ChatMemory 多轮对话记忆管理
4. ToolAgent：多工具编排与动态工具选择
5. 人工接管（HITL）模式
6. 多 Agent 协作架构
7. 生产级 Agent 调优清单

---

## 一、为什么需要 Agent：超越单轮问答

**单轮问答的局限**：每次对话独立，没有状态积累，无法自主决策下一步行动。用户说"帮我分析竞品A和B"，单轮模型直接回答；Agent 则会先"规划"步骤——查竞品A数据、查竞品B数据、对比分析、自动生成报告，每步可观测、可干预。

**Spring AI Agent 的价值**：
- 把 Agent 的"大脑（LLM）+四肢（Tool）+记忆（Memory）"解耦成独立组件，各自独立演进
- 与 Spring Boot/Spring Cloud 生态天然融合：安全、配置、监控、事务语义
- 类型安全的工具注册与调用链

企业级 Agent 的核心挑战不是"能跑"，而是**可控、可观测、可干预**：模型下一步要调哪个工具你是否知道？调错了怎么回滚？Agent 陷入死循环怎么办？Spring AI 的 Agent 框架正是为这些生产问题设计的。

## 二、Spring AI Agent 核心架构

Spring AI 的 Agent 体系围绕三个核心接口展开：

### 2.1 `AgentSpecification`：Agent 的"大脑配置"

```java
public interface AgentSpecification<T extends AgentRequest, R extends AgentResponse> {
    String getName();                          // Agent 名称
    String getDescription();                   // Agent 能力描述（供调度 Agent 参考）
    SystemPromptRenderer getSystemPromptRenderer(); // 系统提示词渲染
}
```

`AgentSpecification` 定义了一个 Agent 的"身份"——它的名字是什么、能干什么、用什么系统提示词。Spring AI 内置了几种 Specification：

```java
// 用户助手型 Agent
UserTaskAgentSpecification spec = new UserTaskAgentSpecification(
    getSystemPrompt("你是一个助手..."),
    chatModel,
    tools // 绑定可用工具
);

// 检索型 Agent（继承 RAG 能力）
RetrievalAgentSpecification spec = new RetrievalAgentSpecification(
    vectorStore,
    chatModel
);
```

**面试点**：`AgentSpecification` 的 `getDescription()` 方法在**多 Agent 调度**场景中至关重要——调度 Agent 通过描述来决定把任务交给哪个子 Agent，这本质上是"模型驱动的路由"，而不是 if-else 硬编码。

### 2.2 `AgentExecutor`：Agent 的"执行引擎"

```java
public interface AgentExecutor {
    AgentResponse execute(AgentRequest request);   // 同步执行
    // 或
    Flux<AgentResponse> executeStream(AgentRequest request);  // 流式执行
}
```

Executor 负责**执行循环**：接收请求 → 调用 LLM → 判断是否需要工具 → 执行工具 → 将结果反馈给 LLM → 判断是否完成 → 返回。Spring AI 提供 `BasicAgentExecutor` 作为默认实现。

```java
@Autowired
private AgentExecutor executor;

public String agentTask(String task) {
    AgentRequest request = AgentRequest.of(task);
    AgentResponse response = executor.execute(request);
    return response.getResult();
}
```

### 2.3 `ChatAgent`：高层 Agent 抽象

在 `spring-ai-starter-extended` 模块中，Spring AI 提供了更易用的 `ChatAgent` 抽象：

```java
public class ChatAgent {
    private final ChatClient chatClient;
    private final List<ToolCallback> toolCallbacks;
    private final ChatMemory chatMemory;

    public ChatAgent(ChatClient chatClient, 
                     List<ToolCallback> toolCallbacks,
                     ChatMemory chatMemory) {
        this.chatClient = chatClient;
        this.toolCallbacks = toolCallbacks;
        this.chatMemory = chatMemory;
    }

    public String chat(String userMessage) {
        // 构造带工具描述的 Prompt
        // 如果 LLM 返回工具调用 → 执行 → 循环
        // 否则 → 返回文本响应
    }
}
```

## 三、ReAct 循环的 Spring AI 实现

ReAct（Reasoning + Acting）是 Agent 的经典范式：**思考（Reason）→ 行动（Act）→ 观察（Observe）→ 循环直到完成**。Spring AI 的 `ToolCallback` 机制天然支持 ReAct：

```java
@Configuration
public class AgentConfig {

    @Bean
    public ChatClient chatClient(ChatModel chatModel) {
        return ChatClient.builder(chatModel).build();
    }

    @Bean
    public ToolCallback weatherTool() {
        return ToolCallback.builder(weatherToolSpec, (input) -> {
            // 实际执行天气查询
            return weatherService.query(input.getLocation());
        }).build();
    }

    @Bean
    public ToolCallback dbTool() {
        return ToolCallback.builder(databaseToolSpec, (input) -> {
            return databaseService.query(input.getSql());
        }).build();
    }

    @Bean
    public ChatAgent assistantAgent(ChatClient chatClient,
                                    List<ToolCallback> tools,
                                    ChatMemory chatMemory) {
        return new ChatAgent(chatClient, tools, chatMemory);
    }
}
```

```java
@Service
public class ReActAgentService {

    @Autowired
    private ChatAgent agent;

    public String execute(String task) {
        // ReAct 循环：每次 chat() 调用在 Agent 内部完成：
        // LLM 决定是否调用工具 → 工具执行 → 结果注入上下文 → LLM 决定下一步
        return agent.chat(task);
    }
}
```

**ReAct 执行流程源码解析**（`ToolCallbackChatMemory` 核心逻辑）：

1. **Prompt 构造**：系统提示词包含所有可用工具的 JSON Schema + 聊天历史 + 用户输入
2. **LLM 推理**：模型分析任务，决定是否需要工具调用
3. **工具执行**：若模型返回 `tool_calls`，Executor 执行对应工具，返回 `tool_result`
4. **循环判断**：结果注入上下文，模型再次判断：任务完成 or 继续调用工具？
5. **终止**：模型返回纯文本回答，或达到最大循环次数（防止死循环）

**面试点**：ReAct 的最大工程挑战是**循环终止条件**。Spring AI 的做法是配置 `maxIterations`（默认 10），超过则抛出 `MaxIterationsExceededException`，你需要在调用方捕获处理。

```java
ChatAgentOptions options = ChatAgentOptions.builder()
    .maxIterations(5)
    .temperature(0.3)
    .build();

try {
    String result = agent.chat(task, options);
} catch (MaxIterationsExceededException e) {
    // Agent 陷入死循环，需要人工介入或重试
    log.warn("Agent reached max iterations, partial result: {}", e.getPartialResult());
}
```

## 四、ChatMemory：多轮对话记忆管理

### 4.1 为什么需要 ChatMemory

单轮对话中历史消息不积累，模型无法理解上下文。ChatMemory 将对话历史持久化，供 Agent 每次推理时参考。

### 4.2 Spring AI 内存实现

```java
// 方式一：简单内存（内存中，进程重启丢失）
ChatMemory chatMemory = new SimpleChatMemory();

// 方式二：Token 计数内存（控制上下文长度）
ChatMemory chatMemory = new TokenWindowChatMemory(
    chatModel,       // 用于计算 token 数
    maxTokens(4000)  // OpenAI GPT-4o max context 的一半
);

// 方式三：持久化内存（Redis，支持分布式 Agent）
ChatMemory chatMemory = new RedisChatMemory(
    redisConnectionFactory,
    "agent:session:" + sessionId  // 按会话隔离
);
```

### 4.3 消息记忆 CRUD

```java
@Autowired
private ChatMemory chatMemory;

public String chat(String sessionId, String userMessage) {
    // 1. 加载该会话的历史
    chatMemory.add(sessionId, new UserMessage(userMessage));

    // 2. Agent 基于历史 + 当前输入推理
    String response = agent.chat(sessionId);

    // 3. 保存 Agent 回复到记忆
    chatMemory.add(sessionId, new AssistantMessage(response));

    // 4. 可选：定期压缩历史（TokenWindowChatMemory 自动裁剪）
    return response;
}
```

**面试点**：
- **TokenWindowChatMemory vs SimpleChatMemory**：前者按 token 数动态裁剪，保证不超模型上下文窗口；后者无限制，适合短对话或测试。
- **Redis ChatMemory**：生产环境推荐，支持多实例 Agent 共享同一会话记忆，是分布式 Agent 架构的基础。
- **记忆的隐私问题**：不同用户/租户的会话必须用不同 sessionId 隔离，Redis key 加租户前缀。

### 4.4 记忆压缩与摘要

当对话很长时，向 LLM 传入全部历史会消耗大量 token。Spring AI 支持**摘要式记忆**：

```java
ChatMemory summaryMemory = new SummaryChatMemory(
    chatModel,           // 用同一个或另一个模型做摘要
    SummarizingChatMemoryFormatter.DEFAULT,
    maxSummaryTokens(500)
);
```

```java
// 原始对话超过阈值后，SummaryChatMemory 自动压缩：
// [msg1, msg2, ..., msg_n] 
//   → [摘要: msg1~msg_n-5, msg_{n-4}, ..., msg_n]
// 这样保留最近上下文的同时，大幅减少 token 开销
```

**面试点**：摘要记忆的核心是"**信息密度换 token**"——用一个小模型或当前模型的摘要能力，把 10 轮对话压缩成 1 轮摘要，节省约 60-80% 的 token。

## 五、ToolAgent：多工具编排与动态选择

### 5.1 单一工具 Agent → 多工具编排

单个 Function Calling 只能调用一个工具。实际 Agent 往往需要**动态选择**调用多个工具：

```java
// 场景：客服 Agent，能查订单、查物流、查商品、生成退款单
@Configuration
public class CustomerServiceAgentConfig {

    @Bean
    public ChatAgent customerServiceAgent(ChatClient chatClient) {
        List<ToolCallback> tools = Arrays.asList(
            toolCallback(queryOrderToolSpec),   // 查订单
            toolCallback(trackDeliveryToolSpec), // 查物流
            toolCallback(queryProductToolSpec),  // 查商品
            toolCallback(createRefundToolSpec)   // 退款
        );

        ChatMemory chatMemory = new TokenWindowChatMemory(chatModel, maxTokens(3000));

        return ChatAgent.builder(chatClient)
            .tools(tools)
            .chatMemory(chatMemory)
            .systemPrompt("你是一个专业客服，擅长分析用户意图并调用相应工具...")
            .build();
    }
}
```

### 5.2 工具优先级的动态选择

面试常问：**Agent 怎么知道该调哪个工具？** 答案在工具的 `description` 字段——模型通过描述决定。Spring AI 允许精细控制描述：

```java
// 好描述：明确能力边界
ToolCallback queryOrderToolSpec = ToolCallback.builder(
    "queryOrder",
    """
    根据用户提供的订单号查询订单详情。
    输入：订单号（字符串，必填）
    输出：订单状态、商品列表、收货地址、总金额
    适用场景：用户问"我的订单到哪了"、"查一下订单X"
    """
).build();

// 坏描述：模糊不清
ToolCallback badSpec = ToolCallback.builder(
    "queryOrder",
    "查询订单"
).build();
```

**面试点**：工具描述本质上是**给模型的指令**。描述质量直接决定模型选对工具的概率。实战中建议：
- 每个工具描述不超过 200 字
- 明确输入输出格式（减少 JSON 解析错误）
- 明确适用场景（减少误调用）

### 5.3 工具执行错误的重试与降级

工具调用可能失败（网络超时、权限不足），Agent 需要优雅处理：

```java
ToolCallback.withRetry(
    queryOrderToolSpec,
    3,                              // 重试 3 次
    Duration.ofSeconds(2),          // 间隔 2 秒
    (input) -> orderService.query(input.getOrderId()),
    (ex) -> log.error("查询订单失败: {}", ex.getMessage())
);
```

## 六、人工接管（HITL）模式

### 6.1 什么是 HITL

Agent 在某些关键节点（如涉及金额、隐私、不可逆操作）需要**人工审批**才能继续执行，这叫 Human-in-the-Loop（人工介入）。

### 6.2 Spring AI 的 HITL 实现

```java
@Service
public class HitlAgentService {

    @Autowired
    private ChatAgent agent;

    @Autowired
    private ApprovalService approvalService; // 自定义审批服务

    public String executeWithApproval(String task) {
        // 第一步：Agent 推理并确定需要审批的操作
        String proposedAction = agent.reason(task);
        // proposedAction: "我将为您生成退款单：订单X，退款金额¥299，确认执行？"

        // 第二步：暂停，等待人工审批
        ApprovalRequest approvalReq = ApprovalRequest.builder()
            .agent("customer-service-agent")
            .action(proposedAction)
            .type(ApprovalType.REFUND)
            .build();

        ApprovalResult result = approvalService.request(approvalReq);

        if (result.getStatus() == ApprovalStatus.REJECTED) {
            return "已取消操作：" + result.getReason();
        }

        // 第三步：审批通过，执行实际操作
        if (result.getStatus() == ApprovalStatus.APPROVED) {
            return agent.executeApprovedAction(task);
        }

        return "审批超时，请稍后重试";
    }
}
```

**审批服务示例（基于飞书消息）**：

```java
@Service
public class ApprovalService {
    
    @Autowired
    private FeishuMessageService messageService;

    public ApprovalResult request(ApprovalRequest req) {
        // 发送飞书消息给审批人
        String msg = String.format("⚠️ Agent 待审批\n类型：%s\n操作：%s",
            req.getType(), req.getAction());
        
        String messageId = messageService.sendToApprover(msg);
        
        // 阻塞等待审批结果（生产中用 CompletableFuture + 回调）
        return waitForApproval(messageId, Duration.ofMinutes(5));
    }
}
```

**面试点**：HITL 的核心设计问题是"**审批接口的可用性**"——审批超时、审批人离线、系统故障时的降级策略。建议：审批超时默认 30 分钟，超时自动转邮件通知 + 默认拒绝。

## 七、多 Agent 协作架构

### 7.1 什么时候需要多 Agent

单 Agent 的局限：工具太多 → 模型选错概率上升 → 性能下降。多 Agent 协作通过**分而治之**解决：
- **调度 Agent**：理解用户意图，拆分任务，分发给子 Agent
- **子 Agent**：各司其职（数据分析、代码生成、文档生成）
- **聚合 Agent**：汇总各子 Agent 结果，生成最终回答

### 7.2 调度 Agent 实现

```java
@Service
public class OrchestratorAgent {

    @Autowired
    private ChatAgent dataAnalystAgent;    // 数据分析 Agent
    @Autowired
    private ChatAgent codeGeneratorAgent;    // 代码生成 Agent
    @Autowired
    private ChatAgent reportWriterAgent;    // 报告撰写 Agent

    public String handle(String request) {
        // 1. 调度 Agent 理解意图并规划
        TaskPlan plan = planTasks(request);
        // plan: [{task: "分析销售数据", agent: "dataAnalyst"}, 
        //        {task: "生成可视化代码", agent: "codeGenerator"}, 
        //        {task: "撰写报告", agent: "reportWriter"}]

        // 2. 并行执行独立任务
        CompletableFuture<String> dataFuture = 
            CompletableFuture.supplyAsync(() -> dataAnalystAgent.chat(plan.get(0).getTask()));
        CompletableFuture<String> codeFuture = 
            CompletableFuture.supplyAsync(() -> codeGeneratorAgent.chat(plan.get(1).getTask()));

        String data = dataFuture.join();
        String code = codeFuture.join();

        // 3. 聚合结果给报告 Agent
        String reportContext = String.format("数据：%s\n代码：%s", data, code);
        String report = reportWriterAgent.chat("基于以下内容撰写报告：" + reportContext);

        return report;
    }
}
```

### 7.3 Agent 间通信协议

多 Agent 的核心问题是**通信协议**——Agent 之间怎么传递结构化信息？

```java
// 用 JSON Schema 定义 Agent 间协议
public record TaskResult(
    String taskId,
    String agentId,
    String status,     // SUCCESS / FAILED / PARTIAL
    Object result,
    String error
) {}

// 子 Agent 返回统一格式
TaskResult result = new TaskResult(
    taskId, "data-analyst",
    "SUCCESS",
    Map.of("revenue", 1_000_000, "growth", "15%"),
    null
);
```

**面试点**：多 Agent 调度的两大工程问题：
1. **Agent 迷失**（Agent Oscillation）：两个 Agent 来回踢皮球，任务在 Agent 间循环而不推进。解法：加任务状态机 + 最多重分发 2 次。
2. **上下文污染**：子 Agent 的回复包含大量推理过程干扰后续 Agent。解法：设计"**结果提取器**"，只传递纯结果字段。

## 八、生产级 Agent 调优清单

| 维度 | 检查项 | 推荐做法 |
|------|--------|---------|
| **循环控制** | 最大迭代次数 | 设置 `maxIterations=10~20`，超限抛出异常 |
| **Token 控制** | 上下文长度 | 用 `TokenWindowChatMemory`，限制 maxTokens |
| **工具选择** | 工具描述质量 | 每个工具描述 100-200 字，明确输入输出 |
| **超时控制** | 工具执行超时 | 每个工具调用设 `timeout=10s` |
| **记忆管理** | 历史清理策略 | Redis TTL=24h，按 sessionId 隔离 |
| **可观测性** | 调用链路追踪 | 集成 OpenTelemetry，打印每个 Tool 的输入输出 |
| **安全** | 敏感操作审批 | 涉及金额、数据删除必须走 HITL |
| **成本** | Token 消耗监控 | 每次调用记录 input_tokens + output_tokens |

```java
// OpenTelemetry 集成：追踪 Agent 执行链路
Span span = tracer.spanBuilder("agent.execute")
    .setAttribute("agent.name", agentName)
    .setAttribute("task", userMessage)
    .startSpan();

try {
    String result = agent.chat(userMessage);
    span.setAttribute("result.length", result.length());
    return result;
} catch (Exception e) {
    span.recordException(e);
    throw e;
} finally {
    span.end();
}
```

## 九、面试高频问题

**Q1：Spring AI 的 Agent 和 LangChain4j 的 Agent 有什么区别？**

Spring AI 的 Agent 强调**与 Spring 生态的深度集成**（依赖注入、配置管理、事务语义），类型安全更好。LangChain4j 的 Agent 在工具编排和记忆管理上更成熟，社区更活跃。选型建议：已有 Spring Boot 项目选 Spring AI，追求 Agent 框架成熟度选 LangChain4j。

**Q2：如何防止 Agent 陷入死循环？**

三道防线：① `maxIterations` 硬上限；② 工具描述设计避免歧义；③ 在每次循环中传入"已执行步骤列表"，让模型自我检查。

**Q3：ChatMemory 的 Redis 方案在高并发下怎么保证一致性？**

Redis ChatMemory 用 Lua 脚本保证读-写原子性；多 Agent 写入同一 session 时用 `WATCH/MULTI` 乐观锁；读操作无需锁。

**Q4：多 Agent 的任务调度策略有哪些？**

- **顺序执行**：任务有依赖关系时串行（流水线模式）
- **并行执行**：独立子任务并行（CompletableFuture），最后聚合
- **层次调度**：调度 Agent 用 LLM 做意图路由，不需要全局队列

**Q5：生产环境 Agent 的监控指标有哪些？**

| 指标 | 含义 | 告警阈值 |
|------|------|---------|
| `agent.iterations.avg` | 平均迭代次数 | >15 → 可能陷入复杂推理 |
| `agent.tool.call.rate` | 工具调用频率 | 突然上升 → 可能工具选择异常 |
| `agent.timeout.rate` | 超时率 | >5% → 工具性能问题 |
| `agent.memory.tokens` | 平均 token 消耗 | 接近上下文窗口 → 需优化 |

---

## 下期预告

**（六）——AI应用性能优化与成本控制**：Token 消耗分析、Prompt 压缩、模型降级策略、缓存复用、流式响应体感优化、分布式推理与网关层限流。帮你在"AI好用"和"AI省钱"之间找到最优平衡点。🚀

---

> 📚 **本系列导航**
> - [（一）——ChatClient API与Prompt模板工程](/posts/Spring-AI面试八股文（一）——ChatClient-API与Prompt模板工程/)
> - [（二）——Embedding模型与向量数据库集成](/posts/Spring-AI面试八股文（二）——Embedding模型与向量数据库集成/)
> - [（三）——Function Calling与Tool Calling深入](/posts/Spring-AI面试八股文（三）——Function-Calling与Tool-Calling深入/)
> - [（四）——RAG企业级实践](/posts/Spring-AI面试八股文（四）——RAG企业级实践/)
> - [（六）——AI应用性能优化与成本控制](/posts/Spring-AI面试八股文（六）——AI应用性能优化与成本控制/)（待发布）
