---
title: Spring AI面试八股文（四）——RAG企业级实践
date: 2026-07-17 10:00:00+08:00
updated: '2026-07-17T10:00:00+08:00'
description: 深入解析Spring AI的企业级RAG实现：从QuestionAnswerAdvisor快速上手，到spring-ai-rag新模块的查询改写/扩展、文档后处理、上下文增强全流程；涵盖元数据过滤、混合检索、重排、引用溯源（grounding
  with citations）与生产级调优。结合源码与实战代码掌握可落地的RAG架构。
topic: ai-engineering
series: spring-ai-interview
series_order: 4
level: intermediate
status: maintained
tags:
- Spring AI
- Java
- AI
- RAG
- Advisor
categories:
- AI 工程化
draft: false
keywords:
- Spring AI
- RAG
- QuestionAnswerAdvisor
- RetrievalAugmentationAdvisor
- VectorStore
- 引用溯源
- 面试八股文
---

> 面试高频问题：RAG在Spring AI里怎么落地？`QuestionAnswerAdvisor`和`RetrievalAugmentationAdvisor`有什么区别？怎么做查询改写和引用溯源？元数据过滤怎么玩？本文带你把"能问答"升级为"答得准、可追溯"。

## 引言

RAG（检索增强生成）的**通用原理**——"检索外部知识 → 拼进 Prompt → 大模型生成"——我在 **《AI大模型面试八股文（四）——大模型应用开发与Agent框架》** 和 **《AI大模型面试八股文（六）——大模型系统设计与工程实践》** 两篇里已用大篇幅讲透（基础流程、高级RAG、评估指标）。那两篇偏"通用架构与算法选型"。

本文**聚焦 Spring AI 自己怎么把 RAG 工程化**：它用一套 **Advisor（顾问）** 模式把"检索—增强—生成"嵌进 `ChatClient` 的拦截链里。掌握这些，你谈 RAG 时就能从"Transformer+向量库"上升到"我能在 Spring 项目里三四十行代码搭出生产级 RAG"的层次。

**本文要点**：
1. Spring AI 的 Advisor 式 RAG 架构与 `QuestionAnswerAdvisor` 快速上手
2. `spring-ai-rag` 新模块：查询改写/扩展、文档后处理、上下文增强
3. 元数据过滤、混合检索与重排（`DocumentRetriever`）
4. 引用溯源（grounding with citations）与可观测
5. 生产级 RAG 调优清单

---

企业级 RAG 与"玩具 RAG"最大的区别，不在于用了多炫的模型，而在于**工程链路的健壮性**：知识是否及时更新、检索是否精准、回答是否可追溯、成本是否可控。很多 demo 用"向量库查一下拼进 prompt"几十行就能跑通，但一上生产就暴露问题——用户问"上个月的报销政策"，模型答非所问；员工问"别的部门"的机密文档，却被召回；模型编造了不存在的条款，却无任何出处。Spring AI 的 Advisor 体系正是为这些生产痛点而生：它把"改写、检索、过滤、增强、溯源"拆成可组合、可观测的标准环节，让你用框架能力而非堆砌胶水代码来解决上述问题。

## 一、为什么是 Advisor 模式

传统手写 RAG 是"先查向量库 → 拼 Prompt → 调模型"的线性代码，检索逻辑和对话逻辑耦合。Spring AI 把 RAG 做成 `ChatClient` 的 **Advisor**（顾问拦截器）：在请求到达模型前自动注入检索到的上下文，在响应返回后还可做后处理。

好处：
- **与对话解耦**：检索增强是"横切关注点"，用 Advisor 一处配置，全链路生效（包括多轮记忆、流式输出）。
- **可组合**：查询改写、扩展、文档过滤、引用标注都能拆成独立 Advisor 拼装。
- **复用 ChatClient**：RAG 不破坏你已有的 `ChatClient` 调用姿势。

---

## 二、快速上手：QuestionAnswerAdvisor

最轻量的 RAG 是 `QuestionAnswerAdvisor`——它内部绑定一个 `VectorStore`，每次请求自动检索 Top-K 片段，拼进系统提示词：

