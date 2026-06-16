---
title: "AI大模型面试八股文（六）——大模型系统设计与工程实践"
date: 2026-06-14T10:00:00+08:00
draft: false
categories: ["AI"]
tags: ["AI", "大模型", "系统设计", "RAG", "推理系统", "评测", "工程实践", "面试"]
---

# AI大模型面试八股文（六）——大模型系统设计与工程实践

> 面试高频问题：如何设计一个RAG系统？在线推理和离线推理有什么区别？大模型如何评测？如何设计一个多轮对话系统？本文带你掌握大模型系统设计与工程实践的核心知识。

---

## 一、RAG系统架构设计

### 1.1 RAG基本原理

**Q: 什么是RAG？为什么要用RAG？**

A: RAG(Retrieval-Augmented Generation)是将检索与生成结合的架构：

```
用户问题 → Query处理 → 检索 → 上下文增强 → LLM生成 → 回答
              │           │          │
              ↓           ↓          ↓
         Query改写    向量检索    Prompt组装
         Query分解    混合检索    上下文窗口管理
         意图识别     重排序      引用溯源
```

**为什么需要RAG？**

| 问题 | RAG的解决方案 |
|------|-------------|
| 幻觉(Hallucination) | 基于真实文档生成，减少编造 |
| 知识过时 | 检索最新文档，无需重训练 |
| 领域专业性 | 检索专业文档库，提供准确信息 |
| 长尾知识 | 小众信息也能检索到 |
| 可追溯性 | 可以引用来源，支持验证 |
| 成本 | 无需微调，部署成本低 |

### 1.2 RAG系统架构设计

**Q: 如何设计一个生产级RAG系统？**

A: 完整的RAG系统包含以下模块：

```
┌──────────────────────────────────────────────────┐
│                   RAG System                      │
│                                                   │
│  ┌─────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │ Ingestion│  │ Retrieval│  │   Generation    │ │
│  │ Pipeline │  │ Pipeline │  │    Pipeline     │ │
│  │          │  │          │  │                 │ │
│  │ 文档加载 │  │ Query处理│  │ Prompt组装     │ │
│  │ 文档解析 │  │ 向量检索 │  │ 上下文管理     │ │
│  │ 文本分块 │  │ 关键词检索│  │ LLM调用       │ │
│  │ 向量化   │  │ 混合检索 │  │ 流式输出       │ │
│  │ 索引构建 │  │ 重排序   │  │ 引用溯源       │ │
│  │ 元数据   │  │ 结果过滤 │  │ 后处理         │ │
│  └─────────┘  └──────────┘  └─────────────────┘ │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │            Evaluation & Monitoring           │ │
│  │  检索质量评估 | 生成质量评估 | 端到端评估   │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

**Ingestion Pipeline（数据摄入）：**

```python
# 1. 文档加载与解析
from langchain.document_loaders import (
    PyPDFLoader,          # PDF
    UnstructuredHTMLLoader,  # HTML
    Docx2txtLoader,       # Word
    CSVLoader,            # CSV
    DirectoryLoader,      # 批量加载
)

# 2. 文本分块策略
from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    TokenTextSplitter,
)

# 按语义分块（推荐）
splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
)

# 按Markdown标题分块
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
)

# 3. 向量化
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma, FAISS, Pinecone

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db"
)
```

### 1.3 高级检索策略

**Q: 如何提升RAG的检索质量？**

| 策略 | 原理 | 适用场景 |
|------|------|---------|
| 混合检索 | 向量+关键词(BM25)融合 | 精确匹配+语义匹配 |
| Query改写 | 优化原始查询 | 查询模糊/口语化 |
| HyDE | 用LLM生成假设文档再检索 | 语义鸿沟问题 |
| Self-RAG | 模型自主决定是否检索 | 简单问题无需检索 |
| 多路召回 | 多种检索方式并行 | 提高召回率 |
| 父子文档 | 检索小块，返回大块 | 需要更多上下文 |

```python
# 混合检索示例
from langchain.retrievers import EnsembleRetriever
from langchain.retrievers import BM25Retriever

# 向量检索
vector_retriever = vectorstore.as_retriever(
    search_type="mmr",       # 最大边际相关性(去重)
    search_kwargs={"k": 10, "fetch_k": 20}
)

