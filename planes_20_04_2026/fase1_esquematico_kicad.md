# Fase 1: Paridad de Esquemático Maestro (.kicad_sch)

## Objetivo Principal
Dotar a PulseLab Forge de la capacidad de exportar un archivo `.kicad_sch` (Esquemático Nativo de KiCad 8) funcional y visualmente idéntico al dibujado en el Canvas interactivo de PulseLab. Solucionar el problema actual donde se exporta el PCB físico (`.kicad_pcb`) pero el proyecto carece de un documento fuente para modificaciones lógicas en KiCad.

## Arquitectura del Módulo (`bridge/schematic_generator.py`)

### 1. Extractor de Coordenadas (`CircuitGraph` → `kicad_sch`)
- **Problema:** En el S-Expression de KiCad, cada símbolo esquemático necesita coordenadas espaciales (X, Y) y orientación (Rotación).
- **Solución:** Utilizar las variables nativas `grid_c`, `grid_r` y `orientation` de `PlacedComponent` de PulseLab, aplicando un factor de escala (ej. `1 Grid Unit Pulse = 2.54 mm KiCad`) para posicionar perfectamente cada componente en el plano A4 de KiCad.

### 2. Mapeo de Diccionarios de Símbolos (`Symbol Library Mapping`)
- Se creará un diccionario maestro que traduzca el `etype` de PulseLab a la librería estándar de KiCad:
  - `R` ➔ `Device:R`
  - `C` ➔ `Device:C`
  - `V` ➔ `Device:Battery` (o un `Power:VCC`)
  - `MCU`/`IC` ➔ Diccionario dinámico soportando `MCU_Espressif:ESP8266`, `Timer:NE555`, etc.

### 3. Trazado de Cables Lógicos (Wires a Junctions)
- **Problema:** Un simple cable en PulseLab `([(c1, r1), (c2, r2)])` debe traducirse a una serie de segmentos lógicos `(wire (pts (xy X1 Y1) (xy X2 Y2)))` en KiCad.
- **Ruteo de Cruces (Junctions):** Implementar un algoritmo simple que detecte intersecciones de `Wire` en el `.kicad_sch` para pintar automáticamente los nodos redondos de conexión explícita `(junction (at X Y))`.

### 4. Integración Forge
- Enlazar el módulo a la acción de UI actual `generar_proyecto_completo()`.
- Ahora, exportar el proyecto creará en la carpeta `output/`:
  - `board.kicad_pro` (Generado hoy)
  - `board.kicad_pcb` (Generado)
  - **`board.kicad_sch` (NUEVO)**

## Criterios de Aceptación (Test)
- Abrir `board.kicad_pro` y hacer doble clic en el esquemático sin que KiCad reporte un error de "Símbolo Huérfano" o "Componente Corrupto".
- Seleccionar "Actualizar PCB desde el esquemático" en KiCad (F8) y confirmar que 0 componentes se eliminan o reasignan.
