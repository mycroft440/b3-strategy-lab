# halloween_effect

Familia: sazonalidade

## Como funciona

Efeito Halloween: comprado de novembro a abril e em caixa de maio a outubro.

## Configuracao

```text
entry_month=11;exit_month=5
```

## Entrada e saida

A funcao produz um sinal binario long-only. Estrategias com estado mantem a posicao ate que uma regra explicita de saida seja confirmada.

Regras deterministicas completas: [../../../docs/extended_strategies.md](../../../docs/extended_strategies.md).

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
