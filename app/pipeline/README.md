# Pipeline SINAN/CNES/IBGE

Esta pasta contém o domínio e os executores da pipeline. O README da raiz
explica instalação e operação geral; este documento explica os contratos das
camadas, o layout dos artefatos, o comportamento dos módulos e a sequência de
execução.

## Arquitetura

```text
                         catálogo IBGE versionado
                        /          |             \
SINAN/PySUS ──> Bronze ──> Silver ──> Gold ad hoc
                                      │
CNES/API ──────> Bronze ──> Silver ───┘
                                      │
                                      └──> Gold serving ──> PostgreSQL
```

### SINAN

1. `sinan.bronze` baixa o Parquet original do PySUS e registra a origem.
2. `sinan.silver` lê em lotes, aplica o schema canônico, normaliza tipos,
   filtra `DT_NOTIFIC` pelo ano solicitado e deduplica.
3. `sinan.gold` resolve municípios contra o IBGE, filtra o escopo, agrega
   casos e faz o join CNES quando solicitado.
4. `run.py` produz Gold `ad_hoc`; `run_load.py` produz Gold `serving` e
   publica no PostgreSQL.

### CNES

1. `run_cnes.py` percorre o escopo e consulta a API CNES.
2. Cada resposta é preservada na Bronze por município.
3. `cnes.silver` valida formato, UF e município da própria unidade.
4. DuckDB consolida o lookup em um Parquet Silver por `batch_id`.
5. A Gold aceita somente batch `COMPLETED`, manifesto íntegro e release IBGE
   compatível. `PARTIAL` nunca é fonte de serving.

O município da unidade CNES vem de `cd_mun_unidade` do próprio registro. O
município epidemiológico da notificação não é fallback da FK da unidade.

### Esporotricose animal

1. `esporo.bronze` preserva o CSV original em Parquet com metadados do lote.
2. `esporo.silver` trata os campos selecionados e não mantém o nome do animal.
3. `esporo.gold` produz uma linha por notificação, padroniza os nomes de coluna,
   codifica as categorias abaixo e escreve um Parquet pronto para consulta e
   carga em `analytics_animal.fato_esporo`.

#### Contrato da Gold ESPORO

| Coluna Gold / PostgreSQL | Tipo | Código | Significado |
|---|---|---:|---|
| `data_notificacao` | `DATE` | — | Data da notificação sem horário |
| `especie_codigo` | `SMALLINT` | 0 | Não informado (`i` na origem) |
|  |  | 1 | Felino |
|  |  | 2 | Canino |
| `sexo_codigo` | `CHAR(1)` | `F` | Fêmea |
|  |  | `M` | Macho |
|  |  | `i` | Não informado |
| `idade_faixa_codigo` | `SMALLINT` | 0 | Não informado (`i`) |
|  |  | 1 | Menos de 1 ano |
|  |  | 2 | De 1 a 3 anos |
|  |  | 3 | De 4 a 6 anos |
|  |  | 4 | De 7 a 10 anos |
|  |  | 5 | Mais de 10 anos |
| `castrado_codigo` | `SMALLINT` | 0 | Não informado (`i`) |
|  |  | 1 | Não castrado |
|  |  | 2 | Castrado |

A Gold normaliza maiúsculas, minúsculas e acentos antes de codificar os valores.
Categorias não reconhecidas causam erro e precisam ser revisadas; não são
convertidas silenciosamente em “não informado”. A Silver mantém os rótulos
textuais inesperados para permitir essa revisão. O `metadata.json` da Gold inclui o lote,
ano de origem, caminho da Silver, quantidade de linhas e contagens de valores
não informados para espécie, sexo, idade e castração.

O artefato é escrito em
`gold/serving/esporo/source_year=<ano>/ingestion_date=<data>/batch_id=<lote>/`.
As migrations `0019`–`0022` alinham os tipos e códigos das colunas no
PostgreSQL com este contrato.

## Contratos das camadas

| Camada | Entrada | Saída | Regra |
|---|---|---|---|
| Bronze SINAN | PySUS/Parquet | Parquet + metadata | preservar fonte |
| Silver SINAN | Bronze | Parquet canônico | validar, normalizar, filtrar e deduplicar |
| Gold SINAN | Silver + IBGE + CNES opcional | Parquet agregado | rejeitar códigos/escopos incompatíveis |
| Bronze CNES | API por município | Parquet + metadata | preservar resposta e município consultado |
| Silver CNES | Bronze CNES | lookup consolidado | validar unidade e cobertura |
| PostgreSQL | Gold serving | fatos, dimensões e métricas | transação, FK e reconciliação |

As escritas são atômicas. Cada execução SINAN propaga um `batch_id` UTC por
Bronze, Silver e Gold; CNES possui ciclo de ingestão independente.

## Fontes e doenças

O código de doença segue `SINAN.group_definitions` do PySUS 2.11.7. Os 49
grupos homologados são:

