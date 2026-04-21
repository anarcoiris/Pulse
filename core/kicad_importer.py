
import re
import os
from pathlib import Path

class KicadImporter:
    """
    Parser ligero de archivos KiCad 8 (S-Expressions) para modo ingestión.
    Extrae componentes y redes para comparativa.
    """
    
    @staticmethod
    def parse_pcb_nets(pcb_path: str) -> dict:
        """Extrae el mapeo de Net ID a Net Name de un .kicad_pcb."""
        if not os.path.exists(pcb_path):
            return {}
        
        with open(pcb_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex para (net 1 "GND")
        nets = {}
        matches = re.finditer(r'\(net\s+(\d+)\s+"([^"]*)"\)', content)
        for m in matches:
            nets[m.group(1)] = m.group(2)
        return nets

    @staticmethod
    def parse_pcb_components(pcb_path: str) -> list:
        """Extrae la lista de componentes (footprints) con su referencia y valor."""
        if not os.path.exists(pcb_path):
            return []
            
        with open(pcb_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Buscar bloques de footprint (empiezan con (footprint "...") y terminan en un balanceado de paréntesis simplificado)
        # KiCad 8 footprints suelen tener (at ...), (property "Reference" ...), etc.
        comps = []
        fp_matches = re.finditer(r'\(footprint\s+"([^"]+)"', content)
        for m in fp_matches:
            start_idx = m.start()
            # Encontrar el cierre del bloque footprint (simplificado: buscar el Reference property cerca)
            # Buscamos la propiedad Reference y Value dentro de los siguientes 500 caracteres
            chunk = content[start_idx:start_idx + 1000]
            ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', chunk)
            val_m = re.search(r'\(property\s+"Value"\s+"([^"]+)"', chunk)
            
            if ref_m and val_m:
                comps.append({
                    'ref': ref_m.group(1),
                    'val': val_m.group(1),
                    'lib': m.group(1)
                })
        return comps

    @staticmethod
    def parse_pcb_connectivity(pcb_path: str) -> dict:
        """Extrae el mapa completo de conectividad: Net -> list of (ref, pad)."""
        if not os.path.exists(pcb_path):
            return {}
            
        with open(pcb_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        nets = KicadImporter.parse_pcb_nets(pcb_path)
        connectivity = {n: [] for n in nets.values()}
        
        # Regex para encontrar pads y sus nets asociados
        # (pad "1" smd rect ... (net 1 "GND") ...)
        # Debemos asociar cada pad con el footprint que lo contiene
        fp_blocks = re.finditer(r'\(footprint\s+"([^"]+)"', content)
        for fp_m in fp_blocks:
            start_idx = fp_m.start()
            # Encontrar el Reference para este footprint
            chunk = content[start_idx:start_idx + 10000] # Chunk grande para capturar todos los pads
            ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', chunk)
            if not ref_m: continue
            ref = ref_m.group(1)
            
            # Buscar pads dentro de este footprint
            # Usamos un scope limitado para no saltar al siguiente footprint
            end_idx = content.find('(footprint', start_idx + 10)
            fp_content = content[start_idx:end_idx] if end_idx > 0 else content[start_idx:]
            
            pad_matches = re.finditer(r'\(pad\s+"([^"]+)"\s+\w+\s+\w+.*?\(net\s+\d+\s+"([^"]+)"\)', fp_content, re.DOTALL)
            for pm in pad_matches:
                p_num = pm.group(1)
                net_name = pm.group(2)
                if net_name in connectivity:
                    connectivity[net_name].append((ref, p_num))
                    
        return connectivity

    @staticmethod
    def parse_schematic_symbols(sch_path: str) -> list:
        """Extrae la lista de símbolos de un archivo .kicad_sch."""
        if not os.path.exists(sch_path):
            return []
            
        with open(sch_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        symbols = []
        # Buscamos (symbol (lib_id "...") (at X Y ...) ... (property "Reference" "..."))
        sym_matches = re.finditer(r'\(symbol\s+\(lib_id\s+"([^"]+)"\)\s+\(at\s+([\d.-]+)\s+([\d.-]+)', content)
        for m in sym_matches:
            lib_id = m.group(1)
            x, y = float(m.group(2)), float(m.group(3))
            
            # Capturamos el contexto del símbolo para buscar sus propiedades
            start_idx = m.start()
            chunk = content[start_idx:start_idx + 2000]
            
            ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', chunk)
            val_m = re.search(r'\(property\s+"Value"\s+"([^"]+)"', chunk)
            
            if ref_m and val_m:
                symbols.append({
                    'ref': ref_m.group(1),
                    'value': val_m.group(1),
                    'lib_id': lib_id,
                    'x': x, 'y': y
                })
        return symbols

    @staticmethod
    def parse_schematic_wires(sch_path: str) -> list:
        """Extrae los hilos (conector visual) de un esquema."""
        if not os.path.exists(sch_path):
            return []
            
        with open(sch_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        wires = []
        # (wire (pts (xy 100 100) (xy 120 100)) (uuid ...))
        matches = re.finditer(r'\(wire\s+\(pts\s+\(xy\s+([\d.-]+)\s+([\d.-]+)\)\s+\(xy\s+([\d.-]+)\s+([\d.-]+)\)\)', content)
        for m in matches:
            wires.append([
                (float(m.group(1)), float(m.group(2))),
                (float(m.group(3)), float(m.group(4)))
            ])
        return wires

    @staticmethod
    def to_circuit_graph(sch_path: str) -> "CircuitGraph":
        """
        Intenta reconstruir un CircuitGraph a partir de un esquema de KiCad.
        Aplica normalización de coordenadas para mapear al grid de PulseLab.
        """
        from ui.editor import CircuitGraph
        graph = CircuitGraph()
        symbols = KicadImporter.parse_schematic_symbols(sch_path)
        
        if not symbols:
            return graph
            
        # 1. Encontrar el centro para normalizar
        min_x = min(s['x'] for s in symbols)
        min_y = min(s['y'] for s in symbols)
        
        # 2. Mapeo a PulseLab Grid
        # KiCad usa coords grandes (mils/mm). Estimamos 1 unit de grid = 1/10" o 50 mils
        SCALE = 50.0 
        
        for s in symbols:
            # Coords relativas y escaladas
            gc = int((s['x'] - min_x) / SCALE) + 5 # +5 offset de margen
            gr = int((s['y'] - min_y) / SCALE) + 5
            
            # Mapeo de tipos
            lib_id = s['lib_id'].lower()
            etype = "R" # default
            if "resistor" in lib_id or ":r" in lib_id: etype = "R"
            elif "capacitor" in lib_id or ":c" in lib_id: etype = "C"
            elif "gnd" in lib_id: etype = "GND"
            elif "battery" in lib_id or "vsource" in lib_id: etype = "V"
            
            # Extraer valor numérico del string
            val_str = s['value'].replace('k', '000').replace('u', 'e-6').replace('n', 'e-9').replace('p', 'e-12')
            try:
                val = float(re.findall(r"[-+]?\d*\.\d+|\d+", val_str)[0])
            except:
                val = 0.0
                
            graph.add(etype, gc, gr, "H", val, s['ref'])
            
        return graph

if __name__ == "__main__":
    # Test con el board recién generado
    path = "output/esp32_v2/pulselab_pcb/board.kicad_pcb"
    nets = KicadImporter.parse_pcb_nets(path)
    comps = KicadImporter.parse_pcb_components(path)
    
    print(f"FACT: Parser de Ingestión activo.")
    print(f"Redes detectadas: {len(nets)}")
    print(f"Componentes detectados: {len(comps)}")
    for c in comps[:3]:
        print(f"  - {c['ref']}: {c['val']}")
