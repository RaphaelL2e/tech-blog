---
title: AI大模型面试八股文（四）——大模型应用开发与Agent框架
date: 2026-06-10 09:00:00+08:00
updated: '2026-06-10T09:00:00+08:00'
description: 面试高频问题：RAG的原理是什么？LangChain的核心组件有哪些？Function Calling怎么实现？Agent和普通大模型调用有什么区别？本文带你掌握大模型应用开发的核心技术栈。 前三篇我们分别聊了大模型架构、训练微调、推理部署。但模型部署上线只是起点，如何让大模型真正解决业务问题？这就。
topic: ai-engineering
series: ai-llm-interview
series_order: 4
level: intermediate
status: maintained
tags:
- AI
- 大模型
- 应用开发
- Agent
- RAG
categories:
- AI 工程化
draft: false
---

> 面试高频问题：RAG的原理是什么？LangChain的核心组件有哪些？Function Calling怎么实现？Agent和普通大模型调用有什么区别？本文带你掌握大模型应用开发的核心技术栈。

## 引言

前三篇我们分别聊了大模型架构、训练微调、推理部署。但模型部署上线只是起点，如何让大模型真正解决业务问题？这就涉及**大模型应用开发**——从RAG检索增强生成，到Agent自主决策，到大模型编排框架，这是2024-2026年最火热的技术方向之一。掌握这些，面试中"大模型怎么落地"的问题你就能对答如流。

**本文要点**：
1. Prompt Engineering 进阶技巧
2. RAG 检索增强生成
3. Function Calling 与工具使用
4. Agent 框架与自主决策
5. 主流开发框架对比

---

## 一、Prompt Engineering 进阶技巧

### 1.1 基础Prompt模式

| 模式 | 说明 | 示例 |
|------|------|------|
| Zero-shot | 不给示例，直接提问 | "请翻译以下句子" |
| Few-shot | 给几个示例再提问 | 给2-3个翻译示例后翻译新句子 |
| Chain-of-Thought | 要求分步推理 | "请一步步思考" |
| Self-Consistency | 多次采样取多数 | 多次推理后投票选最常见答案 |

### 1.2 高级Prompt技巧

**ReAct模式（Reasoning + Acting）**：

```
Thought: 我需要查找当前天气
Action: search("北京天气")
Observation: 北京今天晴，28°C
Thought: 现在我可以回答了
Answer: 北京今天晴天，气温28°C
```

**结构化输出**：
```json
{
  "name": "张三",
  "age": 25,
  "skills": ["Python", "Java"]
}
```

通过在Prompt中指定JSON Schema，可以让大模型输出结构化数据，这是Function Calling的基础。

**多轮对话管理**：
- System Prompt：设定角色和行为规则
- Few-shot examples：嵌入对话历史中
- 上下文窗口管理：截断、摘要、滑动窗口

### 1.3 面试高频问题

**Q: Chain-of-Thought为什么有效？**

A: CoT有效的核心原因是：
1. **分解复杂推理**：将多步推理分解为逐步计算，降低每步难度
2. **中间结果缓存**：前一步的输出作为后一步的输入，类似程序中的中间变量
3. **注意力分散缓解**：避免模型在长距离推理中丢失关键信息
4. **训练数据分布匹配**：人类解答过程也是分步的，CoT更接近预训练数据分布

**Q: Few-shot的选择策略有哪些？**

A: 主要策略包括：
1. **随机选择**：简单但效果不稳定
2. **相似度选择**：用Embedding计算与输入最相似的示例（KNN策略）
3. **多样性选择**：覆盖不同类别，避免偏差
4. **复杂度递进**：从简单到复杂排列示例

---

## 二、RAG 检索增强生成

### 2.1 RAG核心原理

RAG（Retrieval-Augmented Generation）的核心思想：**让大模型在回答时能参考外部知识，而不是仅依赖训练数据**。

```
用户提问 → 检索相关文档 → 拼接到Prompt → 大模型生成回答
```

**为什么需要RAG？**
- 大模型知识有截止日期（训练数据的时间边界）
- 专业知识更新频繁（法律、医疗、金融）
- 企业私有数据大模型未见过
- 减少幻觉（Hallucination）

### 2.2 RAG架构详解

