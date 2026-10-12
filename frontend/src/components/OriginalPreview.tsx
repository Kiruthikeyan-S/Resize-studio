import React from 'react';
import { FileImage, Maximize2, HardDrive, Trash2 } from 'lucide-react';
import type { UploadResponse } from '../services/api';

interface OriginalPreviewProps {
  originalData: UploadResponse;
  onReset: () => void;
}

export const OriginalPreview: React.FC<OriginalPreviewProps> = ({
  originalData,
  onReset,
}) => {
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="w-full bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-xs">
      <div className="flex flex-col md:flex-row items-center gap-5">
        {/* Image thumbnail */}
        <div className="relative w-full md:w-48 h-36 bg-slate-100 rounded-xl overflow-hidden border border-slate-200 flex items-center justify-center shrink-0">
          <img
            src={originalData.original_url}
            alt={originalData.original_filename}
            className="max-w-full max-h-full object-contain"
          />
          <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-900/70 backdrop-blur-xs text-[11px] font-medium text-white">
            Source
          </div>
        </div>

        {/* Metadata info */}
        <div className="flex-1 w-full flex flex-col justify-center">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h4 className="font-semibold text-slate-900 text-base truncate max-w-md" title={originalData.original_filename}>
              {originalData.original_filename}
            </h4>
            <button
              onClick={onReset}
              className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-lg border border-slate-200 transition-colors font-medium"
              title="Change image and upload a new one"
            >
              <Trash2 className="w-3.5 h-3.5 text-slate-500" />
              <span>Change Image</span>
            </button>
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
