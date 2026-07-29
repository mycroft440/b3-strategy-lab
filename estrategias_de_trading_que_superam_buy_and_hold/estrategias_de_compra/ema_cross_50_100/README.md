# ema_cross_50_100

Familia: tendencia

## Como funciona

Cruzamento de medias EMA 50/100.

## Configuracao

```text
average_type=ema;fast=50;slow=100
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
