---
title: AI大模型面试八股文（九）——RAG系统进阶与知识工程
date: 2026-07-26T10:00:00+08:00
updated: '2026-07-26T10:00:00+08:00'
description: '面试高频问题：RAG的分块策略有哪些？如何做混合检索？重排序为什么重要？GraphRAG和Agentic RAG是什么？本文从分块策略、检索架构演进、重排序工程实践、GraphRAG与Agentic RAG四个维度，带你掌握RAG系统进阶与知识工程的核心知识。'
topic: ai-engineering
series: ai-llm-interview
series_order: 9
level: intermediate
status: maintained
featured: true
tags:
- AI
- 大模型
- RAG
- 知识工程
- GraphRAG
categories:
- AI 工程化
---

在第四期中我们介绍了RAG的基础原理和架构，第六期讨论了RAG系统设计的基本思路。但在真实的面试和工程实践中，"RAG怎么做"从来不是一个简单问题——当知识库规模从百篇文档扩展到百万篇，当用户提问从"什么是Spring IoC"变成"对比这三个方案的性能差异"，基础RAG架构的检索召回率低、答案幻觉、无法处理跨文档推理等问题就会集中爆发。

这就是本期的主题——RAG系统进阶。它不是单点优化，而是从文档处理、索引架构、检索策略、生成增强到评估反馈的完整工程体系。本文将从分块策略优化、混合检索与重排序、GraphRAG与知识图谱融合、Agentic RAG四个维度展开，覆盖面试官最关心的"RAG从能用到好用的关键路径"。

## 一、分块策略深度解析

### 1.1 为什么分块是RAG的第一性原理

**Q: 为什么RAG系统需要对文档分块？直接把整篇文档灌进去不行吗？**

A: 分块是RAG系统在精度和成本之间做权衡的第一道关口。原因有三：

1. **Embedding模型输入限制**：主流Embedding模型的输入token上限通常在512-8192之间，超长文本会被截断导致语义信息丢失；
2. **检索精度**：整篇文档做Embedding后，向量是全文语义的平均，对具体问题的区分度很低。一个10页文档中只有一段话回答了用户问题，但全文向量可能被其他段落稀释；
3. **上下文窗口成本**：即便大模型支持128K上下文，把无关内容塞进去也会增加推理成本并降低答案质量（Lost in the Middle问题）。

### 1.2 分块策略分类

**Q: 常见的分块策略有哪些？各有什么适用场景？**

A: 主流分块策略可以分为五类：

#### 固定长度分块（Fixed-Size Chunking）

最基础的策略，按固定token数切分，通常配合overlap避免语义断裂。

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""]
)

chunks = splitter.split_text(long_document)
```

- 优点：实现简单，分块大小可控
- 缺点：可能在句子中间切断，破坏语义完整性
- 适用：格式统一的文本（日志、标准化报告）

#### 递归字符分块（Recursive Character Splitting）

LangChain默认策略，按分隔符优先级递归切分，优先在段落边界切，其次在句子边界切。

```
分隔符优先级（中文场景）:
1. \n\n （段落）
2. \n   （换行）
3. 。    （句号）
4. ！？  （问叹号）
5. ；    （分号）
6. 空格
```

- 优点：尽量在自然边界切分，兼顾语义和长度
- 缺点：对结构化文档（表格、代码）效果差
- 适用：大多数通用文本文档

#### 语义分块（Semantic Chunking）

基于Embedding相似度动态决定切分点。计算相邻句子的向量相似度，当相似度低于阈值时切分。

```python
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings

splitter = SemanticChunker(
    OpenAIEmbeddings(),
    breakpoint_threshold_type="percentile",  # 或 "standard_deviation"
    breakpoint_threshold_amount=95
)

chunks = splitter.split_text(document)
```

- 优点：语义边界更准确，每个块内聚性更强
- 缺点：需要额外的Embedding计算，成本高；对短文本效果不稳定
- 适用：长篇技术文档、学术论文

#### 文档结构分块（Document-Based Chunking）

利用文档自身的结构（标题、段落、列表）进行分块。

```python
from langchain.document_loaders import UnstructuredMarkdownLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter

# 按Markdown标题层级切分
headers_to_split_on = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
chunks = splitter.split_text(markdown_content)

