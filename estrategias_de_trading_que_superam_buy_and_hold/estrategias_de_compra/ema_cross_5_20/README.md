# ema_cross_5_20

Familia: tendencia

## Como funciona

Cruzamento de medias EMA 5/20.

## Configuracao

```text
average_type=ema;fast=5;slow=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
