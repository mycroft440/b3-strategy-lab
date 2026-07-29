# sma_stop

Familia: tendencia

## Como funciona

Segue media simples com stop percentual a partir do topo.

## Configuracao

```text
sma_window=200;stop_pct=0.2
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
