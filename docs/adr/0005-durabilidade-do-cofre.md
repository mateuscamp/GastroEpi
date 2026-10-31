# 0005 — Durabilidade do cofre: checagem na abertura, backup conferido, rotação por data e cópia externa

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** Integridade do dado clínico ("não perder nem corromper dados", prioridade nº 1)
e operação sem suporte (usuário leigo no Windows)

## Contexto

O app vai para a mão de um usuário leigo, no Windows, sem ninguém para chamar. A análise
de 2026-10-24 (branch `docs/adr-0001-arquitetura`) achou estas lacunas na v0.1.16:

- A rotação guarda os 5 backups mais recentes. Abrir o app 5 vezes num dia apaga todo o
  histórico, inclusive a única cópia de antes de um estrago.
- O backup é copiado direto para o nome final e nunca é conferido. Uma cópia truncada ou
  corrompida substitui uma boa, e só se descobre na hora de restaurar.
- Nada confere o banco na abertura. Um arquivo corrompido (disco, desligamento) é lido e
  editado até o erro aparecer no meio de uma tela.
- Duas instâncias podem abrir o mesmo banco. O SQLite aguenta, mas os backups e a
  rotação de uma correm por cima dos da outra.
- Nada impede o banco de ficar numa pasta do OneDrive, Google Drive, Dropbox ou iCloud.
  O cliente de sincronização copia o `.db` no meio de uma escrita, separado do `-wal`, e
  cria "cópias em conflito". É a causa mais comum de banco SQLite corrompido em máquina
  doméstica.
- Todas as cópias ficam no mesmo disco do banco. Disco morto, notebook roubado ou
  ransomware levam tudo junto.

O ADR-0003 deixou para cá a rotação e a validade dos backups (item 7 e Notas). O backup já
sai cifrado pela API de backup entre duas conexões SQLCipher, com o `gastroepi.chave` junto.

Quantum: 1, inalterado. O dono dos arquivos continua sendo `persistencia`; `servicos`
expõe os casos de uso, e a casca (Fase 5) só liga o timer e mostra as ofertas e avisos.

## Alternativas consideradas

| Ponto | Opção | Ganha | Perde | Escolha |
|---|---|---|---|---|
| Checagem na abertura | `PRAGMA integrity_check` | Confere também os índices contra as tabelas | Mais lento; cresce com os índices | Não: fica para o backup e o "verificar" |
| | **`PRAGMA quick_check`** | Lê todas as páginas (e o SQLCipher confere o HMAC de cada uma); O(N) | Não confere índice contra tabela | **Sim** |
| | Nenhuma (como hoje) | Abre na hora | O estrago aparece no meio do trabalho | Não |
| Banco que não passa | Recusar abrir | Simples | O usuário fica sem ver os próprios dados | Não |
| | **Abrir somente leitura + oferecer o último backup bom** | Lê o que der; a escrita não piora o estrago; a saída é um botão | Mais um estado na sessão | **Sim** |
| | Restaurar sozinho | Zero cliques | Descarta, sem perguntar, o que entrou depois do backup | Não |
| Backup | Copiar o arquivo (como hoje) | Simples | Cópia de um banco aberto em WAL pode sair incoerente | Não |
| | **API de backup → temporário → `integrity_check` + `cipher_integrity_check` → renomear** | Só existe com o nome final o que passou na checagem | Uma abertura a mais por backup | **Sim** |
| Rotação | Os N mais recentes (como hoje) | Simples | Um dia movimentado apaga o histórico | Não |
| | **Por data: 7 diários, 4 semanais, 12 mensais** | Um ano de histórico com ~23 cópias; um dia movimentado não apaga a semana passada | Lógica de calendário para testar | **Sim** |
| Quando copiar | Só ao abrir (como hoje) | Simples | Um dia inteiro de digitação sem cópia | Não |
| | **Ao fechar e a cada 15 min, se houve alteração** | Perde no máximo 15 min de digitação se o disco do banco morrer | Backup durante o uso (é rápido: ~16 MiB) | **Sim** |
| Instância única | Socket local / named pipe | Pode passar a janela para a frente | Abre porta (Princípio I) | Não |
| | **Trava de arquivo (`flock` / `msvcrt.locking`)** | O sistema solta a trava quando o processo morre | Não traz a outra janela para a frente | **Sim** |
| Pasta sincronizada | Avisar e deixar abrir | Não trava ninguém | O leigo clica "OK" e corrompe o banco | Não |
| | **Recusar abrir, com heurística por sistema** | Fecha a causa mais comum de corrupção | Falso positivo em pasta com nome parecido | **Sim** |
| Cópia fora da máquina | Mandar o banco em uso para o Drive | Nada a configurar | É exatamente a pasta sincronizada acima | Não |
| | **Destino externo opcional, só com cópias prontas e conferidas** | Sobrevive ao disco, ao roubo e ao ransomware local | Mais uma configuração; pendrive esquecido | **Sim** |

