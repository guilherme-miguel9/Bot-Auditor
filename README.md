# Auditoria de Registros Operacionais — Sistema de Validação

A **Auditoria de Registros Operacionais** é uma solução inteligente e automatizada para validação e auditoria operacional de justificativas registradas por leituristas em coletores de dados. O sistema analisa instantaneamente dezenas de milhares de registros, aplicando regras operacionais de negócio de alta precisão para identificar não conformidades, erros de digitação e desvios de processo no campo.

---

## 🚀 Funcionalidades e Classificações de Auditoria

O motor de validação processa cada linha da planilha de auditoria (Excel ou CSV) e categoriza o comentário na coluna **`ANÁLISE`** em uma das 8 classificações operacionais:

| Sigla | Classificação | Critério e Descrição |
| :---: | :--- | :--- |
| **C** | **CONFORME** | O comentário atende plenamente aos critérios numéricos e textuais exigidos pela nota de leitura. |
| **SC** | **SEM COMENTÁRIO** | A nota exige justificativa/informação obrigatória, mas o comentário foi deixado em branco. |
| **UCE** | **USO DE CARACTERE ESPECIAL** | O comentário contém caracteres especiais proibidos (`*`, `.`, `;`, `_`, `-`, `#`, `/`, `@`, etc.). |
| **EE** | **EXCESSO DE ESPAÇO** | O comentário apresenta 3 ou mais espaços consecutivos no texto (ex: `'   '`). |
| **FL** | **FALTA A LEITURA** | A nota exige leitura operacional junto ao medidor ou função, mas apenas 1 número foi informado. |
| **CFP** | **COMENTÁRIO FORA DO PADRÃO** | Presença de letras não permitidas em notas numéricas, excesso de dados ou uso indevido de `03` no início de `T181`/`R111`. |
| **CI** | **COMENTÁRIO INCORRETO** | O formato informado não atende ao exigido pela nota (ex: numeração de poste fora do padrão `M000000`/`S000000`/`X000`). |
| **NI** | **NOTA INCORRETA** | O comentário não condiz com a nota gerada no coletor (ex: texto explicativo sem números em notas de medidor/leitura). |

> *Nota `L121` (Campanha 1):* O robô ignora automaticamente todas as linhas sob a nota `L121`, preservando integralmente qualquer auditoria prévia nas células originais da planilha.

---

## ⚡ Diferenciais Técnicos e Regras Avançadas

* **Múltiplos Pares de Códigos e Leituras:** As notas de medidor/leitura (`P111`, `B111`, `T181`, `R111`, etc.) aceitam que 1 ou 2 medidores sejam acompanhados por múltiplos pares compostos pelo código/função de ocorrência (até 3 dígitos) e a respectiva leitura (até 6 dígitos), ex: `3203600940 3 012051 24 001929` ou `6252237400 03 999999 103 999999`.
* **Prefixos `S`, `M`, `X`, `MV`, `NF` em Medidores e Postes:** Letras prefixadas a numerações operacionais fazem parte da nomenclatura oficial e são perfeitamente aceitas sem disparar erros de padrão (`CFP`). Postes em notas como `E101` aceitam tanto os formatos `M` e `X` quanto o formato **`S + 6 dígitos`** (ex: `s138628`).
* **Reconhecimento de Menção a Outras Notas:** Quando o técnico referencia outra nota operacional dentro do comentário (código no formato `[A-Z] + 3 dígitos`, como `T111`, `T181`, `P111`), o sistema reconhece o código da nota e não o penaliza como letra proibida.
* **Tokens Operacionais (`S`, `SELO`, `ZELO`, `NR DI`, `NR RE`, `R`, `NR IM`):** Permitidos em qualquer nota sem gerar `CFP`. Podem aparecer isolados apenas em notas puramente textuais (`L131`, `T171`, `P191`).
* **Prefixos e Funções Específicas:** Códigos como `103` e `55` (+ até 6 dígitos) são aceitos em todas as notas. A leitura `03` é aceita em `P111`, `B111` e demais notas, sendo restrita como código inicial isolado apenas em `T181` e `R111`.

---

## 🖥️ Painel Desktop (GUI com PySide6 & Dark Navy Blue)