# 每个chunk自带metadata，记录其所属的标题层级
for chunk in chunks:
    print(chunk.metadata)  # {'Header 1': '第一章', 'Header 2': '1.1 节'}
    print(chunk.page_content[:100])
```

- 优点：保留文档结构信息，metadata可用于过滤检索
- 缺点：依赖文档格式规范，不规则的文档无法使用
- 适用：技术文档、产品手册、API文档

#### 父子分块（Parent-Child Chunking）

核心思想：小块做检索（精度高），大块做生成（上下文足）。

```
父块（2000 tokens）
├── 子块1（200 tokens）→ 用于Embedding检索
├── 子块2（200 tokens）→ 用于Embedding检索
├── 子块3（200 tokens）→ 用于Embedding检索
└── 子块4（200 tokens）→ 用于Embedding检索

检索命中子块2 → 返回父块（包含完整上下文）给LLM生成
```

```python
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore
from langchain_community.vectorstores import Chroma

# 父分块器：大块
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)
# 子分块器：小块
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)

vectorstore = Chroma(embedding_function=OpenAIEmbeddings())
store = InMemoryStore()

retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=store,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter,
)
retriever.add_documents(docs)

# 检索时：用子块匹配，返回父块
results = retriever.get_relevant_documents("查询问题")
```

- 优点：兼顾检索精度和生成上下文完整性
- 缺点：存储开销增大（父子两套索引）
- 适用：知识库文档、需要完整上下文的问答场景

### 1.3 分块参数调优

**Q: chunk_size和chunk_overlap怎么选？**

A: 没有银弹，需要根据文档类型和业务场景实验确定。以下是经验参考值：

| 文档类型 | 推荐 chunk_size | 推荐 overlap | 理由 |
|----------|----------------|-------------|------|
| FAQ/短问答 | 200-300 | 0 | 每条本身就是独立语义单元 |
| 技术文档 | 500-800 | 50-100 | 段落级，兼顾上下文 |
| 法律/合同 | 1000-1500 | 100-200 | 条款间有强关联 |
| 代码文档 | 按函数/类分 | 0 | 函数级天然边界 |
| 长篇小说/报告 | 300-500 | 50 | 语义连贯性要求高 |

**关键原则**：分块不是一次性工作，应该建立评估反馈闭环——用测试集测量不同分块策略的召回率和答案质量，数据驱动地选择最优配置。

## 二、检索架构演进与混合检索

### 2.1 RAG架构演进路线

**Q: RAG架构经历了哪些演进阶段？**

A: 业界通常将RAG分为三代：

#### Naive RAG（朴素RAG）

```
用户Query → Embedding → 向量检索 → Top-K文档 → LLM生成
```

- 流程简单，适合原型验证
- 问题：单一向量检索，召回率有限；不做重排序；无查询理解

#### Advanced RAG（增强RAG）

```
用户Query
    ↓
[查询理解] → 查询改写/扩展/分解
    ↓
[多路检索] → 向量检索 + 关键词检索 + 语义检索
    ↓
[重排序] → Cross-Encoder重排
    ↓
[上下文组装] → 压缩/过滤/加权
    ↓
LLM生成
```

- 增加了查询预处理和后处理
- 支持混合检索和重排序
- 适合中等规模知识库

#### Modular RAG（模块化RAG）

```
用户Query
    ↓
[路由判断] → 是否需要检索？检索哪个知识库？
    ↓ ↓ ↓
[检索模块] [记忆模块] [工具模块]
    ↓     ↓     ↓
[结果融合] → 重排序 → 上下文组装
    ↓
[生成模块] → 自省→是否需要再次检索？
    ↓
LLM生成答案
```

- 检索、记忆、生成模块解耦，可灵活组合
- 支持迭代检索（Agentic RAG的雏形）
- 适合大规模、多知识库、复杂推理场景

### 2.2 混合检索

**Q: 什么是混合检索？为什么比纯向量检索更好？**

A: 混合检索（Hybrid Search）是将稠密向量检索（Dense Retrieval）和稀疏关键词检索（Sparse Retrieval）结合的检索策略。

两种检索方式的互补性：

| 维度 | 稠密向量检索 | 稀疏关键词检索（BM25） |
|------|-------------|---------------------|
| 原理 | 语义相似度 | 词频匹配 |
| 优势 | 理解同义词、语义相近 | 精确匹配专有名词、代码、ID |
| 弱点 | 对精确术语不敏感 | 无法理解语义近似 |
| 适用 | "怎么优化MySQL查询" | "MySQL error 1213" |

#### 混合检索架构实现

```python
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma

# 稀疏检索：BM25关键词检索
bm25_retriever = BM25Retriever.from_documents(docs)
bm25_retriever.k = 10

# 稠密检索：向量检索
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 10})

# 混合检索：加权融合
ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.3, 0.7]  # BM25权重0.3，向量检索权重0.7
)

results = ensemble_retriever.get_relevant_documents("MySQL索引优化方案")
```

#### 融合策略

混合检索的核心是分数融合算法，主流方案有两种：

**RRF（Reciprocal Rank Fusion）**：

```
score(d) = Σ 1 / (k + rank_i(d))

# k通常取60
# rank_i(d) 是文档d在第i路检索中的排名
```

- 不需要分数归一化，对不同检索器的分数尺度不敏感
- 实现简单，效果稳定，是工程实践的首选

**加权线性融合**：

```
score(d) = α * normalize(dense_score) + (1-α) * normalize(sparse_score)

# 需要将不同检索器的分数归一化到同一尺度
# α需要通过实验调优
```

- 理论上更灵活，但实践上调参成本高，且分数归一化不当时效果反而不如RRF

### 2.3 查询理解与改写

**Q: 为什么要在检索前处理用户查询？**

A: 用户原始查询通常不是最优的检索输入。比如：

- "这个bug怎么解决" — 缺少上下文，检索引擎不知道"这个"指什么
- "Spring和SpringBoot的区别" — 可以拆分为两个子查询分别检索
- "之前提到的那个方案" — 需要结合对话历史改写

#### 查询改写（Query Rewriting）

用LLM将用户查询改写为更适合检索的形式：

```python
from langchain.retrievers import MultiQueryRetriever
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(temperature=0)
retriever = MultiQueryRetriever.from_llm(
    retriever=vector_retriever,
    llm=llm
)

# 用户输入："怎么解决OOM"
# LLM生成多个改写查询：
# 1. "Java OutOfMemoryError排查与解决方法"
# 2. "JVM内存溢出诊断工具与分析步骤"
# 3. "OOM常见原因与调优方案"
# 每个查询分别检索，结果去重合并
```

#### 查询分解（Query Decomposition）

将复杂问题拆分为子问题：

```
用户Query: "对比MySQL和PostgreSQL在索引、事务、复制方面的差异"

分解为：
1. "MySQL索引机制"
2. "PostgreSQL索引机制"
3. "MySQL事务特性"
4. "PostgreSQL事务特性"
5. "MySQL复制方案"
6. "PostgreSQL复制方案"

每个子查询独立检索，最后融合结果
```

#### HyDE（Hypothetical Document Embeddings）

**Q: 什么是HyDE？什么场景下有效？**

A: HyDE的核心思想是：先用LLM生成一个假设性答案文档，再用这个假设文档去检索，而不是直接用原始query检索。

```
用户Query: "怎么配置Spring Boot的Profile"
    ↓
LLM生成假设答案（可能是幻觉）:
"Spring Boot的Profile可以通过在application.yml中
设置spring.profiles.active来激活，也可以用@Profile注解..."
    ↓
用假设答案做向量检索 → 检索到真实的配置文档
    ↓
用真实文档 + 用户Query → LLM生成最终答案
```

- 原理：query和document在向量空间中分布不同（query通常短、问句式，document长、陈述式），直接检索存在"语义gap"。假设答案更接近document的分布，检索效果更好
- 适用：query短且语义模糊的场景
- 不适用：事实性问题（假设文档中的错误细节可能误导检索）

### 2.4 重排序（Re-ranking）

**Q: 为什么需要重排序？向量检索的Top-K不够吗？**

A: 向量检索使用的是Bi-Encoder（双塔模型），query和document分别编码再计算相似度，速度快但精度有限。重排序使用Cross-Encoder，将query和document拼接后输入模型，输出相关性分数，精度更高但计算成本也高。

```
向量检索（Bi-Encoder）：
  Embedding(query) · Embedding(doc) → 相似度分数
  → 快，适合从百万文档中粗筛Top-100

