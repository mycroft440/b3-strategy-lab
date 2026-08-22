# Metodologia: pesquisa, replay realista e conta de corretora exata

O laboratório separa três alegações que não devem ser misturadas.

## Nível 1 — pesquisa retrospectiva

A matriz rápida existe para comparar muitas estratégias/gerenciamentos e localizar
hipóteses. Resultados desse nível podem conter seleção retrospectiva e não são
reconstruções de uma conta real.

## Nível 2 — replay realista/certificado de dados públicos

`scripts/run_realistic_pipeline.py` reconstrói semanalmente, de forma point-in-time,
o conjunto histórico elegível de **ações ON/PN** da B3 dentro do escopo tributário
configurado. A seleção não exige sobrevivência futura, usa somente informações
anteriores à decisão, sinais no fechamento e execução no pregão seguinte.

O caminho realista inclui:

- universo point-in-time survivorship-safe por liquidez histórica trailing;
- escopo de instrumentos `ON_PN_SHARES_ONLY`; UNITS, BDRs, ETFs, fundos e outras
  classes ficam fora até existir tratamento específico implementado e documentado;
- COTAHIST oficial, OHLC bruto, volume de quantidade, negócios e volume financeiro;
- mercado padrão `010`/BDI `02` e fracionário `020`/BDI `96` separados;
- quantidades inteiras, caixa, preço médio e ledger de negociações;
- splits/grupamentos e mudanças de ticker fail-closed;
- dividendos/JCP em ledger separado, com certificação de cobertura quando disponível;
- recebíveis de proventos adquiridos, mas ainda não pagos, reconhecidos no patrimônio
  sem se tornarem caixa investível antes do pagamento;
- tarifas temporais, custos configuráveis e slippage explícito;
- IRRF ordinário, créditos, apuração mensal, escrow de DARF e acumulação do mínimo;
- walk-forward separado da execução retrospectiva contínua.

### Isolamento físico do replay point-in-time

O replay realista não reutiliza como destino os artefatos mutáveis da pesquisa ampla.
Por padrão ele grava e lê:

- candles: `data/candles_point_in_time/`;
- ações corporativas: `data/actions_point_in_time/`;
- manifests: `data/manifests_point_in_time/`;
- evidência de quantidade: `data/corporate_actions/point_in_time_split_evidence.json`.

Isso impede que um replay curto, por exemplo encerrado em 2018, trunque candles ou
ações corporativas usados pela matriz de pesquisa de período maior.

`--dataset-split-evidence` existe somente como alias de compatibilidade. No modo
realista ele **precisa ser idêntico** a `--split-evidence`; dois caminhos diferentes
são rejeitados. Assim, o mesmo ledger de splits que é auditado também é aquele cujo
hash entra nos manifests dos candles.

O auditor reabre cada manifest 1D point-in-time com o mesmo arquivo de evidência e
executa `verify_dataset()`. Manifest ausente, hash divergente, action ledger divergente,
candle divergente ou série que ultrapasse o horizonte declarado impedem a certificação.

## Corte causal e universo point-in-time

O construtor survivorship-safe é:

```powershell
python scripts\build_survivorship_safe_realistic_universe.py --download --start 2018-01-02
```

Quando `--end` é informado, o construtor usa somente observações com data menor ou
igual à última sessão B3 do horizonte. Isso vale também para símbolos de continuidade
do mesmo ISIN: um ticker que só passa a existir depois de `--end` não pode aparecer em
`market_data_tickers` de um replay anterior.

O sincronizador point-in-time corta COTAHIST em `selection_end` antes da auditoria de
splits, volume, proventos ou criação de candles. Se os dados não alcançarem exatamente
a última sessão declarada, o build falha em vez de completar a janela com informação
posterior.

Cada decisão semanal considera somente a janela trailing configurada, presença mínima
e volume financeiro médio conhecidos até aquela data. Não usa continuidade futura,
retorno futuro, composição atual de índice ou a antiga lista fixa de 40 ações.

Símbolos históricos ligados por continuidade de ISIN podem entrar em
`market_data_tickers` sem ganhar elegibilidade de seleção. Eles existem apenas para
preservar histórico, posições e eventos.

A estratégia/modelo escolhido ainda pode ser retrospectivo; isso é reportado
separadamente como `RETROSPECTIVE_HYPOTHESIS_REPLAY`.

