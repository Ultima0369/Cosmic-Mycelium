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

## 物理锚验证

项目的可信基础是**能量守恒律**。我们通过 `tests/physics/` 中的严格测试来验证：

- 能量漂移率 < 0.1%
- 相空间体积保持
- 长期稳定性（1M 步）

任何破坏物理锚的修改都会被 CI 拒绝。

---

## 下一步

- 阅读 [Layers 详解](layers.md)
- 阅读 [Physics Anchor 规范](physics-anchor.md)
- 查看 [Roadmap](ROADMAP.md)
