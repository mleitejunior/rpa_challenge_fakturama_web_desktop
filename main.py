from pprint import pprint

from playwright.sync_api import sync_playwright

from src.web.buyer_scraper import scrape_buyer
from src.web.sauce_demo import scrape_products


BROWSER_HEADLESS = False


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


if __name__ == "__main__":
    main()
