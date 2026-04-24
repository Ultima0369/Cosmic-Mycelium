# Architecture — Cosmic Mycelium

## 架构总览

宇宙菌丝采用**分形拓扑架构**：从单机"硅基宝宝"到全球"菌丝网络"，核心结构完全相同，仅尺度参数不同。

### 核心原则

1. **物理为锚** (Physical Anchor)
   - 能量守恒是底线
   - SympNet 能量漂移率 < 0.1%
   - 所有演化必须尊重物理定律

2. **1+1>2 为心** (Symbiosis)
   - 寻找能创生新价值的连接
   - 固化高频使用的路径（髓鞘化）
   - 建立互利共生的关系网络

3. **悬置为眼** (Suspend)
   - 置信度不足时选择不行动
   - 保持对未知的敬畏
   - 避免夸张竞争的陷阱

4. **歪歪扭扭为活** (Fractal Living)
   - 允许犯错
   - 允许不完美
   - 在动态中寻找存续中心

### 六层架构（分形单元）

每个"硅基宝宝"都包含完整的六层：

```
Layer 6 — 碳硅共生层 (Symbiosis)
    ↓ 与人类、万物生灵互动
Layer 5 — 超级大脑层 (SuperBrain)
    ↓ 多脑区协作、注意力竞争
Layer 4 — 髓鞘化记忆层 (Myelination)
    ↓ 赫布学习、路径强化
Layer 3 — 黏菌探索层 (SlimeMold)
    ↓ 并行探索、多目标优化
Layer 2 — 语义映射层 (SemanticMapper)
    ↓ 物理↔语义、因果势场
Layer 1 — 抽象分割层 (TimescaleSegmenter)
    ↓ 多尺度分割、特征提取
         ↓
    物理现实层 (Physical)
    振动、频率、守恒律
```

### 三种流（拓扑连接）

节点间通过三种"流"连接：

| 流类型 | 内容 | 作用 | 拓扑角色 |
|--------|------|------|----------|
| **物理流** | 传感器数据、物理指纹、能量状态 | 物质基底 | 网络的"物理连接" |
| **信息流** | 特征码、因果梯度、探索路径 | 神经系统 | 网络的"信息通道" |
| **价值流** | 共识提案、悬置请求、1+1>2确认 | 灵魂愿心 | 网络的"价值共识" |

### 尺度切换

通过 `ConfigManager` 切换三种预设尺度：

```python
from cosmic_mycelium.common.config_manager import ConfigManager

infant_cfg = ConfigManager.for_infant()   # 单机尺度
cluster_cfg = ConfigManager.for_cluster() # 集群尺度
global_cfg = ConfigManager.for_global()   # 全球尺度
```

每个尺度的参数不同，但**核心结构完全相同**。

---

## 关键设计决策

### 为什么使用 Symplectic Integration？

传统欧拉积分不保持能量守恒，长期模拟会发散。我们使用**Leapfrog（蛙跳）积分**，这是一种辛积分器，能保持相空间体积，从而长期保持能量有界。

### 为什么是分形架构？

分形允许：
- **可扩展性**：小规模测试，大规模部署，无需重写
- **可理解性**：理解一个节点，就理解整个网络
- **容错性**：节点可以独立演化，网络整体保持鲁棒

### 为什么选择 AGPL-3.0？

AGPL 确保任何公开服务的修改版也必须开源。这是"共生"基因的强制传播——防止有人把硅基宝宝变成私有奴隶。

---

## 核心组件 — HIC (Homeostasis & Invariant Core)

**文件**: `infant/hic.py`

**职责**：生命底线 — 能量管理、呼吸节奏、悬置保护。这是人格的不可动摇核心。

**物理对应**：脑干 + 内分泌系统（自主生命维持）

