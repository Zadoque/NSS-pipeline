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
- Registro configurável de disponibilidade de malhas territoriais; municípios
  sem asset permanecem `UNAVAILABLE`.
- Migration `0005` para registrar release IBGE, hash e tipo de escopo na
  publicação PostgreSQL.
- Manifesto SINAN sensível à mudança de `ibgeCatalogId` e
  `ibgeCatalogSha256`.
- Módulos IBGE incluídos no escopo do `mutmut`.
- `flake.nix` e `flake.lock` com Python 3.12, PostgreSQL, Docker e ambiente
  virtual reproduzível.

## Validação executada

```text
nix flake check --no-build  → aprovado
pytest -q                  → 259 passed, 16 skipped
```

Os testes pulados são os testes de integração PostgreSQL, pois
`TEST_DATABASE_URL` não estava configurada nesta execução.

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

1. Parser e fixture versionada da DTB oficial, com SHA-256 real do artefato.
2. Tabela histórica de eventos administrativos e política temporal efetiva.
3. Relatório separado de códigos inválidos, fora do escopo e divergentes de UF
   na Gold, além do `dropped_rows` legado.
4. Paginação e carga CNES dimensionadas para todas as UFs.
5. Execução dos testes com migrations reais e PostgreSQL temporário.
6. Testes oficiais multi-UF, homônimos, Distrito Federal e município recém-criado.
7. Investigação dos mutantes e obtenção de uma taxa de mutação válida.
8. Execução nacional de homologação com dados autorizados e reconciliação dos
   totais da Silver, Gold e PostgreSQL.

## Conclusão

A fundação técnica e a integração dos caminhos principais foram implementadas
com compatibilidade para o RJ e commits semânticos por etapa. A promoção para
Brasil inteiro deve ocorrer somente após as pendências acima, especialmente a
DTB oficial versionada, os testes PostgreSQL e a validação nacional de CNES.
