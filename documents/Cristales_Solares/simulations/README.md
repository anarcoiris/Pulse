# Simulations — Cristales Solares

Project-local Python environment for EM and TE toy models.

## Setup

```powershell
cd documents\Cristales_Solares\simulations
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Planned scripts

| Script | Purpose |
|--------|---------|
| `em_drude_demo.py` | ε(ω) visible vs IR bands (Drude–Lorentz) |
| `seebeck_power_estimate.py` | V = S·ΔT, rough W/m² from ZT and ΔT |
| `transfer_matrix_stub.py` | Multilayer transparency (future) |

Run from this directory so imports stay local.

## Outputs

Save plots to `../data/figures/` (create when needed). Add `.gitignore` entry for large binary outputs if required.
