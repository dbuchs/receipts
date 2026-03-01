from app.models import Receipt, ReceiptItem, Rule, PatternType, ReceiptStatus


def test_receipt_defaults(app):
    with app.app_context():
        from app import db
        r = Receipt(merchant='Test', total=1099)
        db.session.add(r)
        db.session.commit()
        assert r.id is not None
        assert r.status == ReceiptStatus.imported
        assert r.total_dollars == 10.99
        db.session.delete(r)
        db.session.commit()


def test_receipt_item(app):
    with app.app_context():
        from app import db
        r = Receipt(merchant='Test2', total=500)
        db.session.add(r)
        db.session.flush()
        item = ReceiptItem(receipt_id=r.id, description_raw='Milk', total_price_cents=250)
        db.session.add(item)
        db.session.commit()
        assert item.total_price_dollars == 2.50
        db.session.delete(r)
        db.session.commit()
