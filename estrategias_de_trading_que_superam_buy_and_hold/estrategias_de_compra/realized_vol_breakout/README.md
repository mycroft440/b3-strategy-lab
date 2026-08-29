# realized_vol_breakout

Familia: rompimento_volatilidade

## Como funciona

Rompimento acompanhado de volatilidade realizada minima, com saida por media.

## Configuracao

```text
vol_period=63;breakout_lookback=20;min_vol=0.2;exit_sma=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
