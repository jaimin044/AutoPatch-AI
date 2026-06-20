import { useState } from 'react';
import { Play } from 'lucide-react';
import { MagneticElement } from './MagneticElement';

export function JobForm({ onSubmit, disabled }) {
  const [repoUrl, setRepoUrl] = useState('../benchmarks/repos/case_01_divide_by_zero');
  const [issueText, setIssueText] = useState('The divide function crashes with ZeroDivisionError when dividing by zero instead of raising a ValueError with a helpful message.');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (repoUrl.trim() && issueText.trim()) {
      onSubmit(repoUrl, issueText);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="glass-panel p-8 space-y-6 relative group overflow-hidden">
      {/* Subtle hover gradient for the panel */}
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.03] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />
      
      <div className="relative">
        <h2 className="text-sm font-medium tracking-widest text-white/50 uppercase mb-6 flex items-center">
          <Play size={14} className="mr-2 text-white/80" /> Agent Configuration
        </h2>
        
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-white/40 mb-2 uppercase tracking-wider">Repository Target</label>
            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              disabled={disabled}
              className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-gray-200 text-sm focus:outline-none focus:border-white/30 focus:bg-black/60 disabled:opacity-50 transition-all placeholder-white/20"
              placeholder="https://github.com/org/repo"
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-white/40 mb-2 uppercase tracking-wider">Issue Description</label>
            <textarea
              value={issueText}
              onChange={(e) => setIssueText(e.target.value)}
              disabled={disabled}
              rows={4}
              className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-gray-200 text-sm focus:outline-none focus:border-white/30 focus:bg-black/60 disabled:opacity-50 resize-none transition-all placeholder-white/20"
              placeholder="Describe the bug..."
            />
          </div>
        </div>
        
        <div className="mt-8">
          <MagneticElement strength={0.1}>
            <button
              type="submit"
              disabled={disabled || !repoUrl.trim() || !issueText.trim()}
              className="w-full bg-white text-black hover:bg-gray-200 font-medium py-3 px-4 rounded-xl transition-all duration-300 disabled:opacity-30 disabled:cursor-not-allowed flex justify-center items-center group shadow-[0_0_40px_rgba(255,255,255,0.1)] hover:shadow-[0_0_60px_rgba(255,255,255,0.2)]"
            >
              Deploy Agent
            </button>
          </MagneticElement>
        </div>
      </div>
    </form>
  );
}
