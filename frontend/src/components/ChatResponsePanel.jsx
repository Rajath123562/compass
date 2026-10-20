import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../api';

/**
 * ChatResponsePanel - Displays chat mode AI replies in a conversational layout
 * with real-time SSE token typewriter streaming, cursor animation, and 1-click clipboard copy.
 */

const bubbleVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.97 },
  visible: { 
    opacity: 1, y: 0, scale: 1,
    transition: { type: 'spring', stiffness: 350, damping: 28 }
  },
  exit: { opacity: 0, y: -10, scale: 0.97, transition: { duration: 0.15 } }
};

export default function ChatResponsePanel({ task, onNewChat }) {
  const [copied, setCopied] = useState(false);
  const [isUndoing, setIsUndoing] = useState(false);

  if (!task) return null;

  const { state, events = [], metadata = {}, goal } = task;
  const isChatMode = metadata.guidance_mode === 'chat';
  
  if (!isChatMode) return null;

  const isCompleted = state === 'COMPLETED' || state === 'TASK_COMPLETED';
  const isFailed = state === 'FAILED' || state === 'TASK_FAILED';
  const isLoading = !isCompleted && !isFailed && state !== 'STOPPED';

  // 1. Accumulate live streamed tokens
  const chatTokenEvents = events.filter(e => e.event_type === 'chat_token');
  const streamedReply = chatTokenEvents.map(e => e.payload?.chunk || e.payload?.token || '').join('');

  // 2. Extract final completed AI reply from events
  let finalReply = null;
  if (isCompleted || isFailed) {
    const completedEvent = events.find(e => e.event_type === 'task_completed');
    const failedEvent = events.find(e => e.event_type === 'task_failed');
    if (completedEvent?.payload?.details) {
      finalReply = completedEvent.payload.details;
    } else if (failedEvent?.payload?.reason) {
      finalReply = `⚠️ ${failedEvent.payload.reason}`;
    } else {
      const lastEvent = events[events.length - 1];
      if (lastEvent?.payload?.reason) {
        finalReply = lastEvent.payload.reason;
      }
    }
  }

  // Active text to display
  const activeContent = finalReply || streamedReply || '';
  const isActivelyStreaming = isLoading && streamedReply.length > 0;

  const handleCopy = () => {
    if (!activeContent) return;
    navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleUndo = async () => {
    try {
      setIsUndoing(true);
      await api.undoChatMessage();
      onNewChat();
    } catch (err) {
      console.error(err);
      alert('Failed to undo: ' + err.message);
    } finally {
      setIsUndoing(false);
    }
  };

  const wordCount = activeContent.trim() ? activeContent.trim().split(/\s+/).length : 0;

  return (
    <div className="w-full mt-6 space-y-4">
      {/* User Message Bubble */}
      <motion.div 
        variants={bubbleVariants}
        initial="hidden"
        animate="visible"
        className="flex justify-end"
      >
        <motion.div 
          whileHover={{ scale: 1.005 }}
          className="max-w-[85%] bg-blue-600/15 border border-blue-500/25 rounded-2xl rounded-tr-md px-5 py-3 shadow-lg shadow-black/20"
        >
          <div className="flex items-center gap-2 mb-1.5 justify-end">
            <span className="text-[10px] uppercase font-mono tracking-widest text-blue-400/80">You</span>
          </div>
          <p className="text-sm text-white/95 whitespace-pre-wrap leading-relaxed font-sans">{goal}</p>
        </motion.div>
      </motion.div>

      {/* Loading Indicator (Shown only when no tokens have arrived yet) */}
      <AnimatePresence>
        {isLoading && !isActivelyStreaming && (
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
            transition={{ type: 'spring', stiffness: 350, damping: 28 }}
            className="flex justify-start"
          >
            <div className="max-w-[85%] bg-[#121316] border border-white/10 rounded-2xl rounded-tl-md px-5 py-4 shadow-xl">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  {[0, 1, 2].map(i => (
                    <motion.span 
                      key={i}
                      className="w-2 h-2 bg-emerald-400/80 rounded-full"
                      animate={{ 
                        y: [0, -5, 0],
                        opacity: [0.3, 1, 0.3]
                      }}
                      transition={{ 
                        duration: 0.75, 
                        repeat: Infinity, 
                        delay: i * 0.15,
                        ease: 'easeInOut'
                      }}
                    />
                  ))}
                </div>
                <motion.span 
                  className="text-xs text-gray-400 font-mono"
                  animate={{ opacity: [0.6, 1, 0.6] }}
                  transition={{ duration: 1.8, repeat: Infinity }}
                >
                  {state === 'STARTING' && 'Synthesizing local context...'}
                  {state === 'UNDERSTANDING' && 'Querying local model...'}
                  {state === 'OBSERVING' && 'Preparing response...'}
                  {!['STARTING', 'UNDERSTANDING', 'OBSERVING'].includes(state) && `${state}...`}
                </motion.span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* AI Response Bubble (Streams live or displays final) */}
      <AnimatePresence>
        {activeContent && (
          <motion.div 
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            className="flex justify-start"
          >
            <div className="max-w-[90%] bg-[#0F1012] border border-white/10 rounded-2xl rounded-tl-md px-5 py-4 shadow-2xl shadow-black/40 relative group">
              {/* Header: Identity & Actions */}
              <div className="flex items-center justify-between gap-3 mb-3 pb-2 border-b border-white/5">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded-md bg-gradient-to-br from-emerald-500/20 to-sky-500/20 border border-emerald-500/30 flex items-center justify-center">
                    <span className="text-[10px] text-emerald-400 font-bold font-mono">C</span>
                  </div>
                  <span className="text-[10px] font-semibold text-gray-300 uppercase tracking-widest font-mono">
                    COMPASS Co-Pilot
                  </span>
                  {isActivelyStreaming && (
                    <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-mono animate-pulse">
                      ● Streaming Live
                    </span>
                  )}
                  {isCompleted && (
                    <span className="text-[9px] px-2 py-0.5 rounded-full bg-white/5 text-gray-400 font-mono">
                      {wordCount} words
                    </span>
                  )}
                </div>

                {/* 1-Click Copy Button */}
                <button
                  onClick={handleCopy}
                  className="text-[11px] text-gray-400 hover:text-white px-2 py-1 rounded bg-white/5 hover:bg-white/10 border border-white/10 transition-colors flex items-center gap-1.5"
                  title="Copy full response"
                >
                  <span className="material-symbols-outlined text-[13px]">
                    {copied ? 'check' : 'content_copy'}
                  </span>
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              </div>

              {/* Message Content */}
              <p className="text-sm text-gray-100 whitespace-pre-wrap leading-relaxed font-sans selection:bg-blue-500/30">
                {activeContent}
                {isActivelyStreaming && (
                  <motion.span
                    animate={{ opacity: [1, 0, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                    className="inline-block ml-1 text-emerald-400 font-bold"
                  >
                    ▊
                  </motion.span>
                )}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* New Chat button after completion */}
      <AnimatePresence>
        {(isCompleted || isFailed) && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 250, damping: 25 }}
            className="flex justify-center pt-2 gap-4"
          >
            <motion.button
              onClick={handleUndo}
              disabled={isUndoing}
              whileHover={{ scale: 1.03, borderColor: 'rgba(239,68,68,0.25)' }}
              whileTap={{ scale: 0.97 }}
              className="text-xs text-red-300 hover:text-red-200 px-4 py-2 rounded-full border border-red-500/15 bg-red-500/5 hover:bg-red-500/10 transition-colors flex items-center gap-2 shadow-lg disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[14px]">undo</span>
              {isUndoing ? 'Undoing...' : 'Undo Step'}
            </motion.button>
            <motion.button
              onClick={onNewChat}
              whileHover={{ scale: 1.03, borderColor: 'rgba(255,255,255,0.25)' }}
              whileTap={{ scale: 0.97 }}
              className="text-xs text-gray-300 hover:text-white px-4 py-2 rounded-full border border-white/15 bg-white/5 hover:bg-white/10 transition-colors flex items-center gap-2 shadow-lg"
            >
              <span className="material-symbols-outlined text-[14px]">add</span>
              Start New Query
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
