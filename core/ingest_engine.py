
import os
import json
from pathlib import Path
from core.kicad_importer import KicadImporter

class IngestEngine:
    """
    Motor de ingesta masiva y extracción de patrones de diseño.
    Transforma archivos KiCad en conocimiento para el entrenamiento de FORGE.
    """
    
    def __init__(self, reference_dir: str = "data/reference_designs"):
        self.ref_dir = Path(reference_dir)
        self.pattern_db = {
            "mcu_support": {}, # Pattern: MCU -> List of required support components
            "net_styles": {},  # Pattern: Net Name -> Avg track width, etc
        }

    def process_all(self):
        """Escanea el directorio de referencias y extrae patrones."""
        print(f"--- Ingest Engine: Iniciando Proceso Masivo ---")
        pcb_files = list(self.ref_dir.glob("**/*.kicad_pcb"))
        print(f"Detectados {len(pcb_files)} archivos de diseño profesional.")
        
        for pcb in pcb_files:
            self._analyze_design(pcb)
            
        self._save_knowledge()

    def _analyze_design(self, pcb_path: Path):
        print(f"Analizando: {pcb_path.name}...")
        connectivity = KicadImporter.parse_pcb_connectivity(str(pcb_path))
        comps = KicadImporter.parse_pcb_components(str(pcb_path))
        
        # 1. Identificar MCUs y sus componentes de soporte
        for c in comps:
            if "MCU" in c['ref'] or "U" in c['ref']: # Nomenclatura IC estándar
                ref = c['ref']
                val = c['val']
                # Buscar qué redes de poder toca este chip
                power_nets = []
                for net, pads in connectivity.items():
                    if any(p[0] == ref for p in pads):
                        if net.upper() in ("3V3", "VCC", "5V", "VBUS"):
                            power_nets.append(net)
                
                # Para cada red de poder, ver quién más está conectado
                for p_net in power_nets:
                    support = []
                    for other_ref, pad in connectivity[p_net]:
                        if other_ref != ref:
                            # Encontrar valor de este componente support
                            other_val = next((oc['val'] for oc in comps if oc['ref'] == other_ref), "unknown")
                            support.append({'ref': other_ref, 'val': other_val})
                    
                    if val not in self.pattern_db["mcu_support"]:
                        self.pattern_db["mcu_support"][val] = []
                    self.pattern_db["mcu_support"][val].append({
                        "net": p_net,
                        "support": support
                    })

    def _save_knowledge(self):
        out_path = "knowledge/pattern_library.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(self.pattern_db, f, indent=2)
        print(f"FACT 9: Ingesta completada. Patrones guardados en {out_path}")

if __name__ == "__main__":
    engine = IngestEngine()
    # Mocking ingestion with our own success design for the first run
    # (En la práctica aquí el crawler habría descargado SparkFun)
    engine.ref_dir = Path("output/esp32_v2/pulselab_pcb")
    engine.process_all()
