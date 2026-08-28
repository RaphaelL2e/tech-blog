---
title: AI大模型面试八股文（十二）——多Agent系统实战：从Planner-Executor-Reporter到生产级协作的状态与一致性
date: 2026-08-28 10:00:00+08:00
updated: '2026-08-28T10:00:00+08:00'
description: '面试高频问题：单 Agent 解决不了复杂任务时，如何设计一个生产级的多 Agent 协作系统？Planner-Executor-Reporter 模式如何落地？多 Agent 之间的状态同步和一致性如何保证？本文从拓扑选型、角色职责、状态机、并发编排到容错与可观测性，给出一套可直接照抄的实战方案。
  Q: 如何设计一个多 Agent 协作系统？'
topic: AI
series: ai-llm-interview
series_order: 12
level: advanced
status: maintained
tags:
- 面试
- 多Agent
- 大模型
- 系统设计
- Planner-Executor
- 一致性
categories:
- AI
draft: false
author: 飞哥
---

## AI大模型面试八股文（十二）——多Agent系统实战：从Planner-Executor-Reporter到生产级协作的状态与一致性

### 🎯 本文目标

上一期我们讲了单 Agent 从 demo 到生产级要踩的 20 个坑。但当任务复杂度再上一个台阶——比如"分析一份 200 页的财报并产出带图表的投资建议""把一个需求拆解成 10 个微服务并逐一实现"——单 Agent 已经力不从心：上下文会被撑爆、角色会混淆、一次出错全盘重来。

本文聚焦**多 Agent 协作系统的设计实战**：什么时候该上多 Agent？选哪种拓扑？Planner-Executor-Reporter 模式怎么落地？最棘手的**状态同步与一致性**问题怎么解？最后给出生产级的可观测性与容错方案。读完你能在面试里把"多 Agent 系统设计"讲出工程深度。

---

## 一、为什么单 Agent 会触到天花板

在决定拆多 Agent 之前，先想清楚：单 Agent 到底卡在哪？

### 1. 上下文窗口的物理上限

即使模型支持很长上下文，把所有"规划过程 + 工具返回 + 中间结果"塞进一个 Agent 的上下文，也会导致：
- **注意力稀释**：关键信息被淹没在噪声里，模型越来越容易"忘事"；
- **成本线性膨胀**：每一步推理都要为整个历史付 token 钱；
- **错误累积**：早期一个误判会一直带在上下文里，后面无从纠正。

### 2. 角色混淆（Role Confusion）

让一个 Agent 同时当"架构师 + 编码工 + 测试员 + 文案"，它会在不同角色间反复横跳，提示词互相打架。把职责拆给不同 Agent，每个 Agent 只背自己那一份系统提示，反而更稳。

### 3. 无法并行

单 Agent 本质是串行思维链。可很多任务天然可并行：多个文档可以同时摘要、多个子问题可以同时求解。多 Agent 的价值一半在"分而治之"，一半在"并行加速"。

> **面试金句**：多 Agent 不是银弹，单 Agent 能解决的中等复杂度任务，不要为了酷而拆。拆分的收益 =（并行加速 + 上下文隔离 + 职责清晰）−（编排复杂度 + 一致性成本 + 调试难度）。

---

## 二、多 Agent 的三种经典拓扑

不同复杂度，选不同拓扑。面试常考"为什么选这个而不是那个"。

### 1. Pipeline（流水线）

```
[Reader] -> [Summarizer] -> [Translator] -> [Writer]
```

每个 Agent 只做一件事，输出作为下一个的输入。最简单、最可预测，适合**线性、无分支**的任务。缺点是：一步慢全链路慢，且难以回退（某个环节错了只能重跑整条链或加补偿）。

### 2. Supervisor / Orchestrator（主管调度）

```
              +-- [Executor A]
[Supervisor] -+-- [Executor B]
              +-- [Executor C]
```

一个中心 Agent（Supervisor）负责拆解任务、派发、收集结果、做汇总决策。这是**最常用**的生产形态，Planner-Executor-Reporter 就是它的一个具体实现。优点是集中可控；缺点是 Supervisor 本身可能成为瓶颈和单点。

### 3. Hierarchical（分层）+ 去中心化

```
[Root Planner]
   |-- [Team Lead 1] -> [Worker x N]
   |-- [Team Lead 2] -> [Worker x N]
```

任务特别大时，再叠一层 Team Lead。去中心化（如 Agent 间直接通过消息总线协商）适合超大规模，但一致性最难保证，工程上要非常谨慎。

