import re
import subprocess
import time
from pathlib import Path

import pyautogui
import pyperclip
from playwright.sync_api import sync_playwright


# URLs
FAKE_NAME_URL = "https://www.fakenamegenerator.com/gen-random-br-br.php"
SAUCE_DEMO_URL = "https://www.saucedemo.com/"

# Credenciais do Sauce Demo
SAUCE_USERNAME = "standard_user"
SAUCE_PASSWORD = "secret_sauce"

# Fakturama
FAKTURAMA_EXE = r"C:\Program Files\Fakturama2\Fakturama.exe"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAKTURAMA_ASSETS = PROJECT_ROOT / "resources" / "images" / "fakturama"

# Imagens usadas como âncoras na automação 'desktop'
PRODUCT_IMAGE = FAKTURAMA_ASSETS / "product.png"
CONTACT_IMAGE = FAKTURAMA_ASSETS / "contact.png"
NEW_DEBTOR_IMAGE = FAKTURAMA_ASSETS / "new_debtor.png"
FIRST_NAME_LAST_NAME_IMAGE = FAKTURAMA_ASSETS / "first_name_last_name_variant_1.png"
ZIP_CITY_IMAGE = FAKTURAMA_ASSETS / "zip_city.png"
SAVE_IMAGE = FAKTURAMA_ASSETS / "save.png"
ITEM_NUMBER_IMAGE = FAKTURAMA_ASSETS / "item_number_variant_1.png"
NAME_IMAGE = FAKTURAMA_ASSETS / "name_variant_1.png"
DESCRIPTION_IMAGE = FAKTURAMA_ASSETS / "description_variant_1.png"
PRICE_GROSS_IMAGE = FAKTURAMA_ASSETS / "price_gross_variant_1.png"
STOCK_IMAGE = FAKTURAMA_ASSETS / "stock_variant_1.png"

# Esperas e timeouts
IMAGE_CONFIDENCE = 0.80
IMAGE_TIMEOUT_SECONDS = 180
IMAGE_POLL_INTERVAL_SECONDS = 0.5
SAUCE_PRODUCTS_TIMEOUT_MS = 15000
SAUCE_PRODUCTS_RENDER_WAIT_SECONDS = 1
FAKTURAMA_AFTER_SAVE_WAIT_SECONDS = 0.5
FAKTURAMA_CLOSE_WAIT_SECONDS = 1

# Interação 'desktop'
FIELD_CLICK_OFFSET_X = 10
DEFAULT_PRODUCT_STOCK = "1"

# Nesta POC, foi priorizado o copy/paste com pyperclip pela maior velocidade
# de preenchimento. Como trade-off, o conteúdo atual do clipboard do utilizador
# é sobrescrito durante a execução.


