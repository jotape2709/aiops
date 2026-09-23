# BOOTSTRAP_WINDOWS.md — Preparação local

## O que precisa existir

Obrigatório:

- Maestri
- Claude Code CLI
- Codex CLI
- Git
- Python 3.11 ou mais recente

Opcional:

- VS Code
- GitHub CLI (`gh`)

Não é necessário instalar Docker, banco de dados, Node.js ou uma API de IA para este MVP, desde que Claude Code e Codex já estejam funcionando.

## Verificação

Abra PowerShell na pasta do projeto:

```powershell
claude --version
codex --version
git --version
python --version
```

Se `python` não responder, tente:

```powershell
py --version
```

## Criar repositório

```powershell
git init
```

## Ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se estiver usando `py`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Dependências do projeto

O agente Builder pode criar `requirements.txt`. Para bootstrap manual, o conjunto esperado é:

```text
streamlit
pandas
numpy
plotly
networkx
pytest
ruff
```

Depois:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Teste rápido dos agentes

Na raiz do projeto:

```powershell
claude
```

Feche após validar.

Depois:

```powershell
codex
```

Confirme que ambos conseguem abrir na pasta e enxergar os arquivos do projeto.

## Observação para notebook de trabalho

Use somente dados sintéticos e respeite as políticas de software da empresa. Este projeto foi especificado para não inspecionar a rede real, não executar scans e não usar dados internos.