## Decisão

1. **Checagem na abertura.** Toda abertura roda `PRAGMA quick_check`. Um `DatabaseError`
   durante a checagem conta como falha. Se falhar, o banco abre com `PRAGMA query_only = ON`
   e sem migrar. A sessão fica marcada como somente leitura e traz o backup oferecido: o
   mais recente que abre com a chave atual e passa no `quick_check`. Restaurar é sempre um
   pedido do usuário.
2. **Página 1 corrompida.** A senha abriu o `gastroepi.chave`, já que o GCM autentica o
   embrulho, mas a chave não abre o banco. Logo, o banco está ilegível. Nesse caso o
   desbloqueio levanta `BancoIlegivel`, com o mesmo backup oferecido. Pela recovery key,
   continua `ChaveIncorreta`: ali não há como distinguir.
3. **Restaurar** nunca apaga o banco estragado. O `.db`, o `-wal` e o `-shm` são
   renomeados para `gastroepi.db.corrompido-<momento>`. O backup é copiado para um
   temporário na pasta do cofre, conferido e renomeado para `gastroepi.db`. O
   `gastroepi.chave` atual fica: o backup oferecido está na mesma chave de dados, e o
   arquivo do backup pode ter o embrulho de uma senha antiga.
4. **Backup.** Cada backup é uma pasta `backups/gastroepi-AAAA-MM-DD-HHMMSS/` (horário UTC)
   com `gastroepi.db` e `gastroepi.chave`. Passos:
   - a cópia é feita pela API de backup numa pasta `backups/.temp-…`;
   - a cópia passa para `journal_mode = DELETE`, para ser um arquivo só;
   - a cópia é conferida com `integrity_check` = `ok` e `cipher_integrity_check` vazio;
   - os arquivos recebem fsync e a pasta é renomeada para o nome final.

   Cópia que não passa é apagada e vira erro. A rotação não roda, e nenhuma cópia antiga
   sai. Uma `.temp-…` que sobrou de uma queda é apagada no backup seguinte.
5. **Rotação por data**, depois de cada backup bem-sucedido, contando os dias, semanas ISO e
   meses que têm cópia (como o `--keep-daily` do restic):
   - fica a cópia mais recente de cada um dos 7 dias mais recentes, das 4 semanas mais
     recentes e dos 12 meses mais recentes;
   - a cópia mais nova sempre fica;
   - fora disso, a pasta é apagada.

   As datas são as do fuso local da máquina. Contar só os períodos com cópia faz um mês
   sem abrir o app não apagar nada.
6. **Backup automático** como serviço com relógio injetado (`BackupAutomatico`). O timer de
   verdade é da casca.
   - `tique()` copia se passaram 15 min desde a última cópia (ou desde a abertura) e houve
     alteração;
   - `ao_fechar()` copia se houve alteração;
   - a marca de alteração é o maior `id` da `auditoria`, já que toda mutação grava um evento;
   - sessão somente leitura nunca copia, para não deixar uma cópia ruim empurrar as boas
     para fora da rotação;
   - gerar nova recovery key faz backup logo depois do rekey. Assim sempre há uma cópia na
     chave nova, que é a que o item 1 consegue oferecer.