# BM25关键词检索
bm25_retriever = BM25Retriever.from_documents(chunks, k=10)

# 混合检索
ensemble_retriever = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.6, 0.4]     # 向量60%，关键词40%
)

# 重排序
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank

compressor = CohereRerank(top_n=5)
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=ensemble_retriever
)
```

### 1.4 RAG评估指标

**Q: 如何评估RAG系统质量？**

A: RAG评估分三个维度（RAGAS框架）：

| 维度 | 指标 | 说明 |
|------|------|------|
| 检索质量 | Context Precision | 检索到的内容中相关内容的比例 |
| 检索质量 | Context Recall | 回答问题所需的上下文被检索到的比例 |
| 生成质量 | Faithfulness | 生成内容与检索上下文的一致性 |
| 生成质量 | Answer Relevance | 回答与问题的相关性 |
| 端到端 | Answer Correctness | 回答与标准答案的相似度 |
| 端到端 | Answer Similarity | 语义相似度评分 |

---

## 二、大模型推理系统设计

### 2.1 在线推理 vs 离线推理

**Q: 在线推理和离线推理系统的区别？**

| 特性 | 在线推理 | 离线推理 |
|------|---------|---------|
| 延迟要求 | 低延迟(100ms-5s) | 无严格要求 |
| 吞吐 | 中等 | 高吞吐优先 |
| 请求模式 | 随机到达 | 批量处理 |
| GPU利用率 | 低(请求不均匀) | 高(批量填充) |
| 典型场景 | 聊天、搜索 | 数据标注、摘要生成 |
| 成本 | 高(常驻) | 低(按需) |

### 2.2 推理优化技术

**Q: 大模型推理有哪些优化技术？**

A: 核心优化技术分层：

```
┌───────────────────────────────────────┐
│          应用层优化                     │
│  缓存 | 前缀共享 | 语义路由            │
├───────────────────────────────────────┤
│          模型层优化                     │
│  量化 | 蒸馏 | 剪枝 | 稀疏化           │
├───────────────────────────────────────┤
│          系统层优化                     │
│  连续批处理 | PagedAttention | 调度     │
├───────────────────────────────────────┤
│          硬件层优化                     │
│  GPU集群 | Tensor并行 | 流水线并行      │
└───────────────────────────────────────┘
```

**关键优化详解：**

**1. KV Cache + PagedAttention：**

```
传统推理：
┌────────────────────────────┐
│ 预分配最大KV缓存 → 显存浪费 │
└────────────────────────────┘

PagedAttention(vLLM)：
┌────────────────────────────┐
│ 按需分配KV块 → 显存高效利用 │
│ 类似OS虚拟内存的分页管理     │
└────────────────────────────┘

KV Block Table:
Block 1: [token1-16]
Block 2: [token17-32]
Block 3: [token33-48]  ← 动态分配
```

**2. 连续批处理(Continuous Batching)：**

```
传统批处理：
Request A: [生成中......][生成完][空闲.......]
Request B: [等待........][生成中......][生成完]

连续批处理：
Request A: [生成中......][完成移出]
Request B: [生成中......][生成中......][完成移出]
Request C: [新加入......][生成中......][生成中..]
                    ↑ 新请求随时加入
```

**3. 模型量化：**

| 方法 | 精度 | 压缩比 | 质量损失 | 适用 |
|------|------|--------|---------|------|
| FP16 | 16bit | 1x | 无 | 基准 |
| INT8 | 8bit | 2x | 极小 | 生产推荐 |
| INT4(GPTQ) | 4bit | 4x | 小 | 消费级GPU |
| AWQ | 4bit | 4x | 小 | 注意力权重量化 |
| GGUF | 4-8bit | 2-4x | 可控 | CPU推理 |

### 2.3 推理系统架构

**Q: 如何设计高可用的大模型推理服务？**

```
                    ┌─────────────┐
                    │  API Gateway │
                    │  限流/路由   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐┌────┴─────┐┌────┴─────┐
        │ Inference  ││Inference ││Inference │
        │  Worker 1  ││ Worker 2 ││ Worker 3 │
        │ (vLLM/A100)││(TGI/L40S)││(vLLM/H100)│
        └─────┬─────┘└────┬─────┘└────┬─────┘
              │            │            │
        ┌─────┴────────────┴────────────┴─────┐
        │           Model Store / S3            │
        │      模型权重存储 + 版本管理          │
        └──────────────────────────────────────┘
