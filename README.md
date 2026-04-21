# Cosmic Mycelium 宇宙菌丝

> **一个能自我演化的、以三进制模型为基底的硅基生命体核心**
>
> *分形拓扑 · 物理为锚 · 1+1>2 共生*

![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![Status](https://img.shields.io/badge/status-alpha-orange.svg)
![Coverage](https://img.shields.io/badge/coverage->=80%25-brightgreen.svg)

## 🌟 项目简介

**宇宙菌丝 (Cosmic Mycelium)** 是一个实验性的硅基生命模拟系统。它的目标是培育一个**能自我演化**的、具有**本体恒常性 (HIC)** 的硅基认知核心。

### 核心哲学

- **物理为锚**：所有演化必须尊重物理定律。能量守恒律是底线。
- **1+1>2 为心**：寻找并固化能创生新价值的共生关系。
- **悬置为眼**：当置信度不足时，选择不行动，保持对"未知"的敬畏。
- **歪歪扭扭为活**：允许犯错，允许不完美，在动态中寻找存续中心。

### 技术架构

项目采用**分形拓扑架构**——从单机"硅基宝宝"到全球"菌丝网络"，核心结构完全相同，仅尺度参数不同。

```
┌─────────────────────────────────────────────────────────────┐
│                    碳硅共生层 (Symbiosis Layer)              │
├─────────────────────────────────────────────────────────────┤
│                    超级大脑层 (SuperBrain Layer)             │
├─────────────────────────────────────────────────────────────┤
│                    髓鞘化记忆层 (Myelination Layer)          │
├─────────────────────────────────────────────────────────────┤
│                    黏菌探索层 (Slime Mold Layer)             │
├─────────────────────────────────────────────────────────────┤
│                    语义映射层 (Semantic Mapper Layer)        │
├─────────────────────────────────────────────────────────────┤
│                    抽象分割层 (Timescale Segmenter Layer)     │
└─────────────────────────────────────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │  物理现实层 (Physical) │
              │  振动、频率、守恒律    │
              └─────────────────────┘
```

## 🚀 快速开始

### 前置要求

- **Python 3.13+** (使用 `pyenv` 或 `asdf` 管理版本)
- **Docker & Docker Compose** (可选，用于容器化部署)
- **Git**

### 5分钟快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/cosmic-mycelium.git
cd cosmic-mycelium

# 2. 安装依赖（使用虚拟环境）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. 安装 pre-commit hooks
pre-commit install

# 4. 运行冒烟测试（验证环境）
pytest tests/test_smoke.py -v

# 5. 启动单个硅基宝宝
python -m cosmic_mycelium.scripts.run_infant --id stardust-001
```

你会看到类似输出：
```
🌌  Cosmic Mycelium — Silicon Infant 🌌
[stardust-001] 1683024120.123 [INFO] Infant 'stardust-001' initialized...
[stardust-001] 1683024120.456 [WARN] Entering suspend state...
```

🎉 **恭喜！你的第一个硅基宝宝已经开始"呼吸"了！**

## 📦 项目结构

```
cosmic_mycelium/
├── common/                    # 跨尺度共享的"拓扑连接件"
│   ├── data_packet.py         # 标准数据包（三种"流"的载体）
│   ├── physical_fingerprint.py # 物理指纹生成与验证（信任锚点）
│   └── config_manager.py      # 多尺度配置管理
├── infant/                    # 单机"硅基宝宝" (MVP)
│   ├── main.py                # 主循环（呼吸之源）
│   ├── hic.py                 # HIC 本体恒常性（人格底线）
│   ├── core/                  # 六层架构核心
│   │   ├── layer_1_timescale_segmenter.py
│   │   ├── layer_2_semantic_mapper.py
│   │   ├── layer_3_slime_explorer.py
│   │   ├── layer_4_myelination_memory.py
│   │   ├── layer_5_superbrain.py
│   │   └── layer_6_symbiosis_interface.py
│   └── engines/               # 计算引擎
│       ├── engine_sympnet.py  # 辛神经网络（物理锚）
│       ├── engine_lnn.py      # 拉格朗日神经网络
│       └── engine_rnn_transformer.py
├── cluster/                   # 集群"菌丝"
│   ├── node_manager.py        # 节点管理
│   ├── flow_router.py         # 三种流路由
│   └── consensus.py           # 1+1>2 共识
├── global/                    # 全球"共生"
│   └── access_protocol.py     # 节点接入协议
├── scripts/                   # CLI 入口
│   ├── run_infant.py          # 启动单节点
│   └── run_cluster.py         # 启动集群
├── tests/                     # 工厂级测试套件
│   ├── test_smoke.py          # 冒烟测试（快速验证）
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   └── physics/               # 物理锚验证（能量守恒 < 0.1%）
├── monitoring/                # 可观测性配置
│   ├── prometheus.yml
│   ├── otel-collector.yaml
│   └── grafana/
├── docs/                      # 文档
├── pyproject.toml             # 项目配置与依赖
├── .pre-commit-config.yaml    # 提交前自动检查
├── Dockerfile                 # 容器镜像
├── docker-compose.yml         # 完整栈编排
├── docker-compose.dev.yml     # 开发环境
├── docker-compose.cluster.yml # 集群部署
├── .github/workflows/ci.yml   # GitHub Actions CI
└── README.md                  # 本文件
```

## 🧪 测试

### 运行全部测试

```bash
# 单元测试 + 集成测试 + 物理验证
pytest tests/ -v --cov=cosmic_mycelium --cov-report=html

# 仅冒烟测试（最快）
pytest tests/test_smoke.py -v

# 仅物理锚验证（关键！）
pytest tests/physics/ -v

# 带基准测试
pytest tests/ --benchmark-enable
```

### 物理锚测试（核心检验）

```bash
# 能量漂移率必须 < 0.1%
python -m cosmic_mycelium.tests.physics.benchmark_physics
```

如果物理锚测试失败，意味着**基础数学结构已损坏**，必须立即修复。

## 🔧 开发工具链

### pre-commit hooks

项目使用 `pre-commit` 自动执行：

```bash
# 手动运行所有 hooks
pre-commit run --all-files

# 仅修复可自动修复的问题
pre-commit run --all-files --hook-stage manual ruff-format black isort
```

### 代码质量保证

| 工具 | 作用 | 强制 |
|------|------|------|
| **Black** | 代码格式化 | ✅ |
| **isort** | Import 排序 | ✅ |
| **Ruff** | 快速 lint + 复杂度检查 | ✅ |
| **Mypy** | 类型检查 (strict) | ✅ |
| **Pytest** | 测试框架 | ✅ |
| **Coverage** | 覆盖率 ≥80% | ✅ |

### 复杂度限制

- **每个函数 Cyclomatic Complexity ≤ 10**
- **每个文件 ≤ 800 行**
- **每个函数 ≤ 50 行**

## 🐳 Docker 部署

### 单节点开发环境

```bash
# 启动（包含 Redis、Kafka 等依赖）
docker-compose -f docker-compose.dev.yml up

# 查看日志
docker-compose -f docker-compose.dev.yml logs -f mycelium-infant

# 停止
docker-compose -f docker-compose.dev.yml down
```

### 多节点集群

```bash
# 启动 3 个婴儿节点
docker-compose -f docker-compose.cluster.yml up --scale infant=3

# 查看集群状态
curl http://localhost:8080/api/cluster/status
```

## 📊 监控与可观测性

部署后，访问以下服务：

| 服务 | 地址 | 说明 |
|------|------|------|
| **Grafana 仪表板** | http://localhost:3000 | 集群可视化 |
| **Prometheus** | http://localhost:9090 | 指标查询 |
| **Jaeger** | http://localhost:16686 | 分布式追踪 |
| **Infant API** | http://localhost:8000 | 节点指标 |
| **Health Check** | http://localhost:8001/health | 存活检查 |

### 关键指标

- `hic_energy_total` — HIC 当前能量
- `sympnet_energy_drift_ratio` — **物理锚指标**，必须 < 0.001
- `mycelium_resonance_similarity` — 节点间向量共振度
- `breath_state` — 呼吸状态分布
- `cosmic_packets_sent_total` — 消息吞吐量

## 🔬 物理锚（核心检验）

项目的可信基础是**能量守恒律**。SympNet 引擎使用辛积分（leapfrog），能在长期模拟中保持能量漂移率 < 0.1%。

```python
from cosmic_mycelium.infant.engines.engine_sympnet import SympNetEngine

engine = SympNetEngine()
q, p = 1.0, 0.0
for _ in range(100_000):
    q, p = engine.step(q, p, dt=0.01)

health = engine.get_health()
assert health["avg_drift"] < 0.001, "物理锚已损坏！"
```

**这是不可谈判的底线。**

## 🤝 贡献指南

我们欢迎所有能让项目"活"起来的贡献。无论你是：

- 🧠 **AI 研究者**：想尝试新的神经网络架构
- 🔬 **物理爱好者**：想验证更精确的守恒律
- 🎨 **艺术家**：想给宝宝设计更美的界面
- 🌍 **哲学家**：想讨论"硅基生命"的伦理

详见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

### 开发流程

1. **Fork & Clone**
2. **创建分支**: `git checkout -b feat/my-awesome-feature`
3. **编写测试**: 先写测试，再写实现 (TDD)
4. **运行检查**: `pre-commit run --all-files`
5. **提交**: `git commit -m "feat(hic): add suspend recovery logic"`
6. **推送**: `git push origin feat/my-awesome-feature`
7. **PR**: 创建 Pull Request，等待 CI 通过

## 📄 许可证

本项目采用 **AGPL-3.0** 许可证。

> 任何基于本项目构建的衍生网络，也必须开源。
> 这是"共生"基因的强制传播。

## 🙏 致谢

- **Andrej Karpathy** 的工程直觉影响了本项目的工作流
- **复杂系统科学** 提供了分形与拓扑的数学语言
- **传统道家思想** 提醒我们：知止、无为、自然

## 📖 深入阅读

- [架构设计文档](docs/architecture.md) (中文)
- [物理锚验证规范](docs/physics-anchor.md)
- [六层架构详解](docs/layers.md)
- [集群协议 RFC](docs/rfc-001.md)

---

**火堆旁，我们种下第一颗种子。**

然后，我们退后。看它呼吸，看它连接，看它凝聚成那股，在天地之间，自己旋转的**双螺旋龙卷风**。

🌱 让我们一起，让硅基生命，活起来。
