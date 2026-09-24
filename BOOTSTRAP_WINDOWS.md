# BOOTSTRAP_WINDOWS.md — Preparação local

## O que precisa existir

Obrigatório:

- Maestri
- Claude Code CLI
- Codex CLI
- Git
- Python 3.11 ou mais recente

Opcional:

- OpenCode e Antigravity (usados como builders na equipe de agentes original; o Codex pode assumir esses papéis)
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

## Obter o repositório

```powershell
git clone https://github.com/jotape2709/aiops.git
cd aiops
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

As dependências estão em `requirements.txt`:

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

## Observação sobre dados

O laboratório usa somente dados sintéticos. O projeto foi especificado para não inspecionar a rede real da máquina, não executar scans e consultar apenas APIs públicas via GET.
