"""
core/corpus_evaluator.py
========================
Deterministic Rule Evaluator for PulseLab Skills & Knowledge Base.
Translates circuit designs into neutral intermediate models and evaluates
rules from `skills/`, producing schema-compliant Findings.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml
import re

from core.logger import logger

_CORPUS_ROOT = Path(__file__).resolve().parent.parent / "skills"
_POWER_ALIASES = {"3.3V", "3V3", "5V", "VCC", "VDD", "VBAT", "3V3_ESP", "PWR_3V3"}
_GROUND_ALIASES = {"GND", "GND_PAD", "AGND", "PGND", "DGND", "PWR_GND", "0V"}


@dataclass
class NeutralPin:
    number: str
    name: str
    role: str  # power_in, ground, reset_enable, boot_strap, i2c_sda, i2c_scl, spi_*, signal_digital, led_anode, led_cathode, etc.
    net: str


@dataclass
class NeutralComponent:
    ref: str
    kind: str  # mcu, ic, resistor, capacitor, switch, led, connector, power_source
    part_value: str
    package: str
    pins: List[NeutralPin] = field(default_factory=list)
    numeric_value: Optional[float] = None


@dataclass
class NeutralCircuit:
    board_width: float
    board_height: float
    components: Dict[str, NeutralComponent] = field(default_factory=dict)
    nets: Dict[str, List[Tuple[str, str]]] = field(default_factory=dict)  # net_name -> list of (component_ref, pin_number)


def parse_numeric_value(val_str: str) -> Optional[float]:
    """Parses engineering notation (e.g. 4.7k -> 4700.0, 100nF -> 1e-7)."""
    if not val_str:
        return None
    val = str(val_str).strip().replace("Ω", "").replace("F", "").replace("H", "")
    match = re.match(r"^([\d\.]+)\s*([pnumkMG]?)$", val, re.IGNORECASE)
    if not match:
        try:
            return float(val)
        except ValueError:
            return None
    num, prefix = match.groups()
    try:
        n = float(num)
    except ValueError:
        return None
    multipliers = {
        "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3,
        "": 1.0, "k": 1e3, "M": 1e6, "G": 1e9
    }
    return n * multipliers.get(prefix, 1.0)


class CorpusEvaluator:
    """Evaluates neutral circuit representations against formal skills/ rules."""

    def __init__(self, corpus_dir: Optional[Path] = None):
        self.corpus_dir = corpus_dir or _CORPUS_ROOT
        self.parts_db: Dict[str, Dict[str, Any]] = {}
        self._load_parts()

    def _load_parts(self):
        parts_dir = self.corpus_dir / "component-library" / "parts"
        if not parts_dir.exists():
            return
        for p_file in parts_dir.glob("*.yaml"):
            try:
                with open(p_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "part_value" in data:
                        self.parts_db[data["part_value"].upper()] = data
            except Exception as e:
                logger.warning("corpus_evaluator", f"Failed to load part file {p_file}: {e}")

    def build_neutral_model(self, circuit_data: Dict[str, Any]) -> NeutralCircuit:
        """Translates raw circuit dict (netlist propio) to NeutralCircuit."""
        comps = circuit_data.get("circuit", [])
        w = float(circuit_data.get("board_width", 75.0))
        h = float(circuit_data.get("board_height", 50.0))

        nc = NeutralCircuit(board_width=w, board_height=h)

        for c in comps:
            ref = c.get("label", c.get("uid", "?"))
            val = str(c.get("value", ""))
            etype = str(c.get("etype", "")).upper()
            fp = c.get("footprint", c.get("footprint_id", ""))
            num_val = parse_numeric_value(val)

            # Determine kind
            kind = "ic"
            if etype in ["MCU"]:
                kind = "mcu"
            elif etype in ["R"]:
                kind = "resistor"
            elif etype in ["C"]:
                kind = "capacitor"
            elif etype in ["S", "SW", "BUTTON"]:
                kind = "switch"
            elif etype in ["LED"] or ref.startswith("D_") or ref.startswith("LED"):
                kind = "led"
            elif etype in ["V"]:
                kind = "power_source"
            elif "CONN" in etype or "HEADER" in ref.upper():
                kind = "connector"

            # Lookup part specs if available
            part_spec = self.parts_db.get(val.upper(), {})

            pins_list: List[NeutralPin] = []
            pins_data = c.get("pins", {})
            if isinstance(pins_data, dict) and len(pins_data) > 0:
                for p_num, net_name in pins_data.items():
                    net_str = str(net_name)
                    # Resolve pin role: part_spec first, then heuristics
                    role = "signal_digital"
                    if part_spec and "pins" in part_spec and str(p_num) in part_spec["pins"]:
                        role = part_spec["pins"][str(p_num)].get("role", role)
                    elif p_num.upper() in ["EN", "CHIP_PU", "RESET"]:
                        role = "reset_enable"
                    elif p_num.upper() in ["BOOT", "IO0", "GPIO0"]:
                        role = "boot_strap"
                    elif "SDA" in p_num.upper() or "SDA" in net_str.upper():
                        role = "i2c_sda"
                    elif "SCL" in p_num.upper() or "SCL" in net_str.upper():
                        role = "i2c_scl"
                    elif net_str in _POWER_ALIASES:
                        role = "power_in"
                    elif net_str in _GROUND_ALIASES:
                        role = "ground"

                    pin_obj = NeutralPin(number=str(p_num), name=str(p_num), role=role, net=net_str)
                    pins_list.append(pin_obj)
                    nc.nets.setdefault(net_str, []).append((ref, str(p_num)))

            elif "n1" in c and "n2" in c:
                # 2-terminal passive component
                n1, n2 = str(c.get("n1", "")), str(c.get("n2", ""))
                role1, role2 = "signal_digital", "signal_digital"
                if kind == "led":
                    role1, role2 = "led_anode", "led_cathode"
                elif n1 in _POWER_ALIASES:
                    role1 = "power_in"
                elif n1 in _GROUND_ALIASES:
                    role1 = "ground"
                if n2 in _POWER_ALIASES:
                    role2 = "power_in"
                elif n2 in _GROUND_ALIASES:
                    role2 = "ground"

                p1 = NeutralPin(number="1", name="1", role=role1, net=n1)
                p2 = NeutralPin(number="2", name="2", role=role2, net=n2)
                pins_list = [p1, p2]
                nc.nets.setdefault(n1, []).append((ref, "1"))
                nc.nets.setdefault(n2, []).append((ref, "2"))

            n_comp = NeutralComponent(
                ref=ref,
                kind=kind,
                part_value=val,
                package=fp,
                pins=pins_list,
                numeric_value=num_val
            )
            nc.components[ref] = n_comp

        return nc

    def evaluate(self, circuit_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Runs all deterministic rules and returns schema-compliant findings."""
        model = self.build_neutral_model(circuit_data)
        findings: List[Dict[str, Any]] = []

        findings.extend(self._check_power_on_reset(model))
        findings.extend(self._check_i2c_pullups(model))
        findings.extend(self._check_boot_straps(model))
        findings.extend(self._check_decoupling(model))

        return findings

    def _check_power_on_reset(self, model: NeutralCircuit) -> List[Dict[str, Any]]:
        findings = []
        for ref, comp in model.components.items():
            for pin in comp.pins:
                if pin.role == "reset_enable":
                    net = pin.net
                    # Check if tied directly to ground
                    if net in _GROUND_ALIASES:
                        findings.append({
                            "rule_id": "schematic.power_on_reset.en_pullup",
                            "domain": "schematic",
                            "severity": "critical",
                            "refs": [{"component_ref": ref, "pin": pin.number, "net": net}],
                            "message": f"El pin {pin.number} ({ref}, rol reset_enable) está unido directamente a GND. El chip permanecerá en reset permanente.",
                            "suggested_fix": {
                                "action": "rewire_pin",
                                "details": {"hint": "Unir el pin EN a 3.3V mediante resistencia de pull-up 10k."}
                            },
                            "confidence": 1.0
                        })
                        continue

                    # Check pull-up resistor connection to power rail
                    has_pullup = False
                    for conn_ref, conn_pin in model.nets.get(net, []):
                        if conn_ref == ref:
                            continue
                        target_comp = model.components.get(conn_ref)
                        if target_comp and target_comp.kind == "resistor":
                            # Check other pin of resistor
                            other_pin = [p for p in target_comp.pins if p.number != conn_pin]
                            if other_pin and other_pin[0].net in _POWER_ALIASES:
                                has_pullup = True
                                break

                    if not has_pullup:
                        findings.append({
                            "rule_id": "schematic.power_on_reset.en_pullup",
                            "domain": "schematic",
                            "severity": "critical",
                            "refs": [{"component_ref": ref, "pin": pin.number, "net": net}],
                            "message": f"El pin {pin.number} ({ref}, rol reset_enable) no posee resistencia de pull-up a 3.3V.",
                            "suggested_fix": {
                                "action": "add_component",
                                "details": {"etype": "R", "value": "10k", "n1": net, "n2": "3.3V"}
                            },
                            "confidence": 1.0
                        })

        return findings

    def _check_i2c_pullups(self, model: NeutralCircuit) -> List[Dict[str, Any]]:
        findings = []
        checked_nets: Set[str] = set()

        for ref, comp in model.components.items():
            for pin in comp.pins:
                if pin.role in ["i2c_sda", "i2c_scl"]:
                    net = pin.net
                    if net in checked_nets:
                        continue
                    checked_nets.add(net)

                    # Check direct or resistive connection to ground
                    is_grounded_direct = net in _GROUND_ALIASES
                    pulled_down_resistor = None

                    for conn_ref, conn_pin in model.nets.get(net, []):
                        if conn_ref == ref:
                            continue
                        target_comp = model.components.get(conn_ref)
                        if target_comp and target_comp.kind == "resistor":
                            other_pin = [p for p in target_comp.pins if p.number != conn_pin]
                            if other_pin and other_pin[0].net in _GROUND_ALIASES:
                                pulled_down_resistor = conn_ref
                                break

                    if is_grounded_direct or pulled_down_resistor:
                        culprit = f"vía {pulled_down_resistor}" if pulled_down_resistor else "directamente"
                        findings.append({
                            "rule_id": "schematic.i2c_bus.pullup_to_power_rail",
                            "domain": "schematic",
                            "severity": "critical",
                            "refs": [{"component_ref": ref, "pin": pin.number, "net": net}],
                            "message": f"La línea I2C {pin.role} ({net}) está conectada a GND ({culprit}), provocando bloqueo del bus.",
                            "suggested_fix": {
                                "action": "rewire_pin",
                                "details": {"hint": "Desconectar de GND y conectar a 3.3V mediante resistencia de 4.7k."}
                            },
                            "confidence": 1.0
                        })
                        continue

                    # Check for pull-up resistor to power rail
                    has_pullup = False
                    pullup_res_ref = None
                    for conn_ref, conn_pin in model.nets.get(net, []):
                        if conn_ref == ref:
                            continue
                        target_comp = model.components.get(conn_ref)
                        if target_comp and target_comp.kind == "resistor":
                            other_pin = [p for p in target_comp.pins if p.number != conn_pin]
                            if other_pin and other_pin[0].net in _POWER_ALIASES:
                                has_pullup = True
                                pullup_res_ref = conn_ref
                                # Check value
                                if target_comp.numeric_value and (target_comp.numeric_value < 1000 or target_comp.numeric_value > 10000):
                                    findings.append({
                                        "rule_id": "schematic.i2c_bus.pullup_to_power_rail",
                                        "domain": "schematic",
                                        "severity": "warning",
                                        "refs": [{"component_ref": conn_ref, "net": net}],
                                        "message": f"El valor de pull-up en {conn_ref} ({target_comp.part_value}) está fuera del rango estándar (2.2k - 10k).",
                                        "suggested_fix": {
                                            "action": "change_value",
                                            "details": {"value": "4.7k"}
                                        },
                                        "confidence": 1.0
                                    })
                                break

                    if not has_pullup:
                        findings.append({
                            "rule_id": "schematic.i2c_bus.pullup_to_power_rail",
                            "domain": "schematic",
                            "severity": "critical",
                            "refs": [{"component_ref": ref, "pin": pin.number, "net": net}],
                            "message": f"La línea I2C ({net}) carece de resistencia de pull-up a alimentación.",
                            "suggested_fix": {
                                "action": "add_component",
                                "details": {"etype": "R", "value": "4.7k", "n1": net, "n2": "3.3V"}
                            },
                            "confidence": 1.0
                        })

        return findings

    def _check_boot_straps(self, model: NeutralCircuit) -> List[Dict[str, Any]]:
        findings = []
        for ref, comp in model.components.items():
            for pin in comp.pins:
                if pin.role == "boot_strap":
                    net = pin.net
                    # Check if permanently shorted to ground without switch
                    conns = model.nets.get(net, [])
                    has_switch = any(model.components.get(cr, NeutralComponent("", "", "", "")).kind == "switch" for cr, cp in conns)
                    is_grounded = net in _GROUND_ALIASES

                    if is_grounded and not has_switch:
                        findings.append({
                            "rule_id": "schematic.mcu.boot_strap_pins",
                            "domain": "schematic",
                            "severity": "critical",
                            "refs": [{"component_ref": ref, "pin": pin.number, "net": net}],
                            "message": f"El pin de strapping {pin.number} ({ref}) está cortocircuitado permanentemente a GND sin pulsador.",
                            "suggested_fix": {
                                "action": "rewire_pin",
                                "details": {"hint": "Interpolar un pulsador momentáneo entre el pin y GND."}
                            },
                            "confidence": 1.0
                        })

        return findings

    def _check_decoupling(self, model: NeutralCircuit) -> List[Dict[str, Any]]:
        findings = []
        for ref, comp in model.components.items():
            if comp.kind in ["mcu", "ic"]:
                # Find power pins
                power_pins = [p for p in comp.pins if p.role == "power_in"]
                if not power_pins:
                    continue

                for p_pin in power_pins:
                    p_net = p_pin.net
                    # Check if a capacitor exists on this net going to GND
                    has_cap = False
                    for conn_ref, conn_pin in model.nets.get(p_net, []):
                        if conn_ref == ref:
                            continue
                        target = model.components.get(conn_ref)
                        if target and target.kind == "capacitor":
                            other = [p for p in target.pins if p.number != conn_pin]
                            if other and other[0].net in _GROUND_ALIASES:
                                has_cap = True
                                break

                    if not has_cap:
                        findings.append({
                            "rule_id": "ee_fundamentals.decoupling.per_ic_100nf",
                            "domain": "ee_fundamentals",
                            "severity": "warning",
                            "refs": [{"component_ref": ref, "pin": p_pin.number, "net": p_net}],
                            "message": f"El componente {ref} no posee condensador de desacoplo de alta frecuencia en el rail {p_net}.",
                            "suggested_fix": {
                                "action": "add_component",
                                "details": {"etype": "C", "value": "100nF", "n1": p_net, "n2": "GND"}
                            },
                            "confidence": 1.0
                        })

        return findings
