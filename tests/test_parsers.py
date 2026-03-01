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
