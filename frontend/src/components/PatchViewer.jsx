import { Code2 } from 'lucide-react';

export function PatchViewer({ patchCode }) {
  if (!patchCode) return null;

  return (
    <div className="glass-panel p-6 mb-6">
      <h3 className="text-sm font-medium tracking-widest text-white/50 uppercase mb-5 flex items-center">
        <Code2 size={14} className="mr-2 text-white/80" /> 
        Proposed Solution
      </h3>
      
      <div className="inset-panel overflow-hidden">
        <pre className="p-5 text-[11px] font-mono text-white/70 overflow-x-auto leading-relaxed">
          <code>{patchCode}</code>
        </pre>
      </div>
    </div>
  );
}
