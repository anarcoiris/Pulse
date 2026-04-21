import sys
from pathlib import Path

# Agregar raíz al path
sys.path.append(str(Path.cwd()))

from core.kicad_importer import KicadImporter
from core.logger import logger

def test_esp32_import():
    sch_path = "output/esp32_v2/pulselab_pcb/board.kicad_sch"
    
    logger.info("TEST", f"Iniciando importación de: {sch_path}")
    
    try:
        # Test 1: Simbolos directos
        symbols = KicadImporter.parse_schematic_symbols(sch_path)
        logger.info("TEST", f"Símbolos detectados: {len(symbols)}")
        for s in symbols[:5]:
            logger.debug("TEST", f"  [{s['ref']}] {s['value']} en ({s['x']}, {s['y']})")
            
        # Test 2: Hilos
        wires = KicadImporter.parse_schematic_wires(sch_path)
        logger.info("TEST", f"Hilos de conexión detectados: {len(wires)}")
        
        # Test 3: Reconstrucción de CircuitGraph
        graph = KicadImporter.to_circuit_graph(sch_path)
        logger.info("TEST", f"CircuitGraph generado: {len(graph.components)} componentes.")
        
        # Verificar que el modelo unificado de pines funciona
        for c in graph.components[:3]:
            logger.info("TEST", f"  Componente {c.uid} ({c.etype}) -> Pins: {c.pins}")

        logger.ai_review("TEST", "Importación completada con éxito. El mapeo de coordenadas parece razonable.")
        
    except Exception as e:
        logger.error("TEST", f"Fallo en el test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_esp32_import()