```text
DENG CHIK ZIKA TUBE HANS HEPA SIFA SIFC LEPT MENI FMAC TOXC TOXG
ACBI ACGR ANIM ANTR BOTU CANC CHAG ESQU COLE COQU DERM DIFT EXAN FTIF
HANT IEXO INFL LEIV LTAN LERD MALA MENT NTRA PAIR PFAN PNEU PEST RAIV
SDTA SRC SIFG TETA TETN TRAC VARC VIOL
```

Campos específicos variam por ficha. A Bronze preserva colunas de origem; só
as chaves registradas em `sinan/columns.py` podem virar dimensões da Gold.

## Território IBGE

Uma release IBGE local contém municípios, 27 UFs, crosswalk de seis para sete
dígitos, manifesto, SHA-256 e hash lógico. Seleções são mutuamente exclusivas:

```bash
--municipios 3301009,3550308
--ufs RJ,SP
--all-brazil
```

Toda seleção explícita exige `--catalog-root`. Sem catálogo, permanece o
recorte RJ legado. A promoção da release é feita por:

```bash
python -m app.pipeline.reference.ibge.refresh \
  --root /data/reference/ibge --catalog-id ibge-dtb-2025 \
  --reference-year 2025 \
  --dtb-url 'https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/DTB_2025.zip' \
  --expected-sha256 <SHA256_OFICIAL>
```

A candidata é validada antes de `active.json` mudar. Uma release já promovida
é imutável por identidade e hash.

## Layout dos artefatos

Com `DATA_ROOT=/data` no container ou `data/` no host:

```text
data/
├── bronze/sinan/disease=DENG/source_year=2026/ingestion_date=.../batch_id=...
│   ├── data.parquet
│   └── metadata.json
├── silver/sinan/disease=DENG/source_year=2026/ingestion_date=.../batch_id=...
│   ├── data.parquet
│   └── metadata.json
├── gold/ad_hoc/sinan/disease=DENG/source_year=2026/ingestion_date=.../batch_id=...
├── gold/serving/sinan/disease=DENG/source_year=2026/ingestion_date=.../batch_id=...
├── bronze/cnes/municipio=3301009/ingestion_date=.../batch_id=...
└── silver/cnes/batch_id=.../data.parquet + metadata.json
```

Bronze é append-only por batch. Não edite Parquets ou manifests manualmente;
gere um novo batch para corrigir uma execução.

## Catálogo de colunas SINAN

O catálogo em `sinan/columns.py` define origem, limpeza, obrigatoriedade,
deduplicação e agrupamento:

| Chave CLI | Coluna | Obrigatória | Dimensão Gold |
|---|---|:---:|:---:|
| `data_notificacao` | `DT_NOTIFIC` | sim | não |
| `municipio` | `ID_MUNICIP` | sim | não |
| `uf` | `SG_UF_NOT` | sim | não |
| `notificacao_id` | `NU_NOTIFIC` | não | não |
| `semana_notificacao` | `SEM_NOT` | não | sim |
| `ano_notificacao` | `NU_ANO` | não | sim |
| `classificacao_final` | `CLASSI_FIN` | não | sim |
| `evolucao` | `EVOLUCAO` | não | sim |
| `sexo` | `CS_SEXO` | não | sim |
| `ano_nascimento` | `ANO_NASC` | não | sim |
| `idade_sinan` / `tipo_idade` | derivados | não | sim |
| `unidade_notificacao` | `ID_UNIDADE` | não | sim/CNES |

Quando `NU_NOTIFIC` não existe, a Silver usa a combinação exata das colunas
disponíveis e emite aviso de que a deduplicação é menos forte.

## Execução dos módulos

### SINAN ad hoc: `run.py`

```bash
python -m app.pipeline.run --disease DENG --year 2026 --columns ""
python -m app.pipeline.run --disease CHIK --year 2026 \
  --catalog-root data/reference/ibge --ufs RJ --columns "sexo,evolucao"
```

A saída é `gold/ad_hoc`. `--columns` recebe chaves separadas por vírgula.

### Serving/PostgreSQL: `run_load.py`

```bash
python -m app.pipeline.run_load --disease DENG --year 2026 \
  --catalog-root data/reference/ibge --all-brazil \
  --cnes-batch-id <BATCH_CNES_COMPLETED>
```

O comando valida linhagem IBGE, escopo, métricas da Gold, FKs e total
esperado, então substitui transacionalmente o recorte doença/ano/municípios.
Resultados vazios são bloqueados, salvo `--allow-empty` explícito.

### CNES: `run_cnes.py`

```bash
python -m app.pipeline.run_cnes --catalog-root data/reference/ibge \
  --all-brazil --page-size 100 --request-timeout 60 \
  --workers 8 --continue-on-error \
  --checkpoint data/reference/cnes-checkpoint.json
```

`--continue-on-error` termina como `PARTIAL` quando há falhas. A retomada
rejeita mudança no escopo, release, page size, timeout ou workers. Sem opção,
a primeira falha aborta. Municípios concluídos não são consultados novamente.

### Atualização incremental: `update_sinan.py`

```bash
python -m app.pipeline.update_sinan --years 2026
python -m app.pipeline.update_sinan --diseases DENG,FMAC,TOXC \
  --years 2026 --catalog-root data/reference/ibge
```

