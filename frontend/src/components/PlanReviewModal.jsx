import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function PlanReviewModal({
  isOpen,
  onClose,
  plan,
  goal,
  onApprove,
  isExecuting = false,
  language = 'en',
}) {
  const approveBtnRef = useRef(null);
  const [submitting, setSubmitting] = React.useState(false);

  useEffect(() => {
    if (isOpen && approveBtnRef.current) {
      approveBtnRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !isExecuting && !submitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isExecuting, submitting, onClose]);

  const handleApproveClick = async () => {
    if (isExecuting || submitting) return;
    setSubmitting(true);
    try {
      if (onApprove) {
        await onApprove();
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen || !plan) return null;

  const steps = plan.steps || plan.actions || [];
  const targetApp = plan.target_app || plan.target_window || 'Active Window';
  const hasHighRisk = steps.some(
    (s) => s.risk_level === 'HIGH' || s.risk_level === 'CRITICAL' || s.requires_approval
  );

  const isKannada = language === 'kn';

  const t = {
    title: isKannada ? 'ಕಾರ್ಯ ಯೋಜನೆ ವಿಮರ್ಶೆ ಮತ್ತು ಅನುಮೋದನೆ' : 'Pre-Execution Plan Review & Safety Authorization',
    subtitle: isKannada
      ? 'ಡೆಸ್ಕ್‌ಟಾಪ್‌ನಲ್ಲಿ ಯಾವುದೇ ಬದಲಾವಣೆ ಮಾಡುವ ಮೊದಲು ಯೋಜಿತ ಹಂತಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.'
      : 'Verify planned actions and safety boundaries before permitting desktop execution.',
    goalLabel: isKannada ? 'ಕೋರಿಕೆಯ ಗುರಿ' : 'Requested Goal',
    targetLabel: isKannada ? 'ಗುರಿ ಅಪ್ಲಿಕೇಶನ್' : 'Target Application',
    stepCount: (count) => isKannada ? `ಯೋಜಿತ ಹಂತಗಳು (${count})` : `Planned Actions (${count} Steps)`,
    riskBadge: (risk) => {
      switch ((risk || '').toUpperCase()) {
        case 'CRITICAL':
          return { label: isKannada ? 'ಅತ್ಯಂತ ಸೂಕ್ಷ್ಮ' : 'CRITICAL RISK', color: 'bg-rose-500/20 text-rose-300 border-rose-500/40' };
        case 'HIGH':
          return { label: isKannada ? 'ಹೆಚ್ಚಿನ ಅಪಾಯ' : 'HIGH RISK', color: 'bg-red-500/20 text-red-300 border-red-500/40' };
        case 'MEDIUM':
          return { label: isKannada ? 'ಮಧ್ಯಮ ಅಪಾಯ' : 'MEDIUM RISK', color: 'bg-amber-500/20 text-amber-300 border-amber-500/40' };
        default:
          return { label: isKannada ? 'ಸಾಮಾನ್ಯ' : 'LOW RISK', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' };
      }
    },
    safetyNotice: isKannada
      ? 'ಭದ್ರತಾ ಸೂಚನೆ: ಉನ್ನತ ಅಪಾಯದ ಹಂತಗಳು ಜಾರಿಗೆ ಮುನ್ನ ಮತ್ತೊಮ್ಮೆ ಮಾನವ ಅನುಮೋದನೆಯನ್ನು ಕೇಳುತ್ತವೆ.'
      : 'Safety Boundary: Actions modifying files, registry, or credentials will require explicit in-flight approval before dispatch.',
    approveBtn: isKannada ? 'ಅನುಮೋದಿಸಿ ಪ್ರಾರಂಭಿಸಿ' : 'Approve & Start Execution',
    cancelBtn: isKannada ? 'ಯೋಜನೆ ರದ್ದುಗೊಳಿಸಿ' : 'Cancel Plan',
    executing: isKannada ? 'ಪ್ರಾರಂಭಿಸಲಾಗುತ್ತಿದೆ...' : 'Authorizing & Starting...',
  };

  return (
    <AnimatePresence>
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md"
        role="dialog"
        aria-modal="true"
        aria-labelledby="plan-review-title"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          transition={{ type: 'spring', damping: 25, stiffness: 320 }}
          className="w-full max-w-2xl bg-[#111216] border border-white/10 rounded-2xl shadow-2xl p-6 relative overflow-hidden flex flex-col max-h-[85vh]"
        >
          {/* Header */}
          <div className="flex items-center justify-between pb-4 border-b border-white/10 flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse" />
              <div>
                <h2 id="plan-review-title" className="text-base font-semibold text-white tracking-tight">
                  {t.title}
                </h2>
                <p className="text-xs text-gray-400 mt-0.5">{t.subtitle}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              disabled={isExecuting}
              className="text-gray-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
              aria-label="Close dialog"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Goal & Target App Banner */}
          <div className="my-4 p-3.5 bg-white/[0.03] border border-white/5 rounded-xl flex flex-col gap-2 flex-shrink-0">
            <div>
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                {t.goalLabel}
              </span>
              <p className="text-sm text-white font-medium mt-0.5">{goal || plan.goal}</p>
            </div>
            {targetApp && (
              <div className="flex items-center gap-2 text-xs text-gray-300">
                <span className="text-gray-400">{t.targetLabel}:</span>
                <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono text-[11px]">
                  {targetApp}
                </span>
              </div>
            )}
          </div>

          {/* Steps List */}
          <div className="flex-1 overflow-y-auto pr-1 my-2 space-y-2.5 scrollbar-thin scrollbar-thumb-white/10">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              {t.stepCount(steps.length)}
            </div>

            {steps.length === 0 ? (
              <div className="p-4 text-center text-xs text-gray-500 italic bg-white/[0.02] rounded-xl border border-white/5">
                No individual steps generated. Single-stage execution plan.
              </div>
            ) : (
              steps.map((step, idx) => {
                const risk = t.riskBadge(step.risk_level);
                return (
                  <div
                    key={idx}
                    className="p-3 bg-[#16181d] border border-white/5 rounded-xl flex items-start gap-3 hover:border-white/10 transition-colors"
                  >
                    <span className="w-5 h-5 rounded-full bg-white/5 border border-white/10 text-gray-400 flex items-center justify-center text-[10px] font-mono flex-shrink-0 mt-0.5">
                      {idx + 1}
                    </span>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-white truncate font-mono">
                          {(step.action_type || step.action || step.type || 'EXECUTE').toUpperCase()}
                        </span>
                        <span
                          className={`text-[9px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${risk.color}`}
                        >
                          {risk.label}
                        </span>
                      </div>

                      <p className="text-xs text-gray-300 mt-1 leading-relaxed">
                        {step.description || step.target_description || step.intent || JSON.stringify(step.parameters || {})}
                      </p>

                      {(step.target_element || step.coordinate || step.text) && (
                        <div className="mt-1.5 flex flex-wrap gap-2 text-[10px] text-gray-400 font-mono">
                          {step.target_element && (
                            <span className="bg-white/5 px-2 py-0.5 rounded border border-white/5">
                              Target: {step.target_element}
                            </span>
                          )}
                          {step.coordinate && (
                            <span className="bg-white/5 px-2 py-0.5 rounded border border-white/5">
                              Coord: ({step.coordinate.x}, {step.coordinate.y})
                            </span>
                          )}
                          {step.text && (
                            <span className="bg-white/5 px-2 py-0.5 rounded border border-white/5">
                              Text: &quot;{step.text}&quot;
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Safety Notice */}
          {hasHighRisk && (
            <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-center gap-2 text-xs text-amber-300 flex-shrink-0">
              <span className="material-symbols-outlined text-[18px]">gpp_maybe</span>
              <span>{t.safetyNotice}</span>
            </div>
          )}

          {/* Footer Actions */}
          <div className="mt-5 pt-4 border-t border-white/10 flex items-center justify-end gap-3 flex-shrink-0">
            <button
              type="button"
              onClick={onClose}
              disabled={isExecuting || submitting}
              className="px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-300 hover:text-white text-xs font-medium rounded-xl border border-white/10 transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
            >
              {t.cancelBtn}
            </button>
            <button
              ref={approveBtnRef}
              type="button"
              onClick={handleApproveClick}
              disabled={isExecuting || submitting}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-500/25 transition-all flex items-center gap-1.5 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none disabled:opacity-50"
            >
              {(isExecuting || submitting) ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>{t.executing}</span>
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[16px]">verified</span>
                  <span>{t.approveBtn}</span>
                </>
              )}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
