# mfi_momentum_21_60_40_sma200

Familia: volume

## Como funciona

Money Flow Index combina preco e volume com filtro de tendencia.

## Configuracao

```text
period=21;entry_level=60.0;exit_level=40.0;trend_window=200
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