## Transições de ticker: conteúdo e hash precisam coincidir

`scripts/build_ticker_transitions.py` autoaprova somente mudanças 1:1 sustentadas por
continuidade do mesmo ISIN e conhecidas até o horizonte do replay. Desaparecimento
recente ou antigo sem explicação é bloqueador; a antiga tolerância implícita de 45 dias
não representa aprovação.

O manifest de transições registra:

- `transition_file`;
- `transition_csv_sha256`;
- `transition_row_count`;
- `coverage_end`;
- escopo de `market_data_tickers`;
- estado `complete`.

A auditoria standalone, o walk-forward direto e o runner certificado verificam o
SHA-256 e a contagem do **mesmo CSV consumido pelo motor**. Alterar uma linha do CSV
sem regenerar o manifest invalida a certificação.

## Candles, volume e execução

O pipeline oficial retém campos brutos e normalizados. Splits normalizam preço e
quantidade de forma coerente. O auditor de integridade verifica OHLC, volume,
ordenação, duplicatas, fatores de ajuste e incoerências de dados.

No caminho realista, uma quantidade como 114 ações pode exigir duas pernas: 100 no
mercado padrão e 14 no fracionário. Se a cotação necessária não existir, a execução
falha; o programa não copia silenciosamente a abertura de outro mercado.

Quando existe corretagem fixa, a unidade de cobrança também precisa ser conhecida.
O perfil certificado suporta `fixed_fee_application=per_market_order_leg`: uma ordem
`010` e uma ordem `020` são duas pernas e recebem duas parcelas fixas quando essa é a
regra documental da corretora. Tarifa fixa positiva com unidade não comprovada bloqueia
a certificação.

### O que o preço de abertura NÃO prova

Mesmo com todos os inputs públicos certificados, o COTAHIST diário fornece o preço de
abertura observado do mercado; ele não prova que uma ordem hipotética específica teria
recebido exatamente aquele fill sem impacto, prioridade ou alteração do leilão.
Portanto:

- `counterfactual_execution_exact` é sempre `false`;
- a flag legada `conditional_account_reconstruction_exact` é sempre `false`;
- um replay que passa todos os gates recebe, no máximo,
  `CERTIFIED_DETERMINISTIC_OFFICIAL_OPEN_REPLAY`.

Use preferencialmente `scripts/run_certified_realistic_replay.py`. O arquivo
`scripts/run_exact_realistic_reconstruction.py` foi mantido por compatibilidade e não
emite classificação de execução exata.

## Proventos em dinheiro

`scripts/sync_point_in_time_universe_realistic.py` sincroniza os dados necessários para
todos os `market_data_tickers`. Dividendos/JCP ficam em ledger separado.

A data-com cria um direito econômico somente **depois do fechamento daquela sessão**.
Do pregão seguinte até o pagamento, esse direito entra no patrimônio como recebível
não investível. O pagamento nunca pode ficar disponível antes do direito. No pagamento,
o recebível é substituído por caixa e o entitlement é consumido, impedindo crédito
duplicado.

JCP é reconhecido líquido da retenção conhecida. Para dividendos de 2026 em diante,
parcelas conhecidas do mesmo pagador e mês são acumuladas; quando o líquido depende de
exceção/transição não comprovada, o replay falha fechado.

Ausência de erro de parsing não prova cobertura histórica total de proventos. A
certificação de cobertura vincula período, todos os símbolos de dados de mercado,
evidências e hashes dos arquivos. Ela exige revisão humana explícita; o pipeline não
fabrica automaticamente uma atestação de completude.

## Splits, grupamentos e bonificações: quantidade não é a mesma coisa que base fiscal

O ledger de share-count cobre desdobramentos, grupamentos e bonificações para manter a
quantidade e a continuidade de preços. Porém a regra tributária de uma **bonificação em
ações** não é a mesma de um simples desdobramento.

Para desdobramento, conservar o custo total anterior é compatível com a continuidade
de custo. Já a bonificação pode acrescentar custo de aquisição correspondente ao
lucro/reserva capitalizado atribuível ao acionista. O motor atual ainda não consome e
aplica esse valor específico ao preço médio fiscal.

