# Nexo Radar

Radar de licitações baseado no projeto GovPreços/iArquivo, com painel React/TypeScript, coletor Python para o PNCP e publicação na Vercel.

Repositório privado: https://github.com/gabrielgmayrink/nexo-radar.

## Estado inicial

O painel mantém listas, filtros, detalhes, exportação CSV, rascunhos locais e a estrutura de avaliação da equipe. A Public já tem critérios configurados para assessoria administrativa e de gestão, capacitação, EAD e desenvolvimento de sistemas/TI. O perfil do Gerico continua desativado até receber seus serviços. O catálogo começa vazio, aguardando a primeira coleta; a base, os exemplos e as credenciais anteriores não foram copiados.

Empresas desativadas não recebem sugestões. Banco compartilhado e login usam um projeto Supabase independente. O acesso principal usa e-mail e senha, com convite pessoal para o primeiro acesso. O Gmail da plataforma envia resumos aos destinatários autorizados quando o envio estiver habilitado. A IA paga está desligada.

## Identidade visual

Marca: **Nexo Radar**. Logo vetorial em `web/public/brand/nexo-logo.svg` e símbolo em `web/public/brand/nexo-symbol.svg`. O login utiliza a versão 3D `web/public/brand/nexo-symbol-3d.png`. Paleta: azul profundo `#0D1930`, azul `#286BED`, ciano `#42E8E0` e violeta `#8362FF`. Veja [identidade e interface](docs/identidade-e-interface.md) para os componentes React Bits e o prompt da imagem.

## Executar

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
npm ci --prefix web
npm run dev --prefix web
```

O painel de desenvolvimento usa o catálogo local vazio quando as APIs não estão disponíveis. Para exercitar as funções Python, use `vercel dev` com esta instalação configurada. Não carregue as variáveis do radar anterior.

## Configurar empresas

Edite [src/radar/companies.json](src/radar/companies.json). Para cada empresa:

- `services`: produtos e serviços confirmados pela empresa.
- `terms`: expressões específicas que devem aparecer no objeto da contratação.
- `excludeTerms`: expressões que excluem a oportunidade desse perfil.
- `enabled`: mude para `true` depois de preencher serviços e termos.

Os termos são frases literais, sem distinção de acentos e maiúsculas. Não são expressões regulares. Uma correspondência no objeto indica candidata; uma menção apenas nas informações complementares pede revisão e não recomenda participação. A pontuação é uma regra de seleção, não uma probabilidade. Revise uma amostra de editais antes de ativar a operação.

Depois de alterar os perfis, publique novamente o aplicativo e reprocesse o catálogo. O painel e o coletor usam o mesmo arquivo de perfis.

## Publicação

Importe o repositório na conta pessoal de **gabrielgmayrink** na Vercel, mantendo a raiz do repositório como Root Directory. `vercel.json` configura a compilação de `web` e as funções Python. A versão inicial pode ser publicada com o catálogo vazio, sem banco.

Veja [docs/instalacao.md](docs/instalacao.md) para configurar banco, autenticação, coleta e e-mails quando os serviços estiverem definidos.

## Verificação

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests -v
npm run build --prefix web
node scripts/test_search_logic.mjs
```

Os perfis em `tests/profile_fixtures.py` são exemplos sintéticos exclusivos dos testes. Não descrevem os serviços reais das empresas.
