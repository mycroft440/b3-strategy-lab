# ema50_stochastic_21_30_75

Familia: combinada

## Como funciona

Media movel define a tendencia; Estocastico define o pullback e a saida.

## Configuracao

```text
average_type=ema;trend_window=50;k_period=21;lower=30.0;upper=75.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
