# cmf_price_trend

Familia: tendencia_volume

## Como funciona

Tendencia de preco com CMF acima de limiar positivo.

## Configuracao

```text
cmf_period=21;price_period=50;entry_cmf=0.03;exit_cmf=-0.02
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
