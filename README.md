# NSS Pipeline

Pipeline de dados do Núcleo de Situação de Saúde (NSS/UENF). Baixa notificações
do SINAN via PySUS, preserva o dado bruto, valida e deduplica registros,
agrega resultados e publica no PostgreSQL. Também mantém o território IBGE,
ingere CNES e fornece observabilidade Prometheus/Pushgateway/Grafana.

Este repositório contém somente a pipeline Python. A API Java/Spring Boot e o
frontend ficam em repositórios separados.

## Arquitetura

```text
SINAN/PySUS ──> Bronze ──> Silver ──> Gold ──> PostgreSQL ──> API/dashboard
                  ▲          ▲        ▲
IBGE ─────────────┴──────────┴────────┘  identidade, escopo e release
CNES/API ──────> Bronze ──> Silver ──────┘  dimensão de estabelecimentos
```

- **Bronze:** Parquet bruto e metadados de ingestão.
- **Silver:** schema canônico, normalização, filtro temporal e deduplicação.
- **Gold:** agregação por doença/ano/mês/UF/município e dimensões opcionais.
- **Serving:** Gold validada e carregada transacionalmente no PostgreSQL.
- **IBGE:** identidade municipal, UFs, crosswalk 6↔7 dígitos e releases com
  manifesto, SHA-256 e promoção atômica.
- **CNES:** dimensão independente, reutilizável por várias doenças e anos.

Cada execução recebe `batch_id`, grava `metadata.json` e escreve artefatos
atomicamente. Uma carga inválida não deve substituir uma publicação válida.

### Hierarquia das geometrias territoriais

Para classificar notificações por bairro/distrito, a pipeline procura um par
`districts.geojson` e `neighborhoods.geojson` com bairros e vínculos válidos,
nesta ordem: `territories/ibge/<código>`, `territories/official/<código>` e
`territories/osm/<código>`. Os diretórios legados do RJ são consultados
depois dos nacionais. Sem um pacote válido com bairros, a classificação pode
usar somente os distritos.

A malha nacional de distritos vem do Censo 2022. Boa Esperança do Norte usa
o contorno municipal da Malha Municipal Digital 2025 até haver uma camada
distrital no catálogo. O importador OSM usa os distritos já preparados para
associar cada bairro ou localidade. Ele preserva o identificador original e
`sourceLicense=ODbL-1.0`, que exige atribuição ao OpenStreetMap.

Use `python -m scripts.export_territory_catalog` para exportar o mesmo pacote
selecionado para o mapa, o TSV da API e o índice de distritos com bairros.
Depois de alterar a malha, o lote CNES pode ser atualizado sem baixar
novamente os estabelecimentos:

```bash
python -m app.pipeline.reclassify_cnes \
  --source /data/silver/cnes/batch_id=<lote>/data.parquet \
  --catalog-root /data/reference/ibge
```

A Gold do SINAN deve usar o novo lote para refletir os vínculos corrigidos.
Para testes de visualização, `python -m app.pipeline.seed_territory_validation`
publica o agravo sintético `TST` em um banco vazio chamado
`nss_coverage_stage` com as migrações analíticas aplicadas. A fixture gera
uma linha por bairro mais uma por distrito sem bairros. Ela testa a
publicação e a visualização para os territórios do catálogo, enquanto a
classificação de notificações reais é exercitada separadamente.

## Estrutura

```text
app/pipeline/                    código e documentação detalhada
  sinan/                         Bronze, Silver, Gold e fonte SINAN
  cnes/                          ingestão e normalização CNES
  reference/ibge/                releases e catálogo territorial
  esporo/                         fluxo de esporotricose
  run.py                          SINAN até Gold ad hoc
  run_load.py                     SINAN até serving/PostgreSQL
  run_cnes.py                     lote CNES por escopo
  update_sinan.py                 atualização incremental
observability/                   Prometheus, Grafana e alertas
tests/                           testes unitários, nacionais e integração
docker-compose.yml               ambiente local
docker-compose.production.yml    overlay de produção
Dockerfile                       imagem operacional
flake.nix                        ambiente reprodutível
```

Leia [`app/pipeline/README.md`](app/pipeline/README.md) para os contratos de
dados e módulos. O rollout nacional está em
[`IBGE_NATIONAL_ROLLOUT_RUNBOOK.md`](IBGE_NATIONAL_ROLLOUT_RUNBOOK.md).

## Pré-requisitos e configuração

