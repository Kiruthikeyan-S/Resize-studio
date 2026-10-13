import React, { useState } from 'react';
import { Download, Loader2, Maximize2 } from 'lucide-react';
import type { RatioOutput, SizeKey } from '../services/api';
import { api, RATIO_SIZE_TABLE } from '../services/api';

interface RatioCardProps {
  item: RatioOutput;
  imageId: string;
  onUpdate?: (updated: RatioOutput) => void;
  onOpenCropEditor?: (item: RatioOutput) => void;
  onOpenPreviewModal: (item: RatioOutput) => void;
}

export const RatioCard: React.FC<RatioCardProps> = ({
  item,
  imageId,
  onOpenPreviewModal,
}) => {
  const [selectedSize, setSelectedSize] = useState<SizeKey>('large');
  const [imageLoaded, setImageLoaded] = useState(false);

  // Find active variant or resolve from ratio size table
  const activeVariant = item.variants?.find((v) => v.size_key === selectedSize);
  const tableEntry = RATIO_SIZE_TABLE.find((r) => r.safe_key === item.safe_key);

  const activeWidth =
    activeVariant?.width ??
    (tableEntry?.sizes[selectedSize]?.[0] ?? item.width);
  const activeHeight =
    activeVariant?.height ??
    (tableEntry?.sizes[selectedSize]?.[1] ?? item.height);

  const handleDownload = () => {
    const url = api.getDownloadUrl(imageId, item.safe_key, item.mode, selectedSize);
    const link = document.createElement('a');
    link.href = url;
    const downloadName = activeVariant?.file_name || `image_${item.safe_key}_${selectedSize}.jpg`;
    link.setAttribute('download', downloadName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const sizeLabels: Record<SizeKey, string> = {
    large: 'Large',
    medium: 'Medium',
    small: 'Small',
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden flex flex-col justify-between shadow-xs hover:shadow-md hover:border-slate-300 transition-all group h-full">
      {/* Card Header: Ratio Name & Orientation / Badge */}
      <div className="p-3.5 border-b border-slate-100 bg-slate-50/70">
        <div className="flex items-center justify-between gap-1 mb-1">
          <h4 className="font-semibold text-sm text-slate-900 truncate" title={item.name}>
            {item.name}
          </h4>
          <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-md bg-violet-100 text-violet-700 border border-violet-200 shrink-0">
            {item.safe_key.replace('_', ' ').replace('square ', '').replace('portrait ', '').replace('landscape ', '')}
          </span>
        </div>

        {/* Exact Selected Output Resolution */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-slate-500 text-[11px] font-sans">Resolution:</span>
          <span className="font-bold text-violet-700">
            {activeWidth} × {activeHeight} px
          </span>
        </div>
      </div>

      {/* Image Preview Area - Centered without stretching */}
      <div
        onClick={() => onOpenPreviewModal(item)}
        className="relative h-60 w-full bg-slate-100 p-3 flex items-center justify-center cursor-pointer overflow-hidden group/preview select-none"
        title="Click to expand full inspection preview"
      >
        {!imageLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10 backdrop-blur-xs">
            <Loader2 className="w-6 h-6 text-violet-600 animate-spin" />
          </div>
        )}

        <img
          src={item.preview_url}
          alt={item.name}
          onLoad={() => setImageLoaded(true)}
          className="max-h-full max-w-full object-contain mx-auto my-auto rounded-lg shadow-sm transition-transform duration-200 group-hover/preview:scale-[1.02]"
        />

        {/* Hover zoom indicator */}
        <div className="absolute inset-0 bg-slate-900/20 opacity-0 group-hover/preview:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
          <div className="px-3 py-1.5 rounded-full bg-white text-slate-900 font-medium text-xs flex items-center gap-1.5 shadow-md border border-slate-200">
            <Maximize2 className="w-3.5 h-3.5 text-violet-600" />
            <span>Click to Expand</span>
          </div>
        </div>
      </div>

      {/* Card Footer: Size Selector & Download Button */}
      <div className="p-3.5 border-t border-slate-100 bg-white space-y-3">
        {/* Large / Medium / Small Size Selector */}
        <div>
          <div className="grid grid-cols-3 gap-1 bg-slate-100 p-1 rounded-xl">
            {(['large', 'medium', 'small'] as const).map((sKey) => {
              const isSelected = selectedSize === sKey;
              return (
                <button
                  key={sKey}
                  type="button"
                  onClick={() => setSelectedSize(sKey)}
                  className={`py-1 text-[11px] font-semibold rounded-lg transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-white text-violet-700 shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {sizeLabels[sKey]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Download Button */}
        <button
          type="button"
          onClick={handleDownload}
          className="w-full py-2.5 px-3 rounded-xl bg-violet-600 hover:bg-violet-700 active:scale-[0.99] text-xs font-semibold text-white shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Download {sizeLabels[selectedSize]}</span>
        </button>
      </div>
    </div>
  );
};

export default RatioCard;
