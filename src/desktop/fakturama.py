import ctypes
import json
import logging
import os
import subprocess
import time
from decimal import Decimal, InvalidOperation
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
    FOCUS_COLOR_TOLERANCE,
    FOCUS_MIN_MATCH_RATIO,
    ICON_IMAGE_CONFIDENCE,
    IMAGE_POLL_INTERVAL_SECONDS,
    IMAGE_TIMEOUT_SECONDS,
    TEXT_IMAGE_CONFIDENCE,
)

LOGGER = logging.getLogger("rpa.fakturama")


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FAKTURAMA_ASSETS = PROJECT_ROOT / "resources" / "images" / "fakturama"
RUNTIME_STATE_FILE = PROJECT_ROOT / ".runtime_state.json"
PRICE_SEPARATOR_STATE_KEY = "price_decimal_separator"

# Imagens usadas como âncoras na automação desktop.
PRODUCT_IMAGE = FAKTURAMA_ASSETS / "product_icon.png"
CONTACT_IMAGE = FAKTURAMA_ASSETS / "contact_icon.png"
NEW_DEBTOR_IMAGES = (
    FAKTURAMA_ASSETS / "new_debtor_variant_1.png",
    FAKTURAMA_ASSETS / "new_debtor_variant_2.png",
)
FIRST_NAME_LAST_NAME_IMAGES = (
    FAKTURAMA_ASSETS / "first_name_last_name_variant_1.png",
    FAKTURAMA_ASSETS / "first_name_last_name_variant_2.png",
)
ZIP_CITY_IMAGES = (
    FAKTURAMA_ASSETS / "zip_city_variant_1.png",
    FAKTURAMA_ASSETS / "zip_city_variant_2.png",
)
SAVE_IMAGE = FAKTURAMA_ASSETS / "save_icon.png"
ITEM_NUMBER_IMAGES = (
    FAKTURAMA_ASSETS / "item_number_variant_1.png",
    FAKTURAMA_ASSETS / "item_number_variant_2.png",
)
NAME_IMAGES = (
    FAKTURAMA_ASSETS / "name_variant_1.png",
    FAKTURAMA_ASSETS / "name_variant_2.png",
)
DESCRIPTION_IMAGES = (
    FAKTURAMA_ASSETS / "description_variant_1.png",
    FAKTURAMA_ASSETS / "description_variant_2.png",
)
PRICE_GROSS_IMAGES = (
    FAKTURAMA_ASSETS / "price_gross_variant_1.png",
    FAKTURAMA_ASSETS / "price_gross_variant_2.png",
)
STOCK_IMAGES = (
    FAKTURAMA_ASSETS / "stock_variant_1.png",
    FAKTURAMA_ASSETS / "stock_variant_2.png",
)
STREET_IMAGES = (
    FAKTURAMA_ASSETS / "street_variant_1.png",
    FAKTURAMA_ASSETS / "street_variant_2.png",
)
ADDRESS_SPECIFICATION_IMAGES = (
    FAKTURAMA_ASSETS / "address_specification_variant_1.png",
    FAKTURAMA_ASSETS / "address_specification_variant_2.png",
)
DEBTORS_LIST_IMAGE = FAKTURAMA_ASSETS / "debtors_list_icon.png"
PRODUCTS_LIST_IMAGE = FAKTURAMA_ASSETS / "products_list_icon.png"

# Tipos de âncora visual.
# Ícones são mais estáveis entre máquinas; labels textuais recebem tolerância
# própria porque a rasterização de fonte pode variar entre Windows/Java/GPU.
ICON_ANCHORS = {
    PRODUCT_IMAGE,
    CONTACT_IMAGE,
    SAVE_IMAGE,
    DEBTORS_LIST_IMAGE,
    PRODUCTS_LIST_IMAGE,
}
SIDEBAR_ICON_ANCHORS = {
    DEBTORS_LIST_IMAGE,
    PRODUCTS_LIST_IMAGE,
}
TOOLBAR_ICON_ANCHORS = {
    PRODUCT_IMAGE,
    CONTACT_IMAGE,
}

# Regras internas da automação desktop.
DEFAULT_PRODUCT_STOCK = "1"
NUMERIC_FIELD_CLIPBOARD_WAIT_SECONDS = 0.10
CLIPBOARD_VALIDATION_SENTINEL = "__RPA_CLIPBOARD_NOT_UPDATED__"
PRICE_DECIMAL_SEPARATORS = (",", ".")

