"""
knowledge/validate_complex_apps.py
===================================
Suite de validación — each run writes to a timestamped folder (never overwrites prior runs).
All LLM I/O logged under knowledge/data/llm_sessions/sessions/{session_id}/.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from knowledge.circuit_synthesizer import CircuitSynthesizer
from knowledge.llm_backends import list_backends
from knowledge.llm_session_log import new_session_id
from knowledge.semantic_reviewer import SemanticReviewer, generate_markdown_report
from knowledge.circuit_agent import CircuitStewardAgent

OUT_DIR = Path("knowledge/data/validation_complex")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _safe_print(msg: str) -> None:
    """Console output safe on Windows cp1252 (Session 4b harness)."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)

TEST_CASES = [
    {
        "name": "esp32_sensors",
        "description": "ESP32 Devboard + Sensores",
        "prompt": (
            "Diseña un circuito basado en un microcontrolador ESP32. "
            "Conecta una pantalla OLED SSD1306 al bus I2C (pines SDA, SCL). "
            "Conecta también un sensor ambiental BME280 al mismo bus I2C. "
            "Asegúrate de incluir resistencias pull-up en las líneas I2C y "
            "condensadores de desacoplo para la alimentación del ESP32."
        ),
    },
    {
        "name": "pulselab_zero",
        "description": "Proyecto Final: PulseLab Zero (Clon Flipper Zero)",
        "prompt": (
            "Diseña un dispositivo estilo Flipper Zero llamado PulseLab Zero. "
            "Debe tener un microcontrolador ESP32-S3 como núcleo, "
            "una pantalla OLED SSD1306 por I2C, un módulo NFC PN532 por SPI, "
            "un transceptor sub-GHz CC1101 por SPI, "
            "un D-Pad de 5 botones direccionales conectados a GPIOs con resistencias pull-up, "
            "y un conector de expansión de 8 pines (GPIOs libres, 3.3V y GND). "
            "Incluye condensadores de desacoplo para el ESP32."
        ),
    },
]


_SYMBOLS_INDEX_LOOKUP = None


def _load_symbols_index_lookup() -> dict:
    """Carga (una sola vez por proceso) `knowledge/data/symbols_index.json`
    (generado por `python -m knowledge.build_symbol_index` desde una
    instalación real de KiCad, ver docs/calibration_forge/kicad_symbol_kb.md)
    y arma un lookup por nombre de parte normalizado -> {"pins", "lib_id",
    "library"}. Devuelve `{}` sin error si el archivo aún no existe (ej. no se
    ha corrido `build_symbol_index` en esta máquina) — es un fallback, no una
    dependencia dura."""
    global _SYMBOLS_INDEX_LOOKUP
    if _SYMBOLS_INDEX_LOOKUP is not None:
        return _SYMBOLS_INDEX_LOOKUP
    from knowledge.rag_engine import normalize_part_name
    index_file = _ROOT / "knowledge" / "data" / "symbols_index.json"
    lookup: dict = {}
    if index_file.exists():
        try:
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)
            for sym in data.get("symbols", []) or []:
                lib_id = sym.get("lib_id")
                pins = sym.get("pins") or {}
                if lib_id and pins:
                    lookup[normalize_part_name(lib_id)] = {
                        "pins": pins, "lib_id": lib_id, "library": sym.get("library", ""),
                    }
        except (json.JSONDecodeError, OSError):
            pass
    _SYMBOLS_INDEX_LOOKUP = lookup
    return lookup


