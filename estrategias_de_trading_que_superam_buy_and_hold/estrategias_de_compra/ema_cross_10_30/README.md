# ema_cross_10_30

Familia: tendencia

## Como funciona

Cruzamento de medias EMA 10/30.

## Configuracao

```text
average_type=ema;fast=10;slow=30
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
