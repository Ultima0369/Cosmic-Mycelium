#!/usr/bin/env python3
"""
THEIA Training Script — Four-Engine Physics Intuition Model

Generates synthetic harmonic-oscillator data and trains the full
four-engine THEIA architecture with:

  1. Cross-entropy loss (3-class: False / True / Unknown)
  2. Delayed-judgment auxiliary loss (adversarial linear probe)
  3. Gumbel-Softmax prototype assignment regularisation

Data labels:
  - 0 (False):    Energy-violating states
  - 1 (True):     Valid harmonic-oscillator states
  - 2 (Unknown):  Ambiguous / boundary states

Output: models/theia_physics.pt

Usage:
    python scripts/train_theia.py --epochs 100 --output models/theia_physics.pt
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

# Ensure the project root is on sys.path so cosmic_mycelium is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from cosmic_mycelium.common.theia_model import THEIA


# ═══════════════════════════════════════════════════════════════════
# Synthetic Data Generation — Harmonic Oscillator
# ═══════════════════════════════════════════════════════════════════

def generate_synthetic_data(
    n_samples: int = 5000,
    seed: int = 42,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Generate synthetic harmonic-oscillator states with three-class labels.

    Harmonic oscillator: H = p^2/(2m) + (1/2) k q^2
    With m=1, k=1:  E = (q^2 + p^2) / 2

    Labels:
        0 = False   (energy-violating / physically impossible)
        1 = True    (valid harmonic oscillator state)
        2 = Unknown (ambiguous / boundary state)

    Returns:
        a:      (N, 1) position q
        b:      (N, 1) momentum p
        a_unk:  (N, 1) bool -- always False for synthetic data
        b_unk:  (N, 1) bool -- always False for synthetic data
        labels: (N,)   int  -- 0=False, 1=True, 2=Unknown
    """
    rng = np.random.default_rng(seed)

    n_per_class = n_samples // 3
    remainder = n_samples - 3 * n_per_class

    a_list, b_list = [], []
    label_list = []

    # ── Class 1: Valid harmonic oscillator states ──
    # Sample points on constant-energy circles in phase space.
    # q = r*cos(theta), p = r*sin(theta)  ->  E = r^2/2 = const
    n1 = n_per_class + (remainder if remainder > 0 else 0)
    radii = rng.uniform(0.5, 2.5, size=n1)
    thetas = rng.uniform(0, 2 * math.pi, size=n1)
    valid_a = radii * np.cos(thetas)
    valid_b = radii * np.sin(thetas)
    # Add tiny noise to avoid perfect alignment
    valid_a += rng.normal(0, 0.02, size=n1)
    valid_b += rng.normal(0, 0.02, size=n1)

    a_list.append(valid_a)
    b_list.append(valid_b)
    label_list.append(np.ones(n1, dtype=np.int64))

    # ── Class 0: Energy-violating states ──
    # Uniform samples with energy filtered to be far from valid range
    invalid_a = rng.uniform(-3, 3, size=n_per_class)
    invalid_b = rng.uniform(-3, 3, size=n_per_class)
    energies_0 = (invalid_a**2 + invalid_b**2) / 2
    # Resample any that accidentally fall in the valid energy range
    for _ in range(10):
        in_range = (energies_0 >= 0.1) & (energies_0 <= 3.5)
        if not in_range.any():
            break
        n_rs = in_range.sum()
        invalid_a[in_range] = rng.uniform(-3, 3, size=n_rs)
        invalid_b[in_range] = rng.uniform(-3, 3, size=n_rs)
        energies_0 = (invalid_a**2 + invalid_b**2) / 2

    a_list.append(invalid_a)
    b_list.append(invalid_b)
    label_list.append(np.zeros(n_per_class, dtype=np.int64))

    # ── Class 2: Ambiguous / boundary states ──
    ambig_a = rng.uniform(-2.5, 2.5, size=n_per_class)
    ambig_b = rng.uniform(-2.5, 2.5, size=n_per_class)
    ambig_e = (ambig_a**2 + ambig_b**2) / 2
    # Keep states with energy in boundary zones
    for _ in range(10):
        in_ambig = (ambig_e >= 0.05) & (ambig_e <= 3.8)
        if in_ambig.all():
            break
        n_rs = (~in_ambig).sum()
        ambig_a[~in_ambig] = rng.uniform(-2.5, 2.5, size=n_rs)
        ambig_b[~in_ambig] = rng.uniform(-2.5, 2.5, size=n_rs)
        ambig_e = (ambig_a**2 + ambig_b**2) / 2

    a_list.append(ambig_a)
    b_list.append(ambig_b)
    label_list.append(np.full(n_per_class, 2, dtype=np.int64))

    # ── Concatenate and shuffle ──
    a_all = np.concatenate(a_list).reshape(-1, 1).astype(np.float32)
    b_all = np.concatenate(b_list).reshape(-1, 1).astype(np.float32)
    labels_all = np.concatenate(label_list).astype(np.int64)

    perm = rng.permutation(len(a_all))
    a_all = a_all[perm]
    b_all = b_all[perm]
    labels_all = labels_all[perm]

    # Unknown flags: 5% random for realism
    a_unk = (rng.random(len(a_all)) < 0.05).reshape(-1, 1)
    b_unk = (rng.random(len(b_all)) < 0.05).reshape(-1, 1)

    return (
        torch.from_numpy(a_all),
        torch.from_numpy(b_all),
        torch.from_numpy(a_unk),
        torch.from_numpy(b_unk),
        torch.from_numpy(labels_all).long(),
    )


