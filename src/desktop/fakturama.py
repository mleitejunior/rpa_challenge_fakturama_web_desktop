import ctypes
import logging
import os
import subprocess
import time
from pathlib import Path, PureWindowsPath

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

# Controle da janela do Fakturama no Windows.
WINDOW_FOCUS_MAX_ATTEMPTS = 5
WINDOW_FOCUS_RETRY_SECONDS = 0.25
SW_RESTORE = 9
GW_OWNER = 4
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_IMAGE_BUFFER_SIZE = 32768

_FAKTURAMA_WINDOW_HANDLE = None
_USER32 = None
_KERNEL32 = None

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
    global _FAKTURAMA_WINDOW_HANDLE

    _FAKTURAMA_WINDOW_HANDLE = None
    process_name = PureWindowsPath(FAKTURAMA_EXE).name

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

def ensure_fakturama_foreground():
    """Garante que a janela principal do Fakturama esteja em primeiro plano."""
    global _FAKTURAMA_WINDOW_HANDLE

    user32, _, _ = _get_win32_apis()

    if (
        _FAKTURAMA_WINDOW_HANDLE is None
        or not user32.IsWindow(_FAKTURAMA_WINDOW_HANDLE)
    ):
        _FAKTURAMA_WINDOW_HANDLE = _wait_for_fakturama_window()

    window_handle = _FAKTURAMA_WINDOW_HANDLE

    if user32.GetForegroundWindow() == window_handle:
        return window_handle

    for attempt in range(1, WINDOW_FOCUS_MAX_ATTEMPTS + 1):
        _activate_window(window_handle)
        time.sleep(WINDOW_FOCUS_RETRY_SECONDS)

        if user32.GetForegroundWindow() == window_handle:
            LOGGER.info(
                "Fakturama colocado em primeiro plano após tentativa %d/%d",
                attempt,
                WINDOW_FOCUS_MAX_ATTEMPTS,
            )
            return window_handle

        LOGGER.warning(
            "Foco do Fakturama não confirmado após tentativa %d/%d",
            attempt,
            WINDOW_FOCUS_MAX_ATTEMPTS,
        )

    raise RuntimeError(
        "Não foi possível colocar a janela do Fakturama em primeiro plano."
    )


