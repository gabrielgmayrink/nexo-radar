"""Strict libpq TLS options. Public CA material is not a secret."""
import os
from pathlib import Path


def tls_parameters(query, *, environ=None):
    environ=os.environ if environ is None else environ
    result={key:value for key,value in query.items() if key not in ('sslmode','sslrootcert')}
    certificate=environ.get('RADAR_POSTGRES_CA_FILE') or query.get('sslrootcert') or str(Path(__file__).with_name('certificates').joinpath('supabase-prod-ca-2021.crt').resolve())
    if certificate!='system':
        path=Path(certificate)
        if not path.is_absolute() or not path.is_file():
            raise ValueError('Configure an absolute PostgreSQL CA certificate path')
        certificate=str(path)
    result.update(sslmode='verify-full',sslrootcert=certificate)
    return result
