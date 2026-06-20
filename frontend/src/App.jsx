import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { startJob, cancelJob, subscribeToJobEvents } from './utils/api';
import { JobForm } from './components/JobForm';
import { LogsPanel } from './components/LogsPanel';
import { ContextPanel } from './components/ContextPanel';
import { PatchViewer } from './components/PatchViewer';
import { SafetyPanel } from './components/SafetyPanel';
import { StatusBadge, StatusStrip } from './components/StatusBadge';
import { BenchmarkPanel } from './components/BenchmarkPanel';
import { Cursor } from './components/Cursor';

function App() {
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [logs, setLogs] = useState([]);
  const [retrievedFiles, setRetrievedFiles] = useState([]);
  const [patchCode, setPatchCode] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [maxAttempts] = useState(3);
  const [sandboxStatus, setSandboxStatus] = useState('idle');

  useEffect(() => {
    if (!jobId) return;

    const unsubscribe = subscribeToJobEvents(jobId, {
      onLog: (log) => {
        setLogs(prev => [...prev, log]);
        // Parse attempt info from logs
        const attemptMatch = log.match(/attempt\s+(\d+)/i);
        if (attemptMatch) setAttempt(parseInt(attemptMatch[1]));
        // Parse sandbox status from logs
        if (log.toLowerCase().includes('sandbox created') || log.toLowerCase().includes('container')) {
          setSandboxStatus('active');
        }
        if (log.toLowerCase().includes('cleanup') || log.toLowerCase().includes('destroyed')) {
          setSandboxStatus('destroyed');
        }
      },
      onStatus: (newStatus) => {
        setStatus(newStatus);
        if (newStatus === 'success' || newStatus === 'failed' || newStatus === 'cancelled' || newStatus === 'crashed') {
          setSandboxStatus('destroyed');
        }
      },
      onRetrieval: (files) => setRetrievedFiles(files),
      onPatch: (patch) => setPatchCode(patch),
      onError: (err) => {
        setLogs(prev => [...prev, `[System Error] ${err}`]);
        setStatus('failed');
      }
    });

    return () => unsubscribe();
  }, [jobId]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      if (jobId && (status === 'running' || status === 'pending')) {
        cancelJob(jobId).catch(console.error);
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [jobId, status]);

  const handleStart = async (repoUrl, issueText) => {
    try {
      setLogs(['Initializing...']);
      setRetrievedFiles([]);
      setPatchCode('');
      setStatus('pending');
      setAttempt(0);
      setSandboxStatus('idle');
      
      const res = await startJob(repoUrl, issueText);
      setJobId(res.job_id);
    } catch (err) {
      setLogs([`Error starting job: ${err.message}`]);
      setStatus('failed');
    }
  };

  const handleCancel = async () => {
    if (!jobId) return;
    try {
      setLogs(prev => [...prev, '[System] Execution aborted by user.']);
      await cancelJob(jobId);
    } catch (err) {
      console.error("Failed to cancel job", err);
    }
  };

  const isRunning = status === 'pending' || status === 'running';

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20, filter: 'blur(10px)' },
    show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } }
  };

  return (
    <>
      <Cursor />
      
      {/* Background Orbs */}
      <div className="aurora-orb orb-1" />
      <div className="aurora-orb orb-2" />
      <div className="aurora-orb orb-3" />

      <div className="relative z-10 container mx-auto px-4 sm:px-6 lg:px-12 max-w-[1400px] min-h-screen flex flex-col py-12">
        
        <motion.header 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          className="mb-6 flex items-end justify-between border-b border-white/[0.05] pb-8"
        >
          <div>
            <h1 className="text-4xl sm:text-5xl font-semibold tracking-tighter text-white mb-2">
              Intelligence that ships.
            </h1>
            <p className="text-white/40 tracking-wide font-light text-lg">
              AutoPatch AI <span className="mx-2 opacity-30">|</span> Autonomous Bug Resolution
            </p>
          </div>
          <div className="flex items-center space-x-6">
            <StatusBadge status={status} />
            {jobId && <span className="text-xs text-white/30 font-mono tracking-widest">{jobId.split('-')[1]}</span>}
          </div>
        </motion.header>

        {/* Status Strip */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mb-8"
        >
          <StatusStrip
            status={status}
            attempt={attempt}
            maxAttempts={maxAttempts}
            sandboxStatus={sandboxStatus}
          />
        </motion.div>

        <motion.main 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-8 min-h-0"
        >
          {/* Left Column: Controls + Benchmark */}
          <motion.div variants={itemVariants} className="lg:col-span-4 flex flex-col space-y-8 pr-2 pb-4">
            <JobForm onSubmit={handleStart} disabled={isRunning} />
            <SafetyPanel onCancel={handleCancel} isRunning={isRunning} />
            <BenchmarkPanel />
          </motion.div>

          {/* Middle Column: Logs */}
          <motion.div variants={itemVariants} className="lg:col-span-4 min-h-0 h-[600px] lg:h-auto">
            <LogsPanel logs={logs} />
          </motion.div>

          {/* Right Column: Code/Context */}
          <motion.div variants={itemVariants} className="lg:col-span-4 flex flex-col space-y-8 h-[600px] lg:h-auto overflow-y-auto pr-1">
            {retrievedFiles.length > 0 && <ContextPanel files={retrievedFiles} />}
            {patchCode && <PatchViewer patchCode={patchCode} />}
            
            {retrievedFiles.length === 0 && !patchCode && (
               <div className="inset-panel flex flex-col items-center justify-center h-full text-white/20 border-dashed border-white/[0.05]">
                 <p className="text-xs uppercase tracking-widest text-center px-8">Awaiting<br/>Context Assembly</p>
               </div>
            )}
          </motion.div>
        </motion.main>
      </div>
    </>
  );
}

export default App;