```java
@Autowired
private VectorStore vectorStore;     // （二）篇讲过的向量库
@Autowired
private ChatClient.Builder builder;

public String ask(String question) {
    ChatClient client = builder.build();
    String answer = client.prompt()
            .advisors(new QuestionAnswerAdvisor(vectorStore))   // 自动检索并增强
            .user(question)
            .call()
            .content();
    return answer;
}
```

`QuestionAnswerAdvisor` 的关键构造参数：
- **`SearchRequest`**：控制 `topK`、相似度阈值 `similarityThreshold`、`filterExpression`（元数据过滤，详见第四节）。
- **`userTextAdvise`**：自定义上下文模板，默认把检索结果拼成"上下文 + 问题"的结构化提示。
- **`extractContext`**：是否把注入的上下文也返回给调用方（便于做引用展示）。

它适合"单轮问答 + 简单检索"场景，开箱即用、零样板。但**企业级 RAG 往往需要在检索前后做改写、扩展、重排**，这就需要更强大的 `RetrievalAugmentationAdvisor`。

---

选型时有个经验法则：**先用 `QuestionAnswerAdvisor` 跑通 MVP**，验证"向量库 + LLM"能否回答对；一旦遇到"检索不准、召回不全、答非所问"等生产问题，再升级到 `RetrievalAugmentationAdvisor` 补齐改写、扩展、后处理与溯源。前者是"够用就好"，后者是"为质量与合规负责"，两者 API 都基于 `ChatClient.advisors()`，迁移成本极低。

## 三、生产级：RetrievalAugmentationAdvisor 全流程

Spring AI 1.0 引入了独立的 `spring-ai-rag` 模块，把 RAG 拆成清晰的 **Pre-Retrieval（检索前）→ Retrieval（检索）→ Post-Retrieval（检索后）** 三阶段，由 `RetrievalAugmentationAdvisor` 编排：

```java
RetrievalAugmentationAdvisor advisor = RetrievalAugmentationAdvisor.builder()
        .documentRetriever(VectorStoreDocumentRetriever.builder()
                .vectorStore(vectorStore)
                .topK(6)
                .similarityThreshold(0.73)
                .filterExpression("category == 'hr'")   // 元数据过滤
                .build())
        // ===== 检索前：查询改写 + 扩展 =====
        .queryTransformers(List.of(
                RewriteQueryTransformer.builder().chatClient(client).build(),
                CompressionQueryTransformer.builder().chatClient(client).build()))
        .queryExpanders(List.of(
                MultiQueryExpander.builder().chatClient(client).n(3).build()))
        // ===== 检索后：文档后处理 =====
        .documentTransformers(List.of(
                KeywordMetadataEnricher.builder().chatClient(client).build()))
        // ===== 上下文增强器 =====
        .queryAugmenter(ContextualQueryAugmenter.builder()
                .allowEmptyContext(true)
                .build())
        .build();

String answer = client.prompt().advisors(advisor).user(question).call().content();
```

各组件职责：

**检索前（Pre-Retrieval）**
- **`QueryTransformer`（查询改写）**：用户问题常口语化、有指代。"帮我查上个月的报销"里的"上个月"模型/向量库都不懂。`RewriteQueryTransformer` 用 LLM 把问题改写成自包含、利于检索的查询；`CompressionQueryTransformer` 在多轮对话中把历史稀释掉、只保留与当前问题相关的上下文。
- **`QueryExpander`（查询扩展）**：`MultiQueryExpander` 把一个问题扩展成 N 个角度不同的子查询（如"如何退货"→"退货流程""退款时效""退货条件"），分别检索后合并，显著提升召回。

**检索中（Retrieval）**
- **`DocumentRetriever`**：默认 `VectorStoreDocumentRetriever`，封装 `VectorStore` 检索 + topK + 阈值 + 过滤。

**检索后（Post-Retrieval）**
- **`DocumentTransformer`（文档后处理）**：`KeywordMetadataEnricher` 给每个召回片段补充关键词元数据，便于后续过滤/展示；`SummaryMetadataEnricher` 生成片段摘要。企业里也可在此做**重排（rerank）**——用 Cross-Encoder 对召回结果重新打分，把最相关片段排到最前，再截断送入模型。

