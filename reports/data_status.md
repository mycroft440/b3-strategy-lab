# Inventario de dados

Status gerado a partir de `data/candles`, `data/heikin_ashi` e `data/corporate_actions`.

`Backtest = sim` exige preco e splits verificados; dividendos/JCP permanecem fora do modo retorno de preco.

Observacao: `VALE4` nao existe nos dados atuais; o ticker disponivel e `VALE3`.

## BBDC3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/bbdc3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 6589 | 2000-01-03 | 2026-07-31 | `data/candles/bbdc3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1387 | 2000-01-03 | 2026-07-27 | `data/candles/bbdc3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/bbdc3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 6589 | 2000-01-03 | 2026-07-31 | `data/heikin_ashi/bbdc3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1387 | 2000-01-03 | 2026-07-27 | `data/heikin_ashi/bbdc3_1wk.csv` |

Eventos corporativos baixados: 282

## BBSE3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/bbse3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 3291 | 2013-04-29 | 2026-07-31 | `data/candles/bbse3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 692 | 2013-04-29 | 2026-07-27 | `data/candles/bbse3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/bbse3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 3291 | 2013-04-29 | 2026-07-31 | `data/heikin_ashi/bbse3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 692 | 2013-04-29 | 2026-07-27 | `data/heikin_ashi/bbse3_1wk.csv` |

Eventos corporativos baixados: 28

## CSMG3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/csmg3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 5072 | 2006-02-08 | 2026-07-31 | `data/candles/csmg3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1069 | 2006-02-08 | 2026-07-27 | `data/candles/csmg3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/csmg3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 5072 | 2006-02-08 | 2026-07-31 | `data/heikin_ashi/csmg3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1069 | 2006-02-08 | 2026-07-27 | `data/heikin_ashi/csmg3_1wk.csv` |

Eventos corporativos baixados: 68

## FLRY3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/flry3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 4120 | 2009-12-17 | 2026-07-31 | `data/candles/flry3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 868 | 2009-12-17 | 2026-07-27 | `data/candles/flry3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/flry3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 4120 | 2009-12-17 | 2026-07-31 | `data/heikin_ashi/flry3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 868 | 2009-12-17 | 2026-07-27 | `data/heikin_ashi/flry3_1wk.csv` |

Eventos corporativos baixados: 42

## GGBR3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/ggbr3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 5828 | 2001-02-05 | 2026-07-31 | `data/candles/ggbr3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1289 | 2001-02-05 | 2026-07-27 | `data/candles/ggbr3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/ggbr3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 5828 | 2001-02-05 | 2026-07-31 | `data/heikin_ashi/ggbr3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1289 | 2001-02-05 | 2026-07-27 | `data/heikin_ashi/ggbr3_1wk.csv` |

Eventos corporativos baixados: 73

## IRBR3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/irbr3_4h.csv` |
| 1d | ok_retorno_preco | price_verified | verified | 2017-01-01 | unverified | sim | 2236 | 2017-07-31 | 2026-07-31 | `data/candles/irbr3_1d.csv` |
| 1sem | ok_retorno_preco | price_verified | verified | 2017-01-01 | unverified | sim | 470 | 2017-07-31 | 2026-07-27 | `data/candles/irbr3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/irbr3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 2236 | 2017-07-31 | 2026-07-31 | `data/heikin_ashi/irbr3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 470 | 2017-07-31 | 2026-07-27 | `data/heikin_ashi/irbr3_1wk.csv` |

Eventos corporativos baixados: 12

## JHSF3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/jhsf3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 4783 | 2007-04-12 | 2026-07-31 | `data/candles/jhsf3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1008 | 2007-04-12 | 2026-07-27 | `data/candles/jhsf3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/jhsf3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 4783 | 2007-04-12 | 2026-07-31 | `data/heikin_ashi/jhsf3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1008 | 2007-04-12 | 2026-07-27 | `data/heikin_ashi/jhsf3_1wk.csv` |

Eventos corporativos baixados: 59

## LOGG3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/logg3_4h.csv` |
| 1d | ok_retorno_preco | price_verified | verified | 2017-01-01 | unverified | sim | 1892 | 2018-12-21 | 2026-07-31 | `data/candles/logg3_1d.csv` |
| 1sem | ok_retorno_preco | price_verified | verified | 2017-01-01 | unverified | sim | 398 | 2018-12-21 | 2026-07-27 | `data/candles/logg3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/logg3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1892 | 2018-12-21 | 2026-07-31 | `data/heikin_ashi/logg3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 398 | 2018-12-21 | 2026-07-27 | `data/heikin_ashi/logg3_1wk.csv` |

Eventos corporativos baixados: 13

## MLAS3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/mlas3_4h.csv` |
| 1d | ok_retorno_preco | price_verified | verified | 2017-01-01 | unverified | sim | 1255 | 2021-07-22 | 2026-07-31 | `data/candles/mlas3_1d.csv` |
| 1sem | ok_retorno_preco | price_verified | verified | 2017-01-01 | unverified | sim | 263 | 2021-07-22 | 2026-07-27 | `data/candles/mlas3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/mlas3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1255 | 2021-07-22 | 2026-07-31 | `data/heikin_ashi/mlas3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 263 | 2021-07-22 | 2026-07-27 | `data/heikin_ashi/mlas3_1wk.csv` |

Eventos corporativos baixados: 2

## PETR4

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/petr4_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 6589 | 2000-01-03 | 2026-07-31 | `data/candles/petr4_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1387 | 2000-01-03 | 2026-07-27 | `data/candles/petr4_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/petr4_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 6589 | 2000-01-03 | 2026-07-31 | `data/heikin_ashi/petr4_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1387 | 2000-01-03 | 2026-07-27 | `data/heikin_ashi/petr4_1wk.csv` |

Eventos corporativos baixados: 64

## TUPY3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/tupy3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 4977 | 2000-12-11 | 2026-07-31 | `data/candles/tupy3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1154 | 2000-12-11 | 2026-07-27 | `data/candles/tupy3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/tupy3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 4977 | 2000-12-11 | 2026-07-31 | `data/heikin_ashi/tupy3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1154 | 2000-12-11 | 2026-07-27 | `data/heikin_ashi/tupy3_1wk.csv` |

Eventos corporativos baixados: 34

## VALE3

### Grafico de candles

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/candles/vale3_4h.csv` |
| 1d | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 6583 | 2000-01-03 | 2026-07-31 | `data/candles/vale3_1d.csv` |
| 1sem | ok_retorno_preco_desde_split_coverage | price_verified | verified | 2017-01-01 | unverified | sim_desde_2017-01-01 | 1387 | 2000-01-03 | 2026-07-27 | `data/candles/vale3_1wk.csv` |

### Grafico Heikin Ashi

| Tempo | Status | Preco | Splits | Desde | Proventos | Backtest | Linhas | Inicio | Fim | Arquivo |
|---|---|---|---|---|---|---|---:|---|---|---|
| 4h | faltando | unverified | unverified |  | unverified | nao | 0 |  |  | `data/heikin_ashi/vale3_4h.csv` |
| 1d | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 6583 | 2000-01-03 | 2026-07-31 | `data/heikin_ashi/vale3_1d.csv` |
| 1sem | derivado_verificado | derived_from_price_verified | verified | 2017-01-01 | unverified | nao | 1387 | 2000-01-03 | 2026-07-27 | `data/heikin_ashi/vale3_1wk.csv` |

Eventos corporativos baixados: 41
