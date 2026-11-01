# NSS — Pipeline de Dados PySUS/SINAN

Este repositório contém **somente a pipeline Python de dados** do Núcleo de Situação de Saúde (NSS/UENF). Ele não é monorepo e não contém frontend nem backend HTTP da aplicação.

## Responsabilidade

A pipeline ingere dados do SINAN via PySUS e aplica uma arquitetura Medallion:

```text
PySUS / SINAN -> Bronze -> Silver -> Gold
```

- **Bronze:** preservação do dado bruto e metadados de ingestão.
- **Silver:** validação, normalização, filtro temporal e deduplicação.
- **Gold:** agregações prontas para consumo posterior pela arquitetura de persistência/API.

Além do fluxo epidemiológico, a pipeline mantém a identidade territorial canônica
do IBGE e integra o CNES. O modo legado do RJ continua disponível para execuções
incrementais; seleções explícitas podem abranger municípios, UFs ou o Brasil.

O catálogo IBGE é versionado com manifesto, SHA-256, hash lógico e promoção
atômica. A release usada pelo SINAN, CNES e PostgreSQL fica registrada para
permitir reprocessamento e auditoria.

O caminho síncrono definitivo da aplicação é mantido fora deste repositório: frontend -> API Java/Spring Boot -> PostgreSQL. Esta pipeline é responsável pela preparação e atualização dos dados.

## Estrutura

```text
.
├── app/
│   └── pipeline/
│       ├── README.md
│       ├── atomic_io.py
│       ├── columns.py
│       ├── gold.py
│       ├── load.py
│       ├── reference/ibge/
│       ├── run.py
│       ├── run_cnes.py
│       ├── silver.py
│       └── sinan.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

A documentação detalhada da pipeline está em [`app/pipeline/README.md`](app/pipeline/README.md).

Os contratos e resultados da integração nacional estão documentados em:

- [`IBGE_NATIONAL_ROLLOUT_RUNBOOK.md`](IBGE_NATIONAL_ROLLOUT_RUNBOOK.md):
  pré-condições, execução, rollback e verificação operacional;
- [`IBGE_INTEGRATION_EXECUTION.md`](IBGE_INTEGRATION_EXECUTION.md): execuções,
  evidências e resultados de homologação;
- [`IBGE_INTEGRATION_BACKLOG.md`](IBGE_INTEGRATION_BACKLOG.md): critérios de
  aceite e pendências da integração IBGE/CNES/SINAN;
- [`tests/test_national_scope.py`](tests/test_national_scope.py): regressões
  nacionais offline com a DTB oficial e histórico territorial.

## Execução

```bash
docker compose run --rm pipeline --disease DENG --year 2026 --columns=""
```

ou localmente:

```bash
python -m app.pipeline.run --disease DENG --year 2026 --columns ""
```

Para uma publicação `serving`, informe explicitamente o lote CNES já
homologado. A seleção implícita do lote mais recente não é permitida em
produção, pois tornaria a Gold não reprodutível:

```bash
python -m app.pipeline.run \
  --disease DENG \
  --year 2026 \
  --cnes-batch-id 20261031T120000Z \
  --columns ""
```

Para selecionar uma doença do catálogo PySUS e um recorte territorial:

```bash
python -m app.pipeline.run \
  --disease DENG \
  --year 2026 \
  --catalog-root /data/reference/ibge \
  --all-brazil \
  --columns ""
```

`--municipios`, `--ufs` e `--all-brazil` exigem uma release IBGE válida em
`--catalog-root` e são mutuamente exclusivos. Sem uma seleção territorial
explícita, a execução permanece no recorte legado do RJ para compatibilidade.
No Docker, o diretório local que contém o catálogo deve estar disponível em
`/data/reference/ibge`.

O catálogo de doenças acompanhado pela pipeline é derivado dos grupos SINAN
expostos pelo PySUS. A matriz de cobertura e os grupos temporariamente
indisponíveis em fontes externas ficam registrados no relatório de execução;
uma falha de disponibilidade não deve ser confundida com ausência de suporte
do pipeline.

Exemplo com dimensões adicionais:

```bash
python -m app.pipeline.run --disease CHIK --year 2026 --columns "sexo,evolucao"
```

## Dependências principais

- Python 3.12+
- PySUS
- pandas
- pyarrow

Para executar o processamento CNES nacional, use o executor específico e um
catálogo IBGE válido. O lote publicado deve estar completo e vinculado à mesma
release IBGE usada na Gold:

```bash
python -m app.pipeline.run_cnes \
  --catalog-root /data/reference/ibge \
  --all-brazil
