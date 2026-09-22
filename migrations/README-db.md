# Banco de Dados — Camada Analytics

Este documento descreve o banco PostgreSQL que serve como camada de
**serving** para o backend Java: os dados já limpos e agregados pela
pipeline (Gold, em Parquet) são carregados aqui, num schema relacional
pronto para consulta pelo dashboard.

> A pipeline (Python) é dona deste schema e de suas migrations. O backend
> Java, em repositório separado, apenas se conecta e consome — não
> versiona nem altera este schema.

---

## Sumário

- [Onde isso se encaixa na arquitetura](#onde-isso-se-encaixa-na-arquitetura)
- [Modelagem: esquema estrela](#modelagem-esquema-estrela)
- [Tabelas](#tabelas)
- [Setup local](#setup-local)
- [Rodando migrations](#rodando-migrations)
- [Criando novas migrations](#criando-novas-migrations)
- [Conectando o backend Java](#conectando-o-backend-java)
- [Como crescer o schema no futuro](#como-crescer-o-schema-no-futuro)
- [Limitações conhecidas e roadmap](#limitações-conhecidas-e-roadmap)

---

## Onde isso se encaixa na arquitetura

```
PySUS (SINAN) ─▶ Bronze ─▶ Silver ─▶ Gold (Parquet) ─▶ load.py* ─▶ PostgreSQL ─▶ Backend Java
                                        ▲
                                        │ join
API Dados Abertos (CNES) ─▶ Bronze ─▶ Silver
```

\* `load.py` ainda não implementado — veja
[Limitações conhecidas](#limitações-conhecidas-e-roadmap).

O Postgres não é alimentado diretamente pela Silver (dado granular, linha a
linha) — só pela Gold (já agregada), pelos mesmos motivos de volume e
granularidade discutidos para o Parquet.

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
vez de atualizar a existente.

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
cd_unidade, cd_classificacao, cd_evolucao`) é a chave usada pelo futuro
`load.py` no `ON CONFLICT` do upsert — necessária porque o SINAN atualiza
notificações retroativamente, então recarregar a Gold de um mesmo período
deve **atualizar** a linha existente, não duplicá-la.

DDL completo: [`migrations/versions/0001_cria_schema_analytics.py`](./migrations/versions/0001_cria_schema_analytics.py).

---

## Setup local

### 1. Pré-requisitos no repositório

```
alembic
psycopg2-binary
```
no `requirements.txt`, e o serviço `db` no `docker-compose.yml` (ver
`docker-compose.yml` deste projeto).

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

`alembic.ini` fica na **raiz do repositório** (não dentro de `migrations/`
— é a convenção padrão do Alembic, já que `script_location` em
`alembic.ini` é resolvido relativo à posição do próprio arquivo).

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

Edite o arquivo gerado em `migrations/versions/` (as migrations deste
projeto são SQL puro via `op.execute(...)`, sem ORM), depois:

```bash
docker compose run --rm --entrypoint alembic pipeline upgrade head
```

Para reverter a última migration (uso local/teste, não em dado real já
carregado):

```bash
docker compose run --rm --entrypoint alembic pipeline downgrade -1
```

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
| Um eixo novo para fatiar o dado que já existe (ex.: faixa etária) | Nova dimensão + FK em `fato_casos` |
| Uma métrica com granularidade diferente (ex.: ocupação de leitos por dia) | Novo fato, reaproveitando dimensões existentes |
| Um campo que só existe para algumas doenças/categorias (ex.: sintomas) | Fato "estreito" separado (uma linha por combinação, não uma coluna por campo) — evita colunas `NULL` em massa em `fato_casos` |
| Uma dimensão precisa manter histórico de mudanças (ex.: nome de unidade mudou e isso importa para casos antigos) | Slowly Changing Dimension (SCD Tipo 2) — ainda não implementado, avaliar quando o requisito aparecer |

Toda dimensão nova deve nascer com uma linha "não informado" desde a
migration que a cria, seguindo o mesmo padrão já usado nas dimensões
existentes.

---

## Limitações conhecidas e roadmap

- **`load.py` (Gold → Postgres) ainda não implementado.** As tabelas já
  existem; falta o script que lê o Parquet da Gold e faz upsert
  (dimensões primeiro, fato depois, usando a `UNIQUE constraint` como
  chave de conflito).
- **Sem SCD nas dimensões.** `dim_unidade_saude` reflete o cadastro mais
  recente ingerido — não preserva o estado histórico de uma unidade que
  mudou de nome/tipo.
- **Sem ambiente de produção/homologação definido.** Setup atual é só
  para desenvolvimento local; infraestrutura de produção (gerenciada ou
  container próprio) ainda não decidida.
- **Grão de `fato_casos` é fixo hoje** (doença/ano/mês/município/unidade/
  classificação/evolução) — não reflete toda a flexibilidade de
  `--columns` que a Gold em Parquet permite. Se o dashboard precisar de
  mais dimensões (sexo, faixa etária), isso exige nova migration.
