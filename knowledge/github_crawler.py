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

    def download_kicad_files(self, repo_full_name, file_extension="kicad_sch"):
        """Busca archivos de KiCad en un repo y los descarga usando la API de git/trees."""
        # Obtenemos la rama por defecto
        repo_info_url = f"{self.base_url}/repos/{repo_full_name}"
        repo_res = requests.get(repo_info_url, headers=self.headers)
        if repo_res.status_code != 200:
            print(f"❌ Error API GitHub al obtener repo: {repo_res.status_code} - {repo_res.text}")
            return 0
            
        default_branch = repo_res.json().get("default_branch", "master")
        
        # Obtenemos el árbol de archivos recursivamente
        tree_url = f"{self.base_url}/repos/{repo_full_name}/git/trees/{default_branch}?recursive=1"
        tree_res = requests.get(tree_url, headers=self.headers)
        
        if tree_res.status_code != 200:
            print(f"❌ Error API GitHub al obtener tree: {tree_res.status_code} - {tree_res.text}")
            return 0
            
        tree = tree_res.json().get("tree", [])
        # Filtramos por extensión
        items = [item for item in tree if item.get("type") == "blob" and item.get("path", "").endswith(f".{file_extension}")]
        
        downloaded = 0
        
        for item in items:
            path = item["path"]
            filename = os.path.basename(path)
            raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{default_branch}/{path}"
            file_name = f"{repo_full_name.replace('/', '_')}_{filename}"
            
            print(f"  📥 Descargando: {filename}...")
            f_res = requests.get(raw_url)
            if f_res.status_code == 200:
                with open(self.save_dir / file_name, "wb") as f:
                    f.write(f_res.content)
                downloaded += 1
                time.sleep(1) # Protección contra rate limit de descargas raw
                
        return downloaded

if __name__ == "__main__":
    # Nota: Usar un token de GitHub aumenta los límites de la API
    crawler = GitHubPCBCrawler()
    repos = crawler.search_kicad_repos(max_repos=5)
    
    total = 0
    for repo in repos:
        print(f"🚀 Procesando {repo['full_name']} ({repo['stargazers_count']} ⭐)")
        # Descargamos esquemáticos que contienen la información lógica necesaria
        count = crawler.download_kicad_files(repo['full_name'], file_extension="kicad_sch")
        total += count
        
    print(f"\n✅ Proceso completado. {total} archivos de diseño listos en {crawler.save_dir}")
