---
title: Spring AI面试八股文（六）——AI网关与企业级集成：路由、限流、Prompt管理与可观测性
date: 2026-07-18 10:00:00+08:00
updated: '2026-07-18T10:00:00+08:00'
description: 深入解析Spring AI企业级集成核心：AI网关架构设计、Prompt模板注册与版本管理、Token计量与成本控制、AI工作负载限流策略、可观测性建设（Metrics/Logging/Tracing）。结合生产级实战案例与面试高频问题，掌握企业AI平台建设的工程能力。
topic: ai-engineering
series: spring-ai-interview
series_order: 6
level: intermediate
status: maintained
tags:
- Spring AI
- AI网关
- Prompt管理
- 限流
- 可观测性
categories:
- AI 工程化
draft: false
keywords:
- Spring AI
- AI Gateway
- Prompt Registry
- AI限流
- Token计费
- Micrometer
- OpenTelemetry
- 面试八股文
---

> 面试高频问题：Spring AI在企业中的网关架构怎么设计？Prompt模板如何统一管理和版本化？AI调用的Token成本怎么计量和控制？限流策略怎么做才合理？AI服务的可观测性怎么建设？本文从工程化视角全面解答。

## 引言

前五篇解决了 AI 应用的核心能力问题：
- **（一）** ChatClient 统一了对话 API，Prompt 模板基础
- **（二）** Embedding + VectorStore 解决了知识检索
- **（三）** Function Calling / Tool Calling 解决了工具调用
- **（四）** RAG 解决了知识增强
- **（五）** Agent 解决了自主行动闭环

但这些都是**单应用视角**。当 AI 能力走向**企业级**——多团队共用模型、多业务线接入、不同模型混用、成本精细管控、监管合规——就需要从**平台层**思考问题了。

本文聚焦企业 AI 平台建设的四大工程支柱：**AI 网关架构、Prompt 管理与版本化、Token 计量与成本控制、AI 可观测性建设**。

> ⚠️ **跨系列去重说明**：Spring Cloud API 网关的基础能力（路由、过滤器、熔断）在《Spring Cloud微服务架构实战》中已详细阐述，本文**不再重复**那些通用概念，重点聚焦 **AI 工作负载特有的网关扩展点**：模型智能路由、Token 感知限流、Prompt 上下文复用等。

**本文要点**：
1. AI 网关的定位与 Spring AI 集成架构
2. Prompt 注册表（Prompt Registry）：统一管理、版本化、AB 测试
3. Token 计量体系：成本控制与预算告警
4. AI 限流策略：Token 粒度 vs 请求粒度的取舍
5. AI 可观测性：Metrics + Logging + Tracing 最佳实践

---

## 一、AI 网关：企业 AI 平台的总线

### 1.1 为什么 AI 应用需要专属网关

通用 API 网关（Kong、Spring Cloud Gateway）解决的是"南北向"流量问题：路由、认证、限流。但 AI 工作负载有独特的工程挑战：

| 维度 | 通用网关关注点 | AI 网关额外关注点 |
|------|------------|----------------|
| 流量单位 | HTTP 请求数 | Token 数量（输入+输出） |
| 成本 | API 调用次数 | Token 消耗 × 单价 |
| 限流策略 | TPS / QPS | TPM（Tokens Per Minute）/ RPM |
| 路由依据 | URL 路径、Header | 模型能力、上下文长度、价格 |
| 可观测性 | 请求状态码、延迟 | Token 消耗、Token 速率、模型错误率 |
| Prompt 安全 | — | 敏感信息脱敏、审计留痕 |

### 1.2 Spring AI 集成架构

典型的企业 AI 网关架构如下：

```
┌─────────────────────────────────────────────────────────┐
│                    业务应用层                            │
│   [客服机器人]  [风控分析]  [智能写作]  [代码助手]        │
└──────────────────────┬────────────────────────────────┘
                       │ HTTP/gRPC
┌──────────────────────▼────────────────────────────────┐
│               AI Gateway（路由/限流/鉴权）                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │ 模型路由  │  │ Token限流 │  │  API Key │             │
│   └──────────┘  └──────────┘  └──────────┘             │
└──────────────────────┬────────────────────────────────┘
                       │ 模型无关协议（OpenAI兼容）
┌──────────────────────▼────────────────────────────────┐
│            模型适配层（Spring AI Client）                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│   │OpenAIClient│  │AzureClient│  │CohereClient│         │
│   └──────────┘  └──────────┘  └──────────┘             │
└──────────────────────┬────────────────────────────────┘
                       │ HTTP
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
     [GPT-4o]     [Claude]      [DeepSeek]
```

