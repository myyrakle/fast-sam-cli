#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResourceTypeRow {
    pub stack_path: String,
    pub logical_id: String,
    pub resource_id: String,
    pub resource_type: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct ResourceTypeIndex {
    rows: Vec<ResourceTypeRow>,
}

impl ResourceTypeIndex {
    pub fn new(rows: Vec<ResourceTypeRow>) -> Self {
        Self { rows }
    }

    pub fn get_resource_type(&self, resource_identifier: &str) -> Option<String> {
        let (stack_path, resource_iac_id) = parse_resource_identifier(resource_identifier);
        let search_all_stacks = stack_path.is_empty();

        for row in &self.rows {
            if row.stack_path == stack_path || search_all_stacks {
                if row.resource_id == resource_iac_id
                    || (stack_path.is_empty() && row.logical_id == resource_iac_id)
                {
                    return row.resource_type.clone();
                }
            }
        }

        None
    }
}

pub fn dependent_function_ids(
    layer_identifier: &str,
    function_layer_rows: Vec<(String, Vec<String>)>,
) -> Vec<String> {
    function_layer_rows
        .into_iter()
        .filter_map(|(function_id, layer_ids)| {
            if layer_ids
                .iter()
                .any(|layer_id| layer_id == layer_identifier)
            {
                Some(function_id)
            } else {
                None
            }
        })
        .collect()
}

pub fn function_resource_api_call_rows(
    function_identifier: &str,
    layer_ids: Vec<String>,
    codeuri: Option<String>,
    auto_publish_latest_invocable: bool,
) -> Vec<(String, Vec<String>)> {
    let mut rows = Vec::new();

    rows.extend(
        layer_ids
            .into_iter()
            .map(|layer_id| (layer_id, vec!["Build".to_string()])),
    );

    if let Some(codeuri) = codeuri {
        if !codeuri.is_empty() {
            rows.push((codeuri, vec!["Build".to_string()]));
        }
    }

    let mut function_api_calls = vec![
        "UpdateFunctionCode".to_string(),
        "UpdateFunctionConfiguration".to_string(),
    ];
    if auto_publish_latest_invocable {
        function_api_calls.push("PublishVersion".to_string());
    }
    rows.push((function_identifier.to_string(), function_api_calls));

    rows
}

pub fn lock_keys_from_api_call_rows(
    resource_api_call_rows: Vec<(String, Vec<String>)>,
) -> Vec<String> {
    let mut lock_keys = Vec::new();

    for (resource, api_calls) in resource_api_call_rows {
        for api_call in api_calls {
            lock_keys.push(format!("{resource}_{api_call}"));
        }
    }

    lock_keys
}

pub fn collect_rest_api_stage_names(
    api_identifier: &str,
    api_resource_type: Option<String>,
    api_stage_name: Option<String>,
    remote_stage_names: Vec<String>,
    stage_rows: Vec<(Option<String>, Option<String>, Option<String>)>,
    deployment_resource_ids: Vec<String>,
) -> Vec<String> {
    let mut stages = Vec::new();

    if api_resource_type.as_deref() == Some("AWS::Serverless::Api") {
        if let Some(stage_name) = api_stage_name {
            push_unique(&mut stages, stage_name.clone());
            if stage_name != "Stage" && remote_stage_names.iter().any(|stage| stage == "Stage") {
                push_unique(&mut stages, "Stage".to_string());
            }
        } else if remote_stage_names.iter().any(|stage| stage == "Stage") {
            push_unique(&mut stages, "Stage".to_string());
        }
    }

    for (stage_name, rest_api_id, deployment_id) in stage_rows {
        let Some(deployment_id) = deployment_id else {
            continue;
        };
        let Some(rest_api_id) = rest_api_id else {
            continue;
        };
        if rest_api_id == api_identifier
            && deployment_resource_ids
                .iter()
                .any(|resource_id| resource_id == &deployment_id)
        {
            if let Some(stage_name) = stage_name {
                push_unique(&mut stages, stage_name);
            }
        }
    }

    stages
}

