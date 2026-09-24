# TASKS.md — AIOps Network Operations Dashboard

## Status

- [x] Bootstrap do repositório
- [x] Ambiente virtual e dependências
- [x] Estrutura de módulos
- [x] Gerador de dados sintéticos
- [x] Modelo de topologia
- [x] MVP Streamlit executável
- [x] KPIs
- [x] Cenário normal
- [x] Cenário link degradado
- [x] Cenário link down
- [x] Cenário core switch down
- [x] Cenário CPU alta
- [x] Recovery
- [x] Incident engine
- [x] Root cause analysis
- [x] Topologia interativa
- [x] Gráfico de latência
- [x] Gráfico de throughput
- [x] Gráfico de severidade
- [x] Tabela de eventos
- [x] Tema visual NOC
- [x] Testes (79 passando, inclui smoke AppTest da UI)
- [x] Ruff
- [x] README
- [x] docs/architecture.md
- [x] docs/linkedin.md
- [x] QA final
- [x] Integração real: RIPE Atlas (probes BR/SP)
- [x] Integração real: RIPEstat (visibilidade BGP de ASNs institucionais BR)
- [x] Integração real: PeeringDB (IXPs e data centers BR/SP)

## Regra

Somente marque `[x]` após validar a entrega no repositório.

## Equipe e ownership (desde 2026-09-23)

- **OpenCode — Builder UI:** `app.py`, `src/ui/**` (layout, CSS, gráficos Plotly, topologia visual, mapas, estados vazios/erro).
- **Antigravity — Builder Core:** `src/models.py`, `src/config.py`, `src/synthetic_data.py`, `src/network_topology.py`, `src/incident_engine.py`, `src/root_cause.py`, `src/kpis.py`, `src/simulation_state.py`, `src/chart_data.py`, `src/event_data.py`, `src/services/**`, `src/integrations/**` e testes de domínio.
- **Codex — Integrator/fallback:** somente bugs complexos entre camadas.
- Só o Lead edita `TASKS.md` e `requirements.txt`. Sem push/deploy. Bloqueios humanos em `BLOCKERS.md`.

## Milestones

### M1 — MVP vertical ✅ concluído (2026-09-22, aprovado pelo QA após M1.1)

Aplicação inicia, mostra dados sintéticos, KPIs e topologia, e permite alternar entre cenário normal e falha crítica (core switch down).
Inclui fronteira vazia `src/integrations/` + `src/services/real_data_service.py` (sem HTTP).

### M2 — Features restantes do laboratório sintético

**M2a ✅ concluído (2026-09-23, aprovado pelo QA após M2a.1):** cenários link degradado, link down e CPU alta; correlação de incidentes; RCA determinística; Simular incidente / Restaurar ambiente com histórico preservado.
Premissas: impacto por ECMP (caminhos mínimos por saltos) + reroute + servidor degradado; latência média = fim a fim sobre serviços alcançáveis (N/D quando nenhum é alcançável).

**M2b ✅ concluído (2026-09-23):** gráficos de latência (SLO relativo ao baseline), utilização de links e incidentes por severidade; tabela de eventos; acabamento visual; selos SIMULAÇÃO NOC vs DADOS PÚBLICOS REAIS; contratos endurecidos (rótulos PT únicos, `UtilizationBand`, `topology_view` sem NetworkX na UI, `component_kind`, `truncated_reason`); última coleta boa do RIPE. Validado por revisão cruzada Antigravity↔OpenCode, gates, smoke AppTest e Portal 1366x768/1920x1080. Backlogs visuais do M1/M2a resolvidos aqui.

**M4 ✅ concluído (2026-09-23):** README.md, docs/architecture.md, docs/linkedin.md, assets/.gitkeep. QA final (Antigravity) aprovou todos os critérios da seção 17 e da seção 15; tabela de cenários do README conferida contra `compute_kpis` (seed 42).

**Pendências humanas (não bloqueiam o MVP):**
- ~~gerar screenshots em `assets/`~~ — 5 capturas geradas pelo Portal em 2026-09-24;
- reprodução em venv limpo não executada pelo Lead: o caminho temporário excede o limite de caminho do Windows (long paths desativado);
- publicação: M1–M4 publicados em `origin/main` (fa8ce68) em 2026-09-23;
- ~~escolher licença~~ — MIT (`LICENSE`), 2026-09-24.

Backlog herdado do QA do M1:
- símbolos de marcador por tipo de nó (seção 11);
- trocar de cenário não deve zerar `sample_index` (comparar Normal vs falha com a mesma base);
- rótulos da topologia cortados pelas linhas (fundo no texto ou deslocamento lateral);
- links entre nós inalcançáveis devem aparecer como "Impactado", não "Operacional";
- latência de nó inalcançável como N/D no tooltip, em vez de valor degradado;
- hover dos links só nas extremidades (limitação do Plotly; aceitável).

