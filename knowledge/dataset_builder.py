import json
from pathlib import Path
from knowledge.kicad_layout_parser import KiCadLayoutParser
from knowledge.kicad_schematic_parser import KiCadSchematicParser
from knowledge.rag_engine import ElectronicsKnowledgeBase

def build_dataset():
    raw_dir = Path("knowledge/data/raw_kicad")
    train_dir = Path("knowledge/data/training")
    train_dir.mkdir(parents=True, exist_ok=True)
    
    layout_parser = KiCadLayoutParser()
    sch_parser = KiCadSchematicParser()
    rag = ElectronicsKnowledgeBase()
    
    pcb_files = list(raw_dir.glob("*.kicad_pcb"))
    sch_files = list(raw_dir.glob("*.kicad_sch"))
    
    print(f"🏗️ Procesando {len(pcb_files)} PCBs y {len(sch_files)} Esquemáticos...")
    
    success = 0
    # Procesar PCBs
    for pcb in pcb_files:
        try:
            data = layout_parser.parse_pcb(str(pcb))
            _save_sample(data, pcb, train_dir, "Human_KiCad_PCB")
            success += 1
        except Exception as e:
            print(f"  ❌ Error en {pcb.name}: {e}")
            
    # Procesar Esquemáticos e ingestar en RAG
    for sch in sch_files:
        try:
            data = sch_parser.parse_schematic(str(sch))
            _save_sample(data, sch, train_dir, "Human_KiCad_SCH")
            
            # Ingestar el circuito esquemático en la Base de Conocimiento RAG
            # como un "circuit_example" para que el LLM lo pueda referenciar
            rag.ingest_json(data, source=f"Github:{sch.name}")
            # Cambiamos el tipo de chunk en la lista directamente (opcional pero limpio)
            rag._chunks[-1]["type"] = "circuit_example" 
            
            success += 1
        except Exception as e:
            print(f"  ❌ Error en {sch.name}: {e}")
            
    # Re-entrenar el motor RAG después de la ingesta
    rag._fit()
    print(f"\n✨ Dataset actualizado: {success} muestras procesadas e ingestadas en el RAG.")

def _save_sample(data, filepath, train_dir, source_type):
    sample_name = f"human_{filepath.stem}_{filepath.suffix[1:]}.json"
    output_file = train_dir / sample_name
    
    sample_data = {
        "source": source_type,
        "original_file": filepath.name,
        "circuit": data
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)
    
    print(f"  ✅ Convertido: {filepath.name}")

if __name__ == "__main__":
    build_dataset()
