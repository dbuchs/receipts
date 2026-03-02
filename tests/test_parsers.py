from app.parsers.generic import GenericParser
from app.parsers.walmart import WalmartParser
from app.parsers.costco import CostcoParser
from app.parsers.aldi import AldiParser
from app.parsers import detect_parser


def test_generic_parser_basic():
    parser = GenericParser()
    text = """
My Store
Date: 01/15/2024
Apples             2.99
Bananas            1.49
Subtotal           4.48
Tax                0.40
Total              4.88
"""
    result = parser.parse(text)
    assert result.total == 488
    assert result.subtotal == 448
    assert len(result.items) >= 1


def test_walmart_detection():
    text = "WALMART SUPERCENTER\nSave Money. Live Better.\n"
    parser = WalmartParser()
    score = parser.can_parse(text, 'walmart_receipt.txt')
    assert score > 0.8


def test_costco_detection():
    text = "COSTCO WHOLESALE\nMember #: 123456\n"
    parser = CostcoParser()
    score = parser.can_parse(text, 'costco.txt')
    assert score > 0.7


def test_aldi_detection():
    text = "ALDI\nThank you for shopping at ALDI\n"
    parser = AldiParser()
    score = parser.can_parse(text, 'aldi_receipt.txt')
    assert score > 0.7


def test_detect_parser_walmart():
    text = "WALMART SUPERCENTER\nItem1   5.99\nTotal  5.99\n"
    parser, score = detect_parser(text, 'walmart.txt')
    assert parser.name == 'walmart'
    assert score > 0.7


def test_detect_parser_fallback():
    text = "Some random text with no merchant info"
    parser, score = detect_parser(text, 'unknown.txt')
    assert parser is not None  # fallback to generic


def test_costco_parser_single_line_items():
    parser = CostcoParser()
    text = (
        "COSTCO WHOLESALE\n"
        "Member 121549142109\n"
        "1204135 ORG FIRM TO  6.49\n"
        "1056789 PAPER TOWELS  19.99\n"
        "SUBTOTAL  26.48\n"
        "TAX  1.50\n"
        "**** TOTAL  27.98\n"
        "01/15/2024\n"
    )
    result = parser.parse(text)
    assert len(result.items) == 2
    assert result.items[0].description_raw == 'ORG FIRM TO'
    assert result.items[0].total_price_cents == 649
    assert result.items[1].total_price_cents == 1999
    assert result.total == 2798
    assert result.tax == 150


def test_costco_parser_tax_code_letter():
    parser = CostcoParser()
    text = (
        "COSTCO WHOLESALE\n"
        "1204135 ORG FIRM TO  6.49 E\n"
        "**** TOTAL  6.49\n"
    )
    result = parser.parse(text)
    assert len(result.items) == 1
    assert result.items[0].total_price_cents == 649


def test_costco_parser_leading_letter_item_id():
    parser = CostcoParser()
    text = (
        "COSTCO WHOLESALE\n"
        "E1204135 ORGANIC MILK  5.99\n"
        "**** TOTAL  5.99\n"
    )
    result = parser.parse(text)
    assert len(result.items) == 1
    assert result.items[0].total_price_cents == 599


def test_costco_parser_discount_item():
    parser = CostcoParser()
    text = (
        "COSTCO WHOLESALE\n"
        "1204135 ORG FIRM TO  6.49\n"
        "294721 ORG FIRM TO  2.00-\n"
        "**** TOTAL  4.49\n"
    )
    result = parser.parse(text)
    assert len(result.items) == 2
    # Discount should be stored as negative cents
    prices = {item.total_price_cents for item in result.items}
    assert 649 in prices
    assert -200 in prices


def test_costco_parser_multiline_item():
    parser = CostcoParser()
    text = (
        "COSTCO WHOLESALE\n"
        "900091\n"
        "CABERNET\n"
        "7.99\n"
        "**** TOTAL  7.99\n"
    )
    result = parser.parse(text)
    assert len(result.items) == 1
    assert result.items[0].total_price_cents == 799
    assert 'cabernet' in result.items[0].description_normalized


def test_costco_parser_date_two_digit_year():
    parser = CostcoParser()
    text = (
        "COSTCO WHOLESALE\n"
        "1204135 ORG FIRM TO  6.49\n"
        "**** TOTAL  6.49\n"
        "01/15/24\n"
    )
    result = parser.parse(text)
    assert result.purchase_datetime is not None
    assert result.purchase_datetime.year == 2024
