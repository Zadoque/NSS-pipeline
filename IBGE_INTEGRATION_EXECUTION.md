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
- Cliente da API de Localidades do IBGE com validação estrutural da resposta.
- Seleção por município, UF ou Brasil inteiro, mantendo o RJ como default.
- Opções CLI `--catalog-root`, `--municipios`, `--ufs` e `--all-brazil` nos
  executores SINAN.
- Derivação canônica de município e UF na Gold quando um catálogo é fornecido.
- Validação do código municipal antes da consulta CNES e derivação explícita
  do código de seis dígitos.
- Persistência de `cd_mun` canônico na Silver CNES e na dimensão de unidades,
  quando o catálogo IBGE está disponível.
- Registro configurável de disponibilidade de malhas territoriais; municípios
  sem asset permanecem `UNAVAILABLE`.
- Migration `0005` para registrar release IBGE, hash e tipo de escopo na
  publicação PostgreSQL.
- Manifesto SINAN sensível à mudança de `ibgeCatalogId` e
  `ibgeCatalogSha256`.
- Módulos IBGE incluídos no escopo do `mutmut`.
- Publicação SINAN bloqueada quando a Gold reporta código municipal inválido ou
  divergência entre UF declarada e UF canônica; municípios válidos fora do
  escopo continuam sendo contabilizados separadamente.
- `flake.nix` e `flake.lock` com Python 3.12, PostgreSQL, Docker e ambiente
  virtual reproduzível.

## Validação executada

```text
nix flake check --no-build  → aprovado
pytest -q                  → 286 passed, 25 warnings
```

Os 286 testes foram executados com PostgreSQL real em container isolado,
incluindo 17 testes de integração e a migration `0006`.

Também foi executada a leitura do artefato oficial `DTB_2025.zip`:

```text
SHA-256: d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27
Registros municipais: 5571
UFs: 27
Campos dos Goytacazes: 3301009 / 330100
```

A rodada de `mutmut` foi iniciada, mas terminou sem relatório estatístico final
ao encontrar uma falha durante a execução de um cenário mutado de CNES. O
resultado deve ser tratado como inconclusivo; não foi convertido em aprovação.

## Compatibilidade preservada

- O dicionário `MUNICIPIOS_RJ` continua aceito pelas interfaces legadas.
- Sem `--catalog-root`, os executores continuam usando o recorte RJ original.
- As chamadas existentes de `aggregate_file`, `run_load` e `fetch_estabelecimentos`
  continuam válidas.
- A suíte anterior permaneceu verde após as alterações.

## Pendências para declarar suporte nacional de produção

Esta execução não deve ser interpretada como homologação de uma carga nacional
completa. Permanecem necessários:

1. Incorporar ao processo de distribuição o ZIP oficial bruto da DTB ou um
   mecanismo de cache controlado; o repositório mantém checksum e fixture
   representativa, não o ZIP integral.
2. Alimentar a tabela histórica com os eventos oficiais de alterações
   administrativas e definir a política temporal efetiva.
3. Incorporar `resolved_rows`, `discarded_rows` e `aggregation_reduction` aos
   consumidores de auditoria; `dropped_rows` permanece preservado por
   compatibilidade.
4. Paginação e carga CNES dimensionadas e observadas para todas as UFs.
5. Investigação dos mutantes e obtenção de uma taxa de mutação válida; a
   execução atual foi inconclusiva no runner após uma falha em cenário mutado.
6. Execução nacional de homologação com dados autorizados e reconciliação dos
   totais da Silver, Gold e PostgreSQL.

## Conclusão

A fundação técnica e a integração dos caminhos principais foram implementadas
com compatibilidade para o RJ e commits semânticos por etapa. A promoção para
Brasil inteiro deve ocorrer somente após as pendências acima, especialmente a
DTB oficial versionada, os testes PostgreSQL e a validação nacional de CNES.