Backlog herdado do QA do M2a:
- card "Latência média" com N/D sem explicação;
- `event_id` por ocorrência; troca de seed com cenário ativo gera evento reaberto (tratar na tabela);
- severidade/timestamps dos eventos em PT; evento de recovery ao restaurar;
- cor de causa raiz na topologia sobrescreve a cor de estado; falta item "Causa raiz" na legenda;
- documentar premissa ECMP e nova latência fim a fim (Normal ~64 ms) no README/architecture.

### M3 — Primeira integração real: RIPE Atlas ✅ concluído (2026-09-23, aprovado pelo QA após M3.1/M3.2)

GET público em `/api/v2/probes/?country_code=BR` (urllib, timeout 10 s, até 6 páginas), recorte SP local (100 km).
Aba "Internet pública — RIPE Atlas (dados reais)" separada da simulação, com cache de 600 s, fallback e cooldown de atualização.
RIPEstat, PeeringDB e Anatel ficam para depois.

Backlog herdado do QA do M3:
- fallback UNAVAILABLE perde `reported_count`/`invalid_count` (irrelevante hoje);
- orçamento total de tempo da coleta (pior caso ~60 s com 6 páginas).

### M5 — Segunda integração real: PeeringDB ✅ concluído (2026-09-23)

GET público anônimo em `/api/ix?country=BR` e `/api/fac?country=BR` (máx. 2 requisições, 2 s entre elas), sem API key; contatos descartados no parse. 429 respeita `Retry-After` (sem retry automático; cooldown da UI = máx(60 s, Retry-After)); falha parcial explícita via `fetched_endpoints`; cache de 1 h sem cachear falha; regra SP por cidade normalizada (sufixo de UF ignorado) ou Haversine 100 km.
Validação: revisão cruzada Antigravity↔OpenCode, 128 testes, smoke AppTest com fetcher injetado, Portal (NOC/RIPE) e uma carga real controlada pelo Lead: 53 IXPs, 366 data centers (91 em SP), maior IXP IX.br São Paulo (1859 redes). A carga real revelou o bug `"São Paulo/SP"` fora de SP, corrigido e coberto por teste.
Screenshot `assets/peeringdb.png` gerado em 2026-09-24.

Backlog aberto (baixo, pós-MVP):
- coluna `incident_id` clicável ligando evento → incidente → RCA;
- severidade/confiança no painel de RCA;
- `compute_kpis` reaproveitar incidentes do estado;
- 0% quando não há probes ativas deveria ser "—".

### M6 — Terceira integração real: RIPEstat ✅ concluído (2026-09-24)

GET público em `stat.ripe.net/data/routing-status` (com `sourceapp`), um por ASN institucional: NIC.br AS22548, FAPESP/ANSP AS1251, RNP AS1916. Intervalo de 1 s, timeout 10 s, orçamento 20 s; erro de um ASN isolado em `failed_asns` (só 429/orçamento interrompem); estados OK/PARTIAL/UNAVAILABLE; cache no serviço (OK 900 s, PARTIAL 300 s, falha nunca), sem `st.cache_data` na UI; cooldown max(60 s, Retry-After). Quarta aba com KPIs, tabela por ASN e legenda neutra ("Sem anúncios observados" para 0%).
Validação: revisão cruzada Antigravity↔OpenCode (M6.1 corrigiu linguagem de erro, isolamento por ASN, retorno precoce da UI, seeing > total), 173 testes, Ruff, e carga real controlada pelo Lead. A carga real revelou que o AS26162 (route servers do IX.br) não anuncia rotas desde 2015 e parecia "0% — fora do ar"; foi trocado pelo AS1251. Numa das cargas o AS1251 não respondeu e a aba ficou PARTIAL com os outros 2 ASNs (isolamento funcionando); na repetição, os 3 vieram OK.
Screenshot `assets/ripestat.png` gerado em 2026-09-24.

Backlog do M6 (baixo):
- registrar em log o motivo da falha de cada ASN (hoje só entra em `failed_asns`);
- orçamento não reserva a duração da próxima requisição (pode passar até +10 s);
- datas da tabela RIPEstat em ISO cru (`2026-09-24T08:00:00`); formatar como no restante da UI;
- teto para `Retry-After` (vale também para o PeeringDB);
- `PARTIAL` latente nas abas Atlas/PeeringDB (`select_display_status`/`_load_*` só tratam OK/UNAVAILABLE; inalcançável hoje).
