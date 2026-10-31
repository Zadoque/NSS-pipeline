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
pytest -q                  → 414 passed, 25 warnings
pytest -q com PostgreSQL  → 414 passed, 25 warnings
pytest -q nacional + PostgreSQL → 414 passed, 25 warnings
national catalog smoke    → 5571 municípios, 27 UFs
controlled refresh smoke  → release DTB 2025 promovida e recarregada
controlled refresh after safe promotion → release recarregada via active.json,
  5571 municípios e SHA do ZIP confirmado
IBGE Localidades real → 5571 municípios, 27 UFs; Boa Esperança do Norte
  (`5101837`) resolvida via hierarquia de região imediata/intermediária
Refresh end-to-end da API de Localidades → release `ibge-api-2026-final`,
  5571 municípios, 27 UFs e ponteiro `active.json` recarregado com sucesso
national CNES smoke        → 5571 municípios resolvidos, 1 sessão reutilizada
```

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
Execução real do `run_cnes` completo nessa amostra: Bronze → Silver →
consolidação concluída para os cinco municípios, 347 estabelecimentos, metadata
gerada e checkpoint final em estado `COMPLETED`.
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

Também foi executada a rodada global configurada no `pyproject.toml`, com 6.257
mutantes gerados: 4.080 mortos, 1.843 sobreviventes, 332 sem testes associados
e 2 timeouts. A taxa entre os mutantes classificáveis
(`mortos / (mortos + sobreviventes)`) foi de aproximadamente 68,7%. O resultado
é a medição integral mais recente da configuração, mas ainda está abaixo da
meta de 95%; sobreviventes, casos sem testes e timeouts permanecem pendências
de qualidade.

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
| CNES nacional offline/reiniciável | 5.571 municípios simulados, sessão reutilizada e checkpoint validado | Concluído no modo offline |
| Publicação PostgreSQL multi-UF | Migrations reais, fatos, dimensões, FKs e linhagem RJ/SP | Concluído no modo sintético |
| Histórico de sucessões municipais | IBGE possui genealogia histórica 1872–2010 em PDF; não há crosswalk tabular 2011–2025 promovido | Pendente externo |
| CNES real em todas as UFs | Piloto real de Campos; execução nacional ainda não observada | Pendente externo |
| Reconciliação epidemiológica nacional | Não há dados autorizados nacionais no ambiente | Pendente externo |
| Mutação ≥95% | Última medição global: 68,7% entre mutantes classificáveis | Pendente de qualidade |

Esta execução não deve ser interpretada como homologação de uma carga nacional
completa. Permanecem necessários:

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
   proximidade geográfica.
3. Observar e calibrar a paginação CNES para todas as UFs; `page_size`, timeout,
   reutilização de sessão e checkpoint reiniciável já estão disponíveis, mas o
   limite operacional máximo e a execução de todas as requisições ainda
   precisam ser confirmados em homologação.
4. Investigação dos mutantes sobreviventes e obtenção de uma taxa de mutação
   de produção; a configuração e as rodadas dirigidas são classificáveis, mas
   a meta de 95% ainda não foi alcançada.
5. Execução nacional de homologação com dados autorizados e reconciliação dos
   totais da Silver, Gold e PostgreSQL.

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
