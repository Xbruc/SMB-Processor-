# SMB Processor — Pré-processamento Hidrodinâmico com TELEMAC-MASCARET

## Objetivo do Projeto

O **SMB Processor** é uma aplicação desktop desenvolvida para organizar e automatizar
etapas do pré-processamento de modelos hidrodinâmicos da Baía de São Marcos (MA), com
integração ao TELEMAC-MASCARET.

A aplicação reúne, em uma interface gráfica, ferramentas para criação de projetos,
organização dos dados de entrada, definição do domínio, geração de malha, configuração
das condições de contorno e preparação das séries temporais utilizadas nas simulações.

O projeto busca tornar o fluxo de modelagem mais organizado, reproduzível e acessível,
reduzindo tarefas manuais e facilitando a conferência dos arquivos produzidos para
estudos costeiros, ambientais, portuários e oceanográficos.

---

## Tecnologias Utilizadas

### Linguagens

- Python 3.11 ou superior;
- JavaScript, HTML e CSS para o mapa interativo incorporado.

### Bibliotecas e Ferramentas

- PySide6;
- NumPy;
- Pandas;
- SciPy;
- Matplotlib;
- Plotly;
- Gmsh;
- netCDF4;
- PyProj;
- Shapely;
- Leaflet;
- Leaflet Draw;
- imageio-ffmpeg;
- TELEMAC-MASCARET.

### Dados e Formatos Utilizados

- Batimetria GEBCO em NetCDF;
- dados de maré e vazão;
- dados de ADCP e levantamentos oceanográficos;
- arquivos KML e KMZ;
- arquivos SELAFIN (`.slf`);
- arquivos de condições de contorno (`.cli`);
- arquivos de séries temporais (`.prn` e `.csv`);
- arquivos de projeto em JSON.

---

## Estrutura do Projeto

```text
SMB_Preprocessor/
├── docs/                         # Documentação técnica e arquitetura
├── src/
│   └── smb_preprocessor/
│       ├── application/          # Serviços e fluxos da aplicação
│       ├── assets/               # Imagens, ícones e arquivos do mapa
│       ├── cli/                  # Comandos de linha de comando
│       ├── core/                 # Processamento e regras legadas
│       ├── domain/               # Modelos e validações de domínio
│       ├── infrastructure/       # Arquivos, processos e geoprocessamento
│       └── ui/                   # Interface gráfica e páginas
├── tests/                        # Testes automatizados
├── iniciar.bat                   # Inicializador da aplicação no Windows
├── pyproject.toml                # Configuração e dependências do projeto
└── README.md
```

Ao criar um projeto pela interface, a aplicação gera a seguinte estrutura de trabalho:

```text
Nome_do_Projeto/
├── projeto_cebsm.json            # Configurações do projeto
├── Matriz/                       # Dados brutos e fontes oceanográficas
├── Grade/                        # Malhas, SELAFIN e figuras de batimetria
├── Contornos/                    # CLI, JSON e nós de contorno
└── Fronteiras/                   # Séries PRN, CSV e gráficos
```

---

## Funcionalidades

- Criação, abertura e salvamento de projetos;
- organização automática dos diretórios de trabalho;
- importação de dados oceanográficos e batimétricos;
- visualização de mapas OpenStreetMap e Esri;
- desenho do domínio e de regiões de refinamento no mapa;
- importação e exportação de geometrias KML e KMZ;
- geração de malha uniforme ou com refinamento localizado;
- integração com Gmsh e dados batimétricos GEBCO;
- visualização da grade e da batimetria;
- exportação dos nós de contorno para configuração interativa;
- edição e validação das condições de contorno;
- configuração de fronteiras oceânicas e fluviais;
- geração de arquivos CLI, PRN e CSV;
- criação de gráficos das séries temporais;
- validação dos arquivos necessários para o TELEMAC-MASCARET;
- acompanhamento de processos longos pela interface.

---

## Como Executar

### 1. Clone o repositório

```bash
git clone <URL_DO_REPOSITORIO>
```

### 2. Entre na pasta do projeto

```bash
cd SMB_Preprocessor
```

### 3. Crie e ative um ambiente virtual

No Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 4. Instale as dependências

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

### 5. Inicie a aplicação

Clique duas vezes no arquivo `iniciar.bat` ou execute:

```powershell
.\iniciar.bat
```

Também é possível iniciar pelo comando instalado:

```powershell
smb-processor
```

---

## Fluxo Básico de Utilização

1. Abra a aplicação e crie um novo projeto;
2. escolha a pasta do projeto e informe o diretório dos motores de processamento;
3. importe os dados GEBCO, TPXO, ADCP, marégrafo, vazão e demais fontes;
4. desenhe o domínio no mapa ou carregue um arquivo KML/KMZ;
5. configure os parâmetros e gere a grade computacional;
6. defina e valide as condições de contorno;
7. prepare as séries temporais de maré e vazão;
8. confira os arquivos gerados no módulo de validação;
9. utilize os arquivos preparados na configuração do TELEMAC-MASCARET.

---

## Executando os Testes

Com o ambiente configurado, execute:

```powershell
python -m pytest -q
```

Os testes verificam componentes centrais do projeto, incluindo leitura de dados,
geometrias, validações, modelos e separação das camadas da aplicação.

---

## Resultados Esperados

A aplicação permite produzir e organizar os principais arquivos de entrada necessários
ao fluxo de modelagem hidrodinâmica, incluindo:

- domínio computacional e regiões de refinamento;
- malha numérica com batimetria interpolada;
- arquivos SELAFIN e CLI;
- condições de contorno oceânicas e fluviais;
- séries temporais de nível e vazão;
- mapas, figuras e gráficos para conferência;
- estrutura de projeto reproduzível em JSON.

Esses resultados fornecem a base para configurar e executar simulações da circulação,
propagação da maré, níveis d'água e influência das vazões fluviais na Baía de São Marcos.

---

## O que foi Aprendido com a Experiência

Durante o desenvolvimento deste projeto foram consolidados conhecimentos em:

- desenvolvimento de aplicações desktop com PySide6;
- modelagem hidrodinâmica com TELEMAC-MASCARET;
- geração e validação de malhas computacionais;
- processamento de dados NetCDF e SELAFIN;
- definição de condições de contorno oceânicas e fluviais;
- integração de mapas interativos em aplicações Python;
- processamento e conversão de dados geoespaciais;
- automação de rotinas científicas em Python;
- organização de software em camadas de domínio, aplicação e infraestrutura;
- criação de testes automatizados;
- diagnóstico e solução de problemas em fluxos de modelagem numérica;
- documentação técnica e organização de projetos com Git e GitHub.

Além do aprendizado técnico, o projeto contribuiu para o desenvolvimento de habilidades
relacionadas à resolução de problemas, análise crítica, arquitetura de software e
integração entre programação, oceanografia, geoprocessamento e modelagem numérica.

---

## Autor

**Wesley Lima**

Oceanógrafo | Desenvolvedor Back-end | Modelagem Numérica Costeira

- Python
- TELEMAC-MASCARET
- Geoprocessamento
- Modelagem Hidrodinâmica