# Compatibilidade do formulário de contato entre máquinas.
SHORT_ANCHOR_TIMEOUT_SECONDS = 2.0
CONTACT_SCROLL_ATTEMPTS = 4
CONTACT_SCROLL_AMOUNT = -4
CONTACT_SCROLL_WAIT_SECONDS = 0.25
ZIP_ROW_OFFSET_FROM_STREET = 3

# Controle da janela do Fakturama no Windows.
WINDOW_FOCUS_MAX_ATTEMPTS = 5
WINDOW_FOCUS_RETRY_SECONDS = 0.25
WINDOW_MAXIMIZE_WAIT_SECONDS = 0.5
SW_RESTORE = 9
SW_MAXIMIZE = 3
GW_OWNER = 4
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_IMAGE_BUFFER_SIZE = 32768

_FAKTURAMA_WINDOW_HANDLE = None
_USER32 = None
_KERNEL32 = None
_PREFERRED_PRICE_DECIMAL_SEPARATOR = None
_PRICE_SEPARATOR_STATE_LOADED = False

# Validação visual de foco dos campos.
# O Fakturama destaca o input ativo com este tom de amarelo.
FOCUSED_FIELD_COLOR = (250, 240, 162)
FOCUS_SAMPLE_WIDTH = 12
FOCUS_SAMPLE_HEIGHT = 8
FOCUS_RETRY_OFFSET_X = 5
FOCUS_RETRY_COUNT = 5

# Confirmações de fechamento do Fakturama.
FAKTURAMA_CLOSE_CONFIRM_WAIT_SECONDS = 0.5

# O copy/paste com pyperclip foi mantido por ser significativamente mais rápido
# que a digitação caractere a caractere. Como trade-off, o conteúdo atual do
# clipboard do usuário é sobrescrito durante a execução.


def wait_for_image(
    image_path,
    timeout=IMAGE_TIMEOUT_SECONDS,
    confidence=None,
):
    """Aguarda uma das variantes da âncora dentro da janela do Fakturama."""
    candidates = _normalize_anchor_candidates(image_path)
    deadline = time.monotonic() + timeout

    if confidence is None:
        confidence = _get_anchor_confidence(candidates[0])

    while time.monotonic() < deadline:
        ensure_fakturama_foreground()

        for path in candidates:
            region = _get_anchor_search_region(path)
            grayscale = path not in ICON_ANCHORS

            try:
                location = pyautogui.locateOnScreen(
                    str(path),
                    confidence=confidence,
                    region=region,
                    grayscale=grayscale,
                )
            except pyautogui.ImageNotFoundException:
                location = None

            if location:
                if len(candidates) > 1:
                    LOGGER.info(
                        "Âncora %s localizada com a variante %s",
                        candidates[0].stem,
                        path.name,
                    )
                return location

        time.sleep(IMAGE_POLL_INTERVAL_SECONDS)

    candidate_names = ", ".join(path.name for path in candidates)
    raise TimeoutError(
        "Nenhuma variante da imagem foi encontrada em até "
        f"{timeout}s: {candidate_names} "
        f"(confidence={confidence:.2f})"
    )


def _normalize_anchor_candidates(image_path):
    """Normaliza uma âncora única ou uma coleção de variantes."""
    if isinstance(image_path, (tuple, list, set)):
        candidates = tuple(Path(path) for path in image_path)
    else:
        candidates = (Path(image_path),)

    if not candidates:
        raise ValueError("Nenhuma imagem foi informada para a âncora.")

    return candidates


def _get_anchor_confidence(image_path):
    """Retorna a confiança adequada ao tipo de âncora visual."""
    if image_path in ICON_ANCHORS:
        return ICON_IMAGE_CONFIDENCE

    return TEXT_IMAGE_CONFIDENCE


def _get_anchor_search_region(image_path):
    """Limita a busca à área relevante da janela real do Fakturama."""
    left, top, width, height = _get_fakturama_window_region()

    if image_path in TOOLBAR_ICON_ANCHORS:
        toolbar_height = max(120, int(height * 0.22))
        return (left, top, width, min(toolbar_height, height))

    if image_path in SIDEBAR_ICON_ANCHORS:
        sidebar_width = max(220, int(width * 0.28))
        return (left, top, min(sidebar_width, width), height)

    # Labels textuais podem começar muito próximos à borda esquerda do conteúdo
    # dependendo do layout/escala da máquina. Como a busca já está limitada à
    # janela correta do Fakturama, usamos a janela inteira para esses casos.
    return (left, top, width, height)


