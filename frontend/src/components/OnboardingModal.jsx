import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function OnboardingModal({ isOpen, onClose }) {
  const [step, setStep] = useState(0);

  if (!isOpen) return null;

  const steps = [
    {
      title: "Your Ambient Desktop Companion",
      description: "COMPASS is designed to be whisper-quiet. Press Alt + Space or keep it docked to summon instant guidance over any Windows app—Excel, Chrome, VS Code, or Photoshop.",
      badge: "Step 1 of 3",
      icon: (
        <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      )
    },
    {
      title: "Ghost Guidance (Respecting Your Screen)",
      description: "COMPASS illuminates buttons and menus with a gentle, glowing halo and instructional tooltips before acting. It teaches you how to navigate your software rather than blindly hijacking your cursor.",
      badge: "Step 2 of 3",
      icon: (
        <svg className="w-8 h-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      )
    },
    {
      title: "Human Sovereignty & 10ms Kill-Switch",
      description: "You are always in total control. Touching your physical mouse or pressing Escape aborts automation in under 10 milliseconds. Zero data leaves your computer—100% private and on-device.",
      badge: "Step 3 of 3",
      icon: (
        <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
      )
    }
  ];

  const current = steps[step];

  const handleNext = () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      localStorage.setItem('compass_onboarded', 'true');
      onClose();
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          className="w-full max-w-md bg-[#121316] border border-white/10 rounded-2xl shadow-2xl p-7 relative overflow-hidden"
        >
          {/* Badge & Icon */}
          <div className="flex items-center justify-between mb-5">
            <span className="text-[11px] font-semibold tracking-wider uppercase px-2.5 py-1 rounded-md bg-white/5 text-gray-300 border border-white/10">
              {current.badge}
            </span>
            <div className="p-2.5 rounded-xl bg-white/5 border border-white/10">
              {current.icon}
            </div>
          </div>

          {/* Text Content */}
          <h2 className="text-xl font-semibold text-white tracking-tight mb-2.5">
            {current.title}
          </h2>
          <p className="text-sm text-gray-400 leading-relaxed mb-6">
            {current.description}
          </p>

          {/* Dots & Actions */}
          <div className="flex items-center justify-between pt-4 border-t border-white/10">
            <div className="flex items-center gap-1.5">
              {steps.map((_, i) => (
                <div
                  key={i}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    i === step ? 'w-6 bg-blue-500' : 'w-1.5 bg-white/20'
                  }`}
                />
              ))}
            </div>

            <button
              onClick={handleNext}
              className="px-5 py-2 rounded-xl bg-white text-black text-sm font-medium hover:bg-gray-200 transition-all shadow-md active:scale-95"
            >
              {step === steps.length - 1 ? 'Start Using COMPASS' : 'Next →'}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
