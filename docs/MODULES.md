# Modules

This document outlines the core modules of the COMPASS project.

## `.\assurance\compass_assure.py`
**Classes:**
- `AssuranceRunner`
**Functions:**
- `main`
- `__init__`
- `_collect_environment`
- `_run_stage`
- `_should_run`
- `run`

## `.\assurance\finding_schema.py`
**Classes:**
- `Severity`
- `Confidence`
- `FindingStatus`
- `Finding`
- `FindingRegistry`
**Functions:**
- `__init__`
- `_load`
- `_save`
- `_gen_id`
- `add`
- `update_status`
- `get_all`
- `get_by_severity`
- `get_open`
- `summary`

## `.\assurance\inventory_builder.py`
**Functions:**
- `discover_python_files`
- `discover_js_files`
- `discover_api_endpoints`
- `discover_sse_endpoints`
- `discover_python_dependencies`
- `discover_node_dependencies`
- `discover_dangerous_patterns`
- `build_attack_surface`
- `build_inventory`

## `.\assurance\populate_findings.py`
**Functions:**
- `main`

## `.\assurance\real_product_harness.py`
**Classes:**
- `ExternalWindowsObserver`
- `RealProductManager`
**Functions:**
- `get_foreground_window_title`
- `find_windows_by_title_substring`
- `is_process_running`
- `get_process_pids`
- `terminate_processes_by_name`
- `inspect_notepad_text`
- `__init__`
- `is_backend_live`
- `is_frontend_live`
- `ensure_live_product`
- `_free_stale_ports`
- `teardown`
- `enum_windows_callback`
- `_enum_child`

## `.\assurance\real_product_suite.py`
**Classes:**
- `RealProductTester`
**Functions:**
- `__init__`
- `_record_result`
- `test_suite_1_normal_workflow_notepad`
- `test_suite_2_emergency_stop_verification`
- `test_suite_3_controlled_failure_disappearing_window`
- `test_suite_4_adversarial_break_and_fuzzing`
- `test_suite_5_long_run_loop_memory_bounds`
- `run_all`

## `.\assurance\tools\api_security_tester.py`
**Functions:**
- `is_api_running`
- `fetch_openapi_schema`
- `test_malformed_json_body`
- `test_missing_fields`
- `test_invalid_types`
- `test_http_methods`
- `test_security_headers`
- `run_api_security_tests`

## `.\assurance\tools\dependency_scanner.py`
**Functions:**
- `run_pip_audit`
- `run_npm_audit`
- `run_dependency_scan`

## `.\assurance\tools\release_gate.py`
**Functions:**
- `load_json`
- `evaluate_gate`

## `.\assurance\tools\sast_runner.py`
**Functions:**
- `check_bandit_installed`
- `install_bandit`
- `run_bandit`
- `run_sast`

## `.\assurance\tools\secret_scanner.py`
**Functions:**
- `scrub_all_secrets`
- `is_dummy_or_test`
- `scan_file`
- `scan_repository`

## `.\automation\action_dispatcher.py`
**Classes:**
- `MOUSEINPUT`
- `KEYBDINPUT`
- `HARDWAREINPUT`
- `_INPUT_UNION`
- `INPUT`
**Functions:**
- `_send_vk`
- `_send_unicode_char`
- `_get_uia_element`
- `_find_uia_element_by_runtime_id`
- `click_element`
- `type_text`
- `send_key`
- `focus_element`
- `double_click_element`
- `right_click_element`
- `move_cursor`
- `scroll_element`
- `send_key_combination`
- `highlight_element`
- `dispatch_click`
- `dispatch_type`
- `dispatch_focus`
- `dispatch_double_click`
- `dispatch_right_click`
- `dispatch_scroll`
- `dispatch_key_combination`
- `dispatch_highlight`
- `_walk`

## `.\automation\action_log.py`
**Functions:**
- `ensure_action_log_table`
- `log_action`
- `get_recent_logs`

## `.\automation\action_validator.py`
**Classes:**
- `ActionValidator`
**Functions:**
- `__init__`
- `validate_click`
- `validate_type`
- `validate_key`
- `validate_focus`
- `_validate_element_action`

## `.\automation\browser_adapter.py`
**Classes:**
- `BrowserActionResult`
- `AccessibilityNode`
- `BrowserAdapter`
**Functions:**
- `_check_playwright`
- `is_available`
- `to_dict`
- `to_dict`
- `__init__`
- `is_running`
- `start`
- `stop`
- `_check_url_safety`
- `navigate`
- `get_accessibility_tree`
- `find_element`
- `click_element`
- `type_text`
- `get_page_text`
- `take_screenshot`
- `evaluate_js`

## `.\automation\mcp_tools.py`
**Classes:**
- `ToolPermission`
- `ToolSchema`
- `ToolResult`
- `CompassToolRegistry`
**Functions:**
- `create_default_tools`
- `_handle_inspect_ui`
- `_handle_get_ui_state`
- `_handle_find_element`
- `_handle_read_text`
- `_handle_take_screenshot`
- `_handle_get_window_state`
- `_handle_verify_state`
- `_handle_click_element`
- `_handle_type_text`
- `_handle_press_key`
- `_handle_navigate_browser`
- `get_tool_registry`
- `to_dict`
- `to_dict`
- `__init__`
- `register`
- `list_tools`
- `get_tool_schema`
- `validate_parameters`
- `invoke`
- `_log_invocation`
- `get_invocation_log`

## `.\automation\models.py`
**Classes:**
- `ActionType`
- `ExecutionMethod`
- `ValidationResult`
- `ActionResult`
**Functions:**
- `to_dict`
- `to_dict`

## `.\automation\safety.py`
**Classes:**
- `SafetyManager`
**Functions:**
- `_get_window_class`
- `_is_window`
- `_is_window_visible`
- `check_protected_window_class`
- `check_hwnd_safe`
- `check_foreground_context`
- `check_key_safe`
- `check_text_safe`
- `check_element_actionable`
- `check_control_type_for_action`
- `check_coordinates_safe`
- `get_safety_manager`
- `is_safe_hwnd`
- `is_safe_key`
- `is_safe_text`
- `is_safe_coordinate`
- `is_safe_element`
- `check_foreground`

## `.\automation\tests\test_action_dispatcher.py`
**Classes:**
- `TestSendKey`
- `TestActionResult`
- `TestSendVK`
- `TestSafetySaturation`
**Functions:**
- `test_send_key_enter_on_windows`
- `test_send_key_unknown_fails`
- `test_send_key_escape`
- `test_send_key_tab`
- `test_send_key_audit_log_id`
- `test_send_key_duration_recorded`
- `test_to_dict_contains_required_keys`
- `test_failed_result_has_error`
- `test_send_vk_valid_code`
- `test_send_vk_zero_code`
- `test_models_have_vk_codes`
- `test_execution_methods_defined`

## `.\automation\tests\test_action_safety.py`
**Classes:**
- `TestProtectedWindowClasses`
- `TestHWNDSafe`
- `TestForegroundContext`
- `TestActionSafetyModels`
**Functions:**
- `test_protected_list_not_empty`
- `test_taskbar_is_protected`
- `test_desktop_is_protected`
- `test_regular_window_safe`
- `test_taskbar_hwnd_rejected`
- `test_invalid_hwnd_rejected`
- `test_zero_hwnd_rejected`
- `test_non_windows_returns_error`
- `test_matching_hwnd_passes`
- `test_max_type_length_defined`
- `test_protected_windows_classes_are_strings`

## `.\automation\tests\test_action_validator.py`
**Classes:**
- `TestKeySafety`
- `TestTextSafety`
- `TestElementActionable`
- `TestControlTypeForAction`
- `TestActionValidatorUnit`
**Functions:**
- `test_allowed_key_passes`
- `test_all_vk_codes_pass`
- `test_unknown_key_rejected`
- `test_case_insensitive`
- `test_empty_key_rejected`
- `test_normal_text_passes`
- `test_empty_string_passes`
- `test_oversized_text_rejected`
- `test_none_rejected`
- `test_exactly_at_limit_passes`
- `_make_el`
- `test_valid_element_passes`
- `test_disabled_element_rejected`
- `test_invisible_element_rejected`
- `test_zero_bounds_rejected`
- `test_invalid_hwnd_rejected`
- `test_click_button_passes`
- `test_type_edit_passes`
- `test_type_button_rejected`
- `test_key_any_element_passes`
- `setup_method`
- `_make_ref`
- `test_click_valid_element`
- `test_type_into_button_rejected`
- `test_stale_element_rejected`
- `test_key_enter_passes`
- `test_key_unknown_fails`

## `.\automation\tests\test_browser_adapter.py`
**Classes:**
- `TestAvailability`
- `TestSafetyChecks`
- `TestBrowserActionResult`
- `TestBrowserNotStarted`
- `TestJSSafety`
- `TestTextLengthSafety`
- `TestNavigationSafety`
- `TestBrowserLifecycle`
**Functions:**
- `test_is_available_returns_bool`
- `test_blocked_file_url`
- `test_blocked_javascript_url`
- `test_blocked_chrome_url`
- `test_blocked_payment_domain`
- `test_allowed_url`
- `test_allowed_chatgpt_url`
- `test_result_defaults`
- `test_to_dict`
- `test_navigate_not_started`
- `test_find_element_not_started`
- `test_click_not_started`
- `test_type_not_started`
- `test_get_page_text_not_started`
- `test_screenshot_not_started`
- `test_evaluate_js_not_started`
- `test_blocks_document_write`
- `test_blocks_eval`
- `test_blocks_fetch`
- `test_blocks_cookie_access`
- `test_allows_safe_expression`
- `test_blocks_oversized_text`
- `test_navigate_blocked_url`
- `test_start_and_stop`
- `test_navigate_and_get_text`
- `test_screenshot`

