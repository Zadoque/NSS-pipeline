# Backlog — Integração nacional do IBGE ao NSS Pipeline

Este backlog traduz a auditoria técnica em unidades implementáveis. As
prioridades são relativas: `P0` bloqueia a integração segura, `P1` é necessário
para expansão nacional, `P2` completa operação e histórico, e `P3` é evolução.

## Grafo de dependências

```text
IBGE-001 ──┬──> IBGE-002 ──> IBGE-003 ──> IBGE-006 ──> IBGE-009
           ├──> IBGE-004 ──> IBGE-007 ──> IBGE-009
           └──> IBGE-005 ──> IBGE-008 ──> IBGE-009
IBGE-003 ──> IBGE-010
IBGE-002 ──> IBGE-011
IBGE-006 + IBGE-007 + IBGE-008 ──> IBGE-012
IBGE-012 ──> IBGE-013
```

## Catálogo e identidade territorial

### IBGE-001 — Contrato e validação do catálogo nacional

- Prioridade: **P0**
- Estado: **Concluído**
- Dependências: nenhuma
- Escopo: entidades imutáveis, interface de catálogo, validação de códigos
  6/7 dígitos, unicidade, UF e metadados.
- Critérios de aceite:
  - `code7` e `code6` são strings e possuem formatos válidos.
  - A projeção `code6 → code7` é única.
  - Catálogo vazio, duplicado ou com UF divergente é rejeitado.
  - Resolução distingue `VALID`, `UNKNOWN_CODE`, `INVALID_FORMAT`,
    `UF_MISMATCH`, `HISTORICAL_UNRESOLVED` e `OUT_OF_SCOPE`.

### IBGE-002 — Aquisição DTB/API e release local

- Prioridade: **P0**
- Estado: **Concluído**
- Dependências: IBGE-001
- Escopo: download, cache bruto, Parquet, manifesto, SHA-256, hash lógico,
  `active.json` e promoção atômica.
- Critérios de aceite:
  - Falha de rede preserva a release ativa.
  - Candidata inválida não pode ser promovida.
  - O mesmo artefato gera o mesmo hash lógico independentemente da ordem.
  - Release ativa é imutável por `catalog_id` e SHA-256.

### IBGE-003 — Escopo geográfico explícito

- Prioridade: **P0**
- Estado: **Concluído**
- Dependências: IBGE-001
- Escopo: seleção por município, UF, Brasil e recorte RJ legado.
- Critérios de aceite:
  - `--municipios`, `--ufs` e `--all-brazil` são mutuamente exclusivos.
  - Ausência de seleção mantém os quatro municípios legados do RJ.
  - Escopo contém somente identidades materializadas pelo catálogo.
  - Hash do escopo é estável e registrado na publicação.

### IBGE-004 — SINAN Gold canônica

- Prioridade: **P0**
- Estado: **Concluído**
- Dependências: IBGE-001, IBGE-003
- Escopo: resolver códigos SINAN, canonicalizar UF/município e medir linhas
  inválidas, fora do escopo e divergentes.
- Critérios de aceite:
  - `330100` resolve para `3301009` pelo catálogo.
  - Código inválido não é corrigido por preenchimento arbitrário.
  - Nome e UF canônicos vêm do IBGE; campos de origem permanecem auditáveis.
  - Recorte RJ mantém resultados compatíveis, salvo divergência explicada.

### IBGE-005 — CNES com crosswalk e escopo canônico

- Prioridade: **P0**
- Estado: **Concluído no modo offline; piloto real executado**
- Dependências: IBGE-001, IBGE-003
- Escopo: código municipal de seis dígitos, sessão reutilizável, paginação,
  schema, timeout e geometrias opcionais.
- Critérios de aceite:
  - Consulta CNES usa o `code6` validado pelo catálogo.
  - Página com limite efetivo menor não salta registros.
  - Repetição de página interrompe o loop.
  - Checkpoint valida catálogo, escopo, parâmetros e checksum dos Bronzes.
  - Município sem malha recebe `UNAVAILABLE`, sem inferência territorial.

## Execução, publicação e atualização

### IBGE-006 — Orquestradores SINAN/CNES com a mesma release

- Prioridade: **P0**
- Estado: **Concluído**
- Dependências: IBGE-002, IBGE-003, IBGE-004, IBGE-005
- Escopo: `run.py`, `run_load.py`, `run_cnes.py` e argumentos de seleção.
- Critérios de aceite:
  - Uma execução resolve a release uma única vez.
  - SINAN e CNES recebem o mesmo catálogo e escopo.
  - Execução sem seleção continua regional por segurança.
  - Combinações geográficas ambíguas falham no parse da CLI.

### IBGE-007 — Linhagem PostgreSQL

- Prioridade: **P0**
- Estado: **Concluído no modo sintético multi-UF**
- Dependências: IBGE-002, IBGE-003, IBGE-004
- Escopo: tabela de releases, vínculo da publicação, hash do catálogo, tipo e
  hash do escopo, métricas de resolução.
- Critérios de aceite:
  - FK para a release é persistida na mesma transação da publicação.
  - Reuso de `catalog_id` com hash diferente é rejeitado.
  - Rollback não deixa fatos, dimensões ou metadados parciais.
  - Recortes sobrepostos não corrompem a identidade municipal.

### IBGE-008 — Reprocessamento orientado por versão territorial

