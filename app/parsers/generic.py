import re
from datetime import datetime
from .base import BaseParser, ParsedReceipt, ParsedItem


class GenericParser(BaseParser):
    name = 'generic'

    def can_parse(self, text: str, filename: str = '') -> float:
        return 0.1  # fallback, always low confidence

    def parse(self, text: str, filename: str = '') -> ParsedReceipt:
        result = ParsedReceipt(parser_name=self.name)
        lines = text.splitlines()

        # Try to find merchant from first non-empty line
        for line in lines[:5]:
            line = line.strip()
            if line:
                result.merchant = line[:100]
                break

        # Try to find date
        date_patterns = [
            r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\w+ \d{1,2},?\s*\d{4})\b',
        ]
        for pat in date_patterns:
            m = re.search(pat, text)
            if m:
                for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%B %d, %Y', '%B %d %Y'):
                    try:
                        result.purchase_datetime = datetime.strptime(m.group(1), fmt)
                        break
                    except ValueError:
                        continue
                if result.purchase_datetime:
                    break

        # Try to find total (word boundary prevents matching 'subtotal')
        total_match = re.search(r'\b(?:total|amount due|grand total)\b[^\d]*\$?\s*(\d+\.\d{2})', text, re.IGNORECASE)
        if total_match:
            result.total = int(float(total_match.group(1)) * 100)

        subtotal_match = re.search(r'(?:subtotal|sub total|sub-total)[^\d]*\$?\s*(\d+\.\d{2})', text, re.IGNORECASE)
        if subtotal_match:
            result.subtotal = int(float(subtotal_match.group(1)) * 100)

        tax_match = re.search(r'(?:tax|sales tax|hst|gst)[^\d]*\$?\s*(\d+\.\d{2})', text, re.IGNORECASE)
        if tax_match:
            result.tax = int(float(tax_match.group(1)) * 100)

        # Try to extract line items: lines with a price at the end
        item_pattern = re.compile(r'^(.+?)\s+\$?(\d+\.\d{2})\s*$')
        skip_keywords = {'total', 'subtotal', 'tax', 'change', 'cash', 'credit', 'debit', 'balance'}
        for line in lines:
            line = line.strip()
            m = item_pattern.match(line)
            if m:
                desc = m.group(1).strip()
                if any(kw in desc.lower() for kw in skip_keywords):
                    continue
                price_cents = int(float(m.group(2)) * 100)
                if 0 < price_cents < 100000:  # sanity check
                    item = ParsedItem(
                        description_raw=desc,
                        description_normalized=desc.lower().strip(),
                        total_price_cents=price_cents,
                    )
                    result.items.append(item)

        result.confidence = 0.3 if result.total > 0 else 0.1
        return result
