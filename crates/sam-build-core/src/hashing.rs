use md5::{Digest as Md5Digest, Md5};
use sha2::Sha256;
use std::collections::BTreeSet;
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

const BLOCK_SIZE: usize = 4096;

#[derive(Clone, Copy, Debug)]
pub enum HashAlgorithm {
    Md5,
    Sha256,
}

pub fn file_checksum(path: impl AsRef<Path>, algorithm: HashAlgorithm) -> io::Result<String> {
    let mut file = File::open(path)?;
    let mut buffer = [0_u8; BLOCK_SIZE];
    match algorithm {
        HashAlgorithm::Md5 => {
            let mut hasher = Md5::new();
            loop {
                let read = file.read(&mut buffer)?;
                if read == 0 {
                    break;
                }
                hasher.update(&buffer[..read]);
            }
            Ok(format!("{:x}", hasher.finalize()))
        }
        HashAlgorithm::Sha256 => {
            let mut hasher = Sha256::new();
            loop {
                let read = file.read(&mut buffer)?;
                if read == 0 {
                    break;
                }
                hasher.update(&buffer[..read]);
            }
            Ok(format!("{:x}", hasher.finalize()))
        }
    }
}

pub fn dir_checksum(
    directory: impl AsRef<Path>,
    ignore_list: &[&str],
    algorithm: HashAlgorithm,
) -> io::Result<String> {
    let directory = directory.as_ref();
    let ignored: BTreeSet<&str> = ignore_list.iter().copied().collect();
    let mut files = Vec::<PathBuf>::new();

    for entry in WalkDir::new(directory)
        .follow_links(true)
        .into_iter()
        .filter_entry(|entry| {
            entry
                .file_name()
                .to_str()
                .is_none_or(|name| !ignored.contains(name))
        })
    {
        let entry = entry?;
        if entry.file_type().is_file() {
            files.push(entry.into_path());
        }
    }

    files.sort();
    match algorithm {
        HashAlgorithm::Md5 => digest_directory::<Md5>(directory, &files),
        HashAlgorithm::Sha256 => digest_directory::<Sha256>(directory, &files),
    }
}

fn digest_directory<D>(directory: &Path, files: &[PathBuf]) -> io::Result<String>
where
    D: Md5Digest + Default,
{
    let mut hasher = D::default();
    for file in files {
        let relative = file.strip_prefix(directory).unwrap_or(file);
        hasher.update(relative.to_string_lossy().as_bytes());
        // Python's implementation always uses md5 for each file checksum,
        // even when the outer directory checksum uses sha256.
        hasher.update(file_checksum(file, HashAlgorithm::Md5)?.as_bytes());
    }
    Ok(to_hex(&hasher.finalize()))
}

fn to_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    #[test]
    fn directory_hash_ignores_named_entries() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("a.txt"), "hello").unwrap();
        fs::create_dir(dir.path().join(".aws-sam")).unwrap();
        fs::write(dir.path().join(".aws-sam/ignored.txt"), "ignored").unwrap();

        let with_ignored = dir_checksum(dir.path(), &[".aws-sam"], HashAlgorithm::Sha256).unwrap();
        fs::remove_dir_all(dir.path().join(".aws-sam")).unwrap();
        let without_ignored =
            dir_checksum(dir.path(), &[".aws-sam"], HashAlgorithm::Sha256).unwrap();
        assert_eq!(with_ignored, without_ignored);
    }

    #[test]
    fn directory_hash_matches_python_contract() {
        let dir = tempdir().unwrap();
        fs::write(dir.path().join("a.txt"), "hello").unwrap();
        fs::write(dir.path().join("b.txt"), "world").unwrap();
        fs::create_dir(dir.path().join(".aws-sam")).unwrap();
        fs::write(dir.path().join(".aws-sam/ignored.txt"), "ignored").unwrap();

        assert_eq!(
            dir_checksum(dir.path(), &[".aws-sam"], HashAlgorithm::Md5).unwrap(),
            "334740827e90ab1c0d21024d5fc4d529"
        );
        assert_eq!(
            dir_checksum(dir.path(), &[".aws-sam"], HashAlgorithm::Sha256).unwrap(),
            "64c9a04cc4e761d9160adaa645f25e3af658a97a022ed1c32b387141626a0705"
        );
    }
}
