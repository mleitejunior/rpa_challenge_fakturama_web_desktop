import csv
from pathlib import Path


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

CSV_ENCODING = "utf-8"


def save_buyer(buyer: dict, csv_path) -> None:
    """Persiste os dados do comprador em um arquivo CSV."""
    path = Path(csv_path)
    _ensure_parent_directory(path)

    with path.open("w", encoding=CSV_ENCODING, newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=BUYER_HEADERS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerow(buyer)


def load_buyer(csv_path) -> dict:
    """Carrega o comprador persistido em um arquivo CSV."""
    path = Path(csv_path)

    with path.open("r", encoding=CSV_ENCODING, newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        buyer = next(reader, None)

    if buyer is None:
        raise ValueError(f"CSV do comprador está vazio: {path}")

    return buyer


def save_products(products: list[dict], csv_path) -> None:
    """Persiste o catálogo de produtos em um arquivo CSV."""
    path = Path(csv_path)
    _ensure_parent_directory(path)

    with path.open("w", encoding=CSV_ENCODING, newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=PRODUCT_HEADERS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(products)


def load_products(csv_path) -> list[dict]:
    """Carrega o catálogo de produtos persistido em um arquivo CSV."""
    path = Path(csv_path)

    with path.open("r", encoding=CSV_ENCODING, newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def _ensure_parent_directory(path: Path) -> None:
    """Cria o diretório pai do arquivo quando necessário."""
    path.parent.mkdir(parents=True, exist_ok=True)
