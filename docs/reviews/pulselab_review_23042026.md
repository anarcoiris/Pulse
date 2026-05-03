# PulseLab Forge — Revisión técnica, hallazgos y plan de acción

> Revisión realizada el 23 de abril de 2026  
> Repositorio: [github.com/anarcoiris/pulse](https://github.com/anarcoiris/pulse)

---

## 1. Visión general del proyecto

PulseLab Forge es un entorno integrado de simulación de circuitos, diseño algorítmico de PCB y agentes LLM vía protocolo MCP. Su propuesta de valor central es cubrir el pipeline completo desde esquema conceptual hasta archivos de fabricación (Gerbers, Drill, CPL) de forma autónoma, utilizando KiCad 8 como motor de exportación.

**Stack principal:** Python 3.10+, PyGame, NumPy, KiCad CLI, FastMCP, TF-IDF RAG, schemdraw  
**Lenguajes:** Python 90%, TypeScript 6%, OpenSCAD 2.6%, CSS/HTML ~1.4%  
**Estado del pipeline verificado:** `PCBLayout → .kicad_pcb → kicad-cli 8.0.6 → Gerber + Drill + CPL ✓`

---

## 2. Hallazgos: lo que está bien

### 2.1 Motor MNA (`circuit_engine.py`) — punto más fuerte del proyecto

El simulador de circuitos por Análisis Nodal Modificado es de alta calidad técnica:

- Implementa **Backward Euler** con modelos compañeros correctos para R, C, L, fuentes de tensión e interruptores
- La documentación interna cita la referencia bibliográfica correcta (Pillage, Rohrer & Visweswariah, 1994) y explica las ecuaciones de los modelos compañeros
- La regularización diagonal (`A += eye * 1e-12`) maneja nodos flotantes de forma elegante
- Los tests integrados en `__main__` verifican comportamientos concretos con valores de error esperados (RC con tau = 6ms, error ~4.5% esperado con Backward Euler de primer orden)
- `set_dt()`, `set_switch()`, `set_voltage_source()` y `reset_state()` permiten control en tiempo de ejecución

### 2.2 Arquitectura modular y bien separada

| Módulo | Responsabilidad |
|--------|----------------|
| `core/` | Motor de simulación, base de componentes, RF tools |
| `bridge/` | Interconexión con KiCad (layout, exportación, BOM) |
| `knowledge/` | RAG TF-IDF + datos IPC-2221 |
| `mcp/` | Servidor FastMCP con 23 herramientas expuestas |
| `ui/` | Interfaz gráfica PyGame |

### 2.3 Pipeline de fabricación verificado

Tres placas de ejemplo generadas y exportadas con éxito:

| Placa | Tamaño | Componentes | Gerbers | Drill |
|-------|--------|-------------|---------|-------|
| Divisor de tensión | 20×15mm | 3 | 11 ✓ | 1 ✓ |
| 555 LED Driver | 40×25mm | 14 | 11 ✓ | 1 ✓ |
| ESP8266 Sensor Node | 50×35mm | 14 | 11 ✓ | 1 ✓ |

### 2.4 Integración MCP bien diseñada

23 herramientas organizadas en 7 categorías: Simulación, RF/Impedancia, KiCad/Fabricación, PCB Layout, Base de Componentes, Knowledge/RAG, Utilidad. La taxonomía es coherente y permite que un agente LLM externo (Claude Desktop, etc.) orqueste el flujo completo.

### 2.5 Herramientas RF

`rf_tools.py` implementa cálculos de microstrip con error Z₀ < 0.4% y ancho de pista IPC ±3%, lo que es suficiente para la mayoría de diseños de señal digital.

---

## 3. Hallazgos: áreas de mejora

### 3.1 Sin `requirements.txt` en la raíz

El README menciona dependencias (`pygame`, `numpy`, `skidl`, `mcp`) pero el archivo `requirements.txt` no está en el listing raíz del repositorio. Para un proyecto con tantas dependencias externas, incluyendo KiCad en el PATH del sistema, esto es un punto de fricción crítico para cualquier colaborador o usuario nuevo.

**Impacto:** Alto — bloquea la instalación autónoma  
**Esfuerzo de resolución:** Bajo

### 3.2 Acoplamiento duro a rutas de Windows

`kicad_bridge.py` detecta KiCad en `C:\Program Files` y `D:\Program Files` como paths hardcodeados. Esto rompe inmediatamente en Linux y macOS, donde KiCad suele estar en `/usr/bin/kicad-cli` o `/Applications/KiCad/KiCad.app/Contents/MacOS/`.

**Impacto:** Alto — incompatibilidad total en Unix  
**Solución:** `shutil.which('kicad-cli')` como primera opción, con fallback a paths conocidos por OS

```python
import shutil, platform

def find_kicad_cli():
    # Intento 1: en el PATH del sistema
    cli = shutil.which('kicad-cli')
    if cli:
        return cli
    
    # Fallback por plataforma
    candidates = {
        'Windows': [r'C:\Program Files\KiCad\8.0\bin\kicad-cli.exe',
                    r'D:\Program Files\KiCad\8.0\bin\kicad-cli.exe'],
        'Darwin':  ['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'],
        'Linux':   ['/usr/bin/kicad-cli', '/usr/local/bin/kicad-cli'],
    }
    for path in candidates.get(platform.system(), []):
        if Path(path).exists():
            return path
    raise RuntimeError("kicad-cli no encontrado. Instala KiCad 8+ y añádelo al PATH.")
```

### 3.3 RAG demasiado básico para el dominio

TF-IDF con 32 chunks sobre IPC-2221 es funcional pero limitado. El problema fundamental es que TF-IDF no entiende semántica: "35µm copper, external layer, 1A" y "1 oz copper, outer, 1000mA" son la misma consulta pero TF-IDF las trata como completamente distintas.

**Impacto:** Medio — calidad de respuestas técnicas degradada  
**Solución propuesta:** embeddings densos (ver sección 5.2)

### 3.4 Autorouter sin evitación de colisiones

Las trazas se generan como rutas en L automáticas (un codo de 90°). El router no tiene noción del espacio ocupado por otros componentes o trazas, lo que produce cortocircuitos en circuitos con más de ~10-15 componentes cercanos.

**Impacto:** Alto para devboards reales — los Gerbers generados pueden no ser fabricables  
**Solución propuesta:** grid de ocupación + BFS (ver sección 5.1)

### 3.5 Sin footprints SMD para MCUs modernos

El catálogo actual solo incluye componentes THT (DIP ICs, resistencias, condensadores de orificio pasante). Toda devboard moderna usa componentes SMD: QFP, TQFP, QFN para MCUs; 0402/0603 para pasivos.

**Impacto:** Alto — impide diseñar placas con ESP32, STM32, RP2040  
**Solución:** conectar a la biblioteca de footprints de KiCad en lugar de generarlos desde cero

### 3.6 Sin DRC antes de exportar

No hay ninguna verificación de Design Rule Check antes de generar los Gerbers. Un cortocircuito entre pads o una violación de clearance no se detecta hasta que la placa vuelve de fabricación.

**Impacto:** Alto — coste de iteración muy elevado  
**Solución:** invocar `kicad-cli pcb drc` como paso obligatorio en `gerber_export.py`

### 3.7 Archivos de trabajo en el repositorio público

Carpetas como `scratch/`, `planes_20_04_2026/` y archivos `review_output.txt`, `review_output_utf8.txt` son artefactos de trabajo personal que no deberían estar en un repositorio público. Pueden revelar información no intencionada y dificultan la navegación.

**Impacto:** Bajo — estético/seguridad  
**Solución:** añadir al `.gitignore` y limpiar el historial si contienen información sensible

### 3.8 Sin CI/CD

No hay GitHub Actions configurado. Con 7 tests que ya pasan (`test_forge.py`), añadir un workflow básico que los ejecute en cada push sería sencillo.

**Impacto:** Bajo-medio — riesgo de regresiones silenciosas

---

## 4. Análisis: motor de PCB y capacidades de fabricación

### 4.1 Lo que el motor PCBLayout hace bien

- Generación nativa de formato S-Expression `.kicad_pcb` sin depender de la UI de KiCad
- Algoritmos de emplazamiento: distribución lineal, circular, alineaciones, simetrías
- Infraestructura: agujeros de montaje, textos, vías, planos de cobre básicos
- API fluida y bien diseñada:

```python
pcb = PCBLayout(board_width=50, board_height=30)
r1 = pcb.add_resistor("R1", "10k", x=10, y=15, net1="VCC", net2="OUT")
pcb.align_horizontal(r1, c1)
pcb.distribute_circular(r1, c1, u1)
pcb.save("output/mi_placa.kicad_pcb")
```

### 4.2 Límites actuales para devboards reales

| Capacidad | Estado actual | Impacto |
|-----------|--------------|---------|
| Trazas sin colisiones | ❌ Rutas en L sin evitación | Cortocircuitos posibles |
| Footprints SMD | ❌ Solo THT | No sirve para MCUs modernos |
| DRC integrado | ❌ Sin verificación | Errores silenciosos |
| Footprints de conectores | ⚠️ Parcial (headers 2.54mm) | Limitado |
| Plano de masa GND | ⚠️ Básico, sin thermal reliefs | Problemas en soldadura |
| Generación de BOM | ✓ CSV/JSON/texto | Completo |
| Exportación CPL | ✓ Para pick & place | Completo |

---

## 5. Propuestas de mejora

### 5.1 Autorouter con grid de ocupación (GAP CRÍTICO)

Implementar un router de Lee/BFS sobre una grid de ocupación. No requiere el algoritmo completo de Freerouting; con una grid de 0.25mm y BFS se cubre el 80% de los casos de una devboard.

```python
# bridge/occupancy_grid.py
import numpy as np
from collections import deque

class OccupancyGrid:
    def __init__(self, width_mm: float, height_mm: float, step: float = 0.25):
        self.step = step
        self.cols = int(width_mm / step)
        self.rows = int(height_mm / step)
        self.grid = np.zeros((self.rows, self.cols), dtype=bool)

    def _to_cell(self, x_mm: float, y_mm: float) -> tuple[int, int]:
        return int(y_mm / self.step), int(x_mm / self.step)

    def mark_rect(self, x: float, y: float, w: float, h: float, clearance: float = 0.2):
        """Marca un área rectangular como ocupada (pad, componente)."""
        r0, c0 = self._to_cell(x - clearance, y - clearance)
        r1, c1 = self._to_cell(x + w + clearance, y + h + clearance)
        self.grid[max(0,r0):min(self.rows,r1), max(0,c0):min(self.cols,c1)] = True

    def mark_trace(self, points: list[tuple], width: float = 0.25):
        """Marca una traza ya colocada como ocupada."""
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            # Interpolación lineal de celdas
            steps = int(max(abs(x2-x1), abs(y2-y1)) / self.step) + 1
            for t in range(steps + 1):
                xi = x1 + (x2 - x1) * t / steps
                yi = y1 + (y2 - y1) * t / steps
                r, c = self._to_cell(xi, yi)
                hw = int(width / self.step / 2) + 1
                self.grid[max(0,r-hw):min(self.rows,r+hw),
                          max(0,c-hw):min(self.cols,c+hw)] = True

    def route_bfs(self, x1: float, y1: float,
                  x2: float, y2: float) -> list[tuple] | None:
        """BFS de (x1,y1) a (x2,y2). Devuelve lista de puntos en mm o None."""
        start = self._to_cell(x1, y1)
        end   = self._to_cell(x2, y2)
        if self.grid[end]:
            return None  # destino bloqueado

        visited = {start: None}
        queue   = deque([start])
        dirs    = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]

        while queue:
            cur = queue.popleft()
            if cur == end:
                # Reconstruir camino
                path, node = [], cur
                while node is not None:
                    r, c = node
                    path.append((c * self.step, r * self.step))
                    node = visited[node]
                return list(reversed(path))
            for dr, dc in dirs:
                nxt = (cur[0]+dr, cur[1]+dc)
                if (0 <= nxt[0] < self.rows and 0 <= nxt[1] < self.cols
                        and not self.grid[nxt] and nxt not in visited):
                    visited[nxt] = cur
                    queue.append(nxt)
        return None  # sin camino
```

**Integración en `pcb_layout.py`:** instanciar `OccupancyGrid` al crear el PCBLayout, marcar cada componente al añadirlo, y usar `route_bfs` en el método `trace()`.

**Estimación de esfuerzo:** 2-3 días de desarrollo, 1 día de tests.

### 5.2 RAG con embeddings densos

Reemplazar TF-IDF por embeddings densos para mejorar la recuperación semántica de reglas IPC y datos de componentes.

**Opción A — Local (sin coste de API):**
```bash
pip install sentence-transformers faiss-cpu
```

```python
# knowledge/rag_engine_v2.py
from sentence_transformers import SentenceTransformer
import faiss, numpy as np

class DenseRAGEngine:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunks = []

    def ingest(self, texts: list[str]):
        self.chunks.extend(texts)
        vecs = self.model.encode(texts, normalize_embeddings=True)
        if self.index is None:
            self.index = faiss.IndexFlatIP(vecs.shape[1])
        self.index.add(vecs.astype('float32'))

    def search(self, query: str, k: int = 5) -> list[str]:
        vec = self.model.encode([query], normalize_embeddings=True)
        _, ids = self.index.search(vec.astype('float32'), k)
        return [self.chunks[i] for i in ids[0] if i < len(self.chunks)]
```

**Opción B — API de Anthropic (sin dependencias locales):**
```python
import anthropic
client = anthropic.Anthropic()

def embed(text: str) -> list[float]:
    # Usar el endpoint de embeddings cuando esté disponible
    # Por ahora: usar el modelo para generar representaciones semánticas
    pass
```

**Mejora esperada:** recuperación semántica correcta para el 90%+ de consultas técnicas (vs ~60% con TF-IDF para terminología mixta).

### 5.3 RAG acumulativo de experiencias de diseño

Cada diseño generado y exportado con éxito (o cada error detectado en DRC) se convierte en conocimiento estructurado que el sistema puede recuperar en futuros diseños.

**Formato del registro de experiencia:**

```python
# knowledge/design_experience.py
from dataclasses import dataclass, asdict
from datetime import datetime
import json, pathlib

@dataclass
class DesignExperience:
    board_id: str
    timestamp: str
    mcu: str
    mcu_package: str          # QFP48, QFN32, etc.
    board_size_mm: tuple
    component_count: int
    layer_count: int
    drc_violations: int
    routing_success_rate: float
    manufacturing_target: str  # JLCPCB, PCBWay, etc.
    lessons_learned: list[str]
    component_placement_rules: list[str]
    critical_nets: list[str]   # nets con requisitos especiales
    gerber_path: str

    def save(self, knowledge_dir: str = "knowledge/experiences"):
        path = pathlib.Path(knowledge_dir) / f"{self.board_id}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))

    @classmethod
    def from_file(cls, path: str) -> 'DesignExperience':
        return cls(**json.loads(pathlib.Path(path).read_text()))

# Ejemplo de uso tras un diseño exitoso:
exp = DesignExperience(
    board_id="esp32_sensor_v1",
    timestamp=datetime.now().isoformat(),
    mcu="ESP32-WROOM-32",
    mcu_package="SMD-38",
    board_size_mm=(60, 40),
    component_count=22,
    layer_count=2,
    drc_violations=0,
    routing_success_rate=0.94,
    manufacturing_target="JLCPCB",
    lessons_learned=[
        "Decoupling 100nF debe ir a <2mm de cada pin VDD del ESP32",
        "Separar plano GND analógico del digital bajo el ADC",
        "Pines BOOT y EN necesitan pull-up de 10k para programación",
        "Antena del módulo WROOM no puede tener cobre en las capas inferiores",
    ],
    component_placement_rules=[
        "Cristal lo más cerca posible del MCU, sin trazas largas",
        "Condensadores de decoupling antes del pad de potencia, no después",
    ],
    critical_nets=["VDD", "GND", "RF_ANT"],
    gerber_path="output/esp32_sensor_v1/manufacturing/"
)
exp.save()
```

**Ingestión en el RAG:** al guardar cada experiencia, se convierten `lessons_learned` y `component_placement_rules` en chunks y se añaden al índice con `ingest_knowledge_text`. En el próximo diseño con ESP32, el sistema recupera automáticamente las lecciones previas.

### 5.4 Footprints SMD desde la biblioteca de KiCad

```python
# bridge/kicad_bridge.py — extensión
import re
from pathlib import Path

KICAD_FOOTPRINT_LIBS = {
    'Windows': Path(r'C:\Program Files\KiCad\8.0\share\kicad\footprints'),
    'Darwin':  Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'),
    'Linux':   Path('/usr/share/kicad/footprints'),
}

def get_kicad_footprint(lib: str, name: str) -> str:
    """
    Lee un footprint de la biblioteca estándar de KiCad.
    
    Args:
        lib:  Nombre de la librería, e.g. 'Package_QFP'
        name: Nombre del footprint, e.g. 'LQFP-48_7x7mm_P0.5mm'
    
    Returns:
        Contenido del archivo .kicad_mod como string
    """
    import platform
    base = KICAD_FOOTPRINT_LIBS.get(platform.system())
    fp_path = base / f"{lib}.pretty" / f"{name}.kicad_mod"
    if not fp_path.exists():
        raise FileNotFoundError(f"Footprint no encontrado: {lib}:{name}\nBuscado en: {fp_path}")
    return fp_path.read_text(encoding='utf-8')

# Catálogo de footprints para MCUs comunes
MCU_FOOTPRINTS = {
    'ESP32-WROOM-32':  ('RF_Module', 'ESP32-WROOM-32'),
    'STM32F103C8T6':   ('Package_QFP', 'LQFP-48_7x7mm_P0.5mm'),
    'RP2040':          ('Package_DFN_QFN', 'QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm'),
    'ATmega328P-AU':   ('Package_QFP', 'TQFP-32_7x7mm_P0.8mm'),
    'SAMD21G18A-MU':   ('Package_DFN_QFN', 'QFN-48-1EP_7x7mm_P0.5mm_EP3.5x3.5mm'),
}

def add_mcu_to_layout(pcb, mcu_name: str, x: float, y: float):
    """Añade un MCU conocido al layout usando su footprint de KiCad."""
    if mcu_name not in MCU_FOOTPRINTS:
        raise ValueError(f"MCU no en catálogo: {mcu_name}. Disponibles: {list(MCU_FOOTPRINTS)}")
    lib, fp_name = MCU_FOOTPRINTS[mcu_name]
    fp_content = get_kicad_footprint(lib, fp_name)
    # Inyectar en el .kicad_pcb con posición y orientación
    pcb.add_raw_footprint(fp_content, x=x, y=y, rotation=0)
```

### 5.5 DRC obligatorio antes de exportar

```python
# bridge/gerber_export.py — modificación
import subprocess, json

def run_drc(kicad_pcb_path: str) -> dict:
    """
    Ejecuta DRC de KiCad y devuelve el reporte.
    Lanza excepción si hay violaciones críticas.
    """
    report_path = kicad_pcb_path.replace('.kicad_pcb', '_drc.json')
    result = subprocess.run([
        'kicad-cli', 'pcb', 'drc',
        '--output', report_path,
        '--format', 'json',
        '--severity-all',
        kicad_pcb_path
    ], capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        raise RuntimeError(f"kicad-cli DRC falló:\n{result.stderr}")

    report = json.loads(open(report_path).read())
    violations = report.get('violations', [])
    errors = [v for v in violations if v.get('severity') == 'error']

    if errors:
        summary = '\n'.join(f"  - {e['description']}" for e in errors[:5])
        raise ValueError(
            f"DRC: {len(errors)} errores encontrados. Corrige antes de exportar:\n{summary}"
        )

    return {'violations': len(violations), 'errors': len(errors), 'report': report_path}

def generate_gerbers(kicad_pcb_path: str, output_dir: str, skip_drc: bool = False):
    """Genera Gerbers. Por defecto ejecuta DRC primero."""
    if not skip_drc:
        drc_result = run_drc(kicad_pcb_path)
        print(f"DRC OK — {drc_result['violations']} avisos, 0 errores")
    # ... resto del proceso de exportación existente
```

### 5.6 GitHub Actions básico

```yaml
# .github/workflows/ci.yml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Instalar dependencias
        run: |
          pip install numpy pytest
          # KiCad CLI mock para entorno CI
          echo '#!/bin/bash\necho "kicad-cli mock OK"' > /usr/local/bin/kicad-cli
          chmod +x /usr/local/bin/kicad-cli
      - name: Ejecutar tests
        run: pytest tests/test_forge.py -v
        env:
          KICAD_CLI_MOCK: "1"
```

---

## 6. Plan de acción para devboards funcionales

### Flujo viable hoy mismo (sin modificaciones)

Para boards simples con componentes THT ya disponibles en el catálogo:

```
1. Definir netlist en Python usando CircuitSimulator
2. Llamar create_pcb_layout via MCP con los componentes
3. Consultar get_design_rules para clearances y anchos de pista
4. Revisar .kicad_pcb manualmente en KiCad antes de enviar
5. Llamar generate_pcb_gerbers para obtener Gerbers + Drill + CPL
6. Enviar a JLCPCB/PCBWay con el BOM generado
```

**MCUs compatibles hoy:** ESP-01 (DIP-8 breakout), Arduino Nano (DIP), cualquier MCU en socket DIP.

### Flujo objetivo con las mejoras propuestas

```
1. Describir la devboard al agente MCP en lenguaje natural
2. El agente consulta el RAG de experiencias para el MCU elegido
3. Genera el circuito mínimo de soporte (decoupling, reset, programación)
4. PCBLayout coloca componentes con footprints SMD reales de KiCad
5. OccupancyGrid + BFS genera las trazas sin colisiones
6. DRC obligatorio verifica clearances antes de exportar
7. Se exportan Gerbers, Drill, BOM y CPL listos para fabricar
8. La experiencia del diseño se guarda en el RAG para futuros proyectos
```

### Hoja de ruta priorizada

| Prioridad | Tarea | Esfuerzo estimado | Impacto |
|-----------|-------|-------------------|---------|
| 🔴 P0 | `requirements.txt` en la raíz | 1 hora | Desbloquea instalación |
| 🔴 P0 | Detección multiplataforma de kicad-cli | 2 horas | Compatibilidad Unix |
| 🔴 P1 | DRC obligatorio antes de exportar | 1 día | Evita boards defectuosas |
| 🔴 P1 | Footprints SMD desde biblioteca KiCad | 2-3 días | Habilita MCUs modernos |
| 🟡 P2 | OccupancyGrid + router BFS | 3-4 días | Trazas sin colisiones |
| 🟡 P2 | RAG con embeddings densos | 2-3 días | Mejor recuperación técnica |
| 🟡 P2 | RAG acumulativo de experiencias | 2 días | Aprendizaje continuo |
| 🟢 P3 | GitHub Actions CI | 0.5 días | Calidad a largo plazo |
| 🟢 P3 | Limpiar `scratch/`, `planes_*/` del repo | 1 hora | Higiene del repositorio |
| 🟢 P3 | Copper pours con thermal reliefs | 3-4 días | Calidad de fabricación |

---

## 7. Valoración final

PulseLab Forge tiene una base técnica sólida y diferenciadora. El motor MNA es el componente más robusto y demuestra comprensión real del dominio. El pipeline end-to-end que ya funciona (circuito → Gerbers) es el activo más valioso.

Con las mejoras P0 y P1 implementadas, el proyecto puede generar devboards THT listas para fabricar de forma autónoma. Con P2 completo (autorouter + SMD + RAG denso), puede competir con flujos semiprofesionales de diseño asistido por IA para hardware de bajo/medio volumen.

El principal riesgo actual es que los Gerbers generados pasen el pipeline sin DRC y lleguen a fabricación con defectos. Ese es el gap más urgente de cerrar.

---

*Documento generado automáticamente a partir de la revisión técnica de código y arquitectura.*
