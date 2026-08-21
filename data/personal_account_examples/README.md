# Modelos para reconciliação exata de conta pessoal

Estes arquivos são **modelos**, não evidências. Os hashes zerados, `coverage_complete=false`
e caminhos `PRIVATE/...` forçam o runner a falhar até que sejam substituídos por
documentos reais. Nunca coloque documentos financeiros privados neste repositório público.

O fluxo exato é:

1. mantenha PDFs/CSVs/extratos reais numa pasta privada local, fora do Git;
2. normalize as execuções em `fills.csv` usando preço e quantidade realmente executados;
3. normalize toda movimentação não decorrente do principal da compra/venda em
   `cash_events.csv`: taxas B3, corretagem, custódia, impostos, dividendos, JCP,
   depósitos, saques e demais créditos/débitos do extrato;
4. registre ajustes de quantidade sem negociação em `position_events.csv` (split,
   grupamento, bonificação, conversão ou mudança de ticker). Uma troca de ticker pode
   ser representada por uma linha negativa no ticker antigo e uma positiva no novo;
5. forneça snapshots documentais de abertura e fechamento, contendo caixa e posições;
6. calcule SHA-256 de cada arquivo-fonte privado e coloque o mesmo hash em todas as
   linhas normalizadas originadas daquele documento;
7. crie um `coverage_manifest.json` com **todos** os documentos que cobrem a janela,
   datas inicial/final, `coverage_complete=true`, revisor e timestamp. O manifesto é a
   declaração explícita de que não foram omitidos períodos/documentos sem atividade;
8. execute:

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
pasta, arquivo ausente ou hash divergente bloqueiam o selo exato.

A reconciliação só é aprovada quando simultaneamente:

- caixa final fecha com o snapshot em tolerância de meio centavo;
- cada quantidade de ações fecha exatamente;
- não há venda acima da posição reconstruída;
- nenhum evento está fora da janela dos snapshots;
- todos os documentos-fonte referenciados existem e têm o SHA-256 declarado;
- todos os documentos normalizados constam no manifesto de cobertura;
- o manifesto cobre integralmente as datas dos snapshots e foi marcado como completo
  por um revisor identificado.

O programa não consegue descobrir sozinho que um extrato externo foi deliberadamente
omitido; por isso `coverage_complete` é uma afirmação documental/revisada, enquanto os
hashes tornam os arquivos declarados imutáveis e verificáveis.

A reconciliação não tenta adivinhar linhas ausentes. Se um centavo de taxa estiver
faltando, ela deve falhar.