在 Spring Boot 中，AI 网关可以是一个独立的微服务，也可以内嵌为 `@Configuration` 类。核心依赖：

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-webflux</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.ai</groupId>
    <artifactId>spring-ai-openai</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

### 1.3 模型智能路由

AI 网关的核心价值之一是**根据请求特征智能选择模型**。常见的路由策略：

```java
@Service
public class ModelRouter {

    private final Map<String, ChatModel> modelRegistry;

    // 路由策略枚举
    public enum RoutingStrategy {
        CAPABILITY,   // 按能力路由（推理/创意/代码）
        COST,         // 按成本路由（便宜优先）
        LATENCY,      // 按延迟路由（快优先）
        ROUND_ROBIN   // 轮询
    }

    public ChatModel route(String strategy, RoutingContext ctx) {
        return switch (strategy.toUpperCase()) {
            case "COST" -> selectByCost(ctx);
            case "CAPABILITY" -> selectByCapability(ctx);
            case "LATENCY" -> selectByLatency(ctx);
            default -> selectRoundRobin();
        };
    }

    private ChatModel selectByCost(RoutingContext ctx) {
        // 简单查询 → 便宜模型
        if (ctx.isSimpleQuery()) {
            return modelRegistry.get("gpt-4o-mini");
        }
        // 复杂推理 → 高级模型
        return modelRegistry.get("gpt-4o");
    }

    private ChatModel selectByCapability(RoutingContext ctx) {
        return switch (ctx.getIntent()) {
            case "CODE_GENERATION" -> modelRegistry.get("claude-sonnet");
            case "MATH_REASONING" -> modelRegistry.get("gpt-4o");
            case "CREATIVE_WRITING" -> modelRegistry.get("gpt-4o");
            default -> modelRegistry.get("gpt-4o-mini");
        };
    }
}
```

路由上下文可以通过 Header 传递，AI 网关解析后注入到 ChatClient：

```java
@RestController
public class AiGatewayController {

    private final ChatClient chatClient;

    @PostMapping("/api/ai/chat")
    public String chat(@RequestBody ChatRequest request,
                       @RequestHeader(value = "X-Routing-Strategy", defaultValue = "COST") String strategy) {
        return chatClient.prompt()
                .messages(new UserMessage(request.getContent()))
                .advisors(advisor -> advisor.param("routing.strategy", strategy))
                .call()
                .content();
    }
}
```

---

## 二、Prompt 注册表：统一管理与版本化

### 2.1 为什么需要 Prompt 注册表

在单体应用中，Prompt 直接写在代码里没问题。但企业场景下：
- **多团队复用**：同一个 Prompt 被多个服务使用，改一处全量生效
- **版本控制**：Prompt 也是"代码"，需要可回滚
- **AB 测试**：不同 Prompt 版本对比效果
- **权限管理**：只有特定人员能修改生产 Prompt

Spring AI 提供了 `PromptTemplateRegistry` 机制，虽然社区还在完善，但工程实践中可以自己构建一个企业级 Prompt 注册表。

### 2.2 基础设施搭建

```java
// Prompt 模板实体
public record PromptTemplate(
    String id,           // 唯一标识
    String name,         // 业务名称
    String version,      // 版本号
    String template,     // 模板内容
    Map<String, Object> defaultParams,  // 默认参数
    PromptMetadata metadata  // 元数据（作者、创建时间）
) {}

// 版本历史
public record PromptVersion(
    String templateId,
    String version,
    String template,
    String changeLog,
    Instant createdAt,
    String createdBy
) {}
```

存储层可以用 PostgreSQL（生产）或 Redis（高性能缓存）：

