# cci_momentum_10_0_m100_sma50

Familia: combinada

## Como funciona

CCI identifica impulso ou pullback dentro de uma tendencia de alta.

## Configuracao

```text
period=10;entry_level=0.0;exit_level=-100.0;trend_window=50
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