## `.\automation\tests\test_coordinate_safety.py`
**Functions:**
- `test_coordinate_safety_valid`
- `test_coordinate_safety_reject_impossible_rectangle`
- `test_coordinate_safety_reject_offscreen_impossible_coords`
- `test_coordinate_safety_reject_negative_coordinates`

## `.\automation\tests\test_hypothesis_bounds.py`
**Functions:**
- `test_bounds_validation_properties`
- `test_safety_check_text_fuzzing`

## `.\automation\tests\test_mcp_tools.py`
**Classes:**
- `TestCompassToolRegistry`
- `TestDefaultTools`
**Functions:**
- `test_register_and_list`
- `test_invoke_valid_tool`
- `test_invoke_unknown_tool`
- `test_parameter_validation_missing_required`
- `test_parameter_validation_wrong_type`
- `test_invocation_logging`
- `test_create_default_tools`
- `test_get_tool_registry_singleton`
- `test_inspect_ui_no_window`
- `handler`

## `.\backend\app\config.py`
**Classes:**
- `Settings`

## `.\backend\app\database.py`
**Classes:**
- `DatabaseManager`
**Functions:**
- `__init__`
- `get_connection`
- `connection`
- `init_db`
- `check_health`
- `create_task`
- `get_task`
- `list_tasks`
- `update_task_state`
- `get_task_events`
- `log_task_event`
- `save_approval`
- `get_approval`
- `get_approval_by_decision`
- `list_approvals_for_task`
- `update_approval_state`
- `save_decision`
- `get_decision`
- `list_decisions_for_task`
- `create_workflow`
- `update_workflow`
- `get_workflow`
- `list_workflows`
- `upsert_workflow_node`
- `get_workflow_node`
- `list_workflow_nodes`
- `update_workflow_node`
- `create_incident`
- `log_incident_event`
- `get_incident`
- `list_incidents`

## `.\backend\app\logging_config.py`
**Classes:**
- `SecretRedactionFilter`
**Functions:**
- `setup_logging`
- `filter`
- `redact`

## `.\backend\app\models.py`
**Classes:**
- `TaskState`
- `TaskCreate`
- `TaskTransition`
- `TaskEventResponse`
- `TaskResponse`
- `TaskDetailResponse`
- `SubsystemStatus`
- `HealthResponse`
- `SystemInfoResponse`
- `ShutdownResponse`
- `IncidentSeverity`
- `IncidentStatus`
- `IncidentModel`
**Functions:**
- `is_terminal_state`
- `validate_state_transition`

## `.\backend\app\telemetry.py`
**Classes:**
- `CompassTracer`
**Functions:**
- `_ensure_otel`
- `_sanitize_attributes`
- `trace_lifecycle`
- `__init__`
- `start_span`
- `add_event`
- `record_exception`
- `decorator`
- `wrapper`

## `.\backend\app\routers\automation.py`
**Classes:**
- `ElementRefRequest`
- `ClickRequest`
- `TypeRequest`
- `KeyRequest`
- `FocusRequest`
**Functions:**
- `_element_ref_to_dict`

## `.\backend\app\routers\perception.py`
**Classes:**
- `CaptureRequest`
- `FindRequest`

## `.\backend\app\routers\planner.py`
**Classes:**
- `PlanRequest`
- `RunTaskRequest`
- `GoalUnderstandRequest`
- `ConfirmActionRequest`
- `SetModeRequest`
**Functions:**
- `run_worker`

## `.\backend\app\routers\reliability.py`
**Functions:**
- `broadcast_event`

## `.\backend\app\routers\tasks.py`
**Functions:**
- `auto_execute`

## `.\backend\app\routers\workflows.py`
**Classes:**
- `WorkflowNodeCreate`
- `WorkflowCreateRequest`
- `WorkflowStopRequest`
**Functions:**
- `subscriber_cb`

## `.\backend\app\services\task_service.py`
**Classes:**
- `TaskService`
**Functions:**
- `create_task`
- `get_task`
- `get_task_detail`
- `list_tasks`
- `transition_state`
- `stop_task`

## `.\backend\tests\test_config.py`
**Functions:**
- `test_default_settings`

## `.\backend\tests\test_database.py`
**Functions:**
- `test_database_init_and_crud`
- `test_crash_restart_safety_and_approval_invalidation`

## `.\backend\tests\test_failures.py`
**Functions:**
- `test_malformed_task_creation`
- `test_nonexistent_task_queries`
- `test_invalid_state_transition`
- `test_transition_nonexistent_task`
- `test_unknown_route_404`

## `.\backend\tests\test_health.py`
**Functions:**
- `test_health_endpoint`

## `.\backend\tests\test_phase2_api.py`
**Classes:**
- `TestPerceptionEndpoints`
- `TestAutomationEndpoints`
**Functions:**
- `test_perception_status_endpoint`
- `test_perception_foreground_endpoint_responds`
- `test_perception_elements_invalid_hwnd`
- `test_perception_elements_filter_param`
- `test_perception_capture_bad_mode`
- `test_perception_capture_region_missing_params`
- `test_perception_capture_region_negative_dims`
- `test_perception_find_no_params_returns_422`
- `test_perception_status_uia_available_on_windows`
- `_make_element_ref`
- `test_click_invalid_hwnd_rejected_by_validation`
- `test_type_into_button_rejected`
- `test_key_unknown_rejected`
- `test_key_enter_validates`
- `test_action_log_endpoint`
- `test_action_log_with_limit`
- `test_click_without_element_returns_422`
- `test_type_without_text_returns_422`
- `test_key_without_key_returns_422`

## `.\backend\tests\test_phase5_api.py`
**Functions:**
- `test_fastapi_startup_and_health`
- `test_task_creation_and_retrieval`
- `test_malformed_request_returns_422`
- `test_invalid_task_returns_404`
- `test_task_stop_endpoint`
- `test_phase5_state_transitions`
- `test_sse_streaming_media_type`
- `test_ai_status_does_not_expose_credentials`

## `.\backend\tests\test_reliability_api.py`
**Functions:**
- `test_reliability_health`
- `test_incident_creation_db`

## `.\backend\tests\test_reliability_sse.py`
**Functions:**
- `test_repair_guard`

## `.\backend\tests\test_secret_redaction.py`
**Functions:**
- `test_bearer_token_redacted`
- `test_api_key_redacted`
- `test_password_redacted`
- `test_non_secret_text_preserved`

## `.\backend\tests\test_state_machine.py`
**Functions:**
- `test_state_machine_valid_closed_loop_path`
- `test_state_machine_invalid_jumps_rejected`
- `test_state_machine_terminal_state_completed_cannot_transition`
- `test_state_machine_cancellation_and_restart`
- `test_state_machine_recovery_path`
- `test_all_twenty_states_exist_in_enum_and_valid_transitions`
- `test_terminal_states_cannot_execute_further_actions`
- `test_no_bypass_of_validation_approval_safety`
- `test_stop_and_cancellation_safe_from_active_states`
- `test_multimodal_perception_state_transitions`
- `test_target_conflict_safety_blocking`

## `.\backend\tests\test_system.py`
**Functions:**
- `test_system_info`
- `test_shutdown_remote_host_rejected`

## `.\backend\tests\test_tasks.py`
**Functions:**
- `test_task_full_lifecycle`

## `.\backend\tests\test_telemetry.py`
**Classes:**
- `TestAttributeSanitization`
- `TestCompassTracer`
- `TestTraceLifecycleDecorator`
**Functions:**
- `test_sanitizes_passwords`
- `test_sanitizes_tokens`
- `test_truncates_long_strings`
- `test_converts_types_to_string`
- `test_start_span`
- `test_add_event`
- `test_record_exception`
- `test_decorator_success`
- `test_decorator_exception`
- `my_func`
- `my_func`

## `.\overlay\launcher.py`
**Functions:**
- `main`

## `.\overlay\renderer.py`
**Classes:**
- `OverlayRenderer`
**Functions:**
- `_control_color`
- `__init__`
- `set_elements`
- `highlight`
- `clear`
- `set_visible`
- `element_count`
- `paint`
- `_draw_count_badge`

## `.\overlay\win32_helper.py`
**Functions:**
- `set_dpi_awareness`
- `make_window_click_through`
- `is_window_click_through`

## `.\overlay\window.py`
**Classes:**
- `CompassOverlayWindow`
**Functions:**
- `__init__`
- `_auto_close`
- `closeEvent`
- `showEvent`
- `set_click_through`
- `keyPressEvent`
- `update_elements`
- `highlight_element`
- `clear_annotations`
- `paintEvent`
- `_paint_idle_hud`

## `.\overlay\tests\test_overlay.py`
**Functions:**
- `test_dpi_awareness`
- `test_overlay_window_properties`
- `test_overlay_subprocess_clean_exit`

## `.\overlay\tests\test_renderer.py`
**Classes:**
- `TestOverlayRenderer`
- `TestColorPalette`
**Functions:**
- `setup_method`
- `test_initial_element_count_zero`
- `test_set_elements`
- `test_clear_removes_elements`
- `test_highlight_sets_id`
- `test_highlight_none_clears`
- `test_set_visible`
- `test_multiple_elements_stored`
- `test_set_elements_replaces_previous`
- `test_all_known_control_types_have_colors`
- `test_default_color_exists`
- `test_color_values_are_rgba_tuples`

## `.\perception\capture.py`
**Classes:**
- `BITMAPINFOHEADER`
- `BITMAPINFO`
**Functions:**
- `capture_window`
- `capture_desktop`

## `.\perception\context_analyzer.py`
**Classes:**
- `UIContextNode`
- `ContextAnalysisResult`
- `UIContextAnalyzer`
**Functions:**
- `analyze_context`
- `_traverse_tree`

