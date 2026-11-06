# Instalação independente

## Vercel e GitHub

Destino: `gabrielgmayrink/nexo-radar`, privado. Crie um novo projeto `nexo-radar` na conta pessoal de Gabriel. Importe a raiz do repositório. A compilação e a saída estão em `vercel.json`.

A publicação inicial serve o painel e um catálogo vazio. A configuração inicial pode manter todas as integrações desativadas. Não reutilize `.vercel`, `.env`, o banco, os membros da equipe ou as chaves do radar anterior.

## Informações a reunir

A Public já tem os serviços informados cadastrados, incluindo desenvolvimento de sistemas e TI. Faltam os serviços da empresa do Gerico. Para ambas, ainda podem ser detalhados exemplos de objetos desejados, objetos a excluir, estados atendidos e restrições operacionais. Os perfis atuais suportam expressões de inclusão e exclusão; abrangência geográfica e modalidade podem ser filtradas no painel.

## Banco e equipe

Use um novo projeto Supabase. Aplique as migrações em `migrations/` na ordem de 001 a 006. Configure somente no servidor:

- `RADAR_SUPABASE_PROJECT_REF`: identificador do novo projeto.
- `SUPABASE_URL`, `SUPABASE_SECRET_KEY` e `POSTGRES_URL_NON_POOLING`: credenciais dessa instalação. A conexão PostgreSQL deve aceitar sessões e não usar a porta 6543.
- `RADAR_APP_URL`: origem HTTPS exata publicada, sem caminho.
- `FEEDBACK_SIGNING_SECRET`: segredo novo com pelo menos 32 bytes.
- `RADAR_TEAM_EMAILS`: e-mails autorizados, separados por vírgula.

Depois de validar banco e login, habilite `RADAR_CATALOG_STORE=supabase`, `RADAR_TEAM_ENABLED=1` e, se necessário, `RADAR_SHARED_FEEDBACK_ENABLED=1`. Não coloque segredos em variáveis `VITE_`.

## Coleta

Preencha e ative os perfis em `src/radar/companies.json` primeiro. Configure `RADAR_COLLECTION_ENABLED=1` e `RADAR_GITHUB_REPOSITORY_ID=1448230071` na Vercel. O servidor verifica tokens OIDC do GitHub para o repositório privado e o dono `gabrielgmayrink` (ID `169843370`), branch `main` e workflows específicos.

No GitHub, configure as Repository Variables `RADAR_APP_URL` com a URL desta instalação e `RADAR_COLLECTION_ENABLED=1`. O workflow **Collect Radar** começa apenas por acionamento manual, para evitar coletar uma base inteira antes de definir os serviços. Depois de validar a coleta, configure o agendamento desejado.

A coleta local continua disponível com `python scripts/run_local_collection.py --help`. O coletor remoto usa lotes retomáveis, limites e checkpoints da implementação original.

## E-mails

Use um remetente/domínio verificado para esta instalação. Configure `RESEND_API_KEY`, `RADAR_EMAIL_DOMAIN`, `RADAR_EMAIL_FROM`, `RADAR_EMAIL_REPLY_TO`, `RADAR_TEAM_EMAILS` e `RADAR_NOTIFY_EMAILS`. Habilite `RADAR_EMAIL_ENABLED=1` somente após validar o envio. Os destinatários de avisos devem fazer parte da equipe autorizada.

O workflow **Notify Radar** também é manual e exige a Repository Variable `RADAR_EMAIL_ENABLED=1`. Os limites de envio e o controle de duplicidade foram preservados. Nenhum e-mail é enviado durante os testes automatizados.