def _get_fakturama_window_region():
    """Obtém a região visível da janela do Fakturama em coordenadas de tela."""
    global _FAKTURAMA_WINDOW_HANDLE

    user32, _, wintypes = _get_win32_apis()

    if (
        _FAKTURAMA_WINDOW_HANDLE is None
        or not user32.IsWindow(_FAKTURAMA_WINDOW_HANDLE)
    ):
        _FAKTURAMA_WINDOW_HANDLE = _wait_for_fakturama_window()

    rect = wintypes.RECT()

    if not user32.GetWindowRect(
        _FAKTURAMA_WINDOW_HANDLE,
        ctypes.byref(rect),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    screen_width, screen_height = pyautogui.size()

    left = max(0, rect.left)
    top = max(0, rect.top)
    right = min(screen_width, rect.right)
    bottom = min(screen_height, rect.bottom)

    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        raise RuntimeError(
            "A janela do Fakturama não possui uma região visível válida."
        )

    return (left, top, width, height)


def click_image(image_path, timeout=IMAGE_TIMEOUT_SECONDS):
    """Aguarda uma imagem e clica no centro dela."""
    location = wait_for_image(image_path, timeout=timeout)
    center = pyautogui.center(location)
    pyautogui.click(center.x, center.y)
    return location


def click_right_of_image(
    image_path,
    offset_x=FIELD_CLICK_OFFSET_X,
    timeout=IMAGE_TIMEOUT_SECONDS,
    confidence=None,
):
    """Clica à direita da âncora e valida se o campo recebeu foco."""
    candidates = _normalize_anchor_candidates(image_path)
    location = wait_for_image(
        candidates,
        timeout=timeout,
        confidence=confidence,
    )

    x = location.left + location.width + offset_x
    y = location.top + (location.height // 2)

    _click_and_validate_focus(x, y, candidates[0].stem)
    return location


def click_field_image(image_path, timeout=IMAGE_TIMEOUT_SECONDS):
    """Clica no centro de uma das variantes de campo e valida o foco."""
    candidates = _normalize_anchor_candidates(image_path)
    location = wait_for_image(candidates, timeout=timeout)
    center = pyautogui.center(location)

    _click_and_validate_focus(center.x, center.y, candidates[0].stem)
    return location


def paste_text(value):
    """Copia o valor para o clipboard e cola no campo em foco."""
    pyperclip.copy(str(value))
    pyautogui.hotkey("ctrl", "v")


def paste_and_validate_numeric(value, field_name, input_candidates=None):
    """Substitui e valida um valor numérico lendo o conteúdo do próprio campo."""
    expected_value = _parse_numeric_value(value)

    if input_candidates is None:
        input_candidates = _build_numeric_input_candidates(value)

    candidates = tuple(dict.fromkeys(str(item) for item in input_candidates))
    last_read_value = None

    for candidate in candidates:
        # Os campos numéricos já possuem valor padrão. Selecionar e apagar antes
        # de colar impede que o novo conteúdo seja concatenado ao valor existente.
        pyautogui.hotkey("ctrl", "a")
        pyautogui.press("backspace")
        pyperclip.copy(candidate)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(NUMERIC_FIELD_CLIPBOARD_WAIT_SECONDS)

        # O Fakturama aplica a formatação definitiva quando o campo perde foco.
        # Tab + Shift+Tab força esse commit e retorna ao mesmo input antes da leitura.
        pyautogui.press("tab")
        time.sleep(NUMERIC_FIELD_CLIPBOARD_WAIT_SECONDS)
        pyautogui.hotkey("shift", "tab")
        time.sleep(NUMERIC_FIELD_CLIPBOARD_WAIT_SECONDS)

        # Lê o valor já formatado pelo próprio Fakturama. A sentinela garante
        # que um Ctrl+C sem conteúdo não reutilize o valor anterior do clipboard.
        pyautogui.hotkey("ctrl", "a")
        pyperclip.copy(CLIPBOARD_VALIDATION_SENTINEL)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(NUMERIC_FIELD_CLIPBOARD_WAIT_SECONDS)
        last_read_value = pyperclip.paste().strip()

        if last_read_value == CLIPBOARD_VALIDATION_SENTINEL:
            LOGGER.warning(
                "Não foi possível ler o conteúdo do campo %s após inserir %s",
                field_name,
                candidate,
            )
            continue

        try:
            actual_value = _parse_numeric_value(last_read_value)
        except ValueError:
            LOGGER.warning(
                "Campo %s retornou valor não numérico após inserir %s: %r",
                field_name,
                candidate,
                last_read_value,
            )
            continue

        if actual_value == expected_value:
            LOGGER.info(
                "Campo %s validado: inserido=%s | lido=%s",
                field_name,
                candidate,
                last_read_value,
            )
            return last_read_value, candidate

        LOGGER.warning(
            "Validação do campo %s falhou: esperado=%s | inserido=%s | lido=%s",
            field_name,
            expected_value,
            candidate,
            last_read_value,
        )

    raise RuntimeError(
        f"Não foi possível registrar corretamente o valor numérico do campo "
        f"{field_name}. Esperado: {expected_value}. "
        f"Último valor lido: {last_read_value!r}."
    )


def _build_numeric_input_candidates(value):
    """Gera representações numéricas compatíveis com diferentes localidades."""
    numeric_value = _parse_numeric_value(value)
    canonical = format(numeric_value, "f")

    if numeric_value == numeric_value.to_integral():
        integer_value = str(int(numeric_value))
        return (
            integer_value,
            f"{integer_value},00",
            f"{integer_value}.00",
        )

    return (
        canonical.replace(".", ","),
        canonical,
    )


def _build_price_input_candidates(value):
    """Gera candidatos priorizando o separador aprendido nesta máquina."""
    numeric_value = _parse_numeric_value(value)
    canonical = format(numeric_value, "f")
    preferred_separator = _get_preferred_price_decimal_separator()

    separators = list(PRICE_DECIMAL_SEPARATORS)

    if preferred_separator in separators:
        separators.remove(preferred_separator)
        separators.insert(0, preferred_separator)

    return tuple(
        canonical.replace(".", separator)
        for separator in separators
    )


def _remember_price_decimal_separator(candidate):
    """Persiste o separador decimal que foi validado pelo Fakturama."""
    separator = _extract_decimal_separator(candidate)

    if separator not in PRICE_DECIMAL_SEPARATORS:
        return

    current = _get_preferred_price_decimal_separator()

    if current == separator:
        return

    _save_preferred_price_decimal_separator(separator)
    LOGGER.info(
        "Separador decimal preferido do Fakturama atualizado para %r",
        separator,
    )


def _extract_decimal_separator(value):
    """Extrai o último separador decimal explícito de um valor de entrada."""
    text = str(value)
    dot_index = text.rfind(".")
    comma_index = text.rfind(",")

    if dot_index < 0 and comma_index < 0:
        return None

    return "." if dot_index > comma_index else ","


def _get_preferred_price_decimal_separator():
    """Carrega uma vez a preferência local de separador decimal."""
    global _PREFERRED_PRICE_DECIMAL_SEPARATOR
    global _PRICE_SEPARATOR_STATE_LOADED

    if _PRICE_SEPARATOR_STATE_LOADED:
        return _PREFERRED_PRICE_DECIMAL_SEPARATOR

    _PRICE_SEPARATOR_STATE_LOADED = True

    if not RUNTIME_STATE_FILE.exists():
        return None

    try:
        state = json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.warning(
            "Não foi possível ler o estado local de runtime: %s",
            error,
        )
        return None

    separator = state.get(PRICE_SEPARATOR_STATE_KEY)

    if separator not in PRICE_DECIMAL_SEPARATORS:
        LOGGER.warning(
            "Separador decimal salvo é inválido e será ignorado: %r",
            separator,
        )
        return None

    _PREFERRED_PRICE_DECIMAL_SEPARATOR = separator
    LOGGER.info(
        "Separador decimal preferido carregado do estado local: %r",
        separator,
    )
    return separator


def _save_preferred_price_decimal_separator(separator):
    """Salva a preferência local sem tornar a execução dependente do arquivo."""
    global _PREFERRED_PRICE_DECIMAL_SEPARATOR
    global _PRICE_SEPARATOR_STATE_LOADED

    _PREFERRED_PRICE_DECIMAL_SEPARATOR = separator
    _PRICE_SEPARATOR_STATE_LOADED = True

    state = {}

    if RUNTIME_STATE_FILE.exists():
        try:
            state = json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = {}

    state[PRICE_SEPARATOR_STATE_KEY] = separator
    temporary_file = RUNTIME_STATE_FILE.with_suffix(".tmp")

    try:
        temporary_file.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_file.replace(RUNTIME_STATE_FILE)
    except OSError as error:
        LOGGER.warning(
            "Separador decimal foi aprendido em memória, mas não pôde ser "
            "persistido para próximas execuções: %s",
            error,
        )
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass


def _parse_numeric_value(value):
    """Converte valores monetários/decimais em Decimal de forma independente da localidade."""
    normalized = str(value).strip()

    # Mantém apenas os caracteres relevantes para o valor numérico.
    normalized = "".join(
        character
        for character in normalized
        if character.isdigit() or character in {"-", ".", ","}
    )

    if not normalized or normalized in {"-", ".", ","}:
        raise ValueError(f"Valor numérico inválido: {value!r}")

    if "." in normalized and "," in normalized:
        # Quando os dois separadores aparecem, o último é tratado como decimal
        # e o outro como separador de milhar.
        decimal_separator = (
            "." if normalized.rfind(".") > normalized.rfind(",") else ","
        )
        thousands_separator = "," if decimal_separator == "." else "."
        normalized = normalized.replace(thousands_separator, "")
        normalized = normalized.replace(decimal_separator, ".")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"Valor numérico inválido: {value!r}") from error



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


def _maximize_window(window_handle):
    """Maximiza a janela principal do Fakturama e mantém o foco."""
    user32, _, _ = _get_win32_apis()

    user32.ShowWindow(window_handle, SW_MAXIMIZE)
    time.sleep(WINDOW_MAXIMIZE_WAIT_SECONDS)
    ensure_fakturama_foreground()


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

        _USER32.GetWindowRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]
        _USER32.GetWindowRect.restype = wintypes.BOOL

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
        _maximize_window(_FAKTURAMA_WINDOW_HANDLE)

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

    # A aba de novo contato confirma que o formulário terminou de abrir.
    wait_for_image(NEW_DEBTOR_IMAGES)

    # O Customer ID é gerado automaticamente pelo Fakturama.
    click_right_of_image(FIRST_NAME_LAST_NAME_IMAGES)
    paste_text(buyer["first_name"])

    pyautogui.press("tab")
    paste_text(buyer["last_name"])

    _click_zip_city_field()
    paste_text(buyer["zip_code"])

    _save_and_close_tab()


