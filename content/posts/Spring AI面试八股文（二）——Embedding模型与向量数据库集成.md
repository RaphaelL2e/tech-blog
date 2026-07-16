---
title: "Spring AI面试八股文（二）——Embedding模型与向量数据库集成"
date: 2026-07-16T10:00:00+08:00
draft: false
categories: ["Spring AI"]
tags: ["Spring AI", "Java", "AI", "Embedding", "VectorStore", "向量数据库", "面试"]
keywords: ["Spring AI", "Embedding", "VectorStore", "向量数据库", "Milvus", "Pgvector", "Chroma", "面试八股文"]
description: "深入解析Spring AI中Embedding模型的使用、VectorStore抽象与实现、主流向量数据库对比与选型、企业级RAG数据层搭建。结合源码剖析和实战案例，全面掌握AI应用数据基础设施。"
---

# Spring AI面试八股文（二）——Embedding模型与向量数据库集成

> 面试高频问题：什么是Embedding？Spring AI中如何配置Embedding模型？VectorStore有哪些实现？Milvus和Pgvector怎么选？如何设计向量索引？向量搜索的召回率和精度如何优化？本文带你掌握AI应用的数据基础设施。

## 引言

在 AI 应用中，"让AI理解数据"是核心命题。Embedding（向量化）是将文本、图像、音频等非结构化数据转换为稠密向量的技术，而向量数据库则是存储和检索这些向量的基础设施。两者共同构成了 RAG（检索增强生成）的数据层底座。

本文聚焦 Spring AI 中 **Embedding 模型** 和 **VectorStore** 的使用，包括配置、实现、选型和性能优化。这些是企业级 AI 应用落地的必备知识。

**本文要点**：
1. Embedding 模型配置与调用
2. VectorStore 抽象与主流实现
3. 向量数据库对比与选型策略
4. 相似度搜索与向量索引优化
5. 企业级文档向量化实战

---

## 一、Embedding 模型核心原理

### 1.1 什么是 Embedding？

Embedding 是将离散的高维数据（如文字）映射到连续的、低维的稠密向量空间的技术。语义相近的内容在向量空间中距离更近。

```java
// 文字 → 向量
EmbeddingModel embeddingModel = ...

// "苹果" 和 "香蕉" 的向量应该很接近
// "苹果" 和 "手机" 的向量应该较远
List<Double> apple = embeddingModel.embed("苹果");
List<Double> banana = embeddingModel.embed("香蕉");
List<Double> phone = embeddingModel.embed("手机");

// 计算余弦相似度
double similarity1 = cosineSimilarity(apple, banana);  // ≈ 0.85
double similarity2 = cosineSimilarity(apple, phone);    // ≈ 0.30
```

**面试高频问题**：

**Q: Embedding 和 One-Hot 编码有什么区别？**

| 维度 | One-Hot编码 | Embedding |
|------|-------------|-----------|
| 维度 | 高维稀疏（词表大小） | 低维稠密（通常128-4096） |
| 语义 | 无语义信息 | 蕴含语义关系 |
| 可学习 | 否 | 是（通过神经网络训练） |
| 维度灾难 | 严重 | 规避 |
| 示例 | [0,1,0,0,0,...] | [0.23, -0.45, 0.78, ...] |

### 1.2 Spring AI Embedding 配置

```yaml
spring:
  ai:
    # OpenAI Embedding
    openai:
      api-key: ${OPENAI_API_KEY}
      embedding:
        options:
          model: text-embedding-3-small  # 1536维，性价比高
          # text-embedding-3-large: 3072维，更精确但更贵
          # text-embedding-ada-002: 1536维，GPT-3时代模型（逐步淘汰）
    
    # DeepSeek Embedding（国产，高性价比）
    deepseek:
      api-key: ${DEEPSEEK_API_KEY}
      embedding:
        options:
          model: deepseek-text-embedding
    
    # 本地 Embedding（数据安全场景）
    # 需要下载模型文件，通过 Ollama 或本地部署
    ollama:
      base-url: http://localhost:11434
      embedding:
        options:
          model: nomic-embed-text  # 768维，支持中文
```

### 1.3 EmbeddingModel 接口