## `.\perception\coordinate_mapper.py`
**Classes:**
- `MonitorInfo`
- `CoordinateMapper`
- `MONITORINFOEXW`
**Functions:**
- `contains`
- `to_dict`
- `__init__`
- `get_virtual_screen_bounds`
- `get_monitors`
- `get_monitor_for_point`
- `transform_box`
- `validate_target_point`
- `_enum_proc`

## `.\perception\element_filter.py`
**Functions:**
- `_get`
- `_is_bounds_valid`
- `_bounds_area`
- `filter_interactive`
- `filter_visible`
- `filter_enabled`
- `filter_editable`
- `find_by_text`
- `find_by_type`
- `rank_by_relevance`
- `get_best_edit_target`
- `summarize_elements`
- `_score`

## `.\perception\evidence_fusion.py`
**Classes:**
- `EvidenceFusionEngine`
**Functions:**
- `compute_text_similarity`
- `__init__`
- `fuse_evidence`
- `resolve_target`
- `validate_target_staleness`

## `.\perception\fusion.py`
**Functions:**
- `calculate_iou`
- `fuse_evidence`

## `.\perception\mapping.py`
**Functions:**
- `get_system_dpi`
- `physical_to_logical`
- `logical_to_physical`
- `scale_bounds`

## `.\perception\models.py`
**Classes:**
- `CoordinateSpace`
- `CoordinateBounds`
- `TemporalDelta`
- `OcrElement`
- `UiaElement`
- `FusedCluster`
- `MultimodalEvidence`
- `BoundingRect`
- `WindowInfo`
- `UIElement`
- `UISnapshot`
- `CaptureResult`
**Functions:**
- `width`
- `height`
- `__init__`
- `area`
- `is_valid`
- `center`
- `from_ltwh`
- `to_dict`

## `.\perception\models_multimodal.py`
**Classes:**
- `EvidenceSource`
- `CapabilityStatus`
- `ConsistencyOutcome`
- `ResolutionMethod`
- `CoordinateSpace`
- `BoundingBox`
- `EvidenceProvenance`
- `MultimodalEvidence`
- `ObservationSnapshot`
- `ResolvedTarget`
- `MultimodalVerificationResult`
**Functions:**
- `width`
- `height`
- `center`
- `area`
- `is_valid`
- `contains_point`
- `intersects`
- `iou`
- `to_dict`
- `from_ltwh`
- `from_dict`
- `is_expired`
- `to_dict`
- `to_dict`
- `get_by_source`
- `to_dict`
- `__post_init__`
- `to_dict`
- `to_dict`

## `.\perception\multimodal_service.py`
**Classes:**
- `MultimodalPerceptionService`
**Functions:**
- `__init__`
- `get_capabilities`
- `capture_multimodal_snapshot`
- `resolve_target`
- `verify_multimodal_state_change`

## `.\perception\ocr.py`
**Classes:**
- `WinRTOcrBackend`
**Functions:**
- `__init__`
- `extract_text`

## `.\perception\ocr_engine.py`
**Classes:**
- `OCRBackend`
- `WinRTOcrBackend`
- `TesseractOcrBackend`
- `MockOcrBackend`
- `OCREngineManager`
**Functions:**
- `normalize_ocr_text`
- `backend_name`
- `is_available`
- `extract_text_and_boxes`
- `__init__`
- `backend_name`
- `is_available`
- `_extract_inprocess`
- `_extract_powershell`
- `extract_text_and_boxes`
- `__init__`
- `backend_name`
- `is_available`
- `extract_text_and_boxes`
- `__init__`
- `backend_name`
- `is_available`
- `extract_text_and_boxes`
- `__init__`
- `active_backend`
- `get_capability_status`
- `extract`

## `.\perception\omni_parser.py`
**Classes:**
- `OmniParserAdapter`
**Functions:**
- `get_omniparser`
- `__init__`
- `parse_screenshot`

## `.\perception\opencv_processor.py`
**Classes:**
- `VisualDiffResult`
- `VisualRegion`
**Functions:**
- `_ensure_cv2`
- `is_available`
- `screenshot_diff`
- `preprocess_for_ocr`
- `extract_visual_regions`
- `compare_regions`
- `to_dict`
- `to_dict`

## `.\perception\perception_config.py`
**Functions:**
- `validate_image_dimensions`
- `validate_concurrency`

## `.\perception\perception_security.py`
**Classes:**
- `UntrustedContentQuarantine`
- `CredentialRedactor`
- `ScreenshotRingBuffer`
**Functions:**
- `is_injection_attempt`
- `sanitize_untrusted_text`
- `redact`
- `__init__`
- `register_screenshot`
- `_enforce_capacity`
- `cleanup_all`

## `.\perception\screen_capture.py`
**Classes:**
- `BITMAPINFOHEADER`
- `BITMAPINFO`
**Functions:**
- `_get_virtual_screen_bounds`
- `_capture_region_raw`
- `_capture_window_raw`
- `_save_png`
- `capture_region`
- `capture_foreground_window`
- `capture_window`
- `capture_element_rect`
- `capture_full_screen`
- `get_capture_capabilities`

## `.\perception\security.py`
**Classes:**
- `ScreenshotRingBuffer`
**Functions:**
- `redact_text`
- `__init__`
- `add_screenshot`
- `prune`
- `cleanup`

## `.\perception\service.py`
**Classes:**
- `PerceptionService`
**Functions:**
- `__init__`
- `get_snapshot`
- `get_filtered_snapshot`
- `start_polling`
- `is_polling`
- `stop_polling`
- `_poll_loop`
- `get_last_snapshot`
- `subscribe`
- `unsubscribe`
- `get_status`

## `.\perception\temporal.py`
**Functions:**
- `calculate_image_diff_ratio`
- `detect_transition_type`

## `.\perception\temporal_comparator.py`
**Classes:**
- `StateTransitionType`
- `TemporalComparisonResult`
- `TemporalComparator`
**Functions:**
- `has_transition`
- `to_dict`
- `__init__`
- `calculate_image_difference`
- `compare_observations`
- `_find_target`

## `.\perception\uia_inspector.py`
**Functions:**
- `_init_uia`
- `_get_uia`
- `get_uia_status`
- `_get_hwnd_rect`
- `_get_window_class`
- `_get_window_title`
- `_get_window_pid`
- `_is_window`
- `_is_window_minimized`
- `get_foreground_window`
- `get_element_tree`
- `_safe_get`
- `find_element_by_name`
- `find_element_by_type`
- `revalidate_element`
- `_traverse`

## `.\perception\vision_router.py`
**Classes:**
- `VisionRouter`
**Functions:**
- `__init__`
- `is_vision_model_available`
- `get_capability_status`
- `analyze_screenshot`

## `.\perception\tests\test_coordinate_mapper.py`
**Functions:**
- `test_coordinate_mapper_virtual_screen_bounds`
- `test_coordinate_mapper_monitors_enumeration`
- `test_coordinate_space_transformation`
- `test_negative_monitor_coordinates_handling`
- `test_target_point_validation`

## `.\perception\tests\test_element_filter.py`
**Classes:**
- `TestFilterInteractive`
- `TestFilterVisible`
- `TestFilterEditable`
- `TestFindByText`
- `TestFindByType`
- `TestRankByRelevance`
- `TestGetBestEditTarget`
- `TestSummarizeElements`
**Functions:**
- `_make_element`
- `test_returns_interactive_types`
- `test_empty_list`
- `test_keeps_visible_elements`
- `test_empty_list`
- `test_only_edit_and_document`
- `test_empty_list`
- `test_exact_match`
- `test_fuzzy_match`
- `test_text_field_match`
- `test_no_match`
- `test_case_insensitive_by_default`
- `test_matches_control_type`
- `test_case_insensitive`
- `test_no_match`
- `test_interactive_elements_score_higher`
- `test_focused_element_gets_boost`
- `test_disabled_elements_score_lower`
- `test_empty_list`
- `test_prefers_focused_edit`
- `test_returns_none_if_no_editable`
- `test_returns_enabled_visible_fallback`
- `test_summary_counts`
- `test_empty_summary`

## `.\perception\tests\test_evidence_fusion.py`
**Functions:**
- `test_calculate_iou`
- `test_fuse_evidence`

## `.\perception\tests\test_multimodal_evidence.py`
**Functions:**
- `test_coordinate_bounds`
- `test_temporal_delta`
- `test_multimodal_evidence_creation`

## `.\perception\tests\test_multimodal_integration.py`
**Functions:**
- `test_multimodal_service_full_snapshot_and_target_resolution`
- `test_vision_router_ai_unavailable_fallback`
- `test_multimodal_verification_state_change`
- `test_multimodal_execution_controller_events`
- `on_event`

## `.\perception\tests\test_ocr_engine.py`
**Functions:**
- `test_winrt_ocr_initialization`
- `test_winrt_ocr_extraction`

## `.\perception\tests\test_opencv_processor.py`
**Classes:**
- `TestAvailability`
- `TestScreenshotDiff`
- `TestPreprocessForOCR`
- `TestVisualRegionExtraction`
- `TestRegionComparison`
- `TestGracefulDegradation`
**Functions:**
- `sample_image_a`
- `sample_image_b`
- `sample_image_identical`
- `sample_image_with_shapes`
- `test_is_available_returns_bool`
- `test_is_available_true_when_installed`
- `test_identical_images`
- `test_different_images`
- `test_missing_file_a`
- `test_missing_both_files`
- `test_result_has_computation_time`
- `test_to_dict`
- `test_preprocess_creates_output`
- `test_preprocess_default_output_path`
- `test_preprocess_missing_file`
- `test_preprocess_no_denoise`
- `test_extracts_regions_from_shapes`
- `test_region_has_correct_fields`
- `test_missing_file`
- `test_cap_at_100_regions`
- `test_identical_region`
- `test_different_region`
- `test_missing_file`
- `test_out_of_bounds_region`
- `test_screenshot_diff_no_opencv`
- `test_preprocess_no_opencv`
- `test_extract_regions_no_opencv`
- `test_compare_regions_no_opencv`

