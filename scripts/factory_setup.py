#!/usr/bin/env python3
"""
Cosmic Mycelium — Factory Setup Script

Creates a fresh development environment for the project:
1. Creates Python virtual environment
2. Installs dependencies from pyproject.toml
3. Initializes git hooks (pre-commit)
4. Generates .env.example
5. Runs full test suite once to verify

Usage:
    python3 scripts/factory_setup.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()


def run(cmd: list[str], cwd: Path = PROJECT_ROOT, check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command, echo for visibility."""
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if check and result.returncode != 0:
        print(f"❌ Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(1)
    return result


def main():
    print("=" * 60)
    print("Cosmic Mycelium — Factory Setup")
    print("=" * 60)

    # 1. Virtual environment
    venv_path = PROJECT_ROOT / ".venv"
    if not venv_path.exists():
        print("\n[1/6] Creating Python virtual environment...")
        run([sys.executable, "-m", "venv", str(venv_path)])
        print("   ✓ Virtual environment created")
    else:
        print("\n[1/6] Virtual environment already exists — skipping")

    # 2. Install dependencies
    print("\n[2/6] Installing dependencies from pyproject.toml...")
    pip = venv_path / "bin" / "pip"
    run([str(pip), "install", "--upgrade", "pip"])
    run([str(pip), "install", "-e", "."])
    print("   ✓ Dependencies installed")

    # 3. Pre-commit hooks (optional)
    print("\n[3/6] Configuring git hooks...")
    hooks_dir = PROJECT_ROOT / ".git" / "hooks"
    pre_commit = hooks_dir / "pre-commit"
    if pre_commit.exists():
        pre_commit.unlink()
    # Simple pre-commit: run pytest on changed files
    pre_commit.write_text("""#!/usr/bin/env bash
# Pre-commit hook — run tests on staged Python files
set -e

# Get staged .py files
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
if [ -z "$STAGED" ]; then
    exit 0
fi

echo "Running tests on changed files..."
python3 -m pytest $STAGED -q || {
    echo "Tests failed — commit aborted."
    exit 1
}
""")
    pre_commit.chmod(0o755)
    print("   ✓ pre-commit hook installed")

    # 4. .env.example
    print("\n[4/6] Creating .env.example...")
    env_example = PROJECT_ROOT / ".env.example"
    env_example.write_text("""# Cosmic Mycelium Environment Configuration
# Copy to .env and adjust values as needed

# HIC Energy Management
HIC_ENERGY_MAX=100.0
HIC_CONTRACT_DURATION=0.055
HIC_DIFFUSE_DURATION=0.005
HIC_SUSPEND_DURATION=5.0
HIC_RECOVERY_ENERGY=60.0
HIC_RECOVERY_RATE=0.5

# SympNet Physics Anchor
SYMPNET_MASS=1.0
SYMPNET_SPRING_K=1.0
SYMPNET_DAMPING=0.0

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs

# Metrics
METRICS_PORT=8000
HEALTH_PORT=8001
""")
    print("   ✓ .env.example created")

    # 5. Logs directory
    print("\n[5/6] Creating logs directory...")
    (PROJECT_ROOT / "logs").mkdir(exist_ok=True)
    print("   ✓ logs/ ready")

    # 6. Verify — run test suite
    print("\n[6/6] Verifying installation — running test suite...")
    python = venv_path / "bin" / "python3"
    result = run([str(python), "-m", "pytest", "tests/", "-q", "--tb=line"], check=False)
    if result.returncode == 0:
        print("   ✓ All tests passed — installation verified")
    else:
        print("   ⚠ Some tests failed — review output above")

    print("\n" + "=" * 60)
    print("Factory setup complete!")
    print(f"\nNext steps:")
    print(f"  1. source {venv_path}/bin/activate")
    print(f"  2. cp .env.example .env  # edit as needed")
    print(f"  3. python3 -m cosmic_mycelium.infant.main")
    print("=" * 60)


if __name__ == "__main__":
    main()
