# nvi_dual_ema_trend

Familia: tendencia

## Como funciona

NVI acima de duas EMAs alinhadas em alta.

## Configuracao

```text
fast=50;slow=150
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
