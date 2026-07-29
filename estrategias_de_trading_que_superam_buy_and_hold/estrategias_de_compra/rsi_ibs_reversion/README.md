# rsi_ibs_reversion

Familia: reversao

## Como funciona

Combina RSI curto e IBS baixo para entrada.

## Configuracao

```text
rsi_period=2;lower=5.0;upper=60.0;ibs_lower=0.25;ibs_upper=0.75;trend_window=200;max_hold=10
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
