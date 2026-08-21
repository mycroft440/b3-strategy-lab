# Proveniencia e limites dos dados

## Base canonica de precos

Os backtests verificados usam o COTAHIST anual, publicado gratuitamente pela
B3 em [Cotacoes historicas](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/).
O download automatizado usa a URL oficial
`https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A<ANO>.ZIP`.

Dois leitores independentes extraem os registros de ações: mercado padrão
(`TPMERC=010`, `CODBDI=02`) e mercado fracionário (`TPMERC=020`,
`CODBDI=96`). O OHLC canônico permanece o do mercado padrão; quantidade,
negócios e volume financeiro somam os dois mercados. Cada manifesto em
`data/manifests` registra URL, nome, tamanho e SHA-256 de todos os ZIPs anuais
usados. O arquivo do ano corrente é baixado novamente em cada atualização porque
muda a cada pregão.

Os CSVs canonicos preservam duas bases diferentes:

- `raw_open`, `raw_high`, `raw_low` e `raw_close`: OHLC sem ajuste do mercado
  padrão;
- `raw_volume`, `trades` e `financial_volume`: atividade consolidada oficial dos
  mercados padrão e fracionário;
- `fractional_raw_volume`, `fractional_trades` e
  `fractional_financial_volume`: contribuição do mercado fracionário, permitindo
  reconstruir por subtração a atividade padrão;
- `volume_scope`: `consolidated_010_020` nos datasets atuais e
  `standard_010` somente em arquivos legados sem consolidação;
- `open`, `high`, `low`, `close` e `volume`: série normalizada somente por
  grupamentos, desdobramentos e bonificações que alteram a quantidade de ações;
- `adjustment_factor`: relacao `close / raw_close`;
- `trades`, `financial_volume`, `quotation_factor`, `bdi_code`, `market_type`,
  `isin`, `distribution_number`, `specification` e `issuer_name`: campos de
  auditoria preservados do registro oficial.

Dividendos e JCP nao entram na serie normalizada. Custos, impostos e slippage
tambem ficam fora, salvo quando informados explicitamente no simulador.

O ajuste de quantidade e inverso ao de preco: se um evento multiplica a
quantidade de acoes, os precos anteriores sao divididos e o `volume` anterior e
multiplicado pela mesma razao. Assim, `preco tipico * volume` permanece na mesma
base economica, salvo o arredondamento da quantidade inteira. Todos os
indicadores de volume usam essa base normalizada no modo `adjusted`; no modo
`raw`, usam conjuntamente OHLC bruto e `raw_volume`.

Se existir atividade fracionária em uma data sem qualquer OHLC padrão, o
sincronizador não inventa um candle nem mistura o OHLC `020` na série `010`: ele
registra a exclusão e falha se isso ocorrer dentro da janela avaliada. Registros
anteriores usados apenas como histórico legado podem ser omitidos quando não há
preço padrão ao qual associar o volume.

`scripts/audit_volume_indicators.py` inventaria por codigo todos os leitores de
volume e audita MFI, Chaikin Money Flow, Elder Force Index, Ease of Movement,
Negative Volume Index, Klinger Volume Oscillator e os filtros de volume de
Chandelier/Range Expansion: 17 estrategias ao todo. O relatorio tambem lista,
sem alterar os dados, eventuais inconsistencias internas do proprio COTAHIST
entre `VOLTOT/QUATOT` padrão e o intervalo `PREMIN-PREMAX` padrão. A validação
não mistura o VWAP consolidado com um OHLC de apenas um dos mercados.

## Eventos que alteram a quantidade de acoes

O arquivo `data/corporate_actions/split_evidence.json` registra a evidencia
usada desde 2017. As fontes sao o servico de companhias listadas da B3 e as
paginas oficiais de relacoes com investidores dos emissores ou documentos IPE
da CVM. Cada evento tem razao, ultima data com direito, primeiro pregao ex e URL
da fonte.

