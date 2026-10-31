# Relatório de execução — Integração IBGE ao NSS Pipeline

## Escopo

Execução incremental do plano de integração nacional do catálogo municipal do
IBGE, realizada na branch `work/nss-pipeline`. O objetivo desta rodada foi
estabelecer a infraestrutura local, preservar o recorte legado do RJ e levar a
identidade municipal canônica aos executores SINAN e CNES.

## Commits produzidos

| Commit | Conteúdo |
| --- | --- |
| `ad053e7` | Fundação do catálogo municipal IBGE, crosswalk 6↔7 e escopos |
| `02130fb` | Aquisição validada da API de Localidades e suporte da Gold ao catálogo |
| `4a4c0c4` | Seleção geográfica nos executores SINAN |
| `52ceeb3` | Persistência da release IBGE nas publicações PostgreSQL |
| `ddb660f` | Validação do crosswalk municipal no CNES |
| `ec0910b` | Registro configurável de assets territoriais |
| `4425236` | UF e município canônicos na Gold |
| `603526b` | Reprocessamento SINAN quando a release IBGE muda |
| `a5bf89f` | Parser e promoção da DTB oficial 2025 |
| `425dab0` | Correção do encadeamento das migrations (`0006`) |
| `069bef4` | Métricas de resolução municipal na Gold |
| `820a135` | Histórico territorial e classificação do Distrito Federal |
| `5f2fea3` | Teste de linhagem IBGE na publicação PostgreSQL |
| `d8414c1` | Hash lógico para releases obtidas pela API |
| `0f1208d` | FK municipal canônica na Silver CNES e dimensão de unidades |
| `a67f925` | Bloqueio de publicação para resoluções IBGE inválidas |
| `1e34ae4` | Métricas Gold separadas para resolução, descarte e agregação |
| `48720cf` | Promoção do histórico oficial de alterações toponímicas |
| `c5d9964` | Paginação CNES configurável para execução nacional |
| `0977138` | Download e cache da DTB com validação SHA-256 |
| `c6033cd` | Atualização da contagem final de validação |
| `5842e91` | Inclusão do commit final no relatório |
| `3274ac0` | Correção do runner mutante para assets territoriais |
| `726042a` | Cobertura dos contratos de resolução do catálogo |
| `9f01fc2` | Diagnósticos de resolução e leitura Parquet |
| `8d6de55` | Limpeza de temporários em metadados atômicos |
| `3b0f828` | Testes dos fluxos de promoção de releases |
| `40d1c78` | Escopo geográfico e paginação CNES expostos na CLI |
| `66d5920` | Documentação da seleção geográfica CNES |
| `e75e1a9` | Persistência das métricas de qualidade Gold |
| `8983ca3` | Validação de ponteiro e manifesto da release ativa |
| `ab37650` | Fixação do lote CNES para Gold reprodutível |
| `a7ae190` | Documentação de lotes CNES fixados |
| `1c3c99b` | Suporte a eventos administrativos explícitos |
| `c0dc947` | Isolamento do fixture de metadata nos testes |
| `7e0bd6c` | Inclusão do histórico IBGE no escopo do mutmut |
| `7e3be14` | Paginação CNES avança pelo tamanho efetivamente retornado |
| `8e73dc0` | Preservação de identidades imutáveis de releases |
| `aabe4df` | Merge idempotente de eventos históricos promovidos |
| `6486a09` | Materialização de UFs e crosswalk nas releases |
| `be6188c` | CLI de atualização controlada do catálogo IBGE |
| `dea9ad4` | Documentação do refresh controlado |
| `17ca28a` | Cobertura da persistência e imutabilidade das releases IBGE |
| `5e8e78a` | Alinhamento temporal dos registros da API |
| `23cbd2e` | Validação de SHA-256 nos manifestos e publicações |
| `bf2473d` | Derivação segura de diferenças anuais da DTB |
| `159e97e` | Consistência entre ano dos registros e manifesto |
| `696e19d` | Verificação completa antes do reuso de releases |
| `4f97372` | Centralização do recorte RJ legado em `scope.py` |
| `13e14da` | Consistência das identidades de UF no catálogo |
| `c61f36c` | Relatórios tipados de validação do catálogo |
| `fc49691` | Ordenação determinística dos artefatos de release |
| `6f51671` | Reutilização de sessão HTTP no escopo nacional CNES |
| `163e818` | Promoção atômica e segura de releases IBGE |
| `36d5942` | Homologação nacional offline do escopo CNES |
| `a7e99d1` | Contrato explícito de timeout no download da DTB |
| `4d33b14` | Cobertura dos entrypoints de refresh IBGE |
| `84d54d3` | Contrato de chunking no download da DTB |
| `626a02f` | Atualização dos resultados de mutação do streaming |
| `b567e8b` | Persistência do hash do escopo geográfico |
| `d410b41` | Imutabilidade da release IBGE na publicação PostgreSQL |
| `3d4ca99` | Timeout configurável para requisições CNES |
| `79fb79d` | Homologação do timeout no escopo nacional CNES |
| `b61e7e3` | Serialização concorrente do registro de releases IBGE |
| `dc1da0b` | Verificação do hash lógico do conteúdo do catálogo |
| `37bc89d` | Rejeição de municípios duplicados no escopo explícito |
| `00d4986` | Checkpoint reiniciável para ingestão CNES nacional |
| `1e4df67` | Hash de integridade das Bronze retomáveis do CNES |
| `993d6ce` | Bloqueio de resolução contra ano de referência incompatível |
| `56ba752` | Validação estrutural de checkpoints CNES |
| `97c3955` | Fortalecimento dos contratos de resolução e timeout |
| `f2c8cb5` | Bloqueio de rede em timeout CNES inválido |
| `36dfc21` | Fortalecimento dos contratos do cliente de Localidades |
| `45939c1` | Registro da rodada de mutação do cliente de Localidades |
| `feb6303` | Registro da suíte de testes do cliente de Localidades |
| `1a65c89` | Classificação de falhas municipais em lotes CNES |
| `8839764` | Documentação da retomada de lotes CNES parciais |
| `17cdf1d` | Defaults locais para PostgreSQL de desenvolvimento |
| `44e07b4` | Retentativa de municípios falhos na retomada CNES |
| `78d3dd9` | Workers limitados para ingestão CNES nacional |
| `28bf78a` | Janela limitada de requisições CNES |
| `3d4e019` | Série anual explícita de eventos territoriais |
| `ea1ca07` | Reconciliação sintética SINAN em todos os municípios |
| `2daea85` | Compatibilidade do parser com DTBs anuais legadas |
| `df427b3` | Registro da regressão das DTBs legadas |
| `b8ac609` | Registro da regressão nacional sintética |
| `594bdb5` | Promoção idempotente de eventos anuais DTB |
| `0a908e8` | Timeout do download DTB exposto no wrapper e na CLI |
| `9ddd663` | Validação semântica dos eventos históricos |
| `72a16af` | Testes dos contratos de erro do histórico |
| `d6d2efa` | Asserção dos códigos históricos persistidos |
| `cb8b404` | Validação de referências entre edições históricas |
| `8044970` | Reconciliação do total SINAN pelo resolvedor IBGE |
| `ebeedea` | Limpeza do fixture de escopo do teste SINAN |
| `a01cc7a` | Reconciliação do total SINAN com UF declarada |
| `d0c512c` | Gold resolve códigos diretamente pelo catálogo IBGE |
| `56aad3e` | Cobertura direta do contrato do resolvedor Gold |
| `879d637` | Cobertura do contrato CLI do executor SINAN |
| `be0c06c` | Reuso do resolvedor IBGE da Gold no executor SINAN |
| `4113812` | Endurecimento do contrato CLI de `run_load` |
| `e604894` | Cobertura Gold em lotes com métricas nacionais de resolução |
| `36eeaa7` | Asserção do contexto completo do resolvedor IBGE |
| `fa7d43b` | Cobertura das invariantes do relatório de validação IBGE |
| `958f160` | Cobertura do hash lógico canônico do catálogo |
| `121ab52` | Cobertura da validação de metadados de release |
| `135c375` | Inserção de fatos nacionais em lotes limitados |
| `cb11e35` | Rejeição de geocódigos históricos Unicode |
| `f3cc7fd` | Rejeição de geocódigos Unicode no parser DTB |
| `cfca80f` | Cobertura das ramificações do parser de arquivos DTB |
| `b4b1930` | Cobertura de limpeza e falhas do refresh IBGE |
| `f18f733` | Rejeição de ponteiros ativos JSON malformados |
| `682a468` | Cobertura dos contratos CLI do refresh IBGE |
| `9102192` | Preservação imutável de fontes históricas brutas |
| `4cf6523` | Validação ASCII dos códigos municipais CNES |
| `92e4f40` | Separação das métricas de descarte e agregação Gold |
| `29e7653` | Registro da resolução canônica na Gold |
| `a4d26a3` | Defaults de PostgreSQL diretamente no Compose |
| `570939d` | Cobertura das fronteiras de validação CNES |
| `59a8b1f` | Cobertura dos limites mínimos válidos do CNES |
| `8f29811` | Cobertura dos contratos de checkpoint e escopo CNES |
| `09f048a` | Vinculação do checkpoint à identidade da release IBGE |
| `e6571df` | Contrato exato para escopo CNES vazio |
| `a9a64cb` | Garantia de timestamps UTC no lote CNES |
| `11bcf8e` | Parâmetros e sessão HTTP respeitados no escopo RJ legado |
| `90dbd9b` | Validação explícita do schema de respostas CNES |
| `186561e` | Validação estrutural das entradas de checkpoint CNES |
| `6e18209` | Vinculação do escopo geográfico à release IBGE |
| `5a01782` | Teste do vínculo catálogo–escopo no executor SINAN |
| `dd1c300` | Cobertura mutante integral do vínculo catálogo–escopo |
| `195ec3a` | Interrupção segura de paginação CNES repetida |
| `0b8a09f` | Rejeição de registros CNES de município divergente |
| `b46a3d4` | Cobertura mutante das entradas de checkpoint CNES |
| `3d2ab22` | Asserção do payload canônico de resolução IBGE |
| `163d705` | Cobertura dos defaults e normalização do executor de carga |
| `3ae434f` | Canonicalização de recorte explícito no executor CNES |
| `4632a10` | Centralização do recorte legado fora da lógica operacional da Gold |
| `7d7c349` | Validação de geocódigos em eventos históricos administrativos |
| `77b4276` | Smoke SINAN Gold nacional com DTB oficial e cinco UFs |
| `d618302` | Teste de reprocessamento após mudança da release IBGE |
| `c466409` | Teste de erro explícito para município legado ausente |
| `7843e10` | Fechamento seguro de sessões HTTP próprias do refresh IBGE |
| `08fb037` | Teste de linhagem do catálogo no executor de carga |
| `e29cf60` | Rejeição de linhas DTB municipais malformadas |
| `89a0f17` | Validação completa antes da promoção de `active.json` |
| `f9fda72` | Integração PostgreSQL multi-UF com linhagem IBGE |
| `034d45d` | Registro da validação PostgreSQL multi-UF no relatório |
| `bc45eaa` | Matriz de completude da execução |
| `8e70f72` | Delimitação da fonte histórica oficial |
| `b5a64d1` | Calibração CNES real em múltiplas UFs |
| `2218e6a` | Amostra CNES real percorrida integralmente |
| `f602b95` | Amostra real do pipeline CNES completo |
| `ea9c0b6` | Exclusividade da seleção geográfica nas CLIs SINAN |
| `285aea0` | Backlog versionado da integração IBGE |
| `0b12965` | Resultado final da suíte de regressão |
| `3413f09` | Refresh real da release DTB 2025 após a implementação |
| `91cd86c` | Rejeição de releases nacionais sem alguma das 27 UFs |
| `91e14b2` | Fechamento seguro de sessões próprias da API de Localidades |
| `a2a1496` | Fechamento das respostas HTTP em streaming da DTB |
| `b5caa06` | Registro da limpeza de recursos HTTP |
| `788bce9` | Fallback da API para municípios sem microrregião |
| `7098e16` | Registro da validação real da API de Localidades |
| `3251a8e` | Smoke test do refresh via API de Localidades |
| `3c2b06b` | Paridade entre API de Localidades e DTB 2025 |
| `af1fb56` | Regressão final após integração da API real |
| `00a53b3` | Calibração CNES real nas 27 UFs |
| `db34796` | Execução real do `run_cnes` no escopo amostral nacional |
| `cd7721a` | Atualização do status de homologação CNES |
| `36dfc21` | Fortalecimento dos contratos do cliente de Localidades |
| `45939c1` | Registro da rodada de mutação do cliente de Localidades |