def _click_zip_city_field():
    """Localiza o ZIP/City mesmo quando o formulário varia entre máquinas."""
    try:
        click_right_of_image(
            ZIP_CITY_IMAGES,
            timeout=SHORT_ANCHOR_TIMEOUT_SECONDS,
        )
        return
    except TimeoutError:
        LOGGER.info(
            "ZIP/City não visível diretamente; iniciando busca com scroll."
        )

    last_error = None

    for attempt in range(1, CONTACT_SCROLL_ATTEMPTS + 1):
        _scroll_contact_form_down()

        try:
            click_right_of_image(
                ZIP_CITY_IMAGES,
                timeout=SHORT_ANCHOR_TIMEOUT_SECONDS,
            )
            LOGGER.info(
                "ZIP/City localizado após scroll %d/%d",
                attempt,
                CONTACT_SCROLL_ATTEMPTS,
            )
            return
        except TimeoutError as error:
            last_error = error

        try:
            _click_zip_city_from_address_rows()
            LOGGER.info(
                "ZIP/City localizado pela geometria das linhas de endereço "
                "após scroll %d/%d",
                attempt,
                CONTACT_SCROLL_ATTEMPTS,
            )
            return
        except (TimeoutError, RuntimeError) as error:
            last_error = error

    raise TimeoutError(
        "Não foi possível localizar com segurança o campo ZIP/City."
    ) from last_error


