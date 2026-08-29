# atr_trailing_trend

Familia: tendencia

## Como funciona

Tendencia acima da EMA com trailing stop baseado em ATR.

## Configuracao

```text
trend_period=100;atr_period=20;atr_mult=3.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
