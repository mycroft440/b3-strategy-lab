# mfi_trend_follow

Familia: tendencia_volume

## Como funciona

MFI forte confirmado por tendencia de preco.

## Configuracao

```text
period=14;trend_window=100;entry=55.0;exit=45.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
