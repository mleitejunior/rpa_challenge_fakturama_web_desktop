import logging
import subprocess
import time
from pathlib import Path

import pyautogui
import pyperclip

from src.config.settings import (
    EVIDENCE_VIEW_WAIT_SECONDS,
    FAKTURAMA_AFTER_SAVE_WAIT_SECONDS,
    FAKTURAMA_CLOSE_WAIT_SECONDS,
    FAKTURAMA_EXE,
    FAKTURAMA_TERMINATION_TIMEOUT_SECONDS,
    FIELD_CLICK_OFFSET_X,
    FOCUS_AFTER_CLICK_WAIT_SECONDS,
    FOCUS_CLICK_MAX_ATTEMPTS,
    FOCUS_COLOR_TOLERANCE,
    FOCUS_MIN_MATCH_RATIO,
    IMAGE_CONFIDENCE,
    IMAGE_POLL_INTERVAL_SECONDS,
    IMAGE_TIMEOUT_SECONDS,
)

LOGGER = logging.getLogger("rpa.fakturama")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAKTURAMA_ASSETS = PROJECT_ROOT / "resources" / "images" / "fakturama"

# Imagens usadas como âncoras na automação desktop.
PRODUCT_IMAGE = FAKTURAMA_ASSETS / "product.png"
CONTACT_IMAGE = FAKTURAMA_ASSETS / "contact.png"
NEW_DEBTOR_IMAGE = FAKTURAMA_ASSETS / "new_debtor.png"
FIRST_NAME_LAST_NAME_IMAGE = FAKTURAMA_ASSETS / "first_name_last_name.png"
ZIP_CITY_IMAGE = FAKTURAMA_ASSETS / "zip_city.png"
SAVE_IMAGE = FAKTURAMA_ASSETS / "save.png"
ITEM_NUMBER_IMAGE = FAKTURAMA_ASSETS / "item_number.png"
NAME_IMAGE = FAKTURAMA_ASSETS / "name.png"
DESCRIPTION_IMAGE = FAKTURAMA_ASSETS / "description.png"
PRICE_GROSS_IMAGE = FAKTURAMA_ASSETS / "price_gross.png"
STOCK_IMAGE = FAKTURAMA_ASSETS / "stock.png"
DEBTORS_LIST_IMAGE = FAKTURAMA_ASSETS / "debtors_list.png"
PRODUCTS_LIST_IMAGE = FAKTURAMA_ASSETS / "products_list.png"

# Regras internas da automação desktop.
DEFAULT_PRODUCT_STOCK = "1"

# Validação visual de foco dos campos.
# O Fakturama destaca o input ativo com este tom de amarelo.
FOCUSED_FIELD_COLOR = (250, 240, 162)
FOCUS_SAMPLE_WIDTH = 12
FOCUS_SAMPLE_HEIGHT = 8

# O copy/paste com pyperclip foi mantido por ser significativamente mais rápido
# que a digitação caractere a caractere. Como trade-off, o conteúdo atual do
# clipboard do usuário é sobrescrito durante a execução.


