"""
bridge/bom_generator.py
=======================
Generación de BOM enriquecida.
Combina CircuitGraph + ComponentDB para añadir info de fabricante,
footprint KiCad real y disponibilidad básica.
"""

from __future__ import annotations
import csv
import io
import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.circuit_graph import CircuitGraph
    from core.component_db import ComponentDB


def generate_bom(graph: "CircuitGraph",
                 db: Optional["ComponentDB"] = None,
                 fmt: str = "csv") -> dict:
    """
    Genera BOM completo.

    Args:
        graph: CircuitGraph con los componentes del diseño.
        db:    ComponentDB para enriquecer con info de fabricante/footprint.
        fmt:   "csv", "json", o "text".

    Returns:
        dict con "content" (string) y "rows" (lista de dicts).
    """
    # Asignar referencias
    counters: dict[str, int] = {}
    rows = []

    for c in graph.components:
        if c.etype == "GND":
            continue
        counters[c.etype] = counters.get(c.etype, 0) + 1
        ref = f"{c.etype}{counters[c.etype]}"

        # Buscar en DB si disponible
        db_match = None
        if db:
            results = db.search(c.label, top_k=1, category=None)
            if results:
                db_match = results[0]["component"]

        def _fmt_val(etype, val):
            units = {"R": "Ω", "C": "F", "L": "H", "V": "V"}
            u = units.get(etype, "")
            return f"{val:.4g}{u}"

        row = {
            "ref":           ref,
            "uid":           c.uid,
            "type":          c.etype,
            "value":         _fmt_val(c.etype, c.value),
            "label":         c.label,
            "footprint":     db_match.get("kicad_footprint", "") if db_match else "",
            "kicad_symbol":  db_match.get("kicad_symbol", "") if db_match else "",
            "manufacturer":  db_match.get("manufacturer", "") if db_match else "",
            "n1":            c.n1,
            "n2":            c.n2,
            "notes":         db_match.get("notes", "") if db_match else "",
        }
        rows.append(row)

    # Formatear salida
    if fmt == "json":
        content = json.dumps(rows, indent=2, ensure_ascii=False)
    elif fmt == "text":
        lines = ["Bill of Materials", "=" * 60]
        for r in rows:
            lines.append(f"  {r['ref']:6s} {r['value']:12s} {r['label']}")
        content = "\n".join(lines)
    else:  # csv (default)
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        content = buf.getvalue()

    return {
        "content": content,
        "rows": rows,
        "count": len(rows),
        "format": fmt,
    }
