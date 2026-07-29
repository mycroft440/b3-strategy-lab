# profit_only_exit_sma200_atr4_catastrophe8

Familia: avancada

## Como funciona

Refinamento avancado com tendencia, osciladores e controle de saida.

## Configuracao

```text
sma_window=200;atr_period=21;atr_mult=4.0;catastrophe_mult=8.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
