"""
jlcpcb_fetcher.py
=================
JLCPCB / LCSC SMT Component Catalog Fetcher for PulseLab.
"""
import json
import urllib.request
import urllib.parse
from typing import List, Optional, Dict, Any
from core.providers.base_provider import BaseComponentProvider, ProviderComponentResult
from core.logger import logger

class JLCPCBProviderFetcher(BaseComponentProvider):
    """Fetcher para el catálogo SMT y componentes LCSC de JLCPCB."""

    @property
    def provider_name(self) -> str:
        return "jlcpcb"

    def search(self, query: str, limit: int = 10) -> List[ProviderComponentResult]:
        """
        Busca componentes en el catálogo JLCPCB / LCSC.
        Prioriza la base de datos local y realiza búsqueda remota como extensión.
        """
        # 1. First check local catalog for instant and offline resolution
        local_results = self._fallback_local_search(query, limit)
        if local_results:
            return local_results[:limit]

        # 2. Remote lookup fallback
        results = []
        try:
            url = "https://jlcpcb.com/api/overseas-pcb-order/v1/smt/components/search"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PulseLab/1.0",
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/plain, */*"
            }
            payload = json.dumps({
                "keyword": query,
                "pageSize": limit,
                "pageNo": 1,
                "searchType": "ALL"
            }).encode("utf-8")

            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                component_list = data.get("data", {}).get("list", []) or data.get("data", []) or []
                for comp in component_list[:limit]:
                    item = self._parse_jlc_item(comp)
                    if item:
                        results.append(item)
        except Exception:
            pass

        return results or local_results

    def get_by_part_number(self, part_number: str) -> Optional[ProviderComponentResult]:
        """
        Obtiene información de un componente específico por código LCSC (ej. C14267, C2913202).
        """
        code = part_number.upper().strip()
        if not code.startswith("C") and code.isdigit():
            code = f"C{code}"

        res = self.search(code, limit=1)
        if res:
            return res[0]
        return None

    def _parse_jlc_item(self, comp: Dict[str, Any]) -> Optional[ProviderComponentResult]:
        """Convierte una respuesta JSON de JLCPCB en ProviderComponentResult."""
        try:
            part_no = comp.get("componentCode") or comp.get("lcscPartNumber") or comp.get("code")
            if not part_no:
                return None

            mpn = comp.get("componentModelEn") or comp.get("mpn") or comp.get("componentModel") or part_no
            mfg = comp.get("manufacturerHeaderEn") or comp.get("manufacturer") or "Generic"
            desc = comp.get("describe") or comp.get("componentSpecificationEn") or comp.get("description") or ""
            pkg = comp.get("componentSpecificationEn") or comp.get("package") or comp.get("footprint") or ""
            stock = int(comp.get("stockCount") or comp.get("stock") or 0)
            lib_type = "basic" if str(comp.get("componentLibraryType", "")).lower() in ("base", "basic", "0") else "extended"

            # Parse pricing
            prices = comp.get("componentPrices") or comp.get("prices") or []
            unit_price = 0.0
            price_tiers = []
            if isinstance(prices, list):
                for p in prices:
                    if isinstance(p, dict):
                        q = p.get("startNumber") or p.get("qty") or 1
                        pr = float(p.get("productPrice") or p.get("price") or 0.0)
                        price_tiers.append({"qty": q, "price": pr})
                        if unit_price == 0.0:
                            unit_price = pr

            datasheet = comp.get("dataManualUrl") or comp.get("datasheetUrl") or f"https://lcsc.com/product-detail/{part_no}.html"

            return ProviderComponentResult(
                provider="jlcpcb",
                part_number=part_no,
                mpn=mpn,
                manufacturer=mfg,
                description=desc,
                package=pkg,
                mounting_type="SMD",
                stock_count=stock,
                unit_price_usd=unit_price,
                price_tiers=price_tiers,
                library_type=lib_type,
                datasheet_url=datasheet,
                in_stock=stock > 0,
                extra_meta={"jlcpcb_library": lib_type}
            )
        except Exception as err:
            logger.warning("jlcpcb_fetcher", f"Error parsing JLCPCB item: {err}")
            return None

    def _fallback_local_search(self, query: str, limit: int) -> List[ProviderComponentResult]:
        """Parse local components database when network is offline."""
        from core.component_db import ComponentDB
        db = ComponentDB()
        q_clean = query.strip().lower()
        matches = db.search(query, top_k=limit)
        
        # If no match from text search, check direct id or jlcpcb_part match
        if not matches:
            for comp_obj in db.all():
                if comp_obj.jlcpcb_part.lower() == q_clean or comp_obj.id.lower() == q_clean:
                    matches.append({"component": comp_obj.to_dict()})
                    if len(matches) >= limit:
                        break

        results = []
        for m in matches:
            c = m["component"]
            jlc_id = c.get("jlcpcb_part", "C00000")
            results.append(
                ProviderComponentResult(
                    provider="jlcpcb",
                    part_number=jlc_id if jlc_id != "N/A" else f"C_{c['id']}",
                    mpn=c.get("id", ""),
                    manufacturer=c.get("manufacturer", "Generic"),
                    description=c.get("notes", c.get("category", "")),
                    package=c.get("footprint_info", {}).get("package", c.get("kicad_footprint", "")),
                    mounting_type=c.get("footprint_info", {}).get("mounting_type", "SMD"),
                    stock_count=1000,
                    unit_price_usd=0.25,
                    library_type="basic" if jlc_id in ("C6186", "C165948", "C14663") else "extended",
                    datasheet_url=c.get("datasheet", ""),
                    in_stock=True
                )
            )
        return results
