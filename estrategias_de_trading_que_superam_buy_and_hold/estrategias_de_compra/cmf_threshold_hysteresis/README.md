# cmf_threshold_hysteresis

Familia: volume

## Como funciona

CMF com bandas distintas de entrada e saida para reduzir ruido.

## Configuracao

```text
period=21;entry=0.05;exit=-0.02
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