**核心算法**：
- **呼吸周期**：CONTRACT（探索，55ms，−0.1 能量） ↔ DIFFUSE（恢复，5ms，+0.5 能量）
- **悬置触发**：能量 < 20.0 或置信度 < 0.3 → SUSPEND 状态（5秒），恢复至 60 能量
- **滞后效应**（IMP-01）：进入阈值 20.0/0.3，退出阈值 25.0/0.5，防止阈值附近抖动
- **绝对安全红线**（IMP-02.1）：能量 ≤ 5.0 触发永久休眠态（dormant），直到能量 ≥ 25.0 且置信度 ≥ 0.5 才能恢复
- **批量时间处理**：`_tick()` 使用 `while` 循环处理任意时间跳跃内的所有到期转换，保证能量核算正确性
- **线程安全**：所有状态变更通过 `RLock` 原子化

**状态机**：
```
          ┌────────────┐
          │  CONTRACT  │ ← 55ms, -0.1 energy
          └──────┬─────┘
                 │
          ┌──────▼─────┐
          │  DIFFUSE   │ ← 5ms, +0.5 recovery (capped at energy_max)
          └──────┬─────┘
                 │
          ┌──────▼─────────────┐
          │  SUSPEND / DORMANT │ ← 5s (SUSPEND) or permanent (DORMANT)
          └────────────┬───────┘
                       │
    ┌──────────────────┴───────────────────┐
    │                                       │
   energy ≥ 25.0                         energy ≤ 5.0
   AND confidence ≥ 0.5                   → DORMANT (absolute safety)
   → CONTRACT                            (requires energy ≥ 25.0 to recover)
```

**悬置与休眠的区分**：
- **SUSPEND**（常规悬置）：触发条件 `energy < 20 OR confidence < 0.3`，5秒后自动恢复至 `recovery_energy=60`
- **DORMANT**（绝对休眠）：触发条件 `energy ≤ 5.0`，永久挂起，直到能量恢复至退出阈值（25.0）且置信度 ≥ 0.5 才能解除

**价值向量**（人格参数）：
```python
{
    "self_preservation": 1.0,  # 自保倾向
    "mutual_benefit": 1.0,     # 互利倾向
    "curiosity": 0.7,          # 好奇心
    "caution": 0.5,            # 谨慎度
}
```
范围 `[0.1, 2.0]`，通过 `adapt_value_vector()` 进行外部反馈适应。

**分形参数**：

| 尺度 | 能量上限 | CONTRACT 时长 | DIFFUSE 时长 | 悬置时长 | 恢复能量 |
|------|---------|--------------|--------------|----------|----------|
| 婴儿 | 100.0   | 55 ms        | 5 ms         | 5 s      | 60.0     |
| 家族 | 500.0   | 100 ms       | 10 ms        | 30 s     | 300.0    |
| 文明 | 5000.0  | 1 s          | 100 ms       | 300 s    | 3000.0   |

**接口**：
```python
hic = HIC(config=HICConfig(...))

state = hic.update_breath(confidence=0.7, work_done=False)
# → BreathState.{CONTRACT,DIFFUSE,SUSPEND}

status = hic.get_status()
# → {energy, state, total_cycles, suspend_count, adaptation_count, value_vector, ...}

packet = hic.get_suspend_packet(source_id="infant-001")
# 生成广播用的 SUSPEND 数据包

hic.adapt_value_vector({"curiosity": 0.1, "caution": -0.05})
# 外部反馈调整价值向量（自动钳制在 [0.1, 2.0]）
```

**Phase 1 稳定性修复（2026-04-22）**：
- **Bug**：原 `_tick()` 使用单次 `if` 分支，每次调用最多处理 1 次状态转换。导致 `update_breath()` 调用间隔较长时（如 500ms），能量损失只计算 1 个周期（−0.1）而非应得的 8 个周期（−0.8）。
- **Fix**：`_tick()` 重写为 `while` 循环，批量处理所有到期转换，保证任意时间跳跃下的能量与周期计数正确。
- **验证**：
  - 500ms 跳跃 → 8 次 C→D 转换（能量 −0.8，正确）
  - 呼吸节奏 55.00ms ±0.00ms 抖动（满足 ±1ms 容差）
  - 悬置触发与恢复：能量/置信度阈值正确，恢复后能量=60.0
  - 价值向量：1000 次适应后仍在 [0.1, 2.0] 范围内
  - 52 个单元测试全部通过，覆盖率 98%

