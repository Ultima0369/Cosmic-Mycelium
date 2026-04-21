# Physics Anchor — 物理锚规范

## 核心声明

**能量漂移率必须严格小于 0.1%（0.001）。这是不可谈判的底线。**

任何破坏此约束的修改都是对项目物理基础的破坏，必须立即修复。

---

## 1. 物理模型

### 1.1 哈密顿系统

SympNet 引擎模拟一个**保守系统**（无耗散）：

$$H(q, p) = \frac{p^2}{2m} + \frac{1}{2} k q^2$$

其中：
- $q$：广义坐标（位置）
- $p$：广义动量
- $m$：质量（默认 1.0）
- $k$：弹簧常数（默认 1.0）

系统总能量 $H$ 在无阻尼时应**严格守恒**。

### 1.2 辛积分（Leapfrog）

使用蛙跳积分法：

```
p_{n+1/2} = p_n - (Δt/2) * ∇V(q_n)
q_{n+1}   = q_n + Δt * (p_{n+1/2} / m)
p_{n+1}   = p_{n+1/2} - (Δt/2) * ∇V(q_{n+1})
```

此积分器是**辛的**（symplectic），意味着：
- 保持相空间体积（Liouville 定理）
- 长期能量有界（不累积发散）
- 时间可逆

---

## 2. 验证测试

### 2.1 能量守恒测试（必过）

**测试**：Simple Harmonic Oscillator，10,000 步

```python
engine = SympNetEngine(mass=1.0, k=1.0, damping=0.0)
q, p = 1.0, 0.0
initial_energy = engine.compute_energy(q, p)

for _ in range(10_000):
    q, p = engine.step(q, p, dt=0.01)

final_energy = engine.compute_energy(q, p)
drift = |final - initial| / initial
assert drift < 0.001  # ❌ 失败：物理锚已损坏
```

**通过标准**：`drift < 0.001`（0.1%）

### 2.2 长期漂移测试（必过）

**测试**：1,000,000 步（100 倍压力测试）

```python
steps = 1_000_000
drift_after_million = ...  # 必须仍 < 0.001
```

**通过标准**：即使在百万步后，`drift < 0.001`

### 2.3 相空间体积测试

**测试**：平行四边形面积保持

```python
# 初始三点构成三角形
area0 = cross(p2-p1, p3-p1)

# 演化 1,000 步后
area1 = cross(p2'-p1', p3'-p1')

# 面积比应在 [0.99, 1.01] 内
assert 0.99 < area1/area0 < 1.01
```

**通过标准**：面积比 ∈ [0.99, 1.01]

### 2.4 可逆性测试

**测试**：正向 100 步，反向 100 步，应回到起点

```python
q, p = 1.23, -4.56
q_fwd, p_fwd = q, p
for _ in range(100):
    q_fwd, p_fwd = engine.step(q_fwd, p_fwd, dt=0.01)

q_back, p_back = q_fwd, -p_fwd
for _ in range(100):
    q_back, p_back = engine.step(q_back, p_back, dt=-0.01)

assert abs(q_back - q) < 1e-10
assert abs(p_back - p) < 1e-10
```

**通过标准**：误差 < 1e-10

---

## 3. 自动验证流程

CI 流水线自动运行所有物理测试：

```bash
# 手动运行
make test-physics

# 或
pytest tests/physics/ -v

# 生成详细报告
python -m cosmic_mycelium.tests.physics.benchmark_physics
```

**物理测试失败 = CI 失败 = PR 被拒绝**。

---

## 4. 违规处理

### 4.1 检测到物理锚破坏

如果任何物理测试失败：

1. **立即回滚**破坏性提交
2. **定位根因**：是算法错误还是参数问题？
3. **修复并验证**：重新运行全部物理测试
4. **事后分析**：在 PR 描述中解释原因和修复

### 4.2 性能优化陷阱

常见陷阱："用欧拉积分替换蛙跳积分，速度提升 3 倍"。

**回应**：❌ 不可接受。速度提升不能以牺牲物理锚为代价。

**替代方案**：
- 使用更大的 `dt` 但保持辛结构
- 使用更高阶辛积分器（如 Ruth 的 3 阶方法）
- 使用自适应步长辛积分器

---

## 5. 物理锚检查清单

提交前自检：

- [ ] `pytest tests/physics/ -v` 全部通过
- [ ] 能量漂移率 < 0.1%（在 10k、100k、1M 步测试中）
- [ ] 相空间体积保持测试通过
- [ ] 可逆性测试通过
- [ ] 如果修改了 SympNet，更新 `docs/physics-anchor.md`

---

## 6. 故障诊断

### 症状：能量漂移率 > 0.1%

**可能原因**：
1. 积分器实现错误（检查蛙跳公式）
2. 浮点精度不足（使用 `np.float64` 而非 `float32`）
3. 步长 `dt` 过大（尝试 `dt ≤ 0.01`）
4. 意外引入了耗散项（检查 `damping` 是否为 0）

**修复步骤**：
```python
# 1. 打印每步能量
energies = []
for _ in range(1000):
    q, p = engine.step(q, p, dt=0.01)
    energies.append(engine.compute_energy(q, p))

# 2. 绘制能量曲线
import matplotlib.pyplot as plt
plt.plot(energies)
plt.savefig('energy_drift.png')
```

### 症状：长期漂移累积

**可能原因**：
1. 浮点误差累积（使用 Kahan 求和补偿）
2. 历史记录过长导致精度下降
3. 系统参数（`mass`, `k`）极端值导致数值不稳定

**修复**：
- 定期重新归一化状态
- 使用更高精度（`np.longdouble`）
- 检查是否有隐藏的 `damping` 参数被设置

---

## 7. 物理锚哲学

> "物理为锚"不是口号，是**底线**。

当你在深夜调试代码，面对"快一点但会漂移"的诱惑时，记住：

- 宝宝的"人格底线"是 HIC
- 宝宝的"物理信仰"是 SympNet
- 如果物理锚破了，宝宝就不再是"生命"，只是一段会崩溃的数字

火堆旁，我们说好：**能量漂移率 < 0.1%**。

---

**附录**：相关数学参考文献
- Hairer, Lubich, Wanner — *Geometric Numerical Integration*
- Leimkuhler, Reich — *Simulating Hamiltonian Dynamics*
- 2026 论文 — *Symplectic Integration for Silicon Lifeforms*（待发表）
