"""Tests de validacion para PulseLab Forge."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_rf_tools():
    from core.rf_tools import (microstrip_impedance, microstrip_width_for_impedance,
                                trace_width_ipc2221, skin_depth)
    # Ref: FR4 50 Ohm (W=3mm, h=1.6mm)
    r = microstrip_impedance(3.0, 1.6, 4.4, freq_ghz=1.0)
    print(f"FR4 50Ohm: Z0={r['Z0']}Ohm, eff_er={r['eff_er']}")
    assert 46 < r['Z0'] < 54, f"Z0 fuera de rango: {r['Z0']}"

    w = microstrip_width_for_impedance(50.0, 1.6, 4.4)
    print(f"Width para 50Ohm FR4: W={w['W_mm']}mm, error={w['error_pct']}%")
    assert w['error_pct'] < 5.0

    tw = trace_width_ipc2221(2.0)
    print(f"IPC-2221 2A external: W={tw['W_mm']}mm (ref~0.76mm)")
    assert 0.5 < tw['W_mm'] < 1.2

    sd = skin_depth(1e9)
    print(f"Skin depth Cu@1GHz: delta={sd['delta_um']}um (ref~2.1um)")
    assert 1.5 < sd['delta_um'] < 3.0
    print("RF Tools: PASS")


def test_component_db():
    from core.component_db import ComponentDB
    db = ComponentDB()
    print(f"Cargados: {len(db.all())} componentes")
    assert len(db.all()) >= 5

    esp32 = db.get('ESP32-WROOM-32')
    assert esp32 is not None
    print(f"ESP32: {esp32.params.get('uart')} UARTs, WiFi={esp32.params.get('wifi')}")

    mcus = db.by_category('MCU')
    print(f"MCUs: {[c.id for c in mcus]}")
    assert any('ESP8266' in c.id for c in mcus), 'ESP8266 missing'

    fr4 = db.get_substrate('FR4')
    assert fr4.get('er') == 4.4
    print(f"FR4: er={fr4['er']}")

    cl = db.ipc_clearance(48.0, 'external', coated=False)
    print(f"Clearance 48V external uncoated: {cl['min_clearance_mm']}mm")
    assert cl['min_clearance_mm'] is not None
    print("ComponentDB: PASS")


def test_rag_engine():
    from knowledge.rag_engine import ElectronicsKnowledgeBase
    kb = ElectronicsKnowledgeBase()
    stats = kb.stats()
    print(f"KB stats: total_chunks={stats['total_chunks']}, sklearn={stats['sklearn_available']}")
    assert stats['total_chunks'] > 10
    assert stats['by_type'].get('circuit_example', 0) > 100, (
        f"Expected >100 circuit_example chunks, got {stats['by_type']}"
    )

    results = kb.query('ESP32 decoupling WiFi', top_k=3)
    print(f"Query ESP32: {len(results)} results")
    assert len(results) > 0

    rules = kb.get_design_rules(voltage_v=48.0, current_a=2.0)
    print(f"Rules 48V/2A keys: {list(rules.keys())}")
    print("RAG Engine: PASS")


def test_esp32_calibration():
    from bridge.forge_api import generate_pcb
    from presets.esp32_usb_devkit import load
    from knowledge.calibration_run import validate_design

    graph = load()
    result = generate_pcb(graph, out_dir='output/esp32_usb_devkit_test')
    assert result.get('success'), result
    pcb_path = result['path']
    assert Path(pcb_path).exists()
    sch_path = result.get('sch_path', '')
    if sch_path:
        assert Path(sch_path).exists()
        content = Path(sch_path).read_text(encoding='utf-8')
        assert 'ESP32-WROOM-32' in content or 'ESP32' in content
    cal = validate_design(pcb_path)
    print(f"Calibration score: {cal['score']}%")
    assert cal['decoupling_count'] >= 2
    assert cal['has_keepout']
    assert cal['uart_nets_ok']
    print("ESP32 Calibration: PASS")


def test_netlist_generator():
    try:
        from presets.emp_pfn import load
        from core.netlist import NetlistGenerator
        graph = load()
        ng = NetlistGenerator(graph)

        netlist = ng.to_kicad_netlist()
        assert '(export' in netlist
        assert '(nets' in netlist
        print(f"KiCad netlist: {len(netlist)} chars, {len(ng.to_bom_dict())} BOM rows")

        skidl = ng.to_skidl_script()
        assert 'from skidl import' in skidl
        print(f"SKiDL script: {len(skidl)} chars")
        print("Netlist Generator: PASS")
    except ImportError as e:
        if "pygame" in str(e):
            print(f"SKIP: {e} (pygame not in this env, not a real failure)")
        else:
            raise


def test_pcb_layout():
    from bridge.pcb_layout import PCBLayout
    import tempfile, os

    pcb = PCBLayout(board_width=30, board_height=20,
                    corner_radius=1.0, project_name="Test Board")

    r1 = pcb.add_resistor("R1", "10k", x=10, y=10, net1="VCC", net2="OUT")
    c1 = pcb.add_capacitor("C1", "100nF", x=20, y=10, net1="OUT", net2="GND")
    j1 = pcb.add_pin_header("J1", 3, x=5, y=10)
    u1 = pcb.add_dip_ic("U1", 8, x=15, y=15, value="NE555")

    pcb.align_horizontal(r1, c1, y=10.0)
    assert r1.y == c1.y == 10.0

    pcb.trace(r1, "2", c1, "1", net="OUT")
    pcb.add_mounting_holes_corners()

    stats = pcb.stats()
    print(f"Stats: {stats}")
    assert stats['footprints'] == 4
    assert stats['mounting_holes'] == 4
    assert stats['traces'] >= 1

    # Generate and verify S-expression
    sexpr = pcb.to_kicad_pcb()
    assert '(kicad_pcb' in sexpr
    assert '(footprint' in sexpr
    assert '(segment' in sexpr
    assert 'Edge.Cuts' in sexpr
    assert ';' not in sexpr  # No semicolon comments allowed

    # Save to temp and verify file
    tmp = os.path.join(tempfile.gettempdir(), "pulselab_test_board.kicad_pcb")
    pcb.save(tmp)
    assert os.path.exists(tmp)
    size = os.path.getsize(tmp)
    print(f"Generated: {tmp} ({size} bytes)")
    assert size > 500
    os.remove(tmp)

    print("PCB Layout Engine: PASS")


def test_pcb_kicad_export():
    """Test completo: genera PCB y exporta Gerbers si KiCad disponible."""
    from bridge.pcb_layout import PCBLayout
    from bridge.kicad_bridge import KiCadBridge
    from pathlib import Path

    bridge = KiCadBridge()
    if not bridge.available:
        print("KiCad not available — SKIP gerber export")
        print("PCB KiCad Export: PASS (skip)")
        return

    pcb = PCBLayout(board_width=25, board_height=15, project_name="Gerber Test")
    pcb.add_resistor("R1", "1k", x=8, y=7, net1="A", net2="B")
    pcb.add_capacitor("C1", "100nF", x=16, y=7, net1="B", net2="GND")

    out = Path("output/_test_gerber_export/board.kicad_pcb")
    pcb.save(out)

    result = bridge.export_gerbers(out, out.parent / "gerbers")
    print(f"Gerber export success: {result.get('success')}")
    print(f"Files: {result.get('count', 0)}")
    assert result.get('success'), f"Gerber export failed: {result.get('stderr', '')}"
    assert result.get('count', 0) >= 5

    # Drill
    from bridge.gerber_export import export_drill
    drill = export_drill(bridge._cli, out, out.parent / "gerbers")
    print(f"Drill export success: {drill.get('success')}")

    # Cleanup
    import shutil
    shutil.rmtree(out.parent, ignore_errors=True)

    print("PCB KiCad Export: PASS")


def test_design_experience_loop():
    """
    Regression test for docs/calibration_forge/dormant_features_audit.md.

    Confirms record_design_outcome() (called from
    bridge/gerber_export.py::generate_all_manufacturing_files) actually
    produces a knowledge/experiences/<board_id>.json file, and that the
    resulting design_experience chunk is durably visible from a *fresh*
    ElectronicsKnowledgeBase() instance — not just the throwaway KB that
    DesignExperience.ingest_to_rag() builds internally and discards.
    """
    import json
    import shutil
    from bridge.pcb_layout import PCBLayout
    from bridge.kicad_bridge import KiCadBridge
    from bridge.gerber_export import generate_all_manufacturing_files
    from knowledge.design_experience import _EXPERIENCES_DIR
    from knowledge.rag_engine import ElectronicsKnowledgeBase

    bridge = KiCadBridge()
    if not bridge.available:
        print("KiCad not available — SKIP design experience loop test")
        print("Design Experience Loop: PASS (skip)")
        return

    # record_design_outcome() uses pcb_path.stem (the filename, not the parent
    # dir) as board_id — name the .kicad_pcb file itself uniquely so the two
    # match unambiguously for this test.
    board_id = "_test_design_experience_loop"
    pcb = PCBLayout(board_width=25, board_height=15, project_name="Experience Loop Test")
    pcb.add_resistor("R1", "1k", x=8, y=7, net1="A", net2="B")
    pcb.add_capacitor("C1", "100nF", x=16, y=7, net1="B", net2="GND")

    out = Path(f"output/{board_id}/{board_id}.kicad_pcb")
    pcb.save(out)

    exp_file = _EXPERIENCES_DIR / f"{board_id}.json"
    exp_file.unlink(missing_ok=True)  # leftover from a previous failed run

    try:
        result = generate_all_manufacturing_files(bridge._cli, out, out.parent / "manufacturing")
        # Note: result['summary'] may contain non-ASCII glyphs that crash cp1252
        # consoles on Windows (same gotcha as dataset_builder.py) — avoid printing it raw.
        print(f"generate_all_manufacturing_files success={result.get('success')}")

        assert exp_file.exists(), (
            f"knowledge/experiences/{board_id}.json was not created — "
            "record_design_outcome() did not run, or failed silently."
        )
        data = json.loads(exp_file.read_text(encoding="utf-8"))
        assert data["board_id"] == board_id

        # Fresh instance simulates a new process: proves the chunk is
        # persisted to disk, not just visible in the instance ingest_to_rag()
        # created internally.
        kb = ElectronicsKnowledgeBase()
        stats = kb.stats()
        design_exp_count = stats["by_type"].get("design_experience", 0)
        print(f"design_experience chunks visible in fresh KB: {design_exp_count}")
        assert design_exp_count > 0, (
            "New KB instance shows 0 design_experience chunks — "
            "ElectronicsKnowledgeBase is not loading knowledge/experiences/ on init."
        )
    finally:
        exp_file.unlink(missing_ok=True)
        shutil.rmtree(out.parent, ignore_errors=True)

    print("Design Experience Loop: PASS")


def test_kicad_bridge():
    from bridge.kicad_bridge import KiCadBridge
    bridge = KiCadBridge()
    status = bridge.status()
    print(f"KiCad available: {status['available']}")
    if status['available']:
        print(f"Version: {status['version']}")
    print("KiCad Bridge: PASS (detection check)")


if __name__ == '__main__':
    print("=== PulseLab Forge Test Suite ===\n")
    tests = [test_rf_tools, test_component_db, test_rag_engine,
             test_netlist_generator, test_pcb_layout, test_pcb_kicad_export,
             test_design_experience_loop, test_kicad_bridge, test_esp32_calibration]
    passed = 0
    failed = 0
    skipped = 0
    for t in tests:
        print(f"--- {t.__name__} ---")
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        sys.exit(1)