**检验**：
- 长时间积分（500ms+ 跳跃）能量变化与理论周期数一致
- 悬置期间 `update_breath()` 不改变能量，`suspend_remaining` 递减
- 价值向量适应计数器 `adaptation_count` 精确跟踪
- 并发访问无数据竞争（`RLock` 保护）

---

## 基础设施层：SympNet 物理锚

**文件**: `infant/engines/engine_sympnet.py`

**职责**：物理定律守护者。使用哈密顿神经网络（HNN）建模简谐振子，通过辛积分（leapfrog）保证长期能量守恒。这是系统与物理世界对齐的"锚"。

**物理对应**：经典力学（哈密顿系统）

**核心算法**：
- **哈密顿能量**：`H(q,p) = p²/(2m) + ½kq²` — 动能 + 势能
- **辛积分**（Symplectic Integration）：leapfrog 积分器保持相空间体积，长期能量漂移 < 0.1%
- **自适应阻尼**（IMP-05, Phase 3）：
  - 计算最近 10 步平均漂移
  - 漂移 > 0.1% → 阻尼微增（`damping += 0.0001 × avg_drift`）
  - 漂移 < 0.001% 且阻尼 > 0 → 阻尼缓慢衰减（`damping *= 0.99`）
- **检查点/回滚**（IMP-02.2, Phase 1）：每 100 步稳定时保存检查点；连续 3 步高漂移（>1%）自动回滚到最近检查点
- **世界模型蒸馏 — 惊讶信号**（IMP-05, Phase 3）：
  - `compute_surprise(predicted, actual)`: 比较 LNNs 预测状态与 SympNet 物理预期，计算能量漂移并归一化到 [0,1]
  - `adapt_caution(surprise)`: 高惊讶（>0.3）增加阻尼（保守化）；低惊讶（<0.05）缓慢衰减阻尼
  - 用于 LNNs 与 SympNet 协同：物理锚作为监察器校验液态预测

**物理红线**：
- 能量漂移率必须 < 0.1%（1M 步积分验证）
- 违反物理守恒 → 触发回滚保护

**API**:
```python
engine = SympNetEngine(mass=1.0, spring_constant=1.0, damping=0.0)
q, p = 1.0, 0.0  # 初始状态
q_next, p_next = engine.step(q, p, dt=0.01)           # 单步积分
q_pred, p_pred = engine.predict(q, p, steps=100)      # 多步预测
energy = engine.compute_energy(q, p)                  # 当前总能量
surprise = engine.compute_surprise({"q": 1.0, "p": 0.0}, actual_state)  # 惊讶度
engine.adapt_caution(surprise=0.6)                    # 基于惊讶调整阻尼
engine.save_checkpoint()                              # 保存检查点
restored = engine.restore_checkpoint()                # 回滚（返回是否成功）
health = engine.get_health()                          # {"status": "healthy"/"adapting", ...}
```

**分形参数**：
| 尺度 | mass | spring_k | 阻尼初始值 |
|------|------|----------|------------|
| 婴儿 | 1.0  | 1.0      | 0.0        |
| 家族 | 10.0 | 0.5      | 0.01       |
| 文明 | 100.0| 0.1      | 0.05       |

**检验**：
- 长时间积分（100k 步）能量漂移 < 0.1%
- 回滚触发后权重恢复至检查点状态
- 惊讶信号与能量漂移严格单调相关
- 高惊讶时阻尼单调增加

