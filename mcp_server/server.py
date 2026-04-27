"""
mcp/server.py
=============
PulseLab Forge — MCP Server (FastMCP)

Expone todas las capacidades de PulseLab como herramientas MCP,
accesibles por cualquier agente LLM compatible (Claude, GPT-4, etc.)

Transport: stdio (default) — el cliente LLM lanza este script como
           subprocess y se comunica por stdin/stdout en JSON-RPC.
           Para acceso remoto usar: mcp.run(transport="streamable-http")

Integración con Claude Desktop:
    En claude_desktop_config.json:
    {
      "mcpServers": {
        "pulselab": {
          "command": "python",
          "args": ["C:/Users/soyko/Documents/Pulse/mcp/server.py"]
        }
      }
    }

Uso standalone (testing):
    python mcp/server.py
    # Luego: mcp dev mcp/server.py   (MCP Inspector)
"""

from __future__ import annotations
import sys
import json
from pathlib import Path

# Añadir el directorio raíz al path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from mcp.server.fastmcp import FastMCP
    _MCP_OK = True
except ImportError:
    _MCP_OK = False
    print("WARN: mcp package not installed. Run: pip install 'mcp[cli]'", file=sys.stderr)

# Imports del proyecto (lazy para no bloquear si falla)
def _get_rf():
    from core.rf_tools import RFTools
    return RFTools

def _get_db():
    from core.component_db import ComponentDB
    return ComponentDB()

def _get_kb():
    from knowledge.rag_engine import ElectronicsKnowledgeBase
    return ElectronicsKnowledgeBase()

def _get_bridge():
    from bridge.kicad_bridge import KiCadBridge
    return KiCadBridge()

def create_circuit_json(components: list[dict]) -> dict:
    """
    Crea un circuito desde una lista de componentes.

    Args:
        components: Lista de dicts con keys:
            - etype:  Tipo ("R", "C", "L", "V", "S", "GND")
            - value:  Valor numérico (Ω, F, H, V)
            - n1:     Nodo terminal 1 (string)
            - n2:     Nodo terminal 2 (string)
            - label:  Etiqueta descriptiva (opcional)

    Ejemplo:
        [
            {"etype": "V", "value": 5.0, "n1": "VCC", "n2": "GND", "label": "Fuente 5V"},
            {"etype": "R", "value": 1000, "n1": "VCC", "n2": "OUT", "label": "R1 1kΩ"},
            {"etype": "R", "value": 2200, "n1": "OUT", "n2": "GND", "label": "R2 2.2kΩ"}
        ]

    Returns:
        dict con circuit_json.
    """
    from ui.editor import CircuitGraph
    graph = CircuitGraph()
    for i, c in enumerate(components):
        # Conversión segura de valor (por si la IA devuelve texto)
        val_raw = c.get("value", 0)
        try:
            val_f = float(val_raw)
        except (ValueError, TypeError):
            val_f = 0.0
            
        graph.add(
            etype       = c.get("etype", "R"),
            grid_c      = i * 2,
            grid_r      = 0,
            orientation = "H",
            value       = val_f,
            label       = c.get("label", f"{c.get('etype','?')}{i+1}"),
            n1          = c.get("n1", f"N{i}"),
            n2          = c.get("n2", f"N{i+1}"),
        )
    return {
        "circuit_json": json.dumps(graph.to_json()),
        "components": len(graph.components),
        "nodes": graph.all_nodes,
    }


# ─── FastMCP Server ──────────────────────────────────────────────────────────

