# mfi_efi_confirm

Familia: volume_hibrido

## Como funciona

MFI e Elder Force Index confirmam entrada e saida.

## Configuracao

```text
mfi_period=14;efi_period=13;entry_mfi=55.0;exit_mfi=45.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
