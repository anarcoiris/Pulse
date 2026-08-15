"""
base_provider.py
================
Abstract base class and normalized data structures for multi-provider component fetchers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class ProviderComponentResult:
    """Standardized component result from a manufacturing supplier (JLCPCB, PCBWay, etc)."""
    provider: str               # "jlcpcb", "pcbway", etc.
    part_number: str            # e.g. "C14267" (JLCPCB) or "PCBWAY-14267" (PCBWay)
    mpn: str                    # Manufacturer Part Number: "CH340G", "AMS1117-3.3"
    manufacturer: str           # e.g. "WCH", "Espressif", "AMS"
    description: str            # Human-readable product summary
    package: str                # e.g. "SOIC-16", "SOT-223", "0603"
    mounting_type: str = "SMD"  # "SMD" or "THT"
    stock_count: int = 0        # Live inventory count
    unit_price_usd: float = 0.0 # Base unit price in USD
    price_tiers: List[Dict[str, Any]] = field(default_factory=list) # [{"qty": 10, "price": 0.15}, ...]
    library_type: str = "standard" # JLCPCB: "basic" / "extended" | PCBWay: "standard" / "special"
    datasheet_url: str = ""     # Direct URL to PDF or web datasheet
    in_stock: bool = False      # True if stock_count > 0
    extra_meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.stock_count > 0 and not self.in_stock:
            self.in_stock = True

class BaseComponentProvider(ABC):
    """Interfaz abstracta para proveedores de componentes SMT."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the provider unique string identifier."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[ProviderComponentResult]:
        """Búsqueda general de componentes por término o MPN."""
        pass

    @abstractmethod
    def get_by_part_number(self, part_number: str) -> Optional[ProviderComponentResult]:
        """Obtiene información detallada por número de parte del proveedor."""
        pass
