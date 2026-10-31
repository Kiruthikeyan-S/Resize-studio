import React, { useState, useEffect } from 'react';
import {
  X,
  RefreshCw,
  Server,
  Activity,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Cpu,
  Layers,
  HelpCircle,
} from 'lucide-react';
import { api } from '../services/api';
import type { UsageStats } from '../services/api';

interface UsageDashboardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UsageDashboardModal: React.FC<UsageDashboardModalProps> = ({ isOpen, onClose }) => {
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getUsageStats();
      setStats(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch usage metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStats();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-orange-500/10 border border-orange-200 flex items-center justify-center text-orange-600">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
                Cloudflare Workers AI Diagnostics
                <span className="text-[10px] font-semibold uppercase tracking-wider bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full">
                  Live Usage
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                Direct metrics for inpainting model <code className="text-violet-600 bg-violet-50 px-1 py-0.5 rounded">@cf/runwayml/stable-diffusion-v1-5-inpainting</code>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchStats}
              disabled={loading}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors disabled:opacity-50"
              title="Refresh statistics"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-violet-600' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-slate-700">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          {/* Primary Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3.5">
            {/* Total Cloudflare Requests */}
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center justify-between text-slate-500 text-xs font-semibold">
                <span>Cloudflare API Requests</span>
                <Server className="w-4 h-4 text-violet-600" />
              </div>
              <div className="mt-2 text-2xl font-black text-slate-900 font-mono">
                {stats?.cloudflare_requests ?? 0}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">Total remote AI calls made</div>
            </div>

            {/* Successful Requests */}
            <div className="p-4 rounded-xl bg-emerald-50/60 border border-emerald-200">
              <div className="flex items-center justify-between text-emerald-700 text-xs font-semibold">
                <span>Successful Requests</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="mt-2 text-2xl font-black text-emerald-800 font-mono">
                {stats?.successful_cloudflare_requests ?? 0}
              </div>
              <div className="text-[11px] text-emerald-600/80 mt-0.5">HTTP 200 returned image</div>
            </div>

            {/* Failed Requests */}
            <div className="p-4 rounded-xl bg-rose-50/60 border border-rose-200">
              <div className="flex items-center justify-between text-rose-700 text-xs font-semibold">
                <span>Failed Requests</span>
                <XCircle className="w-4 h-4 text-rose-600" />
              </div>
              <div className="mt-2 text-2xl font-black text-rose-800 font-mono">
                {stats?.failed_cloudflare_requests ?? 0}
              </div>
              <div className="text-[11px] text-rose-600/80 mt-0.5">Errors or timeouts</div>
            </div>

            {/* Local Fallback Count */}
            <div className="p-4 rounded-xl bg-amber-50/60 border border-amber-200">
              <div className="flex items-center justify-between text-amber-700 text-xs font-semibold">
                <span>Local Fallback Count</span>
                <Layers className="w-4 h-4 text-amber-600" />
              </div>
              <div className="mt-2 text-2xl font-black text-amber-800 font-mono">
                {stats?.local_fallback_executions ?? 0}
              </div>
              <div className="text-[11px] text-amber-600/80 mt-0.5">OpenCV fallback used</div>
            </div>

            {/* Average Response Time */}
            <div className="p-4 rounded-xl bg-sky-50/60 border border-sky-200">
              <div className="flex items-center justify-between text-sky-700 text-xs font-semibold">
                <span>Average Response Time</span>
                <Clock className="w-4 h-4 text-sky-600" />
              </div>
              <div className="mt-2 text-2xl font-black text-sky-800 font-mono">
                {stats?.average_response_time_ms ? `${stats.average_response_time_ms} ms` : '0 ms'}
              </div>
              <div className="text-[11px] text-sky-600/80 mt-0.5">Workers AI round-trip latency</div>
            </div>

            {/* Total Ratio Generations */}
            <div className="p-4 rounded-xl bg-purple-50/60 border border-purple-200">
              <div className="flex items-center justify-between text-purple-700 text-xs font-semibold">
                <span>Ratios Generated</span>
                <Activity className="w-4 h-4 text-purple-600" />
              </div>
              <div className="mt-2 text-2xl font-black text-purple-800 font-mono">
                {stats?.total_ratios_generated ?? 0}
              </div>
              <div className="text-[11px] text-purple-600/80 mt-0.5">Total aspect outputs created</div>
            </div>
          </div>

