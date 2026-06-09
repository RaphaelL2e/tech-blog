---
title: "AI大模型面试八股文（一）——大模型基础与Transformer架构"
date: 2026-06-08T10:00:00+08:00
draft: false
categories: ["AI"]
tags: ["AI", "大模型", "Transformer", "注意力机制", "LLM", "面试"]
---

# AI大模型面试八股文（一）——大模型基础与Transformer架构

> 面试高频问题：什么是大模型？Transformer的核心原理是什么？自注意力机制如何工作？位置编码为什么重要？本文作为AI大模型系列的开篇，带你从零理解大模型的技术底座。

## 引言

2022年底ChatGPT的发布，标志着AI大模型时代的到来。从GPT系列到LLaMA、Qwen、DeepSeek，大模型已经成为技术面试的必考领域。理解大模型，必须从Transformer开始——它是所有现代大模型的基石。

**本文要点**：
1. 大模型的定义与发展历程
2. Transformer架构全景
3. 自注意力机制深度解析
4. 多头注意力与位置编码
5. 编码器与解码器对比
6. 面试高频问题精讲

## 一、大模型基础概念

### 1.1 什么是大模型？

大模型（Large Language Model, LLM）是指参数量巨大（通常数十亿到数万亿）、在海量文本数据上训练的深度学习模型。

| 模型 | 参数量 | 发布时间 | 特点 |
|------|--------|---------|------|
| GPT-3 | 1750亿 | 2020 | 证明规模的力量 |
| GPT-4 | 未公开（推测万亿级） | 2023 | 多模态，推理增强 |
| LLaMA 2 | 7B-70B | 2023 | 开源里程碑 |
| Qwen 2.5 | 0.5B-72B | 2024 | 中文能力强 |
| DeepSeek-V3 | 671B（MoE） | 2024 | MoE架构，性价比极高 |
| LLaMA 3 | 8B-405B | 2024 | 开源新标杆 |

### 1.2 大模型的核心能力

```
大模型能力图谱
├── 语言理解：阅读理解、情感分析、意图识别
├── 语言生成：对话、写作、翻译、摘要
├── 推理能力：逻辑推理、数学计算、代码生成
├── 知识检索：事实问答、百科知识
├── 指令遵循：按格式输出、遵循约束条件
└── 多模态：图像理解、语音处理（部分模型）
```

### 1.3 大模型的发展脉络

```
统计NLP → 深度学习NLP → 预训练语言模型 → 大语言模型
  (2010前)    (2013-2017)     (2018-2020)     (2020-至今)
    │             │                │                │
  HMM/NB      CNN/RNN/LSTM     BERT/GPT-1      GPT-3/4
  规则驱动     序列建模        双向/单向预训练    规模涌现
```

**关键里程碑**：
- **2017**：Transformer论文《Attention Is All You Need》发布
- **2018**：GPT-1发布，开创"预训练+微调"范式
- **2018**：BERT发布，双向预训练刷新NLP记录
- **2020**：GPT-3证明"规模即力量"（Scaling Law）
- **2022**：ChatGPT展示RLHF对齐的力量
- **2023**：开源大模型爆发（LLaMA、Mistral等）

### 1.4 Scaling Law（规模法则）

OpenAI 2020年提出的经验规律：模型性能与三个因素成幂律关系。

```
Loss ∝ C^(-α)

C = 6ND （计算量）
N = 模型参数量
D = 训练数据量（token数）

核心结论：
1. 增大参数量和数据量都能提升性能
2. 两者需要同步增长，不能偏废
3. 计算预算有限时，优先增大模型（Chinchilla结论修正为均衡增长）
```

**面试重点**：Scaling Law告诉我们，大模型不是"大力出奇迹"的盲目堆参数，而是参数、数据、计算三者需要协调增长。

## 二、Transformer架构全景

### 2.1 整体架构