Todos os commits foram enviados para `origin/work/nss-pipeline`.

## Entregas implementadas

- `Municipality`, `CatalogMetadata`, `MunicipalityCatalog` e resultados
  tipados de resolução.
- Validação de códigos, unicidade de `code7`, unicidade do crosswalk `code6`
  e consistência entre código municipal e UF.
- Resolução de códigos SINAN de seis e sete dígitos, incluindo a compatibilidade
  limitada com `0330100`.
- Armazenamento local em Parquet, manifesto e ponteiro `active.json` com
  escrita atômica.
- Download controlado da DTB para cache bruto, com SHA-256 e promoção somente
  após validação.
- Cliente da API de Localidades do IBGE com validação estrutural da resposta.
- Seleção por município, UF ou Brasil inteiro, mantendo o RJ como default.
- Entry points que recebem `catalog` e `GeographicScope` validam que ambos
  representam a mesma identidade municipal antes de iniciar ingestão ou carga.
- O executor CNES canonicaliza mapas explícitos quando recebe uma release IBGE;
  não substitui silenciosamente um recorte informado pelo RJ padrão e rejeita
  nomes municipais divergentes antes de qualquer requisição HTTP.
- A Gold mantém `MUNICIPIOS_RJ` somente como alias público de compatibilidade;
  sua lógica operacional agora obtém o recorte legado por `scope.py`.
- Eventos administrativos históricos agora rejeitam códigos de origem ou destino
  que não tenham exatamente sete dígitos numéricos.
- O contrato nacional SINAN Gold possui um smoke test contra a DTB oficial,
  resolvendo códigos de seis dígitos para municípios reais em cinco UFs e
  verificando a UF canônica e o total agregado.
- O atualizador SINAN possui teste explícito de reprocessamento quando a
  identidade ou o SHA da release IBGE muda, mesmo que o arquivo remoto tenha o
  mesmo tamanho.
- A mutação dirigida de `legacy_rj_scope` matou o caso que substituía a
  mensagem de município legado ausente por um erro sem contexto.
- O download da DTB fecha a sessão HTTP quando ela é criada internamente,
  mantendo sessões fornecidas externamente sob responsabilidade do chamador.
- O executor `run_load` agora possui teste que comprova a propagação conjunta
  da release IBGE, do escopo por UFs, do tipo de escopo e de seu hash até a
  chamada de publicação PostgreSQL.
- O parser DTB rejeita códigos municipais ou UFs malformados em linhas
  preenchidas e continua aceitando o ZIP oficial 2025: 5.571 municípios, 27 UFs
  e Brasília classificada como `FEDERAL_DISTRICT`.
- `promote_active()` valida a release candidata antes de trocar o ponteiro;
  releases ausentes, inválidas, com ano divergente ou conteúdo adulterado não
  podem deixar um `active.json` quebrado.
- A integração PostgreSQL possui teste multi-UF com RJ e SP, verificando fatos,
  dimensões, FKs municipais e linhagem da release IBGE na mesma publicação.
- Opções CLI `--catalog-root`, `--municipios`, `--ufs` e `--all-brazil` nos
  executores SINAN e CNES, com `--page-size` no CNES.
- Derivação canônica de município e UF na Gold quando um catálogo é fornecido.
- Validação do código municipal antes da consulta CNES e derivação explícita
  do código de seis dígitos.
- Persistência de `cd_mun` canônico na Silver CNES e na dimensão de unidades,
  quando o catálogo IBGE está disponível.
- Registro configurável de disponibilidade de malhas territoriais; municípios
  sem asset permanecem `UNAVAILABLE`.
- Migration `0005` para registrar release IBGE, hash e tipo de escopo na
  publicação PostgreSQL.
- Migration `0008` e metadata Gold para registrar o `scope_sha256` determinístico
  dos códigos municipais publicados, além do tipo e da contagem do escopo.
- Migration `0009` registra o hash lógico canônico dos registros municipais;
  o carregamento ativo rejeita Parquet adulterado mesmo sem o ZIP de origem.
- Publicação PostgreSQL rejeita a reutilização de `catalog_id` com SHA-256
  diferente, mantendo o registro de release imutável sob lock transacional.
- O registro da release usa advisory lock por `catalog_id`, evitando corrida
  entre publicações concorrentes de doenças diferentes.
- Manifesto SINAN sensível à mudança de `ibgeCatalogId` e
  `ibgeCatalogSha256`.
- Módulos IBGE incluídos no escopo do `mutmut`.
- Publicação SINAN bloqueada quando a Gold reporta código municipal inválido ou
  divergência entre UF declarada e UF canônica; municípios válidos fora do
  escopo continuam sendo contabilizados separadamente.
- Parser e promoção de alterações toponímicas oficiais para o histórico local,
  sem inferir criação, extinção ou sucessão municipal.
- Parser e promoção de eventos administrativos declarados para criação,
  extinção, sucessão, fusão e desmembramento, exigindo códigos de origem e
  destino explícitos quando aplicáveis.
- Comparação entre edições anuais da DTB para registrar somente criação,
  extinção e mudança de nome observáveis; sucessões entre códigos distintos
  continuam exigindo fonte histórica explícita.
- Promoção histórica idempotente: eventos toponímicos e administrativos são
  mesclados no mesmo Parquet, com conflito de `event_id` rejeitado.
- Paginação CNES configurável e validada, com `page_size` registrado no
  metadata do lote; o caminho legado RJ também respeita o parâmetro.
- Sessão HTTP CNES reutilizada durante toda a execução, inclusive no escopo
  legado, mantendo retries e reduzindo o overhead de múltiplos municípios.
- Timeout de requisição CNES configurável pela API e CLI, registrado no
  metadata do lote para tornar falhas e homologações reproduzíveis.
- Respostas CNES com JSON estruturalmente inválido são rejeitadas antes de
  acumular registros, evitando transformar respostas de erro em Bronze válida.
- Paginação CNES que repete a mesma página não vazia é interrompida com erro
  explícito, evitando loop infinito quando a API ignora o `offset`.
- Checkpoint opcional da ingestão CNES registra Bronze concluída e parâmetros
  imutáveis; uma nova execução retoma somente municípios pendentes e rejeita
  checkpoints de escopo ou configuração incompatíveis.
- Cada entrada do checkpoint também registra o SHA-256 da Bronze; adulteração
  ou substituição do arquivo persistido bloqueia a retomada.
- Checkpoints com JSON estruturalmente inválido são rejeitados com erro de
  contrato controlado antes de qualquer consulta à API.
- Entradas `completed` de checkpoints são validadas quanto ao escopo, caminho,
  hash SHA-256 e contagem antes da retomada; municípios extras ou registros
  incompletos são bloqueados.
- O CNES compara o município retornado pela API com o município solicitado;
  registros válidos, porém de outro município, são marcados como `OUT_OF_SCOPE`
  e o orquestrador bloqueia o lote antes da consolidação.
- `resolve(..., reference_year=...)` retorna `HISTORICAL_UNRESOLVED` quando a
  edição carregada não corresponde ao ano solicitado, evitando aplicar uma
  territorialidade corrente a uma série histórica silenciosamente.
- Teste de homologação offline opt-in (`IBGE_DTB_ARCHIVE`) percorre os 5.571
  municípios da DTB, simula a resposta CNES e verifica resolução canônica,
  sessão compartilhada e metadata do lote sem depender da rede.
- Fixação opcional de `cnes_batch_id` na Gold e nos executores SINAN, com
  rejeição de lote inexistente e registro do identificador no metadata.
- Métricas Gold de origem, resolução, descarte, redução por agregação, códigos
  inválidos, fora de escopo e divergências de UF persistidas na publicação
  PostgreSQL pela migration `0007`.
- Carregamento da release ativa protegido contra ponteiro inválido, manifesto
  incompatível, release não validada e traversal de caminho.
- Cada nova release materializa `municipalities.parquet`, `ufs.parquet` e
  `code_crosswalk.parquet`; leitores antigos continuam usando o catálogo
  municipal canônico. Os três artefatos são ordenados por suas chaves canônicas,
  independentemente da ordem de entrada.
- A release inteira é escrita em staging e promovida por troca atômica depois
  da validação do manifesto; falhas removem o staging e não alteram o ponteiro
  ativo. `catalog_id` também não pode escapar da raiz de releases.
- CLI `python -m app.pipeline.reference.ibge.refresh` para promover DTB local,
  DTB por URL ou API de Localidades com hash e proveniência explícitos.
- Registros obtidos pela API de Localidades recebem o `reference_year` declarado
  na release, evitando divergência temporal entre entidade e manifesto.
- SHA-256 de releases persistidas é validado como hexadecimal de 64 caracteres
  tanto no armazenamento local quanto na publicação PostgreSQL.
- O carregador rejeita registros cujo `reference_year` diverge do manifesto e
  o refresh não reutiliza releases com identidade ou validação inconsistentes.
- A seleção explícita de municípios rejeita códigos repetidos, evitando que a
  contagem declarada do escopo divirja do conjunto efetivamente processado.
- O contrato de download fixa por teste o timeout padrão de 120 segundos,
  evitando regressões silenciosas no controle de rede da atualização.
- `run_load.py` e `run_cnes.py` não dependem mais diretamente de
  `MUNICIPIOS_RJ`; o recorte legado é fornecido por `scope.py`, mantendo o
  alias público para compatibilidade.
- O validador rejeita o mesmo código de UF associado a siglas ou nomes
  divergentes antes de gerar `ufs.parquet`.
- `MunicipalityCatalog.validate()` expõe relatório tipado com validade,
  contagem de municípios, UFs, códigos 6 e erros sem exceção; a validação
  estrita continua disponível para promoção.