7. **Instância única** por trava exclusiva e não bloqueante em `gastroepi.trava`, na pasta do
   cofre (`fcntl.flock` no Linux, `msvcrt.locking` no Windows). A casca segura a trava
   enquanto o app vive. Outra instância recebe `OutraInstanciaAberta`.
8. **Pasta sincronizada.** Criar, desbloquear e recuperar recusam (`PastaSincronizada`) um
   cofre cujo caminho resolvido fica dentro de uma pasta do OneDrive, Google Drive, Dropbox
   ou iCloud. A heurística é pura e recebe o sistema, as variáveis de ambiente e um teste de
   existência de arquivo. Ela acusa:
   - componentes do caminho: `OneDrive`, `OneDrive - …`, `Google Drive`, `GoogleDrive`,
     `My Drive`, `Meu Drive`, `Shared drives`, `Drives compartilhados`, `Dropbox`,
     `Dropbox (…)`, `iCloudDrive`, `iCloud Drive`, `Mobile Documents`;
   - estar sob `%OneDrive%`, `%OneDriveConsumer%` ou `%OneDriveCommercial%` (Windows);
   - estar sob um montador de nuvem do Linux: `gvfs/google-drive:…` ou `gvfs/onedrive:…`;
   - um ancestral com `.dropbox` ou `.dropbox.cache` (Dropbox com a pasta renomeada).
9. **Destino externo opcional** (pendrive ou pasta do Drive). Fica gravado no `metadados` do
   banco cifrado, junto com o momento da última cópia externa. Depois de cada backup
   automático, a cópia mais nova vai para `<destino>/GastroEpi-backups/`: um temporário,
   conferido ali mesmo, renomeado e com a mesma rotação. Destino ausente (pendrive fora) não
   é erro: a cópia fica para a próxima. As três regras da conversa de 2026-10-24:
   - o banco em uso nunca fica na pasta sincronizada. O item 8 garante isso, e o que vai
     para o destino é só a cópia pronta e conferida, com o `gastroepi.chave`;
   - a recovery key nunca vai para o destino. Nada no app a grava em disco (ADR-0003); um
     teste varre os bytes do destino atrás dela;
   - destino numa pasta sincronizada (detectada pelo item 8) só é aceito com senha de frase
     longa: pelo menos 4 palavras e 20 caracteres. Fora da máquina, o Argon2id só atrasa a
     adivinhação.
10. **Aviso de cópia externa atrasada.** O serviço informa se nunca houve cópia externa ou se
    a última tem mais de 7 dias. Sem destino configurado, não há aviso.

## Consequências

**Ganha:**
- Um dia movimentado não apaga mais o histórico. São até ~23 cópias cobrindo um ano.
- Nenhuma cópia não conferida tem o nome final, e cópia ruim não empurra cópia boa para fora.
- O estrago aparece na abertura, com o banco protegido de escrita e uma saída de um clique.
  O banco estragado fica guardado para quem quiser investigar.
- A causa mais comum de corrupção doméstica (pasta sincronizada) fica fechada.
- Com destino externo, o dado sobrevive ao disco e à máquina, sem o banco em uso sair dela.

**Perde:**
- A abertura fica mais lenta: o `quick_check` lê o arquivo inteiro (medido na Fase 4).
- Cada backup abre a cópia mais uma vez para conferir.
- A heurística de pasta sincronizada pode recusar uma pasta só com nome parecido
  (ex.: `C:\Projetos\Dropbox antigo`). O erro diz qual nome casou.
- O backup oferecido para restaurar tem de estar na chave atual. Cópias de antes de um rekey
  só abrem manualmente, com a recovery key antiga e a senha da época.
- Um backup abre com a senha que valia quando ele foi feito: o `gastroepi.chave` vai junto
  como era.

**Aceito conscientemente:**
- Trava de arquivo não traz a outra janela para a frente. A casca só diz que o app já está aberto.
- O `quick_check` não confere índice contra tabela. O backup e o "verificar" rodam o
  `integrity_check` completo.