重排序（Cross-Encoder）：
  Model([query, doc]) → 相关性分数
  → 精准，适合从Top-100精选Top-10
```

#### 重排序工程实践

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank

# 第一步：向量检索粗筛 Top-50
base_retriever = vectorstore.as_retriever(search_kwargs={"k": 50})

# 第二步：Cohere Rerank 精排 Top-10
reranker = CohereRerank(top_n=10)

compression_retriever = ContextualCompressionRetriever(
    base_retriever=base_retriever,
    base_compressor=reranker
)

results = compression_retriever.get_relevant_documents("查询内容")
```

#### 重排序模型选择

| 模型 | 类型 | 特点 |
|------|------|------|
| Cohere Rerank | API服务 | 效果好，按调用收费 |
| BGE-Reranker | 开源(智源) | 中英文效果好，可本地部署 |
| Jina Reranker | 开源 | 多语言支持好 |
| Cross-Encoder (ms-marco) | 开源 | 经典英文模型 |
| Qwen-Reranker | 开源(阿里) | 中文效果好 |

**Q: 重排序模型的输入长度限制怎么处理？**

A: Cross-Encoder的输入是 `[CLS] query [SEP] document [SEP]`，通常有512 token限制。如果document很长（比如父块2000 tokens），有两种处理方式：

1. **截断**：只取document前512 token做重排序（最常用，因为开头通常最重要）
2. **滑动窗口**：将长文档分段，每段与query做Cross-Encoder，取最高分作为该文档的分数

## 三、GraphRAG与知识图谱融合

### 3.1 向量检索的局限性

**Q: 向量检索有什么解决不了的问题？**

A: 当问题涉及"跨文档关联"或"全局推理"时，纯向量检索会失效。典型场景：

| 问题类型 | 例子 | 向量检索为什么不行 |
|----------|------|----------------|
| 多跳推理 | "A公司的CEO曾在B公司任职，B公司的主营业务是什么？" | 答案跨两篇文档，单次检索无法覆盖 |
| 全局摘要 | "这个知识库的主要主题有哪些？" | 需要遍历所有文档，Top-K检索只返回最相似的 |
| 关系查询 | "Spring框架中哪些模块依赖了BeanFactory？" | 需要结构化的依赖关系，而非语义相似 |

### 3.2 GraphRAG核心思想

**Q: 什么是GraphRAG？它和传统RAG有什么区别？**

A: GraphRAG（由微软在2024年提出）是在向量检索基础上引入知识图谱，通过图结构来捕获文档间的关联关系。

传统RAG vs GraphRAG 的架构对比：

```
传统RAG:
  文档 → 分块 → Embedding → 向量索引 → 检索 → 生成

GraphRAG:
  文档 → 分块 → Embedding → 向量索引 ──┐
  ↓                                    │ 混合检索
  实体抽取 → 关系抽取 → 知识图谱 ───────┘
                              ↓
                    社区检测(层级聚类)
                              ↓
                    社区摘要生成
                              ↓
              [向量检索 + 图遍历 + 社区摘要] → 生成
```

### 3.3 GraphRAG构建流程

#### 第一步：实体与关系抽取

用LLM从每个文档块中抽取实体（Entity）和关系（Relationship）：

```python
# GraphRAG的实体抽取Prompt（简化版）
entity_extraction_prompt = """
从以下文本中抽取实体和关系，输出JSON格式。

实体类型：人物、组织、地点、技术、概念、产品
关系类型：属于、创建、使用、依赖、竞争、合作、包含

文本: {text}

输出格式:
{
  "entities": [
    {"name": "Spring Boot", "type": "技术", "description": "..."},
    {"name": "Pivotal", "type": "组织", "description": "..."}
  ],
  "relations": [
    {"source": "Spring Boot", "target": "Pivotal", "relation": "创建", "description": "..."}
  ]
}
"""
```

#### 第二步：知识图谱构建

将抽取的实体作为节点，关系作为边，构建知识图谱：

