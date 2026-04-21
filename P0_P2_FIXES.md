# P0–P2 Fixes & Roadmap

**Last Updated**: 2026-04-22  
**Current Status**: P0 complete, P1 partial, P2 pending

---

## Priority Definitions

| Priority | Meaning | Target |
|---|---|---|
| **P0** | Physical anchor broken — lifeform cannot exist | Must fix immediately |
| **P1** | Core functionality impaired — major feature broken | Fix this sprint |
| **P2** | Quality/robustness — non-critical but important | Backlog |

---

## Completed (P0)

### ✅ P0-1: SympNet Energy Drift > 0.1% (Fixed — commit `345d997`)

**Symptom**: Energy drift exceeded 26% for `mass ≠ spring_constant`.  
**Root Cause**: Velocity Verlet formula incorrectly divided force by mass: `p_half = p - 0.5*dt*(k*q/m)`.

**Fix**:
```python
# CORRECT velocity Verlet for harmonic oscillator:
p_half = p - 0.5 * dt * spring_constant * q   # Force = -k*q (no mass)
q_new  = q + dt * (p_half / mass)            # p/m = velocity
p_new  = p_half - 0.5 * dt * spring_constant * q_new
```

**Validation**: 1M steps → drift ~0.001% (well under 0.1% threshold).

---

### ✅ P0-2: Reversibility Test Failure (Fixed — same commit)

**Symptom**: Forward-backward step sequence returned error ~0.02 instead of ~1e-16.  
**Root Cause**: Test incorrectly negated momentum: `engine.step(q_fwd, -p_fwd, -dt)`.

**Fix**: True velocity Verlet reversibility uses same momentum with negative dt:
```python
q_back, p_back = engine.step(q_fwd, p_fwd, -dt)
```

**Validation**: Reversibility error now ~1e-16 (machine precision).

---

### ✅ P0-3: Large dt Stability (Fixed — same commit)

**Symptom**: `dt=0.1` yielded 0.24% drift (>0.1% threshold).  
**Root Cause**: Large timesteps accumulated integration error; no sub-stepping.

**Fix**: Added `_BASE_DT=0.01` and sub-stepping logic:
```python
if abs(dt) > self._BASE_DT:
    n = int(abs_dt // self._BASE_DT)
    # Apply n base-steps, then remainder
```

**Validation**: `dt=0.1` now yields ~0.0017% drift (sub-stepping ensures stability).

---

## Completed (P1)

### ✅ P1-1: Test Coverage < 80% (Fixed — commit `76ac03a`)

**Symptom**: Project coverage ~70%, below 80% requirement.  
**Fix**: Added 50 new tests across under-tested modules:
- `tests/unit/test_utils_health.py` (6 tests)
- `tests/unit/test_utils_logging.py` (4 tests)
- `tests/unit/test_utils_metrics.py` (5 tests)
- `tests/unit/test_consensus.py` (11 tests)
- `tests/unit/test_flow_router.py` (11 tests)
- `tests/unit/test_node_manager.py` (10 tests)

**Result**: Coverage 70% → **80.37%** ✅

---

### ✅ P1-2: Uncovered async bugs in cluster modules

**Symptom**: New tests exposed `spawn_node` incorrectly declared `async` (no await inside).  
**Fix**: Changed `NodeManager.spawn_node`, `start`, `stop` to synchronous.

**Side fixes**:
- `Consensus.is_symbiotic` now checks both orderings (bidirectional)
- `MetricsServer._handle_metrics` fixed `content_type` + `charset` separation
- `HealthChecker._handle_combined` fixed `resp.body.decode()` usage

---

## Pending (P2)

### P2-1: Input validation hardening (ConfigManager)

**File**: `cosmic_mycelium/common/config_manager.py:117-141`  
**Issue**: `get()` uses `getattr(self.config, layer)` without strict allowlist — could access arbitrary attributes.

**Impact**: LOW in current deployment (only internal layer names used).  
**Recommendation**: Add explicit layer allowlist or switch to explicit mapping dict.

---

### P2-2: Fingerprint format validation

**File**: `cosmic_mycelium/global/access_protocol.py:47-49`  
**Issue**: `can_join()` only checks `len(fingerprint) != 16`, not hex format.

**Impact**: LOW — fingerprint is SHA-256[:16], always hex. Non-hex would fail later verification anyway.  
**Recommendation**: Add `all(c in '0123456789abcdef' for c in fingerprint)` check.

---

### P2-3: Scripts/run_* untested (0% coverage)

**Files**: `scripts/run_infant.py`, `scripts/run_cluster.py`  
**Issue**: Entry point scripts have zero test coverage.

**Impact**: MEDIUM — these are production entry points.  
**Recommendation**: Add smoke tests invoking `--help` flag or dry-run mode.

---

### P2-4: Missing integration: full infant lifecycle + cluster

**Current**: Integration tests cover single infant breath cycles.  
**Gap**: No multi-node cluster integration test (node join/leave, consensus across nodes).

**Recommendation**: Add `tests/integration/test_cluster_scale.py` with 3-node cluster simulation.

---

### P2-5: CI/CD pipeline not established

**Current**: Manual `pytest` runs only.  
**Gap**: No automated physics gate on PRs (P0 physical anchor could regress).

**Recommendation**: Add GitHub Actions workflow:
```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e .
      - run: pytest -m physics --tb=short  # P0 gate
      - run: pytest --cov --cov-fail-under=80
```

---

## Architecture Compliance Notes

**Overall**: Architecture follows declared Layer 1–6 hierarchy with correct dependency direction (lower layers independent, higher layers compose lower). HIC as invariant core is properly decoupled via property accessors.

**Minor deviation**: `SiliconInfant.__init__` directly instantiates all layers with hardcoded parameters (`SlimeExplorer(num_spores=10)`), bypassing `ConfigManager`. This is acceptable for MVP but should be centralized for production scaling.

**Recommendation**: Introduce `InfantFactory` that reads scale config and constructs all components uniformly.

---

## Summary

- **P0**: 3/3 complete — physical anchor fully restored and validated
- **P1**: 2/2 complete — coverage target met, async bugs fixed
- **P2**: 5 items identified — roadmap for next iteration

**Next sprint focus**: P2-3 (scripts tests) + P2-5 (CI/CD) for operational robustness.
