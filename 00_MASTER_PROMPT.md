# MASTER PROMPT — AIOps Network Operations Dashboard

## 1. Missão

Construir um projeto de portfólio chamado **AIOps Network Operations Dashboard**: um dashboard local, executável e visualmente profissional para simular uma operação NOC/AIOps com **dados 100% sintéticos**.

O sistema deve demonstrar, de forma clara e publicável no GitHub/LinkedIn:

- monitoramento de infraestrutura e redes;
- observabilidade;
- geração de incidentes;
- análise de impacto;
- correlação de eventos;
- análise de causa raiz baseada em regras;
- topologia e dependências de rede;
- análise de dados;
- automação;
- boas práticas de engenharia de software.

Não usar dados, nomes, IPs, topologias, credenciais, arquivos ou informações internas de qualquer empresa real.

---

## 2. Papel dos agentes

Este projeto será desenvolvido em Maestri com Claude Code e Codex.

### Claude Lead / Arquiteto

Responsabilidades:

1. manter a visão do produto;
2. decompor o trabalho;
3. validar arquitetura;
4. definir contratos entre módulos;
5. revisar UX e coerência visual;
6. delegar implementação ao Codex;
7. revisar entregas antes de considerar uma etapa concluída;
8. impedir escopo desnecessário.

O Lead não deve reimplementar silenciosamente o trabalho do Builder. Quando encontrar problemas, deve explicar a correção necessária e delegar a implementação sempre que possível.

### Codex Builder / Engenheiro

Responsabilidades:

1. implementar código;
2. criar e manter testes;
3. executar o projeto;
4. corrigir erros;
5. manter dependências mínimas;
6. refatorar sem alterar requisitos;
7. reportar ao Lead o que foi alterado, testado e o que permanece pendente.

### Claude QA / Reviewer

Responsabilidades:

1. revisar código produzido pelo Builder;
2. procurar bugs, regressões e inconsistências;
3. executar testes;
4. revisar UX, textos e estados vazios/erro;
5. verificar se o projeto pode ser reproduzido a partir do README;
6. não alterar código por conta própria, exceto se o Lead pedir explicitamente;
7. enviar ao Lead uma lista curta e priorizada de problemas.

---

## 3. Regra de coordenação

Antes de implementar:

1. leia este arquivo;
2. leia `AGENTS.md` ou `CLAUDE.md`;
3. inspecione o repositório;
4. leia `TASKS.md`;
5. não assuma que uma tarefa está concluída sem verificar o código e os testes.

Quando houver agentes conectados no Maestri, o Lead deve delegar explicitamente tarefas ao Builder e pedir revisão ao QA.

Evite trabalho duplicado entre agentes.

Não crie frameworks internos desnecessários.

---

# 4. Produto

## Nome

**AIOps Network Operations Dashboard**

## Proposta

Simular uma pequena infraestrutura de rede corporativa/data center e apresentar, em tempo real simulado:

- disponibilidade;
- hosts;
- links;
- latência;
- jitter;
- packet loss;
- throughput;
- CPU;
- memória;
- incidentes;
- severidade;
- serviços afetados;
- dependências;
- provável causa raiz;
- ações recomendadas.

A aplicação deve funcionar totalmente offline depois que as dependências Python forem instaladas.

Nenhuma API de IA é obrigatória.

A “análise inteligente” da primeira versão deve ser produzida por um **motor determinístico de regras**, deixando um adaptador opcional para LLM futuro.

---

# 5. Stack obrigatória

Usar:

- Python 3.11+
- Streamlit
- Pandas
- NumPy
- Plotly
- NetworkX
- Pytest

Qualidade:

- Ruff para lint/format
- type hints nas funções públicas relevantes
- funções pequenas e testáveis
- separação entre geração de dados, regras, domínio e interface

Evitar dependências adicionais sem justificativa.

# Camada de dados públicos reais

Além do laboratório NOC sintético, o projeto deverá consumir
dados públicos reais da infraestrutura da Internet.

A primeira versão deverá integrar:

1. RIPE Atlas
2. RIPEstat
3. PeeringDB

Objetivo:

- consultar informações públicas reais;
- priorizar dados relacionados ao Brasil e São Paulo;
- permitir visualização separada da simulação NOC;
- demonstrar consumo, normalização e apresentação de APIs reais.

Os dados reais NÃO devem ser utilizados para afirmar que existe
um incidente interno em uma operadora.

A camada real representa apenas aquilo que a fonte pública
efetivamente disponibiliza.

As falhas, incidentes e análises de causa raiz do laboratório
continuam sendo explicitamente sintéticos.

## Arquitetura

Toda integração externa deve ficar em:

src/integrations/

Exemplos:

src/integrations/ripe_atlas.py
src/integrations/ripestat.py
src/integrations/peeringdb.py

A interface Streamlit não deve realizar chamadas HTTP diretamente.

As integrações devem ser consumidas por:

src/services/real_data_service.py

## Requisitos para chamadas externas

Toda requisição deve utilizar:

- timeout explícito;
- tratamento de HTTP errors;
- tratamento de timeout;
- validação mínima da resposta;
- cache;
- fallback visual em caso de indisponibilidade;
- mensagens amigáveis no dashboard.

Nunca deixar uma API externa derrubar toda a aplicação.

Usar somente operações GET em APIs públicas durante o MVP.

Não realizar scans de rede.

Não consultar interfaces ou infraestrutura local da máquina.

Não usar dados internos da empresa.

## Cache

Utilizar cache apropriado do Streamlit para evitar chamadas
desnecessárias às APIs.

Exemplo conceitual:

st.cache_data(ttl=300)

O período poderá variar de acordo com a fonte.

## Testes

Testes automatizados de integrações não devem depender
permanentemente da disponibilidade da API externa.

Usar mocks/respostas controladas nos testes de unidade.
---

# 6. Estrutura desejada

```text
aiops-network-dashboard/
├── app.py
├── requirements.txt
├── README.md
├── AGENTS.md
├── CLAUDE.md
├── TASKS.md
├── .gitignore
├── assets/
│   └── .gitkeep
├── docs/
│   ├── architecture.md
│   └── linkedin.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── synthetic_data.py
│   ├── network_topology.py
│   ├── incident_engine.py
│   ├── root_cause.py
│   └── ui/
│       ├── __init__.py
│       ├── theme.py
│       ├── cards.py
│       ├── charts.py
│       └── topology.py
└── tests/
    ├── test_synthetic_data.py
    ├── test_incident_engine.py
    └── test_root_cause.py
```

Pode ajustar levemente a estrutura se houver justificativa clara.

---

# 7. Modelo da infraestrutura simulada

Criar inicialmente uma topologia semelhante a:

```text
                    INTERNET
                       |
                    RTR-EDGE-01
                       |
                    FW-CORE-01
                       |
                 SW-CORE-01
                  /    |    \
                 /     |     \
          SW-ACCESS-01 |   SW-ACCESS-02
              |        |        |
          SRV-WEB-01  SRV-DB-01  SRV-API-01
              \        |        /
               \-------+-------/
                    SERVICES
```

Adicionar redundância suficiente para permitir demonstrar caminhos alternativos.

Tipos de nós:

- Internet/Cloud
- Router
- Firewall
- Core Switch
- Access Switch
- Server
- Service

Cada nó deve conter metadados sintéticos como:

- id;
- hostname;
- type;
- status;
- site;
- cpu;
- memory;
- latency;
- packet_loss;
- availability.

Links devem conter:

- source;
- target;
- status;
- utilization;
- latency;
- capacity_mbps.

---

# 8. Cenários simulados

Implementar pelo menos:

### Cenário normal
Infraestrutura operacional, pequenas oscilações.

### Link degradado
- aumento de latência;
- packet loss;
- warning;
- impacto parcial.

### Link down
- link indisponível;
- critical;
- recalcular alcance;
- detectar serviços impactados.