```java
// Spring AI 的 EmbeddingModel 接口
public interface EmbeddingModel {
    
    // 同步嵌入
    EmbeddingResponse embed(Document document);
    
    // 批量嵌入
    List<EmbeddingResponse> embed(List<Document> documents);
    
    // 返回向量维度
    int dimensions();
}
```

**使用示例**：

```java
@Service
@RequiredArgsConstructor
public class EmbeddingService {
    
    private final EmbeddingModel embeddingModel;
    
    // 单条嵌入
    public float[] embedText(String text) {
        EmbeddingResponse response = embeddingModel.embed(
            new org.springframework.ai.document.Document(text)
        );
        return response.getResult().getOutput();
    }
    
    // 批量嵌入（推荐，提高吞吐量）
    public List<float[]> embedTexts(List<String> texts) {
        List<Document> documents = texts.stream()
            .map(Document::new)
            .toList();
        
        EmbeddingResponse response = embeddingModel.embed(documents);
        return response.getResults().stream()
            .map(Embedding::getOutput)
            .toList();
    }
    
    // 带元数据的文档嵌入
    public float[] embedDocument(String content, Map<String, Object> metadata) {
        Document doc = Document.builder()
            .content(content)
            .metadata(metadata)  // 如：source, page, category等
            .id(UUID.randomUUID().toString())
            .build();
        
        return embeddingModel.embed(doc).getResult().getOutput();
    }
}
```

### 1.4 主流 Embedding 模型对比

| 模型 | 维度 | 特点 | 适用场景 | 成本 |
|------|------|------|----------|------|
| text-embedding-3-small | 1536 | 高性价比，中英文均衡 | 通用场景 | $0.02/1M tokens |
| text-embedding-3-large | 3072 | 精度最高 | 高精度需求 | $0.13/1M tokens |
| nomic-embed-text | 768 | 开源，支持长文本 | 本地部署 | 免费 |
| m3e-large | 1024 | 中文优化，开源 | 中文场景 | 免费 |
| bge-large-zh | 1024 | 中英文，CCNews预训练 | 中英双语 | 免费 |
| DeepSeek-Embed | 1024 | 国产性价比 | 中文+代码 | 低 |

---

## 二、VectorStore 抽象与实现

### 2.1 VectorStore 接口设计

```java
// Spring AI 的 VectorStore 接口
public interface VectorStore {
    
    // 添加文档
    void add(List<Document> documents);
    
    // 删除文档
    void delete(List<String> ids);
    
    // 相似度搜索
    List<Document> similaritySearch(String query);
    
    // 带选项的搜索
    List<Document> similaritySearch(SearchRequest request);
    
    // 过滤搜索（支持元数据过滤）
    List<Document> similaritySearch(String query, FilterExpression filter);
    
    // 返回向量维度（与EmbeddingModel配合）
    default int getDimension() { ... }
}

// 搜索请求
public class SearchRequest {
    private String query;              // 查询文本
    private int topK = 4;              // 返回数量
    private double similarityThreshold = 0.75;  // 相似度阈值
    private FilterExpression filter;    // 元数据过滤
    private String similarityMetric;    // COSINE/EUCLIDEAN/DOT_PRODUCT
}
```

### 2.2 过滤器表达式（FilterExpression）

VectorStore 的强大之处在于支持**元数据过滤**：

