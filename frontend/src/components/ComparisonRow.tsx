import React from 'react';
import type { ComparisonRow as ComparisonRowType, RatioOutput } from '../services/api';
import { ComparisonCard } from './ComparisonCard';

interface ComparisonRowProps {
  row: ComparisonRowType;
  preferredMethod: 'standard' | 'ai';
  onPreferenceChange: (method: 'standard' | 'ai') => void;
  imageId: string;
  onOpenPreviewModal: (item: RatioOutput) => void;
}

export const ComparisonRow: React.FC<ComparisonRowProps> = ({
  row,
  preferredMethod,
  onPreferenceChange,
  imageId,
  onOpenPreviewModal,
}) => {
  const isAiAvailable = row.ai?.status === 'ready' || row.ai?.status === 'fallback';

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-6 shadow-xs space-y-4">
      {/* Ratio Header & Preferred Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center font-bold text-violet-700 text-xs shrink-0">
            {row.ratio_key}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="font-semibold text-base text-slate-900">{row.name}</h4>
              <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200">
                {row.orientation}
              </span>
            </div>
            <p className="text-xs text-slate-500 font-mono">
              Base Output: {row.width} × {row.height} px
            </p>
          </div>
        </div>

        {/* Method Preference Switcher */}
        <div className="flex flex-wrap items-center gap-1.5 bg-slate-100 p-1 rounded-xl self-start sm:self-center">
          <span className="text-[11px] font-medium text-slate-500 px-2">Preference:</span>
          <button
            type="button"
            onClick={() => onPreferenceChange('standard')}
            className={`py-1 px-3 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              preferredMethod === 'standard'
                ? 'bg-white text-violet-700 shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Standard (No AI)
          </button>
          <button
            type="button"
            onClick={() => onPreferenceChange('ai')}
            disabled={!isAiAvailable}
            className={`py-1 px-3 text-xs font-semibold rounded-lg transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
              preferredMethod === 'ai'
                ? 'bg-purple-600 text-white shadow-2xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            AI Enhanced
          </button>
        </div>
      </div>

      {/* Side-by-Side 2-Column Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 w-full min-w-0">
        <ComparisonCard
          item={{ ...row.standard, method: 'standard' }}
          method="standard"
          isPreferred={preferredMethod === 'standard'}
          onSelectPreferred={() => onPreferenceChange('standard')}
          imageId={imageId}
          onOpenPreviewModal={onOpenPreviewModal}
        />
        <ComparisonCard
          item={{ ...row.ai, method: 'ai' }}
          method="ai"
          isPreferred={preferredMethod === 'ai'}
          onSelectPreferred={() => onPreferenceChange('ai')}
          imageId={imageId}
          onOpenPreviewModal={onOpenPreviewModal}
        />
      </div>
    </div>
  );
};
