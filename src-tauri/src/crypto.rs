use aes_gcm::{
    aead::{Aead, KeyInit},
    Aes256Gcm, Nonce, Key
};
use argon2::{Argon2, Algorithm, Version, Params};
use base64::Engine as _;
use rand::RngCore;

pub const TIME_COST: u32 = 3;
pub const MEMORY_COST: u32 = 65536; // 64 MiB
pub const PARALLELISM: u32 = 4;
pub const SALT_BYTES: usize = 16;
pub const KEY_BYTES: usize = 32;
pub const CANARIO_PLAINTEXT: &str = "gastroepidemio:canario:v1";

pub struct Cofre {
    key: [u8; 32],
}

impl Cofre {
    pub fn new(key: [u8; 32]) -> Self {
        Self { key }
    }

    pub fn key(&self) -> &[u8; 32] {
        &self.key
    }

    /// Encripta uma string usando AES-256-GCM.
    /// Retorna o token encodado em Base64 padrão contendo o nonce (12 bytes) concatenado com o ciphertext.
    pub fn encriptar(&self, plaintext: &str) -> Result<String, String> {
        let mut nonce_bytes = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);

        let key = Key::<Aes256Gcm>::from_slice(&self.key);
        let cipher = Aes256Gcm::new(key);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = cipher
            .encrypt(nonce, plaintext.as_bytes())
            .map_err(|e| format!("Falha ao encriptar: {}", e))?;

        let mut combined = Vec::with_capacity(nonce_bytes.len() + ciphertext.len());
        combined.extend_from_slice(&nonce_bytes);
        combined.extend_from_slice(&ciphertext);

        use base64::engine::general_purpose::STANDARD;
        Ok(STANDARD.encode(combined))
    }

    /// Decripta um token em Base64 padrão extraindo o nonce (primeiros 12 bytes) e descriptografando o restante com AES-256-GCM.
    pub fn decriptar(&self, token: &str) -> Result<String, String> {
        use base64::engine::general_purpose::STANDARD;
        let combined = STANDARD
            .decode(token)
            .map_err(|e| format!("Erro Base64 decode: {}", e))?;

        if combined.len() < 12 {
            return Err("Token inválido (tamanho menor que o nonce)".to_string());
        }

        let (nonce_bytes, ciphertext) = combined.split_at(12);
        let key = Key::<Aes256Gcm>::from_slice(&self.key);
        let cipher = Aes256Gcm::new(key);
        let nonce = Nonce::from_slice(nonce_bytes);

        let plaintext_bytes = cipher
            .decrypt(nonce, ciphertext)
            .map_err(|e| format!("Falha ao decriptar (chave errada ou dado corrompido): {}", e))?;

        String::from_utf8(plaintext_bytes)
            .map_err(|e| format!("Erro UTF-8 decode: {}", e))
    }
}

/// Deriva uma chave de 32 bytes a partir de uma senha e salt usando Argon2id.
pub fn derivar_chave(
    senha: &str,
    salt: &[u8],
    m_cost: u32,
    t_cost: u32,
    p_cost: u32,
) -> Result<[u8; 32], String> {
    if senha.is_empty() {
        return Err("Senha vazia".to_string());
    }
    if salt.len() != SALT_BYTES {
        return Err(format!("Salt deve ter {} bytes, tem {}", SALT_BYTES, salt.len()));
    }

    let params = Params::new(m_cost, t_cost, p_cost, Some(KEY_BYTES))
        .map_err(|e| format!("Parâmetros do Argon2 inválidos: {}", e))?;

    let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);

    let mut derived_key = [0u8; 32];
    argon2
        .hash_password_into(senha.as_bytes(), salt, &mut derived_key)
        .map_err(|e| format!("Erro KDF Argon2id: {}", e))?;

    Ok(derived_key)
}

/// Formata a chave em formato Base64 URL-safe amigável para impressão/cópia em blocos de 8 caracteres separados por espaços.
pub fn gerar_recovery_key(key: &[u8; 32]) -> String {
    use base64::engine::general_purpose::URL_SAFE;
    let s = URL_SAFE.encode(key);
    let chars: Vec<char> = s.chars().collect();
    let mut result = String::new();
    for (i, c) in chars.iter().enumerate() {
        if i > 0 && i % 8 == 0 {
            result.push(' ');
        }
        result.push(*c);
    }
    result
}

/// Reconstrói o cofre a partir da chave-mestre amigável (formato com espaços e delimitadores limpos).
pub fn cofre_de_chave_recovery(chave_legivel: &str) -> Result<Cofre, String> {
    let mut bruta: String = chave_legivel.chars().filter(|c| !c.is_whitespace()).collect();
    while bruta.len() % 4 != 0 {
        bruta.push('=');
    }

    use base64::engine::general_purpose::URL_SAFE;
    let decoded = URL_SAFE
        .decode(bruta)
        .map_err(|e| format!("Erro ao decodificar chave de recuperação: {}", e))?;

    if decoded.len() != 32 {
        return Err(format!("Chave de recuperação inválida: tamanho de {} bytes diferente de 32", decoded.len()));
    }

    let mut key = [0u8; 32];
    key.copy_from_slice(&decoded);
    Ok(Cofre::new(key))
}