```python
import networkx as nx

graph = nx.Graph()

# 添加实体节点
for entity in extracted_entities:
    graph.add_node(entity["name"], 
                   type=entity["type"],
                   description=entity["description"])

# 添加关系边
for relation in extracted_relations:
    graph.add_edge(relation["source"], 
                   relation["target"],
                   relation=relation["relation"],
                   description=relation["description"])

# 图统计信息
print(f"节点数: {graph.number_of_nodes()}")
print(f"边数: {graph.number_of_edges()}")
print(f"连通分量数: {nx.number_connected_components(graph)}")
```

#### 第三步：社区检测与层级摘要

用图聚类算法（如Leiden算法）将知识图谱划分为社区，并为每个社区生成摘要：

```python
from community_detection import leiden_algorithm

# Leiden社区检测
communities = leiden_algorithm(graph, resolution_parameter=1.0)

# 为每个社区生成LLM摘要
for i, community in enumerate(communities):
    nodes_info = [graph.nodes[n] for n in community]
    edges_info = [(u, v, graph[u][v]) for u, v in graph.subgraph(community).edges()]
    
    community_summary = llm.generate(
        f"根据以下实体和关系，生成一个主题摘要：\n{nodes_info}\n{edges_info}"
    )
    
    community_summaries[i] = community_summary
```

### 3.4 GraphRAG检索模式

GraphRAG支持三种检索模式，应对不同类型的问题：

#### 全局搜索（Global Search）

用于"全局摘要"类问题：遍历所有社区摘要，聚合生成答案。

```
问题: "这个知识库涉及哪些主要技术主题？"

流程:
1. 读取所有社区摘要
2. 对每个社区摘要，用LLM生成与问题相关的部分回答
3. 汇总所有部分回答，生成最终摘要
```

#### 局部搜索（Local Search）

用于"实体关联"类问题：从问题中提取实体，找到图中的关联实体和文本。

```
问题: "Spring Boot和Spring Cloud什么关系？"

流程:
1. 提取实体: "Spring Boot", "Spring Cloud"
2. 在图中找到这两个节点的邻居
3. 获取相关边的描述（"依赖"、"属于"）
4. 获取关联文本块
5. 组装上下文，生成答案
```

#### 混合搜索（Hybrid Search）

结合向量检索和图检索：

```
问题: "微服务怎么做服务发现？"

流程:
1. 向量检索 → 获取语义相关文本块
2. 图遍历 → 从"服务发现"节点出发，找到关联实体（"Eureka"、"Nacos"、"Consul"）
3. 社区摘要 → 获取相关社区的主题摘要
4. 三路结果融合 → 组装上下文 → 生成答案
```

### 3.5 GraphRAG的权衡

**Q: GraphRAG这么好，是不是应该替代传统RAG？**

A: 不是。GraphRAG在带来更强推理能力的同时，也引入了显著成本：

| 维度 | 传统RAG | GraphRAG |
|------|---------|---------|
| 构建成本 | 文档Embedding | 文档Embedding + LLM实体抽取 + LLM关系抽取 + LLM社区摘要 |
| 索引时间 | 秒级 | 分钟到小时级（取决于文档量） |
| 更新成本 | 增量索引简单 | 新文档可能影响社区结构，需要重新聚类 |
| 检索延迟 | 毫秒级 | 局部搜索较快，全局搜索需要多次LLM调用 |
| 推理能力 | 单跳为主 | 多跳推理、全局摘要 |

**选型建议**：
- **传统RAG**：知识库规模中等（<10万文档）、问题以事实查询为主 → 性价比最高
- **GraphRAG**：需要多跳推理、全局摘要、或知识库中实体关系密集（如企业知识图谱、法律条文）
- **混合方案**：大部分用传统RAG，仅对特定问题类型走GraphRAG路径

## 四、Agentic RAG与自适应检索

### 4.1 从固定流程到自适应检索

**Q: 什么是Agentic RAG？它和普通RAG有什么区别？**

A: 传统RAG是"一次性检索"——用户提问→检索→生成，流程固定。但在复杂场景下，一次检索往往不够：

- 检索结果不相关 → 需要改写查询重新检索
- 问题需要多步推理 → 需要多次检索
- 不同子问题需要检索不同知识库 → 需要路由

Agentic RAG将RAG从"Pipeline"升级为"Agent"——让LLM自主决定何时检索、如何检索、检索几次、何时停止。

### 4.2 Agentic RAG核心机制

#### 检索决策

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import Tool