- Atualização protegida contra reutilização de `catalog_id` com SHA-256
  diferente; a candidata é rejeitada antes de sobrescrever o artefato ou o
  ponteiro ativo.
- Refresh nacional agora rejeita candidatas sem qualquer uma das 27 UFs antes
  de gerar Parquet ou trocar `active.json`; fixtures parciais precisam declarar
  explicitamente `require_national=False`.
- O refresh da API de Localidades fecha somente a sessão que criou; sessões
  fornecidas pelo chamador permanecem sob responsabilidade dele.
- O download em streaming fecha a resposta HTTP mesmo quando a validação do
  hash falha, sem substituir o artefato anterior.
- Configuração do `mutmut` incluindo os assets territoriais necessários aos
  testes-base dos executores CNES.
- `flake.nix` e `flake.lock` com Python 3.12, PostgreSQL, Docker e ambiente
  virtual reproduzível.

## Validação executada

```text
nix flake check --no-build  → aprovado
pytest -q                  → 415 passed, 25 warnings
pytest -q com PostgreSQL  → 415 passed, 25 warnings
pytest -q nacional + PostgreSQL → 415 passed, 25 warnings
regressão local sem PostgreSQL disponível → 395 passed, 22 skipped, 25 warnings
suíte completa com PostgreSQL de integração → 415 passed, 2 skipped, 25 warnings
tests/integration com PostgreSQL → 20 passed, 1 warning
suíte completa após retentativa CNES → 415 passed, 2 skipped, 25 warnings
suíte completa após workers CNES e série histórica → 420 passed, 2 skipped, 25 warnings
suíte completa após suporte às DTBs legadas → 421 passed, 3 skipped, 25 warnings
suíte final após a promoção idempotente de eventos DTB → 422 passed, 3 skipped,
25 warnings
suíte final após exposição do timeout DTB → 422 passed, 3 skipped, 25 warnings
suíte após validação semântica dos eventos históricos → 426 passed, 3 skipped,
25 warnings
testes dirigidos do histórico após contratos de erro → 23 passed, 1 warning
suíte completa após contratos de erro do histórico → 430 passed, 3 skipped,
25 warnings
suíte completa após validação de referências históricas → 432 passed, 3 skipped,
25 warnings
suíte completa após reconciliação do total SINAN pelo catálogo → 433 passed,
3 skipped, 25 warnings
suíte completa após reconciliação com UF declarada → 434 passed, 3 skipped,
25 warnings
suíte completa após resolução canônica na Gold → 435 passed, 3 skipped,
25 warnings
suíte completa após cobertura direta do resolvedor Gold → 436 passed, 3 skipped,
25 warnings
suíte completa após cobertura do contrato CLI de `run_load` → 437 passed,
3 skipped, 25 warnings

Após a convergência dos resolvedores, a suíte completa permaneceu em 437
passed, 3 skipped e 25 warnings. O cálculo independente de totais em
`run_load.py` agora chama `resolve_catalog_municipality_codes()`, o mesmo
helper usado pela Gold, eliminando duas implementações concorrentes do
crosswalk IBGE e mantendo a validação de UF declarada consistente.

Após o endurecimento do contrato CLI, a suíte dirigida de `run_load.py` passou
de 20 para 28 testes e a suíte completa com PostgreSQL passou para 445 passed,
3 skipped e 25 warnings. Foram cobertos explicitamente os argumentos
obrigatórios, conversão de ano, rejeição de ano inválido, defaults, texto de
ajuda e encaminhamento de escopo/lote CNES pelo `main()`.

A rodada dirigida dos 41 mutantes previamente sobreviventes do construtor do
parser matou 6 mutantes. Os 35 restantes alteram principalmente textos de
ajuda ou detalhes de assinatura sem efeito coberto pelo comportamento
funcional atual; isso melhora a cobertura local, mas não é apresentado como
uma nova medição global de mutação.

Foi adicionada uma execução de contrato da Gold em lotes com catálogo IBGE:
uma mesma entrada contém resolução válida, código completo inválido, município
válido fora do escopo e UF divergente. O teste verifica os quatro contadores de
resolução e a linhagem do catálogo. A suíte completa subsequente passou em 446
passed, 3 skipped e 25 warnings.
mutação dirigida de `write_events()` → 10/13 mutantes pendentes mortos; três
mutantes equivalentes ou de parâmetros de iteração permanecem classificados
como sobreviventes para investigação.
O mutante restante que troca um `None` por `str(None)` não altera a saída
persistida e é neutralizado pela própria guarda de valor nulo; foi mantido
como equivalente documentado, sem ser contado artificialmente como morto.

Eventos administrativos agora aceitam conjuntos explícitos de códigos das
edições de origem e destino. Quando fornecidos, qualquer `source_code7` ou
`target_code7` ausente é rejeitado antes da promoção; a implementação não
resolve nomes nem cria sucessões por aproximação.

O executor `run_load.py` também usa `catalog.resolve()` para calcular o total
independente da Gold quando uma release IBGE está ativa. Isso impede que um
código de sete dígitos inválido seja reduzido ao código de seis dígitos de um
município legítimo durante a validação de publicação.
Essa mesma resolução agora recebe `SG_UF_NOT`, mantendo o total independente
consistente com a rejeição de divergências de UF feita pela Gold.

Quando uma release IBGE é fornecida à Gold, `ID_MUNICIP` passa por
`catalog.resolve()` antes da filtragem. Assim, códigos completos inválidos e
municípios acompanhados de UF divergente não são convertidos por truncamento
nem agregados silenciosamente.

A mutação dirigida após essa alteração incluiu os caminhos de `aggregate()` e
`aggregate_file()`, mas não é uma rodada global comparável: os resultados
permanecem parcialmente classificados no cache do mutmut. A evidência de
aceite é a regressão funcional, que cobre explicitamente código completo
inválido e UF divergente.

O novo helper `resolve_catalog_municipality_codes()` também recebeu uma rodada
dirigida própria: 14 de 16 mutantes pendentes morreram. Os dois sobreviventes
alteram apenas a representação de UF ausente (`None` versus string vazia), sem
mudar a resolução observável, e permanecem documentados como equivalentes.

O contrato de `InMemoryMunicipalityCatalog.resolve()` foi ampliado para
verificar o contexto completo dos resultados. Na rodada dirigida dos 22
mutantes sobreviventes desse método, 18 morreram e quatro continuam
classificados como sobreviventes por alterações de inicialização que não
mudam nenhum resultado observável nos caminhos cobertos. A atualização do
cache dirigido passou a registrar 3.987 mortos e 2.268 sobreviventes; esse
valor não substitui a última rodada global completa de 7.000 mutantes.

A regressão completa executada após essa cobertura passou em 447 testes, com
3 testes pulados explicitamente e 25 warnings conhecidos.

Após a cobertura das invariantes de validação, a regressão completa passou em
449 testes, com 3 testes pulados explicitamente e 25 warnings conhecidos. A
rodada dirigida da validação matou 3 de 4 mutantes restantes; o quarto foi
classificado como equivalente porque trocar a normalização global de siglas
`upper()` por `lower()` não altera a igualdade relativa entre registros.

O hash lógico do catálogo passou a ter um teste de contrato com digest fixo,
ordem de entrada permutada e alteração de atributo. Na rodada dirigida de 16
mutantes desse cálculo, 14 morreram e dois foram classificados como
equivalentes: `ensure_ascii=None` mantém a semântica efetiva usada nesse caso,
e nomes de encoding UTF-8 são tratados sem distinção pelo Python.

A validação de metadados da release agora cobre separadamente identificador
vazio, SHA-256 inválido, hash lógico inválido, status pendente e a aceitação
explícita de hash lógico ausente. Os 14 mutantes dirigidos desse helper foram
todos mortos.
fixture SINAN sintética nacional → 3 passed; uma linha por município em 5.571 municípios
national catalog smoke    → 5571 municípios, 27 UFs
controlled refresh smoke  → release DTB 2025 promovida e recarregada
controlled refresh after safe promotion → release recarregada via active.json,
  5571 municípios e SHA do ZIP confirmado
IBGE Localidades real → 5571 municípios, 27 UFs; Boa Esperança do Norte
  (`5101837`) resolvida via hierarquia de região imediata/intermediária
Refresh end-to-end da API de Localidades → release `ibge-api-2026-final`,
  5571 municípios, 27 UFs e ponteiro `active.json` recarregado com sucesso
Comparação API de Localidades × DTB 2025 → 0 códigos exclusivos em qualquer
fonte e 0 divergências de nome, UF ou sigla entre os 5571 registros
comparação DTB 2024 × DTB 2025 → 5571 municípios em cada edição e 3 mudanças
toponímicas explícitas; nenhuma sucessão foi inferida
Série DTB oficial 2011–2025 → edições legíveis com 5565 municípios em 2011/2012,
5570 em 2013–2023 e 5571 em 2024/2025; 53 eventos observáveis (47 mudanças
toponímicas e 6 criações), sem sucessões inferidas
national CNES smoke        → 5571 municípios resolvidos, 1 sessão reutilizada
CNES real nacional         → `COMPLETED`, 5571/5571 municípios, 5571 Bronzes,
  641343 estabelecimentos, zero falhas, 100% `municipality_resolution_status=VALID`,
  catálogo `ibge-dtb-2025-full` (SHA bruto `d077a0e4...dad27`), 8 workers
```

Também foi executada uma homologação epidemiológica com o arquivo público
SINAN DENG 2024 obtido pelo PySUS. O download isolado teve 165009354 bytes;
o pipeline processou 6564163 linhas na Silver em 62 lotes e produziu Gold
nacional com 6179051 linhas, das quais 6179050 foram resolvidas, uma foi
descartada, nenhuma foi classificada como código municipal inválido e nenhuma
ficou fora do escopo. Houve uma divergência de UF sinalizada, sem associação
geográfica indevida; o resultado final contém 2428428 grupos e 6179050 casos.

Essa Gold foi publicada em PostgreSQL de integração isolado, com 2428428 fatos,
6179050 casos e 5571 municípios, mantendo a linhagem da release IBGE. A carga
inicial confirmou o custo elevado de materializar todos os parâmetros em uma
única chamada; por isso `insert_fato_casos()` passou a enviar lotes de 10000
registros dentro da mesma transação (`135c375`).

O PDF oficial de genealogia municipal 1872–2010 também foi preservado em uma
homologação isolada como fonte `RAW_ONLY`, sem gerar eventos automaticamente:
SHA-256 `2050fdf18a4346e2c47ced141f2fc65b68633fb5336d29d3616066a5603711e7`,
1074483 bytes. O manifesto registra URL, período, tamanho e política de
extração; a promoção de uma tabela de sucessões continua condicionada a uma
extração estruturada validada.

Foi revisado também o diretório oficial do estudo de Evolução da Divisão
Territorial do Brasil 1872–2010. A página descreve uma planilha de apoio, mas o
diretório público consultado disponibiliza o quadro de genealogia como PDF e
não expõe uma tabela tabular independente para ingestão. O pipeline, portanto,
mantém o PDF como `RAW_ONLY`; transformar o texto do PDF em sucessões sem uma
validação estrutural própria violaria a política `EXPLICIT_SOURCE_ONLY`.