#### 基础RAG流程

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  文档切分    │ ──→ │  Embedding    │ ──→ │  向量数据库  │
│  Chunking    │     │  向量化       │     │  Vector DB  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                  │
┌─────────────┐     ┌──────────────┐              │ 检索
│  用户查询    │ ──→ │  Query       │ ──→ ────────┘
│  Query       │     │  Embedding   │
└──────┬──────┘     └──────────────┘
       │
       │ + 检索结果
       ↓
┌─────────────┐     ┌──────────────┐
│  Prompt组装  │ ──→ │  LLM生成     │ ──→ 最终回答
└─────────────┘     └──────────────┘
```

#### 文档切分策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 固定长度切分 | 按字符/Token数切 | 简单文档 |
| 递归字符切分 | 按分隔符层级切 | 通用场景 |
| 语义切分 | 按Embedding相似度切 | 高质量需求 |
| 文档结构切分 | 按标题/段落切 | Markdown/HTML |

**Chunk大小选择**：
- 太小（<200 Token）：上下文不完整
- 太大（>2000 Token）：检索精度下降、Token浪费
- 推荐：500-1000 Token，重叠100-200 Token

### 2.3 向量数据库对比

| 数据库 | 类型 | 特点 | 适用场景 |
|--------|------|------|----------|
| Chroma | 嵌入式 | 轻量、Python原生 | 原型开发 |
| FAISS | 库 | Meta开源、速度快 | 大规模检索 |
| Milvus | 分布式 | 云原生、可扩展 | 生产环境 |
| Pinecone | 云服务 | 全托管、零运维 | 快速上线 |
| Weaviate | 独立服务 | 支持混合搜索 | 语义+关键词 |
| Qdrant | 独立服务 | Rust实现、高性能 | 高并发场景 |

### 2.4 高级RAG技术

**混合检索（Hybrid Search）**：
- 向量检索（语义相似）+ 关键词检索（精确匹配）
- 用RRF（Reciprocal Rank Fusion）融合结果
- 效果通常优于单一检索

**重排序（Re-ranking）**：
- 初检索取Top-K（K较大，如20-50）
- 用Cross-Encoder精排，取Top-N（N较小，如5）
- 牺牲速度换精度

**Query改写与扩展**：
- HyDE：让LLM生成假设性回答，用回答的Embedding去检索
- Multi-Query：将一个问题改写为多个子问题，分别检索后合并
- Step-back Prompting：先问抽象层面的上位问题

**Self-RAG**：
- 模型自主决定是否需要检索
- 检索后评估文档相关性
- 评估生成回答是否充分

### 2.5 面试高频问题

**Q: RAG和微调（Fine-tuning）怎么选？**

A:
| 维度 | RAG | Fine-tuning |
|------|-----|-------------|
| 知识更新 | 实时更新 | 需重新训练 |
| 成本 | 低 | 高 |
| 可解释性 | 可追溯来源 | 黑盒 |
| 风格适配 | 弱 | 强 |
| 私有数据 | 天然支持 | 需构建数据集 |
| 幻觉控制 | 较好 | 一般 |

实践中常**结合使用**：Fine-tuning调整模型风格和能力，RAG注入动态知识。

**Q: 如何评估RAG效果？**

A: RAGAS框架提供核心指标：
1. **Context Precision**：检索内容中相关信息的精度
2. **Context Recall**：回答所需信息被检索到的比例
3. **Faithfulness**：回答是否忠于检索内容（无幻觉）
4. **Answer Relevance**：回答与问题的相关性

---

## 三、Function Calling 与工具使用

### 3.1 Function Calling原理

Function Calling让大模型能够**调用外部工具**，是Agent能力的基础。

```
用户提问 → LLM判断需要调用工具 → 输出工具调用请求（JSON）
→ 程序执行工具 → 将结果返回LLM → LLM生成最终回答
```

**OpenAI Function Calling示例**：

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["city"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "北京天气怎么样？"}],
    tools=tools
)

# 模型返回 tool_calls
if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    # 执行函数，将结果返回模型
    result = get_weather(city="北京")
```

### 3.2 并行工具调用

大模型可以同时调用多个工具：

```python
# 用户问："北京和上海的天气怎么样？"
# 模型可能同时返回两个tool_calls：
tool_calls = [
    {"function": {"name": "get_weather", "arguments": '{"city": "北京"}'}},
    {"function": {"name": "get_weather", "arguments": '{"city": "上海"}'}}
]
```

