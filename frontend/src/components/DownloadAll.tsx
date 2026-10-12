import React, { useState } from 'react';
import { Archive, Download, Loader2 } from 'lucide-react';
import { api } from '../services/api';

interface DownloadAllProps {
  imageId: string;
  totalOutputs: number;
  allImageIds?: string[];
  totalConvertedImages?: number;
  mode?: string;
}

export const DownloadAll: React.FC<DownloadAllProps> = ({
  imageId,
  totalOutputs,
  allImageIds = [],
  totalConvertedImages = 1,
  mode,
}) => {
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadingBatch, setIsDownloadingBatch] = useState(false);

  const handleDownloadZip = () => {
    setIsDownloading(true);
    const url = api.getDownloadAllUrl(imageId, mode);
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

  const handleDownloadBatchZip = () => {
    if (!allImageIds.length) return;
    setIsDownloadingBatch(true);
    const url = api.getDownloadBatchUrl(allImageIds, mode);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `ratio-studio-batch-${allImageIds.length}-images.zip`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    setTimeout(() => {
      setIsDownloadingBatch(false);
    }, 2000);
  };

  const hasMultipleImages = allImageIds.length > 1;

  return (
    <div className="w-full bg-gradient-to-r from-violet-50 via-white to-slate-50 border border-violet-200/80 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-sm">
      <div className="flex items-center gap-3.5">
        <div className="w-11 h-11 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center shrink-0">
          <Archive className="w-5 h-5 text-violet-600" />
        </div>
        <div>
          <h4 className="font-semibold text-sm text-slate-900">
            Download ZIP Archive
          </h4>
          <p className="text-xs text-slate-500">
            {hasMultipleImages
              ? `${totalConvertedImages} of ${allImageIds.length} images processed • High-res exports + manifest`
              : `Includes all ${totalOutputs} high-res aspect ratios + detailed format manifest`}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
        <button
          type="button"
          onClick={handleDownloadZip}
          disabled={isDownloading}
          className="flex-1 sm:flex-none px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 active:scale-[0.99] text-xs font-semibold text-white shadow-xs flex items-center justify-center gap-2 transition-all whitespace-nowrap cursor-pointer disabled:opacity-70"
        >
          {isDownloading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Packaging...</span>
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              <span>Download Active Image ZIP ({totalOutputs} Ratios)</span>
            </>
          )}
        </button>

        {hasMultipleImages && (
          <button
            type="button"
            onClick={handleDownloadBatchZip}
            disabled={isDownloadingBatch}
            className="flex-1 sm:flex-none px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 active:scale-[0.99] text-xs font-semibold text-white shadow-xs flex items-center justify-center gap-2 transition-all whitespace-nowrap cursor-pointer disabled:opacity-70"
          >
            {isDownloadingBatch ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Preparing Batch ZIP...</span>
              </>
            ) : (
              <>
                <Archive className="w-4 h-4" />
                <span>Download All Images (Batch ZIP)</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};