**上下文增强（Query Augmenter）**
- **`ContextualQueryAugmenter`**：把处理后的文档拼成最终 Prompt。`allowEmptyContext=true` 表示检索为空时仍让模型基于自身知识回答（避免"无上下文就拒答"）；还可配置脚注模板、空上下文提示语，以及**引用标注行为**（见第五节）。

这套"改写→扩展→检索→后处理→增强"的流水线，正是生产级 RAG 与玩具 RAG 的分水岭。

---

## 四、元数据过滤：让检索更精准

纯向量相似度检索容易"看起来像、其实不对口"。Spring AI 的 `filterExpression` 支持在向量检索时叠加**结构化元数据过滤**，把检索限定在正确子集：

```java
// 只检索"人力资源"分类、且年份 >= 2024 的文档
SearchRequest request = SearchRequest.builder()
        .topK(5)
        .similarityThreshold(0.7)
        .filterExpression("category == 'hr' && year >= 2024")
        .build();
```

`filterExpression` 使用 Spring AI 的过滤表达式语言，支持 `==`、`!=`、`>`、`>=`、`<`、`<=`、`&&`、`||`、`in [...]` 等。它底层会翻译成各向量库自己的过滤语法（Pgvector 的 `WHERE`、Milvus 的 `expr`、Elasticsearch 的 `filter`），**上层写法统一**。实战价值：
- **权限隔离**：`tenantId == '当前租户'`，天然实现多租户文档隔离。
- **场景收敛**：不同业务线/文档类型用 `category` 字段区分，避免跨域误召回。
- **时效控制**：`year >= 2024` 过滤掉过期知识。

---

## 五、引用溯源（Grounding with Citations）

企业 RAG 最怕"模型一本正经胡说"且无法追责。Spring AI 支持**引用溯源**：让模型在回答里标注每段话来自哪个文档片段，便于用户核查与合规审计。
 具体落地时，你只需给每个被注入的 `Document` 设置 `documentId`/`source` 等元数据，再在增强器上开启 `CitationBehavior`，Spring AI 会自动在 Prompt 模板里铺设引用占位符，并提示模型"回答需标注来源编号"。前端拿到回答与上下文后，即可渲染"引用来源"侧边栏。

实现方式（基于 `ContextualQueryAugmenter` + 文档元数据）：
- 给每个被注入的文档片段带上 `documentId` 等元数据；
- 通过增强器的 **`CitationBehavior`** 配置引用风格（如脚注 `[1]` 或行内标注）；
- 模型被提示"回答需引用对应文档编号"，最终回答形如"根据《员工手册》第3章[1]，试用期…[2]"。

同时 `QuestionAnswerAdvisor` 的 `extractContext=true` 可把实际注入的上下文一并返回，前端能据此渲染"引用来源卡片"。溯源带来两大收益：**可信度提升**（用户可点开原文）和**可追溯合规**（金融、医疗等强监管场景的硬要求）。

---

## 六、混合检索与重排

仅靠向量"语义检索"会漏掉关键词精确匹配（如产品型号、专有名词）。企业常用 **混合检索（Hybrid Search）= 向量召回 + 关键词（BM25）召回**，再合并去重：
- Pgvector 可用 `@Extended`/`tsvector` 做关键词；
- Elasticsearch 原生支持 `dense_vector` + `bm25` 混合；
- Milvus 的 `hybrid_search` 支持多路召回融合。

召回后通常接**重排模型（Reranker）**：用 Cross-Encoder 对"问题-片段"对重新打分，把真正相关的排前面，再取 Top-N 送入 LLM。Spring AI 把重排放在 `DocumentTransformer` 阶段实现即可。经验值：向量召回取 20~50 条，重排后取 5~8 条给模型，质量和成本最佳平衡。

---

## 六之一、RAG 评估：别只靠"感觉答对"

