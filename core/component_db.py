"""
core/component_db.py
====================
Base de datos de componentes electrónicos para PulseLab Forge.

Carga definiciones JSON desde knowledge/data/components.json y expone
búsqueda por texto, categoría y parámetros numéricos.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field


# ─── Ruta de datos ────────────────────────────────────────────────────────────

_HERE    = Path(__file__).resolve().parent
_DATA    = _HERE.parent / "knowledge" / "data"
_COMP_F  = _DATA / "components.json"
_IPC_F   = _DATA / "ipc_2221.json"


# ─── Dataclass ───────────────────────────────────────────────────────────────

@dataclass
class Component:
    """Representación de un componente de la base de datos."""
    id:                str
    category:          str
    manufacturer:      str
    kicad_symbol:      str
    kicad_footprint:   str
    params:            dict = field(default_factory=dict)
    pins:              dict = field(default_factory=dict)
    support_circuits:  dict = field(default_factory=dict)
    notes:             str  = ""
    datasheet:         str  = ""
    family:            str  = ""
    subcategory:       str  = ""
    # raw dict for extra fields
    _raw:              dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Component":
        return cls(
            id               = d.get("id", ""),
            category         = d.get("category", ""),
            manufacturer     = d.get("manufacturer", ""),
            kicad_symbol     = d.get("kicad_symbol", ""),
            kicad_footprint  = d.get("kicad_footprint", ""),
            params           = d.get("params", {}),
            pins             = d.get("pins", {}),
            support_circuits = d.get("support_circuits", {}),
            notes            = d.get("notes", ""),
            datasheet        = d.get("datasheet", ""),
            family           = d.get("family", ""),
            subcategory      = d.get("subcategory", ""),
            _raw             = d,
        )

    def to_dict(self) -> dict:
        return self._raw

    def summary(self) -> str:
        p = self.params
        parts = [f"[{self.category}] {self.id} ({self.manufacturer})"]
        if p.get("max_freq_mhz"):
            parts.append(f"{p['max_freq_mhz']}MHz")
        if p.get("flash_kb"):
            parts.append(f"{p['flash_kb']}kB flash")
        if p.get("sram_kb"):
            parts.append(f"{p['sram_kb']}kB RAM")
        if p.get("vout_v"):
            parts.append(f"Vout={p['vout_v']}V")
        if self.notes:
            parts.append(f"→ {self.notes[:80]}")
        return " | ".join(parts)


# ─── ComponentDB ─────────────────────────────────────────────────────────────

class ComponentDB:
    """
    Base de datos cargada de un JSON.

    Uso::

        db = ComponentDB()
        results = db.search("ESP32 wifi", top_k=3)
        mcu = db.get("RP2040")
        mcus = db.by_category("MCU")
        matched = db.filter(uart__gte=3, adc_bits__gte=12)
    """

    def __init__(self, json_path: Optional[Path] = None):
        self._path = json_path or _COMP_F
        self._components: list[Component] = []
        self._ipc: dict = {}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._components = [Component.from_dict(d) for d in data]
        else:
            self._components = []

        if _IPC_F.exists():
            with open(_IPC_F, "r", encoding="utf-8") as f:
                self._ipc = json.load(f)

    def reload(self) -> None:
        """Recarga el JSON desde disco."""
        self._load()

    def all(self) -> list[Component]:
        return list(self._components)

    def get(self, comp_id: str) -> Optional[Component]:
        """Obtiene componente por ID exacto."""
        comp_id_lower = comp_id.lower()
        for c in self._components:
            if c.id.lower() == comp_id_lower:
                return c
        return None

    def by_category(self, category: str) -> list[Component]:
        """Filtra por categoría (MCU, PMIC, Amplifier, ...)."""
        cat = category.lower()
        return [c for c in self._components
                if c.category.lower() == cat or c.subcategory.lower() == cat]

    def search(self, query: str, top_k: int = 5,
               category: Optional[str] = None) -> list[dict]:
        """
        Búsqueda de texto simple en id, family, notes, params.

        Returns:
            Lista de dicts {component, score, summary}.
        """
        tokens = query.lower().split()
        results = []

        for c in self._components:
            if category and c.category.lower() != category.lower():
                continue

            # Texto busqueable
            text = " ".join([
                c.id.lower(), c.family.lower(), c.manufacturer.lower(),
                c.category.lower(), c.subcategory.lower(), c.notes.lower(),
                " ".join(str(v).lower() for v in c.params.values()),
                " ".join(str(k).lower() for k in c.params.keys()),
                " ".join(str(v).lower()
                         for pin in c.pins.values()
                         for v in (pin.get("alt", []) if isinstance(pin, dict) else [])),
            ])

            score = sum(1 for t in tokens if t in text)
            if score > 0:
                results.append({
                    "component": c.to_dict(),
                    "score": score,
                    "summary": c.summary(),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def filter(self, **kwargs) -> list[Component]:
        """
        Filtra por parámetros numéricos con sufijos __gte / __lte / __eq.

        Ejemplos::

            db.filter(uart__gte=3, adc_bits__gte=12, category__eq="MCU")
            db.filter(vcc_max_v__gte=5.0, iout_max_a__gte=2.0)
        """
        out = list(self._components)
        for key, val in kwargs.items():
            # Parse key__op
            if "__" in key:
                parts = key.rsplit("__", 1)
                param_name, op = parts[0], parts[1]
            else:
                param_name, op = key, "eq"

            filtered = []
            for c in out:
                # Check both category and params
                if param_name == "category":
                    cv = c.category
                elif param_name == "subcategory":
                    cv = c.subcategory
                else:
                    cv = c.params.get(param_name)

                if cv is None:
                    continue
                try:
                    cv_num = float(cv) if not isinstance(cv, bool) else int(cv)
                    val_num = float(val)
                    if op == "gte" and cv_num >= val_num:
                        filtered.append(c)
                    elif op == "lte" and cv_num <= val_num:
                        filtered.append(c)
                    elif op == "eq" and cv_num == val_num:
                        filtered.append(c)
                except (TypeError, ValueError):
                    # String comparison
                    if op == "eq" and str(cv).lower() == str(val).lower():
                        filtered.append(c)
            out = filtered

        return out

    # ── IPC-2221 helpers ──────────────────────────────────────────

    def ipc_clearance(self, voltage_v: float, layer: str = "internal",
                      coated: bool = True) -> dict:
        """
        Distancia mínima de aislamiento (clearance) según IPC-2221B.

        Args:
            voltage_v: Voltaje entre conductores (V).
            layer:     "internal", "external".
            coated:    True = revestido, False = al aire.

        Returns:
            dict con min_clearance_mm y referencia.
        """
        if layer == "internal":
            table = self._ipc.get("conductor_spacing_internal", {}).get("voltage_range", {})
        elif coated:
            table = self._ipc.get("conductor_spacing_external_coated", {}).get("voltage_range", {})
        else:
            table = self._ipc.get("conductor_spacing_external_uncoated", {}).get("voltage_range", {})

        clearance_mm = None
        for range_str, value in table.items():
            lo, hi = (float(x) for x in range_str.split("-"))
            if lo <= voltage_v <= hi:
                clearance_mm = value
                break
        if clearance_mm is None and table:
            # Si está fuera de rango, usar el mayor
            clearance_mm = max(table.values())

        return {
            "min_clearance_mm": clearance_mm,
            "voltage_v": voltage_v,
            "layer": layer,
            "coated": coated,
            "ref": "IPC-2221B Table 6-1",
        }

    def ipc_trace_width(self, current_a: float,
                        copper_oz: float = 1.0,
                        layer: str = "external") -> dict:
        """
        Devuelve el ancho de pista mínimo de IPC-2221B para la corriente dada.
        Usa la tabla directa para 1oz / 10°C (caso más común).
        Para otros valores usa la fórmula en rf_tools.trace_width_ipc2221().
        """
        key = "trace_width_external_1oz" if layer == "external" else "trace_width_internal_1oz"
        table = self._ipc.get(key, {}).get("current_a", {})

        # Interpolación lineal en tabla
        currents = sorted(float(k) for k in table.keys())
        widths   = [table[str(int(k)) if k == int(k) else str(k)] for k in currents]

        if current_a <= currents[0]:
            w = widths[0]
        elif current_a >= currents[-1]:
            w = widths[-1]
        else:
            for i in range(len(currents) - 1):
                if currents[i] <= current_a <= currents[i + 1]:
                    frac = (current_a - currents[i]) / (currents[i + 1] - currents[i])
                    w = widths[i] + frac * (widths[i + 1] - widths[i])
                    break
            else:
                w = widths[-1]

        return {
            "W_mm": round(w * (copper_oz ** 0.5), 4),
            "current_a": current_a,
            "copper_oz": copper_oz,
            "layer": layer,
            "temp_rise_c": 10,
            "ref": "IPC-2221B Chart 6-2",
        }

    def get_substrate(self, name: str = "FR4") -> dict:
        """Propiedades de substrato (εr, loss tangent, etc.)."""
        return self._ipc.get("common_substrates", {}).get(name, {})

    def list_substrates(self) -> list[str]:
        return list(self._ipc.get("common_substrates", {}).keys())


# ─── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db = ComponentDB()
    print(f"Cargados {len(db.all())} componentes\n")

    for c in db.search("ESP32 wifi"):
        print("-", c["summary"])

    print()
    mcus = db.by_category("MCU")
    print(f"MCUs en DB: {[c.id for c in mcus]}")

    print()
    three_uart = db.filter(uart__gte=3, category__eq="MCU")
    print(f"MCUs con ≥3 UART: {[c.id for c in three_uart]}")

    print()
    cl = db.ipc_clearance(48.0, layer="external", coated=False)
    print(f"Clearance para 48V externo no revestido: {cl['min_clearance_mm']} mm")

    print()
    tw = db.ipc_trace_width(2.0)
    print(f"Ancho pista para 2A externo 1oz: {tw['W_mm']} mm")

    print()
    fr4 = db.get_substrate("FR4")
    print(f"FR4: εr={fr4.get('er')}, tanδ={fr4.get('loss_tangent')}")
