# TASKS.md — AIOps Network Operations Dashboard

## Status

- [ ] Bootstrap do repositório (estrutura pronta; sem commit inicial)
- [x] Ambiente virtual e dependências
- [x] Estrutura de módulos
- [x] Gerador de dados sintéticos
- [x] Modelo de topologia
- [x] MVP Streamlit executável
- [x] KPIs
- [x] Cenário normal
- [ ] Cenário link degradado
- [ ] Cenário link down
- [x] Cenário core switch down
- [ ] Cenário CPU alta
- [ ] Recovery
- [ ] Incident engine (parcial: thresholds + supressão de sintomas; sem correlação/RCA)
- [ ] Root cause analysis
- [ ] Topologia interativa
- [ ] Gráfico de latência
- [ ] Gráfico de throughput
- [ ] Gráfico de severidade
- [ ] Tabela de eventos
- [ ] Tema visual NOC
- [ ] Testes (parcial: 21 testes passando — M1 + RIPE Atlas)
- [x] Ruff
- [ ] README
- [ ] docs/architecture.md
- [ ] docs/linkedin.md
- [ ] QA final
- [x] Integração real: RIPE Atlas (probes BR/SP)
- [ ] Integração real: RIPEstat
- [ ] Integração real: PeeringDB

## Regra

Somente marque `[x]` após validar a entrega no repositório.

## Milestones

### M1 — MVP vertical ✅ concluído (2026-09-22, aprovado pelo QA após M1.1)

Aplicação inicia, mostra dados sintéticos, KPIs e topologia, e permite alternar entre cenário normal e falha crítica (core switch down).
Inclui fronteira vazia `src/integrations/` + `src/services/real_data_service.py` (sem HTTP).

### M2 — Features restantes do laboratório sintético

Demais cenários, RCA, recovery, gráficos, tabela de eventos.

Backlog herdado do QA do M1:
- símbolos de marcador por tipo de nó (seção 11);
- trocar de cenário não deve zerar `sample_index` (comparar Normal vs falha com a mesma base);
- rótulos da topologia cortados pelas linhas (fundo no texto ou deslocamento lateral);
- links entre nós inalcançáveis devem aparecer como "Impactado", não "Operacional";
- latência de nó inalcançável como N/D no tooltip, em vez de valor degradado;
- hover dos links só nas extremidades (limitação do Plotly; aceitável).

### M3 — Primeira integração real: RIPE Atlas ✅ concluído (2026-09-23, aprovado pelo QA após M3.1/M3.2)

GET público em `/api/v2/probes/?country_code=BR` (urllib, timeout 10 s, até 6 páginas), recorte SP local (100 km).
Aba "Internet pública — RIPE Atlas (dados reais)" separada da simulação, com cache de 600 s, fallback e cooldown de atualização.
RIPEstat, PeeringDB e Anatel ficam para depois.

Backlog herdado do QA do M3:
- fallback UNAVAILABLE perde `reported_count`/`invalid_count` (irrelevante hoje);
- orçamento total de tempo da coleta (pior caso ~60 s com 6 páginas).
