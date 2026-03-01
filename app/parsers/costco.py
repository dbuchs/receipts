import re
from datetime import datetime
from .base import BaseParser, ParsedReceipt, ParsedItem


class CostcoParser(BaseParser):
    name = 'costco'

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

    def parse(self, text: str, filename: str = '') -> ParsedReceipt:
        result = ParsedReceipt(merchant='Costco', parser_name=self.name)
        lines = text.splitlines()

        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        if date_match:
            try:
                result.purchase_datetime = datetime.strptime(date_match.group(1), '%m/%d/%Y')
            except ValueError:
                pass

        for label, attr in [('subtotal', 'subtotal'), ('tax', 'tax'), ('total', 'total')]:
            m = re.search(rf'(?i){label}[^\d]*\$?\s*(\d+\.\d{{2}})', text)
            if m:
                setattr(result, attr, int(float(m.group(1)) * 100))

        # Costco format: item number, description, price
        item_re = re.compile(r'^(\d{5,7})\s+(.+?)\s+(\d+\.\d{2})\s*$')
        skip_kw = {'subtotal', 'tax', 'total'}
        for line in lines:
            line_stripped = line.strip()
            m = item_re.match(line_stripped)
            if m:
                desc = m.group(2).strip()
                if any(kw in desc.lower() for kw in skip_kw):
                    continue
                price = int(float(m.group(3)) * 100)
                if 0 < price < 500000:
                    result.items.append(ParsedItem(
                        description_raw=desc,
                        description_normalized=desc.lower().strip(),
                        total_price_cents=price,
                    ))

        result.confidence = 0.75 if result.items else 0.4
        return result
