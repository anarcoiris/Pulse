# Glossary — Cristales Solares

> **Role:** reference  
> Symbols and terms used across manuscript, findings, and simulations.

## Electromagnetic

| Symbol | Name | Typical window target |
|--------|------|------------------------|
| ε′ | Real part of permittivity | Low in visible (≈ 1–4) |
| ε″ | Imaginary part of permittivity | ≪ 0.1 visible; 0.5–3 in IR |
| μ′, μ″ | Permeability components | ≈ 1 for most optical materials |
| σ | Conductivity | Low in visible; higher effective σ in IR via resonance |
| ω | Angular frequency | Band-dependent |

**Drude–Lorentz (link ε″ to σ):** ε″(ω) = σ(ω) / (ε₀ ω)

## Thermoelectric

| Symbol | Name | Notes |
|--------|------|-------|
| S | Seebeck coefficient | V = S · ΔT |
| ZT | Figure of merit | TE efficiency indicator |
| ΔT | Temperature gradient across film | Critical bottleneck in facades |
| κ | Thermal conductivity | Lower κ helps maintain ΔT |

## Materials (project shorthand)

| Abbrev | Material |
|--------|----------|
| ITO | Indium tin oxide (transparent conductor) |
| TE | Thermoelectric (generic) |
| TCO | Transparent conductive oxide |
| LSPR | Localized surface plasmon resonance |

## Architecture

| Term | Meaning |
|------|---------|
| Photonic crystal | Periodic structure with IR stop/pass bands |
| Metamaterial | Engineered sub-wavelength structure with tailored ε, μ |
| Narrow-band PV | PV layer transparent to part of spectrum; pairs with TE IR harvest |

## Performance (order-of-magnitude from review)

| Quantity | Literature ballpark |
|----------|---------------------|
| Visible transmission | > 80 % (WO₃ windows, thin Bi₂Te₃) |
| TE power density | 10–50 W/m² under concentrated / direct sun |
| ZT (nano composites) | 0.3–0.6 |

Always replace ballparks with cited values in `findings/` as literature pass completes.
