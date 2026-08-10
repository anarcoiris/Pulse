"""
Regression tests for sch_pcb_crosscheck.py using tiny synthetic files.
"""
import tempfile
import os
import sys

from sexp import parse
from sch_pcb_crosscheck import sch_lib_symbol_pin_counts, sch_symbols, sch_labels


MINIMAL_SCH_NO_PINS = '''(kicad_sch (version 20241228) (generator "test")
  (uuid "00000000-0000-0000-0000-000000000000")
  (paper "A4")
  (lib_symbols
    (symbol "Device:R" (pin_numbers hide) (pin_names (offset 1.016) hide)
      (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "Val" (at 0 -2.54 0) (effects (font (size 1.27 1.27))))
    )
  )
  (symbol (lib_id "Device:R") (at 10 10 0) (unit 1)
    (uuid "11111111-1111-1111-1111-111111111111")
    (property "Reference" "R1" (at 10 8 0) (effects (font (size 1.27 1.27))))
    (property "Value" "10k" (at 10 12 0) (effects (font (size 1.27 1.27))))
  )
  (label "GND" (at 12 10 0) (effects (font (size 1.27 1.27)))
    (uuid "22222222-2222-2222-2222-222222222222"))
)
'''

MINIMAL_SCH_WITH_PINS = '''(kicad_sch (version 20241228) (generator "test")
  (uuid "00000000-0000-0000-0000-000000000000")
  (paper "A4")
  (lib_symbols
    (symbol "Device:R" (pin_numbers hide) (pin_names (offset 1.016) hide)
      (property "Reference" "U" (at 0 2.54 0) (effects (font (size 1.27 1.27))))
      (symbol "R_0_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27)))))
      )
    )
  )
  (symbol (lib_id "Device:R") (at 10 10 0) (unit 1)
    (uuid "11111111-1111-1111-1111-111111111111")
    (property "Reference" "R1" (at 10 8 0) (effects (font (size 1.27 1.27))))
    (property "Value" "10k" (at 10 12 0) (effects (font (size 1.27 1.27))))
  )
)
'''


def _write(text: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".kicad_sch")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    return path


def test_detects_zero_pin_symbols():
    path = _write(MINIMAL_SCH_NO_PINS)
    try:
        root = parse(open(path).read())
        counts = sch_lib_symbol_pin_counts(root)
        assert counts == {"Device:R": 0}
    finally:
        os.remove(path)
    print("PASS: test_detects_zero_pin_symbols")


def test_detects_real_pins_when_present():
    path = _write(MINIMAL_SCH_WITH_PINS)
    try:
        root = parse(open(path).read())
        counts = sch_lib_symbol_pin_counts(root)
        assert counts == {"Device:R": 2}, counts
    finally:
        os.remove(path)
    print("PASS: test_detects_real_pins_when_present")


def test_symbol_and_label_extraction():
    path = _write(MINIMAL_SCH_NO_PINS)
    try:
        root = parse(open(path).read())
        syms = sch_symbols(root)
        labels = sch_labels(root)
        assert len(syms) == 1
        assert syms[0]["ref"] == "R1"
        assert syms[0]["value"] == "10k"
        assert len(labels) == 1
        assert labels[0]["name"] == "GND"
    finally:
        os.remove(path)
    print("PASS: test_symbol_and_label_extraction")


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
