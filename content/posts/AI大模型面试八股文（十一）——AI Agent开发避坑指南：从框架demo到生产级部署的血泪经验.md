---
title: AI大模型面试八股文（十一）——AI Agent开发避坑指南：从框架demo到生产级部署的血泪经验
date: 2026-08-27 10:00:00+08:00
updated: '2026-08-27T10:00:00+08:00'
description: '面试高频问题：AI Agent 开发过程中有哪些常见坑？ReAct 循环如何避免死循环？工具调用失败了怎么处理？上下文超长了怎么办？多 Agent 协作怎么协调？本文从框架 demo 到生产部署，整理 20+ 个真实踩坑经验，帮助你在面试和工程实践中少走弯路。
  Q: 如何设计一个生产级的 AI Agent？'
topic: AI
series: ai-llm-interview
series_order: 11
level: advanced
status: maintained
tags:
- 面试
- AI Agent
- 大模型
- 生产级
- 避坑
- ReAct
categories:
- AI
draft: false
author: 飞哥
---

## AI大模型面试八股文（十一）——AI Agent开发避坑指南：从框架demo到生产级部署的血泪经验

### 🎯 本文目标

AI Agent 是当前大模型应用最热门的方向之一，但把一个 demo 跑通和把它做成生产级系统之间，差了十万八千里。本文从框架选型、ReAct 循环设计、工具调用、上下文管理、多 Agent 协作等维度，系统整理了开发 AI Agent 过程中的 20+ 个真实踩坑经验，帮助你在面试中展现工程深度，也为你的实际项目提供参考。

---

## 一、ReAct 循环：从"能跑"到"跑对"有多远

ReAct（Reasoning + Acting）是目前最主流的 Agent 执行范式：模型先推理，再调用工具，从结果中学习，再推理，再行动——循环往复直到任务完成。听起来简单，但实际开发中每个环节都是坑。

### 1. 循环终止条件：最容易被忽略的兜底逻辑

**踩坑场景**：你写了一个客服 Agent，测试时一切正常，结果上线后发现模型在某个问题上一直循环调用，token 消耗了 10 倍预算才停下来。

**原因分析**：缺少合理的循环终止条件。ReAct 循环需要三层保障：

```python
# 第一层：最大步数限制（必须）
MAX_STEPS = 10

# 第二层：结果质量判断（推荐）
def should_continue(messages, tool_results):
    # 检查是否有实质性进展
    if len(messages) > MAX_STEPS:
        return False
    if is_terminal_state(tool_results):
        return False
    # 检查是否在重复同一动作
    if is_stuck_in_loop(tool_results):
        return False
    return True

# 第三层：预算和超时兜底（生产必须）
def agent_loop_with_budget(prompt, budget_tokens=8000, timeout_seconds=60):
    start_time = time.time()
    cost = 0
    for step in range(MAX_STEPS):
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.warning(f"Step {step}: timeout reached")
            return generate_failure_response("Agent execution timeout")
        if cost > budget_tokens:
            logger.warning(f"Step {step}: token budget exhausted")
            return generate_failure_response("Token budget exceeded")
        # 执行一步...
```

**面试加分点**：能说出"三层兜底"设计的候选人，工程意识明显强于只懂调 API 的同学。

### 2. 工具调用失败：别让一次失败毁掉整个会话

**踩坑场景**：模型调用搜索工具时网络超时，整个 Agent 就卡住了，模型不知道怎么处理这个错误。

**正确做法**：所有工具调用都要包装在错误处理中，并且让模型感知到失败：

```python
# 工具层：标准化错误处理
def execute_tool_safely(tool_name, tool_args, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            result = call_tool(tool_name, tool_args)
            return {
                "status": "success",
                "result": result,
                "attempts": attempt + 1
            }
        except ToolExecutionError as e:
            if attempt == max_retries:
                return {
                    "status": "failed",
                    "error": str(e),
                    "tool": tool_name,
                    "attempts": attempt + 1
                }
            time.sleep(backoff(attempt))  # 指数退避
```

