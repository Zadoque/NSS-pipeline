# Runbook de rollout nacional — catálogo IBGE

Este runbook descreve uma execução nacional controlada. O processamento usa
uma release IBGE local aprovada e fixa o escopo e o lote CNES antes de iniciar
SINAN. A rede é necessária para atualizar fontes, não para resolver municípios
durante Bronze, Silver, Gold ou publicação.

## Pré-condições

- executar o preflight sem imprimir secrets:

  ```bash
  python -m app.pipeline.preflight
  ```

  O preflight também exige `PROMETHEUS_PUSHGATEWAY_URL` com uma URL `http` ou
  `https` válida; em produção, a publicação não deve prosseguir sem o destino
  de métricas operacional.

- ambiente carregado pelo `flake.nix`;
- PostgreSQL disponível e migrations aplicadas;
- overlay `docker-compose.production.yml` validado com secrets injetados pelo
  ambiente, sem expor portas internas publicamente;
- `NSS_PIPELINE_IMAGE` apontando para uma imagem promovida por digest imutável
  ou por tag de commit de 40 caracteres hexadecimais;
- diretório de referência com espaço para o ZIP bruto, releases e checkpoints;
- SHA-256 confirmado por uma fonte oficial antes da promoção;
- execução de homologação concluída para a mesma release.
- CI aprovado no commit de rollout, inclusive no push para
  `work/nss-pipeline`.
- contact point e notification policy do Grafana configurados fora do
  repositório, usando secrets do ambiente produtivo.
- Os grupos SINAN do PySUS estão cobertos pelo catálogo operacional. A versão
  PySUS 2.11.7 homologada possui 49 grupos, verificados automaticamente.
  Na consulta remota sequencial de 31/10/2026, 47 grupos retornaram Parquet
  nacional de 2024; `HEPA` retornou 2023 e `INFL` não retornou Parquet nos anos
  2020–2024. A ausência temporal é registrada como condição da fonte, nunca
  convertida em lote vazio ou sucesso falso.

## 1. Promover a release IBGE

```bash
python -m app.pipeline.reference.ibge.refresh \
  --root /data/reference/ibge \
  --catalog-id ibge-dtb-2025 \
  --reference-year 2025 \
  --dtb-url 'https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/2025/DTB_2025.zip' \
  --expected-sha256 d077a0e48c36cf18bcc96268b4a436200c014c6b8522c1a62d894acaf39dad27
```

Verifique `active.json`, `manifest.json`, o status `VALIDATED`, as 27 UFs e a
contagem esperada de municípios. Se a validação falhar, preserve a release
ativa anterior e não prossiga.

## 2. Ingerir CNES nacional com retomada

```bash
python -m app.pipeline.run_cnes \
  --catalog-root /data/reference/ibge \
  --all-brazil \
  --page-size 100 \
  --request-timeout 60 \
  --workers 8 \
  --continue-on-error \
  --checkpoint /data/reference/cnes-2025.json
```

O checkpoint deve permanecer associado à mesma release, escopo, tamanho de
página, timeout e número de workers. Uma falha classificada produz um lote
`PARTIAL`; corrija ou retente antes de promover esse lote como completo.
Municípios já persistidos não devem ser consultados novamente na retomada.

Antes de a Gold ler o lote, `metadata.json` precisa declarar `COMPLETED`,
`batch_id`, contagem de linhas, cobertura municipal e a mesma identidade
(`ibge_catalog_id` + SHA-256) da release selecionada. Lotes sem metadata,
parciais, com cobertura insuficiente ou release divergente são rejeitados.

Para uma execução estrita, remova `--continue-on-error`; nesse modo a primeira
falha interrompe o lote e nenhum resultado parcial deve ser tratado como
homologação nacional.

## 3. Executar SINAN em `serving`

```bash
python -m app.pipeline.run_load \
  --disease DENG \
  --year 2024 \
  --catalog-root /data/reference/ibge \
  --all-brazil \
  --cnes-batch-id 20261031T120000Z
```

O `cnes-batch-id` deve ser substituído pelo lote efetivamente homologado. A
execução bloqueia divergência de release, hash, escopo, doença, ano, métricas
Gold, código municipal inválido ou UF divergente. A publicação PostgreSQL é
transacional e só deve ser considerada concluída após a validação independente
do total da Silver.

