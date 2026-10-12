import React, { useRef, useState } from 'react';
import { Download, RefreshCw, Crop, CheckCircle2, AlertCircle, Loader2, Maximize2, Info } from 'lucide-react';
import type { RatioOutput } from '../services/api';
import { api } from '../services/api';

interface RatioCardProps {
  item: RatioOutput;
  imageId: string;
  onUpdate: (updated: RatioOutput) => void;
  onOpenCropEditor: (item: RatioOutput) => void;
  onOpenPreviewModal: (item: RatioOutput) => void;
  onSwitchToSafeFit?: () => void;
}

export const RatioCard: React.FC<RatioCardProps> = ({
  item,
  imageId,
  onUpdate,
  onOpenCropEditor,
  onOpenPreviewModal,
  onSwitchToSafeFit,
}) => {
  const [isReplacing, setIsReplacing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleDownload = () => {
    const url = api.getDownloadUrl(imageId, item.safe_key);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', item.file_name);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleReplaceFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setErrorMsg(null);
    setIsReplacing(true);
    try {
      const updated = await api.replaceRatio(item.safe_key, imageId, file);
      onUpdate(updated);
      setImageLoaded(false);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to replace image.');
    } finally {
      setIsReplacing(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const modeDisplayLabel = item.mode === 'safe_fit' ? 'Entire Image' : 'Full Frame';

  return (
    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden flex flex-col justify-between shadow-xs hover:shadow-md hover:border-slate-300 transition-all group">
      {/* Hidden file input for single image replacement */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleReplaceFile}
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
      />

      {/* Card Header */}
      <div className="p-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
        <div>
          <h4 className="font-semibold text-sm text-slate-900">{item.name}</h4>
          <span className="text-[11px] text-slate-500 font-medium">
            {item.width} × {item.height} px
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200">
            {item.ratio_key}
          </span>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
            {item.orientation}
          </span>
        </div>
      </div>

      {/* Image Preview Area - Large & object-fit: contain */}
      <div
        onClick={() => onOpenPreviewModal(item)}
        className="relative h-72 w-full bg-slate-100 p-3 flex items-center justify-center cursor-pointer overflow-hidden group/preview"
        title="Click to expand full preview"
      >
        {(!imageLoaded || isReplacing) && (
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

      {/* Subject boundary, trimmed edges, or automatic fallback notice */}
      {item.fallback_reason ? (
        <div className="px-3 py-1.5 bg-violet-50/80 border-t border-violet-100 flex items-center justify-between text-[11px] text-violet-900 font-medium">
          <span className="flex items-center gap-1.5 truncate" title={item.fallback_reason}>
            <Info className="w-3.5 h-3.5 shrink-0 text-violet-600" />
            <span className="truncate">{item.fallback_reason}</span>
          </span>
        </div>
      ) : item.fit_info && !item.fit_info.fits_completely && item.mode === 'smart_crop' ? (
        <div className="px-3 py-1.5 bg-amber-50 border-t border-amber-200/60 flex items-center justify-between text-[11px] text-amber-900 font-medium">
          <span className="flex items-center gap-1 truncate" title={item.fit_info.message}>
            <Info className="w-3.5 h-3.5 shrink-0 text-amber-600" />
            <span className="truncate">Subject trimmed on sides</span>
          </span>
          {onSwitchToSafeFit && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSwitchToSafeFit();
              }}
              className="text-[10px] underline text-amber-800 hover:text-amber-950 font-semibold shrink-0 ml-1.5 cursor-pointer"
            >
              Show Entire Image
            </button>
          )}
        </div>
      ) : item.edges_trimmed && item.mode === 'smart_crop' ? (
        <div className="px-3 py-1.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-700 font-medium">
          <span className="flex items-center gap-1 truncate">
            <Info className="w-3.5 h-3.5 shrink-0 text-violet-600" />
            <span>Full-frame focus active</span>
          </span>
          {onSwitchToSafeFit && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSwitchToSafeFit();
              }}
              className="text-[10px] underline text-violet-700 hover:text-violet-900 font-semibold shrink-0 ml-1 cursor-pointer"
            >
              Show Entire Image
            </button>
          )}
        </div>
      ) : null}

      {/* Card Footer */}
      <div className="p-3.5 border-t border-slate-100 bg-white space-y-3">
        {/* File Size & Processing Mode */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-600 flex items-center gap-1.5 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            {formatBytes(item.file_size)}
          </span>
          <span className="text-[11px] font-semibold text-violet-700 bg-violet-50 px-2.5 py-0.5 rounded-full border border-violet-100">
            {modeDisplayLabel}
          </span>
        </div>

        {errorMsg && (
          <div className="text-[11px] text-rose-600 flex items-center gap-1">
            <AlertCircle className="w-3 h-3 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            type="button"
            onClick={() => onOpenCropEditor(item)}
            className="py-2 px-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 border border-slate-200 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            title="Adjust crop position"
          >
            <Crop className="w-3.5 h-3.5 text-violet-600" />
            <span>Adjust Crop</span>
          </button>

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isReplacing}
            className="py-2 px-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 border border-slate-200 flex items-center justify-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
            title="Replace image for this ratio only"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-slate-600 ${isReplacing ? 'animate-spin' : ''}`} />
            <span>Replace</span>
          </button>
        </div>

        {/* Download Button */}
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