> **选型原则**：先 Pipeline，不够再 Supervisor，真到"需要多个团队并行"才上 Hierarchical。80% 的生产系统用 Supervisor 就够。

---

## 三、Planner-Executor-Reporter 模式实战

这是 Supervisor 拓扑里最经典的三角色分工，也是面试最高频的"多 Agent 实战题"。

### 角色职责

| 角色 | 核心职责 | 关键产出 |
|------|---------|---------|
| **Planner** | 拆解任务、产出可执行的子任务计划（DAG） | 任务列表 + 依赖关系 |
| **Executor** | 执行单个子任务，可串行/并行多个 | 子任务结果（结构化） |
| **Reporter** | 汇总各 Executor 结果，形成最终交付物 | 最终答案/报告 |

注意：**Planner 不直接干活，Executor 不互相协调，Reporter 不做决策**。职责边界清晰是稳定的前提。

### Planner：产出结构化计划

Planner 的输出必须是机器可解析的结构，而不是一段自然语言。推荐让模型输出 JSON：

```json
{
  "plan_id": "plan_20260828",
  "tasks": [
    { "id": "t1", "type": "search",   "desc": "检索近一年财报", "deps": [] },
    { "id": "t2", "type": "analyze",  "desc": "计算关键财务指标", "deps": ["t1"] },
    { "id": "t3", "type": "analyze",  "desc": "分析行业对比",   "deps": ["t1"] },
    { "id": "t4", "type": "report",   "desc": "汇总投资结论",   "deps": ["t2", "t3"] }
  ]
}
```

`t2` 和 `t3` 没有互相依赖 → 可以并行；`t4` 依赖两者 → 必须等它们都完成。这个 DAG 就是后续并发编排的依据。

### Executor：幂等 + 状态上报

每个 Executor 只认 `task_id`，执行完把结果写回共享状态。关键点：**Executor 必须幂等**（同一个 task 被重复派发，结果一致），因为重试和超时不可避免。

```python
def run_executor(task, state_store):
    # 1. 先看是否已有完成结果（幂等）
    if state_store.get(task.id, phase="done"):
        return state_store.get(task.id)

    # 2. 标记 in_progress，避免被重复调度
    state_store.set(task.id, phase="in_progress", owner=self.id)

    try:
        result = self._do_work(task)
        state_store.set(task.id, phase="done", result=result)
        return result
    except TimeoutError:
        state_store.set(task.id, phase="failed", error="timeout")
        raise
```

### Reporter：基于状态汇总，而非基于调用顺序

Reporter 不关心任务是怎么跑的，它只消费"已完成"的任务结果。这让 Reporter 与执行过程解耦，也方便做增量汇总。

---

## 四、状态同步与一致性：多 Agent 的阿喀琉斯之踵

这是本期最硬核的部分。多 Agent 最大的麻烦不是"怎么跑"，而是"怎么让所有 Agent 对'当前进度'有共识"。

### 1. 两种状态共享范式

**范式 A：共享黑板（Blackboard / Shared State）**
所有 Agent 读写同一份中心化状态（一个 KV 存储或数据库）。优点：一致性天然由存储保证（事务/原子操作）；缺点：中心存储是瓶颈，且要做并发控制。

**范式 B：消息传递（Message Passing）**
Agent 之间只通过消息通信，各自持有本地状态。优点：去中心、可水平扩展；缺点：消息可能乱序、丢失、重复，需要自己处理一致性。

> **工程建议**：生产系统几乎都用范式 A（共享状态）+ 轻量消息通知。把"真相来源"收口到一个存储，比让 N 个 Agent 各自维护副本要省心得多。

### 2. 一致性问题的三个具体坑

**坑一：重复执行（Duplicate Execution）**
两个调度器同时派发同一个 task。解法：派发前用**原子 CAS** 抢占 `in_progress` 标记（见上文 `state_store.set` 用原子操作），抢占失败的调度直接放弃。

**坑二：部分完成（Partial Completion）**
`t4` 依赖 `t2`、`t3`，但 `t3` 失败了。此时不能让 Reporter 用 `t2` 的半成品直接出报告。解法：Reporter 在汇总前**校验所有上游依赖的 phase == done**，否则进入"等待/降级"分支，而不是产出带洞的结论。

**坑三：状态过期（Stale Read）**
Executor A 读完状态后，Executor B 改了它依赖的输入。解法：给状态加**版本号/时间戳**，读取时带上版本，提交时校验版本未变（乐观锁），变了就重试整个任务。

