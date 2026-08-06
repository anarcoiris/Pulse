"""
Regression tests for kicad_audit.py using minimal synthetic boards.

Run with:  python3 -m pytest test_kicad_audit.py -v
or plainly: python3 test_kicad_audit.py
"""
import tempfile
import os
import sys

from sexp import parse
from kicad_audit import (
    extract_nets, extract_footprints, run_audit, BoardContext,
)

MINIMAL_HEADER = '''(kicad_pcb (version 20240108) (generator "test")
  (general (thickness 1.6))
  (paper "A4")
  (layers (0 "F.Cu" signal) (31 "B.Cu" signal))
  (net 0 "")
  (net 1 "GND")
  (net 2 "3V3")
'''


def _write_board(body: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".kicad_pcb")
    with os.fdopen(fd, "w") as f:
        f.write(MINIMAL_HEADER + body + "\n)\n")
    return path


def test_net_table_not_corrupted_by_pad_level_net_refs():
    """Regression test for the find_all() vs find_direct() bug: a pad whose
    net id happens to equal a declared net id, but with a DIFFERENT name
    inline (or no name), must not overwrite the top-level net table."""
    body = '''
  (footprint "Test:2pin" (layer "F.Cu") (at 0 0)
    (property "Reference" "R1" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "10k" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu") (net 2 "3V3"))
  )
'''
    path = _write_board(body)
    try:
        text = open(path).read()
        root = parse(text)
        nets = extract_nets(root)
        assert nets[1] == "GND", f"net 1 name corrupted: {nets[1]!r}"
        assert nets[2] == "3V3", f"net 2 name corrupted: {nets[2]!r}"
        assert len(nets) == 3  # 0, 1, 2
    finally:
        os.remove(path)
    print("PASS: test_net_table_not_corrupted_by_pad_level_net_refs")


