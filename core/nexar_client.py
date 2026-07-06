import requests
import json
from typing import List, Dict, Optional

class NexarClient:
    """
    Cliente para la API GraphQL de Nexar (Octopart).
    Permite buscar componentes electrónicos y extraer metadatos técnicos.
    """
    URL = "https://api.nexar.com/graphql"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def query(self, graphql_query: str, variables: Optional[Dict] = None) -> Dict:
        """Ejecuta una consulta GraphQL."""
        payload = {"query": graphql_query, "variables": variables or {}}
        response = requests.post(self.URL, headers=self.headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Nexar API Error {response.status_code}: {response.text}")
            
        data = response.json()
        if "errors" in data:
            raise Exception(f"GraphQL Errors: {json.dumps(data['errors'], indent=2)}")
            
        return data["data"]

    def search_components(self, query: str, limit: int = 5) -> List[Dict]:
        """Busca componentes por texto libre o MPN."""
        gql = """
        query Search($q: String!, $limit: Int!) {
          supSearch(q: $q, limit: $limit) {
            results {
              part {
                mpn
                manufacturer {
                  name
                }
                shortDescription
                bestDatasheet {
                  url
                }
                specs {
                  attribute {
                    name
                    shortname
                  }
                  value
                }
              }
            }
          }
        }
        """
        try:
            res = self.query(gql, {"q": query, "limit": limit})
            parts = []
            for r in res.get("supSearch", {}).get("results", []):
                p = r["part"]
                parts.append({
                    "id": p["mpn"],
                    "manufacturer": p["manufacturer"]["name"],
                    "description": p["shortDescription"],
                    "datasheet": p["bestDatasheet"]["url"] if p["bestDatasheet"] else "",
                    "params": {s["attribute"]["shortname"]: s["value"] for s in p["specs"]}
                })
            return parts
        except Exception as e:
            print(f"Error en búsqueda Nexar: {e}")
            return []

if __name__ == "__main__":
    # Test rápido (usando el token proporcionado)
    TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjA5NzI5QTkyRDU0RDlERjIyRDQzMENBMjNDNkI4QjJFIiwidHlwIjoiYXQrand0In0.eyJuYmYiOjE3NzcxNjcyNjAsImV4cCI6MTc3NzI1MzY2MCwiaXNzIjoiaHR0cHM6Ly9pZGVudGl0eS5uZXhhci5jb20iLCJjbGllbnRfaWQiOiJiODMzMTgyZi02NjE4LTQzMGYtOTc1Mi1hMGEzZWEwNDNhMDQiLCJzdWIiOiJFNkFGNTlCQi1FNUUxLTQ1QjgtODFGMS01NEJFNEFBMEM0N0UiLCJhdXRoX3RpbWUiOjE3NzcxNjcxNDcsImlkcCI6ImxvY2FsIiwicHJpdmF0ZV9jbGFpbXNfaWQiOiJmZTIyZDRlMS1jNWUwLTQ2ZWQtOGI3ZC01M2RkZjgzMzU0MzAiLCJwcml2YXRlX2NsYWltc19zZWNyZXQiOiJCa3U5b3NYRW85SitnUHhKeVcvZjNKVlpTYmZEa2N5N2NKVndpSGVQMkFNPSIsImp0aSI6IkYyQTA5RkI3MDY3QTA2RDlBNzcyOUYxNDU1RTkxMDNGIiwic2lkIjoiOUYyOEUzRUI5RTYyNjI1OUM1MjQ5Nzc4ODU2RTlGN0QiLCJpYXQiOjE3NzcxNjcyNjAsInNjb3BlIjpbIm9wZW5pZCIsInVzZXIuYWNjZXNzIiwicHJvZmlsZSIsImVtYWlsIiwidXNlci5kZXRhaWxzIiwiZGVzaWduLmRvbWFpbiIsInN1cHBseS5kb21haW4iXSwiYW1yIjpbInB3ZCJdfQ.NK9FsFYhC9tmN-Dc0edStqofwXVlSDGpmIvQr8H2N22zYt5CV4xxg-AGEwkhzm1RL2LZ_SmYEDNgxsH4v0qyA1Zuqz7WepbJVV2e6Pl_KBPvW-hL5CVkbs_BzrxL5HEEk4iAahyxKpLVEdoC6Av8KuB9n4labjBSdc-0G3sqihonbqRELUtUrMIirvUSkAXgOH1hdRQFIkPndc6wDliTqddNBTt9i24RrEgqOyqAlSEZChcrkxK-kDWuOkIEHucQX1mKOUdzr8Tw0Ioh47RPP_GJFe2YN6tZ3F3wOc5Nfuv-2FOxuOzxJ4RUDOxePvJvfaz9bHLfVVnVPFroVxxGxA"
    client = NexarClient(TOKEN)
    results = client.search_components("ESP32-WROOM-32", limit=1)
    print(json.dumps(results, indent=2))
