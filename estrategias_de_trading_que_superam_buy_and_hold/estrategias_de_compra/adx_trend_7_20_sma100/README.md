# adx_trend_7_20_sma100

Familia: combinada

## Como funciona

ADX e direcionais confirmam forca compradora acima da media de tendencia.

## Configuracao

```text
adx_period=7;threshold=20.0;trend_window=100;rsi_period=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
