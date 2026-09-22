import pytest


@pytest.fixture
def buyer_data():
    """Comprador normalizado usado nos testes de persistência."""
    return {
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


@pytest.fixture
def products_data():
    """Catálogo reduzido usado nos testes de persistência."""
    return [
        {
            "item_number": "4",
            "name": "Sauce Labs Backpack",
            "description": (
                "carry.allTheThings() with the sleek, streamlined Sly Pack "
                "that melds uncompromising style with unequaled laptop and "
                "tablet protection."
            ),
            "price": "29.99",
        },
        {
            "item_number": "0",
            "name": "Sauce Labs Bike Light",
            "description": (
                "A red light isn't the desired state in testing but it sure "
                "helps when riding your bike at night, water-resistant with "
                "3 lighting modes."
            ),
            "price": "9.99",
        },
    ]
