# Post para LinkedIn (rascunho)

Operações de rede dependem de visibilidade rápida: quando um link degrada ou um switch central cai, a equipe precisa correlacionar alertas, encontrar a causa raiz e agir. Aprender e demonstrar esse fluxo, porém, costuma exigir acesso a infraestrutura real.

O **AIOps Network Operations Dashboard** resolve isso com um laboratório local de observabilidade,100% sintético e reproduzível por seed:

- 5 KPIs operacionais, topologia interativa e gráficos de latência, utilização e severidade;
- correlação determinística de incidentes e análise de causa raiz por regras (sem LLM, sem API paga);
- cenários de falha acionáveis (link degradado, link down, falha no core, CPU alta) com restauração e histórico de eventos.

A separação em camadas — interface em Streamlit sobre contratos tipados de um núcleo de domínio puro — mantém o núcleo testável sem rede. Uma aba dedicada consulta a API pública do RIPE Atlas (sondas reais no Brasil e em São Paulo) apenas como contexto de conectividade externa; nada ali indica falhas do laboratório.

Stack: Python 3.11+, Streamlit, Pandas, NumPy, Plotly, NetworkX e Pytest.

Conferir o repositório: <link>

#observabilidade #noc #aiops #streamlit #python
