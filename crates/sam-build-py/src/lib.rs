use pyo3::exceptions::PyOSError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use sam_build_core::{
    batch_plan_builds as core_batch_plan_builds, clean_redundant_folders, dir_checksum,
    plan_build as core_plan_build, BatchPlanInput, BuildGraph as CoreBuildGraph, HashAlgorithm,
    HashUpdate,
};
use std::collections::{BTreeMap, BTreeSet, HashMap};

#[pyfunction]
fn sha256_dir_checksum(directory: &str, ignore_list: Vec<String>) -> PyResult<String> {
    let ignore_list = ignore_list.iter().map(String::as_str).collect::<Vec<_>>();
    dir_checksum(directory, &ignore_list, HashAlgorithm::Sha256)
        .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
fn md5_dir_checksum(directory: &str, ignore_list: Vec<String>) -> PyResult<String> {
    let ignore_list = ignore_list.iter().map(String::as_str).collect::<Vec<_>>();
    dir_checksum(directory, &ignore_list, HashAlgorithm::Md5)
        .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn plan_build<'py>(
    py: Python<'py>,
    runtime: Option<&str>,
    use_container: bool,
    cache_exists: bool,
    previous_source_hash: &str,
    current_source_hash: &str,
    current_manifest_hash: Option<&str>,
    previous_manifest_hash: &str,
    dependencies_dir_exists: bool,
) -> PyResult<Bound<'py, PyDict>> {
    let plan = core_plan_build(
        runtime,
        use_container,
        cache_exists,
        previous_source_hash,
        current_source_hash,
        current_manifest_hash,
        previous_manifest_hash,
        dependencies_dir_exists,
    );
    let dict = PyDict::new(py);
    dict.set_item(
        "mode",
        match plan.mode {
            sam_build_core::BuildMode::Cached => "cached",
            sam_build_core::BuildMode::Incremental => "incremental",
        },
    )?;
    dict.set_item(
        "cache_status",
        plan.cache_status.map(|status| match status {
            sam_build_core::CacheStatus::Valid => "valid",
            sam_build_core::CacheStatus::Missing => "missing",
            sam_build_core::CacheStatus::SourceChanged => "source_changed",
        }),
    )?;
    dict.set_item("download_dependencies", plan.download_dependencies)?;
    dict.set_item("next_manifest_hash", plan.next_manifest_hash)?;
    Ok(dict)
}

#[pyfunction]
fn batch_plan_builds<'py>(
    py: Python<'py>,
    inputs: Vec<Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, PyList>> {
    let rust_inputs = inputs
        .iter()
        .map(|input| {
            Ok(BatchPlanInput {
                id: input
                    .get_item("id")?
                    .expect("id is required")
                    .extract::<String>()?,
                runtime: input
                    .get_item("runtime")?
                    .and_then(|value| value.extract().ok()),
                use_container: input
                    .get_item("use_container")?
                    .expect("use_container is required")
                    .extract::<bool>()?,
                cache_exists: input
                    .get_item("cache_exists")?
                    .expect("cache_exists is required")
                    .extract::<bool>()?,
                previous_source_hash: input
                    .get_item("previous_source_hash")?
                    .expect("previous_source_hash is required")
                    .extract::<String>()?,
                current_source_hash: input
                    .get_item("current_source_hash")?
                    .expect("current_source_hash is required")
                    .extract::<String>()?,
                current_manifest_hash: input
                    .get_item("current_manifest_hash")?
                    .and_then(|value| value.extract().ok()),
                previous_manifest_hash: input
                    .get_item("previous_manifest_hash")?
                    .expect("previous_manifest_hash is required")
                    .extract::<String>()?,
                dependencies_dir_exists: input
                    .get_item("dependencies_dir_exists")?
                    .expect("dependencies_dir_exists is required")
                    .extract::<bool>()?,
            })
        })
        .collect::<PyResult<Vec<_>>>()?;

    let output = PyList::empty(py);
    for (id, plan) in core_batch_plan_builds(&rust_inputs) {
        let dict = PyDict::new(py);
        dict.set_item("id", id)?;
        dict.set_item(
            "mode",
            match plan.mode {
                sam_build_core::BuildMode::Cached => "cached",
                sam_build_core::BuildMode::Incremental => "incremental",
            },
        )?;
        dict.set_item(
            "cache_status",
            plan.cache_status.map(|status| match status {
                sam_build_core::CacheStatus::Valid => "valid",
                sam_build_core::CacheStatus::Missing => "missing",
                sam_build_core::CacheStatus::SourceChanged => "source_changed",
            }),
        )?;
        dict.set_item("download_dependencies", plan.download_dependencies)?;
        dict.set_item("next_manifest_hash", plan.next_manifest_hash)?;
        output.append(dict)?;
    }
    Ok(output)
}

