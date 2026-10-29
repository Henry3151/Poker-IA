// =====================================================================================
// Poker AI Tournament Lab — Power Query (M) para a exportação P8
// Fonte: pasta gerada por `poker-lab export powerbi` (um subdiretório por tabela,
// um arquivo .parquet por execução: P7.parquet, P7b.parquet, P7c.parquet, all.parquet).
// =====================================================================================

// 1) PARÂMETRO  (Página Inicial > Gerenciar Parâmetros > Novo parâmetro)
//    Nome: PastaExportacao   Tipo: Texto
//    Valor atual: C:\Users\<voce>\Downloads\poker-powerbi
//    (a pasta que contém manifest.json e reconciliation.json)

// 2) FUNÇÃO  (Nova Fonte > Consulta Nula > Editor Avançado; nome da consulta: fnCarregarTabela)
let
    fnCarregarTabela = (NomeTabela as text) as table =>
        let
            Pasta = Text.TrimEnd(PastaExportacao, "\") & "\" & NomeTabela,
            Arquivos = Folder.Files(Pasta),
            // só os arquivos da própria pasta da tabela (não de subpastas)
            Proprios = Table.SelectRows(
                Arquivos,
                each [Extension] = ".parquet" and Text.TrimEnd([Folder Path], "\") = Pasta
            ),
            Tabelas = List.Transform(Proprios[Content], each Parquet.Document(_)),
            Combinada = if List.IsEmpty(Tabelas) then #table({}, {}) else Table.Combine(Tabelas)
        in
            Combinada
in
    fnCarregarTabela

// 3) UMA CONSULTA POR TABELA  (Consulta Nula; o nome da consulta = nome da tabela)
//    Exemplo — consulta "FactEntryResult":
//        = fnCarregarTabela("FactEntryResult")
//
//    Lista completa (crie uma consulta para cada):
//      Dimensões: DimRun, DimScenario, DimCandidate, DimFieldClass, DimOpponentProfile,
//                 DimPosition, DimStackBucket, DimPhase
//      Fatos:     FactEntryResult, FactHandHero, FactDecision, FactLedger, FactAudit,
//                 FactScenarioSummary, FactPairedComparison, FactBreakdownCI,
//                 FactAllinLuck, FactProgressive, FactSteal, FactStealByDimension
//
//    Desmarque "Habilitar carga" em fnCarregarTabela e no parâmetro.
//    Os tipos de coluna vêm do Parquet; não é necessário "Alterar tipo".

// 4) VALIDAÇÃO OPCIONAL DA EXPORTAÇÃO (consulta "Reconciliacao")
//    = let j = Json.Document(File.Contents(Text.TrimEnd(PastaExportacao, "\") & "\reconciliation.json"))
//      in Table.FromRecords(j[runs])
//    Todas as linhas devem ter ok = TRUE; a exportação recusa-se a publicar se houver divergência.
