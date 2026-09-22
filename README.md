# Desafio Técnico RPA — BotCity

Este projeto contém a implementação do desafio técnico para a vaga de **Desenvolvedor RPA Pleno na BotCity**.

O objetivo da automação é integrar etapas de **automação web** e **automação desktop**, realizando:

- geração de um comprador fictício;
- coleta do catálogo completo de produtos do Sauce Demo;
- persistência dos dados coletados em arquivos CSV;
- cadastro do comprador no Fakturama;
- cadastro dos produtos no Fakturama;
- geração de logs e evidências da execução.

## Documentação inicial

O desenho inicial da solução, decisões técnicas, fluxo proposto e premissas estão documentados em:

[`docs/documento_solucao.md`](docs/documento_solucao.md)

O enunciado original do desafio também está disponível na pasta `docs`.

[`docs/desafio_tecnico_rpa_candidato.pdf`](docs/desafio_tecnico_rpa_candidato.pdf)

## Estrutura atual

```text
.
├── main.py
├── src/
│   ├── web/
│   │   ├── buyer_scraper.py
│   │   └── sauce_demo.py
│   ├── repositories/
│   │   └── csv_repository.py
│   └── desktop/
│       └── fakturama.py
├── resources/
│   └── images/
│       └── fakturama/
├── tests/
├── spikes/
│   ├── README.md
│   └── poc.py
├── docs/
└── results/
```

- `src/`: implementação definitiva da automação.
- `resources/`: arquivos necessários em tempo de execução, como as âncoras visuais do Fakturama.
- `spikes/`: provas de conceito preservadas como histórico técnico; não são dependências do código de produção.
- `docs/`: documentação e imagens explicativas.
- `results/`: saída gerada em runtime e não versionada, exceto pelo `.gitkeep`.

## Status

🚧 **Em desenvolvimento**

Este `README.md` será evoluído ao longo da implementação e, ao final do projeto, será o principal documento de referência da solução, contendo:

- visão geral da arquitetura;
- requisitos e dependências;
- configuração do ambiente;
- instalação;
- execução da automação;
- estrutura do projeto;
- estratégia de logs e evidências;
- testes;
- limitações conhecidas;
- decisões técnicas;
- possíveis evoluções.

---

Desenvolvido como parte do processo seletivo técnico da BotCity.