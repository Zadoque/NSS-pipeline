# Banco de Dados — Camada Analytics

Este documento descreve o banco PostgreSQL que serve como camada de
**serving** para o backend Java: os dados já limpos e agregados pela
pipeline (Gold) são carregados aqui, num schema relacional pronto para
consulta pelo dashboard.

> A pipeline (Python) é dona deste schema e de suas migrations. O backend
> Java, em repositório separado, apenas se conecta e consome — não
> versiona nem altera este schema.

Este arquivo vive em `migrations/README.md`; `alembic.ini` fica na **raiz
do repositório** (não aqui dentro — ver [Rodando migrations](#rodando-migrations)).

---

## Sumário

- [Onde isso se encaixa na arquitetura](#onde-isso-se-encaixa-na-arquitetura)
- [Modelagem: esquema estrela](#modelagem-esquema-estrela)
- [Tabelas](#tabelas)
- [Setup local](#setup-local)
- [Rodando migrations](#rodando-migrations)
- [Criando novas migrations](#criando-novas-migrations)
- [A carga (load.py / run_load.py)](#a-carga-loadpy--run_loadpy)
- [Conectando o backend Java](#conectando-o-backend-java)
- [Como crescer o schema no futuro](#como-crescer-o-schema-no-futuro)
- [Limitações conhecidas e roadmap](#limitações-conhecidas-e-roadmap)

---

## Onde isso se encaixa na arquitetura

```
PySUS (SINAN) ─▶ Bronze ─▶ Silver ─▶ Gold (grão fixo) ─▶ load.py ─▶ PostgreSQL ─▶ Backend Java
                                        ▲
                                        │ join
API Dados Abertos (CNES) ─▶ Bronze ─▶ Silver
```

O Postgres é alimentado só pela **Gold** (já agregada), nunca pela Silver
(dado granular). Dentro do código, isso corresponde a:

```
app/pipeline/
├── sinan/          # bronze.py, silver.py, gold.py, columns.py
├── cnes/           # bronze.py, silver.py
├── load.py          # upsert da Gold no Postgres
├── run.py            # CLI: pipeline SINAN (Parquet apenas, exploratório)
├── run_cnes.py         # CLI: ingestão do CNES
└── run_load.py           # CLI: pipeline SINAN + carga no Postgres
```

---

## Modelagem: esquema estrela

O schema segue o padrão **esquema estrela (star schema)**: tabelas de
**fato** (o que se mede — quantidade de casos) cercadas por tabelas de
**dimensão** (os eixos pelos quais esse dado é fatiado — doença, tempo,
município, unidade de saúde, classificação, evolução).

```
dim_doenca ────────┐
dim_municipio ───────┤
dim_unidade_saude ───┼──▶ fato_casos ◀── medida: cases_total
dim_classificacao ───┤
dim_evolucao ───────┘
```

**Por que esse padrão, e não uma tabela única desnormalizada:**
- Dimensões são reaproveitadas por fatos futuros (se um dia existir
  `fato_internacoes`, ele usa as mesmas `dim_municipio`/`dim_doenca`, sem
  duplicar cadastro).
- Evita repetir texto (nome de município, nome de doença) em cada linha do
  fato — o fato guarda só códigos, mais compacto e mais rápido de agregar.
- É o padrão que qualquer ferramenta de BI/dashboard já sabe consumir bem
  (joins simples, agregações diretas).

**Padrão "não informado" em vez de `NULL`:** toda dimensão opcional
(`dim_unidade_saude`, `dim_classificacao`, `dim_evolucao`) tem uma linha
sentinela (`'0000000'` / `'NI'`) para os casos em que o dado de origem não
tem aquela informação. Isso existe porque o Postgres não trata dois `NULL`
como iguais em uma `UNIQUE constraint` — se o FK pudesse ser `NULL`, o
upsert (`ON CONFLICT`) do fato criaria linhas duplicadas a cada execução em
vez de atualizar a existente. As linhas sentinela são seedadas pela
migration `0001` com descrição curada, e o `load.py` nunca as sobrescreve
(ver [A carga](#a-carga-loadpy--run_loadpy)).

---

## Tabelas

| Tabela | Tipo | Chave | Descrição |
|---|---|---|---|
| `analytics.dim_doenca` | Dimensão | `codigo` (SINAN, ex. `DENG`) | Doenças cobertas pela pipeline |
| `analytics.dim_municipio` | Dimensão | `cd_mun` (código IBGE, 7 dígitos) | Municípios de interesse |
| `analytics.dim_unidade_saude` | Dimensão | `cd_unidade` (código CNES, 7 dígitos) | Unidades de saúde, enriquecidas via API do CNES |
| `analytics.dim_classificacao` | Dimensão | `codigo` | Classificação final do caso (`CLASSI_FIN`) |
| `analytics.dim_evolucao` | Dimensão | `codigo` | Evolução do caso (`EVOLUCAO`) |
| `analytics.fato_casos` | Fato | `id` (surrogate) + `UNIQUE` composta | Casos agregados por doença/ano/mês/município/unidade/classificação/evolução |

A `UNIQUE constraint` de `fato_casos` (`disease_codigo, ano, mes, cd_mun,
cd_unidade, cd_classificacao, cd_evolucao`) é a chave usada pelo `load.py`
no `ON CONFLICT` do upsert — necessária porque o SINAN atualiza
notificações retroativamente, então recarregar a Gold de um mesmo período
deve **atualizar** a linha existente, não duplicá-la.

DDL completo: [`versions/0001_cria_schema_analytics.py`](./versions/0001_cria_schema_analytics.py).

---

## Setup local

### 1. Pré-requisitos no repositório

```
alembic
psycopg2-binary
sqlalchemy
```
no `requirements.txt`, e o serviço `db` no `docker-compose.yml`.

### 2. Variáveis de ambiente

```bash
cp .env.example .env
```

Preencha `POSTGRES_PASSWORD` e reflita a mesma senha em `DATABASE_URL`.
`.env` nunca deve ser commitado.

### 3. Build e subida do banco

```bash
docker compose build pipeline
docker compose up -d db
docker compose ps          # confirme que "db" está healthy
```

---

## Rodando migrations

`alembic.ini` fica na **raiz do repositório**, não dentro desta pasta —
`script_location` em `alembic.ini` é resolvido relativo à posição do
próprio arquivo, e a convenção do Alembic é `alembic.ini` na raiz do
projeto com `script_location = migrations` apontando pra cá.

```bash
docker compose run --rm --entrypoint alembic pipeline upgrade head
```

Confirme que as tabelas foram criadas:

```bash
docker compose exec db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt analytics.*"
```

Deve listar as 6 tabelas descritas em [Tabelas](#tabelas).

---

## Criando novas migrations

Nunca edite uma migration já aplicada — sempre uma nova:

```bash
docker compose run --rm --entrypoint alembic pipeline revision -m "descrição da mudança"
```

Edite o arquivo gerado em `versions/` (as migrations deste projeto são SQL
puro via `op.execute(...)`, sem ORM), depois:

```bash
docker compose run --rm --entrypoint alembic pipeline upgrade head
```

Para reverter a última migration (uso local/teste, não em dado real já
carregado):

```bash
docker compose run --rm --entrypoint alembic pipeline downgrade -1
```

---

## A carga (`load.py` / `run_load.py`)

`run_load.py` roda a pipeline SINAN completa (Bronze → Silver → Gold) com
um **grão fixo** de dimensões (`CANONICAL_GOLD_COLUMNS`, definido em
`sinan/columns.py`), diferente do `--columns` livre usado por `run.py`
para exploração em Parquet. Isso existe porque o schema relacional do
banco não pode variar entre execuções, ao contrário do Parquet — ver
[Como crescer o schema](#como-crescer-o-schema-no-futuro) para a
justificativa completa.

```bash
docker compose run --rm --entrypoint python pipeline -m app.pipeline.run_load --disease DENG --year 2026
```

**Como o upsert é estruturado:** `load.py._prepare_fact_frame()` é a
única função que decide os valores finais de `cd_unidade`,
`cd_classificacao` e `cd_evolucao` (normalizando string vazia e `NaN`
igualmente, e aplicando o "não informado" quando ausente). Todas as
funções de upsert de dimensão leem esses valores já normalizados a partir
do mesmo dataframe — nunca recalculam a partir da Gold crua. Isso existe
para eliminar uma classe inteira de bug (violação de FK por divergência
entre a lógica de dimensão e a lógica de fato); se notar uma FK falhando
de novo no futuro, o primeiro lugar a checar é se algum código novo
passou a derivar uma coluna de código fora dessa função central.

Ordem do upsert (dimensões antes do fato, por causa das FKs):
`dim_doenca → dim_municipio → dim_unidade_saude → dim_classificacao →
dim_evolucao → fato_casos`.

---

## Conectando o backend Java

Durante desenvolvimento local, com a porta exposta no `docker-compose.yml`
(`5432:5432`):

```
jdbc:postgresql://localhost:5432/<POSTGRES_DB>
```

com usuário/senha definidos no `.env` deste repositório (compartilhados com
o time do backend por fora do código, não commitados em nenhum dos dois
repositórios).

O backend só precisa consultar o schema `analytics` — não precisa de
acesso de escrita nem de conhecimento de como as migrations funcionam.

---

## Como crescer o schema no futuro

Regra de decisão ao adicionar algo novo:

| Situação | O que fazer |
|---|---|
| Um eixo novo para fatiar o dado que já existe (ex.: faixa etária) | Nova dimensão + FK em `fato_casos`, e adicionar a chave correspondente em `CANONICAL_GOLD_COLUMNS` |
| Uma métrica com granularidade diferente (ex.: ocupação de leitos por dia) | Novo fato, reaproveitando dimensões existentes |
| Um campo que só existe para algumas doenças/categorias (ex.: sintomas) | Fato "estreito" separado (uma linha por combinação, não uma coluna por campo) — evita colunas `NULL` em massa em `fato_casos` |
| Uma dimensão precisa manter histórico de mudanças (ex.: nome de unidade mudou e isso importa para casos antigos) | Slowly Changing Dimension (SCD Tipo 2) — ainda não implementado, avaliar quando o requisito aparecer |

Toda dimensão nova deve nascer com uma linha "não informado" desde a
migration que a cria, seguindo o mesmo padrão já usado nas dimensões
existentes, e `load.py` deve derivá-la a partir do dataframe normalizado
central (`_prepare_fact_frame`), nunca de uma cópia paralela da lógica.

---

## Limitações conhecidas e roadmap

- **Descrição de `dim_classificacao`/`dim_evolucao` é placeholder.**
  `load.py` insere `"Código X (ver dicionário SINAN)"` para códigos ainda
  não vistos — `CLASSI_FIN` e `EVOLUCAO` variam por doença e por versão
  da ficha do SINAN, então não há um dicionário universal seguro para
  preencher automaticamente. Precisa ser complementado manualmente
  (UPDATE ou migration) por alguém que consulte o dicionário oficial da
  doença/ano em questão.
- **`dim_unidade_saude.cd_mun` não é populado.** O `codigo_municipio`
  retornado pela API do CNES tem 6 dígitos; `dim_municipio.cd_mun` usa o
  padrão IBGE de 7 dígitos do SINAN. Converter exige calcular o dígito
  verificador (não é um simples zero à esquerda) — pendente de
  implementação cuidadosa.
- **Sem SCD nas dimensões.** `dim_unidade_saude` reflete o cadastro mais
  recente ingerido — não preserva o estado histórico de uma unidade que
  mudou de nome/tipo.
- **Sem ambiente de produção/homologação definido.** Setup atual é só
  para desenvolvimento local; infraestrutura de produção (gerenciada ou
  container próprio) ainda não decidida.
- **Grão de `fato_casos` é fixo hoje** (doença/ano/mês/município/unidade/
  classificação/evolução) — não reflete toda a flexibilidade de
  `--columns` que a Gold em Parquet permite via `run.py`. Se o dashboard
  precisar de mais dimensões (sexo, faixa etária), isso exige nova
  migration + atualizar `CANONICAL_GOLD_COLUMNS`.
