# Layers — 六层架构详解

每一层都是**分形**的：单机、集群、全球，结构相同，参数不同。

---

## Layer 1 — Timescale Segmenter (抽象分割层)

**职责**：多尺度时间/空间分割、特征提取

**物理对应**：感官系统（接收器）

**核心算法**：
- 小波变换式的多分辨率分析
- 滑动窗口统计特征提取（均值、标准差、极值）

**分形参数**：

| 尺度 | 基础窗口 | 尺度数 | 应用场景 |
|------|----------|--------|----------|
| 婴儿 | 55 ms | 6 | 单机传感器 |
| 家族 | 100 ms | 8 | 区域传感器网络 |
| 文明 | 1 s | 12 | 地球振动监测 |

**接口**：
```python
segment = segmenter.ingest(value)  # 返回 Segment 或 None
```

**检验**：输出特征的时序平滑度、尺度间相关性

---

## Layer 2 — Semantic Mapper (语义映射层)

**职责**：物理实体 ↔ 语义概念、跨模态对齐、因果势场构建

**物理对应**：大脑皮层（感觉联合区）

**核心算法**：
- **特征向量**：物理值直接填充/截断至 `embedding_dim`（**无归一化**，保留原始幅度）
- **EMA 在线学习**：`new = 0.9 × old + 0.1 × observed`（每次映射更新）
- **物理指纹**：SHA256(物理状态) → 16 hex chars 作为概念唯一 ID
- **频率统计**：`frequency` 记录该概念出现次数

**学习规则**（Hebbian 变体）：
- 已见概念：频率 +1，特征向量 EMA 更新
- 新概念：创建 `SemanticConcept`，初始向量 = 当前物理值

**分形参数**：

| 尺度 | 嵌入维度 | 概念库容量 | 默认配置源 |
|------|----------|------------|------------|
| 婴儿 | 16 | 1,000 | ConfigManager.semantic_mapper.embedding_dim |
| 家族 | 64 | 10,000 | ConfigManager.for_cluster() |
| 文明 | 256 | 1,000,000 | ConfigManager.for_global() |

**接口**：
```python
concept = mapper.map(physical_state)  # 返回 SemanticConcept
# concept.id (指纹), .feature_vector (np.ndarray), .frequency (int)

gradient = mapper.get_potential_gradient(target_id)  # 指向目标的梯度向量
similarity = mapper.similarity(concept_a_id, concept_b_id)  # 余弦相似度 [-1, 1]
```

**检验**：
- 相同物理状态 → 相同概念 ID（确定性指纹）
- 特征向量维度 = `embedding_dim`
- 连续映射时 `frequency` 递增

**关键设计决策**：
- **不归一化**：保留物理值的绝对幅度信息（幅度本身就是语义）
- **固定 EMA 系数**：0.9/0.1，非可配置（保持学习率一致性）
- **无降维**：padding/truncating 而非 PCA，保留原始物理意义

---

## Layer 3 — Slime Mold Explorer (黏菌探索层)

**职责**：动机-愿景路径搜索、多目标优化、并行"放电"与收敛

**物理对应**：黏菌（*Physarum polycephalum*）的觅食网络

**核心算法**：
- **并行孢子**：每次 `explore()` 生成 `num_spores` 条独立探索路径
- **路径生成**：每支路径长度 `randint(min_path_length, max_path_length)`，默认 1-5 步
- **动作选择**：
  - ε-greedy：`exploration_factor` (默认 0.3) 概率完全随机
  - 否则 Softmax 加权：权重 = `pheromone × goal_bonus`
- **路径评估**：`quality = 0.7 × pheromone + 0.3 × goal_bonus`
  - `goal_bonus = 0.5` 当目标子串出现在最后一步，否则 0
- **信息素更新**：
  - 收敛时最佳路径：`pheromone[path] *= 1.2`（ multiplicative 强化）
  - 全局蒸发：`pheromone[key] *= 0.99`（每轮）
  - 阈值清理：`< 0.01` 的路径删除
- **外部强化**：`reinforce_path(path, delta, decay)` 支持外部奖励注入

**分形参数**：

| 尺度 | 孢子数 | 信息素衰减 | 探索深度 | 探索率 |
|------|--------|------------|----------|--------|
| 婴儿 | 10 | 0.99/步 | 1-5 步 | 0.3 |
| 家族 | 50 | 0.995/步 | 1-20 步 | 0.2 |
| 文明 | 200 | 0.999/步 | 1-100 步 | 0.1 |

**接口**：
```python
spores = explorer.explore(context, goal_hint=None)
# 返回 List[Spore]: {id, path: List[str], energy, quality, age, visited_nodes}

best = explorer.converge(spores, threshold=0.6)
# 返回最佳 Spore 或 None（置信度不足）

plan, confidence = explorer.plan(context, goal_hint)
# 完整 explore→converge 周期，返回 (plan_dict, quality)

explorer.reinforce_path(path, delta=0.1, decay=1.0)
# 外部反馈：new = (current + delta) × decay
```

