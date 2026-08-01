# laguerre_rsi_reversal

Familia: reversao

## Como funciona

Laguerre RSI de Ehlers: recuperacao da sobrevenda com saida apos sobrecompra.

## Configuracao

```text
gamma=0.5;lower=0.2;upper=0.8
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
