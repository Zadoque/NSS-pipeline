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
- Paginação CNES configurável e validada, com `page_size` registrado no
  metadata do lote; o caminho legado mantém sua chamada compatível.
- Fixação opcional de `cnes_batch_id` na Gold e nos executores SINAN, com
  rejeição de lote inexistente e registro do identificador no metadata.
- Métricas Gold de origem, resolução, descarte, redução por agregação, códigos
  inválidos, fora de escopo e divergências de UF persistidas na publicação
  PostgreSQL pela migration `0007`.
- Carregamento da release ativa protegido contra ponteiro inválido, manifesto
  incompatível, release não validada e traversal de caminho.
- Configuração do `mutmut` incluindo os assets territoriais necessários aos
  testes-base dos executores CNES.
- `flake.nix` e `flake.lock` com Python 3.12, PostgreSQL, Docker e ambiente
  virtual reproduzível.

## Validação executada

```text
nix flake check --no-build  → aprovado
pytest -q                  → 328 passed, 25 warnings
```

Os 328 testes foram executados com PostgreSQL real em container isolado,
incluindo 18 testes de integração e as migrations até `0007`.

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
3. Observar e calibrar a paginação CNES para todas as UFs; a configuração de
   `page_size` já está disponível, mas o limite operacional máximo da API ainda
   precisa ser confirmado em homologação.
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