def _pin_coverage(components: list, pinouts_db: dict) -> dict:
    """Pin Coverage Fidelity metric (see docs/calibration_forge/evaluation_metrics.md).

    For each generated IC/MCU component whose `value` matches a known part, measures
    what fraction of that part's physical pins the generated circuit accounts for:

        coverage = len(component["pins"]) / len(reference_pins[value])

    A pin counts toward coverage whether it's wired to a real net OR explicitly declared
    floating (the "NC"/"unconnected_pins" convention normalizes to unique "NC_<label>_<pin>"
    entries in `pins` before this runs — see circuit_synthesizer._normalize_unconnected_pins).
    Only a pin that's missing from the dict entirely fails to count, since that's exactly
    the "silently dropped" failure mode this metric exists to catch.

    Reference pin tables are resolved in two steps (Sesión 4a):
      1. `knowledge/pinouts_library.json` (curated, `pinouts_db`) — checked first so
         hand-curated enrichments (uart_programming notes, etc.) keep taking priority.
      2. `knowledge/data/symbols_index.json` (real KiCad symbol library, matched by
         normalized name) — fallback for parts never hand-curated, e.g. regulators,
         USB bridges, motor drivers. Matching is by exact normalized lib_id, NOT semantic
         RAG search — a real name drift (ej. "NE555" vs "NE555P", "A4988_StepperMotorDriver"
         vs "Pololu_Breakout_A4988", documented in kicad_symbol_kb.md) will still land in
         "unmatched" here even though the RAG-based prompt injection (`_match_pinouts`)
         would have found it semantically. This is a known, explicitly accepted gap for
         this metric (exact-match validation is intentionally stricter than prompt
         retrieval) rather than a bug to fix in this session.

    Components whose `value` has no entry in either source are reported separately under
    "unmatched" rather than silently skipped or counted as 0/0 — there's no reference to
    compare against, which is itself worth surfacing (see pin_model_coverage.md §5).
    """
    from knowledge.rag_engine import normalize_part_name
    symbols_index = _load_symbols_index_lookup()

    per_component = []
    unmatched = []
    ratios = []
    for comp in components:
        if comp.get("etype") not in ("IC", "MCU"):
            continue
        value = str(comp.get("value", ""))
        known = pinouts_db.get(value)
        known_pins = (known or {}).get("pins") or {}
        source = "pinouts_library" if known_pins else None
        if not known_pins:
            sym = symbols_index.get(normalize_part_name(value))
            if sym:
                known_pins = sym["pins"]
                source = f"kicad_symbols_index:{sym['library']}"
        if not known_pins:
            unmatched.append({"label": comp.get("label"), "value": value})
            continue
        total = len(known_pins)
        generated = len(comp.get("pins") or {})
        ratio = generated / total
        per_component.append(
            {
                "label": comp.get("label"),
                "value": value,
                "generated_pins": generated,
                "total_pins": total,
                "coverage": round(ratio, 4),
                "source": source,
            }
        )
        ratios.append(ratio)
    return {
        "per_component": per_component,
        "unmatched": unmatched,
        "average_coverage": round(sum(ratios) / len(ratios), 4) if ratios else None,
    }


