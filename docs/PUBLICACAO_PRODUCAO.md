# Publicação de produção · 12/11/2026

Endereço canônico: https://nexo-radar-taupe.vercel.app. A liberação foi expressamente autorizada pelo titular, mantendo planos gratuitos. Este documento acompanha a conclusão; o relatório de homologação registra o ensaio anterior.

**Publicação concluída.** Código integrado à main e domínio produtivo atualizado, credenciais restritas ativas, backup privado restaurado, redefinição de senhas por convites privados e somente resumos semanais habilitados. A base nacional concluída está disponível; a atualização incremental de rotina segue em segundo plano e não é apresentada como concluída. [Evidência produtiva sanitizada](validation/2026-11-12-production.json).

## Evidências já obtidas

- Backup produtivo anterior à migração restaurado em banco isolado no [GitHub Actions](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43302849254): 59 tabelas, 92.305 linhas, 74.851.499 bytes cifrados, download conferido e hashes/contagens iguais. Origem somente de leitura; nenhuma escrita produtiva pelo ensaio.
- Armazenamento produtivo dedicado `nexo-radar-backups-producao`, privado, São Paulo, Hobby. As três credenciais autorizadas estão separadas: login SQL somente de leitura, chave AES e token do armazenamento. A conexão administrativa não foi enviada ao job.
- Migrações até 033 aplicadas em produção. Não existe migração 018. Reclassificação concluída de 43.676 registros, sem exclusões. Após a projeção de filtros, a compactação final preservou os 43.679 registros existentes naquele instante e reduziu o banco de 346.175.155 para 284.939.955 bytes em 49,31s, com limite de 120s e espera de bloqueio de 3s. O aumento de três registros veio da coleta iniciada anteriormente.
- API e coletor possuem logins SQL independentes. API não pode alterar a fonte oficial, ler fontes brutas ou hashes de senha. Coletor não pode ler identidades de autenticação. Perfis/avaliações continuam com autorização por empresa e contexto SQL restrito; não se afirma que todas as leituras privadas são isoladas exclusivamente pelo banco.
- Na homologação, o login real, MFA, revogação, escrita de perfis/avaliações e negação de acesso cruzado passaram com as novas credenciais. A prévia contém apenas usuários fictícios.

## Correção encontrada antes da liberação

A busca produtiva lia repetidamente documentos JSON completos para contagens e filtros, chegando a 57,7s e excedendo o limite de uma das consultas. A migração 033 mantém projeções escalares de situação, instrumento, UF, modalidade e valor, sincronizadas pelo mesmo gatilho da gravação oficial. Não altera a fonte nem as decisões da empresa. O documento completo continua disponível na página selecionada.

Na amostra de homologação com 38.370 registros, a consulta completa com paginação e facetas levou 828ms; filtro de UF 531ms, texto 485ms e descoberta 781ms. São medições pontuais, não SLA. Os testes exercitam também alterações do documento, suspensão, mudança de UF/modalidade, valores não numéricos e exclusão de instrumentos incompatíveis.

Em produção, a primeira leitura após migração levou 12.703ms; UF 1.313ms, texto 1.562ms e perfil Gerico desativado 328ms. API autenticada com login próprio recusou alteração canônica, fonte bruta e hash de senha; coletor escreveu com reversão e não leu identidades Auth. Configurações `POSTGRES_*` e `SUPABASE_JWT_SECRET` não têm mais destino Production; as configurações de Auth e SMTP necessárias foram mantidas.

Na retomada, o checkpoint marcado `legacy_count_check` começa uma nova passagem numerada desde a página 1 e zera somente a prova de conferência. Documentos e recibos históricos permanecem. A união visível começa na primeira passagem do novo modelo; se a fonte encurta durante a leitura e exige outra passagem, o limite inicial não avança nem oculta os registros já observados. Testes reproduzem o checkpoint migrado e essa redução da lista.

## Operação prevista e limites