- Prioridade: **P1**
- Estado: **Concluído**
- Dependências: IBGE-002, IBGE-006
- Escopo: manifesto do atualizador SINAN e identificação de mudança da
  release mesmo quando o tamanho remoto não muda.
- Critérios de aceite:
  - Mudança de `catalog_id` ou SHA força reprocessamento.
  - Rede indisponível usa somente release local aprovada.
  - Manifesto registra a identidade territorial utilizada.

## Qualidade e homologação

### IBGE-009 — Homologação CNES nacional real

- Prioridade: **P1**
- Estado: **Concluído; execução real nacional homologada**
- Dependências: IBGE-005, IBGE-006
- Escopo: execução autorizada para todos os municípios ou lotes nacionais,
  medição de taxa de erro, duração, limite da API e retomada.
- Critérios de aceite:
  - Todos os municípios selecionados têm resultado ou erro classificado.
  - Não há salto de paginação nem duplicação após retomada.
  - O lote e seus parâmetros ficam registrados no metadata.
  - A API não é consultada durante reprocessamento de Bronze já validado.
- Implementação adicional: `run_cnes(..., continue_on_error=True)` percorre o lote,
  registra falhas por município no checkpoint e publica o snapshot como `PARTIAL`;
  o comportamento estrito continua sendo o padrão.
- Implementação adicional: `--workers N` usa sessões HTTP independentes em
  janelas limitadas, fixa o parâmetro no checkpoint e mantém `N=1` como default.
- Evidência: execução real com a DTB 2025 cobriu 5.571/5.571 municípios,
  produziu 5.571 Bronzes e 641.343 estabelecimentos, com zero falhas e todas
  as linhas resolvidas como `VALID`.

### IBGE-010 — Fixtures e reconciliação epidemiológica nacional

- Prioridade: **P1**
- Estado: **Parcial; contrato sintético nacional validado, dados autorizados pendentes**
- Dependências: IBGE-004, IBGE-007
- Escopo: dados SINAN autorizados, Gold nacional e reconciliação Silver → Gold
  → PostgreSQL.
- Critérios de aceite:
  - Cada linha é classificada como resolvida, fora do escopo, inválida ou UF
    divergente.
  - Soma de casos elegíveis coincide com a expectativa independente.
  - Resultados são reproduzíveis com Silver, release IBGE e lote CNES fixos.
- Evidência local: fixture sintética com uma linha por cada um dos 5.571
  municípios passa pela Gold sem perdas; isso não substitui uma carga SINAN
  nacional real/autorizada.

### IBGE-011 — Histórico territorial explícito

- Prioridade: **P2**
- Estado: **Parcial; série DTB 2011–2025 processável, sucessões pendentes**
- Dependências: IBGE-002
- Escopo: eventos de criação, extinção, sucessão, desmembramento, fusão e
  alterações toponímicas provenientes de fonte explícita.
- Critérios de aceite:
  - Nenhuma sucessão é inferida por nome, prefixo ou proximidade.
  - Eventos possuem códigos, data de vigência, fonte e identificador estável.
  - A genealogia oficial 1872–2010 é preservada como fonte, mas não é tratada
    como crosswalk completo sem extração validada.
  - Uma fonte tabular oficial 2011–2025 pode ser promovida idempotentemente.
- Implementação atual: o parser lê formatos legados e recentes das edições
  anuais e deriva apenas eventos observáveis; criação/extinção entre códigos
  não é convertida automaticamente em sucessão.
- `promote_annual_dtb_events()` grava o Parquet histórico, manifesto com SHA-256
  de cada edição e a política `OBSERVABLE_ANNUAL_DIFF_ONLY` de forma idempotente.
- `write_events()` também valida a forma semântica de cada evento: criações,
  extinções, sucessões e mudanças toponímicas não podem declarar códigos de
  origem/destino incompatíveis.

### IBGE-012 — Mutação dos contratos críticos

- Prioridade: **P1**
- Estado: **Parcial; 63,9% classificável na última rodada global; refresh reclassificado**
- Dependências: IBGE-001 a IBGE-008
- Escopo: normalização, filtro, cache, promoção, checkpoint, linhagem e
  reprocessamento.
- Critérios de aceite:
  - Mutantes críticos de `code6 → code7`, UF, promoção e linhagem morrem.
  - Mutantes equivalentes são documentados individualmente.
  - Meta global de 95% é atingida sem reduzir artificialmente o escopo.
  - Integrações PostgreSQL são executadas em rodada separada.
  - Última rodada dirigida de `reference/ibge/refresh.py`: 167 mortos,
    167 sobreviventes e 119 sem testes associados; não substitui a medição
    global nem atende à meta de 95%.

### IBGE-013 — Rollout nacional de produção

- Prioridade: **P0 após os gates anteriores**
- Estado: **Bloqueado por gates externos, não por implementação local**
- Dependências: IBGE-009, IBGE-010, IBGE-011, IBGE-012
- Escopo: ativação por UF/lotes, observabilidade, reconciliação e runbook.
- Critérios de aceite:
  - Todas as UFs habilitadas passaram pelos critérios anteriores.
  - Release, escopo, lote CNES e métricas são consultáveis após a publicação.
  - Falhas de atualização não substituem a release ativa.
  - A execução nacional é repetível e auditável.

## Evidência

O estado de execução, commits, comandos e limitações estão registrados em
[`IBGE_INTEGRATION_EXECUTION.md`](IBGE_INTEGRATION_EXECUTION.md).
