# donchian_40_20_trend

Familia: tendencia

## Como funciona

Donchian 40/20: rompe maxima de 40 e sai na minima de 20.

## Configuracao

```text
entry_lookback=40;exit_lookback=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
