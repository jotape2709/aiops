# Post para LinkedIn

## Texto

Construí um laboratório de AIOps para operações de rede em cerca de dois dias, coordenando quatro agentes de IA no mesmo projeto. E aprendi mais sobre coordenação do que sobre código.

**O projeto — AIOps Network Operations Dashboard**

Um NOC local, 100% sintético e reproduzível por seed, com dados públicos reais da Internet brasileira em abas separadas:

🔹 Laboratório NOC: topologia interativa, KPIs, gráficos e 4 cenários de falha, com correlação de incidentes e causa raiz determinísticas (sem LLM, sem API paga). Com o core switch fora, a disponibilidade cai de 100% para 25% e o painel aponta o SW-CORE-01 como causa raiz.
🔹 RIPE Atlas: 471 sondas registradas no Brasil, 163 ativas (84,7% conectadas), 74 na região de São Paulo, em 89 ASNs distintos.
🔹 PeeringDB: 53 IXPs e 366 data centers no Brasil, 91 deles em SP. O maior IXP é o IX.br São Paulo, com 1.859 redes conectadas.
🔹 RIPEstat: visibilidade BGP pública de NIC.br, FAPESP/ANSP e RNP, com 269 prefixos IPv4 anunciados.

São 173 testes sem acesso à rede. As APIs públicas são consultadas só via GET, com timeout, cache e rate limit respeitado. Dado público nunca é apresentado como incidente de uma organização.

**A parte mais interessante: coordenar agentes com o Maestri**

No Maestri, cada agente roda num terminal de um canvas visual, e as conexões definem quem conversa com quem. A equipe:

• Claude Code como Lead/Arquiteto: planeja os milestones, escreve os briefs, valida os entregáveis e faz os commits.
• Antigravity como Builder Core: integrações, serviços e regras de domínio.
• OpenCode como Builder UI: interface e gráficos.
• Codex como Integrador: bugs entre camadas e plano B se um builder travar.

O que fez diferença:

1️⃣ Engenharia de prompt vira arquitetura. Um prompt mestre com a especificação, um arquivo de papel por terminal e uma tabela de ownership dizendo quem pode editar cada arquivo evitaram retrabalho e conflitos.
2️⃣ Contratos antes do código. O Lead define as dataclasses e os campos, e o Core e a UI trabalham em paralelo sobre eles.
3️⃣ Revisão cruzada entre agentes. O Core revisa a UI e vice-versa, e o Lead confere tudo rodando os testes antes de aceitar.
4️⃣ Validação com dados reais. Cargas reais pegaram o que os testes não pegavam: "São Paulo/SP" ficava fora de SP, e o ASN dos route servers do IX.br aparecia com "0%", parecendo fora do ar. Os dois casos foram corrigidos antes de publicar.
5️⃣ O navegador embutido no canvas (Portal) serviu para QA visual e gerou os screenshots do README.

A lição: com vários agentes, o gargalo deixa de ser escrever código. Passa a ser decompor bem o trabalho, definir contratos claros e verificar antes de aceitar.

Stack: Python, Streamlit, Plotly, Pandas, NetworkX e Pytest. Código aberto (MIT):
https://github.com/jotape2709/aiops

#AIOps #Observabilidade #NOC #Redes #Python #IA #AgentesDeIA #EngenhariaDePrompt

## Imagens sugeridas (ordem do carrossel)

1. `assets/maestri-canvas.png`: o canvas do Maestri com os 4 terminais e as conexões.
2. `assets/noc-core-down.png`: incidente simulado com a causa raiz.
3. `assets/noc-normal.png`: estado normal.
4. `assets/peeringdb.png`: IXPs e data centers.
5. `assets/ripestat.png`: visibilidade BGP por ASN.
6. `assets/ripe-atlas.png`: sondas no Brasil.

Números da carga real de 24/09/2026. Os dados públicos mudam com o tempo.