```java
@Repository
public class PromptTemplateRepository {

    private final JdbcTemplate jdbc;

    public PromptTemplate findById(String id) {
        String sql = """
            SELECT * FROM prompt_templates
            WHERE id = ? AND active = true
            """;
        return jdbc.queryForObject(sql, (rs, rowNum) -> mapTemplate(rs));
    }

    public PromptTemplate findByIdAndVersion(String id, String version) {
        String sql = """
            SELECT * FROM prompt_versions
            WHERE template_id = ? AND version = ?
            """;
        return jdbc.queryForObject(sql, (rs, rowNum) -> mapTemplate(rs));
    }

    public List<PromptVersion> findHistory(String templateId) {
        return jdbc.query(
            "SELECT * FROM prompt_versions WHERE template_id = ? ORDER BY created_at DESC",
            (rs, rowNum) -> mapVersion(rs),
            templateId
        );
    }
}
```

### 2.3 Prompt 版本管理与 AB 测试

```java
@Service
public class PromptRegistry {

    private final PromptTemplateRepository repository;
    private final LoadingCache<String, PromptTemplate> cache;

    public PromptTemplate resolve(String templateId, String version, String experimentGroup) {
        String cacheKey = buildCacheKey(templateId, version, experimentGroup);
        return cache.get(cacheKey, () -> {
            PromptTemplate template = repository.findByIdAndVersion(templateId, version);
            // AB 测试：根据实验组选择变体
            if (template.hasVariants() && experimentGroup != null) {
                return template.getVariant(experimentGroup);
            }
            return template;
        });
    }

    // 灰度发布：新版本只生效10%的流量
    public PromptTemplate resolveWithRollout(String templateId, String newVersion) {
        double rollout = featureToggleService.getRollout("prompt." + templateId);
        if (Math.random() < rollout) {
            return repository.findByIdAndVersion(templateId, newVersion);
        }
        return repository.findCurrentVersion(templateId);
    }
}
```

### 2.4 Prompt 模板的 RESTful 管理 API

```java
@RestController
@RequestMapping("/api/admin/prompts")
public class PromptAdminController {

    private final PromptRegistry registry;

    // 查询当前生效版本
    @GetMapping("/{templateId}")
    public PromptTemplate getTemplate(@PathVariable String templateId) {
        return registry.findActive(templateId);
    }

    // 查询历史版本
    @GetMapping("/{templateId}/history")
    public List<PromptVersion> getHistory(@PathVariable String templateId) {
        return registry.findHistory(templateId);
    }

    // 创建新版本
    @PostMapping("/{templateId}/versions")
    @PreAuthorize("hasRole('AI_ADMIN')")
    public PromptVersion createVersion(@PathVariable String templateId,
                                        @RequestBody @Valid PromptVersionRequest request) {
        return registry.createVersion(templateId, request.version(), request.template());
    }

    // 回滚到指定版本
    @PostMapping("/{templateId}/rollback")
    @PreAuthorize("hasRole('AI_ADMIN')")
    public PromptTemplate rollback(@PathVariable String templateId,
                                   @RequestParam String targetVersion) {
        return registry.rollback(templateId, targetVersion);
    }

    // AB 测试：分配实验组
    @PostMapping("/{templateId}/experiments")
    public Experiment createExperiment(@PathVariable String templateId,
                                        @RequestBody ExperimentConfig config) {
        return experimentService.create(config);
    }
}
```

---

## 三、Token 计量与成本控制

### 3.1 为什么 Token 是 AI 计量的核心单位

大模型 API 的定价方式是 **按 Token 计费**（$0.002/1K input tokens, $0.008/1K output tokens），不是按请求数。这意味着：
- 一个包含长上下文的请求，成本可能是短请求的 100 倍
- 流式响应的总 Token 数在响应结束后才知道

所以企业必须建设 **Token 计量体系**，才能做精准成本管控。

### 3.2 Token 消费记录表设计