É necessário Python 3.12+, Docker/Compose v2 e PostgreSQL 16 para serving ou
integração. PySUS, pandas, PyArrow, DuckDB e demais dependências estão em
`requirements.txt`; ferramentas de teste estão em `requirements-dev.txt`.
`nix develop` fornece o ambiente completo e cria `.venv`.

```bash
cp .env.example .env
```

| Variável | Finalidade |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | banco principal |
| `DATABASE_URL` | conexão SQLAlchemy/Alembic |
| `TEST_DATABASE_URL` | somente testes; deve terminar em `_test` |
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | login administrativo Grafana |
| `GRAFANA_DB_USER`, `GRAFANA_DB_PASSWORD` | role read-only do datasource |
| `PROMETHEUS_PUSHGATEWAY_URL` | destino das métricas |
| `NSS_PIPELINE_IMAGE` | imagem do overlay; produção exige digest OCI |

No overlay produtivo, secrets vêm do secret manager. O preflight rejeita
credencial administrativa reutilizada, credenciais locais conhecidas e imagem
sem `@sha256:<64 hex>`.

## Execução local passo a passo

### 1. Ambiente Python

```bash
nix develop
# ou, sem Nix:
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

### 2. Banco e configuração central

```bash
mkdir -p data
docker build -t nss-database:0001 ../NSS-database
docker compose up -d db
docker compose run --rm migrate
```

A imagem do repositório NSS-database provisiona as roles e aplica a configuração `0001`. Ela rejeita bancos legados sem histórico central. Defina as credenciais conforme o Compose antes da execução.

### 3. Release IBGE (quando houver escopo explícito)

```bash
python -m app.pipeline.reference.ibge.refresh \
  --root data/reference/ibge --catalog-id ibge-dtb-2025 \
  --reference-year 2025 \
  --dtb-url 'https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/DTB_2025.zip' \
  --expected-sha256 <SHA256_OFICIAL>
```

O comando valida a release e só depois promove `active.json`. Sem catálogo,
os comandos mantêm o recorte RJ legado.

### 4. SINAN até Gold ad hoc

```bash
python -m app.pipeline.run --disease DENG --year 2026 --columns ""

python -m app.pipeline.run --disease CHIK --year 2026 \
  --catalog-root data/reference/ibge --all-brazil \
  --columns "sexo,evolucao"
```

`--municipios`, `--ufs` e `--all-brazil` são mutuamente exclusivos e exigem
`--catalog-root`.

### 5. CNES e serving/PostgreSQL

```bash
python -m app.pipeline.run_cnes --catalog-root data/reference/ibge \
  --all-brazil --checkpoint data/reference/cnes-checkpoint.json \
  --workers 8 --continue-on-error

python -m app.pipeline.run_load --disease DENG --year 2026 \
  --catalog-root data/reference/ibge --all-brazil \
  --cnes-batch-id <BATCH_CNES_COMPLETED>
```

Lote CNES `PARTIAL` nunca pode enriquecer serving. Em produção, fixe o batch
CNES explicitamente. `--allow-empty` só deve ser usado após confirmar a
ausência na fonte.

## Docker Compose

O volume `./data:/data` mantém os artefatos no host. O fluxo equivalente é:

```bash
mkdir -p data
docker compose build pipeline
docker build -t nss-database:0001 ../NSS-database
docker compose up -d db
docker compose run --rm migrate
docker compose run --rm pipeline --disease DENG --year 2026 --columns=""
```

Para módulos alternativos, use `--entrypoint python`:

```bash
docker compose run --rm --entrypoint python pipeline \
  -m app.pipeline.run_cnes --catalog-root /data/reference/ibge --ufs RJ
docker compose run --rm --entrypoint python pipeline \
  -m app.pipeline.run_load --help
```

No PowerShell, prefira `--columns="sexo,evolucao"`.

## Observabilidade local

```bash
PROMETHEUS_PUSHGATEWAY_URL=http://pushgateway:9091 \
  docker compose --profile observability up -d
docker compose --profile observability ps
curl -fsS http://localhost:9090/-/ready
curl -fsS http://localhost:9091/-/ready
curl -fsS http://localhost:3000/api/health
```

Grafana: `http://localhost:3000`; Prometheus: `http://localhost:9090`;
Pushgateway: `http://localhost:9091`; PostgreSQL: `localhost:5432`.
O dashboard acompanha linhas, descartes totais, descartes anômalos, duração e
estado. Descartes esperados por escopo não acionam o alerta de anomalia. O
alerta de ausência é individualizado por `pipeline/layer/disease/year` para
séries que já publicaram métricas.

