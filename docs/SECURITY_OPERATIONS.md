# Segurança e operação do Nexo Radar

As alterações são preparadas para revisão e staging. Nenhuma credencial, senha,
fator de autenticação, banco ou implantação de produção foi alterado por esta etapa.

## Acesso e isolamento

O navegador recebe somente um identificador aleatório em cookie `__Host-`, HttpOnly,
Secure e SameSite Strict. E-mail e empresa são resolvidos por sessão e vínculo no
servidor. A empresa enviada no navegador nunca concede permissão. Avaliações,
responsáveis, listas de tarefas, perfis e aprendizado permanecem por empresa.

Mudança de senha por convite revoga todas as sessões, convites, links e desafios
pendentes antes da operação no provedor. Uma falha posterior exige novo convite.
O identificador de geração impede que uma autenticação anterior à revogação crie
uma sessão nova. A cada solicitação, a sessão verifica também bloqueio e mudança
da credencial no Supabase. A migração 015 expira sessões legadas: será necessário
entrar novamente. Logout preserva o registro da sessão expirada para auditoria.

A limitação combina origem, origem+conta e orçamento global. Não existe bloqueio
global por e-mail que permita a terceiros impedir indefinidamente o acesso de uma
conta. IP encaminhado só é aceito quando o ambiente confirma o ingresso Vercel.
O limite global pode negar temporariamente acesso sob abuso distribuído; regras
de borda e alertas devem complementar a proteção quando o serviço escalar.

## Segundo fator sem atalho de sessão

`password_login` e `confirm_login` retornam `mfaRequired` quando existe um fator
verificado ou quando a administração exige MFA. Nessa resposta não há cookie de
sessão. `mfa_enroll` fornece o QR de um autenticador; `mfa_verify` confirma o código
no Supabase, valida a identidade e exige `aal2` antes de criar a sessão.

Os tokens intermediários ficam criptografados com AES-GCM, por cinco minutos, com
cinco tentativas por desafio. O navegador mantém apenas o identificador pendente
em memória; nenhum token Supabase é enviado ao navegador ou salvo em localStorage.
O QR é mostrado somente durante o cadastro solicitado pela pessoa autenticada.

Antes de exigir MFA, o titular deve configurar `RADAR_AUTH_ENCRYPTION_KEY` com 32
bytes aleatórios codificados em base64 e guardar cópia no gerenciador de segredos.
Essa chave é diferente da chave de backup. Validar cadastro, código incorreto,
expiração, login por senha, link de e-mail e recuperação em staging. Só depois
definir `RADAR_MFA_REQUIRED_EMAILS` ou `radar_account_security.require_mfa` para as
contas autorizadas, com um procedimento de recuperação de acesso confirmado.
Nenhum fator de contas existentes foi ativado automaticamente.

## Banco e privilégios

O cliente exige TLS `verify-full`. O padrão inclui o certificado público Supabase Root2021 disponibilizado no painel do provedor; a conexão com o banco existente foi conferida por leitura. Se o emissor do banco exigir uma CA específica, provisionar seu arquivo
público e definir `RADAR_POSTGRES_CA_FILE` com caminho absoluto. Não há fallback
para TLS sem verificação. Em staging, testar certificado válido e hostname/CA
inválidos: os inválidos precisam falhar antes de qualquer consulta.

A migração 022 prepara `radar_web` e `radar_collector` como NOLOGIN/NOBYPASSRLS, sem
senhas. As tabelas privadas exigem contexto de empresa e vínculo para `radar_web`.
`database_roles.company_transaction` habilita o papel por transação quando
`RADAR_DB_ENFORCE_ROLES=1`. O titular deve criar credenciais independentes no
provedor, conceder o papel adequado e conectar cada serviço com o menor privilégio
necessário. Não ativar o sinalizador até validar o fluxo inteiro com esse papel. O contexto restrito está ligado às consultas de perfil e exportação/escrita de avaliações; outras rotas mantêm autorização explícita no servidor.
O acesso administrativo atual do servidor continua podendo ultrapassar RLS; a
preparação dos papéis não equivale à troca das credenciais em produção.

## Backup criptografado e restauração

Usar armazenamento privado fora do Git e fora do serviço que contém o banco.
`scripts/backup_database.py` usa `pg_dump` completo e criptografia AES-256-GCM em
blocos, sem gravar a chave no arquivo. A senha do banco é passada ao processo por
ambiente, nunca nos argumentos ou no log. O arquivo inclui dados privados de Auth
e precisa continuar criptografado. O titular deve configurar
`RADAR_BACKUP_ENCRYPTION_KEY` e um destino privado, com retenção e cópia da chave
separada. A chave de backup não deve ser armazenada junto do backup.

Exemplos de operação pelo titular, com variáveis provisionadas no terminal seguro:

```text
python scripts/backup_database.py backup --archive /destino-privado/radar.nexo-backup
python scripts/backup_database.py validate --archive /destino-privado/radar.nexo-backup
python scripts/backup_database.py restore-test --archive /destino-privado/radar.nexo-backup --database-url-env RADAR_RESTORE_TEST_URL --allow-test-restore
```

A restauração só aceita localhost e banco `radar_restore_test_*` já criado e vazio;
não existe comando para excluir ou limpar banco. São exigidos `pg_dump`, `pg_restore`
e `psql` compatíveis com a versão do servidor. O teste automatizado offline cobre
criptografia, integridade e adulteração; a restauração real com PostgreSQL é uma
etapa separada e só deve ser registrada como concluída após executar o último
comando e conferir contagens, hashes, perfis, vínculos e avaliações restaurados.
Agendar backup diário e ensaio mensal em infraestrutura privada do titular.

## Monitoramento e cadeia de dependências

`health.yml` é separado da coleta e autentica `POST /api/collect {action:"health"}`
com identidade OIDC limitada ao repositório privado, branch principal e workflow
exato. Não armazena token de banco no GitHub. Habilitar `RADAR_MONITORING_ENABLED=1`
nas variáveis do repositório somente após staging e configurar recebimento das
notificações de falha do GitHub. Esse monitor compartilha o provedor GitHub;
um monitor externo ao GitHub e à Vercel requer provisionamento adicional.

A CI exige o lock Python com hashes, npm lock, testes, build, auditoria de pacotes
e verificação de padrões de credenciais sem imprimir valores. O scanner local
cobre padrões comuns e arquivos de ambiente; não certifica que todo segredo
possível esteja ausente nem substitui uma análise do histórico completo. Segredos
que já circularam em mensagens devem ser substituídos pelo titular no provedor e
nos ambientes autorizados, sem reenviá-los ao chat.

## Staging, aprovação e reversão

1. Criar banco separado e segredos exclusivos; usar dados públicos e contas de teste.
2. Aplicar migrações em ordem e conferir permissões com contas de Public/Gerico.
3. Validar coleta interrompida/retomada, relatórios de cobertura, falhas, quota,
   login/MFA, isolamento entre empresas e restauração de backup nesse ambiente.
4. Preparar preview privado com resultados e limitações. A publicação em produção
   exige aprovação explícita do titular e janela de mudança.
5. Guardar implantação anterior e backup anterior à migração. Para reversão da
   aplicação, promover a implantação anterior e interromper os jobs novos. Manter
   tabelas e evidências novas: não apagar dados para reverter interface/código.
   Migrações destrutivas ou restauração sobre produção exigem plano específico.

## Ensaio de recuperação e configuração externa

Em 12/11/2026, backup cifrado de dados descartáveis e amostras públicas foi restaurado
em outro PostgreSQL18 local vazio: 33 tabelas, 73 registros e hashes coincidentes.
Isso valida o mecanismo de restauração; não é backup da produção nem prova de S3.
A chave efêmera do ensaio não foi retida. Evidência em HOMOLOGACAO_AUTONOMA.md.

O workflow `backup.yml` permanece desativado. No ambiente protegido `backup` do
GitHub, provisionar os segredos `RADAR_BACKUP_DATABASE_URL`,
`RADAR_BACKUP_ENCRYPTION_KEY`, `RADAR_BACKUP_AWS_ACCESS_KEY_ID`,
`RADAR_BACKUP_AWS_SECRET_ACCESS_KEY`; nas variáveis, bucket, prefixo, endpoint
opcional e região (`RADAR_BACKUP_S3_BUCKET`, `RADAR_BACKUP_S3_PREFIX`,
`RADAR_BACKUP_S3_ENDPOINT`, `RADAR_BACKUP_AWS_REGION`). Credencial limitada a
PutObject/GetObject no prefixo; bucket com acesso público bloqueado e criptografia.
Configurar retenção com lifecycle conforme prazo aprovado pelo titular; o script
não elimina arquivos. Chave AES guardada separada e com recuperação documentada.

O runner precisa de AWS CLI e clientes PostgreSQL18 compatíveis, verificados antes
por `aws --version` e `pg_dump --version`. O upload exige arquivo cifrado, compara
metadados/tamanho e pode conferir download com `--verify-download`. Validar tudo no
destino autorizado antes de definir `RADAR_BACKUP_ENABLED=1`. Ensaio mensal de
restauração em ambiente isolado, sem restaurar sobre a produção.

Para migrar, o bootstrap agora exige `--env-file` e `--project-ref`. O projeto
produtivo conhecido é recusado sem `--production`; essa opção exige aprovação do
titular para a versão exata. Não existe carregamento automático de dotenv produtivo
no comando. Falhas retornam tipo de erro sem imprimir credenciais.