def test_R001_duplicate_pad_number():
    body = '''
  (footprint "Test:BadReg" (layer "F.Cu") (at 0 0)
    (property "Reference" "U1" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "REG" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu") (net 2 "3V3"))
    (pad "2" smd rect (at 2 0) (size 2 2) (layers "F.Cu") (net 2 "3V3"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R001"])
        assert len(findings) == 1
        assert findings[0].rule == "R001"
        assert "U1" in findings[0].location
    finally:
        os.remove(path)
    print("PASS: test_R001_duplicate_pad_number")


def test_R002_unassigned_pad():
    body = '''
  (footprint "Test:Floating" (layer "F.Cu") (at 0 0)
    (property "Reference" "U2" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "IC" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu"))
    (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R002"])
        assert len(findings) == 1
        assert "pad 1" in findings[0].location
    finally:
        os.remove(path)
    print("PASS: test_R002_unassigned_pad")


def test_R002_ignores_mounting_holes():
    body = '''
  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu") (at 0 0)
    (property "Reference" "H1" (layer "F.SilkS") (effects (font (size 1 1))))
    (pad "" thru_hole circle (at 0 0) (size 6 6) (drill 3.2) (layers "*.Cu"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R002"])
        assert len(findings) == 0, f"mounting hole should not trigger R002: {findings}"
    finally:
        os.remove(path)
    print("PASS: test_R002_ignores_mounting_holes")


def test_R003_single_pin_net():
    body = '''
  (footprint "Test:One" (layer "F.Cu") (at 0 0)
    (property "Reference" "J1" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "CONN" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R003"])
        assert len(findings) == 1
        assert findings[0].rule == "R003"
    finally:
        os.remove(path)
    print("PASS: test_R003_single_pin_net")


def test_R004_routed_but_no_pads():
    body = '''
  (via (at 10 10) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1))
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R004"])
        assert len(findings) == 1
        assert findings[0].rule == "R004"
    finally:
        os.remove(path)
    print("PASS: test_R004_routed_but_no_pads")


def test_R006_shorted_cap():
    body = '''
  (footprint "Capacitor_SMD:C_0805" (layer "F.Cu") (at 0 0)
    (property "Reference" "C1" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "100nF" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at -1 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R006"])
        assert len(findings) == 1
        assert findings[0].rule == "R006"
    finally:
        os.remove(path)
    print("PASS: test_R006_shorted_cap")


def test_R008_sot223_duplicate_pad_number_detected():
    body = '''
  (footprint "SOT-223-3_TabPin2" (layer "F.Cu") (at 0 0)
    (property "Reference" "U3" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "AMS1117-3.3" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd roundrect (at -3.15 -2.3) (size 2 1.5) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd roundrect (at -3.15 0) (size 2 1.5) (layers "F.Cu") (net 2 "3V3"))
    (pad "2" smd roundrect (at 3.15 0) (size 2 3.8) (layers "F.Cu") (net 2 "3V3"))
    (pad "3" smd roundrect (at -3.15 2.3) (size 2 1.5) (layers "F.Cu") (net 1 "GND"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R008"])
        assert len(findings) == 1
        assert findings[0].rule == "R008"
    finally:
        os.remove(path)
    print("PASS: test_R008_sot223_duplicate_pad_number_detected")


def test_R009_undeclared_net_id():
    body = '''
  (footprint "Test:X" (layer "F.Cu") (at 0 0)
    (property "Reference" "U4" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "X" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 99 "GHOST"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R009"])
        assert len(findings) == 1
        assert "99" in findings[0].message
    finally:
        os.remove(path)
    print("PASS: test_R009_undeclared_net_id")


def test_R012_duplicate_reference():
    body = '''
  (footprint "Test:A" (layer "F.Cu") (at 0 0)
    (property "Reference" "H" (layer "F.SilkS") (effects (font (size 1 1))))
    (pad "" thru_hole circle (at 0 0) (size 3 3) (drill 2) (layers "*.Cu"))
  )
  (footprint "Test:A" (layer "F.Cu") (at 5 5)
    (property "Reference" "H" (layer "F.SilkS") (effects (font (size 1 1))))
    (pad "" thru_hole circle (at 0 0) (size 3 3) (drill 2) (layers "*.Cu"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R012"])
        assert len(findings) == 1
        assert findings[0].rule == "R012"
    finally:
        os.remove(path)
    print("PASS: test_R012_duplicate_reference")


def test_R013_keepout_single_layer():
    body = '''
  (zone (keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour not_allowed))
    (layers "F.Cu")
    (polygon (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10)))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R013"])
        assert len(findings) == 1
        assert findings[0].rule == "R013"
    finally:
        os.remove(path)
    print("PASS: test_R013_keepout_single_layer")


def test_R014_regulator_missing_caps():
    body = '''
  (footprint "Package_TO_SOT_SMD:SOT-223" (layer "F.Cu") (at 0 0)
    (property "Reference" "U1" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "AMS1117-3.3" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu") (net 2 "3V3"))
    (pad "3" smd rect (at 2 0) (size 1 1) (layers "F.Cu") (net 3 "5V_USB"))
  )
  (footprint "Capacitor_SMD:C_0805" (layer "F.Cu") (at 5 0)
    (property "Reference" "C1" (layer "F.SilkS") (effects (font (size 1 1))))
    (property "Value" "10uF" (layer "F.Fab") (effects (font (size 1 1))))
    (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 2 "3V3"))
    (pad "2" smd rect (at 1 0) (size 1 1) (layers "F.Cu") (net 1 "GND"))
  )
'''
    path = _write_board(body)
    try:
        findings, ctx = run_audit(path, rule_filter=["R014"])
        assert len(findings) == 1
        assert findings[0].rule == "R014"
        assert "5V_USB" in findings[0].message
    finally:
        os.remove(path)
    print("PASS: test_R014_regulator_missing_caps")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL: {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)

