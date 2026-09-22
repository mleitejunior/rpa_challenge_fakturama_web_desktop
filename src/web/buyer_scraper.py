import re
from datetime import date

from playwright.sync_api import Page


FAKE_NAME_URL = "https://www.fakenamegenerator.com/gen-random-br-br.php"
FAKE_NAME_TIMEOUT_MS = 15000

NAME_SELECTOR = "#details .address h3"
ADDRESS_SELECTOR = "#details .address .adr"

CPF_LABEL = "Cadastro de Pessoas Físicas"
PHONE_LABEL = "Phone"
BIRTH_DATE_LABEL = "Birthday"

MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def parse_buyer(full_name, address_text, cpf, phone, birth_date):
    """Normaliza os dados brutos do Fake Name Generator."""
    normalized_name = " ".join(full_name.split())
    name_parts = normalized_name.split(" ", 1)

    if len(name_parts) != 2 or not name_parts[1].strip():
        raise ValueError("O nome completo deve conter nome e sobrenome.")

    first_name, last_name = name_parts

    address_lines = [
        line.strip()
        for line in address_text.splitlines()
        if line.strip()
    ]

    if len(address_lines) < 3:
        raise ValueError("Formato de endereço inválido.")

    street_line = address_lines[0]
    city_state_line = address_lines[1]
    zip_code = address_lines[2]

    if "," not in street_line or "-" not in city_state_line:
        raise ValueError("Formato de endereço inválido.")

    street, number = [part.strip() for part in street_line.rsplit(",", 1)]
    city, state = [part.strip() for part in city_state_line.rsplit("-", 1)]

    if not all((street, number, city, state, zip_code)):
        raise ValueError("Formato de endereço inválido.")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "street": street,
        "number": number,
        "city": city,
        "state": state.upper(),
        "zip_code": zip_code,
        "cpf": cpf.strip(),
        "phone": phone.strip(),
        "birth_date": _normalize_birth_date(birth_date),
    }


def scrape_buyer(page: Page):
    """Coleta e normaliza um comprador fictício brasileiro."""
    page.goto(FAKE_NAME_URL, wait_until="domcontentloaded")

    name_locator = page.locator(NAME_SELECTOR)
    name_locator.wait_for(
        state="visible",
        timeout=FAKE_NAME_TIMEOUT_MS,
    )

    full_name = name_locator.inner_text().strip()
    address_text = page.locator(ADDRESS_SELECTOR).inner_text().strip()
    cpf = _get_detail_value(page, CPF_LABEL)
    phone = _get_detail_value(page, PHONE_LABEL)
    birth_date = _get_detail_value(page, BIRTH_DATE_LABEL)

    return parse_buyer(
        full_name=full_name,
        address_text=address_text,
        cpf=cpf,
        phone=phone,
        birth_date=birth_date,
    )


def _get_detail_value(page: Page, label: str) -> str:
    """Obtém o valor de um campo identificado pelo texto de seu dt."""
    locator = page.locator(
        "xpath="
        f'//dl[contains(@class, "dl-horizontal")]/dt['
        f'normalize-space()="{label}"]/'
        "following-sibling::dd[1]"
    )

    locator.wait_for(
        state="visible",
        timeout=FAKE_NAME_TIMEOUT_MS,
    )

    return locator.inner_text().strip()


def _normalize_birth_date(value: str) -> str:
    """Converte a data em inglês do site para o padrão ISO YYYY-MM-DD."""
    match = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})",
        value.strip(),
    )

    if match is None:
        raise ValueError(f"Data de nascimento inválida: {value}")

    month_name, day_text, year_text = match.groups()
    month = MONTHS.get(month_name)

    if month is None:
        raise ValueError(f"Data de nascimento inválida: {value}")

    try:
        normalized_date = date(
            year=int(year_text),
            month=month,
            day=int(day_text),
        )
    except ValueError as error:
        raise ValueError(
            f"Data de nascimento inválida: {value}"
        ) from error

    return normalized_date.isoformat()