```sql
CREATE TABLE ai_token_usage (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        VARCHAR(64) NOT NULL,    -- 调用链路ID
    user_id         VARCHAR(64) NOT NULL,    -- 终端用户ID
    tenant_id       VARCHAR(64) NOT NULL,    -- 租户ID
    model           VARCHAR(64) NOT NULL,    -- 模型名称
    prompt_tokens   INTEGER NOT NULL,        -- 输入Token数
    completion_tokens INTEGER NOT NULL,       -- 输出Token数
    total_tokens    INTEGER NOT NULL,        -- 总Token数
    unit_price_input DECIMAL(10, 6),         -- 输入单价
    unit_price_output DECIMAL(10, 6),        -- 输出单价
    cost            DECIMAL(10, 4) NOT NULL, -- 本次消费金额
    latency_ms      INTEGER,                 -- 响应延迟
    response_status VARCHAR(32),             -- 响应状态
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_usage_tenant_date ON ai_token_usage(tenant_id, created_at);
CREATE INDEX idx_usage_user_date ON ai_token_usage(user_id, created_at);
CREATE INDEX idx_usage_model ON ai_token_usage(model, created_at);
```

### 3.3 Token 拦截器：自动计量

利用 Spring AOP 或 `ChatClient` 的 `Advisor` 机制，自动记录每次调用的 Token 消耗：

```java
// 方法一：通过 ChatClient Advisor 自动计量
@Configuration
public class TokenMeteringAdvisor {

    @Bean
    public ChatAdvisor tokenMeteringAdvisor(TokenUsageService usageService,
                                              TenantContext tenantContext) {
        return ChatAdvisor.builder()
            .streamAdvice((advice, context) -> {
                // 流式结束时统计
                context.onComplete(response -> {
                    Usage usage = response.getMetadata().getUsage();
                    TokenUsageRecord record = TokenUsageRecord.builder()
                        .traceId(getTraceId())
                        .userId(getUserId())
                        .tenantId(tenantContext.getCurrentTenant())
                        .model(response.getMetadata().getModel())
                        .promptTokens(usage.getPromptTokens())
                        .completionTokens(usage.getCompletionTokens())
                        .totalTokens(usage.getTotalTokens())
                        .cost(calculateCost(usage))
                        .latencyMs(response.getMetadata().getLatencyMs())
                        .build();
                    usageService.recordAsync(record);
                });
            })
            .build();
    }
}
```

### 3.4 成本控制策略

**策略一：用户预算控制**

```java
@Service
public class BudgetControlService {

    private final TokenUsageRepository usageRepo;
    private final AlertService alertService;

    public void checkBudget(String userId, String tenantId, int estimatedTokens) {
        // 查询本月消耗
        BigDecimal monthCost = usageRepo.sumCost(tenantId, getMonthStart());
        BigDecimal budget = getBudget(tenantId);

        if (monthCost.add(estimateCost(estimatedTokens)).compareTo(budget) > 0) {
            throw new BudgetExceededException(
                "本月预算已用尽，剩余额度：" + budget.subtract(monthCost));
        }

        // 消耗超过80%时触发告警
        double usagePercent = monthCost.divide(budget, 4, RoundingMode.HALF_UP).doubleValue();
        if (usagePercent > 0.8) {
            alertService.sendBudgetAlert(tenantId, usagePercent);
        }
    }
}
```

**策略二：Token 限流（TPM）**

```java
@Service
public class TokenRateLimiter {

    private final RedisTemplate<String, String> redis;

    // 基于滑动窗口的 Token 限流
    public boolean allow(String tenantId, int tokensToConsume) {
        String key = "ratelimit:tpm:" + tenantId;
        long now = System.currentTimeMillis();
        long windowStart = now - 60_000; // 1分钟窗口

        // 原子操作：ZADD + ZREMRANGEBYSCORE + ZCARD
        Long count = redis.execute((RedisCallback<Long>) conn -> {
            conn.zSetCommands().zAdd(key, String.valueOf(now), (double) now);
            conn.zSetCommands().zRemRangeByScore(key, 0, windowStart);
            Long size = conn.zSetCommands().zCard(key);
            conn.expire(key, Duration.ofSeconds(120));
            return size;
        });

        long tpmLimit = getTpmLimit(tenantId);
        return count + tokensToConsume <= tpmLimit;
    }

    private long getTpmLimit(String tenantId) {
        // 免费用户: 100K TPM, 付费用户: 1M TPM
        return userService.isPremium(tenantId) ? 1_000_000 : 100_000;
    }
}
```

**策略三：Prompt 压缩节省成本**

当上下文过长时，自动压缩历史消息以节省 Token：