#[pyfunction]
fn batch_plan_modes(inputs: Vec<(String, Option<String>, bool)>) -> Vec<(String, &'static str)> {
    inputs
        .into_iter()
        .map(|(id, runtime, use_container)| {
            let mode = match sam_build_core::planning::select_build_mode(
                runtime.as_deref(),
                use_container,
            ) {
                sam_build_core::BuildMode::Cached => "cached",
                sam_build_core::BuildMode::Incremental => "incremental",
            };
            (id, mode)
        })
        .collect()
}

#[pyfunction]
fn dedupe_function_specs<'py>(
    py: Python<'py>,
    inputs: Vec<Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, PyList>> {
    let mut groups: Vec<Vec<String>> = Vec::new();
    let mut group_indexes = HashMap::<NormalizedFunctionKey, usize>::new();
    for input in inputs {
        let metadata_repr = input
            .get_item("metadata_repr")?
            .expect("metadata_repr is required")
            .extract::<String>()?;
        let key = FunctionKey {
            runtime: input
                .get_item("runtime")?
                .and_then(|value| value.extract().ok()),
            codeuri: input
                .get_item("codeuri")?
                .and_then(|value| value.extract().ok()),
            imageuri: input
                .get_item("imageuri")?
                .and_then(|value| value.extract().ok()),
            packagetype: input
                .get_item("packagetype")?
                .expect("packagetype is required")
                .extract::<String>()?,
            architecture: input
                .get_item("architecture")?
                .expect("architecture is required")
                .extract::<String>()?,
            metadata_repr,
            build_method: input
                .get_item("build_method")?
                .and_then(|value| value.extract().ok()),
            handler: input
                .get_item("handler")?
                .and_then(|value| value.extract().ok()),
            env_vars_repr: input
                .get_item("env_vars_repr")?
                .expect("env_vars_repr is required")
                .extract::<String>()?,
        };
        let full_path = input
            .get_item("full_path")?
            .expect("full_path is required")
            .extract::<String>()?;

        if key.is_never_deduped() {
            groups.push(vec![full_path]);
        } else {
            let normalized = key.normalized();
            if let Some(index) = group_indexes.get(&normalized) {
                groups[*index].push(full_path);
            } else {
                let index = groups.len();
                groups.push(vec![full_path]);
                group_indexes.insert(normalized, index);
            }
        }
    }

    let output = PyList::empty(py);
    for members in groups {
        output.append(members)?;
    }
    Ok(output)
}

#[pyfunction]
fn dedupe_layer_specs<'py>(
    py: Python<'py>,
    inputs: Vec<Bound<'py, PyDict>>,
) -> PyResult<Bound<'py, PyList>> {
    let mut groups: Vec<Vec<String>> = Vec::new();
    let mut group_indexes = HashMap::<LayerKey, usize>::new();
    for input in inputs {
        let key = LayerKey {
            full_path: input
                .get_item("full_path")?
                .expect("full_path is required")
                .extract::<String>()?,
            codeuri: input
                .get_item("codeuri")?
                .and_then(|value| value.extract().ok()),
            build_method: input
                .get_item("build_method")?
                .and_then(|value| value.extract().ok()),
            compatible_runtimes_repr: input
                .get_item("compatible_runtimes_repr")?
                .expect("compatible_runtimes_repr is required")
                .extract::<String>()?,
            architecture: input
                .get_item("architecture")?
                .expect("architecture is required")
                .extract::<String>()?,
            env_vars_repr: input
                .get_item("env_vars_repr")?
                .expect("env_vars_repr is required")
                .extract::<String>()?,
        };
        let full_path = key.full_path.clone();

        if let Some(index) = group_indexes.get(&key) {
            groups[*index][0] = full_path;
        } else {
            let index = groups.len();
            groups.push(vec![full_path]);
            group_indexes.insert(key, index);
        }
    }

    let output = PyList::empty(py);
    for members in groups {
        output.append(members)?;
    }
    Ok(output)
}

