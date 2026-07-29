# rsi_reversion_atr

Familia: reversao

## Como funciona

Reversao por RSI com stop de volatilidade por ATR.

## Configuracao

```text
rsi_period=14;lower=50.0;upper=80.0;atr_period=14;atr_mult=3.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
