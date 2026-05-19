use crate::hashing::{file_checksum, HashAlgorithm};
use md5::{Digest as Md5Digest, Md5};
use std::fs::{self, File};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, DateTime, ZipWriter};

pub fn create_package_zip(
    output_base_path: impl AsRef<Path>,
    source_root: impl AsRef<Path>,
    lambda_permissions: bool,
) -> io::Result<PathBuf> {
    let source_root = fs::canonicalize(source_root)?;
    let zip_path = output_base_path.as_ref().with_extension("zip");
    let file = File::create(&zip_path)?;
    let mut zip = ZipWriter::new(file);

    for path in collect_files(&source_root)? {
        let relative = path.strip_prefix(&source_root).unwrap_or(&path);
        let relative = relative.to_string_lossy().replace('\\', "/");
        let mut mode = file_mode(&path)?;
        if lambda_permissions {
            mode |= 0o100444;
        }
        let options = SimpleFileOptions::default()
            .compression_method(CompressionMethod::Deflated)
            .last_modified_time(DateTime::default())
            .unix_permissions(mode);
        zip.start_file(relative, options)?;

        let mut input = File::open(path)?;
        io::copy(&mut input, &mut zip)?;
    }

    zip.finish()?;
    Ok(zip_path)
}

pub fn create_package_zip_with_md5(
    output_base_path: impl AsRef<Path>,
    source_root: impl AsRef<Path>,
    lambda_permissions: bool,
) -> io::Result<(PathBuf, String)> {
    let source_root = fs::canonicalize(source_root)?;
    let zip_path = output_base_path.as_ref().with_extension("zip");
    let file = File::create(&zip_path)?;
    let mut zip = ZipWriter::new(file);
    let mut dir_hasher = Md5::new();
    let mut buffer = [0_u8; 64 * 1024];

    for path in collect_files(&source_root)? {
        let relative = path.strip_prefix(&source_root).unwrap_or(&path);
        let relative = relative.to_string_lossy().replace('\\', "/");
        dir_hasher.update(relative.as_bytes());

        let mut mode = file_mode(&path)?;
        if lambda_permissions {
            mode |= 0o100444;
        }
        let options = SimpleFileOptions::default()
            .compression_method(CompressionMethod::Deflated)
            .last_modified_time(DateTime::default())
            .unix_permissions(mode);
        zip.start_file(relative, options)?;

        let mut input = File::open(path)?;
        let mut file_hasher = Md5::new();
        loop {
            let read = input.read(&mut buffer)?;
            if read == 0 {
                break;
            }
            file_hasher.update(&buffer[..read]);
            zip.write_all(&buffer[..read])?;
        }
        dir_hasher.update(to_hex(&file_hasher.finalize()).as_bytes());
    }

    zip.finish()?;
    Ok((zip_path, to_hex(&dir_hasher.finalize())))
}

pub fn create_lambda_zip_with_sha256(
    output_base_path: impl AsRef<Path>,
    source_root: impl AsRef<Path>,
) -> io::Result<(PathBuf, String)> {
    let source_root = fs::canonicalize(source_root)?;
    let zip_path = output_base_path.as_ref().with_extension("zip");
    let file = File::create(&zip_path)?;
    let mut zip = ZipWriter::new(file);

    for path in collect_files(&source_root)? {
        let relative = path.strip_prefix(&source_root).unwrap_or(&path);
        let relative = relative.to_string_lossy().replace('\\', "/");
        let mode = file_mode(&path)?;
        let options = SimpleFileOptions::default()
            .compression_method(CompressionMethod::Deflated)
            .last_modified_time(DateTime::default())
            .unix_permissions(mode | 0o444);
        zip.start_file(relative, options)?;

        let mut input = File::open(path)?;
        io::copy(&mut input, &mut zip)?;
    }

    zip.finish()?;
    let sha256 = file_checksum(&zip_path, HashAlgorithm::Sha256)?;
    Ok((zip_path, sha256))
}

fn collect_files(source_root: &Path) -> io::Result<Vec<PathBuf>> {
    let mut files = Vec::new();
    for entry in WalkDir::new(source_root).follow_links(true) {
        let entry = entry?;
        if entry.file_type().is_file() {
            files.push(entry.into_path());
        }
    }
    files.sort();
    Ok(files)
}

fn to_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
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

    #[test]
    fn creates_package_zip() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("app.py"), "print('hi')").unwrap();
        let output = dir.path().join("artifact");

        let zip_path = create_package_zip(&output, dir.path(), false).unwrap();

        assert!(zip_path.exists());
        assert_eq!(zip_path.extension().unwrap(), "zip");
    }

    #[test]
    fn creates_package_zip_with_md5() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("app.py"), "print('hi')").unwrap();
        let output = dir.path().join("artifact");

        let (zip_path, md5) = create_package_zip_with_md5(&output, dir.path(), false).unwrap();

        assert!(zip_path.exists());
        assert_eq!(zip_path.extension().unwrap(), "zip");
        assert_eq!(md5.len(), 32);
    }
}
