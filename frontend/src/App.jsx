import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from './api';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import MainContent from './components/MainContent';
import WorkflowsView from './components/WorkflowsView';
import TaskHistoryView from './components/TaskHistoryView';
import DiagnosticsView from './components/DiagnosticsView';
import SettingsView from './components/SettingsView';
import PlanReviewModal from './components/PlanReviewModal';
import ErrorBanner from './components/ErrorBanner';
import SystemTelemetryModal from './components/SystemTelemetryModal';
import OnboardingModal from './components/OnboardingModal';

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState('reconnecting');
  const [latency, setLatency] = useState(0);
  const [health, setHealth] = useState(null);
  const [systemInfo, setSystemInfo] = useState(null);
  const [activeTask, setActiveTask] = useState(null);
  const [tasksList, setTasksList] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [models, setModels] = useState([]);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [activeWindow, setActiveWindow] = useState(null);
  const [isTelemetryOpen, setIsTelemetryOpen] = useState(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(() => !localStorage.getItem('compass_onboarded'));
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Language state: 'en' | 'kn' (Kannada for Digital Literacy & Governance SIH26171)
  const [language, setLanguage] = useState(() => localStorage.getItem('compass_lang') || 'en');

  // UI Experience Mode: 'simple' (clean, intuitive for everyday users) | 'pro' (power user/developer)
  const [uiMode, setUiMode] = useState(() => localStorage.getItem('compass_ui_mode') || 'simple');

  // URL Hash-based Navigation routing: 'workspace' | 'workflows' | 'history' | 'diagnostics' | 'settings'
  const [activeView, setActiveView] = useState(() => {
    const hash = window.location.hash.replace('#', '');
    return ['workspace', 'workflows', 'history', 'diagnostics', 'settings'].includes(hash)
      ? hash
      : 'workspace';
  });

  // Pre-Execution Plan Review State
  const [pendingPlan, setPendingPlan] = useState(null);
  const [isPlanReviewOpen, setIsPlanReviewOpen] = useState(false);
  const [isExecutingPlan, setIsExecutingPlan] = useState(false);

  const activeTaskIdRef = useRef(null);
  activeTaskIdRef.current = activeTask?.id;

  const handleLanguageChange = (lang) => {
    setLanguage(lang);
    localStorage.setItem('compass_lang', lang);
  };

  const handleViewChange = (view) => {
    setActiveView(view);
    window.location.hash = view;
  };

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      if (['workspace', 'workflows', 'history', 'diagnostics', 'settings'].includes(hash)) {
        setActiveView(hash);
      }
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const fetchTasks = useCallback(async () => {
    try {
      const list = await api.listTasks(25);
      setTasksList(Array.isArray(list) ? list : (list?.items || []));
    } catch (err) {
      console.warn('Failed to fetch task list', err);
    }
  }, []);

  const fetchModels = useCallback(async () => {
    try {
      const res = await api.getAIModels(false);
      setModels(res.models || []);
    } catch (err) {
      console.warn('Failed to fetch models', err);
    }
  }, []);

  const probeHealth = useCallback(async () => {
    const start = performance.now();
    try {
      const data = await api.getHealth();
      const elapsed = Math.round(performance.now() - start);
      setLatency(elapsed);
      setHealth(data);
      setConnectionStatus((prev) => {
        if (prev !== 'connected') {
          fetchTasks();
          fetchModels();
          api.getSystemInfo().then(setSystemInfo).catch(() => {});
          api.getActiveWindow().then(setActiveWindow).catch(() => {});
        }
        return 'connected';
      });
      api.getActiveWindow().then(setActiveWindow).catch(() => {});
      setErrorMessage('');

      if (activeTaskIdRef.current) {
        if (activeTaskIdRef.current.startsWith('chat-')) {
          // Client-side chat tasks stream tokens directly and do not require backend task polling
          return;
        }
        try {
          const taskDetail = await api.getTask(activeTaskIdRef.current);
          setActiveTask(taskDetail);
          if (taskDetail.state === 'WAITING_CONFIRMATION') {
            const appr = await api.getPendingApproval(activeTaskIdRef.current);
            setPendingApproval(appr?.has_pending ? appr.approval : null);
          } else {
            setPendingApproval(null);
          }
        } catch (err) {
          console.warn('Failed to refresh task details:', err);
          if (err.message?.includes('404') || err.message?.includes('not found') || err.message?.includes('Not Found')) {
            setActiveTask(null);
          }
        }
      }
    } catch (err) {
      setConnectionStatus('disconnected');
      setErrorMessage('Backend unavailable. Make sure the FastAPI server is running on 127.0.0.1:8000.');
    }
  }, [fetchTasks, fetchModels]);

  const isTaskRunning = activeTask && ![
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
  ].includes(activeTask.state);

  useEffect(() => {
    probeHealth();
    fetchTasks();
    fetchModels();
    const pollInterval = isTaskRunning ? 600 : 2500;
    const interval = setInterval(probeHealth, pollInterval);
    api.getSystemInfo().then(setSystemInfo).catch(() => {});
    return () => clearInterval(interval);
  }, [probeHealth, fetchTasks, fetchModels, isTaskRunning]);

  // Handle Goal Submission with Safe Pre-Execution Plan Review
  const handleStartTask = async (goal, modelId, selectedMode = 'assist') => {
    setIsSubmitting(true);
    setErrorMessage('');
    try {
      if (selectedMode === 'chat') {
        const fakeTask = {
          id: 'chat-' + Date.now(),
          goal: goal,
          state: 'STARTING',
          metadata: { guidance_mode: 'chat', model_id: modelId },
          events: []
        };
        setActiveTask(fakeTask);
        setActiveView('workspace');

        try {
          const res = await fetch('http://127.0.0.1:8000/api/tasks/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: goal, model_id: modelId })
          });

          if (!res.ok) {
            const err = await res.text();
            throw new Error(err || 'Chat request failed');
          }

          setActiveTask(prev => prev ? { ...prev, state: 'STREAMING' } : prev);

          const reader = res.body.getReader();
          const decoder = new TextDecoder();

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value, { stream: true });
            setActiveTask(prev => {
              if (!prev) return prev;
              return {
                ...prev,
                events: [...prev.events, { event_type: 'chat_token', payload: { chunk } }]
              };
            });
          }

          setActiveTask(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              state: 'COMPLETED',
              events: [...prev.events, { event_type: 'task_completed', payload: { details: '' } }]
            };
          });
        } catch (streamErr) {
          setActiveTask(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              state: 'FAILED',
              events: [...prev.events, { event_type: 'task_failed', payload: { reason: streamErr.message } }]
            };
          });
          setErrorMessage(streamErr.message);
        }
      } else {
        // Step 1: Create task record
        const newTask = await api.createTask(goal, { model_id: modelId, guidance_mode: selectedMode });
        const detail = await api.getTask(newTask.id);
        setActiveTask(detail);
        fetchTasks();
        setActiveView('workspace');

        // Step 2: Attempt Plan Generation for Pre-Execution Review
        try {
          const planRes = await api.generatePlan(goal, newTask.id);
          if (planRes?.plan && (planRes.plan.steps?.length > 0 || planRes.plan.actions?.length > 0)) {
            setPendingPlan({
              plan: planRes.plan,
              goal: goal,
              taskId: newTask.id,
            });
            setIsPlanReviewOpen(true);
            return; // Wait for operator to review & approve in PlanReviewModal
          }
        } catch (planErr) {
          console.warn('Plan generation review fallback to direct execution:', planErr);
        }

        // Direct execution fallback if plan has no steps
        await api.runTask(newTask.id);
        const updated = await api.getTask(newTask.id);
        setActiveTask(updated);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to start task');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Plan Review Modal Approval Handler
  const handleApprovePlan = async () => {
    if (!pendingPlan?.taskId) return;
    setIsExecutingPlan(true);
    try {
      await api.runTask(pendingPlan.taskId);
      const updated = await api.getTask(pendingPlan.taskId);
      setActiveTask(updated);
      setIsPlanReviewOpen(false);
      setPendingPlan(null);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to start approved task');
    } finally {
      setIsExecutingPlan(false);
    }
  };

  const handleCancelPlan = async () => {
    if (pendingPlan?.taskId) {
      try {
        await api.stopTask(pendingPlan.taskId);
        const updated = await api.getTask(pendingPlan.taskId);
        setActiveTask(updated);
      } catch (_) {}
    }
    setIsPlanReviewOpen(false);
    setPendingPlan(null);
  };

  const handleConfirmAction = async (taskId, decisionId, approved, reason = '') => {
    try {
      await api.confirmAction(taskId, decisionId, approved, reason);
      setPendingApproval(null);
      const updated = await api.getTask(taskId);
      setActiveTask(updated);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to submit confirmation');
    }
  };

  const handleTransition = async (taskId, newState, reason) => {
    try {
      await api.transitionTask(taskId, newState, reason);
      const updated = await api.getTask(taskId);
      setActiveTask(updated);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to transition task');
    }
  };

  const handleStopTask = async (taskId) => {
    try {
      const id = typeof taskId === 'string' ? taskId : activeTask?.id;
      if (!id) return;
      await api.stopTask(id);
      const updated = await api.getTask(id);
      setActiveTask(updated);
    } catch (err) {
      try {
        const id = typeof taskId === 'string' ? taskId : activeTask?.id;
        if (id) {
          const updated = await api.getTask(id);
          setActiveTask(updated);
        }
      } catch (_) {}
      console.warn('Stop task error:', err.message);
    }
  };

  const handleRunTask = async (taskId) => {
    try {
      const id = taskId || activeTask?.id;
      if (!id) return;
      await api.runTask(id);
      const updated = await api.getTask(id);
      setActiveTask(updated);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to execute task');
    }
  };

  const handleSelectTask = async (taskId) => {
    try {
      const detail = await api.getTask(taskId);
      setActiveTask(detail);
      setActiveView('workspace');
    } catch (err) {
      console.error('Failed to select task', err);
    }
  };

  const handleClearActiveTask = () => {
    setActiveTask(null);
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await api.deleteTask(taskId);
      if (activeTask?.id === taskId) {
        setActiveTask(null);
      }
      fetchTasks();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to delete task');
    }
  };

  const handleClearCompletedTasks = async () => {
    try {
      await api.clearTasks();
      if (
        activeTask &&
        [
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
        ].includes(activeTask.state)
      ) {
        setActiveTask(null);
      }
      fetchTasks();
    } catch (err) {
      setErrorMessage(err.message || 'Failed to clear completed tasks');
    }
  };

  return (
    <div className="flex h-screen bg-stitch-bg bg-dot-pattern relative overflow-hidden">
      {/* Background Orbs with Motion */}
      <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden">
        <motion.div
          animate={{
            x: [0, 30, -20, 0],
            y: [0, -20, 10, 0],
            scale: [1, 1.1, 0.95, 1],
          }}
          transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[120px] mix-blend-screen"
        />
        <motion.div
          animate={{
            x: [0, -40, 20, 0],
            y: [0, 30, -15, 0],
            scale: [1, 0.95, 1.1, 1],
          }}
          transition={{ duration: 25, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute bottom-[-20%] right-[-10%] w-[800px] h-[800px] bg-purple-600/5 rounded-full blur-[150px] mix-blend-screen"
        />
      </div>

      <div className="z-10 flex h-full w-full">
        {/* Sidebar with Navigation and Workstreams */}
        <Sidebar
          tasks={tasksList}
          onSelectTask={(taskId) => {
            handleSelectTask(taskId);
            setIsMobileSidebarOpen(false);
          }}
          activeTaskId={activeTask?.id}
          onDeleteTask={handleDeleteTask}
          onClearCompleted={handleClearCompletedTasks}
          activeView={activeView}
          onViewChange={(view) => {
            handleViewChange(view);
            setIsMobileSidebarOpen(false);
          }}
          language={language}
          onLanguageChange={handleLanguageChange}
          isOpen={isMobileSidebarOpen}
          onClose={() => setIsMobileSidebarOpen(false)}
        />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col h-screen overflow-y-auto relative">
          {/* Production Header Component */}
          <Header
            connectionStatus={connectionStatus}
            latency={latency}
            activeView={activeView}
            onViewChange={handleViewChange}
            activeWindow={activeWindow}
            language={language}
            onLanguageChange={handleLanguageChange}
            onOpenTelemetry={() => setIsTelemetryOpen(true)}
            onOpenSidebar={() => setIsMobileSidebarOpen(true)}
            onToggleMobileSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
            isMobileSidebarOpen={isMobileSidebarOpen}
            onEmergencyAbort={handleStopTask}
          />

          {/* Conditional View Rendering */}
          <div className="flex-1">
            {activeView === 'workspace' && (
              <MainContent
                onStart={handleStartTask}
                onStop={handleStopTask}
                onTransition={handleTransition}
                onRunTask={handleRunTask}
                isSubmitting={isSubmitting}
                activeTask={activeTask}
                isConnected={connectionStatus === 'connected'}
                systemInfo={systemInfo}
                models={models}
                onClearActiveTask={handleClearActiveTask}
                pendingApproval={pendingApproval}
                onConfirmAction={handleConfirmAction}
                activeWindow={activeWindow}
                latency={latency}
                onOpenTelemetry={() => setIsTelemetryOpen(true)}
                language={language}
              />
            )}

            {activeView === 'workflows' && (
              <WorkflowsView
                language={language}
                onOpenTelemetry={() => setIsTelemetryOpen(true)}
              />
            )}

            {activeView === 'history' && (
              <TaskHistoryView
                tasks={tasksList}
                onSelectTask={handleSelectTask}
                onDeleteTask={handleDeleteTask}
                onClearCompleted={handleClearCompletedTasks}
                onRunTask={handleRunTask}
                language={language}
              />
            )}

            {activeView === 'diagnostics' && (
              <DiagnosticsView
                systemInfo={systemInfo}
                latency={latency}
                health={health}
                language={language}
              />
            )}

            {activeView === 'settings' && (
              <SettingsView
                models={models}
                language={language}
                onLanguageChange={handleLanguageChange}
              />
            )}
          </div>
        </div>
      </div>

      {/* Pre-Execution Plan Review Modal (Priority B) */}
      <PlanReviewModal
        isOpen={isPlanReviewOpen}
        onClose={handleCancelPlan}
        plan={pendingPlan?.plan}
        goal={pendingPlan?.goal}
        onApprove={handleApprovePlan}
        isExecuting={isExecutingPlan}
        language={language}
      />

      {/* System Telemetry Diagnostics Modal */}
      <SystemTelemetryModal
        isOpen={isTelemetryOpen}
        onClose={() => setIsTelemetryOpen(false)}
        systemInfo={systemInfo}
        latency={latency}
        health={health}
      />

      {/* Onboarding Tour Modal */}
      <OnboardingModal
        isOpen={isOnboardingOpen}
        onClose={() => {
          setIsOnboardingOpen(false);
          localStorage.setItem('compass_onboarded', 'true');
        }}
      />

      {/* Global Error Notification */}
      <ErrorBanner
        message={errorMessage}
        onDismiss={() => setErrorMessage('')}
        onRetry={probeHealth}
      />
    </div>
  );
}
