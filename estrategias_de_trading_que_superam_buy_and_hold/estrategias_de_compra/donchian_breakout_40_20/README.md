# donchian_breakout_40_20

Familia: rompimento

## Como funciona

Canal de Donchian com maxima anterior para entrada e minima anterior para saida.

## Configuracao

```text
entry_window=40;exit_window=20;trend_window=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
