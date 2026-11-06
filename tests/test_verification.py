import io
import json
import unittest
from datetime import datetime,timezone
from unittest.mock import Mock
from urllib.error import HTTPError
from radar.verification import fetch_record,verify_shortlist
from radar.notifications import select_cards
from radar.canonical import to_card


class VerificationTests(unittest.TestCase):
    def record(self,**changes):
        return {'numeroControlePNCP':'12345678000100-1-000001/2026',
            'objetoCompra':'Assinatura de plataforma para pesquisa de preços públicos',
            'orgaoEntidade':{'cnpj':'12345678000100'},'anoCompra':2026,'sequencialCompra':1,
            'situacaoCompraId':1,'tipoInstrumentoConvocatorioCodigo':1,
            'dataEncerramentoProposta':'2099-12-31T18:00:00',**changes}

    def test_fixed_destination_bounded_response_and_exact_identity(self):
        row=self.record();opener=Mock()
        opener.open.return_value=io.BytesIO(json.dumps(row).encode())
        self.assertEqual(fetch_record(row['numeroControlePNCP'],opener=opener),row)
        self.assertEqual(opener.open.call_args.args[0].full_url,'https://pncp.gov.br/api/consulta/v1/orgaos/12345678000100/compras/2026/1')
        self.assertEqual(opener.open.call_args.kwargs['timeout'],8)
        opener.open.return_value=io.BytesIO(json.dumps(self.record(numeroControlePNCP='different')).encode())
        with self.assertRaises(ValueError):fetch_record(row['numeroControlePNCP'],opener=opener)

    def test_cancelled_or_changed_object_is_removed_before_email(self):
        now=datetime.now(timezone.utc);old=to_card(self.record());writer=Mock()
        fresh,changed,failures=verify_shortlist([old],{},fetcher=lambda _:self.record(situacaoCompraId=2),writer=writer,now=now)
        self.assertEqual(select_cards(fresh,'weekly',now),[])
        fresh,changed,failures=verify_shortlist([old],{old['id']:('Daltton','Vou participar')},
            fetcher=lambda _:self.record(objetoCompra='Aquisição de microscópio com sistema óptico'),writer=writer,now=now)
        self.assertIn(old['id'],changed);self.assertIsNone(fresh[0][1])
        self.assertEqual(select_cards(fresh,'weekly',now),[])
        self.assertEqual(writer.call_count,2)

    def test_unavailable_source_never_falls_back_to_stale_email_card(self):
        old=to_card(self.record());writer=Mock();fetcher=Mock(side_effect=TimeoutError())
        with self.assertRaises(ValueError):verify_shortlist([old],{},fetcher=fetcher,writer=writer,now=datetime.now(timezone.utc))
        writer.assert_not_called()

    def test_rate_limit_stops_remaining_verification_requests(self):
        old=to_card(self.record());writer=Mock();fetcher=Mock(side_effect=HTTPError('https://pncp.gov.br',429,'limited',{},None))
        with self.assertRaises(ValueError):verify_shortlist([old,{**old,'id':'other'}],{},fetcher=fetcher,writer=writer,now=datetime.now(timezone.utc))
        self.assertEqual(fetcher.call_count,1);writer.assert_not_called()
