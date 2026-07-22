---
title: Spring AI面试八股文（三）——Function Calling与Tool Calling深入
date: 2026-07-17 09:00:00+08:00
updated: '2026-07-17T09:00:00+08:00'
description: 深入解析Spring AI 1.0的Tool Calling抽象：从@Functional到@Tool的演进、ToolCallback核心接口、MethodToolCallback反射实现、@Tool注解与参数Schema、ToolContext上下文传递、结构化输出、企业级Agent编排与安全治理。结合源码剖析与实战代码，掌握Spring
  AI工具调用的工
topic: ai-engineering
series: spring-ai-interview
series_order: 3
level: intermediate
status: maintained
tags:
- Spring AI
- Java
- AI
- Tool Calling
- Function Calling
categories:
- AI 工程化
draft: false
keywords:
- Spring AI
- Tool Calling
- Function Calling
- ToolCallback
- '@Tool'
- Agent
- 面试八股文
---

> 面试高频问题：Spring AI的Tool Calling和普通Function Calling有什么区别？`@Tool`注解怎么用？`ToolCallback`是干什么的？工具调用时如何传递用户上下文？如何在企业里安全地治理工具？本文带你从"会调用"进阶到"工程化掌控"。

## 引言

"让大模型调用工具"是AI应用从"聊天"走向"干活"的分水岭。关于 Function Calling 的通用原理（什么是工具调用、模型的 function_call 返回结构、OpenAI 的 tools 协议），我在 **《AI大模型面试八股文（四）——大模型应用开发与Agent框架》** 中已经用一整章讲透，建议先去那篇打底。

本文**不重复讲通用原理**，而是聚焦 Spring AI 1.0 自己的一套**工具调用抽象**——这是面试里最容易和"裸调 OpenAI API"区别开来的地方，也是企业落地时真正要关心的工程细节：

**本文要点**：
1. 从 `@Functional` 到 `@Tool` 的演进与动机
2. `ToolCallback` 核心接口与 `MethodToolCallback` 反射实现
3. `@Tool` 注解、参数 Schema 生成与 Bean Validation
4. `ToolContext` 上下文传递与结构化输出（`ToolMetadata`/结果转换器）
5. 企业级 Agent 编排模式与工具有效治理（安全、超时、人工确认）

---

## 一、为什么Spring AI要再做一层Tool抽象

裸调 OpenAI 的 Function Calling，你需要：
- 手动维护一个 `tools` 数组（JSON Schema 描述每个函数）；
- 解析模型返回的 `tool_calls`，自己 `switch` 分发到具体方法；
- 把方法返回值再塞回对话，再发一次请求；
- 换模型（比如从 GPT 切到 Claude）时，工具协议从 `function_call` 变成 `tool_use`，代码几乎要重写。

Spring AI 的解法是：**用一套 `ToolCallback` 抽象屏蔽底层差异**。你只需要写 Java 方法 + 注解，框架负责把方法"翻译"成各家模型能懂的工具描述，并在模型决定调用时反射执行你的方法，最后把结果回灌给模型。核心收益：
- **多模型透明**：同一套 `@Tool` 方法，GPT-4o、Claude、通义千问、Ollama 等开箱即用，无需关心各家工具协议差异。
- **类型安全**：工具入参/出参是 Java 类型，Schema 自动推导，告别手写 JSON Schema 易错问题。
- **Spring 原生**：工具可以是一个 `@Bean`、可以注入 `RestTemplate`/`FeignClient`、可以用 `@Transactional`，完全融入 Spring 生态。

---

## 二、核心抽象：ToolCallback 接口

Spring AI 1.0 把"一个工具"建模为 `ToolCallback` 接口：

```java
public interface ToolCallback {
    // 工具定义：名字、描述、输入参数的 JSON Schema
    ToolDefinition getToolDefinition();
    // 工具元数据：结果转换器、是否流式等
    ToolMetadata getToolMetadata();
    // 执行工具（给定模型生成的入参 JSON）
    ToolExecutionResult call(String toolInput);
    // 带上下文的执行（可携带调用方数据，如用户身份）
    default ToolExecutionResult call(String toolInput, ToolContext toolContext) {
        return call(toolInput);
    }
}
```