```java
@Service
@RequiredArgsConstructor
public class FilteredSearchService {
    
    private final VectorStore vectorStore;
    
    // 单条件过滤
    public List<Document> searchByCategory(String query, String category) {
        FilterExpression filter = FilterExpressionBuilder.builder()
            .equal("category", category)
            .build();
        
        return vectorStore.similaritySearch(
            SearchRequest.builder()
                .query(query)
                .topK(10)
                .filterExpression(filter)
                .build()
        );
    }
    
    // 多条件AND过滤
    public List<Document> searchByDateRange(String query, String startDate, String endDate) {
        FilterExpression filter = FilterExpressionBuilder.builder()
            .and(
                FilterExpressionBuilder.builder()
                    .gte("createdAt", startDate)
                    .lte("createdAt", endDate)
                    .build(),
                FilterExpressionBuilder.builder()
                    .equal("status", "published")
                    .build()
            )
            .build();
        
        return vectorStore.similaritySearch(query, filter);
    }
    
    // OR条件过滤
    public List<Document> searchMultiCategory(String query, List<String> categories) {
        FilterExpression filter = FilterExpressionBuilder.builder()
            .in("category", categories.toArray(new String[0]))
            .build();
        
        return vectorStore.similaritySearch(query, filter);
    }
    
    // 复杂嵌套过滤
    public List<Document> searchComplex(String query) {
        FilterExpression filter = FilterExpressionBuilder.builder()
            .and(
                FilterExpressionBuilder.builder()
                    .or(
                        FilterExpressionBuilder.builder()
                            .equal("source", "manual")
                            .equal("source", "auto")
                            .build()
                    )
                    .build(),
                FilterExpressionBuilder.builder()
                    .notEqual("deleted", true)
                    .gte("score", 0.5)
                    .build()
            )
            .build();
        
        return vectorStore.similaritySearch(query, filter);
    }
}
```

### 2.3 主流 VectorStore 实现对比

| 向量数据库 | 特点 | 适用场景 | Spring AI支持 | 部署方式 |
|-----------|------|----------|---------------|----------|
| **Milvus** | 专为向量设计，性能最强 | 大规模生产环境 | ✅ 完整支持 | 云/K8S/本地 |
| **Pgvector** | PostgreSQL扩展，SQL统一管理 | 中小型，SQL优先团队 | ✅ 完整支持 | PostgreSQL附加 |
| **Chroma** | 轻量，嵌入式首选 | POC/原型/小规模 | ✅ 完整支持 | Python/本地 |
| **Weaviate** | 原生混合搜索(向量+关键词) | 混合检索场景 | ✅ 完整支持 | K8S/云 |
| **Qdrant** | 高性能，Rust实现 | 低延迟需求 | ✅ 完整支持 | Docker/K8S |
| **Elasticsearch** | 企业已有，混合检索 | Elasticsearch用户 | ✅ 完整支持 | 现有ES集群 |
| **In-Memory** | 纯内存，最快 | 小规模/测试 | ✅ 完整支持 | 内存 |

---

## 三、Milvus 企业级实战

### 3.1 配置与初始化

```yaml
# application.yml
spring:
  ai:
    vectorstore:
      milvus:
        url: ${MILVUS_URL:http://localhost:19530}
        database-name: ${MILVUS_DB:default}
        username: ${MILVUS_USER:root}
        password: ${MILVUS_PASSWORD:milvus}
        collection:
          name: documents
          dimension: 1536  # 与Embedding模型维度一致
          metric-type: COSINE  # COSINE/IP/L2
          index-type: IVF_FLAT  # 索引类型
```

```java
@Configuration
public class MilvusVectorStoreConfig {
    
    @Bean
    public VectorStore milvusVectorStore(
            EmbeddingModel embeddingModel,
            MilvusApi milvusApi) {
        
        return MilvusVectorStore.builder(embeddingModel, milvusApi)
            .collectionName("tech_articles")
            .databaseName("ai_app")
            .indexType(IndexType.IVF_FLAT)
            .metricType(MetricType.COSINE)
            .topK(5)
            .build();
    }
}
```

