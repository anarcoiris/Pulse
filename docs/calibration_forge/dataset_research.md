# Investigación Profunda: Fuentes de Datos para Entrenamiento Hardware

## Introducción
Para que PulseLab Forge alcance un nivel de diseño profesional, necesitamos una base de datos "Golden Standard" que sirva de referencia para el entrenamiento y la validación. Esta investigación detalla las fuentes actuales, los tipos de datos disponibles y los métodos técnicos para extraer más información de forma automatizada.

---

## 1. Fuentes de Datos Primarias (Datasets Curados)

### A. Dataset: Open-Schematics (Hugging Face)
- **Localización:** `bshada/open-schematics`
- **Contenido:** Miles de esquemáticos KiCad extraídos de GitHub.
- **Formato:** Raw `.kicad_sch`, metadatos en JSON, y renders visuales (PNG).
- **Utilidad:** Ideal para entrenar el `SchematicGenerator` y el `KicadImporter`.

### B. Antmicro Open Hardware Portal
- **Localización:** [Open Hardware Portal](https://antmicro.com/open-hardware-portal/)
- **Contenido:** Diseños industriales verificados (SBCs, módems, módulos Jetson).
- **Formato:** KiCad, Altium, PDF y BOMs detallados.
- **Utilidad:** Referencia para ruteo de alta velocidad y densidades de PCB complejas.

---

## 2. Repositorios Corporativos (Golden Standards)
Estos proveedores publican sus diseños de hardware abierto como parte de su modelo de negocio. Son la fuente más fiable de "buen diseño".

- **SparkFun Electronics (GitHub `sparkfun`):**
    - Cientos de "Breakout Boards". Diseños modulares, limpios y consistentes.
- **Adafruit Industries (GitHub `adafruit`):**
    - Enfoque en ergonomía y usabilidad. Excelentes para estudiar colocación de conectores.
- **Olimex (GitHub `OLIMEX`):**
    - Diseños de nivel industrial, portátiles y laptops OSHW totalmente en KiCad.

---

## 3. Plataformas Comunitarias (Big Data)

### OSWHLab / EasyEDA
- **Método de Extracción:** Uso de herramientas de conversión como `easyeda2kicad` o el SDK oficial de EasyEDA Pro.
- **Volumen:** Millones de proyectos. La calidad varía, pero es la mayor fuente de datos del mundo sobre footprints de componentes chinos (LCSC).

### GitHub (Búsqueda por Tópicos)
- **Queries recomendadas:**
    - `topic:kicad-schematic`
    - `topic:open-hardware`
    - `extension:kicad_pcb` (para encontrar layouts específicos)
- **Automatización:** Uso de la API de GitHub para descargar repositorios que contengan archivos de KiCad 8.

---

## 4. Métodos Técnicos de Recolección de Datos

Para continuar con nuestra recolección, propongo la creación de una rutina automatizada:

1.  **Crawler de GitHub:** Un script que busque repositorios de KiCad con >100 estrellas (filtro de calidad).
2.  **Conversión a JSON:** Pasar todos los `.kicad_sch` a un formato JSON plano que nuestro `KicadImporter` pueda leer sin errores de parsing.
3.  **Generación de Pares (Pair Generation):**
    - Tomar un diseño real (Dataset).
    - Extraer su Netlist y Posicionamiento.
    - Intentar replicarlo.
    - Guardar el "Delta" (error) como dato de entrenamiento.

---

## 5. Mapa de Repositorios Específicos

| Fuente | URL | Tipo de Dato |
| :--- | :--- | :--- |
| **SparkFun** | `https://github.com/sparkfun/KiCad_Footprints` | Footprints Oro |
| **CircuitSnips** | `https://github.com/v-i-s-h-n-u/CircuitSnips` | Esquemas limpios |
| **KiCad Projects** | `https://kicad-design.com/` | Referencias completas |
| **TSCcircuit** | `https://github.com/tscircuit/circuit-json` | JSON de circuitos |

---
*Próxima Acción: Implementar el `JLC2KiCad_lib_sync` para enriquecer nuestra `ComponentDB` con datos de producción real.*