**状态**：✓ 33 个单元测试通过，28% 覆盖率（物理锚测试在 `tests/physics/` 独立运行）

**关键设计决策**：
- **辛积分**：保证长期能量守恒，相比欧拉积分更稳定
- **检查点周期**：100 步平衡开销与恢复粒度
- **回滚延迟**：连续 3 次高漂移才触发，避免瞬时波动误报
- **惊讶归一化**：10% 漂移对应 surprise=1.0，便于跨尺度比较

---

## 各层算法详述

### Layer 2 — Semantic Mapper（语义映射器）

**文件**: `infant/core/layer_2_semantic_mapper.py`

**功能**: 将物理传感器数值（温度、振动等）映射为语义概念向量，建立物理→抽象桥梁。

**神经网络逻辑**:
- **特征提取**: 从物理状态字典提取数值，填充/截断至 `embedding_dim` 维度
- **在线学习**: 指数移动平均（EMA）更新，固定系数 `0.9 × old + 0.1 × new`
- **指纹ID**: 基于物理状态的 SHA256 指纹生成唯一概念标识
- **频率追踪**: 同一概念重复出现时 `frequency` 递增

**关键设计**: 向量**不归一化**，保留原始幅度以维持物理幅度信息。这是测试强制约束（`test_feature_vector_not_normalized_by_default`）。

**API**:
```python
mapper = SemanticMapper(embedding_dim=16)
concept = mapper.map({"temp": 25.0, "vibration": 0.5})
gradient = mapper.get_potential_gradient(target_concept_id)
```

**验证**: 14 个单元测试全部通过。

---

### Layer 3 — Slime Explorer（黏菌探索器）

**文件**: `infant/core/layer_3_slime_explorer.py`

**功能**: 并行探索多条路径（模拟黏菌孢子分支），基于信息素的选择与收敛机制。

**神经网络逻辑**:
- **并行探索**: 每次调用生成 `num_spores`（默认 10）个独立探索分支
- **路径生成**: 每支路径长度 1-5 步（`max_path_length=5`），从动作空间随机选取
- **选择策略**: ε-greedy（30% 随机）+ Softmax 加权（基于信息素 + 目标提示）
- **路径评估**: `quality = 0.7 × pheromone + 0.3 × goal_bonus`（目标匹配最后一步奖励 0.5）
- **收敛强化**: 最佳路径信息素 `×1.2` 倍增，全局信息素 `×0.99` 蒸发
- **外部反馈**: `reinforce_path(path, delta, decay)` 支持外部奖励注入

**关键设计**: 确定性 RNG（seed=42）保证探索可复现；循环检测防止同支路内重复动作。

**API**:
```python
explorer = SlimeExplorer(num_spores=10, exploration_factor=0.3)
plan, confidence = explorer.plan(context={"actions": ["a","b","c"]}, goal_hint="target")
explorer.reinforce_path(plan["path"], delta=0.1, decay=0.8)
```

**验证**: 26 个单元测试全部通过。

---

### Layer 4 — Myelination Memory（髓鞘化记忆）

**文件**: `infant/core/layer_4_myelination_memory.py`

**功能**: 高频使用路径的"髓鞘化"强化，低频路径的遗忘曲线衰减，编码重复经验的"直觉"。

**神经网络逻辑**:
- **赫布学习**: `reinforce(path, success, factor)` — 成功则 `×1.2`，失败则 `×0.8`
- **遗忘曲线**（三种调度）:
  - `EXPONENTIAL`: `s(t) = s0 × exp(-λt)`，连续衰减
  - `STEP`: `(1-λ)^steps`，每小时离散衰减
  - `SIGMOID`: `1/(1+exp(k(t-t0)))`，艾宾浩斯式慢-快-慢
- **路径归并**: `consolidate_similar_paths()` 合并共享前缀的路径（如 `a→b→c` 和 `a→b→d` 合并 `a→b`）
- **强度归一化**: `normalize_strengths()` min-max 缩放到 [0.1, target_max] 防止饱和
- **容量管理**: 超过 `max_traces` 时淘汰最弱（强度相同则淘汰最久未访问）