def retrieve_from_kb(query: str) -> str:
    """从知识库检索"""
    docs = vector_retriever.get_relevant_documents(query)
    return "\n\n".join([d.page_content for d in docs])

def search_web(query: str) -> str:
    """网络搜索"""
    # 调用搜索API
    ...

tools = [
    Tool(name="knowledge_base", func=retrieve_from_kb, 
         description="从内部知识库检索技术文档"),
    Tool(name="web_search", func=search_web,
         description="搜索互联网上的最新信息"),
]

# Agent自主决定使用哪个工具、是否需要多次检索
agent = AgentExecutor.from_agent_and_tools(
    agent=create_openai_tools_agent(llm, tools, prompt),
    tools=tools,
    verbose=True,
    max_iterations=5  # 限制迭代次数防止无限循环
)

result = agent.invoke({"input": "Spring Boot 3.0有哪些新特性？和2.x有什么区别？"})
```

#### 迭代检索与自省

```
用户Query: "对比2024年主流向量数据库的性能"

Agent思考:
1. 需要检索"向量数据库性能对比" → 检索结果不够全面
2. 改写查询: "Milvus vs Pinecone vs Qdrant benchmark" → 检索到部分数据
3. 发现缺少Weaviate的数据 → 再次检索 "Weaviate性能测试"
4. 信息足够 → 生成对比答案
```

关键设计：每轮检索后，Agent评估当前信息是否足够回答问题：
- **足够** → 生成答案
- **不够** → 决定改写查询/换知识库/终止

### 4.3 Agentic RAG架构模式

#### 单Agent + 多工具

最简单的模式，一个Agent管理多个检索工具：

```
Agent → [知识库检索] [网络搜索] [数据库查询] [代码执行]
```

#### 多Agent协作

复杂问题拆分给不同领域的Agent：

```
Router Agent
├── 技术文档Agent → 技术知识库
├── 产品文档Agent → 产品知识库
├── 数据分析Agent → SQL数据库 + 代码执行
└── 汇总Agent → 融合各子Agent的结果，生成最终答案
```

#### Self-RAG（自省RAG）

模型在生成过程中自主决定是否需要检索、检索结果是否相关：

```
Step 1: 接收Query → 判断 [需要检索?]
  ├── Yes → 检索 → 判断 [检索结果相关?]
  │     ├── Yes → 使用检索结果生成
  │     └── No → 不使用检索结果，靠模型自身知识生成
  └── No → 直接生成
  
Step 2: 生成答案 → 判断 [答案是否需要事实支撑?]
  ├── Yes → 检索验证 → 如果矛盾则修正
  └── No → 输出答案
```

### 4.4 Agentic RAG的工程挑战

**Q: Agentic RAG在生产环境有哪些坑？**

A: 主要有三个工程挑战：

#### 延迟控制

Agent每轮决策需要一次LLM调用，多轮迭代后总延迟可能超过用户容忍度。

- **对策**：设置max_iterations上限（通常3-5轮）；使用更快的模型做决策（如GPT-4o-mini），更强的模型做生成；对简单问题直接走Pipeline模式，只有复杂问题才走Agent模式

#### 成本控制

每次LLM调用都消耗token，多轮迭代可能导致单次问答成本是传统RAG的10倍以上。

- **对策**：缓存检索结果；对常见问题类型建立路由规则避免不必要的Agent流程；监控每次查询的token消耗并设置预算上限

#### 评估困难

传统RAG用RAGAS等框架评估，但Agentic RAG的检索路径不固定，难以用单一指标衡量。

- **对策**：引入过程评估——记录每轮决策的合理性，而不仅看最终答案质量；建立测试集覆盖典型问题类型；监控各轮检索的命中率和有用率

## 五、RAG评估体系

### 5.1 RAGAS框架

**Q: 如何系统化评估RAG系统的质量？**

A: RAGAS是目前最主流的RAG评估框架，从三个维度评估：

```
                    RAGAS评估框架
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
     检索质量         生成质量         端到端
          │              │              │
    - 上下文精度    - 答案相关性    - 答案准确性
    - 上下文召回    - 忠实性        - 答案完整性
    (Context       (Answer        (Answer
     Precision)    Relevancy)      Correctness)
    (Context                                        
     Recall)                                        (Faithfulness)