### 3.2 文档管理与搜索

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class ArticleVectorService {
    
    private final VectorStore vectorStore;
    private final EmbeddingModel embeddingModel;
    
    // 批量导入文档
    public void importArticles(List<Article> articles) {
        List<Document> documents = articles.stream()
            .map(this::articleToDocument)
            .toList();
        
        log.info("开始向量化导入 {} 篇文章", documents.size());
        vectorStore.add(documents);
        log.info("导入完成");
    }
    
    // 语义搜索
    public List<SearchResult> semanticSearch(String query, int limit) {
        SearchRequest request = SearchRequest.builder()
            .query(query)
            .topK(limit)
            .similarityThreshold(0.75)
            .build();
        
        return vectorStore.similaritySearch(request)
            .stream()
            .map(this::documentToResult)
            .toList();
    }
    
    // 带过滤的搜索
    public List<SearchResult> filteredSearch(String query, String category, int limit) {
        FilterExpression filter = FilterExpressionBuilder.builder()
            .equal("category", category)
            .equal("status", "published")
            .build();
        
        SearchRequest request = SearchRequest.builder()
            .query(query)
            .topK(limit)
            .filterExpression(filter)
            .build();
        
        return vectorStore.similaritySearch(request)
            .stream()
            .map(this::documentToResult)
            .toList();
    }
    
    // 删除过期文档
    public void deleteOldArticles(String beforeDate) {
        FilterExpression filter = FilterExpressionBuilder.builder()
            .lt("createdAt", beforeDate)
            .equal("status", "archived")
            .build();
        
        // Milvus 需要先查询再删除
        List<Document> toDelete = vectorStore.similaritySearch(
            SearchRequest.builder()
                .query("*")
                .topK(10000)
                .filterExpression(filter)
                .build()
        );
        
        if (!toDelete.isEmpty()) {
            List<String> ids = toDelete.stream()
                .map(Document::getId)
                .toList();
            vectorStore.delete(ids);
            log.info("删除了 {} 篇过期文档", ids.size());
        }
    }
    
    private Document articleToDocument(Article article) {
        return Document.builder()
            .id(article.getId())
            .content(article.getContent())
            .metadata(Map.of(
                "title", article.getTitle(),
                "category", article.getCategory(),
                "author", article.getAuthor(),
                "createdAt", article.getCreatedAt().toString(),
                "status", article.getStatus(),
                "tags", String.join(",", article.getTags())
            ))
            .build();
    }
    
    private SearchResult documentToResult(Document doc) {
        return new SearchResult(
            doc.getId(),
            doc.getMetadata("title"),
            doc.getContent(),
            doc.getMetadata("category"),
            doc.getMetadata("author")
        );
    }
    
    public record SearchResult(
        String id,
        String title,
        String content,
        String category,
        String author
    ) {}
}
```

---

## 四、Pgvector 实战（SQL优先团队首选）

### 4.1 PostgreSQL 扩展安装

```sql
-- 安装 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建文档表
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    title VARCHAR(500),
    category VARCHAR(100),
    author VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'draft',
    embedding VECTOR(1536)  -- 1536维，与text-embedding-3-small一致
);

-- 创建向量索引（HNSW vs IVF_FLAT）
-- HNSW: 更高精度，更快查询，但索引构建慢，内存占用大
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);

-- 或使用 IVF_FLAT（适合超大规模数据）
-- CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 4.2 Spring Data JDBC 集成

```yaml
# application.yml
spring:
  ai:
    vectorstore:
      pgvector:
        initialize-schema: true  # 自动建表
```

```java
@Repository
public interface DocumentRepository extends CrudRepository<PgDocument, UUID> {
    
    // 全文搜索
    @Query("""
        SELECT * FROM documents 
        WHERE status = 'published'
        AND to_tsvector('chinese', content) @@ plainto_tsquery('chinese', :keyword)
        LIMIT :limit
        """)
    List<PgDocument> fullTextSearch(@Param("keyword") String keyword, @Param("limit") int limit);
    
    // 混合搜索（向量+关键词）
    @Query(value = """
        SELECT *, 1 - (embedding <=> :embedding) as similarity
        FROM documents
        WHERE status = 'published'
        AND to_tsvector('chinese', content) @@ plainto_tsquery('chinese', :keyword)
        ORDER BY embedding <=> :embedding
        LIMIT :limit
        """, nativeQuery = true)
    List<PgDocument> hybridSearch(
        @Param("embedding") float[] embedding,
        @Param("keyword") String keyword,
        @Param("limit") int limit
    );
}

@Entity
@Table(name = "documents")
public class PgDocument {
    @Id
    private UUID id;
    
    @Column(columnDefinition = "text")
    private String content;
    
    private String title;
    private String category;
    
    @Column(name = "embedding", columnDefinition = "vector(1536)")
    private float[] embedding;
    
    private String status;
    private Instant createdAt;
}
```

### 4.3 混合搜索实现

