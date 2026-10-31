# 0006 — Empacotar o Windows com PyInstaller (onedir) e instalador Inno Setup por usuário

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** Implantabilidade sem suporte: o usuário leigo instala e abre sozinho, no Windows,
dentro dos limites do ADR-0002 (instalador ≤ 250 MB, abertura a frio ≤ 8 s)

## Contexto

O ADR-0002 trocou um instalador Tauri de 2 MB por um executável Python congelado e deixou
para cá a escolha do empacotador. Ele fixou o gatilho de revisão da casca Qt: instalador acima
de 250 MB ou abertura a frio acima de 8 s na máquina Windows de teste. O usuário é leigo, não tem
suporte e não deve precisar de administrador. O cofre já mora fora da pasta do programa
(`%LOCALAPPDATA%\GastroEpi`, Fase 5), então reinstalar ou atualizar não toca o banco.

O CI já congela com PyInstaller no `windows-latest` duas vezes: a sonda do SQLCipher (Fase 0,
ADR-0003) e a da estatística (Fase 3, numpy + scipy: 176 MB de pasta, 69 MB em zip).

Medição desta fase (sonda temporária, `windows-latest`, PyInstaller onedir `--windowed`, app
inteiro: Qt + numpy + scipy + SQLCipher + pydantic + cryptography):

| Medida | Valor | Limite (ADR-0002) |
|---|---|---|
| Pasta instalada | 272 MB | — (o limite é do instalador) |
| 7z LZMA2 `-mx=9` (o mesmo compressor do Inno Setup) | 62 MB | 250 MB |
| Zip `-mx=9` | 104 MB | 250 MB |
| Janela pronta, 1ª rodada após o build (dentro do processo) | 3,9 s | 8 s |
| Janela pronta, rodadas seguintes | 1,2–1,7 s | 8 s |

O maior bloco é o scipy (47 MB + 20 MB de OpenBLAS, e o numpy traz outra cópia de 20 MB).
O Qt (só QtCore, QtGui e QtWidgets) soma ~70 MB. A folga para o teto é de 4x, então o corte do
scipy previsto no plano não é necessário agora.

Quantum atual: **1**. O executável congelado é dono exclusivo do cofre em
`%LOCALAPPDATA%\GastroEpi` (banco, `gastroepi.chave`, `backups/`). O instalador só copia
programa; nunca cria, move ou apaga o cofre.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| A. Nuitka standalone + instalador | Abertura ~20–40% mais rápida (compila para C); código menos legível no binário | Build de 30–60 min com scipy e PySide6 no CI; plugin do PySide6 exige ajuste por versão; toolchain C no runner; nada medido ainda neste projeto | A abertura já cabe com folga (3,9 s de 8); paga tempo de CI e risco novo sem ganhar no ★ |
| B. Briefcase (BeeWare) + MSI | Instalador MSI oficial; sem bootloader próprio, menos falso positivo de antivírus | Copia os pacotes inteiros, sem poda: PySide6 inteiro (~240 MB só ele no Linux) e scipy com testes; instala pelo pip, fora do `uv.lock`; nenhum spike no projeto | Arrisca o teto de 250 MB e quebra a reprodutibilidade do lock |
| C. PyInstaller onefile | Um `.exe` só | Descompacta ~270 MB no `%TEMP%` a cada abertura (lenta a frio); é o formato que mais dispara antivírus | Contra o ★ nas duas medidas |
| **D. PyInstaller onedir + Inno Setup por usuário** | Já provado no CI com o SQLCipher e o scipy; poda por hooks (só 3 módulos do Qt); build em ~2 min; versão travada no `uv.lock`; instalador LZMA2 de ~62 MB sem pedir administrador | Bootloader do PyInstaller ainda gera falso positivo em alguns antivírus; sem assinatura de código o SmartScreen avisa na 1ª execução; `.exe` em modo janela não tem console | — |

## Decisão

