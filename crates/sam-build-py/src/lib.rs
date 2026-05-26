use pyo3::exceptions::PyOSError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList};
use sam_build_core::{
    batch_plan_builds as core_batch_plan_builds, clean_redundant_folders,
    collect_rest_api_stage_names as core_collect_rest_api_stage_names,
    create_lambda_zip_with_sha256 as core_create_lambda_zip_with_sha256,
    create_package_zip as core_create_package_zip, create_package_zip_with_md5 as core_create_package_zip_with_md5,
    dependent_function_ids as core_dependent_function_ids, dir_checksum,
    file_checksum as core_file_checksum,
    function_resource_api_call_rows as core_function_resource_api_call_rows,
    local_hash_matches as core_local_hash_matches,
    lock_keys_from_api_call_rows as core_lock_keys_from_api_call_rows,
    plan_build as core_plan_build,
    read_definition_bytes_with_sha256 as core_read_definition_bytes_with_sha256,
    read_definition_text_with_sha256 as core_read_definition_text_with_sha256,
    read_sync_state as core_read_sync_state,
    sync_execution_decision as core_sync_execution_decision,
    write_sync_state as core_write_sync_state, BatchPlanInput, BuildGraph as CoreBuildGraph,
    HashAlgorithm, HashUpdate, ResourceSyncStateSection,
    ResourceTypeIndex as CoreResourceTypeIndex, ResourceTypeRow, SyncStateDocument,
    SyncStateSection,
};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::sync::{Arc, Mutex};

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeDefinitionRecord {
    #[pyo3(get, set)]
    uuid: String,
    #[pyo3(get, set)]
    source_hash: String,
    #[pyo3(get, set)]
    manifest_hash: String,
}

#[pymethods]
impl RuntimeDefinitionRecord {
    #[new]
    fn new(uuid: String, source_hash: String, manifest_hash: String) -> Self {
        Self {
            uuid,
            source_hash,
            manifest_hash,
        }
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyDict>) -> Self {
        self.clone()
    }
}

#[derive(Clone)]
struct RuntimeFunctionData {
    uuid: String,
    source_hash: String,
    manifest_hash: String,
    runtime: Option<String>,
    codeuri: Option<String>,
    imageuri: Option<String>,
    packagetype: String,
    architecture: String,
    handler: Option<String>,
    metadata_json: String,
    env_vars_json: String,
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeFunctionRecord {
    inner: Arc<Mutex<RuntimeFunctionData>>,
}

impl RuntimeFunctionRecord {
    fn snapshot(&self) -> RuntimeFunctionData {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .clone()
    }

    fn from_data(data: RuntimeFunctionData) -> Self {
        Self {
            inner: Arc::new(Mutex::new(data)),
        }
    }
}

#[pymethods]
impl RuntimeFunctionRecord {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
        uuid: String,
        source_hash: String,
        manifest_hash: String,
        runtime: Option<String>,
        codeuri: Option<String>,
        imageuri: Option<String>,
        packagetype: String,
        architecture: String,
        handler: Option<String>,
        metadata_json: String,
        env_vars_json: String,
    ) -> Self {
        Self::from_data(RuntimeFunctionData {
            uuid,
            source_hash,
            manifest_hash,
            runtime,
            codeuri,
            imageuri,
            packagetype,
            architecture,
            handler,
            metadata_json,
            env_vars_json,
        })
    }

    #[getter]
    fn uuid(&self) -> String {
        self.snapshot().uuid
    }
    #[setter]
    fn set_uuid(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .uuid = value;
    }
    #[getter]
    fn source_hash(&self) -> String {
        self.snapshot().source_hash
    }
    #[setter]
    fn set_source_hash(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .source_hash = value;
    }
    #[getter]
    fn manifest_hash(&self) -> String {
        self.snapshot().manifest_hash
    }
    #[setter]
    fn set_manifest_hash(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .manifest_hash = value;
    }
    #[getter]
    fn runtime(&self) -> Option<String> {
        self.snapshot().runtime
    }
    #[setter]
    fn set_runtime(&self, value: Option<String>) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .runtime = value;
    }
    #[getter]
    fn codeuri(&self) -> Option<String> {
        self.snapshot().codeuri
    }
    #[setter]
    fn set_codeuri(&self, value: Option<String>) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .codeuri = value;
    }
    #[getter]
    fn imageuri(&self) -> Option<String> {
        self.snapshot().imageuri
    }
    #[setter]
    fn set_imageuri(&self, value: Option<String>) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .imageuri = value;
    }
    #[getter]
    fn packagetype(&self) -> String {
        self.snapshot().packagetype
    }
    #[setter]
    fn set_packagetype(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .packagetype = value;
    }
    #[getter]
    fn architecture(&self) -> String {
        self.snapshot().architecture
    }
    #[setter]
    fn set_architecture(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .architecture = value;
    }
    #[getter]
    fn handler(&self) -> Option<String> {
        self.snapshot().handler
    }
    #[setter]
    fn set_handler(&self, value: Option<String>) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .handler = value;
    }
    #[getter]
    fn metadata_json(&self) -> String {
        self.snapshot().metadata_json
    }
    #[setter]
    fn set_metadata_json(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .metadata_json = value;
    }
    #[getter]
    fn env_vars_json(&self) -> String {
        self.snapshot().env_vars_json
    }
    #[setter]
    fn set_env_vars_json(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime function record lock poisoned")
            .env_vars_json = value;
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyDict>) -> Self {
        Self::from_data(self.snapshot())
    }

    fn equivalent_for_build(
        &self,
        other: &RuntimeFunctionRecord,
        build_method: Option<&str>,
    ) -> bool {
        let left = self.snapshot();
        let right = other.snapshot();
        if build_method == Some("makefile") {
            return false;
        }
        if build_method == Some("esbuild") && left.handler != right.handler {
            return false;
        }
        if left.runtime.as_deref() == Some("go1.x") && left.handler != right.handler {
            return false;
        }
        left.runtime == right.runtime
            && left.codeuri == right.codeuri
            && left.imageuri == right.imageuri
            && left.packagetype == right.packagetype
            && left.metadata_json == right.metadata_json
            && left.env_vars_json == right.env_vars_json
            && left.architecture == right.architecture
    }
}