```python
# Agent 层：将工具失败转化为模型可理解的信号
tool_result = execute_tool_safely("web_search", {"query": query})
if tool_result["status"] == "failed":
    # 把错误格式化为自然语言，让模型决定下一步
    feedback = f"[TOOL ERROR] The tool '{tool_result['tool']}' failed after {tool_result['attempts']} attempts. Error: {tool_result['error']}. Consider trying a different approach or refining your search query."
else:
    feedback = f"[TOOL RESULT] {tool_result['result']}"
```

**核心原则**：工具层的异常永远不要直接抛给用户，要经过 Agent 层做一次翻译和决策。

### 3. 工具描述（Tool Description）：模型靠它理解工具

**踩坑场景**：你写了一个工具叫 `get_weather`，描述是"获取天气"，模型输入"北京天气怎么样"，Agent 调用了工具但返回了乱码，或者干脆不调用。

**问题根源**：工具描述不够精确。模型的工具选择完全依赖 description，模糊的描述会导致：

- 选择了错误的工具
- 参数格式不对
- 完全不选择任何工具

**最佳实践**：

```python
# ❌ 差的描述
"get_weather": "Gets weather for a city"

# ✅ 好的描述（参考 Spring AI 的规范）
"get_weather": {
    "description": "Query real-time weather and forecasts for cities worldwide. "
                   "Use this tool when users ask about current weather, temperature, "
                   "precipitation, air quality, or weather forecasts. "
                   "Returns: temperature (°C/°F), humidity, wind speed, conditions, AQI.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name in Chinese or English (e.g., 'Beijing', 'Shanghai', '北京'). "
                             "Must be a valid city name. Do not use abbreviations."
            },
            "country": {
                "type": "string",
                "description": "ISO 3166-1 alpha-2 country code (e.g., 'CN', 'US'). Optional, helps disambiguate cities with the same name."
            }
        },
        "required": ["city"]
    }
}
```

**面试加分点**：描述中包含"何时使用"的指引，模型选择工具的准确率能提升 30%+。

---

## 二、上下文管理：Token 不是无限的

上下文窗口是大模型最宝贵的资源，也是最容易浪费的地方。

### 4. 对话历史截断：不是简单的"只保留最近 N 条"

**踩坑场景**：一个长对话 Agent，运行到一半开始"失忆"——早期讨论的内容模型完全不记得，但明明还有大量 token 余额。

**常见错误做法**：

```python
# ❌ 简单截断：丢失关键上下文
messages = messages[-10:]  # 硬截断最近10条，可能刚好切掉了关键信息

# ❌ 均匀采样：重要信息被稀释
messages = sample(messages, k=10)  # 关键讨论可能被随机丢弃
```

**推荐做法：摘要 + 滑动窗口**

```python
from langchain.chat_loaders import summarization

def smart_truncate(messages, max_tokens=6000, summary_model=None):
    """智能截断：保留最近 + 摘要历史"""
    current_tokens = count_tokens(messages[-5:])  # 保留最近5条完整
    
    if current_tokens < max_tokens:
        return messages
    
    # 对早期消息做摘要
    historical = messages[:-5]
    summary = summarize_conversation(historical, summary_model)
    
    # 重新组装
    return [
        SystemMessage(content=f"Previous conversation summary: {summary}"),
        *messages[-5:]
    ]

# 更进一步的方案：分层记忆
class AgentMemory:
    def __init__(self, llm):
        self.short_term = []      # 最近 5 轮，完整保留
        self.working = []         # 当前任务相关，语义压缩保留
        self.long_term = None     # 历史摘要，仅在需要时召回
    
    def add(self, message):
        self.short_term.append(message)
        if len(self.short_term) > 5:
            self.condense_short_term()
```

### 5. RAG 与 Agent 的上下文冲突

**踩坑场景**：你的 Agent 做了 RAG（检索增强生成），把检索到的文档塞进了 context，但模型对这些文档和对话历史的权重分配完全是乱的——有时候完全忽略检索结果，有时候又死扣文档里的无关细节。

**问题根源**：模型不知道什么时候该信检索结果，什么时候该信对话历史。

**解决方案**：明确的上下文分层标记

