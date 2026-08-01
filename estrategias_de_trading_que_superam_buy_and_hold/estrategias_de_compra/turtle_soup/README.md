# turtle_soup

Familia: reversao

## Como funciona

Turtle Soup long-only: falso rompimento da minima com saida por media, ATR ou tempo.

## Configuracao

```text
lookback=20;sma_window=5;atr_period=14;stop_atr=0.5;hold_limit=5
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