```bash
docker compose --profile observability down
```

## Produção e recuperação

```bash
export NSS_PIPELINE_IMAGE=registry.example/nss-pipeline@sha256:<64-hex>
python -m app.pipeline.preflight
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability config --quiet
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability up -d db prometheus pushgateway grafana
```

O overlay remove portas públicas, bind mounts de código e builds locais.
Consulte o [runbook nacional](IBGE_NATIONAL_ROLLOUT_RUNBOOK.md) antes de
promover dados.

Backup dentro da rede Compose, com saída persistente no host:

```bash
backup_dir="/var/backups/nss/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  exec -T db pg_dump --format=custom --no-owner --no-acl \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$backup_dir/situacao_saude.dump"
pg_restore --list "$backup_dir/situacao_saude.dump" >/dev/null
sha256sum "$backup_dir/situacao_saude.dump" > "$backup_dir/SHA256SUMS"
```

Após restore, confira a propriedade dos objetos e as permissões das roles antes de liberar a aplicação. Um restore com `--no-owner` atribui objetos ao usuário que executa a restauração. Ensaie a transferência de propriedade para as roles migradoras e a reaplicação dos grants em um banco descartável antes de operar o destino definitivo.

Consulte `IBGE_NATIONAL_ROLLOUT_RUNBOOK.md` para promoção IBGE, rollback,
contact points e cutover.

## Testes e cobertura

```bash
pytest -m "not integration"
docker compose up -d db
TEST_DATABASE_URL=postgresql+psycopg2://nss:nss@localhost:5432/situacao_saude_test \
  pytest -m integration
pytest -q
```

Cobertura de linhas medida em **03/11/2026**, usando `--source=app`:

| Tipo | Testes | Cobertura |
|---|---:|---:|
| Unitários/nacionais (`-m "not integration"`) | 742 | **93,81%** |
| Integração PostgreSQL (`-m integration`) | 26 | **36,87%** |
| Compose/observabilidade | validação de infraestrutura | não aplicável à cobertura Python |
| Mutação (`mutmut`) | métrica de robustez | meta de 95% de mutantes mortos |

São medições independentes sobre todo `app`, não percentuais aditivos. Para
reproduzir:

```bash
coverage run --source=app --data-file=.coverage.unit \
  -m pytest -m "not integration"
coverage report --data-file=.coverage.unit --precision=2

coverage run --source=app --data-file=.coverage.integration \
  -m pytest -m integration
coverage report --data-file=.coverage.integration --precision=2
```

O CI valida também Compose, configuração central, role Grafana, Pushgateway, restore,
alertas e provisionamento; isso não gera cobertura Python de linhas. A métrica
de mutação é separada da cobertura de linhas.

```bash
mutmut run
mutmut results
```

## Comandos úteis

```bash
docker compose ps
docker compose logs -f db migrate
docker compose run --rm migrate
docker compose down
docker compose down -v
python -m app.pipeline.run --help
python -m app.pipeline.run_cnes --help
python -m app.pipeline.run_load --help
python -m app.pipeline.update_sinan --help
python -m app.pipeline.preflight
```

## Documentos relacionados

- [Documentação detalhada da pipeline](app/pipeline/README.md)
- [Runbook nacional](IBGE_NATIONAL_ROLLOUT_RUNBOOK.md)
- [Plano de prontidão](NSS_PRODUCTION_READINESS_PLAN.md)
- [Backlog de integração](IBGE_INTEGRATION_BACKLOG.md)
- Frontend: `Zadoque/nss-front-end`
- Backend: `ArtursPereira/Site-Sala-de-Situa-o-de-Saude-Java`
- Deployment: `Zadoque/nss-deployment`

## Arquitetura e estrutura

```mermaid
flowchart LR
  S[Parquet SINAN/CNES] --> I[ingestion]
  I --> G[gold transform]
  G --> W[analytics writer]
  W --> DB[(PostgreSQL analytics)]
  DB --> API[Java API]
```

`app/` contém o pipeline e seus contratos; `scripts/` contém importação/exportação territorial; `territories/` guarda fontes IBGE/OSM normalizadas; `tests/` cobre unidade e integração. O pipeline usa a imagem central do `NSS-database` e publica somente no lote vigente.
