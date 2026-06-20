import { FileSearch, FileCode } from 'lucide-react';

export function ContextPanel({ files }) {
  if (!files || files.length === 0) {
    return null;
  }
  
  return (
    <div className="glass-panel p-6">
      <h3 className="text-sm font-medium tracking-widest text-white/50 uppercase mb-5 flex items-center">
        <FileSearch size={14} className="mr-2 text-white/80" /> 
        Retrieved Context ({files.length})
      </h3>
      
      <div className="space-y-2">
        {files.map((file, i) => {
          // Handle both string arrays and object arrays
          const isObject = typeof file === 'object' && file !== null;
          const path = isObject ? (file.path || file.file_path || '') : file;
          const score = isObject ? file.score : null;
          const reason = isObject ? file.reason : null;

          return (
            <div key={i} className="bg-white/[0.02] hover:bg-white/[0.04] transition-colors rounded-lg px-4 py-3 border border-white/[0.05]">
              <div className="flex items-center justify-between">
                <div className="flex items-center min-w-0">
                  <FileCode size={14} className="mr-3 text-white/40 flex-shrink-0" />
                  <span className="font-mono text-white/70 text-sm tracking-wide truncate">{path}</span>
                </div>
                {score !== null && score !== undefined && (
                  <span className="text-[10px] font-mono text-white/30 ml-3 flex-shrink-0">
                    score: {typeof score === 'number' ? score.toFixed(2) : score}
                  </span>
                )}
              </div>
              {reason && (
                <p className="text-[11px] text-white/30 mt-1.5 pl-7 leading-relaxed">{reason}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
