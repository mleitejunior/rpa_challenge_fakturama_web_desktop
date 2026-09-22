# Desafio Técnico RPA — Web + Desktop

Projeto desenvolvido para o desafio técnico de **Desenvolvedor RPA Pleno da BotCity**.

A automação executa um fluxo ponta a ponta entre aplicações web e desktop:

1. gera e coleta os dados de um comprador fictício brasileiro no Fake Name Generator;
2. autentica no Sauce Demo e coleta dinamicamente todo o catálogo de produtos;
3. persiste comprador e produtos em arquivos CSV;
4. recarrega os CSVs, que funcionam como ponte entre as etapas web e desktop;
5. cadastra o comprador e todos os produtos no Fakturama;
6. gera log e evidências visuais da execução.

## Stack

- Python 3
- Playwright
- PyAutoGUI
- OpenCV
- Pillow
- Pyperclip
- python-dotenv
- pytest

## Pré-requisitos

A execução desktop foi desenvolvida para **Windows** e requer:

- Python 3 disponível no `PATH`;
- acesso à internet para Fake Name Generator e Sauce Demo;
- Fakturama **2.2.0** instalado;
- Chromium do Playwright instalado;
- interface do Fakturama compatível com as imagens de referência em `resources/images/fakturama/`.

O instalador do Fakturama não é versionado no repositório devido ao tamanho. A versão utilizada como referência pode ser obtida diretamente em:

[Fakturama 2.2.0 — Windows x64 com JRE](https://files.fakturama.info/release/v2.2.0/Installer_Fakturama_windows-x64_2.2.0_with_jre.msi)

Por padrão, o projeto espera o executável em:

```text
C:\Program Files\Fakturama2\Fakturama.exe
```

Caso a instalação esteja em outro local, ajuste `FAKTURAMA_EXE` no arquivo `.env`.

## Instalação

No PowerShell, a partir da raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m playwright install chromium
```

## Configuração

O projeto possui valores padrão em `src/config/settings.py`. Para personalizar a execução, copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

O `.env` é local e não deve ser versionado.

Principais configurações:

```dotenv
APP_ENV=dev
BROWSER_HEADLESS=false
RESULTS_DIR=results

FAKTURAMA_EXE=C:\Program Files\Fakturama2\Fakturama.exe

IMAGE_CONFIDENCE=0.80
IMAGE_TIMEOUT_SECONDS=180
SAUCE_PRODUCTS_TIMEOUT_MS=15000
```

Os demais parâmetros de timeout, polling e validação visual estão documentados no próprio `.env.example`.

`APP_ENV` identifica o ambiente no log. O projeto não mantém perfis separados de `dev`, `staging` e `production`; os valores necessários podem ser sobrescritos pelas variáveis de ambiente.

## Execução

Com o ambiente virtual ativo e o Fakturama instalado:

```powershell
python main.py
```

Durante a execução, não utilize mouse ou teclado sobre o Fakturama, pois a etapa desktop depende do foco da interface.

O fluxo cria uma pasta exclusiva por execução:

```text
results/
└── YYYY-MM-DD_HHMMSS/
    ├── buyer.csv
    ├── products.csv
    ├── execution.log
    └── screenshots/
        ├── customer_registered.png
        ├── products_registered.png
        └── error.png              # somente quando aplicável
```

Os CSVs são gravados ao final da etapa web e **recarregados antes do cadastro no Fakturama**, garantindo que sejam a ponte efetiva de dados entre as duas etapas.

## Evidência de referência

O repositório mantém uma execução concluída para facilitar a avaliação sem exigir uma nova execução imediata:

```text
results/2026-09-21_234913/
```

Ela contém:

- `buyer.csv`;
- `products.csv`;
- `execution.log`;
- screenshot do comprador cadastrado;
- screenshot da lista de produtos cadastrados.

Novas execuções em `results/` são ignoradas pelo Git por padrão.

## Testes

Executar toda a suíte:

```powershell
python -m pytest
```

Somente integração:

```powershell
python -m pytest -m integration
```

Somente cenários de validação:

```powershell
python -m pytest -m validation
```

A suíte contém testes unitários de parsing e CSV, integração entre Playwright/parsing/persistência e cenários de validação da orquestração, incluindo tratamento de falhas e geração de evidências.

## Estrutura do projeto

```text
.
├── main.py
├── .env.example
├── requirements.txt
├── pytest.ini
│
├── src/
│   ├── config/
│   │   └── settings.py
│   ├── core/
│   │   └── execution.py
│   ├── desktop/
│   │   └── fakturama.py
│   ├── repositories/
│   │   └── csv_repository.py
│   └── web/
│       ├── buyer_scraper.py
│       └── sauce_demo.py
│
├── resources/
│   └── images/
│       └── fakturama/
│
├── tests/
│   ├── integration/
│   ├── validation/
│   └── test_*.py
│
├── results/
├── spikes/
└── docs/
```

- `src/web`: coleta e normalização dos dados web.
- `src/repositories`: persistência e leitura dos CSVs.
- `src/desktop`: automação do Fakturama e captura de evidências.
- `src/core`: criação da execução e logging.
- `src/config`: configuração de runtime a partir de variáveis de ambiente.
- `resources`: âncoras visuais utilizadas pelo PyAutoGUI.
- `spikes`: POC preservada como histórico técnico; o código de produção não depende dela.
- `docs`: enunciado, imagens e documento de solução.

## Premissas e limitações

A automação desktop utiliza reconhecimento de imagem e offsets relativos às âncoras visuais. Por isso:

- alterações de tema, zoom ou escala de exibição do Windows podem afetar o reconhecimento;
- recomenda-se manter a escala de exibição estável — preferencialmente 100% — durante a execução;
- não é necessário assumir uma resolução fixa, mas a interface do Fakturama deve manter proporções compatíveis com os assets;
- o Fakturama deve permanecer disponível e sem interação manual durante a etapa desktop;
- o preenchimento utiliza clipboard para ganhar velocidade, portanto o conteúdo atual da área de transferência é sobrescrito;
- repetir a execução cria novos registros no Fakturama.

Antes de inserir texto em um campo, a automação valida visualmente se o input recebeu foco pela cor de destaque da interface. Caso o foco não seja confirmado após as tentativas configuradas, a execução é interrompida e o erro é registrado.

## Documentação técnica

O desenho da solução e as principais decisões técnicas estão em:

[`docs/documento_solucao.md`](docs/documento_solucao.md)

O enunciado original do desafio está em:

[`docs/desafio_tecnico_rpa_candidato.pdf`](docs/desafio_tecnico_rpa_candidato.pdf)
