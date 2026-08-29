# mfi_price_trend

Familia: tendencia_volume

## Como funciona

Typical Price em tendencia com confirmacao do MFI.

## Configuracao

```text
mfi_period=14;price_period=50;entry_mfi=52.0;exit_mfi=45.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