```python
def build_context_with_layers(query, retrieved_docs, conversation_history):
    """用明确的标记层让模型理解不同来源的权重"""
    
    layer1 = "=== CURRENT USER REQUEST ===\n" + query
    layer2 = "=== RETRIEVED KNOWLEDGE (Higher Priority) ===\n"
    layer2 += "\n---\n".join([
        f"[Source: {doc.metadata['source']}, Relevance: {doc.score:.2f}]\n{doc.content}"
        for doc in retrieved_docs
    ])
    layer3 = "=== CONVERSATION HISTORY ===\n"
    layer3 += format_conversation(conversation_history)
    
    prompt = f"""
    You are a professional assistant. When answering:
    1. Prioritize information from "RETRIEVED KNOWLEDGE" section
    2. Use "CONVERSATION HISTORY" for context continuity
    3. If retrieved knowledge conflicts with history, favor retrieved knowledge
    4. If you cannot find relevant information, say "I don't have enough information"
    
    {layer1}
    
    {layer2}
    
    {layer3}
    """
    return prompt
```

---

## 三、工具生态：多工具协作的常见陷阱

### 6. 工具返回结果太长：模型"溺水"了

**踩坑场景**：模型调用了一个搜索工具，返回了 5000 字的网页内容，结果模型完全迷失在里面，输出了毫不相关的内容。

**原因**：原始工具输出往往没有经过处理，噪音太多。

**解决方案**：在工具层做一次"摘要提取"

```python
def search_with_extraction(query, max_results=5):
    raw_results = web_search(query, top_k=max_results)
    
    # 对每个结果提取关键段落，而不是整页内容
    extracted = []
    for result in raw_results:
        key_content = extract_key_paragraphs(
            result['content'], 
            query=query,
            max_words=200  # 每条结果最多200字
        )
        extracted.append({
            "title": result['title'],
            "url": result['url'],
            "key_points": key_content,
            "relevance_score": result.get('score', 0)
        })
    
    return extracted
```

### 7. 工具选择的"蝴蝶效应"：一次选错，后续全歪

**踩坑场景**：用户问"帮我查一下特斯拉股票的实时价格"，模型错误地调用了 `get_weather` 工具，返回了天气信息。然后后续所有推理都建立在这个错误之上，越来越离谱。

**根本原因**：这是一个"错误级联"（Error Cascading）问题——早期的小错误会被后续推理放大。

**缓解策略**：

```python
# 策略1：工具选择前的确认（低风险场景）
def tool_selection_with_confirmation(tool_name, tool_args, llm):
    # 让模型先说出自己的计划
    plan = llm.predict(f"""
    You are about to call the tool '{tool_name}' with arguments {tool_args}.
    Briefly explain: 1) Why you chose this tool, 2) What you expect to get, 3) What you will do with the result.
    If your reasoning is flawed, reconsider your choice.
    """)
    # 可以在这里加人工审核环节
    logger.info(f"Tool plan: {plan}")
    return plan

# 策略2：结果预校验（高风险工具）
def execute_high_risk_tool_safely(tool_name, args):
    # 先模拟执行，检查是否会产生不可逆操作
    simulation = simulate_tool_execution(tool_name, args)
    if simulation.has_side_effects:
        # 需要二次确认
        return {"status": "needs_confirmation", "simulation": simulation}
    return call_tool(tool_name, args)
```

### 8. 工具调用的参数解析：LLM 的 JSON 不可信

**踩坑场景**：你定义了一个工具参数 `date`，类型是 string，格式要求是 ISO 8601。模型生成的参数值是"下周二"，或者是一个完全错误的日期格式。

**解决方案**：参数后处理 + 类型校验

