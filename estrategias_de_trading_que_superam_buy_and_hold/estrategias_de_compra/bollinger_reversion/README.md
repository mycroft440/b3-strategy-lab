# bollinger_reversion

Familia: reversao

## Como funciona

Compra na banda inferior de Bollinger e sai no retorno ao centro.

## Configuracao

```text
window=20;num_std=2.0;exit_z=0.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
