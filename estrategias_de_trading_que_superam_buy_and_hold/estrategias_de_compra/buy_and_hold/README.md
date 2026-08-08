# buy_and_hold

Familia: benchmark

## Como funciona

Mantem o sinal de compra ativo em todos os candles; no teste por ativo, compra na primeira abertura e permanece comprado ate o fim.

## Configuracao

```text
sem parametros
```

## Entrada e saida

O sinal vale 1 em todos os candles. Em um unico ativo, a compra ocorre na primeira abertura executavel e nao existe sinal de saida. Na matriz, esse sinal nao filtra ativos: o gerenciamento de carteira continua livre para selecionar, ponderar, manter caixa e rebalancear na abertura seguinte.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