Congelar com **PyInstaller em modo onedir e janela** (`--windowed`), a partir de um `.spec`
versionado em `empacotamento/`, e embrulhar a pasta num **instalador Inno Setup por usuário**
(`PrivilegesRequired=lowest`, instala em `%LOCALAPPDATA%\Programs\GastroEpi`, atalho no menu
Iniciar). O PyInstaller entra num grupo de dependências `empacotamento` do `pyproject.toml`, com a
versão travada no `uv.lock`. O Inno Setup vem do Chocolatey do runner.

O executável tem um modo `GastroEpi.exe --smoke`: cria um cofre numa pasta temporária, cadastra
um paciente fictício, abre e fecha a janela, verifica a integridade e sai com 0. É ele que o CI
roda, no executável instalado, em todo PR.

A CLI de manutenção (`verificar`, `backup`, `exportar`, `demo`) continua para quem roda pelo
`uv`. No `.exe` em modo janela ela não tem onde pedir a senha, e não é entregue ao usuário.

## Consequências

**Ganha:**
- Instalador de ~62 MB, um quarto do teto, sem pedir administrador.
- Abertura medida em 3,9 s no pior caso do CI, metade do teto.
- Nenhuma ferramenta nova no build: o PyInstaller já congela o SQLCipher e o scipy no CI
  desde as Fases 0 e 3.
- O instalador é testado de verdade: o CI instala em silêncio e roda o `--smoke` do instalado.

**Perde:**
- O instalador fica ~30x maior que o do Tauri (62 MB contra 2 MB).
- Sem certificado de assinatura, o SmartScreen mostra "O Windows protegeu o computador" na 1ª
  execução; o roteiro manual ensina o "Mais informações → Executar assim mesmo".
- Bootloader do PyInstaller pode ser marcado por antivírus; o onedir reduz, mas não zera.
- O `.exe` não tem console: a manutenção pela CLI fica só para quem tem o código.
- A pasta instalada (272 MB) leva duas cópias do OpenBLAS (numpy e scipy).

**Aceito conscientemente:**
- A abertura do CI é "morna" (os arquivos acabaram de ser escritos). A abertura a frio de
  verdade é medida no roteiro manual, depois de reiniciar a máquina de teste.
- Revisitar se: o instalador passar de **200 MB** (primeiro corte: trocar o scipy por fórmulas
  próprias, como o plano diz); a abertura no roteiro passar de **8 s** (avaliar Nuitka); ou um
  antivírus comum bloquear o instalador na máquina de teste (avaliar assinatura de código).

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| ★ O executável congelado funciona | Job `instalador (windows)`: build do `.spec`, instalação silenciosa, `GastroEpi.exe --smoke` do instalado | CI, todo PR, push na `main` e cada tag | Código de saída ≠ 0 |
| ★ Teto de tamanho (ADR-0002) | O mesmo job mede o `.exe` do instalador | CI, idem | Instalador > 250 MB |
| ★ Abertura (ADR-0002) | O mesmo job mede o tempo de parede do `--smoke` | CI, idem | > 8 s |
| Entrega | Instalador como artefato do job (14 dias); em tag `v*`, com o nome da tag (90 dias) | CI, cada tag | Instalador ausente |
| Abertura a frio real e fluxo do usuário | Roteiro manual de ~10 min (`docs/ROTEIRO-WINDOWS.md`), após reiniciar | Máquina Windows de teste, antes de cada entrega | Mateus anota passo estranho sem correção, ou abertura > 8 s |

Regra derivada no `AGENTS.md`: "Empacotamento: `empacotamento/` (PyInstaller onedir + Inno Setup,
ADR-0006). Dependência nova que o congelado não acha entra como `hiddenimports` no `.spec`, com o
motivo; o `--smoke` do instalador no CI é o portão."

## Notas

Autor: Mateus Campelo · Criado em: 2026-10-31 · Aprovado em: 2026-10-31
Medição: sonda temporária no ramo `claude/sonda-fase6-temp` (removido), run 41231879796.