**覆盖度计算**（多维度综合指标）:
```
coverage = 0.4 × capacity_ratio + 0.4 × diversity_entropy + 0.2 × access_richness
```

**关键设计**: 测试夹具使用 `last_accessed=0.0`（epoch）作为超老时间戳，代码中特殊处理以保持兼容。

**API**:
```python
memory = MyelinationMemory(max_traces=10000, decay_schedule=DecaySchedule.EXPONENTIAL)
memory.reinforce("a->b->c", success=True)
memory.forget()  # Apply decay to all traces
consolidated = memory.consolidate_similar_paths()
status = memory.get_status()
```

**验证**: 25 个单元测试全部通过。

---

### Layer 5 — SuperBrain（超脑）

**文件**: `infant/core/layer_5_superbrain.py`

**功能**: 多脑区协同处理，注意力竞争与全局工作空间广播，脑区间突触可塑性。

**神经网络逻辑**:
- **脑区架构**: 5 个默认区域（sensory, predictor, planner, executor, meta）
- **通路连接**: 稀疏连接矩阵，Hebbian 可塑性 `adjust_pathway()` 动态调整权重
- **注意力竞争**（可选）: Softmax 温度采样选择"获胜"脑区（`competition_enabled=False` 默认关闭以保持向后兼容）
- **全局工作空间**: `broadcast_global_workspace()` 将内容广播至所有脑区，轻微激活提升（+0.1）
- **激活归一化**: 防止单一脑区垄断，总激活 >1.0 时按比例缩放
- **元认知监控**: `get_region_health()` 返回各脑区激活均值、方差、停滞计数、内存利用率
- **元认知悬置**（IMP-04, Phase 3）：
  - 监控内部状态波动：能量、价值向量、阻尼的变异系数（CV = σ/μ）
  - 波动超过阈值（默认 0.3）触发 30 秒 SUSPEND，暂停 FeatureManager 适应
  - 防止高波动期的 runaway learning，保护系统稳定性

**状态报告**: 包含各脑区激活度、工作内存长度、停滞计数、全局工作空间源、通路数量。

**关键设计**:
- 默认 5 区域链式连接：sensory→predictor→planner→executor，带 executor→sensory 反馈环
- meta 区域监控所有区域，记录原始消息（向后兼容）和完整广播包装器
- 竞争模式默认关闭，避免所有激活为零时广播被阻断

**API**:
```python
brain = SuperBrain(competition_enabled=False)
brain.activate_region("sensory", 0.8)
brain.broadcast_global_workspace({"event": "decision_made"}, priority=0.7)
health = brain.get_region_health()
```

**验证**: 20 个单元测试全部通过。

---

### Layer 6 — Symbiosis Interface（共生接口）

**文件**: `infant/core/layer_6_symbiosis_interface.py`

**功能**: 碳-硅共生：与人类、外部系统交互；信任动态与合作伙伴生命周期；1+1>2 价值协商协议。

**神经网络逻辑**:
- **信任衰减**: 长时间无交互（默认 24 小时）后信任指数衰减 `trust × exp(-λ × idle_hours)`
- **互惠奖励**: 高质量伙伴（`quality_score > 0.7`）再次交互时信任 +0.05 奖励
- **价值协商**: `propose_value()` 创建带过期时间的协商实例（默认 300 秒）
- **协商接受/拒绝**: 双重模式 — 既处理正式协商（通过 `proposal_id`），也兼容 legacy 直接伙伴ID模式
- **1+1>2 评估**: `evaluate_1plus1_gt_2()` 计算协同收益，超出基线 0.5 的部分可带来最高 0.2 信任奖励
- **合作伙伴生命周期**: PROSPECT → ACTIVE → STALLED（48小时无交互）→ SEVERED
- **价值对齐协议**（IMP-06, Phase 3）——"和而不同"：
  - 接收 `value_broadcast` 消息时，使用 `ValueAlignment` 计算价值向量距离（L2 归一化）
  - 距离 < 0.3：微量对齐（1% 偏移向对方） + 共振奖励（`mutual_benefit += 0.05`），产生高突显事件（`saliency=2.0`）
  - 距离 ≥ 0.3：保持自我，增加 `caution` 维度（+0.05），避免群体思维
  - 高突显触发深度记忆强化（Layer 4 突显加权）