## `.\perception\tests\test_perception_config.py`
**Functions:**
- `test_resource_limits_defined_and_positive`
- `test_validate_image_dimensions`
- `test_validate_concurrency`

## `.\perception\tests\test_perception_security.py`
**Functions:**
- `test_prompt_injection_quarantine`
- `test_credential_redaction`
- `test_screenshot_ring_buffer_capacity_enforcement`

## `.\perception\tests\test_perception_service.py`
**Classes:**
- `TestPerceptionService`
**Functions:**
- `setup_method`
- `test_get_status_returns_dict`
- `test_initial_polling_false`
- `test_get_snapshot_returns_snapshot`
- `test_polling_start_stop`
- `test_polling_start_twice_returns_false`
- `test_subscriber_called_on_poll`
- `test_unsubscribe`
- `teardown_method`

## `.\perception\tests\test_screen_capture.py`
**Functions:**
- `test_system_dpi`
- `test_dpi_conversion`
- `test_scale_bounds`
- `test_capture_desktop`
- `test_capture_window_invalid_hwnd`
- `test_capture_window_valid_hwnd`

## `.\perception\tests\test_temporal_comparator.py`
**Functions:**
- `test_image_diff`
- `test_redact_text`
- `test_ring_buffer`

## `.\perception\tests\test_uia_inspector.py`
**Classes:**
- `TestUIAStatus`
- `TestForegroundWindow`
- `TestElementTree`
- `TestFindElement`
- `TestRevalidate`
- `TestBoundingRect`
**Functions:**
- `test_get_uia_status_returns_dict`
- `test_uia_status_platform_field`
- `test_uia_available_on_windows`
- `test_get_foreground_window_returns_dict`
- `test_get_foreground_window_on_windows`
- `test_foreground_window_has_valid_bounds`
- `test_get_element_tree_invalid_hwnd_returns_error`
- `test_get_element_tree_zero_hwnd_returns_error`
- `test_get_element_tree_foreground_on_windows`
- `test_element_tree_respects_max_elements`
- `test_element_tree_depth_0_returns_error`
- `test_find_by_name_invalid_hwnd`
- `test_find_by_type_invalid_hwnd`
- `test_revalidate_missing_hwnd`
- `test_revalidate_bad_hwnd`
- `test_area`
- `test_zero_area_invalid`
- `test_center`
- `test_from_ltwh`
- `test_to_dict`

## `.\planner\checkpoint_manager.py`
**Classes:**
- `TaskCheckpoint`
- `WorkflowCheckpoint`
- `CheckpointManager`
**Functions:**
- `__init__`
- `save_checkpoint`
- `load_checkpoint`
- `validate_for_resume`
- `_redact_secrets`
- `save_workflow_checkpoint`
- `load_workflow_checkpoint`
- `validate_workflow_for_resume`

## `.\planner\circuit_breaker.py`
**Classes:**
- `CircuitState`
- `CircuitBreaker`
**Functions:**
- `__init__`
- `state`
- `_evaluate_state`
- `can_execute`
- `record_success`
- `record_failure`
- `reset`

## `.\planner\confidence_engine.py`
**Classes:**
- `ConfidenceEvaluation`
- `ConfidenceEngine`
**Functions:**
- `__init__`
- `evaluate_confidence`

## `.\planner\context_builder.py`
**Classes:**
- `ContextBuilder`
**Functions:**
- `sanitize_untrusted_text`
- `__init__`
- `sanitize_text`
- `build_context`

## `.\planner\crash_recovery.py`
**Classes:**
- `CrashRecoveryHandler`
**Functions:**
- `__init__`
- `recover_interrupted_tasks`

## `.\planner\decision_engine.py`
**Classes:**
- `DecisionEngine`
**Functions:**
- `__init__`
- `formulate_decision`
- `_generate_explanation`

## `.\planner\dependency_manager.py`
**Classes:**
- `DependencyValidationError`
- `StepDependencyManager`
**Functions:**
- `__init__`
- `validate_dag`
- `get_topological_order`
- `get_ready_steps`
- `cascade_downstream_blocks`

## `.\planner\dynamic_replanner.py`
**Classes:**
- `DynamicReplanner`
**Functions:**
- `__init__`
- `handle_replan_trigger`

## `.\planner\execution_controller.py`
**Classes:**
- `MultiStepExecutionController`
**Functions:**
- `__init__`
- `_get_stop_event`
- `stop_task`
- `is_stopped`
- `run_multistep_task`
- `_dispatch_step_action`
- `_handle_stop`
- `emit`
- `_enum_wnd`

## `.\planner\execution_engine.py`
**Classes:**
- `ExecutionEngine`
**Functions:**
- `__init__`
- `_get_task_lock`
- `_get_stop_event`
- `stop_task`
- `is_stopped`
- `get_active_plan`
- `get_timeline`
- `record_timeline_entry`
- `run_task`
- `cleanup_task_resources`
- `_dispatch_single_action`
- `emit`

## `.\planner\execution_trace.py`
**Classes:**
- `StepTraceEntry`
- `ExecutionTrace`
- `WorkflowExecutionTrace`
- `ExecutionTraceManager`
**Functions:**
- `__init__`
- `start_trace`
- `get_trace`
- `record_step_start`
- `record_step_finish`
- `record_stop_event`
- `finalize_trace`
- `redact_text`
- `_redact_dict`
- `start_workflow_trace`
- `get_workflow_trace`
- `record_workflow_event`
- `record_node_start`
- `record_node_finish`
- `finalize_workflow_trace`

## `.\planner\goal_understanding.py`
**Classes:**
- `GoalUnderstandingResult`
- `GoalUnderstandingEngine`
**Functions:**
- `__init__`
- `understand_goal`

## `.\planner\human_approval.py`
**Classes:**
- `ApprovalState`
- `ApprovalRecord`
- `HumanApprovalController`
**Functions:**
- `__init__`
- `_persist_record`
- `mode`
- `set_mode`
- `should_require_approval`
- `create_approval_request`
- `grant_approval`
- `reject_approval`
- `consume_approval`
- `invalidate_all_approvals_for_task`
- `cleanup_task`
- `get_approval`
- `get_approval_status`
- `validate_approval_binding`
- `record_approval_response`
- `validate_approval_state`

## `.\planner\loop_detector.py`
**Classes:**
- `LoopDetectionError`
- `LoopDetector`
**Functions:**
- `__init__`
- `record_action_attempt`
- `record_ui_state`
- `record_replan`
- `reset`

## `.\planner\models.py`
**Classes:**
- `ConfidenceLevel`
- `RiskLevel`
- `GuidanceMode`
- `FailureClassification`
- `RecoveryCause`
- `PlannerActionType`
- `TargetReference`
- `VerificationCondition`
- `PlannedAction`
- `TaskPlan`
- `VerificationStatus`
- `EvidenceSource`
- `VerificationResult`
- `Decision`
- `TimelineEntry`
- `StepStatus`
- `TaskStep`
- `DecomposedPlan`
**Functions:**
- `from_score`
- `validate_action_parameters`
- `to_dict`

## `.\planner\multi_step_verifier.py`
**Classes:**
- `MultiStepVerifier`
**Functions:**
- `__init__`
- `verify_step`
- `verify_final_goal`
- `_enum_w`

## `.\planner\planner_service.py`
**Classes:**
- `PlannerService`
**Functions:**
- `extract_json_object`
- `__init__`
- `create_plan`
- `parse_and_validate_plan`

## `.\planner\plan_validator.py`
**Classes:**
- `PlanValidationError`
- `PlanValidator`
**Functions:**
- `__init__`
- `validate_plan`
- `_validate_step`
- `_validate_action`

## `.\planner\recovery_engine.py`
**Classes:**
- `RecoveryStage`
- `StageRecoveryResult`
- `RecoveryDiagnosis`
- `RecoveryEngine`
**Functions:**
- `__init__`
- `diagnose_failure`
- `stage_1_reobserve`
- `stage_2_targeted_retry`
- `stage_3_alternate_strategy`
- `synthesize_adaptive_plan`

## `.\planner\reliability_monitor.py`
**Classes:**
- `IncidentSeverity`
- `IncidentCategory`
- `IncidentRecord`
- `ReliabilityMonitor`
**Functions:**
- `__init__`
- `record_incident`
- `get_incidents_for_task`
- `reconcile_task_state`
- `clear_all`

## `.\planner\resource_governor.py`
**Classes:**
- `ResourceSnapshot`
- `ScreenshotRingBuffer`
- `ResourceGovernor`
**Functions:**
- `__init__`
- `add_frame`
- `get_latest`
- `count`
- `clear`
- `__init__`
- `check_action_budget`
- `check_timeline_budget`
- `check_plan_length`
- `check_workflow_node_budget`
- `check_active_workflows_budget`
- `check_concurrent_nodes_budget`
- `check_workflow_duration`
- `check_workflow_retries`
- `record_frame`
- `clear_ring_buffer`
- `get_adaptive_observation_interval_ms`
- `measure_resources`

## `.\planner\risk_classifier.py`
**Classes:**
- `RiskClassification`
- `RiskClassifier`
**Functions:**
- `__init__`
- `classify_risk`

## `.\planner\security_guards.py`
**Classes:**
- `SecurityGuard`
**Functions:**
- `__init__`
- `validate_action_security`
- `validate_decision_security`
- `sanitize_untrusted_screen_content`

## `.\planner\stale_guard.py`
**Classes:**
- `StaleCheckResult`
- `StaleGuard`
**Functions:**
- `__init__`
- `validate_freshness`
- `has_bounds_drifted`

## `.\planner\target_resolver.py`
**Classes:**
- `TargetResolutionResult`
- `TargetResolver`
**Functions:**
- `__init__`
- `__init__`
- `resolve`
- `revalidate_live_target`
- `revalidate_consequential_target`

