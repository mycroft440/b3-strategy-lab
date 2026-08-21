# Implementacao do catalogo pesquisado e auditoria do backtest

Data da revisao: 2026-08-21.

## Resumo

O catalogo de pesquisa nao deve ser convertido mecanicamente em dezenas de
presets. O projeto ja possui 189 estrategias parametrizadas mais buy-and-hold e
478 configuracoes de carteira. A matriz completa e, portanto, um mecanismo de
**screening**; o resultado economico final deve vir do motor realista.

Nesta revisao foram adicionadas apenas familias que estavam ausentes, sao
causais e podem ser calculadas corretamente com os candles diarios verificados:

- `absolute_momentum_12_1`: retorno de 252 sessoes encerrado 21 sessoes antes;
- `time_series_momentum_3_6_12`: maioria positiva entre 63/126/252 sessoes;
- indicadores `momentum_12_1`, `tsmom_ensemble_score` e
  `realized_volatility_63`.

O motor de extensoes registra essas funcoes automaticamente, sem alterar o
registro central.

## O que ja existia e nao foi duplicado

O repositorio ja cobre SMA/EMA/MACD, SMA200, Donchian/breakout, ATR,
Chandelier, Keltner, SuperTrend, RSI/RSI2/Connors RSI, Bollinger, IBS,
Range Expansion, Gap Momentum, Vortex, KAMA, FRAMA, RVI, CMF, Squeeze,
Turtle Soup, Turn-of-Month, Fisher, Laguerre RSI, Ichimoku, Parabolic SAR,
Aroon, TRIX, Schaff Trend Cycle, Coppock, KST, TSI, Choppiness, NVI,
Klinger, NR7, Halloween e diversas variantes MFI. A camada de carteira ja
cobre equal-weight, inverse-vol, top-N momentum, momentum ajustado por risco,
12/6/3 ROC, momentum absoluto, filtro de tendencia e volatility targeting.

Adicionar outra copia desses motores apenas aumentaria a superficie de data
mining e o tempo da matriz.

## Estrategias do relatorio que nao podem ser simuladas honestamente com OHLCV

As familias abaixo permanecem fora do catalogo diario ate existirem os insumos
corretos:

- **Value / profitability / earnings momentum:** demonstracoes e anuncios com
  timestamp de primeira disponibilidade publica, preservando restatements;
- **Opcoes:** cadeia historica por strike/vencimento, bid/ask, exercicio,
  dividendos, taxas e regras de roll/assignment;
- **Merger arbitrage / PEAD:** feed de eventos e consenso com timestamps
  point-in-time;
- **ML fundamental/cross-sectional:** painel point-in-time suficientemente
  amplo e nested walk-forward; nao e aceitavel treinar um modelo complexo no
  mesmo periodo usado para escolher o vencedor;
- **HFT / Avellaneda-Stoikov:** livro L2/L3, trades, fila, latencia e simulacao
  de fills;
- **Long-short/stat-arb:** exige historico de aluguel/borrow, restricoes de
  short, margem e custos de financiamento antes de ser chamado de realista.

## Auditoria dos candles e do volume

`reports/backtest_data_audit_40.json`, gerado em 2026-08-21, registra:

- `ready=true`;
- 40 tickers com 2.146 sessoes comuns entre 2018-01-02 e 2026-08-19;
- ISIN, negocios e cobertura dos eventos de quantidade presentes;
- todos os ledgers de split verificados desde o warm-up;
- dados com idade de um dia no momento da auditoria;
- **`survivorship_safe=false`**.

O ultimo item e importante: as 30 adicoes foram ranqueadas usando o volume do
ano completo de 2018 e a continuidade ate a data atual. Isso usa informacao
posterior ao inicio do teste e seleciona sobreviventes. O universo fixo e util
para comparacao controlada de sinais, mas nao representa o conjunto investivel
que um investidor de 2018 conheceria naquele momento.

`reports/volume_indicator_audit_40.json`, tambem gerado em 2026-08-21,
registra `ready=true` e audita 17 estrategias que consomem volume. O pipeline:

- usa `QUATOT`, `TOTNEG` e `VOLTOT` oficiais do COTAHIST;
- consolida atividade dos mercados padrao e fracionario para quantidade,
  negocios e volume financeiro;
- preserva OHLC do mercado padrao;
- normaliza quantidade de modo inverso ao fator de preco nos eventos que
  mudam a quantidade de acoes;
- verifica que o notional preco x quantidade permanece consistente dentro do
  erro de arredondamento;
- executa testes de causalidade dos sinais de volume;
- nao encontrou marcador de mudanca de quantidade sem evento oficial coberto.

Existem poucos casos em que o VWAP calculado a partir do volume financeiro
consolidado fica fora do OHLC do mercado padrao. Eles estao explicitamente
registrados no relatorio. Isso e compatível com a mistura de atividade dos
mercados padrao/fracionario e deve continuar sendo auditado, nao apagado.

## Realismo: matriz rapida versus conta realista

A matriz `backtest_strategy_management_combinations.py` e deliberadamente
rapida. Ela ja possui varios controles corretos:

- constroi cada sinal de estrategia uma vez por ticker e reutiliza-o nos 478
  gerenciamentos;
- compartilha perfis de momentum/tendencia/volatilidade entre configuracoes
  semanticamente equivalentes;
- usa ate 8 processos por estrategia;
- conhece o sinal no fechamento e negocia apenas na abertura seguinte;
- exige abertura/fechamento fresco para ativos mantidos;
- cobra custo e slippage por padrao.

Ela continua sendo screening porque nao incorpora toda a contabilidade
realista: o manifesto e o nome do arquivo deixam explicito que dividendos/JCP
ficam fora, e o universo padrao e retrospectivo.

O executor `backtest_strategy_management_realistic.py` e a referencia para
validacao economica. Ele usa:

- snapshots de universo point-in-time;
- abertura oficial separada entre lote padrao e fracionario;
- slippage crescente com participacao no volume financeiro;
- tabela de tarifas;
- proventos e data de direito/pagamento;
- tributacao mensal de operacoes comuns;
- mudancas de ticker e eventos que alteram a quantidade;
- recusa de preco stale e de substituicao silenciosa do fracionario.

Esta revisao adiciona `scripts/validate_matrix_top_realistically.py`. O fluxo
recomendado passa a ser:

```powershell
python scripts\backtest_strategy_management_combinations.py
python scripts\audit_matrix_results.py
python scripts\validate_matrix_top_realistically.py --top 10
```

O ultimo comando audita primeiro os insumos do motor realista, reexecuta os
Top N pares estrategia/gerenciamento e produz
`reports/realistic_gate/TOP_REALISTIC.md`. A classificacao final deve usar esse
arquivo, nao o CAGR bruto da matriz.

## Limitacoes que o gate deve continuar mostrando

Mesmo o motor realista nao deve esconder lacunas. O campo `validity` preserva
flags como universo/selecionamento retrospectivo, tarifas modeladas e cobertura
de proventos ainda nao certificada. Enquanto qualquer uma dessas flags existir,
o resultado e uma estimativa historica condicionada, nao uma promessa de retorno.

O saldo de caixa tambem nao e automaticamente remunerado pelo CDI no motor de
conta. Isso pode representar corretamente uma conta que deixa dinheiro parado,
mas nao e equivalente a um benchmark que aplica caixa em instrumento pos-fixado.
Se a pesquisa quiser comparar com caixa remunerado, essa politica deve ser
modelada explicitamente e com uma serie historica point-in-time da taxa.

## Regra de aceitacao

1. A estrategia precisa ser causal e ter testes de perturbacao do futuro.
2. Dados e volume precisam passar pelos auditores oficiais do projeto.
3. A matriz rapida pode selecionar candidatos, nunca validar dinheiro real.
4. O candidato precisa passar pelo gate realista.
5. Holdout/walk-forward deve ser usado antes de qualquer afirmacao de alpha
   fora da amostra.
6. Nenhuma familia que dependa de um dado ausente deve receber um proxy
   silencioso apenas para aumentar a quantidade de estrategias.