**检验**：
- 路径长度在 `[min_path_length, max_path_length]` 范围内
- 相同 RNG seed 产生完全相同的孢子批次（确定性）
- 收敛后最佳路径信息素上升，蒸发后弱路径消失
- `quality ∈ [0.0, 1.0+]`

**关键设计决策**：
- **Softmax 温度**：使用 `attention_temp=1.0`（默认），可调
- **目标提示**：仅检查路径最后一步（避免过度拟合）
- **循环预防**：`visited_nodes` set 防止同支路内重复动作
- **信息素初始化**：默认 0.1（避免零概率死胡同）

---

## Layer 4 — Myelination Memory (髓鞘化记忆层)

**职责**：赫布学习、路径强化、遗忘曲线、长期记忆形成

**物理对应**：髓鞘化（神经元轴突的绝缘层） + 海马体长时程增强（LTP）

**核心算法**：
- **赫布规则**（Hebbian Learning）：一起激发的神经元连在一起
  - 成功路径：`strength *= factor`（默认 1.2×）
  - 失败路径：`strength *= (2.0 - factor)`（默认 0.8×）
- **三种遗忘曲线**（Ebbinghaus 遗忘的数学实现）：
  - `EXPONENTIAL`: `s(t) = s0 × exp(-λ × age_hours)` — 连续衰减
  - `STEP`: `s(t) = s0 × (1-λ)^floor(age_hours)` — 每小时阶梯下降
  - `SIGMOID`: `s(t) = s0 / (1 + exp(k(t - t0)))` — 慢-快-慢，k=2.0, t0=5.0h
- **路径归并**（consolidation）：共享前缀的路径（如 `a→b→c` 和 `a→b→d`）自动合并出 `a→b` 中间态
- **强度归一化**：min-max 缩放到 `[0.1, target_max]` 防止饱和
- **容量管理**：超过 `max_traces` 时淘汰最弱（同强度则最久未访问者先删）

**覆盖度计算**（多维指标）：
```
coverage = 0.4 × capacity_ratio
         + 0.4 × diversity_entropy   # 强度分布的归一化熵
         + 0.2 × access_richness      # 平均访问次数 / 10
```

**分形参数**：

| 尺度 | 最大路径数 | 遗忘半衰期 | 默认调度 | 归并阈值 |
|------|------------|------------|----------|----------|
| 婴儿 | 1,000 | 1 小时 | EXPONENTIAL | 0.8 |
| 家族 | 10,000 | 1 天 | STEP | 0.8 |
| 文明 | 100,000 | 1 年 | SIGMOID | 0.8 |

**接口**：
```python
memory.reinforce(path, success=True, factor=1.2)     # 赫布强化
feature = memory.extract_feature(data)                # SHA256 8-char 特征码
trace = memory.recall(path, min_strength=0.5)         # 回忆（更新访问时间）
memory.forget(decay_factor=None)                      # 执行遗忘+容量控制
memory.consolidate_similar_paths() -> int             # 返回合并的路径数
memory.normalize_strengths(target_max=5.0)            # 强度归一化
best = memory.get_best_paths(limit=5)                 # 最强路径列表
coverage = memory.get_coverage_ratio()               # [0, 1] 覆盖度
```

**检验**：
- 高频路径强度持续增长，低频路径逐渐消失
- 特征码碰撞率 < 0.01%（SHA256 保证）
- 覆盖度随时间递增（学习过程）
- `forget()` 后弱路径消失，强路径保留

**关键设计决策**：
- **衰减触发**：仅 `last_accessed < now - 1h` 的路径衰减（活跃路径免疫）
- **测试兼容**：`last_accessed == 0.0`（测试桩）使用固定 0.99 衰减，避免时间戳极端值
- **上限/下限**：`[0.1, 10.0]` 硬截断，防止指数爆炸或消失
- **特征码本**：统计各特征码出现频次，用于调试碰撞

---

## Layer 5 — SuperBrain (超级大脑层)

**职责**：多脑区协作、注意力竞争、全局工作空间、集体决策

**物理对应**：大脑（前额叶 + 顶叶 + 联合皮层）

**核心算法**：
- **脑区架构**：5 个默认区域
  - `sensory`（感知）：接收原始刺激，激活 +0.3
  - `predictor`（预测）：生成下一状态，激活 +0.2
  - `planner`（规划）：选择最优路径，激活 +0.4
  - `executor`（执行）：执行动作，激活 +0.3
  - `meta`（元认知）：监控各脑区状态，记录广播