O município de `dim_unidade_saude` vem exclusivamente de `cd_mun_unidade`,
resolvido do próprio registro CNES. `cd_mun` da notificação nunca é usado como
fallback para a FK da unidade.

As métricas globais da execução são gravadas uma única vez em
`analytics.pipeline_execution_metrics`. As colunas de métricas mantidas em
`analytics.pipeline_publications` são legadas e ficam zeradas; relatórios não
devem somá-las por município.

## 4. Backup antes da publicação e rollback

Antes de uma publicação nacional, crie e valide um backup consistente do banco
de serving. O diretório deve estar em armazenamento persistente protegido pelo
ambiente, não no volume efêmero do container:

```bash
backup_dir="/var/backups/nss/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
pg_dump --format=custom --no-owner --no-acl \
  --file="$backup_dir/situacao_saude.dump" \
  --dbname="$DATABASE_URL"
pg_restore --list "$backup_dir/situacao_saude.dump" >/dev/null
sha256sum "$backup_dir/situacao_saude.dump" > "$backup_dir/SHA256SUMS"
```

Se uma etapa falhar antes do commit, a transação é revertida e o snapshot
anterior continua servível. Confirme isso consultando a última publicação e o
`batch_id` antes de retomar.

Se uma publicação já confirmada for considerada incorreta, não apague fatos
manualmente nem tente reconstruí-los a partir de `pipeline_publications`: essa
tabela guarda métricas por município, não o histórico completo dos fatos.
Acione o procedimento de restauração aprovado pela operação, preferivelmente
restaurando o dump em uma instância substituta, validando migrations,
contagens e healthchecks, e só então fazendo o cutover controlado. Registre o
ID do backup, seu SHA-256, o batch revertido e o novo batch de recuperação.

O teste de restore em pré-produção é obrigatório antes do rollout nacional;
sem ele, existe fallback transacional, mas não há evidência de rollback de uma
publicação já confirmada.

## 5. Fallback e retomada

Se o IBGE estiver indisponível durante o processamento, use somente a release
local aprovada. Não execute fallback por nome, proximidade ou truncamento
arbitrário de código. Se não houver release válida, falhe antes da Gold.

Se o CNES falhar, mantenha o checkpoint e o lote parcial identificados; não
misture Bronzes de releases ou parâmetros diferentes. Depois de corrigir a
causa, retome com os mesmos argumentos e valide o metadata novamente.

## 6. Critérios de encerramento

- release IBGE, hash e escopo estão registrados no metadata Gold e na
  publicação;
- todos os municípios selecionados têm resultado ou erro classificado;
- `invalid_municipality_rows` e `uf_mismatch_rows` atendem à política aprovada;
- o total independente da Silver coincide com a Gold/publicação;
- o lote CNES está fixado e consultável;
- rollback ou falha de atualização preservou a release ativa anterior;
- logs, checkpoints e manifestos foram arquivados junto da execução.

## 7. Verificação operacional e observabilidade

Antes de promover a publicação, confirme que o serviço de migration terminou
com sucesso e que o banco está na revisão esperada:

```bash
docker compose run --rm migrate
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c 'SELECT version_num FROM alembic_version;'
```

Com o profile local de observabilidade ativo, valide Prometheus, Pushgateway e
Grafana pelos endpoints publicados:

```bash
docker compose --profile observability ps
curl -fsS http://localhost:9090/-/ready
curl -fsS http://localhost:9091/-/ready
curl -fsS -u "$GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD" \
  http://localhost:3000/api/ruler/grafana/api/v1/rules
```

No overlay de produção, as portas não são publicadas. Execute os healthchecks
dentro da rede Compose e consulte a API autenticada por um bastion ou proxy
interno autorizado:

```bash
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability exec -T prometheus \
  wget -qO- http://localhost:9090/-/ready
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability exec -T pushgateway \
  wget -qO- http://localhost:9091/-/ready
docker compose -f docker-compose.yml -f docker-compose.production.yml \
  --profile observability exec -T grafana \
  wget -qO- http://localhost:3000/api/health
```

As regras `nss-pipeline-stage-failure` e `nss-pipeline-dropped-rows` apenas
avaliam o estado no Grafana. A entrega para e-mail, Slack ou PagerDuty exige
contact point e policy configurados pela operação; credenciais não devem ser
versionadas neste repositório.

Uma execução parcial não deve ser rotulada como rollout nacional concluído.