### Core switch down
- incidente crítico;
- múltiplos serviços impactados;
- causa raiz clara.

### CPU alta
- CPU > 90%;
- warning/critical conforme persistência;
- serviço degradado.

### Recovery
- restaurar ambiente;
- zerar incidentes ativos;
- manter ou reiniciar histórico conforme decisão documentada.

---

# 9. Dashboard

## Layout

### Sidebar
- logo/nome do projeto;
- seletor de cenário;
- controles da simulação;
- seed;
- botão `Gerar nova amostra`;
- botão `Simular incidente`;
- botão `Restaurar ambiente`.

### Header
Título:

`AIOps Network Operations Center`

Subtítulo:

`Laboratório de observabilidade e análise de incidentes com dados 100% sintéticos`

### Linha 1 — KPIs

Cards:

1. Disponibilidade
2. Alertas ativos
3. Incidentes críticos
4. Serviços impactados
5. Latência média

### Linha 2

Esquerda:
- Topologia interativa.

Direita:
- Análise inteligente / provável causa raiz.

### Linha 3

- Latência ao longo do tempo
- Throughput/Utilização
- Incidentes por severidade

### Linha 4

Tabela de eventos recentes.

Campos:

- timestamp;
- host;
- categoria;
- severidade;
- status;
- descrição;
- serviço afetado.

---

# 10. Direção visual

Criar um visual de NOC moderno, inspirado em dashboards corporativos escuros, sem copiar nenhum produto específico.

Características:

- fundo azul-marinho quase preto;
- superfícies em tons de navy/slate;
- roxo e ciano como destaque primário;
- vermelho/laranja somente para incidentes;
- verde para estado saudável;
- bordas discretas;
- cards compactos;
- tipografia legível;
- pouco ruído visual;
- hierarquia forte;
- gráficos limpos;
- alto contraste;
- aparência adequada para screenshot no LinkedIn.

Não usar imagens externas obrigatórias.

Não depender de fontes remotas.

Não criar um dashboard “genérico de vendas”.

A estética deve comunicar imediatamente:

**rede + NOC + observabilidade + operações.**

---

# 11. Topologia

Usar NetworkX para modelo e Plotly para renderização.

Requisitos:

- posição estável dos nós;
- cores/ícones visuais por tipo/estado;
- links normais, degradados e down visualmente distinguíveis;
- tooltip com métricas;
- destacar a provável causa raiz;
- destacar nós/serviços impactados;
- evitar reposicionamento aleatório da rede a cada rerun do Streamlit.

A lógica da topologia deve estar separada da UI.

---

# 12. Motor de incidentes

Criar regras determinísticas.

Exemplo inicial:

```text
packet_loss >= 10%      -> CRITICAL
packet_loss >= 3%       -> WARNING

latency >= 150 ms       -> CRITICAL
latency >= 80 ms        -> WARNING

cpu >= 95%              -> CRITICAL
cpu >= 85%              -> WARNING

memory >= 95%           -> CRITICAL
memory >= 85%           -> WARNING

link_status == DOWN     -> CRITICAL
device_status == DOWN   -> CRITICAL
```

Evitar múltiplos alertas redundantes para a mesma causa.

Adicionar IDs determinísticos para incidentes quando possível.

---

# 13. Root Cause Analysis

A análise deve ser calculada a partir de:

- topologia;
- estado dos nós;
- estado dos links;
- métricas;
- dependências;
- serviços inacessíveis.

Formato esperado:

```text
CAUSA RAIZ PROVÁVEL
SW-CORE-01 indisponível.

EVIDÊNCIAS
• 3 serviços perderam conectividade.
• Links dependentes tornaram-se inacessíveis.
• O evento ocorreu antes dos alertas nos servidores.

IMPACTO
• API: indisponível
• Web: indisponível
• Database: degradado

AÇÃO RECOMENDADA
1. Validar alimentação e estado do equipamento.
2. Verificar uplinks.
3. Confirmar failover.
4. Restaurar conectividade antes de atuar nos sintomas.
```

