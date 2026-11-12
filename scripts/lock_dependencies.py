"""Regenerate reviewed package hashes from the official PyPI JSON API only."""
import json
from pathlib import Path
from urllib.request import urlopen

PACKAGES={'cffi':'2.1.1','cryptography':'50.0.2','psycopg':'3.3.8','psycopg-binary':'3.3.8',
          'pycparser':'3.12','PyJWT':'2.15.1','typing_extensions':'4.16.0','tzdata':'2026.6',
          'pypdf':'7.0.1','setuptools':'84.1.0'}


def main():
    lines=['# Python 3.12 runtime/build lock. Regenerate with scripts/lock_dependencies.py.']
    for name,version in sorted(PACKAGES.items()):
        with urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=20) as response:data=json.load(response)
        hashes=sorted({row['digests']['sha256'] for row in data['urls'] if not row.get('yanked')})
        if not hashes:raise ValueError('No supported release artifacts: '+name)
        lines.append(name+'=='+version+' \\\n'+' \\\n'.join('    --hash=sha256:'+value for value in hashes))
    Path(__file__).resolve().parents[1].joinpath('requirements.lock').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Locked '+str(len(PACKAGES))+' packages from pypi.org')


if __name__=='__main__':main()
