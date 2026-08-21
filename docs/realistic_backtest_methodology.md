# Metodologia: pesquisa, replay realista e conta pessoal exata

O laboratório separa três alegações que não devem ser misturadas.

## Nível 1 — pesquisa retrospectiva

A matriz rápida existe para comparar muitas estratégias/gerenciamentos e localizar
hipóteses. Resultados desse nível podem conter seleção retrospectiva e não são
reconstruções de uma conta real.

## Nível 2 — replay realista/certificado de dados públicos

`scripts/run_realistic_pipeline.py` reconstrói o universo semanal a partir do mercado
histórico completo da B3, sem exigir sobrevivência futura. Ele usa apenas dados
anteriores à decisão, sinais no fechamento e execução no pregão seguinte.

O caminho realista inclui:

- universo point-in-time survivorship-safe por liquidez histórica trailing;
- COTAHIST oficial e volumes financeiros do mercado usado;
- mercado padrão `010`/BDI `02` e fracionário `020`/BDI `96` separados;
- quantidades inteiras, caixa, preço médio e ledger de negociações;
- splits/grupamentos e mudanças de ticker fail-closed;
- dividendos/JCP em ledger separado, com certificação de cobertura quando disponível;
- tarifas temporais, custos configuráveis e slippage explícito;
- tributação econômica, perdas e limite mensal modelados;
- walk-forward separado da execução retrospectiva contínua.

O construtor survivorship-safe é:

```powershell
python scripts\build_survivorship_safe_realistic_universe.py --download --start 2018-01-02
```

Quando `--end` é informado, o construtor infere somente os anos necessários: um ano
de aquecimento antes do início até o ano final. O pipeline propaga a mesma janela
para transições e sincronização, evitando processar anos futuros desnecessariamente.

### O que esse nível NÃO prova

Mesmo com todos os inputs públicos certificados, o COTAHIST diário fornece o preço
de abertura observado do mercado; ele não contém prova de que uma ordem hipotética
específica teria recebido exatamente aquele fill sem impacto, prioridade ou alteração
do leilão. Portanto:

- `counterfactual_execution_exact` é sempre `false`;
- a flag legada `conditional_account_reconstruction_exact` é sempre `false`;
- um replay que passa todos os gates recebe, no máximo,
  `CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY`.

O arquivo `scripts/run_exact_realistic_reconstruction.py` foi mantido por
compatibilidade, mas não emite mais classificação "exact". Ele é um runner
fail-closed de replay determinístico certificado.

## Universo point-in-time

O universo principal usa o COTAHIST histórico completo de ações/units de companhias.
Cada decisão semanal considera somente a janela trailing configurada, presença mínima
e volume financeiro médio conhecido até aquela data. Não usa continuidade futura,
retorno futuro, composição atual de índice ou a antiga lista fixa de 40 ações.

A estratégia/modelo escolhido ainda pode ser retrospectivo; isso é reportado
separadamente como `RETROSPECTIVE_HYPOTHESIS_REPLAY`.

Saídas principais:

- `data/universes/point_in_time_weekly.csv`
- `data/universes/point_in_time_union.json`
- `data/execution/b3_standard_fractional_open.csv`

## Candles, volume e execução

O pipeline oficial retém campos brutos e normalizados. Splits normalizam preço e
quantidade de forma coerente. O auditor de integridade verifica OHLC, volume,
ordenação, duplicatas, fatores de ajuste e incoerências de dados.

No caminho de conta realista, uma quantidade como 114 ações pode exigir duas pernas:
100 no mercado padrão e 14 no fracionário. Se a cotação necessária não existir, a
execução falha; o programa não copia silenciosamente a abertura de outro mercado.

## Proventos e ações corporativas

`scripts/sync_point_in_time_universe_realistic.py` sincroniza candles, ações
corporativas e proventos. Marcadores de mudança de quantidade sem evidência suficiente
interrompem a construção. Dividendos/JCP ficam em ledger separado.

Ausência de erro de parsing não prova cobertura histórica total de proventos. A
certificação de cobertura vincula período, ativos, evidências e hashes dos arquivos.
Sem ela, o resultado permanece estimativa/certificação parcial, nunca conta pessoal
exata.

## Custos e impostos

