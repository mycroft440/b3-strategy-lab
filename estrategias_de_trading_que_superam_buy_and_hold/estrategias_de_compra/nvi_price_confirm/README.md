# nvi_price_confirm

Familia: tendencia_volume

## Como funciona

NVI acima da EMA e preco acima da media.

## Configuracao

```text
nvi_ema=100;price_sma=100
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
