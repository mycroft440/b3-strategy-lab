# donchian_80_30_trend

Familia: tendencia

## Como funciona

Donchian mais lento 80/30 para tendencias prolongadas.

## Configuracao

```text
entry_lookback=80;exit_lookback=30
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
