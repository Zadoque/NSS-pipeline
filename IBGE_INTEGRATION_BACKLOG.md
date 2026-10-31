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
  - O manifesto da release registra `promoted_at`; manifests legados sem esse
    campo continuam legíveis para preservar compatibilidade.

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
- Releases que possuem `ufs.parquet` e `code_crosswalk.parquet` agora validam
  esses artefatos contra `municipalities.parquet` no carregamento; divergências
  de esquema ou conteúdo são rejeitadas. Releases legadas sem os auxiliares
  continuam legíveis por compatibilidade.
- A promoção também rejeita releases parcialmente materializadas: se um
  auxiliar estiver presente, o par correspondente precisa existir e ser
  consistente antes da troca de `active.json`.

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
- Evidência adicional: `72b4774` rejeita algarismos Unicode no hash do escopo e
  cobre exatamente os contratos de seleção por UF, Brasil inteiro e município
  inválido.
- Evidência adicional: `d7439d4` garante que falhas na troca atômica do ZIP DTB
  não deixam temporários no cache bruto; a suíte posterior passou em 496 testes.
- Evidência adicional: `ebe81fd` cobre o esquema oficial 2025 de alterações
  toponímicas com colunas extras; a suíte posterior passou em 497 testes.
- Evidência adicional: `47a5050` cobre a fronteira de 5.500 municípios e mata
  os mutantes de comparação e mensagem dessa validação; a suíte posterior passou
  em 498 testes.
- Evidência adicional: `88f4949` exige validação nacional quando `--all-brazil`
  é usado nos entrypoints SINAN e CNES; catálogos parciais continuam permitidos
  apenas em seleções genéricas e fixtures explícitas.
- Evidência adicional: `555ff4e` registra o instante de promoção no manifesto
  (`promoted_at`) sem quebrar manifests anteriores.
- Evidência adicional: `055dfb5` valida `promoted_at` como ISO-8601 quando o
  campo está presente e rejeita valores inválidos.
- Evidência adicional: `18d4063` exige timezone em `promoted_at`, eliminando
  timestamps locais ambíguos no manifesto.

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
- Quando um `MunicipalityCatalog` é fornecido sem escopo explícito, Gold e
  `aggregate_file()` agora usam todo o catálogo; o default RJ só permanece no
  caminho sem catálogo. Há regressão multi-UF contra a queda silenciosa para o
  recorte legado.

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
  - Checkpoints rejeitam caminhos Bronze inválidos, hashes não hexadecimais e
    contagens de linhas inválidas, sem perder a possibilidade de retomar o lote.
  - Contratos críticos do checkpoint possuem regressões e mutantes direcionados
    mortos.

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
- Estado: **Parcial; homologação pública nacional concluída, dados autorizados pendentes**
- Dependências: IBGE-004, IBGE-007
- Escopo: dados SINAN autorizados, Gold nacional e reconciliação Silver → Gold
  → PostgreSQL.
- Critérios de aceite:
  - Cada linha é classificada como resolvida, fora do escopo, inválida ou UF
    divergente.
  - Soma de casos elegíveis coincide com a expectativa independente.
  - Resultados são reproduzíveis com Silver, release IBGE e lote CNES fixos.
- Evidência local: fixture Parquet derivada do ZIP oficial DTB 2025 contém os
  5.571 municípios e é usada pelos três testes nacionais offline, sem HTTP e
  sem `IBGE_DTB_ARCHIVE`; isso não substitui uma carga SINAN nacional
  real/autorizada.
- Homologação repetida contra o ZIP oficial DTB 2025, SHA-256
  `d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27`:
  `tests/test_national_scope.py` passou com 3 testes; a fixture Parquet
  versionada tem 133.325 bytes e o ZIP bruto continua fora do repositório.
- Homologação remota adicional em 31/10/2026: `IbgeLocalidadesClient` retornou
  5.571 municípios e 27 UFs pela API oficial, com aprovação da validação
  nacional. A rede não é usada durante o processamento de releases locais.
- O total independente de `run_load.py` usa o mesmo resolvedor IBGE quando há
  catálogo ativo; códigos completos inválidos não são mais aceitos por
  truncamento para seis dígitos.
- A UF declarada na Silver (`SG_UF_NOT`) também participa dessa resolução
  independente, evitando contar notificações com município/UF divergentes.
- Gold e `run_load.py` compartilham o helper `resolve_catalog_municipality_codes()`;
  a reconciliação independente não mantém uma segunda implementação do
  crosswalk IBGE.
