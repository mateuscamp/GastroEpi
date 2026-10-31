# Roteiro manual no Windows (~10 min)

Fitness manual do ADR-0006, antes de cada entrega: o instalador passa por este roteiro na
máquina Windows de teste. Só pacientes fictícios, numa pasta descartável. Anote cada passo
estranho (texto confuso, demora, aviso inesperado) na tabela do fim. Passo estranho sem correção
reprova a entrega.

## Antes de começar

- Baixe o instalador do CI: no PR (ou na tag), aba **Checks** → **python** → **Summary** →
  artefato `instalador-…`. Descompacte o zip: dentro está `GastroEpi-<versão>-instalador.exe`.
- Use uma pasta descartável para o cofre: `C:\gastroepi-teste`. Ela não pode existir antes
  nem ficar dentro do OneDrive, Google Drive ou Dropbox (o app recusa, ADR-0005).
- Reinicie a máquina antes do passo 2: é a única forma de medir a abertura **a frio**.
- Tenha um cronômetro (o do celular serve).

## Passos

| # | Faça | Confira | Tempo |
|---|---|---|---|
| 1 | Dê dois cliques no instalador. Se aparecer "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo** (o instalador não é assinado, ADR-0006). Avance até o fim, sem marcar o atalho na área de trabalho, e desmarque "Abrir o GastroEpi". | Não pediu senha de administrador. Apareceu **GastroEpi** no menu Iniciar. | 1 min |
| 2 | Reinicie. Abra o Executar (**Win+R**), cole `"%LOCALAPPDATA%\Programs\GastroEpi\GastroEpi.exe" --pasta C:\gastroepi-teste` e dispare o cronômetro ao apertar Enter. | A tela **Criar a senha do GastroEpi** aparece em **até 8 s** (anote o tempo). | 1 min |
| 3 | Crie a senha `roteiro do gastroepi 2026` nos dois campos e clique em **Criar senha**. | Aparece **Anote a sua recovery key**. Não há botão de copiar. Marque **Anotei a chave no papel** (anote de verdade, num papel que vai para o lixo depois). | 1 min |
| 4 | Em **Pacientes**, clique em **Novo paciente**. Preencha um paciente inventado (nome `Fulano de Teste`, prontuário `T-001`, sexo, data de nascimento) e, na aba **Exames**, um exame com uma lesão. **Salvar**. | Aparece "Paciente cadastrado." e ele está na tabela. | 2 min |
| 5 | Busque `T-001` na caixa de busca e aperte Enter. Mude a data de nascimento e salve. | A ficha abriu pelo prontuário; a mudança aparece na tabela ("Ficha salva."). | 1 min |
| 6 | Cadastre um segundo paciente inventado (`Ciclano de Teste`, `T-002`), selecione-o e clique em **Excluir**. Confirme. | "Paciente excluído." Ele some da tabela; o `T-001` continua. | 1 min |
| 7 | Abra o **Painel**. | Os números batem com 1 paciente e 1 exame; nada cortado ou sobreposto. | 30 s |
| 8 | Abra o **StatCalc** → **Tabela 2x2**, preencha 10, 20, 30, 40 e calcule. | Sai OR, IC e p-valor, sem erro. | 1 min |
| 9 | Abra **Exportar** → **Exportar CSV…** e salve em `C:\gastroepi-teste-export.csv`. Abra o arquivo no Excel. | Os acentos aparecem certos; não há nome nem prontuário (exportação anônima). | 1 min |
| 10 | Feche a janela. Abra de novo pelo mesmo comando do passo 2 e entre com a senha. | Entrou; o `T-001` está lá com a data editada; o `T-002` não. | 1 min |

## Depois

- Desinstale pelo **Configurações → Aplicativos → GastroEpi → Desinstalar**.
- Confira que `C:\gastroepi-teste` continua lá (desinstalar nunca apaga o cofre), e só então
  apague essa pasta, o CSV do passo 9 e o papel do passo 3.

## Anotações

| Data | Versão | Abertura a frio (s) | Passo | O que foi estranho | Corrigido em |
|---|---|---|---|---|---|
| | | | | | |
