"""
studio/__main__.py
==================
Entry point: python -m studio

Headless Rich REPL for streaming LLM circuit debug (Forge Studio v1).
"""

from __future__ import annotations

import argparse
import sys

from studio.commands import ParsedCommand, parse_input, resolve_file_references
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
        args_text = cmd.args.strip()
        if not args_text:
            ui.print_error("Uso: /generate <descripcion del circuito>")
            return True
        args_text = resolve_file_references(args_text)
        renderer = ui.on_chunk_callback()
        result = session.generate(args_text, on_chunk=renderer)
        if "error" in result and result.get("status") != "ok":
            ui.print_error(str(result.get("error")))
        elif result.get("status") == "ok":
            ui.print_ok(_format_pin_coverage(result))
        return True

    if name == "steward":
        args_text = cmd.args.strip()
        if not args_text:
            ui.print_error("Uso: /steward <descripcion del circuito>")
            return True
        args_text = resolve_file_references(args_text)
            
        def on_turn_end(turn: int, status: str):
            ui.print_info(f"\n[Turno {turn}] -> {status}")
            
        renderer = ui.on_chunk_callback()
        result = session.steward(args_text, on_chunk=renderer, on_turn_end=on_turn_end)
        
        if "error" in result and result.get("status") != "ok":
            ui.print_error(str(result.get("error")))
        elif result.get("status") == "ok":
            ui.print_ok(f"[{result.get('turns')} turnos] " + _format_pin_coverage(result))
        return True

    if name in ("paste", "multiline"):
        subcmd = cmd.args.strip().lower()
        ui.print_info("Entrando en modo multilínea. Escribe/pega tu texto.")
        ui.print_info("Para terminar y procesar, escribe '/end' o '.' en una nueva línea:")
        lines = []
        while True:
            try:
                l = input("  > ")
            except (EOFError, KeyboardInterrupt):
                ui.print_info("")
                break
            if l.strip() in ("/end", "."):
                break
            lines.append(l)
        
        text = "\n".join(lines).strip()
        if not text:
            ui.print_info("Entrada vacía. Cancelado.")
            return True
        
        text = resolve_file_references(text)
        
        if subcmd == "steward":
            def on_turn_end_paste(turn: int, status: str):
                ui.print_info(f"\n[Turno {turn}] -> {status}")
            renderer = ui.on_chunk_callback()
            result = session.steward(text, on_chunk=renderer, on_turn_end=on_turn_end_paste)
            if "error" in result and result.get("status") != "ok":
                ui.print_error(str(result.get("error")))
            elif result.get("status") == "ok":
                ui.print_ok(f"[{result.get('turns')} turnos] " + _format_pin_coverage(result))
        else:
            renderer = ui.on_chunk_callback()
            result = session.generate(text, on_chunk=renderer)
            if "error" in result and result.get("status") != "ok":
                ui.print_error(str(result.get("error")))
            elif result.get("status") == "ok":
                ui.print_ok(_format_pin_coverage(result))
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
        path = cmd.args.strip().strip("'\"")
        result = session.save(path)
        if result.get("error"):
            ui.print_error(result["error"])
        else:
            ui.print_ok(f"guardado en {result['path']}")
        return True

    if name == "load":
        if not cmd.args.strip():
            ui.print_error("Uso: /load <ruta.json>")
            return True
        path = cmd.args.strip().strip("'\"")
        result = session.load(path)
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
            "Comandos: /steward /generate /paste /review /backends /save /load /schematic "
            "/session /help /quit  |  texto libre = generar circuito"
        )
        return True

    ui.print_error(f"Comando desconocido: /{name}  (usa /help)")
    return True


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    
    if argv is None:
        argv = sys.argv[1:]
        
    parser = argparse.ArgumentParser(description="PulseLab Studio - Unified CLI", prog="python -m studio")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # repl
    repl_parser = subparsers.add_parser("repl", help="Run the Headless LLM Debug Shell")
    repl_parser.add_argument("--backend", default="auto", help="LLM backend: primary, atomic, or auto")
    
    # gui
    subparsers.add_parser("gui", help="Launch the PulseLab GUI")
    
    # mcp
    subparsers.add_parser("mcp", help="Launch the MCP Server")
    
    # validate
    subparsers.add_parser("validate", help="Run the complex apps validation suite")
    
    # calibrate
    subparsers.add_parser("calibrate", help="Run LLM calibration routines")
    
    # build-index
    subparsers.add_parser("build-index", help="Build vector and symbol indices")
    
    # crawl
    subparsers.add_parser("crawl", help="Execute the GitHub crawler")
    
    # dataset
    subparsers.add_parser("dataset", help="Prepare and process JSONL training datasets")
    
    # train
    subparsers.add_parser("train", help="Initiate model finetuning")
    
    # export
    subparsers.add_parser("export", help="Batch export scripts")
    
    # guide
    subparsers.add_parser("guide", help="Print a comprehensive onboarding guide")

    args, unknown = parser.parse_known_args(argv)
    
    if args.command is None or args.command == "repl":
        return _run_repl(args, unknown)
        
    elif args.command == "gui":
        import pulse_lab
        sys.argv = ["pulse_lab.py"] + unknown
        pulse_lab.main()
        return 0
        
    elif args.command == "mcp":
        from mcp_server import server
        sys.argv = ["server.py"] + unknown
        server.main()
        return 0
        
    elif args.command == "validate":
        from knowledge import validate_complex_apps
        sys.argv = ["validate_complex_apps.py"] + unknown
        validate_complex_apps.main()
        return 0
        
    elif args.command == "calibrate":
        from knowledge import calibration_run
        sys.argv = ["calibration_run.py"] + unknown
        calibration_run.main()
        return 0
        
    elif args.command == "build-index":
        print("--- Building Symbol Index ---")
        from knowledge import build_symbol_index
        sys.argv = ["build_symbol_index.py"] + unknown
        build_symbol_index.main()
        print("\n--- Building Embed Index ---")
        from knowledge import build_embed_index
        sys.argv = ["build_embed_index.py"] + unknown
        build_embed_index.main()
        return 0
        
    elif args.command == "crawl":
        from knowledge import github_crawler
        sys.argv = ["github_crawler.py"] + unknown
        if hasattr(github_crawler, "main"):
            github_crawler.main()
        else:
            github_crawler.run_crawler() # Need to check the method
        return 0
        
    elif args.command == "dataset":
        from knowledge import prepare_llm_dataset
        sys.argv = ["prepare_llm_dataset.py"] + unknown
        if hasattr(prepare_llm_dataset, "main"):
             prepare_llm_dataset.main()
        elif hasattr(prepare_llm_dataset, "prepare_llm_dataset"):
             prepare_llm_dataset.prepare_llm_dataset()
        return 0
        
    elif args.command == "train":
        from knowledge import finetune_circuit_llm
        sys.argv = ["finetune_circuit_llm.py"] + unknown
        finetune_circuit_llm.main()
        return 0
        
    elif args.command == "export":
        from examples import export_all_boards
        sys.argv = ["export_all_boards.py"] + unknown
        export_all_boards.main()
        return 0
        
    elif args.command == "guide":
        print_guide()
        return 0

    return 0