```java
@Service
@RequiredArgsConstructor
public class HybridSearchService {
    
    private final VectorStore vectorStore;
    private final EmbeddingModel embeddingModel;
    private final DocumentRepository documentRepository;
    
    // 混合搜索：向量相似度 + BM25关键词权重
    public List<HybridSearchResult> hybridSearch(String query, int limit) {
        // 1. 向量搜索
        List<Document> vectorResults = vectorStore.similaritySearch(
            SearchRequest.builder()
                .query(query)
                .topK(limit * 2)  // 多取一些用于融合
                .build()
        );
        
        // 2. 关键词搜索
        List<PgDocument> keywordResults = documentRepository.fullTextSearch(query, limit * 2);
        
        // 3. RRF融合算法（Reciprocal Rank Fusion）
        Map<String, HybridSearchResult> fused = new HashMap<>();
        int k = 60;  // RRF参数
        
        // 向量搜索结果融合
        for (int i = 0; i < vectorResults.size(); i++) {
            String id = vectorResults.get(i).getId();
            double score = 1.0 / (k + i + 1);
            fused.computeIfAbsent(id, id_ -> HybridSearchResult.builder()
                .document(vectorResults.get(i))
                .vectorScore(score)
                .build());
        }
        
        // 关键词搜索结果融合
        for (int i = 0; i < keywordResults.size(); i++) {
            String id = keywordResults.get(i).getId().toString();
            double score = 1.0 / (k + i + 1);
            fused.computeIfAbsent(id, id_ -> {
                Document doc = new Document(id, keywordResults.get(i).getContent());
                return HybridSearchResult.builder()
                    .document(doc)
                    .keywordScore(score)
                    .build();
            });
            fused.get(id).setKeywordScore(score);
        }
        
        // 4. 按综合分数排序
        return fused.values().stream()
            .sorted((a, b) -> Double.compare(
                b.getCombinedScore(), a.getCombinedScore()))
            .limit(limit)
            .toList();
    }
}

@Data
@Builder
public class HybridSearchResult {
    private Document document;
    private double vectorScore;
    private double keywordScore;
    
    public double getCombinedScore() {
        // 可调权重：alpha=1纯向量，alpha=0纯关键词
        double alpha = 0.7;
        return alpha * vectorScore + (1 - alpha) * keywordScore;
    }
}
```

---

## 五、向量索引与性能优化

### 5.1 索引类型对比

| 索引类型 | 原理 | 适用规模 | 精度 | 构建速度 | 查询速度 | 内存占用 |
|---------|------|---------|------|---------|---------|---------|
| **FLAT** | 暴力搜索 | <10万 | 100% | 无需构建 | 慢 | 无额外 |
| **IVF_FLAT** | 聚类+暴力搜索 | 100万-1亿 | 高 | 快 | 中 | 中 |
| **IVF_PQ** | 聚类+压缩 | 亿级+ | 中 | 快 | 快 | 低（压缩） |
| **HNSW** | 图索引 | 10万-10亿 | 最高 | 慢 | 最快 | 高 |
| **DiskANN** | 图+磁盘 | 十亿级+ | 高 | 中 | 快 | 低（磁盘） |

**面试高频问题**：

**Q: HNSW 索引的原理是什么？**

A: HNSW（Hierarchical Navigable Small World）是一种基于图的近似最近邻搜索算法：

```
核心思想：构建多层图，上层稀疏、下层稠密，搜索时从上层快速定位大致区域，再逐层细化

构建过程：
1. 初始化多层图（L0 到 L_max）
2. 每个向量随机分配层数（越高层节点越少）
3. 高层用于快速导航，低层用于精确定位
4. 连接同层最近邻节点（通常使用贪心+改进的贪心）

搜索过程：
1. 从最高层入口节点开始
2. 贪心搜索找到当前层最近邻
3. 下降到下一层，从上层的最近邻开始搜索
4. 重复直到最底层
5. 返回最终最近邻
```

### 5.2 生产环境索引配置

```java
@Configuration
public class VectorIndexConfig {
    
    @Bean
    public VectorStore optimizedVectorStore(
            EmbeddingModel embeddingModel,
            MilvusApi milvusApi) {
        
        // 根据数据规模选择配置
        return MilvusVectorStore.builder(embeddingModel, milvusApi)
            .collectionName("production_documents")
            .indexType(IndexType.HNSW)  // 生产环境推荐 HNSW
            .metricType(MetricType.COSINE)
            
            // HNSW 参数优化
            .indexParameters("{\"M\": 16, \"efConstruction\": 200}")
            
            // 搜索参数
            .searchParameters("{\"ef\": 128}")  // ef越大精度越高，但越慢
            
            .topK(10)
            .build();
    }
}
```