- O contrato CLI de `run_load.py` possui testes para obrigatoriedade de doença e
  ano, tipos, defaults, ajuda e encaminhamento de escopo/lote CNES.
- A Gold possui teste em lotes que reconcilia simultaneamente resolução válida,
  código inválido, município fora do escopo, UF divergente e metadados da
  release IBGE.
- A Gold usa o mesmo resolvedor canônico quando o catálogo está ativo; a
  normalização textual legada ficou restrita ao modo sem catálogo.
- `dropped_rows` na Gold representa somente linhas descartadas; a redução por
  agregação é registrada separadamente em `aggregation_reduction`.
- Homologação pública real: SINAN DENG 2024 passou por Silver, Gold e PostgreSQL
  nacional; 6.179.050 casos resolvidos, 2.428.428 grupos, 5.571 municípios e
  uma divergência de UF sinalizada. Essa evidência não substitui eventual
  fixture autorizada de produção.

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
- `write_events()` ordena eventos por data de vigência e `event_id` antes da
  materialização, garantindo o mesmo Parquet para a mesma coleção de eventos
  independentemente da ordem de entrada.
- `write_events()` também valida a forma semântica de cada evento: criações,
  extinções, sucessões e mudanças toponímicas não podem declarar códigos de
  origem/destino incompatíveis.
- `promote_administrative_events()` pode validar referências contra as duas
  edições participantes antes de promover o histórico; sem esses conjuntos a
  promoção continua explícita, mas não afirma uma correspondência histórica.
- `promote_historical_source()` preserva artefatos documentais oficiais em
  `historical/sources/`, com manifesto imutável, SHA-256, URL, período e
  `extraction_status=RAW_ONLY`. A genealogia IBGE 1872–2010 foi homologada
  nesse modo; nenhum crosswalk é criado sem extração tabular validada.
- `download_historical_source()` baixa esses artefatos com temporário, fecha a
  sessão HTTP e valida SHA-256 antes da promoção; falhas não deixam fonte
  parcial no catálogo.

- A validação nacional também rejeita candidatas com menos de 5.500 municípios,
  além de exigir as 27 UFs, para impedir a promoção de respostas truncadas.
- A publicação PostgreSQL rejeita explicitamente releases cujo manifesto não
  esteja em `validation_status=VALIDATED`, mesmo quando o SHA-256 é válido.
- O manifesto histórico acumula múltiplas fontes promovidas, preservando SHA,
  URL, período e política de inferência de cada uma.
- A promoção anual da DTB preserva fontes históricas já existentes e declara
  explicitamente a política mista quando combina eventos explícitos e diferenças
  observáveis.
- Após `5dc9822`, eventos sem `event_id` ou sem proveniência textual são
  rejeitados antes da materialização; `tests/test_ibge_historical.py` passou
  com 71 testes.
- Os parsers administrativo, toponímico e da planilha histórica agora formam
  `event_id` somente a partir da identidade semântica do evento (tipo, data e
  geocódigos), sem depender da posição da linha; reordenação da mesma fonte é
  idempotente e mudança de payload para a mesma identidade continua gerando
  conflito.
- As operações anuais `derive_annual_event_series()` e
  `promote_annual_dtb_events()` também integram o contrato público do pacote
  `reference.ibge`, com regressão de importação.
- A escrita de manifestos, artefatos auxiliares e `active.json` usa temporários
  exclusivos no diretório de destino; atualizações concorrentes não disputam
  mais um nome `.tmp` fixo. A regressão também executa duas promoções
  concorrentes e valida o ponteiro final e a limpeza dos temporários.
- O commit `ca10257` adicionou o parser da planilha oficial
  `pop_mun_TUR_1872_a_2010.xls`, promovendo somente alterações de nome com o
  mesmo código. A execução do artefato oficial produziu 2.149 eventos
  toponímicos; sucessões e desmembramentos sem código de origem continuam
  explicitamente não inferidos.
- A planilha oficial agora está versionada como fixture de contrato em
  `tests/fixtures/ibge/pop_mun_TUR_1872_a_2010.xls`, com SHA-256
  `55b8b767e21394851eae2ccf0c242e30919b867b36e2f36a67c1a4d95e6324df` e
  regressão offline que reproduz os 2.149 eventos. A fixture prova a
  ingestão toponímica, mas não converte descrições sem código em sucessões.
- As notas técnicas oficiais da evolução territorial registram que as origens
  municipais foram compiladas de fontes históricas e podem conter divergências;
  a descrição textual não é evidência suficiente para fabricar um crosswalk
  `source_code7 → target_code7`. A política `EXPLICIT_SOURCE_ONLY` permanece
  correta até existir uma tabela codificada validada.

