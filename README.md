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
│       ├── run.py
│       ├── silver.py
│       └── sinan.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

A documentação detalhada da pipeline está em [`app/pipeline/README.md`](app/pipeline/README.md).

## Execução

```bash
docker compose run --rm pipeline --disease DENG --year 2026 --columns=""
```

ou localmente:

```bash
python -m app.pipeline.run --disease DENG --year 2026 --columns ""
```

Exemplo com dimensões adicionais:

```bash
python -m app.pipeline.run --disease CHIK --year 2026 --columns "sexo,evolucao"
```

## Dependências principais

- Python 3.12+
- PySUS
- pandas
- pyarrow

## Repositórios relacionados

- Frontend: `Zadoque/nss-front-end`
- Backend Java/Spring Boot: `ArtursPereira/Site-Sala-de-Situa-o-de-Saude-Java`
- Arquitetura/deployment: `Zadoque/nss-deployment`
