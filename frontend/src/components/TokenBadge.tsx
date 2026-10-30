import React, { useState } from 'react';
import { Coins, Zap, RefreshCw, ChevronDown, CheckCircle2, Info } from 'lucide-react';
import { useTokenTracker, INITIAL_TOKEN_QUOTA } from '../services/tokenTracker';

interface TokenBadgeProps {
  className?: string;
}

export const TokenBadge: React.FC<TokenBadgeProps> = ({ className = '' }) => {
  const { remaining, totalUsed, lastDeducted, percentRemaining, reset } = useTokenTracker();
  const [showDropdown, setShowDropdown] = useState(false);
  const [showResetNotice, setShowResetNotice] = useState(false);

  const handleReset = (e: React.MouseEvent) => {
    e.stopPropagation();
    reset();
    setShowResetNotice(true);
    setTimeout(() => setShowResetNotice(false), 2500);
  };

  const isLow = remaining < 10_000;
  const isOut = remaining === 0;

  const badgeColor = isOut
    ? 'bg-rose-50 border-rose-200 text-rose-700'
    : isLow
    ? 'bg-amber-50 border-amber-200 text-amber-700'
    : 'bg-emerald-50 border-emerald-200 text-emerald-800';

  const barColor = isOut
    ? 'bg-rose-500'
    : isLow
    ? 'bg-amber-500'
    : 'bg-emerald-500';

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setShowDropdown(!showDropdown)}
        className={`px-3 py-1.5 rounded-xl border flex items-center gap-2 text-xs font-semibold shadow-2xs hover:shadow-xs transition-all cursor-pointer ${badgeColor}`}
        title="View Token Balance & Usage"
      >
        <Coins className="w-3.5 h-3.5 text-amber-500 shrink-0" />
        <div className="flex items-center gap-1.5">
          <span>{remaining.toLocaleString()}</span>
          <span className="text-[10px] opacity-75 font-normal">Tokens</span>
        </div>

        {lastDeducted > 0 && (
          <span className="px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 text-[10px] font-bold flex items-center gap-0.5 animate-pulse">
            <Zap className="w-2.5 h-2.5" />
            -{lastDeducted.toLocaleString()}
          </span>
        )}

        <ChevronDown className="w-3 h-3 opacity-60 ml-0.5" />
      </button>

      {/* Dropdown details card */}
      {showDropdown && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowDropdown(false)}
          />
          <div className="absolute right-0 mt-2 w-72 p-4 bg-white border border-slate-200 rounded-2xl shadow-xl z-50 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-100">
              <div className="flex items-center gap-1.5 font-bold text-slate-800 text-xs">
                <Coins className="w-4 h-4 text-amber-500" />
                <span>AI Token Quota</span>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-semibold">
                {percentRemaining.toFixed(1)}% Left
              </span>
            </div>

            {/* Visual Progress Bar */}
            <div className="mt-3">
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 rounded-full ${barColor}`}
                  style={{ width: `${percentRemaining}%` }}
                />
              </div>
            </div>

            {/* Token Stats Breakdown */}
            <div className="mt-3.5 space-y-2 text-xs">
              <div className="flex items-center justify-between text-slate-600">
                <span className="flex items-center gap-1 text-[11px]">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  Remaining Balance:
                </span>
                <span className="font-bold text-slate-900 font-mono">
                  {remaining.toLocaleString()}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-600">
                <span className="flex items-center gap-1 text-[11px]">
                  <Zap className="w-3.5 h-3.5 text-violet-500" />
                  Last Generation Used:
                </span>
                <span className="font-semibold text-violet-700 font-mono">
                  {lastDeducted > 0 ? `-${lastDeducted.toLocaleString()}` : '0'}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-600">
                <span className="flex items-center gap-1 text-[11px]">
                  <Info className="w-3.5 h-3.5 text-slate-400" />
                  Total Tokens Used:
                </span>
                <span className="font-semibold text-slate-700 font-mono">
                  {totalUsed.toLocaleString()}
                </span>
              </div>

              <div className="flex items-center justify-between text-slate-400 text-[10px] pt-1 border-t border-slate-100">
                <span>Initial Daily Allotment:</span>
                <span className="font-mono">{INITIAL_TOKEN_QUOTA.toLocaleString()}</span>
              </div>
            </div>

            {/* Reset / Refill Button */}
            <div className="mt-4 pt-2.5 border-t border-slate-100 flex items-center justify-between">
              {showResetNotice ? (
                <span className="text-[11px] text-emerald-600 font-medium">
                  Refilled to 100,000 tokens!
                </span>
              ) : (
                <span className="text-[10px] text-slate-400">Free daily refill</span>
              )}
              <button
                type="button"
                onClick={handleReset}
                className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-violet-50 hover:text-violet-700 text-slate-600 text-[11px] font-semibold flex items-center gap-1 transition-all cursor-pointer"
                title="Reset balance to 100,000"
              >
                <RefreshCw className="w-3 h-3" />
                <span>Refill</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default TokenBadge;