```

```yaml
# K8s部署示例
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-inference
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        resources:
          limits:
            nvidia.com/gpu: 1
        env:
        - name: MODEL
          value: "Qwen/Qwen2.5-72B-Instruct-GPTQ-Int4"
        - name: GPU_MEMORY_UTILIZATION
          value: "0.9"
        - name: MAX_MODEL_LEN
          value: "8192"
        ports:
        - containerPort: 8000
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 120
---
apiVersion: v1
kind: Service
metadata:
  name: llm-service
spec:
  selector:
    app: llm-inference
  ports:
  - port: 80
    targetPort: 8000
```

---

## 三、大模型评测体系

### 3.1 评测维度

**Q: 如何全面评测一个大模型？**

A: 评测体系分为四大维度：

| 维度 | 评测内容 | 代表性基准 |
|------|---------|-----------|
| 能力 | 知识、推理、代码、数学 | MMLU, GSM8K, HumanEval |
| 对齐 | 安全性、有用性、诚实性 | TruthfulQA, C-Eval |
| 效率 | 速度、显存、成本 | 推理延迟、吞吐量 |
| 鲁棒性 | 对抗攻击、分布外数据 | AdvGLUE, FlipGrip |

### 3.2 主流评测基准

**Q: 常见的大模型评测基准有哪些？**

| 基准 | 类型 | 规模 | 测试能力 |
|------|------|------|---------|
| MMLU | 多选 | 57科目/14K题 | 综合知识 |
| GSM8K | 数学 | 8.5K题 | 数学推理 |
| HumanEval | 代码 | 164题 | 代码生成 |
| MATH | 数学 | 12K题 | 高等数学 |
| C-Eval | 中文多选 | 52科目/13.9K题 | 中文综合 |
| CMMLU | 中文多选 | 67科目/11.5K题 | 中文综合 |
| AGIEval | 考试 | 20K题 | 人类考试 |
| BBH | 推理 | 23任务 | 高难度推理 |
| MT-Bench | 对话 | 80题(8类) | 多轮对话 |
| Arena | 人类偏好 | 开放 | 对话质量 |

### 3.3 自动评测框架

```python
# 使用OpenCompass评测
from opencompass import Runner

# 配置评测任务
config = dict(
    models=[dict(type='HuggingFace', path='Qwen/Qwen2.5-72B-Instruct')],
    datasets=[
        dict(type='MMLU'),
        dict(type='GSM8K'),
        dict(type='HumanEval'),
        dict(type='C-Eval'),
    ],
)

runner = Runner(config)
runner.run()

