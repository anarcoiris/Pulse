import os
import requests
import time
from pathlib import Path

class GitHubPCBCrawler:
    """
    Busca y descarga diseños de KiCad (.kicad_pcb) desde GitHub
    para construir el dataset de entrenamiento.
    """
    
    def __init__(self, token: str = None):
        self.base_url = "https://api.github.com"
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"
        
        self.save_dir = Path("knowledge/data/raw_kicad")
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def search_kicad_repos(self, query="topic:kicad", max_repos=10):
        url = f"{self.base_url}/search/repositories"
        params = {"q": query, "sort": "stars", "order": "desc", "per_page": max_repos}
        
        print(f"🔍 Buscando repositorios KiCad (query: {query})...")
        res = requests.get(url, headers=self.headers, params=params)
        if res.status_code != 200:
            print(f"❌ Error API GitHub: {res.status_code} - {res.text}")
            return []
            
        return res.json().get("items", [])

    def download_pcb_files(self, repo_full_name):
        """Busca archivos .kicad_pcb en un repo y los descarga."""
        search_url = f"{self.base_url}/search/code"
        # Buscamos archivos .kicad_pcb en el repo específico
        query = f"extension:kicad_pcb repo:{repo_full_name}"
        res = requests.get(search_url, headers=self.headers, params={"q": query})
        
        if res.status_code != 200:
            return 0
            
        items = res.json().get("items", [])
        downloaded = 0
        
        for item in items:
            raw_url = item["html_url"].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            file_name = f"{repo_full_name.replace('/', '_')}_{item['name']}"
            
            print(f"  📥 Descargando: {item['name']}...")
            f_res = requests.get(raw_url)
            if f_res.status_code == 200:
                with open(self.save_dir / file_name, "wb") as f:
                    f.write(f_res.content)
                downloaded += 1
                time.sleep(1) # Rate limit protection
                
        return downloaded

if __name__ == "__main__":
    # Nota: Usar un token de GitHub aumenta los límites de la API
    crawler = GitHubPCBCrawler()
    repos = crawler.search_kicad_repos(max_repos=5)
    
    total = 0
    for repo in repos:
        print(f"🚀 Procesando {repo['full_name']} ({repo['stargazers_count']} ⭐)")
        count = crawler.download_pcb_files(repo['full_name'])
        total += count
        
    print(f"\n✅ Proceso completado. {total} archivos de diseño listos en {crawler.save_dir}")
