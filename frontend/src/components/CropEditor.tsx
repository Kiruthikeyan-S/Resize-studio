import React, { useState, useEffect, useRef } from 'react';
import { X, Check, Crop, RotateCcw, Loader2, ZoomIn, Move } from 'lucide-react';
import type { RatioOutput, UploadResponse } from '../services/api';
import { api } from '../services/api';

interface CropEditorProps {
  item: RatioOutput | null;
  originalData: UploadResponse | null;
  onClose: () => void;
  onSave: (updated: RatioOutput) => void;
}

export const CropEditor: React.FC<CropEditorProps> = ({
  item,
  originalData,
  onClose,
  onSave,
}) => {
  const [posX, setPosX] = useState<number>(50); // percentage 0..100
  const [posY, setPosY] = useState<number>(50); // percentage 0..100
  const [zoom, setZoom] = useState<number>(1.0); // 1.0 .. 2.5
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Active source image URL and source dimensions (honoring replacement isolation)
  const activeSourceUrl = item?.source_url || originalData?.original_url || '';
  const activeSourceW = item?.source_width || originalData?.width || 1920;
  const activeSourceH = item?.source_height || originalData?.height || 1080;

  useEffect(() => {
    if (item && item.crop_box) {
      const [left, top, right, bottom] = item.crop_box;
      const cropW = right - left;
      const cropH = bottom - top;
      const maxLeft = activeSourceW - cropW;
      const maxTop = activeSourceH - cropH;

      const initX = maxLeft > 0 ? (left / maxLeft) * 100 : 50;
      const initY = maxTop > 0 ? (top / maxTop) * 100 : 50;
      setPosX(Math.max(0, Math.min(100, initX)));
      setPosY(Math.max(0, Math.min(100, initY)));
      setZoom(1.0);
      setErrorMessage(null);
    } else {
      setPosX(50);
      setPosY(50);
      setZoom(1.0);
      setErrorMessage(null);
    }
  }, [item, activeSourceW, activeSourceH]);

  if (!item || !originalData) return null;

  const targetRatio = item.width / item.height;
  const origW = activeSourceW;
  const origH = activeSourceH;
  const origRatio = origW / origH;

  // Base max crop window strictly maintaining exact target aspect ratio
  let baseCropW: number;
  let baseCropH: number;
  if (origRatio > targetRatio) {
    baseCropH = origH;
    baseCropW = Math.round(origH * targetRatio);
  } else {
    baseCropW = origW;
    baseCropH = Math.round(origW / targetRatio);
  }

  // Factor in zoom: higher zoom means smaller crop window in original space (zooms in on subject)
  // Ensure minimum 10px and strict target aspect ratio preservation
  const effectiveCropH = Math.max(10, Math.min(baseCropH, Math.round(baseCropH / zoom)));
  const effectiveCropW = Math.max(10, Math.min(baseCropW, Math.round(effectiveCropH * targetRatio)));

  const maxLeft = Math.max(0, origW - effectiveCropW);
  const maxTop = Math.max(0, origH - effectiveCropH);

  const leftPx = Math.round((posX / 100) * maxLeft);
  const topPx = Math.round((posY / 100) * maxTop);
  const rightPx = leftPx + effectiveCropW;
  const bottomPx = topPx + effectiveCropH;

  // Relative percentages for visualization overlay
  const overlayLeftPercent = (leftPx / origW) * 100;
  const overlayTopPercent = (topPx / origH) * 100;
  const overlayWidthPercent = (effectiveCropW / origW) * 100;
  const overlayHeightPercent = (effectiveCropH / origH) * 100;

  const handleApply = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const updated = await api.adjustCrop(originalData.image_id, item.safe_key, [
        leftPx,
        topPx,
        rightPx,
        bottomPx,
      ]);
      onSave(updated);
      onClose();
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || 'Failed to adjust crop. Ensure coordinates are valid.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white border border-slate-200 rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <Crop className="w-4 h-4 text-violet-600" />
            <div>
              <h3 className="font-semibold text-sm text-slate-900">
                Adjust Framing: {item.name}
              </h3>
              <p className="text-[11px] text-slate-500 font-mono">
                Target Ratio: {item.ratio_key} ({item.width} × {item.height} px) • Source: {origW} × {origH} px
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Live Visual Crop Overlay */}
        <div className="p-6 bg-slate-100 flex items-center justify-center overflow-auto flex-1 min-h-[300px]">
          <div
            ref={containerRef}
            className="relative max-h-[380px] max-w-full rounded-xl overflow-hidden border border-slate-300 select-none shadow-inner"
          >
            <img
              src={activeSourceUrl}
              alt="Crop editor preview"
              className="max-h-[380px] w-auto object-contain block"
            />

            {/* Darkened mask outside crop box */}
            <div
              className="absolute inset-0 bg-slate-900/60 pointer-events-none"
              style={{
                clipPath: `polygon(
                  0% 0%, 0% 100%, 100% 100%, 100% 0%, 0% 0%,
                  ${overlayLeftPercent}% ${overlayTopPercent}%,
                  ${overlayLeftPercent + overlayWidthPercent}% ${overlayTopPercent}%,
                  ${overlayLeftPercent + overlayWidthPercent}% ${overlayTopPercent + overlayHeightPercent}%,
                  ${overlayLeftPercent}% ${overlayTopPercent + overlayHeightPercent}%,
                  ${overlayLeftPercent}% ${overlayTopPercent}%
                )`,
              }}
            />

            {/* Active Crop Region Frame */}
            <div
              className="absolute border-2 border-violet-500 shadow-[0_0_20px_rgba(124,58,237,0.5)] transition-all duration-75 pointer-events-none"
              style={{
                left: `${overlayLeftPercent}%`,
                top: `${overlayTopPercent}%`,
                width: `${overlayWidthPercent}%`,
                height: `${overlayHeightPercent}%`,
              }}
            >
              {/* Grid rule-of-thirds guides inside crop box */}
              <div className="w-full h-full grid grid-cols-3 grid-rows-3 pointer-events-none opacity-50">
                <div className="border-r border-b border-violet-300" />
                <div className="border-r border-b border-violet-300" />
                <div className="border-b border-violet-300" />
                <div className="border-r border-b border-violet-300" />
                <div className="border-r border-b border-violet-300" />
                <div className="border-b border-violet-300" />
                <div className="border-r border-b border-violet-300" />
                <div className="border-r border-b border-violet-300" />
                <div />
              </div>

              {/* Center indicator */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-80">
                <div className="w-2.5 h-2.5 rounded-full bg-violet-600 shadow-sm" />
              </div>
            </div>
          </div>
        </div>

        {/* Sliders & Controls */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 space-y-4">
          {errorMessage && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 font-medium">
              {errorMessage}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Horizontal Position */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-600">
                <span className="flex items-center gap-1 font-medium">
                  <Move className="w-3 h-3 text-violet-600" /> Horizontal
                </span>
                <span className="font-mono text-slate-800 font-semibold">{posX}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={posX}
                disabled={maxLeft <= 0}
                onChange={(e) => setPosX(Number(e.target.value))}
                className="w-full accent-violet-600 bg-slate-200 h-2 rounded-lg cursor-pointer disabled:opacity-30"
              />
            </div>

            {/* Vertical Position */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-600">
                <span className="flex items-center gap-1 font-medium">
                  <Move className="w-3 h-3 text-violet-600" /> Vertical
                </span>
                <span className="font-mono text-slate-800 font-semibold">{posY}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={posY}
                disabled={maxTop <= 0}
                onChange={(e) => setPosY(Number(e.target.value))}
                className="w-full accent-violet-600 bg-slate-200 h-2 rounded-lg cursor-pointer disabled:opacity-30"
              />
            </div>

            {/* Zoom Slider */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-600">
                <span className="flex items-center gap-1 font-medium">
                  <ZoomIn className="w-3 h-3 text-violet-600" /> Zoom
                </span>
                <span className="font-mono text-slate-800 font-semibold">{zoom.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min={1.0}
                max={2.5}
                step={0.1}
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
                className="w-full accent-violet-600 bg-slate-200 h-2 rounded-lg cursor-pointer"
              />
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              onClick={() => {
                setPosX(50);
                setPosY(50);
                setZoom(1.0);
              }}
              className="text-xs text-slate-600 hover:text-slate-900 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 transition-colors cursor-pointer font-medium"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Center</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="text-xs text-slate-600 hover:text-slate-900 px-4 py-2 rounded-xl transition-colors cursor-pointer font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApply}
                disabled={isSaving}
                className="px-5 py-2 rounded-xl bg-violet-600 hover:bg-violet-700 text-xs font-semibold text-white shadow-md shadow-violet-200 flex items-center gap-1.5 transition-all disabled:opacity-50 cursor-pointer"
              >
                {isSaving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Check className="w-3.5 h-3.5" />
                )}
                <span>Apply & Update</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