A suíte completa foi executada com PostgreSQL real em container isolado,
incluindo os testes de integração e as migrations até `0009`. Sem as variáveis
de conexão, esses 19 testes são pulados explicitamente; isso não altera os
resultados unitários, mas o comando homologatório deve fornecer o banco.

Também foi executada a leitura do artefato oficial `DTB_2025.zip`:

```text
SHA-256: d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27
Registros municipais: 5571
UFs: 27
Campos dos Goytacazes: 3301009 / 330100
```

O parser histórico foi executado contra a planilha oficial de alterações
toponímicas municipais de 2025: 136 eventos, abrangendo 124 geocódigos. Esses
eventos preservam o mesmo geocódigo na origem e no destino; não representam
sucessões territoriais.

Também foi executada uma comparação real entre as edições DTB 2024 e 2025:

```text
DTB_2024.zip SHA-256: 218d2017cc29ff21cb6e8a0b015c40ea8f456900f95aa18f534be4ea94b473f0
DTB_2025.zip SHA-256: d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27
Municípios em cada edição: 5571
Diferenças observáveis: 3 TOPONYMIC_CHANGE, 0 CREATION, 0 EXTINCTION
```

A comparação não inferiu sucessão, fusão ou desmembramento entre códigos.

A validação nacional recém-adicionada também foi submetida a mutação dirigida:
os seis mutantes gerados para `validate_national_municipalities` morreram
(`6/6`). Isso cobre o contrato de presença das 27 UFs, mas não substitui a
medição global de mutação, que continua abaixo da meta de 95%.

A inspeção dos membros dos ZIPs oficiais confirmou que os arquivos de
“novos/extintos” publicados na DTB 2024/2025 tratam de distritos e
subdistritos, não de uma tabela municipal estruturada de sucessões. Por isso,
nenhum evento administrativo municipal foi inferido a partir deles.

Validações operacionais adicionais:

```text
DTB 2025 em escopo BRAZIL: 5571 municípios, 27 UFs, 92 municípios no RJ
Release Parquet temporária: 5571 municípios recarregados via active.json
Refresh controlado real: DTB_2025.zip promovida em staging e recarregada pelo ponteiro ativo
Refresh end-to-end pós-implementação: release `ibge-dtb-2025-final`, 5571
municípios, 27 UFs e `330100` resolvido para `3301009` após recarga do
`active.json`
API CNES com limit=250: teto observado de 20 registros por resposta
Coleta real de Campos dos Goytacazes: 1604 estabelecimentos, 1604 CNES únicos
Homologação CNES offline: 1 passed em 45,87 s com `IBGE_DTB_ARCHIVE=DTB_2025.zip`
Piloto CNES real: Campos concluído; a API ficou sem resposta ao iniciar São
Paulo após aproximadamente quatro minutos e a execução foi interrompida.
Calibração CNES real limitada: primeira página consultada com sucesso para
RJ, SP, AM, PE e RS; respostas HTTP 200, códigos municipais coerentes e
latência observada entre 0,20 s e 0,24 s por consulta.
Coleta CNES real multi-UF completa em amostra: RO `1100015` (68), AC `1200013`
(23), AM `1300029` (19), RR `1400050` (65) e PA `1500107` (172); todas as
páginas foram percorridas com sucesso, com até 1,43 s por município.
Calibração CNES real em todas as UFs: um município representativo por UF,
27/27 concluídos, 14.515 estabelecimentos percorridos; o DF (`5300108`) foi o
caso mais lento (81,41 s) e concluiu sob o timeout/retry configurado. Isso é
uma amostra nacional operacional, não uma execução integral dos 5.571
municípios.
`run_cnes` real com o mesmo escopo nacional amostral: Bronze → Silver,
consolidação de 14.515 linhas e checkpoint `COMPLETED` em 106,21 s.
Execução real do `run_cnes` completo nessa amostra: Bronze → Silver →
consolidação concluída para os cinco municípios, 347 estabelecimentos, metadata
gerada e checkpoint final em estado `COMPLETED`.
Homologação CNES real nacional integral: de 2026-10-31T02:25:39Z a
2026-10-31T03:17:35Z, 8 workers, `page_size=100`, timeout de 60 s,
`ibge-dtb-2025-full`, SHA bruto
`d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27`;
5.571 municípios, 5.571 Bronzes, 641.343 estabelecimentos, zero falhas e
zero municípios ausentes no checkpoint. A verificação independente encontrou
5.571 códigos municipais canônicos distintos, todos pertencentes à DTB e todas
as 641.343 linhas com resolução `VALID`. Assets territoriais inexistentes
continuaram explicitamente `UNAVAILABLE`.
```

O teto observado da API CNES expôs um risco de salto de registros: o offset
avançava pelo limite solicitado. A implementação foi corrigida para avançar
pelo número retornado na página, e o comportamento foi coberto por teste.

A configuração do `mutmut` foi corrigida para copiar os assets `territories/` e
inclui agora o módulo de histórico administrativo. A rodada integral continua
grande para o hardware local e foi interrompida após 739 de 4.691 mutantes na
configuração anterior. Após a ampliação do escopo, uma execução foi
interrompida após 349 de 5.337 mutantes. As rodadas dirigidas foram executadas
por grupo: a rodada consolidada anterior dos módulos IBGE registrou 615
mutantes, 284 mortos e 206 sobreviventes; as rodadas adicionais registraram
120 mortos, 57 sobreviventes e 21 sem testes associados em `refresh`. A rodada
parcial do histórico registrou 193 mortos, 156 sobreviventes e 77 não
verificados antes da interrupção. A meta de 95% ainda não foi atingida. Os
sobreviventes permanecem pendência de qualidade; não foram ocultados por
alteração artificial do escopo.

Após adicionar a asserção do timeout padrão, a consulta dirigida do módulo
`refresh.py` registrou 35 mutantes mortos e 175 sobreviventes; os 20 casos que
estavam sem associação foram reexecutados após a atualização da coleta de
testes e passaram a ser classificados. Esse resultado continua abaixo da meta
e não é apresentado como
homologação integral de mutação.

Uma rodada dirigida posterior, restrita aos módulos `run_cnes.py` e
`reference/ibge/catalog.py`, gerou 673 mutantes e foi interrompida após
406 execuções: 247 mortos, 155 sobreviventes e 4 timeouts. Os workers que
ficaram presos em mutantes do entrypoint CNES foram encerrados e a configuração
oficial completa do `mutmut` foi restaurada. O resultado é evidência parcial de
qualidade, não um score final nem uma justificativa para reduzir o escopo.
Após essa rodada, os testes de resolução legacy e da razão de código
desconhecido foram reforçados; os dois mutantes correspondentes foram mortos
em uma reexecução dirigida. O teste de timeout foi reforçado depois, mas ainda
aguardava uma nova classificação dirigida.

Essa confirmação foi obtida posteriormente para os dois mutantes de timeout:
`app.pipeline.run_cnes.x_run_cnes__mutmut_10` e
`app.pipeline.run_cnes.x_run_cnes__mutmut_13` foram classificados como mortos.
Isso melhora a cobertura dos contratos críticos, mas não altera a pendência da
meta global de 95%.
Os testes de `page_size` e dos tipos inválidos de timeout foram adicionados
depois dessa classificação e já foram refletidos em nova rodada mutante
dirigida; a suíte funcional global também os executa.
Após a cobertura dos limites mínimos válidos, os mutantes
`app.pipeline.run_cnes.x_run_cnes__mutmut_5` e
`app.pipeline.run_cnes.x_run_cnes__mutmut_14` também foram classificados como
mortos em rodada dirigida.
Os mutantes `48`, `49`, `50`, `52`, `53` e `54` de `run_cnes`, que alteravam
as chaves ou a validação da identidade IBGE no checkpoint, também morreram
após o teste com release catalogada. A mesma rodada matou os caminhos de
checkpoint inválido e o descarte indevido de `GeographicScope`.
O mutante `run_cnes__mutmut_76`, que removia o UTC do timestamp de ingestão,
foi morto após a asserção explícita do sufixo `+00:00`.

Após a validação do vínculo entre catálogo e escopo, os nove mutantes gerados
para `scope.validate_scope_catalog` foram executados e classificados como
mortos (`9/9`). A cobertura inclui tanto o aceite de um escopo materializado
pelo catálogo quanto a rejeição de município ausente, atributos divergentes e
mensagens de erro alteradas. Isso é uma evidência dirigida do contrato, não
uma aprovação da meta global de mutação.

Após a exposição do timeout no wrapper de atualização DTB, os mutantes
pendentes de `reference/ibge/refresh.py` foram reexecutados com a suíte atual.
O módulo ficou com 167 mutantes mortos, 167 sobreviventes e 119 sem testes
associados. Esse resultado é uma reclassificação dirigida do módulo, não uma
medição global; a meta de 95% continua pendente.

Depois da validação semântica dos eventos, a rodada dirigida de `historical.py`
foi repetida sobre 388 mutantes pendentes. O estado observado do módulo ficou
em 335 mortos, 274 sobreviventes, 84 sem testes associados e 112 ainda não
classificados; a ferramenta mantém alguns resultados anteriores no cache, por
isso esses números não são comparáveis a uma rodada global limpa.

Também foi executada novamente a rodada global configurada no `pyproject.toml`,
com 7.000 mutantes: 3.969 mortos, 2.286 sobreviventes, 744 sem testes
associados e 1 timeout. A taxa entre os mutantes classificáveis
(`mortos / (mortos + sobreviventes)`) foi de 63,44%. O resultado continua
abaixo da meta de 95%; sobreviventes, casos sem testes e timeout permanecem
pendências de qualidade. As medições anteriores permanecem no histórico acima
para comparação, mas esta é a medição global atual após a cobertura Gold e CLI.

Os seis mutantes da validação estrutural de `completed` no checkpoint CNES
foram reexecutados após testes unitários diretos e classificados como mortos
(`6/6`), cobrindo mensagens, condições lógicas e o caminho de aceite.

O caso de precedência do formato legado (`1330100`) também morreu na rodada
dirigida. Dois mutantes de inicialização do payload do resolvedor continuam
classificados como sobreviventes pelo `mutmut`, mesmo após asserções diretas do
objeto canônico; eles permanecem pendentes para investigação da associação ou
cache da ferramenta, sem serem contabilizados como mortos.

No executor `run_load.py`, três mutantes críticos foram exercitados em rodada
dirigida: o bloqueio de publicação vazia por padrão, o timestamp UTC e a
normalização da doença. Os dois primeiros foram classificados como mortos; o
mutante que substitui a doença normalizada por `None` continuou sobrevivente
na ferramenta, embora os testes afirmem o valor transmitido ao Bronze, Gold e
PostgreSQL. Ele permanece registrado como pendência de instrumentação/teste,
sem ser tratado como morto artificialmente.

Os contratos do cliente de Localidades foram reforçados com asserções de
ownership de sessão, normalização de URL, hierarquia administrativa, origem,
ano de referência e mensagens de erro. A rodada dirigida foi reexecutada com
os nomes completos dos mutantes; os caminhos de ownership e URL morreram, mas
alguns mutantes de parsing continuam sobrevivendo por associação incompleta da
ferramenta entre testes novos e a função mutada. Eles permanecem pendentes e
não alteram o score global declarado acima.