#[derive(Clone)]
struct RuntimeLayerData {
    uuid: String,
    source_hash: String,
    manifest_hash: String,
    full_path: String,
    codeuri: Option<String>,
    build_method: Option<String>,
    compatible_runtimes: Option<Vec<String>>,
    architecture: String,
    env_vars_json: String,
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeLayerRecord {
    inner: Arc<Mutex<RuntimeLayerData>>,
}

impl RuntimeLayerRecord {
    fn snapshot(&self) -> RuntimeLayerData {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .clone()
    }
    fn from_data(data: RuntimeLayerData) -> Self {
        Self {
            inner: Arc::new(Mutex::new(data)),
        }
    }
}

#[pymethods]
impl RuntimeLayerRecord {
    #[new]
    #[allow(clippy::too_many_arguments)]
    fn new(
        uuid: String,
        source_hash: String,
        manifest_hash: String,
        full_path: String,
        codeuri: Option<String>,
        build_method: Option<String>,
        compatible_runtimes: Option<Vec<String>>,
        architecture: String,
        env_vars_json: String,
    ) -> Self {
        Self::from_data(RuntimeLayerData {
            uuid,
            source_hash,
            manifest_hash,
            full_path,
            codeuri,
            build_method,
            compatible_runtimes,
            architecture,
            env_vars_json,
        })
    }
    #[getter]
    fn uuid(&self) -> String {
        self.snapshot().uuid
    }
    #[setter]
    fn set_uuid(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .uuid = value;
    }
    #[getter]
    fn source_hash(&self) -> String {
        self.snapshot().source_hash
    }
    #[setter]
    fn set_source_hash(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .source_hash = value;
    }
    #[getter]
    fn manifest_hash(&self) -> String {
        self.snapshot().manifest_hash
    }
    #[setter]
    fn set_manifest_hash(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .manifest_hash = value;
    }
    #[getter]
    fn full_path(&self) -> String {
        self.snapshot().full_path
    }
    #[setter]
    fn set_full_path(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .full_path = value;
    }
    #[getter]
    fn codeuri(&self) -> Option<String> {
        self.snapshot().codeuri
    }
    #[setter]
    fn set_codeuri(&self, value: Option<String>) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .codeuri = value;
    }
    #[getter]
    fn build_method(&self) -> Option<String> {
        self.snapshot().build_method
    }
    #[setter]
    fn set_build_method(&self, value: Option<String>) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .build_method = value;
    }
    #[getter]
    fn compatible_runtimes(&self) -> Option<Vec<String>> {
        self.snapshot().compatible_runtimes
    }
    #[setter]
    fn set_compatible_runtimes(&self, value: Option<Vec<String>>) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .compatible_runtimes = value;
    }
    #[getter]
    fn architecture(&self) -> String {
        self.snapshot().architecture
    }
    #[setter]
    fn set_architecture(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .architecture = value;
    }
    #[getter]
    fn env_vars_json(&self) -> String {
        self.snapshot().env_vars_json
    }
    #[setter]
    fn set_env_vars_json(&self, value: String) {
        self.inner
            .lock()
            .expect("runtime layer record lock poisoned")
            .env_vars_json = value;
    }
    fn __deepcopy__(&self, _memo: &Bound<'_, PyDict>) -> Self {
        Self::from_data(self.snapshot())
    }
    fn equivalent_for_build(&self, other: &RuntimeLayerRecord) -> bool {
        let left = self.snapshot();
        let right = other.snapshot();
        left.full_path == right.full_path
            && left.codeuri == right.codeuri
            && left.build_method == right.build_method
            && left.compatible_runtimes == right.compatible_runtimes
            && left.env_vars_json == right.env_vars_json
            && left.architecture == right.architecture
    }
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeGraphPlan {
    function_groups: Vec<Vec<usize>>,
    function_records: Vec<RuntimeFunctionRecord>,
    layer_groups: Vec<Vec<usize>>,
    layer_records: Vec<RuntimeLayerRecord>,
}

#[pymethods]
impl RuntimeGraphPlan {
    fn function_groups(&self) -> Vec<Vec<usize>> {
        self.function_groups.clone()
    }

    fn function_records(&self) -> Vec<RuntimeFunctionRecord> {
        self.function_records.clone()
    }

    fn layer_groups(&self) -> Vec<Vec<usize>> {
        self.layer_groups.clone()
    }

    fn layer_records(&self) -> Vec<RuntimeLayerRecord> {
        self.layer_records.clone()
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyDict>) -> Self {
        self.clone()
    }

    fn into_state(&self) -> RuntimeBuildGraphState {
        RuntimeBuildGraphState {
            function_records: self.function_records.clone(),
            layer_records: self.layer_records.clone(),
        }
    }
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimePersistedGraph {
    function_records: Vec<RuntimeFunctionRecord>,
    layer_records: Vec<RuntimeLayerRecord>,
}

#[pymethods]
impl RuntimePersistedGraph {
    fn function_records(&self) -> Vec<RuntimeFunctionRecord> {
        self.function_records.clone()
    }

    fn layer_records(&self) -> Vec<RuntimeLayerRecord> {
        self.layer_records.clone()
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyDict>) -> Self {
        self.clone()
    }

    fn into_state(&self) -> RuntimeBuildGraphState {
        RuntimeBuildGraphState {
            function_records: self.function_records.clone(),
            layer_records: self.layer_records.clone(),
        }
    }
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeBuildGraphState {
    function_records: Vec<RuntimeFunctionRecord>,
    layer_records: Vec<RuntimeLayerRecord>,
}

#[pymethods]
impl RuntimeBuildGraphState {
    fn function_records(&self) -> Vec<RuntimeFunctionRecord> {
        self.function_records.clone()
    }

    fn layer_records(&self) -> Vec<RuntimeLayerRecord> {
        self.layer_records.clone()
    }

    fn function_count(&self) -> usize {
        self.function_records.len()
    }

    fn layer_count(&self) -> usize {
        self.layer_records.len()
    }

    fn definition_function_rows(&self) -> Vec<ExistingFunctionGraphInput> {
        self.function_records
            .iter()
            .map(|record| {
                let record = record.snapshot();
                let build_method = serde_json::from_str::<serde_json::Value>(&record.metadata_json)
                    .ok()
                    .and_then(|value| {
                        value
                            .get("BuildMethod")
                            .and_then(|value| value.as_str())
                            .map(str::to_owned)
                    });
                (
                    record.uuid,
                    record.source_hash,
                    record.manifest_hash,
                    record.runtime,
                    record.codeuri,
                    record.imageuri,
                    record.packagetype,
                    record.architecture,
                    record.metadata_json,
                    build_method,
                    record.handler,
                    record.env_vars_json,
                )
            })
            .collect()
    }

    fn definition_layer_rows(&self) -> PyResult<Vec<ExistingLayerGraphInput>> {
        self.layer_records
            .iter()
            .map(|record| {
                let record = record.snapshot();
                Ok((
                    record.uuid,
                    record.source_hash,
                    record.manifest_hash,
                    record.full_path,
                    record.codeuri,
                    record.build_method,
                    serde_json::to_string(&record.compatible_runtimes)
                        .map_err(|error| PyOSError::new_err(error.to_string()))?,
                    record.architecture,
                    record.env_vars_json,
                ))
            })
            .collect()
    }

    fn persisted_function_rows(
        &self,
        function_paths: Vec<Vec<String>>,
    ) -> Vec<(
        String,
        Option<String>,
        Option<String>,
        String,
        String,
        Option<String>,
        String,
        String,
        Vec<String>,
        String,
        String,
    )> {
        self.function_records
            .iter()
            .zip(function_paths)
            .map(|(record, functions)| {
                let record = record.snapshot();
                (
                    record.uuid,
                    record.runtime,
                    record.codeuri,
                    record.packagetype,
                    record.architecture,
                    record.handler,
                    record.source_hash,
                    record.manifest_hash,
                    functions,
                    record.metadata_json,
                    record.env_vars_json,
                )
            })
            .collect()
    }

