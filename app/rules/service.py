import re
from app import db
from app.models import Rule, PatternType


def test_rule(rule: Rule, text: str) -> bool:
    """Test if a rule matches the given text."""
    if rule.pattern_type == PatternType.contains:
        return rule.pattern_value.lower() in text.lower()
    elif rule.pattern_type == PatternType.regex:
        try:
            return bool(re.search(rule.pattern_value, text, re.IGNORECASE))
        except re.error:
            return False
    return False
