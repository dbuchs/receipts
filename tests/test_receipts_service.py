import io
import os
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage


def test_allowed_file(app):
    with app.app_context():
        from app.receipts.service import allowed_file
        assert allowed_file('receipt.pdf')
        assert allowed_file('receipt.html')
        assert allowed_file('receipt.txt')
        assert not allowed_file('receipt.jpg')
        assert not allowed_file('receipt.exe')


def test_import_txt_receipt(app, tmp_path):
    with app.app_context():
        from app import db
        from app.receipts.service import import_receipt_file
        from app.models import Receipt

        content = b"Walmart\n01/15/2024\nApples             2.99\nTotal              2.99\n"
        fs = FileStorage(
            stream=io.BytesIO(content),
            filename='test_walmart.txt',
            content_type='text/plain',
        )
        receipt = import_receipt_file(fs)
        assert receipt.id is not None
        assert receipt.merchant is not None

        # cleanup
        if receipt.stored_path and os.path.exists(receipt.stored_path):
            os.remove(receipt.stored_path)
        db.session.delete(receipt)
        db.session.commit()