/// Cria o canário criptografado a partir de um cofre.
pub fn criar_canario(cofre: &Cofre) -> Result<String, String> {
    cofre.encriptar(CANARIO_PLAINTEXT)
}

/// Valida o canário descriptografando-o e comparando com o plaintext do canário.
pub fn validar_canario(cofre: &Cofre, token: &str) -> bool {
    match cofre.decriptar(token) {
        Ok(plaintext) => plaintext == CANARIO_PLAINTEXT,
        Err(_) => false,
    }
}

/// Calcula o hash da entrada de auditoria atual concatenando os campos com \x00 (NUL) e aplicando SHA-256.
pub fn calcular_hash_auditoria(
    hash_anterior: &str,
    timestamp: &str,
    usuario: &str,
    acao: &str,
    entidade: &str,
    entidade_id: Option<i64>,
    snapshot_antes: Option<&str>,
    snapshot_depois: Option<&str>,
) -> String {
    use sha2::{Sha256, Digest};
    let mut hasher = Sha256::new();
    let id_str = entidade_id.map(|id| id.to_string()).unwrap_or_default();
    let partes = [
        hash_anterior,
        timestamp,
        usuario,
        acao,
        entidade,
        &id_str,
        snapshot_antes.unwrap_or(""),
        snapshot_depois.unwrap_or(""),
    ];
    let combined = partes.join("\u{0000}");
    hasher.update(combined.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash_auditoria() {
        let hash = calcular_hash_auditoria(
            "0000000000000000000000000000000000000000000000000000000000000000",
            "2026-06-03T01:36:35Z",
            "mateus",
            "CADASTRAR",
            "Paciente",
            Some(1),
            None,
            Some("{\"nome\":\"João\"}"),
        );
        assert_eq!(hash.len(), 64);
        // O hash deve ser determinístico
        let hash2 = calcular_hash_auditoria(
            "0000000000000000000000000000000000000000000000000000000000000000",
            "2026-06-03T01:36:35Z",
            "mateus",
            "CADASTRAR",
            "Paciente",
            Some(1),
            None,
            Some("{\"nome\":\"João\"}"),
        );
        assert_eq!(hash, hash2);
    }

    #[test]
    fn test_kdf_derivacao() {
        let salt = [0u8; 16];
        let key1 = derivar_chave("minha_senha_super_segura_123", &salt, MEMORY_COST, TIME_COST, PARALLELISM).unwrap();
        let key2 = derivar_chave("minha_senha_super_segura_123", &salt, MEMORY_COST, TIME_COST, PARALLELISM).unwrap();
        assert_eq!(key1, key2);

        let key3 = derivar_chave("outra_senha", &salt, MEMORY_COST, TIME_COST, PARALLELISM).unwrap();
        assert_ne!(key1, key3);
    }

    #[test]
    fn test_cofre_encriptacao_decriptacao() {
        let key = [42u8; 32];
        let cofre = Cofre::new(key);

        let original = "Paciente: João da Silva, CPF: 12345678901";
        let token = cofre.encriptar(original).unwrap();
        assert_ne!(original, token);

        let decifrado = cofre.decriptar(&token).unwrap();
        assert_eq!(original, decifrado);
    }

    #[test]
    fn test_cofre_chave_errada() {
        let key_correta = [1u8; 32];
        let key_errada = [2u8; 32];

        let cofre_correto = Cofre::new(key_correta);
        let cofre_errado = Cofre::new(key_errada);

        let token = cofre_correto.encriptar("segredo").unwrap();
        let resultado = cofre_errado.decriptar(&token);
        assert!(resultado.is_err());
    }

    #[test]
    fn test_canario_fluxo() {
        let key = [9u8; 32];
        let cofre = Cofre::new(key);

        let token_canario = criar_canario(&cofre).unwrap();
        assert!(validar_canario(&cofre, &token_canario));

        let cofre_outro = Cofre::new([8u8; 32]);
        assert!(!validar_canario(&cofre_outro, &token_canario));
    }

    #[test]
    fn test_recovery_key() {
        let key_original = [7u8; 32];
        let legivel = gerar_recovery_key(&key_original);
        
        // Verifica formatação em blocos de 8 caracteres separados por espaços
        let partes: Vec<&str> = legivel.split(' ').collect();
        for p in &partes {
            assert!(p.len() <= 8);
        }

        let cofre_reconstruido = cofre_de_chave_recovery(&legivel).unwrap();
        assert_eq!(key_original, *cofre_reconstruido.key());
    }
}
