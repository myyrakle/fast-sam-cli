use crate::hashing::{file_checksum, HashAlgorithm};
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, DateTime, ZipWriter};

pub fn create_lambda_zip_with_sha256(
    output_base_path: impl AsRef<Path>,
    source_root: impl AsRef<Path>,
) -> io::Result<(PathBuf, String)> {
    let source_root = fs::canonicalize(source_root)?;
    let zip_path = output_base_path.as_ref().with_extension("zip");
    let file = File::create(&zip_path)?;
    let mut zip = ZipWriter::new(file);

    let mut files = Vec::new();
    for entry in WalkDir::new(&source_root).follow_links(true) {
        let entry = entry?;
        if entry.file_type().is_file() {
            files.push(entry.into_path());
        }
    }
    files.sort();

    for path in files {
        let relative = path.strip_prefix(&source_root).unwrap_or(&path);
        let relative = relative.to_string_lossy().replace('\\', "/");
        let mode = file_mode(&path)?;
        let options = SimpleFileOptions::default()
            .compression_method(CompressionMethod::Deflated)
            .last_modified_time(DateTime::default())
            .unix_permissions(mode | 0o444);
        zip.start_file(relative, options)?;

        let mut input = File::open(path)?;
        let mut buffer = Vec::new();
        input.read_to_end(&mut buffer)?;
        zip.write_all(&buffer)?;
    }

    zip.finish()?;
    let sha256 = file_checksum(&zip_path, HashAlgorithm::Sha256)?;
    Ok((zip_path, sha256))
}

#[cfg(unix)]
fn file_mode(path: &Path) -> io::Result<u32> {
    use std::os::unix::fs::MetadataExt;
    Ok(fs::metadata(path)?.mode())
}

#[cfg(not(unix))]
fn file_mode(_path: &Path) -> io::Result<u32> {
    Ok(0o100755)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    #[test]
    fn creates_zip_and_sha256() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("app.py"), "print('hi')").unwrap();
        let output = dir.path().join("artifact");

        let (zip_path, sha) = create_lambda_zip_with_sha256(&output, dir.path()).unwrap();

        assert!(zip_path.exists());
        assert_eq!(zip_path.extension().unwrap(), "zip");
        assert_eq!(sha.len(), 64);
    }
}