三个核心组成：
- **`ToolDefinition`**：持有 `name`、`description`、`inputSchema`（JSON Schema 字符串）。这是真正发给模型的那段"工具说明书"。
- **`ToolMetadata`**：持有可选的 `resultConverter`（`ToolCallResultConverter`），负责把 Java 返回值转成模型能理解的文本。
- **`ToolExecutionResult`**：执行结果，含 `result`（返回给模型的文本）和可选的 `metadata`。

最常见的实现是 **`MethodToolCallback`**——它基于反射，把一个 Java 对象的方法包装成工具：

企业里**最常用的是 `@Tool` 注解方式**（见下节）——框架自动扫描成 `ToolCallback`、几乎零样板代码；而 `MethodToolCallback.builder()` 适合需要动态、编程式构建工具的高级场景（例如工具元数据结构在运行时才能确定）。

---

## 三、@Tool 注解：声明式定义工具

`@Tool` 是 Spring AI 1.0 引入的声明式注解（取代了早期的 `@Functional`）。它只能标注在**返回 `void` 或具体类型**、且有具体入参的方法上：

```java
@Component
public class WeatherTools {

    // 工具名默认取方法名，这里显式指定
    @Tool(name = "getWeather",
          description = "根据城市名查询当前天气，返回温度和天气状况")
    public String getWeather(
            @ToolParam(description = "城市名称，例如：北京") String city) {
        // 实际可调用天气 API / 内部服务
        return "北京 当前 26°C，晴";
    }
}
```

关键点：
1. **方法必须非 `void` 且有具体参数**：Spring AI 靠方法签名推导输入 Schema；返回类型用于推导输出结构。
2. **`@ToolParam` 描述入参**：每个参数建议都加，模型靠这些描述决定传什么值。描述越精确，模型调用越准。
3. **自动注册为 Bean**：标注了 `@Tool` 的 Spring Bean 方法，会被 `ToolCallback` 自动配置扫描并注册。你只需把它注入 `ChatClient` 即可。
4. **对比 `@Functional`**：`@Functional` 是 1.0 前的旧注解，只能标在返回 `java.util.function.Function` 的方法上，且不支持参数级描述。`@Tool` 更直观、信息更丰富，新项目一律用 `@Tool`。

参数 Schema 的生成依赖 **Jackson** 把方法入参类型序列化成 JSON Schema；如果你给入参加了 **JSR-380（如 `@NotNull`、`@Size`）** 注解，Spring AI 会把这些约束（required、minLength 等）也写进 Schema，进一步约束模型传参。

---

## 四、把工具接入 ChatClient

`ChatClient` 提供了流畅的 `.tools()` 接入点：

```java
@Autowired
private ChatClient.Builder chatClientBuilder;
@Autowired
private WeatherTools weatherTools;

public String ask(String question) {
    return chatClientBuilder.build().prompt()
            .user(question)
            .tools(weatherTools)          // 传入 @Tool Bean，框架自动提取 ToolCallback
            .call()
            .content();
}
```

几个企业级用法：
- **按请求开关工具**：`ChatClient` 支持 `FunctionCallingOptions` / `ToolCallingChatOptions`，可在单次请求里 `withToolNames("getWeather")` 指定启用哪些工具，或 `withToolCallbacks(...)` 覆盖默认集合。避免把全部工具一股脑暴露给模型。
- **工具上下文 `ToolContext`**：通过 `.toolContext(Map<String,Object>)` 传入调用方数据（如租户ID、当前用户ID、请求TraceID）。工具方法签名里加一个 `ToolContext` 参数即可读取：

```java
@Tool(name = "queryOrder", description = "查询当前用户的一笔订单")
public String queryOrder(
        @ToolParam(description = "订单号") String orderId,
        ToolContext ctx) {                  // 框架自动注入
    String userId = ctx.getContext().get("userId").toString();
    return orderService.query(userId, orderId);  // 自动带租户隔离
}
```

`ToolContext` 是**多租户隔离与权限控制的关键**：工具自己读上下文拿到用户身份，而不是信任模型传来的 userId，避免模型（或被注入的提示词）越权访问他人数据。

---

## 五、结构化输出与结果转换

