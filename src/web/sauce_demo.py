import re
import time

from playwright.sync_api import Page

from src.config.settings import (
    SAUCE_DEMO_URL,
    SAUCE_PASSWORD,
    SAUCE_PRODUCTS_RENDER_WAIT_SECONDS,
    SAUCE_PRODUCTS_TIMEOUT_MS,
    SAUCE_USERNAME,
)

USERNAME_SELECTOR = '[data-test="username"]'
PASSWORD_SELECTOR = '[data-test="password"]'
LOGIN_BUTTON_SELECTOR = '[data-test="login-button"]'
PRODUCT_TITLE_SELECTOR = 'span[data-test="title"]'
PRODUCT_SELECTOR = '[data-test="inventory-item"]'
PRODUCT_NAME_SELECTOR = '[data-test="inventory-item-name"]'
PRODUCT_DESCRIPTION_SELECTOR = '[data-test="inventory-item-desc"]'
PRODUCT_PRICE_SELECTOR = '[data-test="inventory-item-price"]'
TITLE_LINK_SELECTOR = 'a[id^="item_"][id$="_title_link"]'


def extract_item_number(title_link_id: str) -> str:
    """Extrai o número do item a partir do ID do link do produto."""
    match = re.fullmatch(
        r"item_(\d+)_title_link",
        title_link_id.strip(),
    )

    if match is None:
        raise ValueError(
            f"Não foi possível extrair o número do item do ID: {title_link_id}"
        )

    return match.group(1)


def normalize_price(price_text: str) -> str:
    """Remove o símbolo de moeda e espaços do preço coletado."""
    return price_text.strip().removeprefix("$").strip()


def scrape_products(page: Page):
    """Faz login no Sauce Demo e coleta o catálogo completo de produtos."""
    page.goto(SAUCE_DEMO_URL, wait_until="domcontentloaded")

    page.locator(USERNAME_SELECTOR).fill(SAUCE_USERNAME)
    page.locator(PASSWORD_SELECTOR).fill(SAUCE_PASSWORD)
    page.locator(LOGIN_BUTTON_SELECTOR).click()

    page.wait_for_url(
        "**/inventory.html",
        timeout=SAUCE_PRODUCTS_TIMEOUT_MS,
    )

    # Confirma que a página de produtos foi carregada antes da coleta.
    page.locator(
        PRODUCT_TITLE_SELECTOR,
        has_text="Products",
    ).wait_for(
        state="visible",
        timeout=SAUCE_PRODUCTS_TIMEOUT_MS,
    )

    # Pequena espera adicional para garantir a renderização completa do catálogo.
    time.sleep(SAUCE_PRODUCTS_RENDER_WAIT_SECONDS)

    product_elements = page.locator(PRODUCT_SELECTOR)
    product_count = product_elements.count()

    products = []

    for index in range(product_count):
        item = product_elements.nth(index)

        title_link_id = (
            item.locator(TITLE_LINK_SELECTOR)
            .get_attribute("id")
        )

        if title_link_id is None:
            raise RuntimeError("ID do link do produto não encontrado.")

        products.append(
            {
                "item_number": extract_item_number(title_link_id),
                "name": (
                    item.locator(PRODUCT_NAME_SELECTOR)
                    .inner_text()
                    .strip()
                ),
                "description": (
                    item.locator(PRODUCT_DESCRIPTION_SELECTOR)
                    .inner_text()
                    .strip()
                ),
                "price": normalize_price(
                    item.locator(PRODUCT_PRICE_SELECTOR)
                    .inner_text()
                ),
            }
        )

    return products
