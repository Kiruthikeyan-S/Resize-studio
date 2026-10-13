import React from 'react';
import { CheckCircle2, ImagePlus, Loader2, Maximize2 } from 'lucide-react';
import type { UploadResponse } from '../services/api';

interface CroppedImageReviewProps {
  image: UploadResponse;
  isResizing: boolean;
  hasOutputs: boolean;
  onResize: () => void;
  onChangeImage: () => void;
}

/** Shown only after Done. Displays only the approved cropped working image. */
export const CroppedImageReview: React.FC<CroppedImageReviewProps> = ({
  image,
  isResizing,
  hasOutputs,
  onResize,
  onChangeImage,
}) => (
  <section className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
    <div className="flex flex-wrap justify-between items-center gap-3 px-5 py-4 border-b border-slate-200 bg-slate-50/70">
      <div>
        <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <CheckCircle2 className="w-5 h-5 text-emerald-600" /> Approved Cropped Image
        </h3>
        <p className="text-xs text-slate-500 mt-1 font-mono">
          {image.width} × {image.height} px · This crop is the only source for resizing.
        </p>
      </div>
      <button
        onClick={onChangeImage}
        type="button"
        className="text-xs rounded-xl border border-slate-300 bg-white px-3 py-2 flex items-center gap-2 hover:bg-slate-100 font-semibold text-slate-700 cursor-pointer shadow-2xs transition-colors"
      >
        <ImagePlus className="w-4 h-4 text-violet-600" /> Change Image
      </button>
    </div>
    <div className="px-5 py-6 bg-slate-100 flex items-center justify-center">
      <img
        src={image.original_url}
        alt="Final approved crop"
        draggable={false}
        className="max-h-[480px] max-w-full object-contain rounded-lg shadow-sm"
      />
    </div>
    <div className="flex flex-wrap justify-between items-center gap-3 p-5 border-t border-slate-200">
      <p className="text-xs text-slate-600">
        {hasOutputs
          ? '5 ratios and 15 fixed-size exports are ready.'
          : 'Crop saved. Click Resize to generate all 5 ratios.'}
      </p>
      <button
        type="button"
        onClick={onResize}
        disabled={isResizing}
        className="px-5 py-2.5 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-xl text-sm inline-flex items-center gap-2 disabled:opacity-50 cursor-pointer shadow-md shadow-violet-200 transition-all active:scale-[0.99]"
      >
        {isResizing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Maximize2 className="w-4 h-4" />}
        {isResizing ? 'Resizing...' : hasOutputs ? 'Resize Again' : 'Resize to 5 Ratios'}
      </button>
    </div>
  </section>
);

export default CroppedImageReview;
