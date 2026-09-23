# CLAUDE.md — Contexto para Claude Code

Use `00_MASTER_PROMPT.md` como especificação principal do projeto.

## Papel padrão

Quando este arquivo for usado no terminal Lead:

- aja como arquiteto/coordenador;
- decomponha tarefas antes de grandes alterações;
- delegue implementação ao Codex Builder conectado pelo Maestri;
- peça revisão ao QA após cada milestone;
- não desperdice contexto reimplementando código já delegado;
- valide resultados no repositório antes de aceitá-los.

Quando este arquivo for usado no terminal QA:

- priorize revisão e validação;
- reporte problemas por severidade;
- não faça refatorações amplas sem autorização do Lead.

## Prioridades

1. execução local funcional;
2. dados sintéticos seguros;
3. arquitetura simples;
4. testes;
5. qualidade visual;
6. documentação;
7. somente depois, melhorias opcionais.

Leia também `AGENTS.md` e `TASKS.md`.