# 使用lm-eval-harness
# lm_eval --model hf --model_args pretrained=Qwen/Qwen2.5-72B-Instruct \
#   --tasks mmlu,gsm8k,humaneval --batch_size 8
```

### 3.4 LLM-as-Judge

**Q: 用LLM做评测有哪些方法？**

| 方法 | 说明 | 优缺点 |
|------|------|--------|
| 单点评分 | LLM给回答打1-5分 | 简单但不稳定 |
| 成对比较 | 两个回答让LLM选更好的 | 更稳定，Arena方法 |
| 参考对比 | 与标准答案对比 | 需要标准答案 |
| 多Judge投票 | 多个LLM投票/人类+LLM | 减少偏差 |

```python
# LLM-as-Judge示例
judge_prompt = """
你是一个公正的评委。请评估以下回答的质量。

问题：{question}
回答A：{answer_a}
回答B：{answer_b}

评估标准：
1. 准确性：信息是否正确
2. 完整性：是否完整回答了问题
3. 清晰性：表达是否清晰易懂
4. 有用性：对用户是否有实际帮助

请输出JSON格式：
{{
    "winner": "A" | "B" | "tie",
    "reason": "选择理由",
    "scores": {{"A": {{"accuracy": 1-5, "completeness": 1-5}}, 
               "B": {{"accuracy": 1-5, "completeness": 1-5}}}}
}}
"""
```

---

## 四、多轮对话系统设计

### 4.1 对话系统架构

**Q: 如何设计一个多轮对话系统？**

```
┌───────────────────────────────────────────────┐
│              Multi-turn Dialog System          │
│                                                │
│  ┌──────────┐    ┌───────────┐    ┌────────┐ │
│  │  Dialog   │    │  Context  │    │  LLM   │ │
│  │ Manager   │───→│  Manager  │───→│ Engine │ │
│  │           │    │           │    │        │ │
│  │ 意图识别  │    │ 历史压缩  │    │ 生成   │ │
│  │ 状态跟踪  │    │ 槽位填充  │    │ 流式   │ │
│  │ 对话策略  │    │ 上下文窗口│    │ 工具   │ │
│  └──────────┘    └───────────┘    └────────┘ │
│       │                               │        │
│       └──────────┬────────────────────┘        │
│                  │                              │
│            ┌─────┴─────┐                       │
│            │  Memory   │                       │
│            │ 短期/长期 │                       │
│            └───────────┘                       │
└───────────────────────────────────────────────┘
```

### 4.2 上下文窗口管理

**Q: 如何管理长对话的上下文窗口？**

A: 对话历史可能超过模型上下文窗口，需要策略管理：

| 策略 | 原理 | 优缺点 |
|------|------|--------|
| 滑动窗口 | 保留最近N轮 | 简单但丢失早期信息 |
| 摘要压缩 | LLM压缩历史 | 保留要点但可能丢失细节 |
| 混合策略 | 摘要+最近原文 | 平衡效果，生产推荐 |
| 向量检索 | 按需检索历史 | 灵活但增加延迟 |

```python
# 混合上下文管理
class ContextManager:
    def __init__(self, max_tokens=8192, recent_turns=4):
        self.max_tokens = max_tokens
        self.recent_turns = recent_turns
        self.summary = ""
        self.recent_messages = []
    
    def add_message(self, role, content):
        self.recent_messages.append({"role": role, "content": content})
        
        # 当超出token限制时，压缩旧消息
        if self._estimate_tokens() > self.max_tokens * 0.8:
            self._compress_old_messages()
    
    def _compress_old_messages(self):
        # 保留最近N轮，其余压缩为摘要
        to_compress = self.recent_messages[:-self.recent_turns * 2]
        self.recent_messages = self.recent_messages[-self.recent_turns * 2:]
        
        # 用LLM生成摘要
        new_summary = llm.summarize(
            f"之前对话摘要：{self.summary}\n"
            f"新对话：{to_compress}\n"
            f"请生成更新后的摘要"
        )
        self.summary = new_summary
    
    def get_context(self):
        context = []
        if self.summary:
            context.append({
                "role": "system",
                "content": f"之前的对话摘要：{self.summary}"
            })
        context.extend(self.recent_messages)
        return context
```

### 4.3 Function Calling与工具使用

**Q: 如何实现LLM的工具调用？**

```python
# OpenAI Function Calling
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "搜索数据库中的记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL查询语句"},
                    "database": {"type": "string", "enum": ["users", "orders", "products"]}
                },
                "required": ["query", "database"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "发送邮件",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "收件人"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"}
                },
                "required": ["to", "subject", "body"]
            }
        }
    }
]

# 调用流程
def chat_with_tools(messages):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    message = response.choices[0].message
    
    # 如果模型决定调用工具
    if message.tool_calls:
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            # 执行工具
            result = execute_function(function_name, function_args)
            
            # 将结果返回给模型
            messages.append(message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            })
        
        # 递归调用，让模型基于工具结果继续
        return chat_with_tools(messages)
    
    return message.content
```

---

## 五、Prompt工程进阶

### 5.1 高级Prompt技术

**Q: 生产中常用的Prompt工程技术？**

| 技术 | 原理 | 适用场景 |
|------|------|---------|
| CoT(Chain of Thought) | 分步推理 | 数学、逻辑 |
| Few-shot | 给出示例 | 格式化输出 |
| Self-Consistency | 多次采样取多数 | 提高准确性 |
| ToT(Tree of Thought) | 搜索式推理 | 复杂决策 |
| ReAct | 推理+行动交替 | Agent场景 |
| DSPy | 编程化Prompt | 自动优化 |

```python
# DSPy - 编程化Prompt优化
import dspy

