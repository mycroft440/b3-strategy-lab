# mass_index_reversal

Familia: reversao

## Como funciona

Mass Index: lado comprador da reversal bulge com saida por EMA ou tempo.

## Configuracao

```text
ema_period=9;sum_period=25;bulge_level=27.0;trigger_level=26.5;exit_window=9;hold_limit=20
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
