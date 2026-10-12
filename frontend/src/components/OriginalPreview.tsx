import React from 'react';
import { FileImage, Maximize2, HardDrive, Trash2, Crop, RotateCcw } from 'lucide-react';
import type { UploadResponse } from '../services/api';

interface OriginalPreviewProps {
  originalData: UploadResponse;
  onReset: () => void;
  onOpenEditor: () => void;
  onRevertToRaw?: () => void;
}

export const OriginalPreview: React.FC<OriginalPreviewProps> = ({
  originalData,
  onReset,
  onOpenEditor,
  onRevertToRaw,
}) => {
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="w-full bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-xs space-y-4">
      <div className="flex flex-col md:flex-row items-center gap-5">
        {/* Image thumbnail with Edit Framing overlay shortcut */}
        <div 
          onClick={onOpenEditor}
          className="group/thumb relative w-full md:w-52 h-40 bg-slate-100 rounded-xl overflow-hidden border border-slate-200 flex items-center justify-center shrink-0 cursor-pointer shadow-inner"
          title="Click to adjust original framing"
        >
          <img
            src={originalData.original_url}
            alt={originalData.original_filename}
            className="max-w-full max-h-full object-contain transition-transform duration-200 group-hover/thumb:scale-[1.03]"
          />
          <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-900/70 backdrop-blur-xs text-[11px] font-medium text-white flex items-center gap-1">
            <span>{originalData.is_cropped_master ? 'Adjusted Source' : 'Original Source'}</span>
          </div>

          <div className="absolute inset-0 bg-slate-950/30 opacity-0 group-hover/thumb:opacity-100 transition-opacity flex items-center justify-center">
            <span className="px-3 py-1.5 rounded-full bg-white text-slate-900 font-semibold text-xs flex items-center gap-1.5 shadow-md">
              <Crop className="w-3.5 h-3.5 text-violet-600" /> Adjust Framing
            </span>
          </div>
        </div>

        {/* Metadata info */}
        <div className="flex-1 w-full flex flex-col justify-center">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="font-semibold text-slate-900 text-base truncate max-w-sm" title={originalData.original_filename}>
                  {originalData.original_filename}
                </h4>
                {originalData.is_cropped_master && (
                  <span className="text-[10px] font-semibold text-violet-700 bg-violet-100 px-2 py-0.5 rounded-full border border-violet-200">
                    Framing Customized
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500">
                Adjust position and zoom before generating the 5 commercial aspect ratios.
              </p>
            </div>

            <div className="flex items-center gap-2">
              {originalData.is_cropped_master && onRevertToRaw && (
                <button
                  type="button"
                  onClick={onRevertToRaw}
                  className="flex items-center gap-1.5 text-xs text-amber-700 hover:text-amber-800 bg-amber-50 hover:bg-amber-100 px-3 py-1.5 rounded-xl border border-amber-200 transition-colors font-medium cursor-pointer"
                  title="Revert to original uncropped upload"
                >
                  <RotateCcw className="w-3.5 h-3.5 text-amber-600" />
                  <span>Revert Framing</span>
                </button>
              )}

              <button
                type="button"
                onClick={onOpenEditor}
                className="flex items-center gap-1.5 text-xs text-white bg-violet-600 hover:bg-violet-700 px-3.5 py-1.5 rounded-xl shadow-xs transition-colors font-semibold cursor-pointer active:scale-[0.99]"
              >
                <Crop className="w-3.5 h-3.5" />
                <span>Adjust Framing</span>
              </button>

              <button
                type="button"
                onClick={onReset}
                className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-xl border border-slate-200 transition-colors font-medium cursor-pointer"
                title="Change image and upload a new one"
              >
                <Trash2 className="w-3.5 h-3.5 text-slate-500" />
                <span>Change Image</span>
              </button>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-2.5 text-xs">
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80 flex flex-col">
              <span className="text-slate-500 flex items-center gap-1 mb-1 font-medium">
                <Maximize2 className="w-3.5 h-3.5 text-violet-600" /> Resolution
              </span>
              <span className="font-semibold text-slate-900">
                {originalData.width} × {originalData.height} px
              </span>
            </div>

            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80 flex flex-col">
              <span className="text-slate-500 flex items-center gap-1 mb-1 font-medium">
                <HardDrive className="w-3.5 h-3.5 text-violet-600" /> File Size
              </span>
              <span className="font-semibold text-slate-900">
                {formatBytes(originalData.file_size)}
              </span>
            </div>

            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/80 flex flex-col">
              <span className="text-slate-500 flex items-center gap-1 mb-1 font-medium">
                <FileImage className="w-3.5 h-3.5 text-violet-600" /> Format
              </span>
              <span className="font-semibold text-slate-900">
                {originalData.format}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