O projeto conta com uma interface gráfica desktop interativa e moderna (`main.py`), construída com **PySide6 (Qt6)**, apresentando um layout estilo *Dark Navy Blue & Glassmorphism* (cards elevados, navegação em barra lateral e indicadores instantâneos de status).

### Principais recursos da interface:
1. **Seleção Simplificada:** Suporte nativo a arquivos Excel (`.xlsx`, `.xlsm` com macros, `.xls`) e `.csv`.
2. **Processamento em Thread Qt Dedicada (`ValidationWorker`):** Execução de auditorias complexas sobre mais de 100 mil linhas no fundo sem travar a interface visual.
3. **Barra de Progresso e Métricas ao Vivo:** Exibição imediata da distribuição de todos os indicadores com *badges* coloridos e tempo de execução.
4. **Gravação Automática:** Salva a planilha validada (`_VALIDADO.xlsx`) na mesma pasta do arquivo de origem.
5. **Abertura Cross-Platform em 1 Clique:** Botão para abrir o arquivo Excel validado ou pasta no Finder (macOS) / Explorer (Windows) via `QDesktopServices`.

---

## 📦 Executável Standalone (macOS / Linux / Windows)

Para utilizar o sistema em computadores sem necessidade de instalar Python ou qualquer biblioteca, o projeto compila todas as dependências em um arquivo executável portátil via PyInstaller.

O arquivo executável compilado fica disponível na pasta `dist/`:
- **macOS / Linux:** `dist/Auditoria_Registros_Operacionais`
- **Windows:** `dist/Auditoria_Registros_Operacionais.exe`

---

## 🛠️ Estrutura do Projeto

```
auditoria-registros-operacionais/
├── main.py                  # Painel Desktop Interativo (PySide6 GUI)
├── assets/
│   └── app_icon.ico         # Ícone oficial do aplicativo
├── requirements.txt         # Dependências Python do projeto (PySide6, pandas, openpyxl, etc.)
├── README.md                # Documentação do sistema
├── README_VALIDACAO.md      # Manual detalhado e especificações técnicas de todas as notas
├── walkthrough.md           # Histórico de execuções e métricas validadas
├── src/
│   ├── validation_rules.py    # Motor com todas as regras operacionais de negócio e testes unitários
│   └── validar_comentarios.py # Script CLI principal para auditoria em lote e manipulação de DataFrames
└── dist/
    └── Auditoria_Registros_Operacionais  # Aplicativo executável autônomo compilado
```

---

## 💻 Como Executar via Código Python

### 1. Requisitos
Certifique-se de ter o Python 3.10+ instalado e instale as dependências:
```bash
pip install -r requirements.txt
```

### 2. Executar o Painel Desktop GUI
```bash
python main.py
```

### 3. Executar via Linha de Comando (CLI)
Para executar a auditoria diretamente pelo terminal sem abrir a interface gráfica:
```bash
python src/validar_comentarios.py --input "caminho/para/planilha.xlsm" --output "caminho/para/saida_VALIDADA.xlsx" --sheet "Aud_Coment_Geral" --analyze
```

### 4. Compilar Executável com PyInstaller (Cross-Platform)

O PyInstaller gera um executável autônomo específico para a plataforma em que o comando é executado. Utilize o comando correspondente ao seu sistema operacional:

#### 🍏 macOS
```bash
python3 -m PyInstaller --noconsole --onefile --icon=assets/app_icon.ico --name=Auditoria_Registros_Operacionais --add-data "src:src" --add-data "assets:assets" main.py
```
*Gerado em `dist/Auditoria_Registros_Operacionais`.*

#### 🐧 Linux
```bash
python3 -m PyInstaller --noconsole --onefile --icon=assets/app_icon.ico --name=Auditoria_Registros_Operacionais --add-data "src:src" --add-data "assets:assets" main.py
```
*Gerado em `dist/Auditoria_Registros_Operacionais`.*

#### 🪟 Windows (PowerShell ou CMD)
```cmd
python -m PyInstaller --noconsole --onefile --icon=assets\app_icon.ico --name=Auditoria_Registros_Operacionais --add-data "src;src" --add-data "assets;assets" main.py
```
*(Nota: No Windows, a flag `--add-data` utiliza o ponto e vírgula `;` como separador de caminho, ao invés de dois pontos `:`).*
*Gerado em `dist/Auditoria_Registros_Operacionais.exe`.*
