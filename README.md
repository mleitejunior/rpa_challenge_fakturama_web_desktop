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

- **Python 3** — linguagem principal utilizada para orquestrar todo o fluxo RPA.
- **Playwright** — automação das etapas web, incluindo navegação, login e coleta dos dados.
- **PyAutoGUI** — automação da interface desktop do Fakturama por mouse, teclado e screenshots.
- **OpenCV** — suporte ao reconhecimento das imagens da interface com nível de confiança (`confidence`).
- **Pillow** — manipulação de screenshots e leitura de pixels, utilizada também na validação visual do foco dos campos.
- **Pyperclip** — preenchimento rápido dos campos do Fakturama por copiar/colar.
- **python-dotenv** — carregamento das configurações locais definidas no arquivo `.env`.
- **pytest** — testes unitários, de integração e cenários de validação.

## Pré-requisitos

A automação desktop foi desenvolvida para **Windows**.

### Python 3

Baixe o instalador oficial para Windows em:

[Python — Downloads para Windows](https://www.python.org/downloads/windows/)

Durante a instalação, marque a opção:

```text
Add Python to PATH
```

Após instalar, abra o PowerShell e confirme:

```powershell
python --version
```

### Fakturama 2.2.0

Baixe a versão utilizada como referência no projeto:

[Fakturama 2.2.0 — Windows x64 com JRE](https://files.fakturama.info/release/v2.2.0/Installer_Fakturama_windows-x64_2.2.0_with_jre.msi)

Durante a instalação, utilize o idioma **Inglês (Englisch)**.

O projeto espera, por padrão, o executável em:

```text
C:\Program Files\Fakturama2\Fakturama.exe
```

Se o Fakturama for instalado em outro local, altere `FAKTURAMA_EXE` no arquivo `.env` após realizar a configuração descrita neste documento.

<mark style="color: red; background: transparent;">Após a instalação, crie uma pasta para armazenar dados do Fakturama e faça uma primeira execução, configura a 'Workspace Folder' que foi pedida para a pasta criada e prossiga até que o aplicativo abra. 

### Acesso à internet

É necessário acesso à internet durante a execução para acessar:

- Fake Name Generator;
- Sauce Demo.

## Observações do ambiente

### Sistema operacional

A automação foi desenvolvida para **Windows**.

Recomendação:

```text
Windows 11
```

### Resolução e escala

A automação foi desenvolvida e validada em:

```text
1920 x 1080
Escala do Windows: 100%
```

O uso dessa mesma configuração é recomendado.
Outras resoluções podem funcionar desde que a escala permaneça em 100% e a interface do Fakturama preserve o mesmo tamanho visual dos elementos. Alterações de escala, zoom ou aparência podem exigir nova validação das imagens de referência.

## Instalação

Execute os passos abaixo no Windows.

### 1. Obter o projeto

Há duas opções.

**Opção A — Download pelo GitHub**

Na página do repositório:

```text
Code → Download ZIP
```

Extraia o arquivo ZIP para uma pasta local e abra o PowerShell dentro dessa pasta.

**Opção B — Git clone** (requer [Git for Windows](https://git-scm.com/download/win) instalado)

Copie a URL do repositório no GitHub e execute:

```powershell
git clone <URL_DO_REPOSITORIO>
cd rpa_challenge_fakturama_web_desktop
```

### 2. Criar e ativar o ambiente virtual

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Quando estiver ativo, o terminal deverá mostrar algo semelhante a:

```text
(.venv) PS C:\...\rpa_challenge_fakturama_web_desktop>
```

> Se o PowerShell bloquear a ativação de scripts, execute `Set-ExecutionPolicy -Scope Process Bypass` e tente ativar novamente. Essa alteração vale somente para a janela atual do PowerShell.

### 3. Instalar as dependências

Com o ambiente virtual ativo:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Instalar o Chromium do Playwright

Execute:

```powershell
python -m playwright install chromium
```

Esse comando precisa ser executado apenas no setup da máquina.

### 5. Criar o arquivo de configuração local

Copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

O projeto está pronto para execução com os valores padrão. 

## Configuração

O projeto utiliza dois níveis simples de configuração:

- `.env`: arquivo local com valores que podem variar entre máquinas ou ambientes;
- `src/config/settings.py`: responsável por carregar o `.env`, aplicar valores padrão e converter os tipos utilizados pelo código.

O `.env` é criado a partir de `.env.example` e **não deve ser versionado no Git**.

Exemplo das principais configurações:

```dotenv
APP_ENV=dev
BROWSER_HEADLESS=false
RESULTS_DIR=results

FAKTURAMA_EXE=C:\Program Files\Fakturama2\Fakturama.exe
FAKTURAMA_TERMINATION_TIMEOUT_SECONDS=10

IMAGE_CONFIDENCE=0.80
IMAGE_TIMEOUT_SECONDS=180
SAUCE_PRODUCTS_TIMEOUT_MS=15000
```

### Caminho do Fakturama

Se o Fakturama estiver instalado em outro local, altere somente esta linha do `.env`:

```dotenv
FAKTURAMA_EXE=C:\caminho\para\Fakturama.exe
```

Não é necessário alterar o código-fonte.

Os demais parâmetros de timeout, polling e validação visual estão documentados no próprio `.env.example`.

`APP_ENV` identifica o ambiente no log. O projeto não mantém perfis separados de `dev`, `staging` e `production`; os valores necessários podem ser sobrescritos por variáveis de ambiente.

## Execução

Durante a etapa desktop:

<mark style="color: red; background: transparent;">- não utilize o mouse;</mark><br>
<mark style="color: red; background: transparent;">- não utilize o teclado;</mark><br>
<mark style="color: red; background: transparent;">- não minimize ou mova a janela do Fakturama.</mark>


> **Importante:** salve qualquer trabalho manual aberto no Fakturama antes de executar o RPA. Uma instância já aberta será encerrada e alterações não salvas poderão ser perdidas.


Com o ambiente virtual ativo e o Fakturama instalado:

```powershell
python main.py
```

Antes de iniciar o fluxo, o RPA verifica se já existe uma instância do Fakturama em execução. Caso exista, ela é encerrada de forma forçada para garantir que a automação comece em um estado conhecido.

A automação depende do foco e da aparência da interface.

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

Durante o primeiro cadastro de preço, o RPA identifica automaticamente se o Fakturama daquela máquina aceita melhor `,` ou `.` como separador decimal. A preferência validada é salva em `.runtime_state.json`, também ignorado pelo Git, e passa a ser tentada primeiro nos próximos produtos e nas próximas execuções daquela máquina. Se deixar de funcionar, o outro separador é testado e a preferência é atualizada automaticamente.


## Premissas e limitações

A automação desktop utiliza reconhecimento de imagem e offsets relativos às âncoras visuais. Por isso:

- alterações de tema, zoom ou escala de exibição do Windows podem afetar o reconhecimento;
- recomenda-se utilizar resolução `1920 x 1080` e escala de exibição de 100%;
- outras resoluções devem ser validadas antes do uso;
- o Fakturama deve permanecer disponível e sem interação manual durante a etapa desktop;
- o preenchimento utiliza clipboard para ganhar velocidade, portanto o conteúdo atual da área de transferência é sobrescrito;
- repetir a execução cria novos registros no Fakturama.

Antes de inserir texto em um campo, a automação valida visualmente se o input recebeu foco pela cor de destaque da interface. Caso o foco não seja confirmado após as tentativas configuradas, a execução é interrompida e o erro é registrado.

## Outras Documentações

O desenho da solução e as principais decisões técnicas estão em:

[`docs/documento_solucao.md`](docs/documento_solucao.md)

O enunciado original do desafio está em:

[`docs/desafio_tecnico_rpa_candidato.pdf`](docs/desafio_tecnico_rpa_candidato.pdf)

## Suporte

Esta solução foi desenvolvida por **mleitejunior**.

Em caso de dúvidas, sugestões ou observações sobre o projeto:

- LinkedIn: `mleitejunior`
- E-mail: `mleitejunior@gmail.com`