if _MCP_OK:
    mcp = FastMCP("PulseLab Forge")
    mcp.tool()(create_circuit_json)

    # ══════════════════════════════════════════════════════════════
    # SIMULATION TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def simulate_circuit(circuit_json: str,
                         duration_ms: float = 10.0,
                         dt_us: float = 100.0) -> dict:
        """
        Ejecuta simulación MNA (Modified Nodal Analysis) sobre un circuito.

        Args:
            circuit_json: Circuito serializado en JSON (formato CircuitGraph.to_json()).
                          Obtén este JSON desde load_preset() o create_circuit_json().
            duration_ms:  Duración de la simulación (milisegundos). Default: 10ms.
            dt_us:        Paso de tiempo (microsegundos). Default: 100µs.
                          Usar dt más pequeño para circuitos de alta frecuencia.

        Returns:
            dict con voltajes por nodo, tiempo simulado, y cualquier error.
        """
        from ui.editor import CircuitGraph, SimulationRunner
        try:
            data  = json.loads(circuit_json)
            graph = CircuitGraph.from_json(data)
            runner = SimulationRunner()
            runner._dt_idx = 0  # start with 1ms

            # Ajustar dt
            dt_s = dt_us * 1e-6
            runner.sim = None
            if not runner.load(graph):
                return {"error": runner.error_msg, "voltages": {}}
            runner.sim.set_dt(dt_s)

            steps = int((duration_ms * 1e-3) / dt_s)
            for _ in range(min(steps, 10_000)):
                runner.step()

            voltages = {n: round(runner.get_voltage(n), 6)
                        for n in graph.all_nodes + ["GND"]}

            return {
                "success": True,
                "sim_time_ms": round(runner.sim_time * 1000, 4),
                "voltages": voltages,
                "nodes": list(voltages.keys()),
                "dt_us": dt_us,
                "steps_executed": min(steps, 10_000),
            }
        except Exception as e:
            return {"error": str(e), "voltages": {}}

    @mcp.tool()
    def load_preset(name: str) -> dict:
        """
        Carga un preset de circuito predefinido.

        Args:
            name: Nombre del preset. Opciones: "emp_pfn", "basic_rc", "rlc"

        Returns:
            dict con circuit_json listo para simulate_circuit() o export_to_kicad().
        """
        import importlib
        try:
            mod = importlib.import_module(f"presets.{name}")
            graph = mod.load()
            return {
                "name": name,
                "circuit_json": json.dumps(graph.to_json()),
                "components": len(graph.components),
                "nodes": graph.all_nodes,
            }
        except ImportError:
            return {"error": f"Preset '{name}' no encontrado. Opciones: emp_pfn, basic_rc, rlc"}
        except Exception as e:
            return {"error": str(e)}


    @mcp.tool()
    def generate_circuit_from_text(description: str) -> dict:
        """
        Genera una topología de circuito a partir de una descripción en lenguaje natural.
        Utiliza el agente LLM entrenado (CircuitSynthesizer).

        Args:
            description: Descripción del circuito. Ej: "Filtro RC pasabajos de 1k y 1uF"

        Returns:
            dict con circuit_json o mensaje de error.
        """
        from knowledge.circuit_synthesizer import CircuitSynthesizer
        synth = CircuitSynthesizer()
        res = synth.generate_circuit_json(description)
        if "error" in res:
            return res
            
        return create_circuit_json(res["components"])

    # ══════════════════════════════════════════════════════════════
    # RF / IMPEDANCE TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def calculate_microstrip_impedance(
        trace_width_mm: float,
        substrate_height_mm: float,
        dielectric_constant: float,
        copper_thickness_mm: float = 0.035,
        frequency_ghz: float = 1.0,
    ) -> dict:
        """
        Calcula impedancia característica Z₀ de línea microstrip.

        Usa el modelo Hammerstad-Jensen (IEEE MTT-S 1980), referenciado en
        Pozar "Microwave Engineering" 4th ed., §3.8.

        Args:
            trace_width_mm:      Ancho de pista (mm).
            substrate_height_mm: Alto del substrato dieléctrico (mm).
            dielectric_constant: εr del substrato (FR4 ≈ 4.4, Rogers4003 ≈ 3.55).
            copper_thickness_mm: Grosor del cobre (mm). Default = 0.035mm (1oz Cu).
            frequency_ghz:       Frecuencia para cálculo de λ. Default = 1.0 GHz.

        Returns:
            dict con Z0 (Ω), εeff, velocidad de fase, λ_mm, pérdida conductora.

        Ejemplos típicos (FR4, h=1.6mm, 1oz Cu):
            50Ω → W ≈ 3.0mm
            75Ω → W ≈ 1.5mm
            100Ω → W ≈ 0.7mm
        """
        from core.rf_tools import microstrip_impedance
        return microstrip_impedance(
            w_mm=trace_width_mm,
            h_mm=substrate_height_mm,
            er=dielectric_constant,
            t_mm=copper_thickness_mm,
            freq_ghz=frequency_ghz,
        )

    @mcp.tool()
    def calculate_trace_width_for_impedance(
        target_impedance_ohm: float,
        substrate_height_mm: float,
        dielectric_constant: float,
        copper_thickness_mm: float = 0.035,
    ) -> dict:
        """
        Calcula el ancho de pista necesario para una impedancia Z₀ objetivo.

        Args:
            target_impedance_ohm: Impedancia objetivo (Ω). Típico: 50Ω, 75Ω.
            substrate_height_mm:  Alto del substrato (mm). FR4 estándar: 1.6mm.
            dielectric_constant:  εr. FR4: 4.4, Rogers4003C: 3.55, PTFE: 2.2.
            copper_thickness_mm:  Grosor cobre. 1oz = 0.035mm, 2oz = 0.070mm.

        Returns:
            dict con W_mm (ancho), verificación Z₀, error porcentual.
        """
        from core.rf_tools import microstrip_width_for_impedance
        return microstrip_width_for_impedance(
            Z0_target=target_impedance_ohm,
            h_mm=substrate_height_mm,
            er=dielectric_constant,
            t_mm=copper_thickness_mm,
        )

    @mcp.tool()
    def design_matching_network(
        z_source_real: float,
        z_source_imag: float,
        z_load_real: float,
        z_load_imag: float,
        frequency_mhz: float,
    ) -> dict:
        """
        Diseña una red L de adaptación de impedancias.

        Calcula el valor de los dos componentes reactivos (L o C) necesarios
        para adaptar Z_source → Z_load a la frecuencia dada.
        Ref: Pozar §5.1.

        Args:
            z_source_real: Parte real de la impedancia de fuente (Ω).
            z_source_imag: Parte imaginaria de Zs (Ω). 0 para resistencia pura.
            z_load_real:   Parte real de la impedancia de carga (Ω).
            z_load_imag:   Parte imaginaria de Zl (Ω).
            frequency_mhz: Frecuencia de trabajo (MHz).

        Returns:
            dict con dos soluciones (topología serie-shunt y shunt-serie),
            valores de L (nH) o C (pF), y factor Q de la red.

        Ejemplo: adaptar 50Ω → 200Ω a 100MHz
            → Q = sqrt(200/50 - 1) = sqrt(3) ≈ 1.73
            → Solución 1: L série ≈ 138nH, C shunt ≈ 87pF
        """
        from core.rf_tools import matching_network_L
        return matching_network_L(
            z_source  = complex(z_source_real, z_source_imag),
            z_load    = complex(z_load_real, z_load_imag),
            freq_mhz  = frequency_mhz,
        )

    @mcp.tool()
    def calculate_trace_current_capacity(
        trace_width_mm: float,
        copper_oz: float = 1.0,
        temp_rise_c: float = 10.0,
        layer: str = "external",
    ) -> dict:
        """
        Calcula corriente máxima admisible para una pista según IPC-2221B.

        Ref: IPC-2221B §6.2, Chart 6-2.

        Args:
            trace_width_mm: Ancho de pista (mm).
            copper_oz:      Peso de cobre (oz). 1oz = 35µm, 2oz = 70µm.
            temp_rise_c:    Elevación de temperatura admisible (°C). Típico: 10°C.
            layer:          "external" (exterior) o "internal" (enterrada).

        Returns:
            dict con corriente máxima (A) y resistencia lineal.
        """
        from core.rf_tools import trace_width_ipc2221
        # Invierte la fórmula: dado W, busca I
        # I = K × ΔT^0.44 × A^0.725, donde A = W_mils × t_mils
        K = 0.048 if layer == "external" else 0.024
        t_mils = copper_oz * 1.378
        w_mils = trace_width_mm / 0.0254
        A_mils2 = w_mils * t_mils
        I_max = K * (temp_rise_c ** 0.44) * (A_mils2 ** 0.725)
        rho_cu = 1.72e-8
        A_m2   = A_mils2 * (25.4e-6) ** 2
        R_pm   = rho_cu / A_m2 if A_m2 > 0 else float('inf')
        return {
            "I_max_A": round(I_max, 3),
            "trace_width_mm": trace_width_mm,
            "resistance_ohm_per_m": round(R_pm, 4),
            "copper_oz": copper_oz,
            "temp_rise_c": temp_rise_c,
            "layer": layer,
            "ref": "IPC-2221B §6.2",
        }

    @mcp.tool()
    def calculate_minimum_trace_width(
        current_a: float,
        copper_oz: float = 1.0,
        temp_rise_c: float = 10.0,
        layer: str = "external",
    ) -> dict:
        """
        Calcula ancho mínimo de pista para una corriente dada (IPC-2221B).

        Args:
            current_a:   Corriente máxima a conducir (A).
            copper_oz:   Peso de cobre (oz). Default 1oz (35µm).
            temp_rise_c: Elevación temperatura máxima (°C). Default 10°C.
            layer:       "external" o "internal".

        Returns:
            dict con W_mm mínimo y resistencia de la pista.
        """
        from core.rf_tools import trace_width_ipc2221
        return trace_width_ipc2221(current_a=current_a,
                                    copper_oz=copper_oz,
                                    temp_rise_c=temp_rise_c,
                                    layer=layer)

    # ══════════════════════════════════════════════════════════════
    # KICAD / MANUFACTURING TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def export_to_kicad(circuit_json: str,
                        output_dir: str = "output",
                        project_name: str = "design") -> dict:
        """
        Exporta un circuito a formato KiCad (netlist + SKiDL script + BOM).

        Genera:
          - <name>.net   → Netlist KiCad (importable en PCBNEW)
          - <name>_skidl.py → Script Python SKiDL equivalente
          - <name>_bom.csv  → Bill of Materials

        Args:
            circuit_json: JSON del circuito (de load_preset() o create_circuit_json()).
            output_dir:   Directorio de salida.
            project_name: Nombre del proyecto (sin extensión).

        Returns:
            dict con paths de archivos generados.
        """
        from ui.editor import CircuitGraph
        from bridge.kicad_bridge import KiCadBridge
        try:
            graph  = CircuitGraph.from_json(json.loads(circuit_json))
            bridge = KiCadBridge()
            return bridge.generate_netlist(graph, Path(output_dir), project_name)
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def generate_gerbers(kicad_pcb_path: str,
                         output_dir: str = "gerbers") -> dict:
        """
        Genera archivos Gerber, Excellon drill y CPL desde un .kicad_pcb.

        IMPORTANTE: Requiere KiCad 8+ instalado.
        El .kicad_pcb se genera abriendo el .net en KiCad PCBNEW,
        haciendo el layout manual, y guardando el archivo.

        Args:
            kicad_pcb_path: Ruta absoluta al archivo .kicad_pcb.
            output_dir:     Directorio para los archivos de fabricación.

        Returns:
            dict con lista de archivos generados y estado.
        """
        from bridge.gerber_export import generate_all_manufacturing_files
        from bridge.kicad_bridge import KiCadBridge
        bridge = KiCadBridge()
        if not bridge.available:
            return {
                "error": "KiCad no encontrado en el sistema",
                "hint": f"Instala KiCad 8+ desde https://kicad.org — Status: {bridge.status()}"
            }
        return generate_all_manufacturing_files(
            bridge._cli, Path(kicad_pcb_path), Path(output_dir)
        )

    @mcp.tool()
    def kicad_status() -> dict:
        """
        Verifica si KiCad está instalado y devuelve información del sistema.

        Returns:
            dict con available (bool), versión, y rutas de librerías.
        """
        from bridge.kicad_bridge import KiCadBridge
        return KiCadBridge().status()

    @mcp.tool()
    def generate_bom(circuit_json: str, fmt: str = "csv") -> dict:
        """
        Genera Bill of Materials desde un circuito.

        Args:
            circuit_json: JSON del circuito.
            fmt:          Formato: "csv", "json", o "text".

        Returns:
            dict con content (string del BOM) y rows (lista de componentes).
        """
        from ui.editor import CircuitGraph
        from bridge.bom_generator import generate_bom as _bom
        try:
            graph = CircuitGraph.from_json(json.loads(circuit_json))
            db    = _get_db()
            return _bom(graph, db, fmt)
        except Exception as e:
            return {"error": str(e)}

    # ══════════════════════════════════════════════════════════════
    # COMPONENT DATABASE TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def search_component(query: str,
                         category: str = "",
                         top_k: int = 5) -> list:
        """
        Busca componentes en la base de datos de PulseLab.

        Args:
            query:    Búsqueda en texto libre. Ejemplos:
                      "MCU con WiFi y BLE"
                      "regulador LDO 3.3V 1A"
                      "op-amp bajo ruido"
            category: Filtro de categoría: "MCU", "PMIC", "Amplifier", "Timer", "Interface", "".
            top_k:    Número máximo de resultados (default: 5).

        Returns:
            Lista de componentes con id, category, manufacturer, params, notes, footprint.
        """
        db = _get_db()
        return db.search(query, top_k=top_k,
                         category=category if category else None)

    @mcp.tool()
    def get_component_details(component_id: str) -> dict:
        """
        Obtiene información completa de un componente por su ID.

        Args:
            component_id: ID del componente. Ejemplos: "ESP32-WROOM-32",
                          "ATmega328P", "RP2040", "AMS1117-3.3".

        Returns:
            dict completo con pins, params, support_circuits, datasheet.
        """
        db = _get_db()
        comp = db.get(component_id)
        if comp:
            return comp.to_dict()
        return {"error": f"Componente '{component_id}' no encontrado",
                "available": [c.id for c in db.all()]}

    @mcp.tool()
    def get_mcu_support_circuit(mcu_id: str) -> dict:
        """
        Devuelve el circuito de soporte mínimo para un MCU
        (decoupling, cristal, reset, programación).

        Args:
            mcu_id: ID del MCU. Ejemplos: "ATmega328P", "ESP32-WROOM-32",
                    "STM32F103C8T6", "RP2040", "ESP8266-ESP-12F".

        Returns:
            dict con circuito de soporte mínimo por categoría.
        """
        db   = _get_db()
        comp = db.get(mcu_id)
        if not comp:
            return {"error": f"MCU '{mcu_id}' no encontrado"}
        return {
            "mcu_id": mcu_id,
            "vcc": f"{comp.params.get('typical_vcc_v', '?')}V",
            "max_freq_mhz": comp.params.get("max_freq_mhz"),
            "support_circuits": comp.support_circuits,
            "notes": comp.notes,
            "datasheet": comp.datasheet,
            "kicad_symbol": comp.kicad_symbol,
            "kicad_footprint": comp.kicad_footprint,
        }

    @mcp.tool()
    def filter_components_by_params(
        min_adc_bits: int = 0,
        min_uart: int = 0,
        min_spi: int = 0,
        min_flash_kb: int = 0,
        has_wifi: bool = False,
        has_bluetooth: bool = False,
        max_vcc_v: float = 100.0,
        category: str = "MCU",
    ) -> list:
        """
        Filtra componentes por parámetros técnicos específicos.

        Útil para seleccionar el MCU correcto según requisitos del proyecto.

        Args:
            min_adc_bits:   Resolución mínima del ADC (bits). 0 = sin filtro.
            min_uart:       Número mínimo de periféricos UART.
            min_spi:        Número mínimo de periféricos SPI.
            min_flash_kb:   Flash mínima (kB). 0 = sin filtro.
            has_wifi:       True = requiere WiFi integrado.
            has_bluetooth:  True = requiere BT/BLE integrado.
            max_vcc_v:      Voltaje de alimentación máximo aceptable.
            category:       Categoría a buscar. Default "MCU".

        Returns:
            Lista de componentes que cumplen todos los requisitos.
        """
        db = _get_db()
        kwargs: dict = {}
        if min_adc_bits > 0:
            kwargs["adc_bits__gte"] = min_adc_bits
        if min_uart > 0:
            kwargs["uart__gte"] = min_uart
        if min_spi > 0:
            kwargs["spi__gte"] = min_spi
        if min_flash_kb > 0:
            kwargs["flash_kb__gte"] = min_flash_kb

        results = db.filter(**kwargs)
        # Filtros booleanos (no soportados por filter())
        if has_wifi:
            results = [c for c in results if c.params.get("wifi")]
        if has_bluetooth:
            results = [c for c in results
                       if c.params.get("bluetooth") or c.params.get("bt_version")]
        if category:
            results = [c for c in results
                       if c.category.lower() == category.lower()]

        return [{"id": c.id, "summary": c.summary(),
                 "params": c.params, "footprint": c.kicad_footprint}
                for c in results]

    # ══════════════════════════════════════════════════════════════
    # KNOWLEDGE / RAG TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def search_electronics_knowledge(
        query: str,
        top_k: int = 5,
        knowledge_type: str = "",
    ) -> list:
        """
        Búsqueda semántica en la base de conocimiento de electrónica.

        Cubre: reglas IPC-2221, especificaciones de componentes, y cualquier
        texto adicional ingresado con ingest_knowledge_text().

        Args:
            query:          Consulta en lenguaje natural (español o inglés).
                            Ejemplos:
                            "clearance mínimo para 220V en placa al aire"
                            "decoupling capacitor ESP32"
                            "ancho de pista para 5A"
            top_k:          Número de resultados. Default: 5.
            knowledge_type: Filtrar por tipo: "component", "design_rule",
                            "support_circuit", "note", "". Default: "" (todos).

        Returns:
            Lista de {source, type, score, data, excerpt}.
        """
        kb = _get_kb()
        return kb.query(query, top_k=top_k,
                         chunk_type=knowledge_type if knowledge_type else None)

    @mcp.tool()
    def get_design_rules(
        voltage_v: float = 0.0,
        current_a: float = 0.0,
        category: str = "all",
    ) -> dict:
        """
        Devuelve reglas de diseño IPC-2221B aplicables a los parámetros dados.

        Args:
            voltage_v: Voltaje máximo entre conductores (V). 0 = no aplica.
            current_a: Corriente máxima (A). 0 = no aplica.
            category:  "clearance", "trace_width", "via", "board_edge", "all".

        Returns:
            dict con clearance_mm (por configuración de capa),
            trace_width_mm, via_rules, etc.

        Ejemplos:
            voltage_v=48.0, category="clearance"
              → Distancias de aislamiento para 48V (IPC-2221B)
            current_a=3.0, category="trace_width"
              → Ancho mínimo de pista para 3A
        """
        kb = _get_kb()
        return kb.get_design_rules(
            voltage_v=voltage_v if voltage_v > 0 else None,
            current_a=current_a if current_a > 0 else None,
            category=category,
        )

    @mcp.tool()
    def ingest_knowledge_text(
        text: str,
        source: str = "user_note",
    ) -> dict:
        """
        Añade texto libre a la base de conocimiento RAG.

        Útil para ingestar application notes, fragmentos de datasheet,
        o notas de diseño propias. El texto estará disponible en futuras
        consultas de search_electronics_knowledge().

        Args:
            text:   Texto a indexar (cualquier longitud).
            source: Identificador de fuente (para trazabilidad).

        Returns:
            dict con número de chunks indexados.
        """
        kb = _get_kb()
        n = kb.ingest_text(text, source=source)
        return {
            "indexed_chunks": n,
            "source": source,
            "total_chunks": kb.stats()["total_chunks"],
        }

    @mcp.tool()
    def knowledge_base_stats() -> dict:
        """
        Devuelve estadísticas de la base de conocimiento.

        Returns:
            dict con número de chunks por tipo, estado del vectorizador.
        """
        return _get_kb().stats()

    # ══════════════════════════════════════════════════════════════
    # PCB LAYOUT TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def create_pcb_layout(
        board_width_mm: float,
        board_height_mm: float,
        components: list[dict],
        traces: list[dict] = [],
        project_name: str = "PulseLab Design",
        corner_radius_mm: float = 1.5,
        trace_width_mm: float = 0.25,
        mounting_holes: bool = True,
        output_dir: str = "output",
    ) -> dict:
        """
        Crea un PCB completo con componentes posicionados espacialmente.

        ESTE ES EL CORAZÓN DEL DISEÑO: produce un .kicad_pcb listo para
        fabricar o para abrir en KiCad PCBNEW.

        Args:
            board_width_mm:  Ancho de la placa (mm). Ej: 50.
            board_height_mm: Alto de la placa (mm). Ej: 30.
            components: Lista de dicts, cada uno define un componente:
                {
                    "type": "resistor"|"capacitor"|"inductor"|"pin_header"|"dip_ic"|"raw_footprint",
                    "ref": "R1",
                    "value": "10k",
                    "x": 15.0,        // posición X en mm
                    "y": 10.0,        // posición Y en mm
                    "rotation": 0,    // grados (0, 90, 180, 270)
                    "net1": "VCC",    // nombre de la red (pad 1)
                    "net2": "OUT",    // nombre de la red (pad 2)
                    "package": "0805" // solo para R/C/L: "0402","0603","0805","1206"
                    "pins": 4,        // solo para pin_header/dip_ic
                    "lib": "Package_QFP",          // solo para raw_footprint
                    "name": "LQFP-48_7x7mm_P0.5mm" // solo para raw_footprint
                }
            traces: Lista de conexiones entre pads:
                [
                    {"from_ref": "R1", "from_pad": "2",
                     "to_ref": "C1", "to_pad": "1",
                     "net": "OUT", "width": 0.3}
                ]
            project_name:    Nombre del proyecto.
            corner_radius_mm: Radio de esquinas de la placa.
            trace_width_mm:  Ancho de pista por defecto.
            mounting_holes:  True = añadir M3 en las 4 esquinas.
            output_dir:      Directorio de salida.

        Returns:
            dict con ruta del .kicad_pcb, stats, y lista de archivos.

        Ejemplo completo (divisor de tensión):
            components=[
                {"type":"pin_header","ref":"J1","value":"IO","x":3,"y":7,"pins":3},
                {"type":"resistor","ref":"R1","value":"10k","x":12,"y":5,
                 "net1":"VIN","net2":"VOUT"},
                {"type":"resistor","ref":"R2","value":"22k","x":12,"y":10,
                 "net1":"VOUT","net2":"GND"}
            ],
            traces=[
                {"from_ref":"R1","from_pad":"2","to_ref":"R2","to_pad":"1",
                 "net":"VOUT","width":0.3}
            ]
        """
        from bridge.pcb_layout import PCBLayout
        try:
            pcb = PCBLayout(
                board_width=board_width_mm,
                board_height=board_height_mm,
                corner_radius=corner_radius_mm,
                trace_width=trace_width_mm,
                project_name=project_name,
            )

            # Mapa ref → footprint para las trazas
            fp_map = {}

            for c in components:
                ctype = c.get("type", "resistor")
                ref   = c.get("ref", "X1")
                value = c.get("value", "?")
                x     = float(c.get("x", 0))
                y     = float(c.get("y", 0))
                rot   = float(c.get("rotation", 0))
                net1  = c.get("net1", "")
                net2  = c.get("net2", "")
                pkg   = c.get("package", "0805")
                pins  = int(c.get("pins", 2))

                if ctype == "resistor":
                    fp = pcb.add_resistor(ref, value, x, y, rot,
                                           net1, net2, pkg)
                elif ctype == "capacitor":
                    fp = pcb.add_capacitor(ref, value, x, y, rot,
                                            net1, net2, pkg)
                elif ctype == "inductor":
                    fp = pcb.add_inductor(ref, value, x, y, rot,
                                           net1, net2, pkg)
                elif ctype == "pin_header":
                    fp = pcb.add_pin_header(ref, pins, x, y, rot, value)
                elif ctype == "dip_ic":
                    fp = pcb.add_dip_ic(ref, pins, x, y, rot, value)
                elif ctype == "raw_footprint":
                    # For raw footprint we expect 'lib' and 'name' in component dict
                    lib = c.get("lib", "Package_QFP")
                    name = c.get("name", "LQFP-48_7x7mm_P0.5mm")
                    fp = pcb.add_raw_footprint(ref, lib, name, x, y, rot, value)
                else:
                    fp = pcb.add_resistor(ref, value, x, y, rot,
                                           net1, net2, pkg)

                fp_map[ref] = fp

            # Trazas
            for t in (traces or []):
                fr = t.get("from_ref", "")
                fp1 = t.get("from_pad", "1")
                tr = t.get("to_ref", "")
                tp1 = t.get("to_pad", "1")
                net = t.get("net", "")
                w   = float(t.get("width", trace_width_mm))

                if fr in fp_map and tr in fp_map:
                    pcb.trace(fp_map[fr], fp1, fp_map[tr], tp1,
                              width=w, net=net)

            if mounting_holes:
                pcb.add_mounting_holes_corners(margin=3.5)

            # Texto
            pcb.add_text(project_name,
                         pcb.board.center_x,
                         pcb.board.origin_y + pcb.board.height_mm + 2.5,
                         size=1.0)

            # Guardar
            safe_name = "".join(c if c.isalnum() or c in "_-" else "_"
                                 for c in project_name)
            out_path = Path(output_dir) / safe_name / "board.kicad_pcb"
            pcb.save(out_path)

            return {
                "success": True,
                "pcb_path": str(out_path),
                "stats": pcb.stats(),
                "open_in_kicad": f"Abre {out_path} en KiCad PCBNEW para ver el diseño.",
                "next_step": "Llama generate_pcb_gerbers() con esta ruta para generar Gerbers.",
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    def generate_pcb_gerbers(
        pcb_path: str,
        output_dir: str = "",
    ) -> dict:
        """
        Genera archivos de fabricación completos desde un .kicad_pcb.

        Produce: Gerbers (11 capas) + Drill (Excellon) + CPL (pick & place).
        Estos archivos se pueden subir directamente a JLCPCB, PCBWay, etc.

        Args:
            pcb_path:   Ruta al archivo .kicad_pcb (de create_pcb_layout()).
            output_dir: Directorio para archivos de fabricación.
                        Default: misma carpeta que el PCB + "/manufacturing".

        Returns:
            dict con lista de archivos generados, status, y resumen.
        """
        from bridge.kicad_bridge import KiCadBridge
        from bridge.gerber_export import generate_all_manufacturing_files

        bridge = KiCadBridge()
        if not bridge.available:
            return {
                "error": "KiCad no disponible",
                "hint": "Instala KiCad 8+ desde https://kicad.org",
                "status": bridge.status(),
            }

        pcb = Path(pcb_path)
        if not pcb.exists():
            return {"error": f"Archivo no encontrado: {pcb_path}"}

        pcb = Path(pcb_path)
        if not pcb.exists():
            return {"error": f"Archivo no encontrado: {pcb_path}"}

        out = Path(output_dir) if output_dir else pcb.parent / "manufacturing"
        return generate_all_manufacturing_files(bridge._cli, pcb, out)

    @mcp.tool()
    def generate_pcb_enclosure(
        board_width_mm: float,
        board_height_mm: float,
        project_name: str = "PulseLab Design",
        output_dir: str = "output",
    ) -> dict:
        """
        Genera geometría 3D programática (OpenSCAD) para una caja envolvente
        basada en el tamaño de una placa (PCB) y la posición de sus agujeros.

        Args:
            board_width_mm: Ancho de la placa a envolver.
            board_height_mm: Alto de la placa a envolver.
            project_name: Nombre del proyecto (para nombrar el archivo).
            output_dir: Directorio de salida.

        Returns:
            dict con la ruta generada del modelo SCAD.
        """
        from bridge.pcb_layout import PCBLayout
        # Creamos un layout virtual solo con las medidas base para generar la caja
        pcb = PCBLayout(board_width=board_width_mm, board_height=board_height_mm, project_name=project_name)
        pcb.add_mounting_holes_corners(margin=3.5)
        
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in project_name)
        out_p = Path(output_dir) / safe_name / "enclosures"
        
        return pcb.export_enclosure(out_p)

    @mcp.tool()
    def review_layout(
        board_width_mm: float,
        board_height_mm: float,
        components: list[dict],
        traces: list[dict] = [],
        trace_width_mm: float = 0.25,
    ) -> dict:
        """
        Ejecuta una auditoría de diseño (DRC) basada en IPC-2221 para encontrar
        problemas de clearance o manufactura en un PCB. 
        Utiliza los mismos argumentos de 'create_pcb_layout' para reconstruir y auditar la placa.

        Args:
            board_width_mm, board_height_mm: Dimensiones
            components, traces: Diccionarios de diseño (igual que en create_pcb_layout)
            trace_width_mm: Ancho de pista (para math de choques)

        Returns:
            dict con el reporte de texto formateado generado por el revisor IA.
        """
        from bridge.pcb_layout import PCBLayout
        from knowledge.layout_reviewer import LayoutReviewer
        
        pcb = PCBLayout(board_width=board_width_mm, board_height=board_height_mm, trace_width=trace_width_mm)
        fp_map = {}
        for c in components:
            ctype = c.get("type", "resistor")
            ref   = c.get("ref", "X1")
            val   = c.get("value", "")
            x, y  = float(c.get("x", 0)), float(c.get("y", 0))
            rot   = float(c.get("rotation", 0))
            if ctype == "resistor":
                fp = pcb.add_resistor(ref, val, x, y, rot, c.get("net1",""), c.get("net2",""), c.get("package","0805"))
            elif ctype == "pin_header":
                fp = pcb.add_pin_header(ref, int(c.get("pins",2)), x, y, rot, val)
            elif ctype == "dip_ic":
                fp = pcb.add_dip_ic(ref, int(c.get("pins",8)), x, y, rot, val)
            else:
                fp = pcb.add_resistor(ref, val, x, y, rot, c.get("net1",""), c.get("net2",""), c.get("package","0805"))
            fp_map[ref] = fp

        for t in traces:
            fr, tr = t.get("from_ref", ""), t.get("to_ref", "")
            if fr in fp_map and tr in fp_map:
                pcb.trace(fp_map[fr], t.get("from_pad","1"), fp_map[tr], t.get("to_pad","1"), width=float(t.get("width", trace_width_mm)), net=t.get("net",""))
        
        reviewer = LayoutReviewer(pcb)
        res_dict = reviewer.audit()
        report = reviewer.generate_report()
        
        return {
            "passed": res_dict["passed"],
            "critical_issues": len(res_dict["critical_issues"]),
            "report_text": report
        }

    @mcp.tool()
    def list_pcb_footprints() -> dict:
        """
        Lista los footprints y packages disponibles para create_pcb_layout.

        Returns:
            dict con tipos de componentes, packages soportados, y ejemplos.
        """
        return {
            "component_types": {
                "resistor": {
                    "packages": ["0402", "0603", "0805", "1206"],
                    "default": "0805",
                    "pads": 2,
                    "example": {"type":"resistor","ref":"R1","value":"10k",
                                "x":10,"y":5,"net1":"VCC","net2":"OUT"},
                },
                "capacitor": {
                    "packages": ["0402", "0603", "0805", "1206"],
                    "default": "0805",
                    "pads": 2,
                    "example": {"type":"capacitor","ref":"C1","value":"100nF",
                                "x":15,"y":5,"net1":"VCC","net2":"GND"},
                },
                "inductor": {
                    "packages": ["0402", "0603", "0805", "1206"],
                    "default": "0805",
                    "pads": 2,
                },
                "pin_header": {
                    "pins_range": "1-40",
                    "pitch_mm": 2.54,
                    "type": "THT",
                    "example": {"type":"pin_header","ref":"J1","value":"IO",
                                "x":3,"y":5,"pins":4},
                },
                "dip_ic": {
                    "pins_range": "4-40 (par)",
                    "pitch_mm": 2.54,
                    "row_width_mm": 7.62,
                    "type": "THT",
                    "example": {"type":"dip_ic","ref":"U1","value":"NE555",
                                "x":20,"y":15,"pins":8},
                },
            },
            "board_constraints": {
                "min_size_mm": "10x10",
                "max_size_mm": "300x300",
                "trace_width_range_mm": "0.1 - 5.0",
                "default_trace_width_mm": 0.25,
                "corner_radius_mm": "0 - board_size/4",
            },
            "tips": [
                "Coloca componentes con un margen de 3mm desde los bordes",
                "Los pads se numeran '1', '2', etc. desde la izquierda",
                "Para ICs DIP: pin 1 está arriba-izquierda, numeración anti-horaria",
                "Usa net names consistentes: 'VCC', 'GND', 'OUT', 'SDA', etc.",
                "trace_width 0.5mm para alimentación, 0.25mm para señales",
            ],
        }

    # ══════════════════════════════════════════════════════════════
    # UTILITY TOOLS
    # ══════════════════════════════════════════════════════════════

    @mcp.tool()
    def pulselab_status() -> dict:
        """
        Estado general del sistema PulseLab Forge.

        Verifica disponibilidad de: KiCad, SKiDL, scikit-learn,
        base de conocimiento, y base de datos de componentes.

        Returns:
            dict con estado de cada subsistema.
        """
        status: dict = {"name": "PulseLab Forge", "version": "1.0"}

        # KiCad
        from bridge.kicad_bridge import KiCadBridge
        kicad = KiCadBridge().status()
        status["kicad"] = kicad

        # SKiDL
        try:
            import skidl
            status["skidl"] = {"available": True, "version": getattr(skidl, "__version__", "?")}
        except ImportError:
            status["skidl"] = {"available": False, "hint": "pip install skidl"}

        # scikit-learn
        try:
            import sklearn
            status["sklearn"] = {"available": True, "version": sklearn.__version__}
        except ImportError:
            status["sklearn"] = {"available": False, "hint": "pip install scikit-learn"}

        # KB stats
        kb = _get_kb()
        status["knowledge_base"] = kb.stats()

        # Component DB
        db = _get_db()
        status["component_db"] = {"components": len(db.all())}

        return status


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    """Punto de entrada del servidor MCP."""
    if not _MCP_OK:
        print("ERROR: Instala el SDK de MCP: pip install 'mcp[cli]'", file=sys.stderr)
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="PulseLab Forge MCP Server")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "http"],
                        help="Transporte MCP (default: stdio para uso local)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host para HTTP transport")
    parser.add_argument("--port", type=int, default=8080,
                        help="Puerto para HTTP transport")
    args = parser.parse_args()

    if args.transport == "stdio":
        # Modo local: Claude Desktop lo lanza como subprocess
        # Comunicación vía stdin/stdout JSON-RPC
        mcp.run()
    else:
        # Modo HTTP: para acceso remoto o múltiples clientes
        mcp.run(transport="streamable-http",
                host=args.host, port=args.port)


if __name__ == "__main__":
    main()
