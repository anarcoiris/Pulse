import json
import os
from pathlib import Path
from datetime import datetime

class LayoutAI:
    """
    DEPRECATED/TEMPORARY: Este módulo de recolección de datos y colocación heurística
    es temporal y está acoplado al andamiaje de PyGame. Será reemplazado por la Phase 3
    (arquitectura web-first y el flujo unificado en `knowledge/design_experience.py`).
    
    Sistema de inteligencia para el layout de PCBs.
    Fase 1: Recolección de datos (Dataset generation).
    Fase 2: Heurísticas de colocación.
    Fase 3: Entrenamiento de GNN (Graph Neural Network).
    """
    
    def __init__(self, dataset_path: str = "knowledge/data/training"):
        self.dataset_path = Path(dataset_path)
        self.dataset_path.mkdir(parents=True, exist_ok=True)

    def record_design(self, graph, metadata: dict = None):
        """Guarda un par (Netlist, Placement) para futuro entrenamiento."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            sample_file = self.dataset_path / f"sample_{timestamp}.json"
            
            data = {
                "timestamp": timestamp,
                "metadata": metadata or {},
                "circuit": graph.to_json()
            }
            
            with open(sample_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
            return True
        except Exception as e:
            print(f"Error guardando muestra de entrenamiento: {e}")
            return False

    def suggest_layout(self, graph):
        """
        Placeholder para el modelo de IA. 
        Por ahora usa un algoritmo de 'Spring-Layout' o heurística simple.
        """
        # TODO: Implementar inferencia con modelo pre-entrenado
        pass

# Instancia global para recolección automática
layout_engine = LayoutAI()