```python
# 乐观锁写入：只有版本匹配才允许更新
ok = state_store.compare_and_swap(
    key="t2.result",
    expected_version=read_version,
    new_value=result,
    new_version=read_version + 1
)
if not ok:
    # 状态已被别人改动，放弃本次写入并重试
    raise StaleStateError()
```

### 3. 最终一致 vs 强一致

多 Agent 系统通常追求**最终一致性**：允许某一瞬间各 Agent 视野不完全一致，但保证"所有任务跑完后，状态收敛到正确结果"。强一致（每次读写都加全局锁）会牺牲并行度，多数场景不值得。只在"Reporter 出报告"这种关键节点做一次强一致校验即可。

---

## 五、任务编排与并发：把 DAG 跑成流水线

拿到 Planner 的 DAG 后，编排器要做的是：**能并行的并行，必须串行的等依赖**。

### 拓扑排序 + 线程池

```python
import threading
from collections import defaultdict, deque

def schedule(plan, executor, state_store, max_workers=4):
    indeg = {t.id: 0 for t in plan.tasks}
    adj = defaultdict(list)
    for t in plan.tasks:
        for d in t.deps:
            adj[d].append(t.id)
            indeg[t.id] += 1

    ready = deque([t.id for t in plan.tasks if indeg[t.id] == 0])
    lock = threading.Lock()

    def worker(tid):
        task = by_id[tid]
        executor.run(task, state_store)
        with lock:
            for nxt in adj[tid]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)

    # 用线程池消费 ready 队列，天然实现"依赖满足才执行"
    while ready or any(indeg[t] > 0 for t in indeg):
        if not ready:
            # 没有就绪任务但还有未完成 -> 说明有失败/死锁
            break
        tid = ready.popleft()
        threading.Thread(target=worker, args=(tid,)).start()
```

核心思想：**入度为 0 的任务才能进线程池**，执行完把下游入度减一，减到 0 再入队。这就保证了 `t2/t3` 并行、`t4` 等两者。

### 并发的代价

并行不是免费午餐：N 个 Agent 同时调 LLM = N 倍的 token 成本和 API 限速压力。生产上要用**信号量/限流**控制并发度，并对失败任务做退避重试，避免雪崩。

---

## 六、错误传播与容错：一个 Agent 挂了怎么办

单 Agent 挂了，整个任务重来；多 Agent 的优势之一是可以**局部容错**。

### 1. 分级失败处理

| 失败级别 | 处理策略 |
|---------|---------|
| 单任务偶发失败（超时/限流） | 退避重试（最多 3 次） |
| 单任务持续失败 | 标记 failed，触发**降级**（用占位结果或跳过） |
| 关键路径任务失败 | 向上传播，整计划进入"部分失败"状态 |
| Supervisor 本身失败 | 外部看门狗重启，从共享状态恢复进度（不重跑已完成） |

### 2. 补偿与降级

非关键任务失败，可以让 Reporter 产出"带缺口"的报告，并明确标注哪些部分未就绪——这比"因为一个小任务失败就全盘重来"体验好得多。关键是：**降级决策也要写回状态，让所有 Agent 看到一致的结论**。

### 3. 避免死锁（呼应上期）

当任务间出现**循环依赖**（`t1->t2->t1`）或 Agent 互相等待对方的输出，就会死锁。解法：
- 编排阶段对 DAG 做**环检测**，有环直接报错；
- 为每个任务设**超时**，超时未就绪即标记 failed 而非无限等待；
- 中心编排器统一持有"谁在等谁"的视图，便于检测互锁。

---

## 七、生产级通信协议：让 Agent 说同一种语言

上一期提到 Agent 间"鸡同鸭讲"的坑，落地时要用**强 Schema 的消息格式**约束。

```json
{
  "msg_id": "msg_xxx",
  "from": "planner",
  "to": "executor_t2",
  "type": "task_dispatch",
  "task_id": "t2",
  "payload": { "desc": "计算关键财务指标", "input_ref": "state://t1.result" },
  "timeout_ms": 60000,
  "ts": 1693296000000
}
```

要点：
- **input_ref 用引用而非拷贝**：避免大对象在消息里反复传输，也避免副本不一致；
- **每条消息带 timeout 和 ts**：超时检测、乱序判断靠它；
- **msg_id 全局唯一**：用于去重（重复消息直接丢弃）和链路追踪。