          {/* Actual Neurons Verification Section (TASK 4 & TASK 5 Requirement) */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-orange-50 via-amber-50 to-orange-50 border border-orange-200">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-orange-500 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
                <Cpu className="w-4 h-4" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-slate-900 text-sm">Actual Neurons Consumption</h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white border border-orange-200 text-orange-800 font-bold">
                    Official cf-ai-neurons Header
                  </span>
                </div>

                <div className="mt-2">
                  {stats?.actual_neurons_status?.verified_neurons_per_request !== null &&
                   stats?.actual_neurons_status?.verified_neurons_per_request !== undefined ? (
                    <div className="space-y-1">
                      <div className="text-xl font-black text-orange-900 font-mono flex items-center gap-2">
                        <span>{stats.actual_neurons_status.verified_neurons_per_request.toFixed(2)} Neurons / request</span>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                          Beta: $0.00 / step
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">
                        {stats.actual_neurons_status.message}
                      </p>
                    </div>
                  ) : (
                    <div className="text-xs font-semibold text-slate-600 py-1">
                      Actual Neurons usage is not available through the current integration.
                    </div>
                  )}
                </div>

                <div className="mt-3 pt-2.5 border-t border-orange-200/70 text-[11px] text-slate-500 flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5 text-orange-500 shrink-0" />
                  <span>
                    Why does Cloudflare Dashboard show <strong className="text-slate-700">0 / 10k Neurons</strong>? Because Cloudflare classifies <code>@cf/runwayml/stable-diffusion-v1-5-inpainting</code> as a <em>Beta model</em> with zero-rated billing (<code className="text-slate-700">$0.00</code> per step).
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Event Log */}
          <div>
            <h4 className="font-bold text-slate-900 text-xs uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-violet-600" />
              <span>Recent Cloudflare & Fallback Events</span>
            </h4>
            <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-50/50 max-h-56 overflow-y-auto">
              {stats?.recent_events && stats.recent_events.length > 0 ? (
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-600 text-[11px] uppercase font-semibold sticky top-0">
                    <tr>
                      <th className="py-2 px-3">Timestamp</th>
                      <th className="py-2 px-3">Event Type</th>
                      <th className="py-2 px-3">Ratio</th>
                      <th className="py-2 px-3">Latency</th>
                      <th className="py-2 px-3">Ray ID / Detail</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 bg-white font-mono text-[11px]">
                    {stats.recent_events.map((evt, idx) => {
                      const isSuccess = evt.type === 'CLOUDFLARE_SUCCESS';
                      const isFallback = evt.type === 'LOCAL_FALLBACK_USED';
                      const badgeClass = isSuccess
                        ? 'bg-emerald-100 text-emerald-800'
                        : isFallback
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-rose-100 text-rose-800';

                      return (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                          <td className="py-2 px-3 text-slate-500 whitespace-nowrap">
                            {evt.timestamp ? evt.timestamp.split('T')[1]?.split('.')[0] || evt.timestamp : '-'}
                          </td>
                          <td className="py-2 px-3 font-semibold">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${badgeClass}`}>
                              {evt.type}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-700">{evt.ratio || '-'}</td>
                          <td className="py-2 px-3 text-slate-700">
                            {evt.duration_ms ? `${evt.duration_ms} ms` : '-'}
                          </td>
                          <td className="py-2 px-3 text-slate-500 truncate max-w-xs" title={evt.cf_ray || evt.reason || evt.detail}>
                            {evt.cf_ray ? `Ray: ${evt.cf_ray}` : evt.reason || evt.detail || '-'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div className="p-6 text-center text-xs text-slate-400">
                  No Cloudflare calls or fallback events recorded in this session yet.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <div>
            Total uploads tracked: <strong className="text-slate-800 font-mono">{stats?.total_uploads ?? 0}</strong>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
