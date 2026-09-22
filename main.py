from pathlib import Path
from pprint import pprint

from playwright.sync_api import sync_playwright

from src.desktop.fakturama import (
    close_fakturama,
    open_fakturama,
    register_customer,
)
from src.repositories.csv_repository import save_buyer, save_products
from src.web.buyer_scraper import scrape_buyer
from src.web.sauce_demo import scrape_products


BROWSER_HEADLESS = False

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
BUYER_CSV_PATH = RESULTS_DIR / "buyer.csv"
PRODUCTS_CSV_PATH = RESULTS_DIR / "products.csv"


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=BROWSER_HEADLESS,
        )
        page = browser.new_page()

        buyer = scrape_buyer(page)

        print("\nCOMPRADOR COLETADO:")
        pprint(buyer, sort_dicts=False)

        products = scrape_products(page)

        print(f"\nPRODUTOS ENCONTRADOS: {len(products)}")

        for product in products:
            pprint(product, sort_dicts=False)

        browser.close()

    save_buyer(buyer, BUYER_CSV_PATH)
    save_products(products, PRODUCTS_CSV_PATH)

    print("\nDADOS PERSISTIDOS:")
    print(f"- {BUYER_CSV_PATH}")
    print(f"- {PRODUCTS_CSV_PATH}")

    print("\nABRINDO FAKTURAMA...")
    open_fakturama()

    try:
        register_customer(buyer)
        print("Cadastro do comprador concluído.")
    finally:
        close_fakturama()
        print("Fakturama fechado.")


if __name__ == "__main__":
    main()
