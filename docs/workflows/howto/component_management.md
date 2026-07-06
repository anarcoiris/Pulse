# Workflow: Gestión de Componentes y Librerías KiCad

PulseLab Forge permite utilizar tanto footprints procedimentales (generados por código) como footprints estándar de la industria extraídos directamente de KiCad.

## Métodos de Obtención de Footprints

### 1. Footprints Procedimentales
Para componentes estándar (resistencias 0805, ICs DIP), el sistema genera la geometría S-expression al vuelo. Esto permite parametrización total (e.g., cambiar el número de pines de un IC dinámicamente).

### 2. Extracción de Librerías de Sistema
Para paquetes complejos o propietarios (QFP-48, ESP32, conectores USB-C), el sistema utiliza las librerías oficiales de KiCad instaladas en el host.

#### Funcionamiento de `get_kicad_footprint`:
1.  **Detección de Directorio**: Localiza las librerías en `share/kicad/footprints`.
2.  **Lectura de .kicad_mod**: Accede al archivo fuente de la librería `.pretty` especificada.
3.  **Inyección Dinámica**: PulseLab lee el S-expression, inyecta la posición `(at x y rot)` y la referencia `(property "Reference" ...)` manteniendo el resto de la geometría original.

## Configuración de Rutas

El sistema es multiplataforma y busca automáticamente en:
- **Windows**: `C:\Program Files\KiCad` y `D:\Program Files\KiCad`.
- **Linux**: `/usr/share/kicad`.
- **macOS**: `/Applications/KiCad`.

Se puede forzar una ruta específica mediante la variable de entorno `KICAD_FOOTPRINT_DIR`.

## Uso en Código

```python
# Cargar un componente directamente de la librería oficial
mcu = pcb.add_raw_footprint("U1", "Package_QFP", "LQFP-48_7x7mm_P0.5mm", x=25, y=25)
```

## Ventajas
- **Precisión Industrial**: Uso de geometrías validadas por la comunidad KiCad.
- **Extensibilidad**: Soporte inmediato para miles de componentes sin escribir código adicional.
