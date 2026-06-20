import { Shield, ShieldAlert, XCircle, Clock, Repeat, Cpu, HardDrive, Layers } from 'lucide-react';

const constraints = [
  { icon: ShieldAlert, title: 'Network Disabled', desc: 'Zero egress. Containers are fully airgapped.' },
  { icon: HardDrive, title: 'Memory Cap', desc: 'Hard limit at 256 MB.' },
  { icon: Cpu, title: 'CPU Cap', desc: 'CPU quotas enforced per container.' },
  { icon: Layers, title: 'PID Cap', desc: 'Max 128 processes inside sandbox.' },
  { icon: Clock, title: 'Timeout', desc: 'Commands abort after 120 seconds.' },
  { icon: Repeat, title: 'Max Attempts', desc: 'Agent retries capped at 3 iterations.' },
];

export function SafetyPanel({ onCancel, isRunning }) {
  return (
    <div className="glass-panel p-8 relative group overflow-y-auto">
      <div className="absolute inset-0 bg-gradient-to-tr from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

      <div className="relative">
        <h2 className="text-sm font-medium tracking-widest text-white/50 uppercase mb-6 flex items-center">
          <Shield size={14} className="mr-2 text-white/80" /> Safety Constraints
        </h2>
        
        <div className="space-y-3 mb-8">
          {constraints.map(({ icon: Icon, title, desc }, i) => (
            <div key={i} className="flex items-start">
              <Icon size={14} className="mr-3 mt-0.5 text-white/40 flex-shrink-0" />
              <div className="text-sm">
                <span className="font-medium text-white/90">{title}</span>
                <p className="text-white/40 mt-0.5 text-xs leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
        
        <button
          type="button"
          onClick={onCancel}
          disabled={!isRunning}
          className="w-full bg-transparent hover:bg-white/5 border border-white/10 text-white/70 hover:text-white font-medium py-3 px-4 rounded-xl transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed flex justify-center items-center group"
        >
          <XCircle size={18} className="mr-2 text-white/40 group-hover:text-red-400 transition-colors" />
          Abort Execution
        </button>
      </div>
    </div>
  );
}
