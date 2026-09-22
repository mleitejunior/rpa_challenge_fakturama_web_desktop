import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from src.repositories.csv_repository import (
    load_buyer,
    load_products,
    save_buyer,
    save_products,
)
from src.web.buyer_scraper import scrape_buyer
from src.web.sauce_demo import scrape_products


pytestmark = pytest.mark.integration


FAKE_NAME_HTML = """
<div id="details">
  <div class="address">
    <h3>Miguel Pereira Carvalho</h3>
    <div class="adr">
      Rua Amadeu Natal, 1199<br>
      Curitiba-PR<br>
      82650-440
    </div>
  </div>

  <dl class="dl-horizontal">
    <dt>Cadastro de Pessoas Físicas</dt>
    <dd>160.419.191-01</dd>
  </dl>

  <dl class="dl-horizontal">
    <dt>Phone</dt>
    <dd>(41) 6375-6640</dd>
  </dl>

  <dl class="dl-horizontal">
    <dt>Birthday</dt>
    <dd>July 19, 1941</dd>
  </dl>
</div>
"""


SAUCE_LOGIN_HTML = """
<input data-test="username">
<input data-test="password" type="password">
<button
  data-test="login-button"
  type="button"
  onclick="window.location.href='/inventory.html'"
>
  Login
</button>
"""


SAUCE_INVENTORY_HTML = """
<span class="title" data-test="title">Products</span>

<div data-test="inventory-item">
  <a id="item_4_title_link">
    <div data-test="inventory-item-name">Sauce Labs Backpack</div>
  </a>
  <div data-test="inventory-item-desc">Backpack integration description.</div>
  <div data-test="inventory-item-price">$29.99</div>
</div>

<div data-test="inventory-item">
  <a id="item_0_title_link">
    <div data-test="inventory-item-name">Sauce Labs Bike Light</div>
  </a>
  <div data-test="inventory-item-desc">Bike light integration description.</div>
  <div data-test="inventory-item-price">$9.99</div>
</div>
"""


def test_web_scraping_persists_same_data_in_csv(tmp_path):
    """Integra Playwright, parsing e persistência sem depender da internet."""
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as error:
            pytest.skip(f"Chromium do Playwright não disponível: {error}")

        page = browser.new_page()

        page.route(
            "**/gen-random-br-br.php",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=FAKE_NAME_HTML,
            ),
        )
        page.route(
            "https://www.saucedemo.com/",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=SAUCE_LOGIN_HTML,
            ),
        )
        page.route(
            "https://www.saucedemo.com/inventory.html**",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=SAUCE_INVENTORY_HTML,
            ),
        )

        try:
            buyer = scrape_buyer(page)
            products = scrape_products(page)
        finally:
            browser.close()

    buyer_csv = tmp_path / "buyer.csv"
    products_csv = tmp_path / "products.csv"

    save_buyer(buyer, buyer_csv)
    save_products(products, products_csv)

    assert load_buyer(buyer_csv) == buyer
    assert load_products(products_csv) == products
    assert len(products) == 2
    assert products[0]["item_number"] == "4"
    assert products[1]["item_number"] == "0"