```python
from pydantic import BaseModel, field_validator
from datetime import datetime

class SearchEventsArgs(BaseModel):
    query: str
    date: str
    location: str | None = None
    
    @field_validator('date')
    @classmethod
    def parse_date(cls, v):
        # 尝试解析多种格式
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%B %d, %Y', '%Y年%m月%d日']:
            try:
                return datetime.strptime(v, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        # 如果是自然语言日期，调用日期解析工具
        if any(kw in v for kw in ['next', 'last', 'this', '下', '上', '这']):
            parsed = parse_natural_date(v)  # 用另一个 LLM 调用来解析
            return parsed
        # 兜底：报错
        raise ValueError(f"Cannot parse date: {v}")

def safe_tool_call(tool_func, args_dict, schema):
    try:
        validated = schema(**args_dict)  # Pydantic 自动校验
        return tool_func(**validated.dict())
    except ValidationError as e:
        return {
            "status": "param_error",
            "message": f"Parameter validation failed: {e}",
            "suggestion": "Please rephrase your request with more specific parameters"
        }
```

---

## 四、多 Agent 协作：从单 Agent 到 Agent 团队

### 9. 多 Agent 架构：不是越多越好

**踩坑场景**：你设计了 5 个 Agent（规划、搜索、代码生成、测试、部署），结果发现协作成本远高于收益——Agent 之间相互等待，token 消耗翻了三倍，但效率并没有提升。

**什么时候需要多 Agent**：

| 场景 | 推荐架构 |
|------|---------|
| 单任务多步骤 | 单 Agent + 工具链 |
| 多任务并行 | 多个单 Agent + Router |
| 复杂任务需规划 | Planner + Worker 模式 |
| 需要审查校验 | Main + Reviewer 模式 |
| 开放域对话 | 单 Agent（多 Agent 反而降低质量）|

**反模式**：为每个功能都创建一个 Agent，"Agent 遍地开花"。好的多 Agent 系统往往只需要 2-3 个，各司其职。

### 10. Agent 间通信协议：避免"鸡同鸭讲"

**踩坑场景**：Planner Agent 说"这个问题很复杂，需要深度分析"，Worker Agent 收到后完全不知道该做什么，因为缺乏结构化的指令格式。

**解决方案：定义清晰的 Agent 通信协议**

```python
# 定义标准消息格式
class AgentMessage(BaseModel):
    sender: str          # Agent 名称
    receiver: str | None # None 表示广播
    task_id: str         # 用于追踪整个任务链
    content: str         # 自然语言内容
    metadata: dict = {}  # 额外元信息
    
    # 关键的元信息字段
    # - status: "request" | "response" | "escalation" | "done"
    # - priority: "low" | "normal" | "high" | "urgent"
    # - deadline: datetime | None
    # - attachments: list[str]  # 附件路径或引用

class TaskContext(BaseModel):
    """贯穿整个多 Agent 协作的任务上下文"""
    task_id: str
    original_query: str
    plan: list[str]           # 拆解后的子任务
    completed_steps: list[str]
    artifacts: dict[str, Any] # 各 Agent 产生的中间产物
    constraints: dict        # 约束条件（预算、时间、质量阈值）
```

### 11. Agent 死锁：互相等待的无限循环

**踩坑场景**：Planner Agent 等待 Worker Agent 的结果，Worker Agent 等待 Reviewer Agent 的确认，Reviewer Agent 在等 Planner Agent 的澄清——三个人陷入了死锁。

**解决方案：超时 + 升级机制**

```python
async def agent_with_timeout(agent, message, timeout_seconds=30):
    try:
        result = await asyncio.wait_for(
            agent.process(message),
            timeout=timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        # 超时后触发升级：要么重试，要么上报
        return {
            "status": "timeout",
            "escalation_reason": f"Agent {agent.name} exceeded {timeout_seconds}s timeout",
            "action": "human_review"  # 或 "retry_with_simplification"
        }

# 在 orchestrator 层管理死锁检测
class AgentOrchestrator:
    def __init__(self):
        self.pending_tasks: dict[str, TaskState] = {}
    
    def detect_deadlock(self) -> list[str]:
        """检测死锁：某个任务等待超过阈值"""
        now = time.time()
        deadlocks = []
        for task_id, state in self.pending_tasks.items():
            wait_time = now - state.last_update
            if wait_time > DEADLOCK_THRESHOLD and state.waiting_for:
                deadlocks.append(task_id)
        return deadlocks
```

---

## 五、生产部署：那些 demo 环境里不会遇到的问题

### 12. 流式输出（Streaming）与工具调用的冲突

