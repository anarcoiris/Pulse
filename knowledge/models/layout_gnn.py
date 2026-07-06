import torch
import torch.nn as nn
import torch.nn.functional as F

class SimpleGraphConv(nn.Module):
    """
    Capa de convolución de grafos básica (estilo Kipf & Welling).
    Agrega información de los vecinos para actualizar las features del nodo.
    """
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.lin = nn.Linear(in_channels, out_channels)

    def forward(self, x, edge_index):
        # x: (N, in_channels)
        # edge_index: (2, E)
        
        num_nodes = x.size(0)
        
        # 1. Message passing: Sumar features de vecinos
        adj = torch.zeros((num_nodes, num_nodes), device=x.device)
        if edge_index.numel() > 0:
            adj[edge_index[0], edge_index[1]] = 1
        
        # Añadir self-loops
        adj += torch.eye(num_nodes, device=x.device)
        
        # 2. Agregación: A * X
        out = torch.mm(adj, x)
        
        # 3. Transformación lineal
        return self.lin(out)

class LayoutGNN(nn.Module):
    """
    Modelo GNN para predecir coordenadas (x, y) de componentes.
    """
    def __init__(self, node_features=2, hidden_dim=64):
        super().__init__()
        self.conv1 = SimpleGraphConv(node_features, hidden_dim)
        self.conv2 = SimpleGraphConv(hidden_dim, hidden_dim)
        self.conv3 = SimpleGraphConv(hidden_dim, 32)
        
        # Capa final para predecir coordenadas (x, y)
        self.head = nn.Linear(32, 2)

    def forward(self, x, edge_index):
        # Encoder
        x = F.relu(self.conv1(x, edge_index))
        x = F.relu(self.conv2(x, edge_index))
        x = F.relu(self.conv3(x, edge_index))
        
        # Decoder (Coordenadas)
        coords = self.head(x)
        return coords

if __name__ == "__main__":
    # Test simple
    model = LayoutGNN()
    x = torch.randn(5, 2) # 5 componentes, 2 features
    edges = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]], dtype=torch.long)
    out = model(x, edges)
    print(f"Salida (coordenadas predichas):\n{out}")
