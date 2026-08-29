# sma_triple_alignment_trend

Familia: tendencia

## Como funciona

Alinhamento de tres SMAs em ordem de alta.

## Configuracao

```text
fast=20;middle=50;slow=200
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
