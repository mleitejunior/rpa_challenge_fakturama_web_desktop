import pytest


FULL_NAME = "Miguel Pereira Carvalho"
ADDRESS_TEXT = "Rua Amadeu Natal, 1199\nCuritiba-PR\n82650-440"
CPF = "160.419.191-01"
PHONE = "(41) 6375-6640"
BIRTH_DATE = "July 19, 1941"


def _parse_buyer(**overrides):
    """Import tardio mantém os testes coletáveis antes do feat existir."""
    from src.web.buyer_scraper import parse_buyer

    data = {
        "full_name": FULL_NAME,
        "address_text": ADDRESS_TEXT,
        "cpf": CPF,
        "phone": PHONE,
        "birth_date": BIRTH_DATE,
    }
    data.update(overrides)
    return parse_buyer(**data)


def test_parse_buyer_returns_normalized_customer_data():
    buyer = _parse_buyer()

    assert buyer == {
        "first_name": "Miguel",
        "last_name": "Pereira Carvalho",
        "street": "Rua Amadeu Natal",
        "number": "1199",
        "city": "Curitiba",
        "state": "PR",
        "zip_code": "82650-440",
        "cpf": "160.419.191-01",
        "phone": "(41) 6375-6640",
        "birth_date": "1941-07-19",
    }


def test_parse_buyer_preserves_compound_last_name():
    buyer = _parse_buyer(full_name="Ana Clara de Souza Lima")

    assert buyer["first_name"] == "Ana"
    assert buyer["last_name"] == "Clara de Souza Lima"


def test_parse_buyer_raises_error_when_last_name_is_missing():
    with pytest.raises(ValueError, match="sobrenome"):
        _parse_buyer(full_name="Miguel")


def test_parse_buyer_raises_error_for_invalid_address():
    with pytest.raises(ValueError, match="endereço"):
        _parse_buyer(address_text="Endereço incompleto")
