import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

function TaskHistoryView({
  tasks = [],
  onSelectTask,
  onDeleteTask,
  onClearCompleted,
  onRunTask,
  language = 'en',
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [inspectedTask, setInspectedTask] = useState(null);

  const isKannada = language === 'kn';

  const t = {
    title: isKannada ? 'ಕಾರ್ಯ ಇತಿಹಾಸ ಮತ್ತು ಪರಿಶೀಲನೆ' : 'Task Execution History & Audit Log',
    subtitle: isKannada
      ? 'ಹಿಂದಿನ ಕಾರ್ಯಗಳು, ಪರಿಶೀಲನಾ ಸಾಕ್ಷ್ಯಗಳು ಮತ್ತು ಹಂತದ ಲಾಗ್‌ಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.'
      : 'Audit previous computer-use tasks, step events, and verification outcomes.',
    searchPlaceholder: isKannada ? 'ಗುರಿ ಅಥವಾ ID ಮೂಲಕ ಹುಡುಕಿ...' : 'Search by task goal or ID...',
    allFilter: isKannada ? 'ಎಲ್ಲವೂ' : 'All',
    completedFilter: isKannada ? 'ಪೂರ್ಣಗೊಂಡಿದೆ' : 'Completed',
    runningFilter: isKannada ? 'ಚಾಲನೆಯಲ್ಲಿದೆ' : 'Running',
    failedFilter: isKannada ? 'ವಿಫಲವಾಗಿದೆ' : 'Failed',
    stoppedFilter: isKannada ? 'ನಿಲ್ಲಿಸಲಾಗಿದೆ' : 'Stopped',
    clearAll: isKannada ? 'ಪೂರ್ಣಗೊಂಡವುಗಳನ್ನು ಅಳಿಸಿ' : 'Clear Completed',
    emptyTitle: isKannada ? 'ಯಾವುದೇ ಕಾರ್ಯಗಳು ಕಂಡುಬಂದಿಲ್ಲ' : 'No Tasks Found',
    emptySubtitle: isKannada ? 'ಹೊಸ ಕಾರ್ಯವನ್ನು ಪ್ರಾರಂಭಿಸಿ ಅಥವಾ ಫಿಲ್ಟರ್ ಬದಲಾಯಿಸಿ.' : 'Initialize a task in Workspace or adjust your search filter.',
    inspectTitle: isKannada ? 'ಕಾರ್ಯ ವಿವರಗಳು' : 'Task Inspection & Trace',
    closeInspect: isKannada ? 'ಮುಚ್ಚಿ' : 'Close',
    retryBtn: isKannada ? 'ಪುನಃ ಪ್ರಯತ್ನಿಸಿ' : 'Retry Task',
    deleteBtn: isKannada ? 'ಅಳಿಸಿ' : 'Delete',
    verificationLabel: isKannada ? 'ಸ್ವತಂತ್ರ ಪರಿಶೀಲನೆ' : 'Independent Verification',
  };

  const filteredTasks = useMemo(() => {
    return tasks.filter((task) => {
      const goalMatches = (task.goal || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (task.id || '').toLowerCase().includes(searchTerm.toLowerCase());

      if (!goalMatches) return false;

      const state = (task.state || '').toUpperCase();
      if (statusFilter === 'COMPLETED') {
        return state === 'COMPLETED' || state === 'TASK_COMPLETED';
      }
      if (statusFilter === 'RUNNING') {
        return !['COMPLETED', 'TASK_COMPLETED', 'FAILED', 'TASK_FAILED', 'STOPPED', 'CANCELLED'].includes(state);
      }
      if (statusFilter === 'FAILED') {
        return state === 'FAILED' || state === 'TASK_FAILED';
      }
      if (statusFilter === 'STOPPED') {
        return state === 'STOPPED' || state === 'CANCELLED';
      }
      return true;
    });
  }, [tasks, searchTerm, statusFilter]);

  return (
    <div className="w-full max-w-5xl mx-auto py-8 px-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight flex items-center gap-2.5">
            <span className="material-symbols-outlined text-[26px] text-blue-400">history</span>
            {t.title}
          </h1>
          <p className="text-sm text-gray-400 mt-1">{t.subtitle}</p>
        </div>

        {tasks.length > 0 && onClearCompleted && (
          <button
            onClick={onClearCompleted}
            className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-gray-400 hover:text-white transition-all flex items-center gap-1.5 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          >
            <span className="material-symbols-outlined text-[15px]">mop</span>
            {t.clearAll}
          </button>
        )}
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 bg-white/[0.02] border border-white/5 rounded-2xl">
        <div className="relative flex-1">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={t.searchPlaceholder}
            className="w-full bg-[#14161b] border border-white/10 rounded-xl px-9 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 transition-all font-mono"
          />
          <span className="material-symbols-outlined text-[16px] text-gray-500 absolute left-3 top-1/2 -translate-y-1/2">
            search
          </span>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-xs"
            >
              ✕
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5 bg-black/40 p-1 rounded-xl border border-white/5">
          {['ALL', 'COMPLETED', 'RUNNING', 'FAILED', 'STOPPED'].map((filter) => {
            const label = filter === 'ALL' ? t.allFilter :
              filter === 'COMPLETED' ? t.completedFilter :
              filter === 'RUNNING' ? t.runningFilter :
              filter === 'FAILED' ? t.failedFilter : t.stoppedFilter;
            const active = statusFilter === filter;
            return (
              <button
                key={filter}
                onClick={() => setStatusFilter(filter)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  active ? 'bg-white/15 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Task List */}
      <div className="bg-[#121418] border border-white/5 rounded-2xl p-4 flex flex-col min-h-[420px]">
        <div className="flex items-center justify-between px-2 pb-3 border-b border-white/5 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
          <span>Task Goal & Details</span>
          <div className="flex items-center gap-8">
            <span>Timestamp</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 mt-3 pr-1 scrollbar-thin scrollbar-thumb-white/10">
          {filteredTasks.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center text-gray-500">
              <span className="material-symbols-outlined text-[36px] mb-2 opacity-40">inbox</span>
              <p className="text-xs font-medium">{t.emptyTitle}</p>
              <p className="text-[11px] text-gray-600 mt-1">{t.emptySubtitle}</p>
            </div>
          ) : (
            filteredTasks.map((task) => {
              const state = (task.state || '').toUpperCase();
              const isCompleted = state === 'COMPLETED' || state === 'TASK_COMPLETED';
              const isFailed = state === 'FAILED' || state === 'TASK_FAILED';
              const isStopped = state === 'STOPPED' || state === 'CANCELLED';

              return (
                <div
                  key={task.id}
                  className="p-3.5 bg-white/[0.02] border border-white/5 hover:border-white/15 rounded-xl flex items-center justify-between transition-all group"
                >
                  <div
                    onClick={() => {
                      if (onSelectTask) onSelectTask(task.id);
                      setInspectedTask(task);
                    }}
                    className="flex-1 min-w-0 pr-4 cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-white truncate group-hover:text-blue-400 transition-colors">
                        {task.goal || `Task ${task.id.substring(0, 8)}`}
                      </span>
                      {isCompleted && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                          Verified
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-gray-500 mt-1 flex items-center gap-2 font-mono">
                      <span>ID: {task.id.substring(0, 10)}...</span>
                      <span>·</span>
                      <span>Mode: {task.metadata?.guidance_mode || 'assist'}</span>
                      {task.metadata?.model_id && (
                        <>
                          <span>·</span>
                          <span className="truncate max-w-[140px]">{task.metadata.model_id}</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6 flex-shrink-0">
                    <span className="text-[11px] text-gray-400 font-mono min-w-[70px] text-right">
                      {new Date(task.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>

                    <span
                      className={`text-[9px] font-bold px-2 py-0.5 rounded uppercase tracking-wider min-w-[80px] text-center ${
                        isCompleted
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : isFailed
                          ? 'bg-red-500/20 text-red-300 border border-red-500/40'
                          : isStopped
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-blue-500/20 text-blue-300 border border-blue-500/40 animate-pulse'
                      }`}
                    >
                      {state}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => setInspectedTask(task)}
                        className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-all"
                        title="Inspect Task"
                      >
                        <span className="material-symbols-outlined text-[16px]">visibility</span>
                      </button>

                      {(isFailed || isStopped) && onRunTask && (
                        <button
                          onClick={() => onRunTask(task.id)}
                          className="p-1.5 rounded-lg text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 transition-all"
                          title={t.retryBtn}
                        >
                          <span className="material-symbols-outlined text-[16px]">replay</span>
                        </button>
                      )}

                      {onDeleteTask && (
                        <button
                          onClick={() => onDeleteTask(task.id)}
                          className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                          title={t.deleteBtn}
                        >
                          <span className="material-symbols-outlined text-[16px]">delete_outline</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Task Inspection Modal */}
      <AnimatePresence>
        {inspectedTask && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-xl bg-[#121418] border border-white/10 rounded-2xl p-6 shadow-2xl flex flex-col max-h-[80vh]"
            >
              <div className="flex items-center justify-between pb-3 border-b border-white/10">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px] text-blue-400">info</span>
                  {t.inspectTitle}
                </h3>
                <button
                  onClick={() => setInspectedTask(null)}
                  className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5"
                >
                  ✕
                </button>
              </div>

              <div className="my-4 flex flex-col gap-3">
                <div className="p-3 bg-white/[0.03] rounded-xl border border-white/5">
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">Goal</span>
                  <p className="text-xs text-white font-medium mt-1">{inspectedTask.goal}</p>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2.5 bg-white/[0.02] rounded-lg border border-white/5">
                    <span className="text-[10px] text-gray-500 block">STATUS</span>
                    <span className="text-white font-bold">{inspectedTask.state}</span>
                  </div>
                  <div className="p-2.5 bg-white/[0.02] rounded-lg border border-white/5">
                    <span className="text-[10px] text-gray-500 block">ID</span>
                    <span className="text-gray-300 truncate block">{inspectedTask.id}</span>
                  </div>
                </div>

                {/* Event Logs Trace */}
                <div className="flex-1 overflow-y-auto max-h-48 mt-2 p-2.5 bg-black/40 rounded-xl border border-white/5 space-y-1.5 font-mono text-[11px] scrollbar-thin scrollbar-thumb-white/10">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold block mb-1">
                    Event Trace ({inspectedTask.events?.length || 0})
                  </span>
                  {(inspectedTask.events || []).length === 0 ? (
                    <p className="text-gray-500 italic text-[10px]">No event records captured.</p>
                  ) : (
                    inspectedTask.events.map((evt, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-gray-300">
                        <span className="text-gray-500 text-[10px]">#{idx + 1}</span>
                        <span className="text-blue-400 font-bold uppercase text-[10px]">{evt.event_type}</span>
                        <span className="text-gray-400 truncate">
                          {typeof evt.payload === 'object' ? JSON.stringify(evt.payload) : String(evt.payload)}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="pt-3 border-t border-white/10 flex justify-end">
                <button
                  onClick={() => setInspectedTask(null)}
                  className="px-4 py-1.5 bg-white/10 hover:bg-white/15 text-white text-xs rounded-xl font-medium"
                >
                  {t.closeInspect}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default React.memo(TaskHistoryView);