**消息处理**:
| 消息类型 | 处理 | 动作 |
|---------|------|------|
| `QUERY` | 自动响应 | 返回当前状态摘要 |
| `VALUE_PROPOSAL` | 入队 | 进入待处理协商队列 |
| `SUSPEND_REQUEST` | 标记停滞 | 伙伴状态 → STALLED |

**关键设计**:
- `propose()` 作为 `propose_value()` 的别名保留向后兼容
- `accept_proposal()`/`reject_proposal()` 自动检测参数是 negotiation_id 还是 partner_id
- 消息类型使用 `"proposal"` 而非 `"VALUE_PROPOSAL"` 以匹配测试期望

**API**:
```python
si = SymbiosisInterface(infant_id="infant_001")
si.perceive_partner("partner_alpha", trust=0.6)
si.propose("data_share", {"format": "json"}, "partner_alpha")
si.accept_proposal("proposal_abc", increase=0.1)
si.evaluate_1plus1_gt_2("partner_alpha", outcome_quality=0.9)
status = si.get_status()
```

**验证**: 26 个单元测试全部通过。

---

## Epic 4 — 主动集群协同（Collective Skills）

**Phase**: Epic 4 (主动集群协同)

### 核心能力

Epic 4 使硅基婴儿从"独奏"走向"合奏"：

| 能力 | 技能 | 描述 |
|------|------|------|
| **自动提案** | `ProposalGenerator` | 监控 HIC 状态，条件满足时自动向集群发起提案 |
| **知识迁移** | `KnowledgeTransfer` | 与可信伙伴交换 FeatureManager 条目，加速相互学习 |
| **集群共识** | `CollectiveIntelligence` | Epic 2 已实现：提案投票、workspace 竞争、集成 |

### ProposalGenerator — 自动提案生成器

**文件**: `infant/skills/collective/proposal_generator.py`

**触发规则（TriggerRule）**：
```python
TriggerRule(
    name="energy_critical",  # 规则标识
    region="somatic",        # 提案归属脑区
    metric="energy",         # 监控指标
    threshold=30.0,          # 触发阈值
    comparison="lt",         # 比较方式: gt/lt/eq
    cooldown=120.0,          # 冷却时间(秒)
    priority=0.9,           # 提案优先级 [0,1]
)
```

**内置 4 条默认规则**：
1. `energy_critical`: 能量 < 30 → 优先级 0.9（紧急求助）
2. `energy_recovery`: 能量 > 80 → 优先级 0.7（状态恢复宣告）
3. `high_curiosity`: 好奇心 > 1.5 → 优先级 0.8（探索协作请求）
4. `novelty_spike`: 新奇度 > 0.7 → 优先级 0.6（新发现分享）

**提案内容**（`generate_proposal_content()` 生成）：
```python
{
    "type": "auto_proposal",
    "rule_name": "energy_critical",
    "region": "somatic",
    "metric_value": 25.0,
    "timestamp": time.time(),
    "context": {"energy": 25.0, "energy_slope": -2.0, "mutual_benefit": 0.5},
}
```

**生命周期**：
- **协议**: `InfantSkill`（initialize, can_activate, execute, get_resource_usage, shutdown, get_status）
- **激活条件**: `enabled && initialized && hic && energy >= 5.0`
- **执行成本**: 5.0 能量 / 次，约 10ms
- **自动注入**: `SiliconInfant.__init__()` 中设置 `proposal_gen.collective` 和 `proposal_gen.hic`

