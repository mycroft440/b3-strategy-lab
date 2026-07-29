# rsi_bollinger_14_30_bb30_25

Familia: combinada

## Como funciona

RSI em sobrevenda confirmado pela banda inferior de Bollinger.

## Configuracao

```text
rsi_period=14;lower=30.0;upper=70.0;window=30;num_std=2.5;trend_window=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
