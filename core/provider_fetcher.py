"""
provider_fetcher.py
===================
Unified Provider Fetch Manager for PulseLab Component Supply Chain Integration.

Coordinates queries across JLCPCB (LCSC) and PCBWay fetchers with local disk caching.
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from core.providers.base_provider import BaseComponentProvider, ProviderComponentResult
from core.providers.jlcpcb_fetcher import JLCPCBProviderFetcher
from core.providers.pcbway_fetcher import PCBWayProviderFetcher
from core.logger import logger

_HERE = Path(__file__).resolve().parent
_CACHE_DIR = _HERE.parent / "knowledge" / "cache"
_CACHE_FILE = _CACHE_DIR / "provider_components_cache.json"

class ProviderFetchManager:
    """Gestor unificado de búsqueda de componentes entre proveedores SMT (JLCPCB y PCBWay)."""

    def __init__(self, ttl_seconds: int = 86400):
        self.ttl = ttl_seconds
        self.providers: Dict[str, BaseComponentProvider] = {
            "jlcpcb": JLCPCBProviderFetcher(),
            "pcbway": PCBWayProviderFetcher(),
        }
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if _CACHE_FILE.exists():
            try:
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.warning("provider_fetcher", f"Error loading cache: {e}")
                self._cache = {}

    def _save_cache(self) -> None:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning("provider_fetcher", f"Error saving cache: {e}")

    def search_all_providers(self, query: str, limit: int = 5) -> Dict[str, List[ProviderComponentResult]]:
        """
        Busca componentes simultáneamente en todos los proveedores registrados (JLCPCB y PCBWay).

        Returns:
            Dict de provider_name -> lista de ProviderComponentResult.
        """
        cache_key = f"search:{query.lower().strip()}"
        now = time.time()

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if now - entry.get("timestamp", 0) < self.ttl:
                # Reconstruct from cache
                cached_data = entry.get("data", {})
                res = {}
                for p_name, items in cached_data.items():
                    res[p_name] = [ProviderComponentResult(**item) for item in items]
                return res

        results = {}
        for p_name, provider in self.providers.items():
            try:
                res = provider.search(query, limit=limit)
                results[p_name] = res
            except Exception as e:
                logger.warning("provider_fetcher", f"Error querying provider {p_name}: {e}")
                results[p_name] = []

        # Store in cache
        serializable = {
            p_name: [item.__dict__ for item in items]
            for p_name, items in results.items()
        }
        self._cache[cache_key] = {
            "timestamp": now,
            "data": serializable
        }
        self._save_cache()

        return results

    def get_component_comparison(self, mpn_or_query: str) -> Dict[str, Any]:
        """
        Genera una comparativa lado a lado entre JLCPCB y PCBWay para la toma de decisiones humanas.
        """
        raw_results = self.search_all_providers(mpn_or_query, limit=5)
        jlc_list = raw_results.get("jlcpcb", [])
        pcbway_list = raw_results.get("pcbway", [])

        jlc_best = jlc_list[0] if jlc_list else None
        pcbway_best = pcbway_list[0] if pcbway_list else None

        comparison = {
            "query": mpn_or_query,
            "jlcpcb": {
                "part_number": jlc_best.part_number if jlc_best else "N/A",
                "mpn": jlc_best.mpn if jlc_best else "N/A",
                "manufacturer": jlc_best.manufacturer if jlc_best else "N/A",
                "stock": jlc_best.stock_count if jlc_best else 0,
                "unit_price_usd": jlc_best.unit_price_usd if jlc_best else 0.0,
                "library_type": jlc_best.library_type if jlc_best else "N/A",
                "datasheet_url": jlc_best.datasheet_url if jlc_best else "N/A",
                "in_stock": jlc_best.in_stock if jlc_best else False,
            },
            "pcbway": {
                "part_number": pcbway_best.part_number if pcbway_best else "N/A",
                "mpn": pcbway_best.mpn if pcbway_best else "N/A",
                "manufacturer": pcbway_best.manufacturer if pcbway_best else "N/A",
                "stock": pcbway_best.stock_count if pcbway_best else 0,
                "unit_price_usd": pcbway_best.unit_price_usd if pcbway_best else 0.0,
                "library_type": pcbway_best.library_type if pcbway_best else "N/A",
                "datasheet_url": pcbway_best.datasheet_url if pcbway_best else "N/A",
                "in_stock": pcbway_best.in_stock if pcbway_best else False,
            },
            "recommendation": self._recommend_supplier(jlc_best, pcbway_best)
        }
        return comparison

    def _recommend_supplier(self, jlc: Optional[ProviderComponentResult], pcbway: Optional[ProviderComponentResult]) -> str:
        if not jlc and not pcbway:
            return "No provider options available."
        if jlc and not pcbway:
            return f"JLCPCB recommended ({jlc.part_number}, Stock: {jlc.stock_count})"
        if pcbway and not jlc:
            return f"PCBWay recommended ({pcbway.part_number}, Stock: {pcbway.stock_count})"

        if jlc.library_type == "basic" and jlc.in_stock:
            return f"JLCPCB recommended (Basic Library part {jlc.part_number}, 0 setup fee, Stock: {jlc.stock_count})"
        if jlc.unit_price_usd <= pcbway.unit_price_usd and jlc.in_stock:
            return f"JLCPCB recommended ({jlc.part_number}, ${jlc.unit_price_usd:.3f}/unit, Stock: {jlc.stock_count})"
        if pcbway.in_stock:
            return f"PCBWay recommended ({pcbway.part_number}, ${pcbway.unit_price_usd:.3f}/unit, Stock: {pcbway.stock_count})"

        return "Both providers out of stock or requires manual evaluation."