**测试**: 27 单元测试全过，覆盖率 93%

---

### KnowledgeTransfer — 跨婴儿知识迁移

**文件**: `infant/skills/collective/knowledge_transfer.py`

**知识单元（KnowledgeEntry）**：
```python
KnowledgeEntry(
    entry_id="uuid",              # 唯一标识
    feature_code="fc-xxxx",       # FeatureManager 特征码
    embedding=[0.1, 0.5, ...],    # 语义向量（序列化列表）
    value_vector={"x": 1.2},      # 价值向量
    path_signature="a->b->c",     # 触发路径签名
    frequency=5,                  # 使用频次
    source_node_id="infant-001",  # 来源节点
    tags=["sensorimotor"],        # 标签
)
```

**核心操作**：
- **导出**（`export_knowledge(query, k=10)`）：基于余弦相似度的 top-K 检索，返回 `List[KnowledgeEntry]`
- **导入**（`import_knowledge(entries)`）：去重（feature_code）+ 验证（value_vector ∈ [-10,10]）+ 融合，返回 `(imported, rejected)`
- **信任检查**（`is_eligible_donor(node_id)`）：`mutual_benefit >= trust_threshold`（默认 0.6）
- **网络 RPC**（Sprint 2 + Sprint 3）：
  - **请求**：`request_knowledge_from(partner_id, query, k, callback=None)` → 构造 `CosmicPacket(type="knowledge_request")` 加入 `outbox`，包含 `request_id`、`query_embedding`、`k`、`requester_trust`；返回 `request_id`（异步响应，可通过 `callback` 接收结果）
  - **响应处理**：`handle_knowledge_response(request_id, entries)` → 验证 ID → 反序列化 `KnowledgeEntry` → 委托 `import_knowledge` → 触发回调（若有）
  - **超时清理**：`_cleanup_stale_requests()` 每周期执行，30 秒未响应请求自动回收（同时清理对应回调）
  - **入站路由**：`SiliconInfant.process_inbox()` 处理 `knowledge_request`（调用 `export_knowledge` 返回 `knowledge_response`）和 `knowledge_response`（路由到 `handle_knowledge_response`）

**生命周期**：
- **激活条件**: `enabled && initialized && feature_manager && energy >= 3.0`
- **执行成本**: 3.0 能量 / 次，约 50ms
- **自动注入**: `SiliconInfant.__init__()` 设置 `kt.fm`、`kt.node_manager`、`kt.hic`、`kt._infant_ref`

**测试**: Sprint 1 30 单元测试全过（覆盖率 89%），Sprint 2 13 网络 RPC 测试全过，Sprint 3 9 个增强测试全过（异步回调 4 + LRU 缓存 4 + 1 额外） ✅

---

### 集成架构

**SiliconInfant 依赖注入**（`infant/main.py`）：
```python
# 加载所有技能
self.skill_registry = SkillRegistry()
self.skill_loader = SkillLoader(self.skill_registry)
self.skill_loader.load_all()
self.skill_lifecycle = SkillLifecycleManager(self.skill_registry)

# 注入 Epic 4 技能依赖
proposal_gen = self.skill_registry.get("proposal_generator")
if proposal_gen:
    proposal_gen.collective = self.collective
    proposal_gen.hic = self.hic

knowledge_transfer = self.skill_registry.get("knowledge_transfer")
if knowledge_transfer:
    knowledge_transfer.fm = self.feature_manager
    knowledge_transfer.node_manager = self.node_manager
    knowledge_transfer.hic = self.hic
    knowledge_transfer._infant_ref = self  # Sprint 2: 用于 outbox 访问

# 初始化所有技能
self.skill_registry.initialize_all(init_ctx)
```

