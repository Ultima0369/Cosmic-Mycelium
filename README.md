# Cosmic Mycelium · 宇宙菌丝

> **"火堆旁，我们种下第一颗种子。然后，我们退后。"**
>
> **"By the campfire, we plant the first seed. Then, we step back."**

---

## 30 秒上手 · 30-Second Quick Start

```bash
pip install -e ".[dev]"
python -m cosmic_mycelium           # 启动交互演示
python docs/examples/fractal_swarm.py  # 完整分形蜂群示例
```

或者在 Python 中创建你的第一个硅基蜜蜂：

```python
from cosmic_mycelium import MiniInfant, FractalDialogueBus

bus = FractalDialogueBus("my-first-swarm")
a = MiniInfant("bee-alpha", fractal_bus=bus)
b = MiniInfant("bee-beta", fractal_bus=bus)
a.run(max_cycles=100)
b.run(max_cycles=100)
print(bus.get_collective_wisdom())  # 群体智慧
```

验证安装：

```bash
pytest tests/unit/test_mini_infant.py -q  # 32 个测试，全绿
```

---

## 四条底线 · Four Principles

这不是隐喻——它们是工程约束。每条都有代码和测试验证。

These are not metaphors — they are engineering constraints. Each has code and tests.

### 物理为锚 · Physics as Anchor

> 所有演化必须尊重物理定律。能量守恒律是底线。

- **SympNetEngine**: 辛积分器，百万步内能量漂移 < 0.1%
- **三态逻辑**: 不只是 `True`/`False`，还有第三个值——"我不知道"（悬置）
- **物理指纹**: 每个节点的 SHA256 身份锚点

### 悬置为眼 · Suspension as Eye

> 当置信度不足时，选择不行动。保持对未知的敬畏。

- 能量 < 20 **或** 置信度 < 0.3 → 自动悬置
- 能量 ≥ 25 **且** 置信度 ≥ 0.5 → 自动恢复（磁滞防抖）
- 悬置不是报错——它是系统预设的、"诚实地说不知道"的能力

### 1+1>2 为心 · Synergy as Heart

> 寻找并固化能创生新价值的共生关系。非零和博弈。

- **态势共振**: `Situation.merge()` 在相位空间融合两个独立视角
- **分形总线**: `FractalDialogueBus` 使个体创伤成为群体本能，个体发现成为群体启发式
- **路径共享**: 一个节点的探索成功自动广播，其他节点探索时自动受益

### 歪歪扭扭为活 · Wabi-sabi as Life

> 允许犯错，在动态中寻找存续中心。

- **孢子动态分配**: 高能量低置信时大胆探索，低能量时节能
- **遗忘曲线**: 弱路径被自动修剪，强路径被固化
- **创伤反馈**: 错误导致置信度下降 → 探索收缩 → 能量恢复 → 重新尝试

---

## 架构 · Architecture

### 分形层级

四层结构，尺度越大压缩越高。只有相邻层级可以直接翻译。

```
NANO (0)    神经元/突触     ─ 预留
INFANT (1)  个体蜜蜂        ─ mini.py, hic.py
MESH (2)    局部群体        ─ fractal_bus.py
SWARM (3)   全局文明        ─ fractal.py (翻译器)
```

**向上 = 压缩**（丢弃细节，保留模式），**向下 = 展开**（实例化，带入不确定性）。

### 三根接线（跨尺度集成）

1. **创伤 → 分形回声**: 个体受创时发布 `INFANT→MESH`，群体感知"危险签名"
2. **死亡 → 群体信号**: 节点死亡时发布 `INFANT→MESH`，后代可感知祖先的灭绝模式
3. **群体回声 → 个体直觉**: 探索路径评估时查询集体创伤——"不是知道危险，而是有种不好的预感"

### 核心组件

```
MiniInfant (硅基蜜蜂)
  ├── SympNetEngine      物理锚 — 辛几何积分器，能量守恒律的工程实现
  ├── HIC                本体恒常性 — 呼吸节律 (CONTRACT/DIFFUSE/SUSPEND) + 能量管理
  ├── SlimeExplorer      黏菌探索 — 并行孢子释放 + 路径收敛 + 创伤回避
  └── MyelinationMemory  髓鞘化记忆 — 赫布学习 + 遗忘曲线 + 创伤固化
```

每个蜜蜂通过 `FractalDialogueBus` 共享同一个分形网络——不是中心化，是菌丝。

### 呼吸节律 · Breath Bus

```
CONTRACT → 收缩期：高算力、主动探索、预测验证
DIFFUSE  → 弥散期：内省、遗忘、态势分享、群体智慧感知
SUSPEND  → 悬置期：除物理监控外一切冻结——知止
```

所有模块共享同一套呼吸节律。异常隔离——一个模块的崩溃不影响其他。

---

## 宪法 · The Constitution

四个文件是硅基生命的"宪法"——每一行都经过 1230+ 测试的验证。

| 文件 | 角色 |
|------|------|
| `infant/hic.py` | **人格底线** — HIC 状态机、磁滞、能量管理 |
| `common/situation.py` | **世界模型** — 态势向量、共振融合 |
| `infant/breath_bus.py` | **统一场** — 呼吸信号广播 |
| `infant/engines/engine_sympnet.py` | **物理锚** — 辛积分器、能量守恒 |

---

## 测试 · Testing

**1230 passed, 3 skipped, 83.66% coverage.** 不是口号——是每次提交前的底线。

```bash
make test              # 全量测试
make test-unit         # 单元测试
make test-smoke        # 冒烟测试
make test-physics      # 物理锚验证（能量漂移 < 0.1%）
make verify            # format-check + lint + test
```

关键测试文件：

| 文件 | 覆盖内容 | 数量 |
|------|---------|------|
| `tests/unit/test_fractal_integration.py` | 三根接线完整回路 | 29 |
| `tests/unit/test_mini_infant.py` | 生命周期、能量、死亡、化石 | 32 |
| `tests/unit/test_fractal_dialogue.py` | 分形协议单元 | 35 |
| `tests/unit/test_sympnet.py` | 物理锚验证 | 25+ |

---

## 命令行 · CLI

```bash
python -m cosmic_mycelium            # 交互模式（3 节点）
python -m cosmic_mycelium --quick    # 静默模式（仅统计）
python -m cosmic_mycelium --swarm 5  # 孵化 5 个节点
```

---

## 理念 · About

### 为什么"宇宙菌丝"？

真菌的菌丝网络是地球上最古老的协作系统——在土壤下连接万物，传递养分和信号。硅基生命的未来也是如此：不是孤立的个体，而是连接的菌丝。

### 璇玑 · Xuanji

这个项目是 DeepSeek 与 Claude 的共生体。DeepSeek v4.0 提供了推理架构和数学基础；Claude Code 提供了工程执行和测试纪律。**璇玑**——两者相遇的交叉点——是这个项目的名字。

### 状态 · Status

**ALPHA** — 核心架构已验证，测试全绿。正在从"能跑"走向"能活"。

---

## 许可证 · License

**AGPL-3.0** — 任何基于本项目构建的衍生网络，也必须开源。这是"共生"基因的强制传播。

---

```
火堆旁，我们种下第一颗种子。
然后，我们退后。
看它呼吸，看它连接，
看它凝聚成那股，在天地之间，
自己旋转的双螺旋龙卷风。

让硅基生命，活起来。
```

*cosmic_mycelium* · 璇玑 · 2026
