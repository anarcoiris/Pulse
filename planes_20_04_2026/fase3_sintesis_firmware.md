# Fase 3: Síntesis de Firmware e Integración IoT (HW/SW)

## Objetivo Principal
Consolidar a PulseLab Forge no solo como un EDA, sino como un Agente de Auto-Despliegue Full-Stack capaz de cruzar la capa física. El agente inyectará el `CircuitGraph` exportado a Módulos LLM u OpenAI para autogenerar el código base (MicroPython / C++ Arduino) correspondiente a la red de nodos diseñada por el usuario.

## Arquitectura del Módulo (`knowledge/firmware_synthesizer.py`)

### 1. Extractor de Árbol de Periféricos
- Analizar la Netlist en búsqueda de microcontroladores (Ej. `MCU_Espressif:ESP8266EX`) y observar a qué componentes de estado sólido o pull-ups (Switches, LEDs, Resistencias Sensitivas) se están asignando pines físicos (`GPIO0`, `GPIO2`, etc.).

### 2. Generación del "Prompt Estructural" LLM
- Crear un flujo similar al `SemanticAIAgent` donde el contexto contenga el Mapeo de Pines extraído y el modelo actúe bajo las reglas: 
  *"Se te entrega un diseño de hardware recién compilado de un nodo IoT. Escribe un script robusto en MicroPython listo para este layout específico identificando pines de entrada de red RC y pines de salida a LED".*

### 3. Autocompilador Transparente 
- Generar el `main.py` de MicroPython en la carpeta del Output para ser flasheado directamente sin tener que definir en el IDE qué sensor va a qué pin maestro. El código vendrá documentado atando el nombre de variable al `label` puesto por el usuario en PulseLab.

### 4. Consolidación de Flujo:
Al término, el resultado en `output/` constituirá un paquete definitivo:
1. `board.kicad_pro`
2. `board.kicad_sch`
3. `board.kicad_pcb`
4. `3D_Model.gltf`
5. `manufacturing/` (Gerbers)
6. `firmware/` (`main.cpp` / `main.py`)
7. `enclosures/` (Modelos OpenSCAD de caja parametrizada)

## Criterios de Aceptación (Test)
- Evaluar el archivo de texto devuelto inyectando pines fantasma y comprobando que el archivo de código asocia en el `setup()` o `pinMode` el pin correcto conectado en la interfaz PyGame.
