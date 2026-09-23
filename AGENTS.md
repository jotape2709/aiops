# AGENTS.md — Regras globais do repositório

## Contexto

Projeto: **AIOps Network Operations Dashboard**

Objetivo: construir um laboratório local de observabilidade de rede/NOC usando somente dados sintéticos.

Leia também `00_MASTER_PROMPT.md` e `TASKS.md` antes de alterar o projeto.

## Regras

- Não use dados reais de empresa.
- Não inspecione a rede real da máquina.
- Não execute scan de rede.
- Não use credenciais, tokens ou APIs pagas.
- O MVP deve funcionar offline após instalação das dependências.
- Use Python 3.11+, Streamlit, Pandas, NumPy, Plotly, NetworkX e Pytest.
- Mantenha a camada de domínio separada da UI.
- Use `st.session_state` para estado persistente entre reruns.
- Toda aleatoriedade relevante deve aceitar seed.
- Prefira funções puras para lógica de incidentes e RCA.
- Não adicione banco de dados, autenticação, Docker ou backend separado no MVP.
- Não adicione dependências sem necessidade clara.
- Execute testes antes de declarar uma tarefa concluída.
- Atualize `TASKS.md` apenas com fatos verificáveis.
- Não marque uma tarefa como concluída sem validar execução.

## Comandos esperados

```powershell
python -m pytest
ruff check .
streamlit run app.py
```

## Convenções

- Código e nomes internos podem permanecer em inglês.
- Interface, README principal e textos de demonstração devem ser em português.
- Type hints em APIs internas importantes.
- Docstrings somente onde agregarem contexto.
- Evite comentários que apenas repetem o código.
- Mantenha módulos pequenos e coesos.

## Definição de pronto

Uma feature está pronta quando:

1. funciona manualmente;
2. testes relevantes passam;
3. não quebra cenários existentes;
4. interface não apresenta traceback;
5. comportamento é reproduzível;
6. documentação necessária foi atualizada.
