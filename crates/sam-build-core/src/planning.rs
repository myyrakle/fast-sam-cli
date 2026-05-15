use crate::model::{FunctionBuildDefinition, LayerBuildDefinition};
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BuildMode {
    Cached,
    Incremental,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CacheStatus {
    Valid,
    Missing,
    SourceChanged,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct HashUpdate {
    pub source_hash: String,
    pub manifest_hash: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BuildPlan {
    pub mode: BuildMode,
    pub cache_status: Option<CacheStatus>,
    pub download_dependencies: bool,
    pub next_manifest_hash: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BatchPlanInput {
    pub id: String,
    pub runtime: Option<String>,
    pub use_container: bool,
    pub cache_exists: bool,
    pub previous_source_hash: String,
    pub current_source_hash: String,
    pub current_manifest_hash: Option<String>,
    pub previous_manifest_hash: String,
    pub dependencies_dir_exists: bool,
}

pub fn incremental_build_supported(runtime: Option<&str>, use_container: bool) -> bool {
    if use_container {
        return false;
    }

    runtime.is_some_and(|runtime| {
        ["python", "ruby", "nodejs"]
            .iter()
            .any(|prefix| runtime.starts_with(prefix))
    })
}

pub fn select_build_mode(runtime: Option<&str>, use_container: bool) -> BuildMode {
    if incremental_build_supported(runtime, use_container) {
        BuildMode::Incremental
    } else {
        BuildMode::Cached
    }
}

pub fn cache_status(
    cache_exists: bool,
    previous_source_hash: &str,
    current_source_hash: &str,
) -> CacheStatus {
    if !cache_exists {
        CacheStatus::Missing
    } else if previous_source_hash != current_source_hash {
        CacheStatus::SourceChanged
    } else {
        CacheStatus::Valid
    }
}

pub fn dependency_download_required(
    current_manifest_hash: Option<&str>,
    previous_manifest_hash: &str,
    dependencies_dir_exists: bool,
) -> bool {
    match current_manifest_hash {
        Some(current_manifest_hash) => {
            current_manifest_hash != previous_manifest_hash || !dependencies_dir_exists
        }
        None => true,
    }
}

pub fn update_manifest_state(
    manifest_hash: Option<&str>,
    previous_manifest_hash: &str,
    dependencies_dir_exists: bool,
) -> (String, bool) {
    match manifest_hash {
        Some(manifest_hash)
            if manifest_hash != previous_manifest_hash || !dependencies_dir_exists =>
        {
            (manifest_hash.to_owned(), true)
        }
        Some(_) => (previous_manifest_hash.to_owned(), false),
        None => (previous_manifest_hash.to_owned(), true),
    }
}

#[allow(clippy::too_many_arguments)]
pub fn plan_build(
    runtime: Option<&str>,
    use_container: bool,
    cache_exists: bool,
    previous_source_hash: &str,
    current_source_hash: &str,
    current_manifest_hash: Option<&str>,
    previous_manifest_hash: &str,
    dependencies_dir_exists: bool,
) -> BuildPlan {
    let mode = select_build_mode(runtime, use_container);
    let (next_manifest_hash, download_dependencies) = update_manifest_state(
        current_manifest_hash,
        previous_manifest_hash,
        dependencies_dir_exists,
    );

    match mode {
        BuildMode::Incremental => BuildPlan {
            mode,
            cache_status: None,
            download_dependencies,
            next_manifest_hash,
        },
        BuildMode::Cached => BuildPlan {
            mode,
            cache_status: Some(cache_status(
                cache_exists,
                previous_source_hash,
                current_source_hash,
            )),
            download_dependencies,
            next_manifest_hash,
        },
    }
}

pub fn batch_plan_builds(inputs: &[BatchPlanInput]) -> Vec<(String, BuildPlan)> {
    inputs
        .iter()
        .map(|input| {
            (
                input.id.clone(),
                plan_build(
                    input.runtime.as_deref(),
                    input.use_container,
                    input.cache_exists,
                    &input.previous_source_hash,
                    &input.current_source_hash,
                    input.current_manifest_hash.as_deref(),
                    &input.previous_manifest_hash,
                    input.dependencies_dir_exists,
                ),
            )
        })
        .collect()
}

pub fn compare_hash_changes_for_functions(
    updated: &[FunctionBuildDefinition],
    existing: &mut [FunctionBuildDefinition],
) -> BTreeMap<String, HashUpdate> {
    compare_hash_changes(
        updated,
        existing,
        |left, right| left.equivalent_for_build(right),
        |definition| &definition.uuid,
        |definition| &definition.source_hash,
        |definition| &definition.manifest_hash,
        |definition, download_dependencies| {
            definition.download_dependencies = download_dependencies
        },
    )
}

pub fn compare_hash_changes_for_layers(
    updated: &[LayerBuildDefinition],
    existing: &mut [LayerBuildDefinition],
) -> BTreeMap<String, HashUpdate> {
    compare_hash_changes(
        updated,
        existing,
        |left, right| left.equivalent_for_build(right),
        |definition| &definition.uuid,
        |definition| &definition.source_hash,
        |definition| &definition.manifest_hash,
        |definition, download_dependencies| {
            definition.download_dependencies = download_dependencies
        },
    )
}

pub fn compare_hash_changes<T, EqFn, UuidFn, SourceHashFn, ManifestHashFn, SetDownloadFn>(
    updated: &[T],
    existing: &mut [T],
    equivalent: EqFn,
    uuid: UuidFn,
    source_hash: SourceHashFn,
    manifest_hash: ManifestHashFn,
    mut set_download_dependencies: SetDownloadFn,
) -> BTreeMap<String, HashUpdate>
where
    EqFn: Fn(&T, &T) -> bool,
    UuidFn: Fn(&T) -> &str,
    SourceHashFn: Fn(&T) -> &str,
    ManifestHashFn: Fn(&T) -> &str,
    SetDownloadFn: FnMut(&mut T, bool),
{
    let mut changes = BTreeMap::new();
    for existing_definition in existing {
        if let Some(updated_definition) = updated
            .iter()
            .find(|updated_definition| equivalent(updated_definition, existing_definition))
        {
            let old_manifest_hash = manifest_hash(existing_definition);
            let updated_manifest_hash = manifest_hash(updated_definition);
            let hashes_changed = source_hash(existing_definition)
                != source_hash(updated_definition)
                || old_manifest_hash != updated_manifest_hash;

            if hashes_changed {
                changes.insert(
                    uuid(updated_definition).to_owned(),
                    HashUpdate {
                        source_hash: source_hash(updated_definition).to_owned(),
                        manifest_hash: updated_manifest_hash.to_owned(),
                    },
                );
            }

            set_download_dependencies(
                existing_definition,
                old_manifest_hash != updated_manifest_hash,
            );
        }
    }
    changes
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{EnvVars, Metadata, ZIP};

    fn function(uuid: &str, source_hash: &str, manifest_hash: &str) -> FunctionBuildDefinition {
        FunctionBuildDefinition {
            uuid: uuid.into(),
            runtime: Some("python3.12".into()),
            codeuri: Some("src".into()),
            imageuri: None,
            packagetype: ZIP.into(),
            architecture: "x86_64".into(),
            metadata: Metadata::new(),
            handler: "app.handler".into(),
            source_hash: source_hash.into(),
            manifest_hash: manifest_hash.into(),
            env_vars: EnvVars::new(),
            functions: vec![],
            download_dependencies: true,
        }
    }

    #[test]
    fn incremental_support_matches_python_runtime_prefixes() {
        assert!(incremental_build_supported(Some("python3.12"), false));
        assert!(incremental_build_supported(Some("nodejs20.x"), false));
        assert!(incremental_build_supported(Some("ruby3.2"), false));
        assert!(!incremental_build_supported(Some("go1.x"), false));
        assert!(!incremental_build_supported(Some("python3.12"), true));
        assert!(!incremental_build_supported(None, false));
    }

    #[test]
    fn cache_status_distinguishes_missing_and_changed() {
        assert_eq!(cache_status(false, "old", "old"), CacheStatus::Missing);
        assert_eq!(cache_status(true, "old", "new"), CacheStatus::SourceChanged);
        assert_eq!(cache_status(true, "same", "same"), CacheStatus::Valid);
    }

    #[test]
    fn dependency_download_matches_incremental_strategy() {
        assert!(dependency_download_required(Some("new"), "old", true));
        assert!(dependency_download_required(Some("same"), "same", false));
        assert!(!dependency_download_required(Some("same"), "same", true));
        assert!(dependency_download_required(None, "same", true));
    }

    #[test]
    fn plan_build_uses_incremental_for_supported_runtime() {
        assert_eq!(
            plan_build(
                Some("python3.12"),
                false,
                true,
                "same-source",
                "same-source",
                Some("same-manifest"),
                "same-manifest",
                true,
            ),
            BuildPlan {
                mode: BuildMode::Incremental,
                cache_status: None,
                download_dependencies: false,
                next_manifest_hash: "same-manifest".into(),
            }
        );
    }

    #[test]
    fn plan_build_uses_cache_for_container_builds() {
        assert_eq!(
            plan_build(
                Some("python3.12"),
                true,
                true,
                "old-source",
                "new-source",
                Some("new-manifest"),
                "old-manifest",
                true,
            ),
            BuildPlan {
                mode: BuildMode::Cached,
                cache_status: Some(CacheStatus::SourceChanged),
                download_dependencies: true,
                next_manifest_hash: "new-manifest".into(),
            }
        );
    }

    #[test]
    fn batch_plan_builds_preserves_input_identity_and_order() {
        let plans = batch_plan_builds(&[
            BatchPlanInput {
                id: "fn".into(),
                runtime: Some("python3.12".into()),
                use_container: false,
                cache_exists: false,
                previous_source_hash: String::new(),
                current_source_hash: String::new(),
                current_manifest_hash: None,
                previous_manifest_hash: String::new(),
                dependencies_dir_exists: false,
            },
            BatchPlanInput {
                id: "layer".into(),
                runtime: Some("go1.x".into()),
                use_container: false,
                cache_exists: true,
                previous_source_hash: "same".into(),
                current_source_hash: "same".into(),
                current_manifest_hash: None,
                previous_manifest_hash: String::new(),
                dependencies_dir_exists: false,
            },
        ]);

        assert_eq!(plans[0].0, "fn");
        assert_eq!(plans[0].1.mode, BuildMode::Incremental);
        assert_eq!(plans[1].0, "layer");
        assert_eq!(plans[1].1.mode, BuildMode::Cached);
    }

    #[test]
    fn compare_hash_changes_updates_manifest_download_flag() {
        let updated = vec![function("same-uuid", "new-source", "new-manifest")];
        let mut existing = vec![function("same-uuid", "old-source", "old-manifest")];
        let changes = compare_hash_changes_for_functions(&updated, &mut existing);

        assert_eq!(
            changes.get("same-uuid"),
            Some(&HashUpdate {
                source_hash: "new-source".into(),
                manifest_hash: "new-manifest".into()
            })
        );
        assert!(existing[0].download_dependencies);
    }

    #[test]
    fn compare_hash_changes_preserves_false_download_flag_when_manifest_unchanged() {
        let updated = vec![function("same-uuid", "new-source", "same-manifest")];
        let mut existing = vec![function("same-uuid", "old-source", "same-manifest")];
        compare_hash_changes_for_functions(&updated, &mut existing);
        assert!(!existing[0].download_dependencies);
    }
}
