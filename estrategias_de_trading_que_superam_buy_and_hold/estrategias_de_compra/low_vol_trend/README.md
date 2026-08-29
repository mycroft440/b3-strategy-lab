# low_vol_trend

Familia: regime

## Como funciona

Tendencia de preco filtrada por baixa volatilidade realizada.

## Configuracao

```text
vol_period=63;trend_window=100;max_vol=0.35
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
