use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use uuid::Uuid;

pub const ZIP: &str = "Zip";
const COMPILED_RUNTIMES: &[&str] = &["go1.x"];

pub type Metadata = BTreeMap<String, toml::Value>;
pub type EnvVars = BTreeMap<String, String>;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FunctionBuildDefinition {
    #[serde(default = "new_uuid", skip_serializing)]
    pub uuid: String,
    pub runtime: Option<String>,
    pub codeuri: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub imageuri: Option<String>,
    #[serde(default = "default_packagetype")]
    pub packagetype: String,
    #[serde(default = "default_architecture")]
    pub architecture: String,
    #[serde(default)]
    pub metadata: Metadata,
    #[serde(default)]
    pub handler: String,
    #[serde(default)]
    pub source_hash: String,
    #[serde(default)]
    pub manifest_hash: String,
    #[serde(default)]
    pub env_vars: EnvVars,
    #[serde(default)]
    pub functions: Vec<String>,
    #[serde(skip, default = "default_true")]
    pub download_dependencies: bool,
}

impl FunctionBuildDefinition {
    pub fn equivalent_for_build(&self, other: &Self) -> bool {
        if self.build_method() == Some("makefile") {
            return false;
        }

        if self.build_method() == Some("esbuild") && self.handler != other.handler {
            return false;
        }

        if self
            .runtime
            .as_deref()
            .is_some_and(|runtime| COMPILED_RUNTIMES.contains(&runtime))
            && self.handler != other.handler
        {
            return false;
        }

        self.runtime == other.runtime
            && self.codeuri == other.codeuri
            && self.imageuri == other.imageuri
            && self.packagetype == other.packagetype
            && self.metadata == other.metadata
            && self.env_vars == other.env_vars
            && self.architecture == other.architecture
    }

    pub fn build_method(&self) -> Option<&str> {
        self.metadata
            .get("BuildMethod")
            .and_then(toml::Value::as_str)
    }

    pub fn add_function(&mut self, full_path: impl Into<String>) {
        self.functions.push(full_path.into());
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LayerBuildDefinition {
    #[serde(default = "new_uuid", skip_serializing)]
    pub uuid: String,
    pub layer_name: String,
    pub codeuri: Option<String>,
    pub build_method: Option<String>,
    pub compatible_runtimes: Option<Vec<String>>,
    #[serde(default = "default_architecture")]
    pub architecture: String,
    #[serde(default)]
    pub source_hash: String,
    #[serde(default)]
    pub manifest_hash: String,
    #[serde(default)]
    pub env_vars: EnvVars,
    #[serde(default)]
    pub layer: String,
    #[serde(skip, default = "default_true")]
    pub download_dependencies: bool,
}

impl LayerBuildDefinition {
    pub fn equivalent_for_build(&self, other: &Self) -> bool {
        self.layer_name == other.layer_name
            && self.codeuri == other.codeuri
            && self.build_method == other.build_method
            && self.compatible_runtimes == other.compatible_runtimes
            && self.env_vars == other.env_vars
            && self.architecture == other.architecture
    }
}

fn new_uuid() -> String {
    Uuid::new_v4().to_string()
}

fn default_packagetype() -> String {
    ZIP.to_owned()
}

fn default_architecture() -> String {
    "x86_64".to_owned()
}

fn default_true() -> bool {
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn function() -> FunctionBuildDefinition {
        FunctionBuildDefinition {
            uuid: "uuid".into(),
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
            functions: vec![],
            download_dependencies: true,
        }
    }

    #[test]
    fn makefile_definitions_are_never_deduped() {
        let mut left = function();
        left.metadata
            .insert("BuildMethod".into(), toml::Value::String("makefile".into()));
        assert!(!left.equivalent_for_build(&left.clone()));
    }

    #[test]
    fn esbuild_requires_matching_handlers() {
        let mut left = function();
        let mut right = function();
        left.metadata
            .insert("BuildMethod".into(), toml::Value::String("esbuild".into()));
        right.metadata = left.metadata.clone();
        right.handler = "other.handler".into();
        assert!(!left.equivalent_for_build(&right));
    }

    #[test]
    fn go_requires_matching_handlers() {
        let mut left = function();
        let mut right = function();
        left.runtime = Some("go1.x".into());
        right.runtime = Some("go1.x".into());
        right.handler = "other".into();
        assert!(!left.equivalent_for_build(&right));
    }
}
