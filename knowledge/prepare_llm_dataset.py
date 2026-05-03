import json
import random
from pathlib import Path

def generate_synthetic_description(components):
    """Genera una descripción en lenguaje natural a partir de la lista de componentes."""
    counts = {}
    details = []
    
    for comp in components:
        etype = comp.get("etype", "Desconocido")
        val = comp.get("value_raw", str(comp.get("value", "")))
        counts[etype] = counts.get(etype, 0) + 1
        if val and val != "0.0":
            details.append(f"{etype} de {val}")
            
    summary = ", ".join([f"{count} componente(s) tipo {etype}" for etype, count in counts.items()])
    
    prompts = [
        f"Genera el esquema para un circuito que incluye: {summary}. Específicamente con {', '.join(details)}.",
        f"Necesito la topología en JSON de un circuito con {summary}.",
        f"Diseña un circuito que contenga {len(components)} componentes, incluyendo {', '.join(details)}."
    ]
    
    return random.choice(prompts)

def prepare_llm_dataset():
    train_dir = Path("knowledge/data/training")
    output_file = Path("knowledge/data/llm_finetune.jsonl")
    
    samples = list(train_dir.glob("*.json"))
    if not samples:
        print("❌ No hay muestras en knowledge/data/training. Corre dataset_builder.py primero.")
        return
        
    system_prompt = "Eres el 'PulseLab Circuit Engine', experto en diseño electrónico. Tu tarea es convertir descripciones de circuitos en un JSON estricto devolviendo un objeto con la clave 'circuit'."
    
    dataset = []
    for sample_path in samples:
        with open(sample_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        components = data.get("circuit", {}).get("components", [])
        if not components:
            continue
            
        description = generate_synthetic_description(components)
        
        # Formato ChatML para SFT (Supervised Fine-Tuning)
        chat = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": description},
                {"role": "assistant", "content": json.dumps({"circuit": components})}
            ]
        }
        dataset.append(chat)
        
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    print(f"✅ Dataset de Fine-Tuning LLM generado: {output_file} ({len(dataset)} ejemplos)")

if __name__ == "__main__":
    prepare_llm_dataset()
