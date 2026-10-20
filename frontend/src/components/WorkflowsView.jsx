import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';

export default function WorkflowsView({ language = 'en', onOpenTelemetry }) {
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const isKannada = language === 'kn';

  const t = {
    title: isKannada ? 'ಸ್ವಾಯತ್ತ ಕಾರ್ಯಪ್ರವಾಹಗಳು (DAG)' : 'Autonomous Workflows (DAG Engine)',
    subtitle: isKannada
      ? 'ಪರಸ್ಪರ ಅವಲಂಬಿತ ಮಲ್ಟಿ-ಅಪ್ಲಿಕೇಶನ್ ಕಾರ್ಯಗಳನ್ನು ವ್ಯವಸ್ಥಿತವಾಗಿ ನಿರ್ವಹಿಸಿ.'
      : 'Execute complex multi-step workflows with dependency DAGs, resource limits, and crash recovery.',
    newWorkflow: isKannada ? 'ಹೊಸ ಕಾರ್ಯಪ್ರವಾಹ' : 'New Workflow',
    refresh: isKannada ? 'ನವೀಕರಿಸಿ' : 'Refresh',
    emptyTitle: isKannada ? 'ಯಾವುದೇ ಸಕ್ರಿಯ ಕಾರ್ಯಪ್ರವಾಹಗಳಿಲ್ಲ' : 'No Workflows Found',
    emptySubtitle: isKannada
      ? 'ಪ್ರಾರಂಭಿಸಲು ಕೆಳಗಿನ ಸಿದ್ಧ ಮಾದರಿಯನ್ನು ಆಯ್ಕೆಮಾಡಿ.'
      : 'Deploy a verified DAG workflow template below to begin.',
    nodesLabel: isKannada ? 'ಹಂತಗಳು (ನೋಡ್‌ಗಳು)' : 'Workflow Nodes (DAG)',
    progressLabel: isKannada ? 'ಪ್ರಗತಿ' : 'Progress',
    startBtn: isKannada ? 'ಪ್ರಾರಂಭಿಸಿ' : 'Start Workflow',
    stopBtn: isKannada ? 'ನಿಲ್ಲಿಸಿ' : 'Emergency STOP',
    pauseBtn: isKannada ? 'ವಿರಾಮ' : 'Pause',
    resumeBtn: isKannada ? 'ಮುಂದುವರಿಸಿ' : 'Resume',
    recoverBtn: isKannada ? 'ಚೆಕ್‌ಪಾಯಿಂಟ್ ಮರುಸ್ಥಾಪನೆ' : 'Recover Checkpoint',
  };

  const fetchWorkflows = useCallback(async () => {
    try {
      setLoading(true);
      const list = await api.listWorkflows(20);
      setWorkflows(Array.isArray(list) ? list : (list?.items || []));
      setError('');
    } catch (err) {
      console.warn('Failed to fetch workflows:', err);
      setError(err.message || 'Failed to load workflows.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
    const interval = setInterval(fetchWorkflows, 3000);
    return () => clearInterval(interval);
  }, [fetchWorkflows]);

  const handleSelectWorkflow = async (id) => {
    try {
      const wf = await api.getWorkflow(id);
      setSelectedWorkflow(wf);
    } catch (err) {
      setError(err.message || 'Failed to load workflow details.');
    }
  };

  const handleStartWorkflow = async (id) => {
    try {
      setActionLoading(true);
      await api.startWorkflow(id);
      await fetchWorkflows();
      if (selectedWorkflow?.workflow_id === id) {
        const updated = await api.getWorkflow(id);
        setSelectedWorkflow(updated);
      }
    } catch (err) {
      setError(err.message || 'Failed to start workflow.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopWorkflow = async (id) => {
    try {
      setActionLoading(true);
      await api.stopWorkflow(id, 'User stopped via DAG UI');
      await fetchWorkflows();
      if (selectedWorkflow?.workflow_id === id) {
        const updated = await api.getWorkflow(id);
        setSelectedWorkflow(updated);
      }
    } catch (err) {
      setError(err.message || 'Failed to stop workflow.');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePauseWorkflow = async (id) => {
    try {
      setActionLoading(true);
      await api.pauseWorkflow(id);
      await fetchWorkflows();
      if (selectedWorkflow?.workflow_id === id) {
        const updated = await api.getWorkflow(id);
        setSelectedWorkflow(updated);
      }
    } catch (err) {
      setError(err.message || 'Failed to pause workflow.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleResumeWorkflow = async (id) => {
    try {
      setActionLoading(true);
      await api.resumeWorkflow(id);
      await fetchWorkflows();
      if (selectedWorkflow?.workflow_id === id) {
        const updated = await api.getWorkflow(id);
        setSelectedWorkflow(updated);
      }
    } catch (err) {
      setError(err.message || 'Failed to resume workflow.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateTemplate = async (templateName) => {
    let workflowData;
    const now = Date.now();
    if (templateName === 'system_audit') {
      workflowData = {
        goal: 'Autonomous System Health & Telemetry Audit',
        workflow_id: `wf-audit-${now}`,
        nodes: [
          {
            node_id: 'check_resources',
            goal: 'Sample host CPU, memory, and disk health metrics',
            operation: 'ui_action',
            priority: 8,
            risk_level: 'LOW',
            dependencies: [],
          },
          {
            node_id: 'capture_desktop',
            goal: 'Capture current foreground window and active controls',
            operation: 'ui_action',
            priority: 6,
            risk_level: 'LOW',
            dependencies: ['check_resources'],
          },
          {
            node_id: 'verify_state',
            goal: 'Perform OCR and checksum verification on desktop state',
            operation: 'ui_action',
            priority: 5,
            risk_level: 'LOW',
            dependencies: ['capture_desktop'],
          },
        ],
        auto_start: true,
      };
    } else if (templateName === 'data_export') {
      workflowData = {
        goal: 'Extract Foreground Tables into Structured Archive',
        workflow_id: `wf-export-${now}`,
        nodes: [
          {
            node_id: 'detect_tables',
            goal: 'Identify tabular structures on active screen',
            operation: 'ui_action',
            priority: 7,
            risk_level: 'LOW',
            dependencies: [],
          },
          {
            node_id: 'parse_ocr',
            goal: 'Extract textual table cells with WinRT OCR',
            operation: 'ui_action',
            priority: 6,
            risk_level: 'LOW',
            dependencies: ['detect_tables'],
          },
          {
            node_id: 'save_summary',
            goal: 'Save extracted data to local workspace archive',
            operation: 'ui_action',
            priority: 5,
            risk_level: 'MEDIUM',
            dependencies: ['parse_ocr'],
          },
        ],
        auto_start: false,
      };
    } else {
      workflowData = {
        goal: 'Cross-Application Data Transfer Pipeline',
        workflow_id: `wf-transfer-${now}`,
        nodes: [
          {
            node_id: 'focus_source',
            goal: 'Focus source window and copy target data',
            operation: 'ui_action',
            priority: 7,
            risk_level: 'LOW',
            dependencies: [],
          },
          {
            node_id: 'focus_dest',
            goal: 'Switch to destination window and paste content',
            operation: 'ui_action',
            priority: 6,
            risk_level: 'MEDIUM',
            dependencies: ['focus_source'],
          },
          {
            node_id: 'verify_paste',
            goal: 'Verify content matches clipboard checksum',
            operation: 'ui_action',
            priority: 5,
            risk_level: 'LOW',
            dependencies: ['focus_dest'],
          },
        ],
        auto_start: false,
      };
    }

    try {
      setActionLoading(true);
      const created = await api.createWorkflow(workflowData);
      await fetchWorkflows();
      setSelectedWorkflow(created);
    } catch (err) {
      setError(err.message || 'Failed to create workflow.');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto py-8 px-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[26px] text-blue-400">account_tree</span>
            {t.title}
          </h1>
          <p className="text-sm text-gray-400 mt-1">{t.subtitle}</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchWorkflows}
            disabled={loading}
            className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-gray-300 hover:text-white transition-all flex items-center gap-1.5 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          >
            <span className={`material-symbols-outlined text-[15px] ${loading ? 'animate-spin' : ''}`}>sync</span>
            {t.refresh}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-xs text-red-300 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="text-red-400 hover:text-white text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Templates Row */}
      <div className="p-4 bg-white/[0.02] border border-white/5 rounded-2xl">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Instant DAG Templates
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <button
            onClick={() => handleCreateTemplate('system_audit')}
            disabled={actionLoading}
            className="p-3.5 text-left rounded-xl bg-[#14161b] border border-white/5 hover:border-blue-500/40 hover:bg-white/[0.04] transition-all group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-white group-hover:text-blue-400 transition-colors">
              <span className="material-symbols-outlined text-[16px] text-emerald-400">monitoring</span>
              System Health & State Audit
            </div>
            <p className="text-[11px] text-gray-400 mt-1.5 leading-relaxed">
              3-node DAG: Samples CPU/RAM, checks active window, and verifies OCR checksum.
            </p>
          </button>

          <button
            onClick={() => handleCreateTemplate('data_export')}
            disabled={actionLoading}
            className="p-3.5 text-left rounded-xl bg-[#14161b] border border-white/5 hover:border-blue-500/40 hover:bg-white/[0.04] transition-all group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-white group-hover:text-blue-400 transition-colors">
              <span className="material-symbols-outlined text-[16px] text-blue-400">table_chart</span>
              Screen Table Data Extraction
            </div>
            <p className="text-[11px] text-gray-400 mt-1.5 leading-relaxed">
              3-node DAG: Detects table boundaries, extracts text via OCR, and stages structured CSV.
            </p>
          </button>

          <button
            onClick={() => handleCreateTemplate('cross_app')}
            disabled={actionLoading}
            className="p-3.5 text-left rounded-xl bg-[#14161b] border border-white/5 hover:border-blue-500/40 hover:bg-white/[0.04] transition-all group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          >
            <div className="flex items-center gap-2 text-xs font-semibold text-white group-hover:text-blue-400 transition-colors">
              <span className="material-symbols-outlined text-[16px] text-purple-400">move_up</span>
              Cross-App Transfer Pipeline
            </div>
            <p className="text-[11px] text-gray-400 mt-1.5 leading-relaxed">
              3-node DAG: Captures from source, transfers to destination, and verifies clipboard digest.
            </p>
          </button>
        </div>
      </div>

      {/* Main Workflows Layout: List on left, details on right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Workflows List */}
        <div className="lg:col-span-1 bg-[#121418] border border-white/5 rounded-2xl p-4 flex flex-col h-[520px]">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Active & Stored Graphs ({workflows.length})
          </h2>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin scrollbar-thumb-white/10">
            {workflows.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-4 text-gray-500">
                <span className="material-symbols-outlined text-[32px] mb-2 opacity-50">schema</span>
                <p className="text-xs">{t.emptyTitle}</p>
                <p className="text-[11px] text-gray-600 mt-1">{t.emptySubtitle}</p>
              </div>
            ) : (
              workflows.map((wf) => {
                const id = wf.workflow_id || wf.id;
                const isSelected = selectedWorkflow?.workflow_id === id || selectedWorkflow?.id === id;
                const status = (wf.status || wf.state || 'PENDING').toUpperCase();
                return (
                  <button
                    key={id}
                    onClick={() => handleSelectWorkflow(id)}
                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                      isSelected
                        ? 'bg-blue-600/15 border-blue-500/40 shadow-sm'
                        : 'bg-white/[0.02] border-white/5 hover:border-white/15'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-white truncate max-w-[160px]">
                        {wf.goal || id}
                      </span>
                      <span
                        className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                          status === 'RUNNING'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40 animate-pulse'
                            : status === 'COMPLETED'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : status === 'PAUSED'
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : status === 'STOPPED' || status === 'FAILED'
                            ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                            : 'bg-white/5 text-gray-400 border border-white/10'
                        }`}
                      >
                        {status}
                      </span>
                    </div>

                    <div className="text-[10px] text-gray-500 mt-1.5 flex items-center gap-2 font-mono">
                      <span>ID: {id.substring(0, 12)}...</span>
                      <span>·</span>
                      <span>Nodes: {wf.nodes?.length || wf.node_count || 0}</span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Selected Workflow Inspector / Visual DAG */}
        <div className="lg:col-span-2 bg-[#121418] border border-white/5 rounded-2xl p-6 flex flex-col h-[520px]">
          {selectedWorkflow ? (
            <div className="flex flex-col h-full overflow-hidden">
              {/* Detail Header */}
              <div className="flex items-start justify-between pb-4 border-b border-white/10 flex-shrink-0">
                <div>
                  <h3 className="text-base font-semibold text-white">
                    {selectedWorkflow.goal}
                  </h3>
                  <div className="text-xs text-gray-400 mt-1 flex items-center gap-2 font-mono">
                    <span>Workflow ID: {selectedWorkflow.workflow_id || selectedWorkflow.id}</span>
                    <span>·</span>
                    <span className="text-blue-400 uppercase font-bold">
                      {selectedWorkflow.status || 'CREATED'}
                    </span>
                  </div>
                </div>

                {/* Workflow Actions */}
                <div className="flex items-center gap-2">
                  {selectedWorkflow.status === 'CREATED' || selectedWorkflow.status === 'PENDING' ? (
                    <button
                      onClick={() => handleStartWorkflow(selectedWorkflow.workflow_id || selectedWorkflow.id)}
                      disabled={actionLoading}
                      className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl transition-all shadow-md flex items-center gap-1 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
                    >
                      <span className="material-symbols-outlined text-[15px]">play_arrow</span>
                      {t.startBtn}
                    </button>
                  ) : null}

                  {selectedWorkflow.status === 'RUNNING' ? (
                    <>
                      <button
                        onClick={() => handlePauseWorkflow(selectedWorkflow.workflow_id || selectedWorkflow.id)}
                        disabled={actionLoading}
                        className="px-3 py-1.5 bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-medium rounded-xl hover:bg-amber-500/30 transition-all flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-[14px]">pause</span>
                        {t.pauseBtn}
                      </button>
                      <button
                        onClick={() => handleStopWorkflow(selectedWorkflow.workflow_id || selectedWorkflow.id)}
                        disabled={actionLoading}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-semibold rounded-xl transition-all shadow-md flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-[14px]">stop</span>
                        {t.stopBtn}
                      </button>
                    </>
                  ) : null}

                  {selectedWorkflow.status === 'PAUSED' ? (
                    <button
                      onClick={() => handleResumeWorkflow(selectedWorkflow.workflow_id || selectedWorkflow.id)}
                      disabled={actionLoading}
                      className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-xl transition-all shadow-md flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-[15px]">play_arrow</span>
                      {t.resumeBtn}
                    </button>
                  ) : null}
                </div>
              </div>

              {/* DAG Nodes List */}
              <div className="flex-1 overflow-y-auto my-4 pr-1 space-y-3 scrollbar-thin scrollbar-thumb-white/10">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  {t.nodesLabel} ({selectedWorkflow.nodes?.length || 0})
                </div>

                {(selectedWorkflow.nodes || []).map((node, idx) => {
                  const nodeStatus = (node.status || 'PENDING').toUpperCase();
                  return (
                    <div
                      key={node.node_id || idx}
                      className="p-3.5 bg-[#171920] border border-white/5 rounded-xl flex items-start gap-3.5"
                    >
                      <div className="w-6 h-6 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-mono font-bold flex-shrink-0 mt-0.5">
                        {idx + 1}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-white truncate font-mono">
                            {node.node_id}
                          </span>
                          <span
                            className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase tracking-wider ${
                              nodeStatus === 'COMPLETED'
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                : nodeStatus === 'RUNNING'
                                ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30 animate-pulse'
                                : nodeStatus === 'FAILED'
                                ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                                : 'bg-white/5 text-gray-400 border border-white/10'
                            }`}
                          >
                            {nodeStatus}
                          </span>
                        </div>

                        <p className="text-xs text-gray-300 mt-1 leading-snug">
                          {node.goal || node.description}
                        </p>

                        <div className="mt-2 flex items-center gap-3 text-[10px] text-gray-400 font-mono">
                          <span>Op: {node.operation || 'ui_action'}</span>
                          {node.dependencies?.length > 0 && (
                            <span>Depends on: [{node.dependencies.join(', ')}]</span>
                          )}
                          <span>Risk: {node.risk_level || 'LOW'}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-gray-500">
              <span className="material-symbols-outlined text-[40px] mb-2 opacity-40">alt_route</span>
              <p className="text-sm font-medium text-gray-400">Select a workflow to inspect its DAG</p>
              <p className="text-xs text-gray-500 mt-1">
                You can review node dependencies, execution status, and checkpoints.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