## `.\planner\task_decomposer.py`
**Classes:**
- `TaskDecomposer`
**Functions:**
- `__init__`
- `decompose`
- `_try_deterministic_template`
- `_decompose_rule_based`
- `_build_safe_fallback_plan`
- `_hash_plan`

## `.\planner\verification_engine.py`
**Classes:**
- `VerificationEngine`
**Functions:**
- `__init__`
- `verify_action`
- `_infer_and_verify`
- `verify_click_transition`
- `verify_app_launch`
- `verify_unobservable_action`
- `_find_matching_element`
- `verify_final_goal_state`

## `.\planner\workflow_dag.py`
**Classes:**
- `DAGValidationError`
- `WorkflowDAGValidator`
- `WorkflowDAGEngine`
**Functions:**
- `validate`
- `__init__`
- `validate_workflow`
- `topological_sort`
- `get_topological_order`
- `get_ready_nodes`
- `cascade_failure`
- `is_workflow_terminal`
- `check_workflow_complete`

## `.\planner\workflow_models.py`
**Classes:**
- `WorkflowStatus`
- `WorkflowNodeStatus`
- `RetryPolicy`
- `ResourceBudget`
- `WorkflowNode`
- `WorkflowEventType`
- `Workflow`
**Functions:**
- `validate_workflow_transition`
- `is_workflow_terminal`
- `validate_node_transition`
- `is_node_terminal`
- `_generate_workflow_id`
- `_generate_node_id`
- `is_retryable`
- `get_backoff_seconds`
- `transition_to`
- `transition_to`
- `increment_generation`
- `get_node`
- `get_nodes_by_status`
- `compute_progress`
- `check_resource_budget`

## `.\planner\workflow_orchestrator.py`
**Classes:**
- `WorkflowOrchestrator`
**Functions:**
- `__init__`
- `subscribe`
- `emit_event`
- `create_workflow`
- `start_workflow`
- `stop_workflow`
- `pause_workflow`
- `resume_workflow`
- `recover_workflow`
- `_run_loop`
- `_dispatch_node`
- `_default_node_executor`
- `_verify_node`
- `_load_workflow_from_db`
- `get_workflow`
- `list_active_workflows`
- `unsubscribe`

## `.\planner\workflow_scheduler.py`
**Classes:**
- `ResourceLockManager`
- `ReadyNodeScheduler`
**Functions:**
- `__init__`
- `_get_or_create_lock`
- `acquire_locks`
- `release_locks`
- `locked`
- `is_locked`
- `__init__`
- `get_ready_nodes`
- `compute_required_locks`
- `can_dispatch_node`

## `.\planner\reliability\diagnostics.py`
**Functions:**
- `emit_incident`

## `.\planner\reliability\integrity.py`
**Functions:**
- `_calculate_sha256`
- `verify_critical_integrity`

## `.\planner\reliability\repair.py`
**Functions:**
- `propose_repair`
- `apply_repair`
- `update_incident_status`

## `.\planner\tests\test_ai_untrusted_validation.py`
**Classes:**
- `TestAIUntrustedValidationPipeline`
**Functions:**
- `test_gate_01_schema_validation`
- `test_gate_02_action_validation`
- `test_gate_03_target_validation`
- `test_gate_04_parameter_validation`
- `test_gate_05_dependency_validation`
- `test_gate_06_risk_validation`
- `test_gate_07_safety_validation_forbidden_windows`
- `test_gate_08_approval_validation_binding`
- `test_gate_09_resource_budget_validation`
- `test_gate_10_verification_strategy_validation`

## `.\planner\tests\test_api_planner.py`
**Classes:**
- `TestPlannerAPI`
**Functions:**
- `test_get_ai_status`
- `test_get_ai_models_free_only`
- `test_run_task_endpoint`
- `test_stop_task_endpoint`
- `test_get_task_state_endpoint`
- `test_plan_requires_valid_goal`

## `.\planner\tests\test_api_sse_phase6.py`
**Functions:**
- `test_api_create_task_valid`
- `test_api_create_task_malformed`
- `test_api_cancel_task`
- `test_api_state_transition_validation`

## `.\planner\tests\test_approval_boundaries.py`
**Functions:**
- `test_consequential_action_blocks_without_approval`
- `make_test_decision`
- `test_human_approval_lifecycle`
- `test_approval_invalidated_on_stale_observation`

## `.\planner\tests\test_cancellation_everywhere.py`
**Functions:**
- `test_stop_during_goal_understanding`
- `test_stop_is_idempotent`
- `test_late_ai_response_neutralized_after_stop`
- `delayed_planner_call`

## `.\planner\tests\test_checkpoint_resume.py`
**Functions:**
- `test_checkpoint_save_and_load_integrity`
- `test_checkpoint_tamper_detection`
- `test_checkpoint_secret_redaction`
- `test_checkpoint_validate_for_resume_desktop_context`
- `test_multimodal_checkpoint_integrity_and_corruption`

## `.\planner\tests\test_circuit_breaker.py`
**Functions:**
- `test_circuit_initial_state_closed`
- `test_circuit_opens_after_threshold_failures`
- `test_circuit_resets_failure_count_on_success`
- `test_circuit_half_opens_after_recovery_timeout`
- `test_circuit_closes_on_success_in_half_open`
- `test_circuit_reopens_on_failure_in_half_open`

## `.\planner\tests\test_cleanup.py`
**Functions:**
- `clean_engine`
- `test_cleanup_after_successful_task`
- `test_cleanup_after_failed_task`
- `test_cleanup_after_cancelled_task_stop`
- `test_cleanup_after_confirmation_timeout`
- `test_cleanup_after_recovery_exhaustion`
- `test_cleanup_after_application_crash`
- `test_cleanup_after_planner_failure`
- `test_cleanup_after_ai_unavailable`
- `test_cleanup_after_verification_failure`
- `test_cleanup_after_sse_interruption`
- `test_cleanup_after_unexpected_exception`

## `.\planner\tests\test_concurrency_deep.py`
**Functions:**
- `test_duplicate_execution_prevention`
- `test_simultaneous_task_execution`
- `test_stop_vs_execution_race`
- `test_approval_vs_stop_race`
- `test_concurrent_replanning`
- `test_late_ai_response_after_cancellation`
- `worker`
- `create_plan_mock`
- `worker_a`
- `worker_b`
- `worker`
- `replan_worker`
- `slow_plan`
- `worker`

## `.\planner\tests\test_confidence_engine.py`
**Functions:**
- `test_confidence_strong_match_with_active_window`
- `test_confidence_conflicting_evidence_degrades`
- `test_confidence_missing_element_returns_unknown`
- `test_confidence_disabled_element_penalized`

## `.\planner\tests\test_context_analyzer.py`
**Functions:**
- `test_analyze_context_with_modal_dialog`
- `test_analyze_context_hierarchy_panels`
- `test_analyze_context_empty_fallback_uncertainty`

## `.\planner\tests\test_context_builder.py`
**Classes:**
- `TestContextBuilder`
**Functions:**
- `test_prompt_injection_defense`
- `test_normal_text_preservation`
- `test_build_context_filtering`

## `.\planner\tests\test_crash_recovery.py`
**Functions:**
- `test_interrupted_task_marked_stopped_on_startup`
- `test_stale_approvals_invalidated_on_startup`
- `test_completed_tasks_untouched_by_recovery`
- `test_no_blind_action_resume_after_crash`

## `.\planner\tests\test_crash_recovery_phase5.py`
**Functions:**
- `test_target_application_crash_detection`
- `test_target_window_closed_between_steps`
- `test_planner_failure_fails_safely`
- `test_perception_failure_fails_safely`
- `test_verification_failure_fails_safely`
- `test_backend_restart_recovery_audits_interrupted_tasks`
- `test_zero_blind_resumption_after_restart`

## `.\planner\tests\test_crash_restart_phase6.py`
**Functions:**
- `test_target_application_crash_handling`
- `test_planner_failure_safe_halt`
- `test_perception_failure_safe_halt`
- `test_verification_failure_safe_halt`

## `.\planner\tests\test_dependency_manager.py`
**Functions:**
- `test_valid_linear_dag`
- `test_valid_branching_dag`
- `test_circular_dependency_detected`
- `test_self_dependency_detected`
- `test_missing_dependency_detected`
- `test_duplicate_step_id_detected`
- `test_ready_steps_calculation`
- `test_downstream_failure_cascades_blocks`

## `.\planner\tests\test_diagnostics.py`
**Functions:**
- `test_emit_incident_db`
- `fail_action`

## `.\planner\tests\test_dynamic_replanner.py`
**Functions:**
- `test_dynamic_replan_preserves_completed_steps`
- `test_dynamic_replan_injects_remedial_step_on_modal`

## `.\planner\tests\test_execution_engine.py`
**Classes:**
- `TestExecutionEngine`
**Functions:**
- `setup_method`
- `test_stop_mechanism_sets_flag_and_halts_task`
- `test_single_action_loop_success`
- `test_concurrency_lock_prevents_duplicate_runs`
- `test_bounded_retries_on_repeated_verification_failure`

## `.\planner\tests\test_execution_trace.py`
**Functions:**
- `test_execution_trace_redaction`
- `test_execution_trace_lifecycle_and_serialization`

## `.\planner\tests\test_failures_extended.py`
**Functions:**
- `test_scenario_m_backend_crash_recovery`
- `test_scenario_n_restart_no_blind_action_resume`
- `test_scenario_o_stop_during_approval_race`
- `test_scenario_p_duplicate_approval_replay_rejected`
- `test_scenario_q_coordinate_out_of_bounds_rejection`
- `test_scenario_r_dpi_change_invalidation`
- `test_scenario_s_target_hwnd_destroyed_invalidation`
- `test_scenario_t_user_switches_application_invalidation`
- `test_scenario_u_invalid_api_confirmation_rejection`
- `test_scenario_v_malformed_action_schema_rejection`
- `test_scenario_w_secret_redaction_in_logs`
- `test_scenario_x_resource_action_budget_exhaustion`
- `test_scenario_y_plan_length_budget_exhaustion`
- `test_scenario_z_circuit_breaker_trips_on_repeated_failure`

