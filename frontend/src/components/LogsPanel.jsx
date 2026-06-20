import { useEffect, useRef } from 'react';
import { Terminal } from 'lucide-react';

export function LogsPanel({ logs }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="inset-panel h-full flex flex-col font-mono text-xs tracking-wide">
      <div className="bg-white/[0.03] px-5 py-4 flex items-center border-b border-white/[0.02]">
        <Terminal size={14} className="mr-3 text-white/50" />
        <h3 className="font-medium text-white/70 uppercase tracking-widest text-[10px]">Execution Stream</h3>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-5 space-y-2 bg-transparent"
      >
        {logs.length === 0 ? (
          <div className="text-white/30 italic flex items-center h-full justify-center">System standing by...</div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="text-white/60 break-words leading-relaxed">
              <span className="text-white/20 mr-3">[{new Date().toLocaleTimeString()}]</span>
              {log.includes('✓') || log.toLowerCase().includes('success') ? (
                <span className="text-emerald-400/90">{log}</span>
              ) : log.includes('✗') || log.toLowerCase().includes('fail') || log.toLowerCase().includes('error') ? (
                <span className="text-rose-400/90">{log}</span>
              ) : (
                log
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
