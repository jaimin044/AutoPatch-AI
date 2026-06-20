import { useState, useEffect } from 'react';
import { BarChart3, CheckCircle2, XCircle, Clock, RotateCw } from 'lucide-react';

export function BenchmarkPanel() {
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchBenchmarks = async () => {
    setLoading(true);
    try {
      const baseUrl = import.meta.env.PROD ? '' : 'http://localhost:8000';
      const res = await fetch(`${baseUrl}/api/benchmarks`);
      if (res.ok) {
        const data = await res.json();
        setBenchmarkData(data);
      }
    } catch (err) {
      console.error('Failed to fetch benchmarks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBenchmarks();
  }, []);

  // Compute summary metrics
  const cases = benchmarkData?.cases || [];
  const totalCases = cases.length;
  const solved = cases.filter(c => c.status === 'solved' || c.status === 'success' || c.passed).length;
  const successRate = totalCases > 0 ? ((solved / totalCases) * 100).toFixed(0) : '—';
  const avgAttempts = totalCases > 0
    ? (cases.reduce((sum, c) => sum + (c.attempts || 0), 0) / totalCases).toFixed(1)
    : '—';
  const timeouts = cases.filter(c => c.status === 'timeout' || c.timed_out).length;

  return (
    <div className="glass-panel p-6 relative group overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none" />

      <div className="relative">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-medium tracking-widest text-white/50 uppercase flex items-center">
            <BarChart3 size={14} className="mr-2 text-white/80" />
            Benchmark Results
          </h3>
          <button
            onClick={fetchBenchmarks}
            disabled={loading}
            className="text-white/30 hover:text-white/60 transition-colors disabled:opacity-30"
            title="Refresh"
          >
            <RotateCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {totalCases === 0 ? (
          <p className="text-xs text-white/20 text-center py-4 uppercase tracking-widest">No benchmark data available</p>
        ) : (
          <>
            {/* Summary Metrics Grid */}
            <div className="grid grid-cols-2 gap-3 mb-5">
              <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.05]">
                <div className="text-[10px] tracking-widest uppercase text-white/30 mb-1">Cases</div>
                <div className="text-lg font-mono text-white/80">{totalCases}</div>
              </div>
              <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.05]">
                <div className="text-[10px] tracking-widest uppercase text-white/30 mb-1">Solved</div>
                <div className="text-lg font-mono text-emerald-400/80">{solved}</div>
              </div>
              <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.05]">
                <div className="text-[10px] tracking-widest uppercase text-white/30 mb-1">Success Rate</div>
                <div className="text-lg font-mono text-white/80">{successRate}%</div>
              </div>
              <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.05]">
                <div className="text-[10px] tracking-widest uppercase text-white/30 mb-1">Avg Attempts</div>
                <div className="text-lg font-mono text-white/80">{avgAttempts}</div>
              </div>
            </div>

            {/* Timeouts */}
            {timeouts > 0 && (
              <div className="flex items-center text-xs text-orange-400/60 mb-4">
                <Clock size={12} className="mr-2" />
                <span>{timeouts} timeout{timeouts > 1 ? 's' : ''}</span>
              </div>
            )}

            {/* Individual Cases */}
            <div className="space-y-2">
              {cases.map((c, i) => {
                const isSolved = c.status === 'solved' || c.status === 'success' || c.passed;
                return (
                  <div key={i} className="flex items-center justify-between bg-white/[0.02] rounded-lg px-3 py-2 border border-white/[0.05]">
                    <div className="flex items-center min-w-0">
                      {isSolved ? (
                        <CheckCircle2 size={12} className="text-emerald-400/70 mr-2 flex-shrink-0" />
                      ) : (
                        <XCircle size={12} className="text-rose-400/70 mr-2 flex-shrink-0" />
                      )}
                      <span className="font-mono text-xs text-white/60 truncate">{c.name || c.case_id || `Case ${i + 1}`}</span>
                    </div>
                    <span className="text-[10px] font-mono text-white/30 ml-2 flex-shrink-0">
                      {c.attempts || 0} att
                    </span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
