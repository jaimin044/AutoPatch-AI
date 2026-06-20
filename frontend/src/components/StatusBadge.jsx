import { Loader2 } from 'lucide-react';

export function StatusBadge({ status }) {
  const statusConfig = {
    pending: { color: 'text-white/30', bg: 'bg-white/[0.05]', border: 'border-white/[0.05]', label: 'Idle' },
    running: { color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/20', label: 'Running', icon: Loader2 },
    success: { color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20', label: 'Success' },
    failed: { color: 'text-rose-400', bg: 'bg-rose-400/10', border: 'border-rose-400/20', label: 'Failed' },
    cancelled: { color: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/20', label: 'Cancelled' },
    crashed: { color: 'text-rose-500', bg: 'bg-rose-500/10', border: 'border-rose-500/20', label: 'Crashed' },
  };

  const config = statusConfig[status] || statusConfig.pending;
  const Icon = config.icon;

  return (
    <div className={`flex items-center px-3 py-1.5 rounded-full border backdrop-blur-md ${config.bg} ${config.border} transition-colors duration-500`}>
      {Icon ? (
        <Icon className={`w-3 h-3 mr-2 animate-spin ${config.color}`} />
      ) : (
        <div className={`w-1.5 h-1.5 rounded-full mr-2 ${config.color.replace('text', 'bg')} shadow-[0_0_8px_currentColor]`} />
      )}
      <span className={`text-[10px] font-medium tracking-widest uppercase ${config.color}`}>
        {config.label}
      </span>
    </div>
  );
}

export function StatusStrip({ status, attempt, maxAttempts, sandboxStatus }) {
  return (
    <div className="glass-panel px-6 py-4 flex items-center justify-between">
      <div className="flex items-center space-x-6">
        <StatusBadge status={status} />
        
        <div className="flex items-center space-x-1">
          <span className="text-[10px] tracking-widest uppercase text-white/30">Attempt</span>
          <span className="text-xs font-mono text-white/70 ml-2">{attempt}/{maxAttempts}</span>
        </div>
        
        <div className="flex items-center space-x-1">
          <span className="text-[10px] tracking-widest uppercase text-white/30">Sandbox</span>
          <span className={`text-xs font-mono ml-2 ${
            sandboxStatus === 'active' ? 'text-emerald-400/80' :
            sandboxStatus === 'destroyed' ? 'text-white/30' :
            'text-white/50'
          }`}>
            {sandboxStatus || 'idle'}
          </span>
        </div>
      </div>
    </div>
  );
}