## Execução CNES tolerante a falhas

O executor CNES agora oferece `continue_on_error=True` e a opção de CLI
`--continue-on-error`. Nesse modo, cada município termina como `completed` ou
`failed`, com tipo e mensagem de erro no checkpoint e no metadata do lote.
Quando há municípios com falha, o snapshot recebe status `PARTIAL`; o modo
estrito continua sendo o default para preservar a compatibilidade e impedir
que uma publicação parcial seja confundida com uma carga completa.

O checkpoint também fixa esse parâmetro junto da release IBGE, do escopo, do
page size e do timeout. Municípios já concluídos são lidos da Bronze validada,
sem nova consulta à API.

Os defaults de `.env.example` e do próprio Compose permitem iniciar o
PostgreSQL local com credenciais de desenvolvimento explícitas (`nss`/`nss`)
e banco `situacao_saude`; nenhuma credencial de produção é versionada.

## Compatibilidade preservada

- O dicionário `MUNICIPIOS_RJ` continua aceito pelas interfaces legadas.
- Sem `--catalog-root`, os executores continuam usando o recorte RJ original.
- As chamadas existentes de `aggregate_file`, `run_load` e `fetch_estabelecimentos`
  continuam válidas.
- A suíte anterior permaneceu verde após as alterações.

## Pendências para declarar suporte nacional de produção

## Matriz de completude da execução

| Requisito | Evidência atual | Situação |
| --- | --- | --- |
| Catálogo nacional versionado em Parquet | DTB 2025 real, 5.571 municípios, manifesto, hash bruto e hash lógico | Concluído no código |
| Crosswalk 6→7 e validação de UF | Testes de resolução, homônimos, UF divergente e Gold em cinco UFs | Concluído |
| Recorte RJ compatível | Defaults legados e suíte de regressão verde | Concluído |
| Seleção por município, UF e Brasil | CLI, `GeographicScope` e smoke nacional com 27 UFs | Concluído |
| CNES nacional offline/reiniciável | 5.571 municípios simulados, sessão reutilizada e checkpoint validado | Concluído |
| Publicação PostgreSQL multi-UF | Migrations reais, fatos, dimensões, FKs e linhagem RJ/SP | Concluído no modo sintético |
| Histórico de sucessões municipais | Série DTB 2011–2025 e planilha oficial 1872–2010 processáveis; 2.149 mudanças toponímicas observáveis | Parcial; sucessões/desmembramentos com código de origem pendentes |
| CNES real em todas as UFs | 5.571/5.571 municípios, 5.571 Bronzes, 641.343 estabelecimentos, zero falhas | Concluído |
| Reconciliação epidemiológica nacional | SINAN DENG 2024 público processado e publicado nacionalmente; não é dado autorizado privado | Homologado com fonte pública; reconciliação autorizada ainda pendente |
| Mutação ≥95% | Medição global mais recente: 78,51% entre 7.865 mutantes classificáveis | Pendente de qualidade |

O CNES nacional foi homologado, mas esta execução ainda não é uma homologação
epidemiológica nacional completa. Permanecem necessários:

1. Distribuir o ZIP oficial bruto conforme a política de artefatos do ambiente;
   o código de atualização já mantém cache bruto, SHA-256 e promoção atômica,
   enquanto o repositório mantém checksum e fixture representativa, não o ZIP
   integral.
2. Normalizar e promover uma fonte histórica oficial de criação, extinção e
   sucessão administrativa. O IBGE publica a [genealogia municipal histórica
   1872–2010](https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/evolucao_da_divisao_territorial_do_brasil/evolucao_da_divisao_territorial_do_brasil_1872_2010/municipios_genealogia_e_alteracao_de_nome_e_grafia.pdf)
   em PDF, mas essa publicação ainda não é um crosswalk tabular
   integrado ao NSS e não cobre diretamente 2011–2025. O contrato e o parser
   para eventos explícitos já existem; nenhum evento é inferido por nome ou
   proximidade geográfica. A comparação real DTB 2024/2025 foi validada e
   gerou somente três eventos toponímicos, o que não equivale a um crosswalk
 histórico completo.
   A inspeção do diretório oficial de evolução territorial também não encontrou
   um arquivo tabular de genealogia equivalente: a publicação histórica está
   disponível como PDF, enquanto as alterações recentes são disponibilizadas
   nas edições anuais da DTB e nas planilhas toponímicas já processadas pelo
   pipeline. Por isso, transformar o PDF em sucessões automaticamente ainda
   não seria uma promoção segura.
3. A homologação real CNES nacional confirmou a paginação com `page_size=100`,
   timeout de 60 segundos, oito workers e checkpoint reiniciável. O snapshot
   produzido contém 641.343 estabelecimentos e zero falhas; uma nova execução
   ainda deve reutilizar as Bronzes, sem consultar novamente a API.
4. Investigação dos mutantes sobreviventes e obtenção de uma taxa de mutação
   de produção; a configuração e as rodadas dirigidas são classificáveis, mas
   a meta de 95% ainda não foi alcançada.
5. Reconciliação adicional com dados autorizados, quando disponibilizados, para
   complementar a homologação pública já executada. A cadeia pública teve
   totais reconciliados entre Silver, Gold e PostgreSQL.

## Verificação final desta execução

Após a otimização da publicação nacional e o endurecimento dos códigos
históricos, DTB, refresh, ponteiro ativo, CLI, fontes históricas e CNES, a
suíte completa com PostgreSQL de integração passou em **596 testes**, com **3 testes
pulados** e **25 warnings**.
`nix flake check --no-build` também passou; a checagem avaliou o `devShell`
Linux x86_64 e sinalizou apenas a omissão esperada de `aarch64-linux` por
incompatibilidade de sistema.

O último commit funcional desta rodada foi `0de9f7d`
(`fix(load): reject unvalidated catalog releases`), precedido pelo teste
`81dc7b1` (`test(load): cover pending catalog rejection`) e por `4a91f47`
(`fix(ibge): reject truncated national catalogs`), precedido por `95b99b0`
(`fix(ibge): reject non-ascii municipality codes`), precedido por `4cf6523`
(`fix(cnes): enforce ascii municipality codes`) e seguido do registro da
preservação histórica em `ce08236` e do teste de conversão de registros
Parquet em `0d029e6` (`test(ibge): cover mapping catalog records`), seguido
dos testes de metadados em `4d90061` e da distinção de proveniência em
`576b1c0`.

O commit `46fcf8f` (`fix(ibge): preserve historical source lineage`) corrigiu
o manifesto de eventos históricos para acumular as fontes promovidas, em vez
de sobrescrever a proveniência da promoção anterior. A suíte completa posterior
passou em 486 testes.

O commit `1e378f6` (`fix(ibge): merge annual historical lineage`) estendeu a
mesma garantia às edições anuais da DTB: fontes explícitas e diferenças anuais
agora coexistem no manifesto, com política `MIXED_EXPLICIT_AND_OBSERVABLE`.
A suíte completa posterior passou em 487 testes.

Os commits `8b26762` e `8a2d581` fortaleceram o contrato de registro de releases
no PostgreSQL. Uma rodada dirigida limpa dos 59 mutantes de
`_register_catalog_release()` matou **59/59**. A suíte completa posterior passou
em 488 testes.

Os commits `44abf2c` e `89c5402` fortaleceram os contratos históricos de
identidade de evento e armazenamento de fontes. A rodada dirigida posterior
matou mais **10 mutantes históricos**, incluindo os quatro remanescentes
selecionados para identidade e caminho canônico. Essa evidência é complementar
e não substitui a baseline global limpa. A suíte completa posterior passou em
**490 testes**.

O commit `72b4774` (`fix(scope): enforce ascii municipality scope hashes`)
passou a rejeitar algarismos Unicode no hash do escopo e reforçou os contratos
de seleção por UF, Brasil inteiro e município inválido. A suíte completa
posterior passou em **495 testes**; a execução dirigida de escopo matou os
mutantes relevantes de seleção e serialização, mantendo separados os casos
equivalentes para entradas exclusivamente ASCII.

A rodada global de mutação limpa, executada após as coberturas de catálogo,
publicação, escopo e resolução e antes de `d7439d4`, produziu 7.338 mutantes:
5.430 mortos, 1.815
sobreviventes, 92 sem testes associados e 1 timeout. Considerando mortos,
sobreviventes e timeout, a taxa atual é **74,94%** (5.430 / 7.246). A meta de
95% permanece pendente; a rodada não foi artificialmente restringida nem usada
para reclassificar sobreviventes como equivalentes.

Uma nova rodada global foi executada após os contratos de manifesto, ponteiro
ativo e esquemas Parquet. Ela produziu **7.375 mutantes: 5.536 mortos, 1.745
sobreviventes, 93 sem testes e 1 timeout**. Entre os 7.281 mutantes
classificáveis, a taxa foi **76,03%** (5.536 / 7.281). Esta é a medição global
mais recente; a meta de 95% continua pendente sem redução artificial do escopo.

Como verificação dirigida posterior, os 30 sobreviventes então associados a
`reference/ibge/catalog.py` foram reexecutados após os três commits de testes:
22 morreram e 8 continuaram sobrevivendo. A execução dirigida regenerou 115 mutantes ainda
não verificados em outros módulos; por isso ela não substitui a última rodada
global limpa acima.

O commit `95b99b0` tornou explícita a rejeição de códigos municipais não ASCII
e adicionou regressão para algarismos Unicode; a suíte completa posterior passou
em 485 testes.

O commit `4a91f47` também passou na suíte integral: uma candidata nacional
truncada, mesmo contendo todas as UFs, agora é rejeitada quando possui menos de
5.500 municípios.

O commit `81dc7b1` adicionou a defesa de publicação: releases IBGE com
`validation_status` diferente de `VALIDATED` são rejeitadas antes do registro
na transação PostgreSQL. A suíte completa posterior passou em 486 testes.

O commit `b3cfda6` (`test(ibge): assert invalid resolution context`) adicionou
regressão para preservar o contexto de entradas não numéricas. Os dois
mutantes restantes dessa inicialização foram classificados como equivalentes.

O commit `72b4774` (`fix(scope): enforce ascii municipality scope hashes`)
adicionou a rejeição de dígitos Unicode no identificador de escopo e testes
exatos para seleção municipal, por UF e Brasil inteiro.

O commit `d7439d4` (`fix(ibge): clean failed archive promotions`) tornou a
limpeza do arquivo temporário incondicional quando o download da DTB falha na
troca atômica, incluindo regressão para erro de `os.replace`. A suíte completa
posterior passou em **496 testes**. O grafo Alembic permaneceu com head `0009`
e `nix flake check --no-build` passou novamente.

O commit `ebe81fd` (`test(ibge): cover official toponymic schema`) adicionou
uma fixture contratual com os cabeçalhos e colunas extras publicados na planilha
de Alterações Toponímicas Municipais 2025. O parser converte o registro para
evento toponímico mantendo o mesmo código de origem e destino. A suíte completa
posterior passou em **497 testes**; isso valida o formato da fonte, mas não
transforma a planilha toponímica em sucessão territorial.