A medição produtiva identificou 54.378 cartões de apresentação sem aderência armazenando 81.317.029 bytes regeneráveis. A migração 034 remove apenas esse cache (`score<40`), preservando todas as linhas, originais, hashes, pontuações, recibos e decisões. Novas capturas e reclassificações evitam recriá-lo em massa. Descoberta e revisão geram o cartão para a página solicitada; o teste SQL exercita registro de pontuação zero, objeto integral, fonte bruta e identificação canônica. A homologação manteve seleção, UF, texto e descoberta funcionando; a suíte passou com 276 testes e zero ignorados.

A migração 034 foi aplicada também em produção com a atualização pausada: **55.311 registros e o mesmo fingerprint de fontes antes/depois**, 54.797 caches removidos e nenhum registro oficial excluído. A compactação seguinte preservou a mesma contagem e reduziu o banco de 481.441.459 para **326.227.635 bytes (311MiB)** em 51,84s; a diferença inclui o cache e espaço morto gerado pelas atualizações. Versão publicada e atualização retomada. Esse resultado libera capacidade para a carga inicial, sem prometer armazenamento ilimitado.

Coleta nacional segunda às 07h, atualização diária às 09h17, arquivamento do catálogo ativo domingo às 23h, Brasília. O agendador pode atrasar. Toda página capturada tem recibo; a coleta retoma o cursor em falhas, preserva a união das passagens e distingue captura concluída de cobertura comprovada. A quantidade real é medida, sem meta artificial de um milhão.

O resumo semanal admite duas passagens capturadas e indexadas quando a fonte mudou, com aviso explícito de cobertura não confirmada; cada candidato é reconferido antes do envio. Falhas de verificação são omitidas do e-mail, preservadas no catálogo e contabilizadas. Gerico permanece sem perfil comercial ativo até informar serviços.

Backup produtivo semanal, segunda às 03h41, com restauração isolada em cada execução. Objetivo de perda máxima entre cópias: até uma semana, condicionado ao sucesso do job; não há recuperação contínua garantida. Orçamento de 512MiB no armazenamento; sem exclusão automática. Ao esgotar capacidade, o job falha conservando cópias e exige tratamento. Monitor de banco alerta em 400MiB e a coleta interrompe novas execuções em 450MiB. Planos gratuitos não comportam crescimento indefinido.

Senhas anteriormente compartilhadas devem ser substituídas por convites individuais de uso único, válidos por 24 horas; o administrador configura segundo fator. Convites e chaves de recuperação ficam em arquivos locais ignorados pelo Git. Nenhuma senha ou convite deve ser incluído em evidências públicas. A senha Gmail nova permanece exclusivamente na configuração secreta de produção; o teste autorizado tem destinatário fixo e trava de envio único.

## Estado da conclusão

O monitor avalia a atualidade da base por atualização incremental concluída ou por captura nacional recente com duas passagens e indexação completa. Uma carga nacional antiga, apenas contagem histórica ou indexação incompleta não elimina o alerta. A recência operacional e a confirmação de cobertura permanecem independentes: fonte em movimento pode estar recente com `coverageComplete=false`. O teste SQL reproduz esses casos e o vencimento após 30h; a suíte final tem 277 testes.

A conferência operacional final sobre o banco real encontrou base recente, quarentena zerada, nenhum enriquecimento bloqueado e espaço abaixo do alerta. Havia 1.657 enriquecimentos pendentes, etapa separada da captura; não se afirma extração integral de todos os itens/PDFs. O incremental ativo não tinha erro e mantinha cursor salvo. Public continuava com 311 oportunidades na seleção consultada; os números mudam com os dados e filtros.

PR #1 integrado e produção publicada. Testes HTTP no domínio canônico: página 200, catálogo privado anônimo 401, sessão anônima sem dados, gravação de outra origem 403 e job sem identidade 403. Login visual verificado no domínio produtivo; o fluxo real completo com senha, MFA e negação cruzada foi exercitado na homologação, sem representar como concluída a definição das senhas pessoais em produção.

