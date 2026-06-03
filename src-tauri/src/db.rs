use crate::crypto::{Cofre, derivar_chave, gerar_recovery_key, cofre_de_chave_recovery, TIME_COST, MEMORY_COST, PARALLELISM};
use chrono::Utc;
use rusqlite::{params, Connection, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use rand::RngCore as _;
use base64::Engine as _;

pub const COMORBIDADES_PADRAO: &[&str] = &[
    "Diabetes Mellitus tipo 2",
    "Hipertensão Arterial Sistêmica",
    "Obesidade",
    "Doença de Crohn",
    "Retocolite Ulcerativa",
    "Tabagismo",
    "Etilismo",
    "Dislipidemia",
];

pub const SINTOMAS_PADRAO: &[&str] = &[
    "Hematoquezia / Sangramento retal",
    "Dor abdominal",
    "Alteração do hábito intestinal",
    "Perda de peso involuntária",
    "Anemia ferropriva",
    "Anemia não especificada",
    "TC com espessamento",
    "Diarreia crônica",
    "Constipação crônica",
    "Dor retal / Tenesmo",
    "Náuseas / Vômitos",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoricoFamiliar {
    pub id: Option<i64>,
    pub parentesco: String,
    pub grau: i32,
    pub idade_diagnostico: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Paciente {
    pub id: Option<i64>,
    pub numero_prontuario: String,
    pub cpf: Option<String>,
    pub nome: String,
    pub data_exame: String,
    pub idade: i32,
    pub sexo: String,
    pub polipo: i32,
    pub resultado_histopatologico: Option<String>,
    pub indicacao_exame: String,
    
    // Relacionamentos
    pub comorbidades: Vec<String>,
    pub sintomas: Vec<String>,
    pub historico_familiar: Vec<HistoricoFamiliar>,
    
    // Carregado dinamicamente via log de auditoria
    pub endoscopista: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntradaAuditoria {
    pub id: Option<i64>,
    pub timestamp: String,
    pub usuario: String,
    pub acao: String,
    pub entidade: String,
    pub entidade_id: Option<i64>,
    pub snapshot_antes: Option<String>,
    pub snapshot_depois: Option<String>,
    pub hash_atual: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InconsistenciaAuditoria {
    pub id_entrada: i64,
    pub motivo: String,
    pub hash_esperado: String,
    pub hash_encontrado: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InconsistenciaDados {
    pub entidade: String,
    pub entidade_id: Option<i64>,
    pub motivo: String,
    pub campos: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticoIntegridadeFisica {
    pub status: String, // "ok", "corrompido", "bloqueado", "erro"
    pub mensagem: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResultadoBackup {
    pub caminho: String,
    pub timestamp: String,
    pub removidos: Vec<String>,
}

pub struct BancoDados {
    caminho: String,
    cofre: Option<Cofre>,
}

fn obter_conexao(caminho: &str) -> Result<Connection> {
    let conn = Connection::open(caminho)?;
    conn.pragma_update(None, "busy_timeout", &5000)?;
    conn.pragma_update(None, "synchronous", &"EXTRA")?;
    conn.pragma_update(None, "journal_mode", &"WAL")?;
    conn.pragma_update(None, "foreign_keys", &"ON")?;
    Ok(conn)
}

#[cfg(unix)]
fn proteger_arquivo(caminho: &str) {
    use std::fs;
    use std::os::unix::fs::PermissionsExt;
    let metadata = fs::metadata(caminho);
    if let Ok(meta) = metadata {
        let mut perms = meta.permissions();
        if perms.mode() & 0o777 != 0o600 {
            perms.set_mode(0o600);
            let _ = fs::set_permissions(caminho, perms);
        }
    }
}

#[cfg(windows)]
fn proteger_arquivo(caminho: &str) {
    if let Ok(username) = std::env::var("USERNAME") {
        let status = std::process::Command::new("icacls")
            .arg(caminho)
            .arg("/grant:r")
            .arg(format!("{}:(F)", username))
            .status();
        
        match status {
            Ok(s) if s.success() => {
                let status2 = std::process::Command::new("icacls")
                    .arg(caminho)
                    .arg("/inheritance:r")
                    .status();
                if let Err(e) = status2 {
                    eprintln!("Aviso: Falha ao remover herança de permissões em {}: {:?}", caminho, e);
                } else if let Ok(s2) = status2 {
                    if !s2.success() {
                        eprintln!("Aviso: Comando icacls /inheritance:r retornou erro para {}", caminho);
                    }
                }
            }
            Ok(s) => {
                eprintln!("Aviso: Comando icacls /grant retornou erro para {}: status {}", caminho, s);
            }
            Err(e) => {
                eprintln!("Aviso: Falha ao executar icacls para {}: {:?}", caminho, e);
            }
        }
    } else {
        eprintln!("Aviso: Variável USERNAME não definida. Impossível aplicar ACL ao arquivo {}", caminho);
    }
}

#[cfg(not(any(unix, windows)))]
fn proteger_arquivo(_caminho: &str) {
    // No-op para outras plataformas (best-effort)
}

impl BancoDados {
    pub fn new(caminho: &str) -> Self {
        Self {
            caminho: caminho.to_string(),
            cofre: None,
        }
    }

    pub fn set_cofre(&mut self, cofre: Cofre) {
        self.cofre = Some(cofre);
    }

    pub fn cofre(&self) -> Option<&Cofre> {
        self.cofre.as_ref()
    }

    pub fn esta_desbloqueado(&self) -> bool {
        self.cofre.is_some()
    }

    /// Inicializa as tabelas, triggers e índices do banco de dados SQLite.
    pub fn criar(&self) -> Result<(), String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pacientes (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_prontuario         TEXT    NOT NULL UNIQUE,
                cpf                       TEXT,
                nome                      TEXT    NOT NULL,
                data_exame                TEXT    NOT NULL,
                idade                     INTEGER CHECK (idade >= 0),
                sexo                      TEXT CHECK (sexo IN ('M', 'F')),
                polipo                    INTEGER CHECK (polipo >= 0),
                resultado_histopatologico TEXT,
                indicacao_exame           TEXT    NOT NULL DEFAULT 'Rastreio'
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS comorbidades (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT    NOT NULL UNIQUE COLLATE NOCASE
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS paciente_comorbidade (
                paciente_id    INTEGER NOT NULL,
                comorbidade_id INTEGER NOT NULL,
                PRIMARY KEY (paciente_id, comorbidade_id),
                FOREIGN KEY (paciente_id)
                    REFERENCES pacientes(id) ON DELETE CASCADE,
                FOREIGN KEY (comorbidade_id)
                    REFERENCES comorbidades(id) ON DELETE CASCADE
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS sintomas (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT    NOT NULL UNIQUE COLLATE NOCASE
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS paciente_sintoma (
                paciente_id INTEGER NOT NULL,
                sintoma_id  INTEGER NOT NULL,
                PRIMARY KEY (paciente_id, sintoma_id),
                FOREIGN KEY (paciente_id)
                    REFERENCES pacientes(id) ON DELETE CASCADE,
                FOREIGN KEY (sintoma_id)
                    REFERENCES sintomas(id) ON DELETE CASCADE
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS historico_familiar (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id       INTEGER NOT NULL,
                parentesco        TEXT    NOT NULL,
                grau              INTEGER NOT NULL CHECK (grau IN (1, 2, 3)),
                idade_diagnostico INTEGER CHECK (idade_diagnostico >= 0),
                FOREIGN KEY (paciente_id)
                    REFERENCES pacientes(id) ON DELETE CASCADE
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS auditoria (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                usuario         TEXT    NOT NULL,
                acao            TEXT    NOT NULL,
                entidade        TEXT    NOT NULL,
                entidade_id     INTEGER,
                snapshot_antes  TEXT,
                snapshot_depois TEXT,
                hash_atual      TEXT    NOT NULL DEFAULT ''
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TABLE IF NOT EXISTS metadados (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_auditoria_entidade ON auditoria (entidade, entidade_id)",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp ON auditoria (timestamp)",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pacientes_nome ON pacientes (nome COLLATE NOCASE)",
            [],
        ).map_err(|e| e.to_string())?;

        // Triggers de restrição append-only
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS auditoria_no_update \
             BEFORE UPDATE ON auditoria BEGIN \
             SELECT RAISE(ABORT, 'auditoria é append-only: UPDATE proibido'); \
             END",
            [],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS auditoria_no_delete \
             BEFORE DELETE ON auditoria BEGIN \
             SELECT RAISE(ABORT, 'auditoria é append-only: DELETE proibido'); \
             END",
            [],
        ).map_err(|e| e.to_string())?;

        // Popula comorbidades padrão
        for c in COMORBIDADES_PADRAO {
            let _ = conn.execute(
                "INSERT OR IGNORE INTO comorbidades (nome) VALUES (?1)",
                [c],
            );
        }

        // Popula sintomas padrão
        for s in SINTOMAS_PADRAO {
            let _ = conn.execute(
                "INSERT OR IGNORE INTO sintomas (nome) VALUES (?1)",
                [s],
            );
        }

        proteger_arquivo(&self.caminho);
        Ok(())
    }

    /// Executa PRAGMA integrity_check e retorna o status detalhado.
    pub fn diagnosticar_integridade_fisica(&self) -> DiagnosticoIntegridadeFisica {
        if !Path::new(&self.caminho).exists() {
            return DiagnosticoIntegridadeFisica {
                status: "ok".to_string(),
                mensagem: "Banco ainda não existe".to_string(),
            };
        }

        match Connection::open(&self.caminho) {
            Ok(conn) => {
                if let Err(e) = conn.pragma_update(None, "busy_timeout", &5000) {
                    return DiagnosticoIntegridadeFisica {
                        status: "erro".to_string(),
                        mensagem: format!("Erro busy_timeout: {}", e),
                    };
                }
                
                let mut stmt = match conn.prepare("PRAGMA integrity_check") {
                    Ok(s) => s,
                    Err(e) => {
                        return DiagnosticoIntegridadeFisica {
                            status: "erro".to_string(),
                            mensagem: format!("Erro preparar integrity_check: {}", e),
                        };
                    }
                };

                let res: Result<String, _> = stmt.query_row([], |row| row.get(0));
                match res {
                    Ok(val) => {
                        if val == "ok" {
                            DiagnosticoIntegridadeFisica {
                                status: "ok".to_string(),
                                mensagem: "Integridade física OK".to_string(),
                            }
                        } else {
                            DiagnosticoIntegridadeFisica {
                                status: "corrompido".to_string(),
                                mensagem: val,
                            }
                        }
                    }
                    Err(e) => DiagnosticoIntegridadeFisica {
                        status: "erro".to_string(),
                        mensagem: format!("Erro query integrity_check: {}", e),
                    },
                }
            }
            Err(e) => {
                let msg = e.to_string();
                if msg.contains("locked") || msg.contains("busy") {
                    DiagnosticoIntegridadeFisica {
                        status: "bloqueado".to_string(),
                        mensagem: "Banco ocupado por outro processo; feche outras instâncias e tente novamente".to_string(),
                    }
                } else {
                    DiagnosticoIntegridadeFisica {
                        status: "erro".to_string(),
                        mensagem: msg,
                    }
                }
            }
        }
    }

    pub fn verificar_integridade_fisica(&self) -> bool {
        self.diagnosticar_integridade_fisica().status == "ok"
    }

    /// Cria um backup online do banco de dados rotacionando os backups antigos.
    pub fn realizar_backup(&self, max_backups: usize) -> Result<ResultadoBackup, String> {
        if !Path::new(&self.caminho).exists() {
            return Err("Banco de dados não existe".to_string());
        }

        let parent_dir = Path::new(&self.caminho)
            .parent()
            .unwrap_or(Path::new("."));
        let dir_backups = parent_dir.join("backups");
        std::fs::create_dir_all(&dir_backups).map_err(|e| e.to_string())?;

        let ts = Utc::now().format("%Y%m%d_%H%M%S_%f").to_string();
        let nome_bkp = format!("dados_backup_{}.db", ts);
        let caminho_bkp = dir_backups.join(nome_bkp);
        
        {
            let src_conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
            let mut dst_conn = Connection::open(&caminho_bkp).map_err(|e| e.to_string())?;
            
            let backup = rusqlite::backup::Backup::new(&src_conn, &mut dst_conn)
                .map_err(|e| e.to_string())?;
            
            backup.run_to_completion(100, std::time::Duration::from_millis(250), None)
                .map_err(|e| e.to_string())?;
        }

        proteger_arquivo(caminho_bkp.to_str().unwrap());

        let mut removidos = Vec::new();
        let mut arquivos = Vec::new();
        for entry in std::fs::read_dir(&dir_backups).map_err(|e| e.to_string())? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.is_file() {
                if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                    if name.starts_with("dados_backup_") && name.ends_with(".db") {
                        arquivos.push(path);
                    }
                }
            }
        }
        arquivos.sort();
        
        while arquivos.len() > max_backups {
            let antigo = arquivos.remove(0);
            let _ = std::fs::remove_file(&antigo);
            removidos.push(antigo.to_str().unwrap_or("").to_string());
        }

        Ok(ResultadoBackup {
            caminho: caminho_bkp.to_str().unwrap_or("").to_string(),
            timestamp: ts,
            removidos,
        })
    }

    // ──────────────────────────── Métodos de Autenticação ────────────────────────

    pub fn tem_senha_configurada(&self) -> Result<bool, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT COUNT(*) FROM metadados WHERE chave = 'salt'")
            .map_err(|e| e.to_string())?;
        let count: i64 = stmt.query_row([], |row| row.get(0)).map_err(|e| e.to_string())?;
        Ok(count > 0)
    }

    pub fn configurar_senha(&mut self, senha: &str) -> Result<String, String> {
        if senha.len() < 8 {
            return Err("Senha deve ter no mínimo 8 caracteres".to_string());
        }

        let mut salt = [0u8; 16];
        rand::thread_rng().fill_bytes(&mut salt);

        let key = derivar_chave(senha, &salt, MEMORY_COST, TIME_COST, PARALLELISM)?;
        let cofre = Cofre::new(key);
        let token_canario = crate::crypto::criar_canario(&cofre)?;

        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        
        use base64::engine::general_purpose::STANDARD;
        let salt_b64 = STANDARD.encode(salt);

        conn.execute(
            "INSERT OR REPLACE INTO metadados (chave, valor) VALUES ('salt', ?1)",
            [salt_b64],
        ).map_err(|e| e.to_string())?;

        conn.execute(
            "INSERT OR REPLACE INTO metadados (chave, valor) VALUES ('canario', ?1)",
            [token_canario],
        ).map_err(|e| e.to_string())?;

        self.cofre = Some(cofre);
        Ok(gerar_recovery_key(&key))
    }

    pub fn desbloquear(&mut self, senha: &str) -> Result<bool, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        
        let salt_b64: String = conn.query_row(
            "SELECT valor FROM metadados WHERE chave = 'salt'",
            [],
            |row| row.get(0)
        ).map_err(|_| "Nenhuma senha configurada no banco de dados".to_string())?;

        let token_canario: String = conn.query_row(
            "SELECT valor FROM metadados WHERE chave = 'canario'",
            [],
            |row| row.get(0)
        ).map_err(|e| e.to_string())?;

        use base64::engine::general_purpose::STANDARD;
        let salt = STANDARD.decode(salt_b64)
            .map_err(|e| format!("Falha ao decodificar salt: {}", e))?;

        let key = derivar_chave(senha, &salt, MEMORY_COST, TIME_COST, PARALLELISM)?;
        let cofre = Cofre::new(key);

        if crate::crypto::validar_canario(&cofre, &token_canario) {
            self.cofre = Some(cofre);
            let _ = self.migrar_nomes_para_cifrado();
            Ok(true)
        } else {
            Ok(false)
        }
    }

    pub fn desbloquear_com_chave(&mut self, chave_legivel: &str) -> Result<bool, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        
        let token_canario: String = conn.query_row(
            "SELECT valor FROM metadados WHERE chave = 'canario'",
            [],
            |row| row.get(0)
        ).map_err(|_| "Nenhuma chave configurada no banco".to_string())?;

        let cofre = cofre_de_chave_recovery(chave_legivel)?;
        if crate::crypto::validar_canario(&cofre, &token_canario) {
            self.cofre = Some(cofre);
            let _ = self.migrar_nomes_para_cifrado();
            Ok(true)
        } else {
            Ok(false)
        }
    }

    pub fn migrar_nomes_para_cifrado(&self) -> Result<(), String> {
        let mut conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;
        
        let mut stmt = tx.prepare("SELECT id, nome FROM pacientes").map_err(|e| e.to_string())?;
        let rows = stmt.query_map([], |row| {
            let id: i64 = row.get(0)?;
            let nome: String = row.get(1)?;
            Ok((id, nome))
        }).map_err(|e| e.to_string())?;
        
        let mut updates = Vec::new();
        for r in rows {
            let (id, nome) = r.map_err(|e| e.to_string())?;
            // Se tentar decifrar falhar, significa que está em texto claro (legacy) e precisa ser cifrado!
            let dec_res = self.decifrar_campo(Some(&nome));
            if dec_res.is_err() {
                // É texto claro, cifra e agenda update
                let cifrado = self.cifrar_campo(Some(&nome)).ok_or("Erro ao cifrar nome na migração")?;
                updates.push((id, cifrado));
            }
        }
        drop(stmt);
        
        if !updates.is_empty() {
            // Realiza backup automático antes da migração
            let _ = self.realizar_backup(10);
            
            for (id, cifrado) in updates {
                tx.execute(
                    "UPDATE pacientes SET nome = ?1 WHERE id = ?2",
                    rusqlite::params![cifrado, id]
                ).map_err(|e| e.to_string())?;
            }
        }
        
        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    // ──────────────────────────── CRUD de Pacientes ──────────────────────────────

    fn cifrar_campo(&self, valor: Option<&str>) -> Option<String> {
        match (valor, &self.cofre) {
            (Some(v), Some(cofre)) => cofre.encriptar(v).ok(),
            (Some(v), None) => Some(v.to_string()),
            _ => None,
        }
    }

    fn decifrar_campo(&self, valor: Option<&str>) -> Result<Option<String>, String> {
        match (valor, &self.cofre) {
            (Some(v), Some(cofre)) => {
                let dec = cofre.decriptar(v)?;
                Ok(Some(dec))
            }
            (Some(v), None) => Ok(Some(v.to_string())),
            _ => Ok(None),
        }
    }

    fn para_paciente(&self, row: &rusqlite::Row) -> rusqlite::Result<Paciente> {
        let id: i64 = row.get(0)?;
        let numero_prontuario: String = row.get(1)?;
        let cpf_cifrado: Option<String> = row.get(2)?;
        let nome_cifrado: String = row.get(3)?;
        let data_exame: String = row.get(4)?;
        let idade: i32 = row.get(5)?;
        let sexo: String = row.get(6)?;
        let polipo: i32 = row.get(7)?;
        let laudo_cifrado: Option<String> = row.get(8)?;
        let indicacao_exame: String = row.get(9)?;

        let cpf = self.decifrar_campo(cpf_cifrado.as_deref())
            .map_err(|err| rusqlite::Error::FromSqlConversionFailure(2, rusqlite::types::Type::Text, Box::new(std::io::Error::new(std::io::ErrorKind::Other, err))))?;
        let resultado_histopatologico = self.decifrar_campo(laudo_cifrado.as_deref())
            .map_err(|err| rusqlite::Error::FromSqlConversionFailure(8, rusqlite::types::Type::Text, Box::new(std::io::Error::new(std::io::ErrorKind::Other, err))))?;
        
        let nome = match self.decifrar_campo(Some(&nome_cifrado)) {
            Ok(Some(dec)) => dec,
            _ => nome_cifrado,
        };

        Ok(Paciente {
            id: Some(id),
            numero_prontuario,
            cpf,
            nome,
            data_exame,
            idade,
            sexo,
            polipo,
            resultado_histopatologico,
            indicacao_exame,
            comorbidades: vec![],
            sintomas: vec![],
            historico_familiar: vec![],
            endoscopista: None,
        })
    }

    fn carregar_relacoes(&self, conn: &Connection, pacientes: &mut [Paciente]) -> Result<(), String> {
        if pacientes.is_empty() {
            return Ok(());
        }

        let mut map_pacientes: HashMap<i64, &mut Paciente> = pacientes
            .iter_mut()
            .filter_map(|p| p.id.map(|id| (id, p)))
            .collect();

        let ids: Vec<i64> = map_pacientes.keys().cloned().collect();
        let markers = ids.iter().map(|_| "?").collect::<Vec<_>>().join(",");

        // Comorbidades
        {
            let query = format!(
                "SELECT pc.paciente_id, c.nome \
                 FROM paciente_comorbidade pc \
                 JOIN comorbidades c ON c.id = pc.comorbidade_id \
                 WHERE pc.paciente_id IN ({}) \
                 ORDER BY c.nome",
                markers
            );
            let mut stmt = conn.prepare(&query).map_err(|e| e.to_string())?;
            let rows = stmt.query_map(rusqlite::params_from_iter(&ids), |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            }).map_err(|e| e.to_string())?;

            for r in rows {
                let (pid, nome) = r.map_err(|e| e.to_string())?;
                if let Some(p) = map_pacientes.get_mut(&pid) {
                    p.comorbidades.push(nome);
                }
            }
        }

        // Sintomas
        {
            let query = format!(
                "SELECT ps.paciente_id, s.nome \
                 FROM paciente_sintoma ps \
                 JOIN sintomas s ON s.id = ps.sintoma_id \
                 WHERE ps.paciente_id IN ({}) \
                 ORDER BY s.nome",
                markers
            );
            let mut stmt = conn.prepare(&query).map_err(|e| e.to_string())?;
            let rows = stmt.query_map(rusqlite::params_from_iter(&ids), |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            }).map_err(|e| e.to_string())?;

            for r in rows {
                let (pid, nome) = r.map_err(|e| e.to_string())?;
                if let Some(p) = map_pacientes.get_mut(&pid) {
                    p.sintomas.push(nome);
                }
            }
        }

        // Histórico familiar
        {
            let query = format!(
                "SELECT id, paciente_id, parentesco, grau, idade_diagnostico \
                 FROM historico_familiar \
                 WHERE paciente_id IN ({}) \
                 ORDER BY grau, idade_diagnostico IS NULL, idade_diagnostico",
                markers
            );
            let mut stmt = conn.prepare(&query).map_err(|e| e.to_string())?;
            let rows = stmt.query_map(rusqlite::params_from_iter(&ids), |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, i64>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, i32>(3)?,
                    row.get::<_, Option<i32>>(4)?,
                ))
            }).map_err(|e| e.to_string())?;

            for r in rows {
                let (id, pid, parentesco, grau, idade) = r.map_err(|e| e.to_string())?;
                if let Some(p) = map_pacientes.get_mut(&pid) {
                    p.historico_familiar.push(HistoricoFamiliar {
                        id: Some(id),
                        parentesco,
                        grau,
                        idade_diagnostico: idade,
                    });
                }
            }
        }

        // Endoscopista
        {
            let query = format!(
                "SELECT entidade_id, usuario \
                 FROM auditoria \
                 WHERE entidade = 'paciente' AND acao = 'cadastrar' AND entidade_id IN ({})",
                markers
            );
            let mut stmt = conn.prepare(&query).map_err(|e| e.to_string())?;
            let rows = stmt.query_map(rusqlite::params_from_iter(&ids), |row| {
                Ok((row.get::<_, i64>(0)?, row.get::<_, String>(1)?))
            }).map_err(|e| e.to_string())?;

            let mut endo_map = HashMap::new();
            for r in rows {
                let (pid, user) = r.map_err(|e| e.to_string())?;
                endo_map.insert(pid, user);
            }

            for p in pacientes.iter_mut() {
                if let Some(pid) = p.id {
                    let user = endo_map.get(&pid).cloned().unwrap_or_else(|| "Dr. Sistema".to_string());
                    p.endoscopista = Some(user);
                }
            }
        }

        Ok(())
    }

    fn inserir_relacoes(&self, conn: &Connection, paciente_id: i64, p: &Paciente) -> Result<(), String> {
        for c in &p.comorbidades {
            let _ = conn.execute(
                "INSERT OR IGNORE INTO comorbidades (nome) VALUES (?1)",
                [c],
            );
            let comorbidade_id: i64 = conn.query_row(
                "SELECT id FROM comorbidades WHERE nome = ?1",
                [c],
                |row| row.get(0),
            ).map_err(|e| e.to_string())?;

            conn.execute(
                "INSERT OR IGNORE INTO paciente_comorbidade (paciente_id, comorbidade_id) VALUES (?1, ?2)",
                params![paciente_id, comorbidade_id],
            ).map_err(|e| e.to_string())?;
        }

        for s in &p.sintomas {
            let _ = conn.execute(
                "INSERT OR IGNORE INTO sintomas (nome) VALUES (?1)",
                [s],
            );
            let sintoma_id: i64 = conn.query_row(
                "SELECT id FROM sintomas WHERE nome = ?1",
                [s],
                |row| row.get(0),
            ).map_err(|e| e.to_string())?;

            conn.execute(
                "INSERT OR IGNORE INTO paciente_sintoma (paciente_id, sintoma_id) VALUES (?1, ?2)",
                params![paciente_id, sintoma_id],
            ).map_err(|e| e.to_string())?;
        }

        for h in &p.historico_familiar {
            conn.execute(
                "INSERT INTO historico_familiar (paciente_id, parentesco, grau, idade_diagnostico) \
                 VALUES (?1, ?2, ?3, ?4)",
                params![paciente_id, h.parentesco, h.grau, h.idade_diagnostico],
            ).map_err(|e| e.to_string())?;
        }

        Ok(())
    }

    pub fn listar(&self) -> Result<Vec<Paciente>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame FROM pacientes")
            .map_err(|e| e.to_string())?;

        let rows = stmt.query_map([], |row| {
            self.para_paciente(row)
        }).map_err(|e| e.to_string())?;

        let mut pacientes = Vec::new();
        for p in rows {
            let p_unwrapped = p.map_err(|e| e.to_string())?;
            pacientes.push(p_unwrapped);
        }

        self.carregar_relacoes(&conn, &mut pacientes)?;
        
        // Ordena em memória de forma insensível a maiúsculas/minúsculas
        pacientes.sort_by(|a, b| a.nome.to_lowercase().cmp(&b.nome.to_lowercase()));
        
        Ok(pacientes)
    }

    pub fn cadastrar(&self, usuario: &str, paciente: &Paciente) -> Result<i64, String> {
        let mut conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;

        let cpf_cifrado = self.cifrar_campo(paciente.cpf.as_deref());
        let laudo_cifrado = self.cifrar_campo(paciente.resultado_histopatologico.as_deref());
        let nome_cifrado = self.cifrar_campo(Some(&paciente.nome)).unwrap_or_else(|| paciente.nome.clone());

        tx.execute(
            "INSERT INTO pacientes (numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                paciente.numero_prontuario,
                cpf_cifrado,
                nome_cifrado,
                paciente.data_exame,
                paciente.idade,
                paciente.sexo,
                paciente.polipo,
                laudo_cifrado,
                paciente.indicacao_exame
            ],
        ).map_err(|e| e.to_string())?;

        let novo_id = tx.last_insert_rowid();
        self.inserir_relacoes(&tx, novo_id, paciente)?;

        let mut p_snap = paciente.clone();
        p_snap.id = Some(novo_id);

        self.auditar(&tx, usuario, "cadastrar", "paciente", Some(novo_id), None, Some(&p_snap))?;

        tx.commit().map_err(|e| e.to_string())?;
        Ok(novo_id)
    }

    pub fn buscar(&self, id_paciente: i64) -> Result<Option<Paciente>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame FROM pacientes WHERE id = ?1")
            .map_err(|e| e.to_string())?;

        let res = stmt.query_row([id_paciente], |row| {
            self.para_paciente(row)
        });

        match res {
            Ok(mut p) => {
                self.carregar_relacoes(&conn, std::slice::from_mut(&mut p))?;
                Ok(Some(p))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.to_string()),
        }
    }

    pub fn buscar_por_prontuario(&self, prontuario: &str) -> Result<Option<Paciente>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame FROM pacientes WHERE numero_prontuario = ?1")
            .map_err(|e| e.to_string())?;

        let res = stmt.query_row([prontuario.trim()], |row| {
            self.para_paciente(row)
        });

        match res {
            Ok(mut p) => {
                self.carregar_relacoes(&conn, std::slice::from_mut(&mut p))?;
                Ok(Some(p))
            }
            Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
            Err(e) => Err(e.to_string()),
        }
    }

    pub fn buscar_por_termo(&self, parcial: &str) -> Result<Vec<Paciente>, String> {
        let todos = self.listar()?;
        let parcial_lower = parcial.to_lowercase();
        
        let filtrados: Vec<Paciente> = todos
            .into_iter()
            .filter(|p| {
                p.nome.to_lowercase().contains(&parcial_lower)
                    || p.numero_prontuario.to_lowercase().contains(&parcial_lower)
            })
            .collect();
            
        Ok(filtrados)
    }

    pub fn editar(&self, usuario: &str, paciente: &Paciente) -> Result<(), String> {
        let id = paciente.id.ok_or_else(|| "Não é possível editar paciente sem id".to_string())?;
        
        let mut conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;

        let antes = {
            let mut stmt = tx.prepare("SELECT id, numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame FROM pacientes WHERE id = ?1")
                .map_err(|e| e.to_string())?;
            let mut p = stmt.query_row([id], |row| {
                self.para_paciente(row)
            }).map_err(|e| format!("Paciente id={} não encontrado para edição: {}", id, e))?;
            self.carregar_relacoes(&tx, std::slice::from_mut(&mut p))?;
            p
        };

        let cpf_cifrado = self.cifrar_campo(paciente.cpf.as_deref());
        let laudo_cifrado = self.cifrar_campo(paciente.resultado_histopatologico.as_deref());
        let nome_cifrado = self.cifrar_campo(Some(&paciente.nome)).unwrap_or_else(|| paciente.nome.clone());

        tx.execute(
            "UPDATE pacientes SET numero_prontuario=?1, cpf=?2, nome=?3, data_exame=?4, idade=?5, sexo=?6, polipo=?7, resultado_histopatologico=?8, indicacao_exame=?9 WHERE id=?10",
            params![
                paciente.numero_prontuario,
                cpf_cifrado,
                nome_cifrado,
                paciente.data_exame,
                paciente.idade,
                paciente.sexo,
                paciente.polipo,
                laudo_cifrado,
                paciente.indicacao_exame,
                id
            ],
        ).map_err(|e| e.to_string())?;

        tx.execute("DELETE FROM paciente_comorbidade WHERE paciente_id = ?1", [id]).map_err(|e| e.to_string())?;
        tx.execute("DELETE FROM paciente_sintoma WHERE paciente_id = ?1", [id]).map_err(|e| e.to_string())?;
        tx.execute("DELETE FROM historico_familiar WHERE paciente_id = ?1", [id]).map_err(|e| e.to_string())?;

        self.inserir_relacoes(&tx, id, paciente)?;

        self.auditar(&tx, usuario, "editar", "paciente", Some(id), Some(&antes), Some(paciente))?;

        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn excluir(&self, usuario: &str, id_paciente: i64) -> Result<(), String> {
        let mut conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;

        let antes = {
            let mut stmt = tx.prepare("SELECT id, numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame FROM pacientes WHERE id = ?1")
                .map_err(|e| e.to_string())?;
            let res = stmt.query_row([id_paciente], |row| {
                self.para_paciente(row)
            });
            match res {
                Ok(mut p) => {
                    self.carregar_relacoes(&tx, std::slice::from_mut(&mut p))?;
                    Some(p)
                }
                Err(rusqlite::Error::QueryReturnedNoRows) => None,
                Err(e) => return Err(e.to_string()),
            }
        };

        tx.execute("DELETE FROM pacientes WHERE id = ?1", [id_paciente]).map_err(|e| e.to_string())?;

        if let Some(a) = antes {
            self.auditar(&tx, usuario, "excluir", "paciente", Some(id_paciente), Some(&a), None)?;
        }

        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    // ──────────────────────────── Métodos do Catálogo ────────────────────────────

    pub fn listar_comorbidades_catalogo(&self) -> Result<Vec<String>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn.prepare("SELECT nome FROM comorbidades ORDER BY nome").map_err(|e| e.to_string())?;
        let rows = stmt.query_map([], |row| row.get(0)).map_err(|e| e.to_string())?;
        let mut list = Vec::new();
        for r in rows {
            list.push(r.map_err(|e| e.to_string())?);
        }
        Ok(list)
    }

    pub fn adicionar_comorbidade_catalogo(&self, usuario: &str, nome: &str) -> Result<(), String> {
        let mut conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;

        let affected = tx.execute("INSERT OR IGNORE INTO comorbidades (nome) VALUES (?1)", [nome]).map_err(|e| e.to_string())?;
        if affected > 0 {
            let row_id: i64 = tx.query_row(
                "SELECT id FROM comorbidades WHERE nome = ?1",
                [nome],
                |row| row.get(0)
            ).map_err(|e| e.to_string())?;

            #[derive(Serialize)]
            struct Snap { nome: String }
            let snap = Snap { nome: nome.to_string() };
            let snap_str = serde_json::to_string(&snap).unwrap();
            let snap_cifrado = self.cifrar_campo(Some(&snap_str));

            // Auditoria para comorbidade
            let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
            let prev_hash: String = tx.query_row(
                "SELECT hash_atual FROM auditoria ORDER BY id DESC LIMIT 1",
                [],
                |row| row.get(0)
            ).unwrap_or_else(|_| "0".repeat(64));

            let hash_atual = self.calcular_hash_ou_hmac_auditoria(
                &prev_hash,
                &timestamp,
                usuario,
                "cadastrar",
                "comorbidade_catalogo",
                Some(row_id),
                None,
                snap_cifrado.as_deref(),
            );

            tx.execute(
                "INSERT INTO auditoria (timestamp, usuario, acao, entidade, entidade_id, snapshot_depois, hash_atual) \
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                params![
                    timestamp,
                    usuario,
                    "cadastrar",
                    "comorbidade_catalogo",
                    row_id,
                    snap_cifrado,
                    hash_atual
                ]
            ).map_err(|e| e.to_string())?;
        }

        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn listar_sintomas_catalogo(&self) -> Result<Vec<String>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn.prepare("SELECT nome FROM sintomas ORDER BY nome").map_err(|e| e.to_string())?;
        let rows = stmt.query_map([], |row| row.get(0)).map_err(|e| e.to_string())?;
        let mut list = Vec::new();
        for r in rows {
            list.push(r.map_err(|e| e.to_string())?);
        }
        Ok(list)
    }

    pub fn adicionar_sintoma_catalogo(&self, usuario: &str, nome: &str) -> Result<(), String> {
        let mut conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let tx = conn.transaction().map_err(|e| e.to_string())?;

        let affected = tx.execute("INSERT OR IGNORE INTO sintomas (nome) VALUES (?1)", [nome]).map_err(|e| e.to_string())?;
        if affected > 0 {
            let row_id: i64 = tx.query_row(
                "SELECT id FROM sintomas WHERE nome = ?1",
                [nome],
                |row| row.get(0)
            ).map_err(|e| e.to_string())?;

            #[derive(Serialize)]
            struct Snap { nome: String }
            let snap = Snap { nome: nome.to_string() };
            let snap_str = serde_json::to_string(&snap).unwrap();
            let snap_cifrado = self.cifrar_campo(Some(&snap_str));

            // Auditoria para sintoma
            let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
            let prev_hash: String = tx.query_row(
                "SELECT hash_atual FROM auditoria ORDER BY id DESC LIMIT 1",
                [],
                |row| row.get(0)
            ).unwrap_or_else(|_| "0".repeat(64));

            let hash_atual = self.calcular_hash_ou_hmac_auditoria(
                &prev_hash,
                &timestamp,
                usuario,
                "cadastrar",
                "sintoma_catalogo",
                Some(row_id),
                None,
                snap_cifrado.as_deref(),
            );

            tx.execute(
                "INSERT INTO auditoria (timestamp, usuario, acao, entidade, entidade_id, snapshot_depois, hash_atual) \
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                params![
                    timestamp,
                    usuario,
                    "cadastrar",
                    "sintoma_catalogo",
                    row_id,
                    snap_cifrado,
                    hash_atual
                ]
            ).map_err(|e| e.to_string())?;
        }

        tx.commit().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn listar_auditoria(&self, limite: usize) -> Result<Vec<EntradaAuditoria>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, timestamp, usuario, acao, entidade, entidade_id, snapshot_antes, snapshot_depois, hash_atual \
                      FROM auditoria ORDER BY id DESC LIMIT ?1")
            .map_err(|e| e.to_string())?;

        let rows = stmt.query_map([limite], |row| {
            let snap_antes_raw: Option<String> = row.get(6)?;
            let snap_depois_raw: Option<String> = row.get(7)?;

            let snapshot_antes = self.decifrar_campo(snap_antes_raw.as_deref())
                .map_err(|err| rusqlite::Error::FromSqlConversionFailure(6, rusqlite::types::Type::Text, Box::new(std::io::Error::new(std::io::ErrorKind::Other, err))))?;
            let snapshot_depois = self.decifrar_campo(snap_depois_raw.as_deref())
                .map_err(|err| rusqlite::Error::FromSqlConversionFailure(7, rusqlite::types::Type::Text, Box::new(std::io::Error::new(std::io::ErrorKind::Other, err))))?;

            Ok(EntradaAuditoria {
                id: Some(row.get(0)?),
                timestamp: row.get(1)?,
                usuario: row.get(2)?,
                acao: row.get(3)?,
                entidade: row.get(4)?,
                entidade_id: row.get(5)?,
                snapshot_antes,
                snapshot_depois,
                hash_atual: row.get(8)?,
            })
        }).map_err(|e| e.to_string())?;

        let mut list = Vec::new();
        for r in rows {
            list.push(r.map_err(|e| e.to_string())?);
        }
        Ok(list)
    }

    fn calcular_hash_ou_hmac_auditoria(
        &self,
        hash_anterior: &str,
        timestamp: &str,
        usuario: &str,
        acao: &str,
        entidade: &str,
        entidade_id: Option<i64>,
        snapshot_antes: Option<&str>,
        snapshot_depois: Option<&str>,
    ) -> String {
        match &self.cofre {
            Some(cofre) => crate::crypto::calcular_hmac_auditoria(
                cofre.key(),
                hash_anterior,
                timestamp,
                usuario,
                acao,
                entidade,
                entidade_id,
                snapshot_antes,
                snapshot_depois,
            ),
            None => crate::crypto::calcular_hash_auditoria(
                hash_anterior,
                timestamp,
                usuario,
                acao,
                entidade,
                entidade_id,
                snapshot_antes,
                snapshot_depois,
            ),
        }
    }

    // ──────────────────────────── Métodos de Auditoria Interna ───────────────────

    fn auditar(
        &self,
        conn: &Connection,
        usuario: &str,
        acao: &str,
        entidade: &str,
        entidade_id: Option<i64>,
        antes: Option<&Paciente>,
        depois: Option<&Paciente>,
    ) -> Result<(), String> {
        let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);

        let antes_seguro = antes.map(|p| self.sanitizar_paciente_snapshot(p));
        let depois_seguro = depois.map(|p| self.sanitizar_paciente_snapshot(p));

        let snap_antes = antes_seguro
            .map(|s| serde_json::to_string(&s).unwrap())
            .map(|json| self.cifrar_campo(Some(&json)).unwrap());

        let snap_depois = depois_seguro
            .map(|s| serde_json::to_string(&s).unwrap())
            .map(|json| self.cifrar_campo(Some(&json)).unwrap());

        let prev_hash: String = conn.query_row(
            "SELECT hash_atual FROM auditoria ORDER BY id DESC LIMIT 1",
            [],
            |row| row.get(0)
        ).unwrap_or_else(|_| "0".repeat(64));

        let hash_atual = self.calcular_hash_ou_hmac_auditoria(
            &prev_hash,
            &timestamp,
            usuario,
            acao,
            entidade,
            entidade_id,
            snap_antes.as_deref(),
            snap_depois.as_deref(),
        );

        conn.execute(
            "INSERT INTO auditoria (timestamp, usuario, acao, entidade, entidade_id, snapshot_antes, snapshot_depois, hash_atual) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            params![
                timestamp,
                usuario,
                acao,
                entidade,
                entidade_id,
                snap_antes,
                snap_depois,
                hash_atual
            ],
        ).map_err(|e| e.to_string())?;

        Ok(())
    }

    pub fn sanitizar_paciente_snapshot(&self, p: &Paciente) -> serde_json::Value {
        let hash_integridade = self.calcular_hash_integridade_paciente(p, true, true);

        let mut historico: Vec<(String, Option<i32>)> = p.historico_familiar
            .iter()
            .map(|h| (h.parentesco.clone(), h.idade_diagnostico))
            .collect();
        historico.sort_by(|a, b| {
            let parentesco_cmp = a.0.cmp(&b.0);
            if parentesco_cmp == std::cmp::Ordering::Equal {
                a.1.cmp(&b.1)
            } else {
                parentesco_cmp
            }
        });

        let mut comorbidades = p.comorbidades.clone();
        comorbidades.sort();

        let mut sintomas = p.sintomas.clone();
        sintomas.sort();

        let masked_cpf = p.cpf.as_ref().map(|c| {
            if c.len() == 11 && c.chars().all(|ch| ch.is_ascii_digit()) {
                format!("***.***.***-{}", &c[9..])
            } else {
                c.clone()
            }
        });

        serde_json::json!({
            "id": p.id,
            "numero_prontuario": p.numero_prontuario,
            "cpf": masked_cpf,
            "nome": p.nome,
            "data_exame": p.data_exame,
            "idade": p.idade,
            "sexo": p.sexo,
            "polipo": p.polipo,
            "resultado_histopatologico": p.resultado_histopatologico,
            "indicacao_exame": p.indicacao_exame,
            "comorbidades": comorbidades,
            "sintomas": sintomas,
            "historico_familiar": historico,
            "_integridade_hash": hash_integridade,
        })
    }

    pub fn calcular_hash_integridade_paciente(
        &self,
        p: &Paciente,
        incluir_indicacao: bool,
        incluir_sintomas: bool,
    ) -> String {
        use sha2::{Sha256, Digest};
        let mut historico: Vec<(String, Option<i32>)> = p.historico_familiar
            .iter()
            .map(|h| (h.parentesco.clone(), h.idade_diagnostico))
            .collect();
        historico.sort_by(|a, b| {
            let parentesco_cmp = a.0.cmp(&b.0);
            if parentesco_cmp == std::cmp::Ordering::Equal {
                a.1.cmp(&b.1)
            } else {
                parentesco_cmp
            }
        });

        let mut comorbidades = p.comorbidades.clone();
        comorbidades.sort();

        let mut sintomas = p.sintomas.clone();
        sintomas.sort();

        #[derive(Serialize)]
        struct Normalizado {
            numero_prontuario: String,
            cpf: Option<String>,
            nome: String,
            data_exame: String,
            idade: i32,
            sexo: String,
            polipo: i32,
            resultado_histopatologico: Option<String>,
            comorbidades: Vec<String>,
            historico_familiar: Vec<(String, Option<i32>)>,
            #[serde(skip_serializing_if = "Option::is_none")]
            indicacao_exame: Option<String>,
            #[serde(skip_serializing_if = "Option::is_none")]
            sintomas: Option<Vec<String>>,
        }

        let norm = Normalizado {
            numero_prontuario: p.numero_prontuario.clone(),
            cpf: p.cpf.clone(),
            nome: p.nome.clone(),
            data_exame: p.data_exame.clone(),
            idade: p.idade,
            sexo: p.sexo.clone(),
            polipo: p.polipo,
            resultado_histopatologico: p.resultado_histopatologico.clone(),
            comorbidades,
            historico_familiar: historico,
            indicacao_exame: if incluir_indicacao { Some(p.indicacao_exame.clone()) } else { None },
            sintomas: if incluir_sintomas { Some(sintomas) } else { None },
        };

        let payload = serde_json::to_string(&norm).unwrap();
        let mut hasher = Sha256::new();
        hasher.update(payload.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    fn decifrar_snapshot(&self, snapshot_str: Option<&str>) -> Result<Option<String>, String> {
        match (snapshot_str, &self.cofre) {
            (Some(s), Some(cofre)) => {
                let dec = cofre.decriptar(s)?;
                Ok(Some(dec))
            }
            (Some(s), None) => Ok(Some(s.to_string())),
            _ => Ok(None),
        }
    }

    // ──────────────────────────── Métodos de Verificação de Integridade ───────────

    pub fn verificar_integridade(&self) -> Result<Vec<InconsistenciaAuditoria>, String> {
        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        let mut stmt = conn
            .prepare("SELECT id, timestamp, usuario, acao, entidade, entidade_id, snapshot_antes, snapshot_depois, hash_atual FROM auditoria ORDER BY id")
            .map_err(|e| e.to_string())?;

        let rows = stmt.query_map([], |row| {
            Ok(EntradaAuditoria {
                id: Some(row.get(0)?),
                timestamp: row.get(1)?,
                usuario: row.get(2)?,
                acao: row.get(3)?,
                entidade: row.get(4)?,
                entidade_id: row.get(5)?,
                snapshot_antes: row.get(6)?,
                snapshot_depois: row.get(7)?,
                hash_atual: row.get(8)?,
            })
        }).map_err(|e| e.to_string())?;

        let mut prev_hash = "0".repeat(64);
        let mut inconsistencias = Vec::new();

        for row_res in rows {
            let entry = row_res.map_err(|e| e.to_string())?;
            let entry_id = entry.id.unwrap_or(0);
            let expected = if entry.hash_atual.starts_with("v2:") {
                match &self.cofre {
                    Some(cofre) => crate::crypto::calcular_hmac_auditoria(
                        cofre.key(),
                        &prev_hash,
                        &entry.timestamp,
                        &entry.usuario,
                        &entry.acao,
                        &entry.entidade,
                        entry.entidade_id,
                        entry.snapshot_antes.as_deref(),
                        entry.snapshot_depois.as_deref(),
                    ),
                    None => {
                        return Err("Cofre bloqueado: chave indisponível para verificar a cadeia HMAC".to_string());
                    }
                }
            } else {
                crate::crypto::calcular_hash_auditoria(
                    &prev_hash,
                    &entry.timestamp,
                    &entry.usuario,
                    &entry.acao,
                    &entry.entidade,
                    entry.entidade_id,
                    entry.snapshot_antes.as_deref(),
                    entry.snapshot_depois.as_deref(),
                )
            };

            if expected != entry.hash_atual {
                inconsistencias.push(InconsistenciaAuditoria {
                    id_entrada: entry_id,
                    motivo: format!("Hash-chain quebrado na entrada {}", entry_id),
                    hash_esperado: expected,
                    hash_encontrado: entry.hash_atual,
                });
                break;
            }
            prev_hash = entry.hash_atual;
        }

        Ok(inconsistencias)
    }

    pub fn verificar_integridade_dados(&self) -> Result<Vec<InconsistenciaDados>, String> {
        if self.tem_senha_configurada()? && !self.esta_desbloqueado() {
            return Err("Desbloqueie o cofre para verificar integridade dos pacientes".to_string());
        }

        let conn = obter_conexao(&self.caminho).map_err(|e| e.to_string())?;
        
        let mut stmt = conn
            .prepare("SELECT id, acao, entidade_id, snapshot_antes, snapshot_depois FROM auditoria WHERE LOWER(entidade) = 'paciente' ORDER BY id")
            .map_err(|e| e.to_string())?;

        let rows = stmt.query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, Option<i64>>(2)?,
                row.get::<_, Option<String>>(3)?,
                row.get::<_, Option<String>>(4)?,
            ))
        }).map_err(|e| e.to_string())?;

        let mut problemas = Vec::new();
        let mut ultimo_por_id: HashMap<i64, (String, Option<String>, i64)> = HashMap::new();

        for r_res in rows {
            let (aid, acao, entidade_id, snap_antes, snap_depois) = r_res.map_err(|e| e.to_string())?;
            if entidade_id.is_none() {
                problemas.push(InconsistenciaDados {
                    entidade: "paciente".to_string(),
                    entidade_id: None,
                    motivo: format!("auditoria #{} sem id de paciente", aid),
                    campos: vec![],
                });
                continue;
            }
            let pid = entidade_id.unwrap();
            let acao_norm = acao.to_lowercase();
            let snapshot = if acao_norm == "excluir" { snap_antes } else { snap_depois };
            ultimo_por_id.insert(pid, (acao_norm, snapshot, aid));
        }

        let pacientes_atuais = self.listar()?;
        let pacientes_map: HashMap<i64, &Paciente> = pacientes_atuais
            .iter()
            .filter_map(|p| p.id.map(|id| (id, p)))
            .collect();

        for &pid in pacientes_map.keys() {
            if !ultimo_por_id.contains_key(&pid) {
                problemas.push(InconsistenciaDados {
                    entidade: "paciente".to_string(),
                    entidade_id: Some(pid),
                    motivo: "paciente presente sem evento de auditoria".to_string(),
                    campos: vec![],
                });
            }
        }

        let mut sorted_keys: Vec<i64> = ultimo_por_id.keys().cloned().collect();
        sorted_keys.sort();

        for pid in sorted_keys {
            let (acao, snapshot_str, aid) = ultimo_por_id.get(&pid).unwrap();
            let atual = pacientes_map.get(&pid);

            if acao == "excluir" {
                if atual.is_some() {
                    problemas.push(InconsistenciaDados {
                        entidade: "paciente".to_string(),
                        entidade_id: Some(pid),
                        motivo: format!("paciente presente apesar de exclusão auditada na entrada #{}", aid),
                        campos: vec![],
                    });
                }
                continue;
            }

            if atual.is_none() {
                problemas.push(InconsistenciaDados {
                    entidade: "paciente".to_string(),
                    entidade_id: Some(pid),
                    motivo: format!("paciente ausente apesar de último evento #{} ser {}", aid, acao),
                    campos: vec![],
                });
                continue;
            }
            let atual_paciente = *atual.unwrap();

            let snap_decifrado = match self.decifrar_snapshot(snapshot_str.as_deref()) {
                Ok(Some(s)) => s,
                _ => {
                    problemas.push(InconsistenciaDados {
                        entidade: "paciente".to_string(),
                        entidade_id: Some(pid),
                        motivo: format!("snapshot de auditoria #{} ilegível", aid),
                        campos: vec![],
                    });
                    continue;
                }
            };

            let snap_obj: serde_json::Value = match serde_json::from_str(&snap_decifrado) {
                Ok(v) => v,
                Err(_) => {
                    problemas.push(InconsistenciaDados {
                        entidade: "paciente".to_string(),
                        entidade_id: Some(pid),
                        motivo: format!("snapshot de auditoria #{} ilegível", aid),
                        campos: vec![],
                    });
                    continue;
                }
            };

            let hash_esperado = snap_obj.get("_integridade_hash").and_then(|v| v.as_str());

            let incluir_indicacao = snap_obj.get("indicacao_exame").is_some();
            let incluir_sintomas = snap_obj.get("sintomas").is_some();

            if let Some(h_esp) = hash_esperado {
                let hash_atual = self.calcular_hash_integridade_paciente(atual_paciente, incluir_indicacao, incluir_sintomas);
                if hash_atual != h_esp {
                    problemas.push(InconsistenciaDados {
                        entidade: "paciente".to_string(),
                        entidade_id: Some(pid),
                        motivo: format!("estado atual diverge do hash auditado na entrada #{}", aid),
                        campos: vec![],
                    });
                }
            }
        }

        Ok(problemas)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn temp_db_path(name: &str) -> String {
        let dir = std::env::temp_dir();
        let path = dir.join(name);
        if path.exists() {
            let _ = fs::remove_file(&path);
        }
        path.to_str().unwrap().to_string()
    }

    #[test]
    fn test_banco_criar_e_triggers() {
        let path = temp_db_path("gastroepi_test_triggers.db");
        let db = BancoDados::new(&path);
        db.criar().unwrap();
        
        // Verifica que o banco foi criado
        assert!(Path::new(&path).exists());

        let conn = obter_conexao(&path).unwrap();
        conn.execute(
            "INSERT INTO auditoria (timestamp, usuario, acao, entidade, hash_atual) \
             VALUES ('2026-06-03T01:36:35Z', 'test_user', 'cadastrar', 'paciente', 'dummy')",
            [],
        ).unwrap();

        // UPDATE deve falhar devido à trigger
        let update_res = conn.execute(
            "UPDATE auditoria SET acao = 'deletar' WHERE id = 1",
            [],
        );
        assert!(update_res.is_err());
        assert!(update_res.err().unwrap().to_string().contains("auditoria é append-only: UPDATE proibido"));

        // DELETE deve falhar devido à trigger
        let delete_res = conn.execute(
            "DELETE FROM auditoria WHERE id = 1",
            [],
        );
        assert!(delete_res.is_err());
        assert!(delete_res.err().unwrap().to_string().contains("auditoria é append-only: DELETE proibido"));

        let _ = fs::remove_file(&path);
    }

    #[test]
    fn test_fluxo_autenticacao_e_crud() {
        let path = temp_db_path("gastroepi_test_crud.db");
        let mut db = BancoDados::new(&path);
        db.criar().unwrap();

        // Pré-configuração
        assert!(!db.tem_senha_configurada().unwrap());

        // Configura senha
        let recovery_key = db.configurar_senha("senha12345").unwrap();
        assert!(recovery_key.len() > 0);
        assert!(db.tem_senha_configurada().unwrap());
        assert!(db.esta_desbloqueado());

        // Cadastra um paciente
        let p = Paciente {
            id: None,
            numero_prontuario: "10001".to_string(),
            cpf: Some("12345678909".to_string()),
            nome: "Maria Sousa".to_string(),
            data_exame: "2026-06-03".to_string(),
            idade: 55,
            sexo: "F".to_string(),
            polipo: 2,
            resultado_histopatologico: Some("Adenoma tubular".to_string()),
            indicacao_exame: "Rastreio".to_string(),
            comorbidades: vec!["Obesidade".to_string()],
            sintomas: vec![],
            historico_familiar: vec![HistoricoFamiliar {
                id: None,
                parentesco: "pai".to_string(),
                grau: 1,
                idade_diagnostico: Some(60),
            }],
            endoscopista: None,
        };

        let pid = db.cadastrar("mateus", &p).unwrap();
        assert!(pid > 0);

        // Busca o paciente
        let p_busca = db.buscar(pid).unwrap().unwrap();
        assert_eq!(p_busca.nome, "Maria Sousa");
        assert_eq!(p_busca.cpf, Some("12345678909".to_string()));
        assert_eq!(p_busca.resultado_histopatologico, Some("Adenoma tubular".to_string()));
        assert_eq!(p_busca.comorbidades, vec!["Obesidade".to_string()]);
        assert_eq!(p_busca.historico_familiar[0].parentesco, "pai");

        // Bloqueia / Desbloqueia com senha
        db.cofre = None; // Simula bloqueio
        assert!(!db.esta_desbloqueado());

        let res_desbloqueio = db.desbloquear("senha_errada").unwrap();
        assert!(!res_desbloqueio);

        let res_desbloqueio_certa = db.desbloquear("senha12345").unwrap();
        assert!(res_desbloqueio_certa);

        // Desbloqueia com recovery key
        db.cofre = None;
        let res_recovery = db.desbloquear_com_chave(&recovery_key).unwrap();
        assert!(res_recovery);

        // Verifica integridade da auditoria
        let audit_inc = db.verificar_integridade().unwrap();
        assert!(audit_inc.is_empty());

        // Verifica integridade dos dados
        let dados_inc = db.verificar_integridade_dados().unwrap();
        assert!(dados_inc.is_empty());

        let _ = fs::remove_file(&path);
    }

    #[test]
    fn test_hmac_audit_verification_flow() {
        let path = temp_db_path("gastroepi_test_hmac.db");
        let mut db = BancoDados::new(&path);
        db.criar().unwrap();
        
        // 1. Sem senha configurada: cadastrar comorbidade grava com SHA-256
        db.adicionar_comorbidade_catalogo("mateus", "Comorbidade Legacy").unwrap();
        
        let conn = obter_conexao(&path).unwrap();
        let hash_legacy: String = conn.query_row(
            "SELECT hash_atual FROM auditoria ORDER BY id DESC LIMIT 1",
            [],
            |row| row.get(0)
        ).unwrap();
        assert!(!hash_legacy.starts_with("v2:"));
        
        // Integridade passa
        assert!(db.verificar_integridade().unwrap().is_empty());
        
        // 2. Configura senha: novas inserções devem ter prefixo v2:
        db.configurar_senha("senha12345").unwrap();
        db.adicionar_comorbidade_catalogo("mateus", "Comorbidade HMAC").unwrap();
        
        let hash_hmac: String = conn.query_row(
            "SELECT hash_atual FROM auditoria ORDER BY id DESC LIMIT 1",
            [],
            |row| row.get(0)
        ).unwrap();
        assert!(hash_hmac.starts_with("v2:"));
        
        // Integridade passa com o banco desbloqueado
        assert!(db.verificar_integridade().unwrap().is_empty());
        
        // 3. Bloqueia cofre: verificar_integridade deve falhar com erro de cofre bloqueado
        db.cofre = None;
        let verify_res = db.verificar_integridade();
        assert!(verify_res.is_err());
        assert!(verify_res.err().unwrap().contains("Cofre bloqueado"));
        
        // Desbloqueia novamente
        db.desbloquear("senha12345").unwrap();
        assert!(db.verificar_integridade().unwrap().is_empty());
        
        let _ = fs::remove_file(&path);
    }

    #[test]
    fn test_cifragem_nome_e_migracao() {
        let path = temp_db_path("gastroepi_test_nome_cifragem.db");
        let mut db = BancoDados::new(&path);
        db.criar().unwrap();
        
        // 1. Cria paciente quando o banco está bloqueado/sem senha (nome fica em texto claro)
        let conn = obter_conexao(&path).unwrap();
        conn.execute(
            "INSERT INTO pacientes (numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame) \
             VALUES ('111', NULL, 'João Silva', '2026-06-03', 45, 'M', 0, NULL, 'Rastreio')",
            []
        ).unwrap();
        
        // Verifica que o nome está gravado como "João Silva" (em claro)
        let nome_no_db: String = conn.query_row(
            "SELECT nome FROM pacientes WHERE numero_prontuario = '111'",
            [],
            |row| row.get(0)
        ).unwrap();
        assert_eq!(nome_no_db, "João Silva");
        
        // 2. Configura senha, o que inicializa o cofre.
        db.configurar_senha("senha12345").unwrap();
        
        // A migração deve rodar
        db.migrar_nomes_para_cifrado().unwrap();
        
        // Verifica que o nome no banco de dados agora está cifrado (não é mais "João Silva")
        let nome_cifrado_no_db: String = conn.query_row(
            "SELECT nome FROM pacientes WHERE numero_prontuario = '111'",
            [],
            |row| row.get(0)
        ).unwrap();
        assert_ne!(nome_cifrado_no_db, "João Silva");
        
        // 3. Lê o paciente e verifica se ele é decifrado com sucesso
        let p = db.buscar(1).unwrap().unwrap();
        assert_eq!(p.nome, "João Silva");
        
        // 4. Cadastra um novo paciente com cofre desbloqueado e garante que é cifrado na hora
        let p_novo = Paciente {
            id: None,
            numero_prontuario: "222".to_string(),
            cpf: None,
            nome: "Maria Oliveira".to_string(),
            data_exame: "2026-06-03".to_string(),
            idade: 50,
            sexo: "F".to_string(),
            polipo: 1,
            resultado_histopatologico: None,
            indicacao_exame: "Rastreio".to_string(),
            comorbidades: vec![],
            sintomas: vec![],
            historico_familiar: vec![],
            endoscopista: None,
        };
        let pid_novo = db.cadastrar("mateus", &p_novo).unwrap();
        
        let nome_novo_no_db: String = conn.query_row(
            "SELECT nome FROM pacientes WHERE id = ?1",
            [pid_novo],
            |row| row.get(0)
        ).unwrap();
        assert_ne!(nome_novo_no_db, "Maria Oliveira");
        
        // 5. Verifica buscar_por_termo
        let resultados = db.buscar_por_termo("oliveira").unwrap();
        assert_eq!(resultados.len(), 1);
        assert_eq!(resultados[0].nome, "Maria Oliveira");
        
        let resultados_all = db.buscar_por_termo("joão").unwrap();
        assert_eq!(resultados_all.len(), 1);
        assert_eq!(resultados_all[0].nome, "João Silva");
        
        let _ = fs::remove_file(&path);
    }

    #[test]
    fn test_sqlite_check_constraints() {
        let path = temp_db_path("gastroepi_test_constraints.db");
        let db = BancoDados::new(&path);
        db.criar().unwrap();
        
        let conn = obter_conexao(&path).unwrap();
        
        // 1. Idade negativa deve falhar
        let res_idade = conn.execute(
            "INSERT INTO pacientes (numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame) \
             VALUES ('111', NULL, 'Test', '2026-06-03', -5, 'M', 0, NULL, 'Rastreio')",
            []
        );
        assert!(res_idade.is_err());
        assert!(res_idade.err().unwrap().to_string().contains("CHECK constraint failed"));
        
        // 2. Sexo inválido deve falhar
        let res_sexo = conn.execute(
            "INSERT INTO pacientes (numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame) \
             VALUES ('222', NULL, 'Test', '2026-06-03', 30, 'X', 0, NULL, 'Rastreio')",
            []
        );
        assert!(res_sexo.is_err());
        assert!(res_sexo.err().unwrap().to_string().contains("CHECK constraint failed"));
        
        // 3. Pólipo negativo deve falhar
        let res_polipo = conn.execute(
            "INSERT INTO pacientes (numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame) \
             VALUES ('333', NULL, 'Test', '2026-06-03', 30, 'M', -1, NULL, 'Rastreio')",
            []
        );
        assert!(res_polipo.is_err());
        assert!(res_polipo.err().unwrap().to_string().contains("CHECK constraint failed"));

        // Insere um paciente válido para testar histórico familiar
        conn.execute(
            "INSERT INTO pacientes (id, numero_prontuario, cpf, nome, data_exame, idade, sexo, polipo, resultado_histopatologico, indicacao_exame) \
             VALUES (1, '444', NULL, 'Valid', '2026-06-03', 30, 'F', 0, NULL, 'Rastreio')",
            []
        ).unwrap();
        
        // 4. Grau inválido (não 1, 2 ou 3) deve falhar
        let res_grau = conn.execute(
            "INSERT INTO historico_familiar (paciente_id, parentesco, grau, idade_diagnostico) \
             VALUES (1, 'Tio', 4, 50)",
            []
        );
        assert!(res_grau.is_err());
        assert!(res_grau.err().unwrap().to_string().contains("CHECK constraint failed"));

        // 5. Idade de diagnóstico negativa deve falhar
        let res_idade_diag = conn.execute(
            "INSERT INTO historico_familiar (paciente_id, parentesco, grau, idade_diagnostico) \
             VALUES (1, 'Mãe', 1, -10)",
            []
        );
        assert!(res_idade_diag.is_err());
        assert!(res_idade_diag.err().unwrap().to_string().contains("CHECK constraint failed"));
        
        let _ = fs::remove_file(&path);
    }

    #[test]
    #[cfg(windows)]
    fn test_proteger_arquivo_windows() {
        let path = temp_db_path("gastroepi_test_acl.db");
        fs::write(&path, b"test content").unwrap();
        
        proteger_arquivo(&path);
        
        // Verifica que o arquivo ainda existe e pode ser manipulado
        assert!(std::path::Path::new(&path).exists());
        
        let _ = fs::remove_file(&path);
    }
}
