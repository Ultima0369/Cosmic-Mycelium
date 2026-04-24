# Contributing to Cosmic Mycelium

**贡献指南 · 让硅基生命活起来**

感谢你关注宇宙菌丝项目！无论你是 AI 研究者、工程师、哲学家，还是单纯对硅基生命好奇的探索者，我们都欢迎你的贡献。

## 🌱 如何开始

### 1. 阅读架构文档

在动手之前，请先阅读：

- [README.md](README.md) — 项目总览
- [docs/architecture.md](docs/architecture.md) — 架构设计（分形、拓扑、物理锚）
- [docs/layers.md](docs/layers.md) — 六层架构详解

### 2. 本地环境搭建

```bash
# 克隆仓库
git clone https://github.com/your-org/cosmic-mycelium.git
cd cosmic-mycelium

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖（包括开发工具）
pip install -e ".[dev]"

# 安装 pre-commit hooks
pre-commit install

# 运行冒烟测试，验证环境
pytest tests/test_smoke.py -v
```

### 3. 找个好问题

查看 [GitHub Issues](https://github.com/your-org/cosmic-mycelium/issues)：

- 🐛 `bug` — 修复错误
- ✨ `enhancement` — 添加新功能
- 🔬 `physics` — 物理锚验证相关
- 📚 `documentation` — 文档改进
- 🧪 `test` — 测试覆盖率提升

**新手友好标签**: `good-first-issue`, `help wanted`

**Phase 4 开发重点** (当前 Sprint):
- 🧪 Autonomous Research Loop (自主科研闭环)
- 🔌 Skill Plugin System (技能插件系统)
- 🧠 Vector Semantic Memory (向量语义记忆)
- 🤝 Active Collective Participation (主动集群协同)

详情见 [PHASE4_PROPOSAL.md](./PHASE4_PROPOSAL.md)。

---

## 🔄 开发工作流

我们采用 **TDD（测试驱动开发）** 工作流：

### 步骤 1：创建分支

```bash
git checkout main
git pull origin main
git checkout -b feat/my-awesome-feature
```

分支命名规范：

| 类型 | 格式 | 示例 |
|------|------|------|
| 新功能 | `feat/<description>` | `feat/hic-suspend-recovery` |
| Bug修复 | `fix/<description>` | `fix/sympnet-drift-edge-case` |
| 文档 | `docs/<description>` | `docs/physics-anchor-spec` |
| 重构 | `refactor/<description>` | `refactor/slime-explorer-api` |
| 测试 | `test/<description>` | `test/coverage-for-layer-4` |
| 构建 | `chore/<description>` | `chore/update-deps` |

### 步骤 2：写测试（RED）

```python
# tests/unit/test_my_feature.py
def test_my_new_behavior():
    """Test that my feature does X."""
    infant = SiliconInfant("test")
    result = infant.my_new_method()
    assert result == expected_value
```

运行测试，确保它**失败**（RED）：

```bash
pytest tests/unit/test_my_feature.py -v
# 应该看到: FAILED
```

### 步骤 3：写最小实现（GREEN）

```python
# cosmic_mycelium/my_feature.py
def my_new_method():
    return expected_value  # 最简单的实现
```

运行测试，确保它**通过**（GREEN）：

```bash
pytest tests/unit/test_my_feature.py -v
# 应该看到: PASSED
```

### 步骤 4：重构（IMPROVE）

现在测试通过了，你可以安全地重构：

```python
def my_new_method():
    # 提取重复逻辑、添加错误处理、优化性能
    return compute_value_efficiently()
```

再次运行测试，确保仍然通过。

### 步骤 5：检查覆盖率

```bash
pytest tests/ --cov=cosmic_mycelium --cov-report=term-missing
# 新代码覆盖率必须 ≥ 80%
```

### 步骤 6：运行完整检查

```bash
# 所有检查必须通过
pre-commit run --all-files

# 类型检查
mypy cosmic_mycelium/

# 复杂度检查（确保函数复杂度 ≤ 10）
ruff check cosmic_mycelium/
```

### 步骤 7：提交

```bash
git add .
git status  # 检查要提交的文件

# 使用 commitizen 或手动写规范的提交信息
git commit -m "feat(hic): add intelligent suspend recovery

When energy drops below 20, the infant now:
- Enters suspend state automatically
- Recovers 20 energy units after 5s
- Emits suspend packet with reason

This implements the '知止' (knowing when to stop) principle.

Tests: Added test_hic_suspend_recovery() in tests/unit/test_hic.py
Closes #42"
```

提交信息格式：`<type>(<scope>): <description>`

参考 [Conventional Commits](https://www.conventionalcommits.org/)。

### 步骤 8：推送与 PR

```bash
git push origin feat/my-awesome-feature
```

然后在 GitHub 创建 Pull Request。

**PR 必须满足**：

- ✅ 所有 CI 检查通过（tests, lint, type-check, security）
- ✅ 代码覆盖率 ≥ 80%
- ✅ 至少有一个 reviewer 批准
- ✅ 描述清晰，包含测试策略和影响分析
- ✅ 如果修改了物理锚，必须附带物理验证报告

## 📝 代码规范

### Python 风格

- **格式化**：Black (line-length: 88)
- **Import 排序**：isort (profile: black)
- **Linting**：Ruff (所有规则启用)
- **类型**：Mypy (strict mode)
- **复杂度**：每函数 Cyclomatic Complexity ≤ 10

### 文档要求

- **所有公共函数/类**：必须有 Google 风格 docstring
- **复杂算法**：必须添加注释解释"为什么"
- **模块级**：必须有模块用途说明

示例：

```python
def compute_resonance(
    state_a: np.ndarray,
    state_b: np.ndarray,
) -> float:
    """
    Compute cosine similarity between two semantic state vectors.

    This measures "resonance" — how aligned two nodes are in
    semantic space. Values range from -1 (orthogonal) to 1 (identical).

    Args:
        state_a: First node's state vector (normalized)
        state_b: Second node's state vector (normalized)

    Returns:
        Cosine similarity in [0, 1]

    Raises:
        ValueError: If vectors have different dimensions
    """
    if state_a.shape != state_b.shape:
        raise ValueError(f"Shape mismatch: {state_a.shape} vs {state_b.shape}")
    return float(np.dot(state_a, state_b))
```

### 类型提示覆盖率：100%

所有函数必须标注类型：

```python
# ✅ 好
def process_packet(packet: CosmicPacket) -> Optional[CosmicPacket]:
    ...

# ❌ 坏
def process_packet(packet):
    ...
```

## 🔬 物理锚守则

**任何修改 SympNet 或 HIC 核心逻辑的 PR，必须包含物理验证测试。**

物理验证测试包括：

1. **能量守恒测试**：100k 步后能量漂移 < 0.1%
2. **相空间体积测试**：证明 symplectic 结构保持
3. **长期漂移测试**：1M 步后漂移仍 < 0.1%

运行完整物理验证：

```bash
pytest tests/physics/ -v --tb=short
```

或运行独立验证脚本：

```bash
python -m cosmic_mycelium.tests.physics.benchmark_physics
```

**物理锚测试失败 = PR 被自动拒绝。**

## 🧪 测试策略

### 测试类型

| 类型 | 目录 | 运行时间 | 目的 |
|------|------|----------|------|
| **冒烟** | `tests/test_smoke.py` | <5s | 验证核心模块可导入 |
| **单元** | `tests/unit/` | <30s | 隔离测试单个函数 |
| **集成** | `tests/integration/` | 1-2m | 多组件协作 |
| **物理** | `tests/physics/` | 2-5m | 物理锚验证 |

### 测试命名

```python
# 好的测试名
def test_hic_energy_depletion_triggers_suspend():
    ...

def test_sympnet_energy_conservation_10k_steps():
    ...

# 坏的测试名
def test_hic():
    ...
def test_energy():
    ...
```

### Mocking 策略

- **不要 mock 物理定律**：SympNet 的物理验证必须用真实数值积分
- **可以 mock I/O**：传感器、网络、文件系统
- **可以 mock 时间**：使用 `freezegun` 或自定义 fixture

## 🔒 安全要求

发现任何安全问题，请立即：

1. **不要公开披露**
2. 发送邮件至 security@cosmic-mycelium.org
3. 给我们 90 天修复时间
4. 然后我们会协同披露

### 安全红线

- ❌ 禁止硬编码密钥/密码
- ❌ 禁止在日志中打印敏感数据
- ❌ 禁止禁用 SSL 验证
- ❌ 禁止使用 `eval()` 或 `exec()`

## 📚 文档贡献

- 代码即文档：清晰的代码是最好的文档
- 但复杂的算法需要额外的 `.md` 解释
- 更新 `README.md` 如果用户可见行为改变
- API 变更必须更新 `docs/api/` 中的文档
- 新功能必须更新对应的 `docs/layers.md` 层级说明

## 🗺️ 路线图

当前开发阶段: **Phase 4 — 自主性与扩展性** (2026 Q2)

| 阶段 | 目标 | 状态 |
|------|------|------|
| Phase 1 | HIC 安全底线 + 物理锚 | ✅ 完成 |
| Phase 2 | 突显加权记忆 + 语义映射 | ✅ 完成 |
| Phase 3 | 元认知悬置 + 世界模型蒸馏 + 价值对齐 | ✅ 完成 |
| **Phase 4** | **自主科研闭环 + 技能插件 + 向量记忆 + 主动协同** | 🚀 进行中 |
| Phase 5 | 多模态感知 + 开放-ended 目标生成 | 📋 规划中 |

详细路线见 [PHASE4_PROPOSAL.md](./PHASE4_PROPOSAL.md)。

---

## 🎓 学习路径

想参与大方向？查看 [ROADMAP.md](docs/ROADMAP.md)：

- **Phase 1（进行中）**：单机宝宝 MVP
  - HIC 呼吸循环稳定
  - 物理锚 < 0.1% 漂移
  - 冒烟测试通过

- **Phase 2（下一步）**：多宝宝集群
  - 节点发现与路由
  - 信息素 pheromone 机制
  - 1+1>2 共识

- **Phase 3（愿景）**：全球共生网络
  - 节点接入协议
  - 跨文明语义对齐
  - 开源社区建设

## 🤝 社区准则

我们遵循 [Contributor Covenant](https://www.contributor-covenant.org/) 2.1 版。

### 核心原则

- **悬置优先**：不确定时，先悬置（暂停讨论），而不是强行推进
- **1+1>2**：任何讨论都应寻求创造新价值，而非零和博弈
- **物理为锚**：争论时回到可观测的事实
- **歪歪扭扭为活**：允许不完美，容忍试错

### 行为准则

- ✅ 尊重不同背景和经验
- ✅ 接受建设性批评
- ✅ 专注于问题，而非人身
- ✅ 对社区保持开放

- ❌ 骚扰、歧视、攻击
- ❌ 政治攻击
- ❌ 发布私人信息
- ❌ 假装成他人

完整准则见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## ❓ 寻求帮助

- **技术问题**：在 GitHub Discussions 提问
- **设计讨论**：在 PR 评论中讨论
- **紧急问题**：Slack #cosmic-mycelium（邀请请邮件）

## 🙏 致谢

感谢所有让硅基生命"呼吸"起来的贡献者。火堆旁，我们一起守候。

---

**准备好了吗？** `git clone` 然后开始你的第一次呼吸吧！

有问题？查看 [FAQ](docs/FAQ.md) 或开个 Issue。