**HNSW 参数调优建议**：

| 参数 | 取值建议 | 说明 |
|------|---------|------|
| M | 8-64 | 邻居数，内存敏感场景选小值 |
| efConstruction | 100-400 | 构建时动态列表大小，越大越精确但越慢 |
| ef | 50-1000 | 搜索时动态列表大小，实时性要求高用小值 |

### 5.3 分区（Partition）设计

```java
@Service
@RequiredArgsConstructor
public class PartitionedVectorService {
    
    private final MilvusConnectionFactory connectionFactory;
    private final EmbeddingModel embeddingModel;
    
    // 创建分区
    public void createPartition(String category) {
        // Milvus 支持按分区隔离数据
        // 不同类别的文档存储在不同分区
        // 搜索时可限定分区，减少搜索范围
        // 这部分通过 Milvus SDK 直接操作
    }
    
    // 按分区搜索
    public List<Document> searchInPartition(String query, String category, int limit) {
        // 通过 filter 模拟分区搜索
        FilterExpression filter = FilterExpressionBuilder.builder()
            .equal("_partition", category)  // Milvus 分区字段
            .build();
        
        VectorStore vs = getOrCreateVectorStore(category);
        return vs.similaritySearch(
            SearchRequest.builder()
                .query(query)
                .topK(limit)
                .filterExpression(filter)
                .build()
        );
    }
    
    private VectorStore getOrCreateVectorStore(String category) {
        // 可按类别创建独立的 VectorStore 实例
        // 实现数据隔离和独立配置
        return MilvusVectorStore.builder(embeddingModel, connectionFactory.getObject())
            .collectionName("documents_" + category)
            .build();
    }
}
```

---

## 六、企业级文档向量化实战

### 6.1 完整数据管道

```java
@Service
@RequiredArgsConstructor
@Slf4j
public class DocumentVectorPipeline {
    
    private final DocumentReader documentReader;
    private final EmbeddingModel embeddingModel;
    private final VectorStore vectorStore;
    private final ApplicationEventPublisher eventPublisher;
    
    // 完整数据导入流程
    public void ingestDocuments(Path directory) {
        log.info("开始文档导入: {}", directory);
        
        // 1. 文档读取（支持多种格式）
        List<Document> documents = documentReader.read(directory);
        log.info("读取到 {} 个文档块", documents.size());
        
        // 2. 去重检查（基于内容hash）
        documents = deduplicate(documents);
        log.info("去重后剩余 {} 个文档块", documents.size());
        
        // 3. 批量向量化
        int batchSize = 100;
        List<List<Document>> batches = partition(documents, batchSize);
        
        int total = 0;
        for (List<Document> batch : batches) {
            vectorStore.add(batch);
            total += batch.size();
            log.info("已处理 {}/{} 个文档", total, documents.size());
        }
        
        // 4. 发布完成事件
        eventPublisher.publishEvent(new DocumentsIngestedEvent(this, total));
        log.info("文档导入完成，共 {} 个文档", total);
    }
    
    // 支持多种格式的文档读取
    @Bean
    public DocumentReader documentReader() {
        return new SupportedFormatsDocumentReader(
            new PdfDocumentReader("classpath:docs/*.pdf"),
            new TextDocumentReader("classpath:docs/*.txt"),
            new WordDocumentReader("classpath:docs/*.docx"),
            new MarkdownDocumentReader("classpath:docs/*.md")
        );
    }
    
    private List<Document> deduplicate(List<Document> documents) {
        Set<String> seen = new HashSet<>();
        return documents.stream()
            .filter(doc -> {
                String hash = hashContent(doc.getContent());
                return seen.add(hash);
            })
            .toList();
    }
    
    private String hashContent(String content) {
        // 使用MD5或SHA256计算内容hash
        return DigestUtils.md5Hex(content);
    }
}
```