[Backup após publicação](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43309462418): 73 tabelas, 92.331 linhas, arquivo cifrado de 87.302.378 bytes, SHA256 `e55dbef799286438896bc6869d8c6ea502f6abe52c7d1a7a4fa62551c1dba904`, restauração e hashes/contagens conferidos. Nenhuma escrita produtiva pelo job.

[Envio de teste autorizado](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43309553384): exatamente uma mensagem aceita e encontrada na conta destinatária do proprietário, classificada pelo Gmail como spam. Nenhum reenvio nem alteração na caixa postal. Entrega aceita não garante classificação na caixa de entrada.

Após autorização específica, sessões antigas foram encerradas e as três contas receberam bloqueio de senha até definição por convite individual. Convites locais privados criados para Public, Gerico e administrador, sem envio a clientes. Cabe a cada responsável definir sua senha; o administrador deverá configurar MFA. Os arquivos e tokens não entram no repositório.

A [varredura nacional produtiva](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43310703193) concluiu as duas passagens em 12/11 às 20h35 de Brasília. Foram 797 páginas em cada passagem, 39.811 e 39.847 leituras de registros, com **39.848 identificadores distintos preservados na união**. Um identificador apareceu somente na primeira passagem e continua preservado. Não houve quarentena; captura e indexação completas. O PNCP mudou durante a conferência: `coverageComplete=false`, `consistency=source_changed`. Isso não é apresentado como prova de cobertura sem perdas. Os totais acumulados do checkpoint incluem as passagens históricas; não equivalem aos totais dessa conferência.

A consulta produtiva após a captura retornou 311 oportunidades abertas no perfil Public. É a seleção privada por serviços e prazos, não a quantidade nacional. Gerico continua sem seleção ativa até informar seus serviços.

Após autorização específica do titular, **somente os resumos semanais** foram habilitados para os destinatários empresariais configurados. `RADAR_EMAIL_ENABLED=1`, `RADAR_URGENT_EMAIL_ENABLED=0`. A Gerico só receberá oportunidades após configurar e ativar seu perfil; avisos diários permanecem desligados. Nenhum resumo real foi disparado manualmente durante a publicação.

O monitor independente está habilitado. A atualização incremental diária está em validação com retomada, sem reapresentar como pendente a varredura nacional já concluída. Após a captura, o banco atingiu o alerta de 400MiB. A compactação autorizada, com o coletor pausado, preservou 53.249 registros e reduziu o banco de 423.507.635 para 404.526.771 bytes em 76,69s, sem exclusões. A atualização atual foi iniciada após preservar o cursor legado descrito abaixo. O banco permanece com capacidade limitada; a proteção de 450MiB continua obrigatória.

Na conferência do incremental, o cursor legado ainda apontava para 08/10–06/11 e não tinha `target_end`. Como o escopo aprovado é o catálogo atual de abertas, após a captura nacional ele foi preservado integralmente sob `archive:sync:incremental:1:before-open-baseline-6`, com igualdade de hash do JSON antes/depois. A execução antiga foi identificada como parcial histórica, sem apagar registros, recibos ou tarefas pendentes. A atualização atual começa com sobreposição de dois dias; não se declara que o histórico de outubro foi concluído. A retomada desse histórico é uma operação separada, fora da cobertura de abertas solicitada e sujeita à capacidade.

[Cópia após bloquear senhas antigas](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43312049833): 73 tabelas, 100.096 linhas, 90.237.068 bytes cifrados, SHA256 `6616464174579d7d07e1d9076eb3a1965b835cefa0ee26a1b570b267f656d84c`, download e restauração validados com hashes/contagens coincidentes. Essa cópia inclui o bloqueio de redefinição das senhas, ao contrário dos ensaios anteriores ao bloqueio.