- Datas da rotação no fuso local: na troca do horário de verão, uma cópia pode cair no dia
  vizinho. Isso só muda qual cópia do dia fica.
- Revisitar se a abertura a frio passar do teto de 8 s do ADR-0002 por causa do `quick_check`.
  O primeiro corte é trocá-lo pelo `cipher_integrity_check` (só o HMAC das páginas).

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| ★ Banco estragado abre só para leitura | Teste: bytes trocados no meio do arquivo → desbloquear → sessão somente leitura, escrita recusada, backup válido oferecido | CI | Abre para escrita ou não oferece o backup |
| ★ Página 1 estragada com senha certa | Teste: bytes trocados no 1º bloco → desbloquear → `BancoIlegivel` com o backup oferecido | CI | `ChaveIncorreta` ou sem oferta |
| ★ Oferta é o último backup bom | Teste: o backup mais novo corrompido → a oferta é o anterior | CI | Oferece o corrompido |
| ★ Restaurar não apaga o estragado | Teste: restaurar → banco abre e verifica; `gastroepi.db.corrompido-…` existe com os bytes originais | CI | Banco não abre ou o estragado sumiu |
| ★ Cópia ruim nunca ganha o nome final | Teste: conferência da cópia falha → nenhuma pasta nova, temporário apagado, cópias antigas intactas | CI | Pasta final criada ou cópia antiga apagada |
| Backup conferido e num arquivo só | Teste: a cópia passa em `integrity_check` e `cipher_integrity_check`, sem `-wal`, com `gastroepi.chave`, e abre com a senha | CI | Falha ou sobra arquivo |
| ★ Rotação por data | Propriedade (hypothesis) + exemplos: 7 diários, 4 semanais e 12 mensais mantidos; 20 cópias num dia não apagam os dias anteriores; a mais nova sempre fica | CI | Algum período perde a sua cópia |
| Backup a cada 15 min se alterou, e ao fechar | Teste com relógio falso: sem alteração não copia; com alteração copia só após 15 min; fechar copia se alterou; somente leitura nunca copia | CI | Copia fora da regra |
| Rekey deixa cópia na chave nova | Teste: gerar nova recovery key → existe backup que abre com a chave nova | CI | Não existe |
| Instância única sem socket | Teste: segunda trava na mesma pasta → `OutraInstanciaAberta`; soltar → trava de novo. Contrato "nenhum módulo usa rede" | CI (Ubuntu e Windows) | Duas travas ou socket |
| ★ Recusa pasta sincronizada | Tabela de casos Windows e Linux para a heurística (OneDrive por variável, Meu Drive, Dropbox renomeado, gvfs, iCloud) + teste de `criar_cofre` recusando | CI | Caso não acusado, ou falso positivo nos controles |
| ★ Destino externo: só cópia conferida, sem recovery key | Teste: a cópia externa abre e verifica; os bytes do destino não contêm a recovery key | CI | Cópia não abre ou a recovery key aparece |
| Destino na nuvem exige frase longa | Teste: destino sincronizado + senha curta → recusa; frase de 4 palavras → aceita; pendrive aceita senha curta | CI | Regra invertida |
| Aviso de cópia externa atrasada | Teste com relógio falso: 7 dias não avisa; 7 dias e 1 s avisa; nunca copiado avisa; sem destino não avisa | CI | Avisa errado |
| Tempo da abertura | `ferramentas/medir_listagem.py` mede a abertura com `quick_check` em 10 mil fictícios | Manual, a cada fase | Abertura > 2 s no Linux de referência |

Regras derivadas no `AGENTS.md`:
- "Nenhum backup ganha o nome final sem passar na conferência. Nenhum código apaga o banco
  estragado."
- "Sessão somente leitura nunca escreve nem copia."

## Notas

Autor: Mateus Campelo · Criado em: 2026-10-31 · Aprovado em: 2026-10-31
Estende: 0002, 0003