```
输入序列                              输出序列
   │                                    ↑
   ↓                                    │
┌──────────┐                    ┌──────────────┐
│ Input    │                    │ Output       │
│ Embedding│                    │ Embedding    │
│ + PosEnc │                    │ + PosEnc     │
└────┬─────┘                    └──────┬───────┘
     │                                 │
     ↓                                 ↓
┌──────────┐                    ┌──────────────┐
│ Encoder  │                    │ Decoder      │
│ Block ×N │ ────K,V─────────→ │ Block ×N     │
│ (自注意力 │                    │ (掩码自注意力 │
│  + FFN)  │                    │  + 交叉注意力  │
└──────────┘                    │  + FFN)      │
                                └──────┬───────┘
                                       │
                                       ↓
                                ┌──────────────┐
                                │ Linear +     │
                                │ Softmax      │
                                └──────────────┘
```

**关键设计**：
- **Encoder**：理解输入（双向注意力）
- **Decoder**：生成输出（单向掩码注意力）
- **残差连接** + **层归一化**：每个子层后

### 2.2 数据流详解

```python
# Transformer数据流（伪代码）

# 1. 输入嵌入
x = embedding(input_tokens)        # [batch, seq_len, d_model]
x = x + positional_encoding(seq_len)  # 加入位置信息

# 2. Encoder
for encoder_block in encoder_blocks:
    # 自注意力
    attn_out = multi_head_attention(x, x, x)  # Q=K=V=x
    x = layer_norm(x + attn_out)               # 残差 + LN
    
    # 前馈网络
    ff_out = feed_forward(x)
    x = layer_norm(x + ff_out)                 # 残差 + LN

# 3. Decoder
for decoder_block in decoder_blocks:
    # 掩码自注意力（不能看到未来token）
    attn1 = masked_multi_head_attention(y, y, y)
    y = layer_norm(y + attn1)
    
    # 交叉注意力（Q来自decoder, K/V来自encoder）
    attn2 = multi_head_attention(y, encoder_out, encoder_out)
    y = layer_norm(y + attn2)
    
    # 前馈网络
    ff_out = feed_forward(y)
    y = layer_norm(y + ff_out)

# 4. 输出
logits = linear(y)                  # [batch, seq_len, vocab_size]
probs = softmax(logits)
```

## 三、自注意力机制深度解析

### 3.1 为什么需要注意力？

**RNN的问题**：
- 顺序计算，无法并行
- 长距离依赖衰减（梯度消失）
- 固定大小的隐状态瓶颈

**注意力的核心思想**：每个位置可以直接"关注"序列中的任意其他位置，一步到位获取全局信息。

### 3.2 自注意力计算过程

```
输入: X [seq_len, d_model]

步骤1: 线性变换生成Q、K、V
  Q = X × W_Q    [seq_len, d_k]
  K = X × W_K    [seq_len, d_k]
  V = X × W_V    [seq_len, d_v]

步骤2: 计算注意力分数
  scores = Q × K^T / √d_k    [seq_len, seq_len]

步骤3: Softmax归一化
  attn_weights = softmax(scores)    [seq_len, seq_len]

步骤4: 加权求和
  output = attn_weights × V    [seq_len, d_v]
```

### 3.3 缩放因子√d_k的作用

**问题**：当d_k较大时，Q·K的点积值方差大，导致softmax进入饱和区，梯度极小。

**数学推导**：

```
假设q和k的各元素独立、均值0、方差1

则 q·k = Σ(q_i × k_i)，共d_k项

E[q·k] = 0
Var[q·k] = d_k

标准差 = √d_k

→ 点积值可能很大，softmax梯度趋近于0
→ 除以√d_k，将方差归一化为1
```

**面试回答**：除以√d_k是为了防止点积值过大导致softmax饱和，使梯度消失。这是"缩放点积注意力"名称的由来。

### 3.4 直觉理解

