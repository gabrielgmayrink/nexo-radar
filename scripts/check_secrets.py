"""Fail on common committed credentials without printing their values."""
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=[re.compile(value) for value in (
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{40,}',
    r'sb_secret_[A-Za-z0-9_-]{24,}',r'sk_live_[A-Za-z0-9]{20,}',
    r'AKIA[0-9A-Z]{16}',
)]


def findings(path,content):
    if path.name.startswith('.env') and path.name!='.env.example':return [(0,'environment file')]
    return [(number,'credential pattern') for number,line in enumerate(content.splitlines(),1)
            if any(pattern.search(line) for pattern in PATTERNS)]


def main():
    tracked=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    failed=False
    for name in sorted(set(tracked)):
        path=ROOT/name
        if not name or not path.is_file() or path.stat().st_size>2_000_000:continue
        try:content=path.read_text(encoding='utf-8')
        except (UnicodeError,OSError):continue
        for line,kind in findings(Path(name),content):
            print(f'{name}:{line}: blocked {kind} (value withheld)');failed=True
    if failed:raise SystemExit(1)
    print('No configured credential patterns in tracked/new project text files')


if __name__=='__main__':main()
