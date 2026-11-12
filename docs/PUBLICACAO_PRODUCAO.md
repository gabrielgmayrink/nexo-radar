# Publicação de produção · 12/11/2026

Endereço canônico: https://nexo-radar-taupe.vercel.app. A liberação foi expressamente autorizada pelo titular, mantendo planos gratuitos. Este documento acompanha a conclusão; o relatório de homologação registra o ensaio anterior.

## Evidências já obtidas

- Backup produtivo anterior à migração restaurado em banco isolado no [GitHub Actions](https://github.com/gabrielgmayrink/nexo-radar/actions/runs/43302849254): 59 tabelas, 92.305 linhas, 74.851.499 bytes cifrados, download conferido e hashes/contagens iguais. Origem somente de leitura; nenhuma escrita produtiva pelo ensaio.
- Armazenamento produtivo dedicado `nexo-radar-backups-producao`, privado, São Paulo, Hobby. As três credenciais autorizadas estão separadas: login SQL somente de leitura, chave AES e token do armazenamento. A conexão administrativa não foi enviada ao job.
- Migrações até 032 aplicadas em produção. Não existe migração 018. Reclassificação concluída de 43.676 registros, sem exclusões. Compactação concluída em 69,97s com limite de 120s e espera de bloqueio de 3s; contagem preservada.
- API e coletor possuem logins SQL independentes. API não pode alterar a fonte oficial, ler fontes brutas ou hashes de senha. Coletor não pode ler identidades de autenticação. Perfis/avaliações continuam com autorização por empresa e contexto SQL restrito; não se afirma que todas as leituras privadas são isoladas exclusivamente pelo banco.
- Na homologação, o login real, MFA, revogação, escrita de perfis/avaliações e negação de acesso cruzado passaram com as novas credenciais. A prévia contém apenas usuários fictícios.

## Correção encontrada antes da liberação

A busca produtiva lia repetidamente documentos JSON completos para contagens e filtros, chegando a 57,7s e excedendo o limite de uma das consultas. A migração 033 mantém projeções escalares de situação, instrumento, UF, modalidade e valor, sincronizadas pelo mesmo gatilho da gravação oficial. Não altera a fonte nem as decisões da empresa. O documento completo continua disponível na página selecionada.

Na amostra de homologação com 38.370 registros, a consulta completa com paginação e facetas levou 828ms; filtro de UF 531ms, texto 485ms e descoberta 781ms. São medições pontuais, não SLA. Os testes exercitam também alterações do documento, suspensão, mudança de UF/modalidade, valores não numéricos e exclusão de instrumentos incompatíveis.

## Operação prevista e limites

Coleta nacional segunda às 07h, atualização diária às 09h17, arquivamento do catálogo ativo domingo às 23h, Brasília. O agendador pode atrasar. Toda página capturada tem recibo; a coleta retoma o cursor em falhas, preserva a união das passagens e distingue captura concluída de cobertura comprovada. A quantidade real é medida, sem meta artificial de um milhão.

O resumo semanal admite duas passagens capturadas e indexadas quando a fonte mudou, com aviso explícito de cobertura não confirmada; cada candidato é reconferido antes do envio. Falhas de verificação são omitidas do e-mail, preservadas no catálogo e contabilizadas. Gerico permanece sem perfil comercial ativo até informar serviços.

Backup produtivo semanal, segunda às 03h41, com restauração isolada em cada execução. Objetivo de perda máxima entre cópias: até uma semana, condicionado ao sucesso do job; não há recuperação contínua garantida. Orçamento de 512MiB no armazenamento; sem exclusão automática. Ao esgotar capacidade, o job falha conservando cópias e exige tratamento. Monitor de banco alerta em 400MiB e a coleta interrompe novas execuções em 450MiB. Planos gratuitos não comportam crescimento indefinido.

Senhas anteriormente compartilhadas devem ser substituídas por convites individuais de uso único, válidos por 24 horas; o administrador configura segundo fator. Convites e chaves de recuperação ficam em arquivos locais ignorados pelo Git. Nenhuma senha ou convite deve ser incluído em evidências públicas. A senha Gmail nova permanece exclusivamente na configuração secreta de produção; o teste autorizado tem destinatário fixo e trava de envio único.

## Estado da conclusão

Publicação, medição produtiva da migração 033, retirada das configurações administrativas antigas, teste de e-mail e primeira coleta produtiva permanecem em validação. Atualizar esta seção somente com resultados observados.