def _run_repl(args, unknown) -> int:
    try:
        ui = StreamRenderer()
    except ImportError as e:
        print(str(e), file=sys.stderr)
        return 1

    backend = getattr(args, "backend", "auto")
    session = ForgeSession(backend=backend)
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
            resolved = resolve_file_references(parsed)
            renderer = ui.on_chunk_callback()
            result = session.generate(resolved, on_chunk=renderer)
            if "error" in result and result.get("status") != "ok":
                ui.print_error(str(result.get("error")))
            elif result.get("status") == "ok":
                ui.print_ok(_format_pin_coverage(result))
            continue

        if not _handle_command(session, ui, parsed):
            break

    return 0

def print_guide():
    guide = """
============================================================
           PULSELAB STUDIO - ONBOARDING GUIDE
============================================================

PulseLab Studio is your unified entrypoint for circuit design, 
LLM-based schematic synthesis, and validation.

Commands available via `python -m studio <command>`:

1. Interfaces:
   - `python -m studio gui`   : Launch the visual PulseLab circuit editor.
   - `python -m studio repl`  : Start the interactive headless LLM debug shell.
   - `python -m studio mcp`   : Start the Model Context Protocol (MCP) server.

2. Validation & Quality:
   - `python -m studio validate` : Run the complex apps validation suite. Use 
                                   --case to run specific tests or --base-circuit 
                                   to continue a generation.
   - `python -m studio calibrate`: Run the LLM calibration suite.

3. Knowledge & Retrieval (RAG):
   - `python -m studio build-index`: Parse KiCad libraries and build the vector 
                                     index for the RAG engine.
   - `python -m studio crawl`      : Scrape GitHub for training schematics.

4. Model Training:
   - `python -m studio dataset`: Prepare `.jsonl` datasets from the knowledge base.
   - `python -m studio train`  : Finetune the local LLM model for circuit synthesis.

5. Utilities:
   - `python -m studio export` : Batch export project boards to PCB formats.

Get started by running the GUI or exploring the REPL!
============================================================
"""
    print(guide)

if __name__ == "__main__":
    raise SystemExit(main())
