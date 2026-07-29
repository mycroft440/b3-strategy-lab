# ema_cross

Familia: tendencia

## Como funciona

Cruzamento de medias moveis exponenciais.

## Configuracao

```text
fast=12;slow=26
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
