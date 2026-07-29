# breakout

Familia: rompimento

## Como funciona

Compra rompimento de maxima e sai na perda de minima.

## Configuracao

```text
lookback=55;exit_lookback=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
