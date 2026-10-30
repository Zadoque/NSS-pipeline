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
  metadata do lote; o caminho legado mantém sua chamada compatível.
- Sessão HTTP CNES reutilizada durante uma execução com catálogo, mantendo
  retries e reduzindo o overhead de milhares de municípios no escopo nacional.
- Timeout de requisição CNES configurável pela API e CLI, registrado no
  metadata do lote para tornar falhas e homologações reproduzíveis.
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
- Configuração do `mutmut` incluindo os assets territoriais necessários aos
  testes-base dos executores CNES.
- `flake.nix` e `flake.lock` com Python 3.12, PostgreSQL, Docker e ambiente
  virtual reproduzível.

## Validação executada

```text
nix flake check --no-build  → aprovado
pytest -q                  → 336 passed, 20 skipped, 25 warnings
pytest -q com PostgreSQL  → 355 passed, 1 skipped, 25 warnings
pytest -q nacional + PostgreSQL → 356 passed, 25 warnings
national catalog smoke    → 5571 municípios, 27 UFs
controlled refresh smoke  → release DTB 2025 promovida e recarregada
national CNES smoke        → 5571 municípios resolvidos, 1 sessão reutilizada
```

Os 355 testes foram executados com PostgreSQL real em container isolado,
incluindo 19 testes de integração e as migrations até `0009`. Sem as variáveis
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
API CNES com limit=250: teto observado de 20 registros por resposta
Coleta real de Campos dos Goytacazes: 1604 estabelecimentos, 1604 CNES únicos
Homologação CNES offline: 1 passed em 45,87 s com `IBGE_DTB_ARCHIVE=DTB_2025.zip`
Piloto CNES real: Campos concluído; a API ficou sem resposta ao iniciar São
Paulo após aproximadamente quatro minutos e a execução foi interrompida.
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

## Compatibilidade preservada

- O dicionário `MUNICIPIOS_RJ` continua aceito pelas interfaces legadas.
- Sem `--catalog-root`, os executores continuam usando o recorte RJ original.
- As chamadas existentes de `aggregate_file`, `run_load` e `fetch_estabelecimentos`
  continuam válidas.
- A suíte anterior permaneceu verde após as alterações.

## Pendências para declarar suporte nacional de produção

Esta execução não deve ser interpretada como homologação de uma carga nacional
completa. Permanecem necessários:

1. Distribuir o ZIP oficial bruto conforme a política de artefatos do ambiente;
   o código de atualização já mantém cache bruto, SHA-256 e promoção atômica,
   enquanto o repositório mantém checksum e fixture representativa, não o ZIP
   integral.
2. Obter e promover a tabela oficial completa de criação, extinção e sucessão
   administrativa, além de definir a política temporal efetiva. O contrato e
   o parser para esses eventos já existem, mas nenhum evento é inferido sem
   fonte declarada.
3. Observar e calibrar a paginação CNES para todas as UFs; `page_size`, timeout
   e reutilização de sessão já estão disponíveis, mas o limite operacional
   máximo e a execução de todas as requisições ainda precisam ser confirmados
   em homologação.
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