```java
@Service
public class PromptCompressor {

    private final ChatClient chatClient;

    public List<Message> compressHistory(List<Message> history, int maxTokens) {
        int currentTokens = estimateTokens(history);
        if (currentTokens <= maxTokens) {
            return history;
        }

        // 摘要压缩：把早期消息聚合成摘要
        List<Message> compressed = new ArrayList<>();
        List<Message> summaryBuffer = new ArrayList<>();

        for (Message msg : history) {
            int tokens = estimateTokens(msg.getContent());
            if (currentTokens - tokens <= maxTokens) {
                // 剩余消息直接保留
                compressed.add(msg);
            } else {
                summaryBuffer.add(msg);
            }
        }

        // 将被压缩的消息生成摘要
        if (!summaryBuffer.isEmpty()) {
            String summary = generateSummary(summaryBuffer);
            compressed.add(0, new SystemMessage("[早期对话摘要] " + summary));
        }

        return compressed;
    }

    private String generateSummary(List<Message> messages) {
        String prompt = String.format(
            "将以下对话用50字以内的中文摘要：%s",
            messages.stream().map(Message::getContent).collect(Collectors.joining("; "))
        );
        return chatClient.prompt()
            .messages(new UserMessage(prompt))
            .system("你是一个对话摘要专家，请直接输出摘要，不要解释。")
            .call()
            .content();
    }
}
```

---

## 四、AI 可观测性建设

### 4.1 三大支柱：Metrics / Logging / Tracing

AI 工作负载的可观测性比普通微服务更复杂，因为需要关注：

```
Metrics:
  - ai.tokens.prompt (Counter, 标签: model, tenant)
  - ai.tokens.completion (Counter, 标签: model, tenant)
  - ai.tokens.total (Counter, 标签: model, tenant)
  - ai.cost.dollars (Counter, 标签: tenant)
  - ai.request.duration (Histogram, 标签: model, streaming)
  - ai.rate.limit.rejected (Counter, 标签: tenant, reason)
  - ai.model.errors (Counter, 标签: model, error_type)

Logging:
  - 请求/响应日志（脱敏后）
  - Token 消耗明细
  - 异常堆栈（模型拒绝、超时等）

Tracing:
  - 端到端 Trace（业务请求 → AI 网关 → 模型 API）
  - Span 级别：routing / tokenizing / model_call / parsing
```

### 4.2 Micrometer + Prometheus 集成

```java
@Configuration
public class AiMetricsConfig {

    @Bean
    public MeterRegistry meterRegistry(MeterRegistry registry) {
        // Token 消耗 Counter（带标签）
        MeterBinder tokensBinder = (meterRegistry) -> {
            Counter.builder("ai.tokens.total")
                .description("Total tokens consumed")
                .tag("tenant", "default")
                .register(meterRegistry);

            Counter.builder("ai.cost.dollars")
                .description("Total API cost in dollars")
                .tag("tenant", "default")
                .register(meterRegistry);
        };
        return registry;
    }
}
```

Prometheus 查询示例：

```promql
# 按租户统计 Token 消耗
sum by (tenant) (increase(ai_tokens_total[1d]))

# 按模型统计平均响应时间
histogram_quantile(0.95,
  rate(ai_request_duration_seconds_bucket[5m]) )

# 成本 Top 10 租户
topk(10,
  sum by (tenant) (increase(ai_cost_dollars[30d])) )

# 限流拒绝率
sum(rate(ai_rate_limit_rejected_total[5m]))
  / sum(rate(ai_tokens_total[5m]))
```

### 4.3 Grafana Dashboard 设计

企业 AI 监控大盘至少需要以下 Panel：

1. **实时 Token 消耗**：堆叠柱状图，按租户分色
2. **模型响应延迟 P50/P95/P99**：折线图
3. **成本趋势**：面积图，30天滚动
4. **模型错误分布**：饼图（超时 / 限流 / 模型拒绝 / 解析错误）
5. **Token 速率实时监控**：热力图，展示高峰时段

### 4.4 分布式 Tracing（OpenTelemetry）

