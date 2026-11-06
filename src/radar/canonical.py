"""One representation for website cards, local replay and database reads."""
from radar.relevance import classify,procurement_state


def to_card(row: dict, decision: dict | None = None) -> dict:
    decision=decision or classify(row.get('objetoCompra') or '',row.get('informacaoComplementar') or '')
    org,unit=row.get('orgaoEntidade') or {},row.get('unidadeOrgao') or {}
    return {
        'id':row.get('numeroControlePNCP'),
        'organization':org.get('razaoSocial',''),'state':unit.get('ufSigla',''),
        'city':unit.get('municipioNome',''),'modality':row.get('modalidadeNome',''),
        'publishedAt':row.get('dataPublicacaoPncp',''),'object':row.get('objetoCompra',''),
        'additionalInfo':row.get('informacaoComplementar') or '',
        'estimatedValue':row.get('valorTotalEstimado'),
        'proposalDeadline':row.get('dataEncerramentoProposta') or '',
        'proposalStart':row.get('dataAberturaProposta') or '',
        'procurementState':procurement_state(row),'statusId':row.get('situacaoCompraId'),
        'instrumentId':row.get('tipoInstrumentoConvocatorioCodigo'),
        'pncpUrl':f"https://pncp.gov.br/app/editais/{org.get('cnpj')}/{row.get('anoCompra')}/{row.get('sequencialCompra')}",
        'sourceUrl':row.get('linkSistemaOrigem') or '',
        'sourceSystem':row.get('usuarioNome') or '',**decision,
    }