pub fn local_hash_matches(local_hash: Option<&str>, stored_hash: Option<&str>) -> bool {
    match (local_hash, stored_hash) {
        (Some(local_hash), Some(stored_hash))
            if !local_hash.is_empty() && !stored_hash.is_empty() =>
        {
            local_hash == stored_hash
        }
        _ => false,
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SyncExecutionDecision {
    pub compare_remote: bool,
    pub sync: bool,
}

pub fn sync_execution_decision(
    local_matches: bool,
    remote_matches: Option<bool>,
) -> SyncExecutionDecision {
    if local_matches {
        return SyncExecutionDecision {
            compare_remote: false,
            sync: false,
        };
    }

    match remote_matches {
        None => SyncExecutionDecision {
            compare_remote: true,
            sync: false,
        },
        Some(true) => SyncExecutionDecision {
            compare_remote: false,
            sync: false,
        },
        Some(false) => SyncExecutionDecision {
            compare_remote: false,
            sync: true,
        },
    }
}

fn push_unique(values: &mut Vec<String>, value: String) {
    if !values.iter().any(|existing| existing == &value) {
        values.push(value);
    }
}

fn parse_resource_identifier(resource_identifier: &str) -> (&str, &str) {
    resource_identifier
        .rsplit_once('/')
        .unwrap_or(("", resource_identifier))
}

#[cfg(test)]
mod tests {
    use super::{
        collect_rest_api_stage_names, dependent_function_ids, function_resource_api_call_rows,
        local_hash_matches, lock_keys_from_api_call_rows, sync_execution_decision,
        SyncExecutionDecision,
    };
    use super::{ResourceTypeIndex, ResourceTypeRow};

    #[test]
    fn finds_root_resource_by_logical_id() {
        let index = ResourceTypeIndex::new(vec![ResourceTypeRow {
            stack_path: "".into(),
            logical_id: "LogicalFn".into(),
            resource_id: "CustomerFn".into(),
            resource_type: Some("AWS::Serverless::Function".into()),
        }]);

        assert_eq!(
            index.get_resource_type("LogicalFn").as_deref(),
            Some("AWS::Serverless::Function")
        );
    }

    #[test]
    fn finds_resource_by_normalized_resource_id_across_stacks() {
        let index = ResourceTypeIndex::new(vec![
            ResourceTypeRow {
                stack_path: "".into(),
                logical_id: "RootLogical".into(),
                resource_id: "SharedId".into(),
                resource_type: Some("RootType".into()),
            },
            ResourceTypeRow {
                stack_path: "Child".into(),
                logical_id: "ChildLogical".into(),
                resource_id: "ChildId".into(),
                resource_type: Some("ChildType".into()),
            },
        ]);

        assert_eq!(
            index.get_resource_type("Child/ChildId").as_deref(),
            Some("ChildType")
        );
        assert_eq!(
            index.get_resource_type("SharedId").as_deref(),
            Some("RootType")
        );
    }

    #[test]
    fn stops_on_matching_resource_with_invalid_type() {
        let index = ResourceTypeIndex::new(vec![ResourceTypeRow {
            stack_path: "".into(),
            logical_id: "Thing".into(),
            resource_id: "Thing".into(),
            resource_type: None,
        }]);

        assert_eq!(index.get_resource_type("Thing"), None);
    }

    #[test]
    fn filters_dependent_function_ids_in_input_order() {
        assert_eq!(
            dependent_function_ids(
                "SharedLayer",
                vec![
                    ("FunctionA".into(), vec!["OtherLayer".into()]),
                    ("FunctionB".into(), vec!["SharedLayer".into()]),
                    (
                        "Nested/FunctionC".into(),
                        vec!["Nested/Layer".into(), "SharedLayer".into()],
                    ),
                ],
            ),
            vec!["FunctionB".to_string(), "Nested/FunctionC".to_string()]
        );
    }

    #[test]
    fn creates_function_resource_api_call_rows() {
        assert_eq!(
            function_resource_api_call_rows(
                "Function",
                vec!["LayerA".into(), "LayerB".into()],
                Some("CodeUri/".into()),
                true,
            ),
            vec![
                ("LayerA".into(), vec!["Build".into()]),
                ("LayerB".into(), vec!["Build".into()]),
                ("CodeUri/".into(), vec!["Build".into()]),
                (
                    "Function".into(),
                    vec![
                        "UpdateFunctionCode".into(),
                        "UpdateFunctionConfiguration".into(),
                        "PublishVersion".into(),
                    ],
                ),
            ]
        );
    }

    #[test]
    fn creates_lock_keys_from_api_call_rows() {
        assert_eq!(
            lock_keys_from_api_call_rows(vec![
                ("Layer".into(), vec!["Build".into()]),
                (
                    "Function".into(),
                    vec![
                        "UpdateFunctionCode".into(),
                        "UpdateFunctionConfiguration".into()
                    ],
                ),
            ]),
            vec![
                "Layer_Build".to_string(),
                "Function_UpdateFunctionCode".to_string(),
                "Function_UpdateFunctionConfiguration".to_string(),
            ]
        );
    }

    #[test]
    fn collects_rest_api_stage_names_from_sam_api_and_stage_resources() {
        assert_eq!(
            collect_rest_api_stage_names(
                "Api1",
                Some("AWS::Serverless::Api".into()),
                Some("beta".into()),
                vec!["Stage".into()],
                vec![
                    (
                        Some("prod".into()),
                        Some("Api1".into()),
                        Some("Deployment1".into())
                    ),
                    (
                        Some("other".into()),
                        Some("OtherApi".into()),
                        Some("Deployment1".into())
                    ),
                ],
                vec!["Deployment1".into()],
            ),
            vec!["beta".to_string(), "Stage".to_string(), "prod".to_string()]
        );
    }

    #[test]
    fn compares_local_and_stored_hashes() {
        assert!(local_hash_matches(Some("hash"), Some("hash")));
        assert!(!local_hash_matches(Some("hash"), Some("other")));
        assert!(!local_hash_matches(None, Some("hash")));
        assert!(!local_hash_matches(Some("hash"), None));
        assert!(!local_hash_matches(Some(""), Some("")));
    }

    #[test]
    fn plans_sync_execution_decision() {
        assert_eq!(
            sync_execution_decision(true, None),
            SyncExecutionDecision {
                compare_remote: false,
                sync: false
            }
        );
        assert_eq!(
            sync_execution_decision(false, None),
            SyncExecutionDecision {
                compare_remote: true,
                sync: false
            }
        );
        assert_eq!(
            sync_execution_decision(false, Some(true)),
            SyncExecutionDecision {
                compare_remote: false,
                sync: false
            }
        );
        assert_eq!(
            sync_execution_decision(false, Some(false)),
            SyncExecutionDecision {
                compare_remote: false,
                sync: true
            }
        );
    }
}
