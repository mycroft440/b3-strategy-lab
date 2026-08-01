# ultimate_oscillator_ehlers

Familia: tendencia

## Como funciona

Ultimate Oscillator de Ehlers: comprado acima de zero e em caixa abaixo de zero.

## Configuracao

```text
band_edge=20;bandwidth=2.0;rms_period=100
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/researched_strategies.md](../../../docs/researched_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
