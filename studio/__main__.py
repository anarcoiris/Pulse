"""
studio/__main__.py
==================
Entry point: python -m studio

Headless Rich REPL for streaming LLM circuit debug (Forge Studio v1).
"""

from __future__ import annotations

import argparse
import sys

from studio.commands import ParsedCommand, parse_input
from studio.session import ForgeSession
from studio.stream_ui import StreamRenderer


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _print_backends(ui: StreamRenderer, data: dict) -> None:
    for name, info in data.items():
        if name == "routing":
            continue
        avail = "up" if info.get("available") else "down"
        ui.print_info(
            f"  {name}: {avail}  model={info.get('model')}  "
            f"api={info.get('api')}  url={info.get('base_url')}"
        )
    routing = data.get("routing") or {}
    if routing:
        ui.print_info(f"  routing: {routing}")


def _format_pin_coverage(result: dict) -> str:
    cov = result.get("pin_coverage") or {}
    avg = cov.get("average_coverage")
    n = result.get("component_count", 0)
    parts = [f"components={n}"]
    if avg is not None:
        parts.append(f"pin_coverage_avg={avg:.1%}")
    attempts = result.get("generation_attempts")
    if attempts:
        parts.append(f"attempts={attempts}")
    truncated = result.get("truncated")
    if truncated:
        parts.append("truncated=yes")
    return "  ".join(parts)


def _handle_command(session: ForgeSession, ui: StreamRenderer, cmd: ParsedCommand) -> bool:
    """Return False to exit REPL."""
    name = cmd.name

    if name in ("quit", "exit", "q"):
        return False

    if name == "backends":
        _print_backends(ui, session.backends_table())
        return True

    if name == "session":
        info = session.session_info()
        ui.print_info(
            f"session_id={info['session_id']}  backend={info['backend']}  "
            f"components={info['components']}"
        )
        ui.print_info(f"log_dir={info['log_dir']}")
        return True

    if name == "generate":
        if not cmd.args.strip():
            ui.print_error("Uso: /generate <descripcion del circuito>")
            return True
        renderer = ui.on_chunk_callback()
        result = session.generate(cmd.args.strip(), on_chunk=renderer)
        if "error" in result and result.get("status") != "ok":
            ui.print_error(str(result.get("error")))
        elif result.get("status") == "ok":
            ui.print_ok(_format_pin_coverage(result))
        return True

    if name == "steward":
        if not cmd.args.strip():
            ui.print_error("Uso: /steward <descripcion del circuito>")
            return True
            
        def on_turn_end(turn: int, status: str):
            ui.print_info(f"\n[Turno {turn}] -> {status}")
            
        renderer = ui.on_chunk_callback()
        result = session.steward(cmd.args.strip(), on_chunk=renderer, on_turn_end=on_turn_end)
        
        if "error" in result and result.get("status") != "ok":
            ui.print_error(str(result.get("error")))
        elif result.get("status") == "ok":
            ui.print_ok(f"[{result.get('turns')} turnos] " + _format_pin_coverage(result))
        return True

    if name == "review":
        renderer = ui.on_chunk_callback()
        result = session.review(on_chunk=renderer)
        if result.get("error"):
            ui.print_error(str(result["error"]))
        elif result.get("status") == "ok":
            issues = result.get("issues") or []
            ui.print_ok(f"review backend={result.get('backend')} issues={len(issues)}")
            for i, iss in enumerate(issues[:6], 1):
                sev = iss.get("severity", "?")
                ui.print_info(f"  [{i}] ({sev}) {iss.get('msg', '')}")
        return True

    if name == "save":
        if not cmd.args.strip():
            ui.print_error("Uso: /save <ruta.json>")
            return True
        result = session.save(cmd.args.strip())
        if result.get("error"):
            ui.print_error(result["error"])
        else:
            ui.print_ok(f"guardado en {result['path']}")
        return True

    if name == "load":
        if not cmd.args.strip():
            ui.print_error("Uso: /load <ruta.json>")
            return True
        result = session.load(cmd.args.strip())
        if result.get("error"):
            ui.print_error(result["error"])
        else:
            ui.print_ok(f"cargado {result['components']} componentes desde {result['path']}")
        return True

    if name == "schematic":
        ui.print_info("Generando PCB + SVG preview (puede tardar)...")
        result = session.schematic()
        if result.get("error"):
            ui.print_error(result["error"])
        else:
            ui.print_ok(f"pcb={result.get('pcb')}")
            if result.get("sch"):
                ui.print_info(f"sch={result['sch']}")
            for svg in result.get("svg_files") or []:
                ui.print_info(f"svg={svg}")
        return True

    if name == "help":
        ui.print_info(
            "Comandos: /steward /generate /review /backends /save /load /schematic "
            "/session /help /quit  |  texto libre = generar circuito"
        )
        return True

    ui.print_error(f"Comando desconocido: /{name}  (usa /help)")
    return True


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="Forge Studio — headless LLM debug shell")
    parser.add_argument("--backend", default="auto", help="LLM backend: primary, atomic, or auto")
    args = parser.parse_args(argv)

    try:
        ui = StreamRenderer()
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 1

    session = ForgeSession(backend=args.backend)
    ui.print_info("Forge Studio v1 — headless LLM debug shell")
    ui.print_info(f"session_id={session.session_id}  backend={session.backend}")
    ui.print_info("Escribe un prompt o /help.  Salir: /quit")

    while True:
        try:
            line = input("studio> ")
        except (EOFError, KeyboardInterrupt):
            ui.print_info("")
            break

        parsed = parse_input(line)
        if parsed == "":
            continue
        if isinstance(parsed, str):
            renderer = ui.on_chunk_callback()
            result = session.generate(parsed, on_chunk=renderer)
            if "error" in result and result.get("status") != "ok":
                ui.print_error(str(result.get("error")))
            elif result.get("status") == "ok":
                ui.print_ok(_format_pin_coverage(result))
            continue

        if not _handle_command(session, ui, parsed):
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