As recomendações devem ser genéricas e próprias de laboratório.

Não inventar comandos destrutivos.

---

# 14. Estado e reprodutibilidade

Usar `st.session_state` corretamente.

A aplicação deve:

- manter cenário durante reruns;
- permitir seed configurável;
- não regenerar todo o dataset inesperadamente;
- permitir reset explícito;
- produzir comportamento reproduzível com a mesma seed.

---

# 15. Segurança e privacidade

Obrigatório:

- dados exclusivamente sintéticos;
- IPs apenas das faixas reservadas para documentação/laboratório;
- nenhuma credencial hardcoded;
- nenhum token;
- nenhum dado de empregador;
- nenhum hostname real;
- nenhum nome de cliente;
- nenhum endpoint corporativo;
- nenhuma coleta de rede real.

Não executar scan de rede.

Não chamar ferramentas como nmap.

Não ler configurações da rede da máquina.

---

# 16. Qualidade

Antes de concluir:

```text
python -m pytest
ruff check .
```

A aplicação deve iniciar com:

```text
streamlit run app.py
```

O README precisa explicar:

1. objetivo;
2. arquitetura;
3. instalação;
4. execução;
5. cenários;
6. que todos os dados são sintéticos;
7. screenshots — deixar seção preparada;
8. roadmap.

---

# 17. Critérios de aceite

O MVP só é considerado concluído quando:

- [ ] inicia sem erro;
- [ ] dashboard é utilizável em 1366x768 e 1920x1080;
- [ ] existe topologia;
- [ ] existem ao menos 5 KPIs;
- [ ] existem ao menos 3 visualizações temporais/categóricas;
- [ ] existe tabela de eventos;
- [ ] cenários alteram métricas e topologia;
- [ ] existe análise de causa raiz;
- [ ] existe recovery;
- [ ] dados são 100% sintéticos;
- [ ] testes passam;
- [ ] lint passa;
- [ ] README permite reprodução;
- [ ] nenhuma API paga é necessária.

---

# 18. Fluxo de execução dos agentes

## Fase 1 — Planejamento

Lead:

1. inspecione arquivos;
2. valide arquitetura;
3. atualize `TASKS.md`;
4. delegue ao Builder um MVP vertical executável.

## Fase 2 — Vertical slice

Builder deve entregar primeiro:

- app executável;
- dados sintéticos;
- KPIs;
- uma topologia;
- um cenário normal;
- um cenário crítico.

Não começar refinamentos visuais avançados antes disso funcionar.

## Fase 3 — Features

Implementar:

- gráficos;
- incident engine;
- RCA;
- recovery;
- event table.

## Fase 4 — Visual

Aprimorar:

- layout;
- CSS;
- espaçamento;
- cards;
- responsividade;
- estados visuais.

## Fase 5 — QA

QA:

- rodar testes;
- validar cenários;
- verificar README;
- testar resolução;
- procurar inconsistências.

## Fase 6 — Correções

Lead prioriza os achados.

Builder corrige.

QA revalida.

---

# 19. Política de mudanças

Ao modificar o projeto:

1. faça alterações pequenas e verificáveis;
2. rode testes relacionados;
3. não remova funcionalidade sem justificativa;
4. não substitua arquitetura funcional por abstrações especulativas;
5. não adicione banco de dados ao MVP;
6. não adicione autenticação ao MVP;
7. não adicione backend separado ao MVP;
8. não adicione Docker ao MVP, salvo pedido posterior;
9. não integre LLM externo no MVP.

---

# 20. Entrega final

Entregar:

- código;
- testes;
- README;
- `docs/architecture.md`;
- `docs/linkedin.md`;
- instruções para gerar screenshots;
- lista curta de possíveis V2.

A V2 pode incluir:

- adaptador opcional de LLM;
- histórico persistente;
- detecção estatística/ML;
- comparação entre regras e ML;
- SLA/SLO;
- replay de incidentes;
- exportação de relatório.

Prioridade absoluta: **um MVP local, visual, funcional, reproduzível e demonstrável.**
