# rsi_reversion

Familia: reversao

## Como funciona

Compra sobrevenda por RSI e sai em sobrecompra.

## Configuracao

```text
rsi_period=14;lower=30.0;upper=70.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
