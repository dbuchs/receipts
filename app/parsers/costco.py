import re
from datetime import datetime
from .base import BaseParser, ParsedReceipt, ParsedItem


class CostcoParser(BaseParser):
    name = 'costco'

    # Matches a Costco item line:
    #   optional letter prefix (tax code) + 5-7 digits, description, price,
    #   optional trailing '-' (discount/return), optional tax-code letter
    # Examples:
    #   1204135 ORG FIRM TO 6.49
    #   1204135 ORG FIRM TO 6.49 E
    #   E1204135 CABERNET 7.99
    #   29472 ORG FIRM TO 2.00-
    _ITEM_RE = re.compile(
        r'^([A-Z]?\d{5,7})\s+(.+?)\s+(\d+(?:,\d{3})*\.\d{2})(-?)\s*[A-Z]?\s*$'
    )

    # Matches a line that is *only* an item identifier (multiline format)
    _MULTILINE_ID_RE = re.compile(r'^[A-Z]?\d{5,7}\s*$')

    # Matches a trailing price at end of line (used in multiline mode)
    _PRICE_RE = re.compile(r'(\d+(?:,\d{3})*\.\d{2})(-?)\s*[A-Z]?\s*$')

    _SKIP_KW = {'subtotal', 'tax', 'total'}
    _MAX_ITEM_PRICE_CENTS = 500000  # $5,000.00

    def can_parse(self, text: str, filename: str = '') -> float:
        score = 0.0
        text_lower = text.lower()
        if 'costco' in text_lower:
            score += 0.7
        if 'costco' in filename.lower():
            score += 0.2
        if 'wholesale' in text_lower:
            score += 0.1
        if 'member' in text_lower and 'costco' in text_lower:
            score += 0.1
        return min(score, 1.0)

    @staticmethod
    def _parse_price_cents(price_str: str) -> int:
        return round(float(price_str.replace(',', '')) * 100)

    def parse(self, text: str, filename: str = '') -> ParsedReceipt:
        result = ParsedReceipt(merchant='Costco', parser_name=self.name)
        lines = text.splitlines()

        # Date: support MM/DD/YYYY and MM/DD/YY
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', text)
        if date_match:
            for fmt in ('%m/%d/%Y', '%m/%d/%y'):
                try:
                    result.purchase_datetime = datetime.strptime(date_match.group(1), fmt)
                    break
                except ValueError:
                    continue

        # Totals: SUBTOTAL, TAX, **** TOTAL
        for label, pattern, attr in [
            ('subtotal', r'(?i)subtotal[^\d]*\$?\s*(\d+\.\d{2})', 'subtotal'),
            ('tax', r'(?i)\btax\b[^\d]*\$?\s*(\d+\.\d{2})', 'tax'),
            ('total', r'(?i)\btotal\b[^\d]*\$?\s*(\d+\.\d{2})', 'total'),
        ]:
            m = re.search(pattern, text)
            if m:
                setattr(result, attr, self._parse_price_cents(m.group(1)))

        # Parse line items, handling both single-line and multiline transactions
        multiline_id = None
        multiline_name_parts = []

        for line in lines:
            line_stripped = line.strip()

            # Multiline mode: accumulate name parts until a price line is found
            if multiline_id is not None:
                price_m = self._PRICE_RE.search(line_stripped)
                if price_m:
                    # Price line ends the multiline entry
                    desc = ' '.join(multiline_name_parts).strip()
                    is_discount = price_m.group(2) == '-'
                    price = self._parse_price_cents(price_m.group(1))
                    if not any(kw in desc.lower() for kw in self._SKIP_KW) and 0 < price < self._MAX_ITEM_PRICE_CENTS:
                        result.items.append(ParsedItem(
                            description_raw=desc,
                            description_normalized=desc.lower().strip(),
                            total_price_cents=-price if is_discount else price,
                        ))
                    multiline_id = None
                    multiline_name_parts = []
                else:
                    multiline_name_parts.append(line_stripped)
                continue

            # Single-line item: identifier + description + price on one line
            m = self._ITEM_RE.match(line_stripped)
            if m:
                desc = m.group(2).strip()
                if any(kw in desc.lower() for kw in self._SKIP_KW):
                    continue
                is_discount = m.group(4) == '-'
                price = self._parse_price_cents(m.group(3))
                if 0 < price < self._MAX_ITEM_PRICE_CENTS:
                    result.items.append(ParsedItem(
                        description_raw=desc,
                        description_normalized=desc.lower().strip(),
                        total_price_cents=-price if is_discount else price,
                    ))
                continue

            # Multiline start: line is only an item identifier (no price)
            if self._MULTILINE_ID_RE.match(line_stripped):
                multiline_id = line_stripped.strip()
                multiline_name_parts = []

        result.confidence = 0.75 if result.items else 0.4
        return result