# ═══════════════════════════════════════════════════════════════════
# Adversarial Linear Probe — Delayed Judgment Auxiliary Loss
# ═══════════════════════════════════════════════════════════════════

class AdversarialProbe(nn.Module):
    """
    Linear probe trained adversarially to enforce delayed judgment.

    The model is trained to MAXIMISE this probe's cross-entropy loss,
    meaning the hidden states should NOT contain linearly-decodable
    label information.  A probe accuracy < 40% indicates strong
    delayed judgment (random baseline = 33%).
    """

    def __init__(self, hidden_dim: int, num_classes: int = 3):
        super().__init__()
        self.linear = nn.Linear(hidden_dim, num_classes)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.linear(hidden)


# ═══════════════════════════════════════════════════════════════════
# Training Loop
# ═══════════════════════════════════════════════════════════════════

def train(
    model: THEIA,
    train_loader: DataLoader,
    val_loader: DataLoader,
    *,
    epochs: int = 80,
    lr: float = 1e-3,
    probe_lr: float = 1e-3,
    probe_weight: float = 2.0,
    gumbel_start_temp: float = 1.0,
    gumbel_end_temp: float = 0.5,
    device: torch.device = torch.device("cpu"),
    log_interval: int = 10,
) -> tuple[THEIA, dict]:
    """
    Train THEIA with multi-objective loss.

    Loss = CE(logits, labels)
           - probe_weight * CE(probe(hidden), labels)   [adversarial]
           + 0.1 * prototype_uniformity_loss             [regularisation]
    """
    model = model.to(device)

    optimiser = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)

    # Adversarial probe with its own optimiser
    probe = AdversarialProbe(model.hidden_dim, 3).to(device)
    probe_optimiser = torch.optim.Adam(probe.parameters(), lr=probe_lr)

    history: dict[str, list[float]] = {
        "train_loss": [], "train_acc": [], "val_acc": [], "probe_acc": [],
    }

    for epoch in range(epochs):
        model.train()
        probe.train()

        # Gumbel temperature annealing
        temp = gumbel_start_temp + (gumbel_end_temp - gumbel_start_temp) * (
            epoch / max(epochs - 1, 1)
        )

        total_loss = 0.0
        correct = 0
        total_samples = 0

        for a_batch, b_batch, a_unk_b, b_unk_b, labels_b in train_loader:
            a_batch = a_batch.to(device)
            b_batch = b_batch.to(device)
            a_unk_b = a_unk_b.to(device)
            b_unk_b = b_unk_b.to(device)
            labels_b = labels_b.to(device)

            # ── Forward pass ──
            logits, hidden, _engine_states = model(
                a_batch, b_batch, a_unk_b, b_unk_b,
                temperature=temp, hard=False,
            )

            # ── 1. Cross-entropy classification loss ──
            loss_ce = F.cross_entropy(logits, labels_b)

            # ── 2. Adversarial probe loss (delayed judgment) ──
            # Step A: update probe to predict labels from hidden (minimise CE)
            probe_logits_detached = probe(hidden.detach())
            probe_loss_real = F.cross_entropy(probe_logits_detached, labels_b)

            probe_optimiser.zero_grad()
            probe_loss_real.backward()
            probe_optimiser.step()

            # Step B: compute probe CE on hidden WITH gradients to model
            # Model maximises this -> makes probe fail
            probe_logits_adv = probe(hidden)
            loss_probe_adv = F.cross_entropy(probe_logits_adv, labels_b)

            # ── 3. Gumbel prototype uniformity regularisation ──
            with torch.no_grad():
                gumbel_probs = F.gumbel_softmax(
                    logits.detach(), tau=0.5, hard=False
                )
            avg_probs = gumbel_probs.mean(dim=0)
            target_uniform = torch.full_like(avg_probs, 1.0 / 3.0)
            loss_uniform = F.mse_loss(avg_probs, target_uniform)

            # ── Combined loss ──
            loss = loss_ce - probe_weight * loss_probe_adv + 0.1 * loss_uniform

            optimiser.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimiser.step()

            total_loss += loss.item()
            preds = logits.argmax(dim=-1)
            correct += (preds == labels_b).sum().item()
            total_samples += labels_b.size(0)

        scheduler.step()

        train_acc = correct / total_samples if total_samples > 0 else 0.0
        avg_loss = total_loss / len(train_loader) if len(train_loader) > 0 else 0.0

        # ── Validation ──
        val_acc, probe_acc = evaluate(model, probe, val_loader, device)

        history["train_loss"].append(avg_loss)
        history["train_acc"].append(train_acc)
        history["val_acc"].append(val_acc)
        history["probe_acc"].append(probe_acc)

        if (epoch + 1) % log_interval == 0 or epoch == 0:
            print(
                f"Epoch {epoch+1:3d}/{epochs} | "
                f"Loss: {avg_loss:.4f} | "
                f"Train Acc: {train_acc:.3f} | "
                f"Val Acc: {val_acc:.3f} | "
                f"Probe Acc: {probe_acc:.3f} | "
                f"Temp: {temp:.3f}"
            )

    return model, history