```java
@Configuration
public class AiTracingConfig {

    @Bean
    public OpenTelemetry openTelemetry() {
        return OpenTelemetrySdk.builder()
            .setTracerProvider(
                SdkTracerProvider.builder()
                    .addSpanProcessor(
                        BatchSpanProcessor.builder(OtlpGrpcSpanExporter.builder()
                            .setEndpoint("http://otel-collector:4317")
                            .build())
                        .build())
                    .build())
            .build();
    }

    @Bean
    public ChatAdvisor tracingAdvisor(Tracer tracer) {
        return ChatAdvisor.builder()
            .streamAdvice((advice, context) -> {
                Span span = tracer.spanBuilder("ai.model.call")
                    .setAttribute("model", context.getModel())
                    .setAttribute("estimated_tokens", context.getEstimatedTokens())
                    .startSpan();
                try (Scope ignored = span.makeCurrent()) {
                    return response -> {
                        span.setAttribute("response_tokens",
                            response.getMetadata().getUsage().getTotalTokens());
                        span.end();
                        return response;
                    };
                } catch (Exception e) {
                    span.recordException(e);
                    span.end();
                    throw e;
                }
            })
            .build();
    }
}
```

---

## 五、综合面试高频问题

### Q1：AI 网关和普通 API 网关的核心区别是什么？

**参考答案**：普通 API 网关以**请求数**为单位，AI 网关以 **Token 数**为单位。主要区别体现在：
- **计量维度**：AI 网关需要解析模型响应中的 Token 使用量，普通网关不需要
- **成本路由**：可根据模型价格动态路由（如简单查询走 GPT-4o-mini），普通网关无此场景
- **限流精度**：TPM（Tokens Per Minute）比 QPS 更精准，避免短请求无限流但长请求瞬间打爆
- **Prompt 上下文**：需要处理超长上下文截断、压缩等 AI 特有逻辑

### Q2：如何防止用户通过 Prompt 注入攻击套取敏感信息？

**参考答案**：Prompt 注入是 AI 应用特有的安全风险。防御策略包括：
- **输入过滤**：检测并标记用户输入中的注入特征（如 `Ignore previous instructions`）
- **输出校验**：对模型输出内容进行敏感信息检测（正则/NER）
- **权限隔离**：不同权限的用户只能访问对应的知识库范围（通过 RAG 阶段过滤）
- **审计日志**：所有 AI 请求的输入输出全量记录，供安全审计

> 具体实现可参考《Spring面试八股文（七）——Spring Security安全框架与JWT认证实战》中的鉴权体系，结合 AI 特有的 Prompt 审计层。

### Q3：Token 限流和请求限流如何选型？

**参考答案**：两者各有适用场景：

| 场景 | 推荐限流方式 | 原因 |
|------|------------|------|
| 控制 API 账单成本 | Token 限流（TPM） | 按实际消耗计费，精确控制 |
| 保护下游模型服务 | 请求限流（RPM） | 模型服务端有 RPM 限制 |
| 多模型混合调用 | Token 限流 | 统一口径，可跨模型比较 |
| 突发流量防护 | 请求限流 | 请求数更容易测量和预测 |
| 生产环境推荐 | **双层限流**：RPM + TPM | 先过滤异常流量，再按消耗计费 |

### Q4：企业如何做 AI 成本分析和优化？

**参考答案**：从三个层面入手：
- **日志层**：Token 消费明细记录到 ClickHouse，按租户/模型/时间段聚合
- **分析层**：识别高消耗场景（如长上下文、重复调用、无效 RAG）
- **优化层**：Prompt 压缩 + 模型降级 + 缓存命中 + 流式优先

---

## 下期预告

**（七）——Spring AI 多模型适配与切换：从 OpenAI 到国产大模型实战**

多模型适配是企业 AI 平台的必备能力。本期将深入讲解：
- Spring AI 模型抽象层原理（ChatModel / StreamingChatModel）
- 从 OpenAI 切换到 Claude / DeepSeek / 阿里通义
- 模型能力对比与智能降级策略
- 国产大模型接入的企业级实践（DeepSeek / Qwen / 智谱 GLM）
- 统一接口下的多模型 A/B 测试与效果评估

敬请期待！🚀

---

*本文为 Spring AI 面试八股文系列第六篇，已发布：*
- *（一）ChatClient API与Prompt模板工程*
- *（二）Embedding模型与向量数据库集成*
- *（三）Function Calling与Tool Calling深入*
- *（四）RAG企业级实践*
- *（五）AI Agent开发实战*
