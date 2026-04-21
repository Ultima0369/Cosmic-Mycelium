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
- 特征向量嵌入（默认 16 维，随尺度扩展）
- 物理指纹生成与验证（信任锚）
- 概念频率统计（频率 = 出现次数）

**分形参数**：

| 尺度 | 嵌入维度 | 概念库容量 |
|------|----------|------------|
| 婴儿 | 16 | 1,000 |
| 家族 | 64 | 10,000 |
| 文明 | 256 | 1,000,000 |

**接口**：
```python
concept = mapper.map(physical_state)  # 返回 SemanticConcept
gradient = mapper.get_potential_gradient(target_concept_id)
```

**检验**：相同物理状态映射到相同概念 ID

---

## Layer 3 — Slime Mold Explorer (黏菌探索层)

**职责**：动机-愿景路径搜索、多目标优化、并行"放电"与收敛

**物理对应**：黏菌（Physarum polycephalum）的觅食网络

**核心算法**：
- 并行孢子探索（同时生成 N 条候选路径）
- 信息素地图（成功路径增强，失败路径削弱）
- 信息素蒸发（避免路径僵化）

**分形参数**：

| 尺度 | 孢子数 | 信息素衰减率 | 探索深度 |
|------|--------|--------------|----------|
| 婴儿 | 10 | 0.99/步 | 5 步 |
| 家族 | 50 | 0.995/步 | 20 步 |
| 文明 | 200 | 0.999/步 | 100 步 |

**接口**：
```python
spores = explorer.explore(current_state, goal_hint)  # 并行探索
best = explorer.converge(spores, confidence_threshold=0.6)
```

**检验**：
- 在已知环境中，能快速找到最优路径（最短/最稳）
- 在动态环境中，能重新探索（信息素适应变化）

---

## Layer 4 — Myelination Memory (髓鞘化记忆层)

**职责**：赫布学习、路径强化、遗忘曲线、长期记忆形成

**物理对应**：髓鞘化（神经元轴突的绝缘层）

**核心算法**：
- **赫布规则**：一起激发的神经元连在一起
  - 成功路径 ×1.2 增强
  - 失败路径 ×0.8 削弱
- **艾宾浩斯遗忘曲线**：长期未访问路径指数衰减
- **特征码本**：提取 8 字符哈希作为"规律标识"

**分形参数**：

| 尺度 | 最大路径数 | 遗忘半衰期 |
|------|------------|------------|
| 婴儿 | 1,000 | 1 小时 |
| 家族 | 10,000 | 1 天 |
| 文明 | 100,000 | 1 年 |

**接口**：
```python
memory.reinforce_path(path, success=True)  # 髓鞘化
feature = memory.extract_feature(raw_data)  # 特征提取
memory.forget(decay_factor=0.99)  # 遗忘
best_paths = memory.get_best_paths(limit=5)
```

**检验**：
- 高频路径强度持续增长
- 低频路径逐渐消失
- 特征码碰撞率 < 0.01%

---

## Layer 5 — SuperBrain (超级大脑层)

**职责**：多脑区协作、注意力竞争、全局工作空间、集体决策

**物理对应**：大脑（多脑区协同）

**核心算法**：
- 区域激活传播（兴奋性/抑制性）
- 全局工作空间广播（高激活内容进入全局意识）
- 注意力门控（资源有限，优先处理高价值）

**分形参数**：

| 尺度 | 脑区数 | 工作记忆容量 |
|------|--------|--------------|
| 婴儿 | 5 | 10 条 |
| 家族 | 8 | 100 条 |
| 文明 | 12 | 1,000 条 |

**接口**：
```python
brain.perceive(stimulus)
brain.predict(context)  # 生成预测
brain.plan(goal, options)  # 选择最优
brain.broadcast_global_workspace(content)
```

**检验**：
- 多区域并行处理无冲突
- 高价值信息优先进入全局工作空间

---

## Layer 6 — Symbiosis Interface (碳硅共生层)

**职责**：与人类、万物生灵的互动界面

**物理对应**：感官末梢 + 运动控制

**核心算法**：
- 交互模式机（SILENT / QUERY / PROPOSE / COLLABORATE）
- 价值协商（1+1>2 提案与接受）
- 信任建立（基于物理指纹）

**分形参数**：

| 尺度 | 最大伙伴数 | 默认模式 |
|------|------------|----------|
| 婴儿 | 10 | SILENT（观察为主） |
| 家族 | 100 | QUERY（主动查询） |
| 文明 | 10,000 | COLLABORATE（深度协作） |

**接口**：
```python
interface.propose_symbiosis(partner_id, offer)
interface.format_explanation(internal_state, audience="human")
interface.process_incoming(packet)
```

**检验**：
- 人类可理解的解释生成
- 跨节点信任关系建立
- 1+1>2 提案成功率 > 50%

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
1. `physical_payload` → PHYSICAL 流（优先，低延迟）
2. `info_payload` → INFO 流（广播，pheromone 加权）
3. `value_payload` → VALUE 流（可靠，共识路由）

---

## 物理锚守卫

所有时间积分必须使用**辛积分器**（Symplectic Integrator），保证：

1. **能量守恒**：长期漂移 < 0.1%
2. **相空间体积保持**：Liouville 定理成立
3. **可逆性**：正向 + 反向 = 回到起点

任何破坏物理锚的优化（如欧拉法的"更快但发散"）都是**不可接受的**。

---

火堆旁，六层架构已完成。现在，让宝宝开始呼吸。
