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

## Coleta nacional de abertas

O requisito é percorrer todas as contratações com propostas abertas no PNCP, em todo o Brasil. A coleta usa `/v1/contratacoes/proposta`, sem filtro de modalidade, UF, órgão, empresa ou data de publicação. O parâmetro obrigatório `dataFinal=99991231` evita o limite anterior de um ano para o encerramento. A API aceita até 50 registros por página, embora o manual antigo mencione 500; isso foi conferido no serviço real.

O GitHub consulta diretamente as páginas públicas, com até cinco leituras em andamento e intervalo mínimo de dois segundos entre inícios. A Vercel, em São Paulo, autentica o workflow por OIDC e recebe cada página. Nenhuma credencial do banco sai da Vercel. A gravação em lote usa duas operações de dados por página e preserva os registros originais antes da classificação por empresa.

Cada página tem um recibo durável, hash e referência à execução. Repetir o envio após uma perda de resposta não duplica dados nem avança duas páginas. Uma resposta com paginação incompleta é rejeitada. A coleta só recebe `coverageComplete=true` após percorrer as páginas previstas e conferir os registros únicos. Depois de percorrer as páginas previstas, uma conferência adicional consulta novamente a fonte e incorpora publicações que surgiram durante a leitura. IDs já recebidos são preservados. Uma redução do número de páginas pode ser reconciliada sem prender o cursor em uma página que deixou de existir. A conclusão da última página pode ser retomada se houver interrupção antes da finalização.

A leitura não possui o antigo limite de 10.000 páginas. Cada execução tem tempo operacional limitado, com retomada do cursor; atingir esse tempo não significa completar a busca. A coleta semanal inicia segunda-feira às 07h de Brasília (10h UTC), com até 90 minutos por execução. Timeouts e limites do PNCP continuam respeitados. O início depende da fila do GitHub Actions.

O painel mostra as páginas recebidas, o total nacional informado pela fonte e as candidatas da empresa. Contratações encerradas da antiga coleta por publicação não integram esse catálogo de abertas. Atualizações completas substituem a fotografia anterior; durante a leitura, os resultados já recebidos e a última fotografia concluída permanecem disponíveis.

O instrumento 4 (Edital de Chamamento Público) também é elegível quando ativo e com prazo aberto, incluindo credenciamentos. O instrumento 3 (autorização de contratação direta) continua fora das oportunidades com propostas abertas. Identificadores originais com ano numérico fora de quatro dígitos são preservados na importação, sem inventar uma correção: foi observado um registro da própria fonte com ano `20226`.

## Rotina semanal

- Domingo às 23h de Brasília (segunda, 02h UTC): retira do catálogo ativo as vencidas, inativas e sem aderência aos perfis configurados. Usa a mesma trava da coleta e recusa operar enquanto há uma varredura incompleta.
- A limpeza é um arquivamento do catálogo ativo: preserva os dados de origem, as avaliações, o aprendizado e os recibos da cobertura nacional. Não exclui uma decisão de uma empresa por causa da decisão de outra.
- Uma nova leitura do registro remove o arquivamento. Assim, uma prorrogação de prazo ou uma mudança de perfil pode fazer a oportunidade voltar.
- Segunda às 07h: começa a varredura nacional. O resumo semanal é uma etapa posterior da mesma execução; não tem mais disparo independente às 07h20. O servidor exige cobertura completa, coleta da segunda atual e identidade da execução que a concluiu. Uma coleta parcial não dispara o resumo semanal.
- Os avisos diários de prazo permanecem às 08h20, com conferência individual no PNCP. Os destinatários são resolvidos por empresa. A rotina roda na nuvem sem depender do Codex ou do computador pessoal.

## Verificação

Testes cobrem tentativa de trocar empresa no parâmetro, vazamento de pontuações/evidências, avaliações por empresa, feedback assinado para empresa diferente, descarte de cache após 403 e rotação/retomada do coletor. A validação em produção usa sessões temporárias e remove suas próprias sessões ao final, sem enviar e-mails ou alterar senhas das empresas.