### IBGE-012 — Mutação dos contratos críticos

- Prioridade: **P1**
- Estado: **Parcial; 78,46% classificável na última medição global**
- Dependências: IBGE-001 a IBGE-008
- Escopo: normalização, filtro, cache, promoção, checkpoint, linhagem e
  reprocessamento.
- Critérios de aceite:
  - Mutantes críticos de `code6 → code7`, UF, promoção e linhagem morrem.
  - Mutantes equivalentes são documentados individualmente.
  - Meta global de 95% é atingida sem reduzir artificialmente o escopo.
  - Integrações PostgreSQL são executadas em rodada separada.
- A última rodada global completa registrada após os contratos de publicação
  foi de **7.958 mutantes**, com **6.244 mortos, 1.713 sobreviventes e 1
  timeout**; entre os 7.957 classificáveis, a taxa foi **78,47%**. A meta de
  95% permanece pendente e o escopo não foi reduzido artificialmente.
- Após os contratos de identidade histórica e da API pública, a medição do
  cache completo processou **7.954 mutantes**, com **6.246 mortos, 1.707
  sobreviventes e 1 timeout**; entre os 7.953 classificáveis, a taxa foi
  **78,54%**. Esta é a medição atual para acompanhamento, sem substituir a
  exigência de uma execução global limpa quando o escopo final for congelado.