```

#### 核心指标

| 指标 | 含义 | 计算方式 |
|------|------|---------|
| **Faithfulness（忠实性）** | 答案是否忠实于检索到的上下文，不编造 | 答案中的claim能否在上下文中找到支撑 |
| **Answer Relevancy（答案相关性）** | 答案是否回答了用户的问题 | 从答案反向生成问题，与原问题的相似度 |
| **Context Precision（上下文精度）** | 检索结果中有多少是相关的 | 相关文档在Top-K中的占比 |
| **Context Recall（上下文召回）** | 回答问题所需的信息是否都被检索到 | 标注答案中的信息在检索结果中的覆盖率 |

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy,
    context_precision, context_recall
)
from datasets import Dataset

# 构建评估数据集
eval_data = Dataset.from_dict({
    "question": ["什么是Spring IoC？", "如何配置Redis集群？"],
    "answer": [generated_answer_1, generated_answer_2],
    "contexts": [retrieved_docs_1, retrieved_docs_2],
    "ground_truth": [reference_answer_1, reference_answer_2]
})

results = evaluate(
    eval_data,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall]
)

print(results)
# {'faithfulness': 0.85, 'answer_relevancy': 0.92, 
#  'context_precision': 0.78, 'context_recall': 0.88}
```

### 5.2 评估数据集构建

**Q: 没有标注数据怎么评估RAG？**

A: 三种工程实践中常用的方案：

#### LLM生成评估集

用LLM从知识库文档中自动生成问答对：

```python
# 1. 从文档中抽取问答对
generation_prompt = """
基于以下文档内容，生成3个面试高频问题和标准答案。
要求：问题不能直接照抄原文，答案必须能从文档中推导出来。

文档: {document}

输出JSON格式:
[{"question": "...", "answer": "...", "source_chunk": "..."}]
"""
```

#### 人工标注小样本 + LLM扩展

1. 人工标注20-50个高质量问答对
2. 用LLM基于这些样本的pattern扩展到200-500个
3. 人工抽检扩展质量

#### 线上日志回流

从用户真实查询中采样，人工标注答案质量，形成持续评估闭环。

## 六、RAG系统生产化实践

### 6.1 增量更新

**Q: 知识库频繁更新时，如何做增量索引？**

A: 生产环境的知识库不是静态的，需要支持增量更新：

```python
# 文档变更监听
class DocumentIndexManager:
    def __init__(self, vectorstore, docstore):
        self.vectorstore = vectorstore
        self.docstore = docstore  # 文档元数据存储
    
    def add_document(self, doc):
        """新增文档"""
        chunks = self.splitter.split_text(doc.page_content)
        for chunk in chunks:
            chunk.metadata = {
                **doc.metadata,
                "source_id": doc.metadata["source_id"],
                "updated_at": doc.metadata.get("updated_at", datetime.now())
            }
        self.vectorstore.add_documents(chunks)
        self.docstore.save(doc.metadata["source_id"], doc)
    
    def update_document(self, doc):
        """更新文档：先删旧块再加新块"""
        source_id = doc.metadata["source_id"]
        # 删除旧分块
        self.vectorstore.delete(filter={"source_id": source_id})
        # 重新分块并索引
        self.add_document(doc)
    
    def delete_document(self, source_id):
        """删除文档"""
        self.vectorstore.delete(filter={"source_id": source_id})
        self.docstore.delete(source_id)
```

### 6.2 多租户隔离

**Q: 多个业务线共用一个RAG系统怎么隔离？**

A: 通过metadata过滤实现逻辑隔离：

```python
# 索引时标记租户
for chunk in chunks:
    chunk.metadata["tenant"] = "team_backend"
    chunk.metadata["department"] = "engineering"

# 检索时按租户过滤
results = vectorstore.similarity_search(
    query="如何配置数据库连接池",
    k=10,
    filter={"tenant": "team_backend"}
)
```

### 6.3 检索结果缓存

```python
import hashlib
from functools import lru_cache

class CachedRetriever:
    def __init__(self, base_retriever, ttl_seconds=3600):
        self.base_retriever = base_retriever
        self.ttl_seconds = ttl_seconds
        self.cache = {}
    
    def get_relevant_documents(self, query: str):
        cache_key = hashlib.md5(query.encode()).hexdigest()
        
        if cache_key in self.cache:
            result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.ttl_seconds:
                return result
        
        result = self.base_retriever.get_relevant_documents(query)
        self.cache[cache_key] = (result, time.time())
        return result
```

