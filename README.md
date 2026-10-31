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

Para selecionar uma doença do catálogo PySUS e um recorte territorial:

```bash
python -m app.pipeline.run \
  --disease DENG \
  --year 2026 \
  --all-brazil \
  --columns ""
```

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
python -m app.pipeline.run_cnes --all-brazil
```

Consulte `--help` para os parâmetros de checkpoint, concorrência, timeout e
seleção geográfica.

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