#[pyfunction]
fn plan_graph_groups(
    function_inputs: Vec<(
        Option<String>,
        Option<String>,
        Option<String>,
        String,
        String,
        String,
        Option<String>,
        Option<String>,
        String,
    )>,
    layer_inputs: Vec<(
        String,
        Option<String>,
        Option<String>,
        String,
        String,
        String,
    )>,
) -> (Vec<Vec<usize>>, Vec<Vec<usize>>) {
    let mut function_groups = Vec::<Vec<usize>>::new();
    let mut function_group_indexes = HashMap::<NormalizedFunctionKey, usize>::new();
    for (
        index,
        (
            runtime,
            codeuri,
            imageuri,
            packagetype,
            architecture,
            metadata_repr,
            build_method,
            handler,
            env_vars_repr,
        ),
    ) in function_inputs.into_iter().enumerate()
    {
        let key = FunctionKey {
            runtime,
            codeuri,
            imageuri,
            packagetype,
            architecture,
            metadata_repr,
            build_method,
            handler,
            env_vars_repr,
        };
        if key.is_never_deduped() {
            function_groups.push(vec![index]);
        } else {
            let normalized = key.normalized();
            if let Some(group_index) = function_group_indexes.get(&normalized) {
                function_groups[*group_index].push(index);
            } else {
                let group_index = function_groups.len();
                function_groups.push(vec![index]);
                function_group_indexes.insert(normalized, group_index);
            }
        }
    }

    let mut layer_groups = Vec::<Vec<usize>>::new();
    let mut layer_group_indexes = HashMap::<LayerKey, usize>::new();
    for (
        index,
        (
            full_path,
            codeuri,
            build_method,
            compatible_runtimes_repr,
            architecture,
            env_vars_repr,
        ),
    ) in layer_inputs.into_iter().enumerate()
    {
        let key = LayerKey {
            full_path,
            codeuri,
            build_method,
            compatible_runtimes_repr,
            architecture,
            env_vars_repr,
        };
        if let Some(group_index) = layer_group_indexes.get(&key) {
            layer_groups[*group_index][0] = index;
        } else {
            let group_index = layer_groups.len();
            layer_groups.push(vec![index]);
            layer_group_indexes.insert(key, group_index);
        }
    }

    (function_groups, layer_groups)
}

#[pyfunction]
fn write_hash_updates(
    path: &str,
    function_updates: Vec<(String, String, String)>,
    layer_updates: Vec<(String, String, String)>,
) -> PyResult<()> {
    let function_updates = function_updates
        .into_iter()
        .map(|(uuid, source_hash, manifest_hash)| {
            (
                uuid,
                HashUpdate {
                    source_hash,
                    manifest_hash,
                },
            )
        })
        .collect::<BTreeMap<_, _>>();
    let layer_updates = layer_updates
        .into_iter()
        .map(|(uuid, source_hash, manifest_hash)| {
            (
                uuid,
                HashUpdate {
                    source_hash,
                    manifest_hash,
                },
            )
        })
        .collect::<BTreeMap<_, _>>();

    CoreBuildGraph::default()
        .write_hash_updates(path, &function_updates, &layer_updates)
        .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[derive(Clone)]
struct FunctionKey {
    runtime: Option<String>,
    codeuri: Option<String>,
    imageuri: Option<String>,
    packagetype: String,
    architecture: String,
    metadata_repr: String,
    build_method: Option<String>,
    handler: Option<String>,
    env_vars_repr: String,
}

impl FunctionKey {
    fn is_never_deduped(&self) -> bool {
        self.build_method.as_deref() == Some("makefile")
    }

    fn normalized(self) -> NormalizedFunctionKey {
        let handler = if self.build_method.as_deref() == Some("esbuild")
            || self.runtime.as_deref() == Some("go1.x")
        {
            self.handler
        } else {
            None
        };

        NormalizedFunctionKey {
            runtime: self.runtime,
            codeuri: self.codeuri,
            imageuri: self.imageuri,
            packagetype: self.packagetype,
            architecture: self.architecture,
            metadata_repr: self.metadata_repr,
            handler,
            env_vars_repr: self.env_vars_repr,
        }
    }
}

#[derive(Clone, Eq, Hash, PartialEq)]
struct NormalizedFunctionKey {
    runtime: Option<String>,
    codeuri: Option<String>,
    imageuri: Option<String>,
    packagetype: String,
    architecture: String,
    metadata_repr: String,
    handler: Option<String>,
    env_vars_repr: String,
}

#[derive(Clone, Eq, Hash, PartialEq)]
struct LayerKey {
    full_path: String,
    codeuri: Option<String>,
    build_method: Option<String>,
    compatible_runtimes_repr: String,
    architecture: String,
    env_vars_repr: String,
}

#[pyfunction]
fn remove_redundant_folders(base_dir: &str, retained_uuids: Vec<String>) -> PyResult<Vec<String>> {
    let retained_uuids = retained_uuids.into_iter().collect::<BTreeSet<_>>();
    clean_redundant_folders(base_dir, &retained_uuids)
        .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pymodule]
fn _sam_build_core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(sha256_dir_checksum, module)?)?;
    module.add_function(wrap_pyfunction!(md5_dir_checksum, module)?)?;
    module.add_function(wrap_pyfunction!(plan_build, module)?)?;
    module.add_function(wrap_pyfunction!(batch_plan_builds, module)?)?;
    module.add_function(wrap_pyfunction!(batch_plan_modes, module)?)?;
    module.add_function(wrap_pyfunction!(dedupe_function_specs, module)?)?;
    module.add_function(wrap_pyfunction!(dedupe_layer_specs, module)?)?;
    module.add_function(wrap_pyfunction!(plan_graph_groups, module)?)?;
    module.add_function(wrap_pyfunction!(write_hash_updates, module)?)?;
    module.add_function(wrap_pyfunction!(remove_redundant_folders, module)?)?;
    Ok(())
}