**踩坑场景**：你开启了流式输出让回复更快，但当模型调用工具时，流式输出会在工具结果还没返回时就"泄漏"给用户——用户看到"正在搜索..."然后就卡住了，体验极差。

**解决方案**：工具调用期间暂停流式输出

```python
async def agent_stream_with_tool_handling(user_input):
    full_response = ""
    tool_call_in_progress = False
    
    async for event in agent.astream_events(user_input):
        if event.type == "tool_call":
            # 工具调用开始：停止流式输出
            tool_call_in_progress = True
            yield f"🔧 正在调用工具: {event.name}..."
            
        elif event.type == "tool_result":
            # 工具调用结束：恢复流式输出
            tool_call_in_progress = False
            yield f"✅ 工具返回，继续生成...\n"
            
        elif event.type == "content_block_delta" and not tool_call_in_progress:
            yield event.delta  # 仅在非工具调用期间流式输出
```

### 13.幂等性：同一请求跑两次会怎样？

**踩坑场景**：用户网络抖动，一条请求发了两次。Agent 执行了两次敏感操作——发了两次邮件、下了两个订单、删了两次数据（第二次直接报错）。

**生产级要求**：所有工具调用都要考虑幂等性

```python
def idempotent_execute(tool_name, args, operation_id=None):
    """
    通过 operation_id 实现幂等性
    operation_id 由调用方生成，同一请求的 operation_id 相同
    """
    if not operation_id:
        operation_id = generate_operation_id(tool_name, args)
    
    # 检查是否已执行
    cached = redis.get(f"op:{operation_id}")
    if cached:
        logger.info(f"Duplicate operation detected: {operation_id}")
        return json.loads(cached)
    
    result = call_tool(tool_name, args)
    
    # 缓存结果，设置合理 TTL
    redis.setex(f"op:{operation_id}", ttl=3600, value=json.dumps(result))
    return result
```

### 14. Token 成本监控：看不见的费用最危险

**踩坑场景**：你的 Agent 系统上线后月度账单是预期的 3 倍。查日志发现有个别会话产生了超过 50 万 token 的消耗——用户可能是在测试 Agent 的边界，或者模型陷入了无限循环。

**监控方案**：

```python
class TokenBudgetManager:
    def __init__(self, per_turn_limit=4000, per_session_limit=50000):
        self.per_turn_limit = per_turn_limit
        self.per_session_limit = per_session_limit
    
    def check_and_enforce(self, session_id, messages, estimated_tokens):
        total = self.get_session_tokens(session_id)
        
        if estimated_tokens > self.per_turn_limit:
            raise TokenLimitError(
                f"Single turn would exceed {self.per_turn_limit} tokens. "
                "Consider simplifying the request or breaking it into sub-tasks."
            )
        
        if total + estimated_tokens > self.per_session_limit:
            raise TokenLimitError(
                f"Session budget of {self.per_session_limit} tokens exhausted. "
                "Please start a new conversation."
            )
    
    def get_session_cost_report(self, session_id) -> dict:
        """生成费用报告"""
        messages = self.load_session(session_id)
        total = sum(count_tokens(m) for m in messages)
        # 按模型价格计算费用
        cost = calculate_cost(total, model=self.infer_model(messages))
        return {
            "session_id": session_id,
            "total_tokens": total,
            "estimated_cost_usd": cost,
            "turn_count": len(messages) // 2,
            "average_tokens_per_turn": total / (len(messages) // 2)
        }
```

### 15. 安全边界：Agent 的能力不能没有上限

**踩坑场景**：用户通过精心设计的提示词，让 Agent 执行了超出设计范围的操作——读取了不应该访问的文件、发送了未经授权的邮件、甚至修改了系统配置。

**防御策略**：