上线不是终点。RAG 系统必须用指标说话，否则无法迭代。可借鉴 **《AI大模型面试八股文（六）》** 里的 RAGAS 思路，在 Spring AI 工程里落地三类评测：
- **检索质量**：召回率（相关片段是否被找回）、精确率（召回片段有多少真相关）、MRR/NDCG（排序是否合理）。
- **生成质量**：答案与上下文的**忠实度（Faithfulness）**——模型有没有编造上下文里没有的内容，这是 RAG 最该盯的指标。
- **端到端**：回答是否真正解决了用户问题（可用 LLM-as-Judge 或人工抽检）。

在 Spring AI 里，你可以用 `extractContext=true` 拿到实际注入的文档，把它和答案一起送进评测管线，定期跑回归。这样一个"检索—生成—评估"的闭环，才是企业 RAG 能持续变好的关键。

多路召回合并时，常用 **RRF（Reciprocal Rank Fusion）** 把向量排序与 BM25 排序融合：每个文档的得分取各路排名倒数之和，排名越靠前贡献越大。它不依赖分数量纲统一，工程上简单鲁棒，是混合检索的默认融合算法。落地时先用 RRF 粗融，再上 reranker 精排，是兼顾召回与精度的经典组合。

## 七、生产级 RAG 调优清单

1. **分块策略（Chunking）**：按语义/标题切分，块大小 300~800 token 为宜；重叠（overlap）10~15% 保连贯。这是检索质量的根。
2. **嵌入模型一致性**：检索用的 Embedding 模型必须与入库时一致，否则相似度无意义（详见（二）篇）。
3. **查询改写先行**：口语化、多轮指代问题必须先改写/压缩再检索。
4. **元数据过滤**：用 `tenantId`/`category`/`time` 收窄检索域，既提精度又保隔离。
5. **阈值 + 重排**：设 `similarityThreshold` 过滤噪声，召回后用 reranker 提纯。
6. **引用溯源**：强监管场景必须开启 citations，回答可核查。
7. **空上下文策略**：`allowEmptyContext` 合理取舍——知识库没命中时，是"拒答"还是"基于通用知识答并标注"？
8. **可观测**：记录每次检索的 query、召回片段、相似度分数、最终 token 消耗，建立 RAG 评估闭环（可结合（六）篇的评测思路）。
9. **成本控制**：限制 topK 与上下文长度，避免把整库塞给模型烧钱。

---

## 八、面试高频问答

**Q1：Spring AI 里 `QuestionAnswerAdvisor` 和 `RetrievalAugmentationAdvisor` 怎么选？**
A：前者是轻量封装，绑定一个 `VectorStore`，适合单轮简单问答、开箱即用；后者是 1.0 新 `spring-ai-rag` 模块的生产级编排器，支持查询改写/扩展、文档后处理、重排接入、引用增强的完整流水线，适合复杂企业场景。

**Q2：RAG 检索前为什么要做查询改写？**
A：用户问题常口语化、含指代（"上个月""它"），向量库无法理解。改写把问题转成自包含、利于检索的查询；多轮对话还需压缩历史，只留相关信息，避免噪声稀释。

**Q3：`filterExpression` 有什么用？**
A：在向量检索时叠加结构化元数据过滤（分类、租户、时间等），底层翻译成各向量库自己的过滤语法但上层写法统一。用于多租户隔离、场景收敛、时效控制，显著提升精度。

**Q4：什么是引用溯源（grounding with citations）？**
A：让模型在回答中标注每段话来自哪个文档片段（脚注/行内引用），配合 `documentId` 元数据与 `CitationBehavior` 实现。价值是提升可信度、满足金融/医疗等强监管场景的可追溯合规。

**Q5：混合检索和重排什么时候需要？**
A：纯向量检索会漏掉精确关键词匹配，混合检索（向量+BM25）补召回；召回后用 Cross-Encoder 重排提纯，取 Top-N 给模型，是生产级 RAG 提质的标配组合。

---

## 九、下期预告

RAG 解决了"让模型读得懂私有知识"，Tool Calling（上篇）解决了"让模型动得了手"。把两者 + 记忆 + 编排串起来，就到了**AI Agent 开发实战**——如何基于 `ChatClient` 构建能自主规划、调用多工具、维持长期记忆的 Agent，以及多 Agent 协作与人工介入（HITL）模式。下一篇 **《Spring AI面试八股文（五）——AI Agent 开发实战》** 见！
