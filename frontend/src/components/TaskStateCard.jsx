import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function TaskStateCard({
  task,
  onRunTask = () => {},
  onStop = () => {},
  pendingApproval = null,
  onConfirmAction = () => {},
  language = 'en',
  onDismiss = null,
}) {
  const [showDetails, setShowDetails] = useState(false);
  const isKannada = language === 'kn';

  if (!task) {
    return (
      <div className="glass-card rounded-2xl p-6 min-h-[12rem] flex flex-col justify-center items-center text-center relative overflow-hidden border-dashed border-white/10">
        <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center mb-3 text-gray-500">
          <span className="material-symbols-outlined text-[22px]">terminal</span>
        </div>
        <p className="text-sm font-medium text-gray-300">
          {isKannada ? 'ಯಾವುದೇ ಸಕ್ರಿಯ ಕಾರ್ಯವಿಲ್ಲ' : 'Standby · Ready for instructions'}
        </p>
        <p className="text-xs text-gray-500 mt-1 max-w-sm">
          {isKannada
            ? 'ಮೇಲಿನ ಇನ್‌ಪುಟ್‌ನಲ್ಲಿ ಗುರಿ ನಮೂದಿಸಿ ಪ್ರಾರಂಭಿಸಿ.'
            : 'Type a task prompt above or pick a suggestion chip to begin.'}
        </p>
      </div>
    );
  }

  const { state = '', events = [], metadata = {}, goal = '' } = task;
  const isActing = state === 'ACTING' || state === 'EXECUTING';
  const isWaitingConfirmation = state === 'WAITING_CONFIRMATION';
  const isCompleted = state === 'COMPLETED' || state === 'TASK_COMPLETED';
  const isFailed = state === 'FAILED' || state === 'TASK_FAILED' || state === 'BLOCKED' || state === 'SAFETY_BLOCKED' || state === 'AI_UNAVAILABLE';
  const isStopped = state === 'STOPPED' || state === 'CANCELLED';

  const TERMINAL_STATES = [
    'COMPLETED',
    'TASK_COMPLETED',
    'FAILED',
    'TASK_FAILED',
    'STOPPED',
    'CANCELLED',
    'BLOCKED',
    'SAFETY_BLOCKED',
    'UNVERIFIED',
    'AI_UNAVAILABLE',
  ];
  const isTerminal = TERMINAL_STATES.includes(state);
  const canRetry = isFailed || isStopped;

  // Extract completed event evidence
  const completedEvent = events.find((e) => e.event_type === 'task_completed');
  const failedEvent = events.find((e) => e.event_type === 'task_failed' || e.event_type === 'task_blocked');
  const stoppedEvent = events.find((e) => e.event_type === 'task_stopped');

  const verificationEvidence = completedEvent?.payload?.evidence || task.evidence || null;
  const completionDetails = completedEvent?.payload?.details || '';
  const failureReason = failedEvent?.payload?.reason || task.error || '';
  const stopReason = stoppedEvent?.payload?.reason || '';

  // Pending confirmation payload
  const confirmationEvent = events.slice().reverse().find((e) => e.event_type === 'waiting_confirmation')?.payload;
  const activeDecisionId = pendingApproval?.decision_id || confirmationEvent?.decision_id;
  const actionText = pendingApproval?.action || confirmationEvent?.action || 'Execute Step';
  const targetText = pendingApproval?.target || confirmationEvent?.target || 'Screen Element';
  const explanation = pendingApproval?.explanation || confirmationEvent?.explanation || 'Confirm execution of this UI action.';
  const riskLevel = (pendingApproval?.risk_level || confirmationEvent?.risk_level || 'MEDIUM').toUpperCase();

  // 9-Stage Agent Workflow Pipeline
  const STAGES = [
    { id: 'UNDERSTAND', label: 'Understand', match: ['UNDERSTANDING', 'STARTING', 'IDLE', 'CREATED'] },
    { id: 'PERCEIVE', label: 'Perceive', match: ['PERCEIVING', 'OBSERVING'] },
    { id: 'PLAN', label: 'Plan', match: ['PLANNING', 'DECOMPOSING', 'REPLANNING'] },
    { id: 'VALIDATE', label: 'Validate', match: ['VALIDATING', 'WORKFLOW_VALIDATING'] },
    { id: 'SAFETY', label: 'Safety', match: ['SAFETY_CHECK', 'WAITING_CONFIRMATION', 'WAITING_FOR_USER'] },
    { id: 'ACT', label: 'Act', match: ['ACTING', 'EXECUTING', 'READY_TO_ACT'] },
    { id: 'VERIFY', label: 'Verify', match: ['VERIFYING'] },
    { id: 'ADAPT', label: 'Adapt', match: ['ADAPTING', 'RECOVERING'] },
    { id: 'COMPLETE', label: 'Done', match: ['COMPLETED', 'TASK_COMPLETED'] },
  ];

  const currentStageIndex = STAGES.findIndex((s) => s.match.includes(state));
  const activeStageId = currentStageIndex >= 0 ? STAGES[currentStageIndex].id : (isCompleted ? 'COMPLETE' : 'UNDERSTAND');

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      transition={{ type: 'spring', stiffness: 260, damping: 25 }}
      className={`glass-card rounded-2xl p-5 sm:p-6 flex flex-col justify-between text-white relative overflow-hidden transition-all duration-300 border ${
        isCompleted
          ? 'border-emerald-500/30 shadow-[0_0_30px_rgba(16,185,129,0.12)]'
          : isWaitingConfirmation
          ? 'border-amber-500/40 shadow-[0_0_30px_rgba(245,158,11,0.18)]'
          : isFailed
          ? 'border-rose-500/30 shadow-[0_0_30px_rgba(244,63,94,0.12)]'
          : isActing
          ? 'border-blue-500/40 shadow-[0_0_30px_rgba(59,130,246,0.15)]'
          : 'border-white/10'
      }`}
    >
      {/* Active shimmer animation during execution */}
      {isActing && (
        <div className="absolute inset-0 animate-shimmer pointer-events-none opacity-25" />
      )}

      {/* Header: State Badge & Stage Stepper */}
      <div className="relative z-10 flex flex-col gap-3 w-full">
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Main Status Pill */}
            <span
              className={`text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full border flex items-center gap-1.5 ${
                isCompleted
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : isWaitingConfirmation
                  ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                  : isFailed
                  ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                  : isStopped
                  ? 'bg-gray-500/15 text-gray-300 border-gray-500/30'
                  : 'bg-blue-500/15 text-blue-300 border-blue-500/30'
              }`}
            >
              {isCompleted ? (
                <>
                  <span className="material-symbols-outlined text-[14px] text-emerald-400">check_circle</span>
                  {isKannada ? 'ಪೂರ್ಣಗೊಂಡಿದೆ' : 'COMPLETED & VERIFIED'}
                </>
              ) : isWaitingConfirmation ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  {isKannada ? 'ಅನುಮೋದನೆಗಾಗಿ ಕಾಯಲಾಗುತ್ತಿದೆ' : 'APPROVAL REQUIRED'}
                </>
              ) : isFailed ? (
                <>
                  <span className="material-symbols-outlined text-[14px] text-rose-400">error</span>
                  {isKannada ? 'ಕಾರ್ಯ ವಿಫಲವಾಗಿದೆ' : state}
                </>
              ) : isStopped ? (
                <>
                  <span className="material-symbols-outlined text-[14px] text-gray-400">cancel</span>
                  {isKannada ? 'ನಿಲ್ಲಿಸಲಾಗಿದೆ' : 'STOPPED'}
                </>
              ) : (
                <>
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                  {state}
                </>
              )}
            </span>

            {/* Verification Badge */}
            {isCompleted && (
              <span className="text-[10px] text-emerald-300 font-mono bg-emerald-950/50 border border-emerald-500/20 px-2.5 py-0.5 rounded-md flex items-center gap-1">
                <span className="material-symbols-outlined text-[13px]">verified</span>
                Verified Ground-Truth State
              </span>
            )}

            {/* Model Tag */}
            {metadata?.model_id && (
              <span className="text-[10px] text-gray-400 font-mono bg-white/[0.04] border border-white/5 px-2 py-0.5 rounded-md">
                {metadata.model_id}
              </span>
            )}
          </div>

          {/* Action / Trace Toggle */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="rounded-lg px-2 py-1 text-xs text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 flex items-center gap-1 transition-all focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
              title={showDetails ? 'Hide activity log' : 'Show activity log'}
              aria-expanded={showDetails}
            >
              <span className="material-symbols-outlined text-[14px]">
                {showDetails ? 'expand_less' : 'history'}
              </span>
              <span className="text-[10px] font-mono hidden sm:inline">Trace ({events.length})</span>
            </button>
            {onDismiss && isTerminal && (
              <button
                onClick={onDismiss}
                className="rounded-lg p-1 text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center transition-all"
                title="Dismiss task card"
                aria-label="Dismiss task card"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            )}
          </div>
        </div>

        {/* 9-Stage Agent Control Loop Tracker */}
        <div className="w-full bg-black/40 border border-white/5 rounded-xl p-2 flex items-center justify-between gap-1 overflow-x-auto scrollbar-hide text-[9px] font-mono">
          {STAGES.map((s, idx) => {
            const isActive = s.id === activeStageId && !isTerminal;
            const isDone = isCompleted || currentStageIndex > idx;
            const isFailedStage = isFailed && s.id === activeStageId;
            return (
              <div key={s.id} className="flex items-center gap-1 flex-shrink-0">
                <span
                  className={`px-2 py-0.5 rounded font-bold uppercase transition-all ${
                    isFailedStage
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : isActive
                      ? 'bg-blue-500 text-white shadow-[0_0_8px_rgba(59,130,246,0.6)] animate-pulse'
                      : isDone
                      ? 'text-emerald-400 bg-emerald-500/10'
                      : 'text-gray-500 bg-white/[0.02]'
                  }`}
                >
                  {s.label}
                </span>
                {idx < STAGES.length - 1 && (
                  <span className="text-gray-600 text-[8px]">›</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Goal Title */}
      <div className="relative z-10 w-full overflow-hidden mt-3">
        <h3 className="text-base sm:text-lg font-medium leading-snug text-white">
          {goal}
        </h3>

        {/* Verification Success Evidence Card */}
        {isCompleted && (
          <div className="mt-3 p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex flex-col gap-1.5 text-xs">
            <div className="flex items-center gap-1.5 text-emerald-400 font-semibold text-xs">
              <span className="material-symbols-outlined text-[16px]">task_alt</span>
              <span>{isKannada ? 'ಗುರಿ ಯಶಸ್ವಿಯಾಗಿ ಪರಿಶೀಲಿಸಲಾಗಿದೆ' : 'Goal Verified Successfully'}</span>
            </div>
            {completionDetails && (
              <p className="text-gray-300 text-[11px] leading-relaxed">
                {completionDetails}
              </p>
            )}
            {verificationEvidence && Object.keys(verificationEvidence).length > 0 && (
              <div className="mt-1 pt-1.5 border-t border-emerald-500/20 font-mono text-[10px] text-emerald-300/80">
                <span className="text-gray-400">Evidence: </span>
                {JSON.stringify(verificationEvidence)}
              </div>
            )}
          </div>
        )}

        {/* Failure / Blocked Explanation Banner */}
        {isFailed && (
          <div className="mt-3 p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl flex flex-col gap-1 text-xs">
            <div className="flex items-center gap-1.5 text-rose-400 font-semibold">
              <span className="material-symbols-outlined text-[16px]">report_problem</span>
              <span>{isKannada ? 'ಕಾರ್ಯ ನಿಂತಿದೆ' : 'Execution Interrupted'}</span>
            </div>
            <p className="text-gray-300 text-[11px] leading-relaxed">
              {failureReason || (isKannada ? 'ಕಾರ್ಯಾಚರಣೆ ಪೂರ್ಣಗೊಳ್ಳಲಿಲ್ಲ.' : 'Task did not reach verified completion.')}
            </p>
          </div>
        )}

        {/* Stopped Explanation Banner */}
        {isStopped && (
          <div className="mt-3 p-3 bg-white/[0.03] border border-white/10 rounded-xl flex items-center gap-2 text-xs text-gray-400">
            <span className="material-symbols-outlined text-[16px] text-gray-500">stop_circle</span>
            <span>{stopReason || (isKannada ? 'ಬಳಕೆದಾರರಿಂದ ಕಾರ್ಯ ರದ್ದುಗೊಂಡಿದೆ.' : 'Execution halted upon user STOP signal.')}</span>
          </div>
        )}

        {/* Waiting Confirmation Banner with Action Details */}
        <AnimatePresence>
          {isWaitingConfirmation && (
            <motion.div
              initial={{ opacity: 0, height: 0, scale: 0.98 }}
              animate={{ opacity: 1, height: 'auto', scale: 1 }}
              exit={{ opacity: 0, height: 0, scale: 0.98 }}
              className="mt-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl flex flex-col gap-2.5"
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-amber-300 flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[18px]">security</span>
                  {isKannada ? 'ಮಾನವ ಅನುಮೋದನೆ ಅಗತ್ಯವಿದೆ' : 'Human Authorization Required'}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${
                    riskLevel === 'HIGH' || riskLevel === 'CRITICAL'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  }`}
                >
                  {riskLevel} RISK
                </span>
              </div>
              <div className="text-xs text-gray-200 leading-snug">
                <span className="font-semibold text-white">{actionText}</span>: <span className="font-mono text-amber-200">{targetText}</span>
                <p className="text-gray-400 text-[11px] mt-1">{explanation}</p>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <button
                  type="button"
                  onClick={() => onConfirmAction(task.id, activeDecisionId, true)}
                  className="flex-1 py-2 px-3 bg-emerald-500 text-black font-semibold text-xs rounded-xl hover:bg-emerald-400 transition-colors shadow-md flex items-center justify-center gap-1.5 focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:outline-none"
                >
                  <span className="material-symbols-outlined text-[16px]">check_circle</span>
                  {isKannada ? 'ಅನುಮೋದಿಸಿ ಮುಂದುವರಿಯಿರಿ' : 'Approve Action'}
                </button>
                <button
                  type="button"
                  onClick={() => onConfirmAction(task.id, activeDecisionId, false, 'User rejected from UI')}
                  className="py-2 px-4 bg-red-500/20 border border-red-500/30 text-red-300 font-medium text-xs rounded-xl hover:bg-red-500/30 transition-colors focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:outline-none"
                >
                  {isKannada ? 'ತಿರಸ್ಕರಿಸಿ' : 'Reject'}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapsible Execution Events Stepper */}
        <AnimatePresence>
          {showDetails && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
              className="mt-3 pt-3 border-t border-white/10 max-h-48 overflow-y-auto scrollbar-thin scrollbar-thumb-white/20"
              aria-live="polite"
            >
              <h5 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[13px]">timeline</span>
                Execution Event Trace ({events.length})
              </h5>
              {events.length === 0 ? (
                <p className="text-xs text-gray-500 italic">No events logged yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {events.slice(-8).map((evt, idx) => (
                    <div key={evt.id || idx} className="text-xs flex items-center gap-2 text-gray-300 font-mono">
                      <span className="text-[10px] text-gray-500 min-w-[55px]">
                        {new Date((evt.timestamp || Date.now() / 1000) * 1000).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-white/5 text-[9px] text-blue-400 font-semibold uppercase">
                        {evt.event_type}
                      </span>
                      <span className="text-gray-400 truncate flex-1 text-[11px]">
                        {typeof evt.payload === 'object'
                          ? evt.payload.reason || evt.payload.state || evt.payload.goal || JSON.stringify(evt.payload)
                          : String(evt.payload)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Action Controls & Emergency STOP button */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-2 mt-4 pt-3 border-t border-white/5">
        <div className="flex items-center gap-2">
          {canRetry && (
            <button
              onClick={() => onRunTask(task.id)}
              className="px-3.5 py-1.5 bg-blue-500/20 text-blue-300 border border-blue-500/30 text-xs font-medium rounded-xl hover:bg-blue-500/30 transition-all flex items-center gap-1.5 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
            >
              <span className="material-symbols-outlined text-[15px]">replay</span>
              {isKannada ? 'ಪುನಃ ಪ್ರಯತ್ನಿಸಿ' : 'Retry Task'}
            </button>
          )}
          {isCompleted && (
            <button
              onClick={() => onRunTask(task.id)}
              className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 text-xs font-medium rounded-xl transition-all flex items-center gap-1.5 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
            >
              <span className="material-symbols-outlined text-[15px]">refresh</span>
              {isKannada ? 'ಮತ್ತೊಮ್ಮೆ ರನ್ ಮಾಡಿ' : 'Run Again'}
            </button>
          )}
        </div>

        {/* Persistent Emergency STOP button */}
        {!isTerminal && (
          <button
            onClick={() => onStop(task.id)}
            className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-rose-600/30 transition-all flex items-center gap-1.5 focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:outline-none"
            title="Emergency STOP - Immediately halt all desktop interactions"
          >
            <span className="material-symbols-outlined text-[16px]">front_hand</span>
            {isKannada ? 'ತುರ್ತು ನಿಲ್ಲಿಸಿ (STOP)' : 'Emergency STOP'}
          </button>
        )}
      </div>
    </motion.div>
  );
}
