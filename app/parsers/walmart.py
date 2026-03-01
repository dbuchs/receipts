import re
from datetime import datetime
from .base import BaseParser, ParsedReceipt, ParsedItem


class WalmartParser(BaseParser):
    name = 'walmart'

    def can_parse(self, text: str, filename: str = '') -> float:
        score = 0.0
        text_lower = text.lower()
        filename_lower = filename.lower()
        if 'walmart' in text_lower or 'wal-mart' in text_lower:
            score += 0.7
        if 'walmart' in filename_lower:
            score += 0.2
        if 'save money. live better' in text_lower:
            score += 0.3
        return min(score, 1.0)

    def parse(self, text: str, filename: str = '') -> ParsedReceipt:
        result = ParsedReceipt(merchant='Walmart', parser_name=self.name)
        lines = text.splitlines()

        # Date pattern
        date_match = re.search(r'(\d{2}/\d{2}/\d{2,4})', text)
        if date_match:
            for fmt in ('%m/%d/%Y', '%m/%d/%y'):
                try:
                    result.purchase_datetime = datetime.strptime(date_match.group(1), fmt)
                    break
                except ValueError:
                    continue

        # Totals
        for label, attr in [
            (r'subtotal', 'subtotal'),
            (r'tax', 'tax'),
            (r'total', 'total'),
        ]:
            m = re.search(rf'(?i){label}[^\d]*\$?\s*(\d+\.\d{{2}})', text)
            if m:
                setattr(result, attr, int(float(m.group(1)) * 100))

        # Line items: description followed by price
        item_re = re.compile(r'^(.{3,50})\s{2,}\$?(\d+\.\d{2})\s*[NF]?\s*$')
        skip_kw = {'subtotal', 'tax', 'total', 'change', 'cash', 'credit', 'debit'}
        for line in lines:
            line_stripped = line.strip()
            m = item_re.match(line_stripped)
            if m:
                desc = m.group(1).strip()
                if any(kw in desc.lower() for kw in skip_kw):
                    continue
                price = int(float(m.group(2)) * 100)
                if 0 < price < 100000:
                    result.items.append(ParsedItem(
                        description_raw=desc,
                        description_normalized=desc.lower().strip(),
                        total_price_cents=price,
                    ))

        result.confidence = 0.75 if result.items else 0.4
        return result
