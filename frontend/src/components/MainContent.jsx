import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import TaskEntry from './TaskEntry';
import TaskStateCard from './TaskStateCard';
import ChatResponsePanel from './ChatResponsePanel';
import LiveInspectionViewport from './LiveInspectionViewport';
import ActiveExecutionStepper from './ActiveExecutionStepper';
import {
  GenUIPlanCustomizer,
  GenUIDataExtractor,
  GenUISafetyGate,
  GenUIChoiceChips,
} from './GenerativeUI';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  visible: { 
    opacity: 1, y: 0,
    transition: { type: 'spring', stiffness: 280, damping: 25 }
  }
};

function MainContent({ 
  onStart, 
  onStop, 
  onTransition, 
  onRunTask, 
  isSubmitting, 
  activeTask, 
  isConnected,
  systemInfo,
  models,
  onClearActiveTask,
  pendingApproval = null,
  onConfirmAction = () => {},
  activeWindow = null,
  latency = 0,
  onOpenTelemetry = () => {}
}) {
  const [omniPrompt, setOmniPrompt] = useState('');
  const [showGenUIPlan, setShowGenUIPlan] = useState(false);
  const [showGenUIData, setShowGenUIData] = useState(false);
  const [activeTab, setActiveTab] = useState('console'); // 'console' | 'classic'

  const isChatMode = activeTask?.metadata?.guidance_mode === 'chat';
  const isTaskRunning = activeTask && ![
    'COMPLETED',
    'TASK_COMPLETED',
    'FAILED',
    'TASK_FAILED',
    'STOPPED',
    'CANCELLED'
  ].includes(activeTask.state);

  const handleOmniSubmit = (e) => {
    if (e) e.preventDefault();
    if (!omniPrompt.trim() || isSubmitting || !isConnected) return;
    onStart(omniPrompt, models?.[0]?.id || '', 'assist');
    setOmniPrompt('');
  };

  const handleElementTargeted = (elem) => {
    setOmniPrompt(`Target element ${elem.name} (${elem.properties.controlType}) on HWND ${elem.properties.hwnd}`);
    setShowGenUIPlan(true);
  };

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="flex-1 flex flex-col items-center px-4 sm:px-8 pb-16 w-full max-w-[1280px] mx-auto mt-6"
    >
      {/* 1. Glowing Smart Omni-Goal Input Bar (As in verified UI screenshot) */}
      <motion.div variants={itemVariants} className="w-full max-w-[840px] mb-6">
        <form 
          onSubmit={handleOmniSubmit}
          className="relative flex items-center w-full rounded-full bg-[#0a0f18]/90 border border-cyan-400/40 p-1.5 shadow-[0_0_35px_rgba(6,182,212,0.18)] hover:shadow-[0_0_45px_rgba(6,182,212,0.28)] transition-all duration-300 focus-within:border-cyan-400 focus-within:ring-2 focus-within:ring-cyan-400/20"
        >
          <input
            type="text"
            value={omniPrompt}
            onChange={(e) => setOmniPrompt(e.target.value)}
            placeholder="Smart natural-language goal input to glow."
            className="flex-1 bg-transparent px-5 py-2 text-sm text-gray-100 placeholder-gray-500 font-sans focus:outline-none"
          />
          <button
            type="submit"
            disabled={!omniPrompt.trim() || isSubmitting}
            className="w-9 h-9 rounded-full bg-cyan-500/20 hover:bg-cyan-500/40 text-cyan-300 hover:text-white border border-cyan-400/40 flex items-center justify-center transition-all disabled:opacity-40 cursor-pointer"
            title="Dispatch Goal"
          >
            <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
          </button>
        </form>

        {/* Generative UI Choice Chips */}
        <div className="mt-2.5 flex justify-center">
          <GenUIChoiceChips
            prompt="Quick targets:"
            options={['MockNotepad UIA', 'Paint HWND', 'Vite Web Console', 'Sandbox JSON']}
            onSelect={(opt) => {
              setOmniPrompt(`Automate ${opt}`);
              setShowGenUIPlan(true);
            }}
          />
        </div>
      </motion.div>

      {/* 2. Main Operator Split-Screen Workspace (Matching Screenshot) */}
      <motion.div variants={itemVariants} className="w-full grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch mb-6">
        {/* Left Column: Live Simulated Desktop Inspection Viewport */}
        <div className="w-full h-full flex">
          <LiveInspectionViewport
            activeWindow={activeWindow}
            activeTask={activeTask}
            onElementSelect={handleElementTargeted}
          />
        </div>

        {/* Right Column: Active Execution Stepper */}
        <div className="w-full h-full flex">
          <ActiveExecutionStepper
            activeTask={activeTask}
            onStop={onStop}
            pendingApproval={pendingApproval}
            onConfirmAction={onConfirmAction}
          />
        </div>
      </motion.div>

      {/* 3. Generative UI Interactive Extensions Container */}
      <AnimatePresence>
        {showGenUIPlan && (
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="w-full max-w-[840px] mb-6"
          >
            <GenUIPlanCustomizer
              onExecutePlan={(customSteps) => {
                setShowGenUIPlan(false);
                onStart(`Custom Plan with ${customSteps.length} steps`, models?.[0]?.id || '', 'assist');
              }}
              onCancel={() => setShowGenUIPlan(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Consequential Safety Gate (Dynamic when approval required) */}
      <AnimatePresence>
        {pendingApproval && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            className="w-full max-w-[840px] mb-6"
          >
            <GenUISafetyGate
              action={pendingApproval.action || 'High-Risk Operation'}
              target={pendingApproval.target || 'Windows Operating System'}
              riskLevel={pendingApproval.risk_level || 'HIGH'}
              onApprove={(opts) => onConfirmAction(true, opts)}
              onReject={() => onConfirmAction(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* 4. Chat Response Panel (when in chat mode) */}
      <AnimatePresence mode="wait">
        {isChatMode && (
          <motion.div
            key="chat-panel"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="w-full max-w-[840px] mt-6"
          >
            <ChatResponsePanel 
              task={activeTask}
              onNewChat={onClearActiveTask}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* 5. Telemetry Status Bar Footer */}
      <motion.div 
        variants={itemVariants}
        className="w-full flex flex-col sm:flex-row justify-between items-center mt-8 pt-4 border-t border-white/[0.06] text-xs text-gray-400 gap-3"
      >
        <button
          onClick={onOpenTelemetry}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 transition-all text-gray-300 hover:text-white"
          title="Click to view hardware diagnostics"
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span>{isConnected ? 'System Ready' : 'Connecting'}</span>
          <span className="text-gray-500">·</span>
          <span>{latency ? `${latency}ms loopback` : 'Loopback'}</span>
          <span className="text-gray-500">·</span>
          <span>
            {systemInfo?.memory_used_mb !== undefined
              ? `${systemInfo.memory_used_mb} MB Process RAM`
              : '73.2 MB RSS'}
          </span>
        </button>

        <div className="flex items-center gap-3 text-gray-400 text-[11px] font-mono">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
            <span>Generative UI: ACTIVE</span>
          </span>
          <span className="text-gray-600">·</span>
          <span className="text-gray-400">Local Telemetry (SQLite WAL)</span>
        </div>
      </motion.div>
    </motion.div>
  );
}

export default React.memo(MainContent);