`data/fees/b3_equity_fee_schedule.json` contém a parcela B3 por período. Tarifas da
corretora são separadas e precisam de perfil documentado para o replay certificado.
O modo realista geral pode usar slippage e custos modelados; essas premissas ficam
visíveis no relatório.

O ledger tributário geral mede o ônus econômico. Ele não pretende reproduzir cada
movimento de IRRF/DARF de uma conta pessoal. O runner determinístico conservador usa
um gate de pequena conta; se o patrimônio/giro sai do escopo que o motor consegue
tratar sem aproximações adicionais, ele falha.

No Nível 3 abaixo, imposto, taxa, provento e qualquer outro movimento de caixa vêm
do extrato real e não são calculados por esse modelo.

## Nível 3 — reconciliação EXATA da conta pessoal realmente executada

A única rotina autorizada a emitir
`ACTUAL_PERSONAL_ACCOUNT_EXACT_RECONCILIATION` é:

```powershell
python scripts\reconcile_actual_personal_account.py \
  --fills <fills.csv> \
  --cash-events <cash_events.csv> \
  --position-events <position_events.csv> \
  --opening-snapshot <opening_snapshot.json> \
  --closing-snapshot <closing_snapshot.json> \
  --coverage-manifest <coverage_manifest.json> \
  --evidence-root <pasta_privada_de_fontes>
```

Esse caminho não usa preço de mercado estimado para substituir execução. Ele exige:

1. snapshot inicial documentado de caixa e posições;
2. fills realmente executados, com preço/quantidade da corretora;
3. data de negociação e data de liquidação separadas;
4. todo movimento de caixa não pertencente ao principal da compra/venda: taxas,
   impostos, proventos, depósitos, saques, custódia etc.;
5. ajustes de posição sem negociação para splits, grupamentos, bonificações,
   conversões e mudanças de ticker;
6. snapshot final documentado;
7. `source_document` e SHA-256 em cada linha normalizada;
8. arquivos-fonte privados presentes em `--evidence-root`, com bytes iguais ao hash;
9. manifesto de cobertura que abrange toda a janela, lista os documentos e declara
   `coverage_complete=true` com revisor/timestamp.

O caixa precisa fechar em tolerância de meio centavo e cada quantidade precisa fechar
exatamente. Venda acima da posição reconstruída, evento fora da janela, documento
ausente, hash alterado, cobertura incompleta ou qualquer diferença de caixa/posição
rejeitam a classificação exata.

Os modelos ficam em `data/personal_account_examples/`. Eles usam hashes zerados e
`coverage_complete=false` de propósito; não são evidência válida.

Documentos privados não devem ser commitados neste repositório público.

## Auditoria dos inputs públicos

```powershell
python scripts\audit_realistic_backtest_inputs.py
```

Campos principais:

- `ready_for_realistic_estimate`: estrutura mínima para estimativa;
- `ready_for_certified_market_inputs`: dados públicos/corporativos fortes o bastante
  para um replay certificado;
- `ready_for_exact_historical_account_claim`: campo legado, sempre `false` para
  contrafactuais baseados em dados públicos;
- `counterfactual_execution_exact`: sempre `false`.

Certificação de inputs públicos é necessária para um replay forte, mas não substitui
fills/extratos reais.

## Walk-forward e seleção de estratégia

A validade de ter escolhido uma estratégia é separada da mecânica da conta. O replay
contínuo de uma regra escolhida depois dos fatos continua retrospectivo mesmo com
universo survivorship-safe.

Use:

```powershell
python scripts\walk_forward_realistic.py --initial-cash 1000 --all-strategies
```

ou:

```powershell
python scripts\run_realistic_pipeline.py --initial-cash 1000 --walk-forward-all-strategies
```

para validar seleção em folds out-of-sample. Dados posteriores ao congelamento da
metodologia só fornecem evidência prospectiva se as regras não forem reotimizadas.

## Linguagem permitida

Para backtest público/contrafactual:

> "Sob estas regras e premissas, o replay determinístico/realista resultou em R$ X."

Não usar "fill exato", "conta exata" ou equivalente.

Para dados reais da corretora, somente quando o runner do Nível 3 retorna sucesso:

> "Os fills, movimentos de caixa e posições fornecidos reconciliam exatamente entre
> os snapshots documentais e os arquivos-fonte declarados."

Essa última frase continua limitada à cobertura documental certificada fornecida; o
software não consegue descobrir sozinho um documento externo deliberadamente omitido.
