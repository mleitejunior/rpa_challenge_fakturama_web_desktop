import csv


BUYER_HEADERS = [
    "first_name",
    "last_name",
    "street",
    "number",
    "city",
    "state",
    "zip_code",
    "cpf",
    "phone",
    "birth_date",
]

PRODUCT_HEADERS = [
    "item_number",
    "name",
    "description",
    "price",
]


def _repository_functions():
    """Import tardio mantém os testes coletáveis antes do feat existir."""
    from src.repositories.csv_repository import (
        load_buyer,
        load_products,
        save_buyer,
        save_products,
    )

    return save_buyer, load_buyer, save_products, load_products


def test_save_buyer_creates_expected_csv_and_round_trip(tmp_path, buyer_data):
    save_buyer, load_buyer, _, _ = _repository_functions()
    csv_path = tmp_path / "buyer.csv"

    save_buyer(buyer_data, csv_path)

    assert csv_path.exists()

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    assert reader.fieldnames == BUYER_HEADERS
    assert rows == [buyer_data]
    assert load_buyer(csv_path) == buyer_data


def test_save_buyer_preserves_unicode_characters(tmp_path, buyer_data):
    save_buyer, load_buyer, _, _ = _repository_functions()
    csv_path = tmp_path / "buyer.csv"

    buyer = {
        **buyer_data,
        "first_name": "João",
        "last_name": "Gonçalves Araújo",
        "street": "Rua São José",
    }

    save_buyer(buyer, csv_path)

    assert load_buyer(csv_path) == buyer


def test_save_products_writes_all_rows_and_round_trip(tmp_path, products_data):
    _, _, save_products, load_products = _repository_functions()
    csv_path = tmp_path / "products.csv"

    save_products(products_data, csv_path)

    assert csv_path.exists()

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    assert reader.fieldnames == PRODUCT_HEADERS
    assert rows == products_data
    assert load_products(csv_path) == products_data


def test_save_products_overwrites_previous_execution(tmp_path, products_data):
    _, _, save_products, load_products = _repository_functions()
    csv_path = tmp_path / "products.csv"

    save_products(products_data, csv_path)

    new_execution = [
        {
            "item_number": "1",
            "name": "Sauce Labs Bolt T-Shirt",
            "description": "Get your testing superhero on with the Sauce Labs bolt T-shirt.",
            "price": "15.99",
        }
    ]

    save_products(new_execution, csv_path)

    assert load_products(csv_path) == new_execution