模型"看不见"你的 Java 对象，它只接收文本。工具返回的对象需要被转换成模型能理解的文本，这就是 `ToolMetadata.resultConverter` 的职责。

默认情况下，Spring AI 用 `DefaultToolCallResultConverter` 把返回值 `toString()`。但企业里更常见两种：
- **返回 POJO 并转成 JSON**：用 `BeanOutputConverter` 把对象序列化为 JSON 文本，模型能更好地消费结构化结果。
- **自定义转换器**：实现 `ToolCallResultConverter` 接口，把结果裁剪成模型真正需要的信息（避免把冗长的内部对象全塞回去，节省 token）。

```java
ToolCallback tool = MethodToolCallback.builder()
        .toolObject(orderService)
        .toolMethod(...)
        .resultConverter(new BeanOutputConverter(OrderDTO.class))  // POJO→JSON
        .build();
```

反过来，**结构化输入**（让模型按 Schema 生成入参）由 `inputType` + JSON Schema 约束，模型返回的 `toolInput` 会被框架反序列化成你的入参对象——这就是 Spring AI 工具调用"类型安全"的来源。

---

## 六、异常处理与执行语义

工具执行抛异常时，Spring AI 的行为是**把错误回传给模型**，让模型自己纠正（重试或换方案），而不是简单中断：
- 工具方法抛出 `ToolExecutionException` 时，框架捕获其 message 作为工具执行结果返回给模型；
- 未捕获的其它异常也会被兜底包装，避免整条链路 500。

企业实践建议：
- 工具内部做好**幂等**：模型可能因网络抖动/重试多次调用同一工具，写操作（下单、扣款）必须有幂等键。
- 设置**超时**：工具调用外部 HTTP 服务时，用 `RestTemplate`/`WebClient` 的超时配置，防止模型被一个慢工具拖死。
- **不要泄露内部异常细节**给模型/用户，捕获后返回业务友好的错误描述。

---

## 七、企业级 Agent 编排模式

工具齐了，如何让模型"自主多步调用"？Spring AI 1.0 既提供底层能力，也鼓励你用 `ChatClient` + 工具 + 记忆做 **ReAct 式 Agent**。一个稳健的手写循环示例：

```java
public String runAgent(String goal, String conversationId) {
    String userMsg = goal;
    for (int i = 0; i < MAX_STEPS; i++) {            // 限制最大步数，防失控
        ChatResponse resp = chatClient.prompt()
                .user(userMsg)
                .tools(allTools)                        // 注入全部工具
                .advisors(new MessageChatMemoryAdvisor( // 多轮记忆
                        new InMemoryChatMemory(), conversationId))
                .call().chatResponse();
        // 模型不再请求工具 → 返回最终答案；否则框架已自动执行工具并回灌结果
        if (resp.getResult().getOutput().getToolCalls().isEmpty())
            return resp.getResult().getOutput().getContent();
        userMsg = "请基于工具返回结果继续";
    }
    return "已达最大步数";
}
```

这个循环的关键在于：**工具执行是隐式发生的**。`call()` 一旦检测到模型返回的 `tool_calls`，会在内部自动调用对应 `ToolCallback`、把执行结果追加进消息历史、再发起新一轮请求；你的代码只需要关心"模型何时停止要工具"。这种设计让"多步推理 + 多工具协作"变得非常自然——模型可以查天气后再查航班，再综合回答，全程无需你手写调度逻辑。

要点：
- **步数上限**：Agent 必须设 `MAX_STEPS`，否则可能无限循环烧钱。
- **记忆**：用 `MessageChatMemoryAdvisor` 维持多轮上下文，让模型知道"上一步查到了什么"。
- **底层透明**：Spring AI 在 `call()` 内部检测到模型请求工具时，会自动执行 `ToolCallback.call()` 并把 `ToolExecutionResult` 追加到消息历史，再次请求模型——你不需要手动解析 `tool_calls`。

> 提示：Spring AI 1.0 也在推进更高层的 Agentic 抽象（如基于 `ChatClient` 的 Agent 编排），手写循环仍是目前最可控、面试最易讲清楚的模式。

---

## 七之一、Spring AI 工具生态与可观测

