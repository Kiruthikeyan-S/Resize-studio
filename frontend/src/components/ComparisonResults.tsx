import React from 'react';
import type { ComparisonRow as ComparisonRowType, RatioOutput } from '../services/api';
import { ComparisonRow } from './ComparisonRow';
import { SlidersHorizontal, Cpu, Image } from 'lucide-react';

interface ComparisonResultsProps {
  rows: ComparisonRowType[];
  preferences: Record<string, 'standard' | 'ai'>;
  onPreferenceChange: (safeKey: string, method: 'standard' | 'ai') => void;
  imageId: string;
  aiStatus?: string;
  aiProvider?: string;
  aiMessage?: string;
  onOpenPreviewModal: (item: RatioOutput) => void;
}

const RATIO_ORDER = ['square_1x1', 'portrait_4x5', 'portrait_3x4', 'landscape_16x9', 'landscape_5x4'];

export const ComparisonResults: React.FC<ComparisonResultsProps> = ({
  rows,
  preferences,
  onPreferenceChange,
  imageId,
  aiStatus,
  aiProvider,
  aiMessage,
  onOpenPreviewModal,
}) => {
  // Sort 5 rows in mandatory order
  const sortedRows = [...rows].sort((a, b) => {
    const idxA = RATIO_ORDER.indexOf(a.safe_key);
    const idxB = RATIO_ORDER.indexOf(b.safe_key);
    return (idxA !== -1 ? idxA : 99) - (idxB !== -1 ? idxB : 99);
  });

  return (
    <div className="space-y-6">
      {/* Comparison Overview Header Card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-5 h-5 text-violet-600" />
              <h3 className="font-bold text-lg text-slate-900">
                Standard Resize vs. AI Enhanced Comparison
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Compare both resizing approaches side-by-side for each aspect ratio and choose your preferred version.
            </p>
          </div>

          {/* AI Status Badge */}
          {aiStatus && (
            <div className="flex items-center gap-2 self-start md:self-auto">
              <span className="text-xs text-slate-500">AI Provider:</span>
              <span
                className={`text-xs font-semibold px-2.5 py-1 rounded-lg border ${
                  aiStatus === 'ready'
                    ? 'bg-purple-50 text-purple-700 border-purple-200'
                    : aiStatus === 'unavailable'
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : aiStatus === 'fallback'
                    ? 'bg-sky-50 text-sky-700 border-sky-200'
                    : 'bg-rose-50 text-rose-700 border-rose-200'
                }`}
              >
                {aiProvider ? `${aiProvider.toUpperCase()} (${aiStatus})` : aiStatus}
              </span>
            </div>
          )}
        </div>

        {/* Legend / Method Explanations */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-slate-200/80 flex items-center justify-center shrink-0 text-slate-700">
              <Image className="w-4 h-4" />
            </div>
            <div>
              <h5 className="font-semibold text-slate-900">Method A: Standard Resize (Without AI)</h5>
              <p className="text-slate-600 mt-0.5 leading-relaxed">
                Uses <strong>Direct Stretch (Lanczos)</strong>. 100% of your approved crop pixels are preserved without padding or secondary cropping. Changing aspect ratios may distort proportions.
              </p>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-purple-50/60 border border-purple-200/80 flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center shrink-0 text-purple-700">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <h5 className="font-semibold text-purple-900">Method B: AI Enhanced Resize (With AI)</h5>
              <p className="text-purple-800 mt-0.5 leading-relaxed">
                Maintains your product's natural proportions and outpaints matching background. Original cropped pixels are composited onto the final canvas.
              </p>
            </div>
          </div>
        </div>

        {aiStatus === 'unavailable' && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
            <strong>Notice:</strong> {aiMessage || 'AI provider is unavailable. Configure OPENAI_API_KEY or GEMINI_API_KEY in backend/.env to generate AI outpainted images. Standard resize is fully available.'}
          </div>
        )}
      </div>

      {/* 5 Vertically Stacked Comparison Rows */}
      <div className="space-y-6">
        {sortedRows.map((row) => (
          <ComparisonRow
            key={row.safe_key}
            row={row}
            preferredMethod={preferences[row.safe_key] || row.preferred_method || 'standard'}
            onPreferenceChange={(method) => onPreferenceChange(row.safe_key, method)}
            imageId={imageId}
            onOpenPreviewModal={onOpenPreviewModal}
          />
        ))}
      </div>
    </div>
  );
};