O commit `47a5050` (`test(ibge): cover national catalog boundary`) adicionou
o teste de fronteira para 5.500 municípios e a mensagem completa de rejeição de
catálogos nacionais abaixo do mínimo. Os dois mutantes dessa fronteira morreram
na rodada dirigida. A suíte completa posterior passou em **498 testes**.

Os commits mais recentes desta continuação foram `44abf2c`
(`test(ibge): strengthen historical source contracts`) e `89c5402`
(`test(ibge): assert historical artifact identity`).

O estado histórico permanece deliberadamente parcial: a fonte oficial de
genealogia 1872–2010 preservada pelo pipeline é um PDF documental, sem tabela
estruturada de sucessões. Portanto, ela continua em `RAW_ONLY` e não produz
crosswalk histórico automático. A série anual DTB registra apenas diferenças
observáveis entre edições consecutivas.

### Atualização final desta continuação — 31/10/2026

O commit `627e9c1` (`test(load): cover Gold metadata forwarding`) adicionou
regressão para garantir que as métricas do `metadata.json` da Gold sejam
encaminhadas à publicação PostgreSQL. A rodada dirigida do contrato de
`run_load` matou **13 mutantes relevantes** (incluindo fonte/ano, colunas
selecionadas, lote CNES, escopo padrão e métricas de qualidade); essa evidência
é complementar e não altera a baseline global de 74,94%.

O commit `44cfbdc` (`test(sinan): cover missing declared municipality uf`)
adicionou cobertura para UF declarada ausente (`pd.NA`) durante a resolução
municipal. O mutante que deixava esse valor sem normalização morreu na rodada
dirigida; a variante que troca `None` por string vazia foi classificada como
equivalente porque ambas são tratadas como ausência pelo contrato do catálogo.

A validação integral posterior, usando o PostgreSQL de integração local,
passou em **500 testes**, com **3 testes pulados** e **25 warnings**. O teste
de contrato usa fixtures locais e não depende da disponibilidade do IBGE ou do
CNES durante a execução normal.

O commit `88f4949` (`fix(scope): require national catalog for all brazil`)
fechou uma lacuna no caminho de execução: `--all-brazil` agora exige que o
catálogo carregado contenha todas as UFs e atenda ao limite mínimo de validação
nacional antes de materializar o escopo. A mesma regra foi aplicada a `run.py`,
`run_load.py` e `run_cnes.py`; seleções por município ou UF não foram ampliadas
artificialmente. A suíte integral posterior passou em **501 testes**, com **3
testes pulados** e **25 warnings**, e `nix flake check --no-build` passou.

O commit `5d5c055` (`test(scope): cover national cli guard`) adicionou testes
diretos para o encaminhamento de `require_national=True` em `run.py` e
`run_cnes.py`, complementando a cobertura já existente de `run_load.py`. A
suíte integral posterior passou em **503 testes**, com **3 testes pulados** e
**25 warnings**.

O commit `0c2d440` (`test(sinan): cover catalog version reprocessing`) completou
o contrato do atualizador SINAN: uma alteração apenas no identificador da
release ou apenas no SHA do catálogo força reprocessamento, enquanto arquivo,
`catalog_id` e SHA idênticos permanecem `UNCHANGED`. Os **3 mutantes**
selecionados desse vínculo morreram. A suíte integral posterior passou em
**522 testes**, com **3 testes pulados** e **25 warnings**.

O commit `3d28740` (`test(load): cover publication scope types`) adicionou
regressões para `MUNICIPALITIES`, `UFs` e `BRAZIL` no contrato de publicação,
além da mensagem exata para escopo inválido. Os **6 mutantes** selecionados
desse contrato morreram. A suíte integral posterior passou em **525 testes**,
com **3 testes pulados** e **25 warnings**.

O commit `9f39029` (`test(cnes): harden checkpoint validation contracts`)
reforçou as invariantes do checkpoint CNES para `rows`, SHA-256, tipos de
entradas e mensagens de erro. A rodada dirigida matou **7 mutantes** previamente
selecionados nesses validadores. A suíte integral posterior passou em **513
testes**, com **3 testes pulados** e **25 warnings**.

O commit `8c84ac7` (`test(cnes): cover error classification contract`) adicionou
uma matriz explícita para as seis classes de falha do CNES. Os **8 mutantes**
selecionados do classificador morreram. A suíte integral posterior, com
PostgreSQL de integração, passou em **519 testes**, com **3 testes pulados** e
**25 warnings**.

O commit `8e4e730` (`test(load): cover geographic scope hash contract`) adicionou
regressões para aceitar o hash canônico do escopo geográfico e rejeitar um hash
divergente antes de abrir a transação. Os **3 mutantes** selecionados desse
contrato morreram. A suíte integral posterior passou em **527 testes**, com
**3 testes pulados** e **25 warnings**.

O commit `555ff4e` (`feat(ibge): record release promotion timestamp`) adicionou
`promoted_at` ao manifesto das releases promovidas. O campo é preenchido nas
novas promoções e permanece opcional na leitura, preservando a compatibilidade
com manifests históricos.

A validação pós-mudança, executada com o PostgreSQL de integração local, passou
em **530 testes**, com **3 testes pulados** e **25 warnings**. `nix flake check
--no-build` também passou.

O commit `055dfb5` (`fix(ibge): validate promotion timestamp`) fechou a
validação do novo campo: timestamps presentes no manifesto precisam ser
ISO-8601; a ausência continua válida para releases legadas. O contrato foi
testado para valores textuais inválidos e tipos não textuais.

O commit `18d4063` (`fix(ibge): require timezone in promotion metadata`)
completou essa validação exigindo timezone explícito, evitando timestamps
locais ambíguos.

A rodada dirigida de mutação executada com o identificador privado correto do
`mutmut` matou **34/34 mutantes** de `storage._validate_metadata()`. A evidência
abrange as validações de hashes, status da release e timestamp de promoção; ela
é específica do contrato e não é apresentada como a taxa global de mutação.

O commit `da5ebff` (`test(ibge): harden active pointer errors`) adicionou
regressões para ponteiro ausente, JSON inválido e `catalog_id` não textual. A
rodada dirigida correspondente matou **4 de 5 mutantes** selecionados; o
sobrevivente restante é equivalente no ambiente Linux por usar o encoding UTF-8
implícito de `Path.read_text(encoding=None)`. A suíte integral posterior passou
em **534 testes**, com **3 testes pulados** e **25 warnings**.

O commit `b0bef0a` (`test(ibge): cover fresh release directory creation`)
adicionou uma instalação em árvore ainda inexistente e matou os **2 mutantes**
selecionados de criação de diretórios em `write_manifest()`. As variantes de
`promote_active()` que removem `parents=True` foram mantidas como equivalentes:
essa função chama `_load_release()` antes de criar o ponteiro, portanto o pai já
precisa existir para a release ser válida.

O commit `7b894ca` (`test(ibge): assert canonical parquet schemas`) adicionou
assertions explícitas para as colunas de `municipalities.parquet`, `ufs.parquet`
e `code_crosswalk.parquet`. A rodada dirigida matou **8 mutantes** de nomes de
colunas; seis mutantes restantes alteram somente parâmetros de serialização que
não mudam o contrato observado ao reler o Parquet.

Na análise dirigida de `InMemoryMunicipalityCatalog.resolve()`, os dois
mutantes sobreviventes foram classificados como equivalentes: eles alteram
somente inicializações substituídas antes de qualquer retorno observável nos
caminhos de formato inválido. Os caminhos de resolução válida, código
desconhecido, UF divergente e referência histórica continuam cobertos por
resultados distintos.

O commit `ba7a706` (`test(ibge): cover localidades parser contracts`) reforçou
o cliente da API de Localidades: o teste agora verifica a preservação do nome
municipal e exige a mensagem completa para registros sem campos
administrativos. A rodada dirigida matou os **3 mutantes** restantes desse
parser (`_parse`), elevando a medição global mais recente para **5.539 mortos
entre 7.281 mutantes classificáveis (76,07%)**. Essa taxa continua abaixo da
meta de 95%; os mutantes equivalentes e os módulos ainda não cobertos seguem
registrados como pendências.

O commit `b2dca26` (`fix(ibge): make historical events deterministic`) passou a
ordenar eventos históricos por data de vigência e `event_id` antes de gravar o
Parquet. A regressão compara duas entradas equivalentes em ordens opostas e
confirma a mesma materialização, reforçando a reprodutibilidade do histórico.

O commit `a5ea378` (`feat(ibge): download historical sources safely`) adicionou
a aquisição HTTP controlada de fontes históricas documentais. O download usa
arquivo temporário, fecha a resposta/sessão, valida SHA-256 quando fornecido e
só então promove o artefato com `extraction_status=RAW_ONLY`; uma divergência
de hash não deixa fonte parcial no catálogo. Isso melhora a proveniência sem
converter automaticamente o PDF de genealogia em sucessões.

A rodada global posterior, regenerada após a aquisição histórica, produziu
**7.459 mutantes: 5.586 mortos, 1.779 sobreviventes, 93 sem testes e 1
timeout**. Entre os **7.365 mutantes classificáveis**, a taxa foi **75,85%**.
O aumento de escopo explica a diferença em relação à medição anterior; a
execução não excluiu módulos nem tratou sobreviventes equivalentes como mortos.

A suíte integral posterior passou em **535 testes**, com **3 testes pulados** e
**25 warnings**. `nix flake check --no-build` também passou após essa mudança.

Após a regressão de quarentena de UF, a suíte integral foi executada novamente:
**540 testes passaram, 3 foram pulados e 25 warnings foram emitidos**.

O commit `213c94c` (`test(sinan): cover catalog normalization contract`)
adicionou uma regressão direta para o caminho que recebe um
`InMemoryMunicipalityCatalog` em `normalize_municipality_codes()`. A rodada
dirigida matou **4 de 5 mutantes** previamente sobreviventes; o restante é
equivalente porque as entradas válidas já são exclusivamente numéricas.

O commit `585450d` (`test(sinan): assert UF mismatch quarantine`) adicionou um
caso explícito em que o código municipal resolve no catálogo, mas a UF da
fonte diverge. A Gold mantém o resultado vazio e não substitui a divergência
por uma UF canônica; o mutante que força o fallback para a UF da fonte é
inalcançável para entradas válidas porque a resolução já rejeita o registro.

O commit `fdd967b` (`test(run-load): block UF mismatch publication`) cobriu o
segundo bloqueio da publicação com catálogo ativo: `run_load.py` agora possui
regressão para `uf_mismatch_rows > 0`. A rodada dirigida matou **3 mutantes**
desse caminho (`_run_load`), garantindo que a carga não abra conexão nem
publique uma Gold territorialmente inconsistente.

O commit `093add6` (`test(cnes): harden checkpoint artifact validation`)
completou a matriz de invariantes do checkpoint CNES. Foram adicionados casos
para caminho Bronze não textual ou vazio, hash SHA-256 hexadecimal em maiúsculas
e caracteres fora do alfabeto hexadecimal. Os **5 mutantes** direcionados
correspondentes morreram, incluindo variantes que aceitavam caminhos inválidos
ou rejeitavam hashes válidos em maiúsculas. A suíte específica do executor CNES
passou em **59 testes**.