除了 `@Tool` 与 `ToolCallback`，Spring AI 还提供了一整套工具生态：你可以通过 `@Bean` 直接暴露 `ToolCallback`，框架会自动注册；`ToolCallbackResolver` 支持按名称在运行时解析工具，便于做动态路由；配合 Micrometer，框架能记录每次工具调用的耗时与成功率，接入 Prometheus/Grafana 做可观测。面试时如果能顺带提到"工具也是一等公民、可注册可观测"，会比只讲注解用法高出一个层次。

## 八、工具治理：安全的底线

把内部方法暴露给"会自己决定调用什么"的模型，是巨大的攻击面。企业落地必须：
1. **最小暴露面**：只用 `withToolNames` 暴露当前场景必需的工具，绝不把所有 `@Tool` 全挂上。
2. **参数白名单 + 校验**：用 `@ToolParam` 描述 + Bean Validation 约束模型输入；工具内部对关键入参（如 SQL、文件路径）做二次校验。
3. **租户/权限隔离**：永远通过 `ToolContext` 拿用户身份，不信任模型传来的身份字段。
4. **高危操作人工确认（HITL）**：删除、转账、发消息等工具，先返回"拟执行"信息，等人工确认后再真正执行。
5. **审计日志**：记录每次工具调用的入参、结果、耗时，便于回溯与合规。

---

## 八之一、Tool Calling 与 RAG、Agent 的关系

理清三者边界，面试时能讲出层次：
- **Tool Calling** 是"能力接口"——它让模型能调用外部函数，是 Agent 的"手"。
- **RAG** 是"知识接口"——它让模型在生成前注入私有知识，是 Agent 的"脑外记忆"。
- **Agent** 是"编排范式"——它用循环把 Tool Calling、RAG、记忆串成"感知—思考—行动"的自主流程。

在实际企业项目里，这三者常常组合：一个客服 Agent，先用 RAG 检索知识库，再用 Tool Calling 查询订单系统，最后综合作答。Spring AI 的 `ChatClient` + Advisor + `@Tool` 恰好能在一套 API 下把这三点全部串起来，这也是它相比"裸调模型 API"最大的工程价值。

## 九、面试高频问答

**Q1：Spring AI 的 Tool Calling 和直接调 OpenAI Function Calling 有何区别？**
A：Spring AI 用 `ToolCallback` 抽象屏蔽了各家模型的工具协议差异（OpenAI 的 `function_call` vs Anthropic 的 `tool_use`），你写 `@Tool` 方法即可跨模型复用；同时提供类型安全的入参反序列化、结果转换器、工具上下文 `ToolContext` 等企业能力，免去手写 JSON Schema 与手动分发。

**Q2：`@Tool` 和旧的 `@Functional` 怎么选？**
A：新项目一律 `@Tool`。`@Functional` 只能标返回 `Function` 的方法且不支持参数级描述；`@Tool` 信息更丰富、用法更直观，是 1.0 的推荐方式。

**Q3：多租户下工具怎么保证数据隔离？**
A：工具方法签名注入 `ToolContext`，从上下文读取经认证的 `userId`/`tenantId`，工具内部用该身份查数据，**绝不信任模型传入的身份参数**，从根本上防越权。

**Q4：工具执行失败了会怎样？**
A：框架捕获异常并把错误信息作为工具结果回传给模型，让模型自我纠正（重试/换方案）；你应保证工具幂等、设超时、不向模型泄露内部异常细节。

**Q5：如何防止 Agent 无限循环、乱花钱？**
A：循环编排必须设最大步数 `MAX_STEPS`；用 `withToolNames` 收敛工具面；写操作做幂等键；高危工具加人工确认。

---

## 十、下期预告

本文把"工具调用"从原理讲到工程治理。但工具只是手段，**真正的企业价值在于把"检索 + 工具 + 生成"串成一条生产级 RAG 流水线**。下一篇 **《Spring AI面试八股文（四）——RAG 企业级实践》** 将深入 Spring AI 的 Advisor 式 RAG 架构：`QuestionAnswerAdvisor` 快速上手、`spring-ai-rag` 新模块（查询改写/扩展、文档后处理、上下文增强）、元数据过滤与引用溯源（grounding with citations），帮你把"能问答"升级为"答得准、可追溯"。敬请期待！