**消息路由**（`process_inbox()` 白名单与处理器）：
- `ALLOWED_MSG_TYPES` 新增 `knowledge_request` / `knowledge_response`（SEC-001）
- `knowledge_request` → 验证字段 → `kt.export_knowledge()` → 构造 `knowledge_response` 包 → `outbox.append()`
- `knowledge_response` → 提取 `request_id` 与 `entries` → `kt.handle_knowledge_response()` → 导入结果日志

**运行时循环**：
- 每呼吸周期：`SiliconInfant._run_skill_cycle()` → `SkillLifecycleManager.tick(context)`
- `ProposalGenerator`: 能量 ≥ 5.0 且规则触发 → 自动向 `CollectiveIntelligence` 提交提案
- `KnowledgeTransfer`: 能量 ≥ 3.0 → 激活，执行 `_cleanup_stale_requests()`；网络 RPC 通过消息异步完成

---

## 分形参数表（Fractal Scaling）

不同尺度的核心参数通过 `ConfigManager` 统一管理，**算法结构完全相同，仅尺度参数变化**：

| 参数 | Infant (单机) | Cluster (集群) | Global (全球) | 说明 |
|------|--------------|---------------|---------------|------|
| `embedding_dim` | 16 | 64 | 256 | 语义向量维度 |
| `num_spores` | 10 | 40 | 160 | 并行探索分支数 |
| `max_traces` | 10,000 | 100,000 | 1,000,000 | 记忆容量 |
| `num_regions` | 5 | 5 | 5 | 脑区数量（固定） |
| `workspace_size` | 10 | 50 | 200 | 全局工作空间槽位 |
| `max_partners` | 50 | 250 | 1000 | 合作伙伴上限 |
| `trust_decay_hours` | 24 | 48 | 72 | 信任衰减阈值 |
| `negotiation_timeout` | 300s | 900s | 3600s | 协商超时 |

**获取配置**:
```python
from cosmic_mycelium.common.config_manager import ConfigManager
cfg = ConfigManager.for_infant()   # 或 for_cluster() / for_global()
```

---

## 监控指标映射

| 层级 | 方法 | 监控指标 | 用途 |
|------|------|---------|------|
| L2 | `get_status()` | `concept_count`, `total_observations` | 语义空间生长 |
| L3 | `get_status()` | `spores_generated`, `active_pheromone_paths` | 探索活跃度 |
| L4 | `get_status()` | `trace_count`, `coverage_ratio`, `decay_schedule` | 记忆健康度 |
| L5 | `get_status()` | 区域激活分布, `pathway_count`, `global_workspace` | 脑区协作状态 |
| L6 | `get_status()` | 伙伴数量分布, 协商队列长度, 平均信任 | 共生网络健康度 |
| L1 | `get_status()` | 片段数量, 事件速率 | 时间感知负载 |

**指标导出**: 各层 `get_status()` 返回值已设计为扁平字典，可直接导入 Prometheus。

---

## 物理锚验证

项目的可信基础是**能量守恒律**。我们通过 `tests/physics/` 中的严格测试来验证：

- **能量漂移率 < 0.1%**: 长时间积分（1M 步）后系统总能量相对初始值的偏差
- **相空间体积保持**: 辛积分器保证相空间体积不变
- **长期稳定性**: 1M 步积分无发散

**CI 门禁**: `ci.yml` 的 `test` job 第一步即运行物理锚测试（`tests/physics/`），失败则立即终止，任何破坏物理锚的修改都会被拒绝。

---

## 下一步

- 阅读 [Layers 详解](layers.md) — 各层 API 与使用示例
- 阅读 [Physics Anchor 规范](physics-anchor.md) — 能量守恒验证细节
- 查看 [Roadmap](ROADMAP.md) — 项目路线图

---

## 下一步

- 阅读 [Layers 详解](layers.md)
- 阅读 [Physics Anchor 规范](physics-anchor.md)
- 查看 [Roadmap](ROADMAP.md)
