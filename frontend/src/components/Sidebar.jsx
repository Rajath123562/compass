import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function Sidebar({
  tasks = [],
  onSelectTask = () => {},
  activeTaskId,
  onDeleteTask,
  onClearCompleted,
  activeView = 'workspace',
  onViewChange = () => {},
  language = 'en',
  onLanguageChange = () => {},
  isOpen = false,
  onClose = () => {},
}) {
  const isKannada = language === 'kn';

  const navItems = [
    {
      id: 'workspace',
      label: isKannada ? 'ಕಾರ್ಯಕ್ಷೇತ್ರ' : 'Agent Workspace',
      icon: 'explore',
      desc: isKannada ? 'ಸಕ್ರಿಯ ಕಂಪ್ಯೂಟರ್ ಬಳಕೆ' : 'Live Computer Use',
    },
    {
      id: 'workflows',
      label: isKannada ? 'ಕಾರ್ಯಪ್ರವಾಹಗಳು' : 'Workflows (DAG)',
      icon: 'account_tree',
      desc: isKannada ? 'ಮಲ್ಟಿ-ಅಪ್ಲಿಕೇಶನ್ DAG' : 'Autonomous Graphs',
    },
    {
      id: 'history',
      label: isKannada ? 'ಇತಿಹಾಸ ಮತ್ತು ಲಾಗ್' : 'Task History',
      icon: 'history',
      desc: isKannada ? 'ಹಿಂದಿನ ಕಾರ್ಯಗಳು' : 'Audit Trail & Results',
    },
    {
      id: 'diagnostics',
      label: isKannada ? 'ಡಯಾಗ್ನೋಸ್ಟಿಕ್ಸ್' : 'Diagnostics',
      icon: 'shield_with_heart',
      desc: isKannada ? 'ಟೆಲಿಮೆಟ್ರಿ ಮತ್ತು ಗೇಟ್‌ಗಳು' : 'Telemetry & Gates',
    },
    {
      id: 'settings',
      label: isKannada ? 'ಸಂರಚನೆ' : 'Settings',
      icon: 'tune',
      desc: isKannada ? 'AI ಮತ್ತು ಭದ್ರತೆ' : 'Model & Safety Rules',
    },
  ];

  const handleNavClick = (viewId) => {
    onViewChange(viewId);
    if (onClose) onClose();
  };

  const getStatusColor = (state) => {
    switch (state) {
      case 'COMPLETED':
      case 'TASK_COMPLETED':
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'WAITING_CONFIRMATION':
        return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      case 'FAILED':
      case 'TASK_FAILED':
        return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      case 'STOPPED':
      case 'CANCELLED':
        return 'text-gray-400 bg-gray-500/10 border-gray-500/20';
      default:
        return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
    }
  };

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden"
            aria-hidden="true"
          />
        )}
      </AnimatePresence>

      {/* Sidebar Container: Fixed on mobile/tablet when open, static on lg+ */}
      <aside
        className={`w-[280px] h-full bg-[#0d0f15]/95 lg:bg-stitch-sidebar/80 backdrop-blur-2xl border-r border-white/5 flex flex-col pt-5 pb-4 flex-shrink-0 z-50 lg:z-20 shadow-[4px_0_24px_rgba(0,0,0,0.3)] transition-transform duration-300 ease-in-out fixed inset-y-0 left-0 lg:static lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
        aria-label="Application navigation"
      >
        {/* Brand Header */}
        <div className="px-5 mb-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 p-[1px] shadow-md shadow-blue-500/20">
              <div className="w-full h-full bg-[#0e1017] rounded-[11px] flex items-center justify-center">
                <span className="material-symbols-outlined text-[18px] text-blue-400">
                  explore
                </span>
              </div>
            </div>
            <div>
              <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-1.5">
                COMPASS
                <span className="text-[9px] px-1.5 py-0.2 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-mono">
                  v2.0
                </span>
              </h1>
              <span className="text-[10px] text-gray-500 font-mono tracking-wider block">
                Intelligent Desktop Agent
              </span>
            </div>
          </div>

          {/* Close button for mobile */}
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
            aria-label="Close sidebar"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        </div>

        {/* Primary Navigation */}
        <nav className="px-3 mb-4 space-y-1" aria-label="Main menu">
          <div className="px-3 mb-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-widest font-mono">
            {isKannada ? 'ಮುಖ್ಯ ಮೆನು' : 'Navigation'}
          </div>
          {navItems.map((item) => {
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`w-full text-left px-3 py-2 rounded-xl flex items-center gap-3 transition-all relative overflow-hidden group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none ${
                  isActive
                    ? 'bg-blue-600/15 border border-blue-500/30 text-white shadow-sm'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.03] border border-transparent'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                {isActive && (
                  <motion.div
                    layoutId="activeNavIndicator"
                    className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-blue-500 rounded-r-full shadow-[0_0_8px_rgba(59,130,246,0.8)]"
                  />
                )}
                <span
                  className={`material-symbols-outlined text-[18px] transition-colors ${
                    isActive ? 'text-blue-400' : 'text-gray-400 group-hover:text-gray-300'
                  }`}
                >
                  {item.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <span className="text-xs font-semibold block leading-tight">{item.label}</span>
                  <span className="text-[10px] text-gray-500 block truncate">{item.desc}</span>
                </div>
              </button>
            );
          })}
        </nav>

        {/* Recent Workstreams Section */}
        <div className="flex-1 overflow-y-auto scrollbar-hide px-3 pt-3 border-t border-white/5">
          <div className="flex items-center justify-between px-3 mb-2">
            <h2 className="text-[10px] font-semibold text-gray-500 uppercase tracking-widest font-mono">
              {isKannada ? 'ಇತ್ತೀಚಿನ ಕಾರ್ಯಗಳು' : 'Recent Workstreams'}
            </h2>
            {tasks.length > 0 && onClearCompleted && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onClearCompleted();
                }}
                className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-white/5"
                title="Clear completed tasks"
              >
                <span className="material-symbols-outlined text-[12px]">mop</span>
                Clear
              </button>
            )}
          </div>

          <div className="space-y-1">
            {tasks.length === 0 ? (
              <div className="px-3 py-3 text-xs text-gray-500 italic bg-white/[0.01] rounded-xl border border-white/5 text-center">
                {isKannada ? 'ಯಾವುದೇ ಕಾರ್ಯಗಳಿಲ್ಲ.' : 'No active workstreams.'}
              </div>
            ) : (
              tasks.slice(0, 10).map((task) => {
                const isActive = task.id === activeTaskId && activeView === 'workspace';
                return (
                  <div
                    key={task.id}
                    onClick={() => {
                      onViewChange('workspace');
                      onSelectTask(task.id);
                      if (onClose) onClose();
                    }}
                    className={`w-full text-left p-2.5 rounded-xl flex gap-2.5 items-center transition-all mb-1 group relative overflow-hidden cursor-pointer border ${
                      isActive
                        ? 'bg-blue-500/10 border-blue-500/30 text-white shadow-sm'
                        : 'bg-white/[0.02] hover:bg-white/[0.05] border-white/5 text-gray-300'
                    }`}
                  >
                    <div className="flex-1 overflow-hidden min-w-0">
                      <div className="text-xs font-medium truncate">
                        {task.goal || `Task ${task.id.substring(0, 8)}`}
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`text-[9px] font-mono uppercase px-1.5 py-0.2 rounded border ${getStatusColor(task.state)}`}>
                          {task.state || 'PENDING'}
                        </span>
                        <span className="text-[10px] text-gray-500 font-mono">
                          {new Date(task.created_at || Date.now()).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                    </div>

                    {onDeleteTask && (
                      <button
                        className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-rose-400 p-1 rounded hover:bg-white/5 transition-all"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteTask(task.id);
                        }}
                        title="Delete task"
                        aria-label={`Delete task ${task.id}`}
                      >
                        <span className="material-symbols-outlined text-[14px]">delete_outline</span>
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Footer System Status Chip */}
        <div className="px-4 pt-3 border-t border-white/5 flex items-center justify-between text-[11px] text-gray-400 font-mono">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Shield Active
          </span>
          <span className="text-gray-500 text-[10px]">Windows UIA</span>
        </div>
      </aside>
    </>
  );
}