```
自注意力的本质：让序列中的每个位置，通过"查询"找到相关的"键"，然后提取对应的"值"

类比图书馆：
- Q (Query):  "我想找关于Java并发的书"
- K (Key):    每本书的标签/索引（"Java", "并发", "数据库"）
- V (Value):  书的实际内容

注意力 = Q与K的匹配程度 → 决定从V中提取多少信息
```

### 3.5 自注意力 vs 卷积 vs 循环

| 维度 | 自注意力 | 卷积 | 循环 |
|------|---------|------|------|
| 最大路径长度 | O(1) | O(log n) | O(n) |
| 每层复杂度 | O(n²·d) | O(k·n·d) | O(n·d) |
| 并行度 | 完全并行 | 完全并行 | 顺序 |
| 长距离依赖 | 强 | 弱 | 弱 |

**结论**：自注意力在长距离建模上最强，但O(n²)复杂度是瓶颈。

## 四、多头注意力

### 4.1 为什么要多头？

单头注意力只能学习一种"关注模式"，多头让模型同时关注不同子空间的不同模式。

```
例如翻译 "The animal didn't cross the street because it was too tired"

- 头1可能关注 "it" → "animal"（指代消解）
- 头2可能关注 "it" → "tired"（语义关联）
- 头3可能关注位置关系（语法结构）
```

### 4.2 多头注意力计算

```
输入: X [batch, seq_len, d_model]

对每个头h (共h个头):
  Q_h = X × W_Q_h    [batch, seq_len, d_k]    d_k = d_model / h
  K_h = X × W_K_h    [batch, seq_len, d_k]
  V_h = X × W_V_h    [batch, seq_len, d_k]
  
  head_h = Attention(Q_h, K_h, V_h)    [batch, seq_len, d_k]

拼接所有头:
  MultiHead = Concat(head_1, ..., head_h)    [batch, seq_len, d_model]

最终投影:
  output = MultiHead × W_O    [batch, seq_len, d_model]
```

**关键约束**：d_k × h = d_model，保证计算量与单头相当。

### 4.3 常见配置

| 模型 | d_model | 头数h | d_k |
|------|---------|-------|-----|
| Transformer-base | 512 | 8 | 64 |
| Transformer-large | 1024 | 16 | 64 |
| GPT-2 | 768/1024/1280 | 12/16/20 | 64 |
| GPT-3 | 12288 | 96 | 128 |
| LLaMA 2-70B | 8192 | 64 | 128 |

**趋势**：d_k通常在64-128之间，增加模型大小时主要增加头数和d_model。

## 五、位置编码

### 5.1 为什么需要位置编码？

自注意力是**置换不变**的（permutation invariant）：

```
Attention([A, B, C]) 与 Attention([C, A, B]) 的输出关系
≠ 位置交换，而是完全不同的语义

但自注意力本身无法区分位置顺序
→ 需要显式注入位置信息
```

### 5.2 正弦位置编码（原始Transformer）

```
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

pos: 位置索引
i:   维度索引（0到d_model/2）
```

**特性**：
- 每个维度对应不同频率的正弦/余弦波
- 低维高频，高维低频
- 可以通过线性变换表示相对位置

### 5.3 学习式位置编码（BERT/GPT）

```
PE = 可训练参数 [max_seq_len, d_model]

优点：灵活，可以学习最优的位置表示
缺点：无法外推到比训练更长的序列
```

### 5.4 旋转位置编码RoPE（LLaMA系列）

```
核心思想：在复数空间中对Q和K施加旋转，内积自然编码相对位置

q_m = q × e^(i·m·θ)    位置m的query
k_n = k × e^(i·n·θ)    位置n的key

q_m · k_n = q · k × e^(i·(m-n)·θ)
                          ↑
                   只依赖相对位置m-n

优点：
1. 自然编码相对位置
2. 理论上可外推
3. 计算高效
```

**面试重点**：RoPE是当前大模型的主流选择（LLaMA、Qwen、DeepSeek等），因为它能自然地编码相对位置关系。

### 5.5 位置编码对比

