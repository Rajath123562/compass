import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ErrorBanner({ message, onDismiss, onRetry }) {
  return (
    <AnimatePresence>
      {message && (
        <motion.aside 
          initial={{ y: 80, opacity: 0, scale: 0.95 }}
          animate={{ y: 0, opacity: 1, scale: 1 }}
          exit={{ y: 80, opacity: 0, scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] w-[92%] max-w-2xl"
        >
          <motion.div 
            layout
            className="bg-[#1a1012]/90 backdrop-blur-xl border border-red-500/30 rounded-full px-4 py-2.5 flex items-center justify-between gap-3 shadow-[0_20px_50px_rgba(0,0,0,0.8),0_0_30px_rgba(239,68,68,0.1)]"
          >
            <div className="flex items-center gap-3 overflow-hidden">
              <motion.div 
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="w-7 h-7 rounded-full bg-red-500/15 border border-red-500/30 flex items-center justify-center shrink-0 text-red-400"
              >
                <span className="material-symbols-outlined text-[16px]">error</span>
              </motion.div>
              <p className="text-xs text-gray-200 truncate font-medium">
                {message}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {onRetry && (
                <motion.button 
                  onClick={onRetry}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="px-3 py-1 rounded-full bg-white/10 hover:bg-white/15 border border-white/10 text-white text-xs font-medium transition-colors flex items-center gap-1"
                >
                  <span>Retry</span>
                </motion.button>
              )}
              <motion.button 
                onClick={onDismiss}
                whileHover={{ scale: 1.1, backgroundColor: 'rgba(255,255,255,0.1)' }}
                whileTap={{ scale: 0.9 }}
                className="p-1 rounded-full text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined text-[18px]">close</span>
              </motion.button>
            </div>
          </motion.div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
