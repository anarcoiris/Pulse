# Fase 2: Motor de Visualización 3D y Renders

## Objetivo Principal
Reemplazar la estricta dependencia de visualizaciones bidimensionales (SVG estáticos o PDFs esquemáticos) introduciendo visualizaciones inmersivas CAD-fotorealistas automáticas invocando silenciosamente el renderizado CLI de KiCad y las librerías nativas 3D hacia el GUI.

## Arquitectura del Módulo (`bridge/render_engine.py`)

### 1. Interfaz de KiCad CLI para GLTF/STEP
- **Desarrollo:** Expandir el actual `kicad_bridge.py` con un comando `export_pcb_3d(format="step|gltf")`.
- **Implementación CLI:** Ejecutar en el sub-proceso asíncrono:
  ```bash
  kicad-cli pcb export gltf --subst-models --board-only False output/board.kicad_pcb -o output/board.gltf
  ```
- **Librería de Modelos:** Mapear la variable interna `KICAD8_3DMODEL_DIR` para asegurar que el GLTF generado traiga a bordo las siluetas volumétricas y texturas de Resistencias, Integrados QFP, etc.

### 2. Visor Local PyGame/OpenGL
- **Integración UI:** Emplear Python (Idealmente renderizado mínimo sobre la Canvas de PyGame) para cargar el snapshot renderizado al culminarse la exportación del Forge.
- Alternativa liviana (Si OpenGL bloquea dependencias): Exportar fotogramas isométricos prerenderizados en `PNG` y desplegarlos en un Popup animado al finalizar la exportación.

### 3. Fusión con el Enclosure Engine (OpenSCAD)
- Actualmente `enclosure_engine.py` genera código OpenSCAD (`.scad`). 
- **Mejora:** Hacer que el render del modelo GLTF exportado actúe como un maniquí virtual, restando o sumando tolerancias paramétricas exactas en los bordes de la placa para que la caja exterior embone sin fallos milimétricos.

## Criterios de Aceptación (Test)
- Al cliquear "Exportar", independientemente de los archivos de fabricación industrial, la carpeta `output/` contendrá un `board_render.step` o `.gltf`.
- Interfaz gráfica reflejando una imagen de pre-visualización volumétrica real demostrando el layout.
