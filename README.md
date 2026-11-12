# Nexo Radar

Radar de licitações para Public e Gerico, com React/TypeScript, Python, PostgreSQL/Supabase e Vercel. A base pública é compartilhada; critérios, avaliações, responsáveis, checklist e histórico comercial são separados por empresa.

Repositório privado: [gabrielgmayrink/nexo-radar](https://github.com/gabrielgmayrink/nexo-radar). A versão desta branch está em homologação; não foi promovida à produção.

Estado mais recente e evidências de Auth/MFA real, isolamento, coleta nacional e restauração externa: [homologação em nuvem](docs/HOMOLOGACAO_CLOUD.md).

## Funcionalidades

- Coleta nacional do que o PNCP disponibiliza como propostas abertas, sem filtro comercial na captura; incrementais de publicação e atualização com retomada.
- Recibos brutos, quarentena, identificação oficial, histórico de mudanças e prova por duas passagens completas de identificadores e versões. Fonte em movimento pode permanecer com cobertura não confirmada.
- Busca paginada no servidor por objeto e itens enriquecidos, UF, município, órgão, fonte complementar, valores, datas e situação.
- Classificação explicável de objeto principal/contexto/escopo misto; revisão de descartes, sem apagar dados oficiais.
- Perfis editáveis com produtos, serviços, expressões, sinônimos, exclusões, regiões, órgãos e preferência de resumo semanal.
- Login separado por empresa, avaliação auditada e acompanhamento que preserva registros encerrados.
- Itens, anexos e trechos de PDFs com fontes. Extração textual não representa análise jurídica nem OCR.
- Diagnóstico das fontes para responsáveis; manutenção por jobs autenticados; backup cifrado com restauração externa validada em homologação.

Public mantém os quatro grupos confirmados de serviços administrativos, gestão, palestras/capacitação e EAD. TI está fora do perfil. Gerico permanece desativada até receber seus produtos/serviços; nenhum segmento foi inventado.

## Instalação e testes

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements.lock
.venv\Scripts\python -m pip install --no-build-isolation --no-deps -e .
npm ci --prefix web
npm ci --prefix scripts --ignore-scripts
$env:PYTHONPATH='src'
.venv\Scripts\python -m unittest discover -s tests -v
npm run build --prefix web
node scripts/test_search_logic.mjs
node scripts/test_login_token.mjs
node scripts/test_catalog_search.mjs
```

O build inclui verificação TypeScript. A CI executa também PostgreSQL real, migrações, testes de integração, lint de sintaxe/nomes indefinidos, auditorias e scanner de padrões de credenciais. Testes não carregam dotenv de produção.

## Homologação local reproduzível

Use um PostgreSQL descartável em loopback com nome `radar_restore_test_*`. A CI cria esse banco automaticamente. Localmente, com o banco vazio criado:

```powershell
$env:RADAR_TEST_POSTGRES_DSN='postgresql://postgres:SENHA_LOCAL@127.0.0.1:55439/radar_restore_test_ci'
.venv\Scripts\python tests/bootstrap_postgres.py
.venv\Scripts\python scripts/seed_acceptance.py
.venv\Scripts\python scripts/local_acceptance.py
```

Acesse `http://localhost:8000`. Contas exclusivamente fictícias: `public.qa@example.com`, `gerico.qa@example.com` e `admin.qa@example.com`; senha de teste `Homologacao-local@2026`. O servidor recusa banco remoto e não usa credenciais reais. O provedor Auth é uma fixture; este teste não equivale a homologar Supabase Auth/MFA. As licitações são snapshots públicos identificados, sem promessa de atualidade/cobertura. O quadro `/qa/mobile` verifica responsividade em390px.

## Ambientes e migrações

Configure um banco e segredos próprios de homologação, usando `.env.example` e as variáveis de Preview da branch. Não copie credenciais produtivas para preview. Nenhum arquivo `.env` com valores entra no Git.

O comando de migração exige alvo explícito:

```text
python scripts/bootstrap_database.py --env-file .env.staging.local --project-ref REFERENCIA_DO_PROJETO_DE_HOMOLOGACAO
```

O arquivo deve apontar exatamente ao projeto informado. O projeto produtivo conhecido é recusado por padrão; a opção `--production` só pode ser usada pelo titular após aprovar a versão exata. As migrações são registradas e não devem ser reaplicadas manualmente. Coletores em andamento impedem o início da migração.

Perfis são editados no painel por responsáveis autorizados e registrados no banco com versão. O arquivo `companies.json` fornece os padrões iniciais; não é necessário republicar para alterar preferências. A seleção por regras é triagem, não probabilidade de êxito ou elegibilidade.

## Operação

Coleta nacional: segunda07h; incremental diário09h17; manutenção: domingo23h, sempre Brasília. Agendamento GitHub pode atrasar. O monitor separado precisa ser habilitado após homologação. Arquivamento preserva os originais e as avaliações. O resumo semanal depende da conferência da coleta e do envio habilitado aos destinatários autorizados.

O certificado público Supabase acompanha o pacote; conexões exigem `verify-full`. Privilégios restritos por papel são preparados e testados; `RADAR_DB_ENFORCE_ROLES` só deve ser habilitado após provisionamento e validação das credenciais próprias.

Backup local: AES-GCM, validação do arquivo e restauração somente em banco local vazio. Upload S3 privado e agenda estão preparados, desativados até configurar destino, chave separada e retenção. Não existe serviço pago contratado por esta implementação.

## Evidências e limites

Veja [homologação](docs/HOMOLOGACAO_AUTONOMA.md), [fontes](docs/EVOLUCAO_E_FONTES.md), [segurança e backup](docs/SECURITY_OPERATIONS.md), [instalação](docs/instalacao.md) e [identidade visual](docs/identidade-e-interface.md).

Não se presume um milhão de editais por semana. A aplicação mede identificadores distintos e pendências da fonte. Armazenamento gratuito, OCR, novas fontes e alta escala têm limites explícitos; nenhum limite atingido pode virar cobertura completa.
