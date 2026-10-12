import React, { useState } from 'react';
import { Download, Loader2, Maximize2 } from 'lucide-react';
import type { RatioOutput } from '../services/api';
import { api } from '../services/api';

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
  const [imageLoaded, setImageLoaded] = useState(false);

  const handleDownload = () => {
    const url = api.getDownloadUrl(imageId, item.safe_key, item.mode);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', item.file_name);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden flex flex-col justify-between shadow-xs hover:shadow-md hover:border-slate-300 transition-all group">
      {/* Card Header */}
      <div className="p-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
        <div>
          <h4 className="font-semibold text-sm text-slate-900">{item.name}</h4>
          <span className="text-[11px] text-slate-500 font-medium">
            {item.width} × {item.height} px
          </span>
        </div>
      </div>

      {/* Image Preview Area - Large & object-fit: contain */}
      <div
        onClick={() => onOpenPreviewModal(item)}
        className="relative h-72 w-full bg-slate-100 p-3 flex items-center justify-center cursor-pointer overflow-hidden group/preview"
        title="Click to expand full preview"
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
          <div className="px-3.5 py-1.5 rounded-full bg-white text-slate-900 font-medium text-xs flex items-center gap-1.5 shadow-md border border-slate-200">
            <Maximize2 className="w-3.5 h-3.5 text-violet-600" />
            <span>Click to Expand</span>
          </div>
        </div>
      </div>

      {/* Card Footer - Only Download Button */}
      <div className="p-3.5 border-t border-slate-100 bg-white">
        <button
          type="button"
          onClick={handleDownload}
          className="w-full py-2.5 px-3 rounded-xl bg-violet-600 hover:bg-violet-700 active:scale-[0.99] text-xs font-semibold text-white shadow-xs flex items-center justify-center gap-2 transition-all cursor-pointer"
        >
          <Download className="w-3.5 h-3.5" />
          <span>Download {item.name}</span>
        </button>
      </div>
    </div>
  );
};

export default RatioCard;