def _semantic_review_summary(review_result: dict) -> dict:
    """Normalize SemanticReviewer output for run manifests (Session 4b)."""
    if "error" in review_result:
        return {"error": review_result["error"], "issue_count": None, "critical_count": None, "issues": []}
    issues = review_result.get("issues") or []
    critical = sum(1 for i in issues if i.get("severity") == "critical")
    return {
        "issue_count": len(issues),
        "critical_count": critical,
        "issues": issues,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="PulseLab complex circuit validation")
    parser.add_argument("--case", help="Run single test by name (e.g. esp32_sensors)")
    parser.add_argument("--backend", default="auto", help="LLM backend for synthesis: auto|primary|atomic")
    parser.add_argument(
        "--review-backend",
        default="auto",
        help="LLM backend for semantic review: auto|primary|atomic (default: auto -> llm.routing.review_backend, Session 4d)",
    )
    parser.add_argument("--variant", choices=("a", "b"), default="a", help="A/B variant: a=rules+rag_top_k=1, b=trimmed rules+richer RAG")
    parser.add_argument("--session", help="Reuse session id (default: new run session)")
    parser.add_argument("--base-circuit", help="Path to a base circuit JSON file to build upon (Follow-up)")
    parser.add_argument("--follow-up-prompt", help="A prompt providing instructions for modifications on the base circuit")
    args = parser.parse_args()

    run_session = args.session or new_session_id("validate")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = OUT_DIR / "runs" / f"{ts}_{run_session}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("Iniciando Suite de Validacion de Aplicaciones Complejas")
    print(f"Run session: {run_session}")
    print(f"Run dir:     {run_dir}")

    backends = list_backends()
    primary = backends.get("primary", {})
    if not primary.get("available") and not backends.get("atomic", {}).get("available"):
        print("ERROR: No LLM backend available.")
        print(json.dumps(backends, indent=2))
        return

    print(f"OK: Backends: primary={primary.get('available')} atomic={backends.get('atomic', {}).get('available')}")
    print(f"Variant: {args.variant}")
    synth = CircuitSynthesizer(backend=args.backend, ab_variant=args.variant)
    reviewer = SemanticReviewer(backend=args.review_backend)
    print(f"Review backend: {reviewer.backend_name}")

    cases = TEST_CASES
    if args.case:
        cases = [c for c in TEST_CASES if c["name"] == args.case]
        if not cases:
            print(f"ERROR: Unknown case '{args.case}'")
            return

    run_manifest = {
        "run_session": run_session,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "backend_pref": args.backend,
        "review_backend_pref": args.review_backend,
        "review_backend_resolved": reviewer.backend_name,
        "ab_variant": args.variant,
        "backends": backends,
        "results": [],
    }

    base_circuit_data = None
    if args.base_circuit:
        try:
            with open(args.base_circuit, "r", encoding="utf-8") as f:
                base_circuit_data = json.load(f)
        except Exception as e:
            print(f"ERROR al cargar base-circuit: {e}")
            return

    for case in cases:
        name = case["name"]
        print(f"\n-----------------------------------------------------")
        print(f"Test: {case['description']}")
        print(f"-----------------------------------------------------")

        prompt = case["prompt"]
        if args.base_circuit and args.follow_up_prompt:
            base_wrapped = {"circuit": base_circuit_data.get("circuit", base_circuit_data)}
            prompt = args.follow_up_prompt + f"\n\nCIRCUITO BASE A MODIFICAR:\n```json\n{json.dumps(base_wrapped, indent=2)}\n```\n(Por favor, aplica las modificaciones del prompt anterior sobre este circuito preservando los componentes existentes a menos que se te pida explícitamente eliminarlos. Asegúrate de devolver el JSON envuelto en la clave 'circuit' tal como se muestra en el circuito base.)"

        print("Generando circuito (Agente Multi-Turno)...", flush=True)
        t0 = time.time()
        steward = CircuitStewardAgent(synth)
        history = []
        result = steward.run_agent_loop(
            prompt=prompt,
            session_id=run_session,
            history=history,
            on_turn_end=lambda t, status: _safe_print(f"  [Turno {t}] {status}")
        )
        elapsed = time.time() - t0
        
        # Compatibility with the rest of the script
        result["session_dir"] = str(_ROOT / "knowledge" / "data" / "llm_sessions" / "sessions" / run_session)
        result["generation_attempts"] = result.get("turns", 1)
        result["truncated"] = False
        print(f"  ({elapsed:.0f}s)", flush=True)

        entry = {
            "name": name,
            "elapsed_s": round(elapsed, 1),
            "session_id": run_session,
            "generation_attempts": result.get("generation_attempts"),
            "truncated": result.get("truncated"),
        }

        if "error" in result:
            print(f"ERROR en generacion: {result['error']}")
            entry["error"] = result["error"]
            run_manifest["results"].append(entry)
            continue

        components = result.get("components", [])
        print(f"OK: Generacion exitosa. {len(components)} componentes.")
        print(f"  backend: {result.get('backend', '?')}")
        if result.get("session_dir"):
            print(f"  llm logs: {result['session_dir']}", flush=True)

        pin_coverage = _pin_coverage(components, synth.pinouts_db)

        print("Revisando semantica (AI DRC)...", flush=True)
        t_review = time.time()
        review_raw = reviewer.review_netlist(
            json.dumps({"components": components}, ensure_ascii=False),
            session_id=run_session,
            meta={"test": name, "ab_variant": args.variant},
        )
        review_elapsed = time.time() - t_review
        semantic_review = _semantic_review_summary(review_raw)
        print(f"  ({review_elapsed:.0f}s)", flush=True)

        out_file = run_dir / f"{name}.json"
        output_data = {
            "run_session": run_session,
            "test_case": case["description"],
            "prompt": prompt,
            "ab_variant": args.variant,
            "backend": result.get("backend"),
            "synthesis_backend": result.get("backend"),
            "review_backend": review_raw.get("backend"),
            "generation_attempts": result.get("generation_attempts"),
            "truncated": result.get("truncated"),
            "llm_session_dir": result.get("session_dir"),
            "circuit": components,
            "pin_coverage": pin_coverage,
            "semantic_review": semantic_review,
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Guardado en: {out_file}")

        review_file = run_dir / "review.md"
        with open(review_file, "w", encoding="utf-8") as f:
            f.write(generate_markdown_report(semantic_review.get("issues", [])))
        print(f"Revisión generada en: {review_file}")

        etypes = {}
        for comp in components:
            t = comp.get("etype", "UNKNOWN")
            etypes[t] = etypes.get(t, 0) + 1
        print(f"Resumen: {etypes}")

        if pin_coverage["per_component"]:
            cov_str = ", ".join(
                f"{c['label']}({c['value']}): {c['generated_pins']}/{c['total_pins']} pins "
                f"({c['coverage'] * 100:.0f}%)"
                for c in pin_coverage["per_component"]
            )
            avg = pin_coverage["average_coverage"]
            print(f"Pin Coverage Fidelity: {cov_str}  [avg={avg * 100:.0f}%]" if avg is not None else f"Pin Coverage Fidelity: {cov_str}")
        if pin_coverage["unmatched"]:
            unmatched_vals = [u["value"] for u in pin_coverage["unmatched"]]
            print(f"  (sin pinout de referencia en pinouts_library.json ni symbols_index.json: {unmatched_vals})")

        if semantic_review.get("error"):
            _safe_print(f"Semantic review ERROR: {semantic_review['error']}")
        else:
            _safe_print(
                f"Semantic review: {semantic_review['issue_count']} issues "
                f"({semantic_review['critical_count']} critical)"
            )

        entry.update(
            {
                "ok": True,
                "components": len(components),
                "backend": result.get("backend"),
                "synthesis_backend": result.get("backend"),
                "review_backend": review_raw.get("backend"),
                "ab_variant": args.variant,
                "output_file": str(out_file),
                "llm_session_dir": result.get("session_dir"),
                "pin_coverage": pin_coverage,
                "semantic_review": semantic_review,
                "review_elapsed_s": round(review_elapsed, 1),
            }
        )
        run_manifest["results"].append(entry)

    run_manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    run_manifest["truncation_events"] = sum(1 for r in run_manifest["results"] if r.get("truncated"))
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRun manifest: {manifest_path}")


if __name__ == "__main__":
    main()