### 6.4 A/B测试框架

```python
class RAGABTest:
    def __init__(self, retriever_a, retriever_b, ratio_b=0.5):
        self.retriever_a = retriever_a
        self.retriever_b = retriever_b
        self.ratio_b = ratio_b
    
    def retrieve(self, query: str, user_id: str):
        # 基于user_id做确定性分流
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        use_b = (hash_val % 100) < (self.ratio_b * 100)
        
        if use_b:
            results = self.retriever_b.get_relevant_documents(query)
            variant = "B"
        else:
            results = self.retriever_a.get_relevant_documents(query)
            variant = "A"
        
        # 记录AB测试日志
        self.log(query, user_id, variant, results)
        return results
```

## 七、面试高频问题与标准回答

**Q1: RAG系统中分块策略怎么选？**

分块策略的选择取决于文档类型和业务场景。对于通用文本文档，递归字符分块是最常用的，它能在自然边界切分并兼顾长度控制。对于结构化文档如技术手册，按文档结构（标题层级）分块更合适，因为保留了上下文层级。如果对检索精度要求高且预算允许，语义分块能让每个块内聚性更强。对于需要完整上下文的场景，父子分块是最佳选择——小块做检索，大块做生成。关键原则是建立评估闭环：用测试集测量不同策略的召回率和答案质量，数据驱动选择。

**Q2: 混合检索中BM25和向量检索的权重怎么设置？**

没有固定最优值，通常向量检索权重更高（0.6-0.8），因为语义匹配覆盖面更广。但如果知识库中有大量专有名词、代码片段、ID编号，可以适当提高BM25权重（0.3-0.4）。实践中建议用RRF（Reciprocal Rank Fusion）替代加权融合——RRF不需要分数归一化，对不同检索器的分数尺度不敏感，实现简单且效果稳定，是工程实践的首选。最终权重需要通过A/B测试在真实数据上调优。

**Q3: GraphRAG和传统RAG什么时候用哪个？**

传统RAG适合知识库规模中等（10万文档以内）、问题以事实查询和单跳推理为主的场景，它的优势是构建成本低、检索速度快、增量更新简单。GraphRAG适合需要多跳推理、全局摘要、或知识库中实体关系密集的场景，比如企业知识图谱、法律条文关联分析。它通过引入知识图谱捕获文档间的结构化关联，但代价是构建成本高（需要LLM做实体和关系抽取）且更新复杂。实践中常用混合方案：大部分查询走传统RAG，只有涉及跨文档推理或全局分析时才走GraphRAG路径。

**Q4: Agentic RAG如何控制延迟和成本？**

三个关键手段：第一，设置迭代上限（通常3-5轮），防止无限循环；第二，模型分级——用轻量模型做检索决策（判断是否需要重新检索），用强模型做最终生成，因为决策任务比生成任务简单；第三，智能路由——对简单问题直接走Pipeline模式（单次检索+生成），只有问题复杂度超过阈值时才进入Agent流程。此外，检索结果缓存和查询模式分类也能有效减少重复的LLM调用。

**Q5: 如何评估RAG系统的检索质量？**

用RAGAS框架从四个维度评估：忠实性（Faithfulness）衡量答案是否忠实于上下文不编造；答案相关性（Answer Relevancy）衡量答案是否真正回答了问题；上下文精度（Context Precision）衡量Top-K检索结果中有多少是相关的；上下文召回（Context Recall）衡量回答问题所需信息是否都被检索到。评估数据集可以通过LLM从文档中自动生成问答对、人工标注小样本后LLM扩展、或线上日志回流三种方式构建。关键是建立持续评估的流水线，每次迭代后自动跑评估，追踪指标变化趋势。

## 下一期预告

AI大模型面试第十期将聚焦 **AI Agent工程化实战与面试冲刺**——从Agent架构模式、多Agent协作、Agent评估与安全、到企业级Agent平台落地，系统梳理Agent工程化的核心知识，并附上本系列高频面试题总串讲，敬请期待。

---

*如果本文对你有帮助，欢迎关注并收藏「Raphael Lab」，我会持续输出高质量的技术博客。*
