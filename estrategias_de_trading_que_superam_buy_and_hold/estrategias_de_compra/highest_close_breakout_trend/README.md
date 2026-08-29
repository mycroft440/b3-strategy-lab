# highest_close_breakout_trend

Familia: tendencia

## Como funciona

Rompimento do maior fechamento com saida pelo menor fechamento recente.

## Configuracao

```text
entry_lookback=60;exit_lookback=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