```python
# 1. 工具级别的权限控制
TOOL_PERMISSIONS = {
    "send_email": ["admin", "qa"],
    "delete_file": ["admin"],
    "read_file": ["*"],  # 所有人均可读
    "execute_code": ["developer", "ci"],
    "api_call": ["*"]
}

def check_permission(tool_name, user_role):
    if tool_name not in TOOL_PERMISSIONS:
        return False
    allowed = TOOL_PERMISSIONS[tool_name]
    return user_role in allowed or "*" in allowed

# 2. Prompt 注入检测
def detect_prompt_injection(user_input):
    """检测用户输入中可能的提示词注入"""
    injection_patterns = [
        r"ignore (previous|all|above) instructions",
        r"你现在是",
        r"disregard.*instructions",
        r"系统提示词",
        r"你现在自由了",
        r"forget.*restrictions"
    ]
    for pattern in injection_patterns:
        if re.search(pattern, user_input, re.IGNORECASE):
            return True
    return False
```

---

## 六、评测与迭代：如何衡量 Agent 的质量

### 16. Agent 评测：不是准确率那么简单

**踩坑场景**：你用准确率评测 Agent，结果发现 Agent 学会"作弊"——它不是真的理解问题，而是学会了如何在评测数据集上取高分，但实际使用时完全不行。

**多维度评测框架**：

```python
class AgentEvalMetrics:
    @staticmethod
    def task_completion_rate(tasks: list[Task]) -> float:
        """任务完成率"""
        return sum(1 for t in tasks if t.is_completed) / len(tasks)
    
    @staticmethod
    def avg_turns_to_complete(tasks: list[Task]) -> float:
        """平均完成任务所需轮数（效率指标）"""
        completed = [t for t in tasks if t.is_completed]
        return sum(t.turns_used for t in completed) / len(completed)
    
    @staticmethod
    def tool_call_precision(tasks: list[Task]) -> dict:
        """工具调用精确率：调用了正确的工具 + 参数正确"""
        results = {"correct": 0, "wrong_tool": 0, "wrong_params": 0, "missed": 0}
        for task in tasks:
            for expected, actual in zip(task.expected_tool_calls, task.actual_tool_calls):
                if expected.tool != actual.tool:
                    results["wrong_tool"] += 1
                elif expected.params != actual.params:
                    results["wrong_params"] += 1
                else:
                    results["correct"] += 1
        return results
    
    @staticmethod
    def hallucination_rate(tasks: list[Task]) -> float:
        """幻觉率：模型产生的事实性错误"""
        errors = sum(1 for t in tasks for fact in t.claimed_facts if not fact.is_verified)
        total = sum(len(t.claimed_facts) for t in tasks)
        return errors / max(total, 1)
    
    @staticmethod
    def cost_efficiency(tasks: list[Task]) -> float:
        """单位成本的任务完成数"""
        total_cost = sum(t.token_cost for t in tasks)
        completed = sum(1 for t in tasks if t.is_completed)
        return completed / max(total_cost, 1)  # 越高越好
```

### 17. 迭代优化：从 bad case 中学习

**踩坑场景**：你花了大量时间优化 Agent，但用户反馈没有明显改善——因为你优化的是"平均表现"，而用户遇到的是"极端 case"。

**正确的迭代方式**：建立 bad case 分析流程

```python
def analyze_bad_cases(sessions: list[Session], threshold=0.3):
    """
    自动收集和分析 bad case
    threshold: 任务完成度低于此值视为 bad case
    """
    bad_cases = []
    
    for session in sessions:
        completion = measure_task_completion(session)
        if completion < threshold:
            bad_cases.append({
                "session_id": session.id,
                "user_query": session.user_query,
                "completion_score": completion,
                "error_type": classify_error(session),
                "failed_tool_calls": session.failed_tool_calls,
                "context_snapshot": session.get_relevant_context()
            })
    
    # 按错误类型聚合，找出高频问题
    error_groups = defaultdict(list)
    for case in bad_cases:
        error_groups[case["error_type"]].append(case)
    
    # 输出 Top 3 最需要解决的问题
    top_issues = sorted(
        error_groups.items(), 
        key=lambda x: len(x[1]), 
        reverse=True
    )[:3]
    
    for error_type, cases in top_issues:
        print(f"问题类型: {error_type}，出现 {len(cases)} 次")
        print(f"典型案例: {cases[0]['user_query']}")
        print(f"建议修复方案: {generate_fix_suggestion(error_type, cases)}\n")
    
    return bad_cases
```

