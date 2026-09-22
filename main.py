from pprint import pprint

from playwright.sync_api import sync_playwright

from src.web.buyer_scraper import scrape_buyer


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        page = browser.new_page()

        buyer = scrape_buyer(page)

        print("\nCOMPRADOR COLETADO:")
        pprint(buyer, sort_dicts=False)

        browser.close()


if __name__ == "__main__":
    main()