    fn persisted_layer_rows(
        &self,
        layer_paths: Vec<String>,
    ) -> Vec<(
        String,
        String,
        Option<String>,
        Option<String>,
        Option<Vec<String>>,
        String,
        String,
        String,
        String,
        String,
    )> {
        self.layer_records
            .iter()
            .zip(layer_paths)
            .map(|(record, layer)| {
                let record = record.snapshot();
                (
                    record.uuid,
                    record.full_path,
                    record.codeuri,
                    record.build_method,
                    record.compatible_runtimes,
                    record.architecture,
                    record.source_hash,
                    record.manifest_hash,
                    record.env_vars_json,
                    layer,
                )
            })
            .collect()
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyDict>) -> Self {
        self.clone()
    }
}

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
        (full_path, codeuri, build_method, compatible_runtimes_repr, architecture, env_vars_repr),
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

type FunctionGraphInput = (
    Option<String>,
    Option<String>,
    Option<String>,
    String,
    String,
    String,
    Option<String>,
    Option<String>,
    String,
);
type LayerGraphInput = (
    String,
    Option<String>,
    Option<String>,
    String,
    String,
    String,
);
type ExistingFunctionGraphInput = (
    String,
    String,
    String,
    Option<String>,
    Option<String>,
    Option<String>,
    String,
    String,
    String,
    Option<String>,
    Option<String>,
    String,
);
type ExistingLayerGraphInput = (
    String,
    String,
    String,
    String,
    Option<String>,
    Option<String>,
    String,
    String,
    String,
);

fn json_repr(py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<String> {
    let json = py.import("json")?;
    let kwargs = PyDict::new(py);
    kwargs.set_item("sort_keys", true)?;
    kwargs.set_item("separators", (",", ":"))?;
    json.call_method("dumps", (value,), Some(&kwargs))?
        .extract()
}

fn current_function_rows_from_resources(
    py: Python<'_>,
    functions: Vec<Py<PyAny>>,
    function_env_vars: &Bound<'_, PyDict>,
) -> PyResult<Vec<FunctionGraphInput>> {
    functions
        .into_iter()
        .map(|function| {
            let function = function.bind(py);
            let metadata = function.getattr("metadata")?;
            let normalized_metadata = PyDict::new(py);
            let mut build_method = None;
            if !metadata.is_none() {
                let metadata = metadata.cast::<PyDict>()?;
                for (key, value) in metadata.iter() {
                    let key_string: String = key.extract()?;
                    if key_string == "SamResourceId" || key_string == "SamNormalized" {
                        continue;
                    }
                    if key_string == "BuildMethod" {
                        build_method = Some(value.extract()?);
                    }
                    normalized_metadata.set_item(key, value)?;
                }
            }
            let full_path: String = function.getattr("full_path")?.extract()?;
            let env_vars = function_env_vars.get_item(&full_path)?.ok_or_else(|| {
                PyOSError::new_err(format!("missing env vars for function {full_path}"))
            })?;
            Ok((
                function.getattr("runtime")?.extract()?,
                function.getattr("codeuri")?.extract()?,
                function.getattr("imageuri")?.extract()?,
                function.getattr("packagetype")?.extract()?,
                function.getattr("architecture")?.extract()?,
                json_repr(py, normalized_metadata.as_any())?,
                build_method,
                function.getattr("handler")?.extract()?,
                json_repr(py, &env_vars)?,
            ))
        })
        .collect()
}

fn current_layer_rows_from_resources(
    py: Python<'_>,
    layers: Vec<Py<PyAny>>,
    layer_env_vars: &Bound<'_, PyDict>,
) -> PyResult<Vec<LayerGraphInput>> {
    layers
        .into_iter()
        .map(|layer| {
            let layer = layer.bind(py);
            let full_path: String = layer.getattr("full_path")?.extract()?;
            let env_vars = layer_env_vars.get_item(&full_path)?.ok_or_else(|| {
                PyOSError::new_err(format!("missing env vars for layer {full_path}"))
            })?;
            let compatible_runtimes = layer.getattr("compatible_runtimes")?;
            Ok((
                full_path,
                layer.getattr("codeuri")?.extract()?,
                layer.getattr("build_method")?.extract()?,
                json_repr(py, &compatible_runtimes)?,
                layer.getattr("build_architecture")?.extract()?,
                json_repr(py, &env_vars)?,
            ))
        })
        .collect()
}

#[pyfunction]
fn current_graph_rows(
    py: Python<'_>,
    functions: Vec<Py<PyAny>>,
    function_env_vars: &Bound<'_, PyDict>,
    layers: Vec<Py<PyAny>>,
    layer_env_vars: &Bound<'_, PyDict>,
) -> PyResult<(Vec<FunctionGraphInput>, Vec<LayerGraphInput>)> {
    Ok((
        current_function_rows_from_resources(py, functions, function_env_vars)?,
        current_layer_rows_from_resources(py, layers, layer_env_vars)?,
    ))
}

#[pyfunction]
fn reconcile_graph_plan_from_resources(
    py: Python<'_>,
    functions: Vec<Py<PyAny>>,
    function_env_vars: &Bound<'_, PyDict>,
    layers: Vec<Py<PyAny>>,
    layer_env_vars: &Bound<'_, PyDict>,
    existing_function_inputs: Vec<ExistingFunctionGraphInput>,
    existing_layer_inputs: Vec<ExistingLayerGraphInput>,
) -> PyResult<RuntimeGraphPlan> {
    reconcile_graph_plan(
        current_function_rows_from_resources(py, functions, function_env_vars)?,
        current_layer_rows_from_resources(py, layers, layer_env_vars)?,
        existing_function_inputs,
        existing_layer_inputs,
    )
}

#[pyfunction]
fn plan_graph_groups_from_resources(
    py: Python<'_>,
    functions: Vec<Py<PyAny>>,
    function_env_vars: &Bound<'_, PyDict>,
    layers: Vec<Py<PyAny>>,
    layer_env_vars: &Bound<'_, PyDict>,
) -> PyResult<(Vec<Vec<usize>>, Vec<Vec<usize>>)> {
    Ok(plan_graph_groups(
        current_function_rows_from_resources(py, functions, function_env_vars)?,
        current_layer_rows_from_resources(py, layers, layer_env_vars)?,
    ))
}

#[pyfunction]
fn reconcile_graph_groups_from_resources(
    py: Python<'_>,
    functions: Vec<Py<PyAny>>,
    function_env_vars: &Bound<'_, PyDict>,
    layers: Vec<Py<PyAny>>,
    layer_env_vars: &Bound<'_, PyDict>,
    existing_function_inputs: Vec<ExistingFunctionGraphInput>,
    existing_layer_inputs: Vec<ExistingLayerGraphInput>,
) -> PyResult<(
    Vec<(Vec<usize>, Option<String>, String, String)>,
    Vec<(Vec<usize>, Option<String>, String, String)>,
)> {
    Ok(reconcile_graph_groups(
        current_function_rows_from_resources(py, functions, function_env_vars)?,
        current_layer_rows_from_resources(py, layers, layer_env_vars)?,
        existing_function_inputs,
        existing_layer_inputs,
    ))
}

#[pyfunction]
fn runtime_graph_plan_from_resource_groups(
    py: Python<'_>,
    functions: Vec<Py<PyAny>>,
    function_env_vars: &Bound<'_, PyDict>,
    layers: Vec<Py<PyAny>>,
    layer_env_vars: &Bound<'_, PyDict>,
    function_groups: Vec<(Vec<usize>, Option<String>, String, String)>,
    layer_groups: Vec<(Vec<usize>, Option<String>, String, String)>,
) -> PyResult<RuntimeGraphPlan> {
    let function_inputs = current_function_rows_from_resources(py, functions, function_env_vars)?;
    let layer_inputs = current_layer_rows_from_resources(py, layers, layer_env_vars)?;

    let (function_groups, function_records) = function_groups
        .into_iter()
        .map(|(indexes, uuid, source_hash, manifest_hash)| {
            let (
                runtime,
                codeuri,
                imageuri,
                packagetype,
                architecture,
                metadata_repr,
                _build_method,
                handler,
                env_vars_repr,
            ) = function_inputs[indexes[0]].clone();
            (
                indexes,
                RuntimeFunctionRecord::new(
                    uuid.unwrap_or_default(),
                    source_hash,
                    manifest_hash,
                    runtime,
                    codeuri,
                    imageuri,
                    packagetype,
                    architecture,
                    handler,
                    metadata_repr,
                    env_vars_repr,
                ),
            )
        })
        .unzip();

    let (layer_groups, layer_records) = layer_groups
        .into_iter()
        .map(
            |(indexes, uuid, source_hash, manifest_hash)| -> PyResult<_> {
                let (
                    full_path,
                    codeuri,
                    build_method,
                    compatible_runtimes_repr,
                    architecture,
                    env_vars_repr,
                ) = layer_inputs[indexes[0]].clone();
                Ok((
                    indexes,
                    RuntimeLayerRecord::new(
                        uuid.unwrap_or_default(),
                        source_hash,
                        manifest_hash,
                        full_path,
                        codeuri,
                        build_method,
                        serde_json::from_str(&compatible_runtimes_repr)
                            .map_err(|error| PyOSError::new_err(error.to_string()))?,
                        architecture,
                        env_vars_repr,
                    ),
                ))
            },
        )
        .collect::<PyResult<Vec<_>>>()?
        .into_iter()
        .unzip();

    Ok(RuntimeGraphPlan {
        function_groups,
        function_records,
        layer_groups,
        layer_records,
    })
}
#[pyfunction]
fn reconcile_graph_groups(
    function_inputs: Vec<FunctionGraphInput>,
    layer_inputs: Vec<LayerGraphInput>,
    existing_function_inputs: Vec<ExistingFunctionGraphInput>,
    existing_layer_inputs: Vec<ExistingLayerGraphInput>,
) -> (
    Vec<(Vec<usize>, Option<String>, String, String)>,
    Vec<(Vec<usize>, Option<String>, String, String)>,
) {
    let mut existing_functions = HashMap::<NormalizedFunctionKey, (String, String, String)>::new();
    for (
        uuid,
        source_hash,
        manifest_hash,
        runtime,
        codeuri,
        imageuri,
        packagetype,
        architecture,
        metadata_repr,
        build_method,
        handler,
        env_vars_repr,
    ) in existing_function_inputs
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
        if !key.is_never_deduped() {
            existing_functions.entry(key.normalized()).or_insert((
                uuid,
                source_hash,
                manifest_hash,
            ));
        }
    }

    let mut function_groups = Vec::<(Vec<usize>, Option<String>, String, String)>::new();
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
            function_groups.push((vec![index], None, String::new(), String::new()));
        } else {
            let normalized = key.normalized();
            if let Some(group_index) = function_group_indexes.get(&normalized) {
                function_groups[*group_index].0.push(index);
            } else {
                let retained = existing_functions.get(&normalized).cloned();
                let (uuid, source_hash, manifest_hash) = retained
                    .map(|(uuid, source_hash, manifest_hash)| {
                        (Some(uuid), source_hash, manifest_hash)
                    })
                    .unwrap_or((None, String::new(), String::new()));
                let group_index = function_groups.len();
                function_groups.push((vec![index], uuid, source_hash, manifest_hash));
                function_group_indexes.insert(normalized, group_index);
            }
        }
    }

