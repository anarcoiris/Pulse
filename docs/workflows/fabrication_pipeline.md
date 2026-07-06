# Workflow: Pipeline de Fabricación Seguro (DRC Gate)

Este workflow describe el proceso de generación de archivos de fabricación, integrando validaciones obligatorias para garantizar la calidad del hardware.

## Descripción del Proceso

El pipeline sigue un flujo descendente desde la representación abstracta del circuito hasta los archivos listos para el fabricante:

1.  **Generación de Netlist**: Se extrae la conectividad del `CircuitGraph`.
2.  **Layout Espacial**: El motor de layout posiciona los componentes y traza las pistas.
3.  **Generación de PCB**: Se exporta el diseño en formato `.kicad_pcb` (KiCad 8+).
4.  **Validación de Reglas (DRC)**: **[CRÍTICO]** Antes de exportar Gerbers, se invoca `kicad-cli pcb drc`.
    -   Se verifica clearance entre pistas.
    -   Se detectan cortocircuitos.
    -   Se validan los límites de la placa.
5.  **Exportación Condicional**: 
    -   Si el DRC falla: El proceso se detiene y se genera un reporte de errores.
    -   Si el DRC pasa: Se generan Gerbers, archivos de taladro (Drill) y archivos de posición (CPL).

## Implementación Técnica

El control de este flujo reside en `bridge/kicad_bridge.py` dentro del método `export_all`.

```python
# Ejemplo de uso del pipeline seguro
bridge = KiCadBridge()
result = bridge.export_all(graph, output_dir="manufacturing", project_name="power_shield")

if "error" in result:
    print(f"Error en fabricación: {result['error']}")
    # El usuario debe corregir el layout antes de reintentar
```

## Beneficios
- **Cero Defectos**: Evita el envío de archivos con errores de diseño básicos a la fábrica.
- **Auditoría**: Genera automáticamente un `drc_report.json` para revisión técnica.
