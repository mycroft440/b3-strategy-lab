# rsi_cross_reversion

Familia: reversao

## Como funciona

Entra quando o RSI recupera acima do limite inferior.

## Configuracao

```text
rsi_period=14;lower=50.0;upper=80.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