Consequentemente, o código é fail-closed:

- qualquer venda no mesmo ticker depois de uma bonificação é marcada como dependente
  de base fiscal não implementada;
- o risco acompanha mudanças 1:1 de ticker, portanto renomear o papel não elimina o
  bloqueio;
- mesmo que um arquivo futuro contenha `tax_basis_per_new_share`, isso **não libera** a
  certificação enquanto o motor não aplicar e testar esse valor no custo médio;
- o replay realista geral pode continuar como estimativa, com a limitação exposta no
  `validity`;
- o runner certificado rejeita a classificação certificada quando o ganho realizado
  depende dessa base.

Essa escolha é deliberadamente conservadora: pode bloquear casos em que as ações
vendidas foram compradas apenas depois da bonificação, mas não permite certificar em
silêncio um ganho tributável com custo possivelmente incorreto.

## Custos e impostos

`data/fees/b3_equity_fee_schedule.json` contém a parcela B3 por período. Tarifas da
corretora são separadas e precisam de perfil documentado para o replay certificado.

O ledger atual de operações comuns modela:

- isenção mensal no escopo de ações ON/PN configurado;
- alíquota ordinária e prejuízo acumulado;
- IRRF de 0,005% como antecipação/crédito quando aplicável;
- taxas de compra incorporadas ao custo médio;
- taxas de venda reduzindo o ganho realizado;
- apuração causal por mês;
- obrigação apurada retirada do caixa investível para `tax_escrow`;
- pagamento de DARF sem dupla redução do patrimônio;
- acumulação de valores abaixo do mínimo de pagamento implementado.

A apuração de um mês completo é reconhecida na própria curva no fechamento da última
sessão daquele mês, não apenas no primeiro pregão do mês seguinte.

### Replay encerrado no meio de um mês

O último mês é um caso diferente. O resultado final precisa reconhecer o passivo já
produzido pelas operações observadas até `--end`, mas o software não conhece operações
que ocorreriam depois do fim do replay. Por isso o relatório sempre expõe:

- `terminal_tax_month`;
- `terminal_tax_finalized_through`;
- `terminal_month_full_calendar_activity_known=false`;
- `terminal_month_assumption`.

A hipótese é explícita: a obrigação terminal usa somente vendas/ganhos da estratégia
observados até a data final e, se o mês ainda não terminou, pressupõe **nenhuma operação
adicional da estratégia naquele mesmo mês**. Uma operação posterior poderia mudar
limite de isenção, prejuízo acumulado, IRRF e DARF.

A tributação mínima anual de altas rendas de 2026+ depende do contexto do CPF como um
todo e permanece explicitamente `OUT_OF_SCOPE` no replay isolado.

## Replay certificado de conta pequena

O runner certificado ainda usa um envelope conservador de pequena conta. Ele verifica
patrimônio, vendas diárias e vendas mensais contra R$20 mil e rejeita o resultado se
sair desse escopo. Isso reduz dependência de modelagem tributária mais ampla, mas não
substitui os demais gates: proventos, transições, corretora, bonificação, seleção de
estratégia e execução continuam verificações separadas.

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
10. revisão de normalização identificada e vinculada aos arquivos normalizados.

O caixa precisa fechar em tolerância de meio centavo e cada quantidade precisa fechar
exatamente. Venda acima da posição reconstruída, evento fora da janela, documento
ausente, hash alterado, cobertura incompleta ou qualquer diferença de caixa/posição
rejeitam a classificação exata.

Os modelos ficam em `data/personal_account_examples/` e não constituem evidência real.
Documentos privados não devem ser commitados neste repositório público.

## Auditoria dos inputs públicos

```powershell
python scripts\audit_realistic_backtest_inputs.py
```

Campos principais:

- `ready_for_realistic_estimate`: estrutura mínima para estimativa;
- `ready_for_certified_market_inputs`: dados públicos/corporativos fortes o bastante
  para o replay certificado de inputs;
- `ready_for_exact_historical_account_claim`: campo legado, sempre `false` para
  contrafactuais de dados públicos;
- `counterfactual_execution_exact`: sempre `false`.

A auditoria certificada exige, entre outros itens, que o manifest de transições esteja
criptograficamente ligado ao CSV consumido. O walk-forward direto aplica o mesmo gate.

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