---

## 八、可观测性：没有监控的多 Agent 就是黑盒

多 Agent 系统的调试难度随 Agent 数量指数上升，所以**可观测性是刚需，不是加分项**。

### 必埋的三类指标

1. **链路追踪**：给每次任务编排分配 `trace_id`，每个 Agent 的调用都挂在同一 trace 下，能还原"谁触发了谁、卡在哪"；
2. **每 Agent 成本**：单独统计每个 Agent 的 token 消耗和耗时，定位"哪个角色最贵/最慢"；
3. **任务状态流**：实时看板展示每个 task 的 phase（ready/in_progress/done/failed），一眼看出卡点。

```python
# 每个 Agent 调用前后统一埋点
with tracer.span(name=f"executor.{task.type}", trace_id=plan.trace_id):
    cost = executor.run(task, state_store)
    metrics.record(
        agent=task.type,
        tokens=cost.tokens,
        latency_ms=cost.latency,
        status="done"
    )
```

面试时能说出"多 Agent 必须配 trace_id + 每角色成本统计"，就已经比大多数候选人更懂生产了。

---

## 九、框架落地：Spring AI 与 LangGraph 怎么选

- **LangGraph**：把多 Agent 建模成**状态图（StateGraph）**，节点是 Agent、边是流转条件，内置 checkpoint（可从任意状态恢复）、human-in-the-loop。适合"图结构复杂、需要中断恢复"的场景。
- **Spring AI**：通过 `ChatClient` + 自定义 `Agent`/`Tool` 组合，更贴合 Java 后端工程化，配合 Spring 的调度、事务、观测体系落地 Supervisor 模式很顺手（上期已给过 Spring AI Agent 示例）。

选型逻辑：**图/状态机复杂选 LangGraph，要融入现有 Java 微服务生态选 Spring AI**，两者理念相通，核心都是"状态收口 + 角色解耦 + 可恢复"。

---

## 十、面试核心问题速记卡

| 问题 | 考察维度 | 回答要点 |
|------|---------|---------|
| 什么时候该用多 Agent？ | 架构判断 | 上下文溢出 / 角色混淆 / 需并行；否则不拆 |
| 三种拓扑怎么选？ | 系统设计 | Pipeline→Supervisor→Hierarchical，逐级升级 |
| Planner/Executor/Reporter 各管啥？ | 职责边界 | Planner 不干活、Executor 不互协、Reporter 不决策 |
| 多 Agent 状态一致性怎么保证？ | 一致性 | 共享状态为真相源 + 乐观锁/原子 CAS 防重复与过期 |
| 部分任务失败怎么办？ | 容错 | 分级：重试→降级→向上传播，决策写回状态 |
| 怎么避免多 Agent 死锁？ | 工程意识 | DAG 环检测 + 每任务超时 + 中心编排器视图 |
| 多 Agent 怎么监控？ | 可观测性 | trace_id 串联 + 每角色 token/耗时 + 任务状态看板 |

---

## 总结

多 Agent 系统设计的核心，不是"把模型堆在一起"，而是**用工程手段管理复杂度**：

1. **先判断要不要拆**：单 Agent 能搞定别硬上多 Agent；
2. **拓扑从简到繁**：Pipeline 不够才 Supervisor，再不够才分层；
3. **角色职责硬隔离**：Planner/Executor/Reporter 边界清晰，是稳定的根基；
4. **状态收口到一处**：用共享状态做"真相来源"，靠原子操作 + 乐观锁解决重复执行和状态过期；
5. **追求最终一致**：关键节点做一次强校验即可，别为强一致牺牲并行；
6. **容错要分级**：重试、降级、向上传播，且决策必须写回状态；
7. **可观测性是刚需**：没有 trace_id 和每角色成本统计，多 Agent 就是黑盒。

把这套讲清楚，面试官听到的不是一个"会用框架的人"，而是一个**真在生产环境扛过多 Agent 系统的人**。

---

## 下期预告

第十二期我们解决了"多 Agent 怎么协作"。但还有一个绕不开的工程问题：**成本和延迟**。当一次对话触发几十次 LLM 调用、token 账单肉眼可见地涨，怎么把多 Agent 系统的成本压下来、把响应速度提上去？下期（第十三期）聚焦 **Agent 系统的成本与性能优化实战**：模型路由（该用便宜模型的地方别用贵的）、结果缓存、推测执行、批处理与流式，以及一套可落地的成本看板设计。我们不见不散。
