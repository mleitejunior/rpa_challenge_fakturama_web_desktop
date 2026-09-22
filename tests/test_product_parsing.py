import pytest


def _extract_item_number(title_link_id):
    """Import tardio mantém os testes coletáveis antes do feat existir."""
    from src.web.sauce_demo import extract_item_number

    return extract_item_number(title_link_id)


def _normalize_price(price_text):
    """Import tardio mantém os testes coletáveis antes do feat existir."""
    from src.web.sauce_demo import normalize_price

    return normalize_price(price_text)


def test_extract_item_number_from_sauce_demo_id():
    assert _extract_item_number("item_4_title_link") == "4"


def test_extract_item_number_raises_error_for_unexpected_id():
    with pytest.raises(ValueError, match="item"):
        _extract_item_number("product_title")


def test_normalize_price_removes_currency_symbol_and_whitespace():
    assert _normalize_price("  $29.99  ") == "29.99"