```

Como o `docker-compose.yml` usa `app.pipeline.run` como entrypoint padrão, o
CNES precisa selecionar explicitamente o interpretador e o módulo:

```bash
docker compose run --rm --entrypoint python pipeline \
  -m app.pipeline.run_cnes \
  --catalog-root /data/reference/ibge \
  --all-brazil
```

Consulte `--help` para os parâmetros de checkpoint, concorrência, timeout e
seleção geográfica.

### Observabilidade local

A stack inspirada na branch `prometheus/grafana` é isolada em um profile
opcional e não altera a execução quando o Pushgateway não está disponível:

```bash
PROMETHEUS_PUSHGATEWAY_URL=http://pushgateway:9091 \
  docker compose --profile observability up -d
```

Depois, o Grafana fica em `http://localhost:3000` e o Prometheus em
`http://localhost:9090`. O dashboard operacional acompanha Bronze, Silver,
Gold e PostgreSQL por quantidade de linhas, descartes, duração e estado. As
métricas usam somente labels operacionais de baixa cardinalidade; municípios,
unidades e semanas não são labels Prometheus. O datasource `NSS PostgreSQL`
também é provisionado para consultas SQL de auditoria; suas credenciais vêm
de `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB` do ambiente. O
dashboard inclui tabelas de reconciliação de execução e de publicações no
PostgreSQL, sem misturar contagens de camadas com métricas epidemiológicas.
As credenciais administrativas do Grafana vêm de `GRAFANA_ADMIN_USER` e
`GRAFANA_ADMIN_PASSWORD`; os defaults do Compose são somente para o ambiente
local e devem ser substituídos antes de qualquer exposição compartilhada.
O preflight do overlay de produção também exige
`PROMETHEUS_PUSHGATEWAY_URL`, garantindo que as execuções produtivas tenham um
destino de métricas configurado.
Também são provisionadas regras Grafana para falha de etapa e descarte de
linhas. Elas alteram o estado dos alertas, mas o canal de notificação deve ser
configurado no ambiente produtivo com um contact point e uma notification
policy aprovados pela operação.

O Compose executa `alembic upgrade head` no serviço `migrate` antes de permitir
que a pipeline rode. Para aplicar migrations manualmente em um ambiente já
subido, use:

```bash
docker compose run --rm migrate
```

Para um ambiente compartilhado, use também o overlay
`docker-compose.production.yml`. Ele exige as credenciais por ambiente e
remove as portas públicas de PostgreSQL, Prometheus, Pushgateway e Grafana:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability config --quiet
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability up -d db prometheus pushgateway grafana
```

O overlay não contém secrets; eles devem ser fornecidos pelo secret manager do
ambiente de deploy.

## Qualidade e CI

As verificações locais recomendadas são:

```bash
pytest -q
nix flake check --no-build
```

O workflow de testes também é executado em pushes para `work/nss-pipeline`,
além de `main`, `master` e pull requests. A branch não é considerada pronta
para produção nacional apenas pela aprovação da suíte: a homologação deve
incluir PostgreSQL, artefatos oficiais do IBGE, dados autorizados do SINAN e
os critérios de cobertura e mutação registrados no backlog.

## Teste de mutação

O projeto usa `mutmut` para verificar se os testes detectam pequenas alterações
no código. A configuração inicial limita a análise aos módulos prioritários e
exclui os testes de integração com PostgreSQL:

```bash
mutmut run
mutmut results
mutmut browse
```

Mutantes sobreviventes indicam comportamentos que a suíte atual não conseguiu
detectar e devem orientar a criação de novos testes.

### Plano incremental de qualidade

Cada rodada deve seguir o mesmo ciclo: (1) escolher um comportamento de negócio
com baixa cobertura, (2) escrever testes de contrato para entradas válidas,
inválidas e limites reais, (3) executar testes unitários e de integração, (4)
medir linhas e branches e (5) executar o `mutmut` no módulo alterado. Mutantes
equivalentes ou sobreviventes devem ser registrados; não são removidos apenas
para melhorar a porcentagem.

Ordem de expansão prevista:

1. parsing e publicação de ESPORO e mapeamento territorial;
2. validações e transações do carregamento PostgreSQL;
3. orquestradores CNES/SINAN/ESPORO e seus caminhos de falha;
4. módulos restantes e uma rodada final no escopo completo.

As metas são 95% de linhas e branches no escopo coberto e pelo menos 95% de
mutação nos módulos priorizados. O resultado só é considerado válido quando
`mutmut` associa os testes aos mutantes e não informa `no tests`.

## Repositórios relacionados

- Frontend: `Zadoque/nss-front-end`
- Backend Java/Spring Boot: `ArtursPereira/Site-Sala-de-Situa-o-de-Saude-Java`
- Arquitetura/deployment: `Zadoque/nss-deployment`
