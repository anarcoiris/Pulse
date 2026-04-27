import json
from pathlib import Path
from knowledge.kicad_layout_parser import KiCadLayoutParser

def build_dataset():
    raw_dir = Path("knowledge/data/raw_kicad")
    train_dir = Path("knowledge/data/training")
    train_dir.mkdir(parents=True, exist_ok=True)
    
    parser = KiCadLayoutParser()
    pcb_files = list(raw_dir.glob("*.kicad_pcb"))
    
    print(f"🏗️ Procesando {len(pcb_files)} archivos para el dataset...")
    
    success = 0
    for pcb in pcb_files:
        try:
            data = parser.parse_pcb(str(pcb))
            
            # Guardar como sample de PulseLab
            sample_name = f"human_{pcb.stem}.json"
            output_file = train_dir / sample_name
            
            sample_data = {
                "source": "Human_KiCad",
                "original_file": pcb.name,
                "circuit": data
            }
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(sample_data, f, indent=2)
            
            success += 1
            print(f"  ✅ Convertido: {pcb.name}")
        except Exception as e:
            print(f"  ❌ Error en {pcb.name}: {e}")
            
    print(f"\n✨ Dataset actualizado: {success} nuevas muestras humanas añadidas.")

if __name__ == "__main__":
    build_dataset()