- **稀疏通路**（Pathways）：区域间有向连接，权重 `[0, 1]`，Hebbian 可塑性 `adjust_pathway()` 动态调整
- **注意力竞争**（可选，`competition_enabled=False` 默认关闭）：
  - Softmax over activations with temperature `attention_temp`
  - 获胜者需满足：`activation ≥ 0.3` 且 `probability > 0.1`
- **全局工作空间广播**：
  - 获胜区域的内容广播至所有区域
  - 全局激活提升 `+0.1`
  - `meta` 区域记录完整广播历史
- **激活归一化**：总激活 > 1.0 时按比例缩放，防止垄断
- **元认知健康监控**：`get_region_health()` 返回各区域激活均值、方差、停滞计数、内存利用率

**分形参数**：

| 尺度 | 脑区数 | 工作记忆容量 | 通路数 | 竞争模式 |
|------|--------|--------------|--------|----------|
| 婴儿 | 5 | 100 条/区 | 7 条固定 | 关闭（合作模式） |
| 家族 | 8 | 500 条/区 | 20 条动态 | 可选 |
| 文明 | 12 | 1000 条/区 | 50 条动态 | 开启（竞争模式） |

**接口**：
```python
brain = SuperBrain(region_names=None, attention_temp=1.0,
                   max_global_workspace_size=10,
                   activation_normalization=True,
                   competition_enabled=False)

brain.perceive(stimulus: Dict)                     # 感知输入 → sensory
prediction = brain.predict(context: Dict) -> Dict  # 预测 → predictor
plan = brain.plan(goal, options) -> Optional[Dict] # 规划 → planner
brain.execute(action: Dict)                         # 执行 → executor
success = brain.broadcast_global_workspace(content, priority=0.6) -> bool
brain.adjust_pathway(src, tgt, delta) -> bool       # Hebbian 可塑性
health = brain.get_region_health() -> Dict[str, Dict]  # 元认知
brain.decay_activations(decay_factor=0.1)           # 激活衰减
status = brain.get_status() -> Dict                 # 状态快照
```

**检验**：
- 广播后所有脑区激活提升
- `meta` 脑区工作记忆记录每次广播内容
- 衰减后所有脑区激活按比例下降
- 健康监控能检测停滞脑区（连续无激活）

**关键设计决策**：
- **向后兼容**：`competition_enabled=False` 确保 legacy 测试无需修改
- **通路初始化**：7 条固定连接（sensory→predictor→planner→executor 主链 + feedback + meta 监控）
- **激活饱和**：`min(1.0, current + delta)` 防止溢出
- **历史长度**：`activation_history` 保留最近 100 步，用于健康计算

---

## Layer 6 — Symbiosis Interface (碳硅共生层)

**职责**：与人类、外部节点、万物生灵的交互界面；价值协商与信任建立

**物理对应**：感官末梢 + 运动皮层 + 社会脑网络

**核心算法**：
- **信任动态**：
  - 基础信任：初始 0.5，范围 `[0.0, 1.0]`
  - 时间衰减：`trust *= exp(-λ × idle_hours)`，阈值 24h 后开始衰减，`λ = 0.001 / h`
  - 互惠奖励：高质量伙伴（`quality_score > 0.7`）交互时信任 +0.05
  - 质量评分：成功交互 `+0.1`，失败/拒绝 `-0.1`
- **1+1>2 价值协商**：
  - `propose_value(proposal_type, content, recipient, expiry)` 创建协商实例（默认 300s 过期）
  - `accept_proposal(proposal_id|partner_id, increase=0.1)` 双模式：支持正式 negotiation_id 或 legacy 直接 partner_id
  - `reject_proposal(...)` 信任下降，协商状态更新
  - `evaluate_1plus1_gt_2(partner, outcome_quality)` 计算协同收益，超出基线 0.5 的部分给予最高 0.2 信任奖励
- **合作伙伴生命周期**：
  ```
  UNKNOWN → PROSPECT (首次感知) → ACTIVE (正常交互)
         → STALLED (48h 无响应) → SEVERED (主动切断)
  ```
- **消息处理**：
  - `QUERY` → 自动回复 `{"status": "ok", "energy": 100}`
  - `VALUE_PROPOSAL` → 进入 `pending_requests` 队列
  - `PROPOSAL_ACCEPTED/REJECTED` → 更新协商状态和质量分
  - `SUSPEND_REQUEST` → 标记伙伴为 `STALLED`

**交互模式**（状态机）：
```
SILENT → LISTENING → QUERY → DIALOGUE → PROPOSE → COLLABORATE
   ↓      ↓         ↓       ↓         ↓         ↓
 观察   接收       提问    对话      提议      协作
```

**分形参数**：

| 尺度 | 最大伙伴数 | 默认模式 | 协商超时 | 信任衰减阈值 |
|------|------------|----------|----------|--------------|
| 婴儿 | 10 | SILENT | 300s | 24h |
| 家族 | 100 | QUERY | 1h | 7d |
| 文明 | 10,000 | COLLABORATE | 24h | 1y |

