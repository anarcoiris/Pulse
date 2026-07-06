"""
knowledge/finetune_circuit_llm.py
=================================
Validación del modelo de circuitos contra el Ollama Docker (symmetry_ollama).

El modelo qwen2.5:3b ya está corriendo en http://localhost:11434 vía Docker.
Este script NO descarga ni entrena nada localmente — hace inferencia contra
el endpoint vivo y mide la calidad del modelo base sobre nuestro dataset.

Si los resultados son insuficientes, el siguiente paso es hacer fine-tuning
con Ollama Modelfile o exportar el adaptador LoRA al servidor.

Uso:
    py -3.10 -m knowledge.finetune_circuit_llm
"""

import json
import random
from pathlib import Path
from knowledge.llm_client import LLMClient

# ── Configuración ──────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/v1"
MODEL        = "qwen2.5:3b"
DATASET_FILE = Path("knowledge/data/llm_finetune.jsonl")
EVAL_SAMPLES = 3           # Cuántos ejemplos del dataset evaluar
PASS_SCORE   = 0.5         # Fracción mínima de respuestas válidas para considerar OK

SYSTEM_PROMPT = (
    "Eres el 'PulseLab Circuit Engine', experto en diseño electrónico. "
    "Tu tarea es convertir descripciones de circuitos en un JSON estricto "
    "devolviendo un objeto con la clave 'circuit'. Responde ÚNICAMENTE con JSON válido."
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_eval_samples(n: int) -> list[dict]:
    """Carga n ejemplos aleatorios del dataset JSONL."""
    if not DATASET_FILE.exists():
        raise FileNotFoundError(
            f"Dataset no encontrado: {DATASET_FILE}\n"
            "Corre primero: py -3.10 -m knowledge.prepare_llm_dataset"
        )
    samples = []
    with open(DATASET_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if not samples:
        raise ValueError("El dataset JSONL está vacío.")
    return random.sample(samples, min(n, len(samples)))


def extract_user_prompt(sample: dict) -> str:
    """Extrae el mensaje del usuario del formato ChatML."""
    for msg in sample.get("messages", []):
        if msg.get("role") == "user":
            return msg["content"]
    return ""


def extract_expected(sample: dict) -> dict | None:
    """Extrae el JSON de respuesta esperado del sample."""
    for msg in sample.get("messages", []):
        if msg.get("role") == "assistant":
            try:
                return json.loads(msg["content"])
            except json.JSONDecodeError:
                return None
    return None


def parse_json_response(text: str) -> dict | None:
    """Intenta parsear el JSON de la respuesta del LLM."""
    text = text.strip()
    # Buscar primer bloque JSON entre llaves
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


def score_response(predicted: dict | None, expected: dict | None) -> dict:
    """
    Evalúa la respuesta del LLM contra la esperada.
    Devuelve un dict con métricas de calidad.
    """
    if predicted is None:
        return {"valid_json": False, "has_circuit": False, "component_match": 0.0}

    has_circuit = "circuit" in predicted
    pred_comps  = predicted.get("circuit", [])
    exp_comps   = expected.get("circuit", []) if expected else []

    # Comparar cantidad de componentes como métrica proxy
    if exp_comps and isinstance(pred_comps, list):
        ratio = min(len(pred_comps), len(exp_comps)) / max(len(exp_comps), 1)
    else:
        ratio = 0.0

    return {
        "valid_json":       True,
        "has_circuit":      has_circuit,
        "component_match":  round(ratio, 2),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"🔍 Evaluando modelo '{MODEL}' en {OLLAMA_URL}")
    print(f"   Dataset: {DATASET_FILE}\n")

    # 1. Verificar que el servicio Ollama está vivo
    client = LLMClient(base_url=OLLAMA_URL, model=MODEL)
    if not client.available:
        print("❌ Ollama no está disponible en", OLLAMA_URL)
        print("   Verifica que el Docker de Symmetry está corriendo:")
        print("   docker ps | findstr symmetry_ollama")
        return

    print(f"✅ Ollama disponible — modelo: {MODEL}\n")

    # 2. Cargar muestras de evaluación
    try:
        samples = load_eval_samples(EVAL_SAMPLES)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        return

    print(f"📊 Evaluando {len(samples)} muestras...\n")

    results = []
    for i, sample in enumerate(samples, 1):
        user_prompt = extract_user_prompt(sample)
        expected    = extract_expected(sample)

        if not user_prompt:
            continue

        # 3. Llamar al modelo vía LLMClient (OpenAI-compatible API de Ollama)
        resp = client.chat(system=SYSTEM_PROMPT, user=user_prompt, temperature=0.1)

        if "error" in resp:
            print(f"  [{i:02d}] ❌ Error: {resp['error']}")
            results.append({"valid_json": False, "has_circuit": False, "component_match": 0.0})
            continue

        parsed   = parse_json_response(resp["content"])
        score    = score_response(parsed, expected)
        results.append(score)

        status = "✅" if score["has_circuit"] else "⚠️ "
        print(
            f"  [{i:02d}] {status}  JSON válido={score['valid_json']}  "
            f"circuit={score['has_circuit']}  "
            f"componentes_match={score['component_match']:.0%}"
        )
        if parsed and not score["has_circuit"]:
            print(f"        Respuesta: {str(parsed)[:120]}...")

    # 4. Resumen
    total    = len(results)
    valid    = sum(1 for r in results if r["valid_json"])
    circuit  = sum(1 for r in results if r["has_circuit"])
    avg_comp = sum(r["component_match"] for r in results) / max(total, 1)

    print(f"\n{'─'*55}")
    print(f"📈 RESULTADOS DE VALIDACIÓN ({total} muestras)")
    print(f"   JSON válido:          {valid}/{total} ({valid/total:.0%})")
    print(f"   Con clave 'circuit':  {circuit}/{total} ({circuit/total:.0%})")
    print(f"   Match de componentes: {avg_comp:.0%} (promedio)")
    print(f"{'─'*55}")

    pass_rate = circuit / max(total, 1)
    if pass_rate >= PASS_SCORE:
        print(f"\n🎉 Modelo APTO para uso en PulseLab ({pass_rate:.0%} ≥ umbral {PASS_SCORE:.0%})")
        print("   El LLMClient de Pulse ya apunta a este modelo — integración lista.")
    else:
        print(f"\n⚠️  Modelo por debajo del umbral ({pass_rate:.0%} < {PASS_SCORE:.0%})")
        print("   Considera hacer fine-tuning exportando un Modelfile a Ollama:")
        print("   ollama create pulse-circuit -f knowledge/models/Modelfile")


if __name__ == "__main__":
    main()
