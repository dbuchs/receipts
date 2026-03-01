from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class ParsedItem:
    description_raw: str
    description_normalized: str
    quantity: Optional[float] = None
    unit_price_cents: Optional[int] = None
    total_price_cents: int = 0


@dataclass
class ParsedReceipt:
    merchant: Optional[str] = None
    purchase_datetime: Optional[datetime] = None
    subtotal: int = 0
    tax: int = 0
    total: int = 0
    currency: str = 'USD'
    items: List[ParsedItem] = field(default_factory=list)
    confidence: float = 0.0
    parser_name: str = 'unknown'


class BaseParser:
    name = 'base'

    def can_parse(self, text: str, filename: str = '') -> float:
        """Return confidence 0-1 that this parser handles this receipt."""
        return 0.0

    def parse(self, text: str, filename: str = '') -> ParsedReceipt:
        raise NotImplementedError