O manifest registra `UPDATED`, `UNCHANGED` ou `UNAVAILABLE`. Indisponibilidade
de fonte não é convertida em lote vazio ou zeros falsos; `--allow-unavailable`
é reservado para descoberta aceita.

### Camadas isoladas

```bash
python -m app.pipeline.sinan.bronze --disease DENG --year 2024
python -m app.pipeline.sinan.silver --source <bronze.parquet> \
  --disease DENG --year 2024 --batch-size 50000 --memory-limit 512MB
python -m app.pipeline.cnes.silver --source <bronze.parquet> \
  --municipio <CODIGO_IBGE>
```

Silver lê em lotes de 50 mil e usa DuckDB para deduplicação global, com limite
de 512 MB e temporários em disco por padrão. Esse limite não inclui pandas,
Arrow e o processo Python. Gold agrega os grupos consolidados em memória.

## CNES na Gold

Quando `unidade_notificacao` está em `--columns`, o join é:

```text
SINAN.ID_UNIDADE ──left join──> CNES.cd_unidade
                               └─ nm_unidade, razao_social_unidade, tp_unidade
```

Uma unidade não encontrada vira nulo e não interrompe a Gold. Para serving,
informe sempre `--cnes-batch-id`; o batch deve existir exatamente em
`silver/cnes/batch_id=<id>`, estar `COMPLETED` e ser compatível com a release
IBGE.

## Metadados e PostgreSQL

Um `metadata.json` registra, conforme a camada:

```json
{
  "disease": "DENG",
  "source_year": 2026,
  "batch_id": "20261103T120000Z",
  "rows": 1234,
  "dropped_rows": 56,
  "gold_target": "serving"
}
```

Silver acrescenta `source_rows`, `invalid_date_rows`, `outside_year_rows`,
`duplicate_rows`, `batch_size` e `batches_processed`. Gold acrescenta métricas
de resolução, escopo e agregação. CNES registra status, release, cobertura e
checksum.

Tabelas principais:

- `analytics.fato_casos`: fatos agregados;
- `analytics.dim_municipio`: municípios IBGE;
- `analytics.dim_unidade_saude`: unidades CNES;
- `analytics.pipeline_publications`: snapshot por município;
- `analytics.pipeline_execution_metrics`: métricas globais;
- `analytics.reference_catalog_releases`: releases usadas.

`pipeline_publications` é controle/métrica por município, não o histórico
completo de fatos. Para rollback, use backup e o procedimento do runbook.

## Código principal

| Módulo | Responsabilidade |
|---|---|
| `sinan/bronze.py` | download e preservação SINAN |
| `sinan/silver.py` | schema, tipos, ano e deduplicação |
| `sinan/gold.py` | escopo, agregação e join CNES |
| `sinan/columns.py` | catálogo de colunas |
| `cnes/bronze.py` | API CNES por município |
| `cnes/silver.py` | validação do cadastro |
| `run.py` | orquestrador ad hoc |
| `run_load.py` | serving/PostgreSQL |
| `run_cnes.py` | lote CNES/checkpoint |
| `update_sinan.py` | atualização incremental |
| `load.py` | dimensões, FKs e transação |
| `reference/ibge/` | releases e validação territorial |
| `observability/` | métricas e role Grafana |
| `atomic_io.py` | escrita atômica |

## Testes e cobertura

```bash
pytest -m "not integration"
docker compose up -d db
TEST_DATABASE_URL=postgresql+psycopg2://nss:nss@localhost:5432/situacao_saude_test \
  pytest -m integration
pytest -q
```

Medição de cobertura de linhas em **03/11/2026**, com `--source=app`:

| Tipo | Testes | Cobertura |
|---|---:|---:|
| Unitários/nacionais | 742 | **93,81%** |
| Integração PostgreSQL | 26 | **36,87%** |
| Compose/observabilidade | validação de infraestrutura | não aplicável à cobertura Python |
| Mutação (`mutmut`) | métrica de robustez | meta de 95% de mutantes mortos |

São medições independentes sobre todo `app`, não percentuais aditivos. O CI
também valida Compose, migrations, role Grafana, Pushgateway, restore,
alertas e provisionamento, mas esses testes de infraestrutura não geram
cobertura Python. A mutação é uma métrica separada da cobertura de linhas:

```bash
coverage run --source=app --data-file=.coverage.unit \
  -m pytest -m "not integration"
coverage report --data-file=.coverage.unit --precision=2
mutmut run
mutmut results
```

## Limitações conhecidas

- O ano é filtrado por `DT_NOTIFIC`, que pode divergir de `NU_ANO`.
- Bronze é append-only e ainda não possui retenção automática.
- CNES é manual; scheduler não está versionado neste repositório.
- A API CNES pode ficar indisponível; retries não substituem reprocessamento.
- Gold mantém grupos distintos em memória; capacidade nacional requer ensaio.
- O alerta de ausência detecta séries que já publicaram métrica. Detectar uma
  etapa que nunca publicou exige inventário de execuções esperadas.
- Produção ainda exige dados autorizados, secrets, digest real de registry,
  contact points e ensaio de desempenho/cutover.