| 类型 | 代表模型 | 可外推 | 相对位置 | 复杂度 |
|------|---------|--------|---------|--------|
| 正弦编码 | 原始Transformer | 部分 | 是 | O(1) |
| 学习式 | BERT, GPT | 否 | 否 | O(1) |
| RoPE | LLaMA, Qwen | 是 | 是 | O(1) |
| ALiBi | BLOOM | 是 | 是 | O(n) |
| 1D-RoPE | 大多数新模型 | 是 | 是 | O(1) |

## 六、Encoder vs Decoder

### 6.1 架构对比

| 维度 | Encoder-only | Decoder-only | Encoder-Decoder |
|------|-------------|-------------|-----------------|
| 代表 | BERT | GPT系列 | T5, BART |
| 注意力 | 双向 | 单向（掩码） | 编码双向+解码单向 |
| 训练目标 | MLM（掩码语言模型） | CLM（因果语言模型） | Seq2Seq |
| 擅长 | 理解任务 | 生成任务 | 翻译、摘要 |
| 生成能力 | 弱 | 强 | 中等 |

### 6.2 为什么GPT选择了Decoder-only？

```
1. 生成任务的天然适配
   自回归生成：P(x_t | x_1, ..., x_{t-1})
   掩码注意力保证只看前文，防止信息泄漏

2. 统一的预训练目标
   CLM：预测下一个token
   无需额外任务设计，数据利用率高

3. Scaling Law的优势
   GPT-3论文证明：更大模型+更多数据=更强能力
   单向注意力更适合规模扩展

4. In-context Learning的涌现
   GPT-3发现：模型大到一定程度，无需微调就能理解指令
   这是Decoder-only架构的独特涌现能力
```

### 6.3 Decoder掩码注意力

```python
# 因果掩码（Causal Mask）
# 防止当前位置看到未来token

mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()
# mask[i][j] = True 当 j > i，表示位置i不能看到位置j

scores = scores.masked_fill(mask, float('-inf'))
# 将未来位置的分数设为负无穷，softmax后为0
```

```
掩码矩阵示意（✓=可见，✗=屏蔽）：
      位置0  位置1  位置2  位置3
位置0   ✓     ✗     ✗     ✗
位置1   ✓     ✓     ✗     ✗
位置2   ✓     ✓     ✓     ✗
位置3   ✓     ✓     ✓     ✓
```

## 七、前馈网络（FFN）

### 7.1 标准FFN

```
FFN(x) = ReLU(x × W_1 + b_1) × W_2 + b_2

d_model → d_ff → d_model
典型: 512 → 2048 → 512 (d_ff = 4 × d_model)
```

### 7.2 GLU变体（LLaMA使用）

```
SwiGLU(x) = (Swish(x × W_1) ⊙ (x × V)) × W_2

Swish(x) = x × σ(βx)  （σ是sigmoid）

门控机制：V矩阵作为门控，控制信息流
比ReLU性能更好，当前大模型主流选择
```

### 7.3 FFN的作用

```
注意力层：信息交流（token之间传递信息）
FFN层：  信息变换（每个token独立变换表示）

类比：
注意力 = 通信（讨论问题）
FFN    = 思考（独立消化信息）
```

**研究发现**：FFN可能充当"键值存储"，第一层是键，第二层是值，存储了模型的事实知识。

## 八、Layer Normalization

### 8.1 Post-LN vs Pre-LN

```
Post-LN（原始Transformer）:
  x = LayerNorm(x + Sublayer(x))
  问题：训练不稳定，需要warm-up

Pre-LN（GPT-2及之后主流）:
  x = x + Sublayer(LayerNorm(x))
  优点：训练稳定，不需要warm-up
```

### 8.2 RMSNorm（LLaMA使用）

```
LayerNorm: 归一化均值和方差
RMSNorm:   只归一化均方根，去掉均值偏移

RMSNorm(x) = x / √(mean(x²) + ε) × γ

优点：计算量减少约10%，性能基本持平
```

