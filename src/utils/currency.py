from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

PRICE_TOKEN_RE = re.compile(r"(?:R\$\s*)?[\d\.,]+")


def parse_price_to_decimal(raw_price: str) -> Optional[Decimal]:
    token_match = PRICE_TOKEN_RE.search(raw_price)
    if not token_match:
        return None

    token = token_match.group(0)
    token = token.replace("R$", "")
    token = re.sub(r"\s+", "", token)

    if "." in token and "," in token:
        if token.rfind(",") > token.rfind("."):
            normalized = token.replace(".", "").replace(",", ".")
        else:
            normalized = token.replace(",", "")
    elif "," in token:
        normalized = token.replace(".", "").replace(",", ".")
    else:
        normalized = token.replace(",", "")

    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
