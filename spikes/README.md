# Spikes técnicos

Esta pasta preserva experimentos e provas de conceito realizados durante a
evolução do desafio.

## `poc.py`

POC usada para validar a viabilidade técnica do fluxo ponta a ponta:

- coleta do comprador no Fake Name Generator;
- login e scraping do Sauce Demo;
- automação desktop do Fakturama por reconhecimento de imagem.

O arquivo é mantido como histórico técnico e referência da evolução da solução.
O código de produção em `src/` não importa nem depende de módulos desta pasta.

As imagens utilizadas pelo Fakturama foram centralizadas em
`resources/images/fakturama/`, evitando duplicação entre a POC e a implementação
definitiva.
