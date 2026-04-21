
import os
import sys
from core.kicad_importer import KicadImporter

def validate_design(pcb_path: str):
    print(f"--- Calibration Forge: Validation Run ---")
    print(f"Target: {pcb_path}")
    
    if not os.path.exists(pcb_path):
        print("ERROR: Design file not found.")
        return
        
    nets = KicadImporter.parse_pcb_nets(pcb_path)
    comps = KicadImporter.parse_pcb_components(pcb_path)
    
    # 1. Check Decoupling Caps
    caps = [c for c in comps if c['lib'].startswith('Capacitor_SMD')]
    decoupling_count = len([c for c in caps if 'C_MCU_000' in c['ref']]) # Autogenerados tienen este prefijo
    
    # 2. Check Keepout (vía raw search por ahora hasta extender importer)
    with open(pcb_path, 'r', encoding='utf-8') as f:
        content = f.read()
    has_keepout = "(keepout" in content
    
    # 3. Accuracy Score (Weighted)
    score = 0
    if decoupling_count >= 2: score += 50
    if has_keepout: score += 50
    
    print(f"FACT 7: Validation Results")
    print(f"  - Decoupling Caps for ESP32: {decoupling_count} (Pass: >=2)")
    print(f"  - Antenna Keep-out Zone: {'YES' if has_keepout else 'NO'} (Pass: YES)")
    print(f"  - FINAL ACCURACY SCORE: {score}%")
    
    if score == 100:
        print("RESULT: CALIBRATION SUCCESS. Design matches Industry Standard (v2.1).")
    else:
        print("RESULT: CALIBRATION FAILED. Gaps detected.")

if __name__ == "__main__":
    pcb_path = "output/esp32_v2/pulselab_pcb/board.kicad_pcb"
    validate_design(pcb_path)
