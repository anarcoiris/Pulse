"""
knowledge/validate_complex_apps.py
===================================
Suite de validación para evaluar la capacidad de PulseLab Circuit Engine 
de generar topologías complejas y multi-módulo (ESP32, Sensores, RF, etc.)

El LLM utilizado es el configurado en LLMClient (Ollama qwen2.5:3b por defecto).
Si el modelo falla, el script reportará los problemas de generación de JSON o componentes.
"""

import json
from pathlib import Path
from knowledge.circuit_synthesizer import CircuitSynthesizer
from knowledge.llm_client import get_llm_client

# Configuración
OUT_DIR = Path("knowledge/data/validation_complex")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Pruebas de Aplicaciones Complejas ──────────────────────────────────────────

TEST_CASES = [
    {
        "name": "esp32_sensors",
        "description": "ESP32 Devboard + Sensores",
        "prompt": (
            "Diseña un circuito basado en un microcontrolador ESP32. "
            "Conecta una pantalla OLED SSD1306 al bus I2C (pines SDA, SCL). "
            "Conecta también un sensor ambiental BME280 al mismo bus I2C. "
            "Asegúrate de incluir resistencias pull-up en las líneas I2C y "
            "condensadores de desacoplo para la alimentación del ESP32."
        )
    },
    {
        "name": "esp32_steppers",
        "description": "ESP32 + Controladores Stepper",
        "prompt": (
            "Diseña un circuito con un ESP32 que controle dos motores paso a paso NEMA17 "
            "utilizando dos drivers A4988. "
            "Conecta los pines STEP y DIR de los A4988 a pines GPIO del ESP32. "
            "Los drivers deben estar alimentados por una fuente externa de 12V para los motores (VMOT), "
            "e incluir condensadores electrolíticos grandes (ej: 100uF) cerca del pin VMOT. "
            "El ESP32 y la lógica de los A4988 (VDD) deben estar a 3.3V."
        )
    },
    {
        "name": "esp32_rf_nfc",
        "description": "ESP32 + NFC + 433 MHz RF",
        "prompt": (
            "Diseña un sistema IoT con un ESP32. "
            "Conecta un lector NFC PN532 a través de I2C. "
            "Conecta un transceptor de radio 433 MHz CC1101 a través del bus SPI "
            "(MISO, MOSI, SCK, CS). "
            "Incluye alimentación de 3.3V para todos los módulos y condensadores de bypass."
        )
    },
    {
        "name": "pulselab_zero",
        "description": "Proyecto Final: PulseLab Zero (Clon Flipper Zero)",
        "prompt": (
            "Diseña un dispositivo estilo Flipper Zero llamado PulseLab Zero. "
            "Debe tener un microcontrolador ESP32-S3 como núcleo, "
            "una pantalla OLED SSD1306 por I2C, un módulo NFC PN532 por SPI, "
            "un transceptor sub-GHz CC1101 por SPI, "
            "un D-Pad de 5 botones direccionales conectados a GPIOs con resistencias pull-up, "
            "y un conector de expansión de 8 pines (GPIOs libres, 3.3V y GND). "
            "Incluye condensadores de desacoplo para el ESP32."
        )
    }
]

def main():
    print("🚀 Iniciando Suite de Validación de Aplicaciones Complejas")
    
    llm = get_llm_client()
    if not llm.available:
        print("❌ El LLM no está disponible. Verifica el servicio en", llm.base_url)
        return
        
    print(f"✅ Conectado a LLM: {llm.model}")
    print("🧠 Inicializando Circuit Synthesizer (con RAG)...")
    
    synth = CircuitSynthesizer()
    
    for case in TEST_CASES:
        name = case["name"]
        print(f"\n─────────────────────────────────────────────────────")
        print(f"🧪 Test: {case['description']}")
        print(f"─────────────────────────────────────────────────────")
        
        print("⏳ Generando circuito...")
        result = synth.generate_circuit_json(case["prompt"])
        
        if "error" in result:
            print(f"❌ Error en generación: {result['error']}")
            continue
            
        components = result.get("components", [])
        print(f"✅ Generación exitosa. {len(components)} componentes generados.")
        
        # Guardar resultado
        out_file = OUT_DIR / f"{name}.json"
        
        output_data = {
            "test_case": case["description"],
            "prompt": case["prompt"],
            "circuit": components
        }
        
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        print(f"💾 Guardado en: {out_file}")
        
        # Análisis rápido de los componentes
        etypes = {}
        ic_labels = []
        for comp in components:
            t = comp.get("etype", "UNKNOWN")
            etypes[t] = etypes.get(t, 0) + 1
            if t == "IC":
                ic_labels.append(comp.get("label", "Unknown IC"))
                
        print(f"📊 Resumen de Componentes: {etypes}")
        if ic_labels:
            print(f"🔌 Chips Integrados/Módulos: {', '.join(ic_labels)}")

if __name__ == "__main__":
    main()
