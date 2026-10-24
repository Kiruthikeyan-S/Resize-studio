import React, { useState } from 'react';
import { Download, Loader2, Maximize2, Check, AlertCircle, Info } from 'lucide-react';
import type { RatioOutput, SizeKey } from '../services/api';
import { api, RATIO_SIZE_TABLE } from '../services/api';

interface ComparisonCardProps {
  item: RatioOutput;
  method: 'standard' | 'ai';
  isPreferred: boolean;
  onSelectPreferred: () => void;
  imageId: string;
  onOpenPreviewModal: (item: RatioOutput) => void;
}

const SIZE_LABELS: Record<SizeKey, string> = {
  large: 'Large',
  medium: 'Medium',
  small: 'Small',
};

export const ComparisonCard: React.FC<ComparisonCardProps> = ({
  item,
  method,
  isPreferred,
  onSelectPreferred,
  imageId,
  onOpenPreviewModal,
}) => {
  const [selectedSize, setSelectedSize] = useState<SizeKey>('large');
  const [imageLoaded, setImageLoaded] = useState<boolean>(false);

  const activeVariant = item.variants?.find((v) => v.size_key === selectedSize);
  const tableEntry = RATIO_SIZE_TABLE.find((r) => r.safe_key === item.safe_key);

  const activeWidth =
    activeVariant?.width ?? (tableEntry?.sizes[selectedSize]?.[0] ?? item.width);
  const activeHeight =
    activeVariant?.height ?? (tableEntry?.sizes[selectedSize]?.[1] ?? item.height);

  const isAI = method === 'ai';
  const status = item.status || 'ready';
  const isAvailable = status === 'ready' || status === 'fallback';

  const handleDownload = () => {
    if (!isAvailable) return;
    const url = api.getDownloadUrl(imageId, item.safe_key, undefined, selectedSize, method);
    const link = document.createElement('a');
    link.href = url;
    const downloadName =
      activeVariant?.file_name || `${method}_${item.safe_key}_${selectedSize}.jpg`;
    link.setAttribute('download', downloadName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleSizeChange = (sKey: SizeKey) => {
    if (sKey !== selectedSize) {
      setImageLoaded(false);
      setSelectedSize(sKey);
    }
  };

  const previewSrc = isAvailable
    ? api.getPreviewUrl(imageId, item.safe_key, item.version, undefined, selectedSize, method)
    : '';

  return (
    <div
      className={`rounded-2xl border transition-all flex flex-col justify-between h-full overflow-hidden ${
        isPreferred
          ? 'bg-white border-violet-400 ring-2 ring-violet-200 shadow-md'
          : 'bg-white border-slate-200 shadow-xs hover:border-slate-300'
      }`}
    >
      {/* Header */}
      <div className={`p-4 border-b flex items-start justify-between gap-3 ${
        isAI ? 'bg-purple-50/50 border-purple-100' : 'bg-slate-50/70 border-slate-100'
      }`}>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-md ${
                isAI
                  ? 'bg-purple-100 text-purple-700 border border-purple-200'
                  : 'bg-slate-200/80 text-slate-700 border border-slate-300'
              }`}
            >
              {isAI ? 'Method B: AI Enhanced' : 'Method A: Standard'}
            </span>

            {isAI && status === 'unavailable' && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 border border-amber-200 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                <span>AI Unavailable</span>
              </span>
            )}
            {isAI && status === 'failed' && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-rose-100 text-rose-800 border border-rose-200 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                <span>Failed</span>
              </span>
            )}
            {isAI && status === 'fallback' && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 border border-amber-200">
                Standard/OpenCV Fallback — Not AI Enhanced
              </span>
            )}
            {isAI && status === 'ready' && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                <Check className="w-3 h-3" />
                <span>AI Enhanced</span>
              </span>
            )}
          </div>

          <p className="text-xs text-slate-500">
            {isAI
              ? (item.is_generative_ai
                  ? 'Maintains natural proportions; genuine generative AI outpainted background.'
                  : 'Standard/OpenCV fallback — non-AI canvas extension. Configure OPENAI_API_KEY in backend/.env for genuine AI outpainting.')
              : item.mode === 'safe_fit'
              ? 'Safe Fit (contain). 100% original content preserved without distortion.'
              : item.mode === 'smart_crop'
              ? 'Smart Cover (crop). Fills canvas with subject-centered crop.'
              : 'Direct stretch (Lanczos). Preserves 100% of approved pixels.'}
          </p>
        </div>

        {/* Preferred Selector Toggle Button */}
        <button
          type="button"
          onClick={onSelectPreferred}
          disabled={!isAvailable}
          className={`shrink-0 py-1.5 px-3 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
            isPreferred
              ? 'bg-violet-600 text-white shadow-xs'
              : 'bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 hover:border-slate-300 disabled:opacity-40 disabled:cursor-not-allowed'
          }`}
          title={isPreferred ? 'This version is currently preferred' : 'Mark this version as preferred'}
        >
          {isPreferred ? (
            <>
              <Check className="w-3.5 h-3.5" />
              <span>Preferred</span>
            </>
          ) : (
            <span>Use This</span>
          )}
        </button>
      </div>

      {/* Resolution & Details bar */}
      <div className="px-4 py-2 bg-slate-50/50 border-b border-slate-100 flex items-center justify-between text-xs font-mono">
        <span className="text-slate-500 text-[11px] font-sans">Output Resolution:</span>
        <span className="font-bold text-violet-700">
          {activeWidth} × {activeHeight} px
        </span>
      </div>

      {/* Fallback configuration guidance */}
      {isAI && status === 'fallback' && (
        <div className="px-4 py-2 bg-amber-50/80 border-b border-amber-200/60 flex items-start gap-2 text-[11px] text-amber-900 leading-tight">
          <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">{item.error_message || 'Computer-vision photographic fallback used.'}</div>
            <div className="text-[10px] text-amber-700 mt-0.5">
              To enable genuine generative AI outpainting, configure a funded <code className="bg-amber-100/80 px-1 py-0.2 rounded font-mono">OPENAI_API_KEY</code>, <code className="bg-amber-100/80 px-1 py-0.2 rounded font-mono">STABILITY_API_KEY</code>, or <code className="bg-amber-100/80 px-1 py-0.2 rounded font-mono">HF_TOKEN</code> in <code className="bg-amber-100/80 px-1 py-0.2 rounded font-mono">backend/.env</code>.
            </div>
          </div>
        </div>
      )}

      {/* Preview Area or Unavailable State */}
      <div className="relative min-h-[260px] h-[280px] w-full bg-slate-100/70 p-4 flex items-center justify-center overflow-hidden select-none">
        {isAvailable ? (
          <>
            {!imageLoaded && (
              <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10 backdrop-blur-xs">
                <Loader2 className="w-6 h-6 text-violet-600 animate-spin" />
              </div>
            )}

            <div
              onClick={() => onOpenPreviewModal(item)}
              className="relative max-h-full max-w-full flex items-center justify-center cursor-pointer group/preview"
              title="Click to expand high-resolution inspection preview"
            >
              <img
                key={previewSrc}
                src={previewSrc}
                alt={`${item.name} (${method})`}
                onLoad={() => setImageLoaded(true)}
                className="max-h-[248px] max-w-full object-contain mx-auto rounded-lg shadow-xs transition-transform duration-200 group-hover/preview:scale-[1.02]"
              />

              <div className="absolute inset-0 bg-slate-900/25 opacity-0 group-hover/preview:opacity-100 transition-opacity rounded-lg flex items-center justify-center pointer-events-none">
                <div className="px-3 py-1.5 rounded-full bg-white text-slate-900 font-medium text-xs flex items-center gap-1.5 shadow-md border border-slate-200">
                  <Maximize2 className="w-3.5 h-3.5 text-violet-600" />
                  <span>Click to Expand</span>
                </div>
              </div>
            </div>
          </>
        ) : (
          /* Informative AI Unavailable / Failed Card */
          <div className="p-6 text-center space-y-3 max-w-sm mx-auto">
            <div className="w-12 h-12 mx-auto rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-200">
              <Info className="w-6 h-6" />
            </div>
            <div>
              <h5 className="font-semibold text-sm text-slate-800">
                {status === 'failed' ? 'AI Outpainting Failed' : 'AI Outpainting Unavailable'}
              </h5>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                {item.error_message ||
                  'Configure OPENAI_API_KEY in backend/.env to enable genuine AI background expansion (DALL-E 2 Inpainting).'}
              </p>
            </div>
            <div className="pt-1">
              <span className="text-[11px] font-medium text-slate-600 bg-white px-3 py-1 rounded-full border border-slate-200">
                Standard Resize is ready for download
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Footer: Size Selector & Download */}
      <div className="p-4 border-t border-slate-100 bg-white space-y-3">
        {/* Size Selector */}
        <div className="grid grid-cols-3 gap-1 bg-slate-100 p-1 rounded-xl">
          {(['large', 'medium', 'small'] as const).map((sKey) => {
            const isSelected = selectedSize === sKey;
            return (
              <button
                key={sKey}
                type="button"
                disabled={!isAvailable}
                onClick={() => handleSizeChange(sKey)}
                className={`py-1 text-[11px] font-semibold rounded-lg transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                  isSelected
                    ? 'bg-white text-violet-700 shadow-2xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {SIZE_LABELS[sKey]}
              </button>
            );
          })}
        </div>

        {/* Download Button */}
        <button
          type="button"
          onClick={handleDownload}
          disabled={!isAvailable}
          className={`w-full py-2.5 px-3 rounded-xl text-xs font-semibold shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
            isAI
              ? 'bg-purple-600 hover:bg-purple-700 text-white'
              : 'bg-violet-600 hover:bg-violet-700 text-white'
          }`}
        >
          <Download className="w-3.5 h-3.5" />
          <span>
            Download {isAI ? 'AI' : 'Standard'} ({SIZE_LABELS[selectedSize]})
          </span>
        </button>
      </div>
    </div>
  );
};
