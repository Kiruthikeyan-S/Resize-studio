import React from 'react';
import { X, Download, Maximize2 } from 'lucide-react';
import type { RatioOutput } from '../services/api';
import { api } from '../services/api';

interface PreviewModalProps {
  item: RatioOutput | null;
  imageId: string;
  onClose: () => void;
}

export const PreviewModal: React.FC<PreviewModalProps> = ({
  item,
  imageId,
  onClose,
}) => {
  if (!item) return null;

  const handleDownload = () => {
    const url = api.getDownloadUrl(imageId, item.safe_key, item.mode);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', item.file_name);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/60 backdrop-blur-md animate-fade-in">
      <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2.5">
            <Maximize2 className="w-4 h-4 text-violet-600" />
            <div>
              <h3 className="font-semibold text-sm text-slate-900 flex items-center gap-2">
                <span>{item.name}</span>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-violet-100 text-violet-700 border border-violet-200 font-semibold">
                  {item.ratio_key}
                </span>
              </h3>
              <p className="text-[11px] text-slate-500 font-mono">
                {item.width} × {item.height} px • {formatBytes(item.file_size)} • {item.mode === 'smart_crop' ? 'Full-Frame Photo' : 'Entire Image Visible'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* High-Res Full Resolution Image Preview Box */}
        <div className="p-4 sm:p-6 bg-slate-100 flex items-center justify-center overflow-auto flex-1 min-h-[350px]">
          <div className="relative max-h-[65vh] max-w-full flex items-center justify-center rounded-xl overflow-hidden border border-slate-200 bg-white shadow-sm">
            <img
              src={api.getFullPreviewUrl(imageId, item.safe_key, item.version || 1)}
              alt={item.name}
              className="max-h-[65vh] max-w-full object-contain"
            />
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            Full resolution output with {item.width} × {item.height} pixels
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs text-slate-600 hover:text-slate-900 transition-colors cursor-pointer font-medium"
            >
              Close
            </button>
            <button
              onClick={handleDownload}
              className="px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-xs font-semibold text-white shadow-md shadow-violet-200 flex items-center gap-2 transition-all cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download File</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
