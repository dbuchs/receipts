from .walmart import WalmartParser
from .costco import CostcoParser
from .aldi import AldiParser
from .generic import GenericParser

ALL_PARSERS = [WalmartParser(), CostcoParser(), AldiParser(), GenericParser()]

def detect_parser(text: str, filename: str = ''):
    """Return the parser with the highest confidence for this text."""
    best = None
    best_score = -1.0
    for parser in ALL_PARSERS:
        score = parser.can_parse(text, filename)
        if score > best_score:
            best_score = score
            best = parser
    return best, best_score
