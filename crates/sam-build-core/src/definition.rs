use sha2::{Digest, Sha256};
use std::fs;
use std::io;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DefinitionBytes {
    pub bytes: Vec<u8>,
    pub sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DefinitionText {
    pub text: String,
    pub sha256: String,
}

pub fn read_definition_bytes_with_sha256(path: impl AsRef<Path>) -> io::Result<DefinitionBytes> {
    let bytes = fs::read(path)?;
    let text = String::from_utf8(bytes.clone())
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
    let sha256 = sha256_hex(text.as_bytes());
    Ok(DefinitionBytes { bytes, sha256 })
}

pub fn read_definition_text_with_sha256(path: impl AsRef<Path>) -> io::Result<DefinitionText> {
    let text = fs::read_to_string(path)?;
    let sha256 = sha256_hex(text.as_bytes());
    Ok(DefinitionText { text, sha256 })
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

#[cfg(test)]
mod tests {
    use super::{read_definition_bytes_with_sha256, read_definition_text_with_sha256};
    use std::fs;

    #[test]
    fn reads_definition_bytes_and_sha256() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("openapi.json");
        fs::write(&path, br#"{"key": "value"}"#).expect("write");

        let definition = read_definition_bytes_with_sha256(&path).expect("definition");

        assert_eq!(definition.bytes, br#"{"key": "value"}"#);
        assert_eq!(
            definition.sha256,
            "9724c1e20e6e3e4d7f57ed25f9d4efb006e508590d528c90da597f6a775c13e5"
        );
    }

    #[test]
    fn reads_definition_text_and_sha256() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("state-machine.json");
        fs::write(&path, r#"{"key": "value"}"#).expect("write");

        let definition = read_definition_text_with_sha256(&path).expect("definition");

        assert_eq!(definition.text, r#"{"key": "value"}"#);
        assert_eq!(
            definition.sha256,
            "9724c1e20e6e3e4d7f57ed25f9d4efb006e508590d528c90da597f6a775c13e5"
        );
    }
}