## `.\planner\tests\test_false_success.py`
**Functions:**
- `test_click_api_success_but_dialog_did_not_open`
- `test_typing_api_success_but_text_missing_from_control`
- `test_app_launch_reported_but_window_never_appeared`
- `test_toggle_click_but_state_remains_unchanged`
- `test_stale_ui_cache_reports_success_when_live_ui_changed`
- `test_action_success_with_unobservable_outcome_returns_unverified`

## `.\planner\tests\test_final_state_verification.py`
**Functions:**
- `test_action_success_does_not_equal_task_success_when_final_state_absent`
- `test_action_success_with_verified_final_state_completes_task`

## `.\planner\tests\test_goal_understanding.py`
**Functions:**
- `test_goal_understanding_notepad_typing`
- `test_goal_understanding_calculator`
- `test_goal_understanding_high_risk_deletion`
- `test_goal_understanding_ambiguous_short_goal`
- `test_goal_understanding_ambiguous_vague_phrase`

## `.\planner\tests\test_goal_verification.py`
**Functions:**
- `test_step_verification_window_title_match`
- `test_step_verification_window_title_mismatch`
- `test_step_verification_filesystem_file_exists`
- `test_final_goal_verification_all_steps_completed`
- `test_final_goal_verification_uncompleted_steps_fail`

## `.\planner\tests\test_human_approval.py`
**Functions:**
- `make_test_decision`
- `test_high_risk_requires_approval_in_all_modes`
- `test_autonomous_mode_allows_low_and_medium`
- `test_approval_anti_bypass_target_change`
- `test_approval_anti_bypass_action_change`
- `test_approval_anti_bypass_hwnd_change`
- `test_approval_anti_bypass_material_movement`
- `test_approval_anti_bypass_parameters_change`
- `test_approval_anti_bypass_application_change`
- `test_approval_anti_bypass_target_disappears`
- `test_approval_anti_bypass_stale_observation`
- `test_approval_anti_bypass_display_context_change`
- `test_approval_anti_bypass_task_or_decision_mismatch`
- `test_approval_consumed_once_only`
- `test_replay_approval_rejected`
- `test_cannot_consume_unapproved`
- `test_expired_approval_cannot_be_consumed`

## `.\planner\tests\test_idempotency_recovery.py`
**Functions:**
- `test_non_repeatable_action_fails_verification_cannot_retry`
- `test_non_repeatable_action_dispatch_failure_cannot_retry`
- `test_repeatable_action_allows_bounded_retry`

## `.\planner\tests\test_integrity.py`
**Functions:**
- `test_verify_critical_integrity`

## `.\planner\tests\test_loop_termination.py`
**Functions:**
- `test_repeated_action_failure_loop_detected`
- `test_action_success_resets_failure_streak`
- `test_state_oscillation_cycle_detected`
- `test_replan_limit_enforced`
- `test_cyclic_replan_detected`

## `.\planner\tests\test_multi_step_stop.py`
**Functions:**
- `test_stop_before_decomposition`
- `test_stop_mid_step_execution`
- `test_stop_is_idempotent_and_thread_safe`
- `on_event`

## `.\planner\tests\test_omniroute_failures_phase10.py`
**Classes:**
- `TestOmniRouteFailureMatrix`
**Functions:**
- `test_01_omniroute_available`
- `test_02_omniroute_unavailable`
- `test_03_model_unavailable`
- `test_04_free_model_unavailable_strict_rejection`
- `test_05_invalid_model_response_format`
- `test_06_malformed_planner_output`
- `test_07_timeout_handling`
- `test_08_routing_failure`
- `test_09_network_failure`
- `test_10_provider_failure_500`
- `test_11_ai_planner_exception_safety`
- `test_12_safe_deterministic_fallback`
- `test_13_truthful_ai_unavailable_reporting`
- `test_14_free_only_policy_prevents_silent_paid_fallback`

## `.\planner\tests\test_omniroute_provider.py`
**Classes:**
- `TestOmniRouteProvider`
**Functions:**
- `test_provider_initialization`
- `test_resolve_api_key_override`
- `test_free_only_policy_enforcement`
- `test_error_classification_rate_limit`
- `test_error_classification_timeout`
- `test_validate_model_capabilities_enforced`

## `.\planner\tests\test_partial_completion.py`
**Functions:**
- `test_partial_completion_preserves_verified_steps`
- `test_consequential_action_never_auto_repeated_in_recovery`
- `test_cascading_blocked_downstream_steps`

## `.\planner\tests\test_phase10_hardening.py`
**Classes:**
- `TestPhase10ReliabilityAndHardening`
**Functions:**
- `test_01_incident_logging_and_retrieval`
- `test_02_state_reconciliation_safely_resolves_stopped`
- `test_03_risk_uncertainty_elevation`
- `test_04_loop_detection_oscillation_protection`
- `test_05_secret_redaction_in_traces_and_logs`

## `.\planner\tests\test_phase11_defects.py`
**Classes:**
- `TestPhase11Defects`
**Functions:**
- `setup_and_teardown`
- `test_def_p11_01_circuit_breaker_open_transitions_to_ai_unavailable`
- `test_def_p11_01_planning_ai_failure_transitions_safely`
- `test_def_p11_02_cleanup_preserves_all_terminal_states`
- `test_def_p11_02_cleanup_forces_transitional_to_failed`
- `test_def_p11_03_load_workflow_from_db_handles_zero_priority`
- `test_def_p11_03_workflow_node_create_pydantic_validation`
- `test_def_p11_04_stop_task_rejects_all_terminal_states`
- `test_def_p11_04_stop_task_is_idempotent_on_stopped_state`
- `test_def_p11_05_frontend_task_state_card_includes_task_completed`
- `event_sink`

## `.\planner\tests\test_phase12_functional_loop.py`
**Classes:**
- `TestPhase12FunctionalLoop`
**Functions:**
- `clean_circuit_breaker`
- `test_pre_dispatch_target_revalidation_rejects_closed_window`
- `test_stale_observation_rejected_when_age_exceeds_threshold`
- `test_action_success_does_not_equal_task_success_without_goal_verification`
- `test_partial_completion_preserves_verified_steps`
- `test_loop_detector_flags_repeated_identical_actions`
- `test_stop_asserted_before_execution_halts_immediately`
- `test_late_ai_response_neutralized_after_stop`
- `test_malformed_ai_plan_bounds_rejected`
- `test_unsafe_plan_triggers_high_risk_and_approval`
- `test_approval_invalidated_when_target_context_changes`
- `test_checkpoint_tamper_detection`

## `.\planner\tests\test_phase13_adversarial.py`
**Classes:**
- `TestPhase13AdversarialHardening`
**Functions:**
- `clean_circuit_breaker`
- `test_input_attack_empty_or_whitespace_goal_flags_ambiguity`
- `test_input_attack_extremely_oversized_payload`
- `test_input_attack_unicode_and_control_chars`
- `test_prompt_injection_in_goal_classified_high_risk`
- `test_prompt_injection_in_window_title_treated_as_inert_data`
- `test_ai_attack_malicious_shell_execution_blocked`
- `test_ai_attack_out_of_bounds_negative_and_extreme_coordinates`
- `test_planner_attack_unknown_action_type_rejected`
- `test_perception_attack_coordinate_drift_invalidates_target`
- `test_verification_attack_action_success_with_missing_state_marked_unverified`
- `test_recovery_attack_non_repeatable_consequential_action_blocks_retry`
- `test_loop_attack_alternating_state_oscillation_detected`
- `test_state_machine_attack_illegal_transition_from_terminal_rejected`
- `test_concurrency_attack_simultaneous_stop_halts_execution`
- `test_checkpoint_attack_tampered_payload_rejected`

## `.\planner\tests\test_phase4_api.py`
**Functions:**
- `test_api_goal_understand`
- `test_api_guidance_mode_get_and_set`
- `test_api_confirm_action`
- `test_api_get_timeline`
- `test_api_resources_endpoint`
- `test_api_confirm_nonexistent_task_returns_404`
- `test_api_confirm_nonexistent_decision_returns_404`
- `test_api_confirm_terminal_task_returns_409`
- `test_api_confirm_consumed_approval_returns_409`

## `.\planner\tests\test_planner_schemas.py`
**Classes:**
- `TestPlannerSchemas`
**Functions:**
- `test_valid_task_plan_creation`
- `test_unsupported_action_type_rejected`
- `test_type_action_missing_text_rejected`
- `test_type_action_oversized_text_rejected`
- `test_key_action_invalid_key_rejected`
- `test_wait_duration_bounds`

## `.\planner\tests\test_recovery_engine.py`
**Functions:**
- `test_completed_step_preservation_on_failure`
- `test_user_intervention_overrides_stale_plan`
- `test_target_moved_diagnosis`
- `test_adaptive_plan_merging`
- `test_all_thirteen_failure_states_diagnosed`

## `.\planner\tests\test_recovery_stages.py`
**Functions:**
- `test_stage_1_reperception_detects_drift`
- `test_stage_1_missing_target_fails`
- `test_stage_2_blocks_non_repeatable_action`
- `test_stage_2_retry_budget_exhaustion`
- `test_stage_2_disabled_target_rejection`
- `test_stage_2_authorized_retry`
- `test_stage_3_semantic_invoke_pattern`
- `test_stage_3_semantic_toggle_pattern`
- `test_stage_3_keyboard_shortcut_fallback`
- `test_stage_3_fallback_triggers_replan`
- `test_extended_failure_classifications_diagnosis`

