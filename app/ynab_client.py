import json
import requests
from datetime import date, timedelta
from rapidfuzz import fuzz


YNAB_BASE_URL = 'https://api.ynab.com/v1'


class YnabClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        })

    def get_budgets(self):
        resp = self.session.get(f'{YNAB_BASE_URL}/budgets')
        resp.raise_for_status()
        return resp.json()['data']['budgets']

    def get_accounts(self, budget_id: str):
        resp = self.session.get(f'{YNAB_BASE_URL}/budgets/{budget_id}/accounts')
        resp.raise_for_status()
        return resp.json()['data']['accounts']

    def get_transactions(self, budget_id: str, account_id: str = None, since_date: str = None):
        url = f'{YNAB_BASE_URL}/budgets/{budget_id}/transactions'
        params = {}
        if since_date:
            params['since_date'] = since_date
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        txns = resp.json()['data']['transactions']
        if account_id:
            txns = [t for t in txns if t.get('account_id') == account_id]
        return txns

    def update_transaction(self, budget_id: str, transaction_id: str, data: dict):
        url = f'{YNAB_BASE_URL}/budgets/{budget_id}/transactions/{transaction_id}'
        resp = self.session.put(url, json={'transaction': data})
        resp.raise_for_status()
        return resp.json()


def find_matching_transactions(receipt, transactions, top_n=5):
    """
    Returns top_n candidate YNAB transactions for a receipt.
    Scoring: amount diff, date proximity, merchant name fuzzy match.
    """
    receipt_amount = receipt.total  # cents (negative in YNAB)
    receipt_date = receipt.purchase_datetime.date() if receipt.purchase_datetime else None
    receipt_merchant = (receipt.merchant or '').lower()

    candidates = []
    for txn in transactions:
        # YNAB amounts are in milliunits (1000 = $1.00)
        txn_amount_cents = abs(txn.get('amount', 0)) // 10
        amount_diff = abs(txn_amount_cents - receipt_amount)

        # Skip if amount diff > $2.00 (200 cents)
        if amount_diff > 200:
            continue

        score = 0.0
        explanation = []

        # Amount score (0-40)
        amount_score = max(0, 40 - amount_diff / 5)
        score += amount_score
        explanation.append(f'amount diff ${amount_diff/100:.2f}')

        # Date score (0-30)
        if receipt_date:
            try:
                txn_date = date.fromisoformat(txn.get('date', ''))
                day_diff = abs((txn_date - receipt_date).days)
                if day_diff <= 3:
                    date_score = max(0, 30 - day_diff * 10)
                    score += date_score
                    explanation.append(f'date diff {day_diff}d')
                else:
                    continue  # outside ±3 days
            except (ValueError, TypeError):
                pass
        
        # Merchant/payee fuzzy match (0-30)
        payee = (txn.get('payee_name') or '').lower()
        if receipt_merchant and payee:
            fuzzy_score = fuzz.token_set_ratio(receipt_merchant, payee)
            merchant_score = fuzzy_score * 0.3
            score += merchant_score
            explanation.append(f'payee match {fuzzy_score:.0f}%')

        candidates.append({
            'transaction': txn,
            'score': round(score, 1),
            'explanation': ', '.join(explanation),
        })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[:top_n]
