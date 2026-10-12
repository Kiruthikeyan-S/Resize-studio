import React from 'react';
import type { RatioOutput } from '../services/api';
import { RatioCard } from './RatioCard';
import { Layers } from 'lucide-react';

interface PreviewGridProps {
  outputs: RatioOutput[];
  imageId: string;
  onUpdateRatio: (updated: RatioOutput) => void;
  onOpenCropEditor: (item: RatioOutput) => void;
  onOpenPreviewModal: (item: RatioOutput) => void;
  onSwitchToSafeFit?: () => void;
}

export const PreviewGrid: React.FC<PreviewGridProps> = ({
  outputs,
  imageId,
  onUpdateRatio,
  onOpenCropEditor,
  onOpenPreviewModal,
  onSwitchToSafeFit,
}) => {
  if (outputs.length === 0) return null;

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-violet-600" />
          <h3 className="font-semibold text-base text-slate-900">Generated Ratio Previews</h3>
          <span className="text-xs font-mono text-slate-600 bg-white px-2.5 py-0.5 rounded-full border border-slate-200 shadow-xs">
            {outputs.length} outputs
          </span>
        </div>
        <p className="text-xs text-slate-500 hidden sm:block">
          Proportional aspect framing • Click any preview to inspect high-resolution output
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {outputs.map((item) => (
          <RatioCard
            key={item.safe_key}
            item={item}
            imageId={imageId}
            onUpdate={onUpdateRatio}
            onOpenCropEditor={onOpenCropEditor}
            onOpenPreviewModal={onOpenPreviewModal}
            onSwitchToSafeFit={onSwitchToSafeFit}
          />
        ))}
      </div>
    </div>
  );
};
