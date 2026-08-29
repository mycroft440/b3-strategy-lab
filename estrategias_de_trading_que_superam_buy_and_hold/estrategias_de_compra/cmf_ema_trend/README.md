# cmf_ema_trend

Familia: tendencia

## Como funciona

Tendencia de preco por EMA confirmada por Chaikin Money Flow.

## Configuracao

```text
cmf_period=21;ema_period=100;entry_cmf=0.05;exit_cmf=-0.05
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
