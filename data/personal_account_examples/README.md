# Modelos para reconciliação exata da conta da corretora

Estes arquivos são **modelos**, não evidências. Os hashes zerados, `coverage_complete=false`,
`normalization_verified=false` e caminhos `PRIVATE/...` forçam o runner a falhar até que
sejam substituídos por documentos reais. Nunca coloque documentos financeiros privados
neste repositório público.

O selo final é deliberadamente restrito a:

`ACTUAL_BROKERAGE_ACCOUNT_EXACT_RECONCILIATION`

Ele significa que o **razão da conta da corretora** fecha documentalmente. Não significa
que um backtest contrafactual obteve fills exatos, nem que impostos pagos fora da corretora
ou o patrimônio pessoal total foram reconstruídos.

O fluxo é:

1. mantenha PDFs/CSVs/extratos reais numa pasta privada local, fora do Git;
2. normalize as execuções em `fills.csv` usando preço e quantidade realmente executados;
3. normalize toda movimentação não decorrente do principal da compra/venda em
   `cash_events.csv`: taxas B3, corretagem, custódia, impostos debitados na conta,
   dividendos, JCP, depósitos, saques e demais créditos/débitos do extrato;
4. registre ajustes de quantidade sem negociação em `position_events.csv` (split,
   grupamento, bonificação, conversão ou mudança de ticker). Uma troca de ticker pode
   ser representada por uma linha negativa no ticker antigo e uma positiva no novo;
5. forneça um snapshot inicial com `boundary=START_OF_DAY` e um snapshot final com
   `boundary=END_OF_DAY`, ambos contendo caixa e posições e lastreados por
   `account_statement`;
6. calcule SHA-256 de cada arquivo-fonte privado e coloque o mesmo hash em todas as
   linhas normalizadas originadas daquele documento;
7. crie um `coverage_manifest.json` no **schema_version 2**. Ele deve listar todos os
   documentos, classificar seus tipos, demonstrar cobertura contínua por extratos de
   conta (`account_statement`) do início ao fim, registrar revisor e timestamp;
8. depois de conferir manualmente que cada valor normalizado corresponde ao documento
   referenciado e que nenhuma movimentação foi omitida, calcule o SHA-256 de
   `fills.csv`, `cash_events.csv`, snapshots e `position_events.csv` quando usado.
   Registre esses hashes em `normalized_inputs`, marque `normalization_verified=true`,
   identifique o revisor e preencha `normalization_attestation`;
9. execute:

```powershell
python scripts\reconcile_actual_personal_account.py `
  --fills C:\privado\normalizado\fills.csv `
  --cash-events C:\privado\normalizado\cash_events.csv `
  --position-events C:\privado\normalizado\position_events.csv `
  --opening-snapshot C:\privado\normalizado\opening_snapshot.json `
  --closing-snapshot C:\privado\normalizado\closing_snapshot.json `
  --coverage-manifest C:\privado\normalizado\coverage_manifest.json `
  --evidence-root C:\privado\fontes
```

`source_document` deve ser um caminho **relativo** a `--evidence-root`. O programa lê
os bytes do arquivo e confere `source_sha256`. Caminho absoluto, `..` que escape da
pasta, arquivo ausente ou hash divergente bloqueiam o selo.

Tipos de documentos também são verificados. Snapshots exigem `account_statement`;
fills exigem `trade_note` ou `account_statement`; ajustes de posição exigem
`corporate_action_notice` ou `account_statement`. O tipo permitido para movimentações
de caixa depende da natureza do evento.

A reconciliação só é aprovada quando simultaneamente:

- caixa final fecha com o snapshot em tolerância de meio centavo;
- cada quantidade de ações fecha exatamente;
- não há venda acima da posição reconstruída;
- liquidação nunca antecede a data da negociação;
- nenhum evento está fora da janela START_OF_DAY → END_OF_DAY;
- todos os documentos-fonte existem e têm o SHA-256 declarado;
- os tipos dos documentos são compatíveis com os registros que suportam;
- extratos de conta cobrem continuamente toda a janela, sem lacunas de datas;
- cada arquivo normalizado consumido pelo runner tem exatamente o SHA-256 revisado
  no manifesto;
- a revisão do manifesto e da normalização ocorre depois do fim do período.

O programa não consegue provar matematicamente que um documento externo nunca existiu.
Por isso a completude continua dependendo de uma declaração documental/revisada; o
software torna essa declaração verificável e impede alterações posteriores nos arquivos
que foram efetivamente revisados.

A reconciliação não tenta adivinhar linhas ausentes. Se um centavo de taxa estiver
faltando, ela deve falhar.