def wait_for_image(image_path, timeout=IMAGE_TIMEOUT_SECONDS):
    """Aguarda uma imagem aparecer na tela e retorna a área (região)."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            location = pyautogui.locateOnScreen(
                str(image_path),
                confidence=IMAGE_CONFIDENCE,
            )
        except pyautogui.ImageNotFoundException:
            location = None

        if location:
            return location

        time.sleep(IMAGE_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Imagem não encontrada em até {timeout}s: {image_path.name}"
    )


def click_image(image_path, timeout=IMAGE_TIMEOUT_SECONDS):
    """Aguarda uma imagem e clica no centro dela."""
    location = wait_for_image(image_path, timeout=timeout)
    center = pyautogui.center(location)
    pyautogui.click(center.x, center.y)
    return location


def click_right_of_image(image_path, offset_x=FIELD_CLICK_OFFSET_X):
    """Clica à direita de uma imagem usada como âncora de um campo."""
    location = wait_for_image(image_path)

    x = location.left + location.width + offset_x
    y = location.top + (location.height // 2)

    pyautogui.click(x, y)
    return location


def paste_text(value):
    """Copia o valor para o clipboard e cola no campo em foco."""
    pyperclip.copy(str(value))
    pyautogui.hotkey("ctrl", "v")


def save_and_close_tab():
    """Salva o registro atual e fecha a aba do Fakturama."""
    click_image(SAVE_IMAGE)
    time.sleep(FAKTURAMA_AFTER_SAVE_WAIT_SECONDS)
    pyautogui.hotkey("ctrl", "w")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()

    # ---------------------------------------------------------
    # 1. Gerar e coletar comprador fictício
    # ---------------------------------------------------------
    page.goto(FAKE_NAME_URL, wait_until="domcontentloaded")

    full_name = page.locator("#details .address h3").inner_text().strip()
    address_text = page.locator("#details .address .adr").inner_text().strip()

    first_name, last_name = full_name.split(" ", 1)
    zip_code = address_text.splitlines()[-1].strip()

    buyer = {
        "first_name": first_name,
        "last_name": last_name,
        "zip_code": zip_code,
    }

    print("\nCOMPRADOR")
    print(buyer)

    # ---------------------------------------------------------
    # 2. Fazer login no Sauce Demo
    # ---------------------------------------------------------
    page.goto(SAUCE_DEMO_URL, wait_until="domcontentloaded")

    page.locator('[data-test="username"]').fill(SAUCE_USERNAME)
    page.locator('[data-test="password"]').fill(SAUCE_PASSWORD)
    page.locator('[data-test="login-button"]').click()

    page.wait_for_url("**/inventory.html")

    # Confirma que a página de produtos foi carregada antes da coleta.
    page.locator('span[data-test="title"]', has_text="Products").wait_for(
        state="visible",
        timeout=SAUCE_PRODUCTS_TIMEOUT_MS,
    )

    time.sleep(SAUCE_PRODUCTS_RENDER_WAIT_SECONDS)

    # ---------------------------------------------------------
    # 3. Coletar catálogo completo de produtos
    # ---------------------------------------------------------
    product_elements = page.locator('[data-test="inventory-item"]')
    product_count = product_elements.count()

    products = []

    for index in range(product_count):
        item = product_elements.nth(index)

        title_link = item.locator('a[id^="item_"][id$="_title_link"]')
        title_link_id = title_link.get_attribute("id")

        if title_link_id is None:
            raise RuntimeError("ID do link do produto não encontrado.")

        match = re.search(
            r"item_(\d+)_title_link",
            title_link_id,
        )

        if match is None:
            raise RuntimeError(
                f"Não foi possível extrair o número do item do ID: {title_link_id}"
            )

        item_number = match.group(1)

        name = (
            item.locator('[data-test="inventory-item-name"]')
            .inner_text()
            .strip()
        )

        description = (
            item.locator('[data-test="inventory-item-desc"]')
            .inner_text()
            .strip()
        )

        price = (
            item.locator('[data-test="inventory-item-price"]')
            .inner_text()
            .strip()
            .replace("$", "")
        )

        products.append(
            {
                "item_number": item_number,
                "name": name,
                "description": description,
                "price": price,
            }
        )

    print(f"\nPRODUTOS ENCONTRADOS: {len(products)}")

    for product in products:
        print(product)

    browser.close()


# ---------------------------------------------------------
# 4. Abrir Fakturama e validar automação 'desktop'
# ---------------------------------------------------------
print("\nAbrindo Fakturama...")
subprocess.Popen([FAKTURAMA_EXE])

# Product+ é usado como indicador de que a aplicação terminou de abrir.
wait_for_image(PRODUCT_IMAGE)
print("Fakturama pronto.")

# ---------------------------------------------------------
# 5. Cadastrar comprador
# ---------------------------------------------------------
click_image(CONTACT_IMAGE)
wait_for_image(NEW_DEBTOR_IMAGE)

# O Customer 'ID' é gerado automaticamente pelo Fakturama.
click_right_of_image(FIRST_NAME_LAST_NAME_IMAGE)
paste_text(buyer["first_name"])

pyautogui.press("tab")
paste_text(buyer["last_name"])

click_right_of_image(ZIP_CITY_IMAGE)
paste_text(buyer["zip_code"])

save_and_close_tab()

print("\nCadastro do comprador concluído.")

# ---------------------------------------------------------
# 6. Cadastrar produtos
# ---------------------------------------------------------
print(f"\nCadastrando {len(products)} produtos no Fakturama...")

for product in products:
    print(
        f'Cadastrando produto {product["item_number"]}: '
        f'{product["name"]}'
    )

    click_image(PRODUCT_IMAGE)

    # A presença do campo Item Number confirma que o formulário está pronto.
    wait_for_image(ITEM_NUMBER_IMAGE)

    click_right_of_image(ITEM_NUMBER_IMAGE)
    paste_text(product["item_number"])

    click_right_of_image(NAME_IMAGE)
    paste_text(product["name"])

    # A imagem de Description inclui o próprio campo, então o clique é central.
    click_image(DESCRIPTION_IMAGE)
    paste_text(product["description"])

    # O Fakturama utiliza vírgula como separador decimal.
    fakturama_price = product["price"].replace(".", ",")

    click_right_of_image(PRICE_GROSS_IMAGE)
    paste_text(fakturama_price)

    click_right_of_image(STOCK_IMAGE)
    paste_text(DEFAULT_PRODUCT_STOCK)

    save_and_close_tab()

    print(f'Produto {product["item_number"]} salvo.')

print("\nCadastro dos produtos concluído.")

# ---------------------------------------------------------
# 7. Fechar Fakturama
# ---------------------------------------------------------
time.sleep(FAKTURAMA_CLOSE_WAIT_SECONDS)
pyautogui.hotkey("alt", "f4")

print("Fakturama fechado.")
print("\nPOC concluída com sucesso.")