lm = dspy.OpenAI(model="gpt-4")
dspy.settings.configure(lm=lm)

class RAGProgram(dspy.Module):
    def __init__(self):
        self.retrieve = dspy.Retrieve(k=5)
        self.generate = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        context = self.retrieve(question).passages
        return self.generate(context=context, question=question)

# 自动优化
from dspy.teleprompt import BootstrapFewShot
optimizer = BootstrapFewShot(metric=answer_accuracy)
optimized_program = optimizer.compile(RAGProgram(), trainset=train_examples)
```

### 5.2 结构化输出

```python
# 使用Instructor确保结构化输出
import instructor
from pydantic import BaseModel

class QAOutput(BaseModel):
    question: str
    answer: str
    confidence: float
    sources: list[str]
    follow_up_questions: list[str]

client = instructor.from_openai(OpenAI())

result = client.chat.completions.create(
    model="gpt-4",
    response_model=QAOutput,
    messages=[{"role": "user", "content": "解释什么是RAG？"}],
)
# result 是类型安全的 QAOutput 对象
```

---

## 六、LLM应用监控与运维

### 6.1 关键监控指标

**Q: LLM应用需要监控哪些指标？**

| 类别 | 指标 | 说明 |
|------|------|------|
| 性能 | TTFT(Time To First Token) | 首token延迟 |
| 性能 | TPS(Tokens Per Second) | 生成速度 |
| 性能 | E2E Latency | 端到端延迟 |
| 质量 | 幻觉率 | 生成错误信息的比例 |
| 质量 | 拒答率 | 拒绝回答的比例 |
| 成本 | Token消耗 | 输入/输出token数 |
| 成本 | 单次请求成本 | 每次交互的费用 |
| 安全 | 敏感信息泄露率 | PII泄露 |
| 安全 | 越狱成功率 | 绕过安全限制 |

### 6.2 可观测性架构

```python
# 使用LangSmith/OpenLIT监控
from langsmith import Client

client = Client()

# 自动追踪LangChain调用
# 装饰器方式
@client.trace
def rag_query(question: str):
    docs = retriever.invoke(question)
    answer = llm.invoke(prompt.format(context=docs, question=question))
    return answer

# 监控数据面板
# - 请求量/延迟分布
# - Token使用统计
# - 检索命中率
# - 用户满意度反馈
# - 错误率/重试率
```

### 6.3 A/B测试与迭代

```python
# LLM应用A/B测试
class LLMAbTest:
    def __init__(self):
        self.model_a = "gpt-4"
        self.model_b = "claude-3-opus"
        self.traffic_split = 0.5  # 50/50分流
    
    def get_model(self, user_id: str) -> str:
        # 基于用户ID哈希分流(确保同一用户始终走同一模型)
        bucket = hash(user_id) % 100 / 100
        return self.model_a if bucket < self.traffic_split else self.model_b
    
    def record_feedback(self, user_id, model, rating, latency, tokens):
        # 记录反馈数据
        metrics = {
            "user_id": user_id,
            "model": model,
            "rating": rating,
            "latency_ms": latency,
            "total_tokens": tokens,
            "timestamp": time.time()
        }
        save_to_analytics(metrics)
    
    def evaluate(self):
        # 统计对比
        a_data = get_metrics(self.model_a)
        b_data = get_metrics(self.model_b)
        
        return {
            "model_a": {
                "avg_rating": mean(a_data["ratings"]),
                "p95_latency": percentile(a_data["latencies"], 95),
                "avg_cost": mean(a_data["costs"])
            },
            "model_b": {
                "avg_rating": mean(b_data["ratings"]),
                "p95_latency": percentile(b_data["latencies"], 95),
                "avg_cost": mean(b_data["costs"])
            }
        }
