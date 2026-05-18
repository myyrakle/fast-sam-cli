use crate::graph::BuildGraph;
use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::path::Path;

pub fn retained_definition_uuids(graph: &BuildGraph) -> BTreeSet<String> {
    graph
        .function_build_definitions
        .iter()
        .map(|definition| definition.uuid.clone())
        .chain(
            graph
                .layer_build_definitions
                .iter()
                .map(|definition| definition.uuid.clone()),
        )
        .collect()
}

pub fn clean_redundant_folders(
    base_dir: impl AsRef<Path>,
    retained_uuids: &BTreeSet<String>,
) -> io::Result<Vec<String>> {
    let base_dir = base_dir.as_ref();
    if !base_dir.exists() {
        return Ok(Vec::new());
    }

    let mut removed = Vec::new();
    for entry in fs::read_dir(base_dir)? {
        let entry = entry?;
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().into_owned();
        if path.is_dir() && !retained_uuids.contains(&name) {
            fs::remove_dir_all(path)?;
            removed.push(name);
        }
    }
    removed.sort();
    Ok(removed)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{EnvVars, FunctionBuildDefinition, Metadata, ZIP};
    use tempfile::tempdir;

    #[test]
    fn removes_only_redundant_directories() {
        let dir = tempdir().unwrap();
        fs::create_dir(dir.path().join("keep")).unwrap();
        fs::create_dir(dir.path().join("remove")).unwrap();
        fs::write(dir.path().join("file.txt"), "not a directory").unwrap();

        let removed =
            clean_redundant_folders(dir.path(), &BTreeSet::from(["keep".to_owned()])).unwrap();
        assert_eq!(removed, vec!["remove"]);
        assert!(dir.path().join("keep").exists());
        assert!(dir.path().join("file.txt").exists());
    }

    #[test]
    fn gathers_function_and_layer_uuids() {
        let graph = BuildGraph {
            function_build_definitions: vec![FunctionBuildDefinition {
                uuid: "fn".into(),
                runtime: Some("python3.12".into()),
                codeuri: Some("src".into()),
                imageuri: None,
                packagetype: ZIP.into(),
                architecture: "x86_64".into(),
                metadata: Metadata::new(),
                handler: "app.handler".into(),
                source_hash: String::new(),
                manifest_hash: String::new(),
                env_vars: EnvVars::new(),
                functions: vec!["Fn".into()],
                download_dependencies: true,
            }],
            layer_build_definitions: vec![],
        };
        assert_eq!(
            retained_definition_uuids(&graph),
            BTreeSet::from(["fn".to_owned()])
        );
    }
}
