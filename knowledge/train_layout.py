import torch
import torch.nn as nn
import torch.optim as optim
from knowledge.dataset_processor import CircuitDatasetProcessor
from knowledge.models.layout_gnn import LayoutGNN

def train():
    print("🚀 Iniciando entrenamiento de PulseLab Layout AI...")
    
    processor = CircuitDatasetProcessor()
    samples = processor.load_samples()
    
    if not samples:
        print("❌ No hay muestras suficientes en knowledge/data/training/")
        return

    model = LayoutGNN(node_features=2, hidden_dim=64)
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.MSELoss()

    model.train()
    epochs = 100
    
    for epoch in range(epochs):
        total_loss = 0
        for sample in samples:
            data = processor.process_sample(sample)
            x, y, edge_index = data["x"], data["y"], data["edge_index"]
            
            optimizer.zero_grad()
            pred = model(x, edge_index)
            
            loss = criterion(pred, y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        if (epoch + 1) % 10 == 0:
            print(f"Época [{epoch+1}/{epochs}], Loss: {total_loss/len(samples):.4f}")

    # Guardar los pesos
    save_path = "knowledge/models/layout_weights.pth"
    torch.save(model.state_dict(), save_path)
    print(f"\n✅ Entrenamiento completado. Pesos guardados en {save_path}")

if __name__ == "__main__":
    train()
