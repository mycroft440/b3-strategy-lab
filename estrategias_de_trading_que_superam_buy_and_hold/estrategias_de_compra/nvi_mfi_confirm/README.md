# nvi_mfi_confirm

Familia: volume_hibrido

## Como funciona

NVI acima da EMA combinado com MFI comprador.

## Configuracao

```text
nvi_ema=100;mfi_period=14;entry_mfi=52.0;exit_mfi=45.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