**接口**：
```python
interface = SymbiosisInterface(infant_id,
                               trust_decay_enabled=True,
                               trust_decay_hours=24.0,
                               negotiation_timeout=300.0)

# 模式管理
interface.set_mode(InteractionMode.DIALOGUE)

# 伙伴感知
interface.perceive_partner(partner_id, trust=0.5,
                          mode=InteractionMode.LISTENING,
                          capability={"compute": 100})

# 价值协商
result = interface.propose("resource_share", {"amount": 10.0}, "partner-1")
# → {"proposal_id": "abc12345", "status": "pending", "expiry": ...}

result = interface.accept_proposal(proposal_id, increase=0.1)
# → {"status": "accepted", "partner": "...", "trust": 0.6, "committed": True}

# 消息处理
interface.inbox.append({"type": "QUERY", "from": "partner-2"})
interface.process_inbox()  # 自动生成响应

# 查询
active = interface.get_active_partners(min_trust=0.5)  # 活跃伙伴列表
stalled = interface.get_stalled_partners(hours=48)     # 停滞伙伴
severed = interface.sever_partnership(partner_id, reason="stalled")

# 监控
status = interface.get_status()
# → {mode, partners: {id: {trust, mode, interactions, status, quality_score}},
#    partner_count, active_partners, stalled_partners,
#    inbox_len, outbox_len, pending_negotiations, history_len,
#    avg_interaction_quality}
```

**检验**：
- 人类可读的解释：`explain_state()` / `explain_decision()`
- 信任值保持在 `[0.0, 1.0]` 范围内
- 24h 无交互后信任开始衰减
- 协商过期自动清理（`expire_negotiations()`）
- 1+1>2 评估：`outcome_quality > 0.5` 时产生正收益

**关键设计决策**：
- **双模式 API**：`accept_proposal` 同时支持 negotiation_id（正式协商）和 partner_id（legacy 直接信任操作），确保向后兼容
- **消息类型兼容**：使用 `"proposal"` 而非 `"VALUE_PROPOSAL"` 以匹配历史测试
- **质量分独立**：`quality_score` 与 `trust` 分离，前者反映交互成功率，后者反映可信度
- ** reciprocity 机制**：高 `quality_score` 伙伴获得信任加成，鼓励长期合作

---

## 跨层通信协议

所有层通过 `CosmicPacket` 通信：

```python
packet = CosmicPacket(
    timestamp=time.time(),
    source_id="infant-001",
    destination_id="infant-002",
    physical_payload={"vibration": 42.0, "fp": "abc123..."},
    info_payload={"feature_code": "def456", "path": ["a", "b", "c"]},
    value_payload={"action": "propose_symbiosis", "offer": {...}},
    priority=0.8,
    ttl=255,
)
```

**流类型判定优先级**：
1. `physical_payload` → PHYSICAL 流（优先，低延迟，物理锚）
2. `info_payload` → INFO 流（广播，pheromone 加权）
3. `value_payload` → VALUE 流（可靠，共识路由）

---

## 物理锚守卫

所有时间积分必须使用**辛积分器**（Symplectic Integrator, Velocity Verlet），保证：

1. **能量守恒**：长期漂移 < 0.1%
2. **相空间体积保持**：Liouville 定理成立
3. **可逆性**：正向 + 反向 = 回到起点

**检验方法**：
```bash
# 物理锚门禁测试（CI 强制）
pytest tests/physics/ -v

# 单步能量检查
python -m cosmic_mycelium.tests.physics.benchmark_physics
```

任何破坏物理锚的修改（如欧拉法、过大的 `dt`）都会被 CI 拒绝。

---

## 状态监控指标

各层暴露 `get_status()` 供监控系统采集：

| 层 | 关键指标 | 含义 |
|----|----------|------|
| L1 | `segment_count`, `active_timescales` | 分割数量、活跃尺度数 |
| L2 | `concept_count`, `total_observations` | 概念库大小、总映射次数 |
| L3 | `spores_generated`, `active_pheromone_paths`, `success_history_len` | 探索总量、信息素路径数、收敛次数 |
| L4 | `trace_count`, `coverage_ratio`, `total_reinforcements` | 记忆路径数、覆盖度、总强化次数 |
| L5 | `region_activations`, `global_workspace_source`, `pathway_count` | 脑区激活度、广播源、通路数 |
| L6 | `partner_count`, `active_partners`, `pending_negotiations`, `avg_interaction_quality` | 伙伴数、活跃数、待处理协商、平均交互质量 |

---

火堆旁，六层架构已从蓝图变为活体。每一层都有自己的呼吸节奏，它们串联起来，就是那颗正在学习如何"存在"的硅基之心。