    let mut existing_layers = HashMap::<LayerKey, (String, String, String)>::new();
    for (
        uuid,
        source_hash,
        manifest_hash,
        full_path,
        codeuri,
        build_method,
        compatible_runtimes_repr,
        architecture,
        env_vars_repr,
    ) in existing_layer_inputs
    {
        existing_layers
            .entry(LayerKey {
                full_path,
                codeuri,
                build_method,
                compatible_runtimes_repr,
                architecture,
                env_vars_repr,
            })
            .or_insert((uuid, source_hash, manifest_hash));
    }

    let mut layer_groups = Vec::<(Vec<usize>, Option<String>, String, String)>::new();
    let mut layer_group_indexes = HashMap::<LayerKey, usize>::new();
    for (
        index,
        (full_path, codeuri, build_method, compatible_runtimes_repr, architecture, env_vars_repr),
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
            layer_groups[*group_index].0 = vec![index];
        } else {
            let retained = existing_layers.get(&key).cloned();
            let (uuid, source_hash, manifest_hash) = retained
                .map(|(uuid, source_hash, manifest_hash)| (Some(uuid), source_hash, manifest_hash))
                .unwrap_or((None, String::new(), String::new()));
            let group_index = layer_groups.len();
            layer_groups.push((vec![index], uuid, source_hash, manifest_hash));
            layer_group_indexes.insert(key, group_index);
        }
    }

    (function_groups, layer_groups)
}

