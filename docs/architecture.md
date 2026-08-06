# Arquitetura do SMB Processor

O código é organizado por responsabilidade e mantém compatibilidade com os
projetos, scripts e imports anteriores.

```text
src/cebsm_preprocessor/
├── domain/             modelos e validações sem Qt
├── application/        casos de uso e coordenação dos fluxos
├── infrastructure/     NetCDF, SELAFIN, KML e processos externos
├── cli/                construção dos comandos dos motores científicos
├── ui/
│   ├── pages/          páginas independentes
│   ├── widgets/        componentes reutilizáveis
│   ├── map_widget.py   integração Leaflet
│   ├── main_window.py  composição e coordenação da aplicação
│   └── theme.py        sistema visual
├── core/               fachada de compatibilidade e motores já validados
└── assets/             imagens, mapa e ícones
```

## Direção das dependências

```text
UI → Application → Domain
UI → Infrastructure
Application → CLI / Domain
Infrastructure → implementações científicas validadas
```

O domínio não importa PySide6, leitores científicos ou componentes visuais.
Os serviços de aplicação não exibem diálogos nem acessam widgets. A interface
é responsável apenas pela entrada do usuário, apresentação e coordenação.

## Compatibilidade

O pacote permanece chamado `cebsm_preprocessor` nesta etapa para não invalidar
atalhos instalados e chamadas `python -m` existentes. Imports históricos como
`cebsm_preprocessor.core.project.Project` continuam válidos e apontam para o
modelo canônico em `domain.models.project`.

Arquivos e diretórios gerados (`projeto_cebsm.json`, `Matriz`, `Grade`,
`Contornos`, `Fronteiras`, `Configurações` e `Resultados`) não foram renomeados,
pois fazem parte do formato persistente e dos motores externos.

## Regras para novas funcionalidades

- Regras e modelos independentes entram em `domain`.
- Um fluxo iniciado pelo usuário entra em `application`.
- Leitura de formatos, subprocessos e bibliotecas externas entram em
  `infrastructure`.
- Scripts devem apenas interpretar argumentos e chamar serviços.
- Páginas Qt ficam em `ui/pages`; componentes repetidos ficam em `ui/widgets`.
- `main_window.py` deve apenas compor páginas, conectar ações e apresentar o
  estado geral.