Essa evidência é complementar à baseline global: a última rodada global limpa
continua sendo a de **7.459 mutantes**, com **5.586 mortos**, **1.779
sobreviventes**, **93 sem testes** e **1 timeout**; mutantes dirigidos
posteriores não devem ser somados a essa taxa sem uma nova rodada global limpa.

Os commits `2300c77` (`fix(ibge): validate complete release artifacts`) e
`46a4ddf` (`test(ibge): cover incomplete release artifacts`) fecharam uma
lacuna na reutilização idempotente de releases. O refresh agora exige a
presença de `manifest.json`, `municipalities.parquet`, `ufs.parquet` e
`code_crosswalk.parquet` antes de reutilizar uma release existente; há uma
regressão para cada artefato ausente. A tentativa de mutação dirigida desse
trecho foi invalidada por um mutante que alterou deliberadamente o manifesto
do cenário de teste e falhou na pré-condição; ela não é contabilizada como
mutante morto.

A suíte integral posterior, executada com PostgreSQL de integração local, passou
em **544 testes**, com **3 testes pulados** e **25 warnings**. `nix flake check
--no-build` permanece como verificação adicional do ambiente reprodutível.

Após os commits de integridade da release e o ajuste dos fixtures de manifesto,
a suíte integral foi repetida com PostgreSQL local: **547 testes passaram, 3
foram pulados e 25 warnings foram emitidos**.

A nova rodada global limpa de mutação, executada após a validação de releases
completas, produziu **7.475 mutantes: 5.608 mortos, 1.773 sobreviventes, 93
sem testes e 1 timeout**. Entre os **7.381 mutantes classificáveis**, a taxa
foi **75,98%**. A meta de 95% continua pendente; esta medição substitui a
baseline global anterior para fins de acompanhamento e não reduz o escopo de
módulos configurado no `pyproject.toml`.

O commit `096b384` (`test(ibge): guard logical release identity`) adicionou a
regressão para o caso em que o mesmo `catalog_id` e o mesmo SHA do artefato
bruto reaparecem com conteúdo lógico diferente. A promoção é rejeitada antes
de substituir a release, e o mutante dirigido que invertia essa comparação
morreu. A suíte integral posterior passou em **548 testes**, com **3 pulados**
e **25 warnings**.

O commit `f13ff22` (`test(ibge): assert canonical release hashing`) adicionou
um digest fixo para `_records_sha256()`, cobrindo ordem dos registros, Unicode
e separadores JSON. Na rodada dirigida, **3 de 4 mutantes** selecionados
morreram; o sobrevivente que substitui `ensure_ascii=False` por `None` é
equivalente no comportamento do serializador Python usado pelo projeto. A
suíte específica do contrato passou em **1 teste**.

O commit `4f1d0b0` (`test(ibge): cover administrative history parser`) ampliou
as regressões do parser de eventos administrativos para formato não suportado,
colunas ausentes, fonte vazia, data inválida e mensagens de linha para códigos
ou tipos inválidos. A rodada dirigida matou o mutante que removia a mensagem do
tipo inválido; seis variantes que apenas retiravam formatos já permitidos foram
classificadas como equivalentes porque continuam rejeitando o formato `.txt`.
A suíte integral posterior passou em **553 testes**, com **3 pulados** e **25
warnings**.

O commit `9ed4667` (`test(ibge): cover toponymic history parser`) adicionou
regressões para formato não suportado, esquema incompleto, fonte vazia, data
inválida e nomes ausentes na planilha de alterações toponímicas. A rodada
dirigida matou **2 de 8 mutantes** selecionados; as seis variantes restantes
apenas retiravam extensões permitidas e continuavam rejeitando o formato de
teste não suportado. A suíte integral posterior passou em **558 testes**, com
**3 pulados** e **25 warnings**.

O commit `7b30f34` (`test(ibge): assert annual event lineage`) reforçou a
derivação observável entre edições DTB: criações, extinções e mudanças
toponímicas agora têm regressões para `event_id`, `source_name` e
`target_name`, além da garantia de que nenhuma sucessão é inferida. Os **5
mutantes** direcionados selecionados morreram. A suíte integral permaneceu em
**558 testes passantes**, com **3 pulados** e **25 warnings**. Essa medição de
mutação é dirigida e não altera a baseline global limpa de 7.475 mutantes.

O commit `6b163e5` (`test(ibge): verify historical promotion idempotence`)
adicionou regressões para promover a mesma fonte sem duplicar eventos ou
linhagem e para rejeitar alteração de um evento já registrado sob o mesmo
`event_id`. Os **8 mutantes** selecionados do merge histórico morreram. A
suíte integral posterior passou em **560 testes**, com **3 pulados** e **25
warnings**.

O commit `0a15030` (`test(ibge): cover historical source acquisition lifecycle`)
adicionou regressões para identificador inválido, fechamento da sessão criada
internamente, fechamento da resposta HTTP e descarte do artefato temporário
quando o SHA-256 diverge. Na rodada dirigida, **5 de 7 mutantes** selecionados
morreram; dois sobreviventes não produziram diferença observável nos contratos
atuais. A suíte integral posterior passou em **564 testes**, com **3 pulados**
e **25 warnings**.

O commit `fa190c5` (`test(ibge): preserve historical parquet round trips`)
adicionou uma regressão direta para leitura do Parquet histórico, preservando
`event_id`, nomes, códigos, fonte e campos opcionais, além do comportamento de
arquivo ausente. Os **9 mutantes** selecionados de `_read_events()` morreram.
A suíte integral posterior passou em **565 testes**, com **3 pulados** e **25
warnings**.

O commit `39014f0` (`test(ibge): preserve historical reference errors`)
completou o contrato de validação das edições de origem e destino: os erros
permanecem distintos e a exceção agregada conserva todas as referências
inválidas. Os **3 mutantes** direcionados restantes desse contrato morreram.
A suíte integral posterior passou em **566 testes**, com **3 pulados** e **25
warnings**.

O commit `6bbc6a0` (`feat(ibge): require historical source provenance`)
passou a exigir `source_url` e `reference_period` tanto na aquisição quanto na
promoção de fontes históricas. Foram adicionadas regressões para os dois
campos ausentes, impedindo artefatos `RAW_ONLY` sem origem auditável. A suíte
integral posterior passou em **570 testes**, com **3 pulados** e **25 warnings**.

O commit `236acfc` (`fix(ibge): reject malformed historical manifests`)
passou a rejeitar explicitamente manifests com `sources` que não seja um mapa
de objetos na preservação de fontes ou uma lista de objetos no histórico de
eventos. Foram adicionadas regressões para os dois caminhos, evitando perda
silenciosa de linhagem. A suíte integral posterior passou em **572 testes**,
com **3 pulados** e **25 warnings**.

O commit `b7a4e0c` (`test(ibge): cover historical event shapes`) ampliou o
contrato de `write_events()` para todos os tipos suportados e para ausência de
códigos obrigatórios em extinções, sucessões e renomeações. Na rodada dirigida,
**2 de 3 mutantes** selecionados morreram; a variante restante apenas remove um
tipo do conjunto de validação em um caso que ainda possui os dois códigos
obrigatórios, sendo equivalente nesse caminho. A suíte integral posterior
passou em **576 testes**, com **3 pulados** e **25 warnings**.

O commit `e297778` (`fix(sinan): normalize missing UF in quality metrics`)
corrigiu um erro real na reconciliação Gold: `pd.NA` em `SG_UF_NOT` agora é
tratado como UF ausente antes de chamar o catálogo, evitando
`TypeError: boolean value of NA is ambiguous`. O teste também verifica a
contagem de múltiplas linhas resolvidas, inválidas, fora do escopo e divergentes;
os **5 mutantes** selecionados morreram. A suíte integral posterior passou em
**577 testes**, com **3 pulados** e **25 warnings**.

O commit `21b8195` (`fix(sinan): reject malformed source metadata`) passou a
validar que o `metadata.json` da Silver seja um objeto antes de consultar
doença e ano. A regressão cobre uma lista JSON inválida e evita falha indireta
durante a Gold. A suíte integral posterior passou em **578 testes**, com **3
pulados** e **25 warnings**.

O commit `6fd95ec` (`fix(run-load): validate catalog gold metrics`) fechou a
reconciliação da publicação catalogada: `run_load.py` agora exige as sete
métricas de qualidade da Gold, rejeita valores booleanos, não inteiros ou
negativos e mantém o bloqueio para resoluções municipais inválidas ou UF
divergente. Foram adicionadas regressões para metadata incompleto e métrica
com tipo inválido, além da atualização dos cenários catalogados existentes.
A suíte integral passou em **580 testes**, com **3 pulados** e **25 warnings**;
`nix flake check --no-build` também passou. A baseline global de mutação não
foi recalculada nesta etapa.

Após `6fd95ec`, a rodada dirigida dos **12 mutantes** novos do caminho de
validação de métricas em `run_load.py` (`mutmut_249` a `mutmut_260`) matou
todos. Essa medição é complementar: a rodada global limpa continua sendo a
baseline registrada no backlog.

O commit `4307e6c` (`fix(run-load): reconcile gold quality counts`) adicionou
uma segunda barreira de integridade: `source_rows` deve ser exatamente a soma
de `resolved_rows` e `discarded_rows`, e a redução por agregação não pode
exceder as linhas resolvidas. A regressão cobre metadata aritmeticamente
inconsistente. A suíte integral passou em **581 testes**, com **3 pulados** e
**25 warnings**.

Na rodada dirigida posterior, os **20 mutantes** novos dessa reconciliação
(`mutmut_261` a `mutmut_280`) morreram. A contagem global exibida pelo
mutmut não foi usada como baseline, pois a execução foi seletiva e o cache
contém resultados de rodadas anteriores.

O commit `3707994` (`fix(run-load): verify gold lineage`) adicionou a
verificação de que a Gold foi gerada pela mesma release IBGE, hash de release e
escopo geográfico da publicação. Metadata ausente ou divergente agora bloqueia
a carga, evitando linhagem falsa em PostgreSQL. Foram adicionadas regressões
para release antiga e escopo diferente. A suíte integral passou em **583
testes**, com **3 pulados** e **25 warnings**. Na rodada dirigida, os
mutantes substantivos desse contrato morreram; sobreviventes restantes são
variantes de logging ou de argumentos sem efeito observável no contrato atual.

O commit `7ef49b5` (`fix(run-load): validate gold execution identity`) passou
a exigir que a Gold catalogada declare a mesma doença, ano de origem e destino
`serving` da execução. A regressão cobre uma doença divergente, evitando que
uma publicação reutilize uma Gold semanticamente incompatível. A suíte integral
passou em **584 testes**, com **3 pulados** e **25 warnings**.

O commit `f3a0b02` (`fix(ibge): reject malformed annual history manifests`)
corrigiu uma perda silenciosa de linhagem em `promote_annual_dtb_events()`:
o campo `sources` agora precisa ser uma lista de objetos, como já ocorria
nos caminhos administrativo e documental. A regressão cobre manifesto anual
com estrutura inválida. A suíte integral passou em **585 testes**, com **3
pulados** e **25 warnings**.

