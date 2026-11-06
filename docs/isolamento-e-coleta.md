# Contas separadas e cobertura da coleta

## Isolamento

- Cada sessão é vinculada no servidor a um e-mail autorizado e às empresas de `radar_memberships`.
- As contas Public e Gerico têm um único vínculo cada. A administração tem os dois vínculos e escolhe um espaço por vez.
- O parâmetro `company` apenas seleciona um vínculo existente. Alterá-lo não concede acesso.
- Catálogo, situação da coleta e detalhes exigem sessão válida. Respostas são privadas, sem cache compartilhado. Não há exploração pública nem fallback de catálogo entre contas.
- A chave das avaliações é `(opportunity_id, company_id)`. Histórico e exemplos também incluem a empresa. A mesma contratação pode receber decisões independentes.
- Rascunhos ficam na sessão do navegador, com chave por empresa e conta; sair limpa esses rascunhos. O cache em memória é criado por montagem do espaço e descartado ao sair ou trocar de empresa.
- Resumos são montados por empresa e só enviados aos seus destinatários. Perfis ainda não configurados não recebem oportunidades de outra empresa.
- As tabelas continuam com RLS e sem permissões para `anon` ou `authenticated`. A autorização do aplicativo ocorre antes de usar as credenciais exclusivas do servidor.

## Perfil Public

Mantém quatro grupos: documentos/apoio administrativo; gestão empresarial pública e privada; palestras e capacitação profissional/gerencial; ensino EAD. Desenvolvimento de sistemas e serviços de TI foram removidos. Contratos de licenciamento, locação, desenvolvimento ou manutenção de software são excluídos mesmo quando mencionam treinamento como serviço acessório. A reclassificação recalcula apenas dados derivados, preservando os registros originais.

Frases específicas no objeto produzem candidatas. Combinações de treinamento/curso com servidores, gestores ou contexto profissional entram com 45 pontos e exigem análise. Menções apenas nas informações complementares não viram recomendações. Essa ampliação não significa que toda candidata está apta à participação.

## Coleta

A coleta inicial tinha recebido 1.400 registros e estava na primeira modalidade; seis candidatas não representavam cobertura nacional concluída. A modalidade 9 (inexigibilidade) foi acrescentada. Além de publicações e atualizações, a coleta inclui propostas abertas.

A fila incremental prioriza a primeira leitura das propostas abertas. Depois, alterna uma página por modalidade e origem antes de retornar à próxima página. O cursor antigo é migrado mantendo a página já salva e as verificações de repetição. Assim, uma modalidade com muitas páginas não impede a primeira leitura das demais. Cada página e seu avanço são gravados juntos. Falhas de transporte de uma modalidade mantêm sua página pendente e deixam as demais avançarem. Limites do PNCP (429), espera entre consultas, retomada e proteção de armazenamento foram mantidos.

Execuções automáticas em 00h15, 06h15, 12h15 e 18h15 (Brasília), com orçamento de oito minutos cada. Uma execução pode terminar com cobertura parcial e progresso salvo. Timeouts, limites de consulta e indisponibilidades conhecidas do PNCP são registrados como pausa, com aviso e resumo explícito de cobertura incompleta no GitHub. Falhas de autenticação, dados inválidos e problemas de armazenamento continuam sendo falhas da execução. Uma checagem manual de 120 segundos está disponível sem alterar o orçamento normal agendado. O painel distingue registros recebidos, candidatas por perfil e processos com prazo futuro. Inexigibilidades e processos encerrados podem servir como referência e não são apresentados como disputa aberta.

## Verificação

Testes cobrem tentativa de trocar empresa no parâmetro, vazamento de pontuações/evidências, avaliações por empresa, feedback assinado para empresa diferente, descarte de cache após 403 e rotação/retomada do coletor. A validação em produção usa sessões temporárias e remove suas próprias sessões ao final, sem enviar e-mails ou alterar senhas das empresas.