def evaluate(
    model: THEIA,
    probe: AdversarialProbe,
    loader: DataLoader,
    device: torch.device,
) -> tuple[float, float]:
    """Evaluate classification accuracy and probe accuracy."""
    model.eval()
    probe.eval()

    correct = 0
    total = 0
    probe_correct = 0

    with torch.no_grad():
        for a_batch, b_batch, a_unk_b, b_unk_b, labels_b in loader:
            a_batch = a_batch.to(device)
            b_batch = b_batch.to(device)
            a_unk_b = a_unk_b.to(device)
            b_unk_b = b_unk_b.to(device)
            labels_b = labels_b.to(device)

            logits, hidden, _engine_states = model(
                a_batch, b_batch, a_unk_b, b_unk_b
            )

            preds = logits.argmax(dim=-1)
            correct += (preds == labels_b).sum().item()
            total += labels_b.size(0)

            probe_logits = probe(hidden)
            probe_preds = probe_logits.argmax(dim=-1)
            probe_correct += (probe_preds == labels_b).sum().item()

    acc = correct / total if total > 0 else 0.0
    probe_acc = probe_correct / total if total > 0 else 0.0
    return acc, probe_acc


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train THEIA four-engine physics intuition model"
    )
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--hidden-dim", type=int, default=128, help="Hidden dimension")
    parser.add_argument("--n-samples", type=int, default=6000,
                        help="Synthetic training samples")
    parser.add_argument("--n-val", type=int, default=1200,
                        help="Synthetic validation samples")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--probe-weight", type=float, default=2.0,
                        help="Delayed judgment regularisation strength")
    parser.add_argument("--output", type=str, default="models/theia_physics.pt",
                        help="Output checkpoint path")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Hidden dim: {args.hidden_dim}, Epochs: {args.epochs}")

    # ── Generate data ──
    print(f"\nGenerating synthetic harmonic-oscillator data...")
    a_train, b_train, a_unk_tr, b_unk_tr, labels_train = generate_synthetic_data(
        args.n_samples, args.seed
    )
    a_val, b_val, a_unk_vl, b_unk_vl, labels_val = generate_synthetic_data(
        args.n_val, args.seed + 100
    )

    for name, labels in [("Train", labels_train), ("Val", labels_val)]:
        unique, counts = torch.unique(labels, return_counts=True)
        dist = dict(zip(unique.tolist(), counts.tolist()))
        print(f"  {name}: {dist}  (0=False, 1=True, 2=Unknown)")

    # ── Create DataLoaders ──
    train_dataset = TensorDataset(
        a_train, b_train, a_unk_tr, b_unk_tr, labels_train,
    )
    val_dataset = TensorDataset(
        a_val, b_val, a_unk_vl, b_unk_vl, labels_val,
    )

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False
    )

    # ── Initialise model ──
    print(f"\nInitialising THEIA with hidden_dim={args.hidden_dim}...")
    model = THEIA(hidden_dim=args.hidden_dim)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {num_params:,}")

    # ── Train ──
    print(f"\nTraining for {args.epochs} epochs...")
    model, history = train(
        model,
        train_loader,
        val_loader,
        epochs=args.epochs,
        lr=args.lr,
        probe_weight=args.probe_weight,
        gumbel_start_temp=1.0,
        gumbel_end_temp=0.5,
        device=device,
        log_interval=10,
    )

    # ── Final evaluation ──
    # Retrain probe to convergence on final hidden states for a clean measurement
    probe = AdversarialProbe(args.hidden_dim, 3).to(device)
    model.eval()
    all_hidden, all_labels_l = [], []
    with torch.no_grad():
        for a_b, b_b, a_u, b_u, lbl in val_loader:
            a_b = a_b.to(device); b_b = b_b.to(device)
            a_u = a_u.to(device); b_u = b_u.to(device)
            _logits, hidden, _es = model(a_b, b_b, a_u, b_u)
            all_hidden.append(hidden.cpu())
            all_labels_l.append(lbl)

    all_hidden_t = torch.cat(all_hidden, dim=0)
    all_labels_t = torch.cat(all_labels_l, dim=0)

    probe_opt = torch.optim.Adam(probe.parameters(), lr=1e-3)
    for _ in range(200):
        probe_opt.zero_grad()
        pl = F.cross_entropy(
            probe(all_hidden_t.to(device)), all_labels_t.to(device)
        )
        pl.backward()
        probe_opt.step()

    probe.eval()
    with torch.no_grad():
        final_probe_logits = probe(all_hidden_t.to(device))
        final_probe_acc = (
            (final_probe_logits.argmax(dim=-1).cpu() == all_labels_t)
            .float().mean().item()
        )

    final_val_acc = history["val_acc"][-1]

    # ── Print results ──
    print(f"\n{'='*60}")
    print(f"  THEIA Training Complete")
    print(f"{'='*60}")
    print(f"  Final Validation Accuracy:  {final_val_acc:.4f}  "
          f"({final_val_acc*100:.1f}%)")
    print(f"  Final Probe Accuracy:       {final_probe_acc:.4f}  "
          f"({final_probe_acc*100:.1f}%)")
    print(f"  Delayed Judgment Status:    ", end="")
    if final_probe_acc < 0.40:
        print("STRONG (probe < 40%)")
    elif final_probe_acc < 0.50:
        print("MODERATE (probe 40-50%)")
    else:
        print("WEAK (probe > 50%) -- consider increasing --probe-weight")
    print(f"{'='*60}")

    # ── Save checkpoint ──
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)
    print(f"\nCheckpoint saved to: {output_path}")

    # ── Quick sanity check: load and infer ──
    print("\nSanity check: loading from checkpoint...")
    loaded = THEIA.load_from_checkpoint(str(output_path), device=device)
    loaded.eval()
    with torch.no_grad():
        test_a = torch.tensor([[1.0]], dtype=torch.float32).to(device)
        test_b = torch.tensor([[0.5]], dtype=torch.float32).to(device)
        test_au = torch.tensor([[False]], dtype=torch.bool).to(device)
        test_bu = torch.tensor([[False]], dtype=torch.bool).to(device)
        test_logits, _h, _es = loaded(test_a, test_b, test_au, test_bu)
        test_probs = F.softmax(test_logits, dim=-1)
        print(f"  Input (a=1.0, b=0.5) -> probs: {test_probs.cpu().numpy()[0]}")
        print(f"  Verdict: {test_logits.argmax(dim=-1).item()}  "
              f"(0=False, 1=True, 2=Unknown)")
    print("  OK -- model loads and runs correctly.")


if __name__ == "__main__":
    main()
