import json
import os
import torch
import numpy as np
from pathlib import Path
from typing import List, Tuple

class CircuitDatasetProcessor:
    """
    Convierte el dataset de PulseLab en Tensores de PyTorch.
    Mapea tipos de componentes a IDs numéricos y normaliza coordenadas.
    """
    
    TYPE_MAP = {"R": 0, "C": 1, "L": 2, "V": 3, "S": 4, "GND": 5, "IC": 6, "MCU": 7}
    
    def __init__(self, training_dir: str = "knowledge/data/training"):
        self.training_dir = Path(training_dir)

    def load_samples(self) -> List[dict]:
        samples = []
        for file in self.training_dir.glob("sample_*.json"):
            with open(file, "r", encoding="utf-8") as f:
                samples.append(json.load(f))
        return samples

    def process_sample(self, sample: dict):
        circuit = sample["circuit"]
        comps = circuit.get("components", [])
        
        # 1. Feature matrix (N, F): [etype_id, value]
        x = []
        # 2. Target coordinates (N, 2): [grid_c, grid_r]
        y = []
        
        comp_to_idx = {}
        for i, c in enumerate(comps):
            etype_id = self.TYPE_MAP.get(c["etype"], 6)
            x.append([etype_id, float(c.get("value", 0))])
            y.append([c["grid_c"], c["grid_r"]])
            comp_to_idx[c["uid"]] = i
            
        # 3. Edge index (2, E): Conexiones entre componentes
        edge_index = []
        # Agrupamos por nodos (nets) para encontrar conexiones
        nets = {}
        for c in comps:
            for pin_id, net in c.get("pins", {}).items():
                if net not in nets: nets[net] = []
                nets[net].append(c["uid"])
        
        for net, uids in nets.items():
            for i in range(len(uids)):
                for j in range(i + 1, len(uids)):
                    u1, u2 = uids[i], uids[j]
                    idx1, idx2 = comp_to_idx[u1], comp_to_idx[u2]
                    edge_index.append([idx1, idx2])
                    edge_index.append([idx2, idx1]) # Grafo no dirigido
                    
        return {
            "x": torch.tensor(x, dtype=torch.float),
            "y": torch.tensor(y, dtype=torch.float),
            "edge_index": torch.tensor(edge_index, dtype=torch.long).t().contiguous() if edge_index else torch.zeros((2, 0), dtype=torch.long)
        }

if __name__ == "__main__":
    processor = CircuitDatasetProcessor()
    samples = processor.load_samples()
    print(f"Muestras encontradas: {len(samples)}")
    if samples:
        data = processor.process_sample(samples[0])
        print(f"Features shape: {data['x'].shape}")
        print(f"Edges shape: {data['edge_index'].shape}")
