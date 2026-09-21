# Pipeline SINAN — Núcleo de Situação de Saúde

Pipeline de dados em Python responsável por ingerir, limpar e agregar dados de
notificação compulsória do **SINAN** (Sistema de Informação de Agravos de
Notificação), via [PySUS](https://pysus.readthedocs.io/), seguindo a
arquitetura **Medallion (Bronze → Silver → Gold)**. Os casos são enriquecidos
com o cadastro de unidades de saúde do **CNES**, obtido via
[API de Dados Abertos do Ministério da Saúde](https://apidadosabertos.saude.gov.br).
O resultado alimenta um dashboard de sala de situação de saúde.

Este repositório cobre **apenas a pipeline**.

---

## Sumário

- [Arquitetura](#arquitetura)
- [Fonte de dados e doenças suportadas](#fonte-de-dados-e-doenças-suportadas)
- [Estrutura de diretórios e partições](#estrutura-de-diretórios-e-partições)
- [Catálogo de colunas](#catálogo-de-colunas)
- [Enriquecimento com CNES (unidades de saúde)](#enriquecimento-com-cnes-unidades-de-saúde)
- [Como rodar](#como-rodar)
- [Metadata e auditoria de execução](#metadata-e-auditoria-de-execução)
- [Limitações conhecidas e roadmap](#limitações-conhecidas-e-roadmap)
- [Estrutura do código](#estrutura-do-código)

---

## Arquitetura

```
PySUS (SINAN) ─▶ Bronze ─▶ Silver ─▶ Gold ─▶ (planejado) PostgreSQL ─▶ Backend Java
                 (cru)     (limpo)     ▲
                                       │ join (unidade de notificação)
                                       │
API Dados Abertos (CNES) ─▶ Bronze ─▶ Silver
                             (cru)    (lookup de unidades)
```

| Camada | O que contém | Formato | Idempotência |
|---|---|---|---|
| **Bronze** | Dado bruto retornado pela fonte (PySUS ou API do CNES), sem nenhuma transformação | Parquet | Append-only — cada execução gera um novo `batch_id`, nada é sobrescrito |
| **Silver** | Dado limpo, tipado, deduplicado e filtrado pelo ano de referência (SINAN) ou consolidado por município (CNES) | Parquet | Reprocessável a qualquer momento a partir da Bronze |
| **Gold** | Casos agregados por doença/ano/mês/UF/município (+ dimensões opcionais, incluindo unidade de notificação enriquecida via CNES) | Parquet | Reprocessável a qualquer momento a partir da Silver |

Cada camada só lê da camada imediatamente anterior — nenhuma etapa pula ou
acessa uma camada não adjacente. O CNES é uma **dimensão** com ciclo de vida
próprio (ingerido separadamente do fluxo por doença) — a Gold apenas lê o
lookup mais recente da Silver do CNES no momento da agregação.

### Por que Medallion?

- **Bronze** preserva o dado exatamente como veio da fonte, permitindo
  reprocessar tudo do zero se uma regra de limpeza mudar, sem precisar baixar
  de novo.
- **Silver** já resolve problemas de qualidade e schema variável entre anos
  do SINAN, mas ainda é granular (uma linha por notificação) — útil para
  análises que não cabem nos agregados da Gold.
- **Gold** é o formato pronto para consumo do dashboard: pequeno, agregado,
  autodescritivo (contém `disease`, `year`, etc. como colunas, não só no
  caminho do arquivo).

### Rastreabilidade de execução (`batch_id` compartilhado)

Em cada execução de `run.py`, um único timestamp (`run_at`) é gerado uma vez
e propagado para Bronze, Silver e Gold do SINAN. Isso garante que os três
artefatos de uma mesma execução compartilhem o mesmo `batch_id`, facilitando
correlacionar rapidamente "essa Gold veio dessa Silver, que veio dessa
Bronze" sem precisar comparar timestamps próximos.

---

## Fonte de dados e doenças suportadas

Os dados vêm do SINAN via [PySUS](https://github.com/AlertaDengue/PySUS). O
código da doença é passado como está definido pelo próprio SINAN/PySUS:

| Código | Doença |
|---|---|
| `DENG` | Dengue |
| `CHIK` | Chikungunya |
| `ZIKA` | Zika |
| `TUBE` | Tuberculose |
| `HANS` | Hanseníase |
| `HEPA` | Hepatites virais |
| `SIFA` | Sífilis adquirida |
| `SIFC` | Sífilis congênita |
| `LEPT` | Leptospirose |
| `MENI` | Meningite |

> Esta lista não é exaustiva — qualquer código de doença aceito pelo PySUS
> pode ser usado. Nem todas as doenças compartilham o mesmo schema de campos
> (ex.: campos de sintomas de arboviroses não existem na ficha de
> tuberculose); veja [Limitações conhecidas](#limitações-conhecidas-e-roadmap).

---

## Estrutura de diretórios e partições

Cada execução grava um `batch_id` (timestamp `%Y%m%dT%H%M%SZ`) particionado
no estilo Hive:

```
/data
├── bronze/sinan/disease={doenca}/source_year={ano}/ingestion_date={data}/batch_id={batch}/
│   ├── data.parquet
│   └── metadata.json
├── silver/sinan/disease={doenca}/source_year={ano}/ingestion_date={data}/batch_id={batch}/
│   ├── data.parquet
│   └── metadata.json
├── gold/sinan/disease={doenca}/source_year={ano}/ingestion_date={data}/batch_id={batch}/
│   ├── data.parquet
│   └── metadata.json
├── bronze/cnes/municipio={codigo_ibge}/ingestion_date={data}/batch_id={batch}/
│   ├── data.parquet
│   └── metadata.json
└── silver/cnes/batch_id={batch}/
    ├── data.parquet          # lookup consolidado de todos os municípios de interesse
    └── metadata.json
```

Bronze e Silver do SINAN compartilham o mesmo `batch_id` de uma execução
(veja [Rastreabilidade de execução](#rastreabilidade-de-execução-batch_id-compartilhado)).
O CNES tem ciclo de ingestão independente, sem `source_year`/`disease`, já
que o cadastro de unidades não varia por doença nem por ano de notificação.

Todo `data.parquet` é gravado de forma atômica (escrita em arquivo temporário
+ `os.replace`), evitando arquivos parciais/corrompidos em caso de falha no
meio da escrita.

---

## Catálogo de colunas

As colunas do SINAN utilizadas pela pipeline são centralizadas em
[`columns.py`](./columns.py), em um catálogo declarativo (`CATALOG`). Cada
entrada define:

- `label`: nome amigável da coluna.
- `source_column`: nome real da coluna no SINAN.
- `required`: se ausente, a Silver falha com erro explícito.
- `groupable`: se pode ser usada como dimensão extra na agregação da Gold.
- `dedup_key`: se faz parte da chave de deduplicação de notificações.
- `transform`: função de limpeza/normalização aplicada à coluna.

| Chave | Coluna SINAN | Obrigatória | Agrupável |
|---|---|:---:|:---:|
| `data_notificacao` | `DT_NOTIFIC` | ✅ | |
| `municipio` | `ID_MUNICIP` | ✅ | |
| `uf` | `SG_UF_NOT` | ✅ | |
| `notificacao_id` | `NU_NOTIFIC` | | |
| `semana_notificacao` | `SEM_NOT` | | ✅ |
| `ano_notificacao` | `NU_ANO` | | ✅ |
| `classificacao_final` | `CLASSI_FIN` | | ✅ |
| `evolucao` | `EVOLUCAO` | | ✅ |
| `sexo` | `CS_SEXO` | | ✅ |
| `ano_nascimento` | `ANO_NASC` | | ✅ |
| `unidade_notificacao` | `ID_UNIDADE` | | ✅ |

Colunas marcadas como `groupable` podem ser passadas via `--columns` na CLI
para virarem dimensões extras na Gold (além de doença/ano/mês/UF/município,
que já são sempre incluídas). `unidade_notificacao` é especial: quando
selecionada, a Gold também tenta enriquecer o resultado com nome/tipo da
unidade via join com o CNES (veja a seção seguinte).

**Deduplicação de notificações**: a chave primária ideal é `NU_NOTIFIC`
(`notificacao_id`). Como esse campo não existe em todos os anos/datasets do
SINAN, a pipeline cai automaticamente em um fallback de deduplicação por
correspondência exata entre todas as colunas presentes — e emite um
`UserWarning` avisando disso, já que essa estratégia é mais fraca (duas
notificações distintas, porém idênticas em todos os campos capturados, seriam
tratadas como duplicata).

---

## Enriquecimento com CNES (unidades de saúde)

O SINAN registra a unidade de notificação (`ID_UNIDADE`) apenas como código
— o **CNES** (Cadastro Nacional de Estabelecimentos de Saúde). Nome, razão
social e tipo do estabelecimento não vêm do SINAN nem dos arquivos
históricos de CNES disponíveis via PySUS (que trazem apenas dados
operacionais/estruturais, sem nome ou endereço). Essas informações são
obtidas separadamente, via a
[API de Dados Abertos do Ministério da Saúde](https://apidadosabertos.saude.gov.br/cnes/estabelecimentos).

### Por que é uma ingestão separada

O CNES é tratado como uma **dimensão** com ciclo de vida próprio, não como
parte do fluxo por doença/ano:

- O cadastro de estabelecimentos muda devagar (mês a mês, no máximo), ao
  contrário dos dados de notificação, que são reprocessados com frequência.
- Acoplar essa chamada de API externa (que já se mostrou instável em
  algumas execuções) dentro do fluxo crítico do SINAN arriscaria travar uma
  execução de doença por uma falha momentânea numa fonte não relacionada.
- Várias Golds de doenças diferentes podem reaproveitar o mesmo lookup do
  CNES sem reingeri-lo a cada execução.

### Como rodar a ingestão do CNES

```bash
docker compose run --rm --entrypoint python pipeline -m app.pipeline.run_cnes
```

Isso itera sobre os municípios definidos em `MUNICIPIOS_RJ` (`gold.py`),
busca os estabelecimentos de cada um via API, grava a Bronze por município e
consolida tudo em uma única Silver de lookup
(`silver/cnes/batch_id={batch}/data.parquet`), sem duplicatas de `cd_unidade`.

Essa ingestão é **manual e independente** do `run.py` principal — não há
agendamento automático definido ainda (veja
[Limitações conhecidas](#limitações-conhecidas-e-roadmap)).

### Como o join acontece na Gold

Quando `unidade_notificacao` é passada em `--columns`, `aggregate_file` lê o
**Silver do CNES mais recente disponível** (`_latest_cnes_lookup()`, que
escolhe o `batch_id` mais alto por ordenação lexicográfica do timestamp) e
faz um `left join` entre `ID_UNIDADE` (SINAN) e `cd_unidade` (CNES),
trazendo `nm_unidade`, `razao_social_unidade` e `tp_unidade` para a Gold.

```bash
docker compose run --rm pipeline --disease DENG --year 2026 --columns="unidade_notificacao"
```

Se nenhuma Silver do CNES existir ainda (`run_cnes.py` nunca foi executado),
`_latest_cnes_lookup()` retorna `None` e a Gold é gerada normalmente, apenas
sem as colunas de enriquecimento — a pipeline do SINAN nunca falha por
ausência da dimensão do CNES.

**Cuidados conhecidos:**
- **Nem todo `ID_UNIDADE` vai casar** com o CNES (unidade desativada, código
  incorreto na notificação, notificação fora de estabelecimento formal). O
  `left join` garante que isso vira nulo, não quebra o pipeline — mas o
  consumidor final (dashboard) precisa tratar essa ausência.
- **O lookup é um snapshot**: uma unidade muito recente pode não aparecer
  ainda se o CNES não tiver sido reingerido desde sua criação.

---

## Como rodar

### Via Docker Compose

```bash
docker compose run --rm pipeline --disease DENG --year 2026 --columns=""
```

> **Atenção (PowerShell/Windows):** ao passar `--columns` com valor vazio ou
> contendo vírgulas, prefira a forma `--columns="valor"` (com `=`) em vez de
> `--columns "valor"` (com espaço). O PowerShell pode descartar strings
> vazias/quebrar argumentos ao repassá-los para o `docker compose run`,
> resultando em `error: argument --columns: expected one argument`.

Com dimensões extras selecionadas:

```bash
docker compose run --rm pipeline --disease CHIK --year 2026 --columns="sexo,evolucao"
```

Com enriquecimento de unidade de saúde (requer ter rodado `run_cnes.py`
pelo menos uma vez antes):

```bash
docker compose run --rm pipeline --disease DENG --year 2026 --columns="unidade_notificacao"
```

### CLI (`run.py`)

```bash
python -m app.pipeline.run --disease <CODIGO_SINAN> --year <ANO> [--columns "chave1,chave2"]
```

| Argumento | Obrigatório | Descrição |
|---|:---:|---|
| `--disease` | ✅ | Código SINAN da doença (ex.: `DENG`, `ZIKA`, `TUBE`) |
| `--year` | ✅ | Ano de referência (filtra por `DT_NOTIFIC`) |
| `--columns` | | Chaves do catálogo separadas por vírgula, usadas como dimensões extras na Gold |

O pipeline executa as três camadas em sequência (Bronze → Silver → Gold) e
imprime o caminho final de cada parquet gerado.

### CLI (`run_cnes.py`)

```bash
python -m app.pipeline.run_cnes
```

Sem argumentos — usa `MUNICIPIOS_RJ` como escopo padrão. Ingere a Bronze por
município e consolida a Silver de lookup do CNES.

### Executando camadas isoladamente

`silver.py` também pode ser chamado de forma isolada, útil para reprocessar
uma Silver a partir de uma Bronze já existente:

```bash
python -m app.pipeline.silver --source <bronze.parquet> --destination <silver.parquet> --year <ano>
```

`silver_cnes.py` também pode transformar uma Bronze do CNES isoladamente:

```bash
python -m app.pipeline.silver_cnes --source <bronze_cnes.parquet> --municipio <codigo_ibge>
```

---

## Metadata e auditoria de execução

Cada camada grava um `metadata.json` ao lado do `data.parquet`, contendo:

```json
{
  "disease": "DENG",
  "source_year": 2026,
  "batch_id": "20260914T123721Z",
  "ingested_at": "2026-09-14T12:37:21+00:00",
  "rows": 1234,
  "dropped_rows": 56,
  "columns": ["DT_NOTIFIC", "ID_MUNICIP", "..."]
}
```

Isso serve tanto como log de execução quanto como **checagem de sanidade**:
antes de agregar uma Silver para Gold, a pipeline lê o `metadata.json` de
origem e valida que `disease`/`year` batem com o que foi solicitado,
abortando com erro claro em caso de inconsistência (por exemplo, se um
caminho estiver apontando para o batch errado).

---

## Limitações conhecidas e roadmap

Itens já identificados e ainda não resolvidos, para não serem esquecidos:

- **Carga no PostgreSQL ainda não implementada.** A Gold hoje só é
  persistida em Parquet. Está planejado um `load.py` que faça upsert (ou
  replace por partição `disease`/`year`) numa tabela do Postgres, já que o
  SINAN atualiza registros retroativamente e a carga precisa refletir o
  estado mais recente, não apenas fazer `append`.
- **`year` filtrado por `DT_NOTIFIC`, não por `NU_ANO`.** O SINAN também
  expõe um "ano epidemiológico" (`NU_ANO`), que pode divergir do ano
  calendário perto da virada do ano. Vale confirmar com quem define a regra
  de negócio qual definição de "ano" a sala de situação espera.
- **Sem colunas de sintomas no catálogo.** Campos como `FEBRE`, `MIALGIA`,
  `EXANTEMA` (típicos de arboviroses) ainda não estão mapeados em
  `columns.py`. Além disso, esses campos não são universais entre doenças —
  antes de adicioná-los, decidir se o catálogo permanece único e genérico ou
  se passa a existir um catálogo específico por doença/família de doenças.
- **Schema do Parquet não é fixado explicitamente.** Como colunas
  `groupable` selecionadas variam entre execuções, o schema do Parquet pode
  divergir entre anos/batches. Isso pode ser um problema se o consumidor (ex.:
  Java lendo múltiplos anos de uma vez) esperar schema uniforme.
- **Sem política de retenção definida para a Bronze.** Como a Bronze é
  append-only por natureza da arquitetura Medallion, o volume em disco cresce
  a cada execução. Ainda não há decisão sobre por quanto tempo manter batches
  antigos.
- **Uso de `print()` em vez de `logging`.** Adequado para execução manual,
  mas deve ser substituído antes de rodar em produção/agendado.
- **Sem tabela de controle de execuções (`pipeline_runs`).** Hoje a
  rastreabilidade depende de vasculhar os `metadata.json`. Uma tabela simples
  de controle (`disease`, `year`, `batch_id`, `layer`, `status`) facilitaria
  saber o que já foi processado/carregado, especialmente quando a carga no
  Postgres for implementada.
- **Ingestão do CNES sem agendamento.** `run_cnes.py` é executado
  manualmente hoje. Vale definir uma cadência (ex.: mensal) e automatizá-la,
  já que a Gold sempre usa o lookup mais recente disponível — se ele nunca
  for atualizado, unidades novas nunca aparecerão no enriquecimento.
- **Municípios de interesse hardcoded em `gold.py` (`MUNICIPIOS_RJ`)**,
  reutilizados também pelo `run_cnes.py`. Se a lista de municípios da sala
  de situação crescer, vale mover para um arquivo de configuração externo.
- **API do CNES sem SLA conhecido.** Já foram observadas falhas
  transitórias de DNS/conexão nessa API durante o desenvolvimento. A
  ingestão usa retry com backoff (`urllib3.util.Retry`, incluindo `connect`)
  para absorver instabilidades pontuais, mas não há alerta automatizado caso
  a fonte fique indisponível por mais tempo.

---

## Estrutura do código

```
app/pipeline/
├── sinan.py        # Ingestão via PySUS -> Bronze (SINAN)
├── silver.py        # Limpeza, tipagem, deduplicação -> Silver (SINAN)
├── gold.py           # Agregação por doença/tempo/geografia + join com CNES -> Gold
├── columns.py        # Catálogo declarativo de colunas do SINAN
├── bronze_cnes.py    # Ingestão via API de Dados Abertos -> Bronze (CNES)
├── silver_cnes.py    # Limpeza do cadastro de estabelecimentos -> Silver (CNES)
├── run_cnes.py        # Orquestrador da ingestão do CNES (todos os municípios)
├── atomic_io.py       # Escrita atômica de parquet/json
└── run.py             # Orquestrador da pipeline completa do SINAN (CLI)
```

| Módulo | Responsabilidade |
|---|---|
| `sinan.py` | Baixa dados via PySUS e grava a camada Bronze com metadata de ingestão |
| `silver.py` | Valida colunas obrigatórias, aplica transformações, filtra por ano, deduplica e grava a Silver |
| `columns.py` | Define quais colunas do SINAN existem, como são limpas, e quais podem ser usadas como dimensão |
| `gold.py` | Filtra por municípios de interesse, agrega casos por período/geografia/dimensões extras, enriquece com o CNES quando aplicável, e grava a Gold |
| `bronze_cnes.py` | Consulta a API de Dados Abertos por município e grava a Bronze do CNES |
| `silver_cnes.py` | Limpa e normaliza o cadastro de estabelecimentos (código, nome, tipo, município) |
| `run_cnes.py` | Itera sobre os municípios de interesse, ingere e consolida a Silver de lookup do CNES |
| `atomic_io.py` | Utilitário genérico de escrita atômica, usado por todas as camadas |
| `run.py` | Ponto de entrada CLI que encadeia Bronze → Silver → Gold do SINAN com `batch_id` compartilhado |

---

## Requisitos

- Python 3.12+
- [PySUS](https://pypi.org/project/PySUS/)
- pandas / pyarrow (leitura e escrita de Parquet)
- requests (consumo da API de Dados Abertos do CNES)
- Docker + Docker Compose (execução via container)
