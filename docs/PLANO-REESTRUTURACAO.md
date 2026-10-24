# Plano de reestruturação do GastroEpi

**Status:** Proposto · **Data:** 2026-10-24

## Decisões tomadas na conversa de 2026-10-24

| Decisão | Motivo | O que faria revisitar |
|---|---|---|
| Manter Tauri + Rust no núcleo | O app existe e funciona; o usuário final usa Windows (WebView2/Chromium), onde o Tauri não tem o problema do WebKitGTK | Bugs de tela tomarem mais tempo que funcionalidades; Tauri sem manutenção |
| Manter TypeScript + React na interface | No Tauri a tela é web; TS é a forma tipada de escrevê-la. Regra de negócio continua no Rust | — |
| Cifrar o arquivo inteiro com SQLCipher | Hoje idade, sexo, prontuário, pólipo, comorbidades ficam legíveis no arquivo e nos backups | Build com SQLCipher instável no CI do Windows |
| Estatística avançada = relatório fechado dentro do app (um botão, análises fixas, frases prontas) | Uso por pessoa leiga sem suporte; Jamovi exige escolhas; Python reabre empacotamento | Perguntas estatísticas passarem a mudar com frequência → Python |
| Teste manual em Windows real (máquina da esposa) com pacientes fictícios | Mesmo motor de tela do usuário final | — |
| Desenvolvimento pode seguir no Mac M1 ou no Linux | Indiferente, desde que cada entrega passe no roteiro em Windows | — |

## O que já existe na proteção do banco (levantado no código)

- `journal_mode=WAL`, `synchronous=EXTRA`, `foreign_keys=ON`, `busy_timeout=5000` (`db.rs` `obter_conexao`).
- Backup pela API online do SQLite no boot (`lib.rs`), rotação dos 5 mais recentes.
- `PRAGMA integrity_check` apenas sob demanda (botão na tela de auditoria).
- Permissão restrita no arquivo (0600 / ACL no Windows).
- Cadeia de auditoria HMAC com triggers append-only.

## Lacunas

1. Backup não é verificado depois de gravado, e é gravado direto com o nome final.
2. Rotação por quantidade: abrir o app 5 vezes num dia apaga todo o histórico anterior.
3. Backup só no boot; nada ao fechar nem periódico.
4. Backups no mesmo disco do banco; sem cópia externa.
5. Nenhuma checagem de integridade na abertura; banco corrompido abre para escrita.
6. Nada impede duas instâncias abertas.
7. Nada impede o banco de morar numa pasta sincronizada (OneDrive, Drive, Dropbox).
8. O sal da senha está dentro do banco; com SQLCipher ele precisa sair para um arquivo ao lado.

## Fases (nesta ordem)

### Fase 0 — Rede de segurança no CI
- `cargo test` e `npm run build` no `build.yml` (job Linux já tem GTK).
- Gerador de pacientes fictícios (comando de dev) para testes e para o Windows de teste.

### Fase 1 — Camada de durabilidade (ADR-0002)
Primeiro teste, visto falhar: criar banco → gravar eventos → corromper bytes → abrir → esperar modo somente leitura e oferta de restauração do último backup válido.
- `PRAGMA quick_check` ao abrir; falhou → somente leitura + assistente de restauração.
- Backup em arquivo temporário → `integrity_check` no backup → renomear para o nome final.
- Rotação por data: 7 diários, 4 semanais, 12 mensais.
- Backup ao fechar e a cada 15 min com alteração.
- Instância única (`tauri-plugin-single-instance`).
- Recusar abrir banco em pasta sincronizada.
- Destino externo configurável (pendrive/HD e, opcionalmente, pasta sincronizada **só para cópias de backup**), com aviso se a última cópia externa tiver mais de 7 dias.

### Fase 2 — Núcleo sem Tauri (ADR-0001)
Extrair `crates/gastroepi-core`; `math` deixa de importar `db`; validação de CPF/prontuário também no Rust.

### Fase 3 — SQLCipher (ADR-0003)
- Arquivo de chave ao lado do banco (sal e parâmetros do Argon2id); vai junto em todo backup.
- Migração em arquivo novo → conferir contagens e `verificar_integridade` → trocar → manter o antigo até confirmar.
- Cifragem por campo mantida na transição; removida depois de comprovado.
- Teste: buscar CPF e nome conhecidos nos bytes do arquivo → nenhum achado.
- Teste: backup + arquivo de chave restauram em diretório limpo.

### Fase 4 — Interface
Dividir `App.tsx` em `src/features/<painel>/`; tipos gerados do Rust em `src/bindings/`; `invoke` só em `src/api/`.

### Fase 5 — Dados para estatística (depende do dono)
- Lista de 5 a 10 perguntas que o dono quer respondidas.
- Laudo com campos estruturados (adenoma, serrilhado, avançado, câncer) além do texto.
- Relatório fechado: descritiva, associações com correção de Benjamini-Hochberg, uma regressão logística, tendência por idade, frases automáticas, avisos de poucos casos, parágrafo de limitações. Valores conferidos contra o R em teste.

## Teste em Windows (antes de cada entrega)
Máquina da esposa, **somente pacientes fictícios**, banco numa pasta de teste descartável. Roteiro fixo de ~10 min:
abrir e criar senha → cadastrar → editar → excluir → painel e estatísticas → relatório → exportar → fechar e reabrir → anotar o que pareceu estranho.
