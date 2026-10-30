import React from 'react';
import { Coins, Zap, PieChart, ShieldCheck } from 'lucide-react';
import { useTokenTracker, INITIAL_TOKEN_QUOTA } from '../services/tokenTracker';
import type { TokenUsage } from '../services/api';

interface TokenConsumptionCardProps {
  tokenUsage?: TokenUsage | null;
  className?: string;
}

export const TokenConsumptionCard: React.FC<TokenConsumptionCardProps> = ({
  tokenUsage,
  className = '',
}) => {
  const { remaining, totalUsed, lastDeducted } = useTokenTracker();

  // If tokenUsage is provided from the current generation, use it; otherwise fallback to lastDeducted
  const currentUsed = tokenUsage?.total_tokens || lastDeducted || 0;
  const promptTokens = tokenUsage?.prompt_tokens || Math.round(currentUsed * 0.88);
  const completionTokens = tokenUsage?.completion_tokens || (currentUsed - promptTokens);

  // Guarantee remainder reflects deduction even before custom event completes
  const displayTotalUsed = Math.max(totalUsed, currentUsed);
  const displayRemaining = Math.max(0, Math.min(remaining, INITIAL_TOKEN_QUOTA - displayTotalUsed));
  const displayPercent = Math.max(0, Math.min(100, (displayRemaining / INITIAL_TOKEN_QUOTA) * 100));

  return (
    <div className={`p-4 rounded-2xl bg-gradient-to-r from-amber-50/90 via-orange-50/40 to-violet-50/60 border border-amber-200/80 shadow-xs mb-6 ${className}`}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Left: Icon & Description */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-300/80 flex items-center justify-center shrink-0 shadow-2xs">
            <Coins className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                AI Token Consumption & Balance
              </h4>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100/90 text-amber-800 font-bold border border-amber-200/70">
                Groq Vision
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Live token deduction for this image conversion session
            </p>
          </div>
        </div>

        {/* Right: 3 Key Metrics Pills (Reduced, Remainder, Total Used) */}
        <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
          {/* Tokens Reduced */}
          <div className="px-3.5 py-2 rounded-xl bg-white/95 border border-rose-200 shadow-2xs">
            <div className="flex items-center gap-1.5 text-rose-500 text-[10px] uppercase font-bold tracking-wider">
              <Zap className="w-3 h-3 text-rose-500" />
              <span>Tokens Reduced</span>
            </div>
            <div className="text-sm font-extrabold text-rose-600 font-mono mt-0.5">
              {currentUsed > 0 ? `-${currentUsed.toLocaleString()}` : '0'}
              <span className="text-[10px] font-normal text-rose-400 ml-1">tokens</span>
            </div>
          </div>

          {/* Tokens Remainder */}
          <div className="px-3.5 py-2 rounded-xl bg-white/95 border border-emerald-200 shadow-2xs">
            <div className="flex items-center gap-1.5 text-emerald-600 text-[10px] uppercase font-bold tracking-wider">
              <ShieldCheck className="w-3 h-3 text-emerald-600" />
              <span>Tokens Remainder</span>
            </div>
            <div className="text-sm font-extrabold text-emerald-700 font-mono mt-0.5 flex items-center gap-1">
              <span>{displayRemaining.toLocaleString()}</span>
              <span className="text-[10px] font-semibold text-emerald-500 bg-emerald-50 px-1.5 py-0.2 rounded-md border border-emerald-100">
                {displayPercent.toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Total Cumulative Used */}
          <div className="px-3.5 py-2 rounded-xl bg-white/95 border border-slate-200 shadow-2xs hidden sm:block">
            <div className="flex items-center gap-1.5 text-slate-400 text-[10px] uppercase font-bold tracking-wider">
              <PieChart className="w-3 h-3 text-slate-400" />
              <span>Total Used</span>
            </div>
            <div className="text-sm font-bold text-slate-800 font-mono mt-0.5">
              {displayTotalUsed.toLocaleString()}
              <span className="text-[10px] font-normal text-slate-400 ml-1">/ {INITIAL_TOKEN_QUOTA.toLocaleString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar & Sub-details */}
      <div className="mt-3.5 pt-3 border-t border-amber-200/50 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-slate-500">
        <div className="flex items-center gap-3 text-[11px]">
          <span>
            Input Prompt: <strong className="text-slate-700 font-mono">{promptTokens.toLocaleString()}</strong>
          </span>
          <span>•</span>
          <span>
            Output Response: <strong className="text-slate-700 font-mono">{completionTokens.toLocaleString()}</strong>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-500">Remainder Quota:</span>
          <div className="w-32 bg-amber-200/60 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-emerald-500 h-full rounded-full transition-all duration-500"
              style={{ width: `${displayPercent}%` }}
            />
          </div>
          <span className="text-[11px] font-mono font-semibold text-slate-700">
            {remaining.toLocaleString()} left
          </span>
        </div>
      </div>
    </div>
  );
};

export default TokenConsumptionCard;
