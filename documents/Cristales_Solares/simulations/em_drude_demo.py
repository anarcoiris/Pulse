"""
em_drude_demo.py — toy Drude model for visible vs IR permittivity bands.

Run from simulations/ with project venv active:
    python em_drude_demo.py

Outputs a plot to ../data/figures/drude_epsilon_demo.png (creates dirs if needed).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# Simplified Drude: eps = eps_inf - wp^2 / (w^2 + i*gamma*w)
EPS0 = 8.854e-12
C = 299792458.0


def wavelength_to_omega(nm: np.ndarray) -> np.ndarray:
    return 2 * np.pi * C / (nm * 1e-9)


def drude_epsilon(omega: np.ndarray, eps_inf: float, wp: float, gamma: float) -> np.ndarray:
    return eps_inf - wp**2 / (omega**2 + 1j * gamma * omega)


def main() -> None:
    nm = np.linspace(300, 3000, 600)
    omega = wavelength_to_omega(nm)

    # Illustrative parameters — replace with literature values in findings/
    eps_visible = drude_epsilon(omega, eps_inf=3.0, wp=1.0e14, gamma=1.0e13)
    eps_ir = drude_epsilon(omega, eps_inf=5.0, wp=5.0e13, gamma=2.0e13)

    fig, axes = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    axes[0].plot(nm, eps_visible.real, label="Re ε (visible-like)")
    axes[0].plot(nm, eps_ir.real, label="Re ε (IR-like)", linestyle="--")
    axes[0].axvspan(400, 700, alpha=0.15, color="green", label="Visible")
    axes[0].axvspan(700, 2500, alpha=0.1, color="red", label="NIR/SWIR")
    axes[0].set_ylabel("Re(ε)")
    axes[0].legend(loc="upper right", fontsize=8)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(nm, eps_visible.imag, label="Im ε (visible-like)")
    axes[1].plot(nm, eps_ir.imag, label="Im ε (IR-like)", linestyle="--")
    axes[1].axvspan(400, 700, alpha=0.15, color="green")
    axes[1].axvspan(700, 2500, alpha=0.1, color="red")
    axes[1].set_xlabel("Wavelength (nm)")
    axes[1].set_ylabel("Im(ε)")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].grid(True, alpha=0.3)

    fig.suptitle("Cristales Solares — toy Drude ε(λ) (illustrative parameters)")
    fig.tight_layout()

    out = Path(__file__).resolve().parent.parent / "data" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "drude_epsilon_demo.png"
    fig.savefig(path, dpi=150)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
