# trend_pullback

Familia: reversao

## Como funciona

Compra pullback em tendencia positiva.

## Configuracao

```text
trend_window=200;rsi_period=14;lower=40.0;upper=70.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
