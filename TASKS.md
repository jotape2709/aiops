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
- [ ] Testes (parcial: 10 testes do M1 passando)
- [x] Ruff
- [ ] README
- [ ] docs/architecture.md
- [ ] docs/linkedin.md
- [ ] QA final

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

### M3 — Primeira integração real: RIPE Atlas

Somente após M1 validado. RIPEstat, PeeringDB e Anatel ficam para depois.