## 九、面试高频问题

### Q1: Transformer为什么比RNN好？

| 维度 | Transformer | RNN |
|------|------------|-----|
| 并行 | 完全并行 | 顺序 |
| 长距离 | O(1)直达 | O(n)衰减 |
| 训练速度 | 快（GPU友好） | 慢 |
| 灵活性 | 自由组合注意力 | 固定隐状态 |

### Q2: 自注意力的复杂度怎么优化？

| 方法 | 复杂度 | 代表 |
|------|--------|------|
| 标准注意力 | O(n²) | 原始Transformer |
| 稀疏注意力 | O(n√n) | Longformer |
| 线性注意力 | O(n) | Linear Transformer |
| Flash Attention | O(n²)但内存O(n) | FlashAttention-1/2/3 |
| 滑动窗口 | O(n·w) | Mistral |

**注意**：Flash Attention不改变计算复杂度，但通过IO优化大幅减少显存访问，是当前实际使用的标准方案。

### Q3: BERT和GPT的区别？

| 维度 | BERT | GPT |
|------|------|-----|
| 架构 | Encoder-only | Decoder-only |
| 注意力 | 双向 | 单向 |
| 预训练 | MLM（填空） | CLM（续写） |
| 微调 | 判别任务 | 生成任务 |
| 代表应用 | 文本分类、NER | 对话、写作 |

### Q4: 什么是涌现能力（Emergent Abilities）？

```
定义：小模型没有，大模型突然出现的能力

典型涌现能力：
1. In-context Learning（上下文学习）
2. Chain-of-Thought（思维链推理）
3. 指令遵循
4. 代码生成

关键研究：
- 2022年Google论文发现：能力在特定规模阈值后突然出现
- 后续研究质疑：可能是评估指标导致的"假象"
- 争议仍在继续，但大模型能力提升是事实
```

### Q5: 大模型的token是什么？

```
Token = 文本的最小处理单位

主流分词方法：BPE (Byte Pair Encoding)
1. 从字符级别开始
2. 统计高频字符对，合并为新token
3. 重复直到达到目标词表大小

示例：
"hello world" → ["hel", "lo", " world"]

词表大小：
- GPT-2: 50,257
- GPT-4: ~100,000
- LLaMA 2: 32,000
- Qwen 2.5: 151,643（中文友好）

关键：中文1个字≈1-2个token，英文1个单词≈1-1.5个token
```

## 十、总结

**本文核心知识**：

| 模块 | 关键要点 | 面试重点 |
|------|---------|---------|
| 大模型基础 | 参数量大、涌现能力、Scaling Law | 规模法则三要素 |
| Transformer | Encoder-Decoder架构 | 数据流走向 |
| 自注意力 | Q·K^T/√d_k × V | √d_k的缩放作用 |
| 多头注意力 | 多子空间并行关注 | d_k×h=d_model |
| 位置编码 | 正弦/学习/RoPE/ALiBi | RoPE的相对位置编码 |
| Encoder vs Decoder | 双向vs单向 | GPT选择Decoder的原因 |
| FFN | 信息变换/键值存储 | SwiGLU优于ReLU |
| Layer Norm | Post-LN vs Pre-LN | Pre-LN更稳定 |

**核心记忆口诀**：

1. **注意力三件套**：Q查K配V取值
2. **缩放因子**：除以√d_k防饱和
3. **多头**：不同头看不同模式
4. **位置编码**：RoPE编码相对位置
5. **Decoder-only**：统一目标，规模涌现

---

> **下期预告**：《AI大模型面试八股文（二）——大模型训练与微调技术》— 预训练怎么做？SFT和RLHF有什么区别？LoRA等参数高效微调的原理是什么？带你深入理解大模型从训练到对齐的完整流程，敬请期待！

---

*作者：亚飞的技术笔记 | 公众号：亚飞的技术笔记*