A consulta corrente de companhias listadas da B3 nao devolve todo o historico.
Por isso, `data/corporate_actions/supplemental_split_events.json` versiona 25
eventos ausentes, sempre com fonte primaria do emissor ou da CVM. O construtor
valida a data ex contra o primeiro pregao COTAHIST posterior a ultima data com
direito, rejeita divergencias entre fontes e reconcilia todos os 59 inicios de
marcador `EB/EG` observados desde 2017. Tambem registra o retorno bruto depois de
neutralizar cada fator; a maior descontinuidade absoluta aceita e 35%.

Na matriz padrao, tanto os indicadores das estrategias quanto os lookbacks dos
gerenciamentos sao construidos apenas a partir desse inicio de cobertura. Isso
impede que uma janela longa alcance precos anteriores ao periodo certificado.

O construtor recusa um split sem evidencia ou com razao divergente. A cobertura
desde 2017 inclui o ano de aquecimento anterior ao inicio padrao da matriz em
2018. Eventos anteriores continuam no historico para pesquisa, mas nao possuem
o mesmo nivel de certificacao; por isso nao se deve apresentar um backtest
anterior a 2017 como totalmente verificado.

Dividendos/JCP legados continuam marcados como `unverified`. O modo
`raw_events` e bloqueado por padrao porque nao ha, neste repositorio, uma base
oficial completa com data ex, valor, data de pagamento e tratamento tributario.

## Fontes oficiais e gratuitas para ampliar a cobertura

- B3 COTAHIST: OHLC, quantidade, negocios e volume financeiro diarios. E a
  fonte canonica deste projeto.
- B3 Companhias Listadas: dados cadastrais e eventos de capital recentes por
  emissor. O endpoint e usado como evidencia local de splits.
- [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/): cadastro de
  companhias, documentos periodicos/eventuais, fatos relevantes, comunicados e
  avisos aos acionistas.
- [Documentos IPE da CVM](https://dados.cvm.gov.br/dataset/cia_aberta-doc-ipe):
  caminho gratuito para automatizar a leitura de assembleias, avisos aos
  acionistas e comunicados ao mercado.
- RI do emissor: fonte primaria complementar quando o registro estruturado da
  B3 nao apresenta todo o historico.

Nao existe aqui uma fonte oficial gratuita unica que entregue uma serie total
return pronta, historica e livre de revisoes. Para esse objetivo, e necessario
montar e versionar um ledger proprio de eventos a partir de B3, CVM e emissores,
definindo de forma explicita data ex, data de pagamento, impostos e regra de
reinvestimento.

## Universo de ativos

`data/universes/fixed_40_2018.json` torna explicita a lista padrao usada na
matriz, a data de selecao e o inicio do aquecimento. As 10 acoes originais foram
mantidas; as 30 adicoes foram ranqueadas pelo volume financeiro oficial de 2018,
com presenca minima de 95% em cada ano ate a atualizacao. O manifesto declara
`survivorship_safe=false`: o ranking usa o ano completo de 2018 apesar de a
avaliacao comecar em 2 de janeiro, o que cria vies de selecao, e a exigencia de
continuidade usa informacao posterior, o que cria vies de sobrevivencia.
`fixed_2018.json` permanece apenas para reproduzir os relatorios historicos do
universo anterior.

Uma analise sem esse vies precisa construir snapshots point-in-time com o
cadastro historico B3/CVM, incluindo IPOs, mudancas de ticker, incorporacoes,
registros suspensos e cancelados, e aplicar criterios de liquidez usando apenas
informacao disponivel em cada data.

## Reproducao

```powershell
python scripts\sync_official_universe.py --download --refresh-current --refresh-actions --refresh-selection
python -m b3_strategy_lab verify-data --interval 1d
python -m b3_strategy_lab verify-data --interval 1wk
python scripts\audit_backtest_readiness.py --max-age-calendar-days 4
python scripts\audit_volume_indicators.py
python scripts\backtest_strategy_management_combinations.py --initial-cash 1000 --cost-bps 3.2 --slippage-bps 10
python scripts\audit_matrix_results.py
python scripts\organize_market_data.py --quarantine-unverified
```

Os arquivos de 4 horas provenientes do Yahoo nao possuem manifesto oficial e
ficam em `data/legacy`. Eles nao sao carregados pelo caminho verificado.