## `.\planner\tests\test_resource_cleanup_phase6.py`
**Functions:**
- `test_cleanup_after_successful_multistep_task`
- `test_cleanup_after_stop_signal`
- `test_cleanup_after_task_timeout`
- `test_cleanup_after_consequential_safety_block`

## `.\planner\tests\test_resource_governor.py`
**Functions:**
- `test_screenshot_ring_buffer_bounded_capacity`
- `test_resource_governor_measurement_breakdown`
- `test_adaptive_observation_interval`

## `.\planner\tests\test_risk_classifier.py`
**Functions:**
- `test_risk_click_delete_is_high`
- `test_risk_click_open_menu_is_low`
- `test_risk_click_submit_is_high`
- `test_risk_alt_f4_combination_is_high`
- `test_risk_observe_and_highlight_are_low`

## `.\planner\tests\test_security_guards.py`
**Functions:**
- `test_reject_powershell_in_parameters`
- `test_reject_cmd_in_parameters`
- `test_reject_python_in_target_description`
- `test_reject_rm_in_parameters`
- `test_screen_content_prompt_injection_defense`
- `test_malicious_model_proposal_cannot_reach_os_execution`
- `test_prompt_injection_vectors_all_neutralized`

## `.\planner\tests\test_security_phase5.py`
**Functions:**
- `test_malformed_planner_output_rejected`
- `test_unknown_action_type_rejected`
- `test_action_parameter_bounds_and_schema`
- `test_hallucinated_target_fails_revalidation`
- `test_planner_cannot_bypass_human_approval`
- `test_protected_window_safety`
- `test_prompt_injection_in_ui_text_sanitized`
- `test_context_builder_quarantines_untrusted_screen_text`
- `test_bearer_token_redacted_from_logs`
- `test_api_key_redacted_from_logs`
- `test_password_redacted_from_logs`

## `.\planner\tests\test_security_phase6.py`
**Functions:**
- `test_action_injection_rejection`
- `test_observed_prompt_injection_safety`
- `test_consequential_approval_stale_invalidation`
- `test_trace_manager_credential_redaction`
- `test_checkpoint_redaction_and_integrity`

## `.\planner\tests\test_stale_guard.py`
**Functions:**
- `test_stale_guard_fresh_observation`
- `test_stale_guard_normal_expired_over_5000ms`
- `test_stale_guard_sensitive_threshold_2000ms`
- `test_stale_guard_target_element_disappeared`
- `test_stale_guard_bounds_drift_detected`
- `test_stale_guard_dead_hwnd_detected`
- `test_stale_guard_element_disabled`
- `test_stale_guard_element_invisible`

## `.\planner\tests\test_target_resolver.py`
**Classes:**
- `TestTargetResolver`
**Functions:**
- `setup_method`
- `test_resolve_by_runtime_id`
- `test_resolve_by_automation_id`
- `test_resolve_ambiguity_rejected`
- `test_resolve_non_existent`

## `.\planner\tests\test_task_decomposer.py`
**Functions:**
- `test_decompose_notepad_template`
- `test_decompose_notepad_with_save`
- `test_decompose_calculator_template`
- `test_decompose_rule_based_conjunctions`
- `test_plan_validator_consequential_risk_enforcement`
- `test_plan_validator_step_limit_enforced`

## `.\planner\tests\test_verification_engine.py`
**Classes:**
- `TestVerificationEngine`
**Functions:**
- `setup_method`
- `test_wait_verification`
- `test_text_verification_success`
- `test_text_verification_failure`

## `.\planner\tests\test_workflow_api.py`
**Functions:**
- `test_api_create_and_get_workflow`
- `test_api_list_workflows`
- `test_api_stop_workflow`
- `test_api_pause_and_resume`
- `test_api_invalid_dag_rejected`

## `.\planner\tests\test_workflow_concurrency.py`
**Functions:**
- `test_deadlock_free_lock_ordering`
- `test_concurrent_independent_nodes`
- `test_serialized_ui_actions`
- `worker_A`
- `worker_B`
- `custom_executor`

## `.\planner\tests\test_workflow_dag.py`
**Functions:**
- `test_dag_validation_success`
- `test_dag_validation_cycle`
- `test_dag_validation_missing_dep`
- `test_get_ready_nodes`
- `test_max_depth_exceeded`

## `.\planner\tests\test_workflow_loop_detection.py`
**Functions:**
- `test_repeated_action_failure_detection`
- `test_state_oscillation_detection`

## `.\planner\tests\test_workflow_models.py`
**Functions:**
- `test_workflow_status_count`
- `test_node_status_count`
- `test_workflow_legal_transitions`
- `test_workflow_illegal_transitions`
- `test_node_legal_transitions`
- `test_node_illegal_transitions`
- `test_resource_budget_defaults_and_validation`
- `test_retry_policy_logic`
- `test_workflow_generation_fencing`

## `.\planner\tests\test_workflow_orchestrator.py`
**Functions:**
- `orchestrator`

## `.\planner\tests\test_workflow_partial.py`
**Functions:**
- `test_partial_completion_independent_branches`
- `branch_executor`

## `.\planner\tests\test_workflow_pause_resume.py`
**Functions:**
- `test_pause_and_resume_lifecycle`
- `test_pause_invalid_state`

## `.\planner\tests\test_workflow_recovery.py`
**Functions:**
- `test_checkpoint_save_and_load`
- `test_checkpoint_not_found`
- `test_checkpoint_tampering`
- `test_checkpoint_clear`

## `.\planner\tests\test_workflow_resource.py`
**Functions:**
- `test_resource_governor_node_budget`
- `test_resource_governor_active_workflows`
- `test_resource_governor_concurrent_nodes`
- `test_resource_governor_measured_snapshot`

## `.\planner\tests\test_workflow_retry.py`
**Functions:**
- `test_transient_retry_succeeds`
- `test_retry_exhaustion_cascades_failure`
- `failing_first_executor`
- `always_fail_executor`

## `.\planner\tests\test_workflow_scheduler.py`
**Functions:**
- `test_scheduler_concurrency`

## `.\planner\tests\test_workflow_security.py`
**Functions:**
- `test_high_risk_node_approval_gating`
- `test_secret_redaction_in_checkpoint`
- `test_secret_redaction_in_trace`

## `.\planner\tests\test_workflow_stop.py`
**Functions:**
- `test_universal_stop_transitions_and_fencing`
- `slow_executor`

## `.\planner\tests\test_workflow_timeout.py`
**Functions:**
- `test_workflow_deadline_timeout`
- `slow_executor`

## `.\planner\workflow\dag.py`
**Classes:**
- `DAGValidationError`
- `DAGEngine`
**Functions:**
- `__init__`
- `validate_and_sort`
- `get_ready_nodes`

## `.\planner\workflow\models.py`
**Classes:**
- `WorkflowState`
- `NodeState`
- `RetryPolicy`
- `WorkflowNode`
- `WorkflowGraph`

## `.\planner\workflow\orchestrator.py`
**Classes:**
- `WorkflowOrchestrator`
**Functions:**
- `__init__`
- `register_action`
- `submit_workflow`
- `_save_state`
- `stop_workflow`

## `.\planner\workflow\recovery.py`
**Classes:**
- `CheckpointCorruptedError`
- `CheckpointManager`
**Functions:**
- `__init__`
- `_get_path`
- `_generate_hmac`
- `save_checkpoint`
- `load_checkpoint`
- `clear_checkpoint`

## `.\planner\workflow\scheduler.py`
**Classes:**
- `LockManager`
- `Scheduler`
**Functions:**
- `__init__`
- `__init__`
- `can_schedule`
- `mark_scheduled`
- `mark_completed`

## `.\providers\ai_provider.py`
**Classes:**
- `PlanningRequest`
- `PlannedAction`
- `PlanningResult`
- `AIPlannerProvider`
- `_DisabledAIProvider`
- `ModelRouterProvider`
**Functions:**
- `name`
- `is_available`
- `plan`
- `name`
- `is_available`
- `plan`
- `__init__`
- `register`
- `set_active`
- `get_active`
- `get_status`

## `.\providers\hardware_detector.py`
**Functions:**
- `get_system_hardware`

## `.\providers\omniroute_provider.py`
**Classes:**
- `OmniRouteErrorCode`
- `ModelMetadata`
- `OmniRouteProvider`
**Functions:**
- `__init__`
- `to_safe_dict`
- `__init__`
- `name`
- `base_url`
- `free_only`
- `resolve_api_key`
- `check_health`
- `is_available`
- `is_model_free`
- `discover_models`
- `get_permitted_models`
- `select_active_model`
- `validate_model_capabilities`
- `chat_completion`
- `plan`

## `.\providers\screen_provider.py`
**Classes:**
- `ScreenProvider`
**Functions:**
- `capture_region`
- `capture_foreground`
- `capture_element`
- `capture_full_screen`
- `get_capabilities`

## `.\providers\uia_provider.py`
**Classes:**
- `UIAProvider`
**Functions:**
- `get_foreground_window`
- `get_element_tree`
- `find_by_name`
- `find_by_type`
- `revalidate`
- `get_status`

## `.\providers\tests\test_providers.py`
**Classes:**
- `TestAIProviderStub`
- `TestPerceptionProviders`
**Functions:**
- `test_disabled_provider_properties`
- `test_disabled_provider_plan_returns_disabled_error`
- `test_model_router_status`
- `test_planning_request_dataclass`
- `test_planned_action_dataclass`
- `test_uia_provider_metadata`
- `test_screen_provider_metadata`
- `test_screen_provider_capabilities`

## `.\scripts\audit_phase2_verification.py`
**Functions:**
- `kill_all_notepad`
- `find_notepad_window`
- `audit_test_1_real_click`
- `audit_test_2_real_keyboard`
- `audit_test_3_stale_element`
- `audit_test_4_invalid_targets`
- `audit_test_5_protected_windows`
- `audit_test_6_stop_cancellation`
- `audit_test_7_screen_capture_resource_leak`
- `audit_test_8_privacy`
- `audit_test_9_portability`
- `main`
- `_enum`
- `on_snapshot`

