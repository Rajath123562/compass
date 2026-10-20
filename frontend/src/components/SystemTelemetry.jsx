import React from 'react';
import { motion } from 'framer-motion';

export default function SystemTelemetry({ systemInfo }) {
  if (!systemInfo) return null;

  const memPercent = (systemInfo.memory_used_mb / systemInfo.memory_total_mb) * 100;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 200, damping: 25 }}
      whileHover={{ y: -4, boxShadow: '0 20px 50px rgba(59,130,246,0.08)' }}
      className="glass-card rounded-[24px] p-6 h-56 flex flex-col justify-between text-white relative overflow-hidden group cursor-pointer transition-all duration-500"
    >
      {/* Decorative gradient orb inside card */}
      <motion.div 
        animate={{ 
          scale: [1, 1.1, 1],
          opacity: [0.2, 0.3, 0.2]
        }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute -top-12 -right-12 w-32 h-32 bg-blue-500/20 rounded-full blur-[40px]"
      />
      
      <div className="relative z-10 flex justify-between items-start">
         <motion.div 
           whileHover={{ scale: 1.1, rotate: 5 }}
           className="bg-white/5 border border-white/10 rounded-full w-10 h-10 flex items-center justify-center backdrop-blur-md"
         >
            <span className="material-symbols-outlined text-[20px] text-blue-300">memory</span>
         </motion.div>
         <motion.span 
           initial={{ opacity: 0, x: 10 }}
           animate={{ opacity: 1, x: 0 }}
           transition={{ delay: 0.3 }}
           className="text-xs font-mono text-gray-500 bg-black/20 px-2 py-1 rounded"
         >
            UPTIME: {systemInfo.uptime_seconds}s
         </motion.span>
      </div>

      <div className="relative z-10 flex flex-col gap-4">
         <div className="flex justify-between items-end">
            <div>
               <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">Compute Core</h4>
               <motion.p 
                 key={systemInfo.cpu_percent}
                 initial={{ opacity: 0, y: 5 }}
                 animate={{ opacity: 1, y: 0 }}
                 className="text-3xl font-light tracking-tight"
               >
                 {systemInfo.cpu_percent}<span className="text-xl text-gray-500">%</span>
               </motion.p>
            </div>
            <div className="text-right">
               <h4 className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-1">RAM Allocation</h4>
               <motion.p 
                 key={systemInfo.memory_used_mb}
                 initial={{ opacity: 0, y: 5 }}
                 animate={{ opacity: 1, y: 0 }}
                 className="text-xl font-light tracking-tight"
               >
                 {systemInfo.memory_used_mb}<span className="text-sm text-gray-500"> MB</span>
               </motion.p>
            </div>
         </div>
         
         <div className="w-full bg-black/40 h-1.5 rounded-full overflow-hidden mt-1 backdrop-blur-sm border border-white/5">
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${memPercent}%` }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
              className="bg-gradient-to-r from-blue-500 to-indigo-400 h-full shadow-[0_0_10px_rgba(59,130,246,0.5)]"
            />
         </div>
      </div>
    </motion.div>
  );
}
