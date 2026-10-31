# Runbook de rollout nacional — catálogo IBGE

Este runbook descreve uma execução nacional controlada. O processamento usa
uma release IBGE local aprovada e fixa o escopo e o lote CNES antes de iniciar
SINAN. A rede é necessária para atualizar fontes, não para resolver municípios
durante Bronze, Silver, Gold ou publicação.

## Pré-condições

- ambiente carregado pelo `flake.nix`;
- PostgreSQL disponível e migrations aplicadas;
- diretório de referência com espaço para o ZIP bruto, releases e checkpoints;
- SHA-256 confirmado por uma fonte oficial antes da promoção;
- execução de homologação concluída para a mesma release.

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

## 4. Fallback e retomada

Se o IBGE estiver indisponível durante o processamento, use somente a release
local aprovada. Não execute fallback por nome, proximidade ou truncamento
arbitrário de código. Se não houver release válida, falhe antes da Gold.

Se o CNES falhar, mantenha o checkpoint e o lote parcial identificados; não
misture Bronzes de releases ou parâmetros diferentes. Depois de corrigir a
causa, retome com os mesmos argumentos e valide o metadata novamente.

## 5. Critérios de encerramento

- release IBGE, hash e escopo estão registrados no metadata Gold e na
  publicação;
- todos os municípios selecionados têm resultado ou erro classificado;
- `invalid_municipality_rows` e `uf_mismatch_rows` atendem à política aprovada;
- o total independente da Silver coincide com a Gold/publicação;
- o lote CNES está fixado e consultável;
- rollback ou falha de atualização preservou a release ativa anterior;
- logs, checkpoints e manifestos foram arquivados junto da execução.

Uma execução parcial não deve ser rotulada como rollout nacional concluído.
