# Painéis de backtest em um clique

Há dois painéis separados porque eles respondem perguntas diferentes:

- **Matriz de pesquisa**: cruza estratégias e gerenciamentos no período completo.
  É retrospectiva, exclui proventos e impostos e não autoriza alegação de retorno
  real.
- **Validação realista**: usa universo point-in-time, mercado padrão e
  fracionário, eventos em caixa, tarifas, slippage e tributação modelada. O
  relatório informa se a reconstrução é estimativa ou se possui certificação
  suficiente para uma alegação exata.

## Abrir no Windows

Dê dois cliques no painel desejado:

- `abrir_painel_backtest.bat` — matriz de pesquisa;
- `abrir_painel_realista.bat` — validação realista.

No Linux/macOS, execute `./abrir_painel_backtest.sh` ou
`./abrir_painel_realista.sh`. O navegador abre automaticamente em uma porta
local. Também é possível iniciar pelos comandos:

```bash
python scripts/realistic_combination_backtest_control_panel.py
python scripts/realistic_backtest_control_panel.py
```

## Matriz de pesquisa

O painel permite selecionar qualquer subconjunto do universo canônico sem
substituir ativos. Antes da execução, por padrão ele:

1. atualiza o COTAHIST e os eventos oficiais;
2. valida hashes, cobertura, atualidade e candles;
3. audita a consolidação de volume dos mercados padrão (`010`) e fracionário
   (`020`) em todos os 17 consumidores de volume;
4. executa a matriz em paralelo;
5. mostra o período **efetivamente** usado, custos, slippage e o primeiro colocado.

Os padrões são R$ 1.000, 3,2 bps de custos e 10 bps de slippage por ordem. O
paralelismo recomendado usa até 8 processos; o campo pode ser ajustado entre 1 e
o número de CPUs detectado. A data final vazia significa o último pregão comum
verificado — nunca a data do calendário simplesmente digitada.

Arquivos temporários e resultados:

- `.cache/control_panel/selected_universe_combinations.json`;
- `reports/control_panel_combinations.log`;
- `reports/control_panel_strategy_management_combinations.csv.gz`;
- `reports/control_panel_strategy_management_combinations.manifest.json`.

## Validação realista

O painel realista controla data inicial/final, capital e atualização de dados. Ele
executa as variantes `raw_gap` e `economic_gap`, além do walk-forward configurado,
e apresenta a classificação de qualidade dos dados. A falta de certificação
histórica de proventos não é escondida: `cash_events_complete=false` e a execução
permanece rotulada como estimativa.

Arquivos principais:

- `.cache/control_panel/selected_universe.json`;
- `reports/control_panel_backtest.log`;
- `reports/control_panel_realistic_pipeline_status.json`.

## Regras de segurança

- BOAC34 permanece explicitamente excluída;
- tickers fora da lista permitida são recusados;
- não há substituição silenciosa de ativos;
- preço ausente necessário para execução ou marcação interrompe a simulação;
- o painel de pesquisa não é rotulado como resultado de dinheiro real;
- o painel realista não transforma cobertura incompleta em certificação.
