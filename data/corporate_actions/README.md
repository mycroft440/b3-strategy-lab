# Estado dos eventos corporativos

Os valores em dinheiro destes CSVs ainda sao uma base legada do endpoint Chart
do Yahoo. Eles sao preservados para auditoria, mas o modo seguro `price_only`
os ignora integralmente.

Isso importa para este projeto porque:

- o endpoint nao informa no CSV se o pagamento e dividendo ou JCP;
- nao ha prova de que todos os eventos historicos estejam completos;
- o valor precisa estar na mesma base acionaria dos precos normalizados;
- um backtest sem impostos deve creditar o valor bruto, nao um valor liquido
  desconhecido.

Backtests de retorno por preco nao dependem desses valores e estao liberados.
Somente o modo opcional `raw_events`, que tenta medir retorno total, permanece
bloqueado ate que os eventos recebam `corporate_action_status = verified`. A B3
oferece a consulta publica de eventos recentes e o canal estruturado Corporate
Action do UP2DATA:

- https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/dividendos-e-outros-eventos-corporativos/
- https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/up2data/dados-disponiveis/

## Ajuste de base auditado em PETR4

A linha `2000-06-23,PETR4,B3_COTAHIST_AUDIT,0.0,0.01` registra uma mudanca
historica de base necessaria para manter preco e volume comparaveis:

- 21/06/2000: fechamento economico de R$ 0,515 por acao antiga, quantidade
  149.270.000 e `FATCOT=1000`;
- 23/06/2000: fechamento de R$ 51,51, quantidade 877.300 e `FATCOT=1`;
- a razao `0,01`, combinada com os desdobramentos posteriores, reproduz a
  continuidade de preco e de volume na base acionaria atual.

Esses numeros foram conferidos diretamente no arquivo oficial
`COTAHIST_A2000.ZIP`. A linha corrige a base dos precos, mas nao transforma os
demais proventos legados em eventos certificados.

## Correcoes de desdobramentos encontradas na auditoria

Duas razoes da base legada estavam erradas ou incompletas e foram substituidas
por linhas marcadas como `B3_COTAHIST_ISSUER_AUDIT`:

- BBDC3 em 14/12/2004: razao corrigida de `2` para `3`. A razao antiga deixava
  uma queda artificial de 34,30%; `3` recompõe a continuidade observada no
  COTAHIST: o fechamento oficial passou de R$ 170,48 para R$ 56,00 e o retorno
  diário normalizado passou a -1,45%.
- GGBR3 em 02/05/2003: razão combinada corrigida de `0,001` para `0,0013`.
  Houve grupamento de `0,001` e bonificação de 30% na mesma transição. Considerar
  apenas o grupamento deixava uma queda artificial de 16,96%. O histórico
  oficial de bonificações da Gerdau registra os 30%.

Fontes primárias usadas no cruzamento:

- consulta de eventos corporativos da B3:
  https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/dividendos-e-outros-eventos-corporativos/
- histórico de bonificações e desdobramentos da Gerdau:
  https://ri.gerdau.com/informacoes-ao-mercado/dividendos-e-jcp/

As razões corrigidas liberam a camada de preço normalizada para indicadores e
backtests `price_only`. Elas não certificam os valores em dinheiro nem suas
datas de pagamento; por isso somente o modo opcional de retorno total permanece
bloqueado.
