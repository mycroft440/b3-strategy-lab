# ema_rsi_stochastic_adx_50_100

Familia: avancada

## Como funciona

Refinamento avancado com tendencia, osciladores e controle de saida.

## Configuracao

```text
fast=50;slow=100;rsi_period=14;stoch_period=21;adx_period=21;adx_threshold=20.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