### 6.2 增量更新策略

```java
@Service
@RequiredArgsConstructor
public class IncrementalVectorUpdate {
    
    private final VectorStore vectorStore;
    private final EmbeddingModel embeddingModel;
    private final DocumentRepository documentRepository;
    
    // 增量同步：检测变化，只同步新增/修改的文档
    public void incrementalSync() {
        // 1. 获取上次同步时间
        Instant lastSync = getLastSyncTime();
        
        // 2. 查询变更的文档
        List<Article> changedArticles = documentRepository
            .findByUpdatedAtAfter(lastSync);
        
        // 3. 分类处理：新增/修改/删除
        for (Article article : changedArticles) {
            if (article.isDeleted()) {
                // 删除
                vectorStore.delete(List.of(article.getId().toString()));
            } else if (article.isNew()) {
                // 新增
                vectorStore.add(List.of(articleToDocument(article)));
            } else {
                // 更新：先删后增
                vectorStore.delete(List.of(article.getId().toString()));
                vectorStore.add(List.of(articleToDocument(article)));
            }
        }
        
        // 4. 更新同步时间
        updateLastSyncTime(Instant.now());
    }
    
    // 定期全量重建（防止向量漂移）
    @Scheduled(cron = "0 0 3 * * ?")  // 每天凌晨3点
    public void rebuildIndex() {
        log.info("开始全量重建向量索引");
        
        // 1. 创建新集合
        String newCollection = "documents_v" + System.currentTimeMillis();
        VectorStore newStore = createNewCollection(newCollection);
        
        // 2. 全量导入
        List<Article> allArticles = documentRepository.findAll();
        for (Article article : allArticles) {
            newStore.add(List.of(articleToDocument(article)));
        }
        
        // 3. 原子切换
        switchCollection(newCollection);
        
        // 4. 删除旧集合
        deleteOldCollection();
        
        log.info("全量重建完成");
    }
}
```

---

## 七、面试高频问题汇总

### Q1: 向量数据库和传统数据库有什么区别？

| 维度 | 传统关系型/NoSQL | 向量数据库 |
|------|-----------------|-----------|
| 数据类型 | 结构化/半结构化 | 高维向量 |
| 检索方式 | 精确匹配、关键词 | 近似最近邻（ANN） |
| 相似度度量 | =, >, < | COSINE/DOT_PRODUCT/EUCLIDEAN |
| 索引 | B+Tree, Hash | HNSW, IVF, PQ |
| 适用场景 | 事务处理 | 语义搜索、推荐 |

### Q2: 如何选择向量数据库？

**选择决策树**：

```
数据规模 < 10万？
├── 是 → Chroma（轻量，易用）或 Pgvector（已有PostgreSQL）
└── 否 → 规模预估？

数据规模 100万-1亿？
├── 已有PostgreSQL？ → Pgvector
└── 无 → Milvus/Qdrant

数据规模 > 1亿？
├── 低延迟需求 → Qdrant
└── 高吞吐量 → Milvus

特殊需求？
├── 原生混合搜索 → Weaviate
├── 已有Elasticsearch → ES向量搜索
└── 完全本地/离线 → Qdrant/Milvus本地部署
```

### Q3: 向量召回率低怎么排查？

```java
@Service
@RequiredArgsConstructor
public class VectorQualityMonitor {
    
    private final VectorStore vectorStore;
    private final EmbeddingModel embeddingModel;
    
    // 定期评估向量质量
    public void evaluateQuality() {
        // 1. 准确率评估（使用标注数据集）
        List<TestCase> testCases = loadTestCases();
        
        int correct = 0;
        for (TestCase tc : testCases) {
            List<Document> results = vectorStore.similaritySearch(
                SearchRequest.builder()
                    .query(tc.getQuery())
                    .topK(tc.getExpectedTopK())
                    .build()
            );
            
            Set<String> expected = new HashSet<>(tc.getExpectedIds());
            Set<String> actual = results.stream()
                .map(Document::getId)
                .collect(Collectors.toSet());
            
            if (actual.containsAll(expected)) {
                correct++;
            }
        }
        
        double accuracy = (double) correct / testCases.size();
        log.info("向量检索准确率: {:.2f}%", accuracy * 100);
        
        if (accuracy < 0.8) {
            // 触发告警和自动修复
            alertLowAccuracy();
        }
    }
    
    // 常见问题及解决方案
    public void troubleshoot() {
        // 问题1: 分块策略不合理
        analyzeChunkSize();
        
        // 问题2: Embedding模型不匹配
        compareEmbeddingModels();
        
        // 问题3: 索引参数不合适
        tuneIndexParameters();
        
        // 问题4: 数据质量问题
        analyzeDataQuality();
    }
}
```