### 3.3 工具设计最佳实践

1. **描述要精确**：Function的description是模型理解工具的唯一依据
2. **参数要明确**：类型、枚举值、必填项要清晰定义
3. **粒度要适中**：一个工具做一件事，避免大而全
4. **错误处理**：工具执行失败时返回有意义的错误信息
5. **幂等性**：相同参数多次调用结果一致（GET类天然幂等）

### 3.4 MCP（Model Context Protocol）

MCP是Anthropic提出的开放协议，标准化大模型与外部工具的交互：

```
┌────────┐    MCP协议    ┌────────────┐    本地/API    ┌──────────┐
│  LLM   │ ←──────────→ │ MCP Server │ ←───────────→ │ 外部工具  │
└────────┘              └────────────┘              └──────────┘
```

- **统一接口**：不同工具通过MCP Server暴露统一API
- **双向通信**：支持请求-响应和流式推送
- **安全沙箱**：工具在受控环境中执行

---

## 四、Agent 框架与自主决策

### 4.1 什么是Agent？

Agent = LLM + 记忆 + 工具 + 规划

```
         ┌──────────────────────────┐
         │        Agent Core        │
         │  ┌────────────────────┐  │
         │  │   LLM (Brain)      │  │
         │  └────────────────────┘  │
         │  ┌────────────────────┐  │
         │  │   Memory (记忆)     │  │
         │  │  - 短期：对话上下文  │  │
         │  │  - 长期：向量数据库  │  │
         │  └────────────────────┘  │
         │  ┌────────────────────┐  │
         │  │   Planning (规划)   │  │
         │  │  - 任务分解         │  │
         │  │  - 执行计划         │  │
         │  └────────────────────┘  │
         │  ┌────────────────────┐  │
         │  │   Tools (工具)      │  │
         │  │  - 搜索、代码执行    │  │
         │  │  - API调用、文件操作  │  │
         │  └────────────────────┘  │
         └──────────────────────────┘
```

### 4.2 Agent vs 普通LLM调用

| 维度 | 普通LLM调用 | Agent |
|------|------------|-------|
| 执行流程 | 单次问答 | 多步推理+行动循环 |
| 工具使用 | 无/简单Function Call | 自主选择和组合工具 |
| 记忆 | 仅对话上下文 | 短期+长期记忆 |
| 目标 | 回答问题 | 完成任务 |
| 自主性 | 被动 | 主动规划 |

### 4.3 主流Agent模式

**ReAct Agent**：
```
while not done:
    thought = LLM.think(observation)    # 思考
    action = LLM.decide(thought)        # 决策
    observation = execute(action)        # 执行并观察
```

**Plan-and-Execute Agent**：
```
plan = LLM.create_plan(goal)           # 制定计划
for step in plan:
    result = execute(step)              # 逐步执行
    if need_replan(result):
        plan = LLM.replan(plan, result) # 必要时重规划
```

**Multi-Agent**：
- 多个Agent协作，各司其职
- 典型模式：Supervisor + Workers
- 例子：Coder Agent + Reviewer Agent + Tester Agent

### 4.4 Agent开发关键问题

**工具选择问题**：
- 工具太多→模型选择困难→给每个工具加详细描述+分类
- 工具太少→能力受限→按需扩展

**循环控制**：
- 最大迭代次数限制（防无限循环）
- 重复检测（连续相同动作强制终止）
- 超时控制

**记忆管理**：
- 短期记忆：对话历史，滑动窗口
- 长期记忆：向量数据库存储经验
- 工作记忆：当前任务状态

---

## 五、主流开发框架对比

### 5.1 框架全景

| 框架 | 定位 | 语言 | 特点 |
|------|------|------|------|
| LangChain | 全栈框架 | Python/JS | 生态最全，学习曲线陡 |
| LlamaIndex | RAG专用 | Python | 数据索引最强 |
| CrewAI | Multi-Agent | Python | 角色扮演式协作 |
| AutoGen | Multi-Agent | Python | 微软出品，对话式协作 |
| Semantic Kernel | 企业级 | C#/Python | 微软出品，.NET友好 |
| Dify | 低代码平台 | - | 可视化编排，快速搭建 |
| Coze | 低代码平台 | - | 字节出品，国内友好 |