- O commit `58c11f5` cobriu o `main()` de `update_sinan.py`: os 92 mutantes
  anteriormente sem testes passaram a ser exercitados; 44 morreram e 48
  sobreviveram em rodada dirigida. A baseline global continua separada dessa
  medição seletiva.
  - Última rodada dirigida de `reference/ibge/refresh.py`: 167 mortos,
    167 sobreviventes e 119 sem testes associados; não substitui a medição
    global nem atende à meta de 95%.
  - Após `0d029e6`, `4d90061` e `576b1c0`, os 30 sobreviventes então
    associados a `reference/ibge/catalog.py` foram reexecutados: 22 mortos e
    8 sobreviventes; a rodada dirigida não altera a medição global limpa.
  - Os 59 mutantes de `_register_catalog_release()` foram executados em cache
    limpo após `8b26762` e `8a2d581`: **59/59 mortos**.
  - Após `44abf2c` e `89c5402`, uma rodada dirigida matou mais **10 mutantes
    históricos** de identidade de evento, erros de fonte e caminhos de artefato;
    essa medição é complementar e não substitui a baseline global limpa.
  - O commit `627e9c1` adicionou o contrato de encaminhamento das métricas da
    Gold; a rodada dirigida de `run_load` matou mais **13 mutantes relevantes**
    de fonte, ano, colunas, lote CNES, escopo e qualidade. Essa evidência é
    complementar à medição global.
  - Após `6fd95ec`, os **12 mutantes** novos da validação de métricas obrigatórias
    e tipos em `run_load.py` foram executados e mortos em rodada dirigida; a
    baseline global não foi substituída por essa medição parcial.
  - O commit `4307e6c` adicionou reconciliação aritmética entre
    `source_rows`, `resolved_rows`, `discarded_rows` e
    `aggregation_reduction`, com regressão para metadata inconsistente. A
    suíte integral passou em **581 testes**, com **3 pulados** e **25 warnings**.
  - Os **20 mutantes** gerados para essa reconciliação foram executados em
    rodada dirigida e todos morreram; essa medição não altera a baseline global
    por não ser uma execução limpa e completa.
  - O commit `3707994` passou a comparar release, SHA-256 e hash/tipo/tamanho
    do escopo no metadata Gold antes da publicação. Os cenários de release e
    escopo divergentes foram adicionados; a suíte integral chegou a **583
    testes**, com **3 pulados** e **25 warnings**.
  - O commit `7ef49b5` adicionou a validação de doença, ano e destino
    `serving` no metadata da Gold antes da carga catalogada; o teste de
    identidade divergente foi adicionado e a suíte chegou a **584 testes**,
    com **3 pulados** e **25 warnings**.
  - O commit `f3a0b02` corrigiu a promoção anual histórica para rejeitar
    `sources` malformado em vez de descartá-lo silenciosamente. A regressão
    foi adicionada e a suíte integral passou em **585 testes**, com **3 pulados**
    e **25 warnings**.
  - A genealogia oficial 1872--2010 foi verificada com `pypdf`: o PDF tem 97
    páginas, mas a extração local embaralha colunas e caracteres dos códigos.
    O artefato permanece `RAW_ONLY` até existir extração tabular validável;
    nenhuma sucessão é inferida dessa saída.
  - O commit `3accdea` passou a validar a forma de `inference_policies` no
    manifesto anual, com regressão para valor serializado como string. A suíte
    integral passou em **586 testes**, com **3 pulados** e **25 warnings**.
  - O commit `4e456bf` centralizou a validação de proveniência das fontes
    históricas, exigindo ano, caminho e SHA-256 válido; a regressão de fonte
    sem SHA foi adicionada e a suíte chegou a **587 testes**, com **3 pulados**
    e **25 warnings**.
  - O commit `41437ad` passou a validar o esquema completo das fontes
    documentais `RAW_ONLY`, incluindo URL, período, SHA, tamanho e status.
    A regressão de entrada sem URL foi adicionada; a suíte passou em **588
    testes**, com **3 pulados** e **25 warnings**.
  - O commit `fdb0786` tornou obrigatórios ano, fonte, URL e
    `retrieved_at` com timezone nas releases IBGE, com regressões para
    metadata incompleto. A suíte integral passou em **594 testes**, com
    **3 pulados** e **25 warnings**.
  - O commit `44cfbdc` cobriu UF declarada ausente no resolvedor municipal; o
    mutante de normalização de `pd.NA` morreu. A variante `None` versus string
    vazia foi classificada como equivalente pelo contrato atual.
  - O commit `213c94c` adicionou o contrato direto de normalização com catálogo;
    a rodada dirigida matou **4 de 5 mutantes** desse caminho. O quinto foi
    classificado como equivalente sob a restrição de códigos numéricos.
  - O commit `585450d` adicionou regressão para UF divergente; a Gold mantém o
    recorte vazio e não mascara a inconsistência com a UF canônica.
  - O commit `fdd967b` adicionou regressão de bloqueio do `run_load` quando
    `uf_mismatch_rows` é positivo; a rodada dirigida matou **3 mutantes** do
    caminho de publicação.
  - A suíte integral posterior passou em **500 testes**, com **3 pulados** e
    **25 warnings**, incluindo PostgreSQL de integração local.
  - Após `88f4949`, a suíte integral passou em **501 testes**, com **3 pulados**
    e **25 warnings**; `nix flake check --no-build` também passou.
  - O commit `5d5c055` adicionou regressões de CLI para `run.py` e
    `run_cnes.py`; a suíte integral posterior passou em **503 testes**, com
    **3 pulados** e **25 warnings**.
  - O commit `9f39029` reforçou os contratos de checkpoint do CNES; uma rodada
    dirigida matou **7 mutantes** selecionados de validação de hash, contagem,
    tipos e mensagens. A suíte integral posterior passou em **513 testes**, com
    **3 pulados** e **25 warnings**.
  - O commit `8c84ac7` cobriu a classificação de timeout, conexão, HTTP,
    validação, API e processamento; os **8 mutantes** selecionados morreram.
    A suíte integral posterior passou em **519 testes**, com **3 pulados** e
    **25 warnings**.
  - O commit `0c2d440` cobriu reprocessamento com divergência isolada de
    `catalog_id` ou SHA e o caminho idêntico `UNCHANGED`; os **3 mutantes**
    selecionados do vínculo territorial morreram. A suíte integral posterior
    passou em **522 testes**, com **3 pulados** e **25 warnings**.
  - O commit `3d28740` cobriu os três tipos de escopo aceitos na publicação
    PostgreSQL e a mensagem exata para tipo inválido; **6 mutantes** selecionados
    morreram. A suíte integral posterior passou em **525 testes**, com **3
    pulados** e **25 warnings**.
  - A rodada dirigida correta de `storage._validate_metadata()` executou
    **34/34 mutantes mortos**, incluindo SHA-256, status de validação e
    `promoted_at` com timezone. O identificador utilizado pelo `mutmut` inclui
    `x__` para funções privadas; essa medição não substitui a rodada global.
  - O commit `da5ebff` cobriu ponteiro ativo ausente, JSON inválido e
    `catalog_id` não textual. Na rodada dirigida, **4/5 mutantes selecionados**
    morreram; o quinto foi classificado como equivalente por depender do
    encoding UTF-8 padrão do ambiente.
  - O commit `b0bef0a` adicionou o cenário de instalação em árvore inexistente;
    os **2 mutantes** selecionados de `write_manifest()` relativos a
    `mkdir(parents=True)` morreram. Os mutantes equivalentes de
    `promote_active()` permanecem documentados porque sua pré-condição
    `_load_release()` já exige o diretório da release.
  - O commit `7b894ca` passou a afirmar explicitamente os esquemas canônicos de
    municípios, UFs e crosswalk Parquet. Na rodada dirigida, **8 mutantes** de
    nomes de colunas morreram; seis variantes de serialização sem efeito no
    contrato lido foram classificadas como equivalentes.
  - A análise dirigida de `InMemoryMunicipalityCatalog.resolve()` deixou dois
    mutantes equivalentes: inicializações de `candidate` e `input_format` que
    só afetam caminhos já encerrados por formato inválido. Nenhum mutante altera
    uma resolução `VALID`, `UNKNOWN_CODE`, `UF_MISMATCH` ou
    `HISTORICAL_UNRESOLVED` observável.
  - O CLI do atualizador SINAN passou a ter regressões para defaults, caminho do
    manifesto, conversão de `--catalog-root`, carregamento condicional,
    mensagem de lista vazia e código de saída em falha. Na rodada dirigida, 10
    de 12 mutantes comportamentais morreram; os dois sobreviventes são apenas
    remoções do texto de ajuda do argumento.
  - O commit `fddcbff` cobriu o crosswalk CNES com um resultado de resolução
    inconsistente e a preservação da identidade canônica; os 2 mutantes
    dirigidos correspondentes morreram. A baseline global continua sendo a
    última rodada completa documentada, pois esta alteração foi medida apenas
    de forma dirigida.
  - O commit `5c7b0e8` cobriu o encaminhamento dos parâmetros de cada worker
    paralelo CNES; 6 mutantes dirigidos morreram. A baseline global ainda não
    foi recalculada.
  - A rodada global posterior processou novamente 7.958 mutantes: 6.237
    mortos, 1.720 sobreviventes e 1 timeout, com **78,38%** entre os
    classificáveis. A meta de 95% permanece pendente.
  - O commit `cb25975` cobriu o contrato de chamada da fonte SINAN no
    `run_load`; os 4 mutantes dirigidos de argumentos morreram. A baseline
    global não foi recalculada após essa alteração.
  - O commit `6da713a` cobriu métricas Gold textuais, booleanas e negativas;
    o mutante comportamental correspondente morreu. A baseline global ainda
    precisa ser recalculada para incorporar a alteração.
  - O commit `66329bd` cobriu a ausência de `metadata.json` da Gold com catálogo
    ativo; o mutante comportamental correspondente morreu. A baseline global
    ainda não foi recalculada após os dois últimos testes.
  - O commit `2adf4f0` isolou doença, ano e alvo na validação de identidade da
    Gold; o mutante que trocava a conjunção lógica morreu. A baseline global
    ainda não foi recalculada após essa alteração.
