import React, { useState, useEffect, useRef } from 'react';
import { X, Check, Crop, RotateCcw, Loader2, ZoomIn, Move, Home } from 'lucide-react';
import type { UploadResponse } from '../services/api';
import { api } from '../services/api';

interface OriginalCropEditorProps {
  originalData: UploadResponse;
  onClose?: () => void;
  onApply: (updated: UploadResponse) => void | Promise<void>;
  onChangeImage?: () => void;
  inline?: boolean;
}

export const OriginalCropEditor: React.FC<OriginalCropEditorProps> = ({
  originalData,
  onClose,
  onApply,
  onChangeImage,
  inline = false,
}) => {
  const [posX, setPosX] = useState<number>(50); // percentage 0..100
  const [posY, setPosY] = useState<number>(50); // percentage 0..100
  const [zoom, setZoom] = useState<number>(1.0); // 1.0 .. 3.0
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Dragging state for mouse/touch panning
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  // Use untouched raw source URL if available, else original_url
  const sourceUrl = originalData.raw_url || originalData.original_url;
  // Always frame against raw uncropped dimensions when present
  const origW = originalData.raw_width || originalData.width;
  const origH = originalData.raw_height || originalData.height;

  useEffect(() => {
    // If original already has master_crop_box, initialize position
    if (originalData.master_crop_box) {
      const [left, top, right, bottom] = originalData.master_crop_box;
      const cropW = right - left;
      const cropH = bottom - top;
      const maxL = origW - cropW;
      const maxT = origH - cropH;
      setPosX(maxL > 0 ? Math.round((left / maxL) * 100) : 50);
      setPosY(maxT > 0 ? Math.round((top / maxT) * 100) : 50);
      const calculatedZoom = Math.max(1.0, Math.min(3.0, origW / cropW));
      setZoom(Number(calculatedZoom.toFixed(1)));
    } else {
      setPosX(50);
      setPosY(50);
      setZoom(1.0);
    }
  }, [originalData.image_id, originalData.master_crop_box, origW, origH]);

  // The crop frame maintains the original image aspect ratio, zooming into the subject
  const effectiveCropW = Math.max(20, Math.round(origW / zoom));
  const effectiveCropH = Math.max(20, Math.round(origH / zoom));

  const maxLeft = Math.max(0, origW - effectiveCropW);
  const maxTop = Math.max(0, origH - effectiveCropH);

  const leftPx = Math.round((posX / 100) * maxLeft);
  const topPx = Math.round((posY / 100) * maxTop);
  const rightPx = leftPx + effectiveCropW;
  const bottomPx = topPx + effectiveCropH;

  const overlayLeftPercent = (leftPx / origW) * 100;
  const overlayTopPercent = (topPx / origH) * 100;
  const overlayWidthPercent = (effectiveCropW / origW) * 100;
  const overlayHeightPercent = (effectiveCropH / origH) * 100;

  // Direct pointer drag handlers
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (maxLeft <= 0 && maxTop <= 0) return;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    setIsDragging(true);
    dragStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPosX: posX,
      startPosY: posY,
    };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || !dragStartRef.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const deltaX = e.clientX - dragStartRef.current.startX;
    const deltaY = e.clientY - dragStartRef.current.startY;

    // Movement sensitivity relative to container dimensions
    const deltaPercentX = (deltaX / rect.width) * 100;
    const deltaPercentY = (deltaY / rect.height) * 100;

    const newX = Math.max(0, Math.min(100, Math.round(dragStartRef.current.startPosX + deltaPercentX)));
    const newY = Math.max(0, Math.min(100, Math.round(dragStartRef.current.startPosY + deltaPercentY)));

    setPosX(newX);
    setPosY(newY);
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (isDragging) {
      try {
        (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
      } catch {
        // Safe ignore
      }
      setIsDragging(false);
      dragStartRef.current = null;
    }
  };

  const handleApply = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const updated = await api.updateOriginalFraming(originalData.image_id, [
        leftPx,
        topPx,
        rightPx,
        bottomPx,
      ]);
      await onApply(updated);
      if (onClose) onClose();
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to update framing.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetToUntouched = async () => {
    setIsResetting(true);
    setErrorMessage(null);
    try {
      const reset = await api.resetOriginalFraming(originalData.image_id);
      setPosX(50);
      setPosY(50);
      setZoom(1.0);
      await onApply(reset);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to reset image.'
      );
    } finally {
      setIsResetting(false);
    }
  };

  const content = (
    <div className={`bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs ${inline ? 'w-full' : 'w-full max-w-3xl max-h-[94vh] shadow-2xl'}`}>
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center text-violet-700">
            <Crop className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-base text-slate-900">
              Original Image Framing
            </h3>
            <p className="text-xs text-slate-500 font-mono">
              {originalData.original_filename} • Source: {origW} × {origH} px
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onChangeImage && (
            <button
              type="button"
              onClick={onChangeImage}
              className="py-1.5 px-3 rounded-xl border border-slate-200 hover:border-violet-300 bg-white hover:bg-violet-50 text-slate-700 hover:text-violet-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-2xs"
              title="Return to Home Screen to upload a new image"
            >
              <Home className="w-3.5 h-3.5 text-violet-600" />
              <span>Home Screen</span>
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
              title="Cancel"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>
      </div>

      {/* Live Visual Crop & Framing Canvas with Direct Pointer Drag */}
      <div className="p-4 sm:p-6 bg-slate-100 flex items-center justify-center overflow-hidden flex-1 min-h-[340px] max-h-[460px]">
        <div
          ref={containerRef}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className={`relative max-h-[420px] max-w-full rounded-xl overflow-hidden border border-slate-300 select-none shadow-inner bg-slate-900/10 flex items-center justify-center touch-none ${
            isDragging ? 'cursor-grabbing' : 'cursor-grab'
          }`}
          title="Drag image to adjust framing position"
        >
          <img
            src={sourceUrl}
            alt="Original framing preview"
            className="max-h-[420px] w-auto object-contain block pointer-events-none select-none"
            draggable={false}
          />

          {/* Darkened mask outside crop box */}
          <div
            className="absolute inset-0 bg-slate-950/60 pointer-events-none transition-all duration-75"
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
            className="absolute border-2 border-violet-500 shadow-[0_0_24px_rgba(124,58,237,0.6)] transition-all duration-75 pointer-events-none"
            style={{
              left: `${overlayLeftPercent}%`,
              top: `${overlayTopPercent}%`,
              width: `${overlayWidthPercent}%`,
              height: `${overlayHeightPercent}%`,
            }}
          >
            {/* 3x3 Grid rule-of-thirds guides */}
            <div className="w-full h-full grid grid-cols-3 grid-rows-3 pointer-events-none opacity-60">
              <div className="border-r border-b border-violet-300/80" />
              <div className="border-r border-b border-violet-300/80" />
              <div className="border-b border-violet-300/80" />
              <div className="border-r border-b border-violet-300/80" />
              <div className="border-r border-b border-violet-300/80" />
              <div className="border-b border-violet-300/80" />
              <div className="border-r border-b border-violet-300/80" />
              <div className="border-r border-b border-violet-300/80" />
              <div />
            </div>

            {/* Center crosshair marker */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-90">
              <div className="w-3 h-3 rounded-full bg-violet-600 border-2 border-white shadow-sm" />
            </div>

            {/* Corner handles indicator */}
            <div className="absolute -top-1 -left-1 w-2.5 h-2.5 bg-white border-2 border-violet-600 rounded-xs" />
            <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-white border-2 border-violet-600 rounded-xs" />
            <div className="absolute -bottom-1 -left-1 w-2.5 h-2.5 bg-white border-2 border-violet-600 rounded-xs" />
            <div className="absolute -bottom-1 -right-1 w-2.5 h-2.5 bg-white border-2 border-violet-600 rounded-xs" />
          </div>
        </div>
      </div>

      {/* Framing Dimensions Bar */}
      <div className="px-5 py-2.5 bg-violet-50/70 border-t border-violet-100 flex flex-wrap items-center justify-between text-xs text-violet-900 font-medium">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-700">Working Crop Area:</span>
          <span className="font-mono font-bold text-violet-700">{effectiveCropW} × {effectiveCropH} px</span>
          <span className="text-slate-400">•</span>
          <span className="text-slate-600 font-mono">Zoom: {zoom.toFixed(1)}x</span>
        </div>
        <span className="text-slate-500 text-[11px]">
          Drag preview or use sliders below.
        </span>
      </div>

        {/* Sliders & Controls */}
        <div className="p-4 sm:p-5 bg-slate-50 border-t border-slate-200 space-y-4">
          {errorMessage && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
              {errorMessage}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Horizontal Position */}
            <div className="space-y-1.5 bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex justify-between text-xs text-slate-600">
                <span className="flex items-center gap-1.5 font-medium text-slate-700">
                  <Move className="w-3.5 h-3.5 text-violet-600" /> Horizontal Pan
                </span>
                <span className="font-mono text-slate-900 font-bold">{posX}%</span>
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
            <div className="space-y-1.5 bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex justify-between text-xs text-slate-600">
                <span className="flex items-center gap-1.5 font-medium text-slate-700">
                  <Move className="w-3.5 h-3.5 text-violet-600" /> Vertical Pan
                </span>
                <span className="font-mono text-slate-900 font-bold">{posY}%</span>
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
            <div className="space-y-1.5 bg-white p-3 rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex justify-between text-xs text-slate-600">
                <span className="flex items-center gap-1.5 font-medium text-slate-700">
                  <ZoomIn className="w-3.5 h-3.5 text-violet-600" /> Zoom Level
                </span>
                <span className="font-mono text-slate-900 font-bold">{zoom.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min={1.0}
                max={3.0}
                step={0.1}
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
                className="w-full accent-violet-600 bg-slate-200 h-2 rounded-lg cursor-pointer"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-200/80">
            <button
              type="button"
              onClick={() => {
                setPosX(50);
                setPosY(50);
                setZoom(1.0);
              }}
              className="text-xs text-slate-700 hover:text-slate-900 flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 transition-colors cursor-pointer font-medium"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
              <span>Reset Center</span>
            </button>

            {onChangeImage && (
              <button
                type="button"
                onClick={onChangeImage}
                className="text-xs text-slate-600 hover:text-slate-900 px-3 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 transition-colors cursor-pointer font-medium"
              >
                Change Image
              </button>
            )}

            {originalData.is_cropped_master && (
              <button
                type="button"
                onClick={handleResetToUntouched}
                disabled={isResetting}
                className="text-xs text-amber-700 hover:text-amber-800 bg-amber-50 hover:bg-amber-100 border border-amber-200 px-3 py-2 rounded-xl transition-colors cursor-pointer font-medium"
              >
                {isResetting ? 'Resetting...' : 'Revert to Raw Original'}
              </button>
            )}

            <div className="flex items-center gap-2.5 ml-auto">
              {onClose && (
                <button
                  type="button"
                  onClick={onClose}
                  className="text-xs text-slate-600 hover:text-slate-900 px-4 py-2.5 rounded-xl transition-colors cursor-pointer font-medium hover:bg-slate-200/50"
                >
                  Cancel
                </button>
              )}
              <button
                type="button"
                onClick={handleApply}
                disabled={isSaving}
                className="px-6 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-xs font-semibold text-white shadow-md shadow-violet-200 flex items-center gap-2 transition-all disabled:opacity-50 cursor-pointer active:scale-[0.99]"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Applying Framing...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Apply & Update</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
  );

  if (inline) {
    return content;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      {content}
    </div>
  );
};
