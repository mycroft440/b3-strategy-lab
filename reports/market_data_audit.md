# Auditoria da base de mercado

Data da reconstrucao: 2026-07-29.

## Resultado

- 12 ativos com preco diario oficial COTAHIST da B3.
- 53.179 candles diarios e 11.372 semanais.
- Janela mais recente: 28/07/2026 no diario e semana iniciada em 27/07/2026.
- 24 manifestos com SHA-256 do CSV, das razoes de split e de cada ZIP anual.
- Nenhum erro estrutural de OHLC, ordem de datas, positividade, fator de
  fechamento ou duplicidade.
- Duas variacoes superiores a 50% em TUPY3, ambas confirmadas como negocios
  oficiais extremamente iliquidos, e a queda normalizada de 20,93% de IRBR3
  no primeiro pregao apos o grupamento de 2023; os tres casos estao revisados
  em `data/quality_reviews.json`.
- A auditoria de transicoes societarias encontrou e corrigiu duas razoes
  legadas: BBDC3 em 14/12/2004 (`2` para `3`) e GGBR3 em 02/05/2003
  (`0,001` para `0,0013`, incluindo bonificacao de 30%).
- Transicoes de split que deixem variacao normalizada superior a 15% agora
  exigem evidencia explicita ou o dataset e rejeitado.
- Intradiario 4h e derivados sem manifesto movidos para `data/legacy`.
- Os 24 Heikin Ashi e os 928 fragmentos anuais foram recompostos e comparados
  exatamente com suas series de origem.
- A escrita dos CSVs passou a ser atomica: uma interrupcao preserva o ultimo
  arquivo completo em vez de deixar uma serie truncada.
- As 27 estrategias foram exercitadas sobre cada uma das 24 series canônicas:
  648 execucoes de indicadores e 648 simulacoes `price_only` sem erro ou
  credito de proventos, com custo e slippage iguais a zero.
- Os 41 testes automatizados, a compilacao e a verificacao de whitespace do
  diff terminaram sem falhas.

## Comparacao com a base anterior

No intervalo diario foram comparados 210.756 valores OHLC em datas comuns:

- 49.065 valores divergiam mais de R$ 0,02;
- 20.858 linhas tinham volume diferente;
- a base oficial adicionou 490 datas ausentes na referencia;
- 92 datas existentes apenas na referencia foram excluidas por nao terem
  correspondente no instrumento padrao do COTAHIST selecionado.

O detalhamento por ticker e intervalo esta em
`reports/market_data_source_comparison.csv`.

As divergencias nao foram "corrigidas" por aproximacao: o valor oficial
COTAHIST passou a ser a fonte de verdade. O semanal foi reconstruido
exclusivamente a partir do diario oficial.

## Normalizacao acionaria

Preco e volume foram convertidos para a mesma base:

- preco historico e dividido pelo produto dos desdobramentos futuros;
- volume historico e multiplicado pelo mesmo produto;
- `FATCOT` e interpretado antes dessa normalizacao.

Esse tratamento preserva preco vezes quantidade e evita descontinuidades
artificiais em indicadores de volume. A transicao historica de PETR4 em
23/06/2000 exigiu uma razao de base de `0,01`, documentada em
`data/corporate_actions/README.md`.

As correcoes de BBDC3 e GGBR3 tambem estao documentadas nesse arquivo. Depois
das correcoes, os retornos nas transicoes passaram, respectivamente, de
-34,30% para -1,45% e de -16,96% para +7,96%.

## Escopo certificado do backtest

O escopo solicitado exclui dividendos e JCP, alem de impostos, custos e
slippage. O modo padrao `price_only`:

- executa no OHLC oficial normalizado apenas por splits;
- ignora todos os valores em dinheiro, mesmo que estejam presentes no arquivo
  de eventos;
- usa sinais no fechamento e executa na abertura seguinte;
- esta liberado quando o manifesto de preco e suas revisoes passam.

Os eventos em dinheiro atuais continuam sem garantia oficial estruturada de
tipo, valor bruto, base acionaria e data de pagamento. Por isso apenas o modo
opcional `raw_events`, destinado a retorno total, permanece bloqueado por
padrao. `--allow-unverified-actions` existe somente para diagnostico.
