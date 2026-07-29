# cci_momentum_20_50_m50_sma200

Familia: combinada

## Como funciona

CCI identifica impulso ou pullback dentro de uma tendencia de alta.

## Configuracao

```text
period=20;entry_level=50.0;exit_level=-50.0;trend_window=200
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