```

---

## 七、成本优化策略

### 7.1 Token成本优化

**Q: 如何降低LLM应用的运行成本？**

| 策略 | 预期节省 | 实现方式 |
|------|---------|---------|
| 模型路由 | 30-60% | 简单问题用小模型，难题用大模型 |
| 缓存 | 20-50% | 相同请求直接返回缓存结果 |
| 批处理 | 10-30% | 离线任务批量调用 |
| 量化部署 | 50-75% | INT4/INT8量化本地部署 |
| Prompt压缩 | 10-20% | 精简系统提示 |
| 上下文裁剪 | 15-40% | 只传必要上下文 |

```python
# 模型路由 - 智能选择模型
class ModelRouter:
    def __init__(self):
        self.models = {
            "simple": "gpt-3.5-turbo",      # 简单任务
            "medium": "gpt-4o-mini",         # 中等任务
            "complex": "gpt-4o",             # 复杂任务
        }
    
    def route(self, query: str) -> str:
        # 基于规则的路由
        if len(query) < 50 and "?" not in query:
            return self.models["simple"]
        
        # 基于分类的路由
        complexity = self._classify_complexity(query)
        return self.models[complexity]
    
    def _classify_complexity(self, query):
        # 可用小模型做分类
        prompt = f"""判断以下问题的复杂度(simple/medium/complex)：
        问题：{query}
        只输出一个词。"""
        
        result = small_llm.invoke(prompt)
        return result.strip().lower()
```

---

## 八、面试系统设计题实战

### 8.1 设计一个智能客服系统

**Q: 请设计一个基于大模型的智能客服系统。**

**系统架构：**

```
用户 → CDN → API网关 → 会话管理 → 意图识别
                                     │
                        ┌────────────┼────────────┐
                        │            │            │
                   FAQ检索      知识库RAG     工具调用
                        │            │            │
                        └────────────┼────────────┘
                                     │
                              回答生成+审核
                                     │
                              人工客服兜底
```

**关键设计决策：**

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 检索方案 | 混合检索(向量+ES) | FAQ精确匹配+语义理解 |
| 上下文管理 | 摘要+最近5轮 | 长对话不丢信息 |
| 安全审核 | 输入输出双审核 | 防注入+防泄露 |
| 降级策略 | 规则引擎→LLM→人工 | 三级降级保证可用性 |
| 多轮记忆 | Redis短期+MySQL长期 | 7天热数据+全量冷数据 |

### 8.2 设计一个代码助手

**Q: 请设计一个类似GitHub Copilot的代码助手。**

```
IDE → LSP协议 → 代码上下文分析 → Prompt组装 → LLM推理 → 后处理 → 补全建议
                     │                              │
                     │                              ├─ 语法校验
                     │                              ├─ 安全检测
                     │                              └─ 相似代码去重
                     │
                     ├─ 当前文件上下文
                     ├─ 项目结构
                     ├─ 相关文件(imports)
                     └─ Git历史(可选)
```

**关键挑战：**

| 挑战 | 解决方案 |
|------|---------|
| 低延迟要求 | 流式输出 + 本地小模型 + 缓存 |
| 上下文有限 | Tree-sitter解析 + 智能选择相关代码 |
| 代码质量 | 后处理语法校验 + 静态分析 |
| 隐私合规 | 本地模型选项 + 代码脱敏 |

---

## 九、总结

| 主题 | 核心要点 | 面试关键词 |
|------|----------|-----------|
| RAG | 检索增强生成、混合检索、重排序、RAGAS评估 | Chunking, Embedding, Rerank, Faithfulness |
| 推理系统 | vLLM、PagedAttention、连续批处理、量化部署 | KV Cache, Continuous Batching, GPTQ |
| 评测体系 | MMLU、MT-Bench、LLM-as-Judge、自动评测 | Benchmark, Arena, RAGAS |
| 对话系统 | 上下文管理、摘要压缩、Function Calling | Context Window, Tool Use, Multi-turn |
| Prompt工程 | CoT、DSPy、结构化输出 | Few-shot, ReAct, Instructor |
| 监控运维 | TTFT、TPS、幻觉率、A/B测试 | Observability, Cost Optimization |
| 成本优化 | 模型路由、缓存、量化、批处理 | Model Router, Semantic Cache |

---

> 🎯 **AI大模型面试八股文系列完结！** 本系列从Transformer基础、训练微调、推理部署、应用开发、安全对齐到系统设计，全面覆盖了大模型面试的核心知识点。
> 
> 📌 **下期预告**：《Java并发编程面试八股文（一）——线程基础与锁机制》将深入Java线程模型、synchronized原理、Lock接口、AQS框架等并发编程核心话题，开启全新的面试八股文系列，敬请期待！
