# rsi2_trend_reversion

Familia: reversao

## Como funciona

Reversao por RSI curto com filtro de tendencia e saida por media curta.

## Configuracao

```text
rsi_period=2;lower=5.0;upper=70.0;trend_window=200;sma_window=5;max_hold=10
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
