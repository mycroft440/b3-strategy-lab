# Metodologia: pesquisa, replay realista e conta de corretora exata

O laboratório separa três alegações que não devem ser misturadas.

## Nível 1 — pesquisa retrospectiva

A matriz rápida existe para comparar muitas estratégias/gerenciamentos e localizar
hipóteses. Resultados desse nível podem conter seleção retrospectiva e não são
reconstruções de uma conta real.

## Nível 2 — replay realista/certificado de dados públicos

`scripts/run_realistic_pipeline.py` reconstrói semanalmente, de forma point-in-time,
o conjunto histórico elegível de **ações ON/PN** da B3 dentro do escopo tributário
certificado. A seleção não exige sobrevivência futura, usa somente informações
anteriores à decisão, sinais no fechamento e execução no pregão seguinte.

O caminho realista inclui:

- universo point-in-time survivorship-safe por liquidez histórica trailing;
- escopo certificado de instrumentos `ON_PN_SHARES_ONLY`; UNITS, BDRs, ETFs, fundos e
  outras classes ficam fora até existir tratamento específico implementado e documentado;
- COTAHIST oficial e volumes financeiros do mercado usado;
- mercado padrão `010`/BDI `02` e fracionário `020`/BDI `96` separados;
- quantidades inteiras, caixa, preço médio e ledger de negociações;
- splits/grupamentos e mudanças de ticker fail-closed;
- dividendos/JCP em ledger separado, com certificação de cobertura quando disponível;
- recebíveis de proventos adquiridos, mas ainda não pagos, reconhecidos no patrimônio
  sem se tornarem caixa investível antes do pagamento;
- tarifas temporais, custos configuráveis e slippage explícito;
- IRRF ordinário, créditos, apuração mensal, escrow de DARF e acumulação do mínimo de R$10;
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

Use preferencialmente `scripts/run_certified_realistic_replay.py`. O arquivo
`scripts/run_exact_realistic_reconstruction.py` foi mantido por compatibilidade, mas
não emite classificação de execução "exact".

## Universo point-in-time

O universo certificado usa o histórico de ações ON/PN de companhias dentro do escopo
definido. Cada decisão semanal considera somente a janela trailing configurada,
presença mínima e volume financeiro médio conhecido até aquela data. Não usa
continuidade futura, retorno futuro, composição atual de índice ou a antiga lista
fixa de 40 ações.

Símbolos históricos ligados por continuidade de ISIN podem entrar em
`market_data_tickers` sem ganhar elegibilidade de seleção. Eles existem para preservar
histórico/posição/eventos. Por isso, certificações de proventos precisam abranger o
**conjunto completo `market_data_tickers`**, e não somente o `union` selecionável.

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

Quando existe corretagem fixa, a unidade de cobrança também precisa ser conhecida.
O perfil certificado suporta `fixed_fee_application=per_market_order_leg`: uma ordem
`010` e uma ordem `020` são tratadas como duas pernas/ordens e recebem duas parcelas
fixas quando essa é a regra documental da corretora. Uma tarifa fixa positiva com
unidade de cobrança não comprovada bloqueia a certificação.

## Proventos e ações corporativas

`scripts/sync_point_in_time_universe_realistic.py` sincroniza candles, ações
corporativas e proventos para todos os `market_data_tickers`. Marcadores de mudança de
quantidade sem evidência suficiente interrompem a construção. Dividendos/JCP ficam em
ledger separado.

A data-com cria um direito econômico apenas **depois do fechamento daquela sessão**.
Do pregão seguinte até o pagamento, esse direito entra no patrimônio como recebível
não investível. No pagamento, o recebível é substituído por caixa, evitando tanto um
drawdown ex-provento fictício quanto reinvestimento antecipado.

JCP é reconhecido líquido da retenção conhecida. Para dividendos de 2026 em diante,
parcelas conhecidas do mesmo pagador e mês são acumuladas; se o valor ultrapassar a
faixa cujo líquido depende de exceções/transições não comprovadas, o replay falha
fechado em vez de presumir um valor líquido.

Ausência de erro de parsing não prova cobertura histórica total de proventos. A
certificação de cobertura vincula período, **todos os símbolos de dados de mercado**,
evidências e hashes dos arquivos. Sem ela, o resultado permanece estimativa/
certificação parcial, nunca conta de corretora exata.

## Custos e impostos

`data/fees/b3_equity_fee_schedule.json` contém a parcela B3 por período. Tarifas da
corretora são separadas e precisam de perfil documentado para o replay certificado.
O modo realista geral pode usar slippage e custos modelados; essas premissas ficam
visíveis no relatório.

O ledger atual de operações comuns modela:

- isenção mensal dentro do escopo de ações ON/PN configurado;
- alíquota ordinária e prejuízo acumulado;
- IRRF de 0,005% como antecipação/crédito quando aplicável;
- apuração causal por mês;
- obrigação apurada retirada do caixa investível para `tax_escrow`;
- pagamento do DARF no vencimento modelado sem dupla redução do patrimônio;
- acumulação de DARF inferior a R$10.

O relatório separa `final_equity`, `brokerage_final_equity`,
`outstanding_accrued_tax_liability`, `net_equity_after_accrued_tax`,
`unpaid_distribution_receivable`, `ordinary_irrf_withheld` e `darf_paid`.

A tributação mínima anual de altas rendas de 2026+ depende do contexto do CPF como um
todo e permanece explicitamente `OUT_OF_SCOPE` no replay isolado.

No Nível 3 abaixo, imposto, taxa, provento e qualquer outro movimento de caixa vêm
do extrato real e não são recalculados para substituir o que aconteceu na conta.

## Nível 3 — reconciliação EXATA da conta da corretora realmente executada

A única rotina autorizada a emitir
`ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION` é:

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

1. snapshot inicial documentado com `boundary=START_OF_DAY`;
2. fills realmente executados, com preço/quantidade da corretora;
3. data de negociação e data de liquidação separadas;
4. todo movimento de caixa não pertencente ao principal da compra/venda: taxas,
   impostos, proventos, depósitos, saques, custódia etc.;
5. ajustes de posição sem negociação para splits, grupamentos, bonificações,
   conversões e mudanças de ticker;
6. snapshot final documentado com `boundary=END_OF_DAY`;
7. `source_document` e SHA-256 em cada linha normalizada;
8. arquivos-fonte privados presentes em `--evidence-root`, com bytes iguais ao hash;
9. manifesto de cobertura contínua por extratos de conta;
10. revisão de normalização identificada, posterior ao período, vinculada por SHA-256
    a cada arquivo normalizado consumido pelo runner.

O caixa precisa fechar em tolerância de meio centavo e cada quantidade precisa fechar
exatamente. Venda acima da posição reconstruída, evento fora da janela, documento
ausente, hash alterado, cobertura incompleta ou qualquer diferença de caixa/posição
rejeitam a classificação exata.

Os modelos ficam em `data/personal_account_examples/`. Eles usam hashes zerados,
`coverage_complete=false` e `normalization_verified=false` de propósito; não são
evidência válida.

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

A auditoria também verifica explicitamente o escopo `ON_PN_SHARES_ONLY`, a coerência
de `market_data_tickers` e se a certificação de proventos cobre inclusive os símbolos
de continuidade histórica.

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
