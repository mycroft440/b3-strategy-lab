# rsi14_reversion_25_60

Familia: reversao

## Como funciona

Reversao comprada por RSI com filtro de tendencia e permanencia maxima opcionais.

## Configuracao

```text
rsi_period=14;lower=25.0;upper=60.0;trend_window=0;max_hold=30
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
