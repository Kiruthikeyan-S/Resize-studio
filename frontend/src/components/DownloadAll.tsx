import React, { useState } from 'react';
import { Archive, Download, Loader2 } from 'lucide-react';
import { api } from '../services/api';

interface DownloadAllProps {
  imageId: string;
  totalOutputs: number;
}

export const DownloadAll: React.FC<DownloadAllProps> = ({
  imageId,
  totalOutputs,
}) => {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownloadZip = () => {
    setIsDownloading(true);
    const url = api.getDownloadAllUrl(imageId);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'ratio-studio-images.zip');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => {
      setIsDownloading(false);
    }, 1500);
  };

  return (
    <div className="w-full bg-gradient-to-r from-violet-50 via-white to-slate-50 border border-violet-200/80 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
      <div className="flex items-center gap-3.5">
        <div className="w-11 h-11 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center shrink-0">
          <Archive className="w-5 h-5 text-violet-600" />
        </div>
        <div>
          <h4 className="font-semibold text-sm text-slate-900">
            Download Complete Package
          </h4>
          <p className="text-xs text-slate-500">
            Includes all {totalOutputs} high-res aspect ratios + detailed format manifest
          </p>
        </div>
      </div>

      <button
        type="button"
        onClick={handleDownloadZip}
        disabled={isDownloading}
        className="w-full sm:w-auto px-6 py-3 rounded-xl bg-violet-600 hover:bg-violet-700 active:scale-[0.99] text-xs font-semibold text-white shadow-md shadow-violet-200 flex items-center justify-center gap-2 transition-all whitespace-nowrap cursor-pointer disabled:opacity-70 disabled:cursor-not-allowed"
      >
        {isDownloading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Packaging ZIP...</span>
          </>
        ) : (
          <>
            <Download className="w-4 h-4" />
            <span>Download All ({totalOutputs} Ratios ZIP)</span>
          </>
        )}
      </button>
    </div>
  );
};