def wait_for_image(image_path, timeout=IMAGE_TIMEOUT_SECONDS):
    """Aguarda uma imagem aparecer na tela e retorna sua região."""
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
    """Clica à direita da âncora e valida se o campo recebeu foco."""
    location = wait_for_image(image_path)

    x = location.left + location.width + offset_x
    y = location.top + (location.height // 2)

    _click_and_validate_focus(x, y, image_path.name)
    return location


def click_field_image(image_path, timeout=IMAGE_TIMEOUT_SECONDS):
    """Clica no centro de uma imagem de campo e valida o foco."""
    location = wait_for_image(image_path, timeout=timeout)
    center = pyautogui.center(location)

    _click_and_validate_focus(center.x, center.y, image_path.name)
    return location


def paste_text(value):
    """Copia o valor para o clipboard e cola no campo em foco."""
    pyperclip.copy(str(value))
    pyautogui.hotkey("ctrl", "v")



def terminate_existing_fakturama():
    """Encerra qualquer instância anterior do Fakturama antes da execução."""
    process_name = Path(FAKTURAMA_EXE).name

    if not _is_process_running(process_name):
        return False

    result = subprocess.run(
        ["taskkill", "/IM", process_name, "/F", "/T"],
        capture_output=True,
        text=True,
        check=False,
        timeout=FAKTURAMA_TERMINATION_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "Não foi possível encerrar a instância existente do Fakturama. "
            f"Detalhes: {details or 'taskkill retornou erro sem detalhes.'}"
        )

    deadline = time.monotonic() + FAKTURAMA_TERMINATION_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        if not _is_process_running(process_name):
            return True

        time.sleep(IMAGE_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        "O processo do Fakturama continuou ativo após a tentativa de "
        f"finalização: {process_name}"
    )


def _is_process_running(process_name):
    """Verifica pelo tasklist se o processo informado está em execução."""
    result = subprocess.run(
        [
            "tasklist",
            "/FI",
            f"IMAGENAME eq {process_name}",
            "/FO",
            "CSV",
            "/NH",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=FAKTURAMA_TERMINATION_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            "Não foi possível verificar processos ativos do Fakturama. "
            f"Detalhes: {details or 'tasklist retornou erro sem detalhes.'}"
        )

    return process_name.lower() in result.stdout.lower()

def open_fakturama():
    """Abre o Fakturama e aguarda a tela principal ficar disponível."""
    executable = Path(FAKTURAMA_EXE)

    if not executable.exists():
        raise FileNotFoundError(
            f"Executável do Fakturama não encontrado: {executable}"
        )

    subprocess.Popen([str(executable)])

    # Product+ é usado como indicador visual de que o aplicativo terminou de abrir.
    wait_for_image(PRODUCT_IMAGE)


def register_customer(buyer: dict):
    """Cadastra o comprador como um novo contato no Fakturama."""
    required_fields = ("first_name", "last_name", "zip_code")
    missing_fields = [
        field
        for field in required_fields
        if not str(buyer.get(field, "")).strip()
    ]

    if missing_fields:
        raise ValueError(
            "Dados obrigatórios do comprador ausentes: "
            + ", ".join(missing_fields)
        )

    click_image(CONTACT_IMAGE)
    wait_for_image(NEW_DEBTOR_IMAGE)

    # O Customer ID é gerado automaticamente pelo Fakturama.
    click_right_of_image(FIRST_NAME_LAST_NAME_IMAGE)
    paste_text(buyer["first_name"])

    pyautogui.press("tab")
    paste_text(buyer["last_name"])

    click_right_of_image(ZIP_CITY_IMAGE)
    paste_text(buyer["zip_code"])

    _save_and_close_tab()


def register_product(product: dict):
    """Cadastra um único produto no Fakturama."""
    required_fields = ("item_number", "name", "description", "price")
    missing_fields = [
        field
        for field in required_fields
        if not str(product.get(field, "")).strip()
    ]

    if missing_fields:
        raise ValueError(
            "Dados obrigatórios do produto ausentes: "
            + ", ".join(missing_fields)
        )

    click_image(PRODUCT_IMAGE)

    # A presença do campo Item Number confirma que o formulário está pronto.
    wait_for_image(ITEM_NUMBER_IMAGE)

    click_right_of_image(ITEM_NUMBER_IMAGE)
    paste_text(product["item_number"])

    click_right_of_image(NAME_IMAGE)
    paste_text(product["name"])

    # A imagem de Description inclui o próprio campo, então o clique é central.
    click_field_image(DESCRIPTION_IMAGE)
    paste_text(product["description"])

    # O Fakturama utiliza vírgula como separador decimal.
    fakturama_price = str(product["price"]).replace(".", ",")

    click_right_of_image(PRICE_GROSS_IMAGE)
    paste_text(fakturama_price)

    click_right_of_image(STOCK_IMAGE)
    paste_text(DEFAULT_PRODUCT_STOCK)

    _save_and_close_tab()



def capture_customer_evidence(screenshot_path):
    """Abre a lista de compradores e captura a evidência do cadastro."""
    click_image(DEBTORS_LIST_IMAGE)
    time.sleep(EVIDENCE_VIEW_WAIT_SECONDS)
    return capture_screenshot(screenshot_path)


def capture_products_evidence(screenshot_path):
    """Abre a lista de produtos e captura a evidência dos cadastros."""
    click_image(PRODUCTS_LIST_IMAGE)
    time.sleep(EVIDENCE_VIEW_WAIT_SECONDS)
    return capture_screenshot(screenshot_path)


def capture_screenshot(screenshot_path):
    """Captura a tela atual e salva a imagem no caminho informado."""
    path = Path(screenshot_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    pyautogui.screenshot(str(path))
    return path


def close_fakturama():
    """Fecha o Fakturama ao final da execução."""
    time.sleep(FAKTURAMA_CLOSE_WAIT_SECONDS)
    pyautogui.hotkey("alt", "f4")


def _click_and_validate_focus(x, y, field_name):
    """Clica no campo e confirma visualmente que ele recebeu foco."""
    for attempt in range(1, FOCUS_CLICK_MAX_ATTEMPTS + 1):
        pyautogui.click(x, y)
        time.sleep(FOCUS_AFTER_CLICK_WAIT_SECONDS)

        if _is_field_focused(x, y):
            return

        LOGGER.warning(
            "Foco não confirmado no campo %s após tentativa %d/%d",
            field_name,
            attempt,
            FOCUS_CLICK_MAX_ATTEMPTS,
        )

    raise RuntimeError(
        f"Campo não recebeu foco após {FOCUS_CLICK_MAX_ATTEMPTS} "
        f"tentativas: {field_name}"
    )


def _is_field_focused(x, y):
    """Verifica se a região clicada possui a cor de foco do Fakturama."""
    left = max(0, int(x - (FOCUS_SAMPLE_WIDTH // 2)))
    top = max(0, int(y - (FOCUS_SAMPLE_HEIGHT // 2)))

    screenshot = pyautogui.screenshot(
        region=(
            left,
            top,
            FOCUS_SAMPLE_WIDTH,
            FOCUS_SAMPLE_HEIGHT,
        )
    ).convert("RGB")

    matching_pixels = 0
    total_pixels = FOCUS_SAMPLE_WIDTH * FOCUS_SAMPLE_HEIGHT

    for pixel_x in range(FOCUS_SAMPLE_WIDTH):
        for pixel_y in range(FOCUS_SAMPLE_HEIGHT):
            pixel = screenshot.getpixel((pixel_x, pixel_y))

            if _is_color_close(pixel, FOCUSED_FIELD_COLOR):
                matching_pixels += 1

    match_ratio = matching_pixels / total_pixels
    return match_ratio >= FOCUS_MIN_MATCH_RATIO


def _is_color_close(actual_color, expected_color):
    """Compara duas cores considerando uma pequena tolerância por canal RGB."""
    return all(
        abs(actual - expected) <= FOCUS_COLOR_TOLERANCE
        for actual, expected in zip(actual_color, expected_color)
    )


def _save_and_close_tab():
    """Salva o registro atual e fecha a aba aberta no Fakturama."""
    click_image(SAVE_IMAGE)
    time.sleep(FAKTURAMA_AFTER_SAVE_WAIT_SECONDS)
    pyautogui.hotkey("ctrl", "w")