- A nova rodada global posterior processou novamente 7.958 mutantes: 6.244
    mortos, 1.713 sobreviventes e 1 timeout, com **78,47%** entre os
    classificáveis. A meta de 95% segue pendente.
- A rodada global mais recente, após as fixtures oficiais históricas, processou
  **7.966 mutantes**: **6.249 mortos, 1.716 sobreviventes e 1 timeout**. A
  taxa foi **78,46%** entre os 7.965 mutantes não temporizados; a configuração
  global não foi reduzida e a meta de 95% segue pendente.

### IBGE-013 — Rollout nacional de produção

- Prioridade: **P0 após os gates anteriores**
- Estado: **Bloqueado por gates externos, não por implementação local**
- Dependências: IBGE-009, IBGE-010, IBGE-011, IBGE-012
- Escopo: ativação por UF/lotes, observabilidade, reconciliação e runbook.
- Runbook operacional criado em
  [`IBGE_NATIONAL_ROLLOUT_RUNBOOK.md`](IBGE_NATIONAL_ROLLOUT_RUNBOOK.md), com
  promoção de release, CNES reiniciável, execução SINAN serving, fallback local
  e critérios de encerramento.
- Critérios de aceite:
  - Todas as UFs habilitadas passaram pelos critérios anteriores.
  - Release, escopo, lote CNES e métricas são consultáveis após a publicação.
  - Falhas de atualização não substituem a release ativa.
  - A execução nacional é repetível e auditável.

## Evidência

O estado de execução, commits, comandos e limitações estão registrados em
[`IBGE_INTEGRATION_EXECUTION.md`](IBGE_INTEGRATION_EXECUTION.md).