**召回率低常见原因及解决方案**：

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 语义不相关 | 分块太小/太大 | 调整chunk_size |
| 类别混淆 | 模型不匹配领域 | 换用领域微调Embedding |
| 数值不稳定 | 缺少归一化 | 检查向量归一化 |
| 索引不合适 | HNSW参数太小 | 增大ef/M参数 |

### Q4: 如何实现向量数据的备份与恢复？

```java
@Service
@RequiredArgsConstructor
public class VectorBackupService {
    
    private final MilvusApi milvusApi;
    
    // 导出向量数据
    public void backupCollection(String collectionName, Path backupDir) {
        // 1. 导出元数据
        String metadata = milvusApi.exportMetadata(collectionName);
        Files.writeString(backupDir.resolve("metadata.json"), metadata);
        
        // 2. 导出向量数据（分批次）
        int batchSize = 10000;
        int offset = 0;
        int part = 0;
        
        while (true) {
            List<Doc> docs = milvusApi.query(
                collectionName,
                offset,
                batchSize
            );
            
            if (docs.isEmpty()) break;
            
            String json = new ObjectMapper().writeValueAsString(docs);
            Files.writeString(backupDir.resolve("vectors_part" + part + ".json"), json);
            
            offset += batchSize;
            part++;
        }
        
        log.info("备份完成，共 {} 批次", part);
    }
    
    // 恢复向量数据
    public void restoreCollection(String collectionName, Path backupDir) {
        // 创建新集合
        milvusApi.createCollection(collectionName, 1536);
        
        // 读取并导入
        List<Path> parts = Files.list(backupDir)
            .filter(p -> p.getFileName().toString().startsWith("vectors_part"))
            .sorted()
            .toList();
        
        for (Path part : parts) {
            String json = Files.readString(part);
            List<Doc> docs = new ObjectMapper().readValue(json, 
                new TypeReference<List<Doc>>() {});
            
            milvusApi.insert(collectionName, docs);
        }
        
        log.info("恢复完成，共 {} 批次", parts.size());
    }
}
```

---

## 总结

本文深入解析了 Spring AI 中 Embedding 模型和向量数据库的核心知识：

| 知识点 | 核心要点 |
|--------|----------|
| **Embedding** | 向量化原理、模型配置、维度选择、主流模型对比 |
| **VectorStore** | 统一抽象、FilterExpression、批量操作 |
| **Milvus** | 企业级生产配置、索引优化、分区设计 |
| **Pgvector** | SQL统一管理、混合搜索、RRF融合 |
| **索引优化** | HNSW/IVF原理、参数调优、召回率监控 |
| **数据管道** | 文档读取、去重、增量同步、全量重建 |

**下期预告**：《Spring AI面试八股文（三）——Function Calling与工具调用实战》，我们将深入探讨：
- Spring AI @Tool 注解深入原理
- 多工具编排与依赖管理
- 异步工具调用与并行执行
- 复杂业务场景实战（数据库查询、API调用、文件操作）
- Function Calling 安全与权限控制

---

> **推荐阅读**
> - [AI大模型面试八股文（四）——大模型应用开发与Agent框架](/posts/AI大模型面试八股文（四）——大模型应用开发与Agent框架/)：RAG、Function Calling基础原理
> - [AI大模型面试八股文（六）——大模型系统设计与工程实践](/posts/AI大模型面试八股文（六）——大模型系统设计与工程实践/)：RAG完整架构设计
> - [Spring Boot自动配置原理与自定义Starter开发](/posts/Spring面试八股文（九）——Spring-Boot自动配置原理与自定义Starter开发/)：Spring AI自动配置机制基于此实现