def _wait_for_fakturama_window(process_id=None, timeout=IMAGE_TIMEOUT_SECONDS):
    """Aguarda a janela principal do Fakturama ficar disponível."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        window_handle = _find_fakturama_window(process_id)

        if window_handle:
            return window_handle

        time.sleep(IMAGE_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"Janela do Fakturama não encontrada em até {timeout}s."
    )


def _find_fakturama_window(process_id=None):
    """Localiza a janela pertencente exatamente ao processo do Fakturama."""
    user32, _, wintypes = _get_win32_apis()

    expected_process_name = PureWindowsPath(FAKTURAMA_EXE).name.lower()
    candidates = []

    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    @callback_type
    def enum_window(window_handle, _):
        if not user32.IsWindowVisible(window_handle):
            return True

        # Ignora janelas auxiliares/filhas que possuam uma janela proprietária.
        if user32.GetWindow(window_handle, GW_OWNER):
            return True

        title = _get_window_title(window_handle)

        if not title:
            return True

        window_process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(
            window_handle,
            ctypes.byref(window_process_id),
        )

        owner_process_id = window_process_id.value

        # Melhor cenário: a janela pertence exatamente ao PID retornado pelo Popen.
        if process_id is not None and owner_process_id == process_id:
            candidates.append((0, window_handle, title))
            return True

        # Alguns launchers podem criar outro processo. Nesse caso, só aceitamos
        # uma janela cujo executável proprietário seja exatamente Fakturama.exe.
        owner_process_name = _get_process_executable_name(owner_process_id)

        if owner_process_name != expected_process_name:
            return True

        candidates.append((1, window_handle, title))
        return True

    user32.EnumWindows(enum_window, 0)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    _, window_handle, title = candidates[0]

    LOGGER.debug(
        "Janela do Fakturama identificada: hwnd=%s | título=%s",
        window_handle,
        title,
    )
    return window_handle


def _get_process_executable_name(process_id):
    """Obtém o nome exato do executável proprietário de um processo Windows."""
    _, kernel32, wintypes = _get_win32_apis()

    process_handle = kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        process_id,
    )

    if not process_handle:
        return None

    try:
        buffer = ctypes.create_unicode_buffer(PROCESS_IMAGE_BUFFER_SIZE)
        buffer_size = wintypes.DWORD(len(buffer))

        success = kernel32.QueryFullProcessImageNameW(
            process_handle,
            0,
            buffer,
            ctypes.byref(buffer_size),
        )

        if not success:
            return None

        return PureWindowsPath(buffer.value).name.lower()

    finally:
        kernel32.CloseHandle(process_handle)


def _get_window_title(window_handle):
    """Obtém o título de uma janela Win32."""
    user32, _, _ = _get_win32_apis()
    length = user32.GetWindowTextLengthW(window_handle)

    if length <= 0:
        return ""

    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(window_handle, buffer, len(buffer))
    return buffer.value.strip()


def _activate_window(window_handle):
    """Restaura e solicita ao Windows o foco da janela informada."""
    user32, kernel32, wintypes = _get_win32_apis()

    if user32.IsIconic(window_handle):
        user32.ShowWindow(window_handle, SW_RESTORE)

    foreground_window = user32.GetForegroundWindow()
    current_thread_id = kernel32.GetCurrentThreadId()

    foreground_thread_id = 0
    if foreground_window:
        foreground_thread_id = user32.GetWindowThreadProcessId(
            foreground_window,
            None,
        )

    target_thread_id = user32.GetWindowThreadProcessId(
        window_handle,
        None,
    )

    attached_threads = []

    try:
        for thread_id in {
            foreground_thread_id,
            target_thread_id,
        }:
            if (
                thread_id
                and thread_id != current_thread_id
                and user32.AttachThreadInput(
                    current_thread_id,
                    thread_id,
                    True,
                )
            ):
                attached_threads.append(thread_id)

        user32.ShowWindow(window_handle, SW_RESTORE)
        user32.BringWindowToTop(window_handle)
        user32.SetForegroundWindow(window_handle)

    finally:
        for thread_id in reversed(attached_threads):
            user32.AttachThreadInput(
                current_thread_id,
                thread_id,
                False,
            )


def _get_win32_apis():
    """Carrega e configura as APIs Win32 usadas no controle da janela."""
    global _USER32, _KERNEL32

    if os.name != "nt":
        raise RuntimeError(
            "O controle de janela do Fakturama requer Windows."
        )

    from ctypes import wintypes

    if _USER32 is None:
        _USER32 = ctypes.WinDLL("user32", use_last_error=True)
        _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

        _USER32.IsWindow.argtypes = [wintypes.HWND]
        _USER32.IsWindow.restype = wintypes.BOOL

        _USER32.IsWindowVisible.argtypes = [wintypes.HWND]
        _USER32.IsWindowVisible.restype = wintypes.BOOL

        _USER32.GetWindow.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
        ]
        _USER32.GetWindow.restype = wintypes.HWND

        _USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        _USER32.GetWindowTextLengthW.restype = ctypes.c_int

        _USER32.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        _USER32.GetWindowTextW.restype = ctypes.c_int

        _USER32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        _USER32.GetWindowThreadProcessId.restype = wintypes.DWORD

        _USER32.IsIconic.argtypes = [wintypes.HWND]
        _USER32.IsIconic.restype = wintypes.BOOL

        _USER32.ShowWindow.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
        ]
        _USER32.ShowWindow.restype = wintypes.BOOL

        _USER32.BringWindowToTop.argtypes = [wintypes.HWND]
        _USER32.BringWindowToTop.restype = wintypes.BOOL

        _USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
        _USER32.SetForegroundWindow.restype = wintypes.BOOL

        _USER32.GetForegroundWindow.argtypes = []
        _USER32.GetForegroundWindow.restype = wintypes.HWND

        _USER32.AttachThreadInput.argtypes = [
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.BOOL,
        ]
        _USER32.AttachThreadInput.restype = wintypes.BOOL

        _KERNEL32.GetCurrentThreadId.argtypes = []
        _KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD

        _KERNEL32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        _KERNEL32.OpenProcess.restype = wintypes.HANDLE

        _KERNEL32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        _KERNEL32.QueryFullProcessImageNameW.restype = wintypes.BOOL

        _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
        _KERNEL32.CloseHandle.restype = wintypes.BOOL

    return _USER32, _KERNEL32, wintypes


def open_fakturama():
    """Abre o Fakturama, garante o foco e aguarda a tela principal."""
    global _FAKTURAMA_WINDOW_HANDLE

    executable = Path(FAKTURAMA_EXE)

    if not executable.exists():
        raise FileNotFoundError(
            f"Executável do Fakturama não encontrado: {executable}"
        )

    process = subprocess.Popen([str(executable)])

    try:
        _FAKTURAMA_WINDOW_HANDLE = _wait_for_fakturama_window(
            process_id=process.pid,
        )
        LOGGER.info(
            "Janela do Fakturama localizada: hwnd=%s",
            _FAKTURAMA_WINDOW_HANDLE,
        )

        ensure_fakturama_foreground()

        # Product+ indica visualmente que o aplicativo terminou de abrir.
        wait_for_image(PRODUCT_IMAGE)

    except Exception:
        LOGGER.exception(
            "Falha ao preparar a janela do Fakturama para automação"
        )

        try:
            terminate_existing_fakturama()
        except Exception:
            LOGGER.exception(
                "Não foi possível encerrar o Fakturama após falha na abertura"
            )

        raise


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

    ensure_fakturama_foreground()
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

    ensure_fakturama_foreground()
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
    ensure_fakturama_foreground()
    click_image(DEBTORS_LIST_IMAGE)
    time.sleep(EVIDENCE_VIEW_WAIT_SECONDS)
    return capture_screenshot(screenshot_path)


def capture_products_evidence(screenshot_path):
    """Abre a lista de produtos e captura a evidência dos cadastros."""
    ensure_fakturama_foreground()
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
    global _FAKTURAMA_WINDOW_HANDLE

    ensure_fakturama_foreground()
    time.sleep(FAKTURAMA_CLOSE_WAIT_SECONDS)
    pyautogui.hotkey("alt", "f4")
    _FAKTURAMA_WINDOW_HANDLE = None


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