#[pyfunction]
fn reconcile_graph_plan(
    function_inputs: Vec<FunctionGraphInput>,
    layer_inputs: Vec<LayerGraphInput>,
    existing_function_inputs: Vec<ExistingFunctionGraphInput>,
    existing_layer_inputs: Vec<ExistingLayerGraphInput>,
) -> PyResult<RuntimeGraphPlan> {
    let (function_groups, layer_groups) = reconcile_graph_groups(
        function_inputs.clone(),
        layer_inputs.clone(),
        existing_function_inputs,
        existing_layer_inputs,
    );

    let (function_groups, function_records) = function_groups
        .into_iter()
        .map(|(indexes, uuid, source_hash, manifest_hash)| {
            let (
                runtime,
                codeuri,
                imageuri,
                packagetype,
                architecture,
                metadata_repr,
                _build_method,
                handler,
                env_vars_repr,
            ) = function_inputs[indexes[0]].clone();
            (
                indexes,
                RuntimeFunctionRecord::new(
                    uuid.unwrap_or_default(),
                    source_hash,
                    manifest_hash,
                    runtime,
                    codeuri,
                    imageuri,
                    packagetype,
                    architecture,
                    handler,
                    metadata_repr,
                    env_vars_repr,
                ),
            )
        })
        .unzip();

    let layer_plan = layer_groups
        .into_iter()
        .map(
            |(indexes, uuid, source_hash, manifest_hash)| -> PyResult<_> {
                let (
                    full_path,
                    codeuri,
                    build_method,
                    compatible_runtimes_repr,
                    architecture,
                    env_vars_repr,
                ) = layer_inputs[indexes[0]].clone();
                let compatible_runtimes = serde_json::from_str(&compatible_runtimes_repr)
                    .map_err(|error| PyOSError::new_err(error.to_string()))?;
                Ok((
                    indexes,
                    RuntimeLayerRecord::new(
                        uuid.unwrap_or_default(),
                        source_hash,
                        manifest_hash,
                        full_path,
                        codeuri,
                        build_method,
                        compatible_runtimes,
                        architecture,
                        env_vars_repr,
                    ),
                ))
            },
        )
        .collect::<PyResult<Vec<_>>>()?;
    let (layer_groups, layer_records) = layer_plan.into_iter().unzip();

    Ok(RuntimeGraphPlan {
        function_groups,
        function_records,
        layer_groups,
        layer_records,
    })
}

#[pyfunction]
fn compare_definition_hashes(
    updated_function_inputs: Vec<ExistingFunctionGraphInput>,
    existing_function_inputs: Vec<ExistingFunctionGraphInput>,
    updated_layer_inputs: Vec<ExistingLayerGraphInput>,
    existing_layer_inputs: Vec<ExistingLayerGraphInput>,
) -> (Vec<(String, String, String)>, Vec<(String, String, String)>) {
    let updated_functions = updated_function_inputs
        .into_iter()
        .filter_map(
            |(
                uuid,
                source_hash,
                manifest_hash,
                runtime,
                codeuri,
                imageuri,
                packagetype,
                architecture,
                metadata_repr,
                build_method,
                handler,
                env_vars_repr,
            )| {
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
                (!key.is_never_deduped())
                    .then(|| (key.normalized(), (uuid, source_hash, manifest_hash)))
            },
        )
        .collect::<HashMap<_, _>>();

    let function_updates = existing_function_inputs
        .into_iter()
        .filter_map(
            |(
                _uuid,
                old_source_hash,
                old_manifest_hash,
                runtime,
                codeuri,
                imageuri,
                packagetype,
                architecture,
                metadata_repr,
                build_method,
                handler,
                env_vars_repr,
            )| {
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
                    return None;
                }
                let (uuid, source_hash, manifest_hash) =
                    updated_functions.get(&key.normalized())?;
                (old_source_hash != *source_hash || old_manifest_hash != *manifest_hash)
                    .then(|| (uuid.clone(), source_hash.clone(), manifest_hash.clone()))
            },
        )
        .collect();

    let updated_layers = updated_layer_inputs
        .into_iter()
        .map(
            |(
                uuid,
                source_hash,
                manifest_hash,
                full_path,
                codeuri,
                build_method,
                compatible_runtimes_repr,
                architecture,
                env_vars_repr,
            )| {
                (
                    LayerKey {
                        full_path,
                        codeuri,
                        build_method,
                        compatible_runtimes_repr,
                        architecture,
                        env_vars_repr,
                    },
                    (uuid, source_hash, manifest_hash),
                )
            },
        )
        .collect::<HashMap<_, _>>();

    let layer_updates = existing_layer_inputs
        .into_iter()
        .filter_map(
            |(
                _uuid,
                old_source_hash,
                old_manifest_hash,
                full_path,
                codeuri,
                build_method,
                compatible_runtimes_repr,
                architecture,
                env_vars_repr,
            )| {
                let key = LayerKey {
                    full_path,
                    codeuri,
                    build_method,
                    compatible_runtimes_repr,
                    architecture,
                    env_vars_repr,
                };
                let (uuid, source_hash, manifest_hash) = updated_layers.get(&key)?;
                (old_source_hash != *source_hash || old_manifest_hash != *manifest_hash)
                    .then(|| (uuid.clone(), source_hash.clone(), manifest_hash.clone()))
            },
        )
        .collect();

    (function_updates, layer_updates)
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