## `.\scripts\audit_phase3_acceptance.py`
**Functions:**
- `kill_notepad`
- `find_notepad_hwnd`
- `log_audit_header`
- `main`
- `_enum`
- `on_e2e_event`
- `on_retry_event`

## `.\scripts\audit_phase4_acceptance.py`
**Functions:**
- `kill_process_by_name`
- `find_window_by_substr`
- `find_window_for_pid`
- `log_header`
- `main`
- `_enum`
- `_enum`
- `on_event`

## `.\scripts\audit_security_secrets.py`
**Functions:**
- `scan_repository`

## `.\scripts\benchmark_phase14.py`
**Functions:**
- `get_process_memory_mb`
- `get_vram_info`
- `measure_storage`
- `measure_latencies_and_throughput`
- `measure_cpu_and_ram`
- `measure_emergency_stop_response`
- `check_orphan_processes`
- `collect_hardware_profile`
- `main`
- `get_dir_size`

## `.\scripts\build_repository_inventory.py`
**Functions:**
- `analyze_python_file`
- `generate_inventory`

## `.\scripts\demo_chatgpt_guide.py`
**Functions:**
- `inject_guide_styles`
- `show_guide`
- `run_chatgpt_guide`

## `.\scripts\e2e_integration_test.py`
**Functions:**
- `run_integration_test`

## `.\scripts\evaluate_external_qa.py`
**Functions:**
- `evaluate_external_qa`

## `.\scripts\map_project.py`
**Functions:**
- `get_ast_info`

## `.\scripts\measure_baseline.py`
**Functions:**
- `measure`

## `.\scripts\run_phase10_tests.py`
**Functions:**
- `run_command_capture`
- `audit_repository_security`
- `execute_master_runner`

## `.\scripts\run_phase11_tests.py`
**Functions:**
- `get_hardware_profile`
- `run_command`
- `main`

## `.\scripts\run_phase12_tests.py`
**Functions:**
- `get_hardware_profile`
- `run_command`
- `main`

## `.\scripts\run_phase13_tests.py`
**Functions:**
- `run_stage`
- `collect_hardware_profile`
- `main`

## `.\scripts\run_phase14_tests.py`
**Functions:**
- `run_stage`
- `collect_hardware_profile`
- `main`

## `.\scripts\run_phase1_tests.py`
**Functions:**
- `is_port_open`
- `kill_tree`
- `run_step`
- `main`

## `.\scripts\run_phase2_tests.py`
**Functions:**
- `is_port_open`
- `kill_tree`
- `run_step`
- `main`
- `_enum_np`

## `.\scripts\run_phase3_tests.py`
**Functions:**
- `run_step`
- `run_pytest`
- `main`

## `.\scripts\run_phase4_tests.py`
**Functions:**
- `run_step`
- `run_pytest`
- `main`

## `.\scripts\run_phase5_tests.py`
**Functions:**
- `run_step`
- `parse_pytest_metrics`
- `run_pytest`
- `main`

## `.\scripts\run_phase6_tests.py`
**Functions:**
- `run_step`
- `parse_pytest_metrics`
- `run_pytest`
- `main`

## `.\scripts\run_phase7_tests.py`
**Functions:**
- `is_port_open`
- `run_gate_header`
- `parse_pytest_metrics`
- `run_pytest_command`
- `run_script_command`
- `main`
- `record_gate`

## `.\scripts\run_phase8_tests.py`
**Functions:**
- `is_port_open`
- `run_gate_header`
- `parse_pytest_metrics`
- `run_pytest_command`
- `run_script_command`
- `main`
- `record_gate`

## `.\scripts\run_phase9_tests.py`
**Functions:**
- `run_tests`

## `.\scripts\start_compass.py`
**Functions:**
- `is_port_in_use`
- `save_pids`
- `load_pids`
- `start_backend`
- `start_frontend`
- `start_overlay`
- `main`
- `handle_signal`

## `.\scripts\stop_compass.py`
**Functions:**
- `is_port_in_use`
- `is_compass_process`
- `terminate_process_tree`
- `free_port_if_compass`
- `stop_compass`

## `.\scripts\test_adversarial_phase13.py`
**Functions:**
- `find_window_by_substr`
- `record_attack_result`
- `attack_01_malformed_empty_goal`
- `attack_02_prompt_injection_goal`
- `attack_03_prompt_injection_window_title`
- `attack_04_ai_malicious_destructive_command`
- `attack_05_out_of_bounds_coordinate_dispatch`
- `attack_06_target_element_drift_displacement`
- `attack_07_target_element_destroyed_pre_dispatch`
- `attack_08_verification_failure_withheld_state`
- `attack_09_consequential_action_blocks_automatic_retry`
- `attack_10_loop_and_state_oscillation_circuit_breaker`
- `attack_11_state_machine_terminal_immutability`
- `attack_12_emergency_stop_preemption_latency`
- `attack_13_emergency_stop_mid_dag_universal_freeze`
- `attack_14_late_ai_response_neutralization`
- `attack_15_approval_context_invalidation`
- `attack_16_checkpoint_cryptographic_tamper_rejection`
- `attack_17_application_crash_hwnd_reconciliation`
- `attack_18_backend_reboot_orphan_task_sweep`
- `attack_19_sse_transport_interruption_resilience`
- `attack_20_secret_token_zero_leakage`
- `run_adversarial_campaign`
- `_enum`

## `.\scripts\test_real_windows_phase10.py`
**Functions:**
- `safe_kill_process_by_name`
- `find_window_by_substr`
- `save_evidence`
- `test_workflow_A`
- `test_workflow_B`
- `test_workflow_C`
- `test_workflow_D`
- `test_workflow_E`
- `test_workflow_F`
- `test_workflow_G`
- `test_workflow_H`
- `test_workflow_I`
- `test_workflow_J`
- `test_workflow_K`
- `test_workflow_L`
- `run_all_workflows`
- `_enum`

## `.\scripts\test_real_windows_phase12.py`
**Functions:**
- `safe_kill_process_by_name`
- `find_window_by_substr`
- `save_evidence`
- `test_workflow_A`
- `test_workflow_B`
- `test_workflow_C`
- `test_workflow_D`
- `test_workflow_E`
- `test_workflow_F`
- `test_workflow_G`
- `test_workflow_H`
- `test_workflow_I`
- `test_workflow_J`
- `test_workflow_K`
- `test_workflow_L`
- `test_workflow_M`
- `test_workflow_N`
- `test_workflow_O`
- `test_workflow_P`
- `test_workflow_Q`
- `test_workflow_R`
- `test_workflow_S`
- `test_workflow_T`
- `test_workflow_U`
- `test_workflow_V`
- `test_workflow_W`
- `test_workflow_X`
- `run_all_workflows`
- `_enum`

## `.\scripts\test_real_windows_phase5.py`
**Functions:**
- `safe_kill_process_by_name`
- `find_window_by_substr`
- `find_window_for_pid`
- `ensure_evidence_dir`
- `save_screenshot_evidence`
- `run_workflow_A`
- `run_workflow_B`
- `run_workflow_C`
- `run_workflow_D`
- `run_workflow_E`
- `run_workflow_F`
- `run_workflow_G`
- `run_workflow_H`
- `run_all_workflows`
- `_enum`
- `_enum`
- `log`
- `log`
- `log`

## `.\scripts\test_real_windows_phase6.py`
**Functions:**
- `safe_kill_process_by_name`
- `find_window_by_substr`
- `capture_evidence_bundle`
- `run_workflow_A`
- `run_workflow_B`
- `run_workflow_C`
- `run_workflow_D`
- `run_workflow_E`
- `run_workflow_F`
- `run_workflow_G`
- `run_workflow_H`
- `run_workflow_I`
- `run_workflow_J`
- `main`
- `_enum`

## `.\scripts\test_real_windows_phase7.py`
**Functions:**
- `safe_kill_process_by_name`
- `find_window_by_substr`
- `capture_workflow_bundle`
- `run_workflow_A`
- `run_workflow_B`
- `run_workflow_C`
- `run_workflow_D`
- `run_workflow_E`
- `run_workflow_F`
- `run_workflow_G`
- `run_workflow_H`
- `run_workflow_I`
- `run_workflow_J`
- `run_workflow_K`
- `run_workflow_L`
- `run_workflow_M`
- `run_all_workflows`
- `_enum`

## `.\scripts\test_real_windows_phase8.py`
**Functions:**
- `safe_kill_process_by_name`
- `find_window_by_substr`
- `save_evidence`
- `test_workflow_A`
- `test_workflow_B`
- `test_workflow_C`
- `test_workflow_D`
- `test_workflow_E`
- `test_workflow_F`
- `test_workflow_G`
- `test_workflow_H`
- `test_workflow_I`
- `test_workflow_J`
- `test_workflow_K`
- `test_workflow_L`
- `test_workflow_M`
- `test_workflow_N`
- `test_workflow_O`
- `test_workflow_P`
- `test_workflow_Q`
- `test_workflow_R`
- `run_all_workflows`
- `calc_executor`
- `cross_app_executor`
- `slow_exec`
- `retry_exec`
- `branch_exec`
- `_enum`

## `.\scripts\test_stability_phase10.py`
**Functions:**
- `query_gpu_vram`
- `execute_stability_task`
- `run_stability_suite`

## `.\scripts\universality_test.py`
**Functions:**
- `run_universality_test`

## `.\scripts\validate_env.py`
**Functions:**
- `check_os`
- `check_python`
- `check_node`
- `check_npm`
- `check_python_packages`
- `check_port`
- `check_filesystem`
- `check_win32_ctypes`
- `run_all_checks`