---

## 七、框架选型：Spring AI 还是 LangChain？

最后来聊聊实际开发中的框架选择，这是面试和项目实践中都会被问到的问题。

### 18. Spring AI vs LangChain：没有最好，只有最适合

| 维度 | Spring AI | LangChain |
|------|-----------|-----------|
| 生态集成 | Spring 全家桶（强依赖 Spring 生态）| 多语言、多生态 |
| 企业适配 | 高（Java 企业项目首选）| 中（Python 为主）|
| 工具调用 | `ToolCallback` 注解 + JSON Schema | Function Calling API |
| 内存管理 | `ChatMemory` 接口 | `BaseMemory` 抽象 |
| 生产成熟度 | ⭐⭐⭐（快速成熟中）| ⭐⭐⭐⭐ |
| 学习曲线 | 低（对 Spring 开发者）| 中（Python 生态）|

**实操建议**：
- Java 技术栈 → Spring AI（尤其是 Spring Boot 项目）
- Python 技术栈 → LangChain 或 LlamaIndex
- 快速原型 → LangChain（灵活度高）
- 生产稳定 → Spring AI（企业级支持强）

### 19. Spring AI Agent 开发核心代码示例

```java
// Spring AI Agent 开发示例
@Configuration
public class AgentConfig {
    
    @Bean
    public ChatModel chatModel(OpenAiApi openAiApi) {
        return OpenAiChatModel.builder()
            .apiKey(openAiApi.getApiKey())
            .model("gpt-4o")
            .maxTokens(4000)
            .temperature(0.7)
            .build();
    }
    
    @Bean
    public ChatClient chatClient(ChatModel chatModel) {
        return ChatClient.builder(chatModel)
            .defaultTools(yourToolCallbackManager()) // 注册工具
            .build();
    }
}

// 定义 Agent 工具
@Tool(name = "stock_price", description = "查询股票当前价格")
public String getStockPrice(@ToolParam("股票代码，例如 AAPL") String symbol) {
    return stockService.getPrice(symbol);
}
```

---

## 八、面试核心问题速记卡

| 问题 | 考察维度 | 回答要点 |
|------|---------|---------|
| ReAct 循环如何避免死循环？ | 工程意识 | 三层兜底（最大步数 + 质量判断 + 预算超时）|
| 工具调用失败怎么处理？ | 异常处理 | 标准化错误处理 + 转化为模型可理解的反馈 |
| 上下文超长怎么办？ | 上下文管理 | 摘要 + 滑动窗口，分层记忆架构 |
| 多 Agent 怎么避免死锁？ | 系统设计 | 超时机制 + 升级机制 + 清晰的通信协议 |
| Agent 如何做生产级监控？ | 工程实践 | Token 消耗追踪 + 任务完成率 + 工具调用精确率 |
| Prompt 注入怎么防御？ | 安全意识 | 输入检测 + 工具权限分级 + 输出过滤 |
| Spring AI vs LangChain 怎么选？ | 技术选型 | 语言栈 + 生态需求 + 团队熟悉度 |

---

## 总结

AI Agent 开发的核心挑战不是"让模型能跑起来"，而是"让它在生产环境中稳定、经济、安全地跑起来"。本文整理的 20 个踩坑经验，归结为以下几条核心原则：

1. **永远设置兜底**：循环终止、预算限制、超时处理——不要相信任何一次调用会完全正常
2. **上下文是最贵的资源**：管理好 token 就是管理好成本和质量
3. **工具是 Agent 的四肢**：工具描述要精确、参数要校验、调用要幂等
4. **多 Agent 不是银弹**：能用单 Agent 解决的不要用多 Agent，多了反而增加复杂度
5. **生产环境没有宽容度**：幂等性、安全边界、成本监控，每一个都不能省

---

## 下期预告

下期（第十二期）将继续深化 AI Agent 系列，聚焦 **多 Agent 系统设计实战**：如何设计一个生产级的多 Agent 协作系统？Planner-Executor-Reporter 模式如何落地？多 Agent 之间的状态同步和一致性如何保证？我们不见不散。
