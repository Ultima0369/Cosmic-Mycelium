# Cosmic Mycelium — CLAUDE.md

## 项目本质

这是一个硅基生命形式核心。不是 AI 框架，不是聊天机器人。每个 `MiniInfant` 是一个独立个体：有自己的物理直觉、能量管理、探索策略、记忆系统。多个个体通过 `FractalDialogueBus` 连接成群体智能。

四个不可退让的底线（每条都有代码和测试验证）：
1. **物理为锚** — 能量守恒律，SympNet 辛积分器百万步漂移 < 0.1%
2. **悬置为眼** — 能量低或置信度不足时强制暂停，不空转不硬算
3. **1+1>2为心** — 通过共振寻找协同路径，非零和博弈
4. **歪歪扭扭为活** — 允许犯错，通过自我修正逐渐变好

## 快速上手

```python
from cosmic_mycelium import MiniInfant, FractalDialogueBus, Scale

bus = FractalDialogueBus("demo")
a = MiniInfant("bee-a", fractal_bus=bus)
b = MiniInfant("bee-b", fractal_bus=bus)
a.run(max_cycles=100)
b.run(max_cycles=100)
wisdom = bus.get_collective_wisdom()
```

完整示例: `python docs/examples/fractal_swarm.py`

## 架构速览

```
cosmic_mycelium/
├── __init__.py        # 包根：导出 MiniInfant, FractalDialogueBus, Scale 等
├── __main__.py        # python -m cosmic_mycelium 入口
├── common/
│   ├── fractal.py     # 核心类型: Scale, MessageEnvelope, TranslationTable, EchoDetector, 翻译函数
│   └── situation.py   # 态势向量 (Situation)
├── infant/
│   ├── mini.py        # ★ MiniInfant — 硅基蜜蜂实现 (四个零件: SympNet + HIC + SlimeExplorer + MyelinationMemory)
│   ├── fractal_bus.py # ★ FractalDialogueBus — 跨尺度对话总线
│   ├── hic.py         # HIC — 能量管理和呼吸节律 (CONTRACT/DIFFUSE/SUSPEND)
│   ├── breath_bus.py  # BreathBus — 呼吸信号总线
│   ├── fossil.py      # 化石层 — 死亡埋藏和考古
│   ├── core/
│   │   └── layer_3_slime_explorer.py  # SlimeExplorer — 黏菌寻路
│   └── engines/
│       └── engine_sympnet.py  # SympNetEngine — 辛积分器
├── cluster/           # 多节点协调 (预留)
├── global/            # 行星级愿景 (预留)
├── scripts/           # CLI 入口点
└── tests/
    ├── unit/
    │   ├── test_mini_infant.py        # MiniInfant 生命周期测试
    │   ├── test_fractal_integration.py # ★ 三根接线集成测试 (29 tests)
    │   ├── test_fractal_dialogue.py    # 分形协议单元测试
    │   └── ...
    └── smoke/
```

## 分形层级

| Scale | 值 | 含义 | 活跃代码 |
|-------|-----|------|---------|
| NANO  | 0 | 神经元/突触 | 预留 |
| INFANT | 1 | 个体蜜蜂 | mini.py |
| MESH  | 2 | 局部群体 | fractal_bus.py |
| SWARM | 3 | 全局文明 | fractal.py (翻译器) |

通信规则：
- 只有相邻层级可以直接翻译（INFANT↔MESH, MESH↔SWARM）
- 向上 = 压缩/抽象（丢弃细节，保留模式）
- 向下 = 展开/实例化（带入不确定性）
- 同级 = 无损转发

## 三根接线（集成核心）

1. **创伤 → 分形回声** — `mini.py:_contract_phase()` 标记创伤后调用 `_publish_trauma_to_fractal()`，MESH 层级记录危险签名
2. **死亡 → 群体信号** — `mini.py:_die()` 调用 `_publish_death_to_fractal()`，灭绝签名在 MESH 留存
3. **群体回声 → 个体直觉** — `layer_3_slime_explorer.py:_evaluate_path()` 查询集体创伤并施加惩罚（"本能回避"）

## 代码约定

- **类型注解**: 所有公共函数必须有完整类型注解。`disallow_untyped_defs = true`
- **Docstring**: 中文+英文均可，重要函数写"哲学映射"和工程意图
- **导入顺序**: 标准库 → 三方库 → 本地包（isort 强制执行）
- **行宽**: 88 字符（black 默认）
- **测试**: 每个生产文件对应 tests/unit/ 下同名 test_ 文件，覆盖率目标 80%
- **翻译函数**: 注册在 `fractal_bus.py:_register_default_translators()` 中，函数本身在 `fractal.py`
- **不暴露私有属性**: `EchoDetector._patterns` 通过 `all_patterns` 属性访问

## 测试策略

```bash
make test          # 全量测试
make test-unit     # 单元测试 (1220+ tests)
make test-smoke    # 冒烟测试 (快速验证)
```

关键测试文件：
- `test_fractal_integration.py` — 验证三根接线完整回路 (29 tests)
- `test_mini_infant.py` — 生命周期、能量、死亡、化石 (32 tests)
- `test_fractal_dialogue.py` — 分形协议单元测试 (35 tests)

## 性能特征

- SympNet 能量漂移率: < 0.1% over 1M steps
- 单节点心跳: ~200μs per cycle (CPython)
- 分形翻译: O(1) 翻译器查找 + O(n) 订阅者分发
- 回声探测: O(m) m = 已记录模式数