### 5.2 LangChain核心架构

```
LangChain
├── Model I/O         # 模型调用统一接口
│   ├── Prompts       # Prompt模板管理
│   ├── LLMs          # 文本补全模型
│   └── Chat Models   # 对话模型
├── Retrieval         # RAG检索链
│   ├── Document Loaders  # 文档加载
│   ├── Text Splitters   # 文本切分
│   ├── Embeddings       # 向量化
│   └── Vector Stores    # 向量存储
├── Chains            # 调用链编排
│   ├── Sequential    # 顺序链
│   ├── Router        # 路由链
│   └── Transform     # 转换链
├── Agents            # 智能体
│   ├── Toolkits      # 工具集
│   └── Executors     # 执行器
└── Memory            # 记忆管理
    ├── Buffer        # 缓冲记忆
    ├── Summary       # 摘要记忆
    └── KG            # 知识图谱记忆
```

**LangChain vs LangGraph**：
- LangChain：Chain式编排，线性流程
- LangGraph：图式编排，支持循环和分支，更适合Agent

### 5.3 LlamaIndex核心能力

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# 5行代码实现RAG
documents = SimpleDirectoryReader("data").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()
response = query_engine.query("什么是RAG？")
print(response)
```

LlamaIndex的优势：
1. **索引结构丰富**：向量索引、关键词索引、树索引、知识图谱索引
2. **查询引擎灵活**：子问题查询、路由查询、流式查询
3. **数据连接器多**：支持100+数据源

### 5.4 面试高频问题

**Q: LangChain和LlamaIndex怎么选？**

A:
- 需要RAG → LlamaIndex（数据索引更强）
- 需要Agent → LangChain/LangGraph（编排能力更强）
- 需要全栈 → LangChain（覆盖面更广）
- 实践中常**组合使用**：LlamaIndex做检索，LangChain做编排

**Q: 如何评估Agent效果？**

A: 核心评估维度：
1. **任务完成率**：能否成功完成目标任务
2. **步骤效率**：完成任务的步骤数（越少越好）
3. **工具使用准确率**：是否选择了正确的工具和参数
4. **鲁棒性**：面对异常输入时的表现
5. **成本效率**：Token消耗与完成质量的比例

---

## 六、大模型应用开发最佳实践

### 6.1 架构设计原则

1. **LLM作为编排者，不是执行者**：让LLM做决策，具体执行交给确定性代码
2. **Fail-Fast**：工具调用失败快速反馈，避免错误累积
3. **可观测性**：记录每步的输入输出，便于调试和优化
4. **降级策略**：LLM调用失败时有兜底方案
5. **缓存为王**：相似查询缓存结果，降低成本和延迟

### 6.2 生产环境注意事项

- **速率限制**：LLM API有QPS限制，需要做队列和限流
- **Token预算**：设置最大Token消耗，防止单次请求失控
- **内容安全**：输入输出都要过安全审核
- **版本管理**：Prompt也是代码，需要版本控制
- **A/B测试**：不同Prompt策略的效果对比

### 6.3 成本优化

| 策略 | 说明 | 节省比例 |
|------|------|----------|
| 模型分级 | 简单问题用小模型，复杂问题用大模型 | 40-60% |
| 缓存 | 相同/相似查询直接返回 | 20-40% |
| 批处理 | 合并多次调用为一次 | 10-20% |
| Prompt优化 | 精简Prompt减少Token | 10-30% |
| 流式输出 | 边生成边返回，减少等待 | 体验提升 |

---

## 总结

| 技术栈 | 核心价值 | 适用场景 |
|--------|----------|----------|
| Prompt Engineering | 低成本调优模型输出 | 快速原型、简单任务 |
| RAG | 动态知识注入 | 知识库问答、文档分析 |
| Function Calling | 扩展模型能力边界 | 工具调用、API集成 |
| Agent | 自主任务完成 | 复杂多步任务、自动化 |
| 开发框架 | 工程化开发 | 生产级应用 |

**学习路径建议**：Prompt Engineering → RAG → Function Calling → Agent → 框架实践

---

> 📌 **下期预告**：《AI大模型面试八股文（五）——大模型安全、对齐与前沿趋势》将深入RLHF对齐原理、大模型安全攻防、多模态融合、长上下文技术等前沿话题，敬请期待！