Foi feita uma verificação adicional da fonte oficial de genealogia
1872--2010, baixada temporariamente do FTP do IBGE: o artefato possui 97
páginas, mas o texto extraído por `pypdf` apresenta colunas embaralhadas e
caracteres invertidos, inclusive nos geocódigos. Como essa saída não permite
provar relações de sucessão linha a linha, a fonte continua corretamente
preservada como `RAW_ONLY`; nenhuma sucessão foi inferida ou promovida.

O commit `3accdea` (`fix(ibge): validate annual history policies`) também
passou a rejeitar `inference_policies` que não seja uma lista de textos não
vazios no manifesto histórico anual. A regressão cobre uma política serializada
como string. A suíte integral passou em **586 testes**, com **3 pulados** e
**25 warnings**.

O commit `4e456bf` (`fix(ibge): validate historical source lineage`)
centralizou a validação mínima das entradas `sources`: cada fonte histórica
promovida precisa declarar `reference_year`, `source_path` e um SHA-256
hexadecimal válido. A regressão cobre uma fonte sem SHA. A suíte integral
passou em **587 testes**, com **3 pulados** e **25 warnings**.

O commit `41437ad` (`fix(ibge): validate documentary source manifests`)
estendeu a validação ao manifesto documental da genealogia: cada entrada
`RAW_ONLY` agora precisa manter identidade, URL, caminho, período, SHA-256,
tamanho positivo e status de extração compatível. A regressão cobre entrada
documental sem URL. A suíte integral passou em **588 testes**, com **3 pulados**
e **25 warnings**.

O commit `fdb0786` (`fix(ibge): require release provenance metadata`)
endureceu o manifesto das releases principais: ano de referência, nome da
fonte, URL e `retrieved_at` ISO-8601 com timezone agora são obrigatórios,
além dos hashes e status já validados. Foram adicionadas regressões para
campos ausentes e timestamps inválidos. A suíte integral passou em **594
testes**, com **3 pulados** e **25 warnings**.

## Verificação global de mutação

Foi executada a rodada completa com `nix develop --command mutmut run`. O
processo terminou com código de saída zero após processar **7.791 mutantes**:

- **5.885 mortos**;
- **1.812 sobreviventes**;
- **93 sem testes associados**;
- **1 timeout**.

O resultado confirma que a suíte detecta uma parcela relevante das alterações,
mas a taxa global permanece abaixo da meta de 95% definida no projeto. A
medição também exibiu o aviso de que um fixture CSV foi alterado desde uma
rodada anterior; portanto, os números devem ser tratados como baseline
operacional da branch, e não como evidência de aprovação integral da meta.
Os contratos críticos de catálogo, escopo, linhagem e publicação continuam
complementados pelas rodadas dirigidas documentadas neste relatório.

Ao final, `nix flake check --no-build` passou novamente e a árvore de trabalho
permaneceu limpa.

O commit `5dc9822` (`fix(ibge): require historical event provenance`) reforçou
o contrato do histórico: eventos sem `event_id` ou sem fonte textual agora são
rejeitados antes da materialização em Parquet. A regressão correspondente
passou junto com os **71 testes** de `tests/test_ibge_historical.py`.

Após essa alteração, a suíte integral com PostgreSQL passou em **596 testes**,
com **3 pulados** e **25 warnings**. O teste de ambiente continuou usando as
mesmas migrations e os bancos temporários configurados no `flake.nix`.

Também foi repetida a homologação nacional com o ZIP oficial `DTB_2025.zip`,
baixado temporariamente do FTP do IBGE. O artefato tinha SHA-256
`d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27`; os três
testes de `tests/test_national_scope.py` passaram, confirmando **5.571
municípios**, resolução Gold em múltiplas UFs e reconciliação sintética de uma
linha por município. O ZIP não foi incorporado ao repositório.

O commit `474c39b` (`test(ibge): cover malformed history source maps`) adicionou
regressões para manifestos históricos cujo campo `sources` é nulo, textual ou
lista. Os **74 testes** do histórico passaram; na rodada dirigida do mutmut,
1 dos 3 mutantes selecionados desse contrato morreu e 2 permaneceram como
variantes ainda não distinguidas pela suíte.

O commit `cf39978` (`test(ibge): distinguish historical manifest errors`)
adicionou ainda o caso de SHA-256 ausente e tornou mais específico o contrato
da mensagem de mapa inválido. O conjunto histórico passou em **75 testes**.

Uma repetição dirigida inicialmente reutilizou resultados antigos do mutmut.
Após mover o cache gerado para `/tmp` e executar em cache limpo, os dois
mutantes de mensagem/estrutura foram reexecutados e **ambos morreram**. O
resultado anterior foi, portanto, classificado como artefato de cache e não
como falha da cobertura atual.

O commit `ca10257` (`feat(ibge): parse historical municipality workbook`)
adicionou suporte à planilha oficial `pop_mun_TUR_1872_a_2010.xls`. O parser
promove somente mudanças toponímicas com o mesmo código em anos consecutivos;
descrições textuais de desmembramento continuam fora do crosswalk. A execução
contra o arquivo oficial (SHA-256
`55b8b767e21394851eae2ccf0c242e30919b867b36e2f36a67c1a4d95e6324df`) produziu
**2.149 eventos toponímicos observáveis**. Os testes históricos passaram em
**77 casos**.
URL do artefato: `https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/evolucao_da_divisao_territorial_do_brasil/evolucao_da_divisao_territorial_do_brasil_1872_2010/municipios_1872_1991/Documentacao/pop_mun_TUR_1872_a_2010.xls`.

Foi inspecionada também a malha municipal histórica de 1991. Seu DBF contém
somente `BR91POLY_I` e `NOMEMUNICP`, sem código de origem do desmembramento;
por isso ela não foi usada para fabricar relações de sucessão.

O commit `e0d96ab` (`docs(ibge): add national rollout runbook`) adicionou
[`IBGE_NATIONAL_ROLLOUT_RUNBOOK.md`](IBGE_NATIONAL_ROLLOUT_RUNBOOK.md), com o
procedimento de promoção da release, ingestão CNES reiniciável, execução SINAN
em `serving`, fallback exclusivamente local e critérios objetivos de
encerramento. O rollout continua condicionado aos gates de dados autorizados,
sucessões explícitas e mutação global.

## Baseline global de mutação atualizada

Após o parser histórico e o runbook, `nix develop --command mutmut run`
terminou com código de saída zero após processar **7.958 mutantes**:

- **6.175 mortos**;
- **1.690 sobreviventes**;
- **92 sem testes associados**;
- **1 timeout**.

Entre os **7.865 mutantes classificáveis**, a taxa foi **78,51%**. A meta
global de 95% continua pendente; o escopo da configuração não foi reduzido.

O commit `58c11f5` (`test(sinan): cover updater CLI`) adicionou testes para o
entrypoint de `update_sinan.py`, incluindo parsing de doenças/anos, manifesto,
catálogo IBGE e rejeição de argumentos inválidos. Os **16 testes** do módulo
passaram. Em rodada dirigida, os 92 mutantes de `main()` que antes estavam
como `no tests` passaram a ser exercitados: **44 morreram e 48 sobreviveram**.
Essa medição é complementar e não altera a baseline global anterior.

Após a integração do parser histórico, a suíte integral com PostgreSQL passou
em **602 testes**, com **3 pulados** e **25 warnings**. O `flake check` também
permaneceu aprovado.

## Conclusão

A fundação técnica e a integração dos caminhos principais foram implementadas
com compatibilidade para o RJ e commits semânticos por etapa. A promoção para
Brasil inteiro deve ocorrer somente após as pendências acima, especialmente a
DTB oficial versionada, os testes PostgreSQL e a validação nacional de CNES.

O backlog operacional, com dependências, prioridades, estados e critérios de
aceite, está em [`IBGE_INTEGRATION_BACKLOG.md`](IBGE_INTEGRATION_BACKLOG.md).
Na etapa final da execução, `run.py` e `run_load.py` também passaram a impor no
próprio parser da CLI a exclusividade entre município, UF e Brasil inteiro;
essa regra é coberta por regressão unitária e pelo commit `ea9c0b6`.
Mutações dirigidas de `run_load._build_parser()` → 22 de 64 mutantes
previamente sobreviventes morreram após o teste de contrato dos argumentos;
os demais continuam pendentes e não são apresentados como aprovação global.

O commit desta etapa adicionou regressões
para os defaults e falhas observáveis do CLI de `update_sinan.py`: doenças
acompanhadas por padrão, manifesto padrão, carregamento condicional do catálogo,
conversão do caminho para `Path`, erro de lista vazia e código de saída 1 em
falha de atualização. O módulo passou em **19 testes**. Na reexecução dirigida
dos 12 mutantes comportamentais selecionados, **10 morreram**; os dois
sobreviventes removem apenas texto de ajuda sem alterar o contrato operacional.

Verificação final após essa etapa: a suíte integral passou em **608 testes**,
com **3 pulados** e **25 warnings**; `nix flake check --no-build` também passou.
O branch permaneceu limpo e sincronizado com `origin/work/nss-pipeline`.

O commit `fddcbff` (`test(cnes): harden canonical municipality resolution`)
adicionou regressões para rejeitar um resultado de resolução com status inválido
mesmo quando ele carrega um município, e para preservar a identidade canônica
7 dígitos/nome no mapa CNES. O módulo passou em **61 testes**; os dois mutantes
dirigidos correspondentes morreram. A baseline global de mutação não foi
recalculada nesta etapa.

O commit `5c7b0e8` (`test(cnes): verify parallel request parameters`) cobriu o
encaminhamento de limite de página, catálogo, sessão isolada e timeout para
cada worker paralelo. O módulo passou em **62 testes** e os 6 mutantes
dirigidos correspondentes morreram.

Revalidação integral após as duas etapas CNES: **611 testes passaram**, com
**3 pulados** e **25 warnings**; `nix flake check --no-build` passou e o branch
continua limpo e sincronizado com o remoto.

Uma nova rodada global completa do mutmut, após as regressões CNES, processou
**7.958 mutantes**: **6.237 mortos**, **1.720 sobreviventes** e **1 timeout**.
Entre os 7.957 mutantes classificáveis, a taxa foi **78,38%**. A melhora em
relação à baseline anterior foi registrada, mas a meta de 95% continua aberta.

O commit `cb25975` (`test(sinan): verify source fetch contract`) adicionou a
assertiva de que o orquestrador chama `fetch_sinan` com doença e ano canônicos.
Os 4 mutantes dirigidos de argumentos desse caminho morreram. A baseline global
acima permanece a última rodada completa; esta correção foi medida apenas de
forma dirigida.

O commit `6da713a` (`test(sinan): reject invalid Gold metrics`) ampliou a
regressão de métricas Gold para tipos textual, booleano e negativo. O módulo
passou em **38 testes** e o mutante comportamental da validação de métricas
morreu.

O commit `66329bd` (`test(sinan): cover missing Gold metadata`) adicionou o
cenário de `metadata.json` ausente quando há catálogo IBGE. O módulo passou em
**39 testes** e o mutante que trocava o mapa vazio por `None` morreu.
