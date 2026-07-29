# connors_rsi_reversion

Familia: reversao

## Como funciona

Reversao por Connors RSI.

## Configuracao

```text
rsi_period=3;streak_rsi_period=2;rank_period=100;lower=20.0;upper=70.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
