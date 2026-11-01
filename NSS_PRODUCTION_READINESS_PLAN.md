# Plano de prontidão para produção — NSS Pipeline

Este plano converte a auditoria independente de 31/10/2026 em um roteiro
executável para o rollout nacional, incorporando a observabilidade da branch do
Grafana sem tornar o Grafana uma dependência da publicação dos dados.

## Objetivo e definição de pronto

A pipeline estará pronta para produção quando:

1. as invariantes de identidade territorial, CNES, Gold e PostgreSQL forem
   verificadas por testes unitários e integração real;
2. cada execução publicar métricas de sucesso e falha, com dashboard e alertas
   provisionáveis de forma reproduzível;
3. CI, migrations, Compose de produção, rollback e runbook forem validados;
4. uma execução nacional autorizada for reconciliada contra as fontes e o
   escopo selecionados;
5. os gates operacionais externos — secrets, dados autorizados e roteamento de
   alertas — tiverem responsáveis e evidência de aceite.

Uma suíte verde, isoladamente, não autoriza o rollout nacional.

## Fases de execução

### Fase 0 — Baseline e controle de mudanças

- manter a branch `work/nss-pipeline` sincronizada com o GitHub;
- usar commits semânticos pequenos, cada um com teste ou documentação
  correspondente;
- acompanhar cada push pelo `gh` e guardar o URL do run no backlog;
- repetir a baseline de mutação após mudanças de contrato, distinguindo
  `killed`, `survived` e `timeout`.

Estado atual: concluída parcialmente. O acesso `gh` está confirmado e o CI do
commit `c8a9c6d` foi aprovado no run
[41261232809](https://github.com/Zadoque/NSS-pipeline/actions/runs/41261232809).
A baseline global anterior à inclusão do preflight é 7.143/9.294 mutantes
mortos, 2.124 sobreviventes e 27 timeouts; a meta global de 95% continua
pendente e não deve ser confundida com a validação funcional dos gates P0/P1.
O preflight foi posteriormente incluído no escopo com 57/57 mutantes mortos;
é necessária uma nova rodada global para atualizar o denominador consolidado.

### Fase 1 — Integridade de dados e publicação

- preservar a separação entre município da notificação (`cd_mun`) e município
  da unidade CNES (`cd_mun_unidade`);
- garantir que municípios CNES canônicos existam em `dim_municipio` antes da
  inserção da unidade, na mesma transação;
- preservar atributos cadastrais já válidos quando uma carga posterior vier
  sem enriquecimento CNES;
- aceitar em `serving` somente lote CNES explicitamente identificado, completo,
  compatível com a release IBGE e com manifesto íntegro;
- usar temporário exclusivo e lock por destino na consolidação CNES;
- verificar checksum, cobertura declarada e cobertura efetiva do Parquet;
- manter publicação atômica e snapshot anterior visível quando um gate falhar.

Evidência atual: migrations até `0010`, testes PostgreSQL para município da
unidade fora do município da notificação e preservação cadastral, manifesto
CNES v2, seleção explícita de lote em serving e locks de consolidação.

### Fase 2 — Observabilidade Grafana adaptada

- exportar por etapa `rows`, `dropped_rows`, duração, status e timestamp;
- publicar `status=failure` também em falhas fatais, sem mascarar a exceção
  original e sem fazer o Pushgateway bloquear a pipeline;
- provisionar Prometheus, Pushgateway, Grafana, datasources e dashboard por
  arquivos versionados;
- manter consultas PostgreSQL para publicações, falhas e métricas históricas;
- provisionar alertas para falha de etapa e descarte anormal de linhas;
- validar o stack completo no smoke test do CI;
- configurar contact point e notification policy produtivos fora do repositório,
  com teste de entrega e responsável operacional.

Evidência atual: dashboard e provisioning versionados, regras
`nss-pipeline-stage-failure` e `nss-pipeline-dropped-rows`, smoke test Compose
verde e testes de contrato do módulo de métricas em 151/151 mutantes mortos.

### Fase 3 — Pré-produção e ensaio de rollback

- executar `python -m app.pipeline.preflight` com o secret manager injetado;
- construir imagens a partir de commit imutável;
- aplicar `alembic upgrade head` em banco de pré-produção;
- executar uma doença/ano de fixture autorizada com lote CNES explicitamente
  fixado;
- conferir contagens Gold/PostgreSQL, métricas e alertas;
- simular falha em Bronze, Gold, CNES e PostgreSQL;
- confirmar que a publicação anterior permanece servível e que o rollback do
  snapshot não apaga dados válidos;
- registrar logs, IDs de execução, hashes e divergências.

Critério de saída: todos os gates passam sem intervenção manual não descrita no
runbook e o alerta chega ao contact point produtivo de teste.

### Fase 4 — Execução nacional controlada

- obter fixture/dados SINAN nacionais autorizados e fixar release/ano;
- fixar catálogo IBGE e escopo geográfico por hash;
- fixar `cnes_batch_id` e verificar manifesto antes de iniciar a Gold;
- executar por janela operacional com observação ativa do dashboard;
- reconciliar source/resolved/discarded, cobertura municipal, fatos e dimensões;
- aprovar publicação por checklist de duas pessoas;
- liberar leitura gradualmente e manter o snapshot anterior para fallback.

### Fase 5 — Pós-rollout

- observar falhas, descartes, latência e freshness por 24 horas;
- comparar métricas com a baseline pré-rollout;
- fechar divergências ou abrir incidente com evidência de execução;
- atualizar o runbook e o backlog somente após a reconciliação final.

## Gates externos ainda necessários

Os seguintes itens não podem ser inventados nem validados apenas no ambiente
local:

- secrets reais de PostgreSQL, Grafana e fontes;
- fixture ou acesso autorizado aos dados SINAN nacionais;
- release CNES nacional e seu manifesto assinado/hasheado;
- contact point e notification policy de produção, incluindo teste de entrega;
- ambiente de pré-produção/produção com backup, retenção e procedimento de
  rollback;
- aprovação operacional da reconciliação nacional.

Até esses itens terem evidência, o estado correto é “código preparado e rollout
bloqueado por gate operacional”, não “produção concluída”.

## Próxima ordem de trabalho

1. manter o CI do commit `c8a9c6d` como evidência de documentação/baseline;
2. revisar sobreviventes de `load`, `run_cnes` e `run_load` somente quando
   representarem contratos P0/P1 ou ausência de teste de regressão;
3. executar o ensaio PostgreSQL/CNES fora do município da notificação em um
   ambiente limpo;
4. executar o smoke de observabilidade com contact point de pré-produção;
5. preencher os gates externos e realizar o ensaio nacional controlado;
6. só depois decidir o rollout e fechar `IBGE-013`.