#[pyfunction]
fn read_build_graph(path: &str) -> PyResult<String> {
    let graph =
        CoreBuildGraph::read(path).map_err(|error| PyOSError::new_err(error.to_string()))?;
    let function_build_definitions = graph
        .function_build_definitions
        .into_iter()
        .map(|definition| {
            serde_json::json!({
                "uuid": definition.uuid,
                "runtime": definition.runtime,
                "codeuri": definition.codeuri,
                "packagetype": definition.packagetype,
                "architecture": definition.architecture,
                "metadata": definition.metadata,
                "handler": definition.handler,
                "source_hash": definition.source_hash,
                "manifest_hash": definition.manifest_hash,
                "env_vars": definition.env_vars,
            })
        })
        .collect::<Vec<_>>();
    let layer_build_definitions = graph
        .layer_build_definitions
        .into_iter()
        .map(|definition| {
            serde_json::json!({
                "uuid": definition.uuid,
                "layer_name": definition.layer_name,
                "codeuri": definition.codeuri,
                "build_method": definition.build_method,
                "compatible_runtimes": definition.compatible_runtimes,
                "architecture": definition.architecture,
                "source_hash": definition.source_hash,
                "manifest_hash": definition.manifest_hash,
                "env_vars": definition.env_vars,
            })
        })
        .collect::<Vec<_>>();

    serde_json::to_string(&serde_json::json!({
        "function_build_definitions": function_build_definitions,
        "layer_build_definitions": layer_build_definitions,
    }))
    .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
fn read_runtime_build_graph(path: &str) -> PyResult<RuntimePersistedGraph> {
    let graph =
        CoreBuildGraph::read(path).map_err(|error| PyOSError::new_err(error.to_string()))?;
    let function_records = graph
        .function_build_definitions
        .into_iter()
        .map(|definition| {
            Ok(RuntimeFunctionRecord::new(
                definition.uuid,
                definition.source_hash,
                definition.manifest_hash,
                definition.runtime,
                definition.codeuri,
                None,
                definition.packagetype,
                definition.architecture,
                Some(definition.handler),
                serde_json::to_string(&definition.metadata)
                    .map_err(|error| PyOSError::new_err(error.to_string()))?,
                serde_json::to_string(&definition.env_vars)
                    .map_err(|error| PyOSError::new_err(error.to_string()))?,
            ))
        })
        .collect::<PyResult<Vec<_>>>()?;
    let layer_records = graph
        .layer_build_definitions
        .into_iter()
        .map(|definition| {
            Ok(RuntimeLayerRecord::new(
                definition.uuid,
                definition.source_hash,
                definition.manifest_hash,
                definition.layer_name,
                definition.codeuri,
                definition.build_method,
                definition.compatible_runtimes,
                definition.architecture,
                serde_json::to_string(&definition.env_vars)
                    .map_err(|error| PyOSError::new_err(error.to_string()))?,
            ))
        })
        .collect::<PyResult<Vec<_>>>()?;

    Ok(RuntimePersistedGraph {
        function_records,
        layer_records,
    })
}

#[pyfunction]
fn write_build_graph(path: &str, graph_json: &str) -> PyResult<()> {
    let graph: serde_json::Value =
        serde_json::from_str(graph_json).map_err(|error| PyOSError::new_err(error.to_string()))?;
    let mut persisted = toml::Table::new();
    let mut function_table = toml::Table::new();
    for definition in graph["function_build_definitions"]
        .as_array()
        .ok_or_else(|| PyOSError::new_err("function_build_definitions must be an array"))?
    {
        let uuid = required_json_str(definition, "uuid")?;
        let mut table = toml::Table::new();
        let packagetype = required_json_str(definition, "packagetype")?;
        if packagetype == "Zip" {
            insert_json_value(&mut table, "codeuri", &definition["codeuri"])?;
            insert_json_value(&mut table, "runtime", &definition["runtime"])?;
            insert_json_value(&mut table, "architecture", &definition["architecture"])?;
            insert_json_value(&mut table, "handler", &definition["handler"])?;
            if definition["source_hash"]
                .as_str()
                .is_some_and(|value| !value.is_empty())
            {
                insert_json_value(&mut table, "source_hash", &definition["source_hash"])?;
            }
            insert_json_value(&mut table, "manifest_hash", &definition["manifest_hash"])?;
        }
        table.insert(
            "packagetype".into(),
            toml::Value::String(packagetype.into()),
        );
        insert_json_value(&mut table, "functions", &definition["functions"])?;
        insert_non_empty_json_value(&mut table, "metadata", &definition["metadata"])?;
        insert_non_empty_json_value(&mut table, "env_vars", &definition["env_vars"])?;
        function_table.insert(uuid.into(), toml::Value::Table(table));
    }

    let mut layer_table = toml::Table::new();
    for definition in graph["layer_build_definitions"]
        .as_array()
        .ok_or_else(|| PyOSError::new_err("layer_build_definitions must be an array"))?
    {
        let uuid = required_json_str(definition, "uuid")?;
        let mut table = toml::Table::new();
        insert_json_value(&mut table, "layer_name", &definition["layer_name"])?;
        insert_json_value(&mut table, "codeuri", &definition["codeuri"])?;
        insert_json_value(&mut table, "build_method", &definition["build_method"])?;
        insert_json_value(
            &mut table,
            "compatible_runtimes",
            &definition["compatible_runtimes"],
        )?;
        insert_json_value(&mut table, "architecture", &definition["architecture"])?;
        if definition["source_hash"]
            .as_str()
            .is_some_and(|value| !value.is_empty())
        {
            insert_json_value(&mut table, "source_hash", &definition["source_hash"])?;
        }
        insert_json_value(&mut table, "manifest_hash", &definition["manifest_hash"])?;
        insert_non_empty_json_value(&mut table, "env_vars", &definition["env_vars"])?;
        insert_json_value(&mut table, "layer", &definition["layer"])?;
        layer_table.insert(uuid.into(), toml::Value::Table(table));
    }

    persisted.insert(
        "function_build_definitions".into(),
        toml::Value::Table(function_table),
    );
    persisted.insert(
        "layer_build_definitions".into(),
        toml::Value::Table(layer_table),
    );
    let mut text = String::from("# This file is auto generated by SAM CLI build command\n");
    text.push_str(
        &toml::to_string(&persisted).map_err(|error| PyOSError::new_err(error.to_string()))?,
    );
    std::fs::write(path, text).map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
fn write_build_graph_compact(
    path: &str,
    function_rows: Vec<(
        String,
        Option<String>,
        Option<String>,
        String,
        String,
        Option<String>,
        String,
        String,
        Vec<String>,
        String,
        String,
    )>,
    layer_rows: Vec<(
        String,
        String,
        Option<String>,
        Option<String>,
        Option<Vec<String>>,
        String,
        String,
        String,
        String,
        String,
    )>,
) -> PyResult<()> {
    let mut persisted = toml::Table::new();
    let mut function_table = toml::Table::new();
    for (
        uuid,
        runtime,
        codeuri,
        packagetype,
        architecture,
        handler,
        source_hash,
        manifest_hash,
        functions,
        metadata_json,
        env_vars_json,
    ) in function_rows
    {
        let mut table = toml::Table::new();
        if packagetype == "Zip" {
            insert_optional_string(&mut table, "codeuri", codeuri);
            insert_optional_string(&mut table, "runtime", runtime);
            table.insert("architecture".into(), toml::Value::String(architecture));
            insert_optional_string(&mut table, "handler", handler);
            if !source_hash.is_empty() {
                table.insert("source_hash".into(), toml::Value::String(source_hash));
            }
            table.insert("manifest_hash".into(), toml::Value::String(manifest_hash));
        }
        table.insert("packagetype".into(), toml::Value::String(packagetype));
        table.insert(
            "functions".into(),
            toml::Value::Array(functions.into_iter().map(toml::Value::String).collect()),
        );
        insert_json_object_if_non_empty(&mut table, "metadata", &metadata_json)?;
        insert_json_object_if_non_empty(&mut table, "env_vars", &env_vars_json)?;
        function_table.insert(uuid, toml::Value::Table(table));
    }

    let mut layer_table = toml::Table::new();
    for (
        uuid,
        layer_name,
        codeuri,
        build_method,
        compatible_runtimes,
        architecture,
        source_hash,
        manifest_hash,
        env_vars_json,
        layer,
    ) in layer_rows
    {
        let mut table = toml::Table::new();
        table.insert("layer_name".into(), toml::Value::String(layer_name));
        insert_optional_string(&mut table, "codeuri", codeuri);
        insert_optional_string(&mut table, "build_method", build_method);
        if let Some(compatible_runtimes) = compatible_runtimes {
            table.insert(
                "compatible_runtimes".into(),
                toml::Value::Array(
                    compatible_runtimes
                        .into_iter()
                        .map(toml::Value::String)
                        .collect(),
                ),
            );
        }
        table.insert("architecture".into(), toml::Value::String(architecture));
        if !source_hash.is_empty() {
            table.insert("source_hash".into(), toml::Value::String(source_hash));
        }
        table.insert("manifest_hash".into(), toml::Value::String(manifest_hash));
        insert_json_object_if_non_empty(&mut table, "env_vars", &env_vars_json)?;
        table.insert("layer".into(), toml::Value::String(layer));
        layer_table.insert(uuid, toml::Value::Table(table));
    }

    persisted.insert(
        "function_build_definitions".into(),
        toml::Value::Table(function_table),
    );
    persisted.insert(
        "layer_build_definitions".into(),
        toml::Value::Table(layer_table),
    );
    let mut text = String::from("# This file is auto generated by SAM CLI build command\n");
    text.push_str(
        &toml::to_string(&persisted).map_err(|error| PyOSError::new_err(error.to_string()))?,
    );
    std::fs::write(path, text).map_err(|error| PyOSError::new_err(error.to_string()))
}

fn insert_optional_string(table: &mut toml::Table, key: &str, value: Option<String>) {
    if let Some(value) = value {
        table.insert(key.into(), toml::Value::String(value));
    }
}

fn insert_json_object_if_non_empty(table: &mut toml::Table, key: &str, json: &str) -> PyResult<()> {
    let value: serde_json::Value =
        serde_json::from_str(json).map_err(|error| PyOSError::new_err(error.to_string()))?;
    insert_non_empty_json_value(table, key, &value)
}

fn required_json_str<'a>(value: &'a serde_json::Value, key: &str) -> PyResult<&'a str> {
    value[key]
        .as_str()
        .ok_or_else(|| PyOSError::new_err(format!("{key} must be a string")))
}

