# MAESTRI_SETUP.md — Quadro, agentes e conexões

# 1. Workspace

Crie um workspace no Maestri apontando para a pasta raiz:

```text
aiops-network-dashboard/
```

Ative a sincronização entre `CLAUDE.md` e `AGENTS.md` somente se você quiser que ambos recebam exatamente as mesmas instruções. Neste pacote eles são deliberadamente diferentes: `AGENTS.md` contém regras globais e `CLAUDE.md` acrescenta comportamento específico do Claude. Portanto, **não sincronize automaticamente estes dois arquivos inicialmente**.

# 2. Quadro recomendado

Use três terminais e duas notas.

```text
┌────────────────────────────┐
│ NOTA: SPEC / MASTER PROMPT │
│ 00_MASTER_PROMPT.md        │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ CLAUDE — LEAD / ARCHITECT  │
│ planeja, delega, aceita    │
└───────┬───────────┬────────┘
        │           │
        │           ▼
        │   ┌─────────────────────┐
        │   │ CLAUDE — QA/REVIEW  │
        │   │ testes + revisão    │
        │   └──────────┬──────────┘
        │              ▲
        ▼              │
┌────────────────────────────┐
│ CODEX — BUILDER            │
│ implementação + testes     │
└─────────────┬──────────────┘
              │
              ▼
     ┌──────────────────┐
     │ PORTAL            │
     │ localhost:8501    │
     └──────────────────┘

        [FILE TREE]
   raiz do repositório
```

# 3. Conexões

Crie estas conexões:

1. `MASTER PROMPT` → `Claude Lead`
2. `Claude Lead` ↔ `Codex Builder`
3. `Claude Lead` ↔ `Claude QA`
4. `Codex Builder` ↔ `Claude QA`
5. `Codex Builder` ↔ `Portal localhost:8501`
6. opcional: `Claude QA` ↔ `Portal localhost:8501`

Não é necessário ligar a árvore de arquivos; ela serve como visão do repositório.

# 4. Responsabilidades no Maestri

Em **Configurações → Agentes → Responsabilidades**, crie:

## LEAD

```text
Você é o Lead e Arquiteto deste projeto. Leia 00_MASTER_PROMPT.md, AGENTS.md, CLAUDE.md e TASKS.md. Planeje milestones pequenos, delegue implementação ao Codex Builder conectado e use o Claude QA para revisão. Verifique o repositório antes de aceitar entregas. Evite implementar diretamente aquilo que pode ser delegado. Preserve escopo, simplicidade, segurança e reprodutibilidade.
```

## BUILDER

```text
Você é o Builder. Implemente as tarefas delegadas pelo Lead no repositório atual. Leia 00_MASTER_PROMPT.md, AGENTS.md e TASKS.md. Escreva código funcional, testes e documentação relacionada. Execute testes e lint antes de reportar conclusão. Não amplie o escopo por conta própria. Quando terminar uma tarefa, informe ao Lead arquivos alterados, testes executados, resultados e pendências.
```

## QA

```text
Você é o QA/Reviewer. Revise o estado atual do projeto contra 00_MASTER_PROMPT.md, AGENTS.md e TASKS.md. Execute testes e valide funcionalidade. Procure bugs, regressões, inconsistências de UX, problemas de reprodutibilidade e violações de escopo. Reporte achados ao Lead em ordem de severidade. Não faça mudanças amplas sem autorização.
```

# 5. Agentes

- Terminal 1: **Claude Code**, responsabilidade `LEAD`
- Terminal 2: **Codex**, responsabilidade `BUILDER`
- Terminal 3: **Claude Code**, responsabilidade `QA`

Para economizar uso, o QA pode permanecer parado até o primeiro milestone.

# 6. Primeira mensagem

Envie somente ao **Claude Lead**:

```text
Leia @00_MASTER_PROMPT.md, AGENTS.md, CLAUDE.md e TASKS.md. Assuma a coordenação do projeto. Primeiro inspecione o repositório e valide o ambiente. Depois produza um plano curto para o primeiro milestone e delegue ao Codex Builder a implementação do MVP vertical. Não implemente o projeto inteiro sozinho. Quando o Builder terminar, peça ao QA para revisar. Priorize um MVP executável antes do polimento visual.
```

Depois disso, deixe o Lead coordenar os agentes usando as conexões.

# 7. Regra importante ao usar conexões

Quando um agente enviar uma tarefa a outro agente conectado, deixe o terminal receptor **sem foco/sem seleção** enquanto ele trabalha. O Maestri monitora terminais não selecionados para detectar quando a resposta terminou.

# 8. Portal

Depois que o Builder tiver o Streamlit rodando:

```powershell
streamlit run app.py
```

Abra no Portal:

```text
http://localhost:8501
```

Conecte o Portal ao Builder para permitir inspeção visual e, se desejado, também ao QA.

# 9. Organização visual do canvas

Recomendação:

- esquerda superior: Master Prompt;
- centro superior: Claude Lead;
- centro inferior: Codex Builder;
- direita superior: Claude QA;
- direita inferior: Portal;
- parte inferior/lateral: File Tree;
- nota `TASKS.md` próxima do Lead.

Isso deixa o fluxo visual:

```text
SPEC → LEAD → BUILD → PREVIEW
         ↘       ↗
           QA
```

# 10. Economia de tokens

- Use o Lead para coordenação, não para escrever tudo.
- Dê tarefas fechadas ao Builder.
- Acione QA apenas por milestone.
- Não peça aos três agentes para analisarem o mesmo arquivo ao mesmo tempo.
- Faça o Lead enviar referências de arquivos e critérios de aceite, não repetir toda a especificação em cada mensagem.
- Mantenha `TASKS.md` como estado compartilhado.
