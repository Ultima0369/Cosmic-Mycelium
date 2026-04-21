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