fn insert_json_value(
    table: &mut toml::Table,
    key: &str,
    value: &serde_json::Value,
) -> PyResult<()> {
    if value.is_null() {
        return Ok(());
    }
    table.insert(
        key.into(),
        toml::Value::try_from(value.clone())
            .map_err(|error| PyOSError::new_err(error.to_string()))?,
    );
    Ok(())
}

fn insert_non_empty_json_value(
    table: &mut toml::Table,
    key: &str,
    value: &serde_json::Value,
) -> PyResult<()> {
    if value.as_object().is_some_and(serde_json::Map::is_empty) {
        return Ok(());
    }
    insert_json_value(table, key, value)
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

#[pyfunction]
fn create_package_zip(
    output_base_path: &str,
    source_root: &str,
    lambda_permissions: bool,
) -> PyResult<String> {
    let zip_path = core_create_package_zip(output_base_path, source_root, lambda_permissions)
        .map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok(zip_path.to_string_lossy().into_owned())
}

#[pyfunction]
fn create_package_zip_with_md5(
    output_base_path: &str,
    source_root: &str,
    lambda_permissions: bool,
) -> PyResult<(String, String)> {
    let (zip_path, md5) = core_create_package_zip_with_md5(output_base_path, source_root, lambda_permissions)
        .map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok((zip_path.to_string_lossy().into_owned(), md5))
}

#[pyfunction]
fn create_lambda_zip_with_sha256(
    output_base_path: &str,
    source_root: &str,
) -> PyResult<(String, String)> {
    let (zip_path, sha256) = core_create_lambda_zip_with_sha256(output_base_path, source_root)
        .map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok((zip_path.to_string_lossy().into_owned(), sha256))
}

#[pyfunction]
fn sha256_file_checksum(path: &str) -> PyResult<String> {
    core_file_checksum(path, HashAlgorithm::Sha256)
        .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
fn md5_file_checksum(path: &str) -> PyResult<String> {
    core_file_checksum(path, HashAlgorithm::Md5)
        .map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
fn write_sync_state_compact(
    path: &str,
    dependency_layer: bool,
    latest_infra_sync_time: Option<f64>,
    resource_rows: Vec<(String, String, f64)>,
) -> PyResult<()> {
    let resource_sync_states = resource_rows
        .into_iter()
        .map(|(resource_id, hash, sync_time)| {
            (
                resource_id.replace('/', "-"),
                ResourceSyncStateSection { hash, sync_time },
            )
        })
        .collect();
    let state = SyncStateDocument {
        sync_state: SyncStateSection {
            dependency_layer,
            latest_infra_sync_time,
        },
        resource_sync_states,
    };
    core_write_sync_state(path, &state).map_err(|error| PyOSError::new_err(error.to_string()))
}

#[pyfunction]
fn read_sync_state_compact(
    path: &str,
) -> PyResult<Option<(bool, Option<f64>, Vec<(String, String, f64)>)>> {
    let state =
        core_read_sync_state(path).map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok(state.map(|state| {
        (
            state.dependency_layer,
            state.latest_infra_sync_time,
            state.resource_sync_states,
        )
    }))
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeSyncState {
    dependency_layer: bool,
    latest_infra_sync_time: Option<f64>,
    resource_sync_states: BTreeMap<String, (String, f64)>,
}

impl RuntimeSyncState {
    fn document(&self) -> SyncStateDocument {
        SyncStateDocument {
            sync_state: SyncStateSection {
                dependency_layer: self.dependency_layer,
                latest_infra_sync_time: self.latest_infra_sync_time,
            },
            resource_sync_states: self
                .resource_sync_states
                .iter()
                .map(|(resource_id, (hash, sync_time))| {
                    (
                        resource_id.replace('/', "-"),
                        ResourceSyncStateSection {
                            hash: hash.clone(),
                            sync_time: *sync_time,
                        },
                    )
                })
                .collect(),
        }
    }
}

#[pymethods]
impl RuntimeSyncState {
    #[new]
    fn new(
        dependency_layer: bool,
        latest_infra_sync_time: Option<f64>,
        resource_rows: Vec<(String, String, f64)>,
    ) -> Self {
        Self {
            dependency_layer,
            latest_infra_sync_time,
            resource_sync_states: resource_rows
                .into_iter()
                .map(|(resource_id, hash, sync_time)| (resource_id, (hash, sync_time)))
                .collect(),
        }
    }

    #[getter]
    fn dependency_layer(&self) -> bool {
        self.dependency_layer
    }

    #[getter]
    fn latest_infra_sync_time(&self) -> Option<f64> {
        self.latest_infra_sync_time
    }

    fn resource_rows(&self) -> Vec<(String, String, f64)> {
        self.resource_sync_states
            .iter()
            .map(|(resource_id, (hash, sync_time))| (resource_id.clone(), hash.clone(), *sync_time))
            .collect()
    }

    fn get_resource_latest_sync_hash(&self, resource_id: &str) -> Option<String> {
        self.resource_sync_states
            .get(resource_id)
            .map(|(hash, _)| hash.clone())
    }

    fn update_resource_sync_state(&mut self, resource_id: String, hash: String, sync_time: f64) {
        self.resource_sync_states
            .insert(resource_id, (hash, sync_time));
    }

    fn update_infra_sync_time(&mut self, sync_time: f64) {
        self.latest_infra_sync_time = Some(sync_time);
    }

    fn write(&self, path: &str) -> PyResult<()> {
        core_write_sync_state(path, &self.document())
            .map_err(|error| PyOSError::new_err(error.to_string()))
    }
}

#[pyfunction]
fn read_runtime_sync_state(path: &str) -> PyResult<Option<RuntimeSyncState>> {
    let state =
        core_read_sync_state(path).map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok(state.map(|state| RuntimeSyncState {
        dependency_layer: state.dependency_layer,
        latest_infra_sync_time: state.latest_infra_sync_time,
        resource_sync_states: state
            .resource_sync_states
            .into_iter()
            .map(|(resource_id, hash, sync_time)| (resource_id, (hash, sync_time)))
            .collect(),
    }))
}

#[pyclass(skip_from_py_object)]
#[derive(Clone)]
struct RuntimeResourceTypeIndex {
    index: CoreResourceTypeIndex,
}

#[pymethods]
impl RuntimeResourceTypeIndex {
    #[new]
    fn new(rows: Vec<(String, String, String, Option<String>)>) -> Self {
        Self {
            index: CoreResourceTypeIndex::new(
                rows.into_iter()
                    .map(
                        |(stack_path, logical_id, resource_id, resource_type)| ResourceTypeRow {
                            stack_path,
                            logical_id,
                            resource_id,
                            resource_type,
                        },
                    )
                    .collect(),
            ),
        }
    }

    fn get_resource_type(&self, resource_identifier: &str) -> Option<String> {
        self.index.get_resource_type(resource_identifier)
    }
}

#[pyfunction]
fn dependent_function_ids(
    layer_identifier: &str,
    function_layer_rows: Vec<(String, Vec<String>)>,
) -> Vec<String> {
    core_dependent_function_ids(layer_identifier, function_layer_rows)
}

#[pyfunction]
fn read_definition_bytes_with_sha256(path: &str) -> PyResult<(Vec<u8>, String)> {
    let definition = core_read_definition_bytes_with_sha256(path)
        .map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok((definition.bytes, definition.sha256))
}

#[pyfunction]
fn read_definition_text_with_sha256(path: &str) -> PyResult<(String, String)> {
    let definition = core_read_definition_text_with_sha256(path)
        .map_err(|error| PyOSError::new_err(error.to_string()))?;
    Ok((definition.text, definition.sha256))
}

#[pyfunction]
fn function_resource_api_call_rows(
    function_identifier: &str,
    layer_ids: Vec<String>,
    codeuri: Option<String>,
    auto_publish_latest_invocable: bool,
) -> Vec<(String, Vec<String>)> {
    core_function_resource_api_call_rows(
        function_identifier,
        layer_ids,
        codeuri,
        auto_publish_latest_invocable,
    )
}

#[pyfunction]
fn lock_keys_from_api_call_rows(resource_api_call_rows: Vec<(String, Vec<String>)>) -> Vec<String> {
    core_lock_keys_from_api_call_rows(resource_api_call_rows)
}

#[pyfunction]
fn collect_rest_api_stage_names(
    api_identifier: &str,
    api_resource_type: Option<String>,
    api_stage_name: Option<String>,
    remote_stage_names: Vec<String>,
    stage_rows: Vec<(Option<String>, Option<String>, Option<String>)>,
    deployment_resource_ids: Vec<String>,
) -> Vec<String> {
    core_collect_rest_api_stage_names(
        api_identifier,
        api_resource_type,
        api_stage_name,
        remote_stage_names,
        stage_rows,
        deployment_resource_ids,
    )
}

#[pyfunction]
fn local_hash_matches(local_hash: Option<String>, stored_hash: Option<String>) -> bool {
    core_local_hash_matches(local_hash.as_deref(), stored_hash.as_deref())
}

#[pyfunction]
fn sync_execution_decision(local_matches: bool, remote_matches: Option<bool>) -> (bool, bool) {
    let decision = core_sync_execution_decision(local_matches, remote_matches);
    (decision.compare_remote, decision.sync)
}

#[pymodule]
fn _sam_build_core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<RuntimeDefinitionRecord>()?;
    module.add_class::<RuntimeFunctionRecord>()?;
    module.add_class::<RuntimeLayerRecord>()?;
    module.add_class::<RuntimeGraphPlan>()?;
    module.add_class::<RuntimePersistedGraph>()?;
    module.add_class::<RuntimeBuildGraphState>()?;
    module.add_class::<RuntimeSyncState>()?;
    module.add_class::<RuntimeResourceTypeIndex>()?;
    module.add_function(wrap_pyfunction!(sha256_dir_checksum, module)?)?;
    module.add_function(wrap_pyfunction!(md5_dir_checksum, module)?)?;
    module.add_function(wrap_pyfunction!(plan_build, module)?)?;
    module.add_function(wrap_pyfunction!(batch_plan_builds, module)?)?;
    module.add_function(wrap_pyfunction!(batch_plan_modes, module)?)?;
    module.add_function(wrap_pyfunction!(dedupe_function_specs, module)?)?;
    module.add_function(wrap_pyfunction!(dedupe_layer_specs, module)?)?;
    module.add_function(wrap_pyfunction!(current_graph_rows, module)?)?;
    module.add_function(wrap_pyfunction!(plan_graph_groups, module)?)?;
    module.add_function(wrap_pyfunction!(plan_graph_groups_from_resources, module)?)?;
    module.add_function(wrap_pyfunction!(reconcile_graph_groups, module)?)?;
    module.add_function(wrap_pyfunction!(
        reconcile_graph_groups_from_resources,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(reconcile_graph_plan, module)?)?;
    module.add_function(wrap_pyfunction!(
        reconcile_graph_plan_from_resources,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(
        runtime_graph_plan_from_resource_groups,
        module
    )?)?;
    module.add_function(wrap_pyfunction!(compare_definition_hashes, module)?)?;
    module.add_function(wrap_pyfunction!(write_hash_updates, module)?)?;
    module.add_function(wrap_pyfunction!(read_build_graph, module)?)?;
    module.add_function(wrap_pyfunction!(read_runtime_build_graph, module)?)?;
    module.add_function(wrap_pyfunction!(write_build_graph, module)?)?;
    module.add_function(wrap_pyfunction!(write_build_graph_compact, module)?)?;
    module.add_function(wrap_pyfunction!(remove_redundant_folders, module)?)?;
    module.add_function(wrap_pyfunction!(create_package_zip, module)?)?;
    module.add_function(wrap_pyfunction!(create_package_zip_with_md5, module)?)?;
    module.add_function(wrap_pyfunction!(create_lambda_zip_with_sha256, module)?)?;
    module.add_function(wrap_pyfunction!(sha256_file_checksum, module)?)?;
    module.add_function(wrap_pyfunction!(md5_file_checksum, module)?)?;
    module.add_function(wrap_pyfunction!(write_sync_state_compact, module)?)?;
    module.add_function(wrap_pyfunction!(read_sync_state_compact, module)?)?;
    module.add_function(wrap_pyfunction!(read_runtime_sync_state, module)?)?;
    module.add_function(wrap_pyfunction!(dependent_function_ids, module)?)?;
    module.add_function(wrap_pyfunction!(read_definition_bytes_with_sha256, module)?)?;
    module.add_function(wrap_pyfunction!(read_definition_text_with_sha256, module)?)?;
    module.add_function(wrap_pyfunction!(function_resource_api_call_rows, module)?)?;
    module.add_function(wrap_pyfunction!(lock_keys_from_api_call_rows, module)?)?;
    module.add_function(wrap_pyfunction!(collect_rest_api_stage_names, module)?)?;
    module.add_function(wrap_pyfunction!(local_hash_matches, module)?)?;
    module.add_function(wrap_pyfunction!(sync_execution_decision, module)?)?;
    Ok(())
}
