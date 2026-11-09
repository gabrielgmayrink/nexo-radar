# Seleção pelo objeto contratado

A coleta nacional não usa palavras-chave da Public: percorre todas as páginas
de `/v1/contratacoes/proposta`, sem filtros de UF, modalidade ou publicação.
O total nacional é diferente do número de oportunidades selecionadas por empresa.
Itens, documentos, contratos assinados e republicações não são novos editais.

A rotina nacional retoma automaticamente até três tentativas de 90 minutos no
mesmo job, com intervalo entre tentativas e sem repetir páginas já confirmadas.
Uma execução ainda incompleta termina com erro, preserva o cursor e não libera o
resumo semanal. O diagnóstico curto de 120 segundos executa uma única tentativa.

A Public exige indícios do serviço no objeto principal. A regra normaliza o texto
e delimita menções a finalidade do espaço, exemplos, temas de cursos e serviços
incluídos. Compras de equipamentos, materiais, software, transporte, reformas,
tradução e alimentação não se tornam oportunidades apenas por mencionar palestras,
capacitação ou apoio administrativo. O tema de um curso ou o local da prestação
também não elimina uma contratação real do serviço.

Exemplo: modernização de auditório onde ocorrem palestras não contrata palestra.
Já contratação de palestrante para ministrar palestra em auditório é selecionável.
Inscrições e descrições menos específicas de formação de equipes continuam na
lista de análise, sem recomendação forte. A regra é determinística, explicável e
não garante elegibilidade: o edital e seus anexos continuam sujeitos a conferência.

`requireServiceIntent` é uma opção de perfil; não altera empresas sem essa opção.
A Gerico permanece sem critérios enquanto seus serviços não forem definidos.

Ao mudar a versão da regra, a leitura do catálogo recalcula cartões antigos antes
de devolvê-los. `scripts/reclassify_profiles.py` atualiza os campos derivados em
lotes, com trava global e comparação do hash da fonte. Não modifica o objeto bruto,
os recibos de cobertura nacional, avaliações ou histórico. Pode reabrir arquivados
por perfil que passem a ser pertinentes; preserva arquivamentos por prazo/situação.
A classificação futura de novas páginas e a leitura usam a mesma regra.
