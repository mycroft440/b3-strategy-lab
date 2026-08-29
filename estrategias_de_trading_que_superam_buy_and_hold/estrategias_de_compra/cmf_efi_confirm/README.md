# cmf_efi_confirm

Familia: volume_hibrido

## Como funciona

Chaikin Money Flow e Force Index simultaneamente positivos.

## Configuracao

```text
cmf_period=21;efi_period=13
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