def _scroll_contact_form_down():
    """Rola o painel superior do formulário de contato para baixo."""
    left, top, width, height = _get_fakturama_window_region()
    x = left + width - 35
    y = top + int(height * 0.40)
    pyautogui.moveTo(x, y)
    pyautogui.scroll(CONTACT_SCROLL_AMOUNT)
    time.sleep(CONTACT_SCROLL_WAIT_SECONDS)


def _click_zip_city_from_address_rows():
    """Calcula o ZIP/City a partir de duas linhas de endereço reconhecidas."""
    street = wait_for_image(
        STREET_IMAGES,
        timeout=SHORT_ANCHOR_TIMEOUT_SECONDS,
    )
    address_specification = wait_for_image(
        ADDRESS_SPECIFICATION_IMAGES,
        timeout=SHORT_ANCHOR_TIMEOUT_SECONDS,
    )

    row_spacing = address_specification.top - street.top

    if row_spacing <= 0 or row_spacing > 80:
        raise RuntimeError(
            "Espaçamento inesperado entre as linhas Street e "
            f"Address specification: {row_spacing}px"
        )

    x = street.left + street.width + FIELD_CLICK_OFFSET_X
    y = (
        street.top
        + (ZIP_ROW_OFFSET_FROM_STREET * row_spacing)
        + (street.height // 2)
    )

    left, top, width, height = _get_fakturama_window_region()
    if not (left <= x < left + width and top <= y < top + height):
        raise RuntimeError(
            "Posição calculada para ZIP/City ficou fora da janela do Fakturama."
        )

    # Se a geometria estiver incorreta, a validação de cor impede a digitação
    # em outro componente da interface.
    _click_and_validate_focus(
        x,
        y,
        "ZIP - City (posição relativa)",
    )


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

    # A própria âncora do Item Number confirma que o formulário está pronto.
    click_right_of_image(ITEM_NUMBER_IMAGES)
    paste_text(product["item_number"])

    click_right_of_image(NAME_IMAGES)
    paste_text(product["name"])

    # A imagem de Description inclui o próprio campo, então o clique é central.
    click_field_image(DESCRIPTION_IMAGES)
    paste_text(product["description"])

    click_right_of_image(PRICE_GROSS_IMAGES)
    _, validated_price_candidate = paste_and_validate_numeric(
        product["price"],
        "Price (gross)",
        input_candidates=_build_price_input_candidates(product["price"]),
    )
    _remember_price_decimal_separator(validated_price_candidate)

    click_right_of_image(STOCK_IMAGES)
    paste_and_validate_numeric(
        DEFAULT_PRODUCT_STOCK,
        "Stock",
    )

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
    """Fecha o Fakturama tratando as confirmações exibidas pela aplicação."""
    global _FAKTURAMA_WINDOW_HANDLE

    ensure_fakturama_foreground()
    time.sleep(FAKTURAMA_CLOSE_WAIT_SECONDS)

    # 1) Solicita o fechamento da aplicação.
    pyautogui.hotkey("alt", "f4")
    time.sleep(FAKTURAMA_CLOSE_CONFIRM_WAIT_SECONDS)

    # 2) Confirma o diálogo "Quit Fakturama".
    pyautogui.press("enter")
    time.sleep(FAKTURAMA_CLOSE_CONFIRM_WAIT_SECONDS)

    process_name = PureWindowsPath(FAKTURAMA_EXE).name

    # 3) Quando existe uma aba/registro não salvo, o Fakturama pode abrir o
    # diálogo "Save Parts". Executa a sequência solicitada somente se o
    # processo ainda estiver ativo, evitando enviar teclas a outra aplicação.
    if _is_process_running(process_name):
        pyautogui.hotkey("shift", "tab")
        pyautogui.press("enter")

    deadline = time.monotonic() + FAKTURAMA_TERMINATION_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        if not _is_process_running(process_name):
            _FAKTURAMA_WINDOW_HANDLE = None
            return

        time.sleep(IMAGE_POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        "O Fakturama permaneceu aberto após as confirmações de fechamento."
    )


def _click_and_validate_focus(x, y, field_name):
    """Valida o foco tentando até cinco posições 5 px mais à direita."""
    total_attempts = FOCUS_RETRY_COUNT + 1

    for attempt in range(total_attempts):
        current_x = x + (attempt * FOCUS_RETRY_OFFSET_X)

        pyautogui.click(current_x, y)
        time.sleep(FOCUS_AFTER_CLICK_WAIT_SECONDS)

        if _is_field_focused(current_x, y):
            if attempt:
                LOGGER.info(
                    "Foco confirmado no campo %s após deslocamento de +%dpx",
                    field_name,
                    attempt * FOCUS_RETRY_OFFSET_X,
                )
            return

        LOGGER.warning(
            "Foco não confirmado no campo %s na tentativa %d/%d "
            "(deslocamento +%dpx)",
            field_name,
            attempt + 1,
            total_attempts,
            attempt * FOCUS_RETRY_OFFSET_X,
        )

    raise RuntimeError(
        f"Campo não recebeu foco após a posição inicial e "
        f"{FOCUS_RETRY_COUNT} novas tentativas de "
        f"{FOCUS_RETRY_OFFSET_X}px à direita: {field_name}"
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
