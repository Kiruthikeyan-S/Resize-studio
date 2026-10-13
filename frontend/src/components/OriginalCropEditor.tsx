import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Check,
  Crop,
  RotateCcw,
  Loader2,
  Home,
  Lock,
  Unlock,
} from 'lucide-react';
import type { UploadResponse } from '../services/api';
import { api } from '../services/api';
import type { Rect, HandleType, AspectPresetKey } from '../utils/cropMath';
import {
  ASPECT_PRESETS,
  clampRect,
  createDefaultCrop,
  moveRect,
  resizeRectFromHandle,
  setCropDimension,
  rectToCropBox,
  cropBoxToRect,
} from '../utils/cropMath';

interface OriginalCropEditorProps {
  originalData: UploadResponse;
  onClose?: () => void;
  onApply: (updated: UploadResponse) => void | Promise<void>;
  onChangeImage?: () => void;
  inline?: boolean;
}

interface DragState {
  type: 'move' | 'resize';
  handle?: HandleType;
  pointerId: number;
  startX: number;
  startY: number;
  startRect: Rect;
  scaleX: number;
  scaleY: number;
}

export const OriginalCropEditor: React.FC<OriginalCropEditorProps> = ({
  originalData,
  onClose,
  onApply,
  onChangeImage,
  inline = false,
}) => {
  const sourceUrl = originalData.raw_url || originalData.original_url;
  const origW = originalData.raw_width || originalData.width;
  const origH = originalData.raw_height || originalData.height;

  // Aspect ratio preset and lock state
  const [preset, setPreset] = useState<AspectPresetKey>('free');
  const [lockAspect, setLockAspect] = useState<boolean>(false);

  // Crop rectangle state in original-image pixel space
  const [crop, setCrop] = useState<Rect>(() => {
    if (originalData.master_crop_box) {
      return clampRect(cropBoxToRect(originalData.master_crop_box), origW, origH);
    }
    return createDefaultCrop(origW, origH, null, 0.9);
  });

  // String values for Width and Height input boxes (to allow smooth typing)
  const [inputWidth, setInputWidth] = useState<string>(String(crop.width));
  const [inputHeight, setInputHeight] = useState<string>(String(crop.height));

  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // References
  const imgRef = useRef<HTMLImageElement>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

  // Re-sync input strings when crop rect changes
  useEffect(() => {
    setInputWidth(String(crop.width));
    setInputHeight(String(crop.height));
  }, [crop.width, crop.height]);

  // When image session changes, initialize crop
  useEffect(() => {
    if (originalData.master_crop_box) {
      const initRect = clampRect(cropBoxToRect(originalData.master_crop_box), origW, origH);
      setCrop(initRect);
    } else {
      setCrop(createDefaultCrop(origW, origH, null, 0.9));
    }
    setPreset('free');
    setLockAspect(false);
    setErrorMessage(null);
  }, [originalData.image_id, origW, origH]);

  // Determine active ratio constraint (number or null)
  const getActiveRatio = (): number | null => {
    if (preset !== 'free') {
      const match = ASPECT_PRESETS.find((p) => p.key === preset);
      if (match?.ratio) return match.ratio;
    }
    if (lockAspect && crop.height > 0) {
      return crop.width / crop.height;
    }
    return null;
  };

  // Helper to calculate current image display scale (screen px to original image px)
  const getScale = (): { scaleX: number; scaleY: number } => {
    const el = imgRef.current;
    if (!el || !el.clientWidth || !el.clientHeight) {
      return { scaleX: 1, scaleY: 1 };
    }
    return {
      scaleX: origW / el.clientWidth,
      scaleY: origH / el.clientHeight,
    };
  };

  // Handle preset dropdown change
  const handlePresetChange = (newPresetKey: AspectPresetKey) => {
    setPreset(newPresetKey);
    const selectedPreset = ASPECT_PRESETS.find((p) => p.key === newPresetKey);

    if (newPresetKey === 'free' || !selectedPreset?.ratio) {
      setLockAspect(false);
    } else {
      setLockAspect(true);
      const ratio = selectedPreset.ratio;
      // Reshape crop to fit selected aspect ratio centered
      const newCrop = createDefaultCrop(origW, origH, ratio, 0.9);
      setCrop(newCrop);
    }
  };

  // Toggle Lock Aspect Ratio
  const handleToggleLock = () => {
    setLockAspect((prev) => !prev);
  };

  // Manual Width Input Change
  const handleWidthChange = (valStr: string) => {
    setInputWidth(valStr);
    const parsed = parseInt(valStr, 10);
    if (!isNaN(parsed) && parsed > 0) {
      const lockedRatio = getActiveRatio();
      const updated = setCropDimension(crop, 'width', parsed, origW, origH, lockedRatio);
      setCrop(updated);
    }
  };

  // Manual Height Input Change
  const handleHeightChange = (valStr: string) => {
    setInputHeight(valStr);
    const parsed = parseInt(valStr, 10);
    if (!isNaN(parsed) && parsed > 0) {
      const lockedRatio = getActiveRatio();
      const updated = setCropDimension(crop, 'height', parsed, origW, origH, lockedRatio);
      setCrop(updated);
    }
  };

  // Re-clamp on input blur
  const handleInputBlur = () => {
    setInputWidth(String(crop.width));
    setInputHeight(String(crop.height));
  };

  // Reset Crop Button
  const handleResetCrop = () => {
    const lockedRatio = preset !== 'free' ? getActiveRatio() : null;
    const defaultRect = createDefaultCrop(origW, origH, lockedRatio, 0.9);
    setCrop(defaultRect);
  };

  // Pointer event handlers for moving the crop rectangle
  const handleBoxPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // Only drag with primary pointer button
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);

    const { scaleX, scaleY } = getScale();
    setDragState({
      type: 'move',
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      startRect: { ...crop },
      scaleX,
      scaleY,
    });
  };

  // Pointer event handlers for resizing from one of 8 handles
  const handleHandlePointerDown = (
    handle: HandleType,
    e: React.PointerEvent<HTMLDivElement>
  ) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);

    const { scaleX, scaleY } = getScale();
    setDragState({
      type: 'resize',
      handle,
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      startRect: { ...crop },
      scaleX,
      scaleY,
    });
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragState) return;

    const clientDx = e.clientX - dragState.startX;
    const clientDy = e.clientY - dragState.startY;
    const dx = clientDx * dragState.scaleX;
    const dy = clientDy * dragState.scaleY;

    const lockedRatio = getActiveRatio();

    if (dragState.type === 'move') {
      const nextRect = moveRect(dragState.startRect, dx, dy, origW, origH);
      setCrop(nextRect);
    } else if (dragState.type === 'resize' && dragState.handle) {
      const nextRect = resizeRectFromHandle(
        dragState.startRect,
        dragState.handle,
        dx,
        dy,
        origW,
        origH,
        lockedRatio
      );
      setCrop(nextRect);
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragState) {
      try {
        (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
      } catch {
        // Safe ignore
      }
      setDragState(null);
    }
  };

  // Done finalizes the selected crop without triggering any resizing.
  const handleApply = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const cropBox = rectToCropBox(crop);
      const updated = await api.updateOriginalFraming(originalData.image_id, cropBox);
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

  // Percentage positioning for CSS overlays
  const overlayLeftPercent = (crop.x / origW) * 100;
  const overlayTopPercent = (crop.y / origH) * 100;
  const overlayWidthPercent = (crop.width / origW) * 100;
  const overlayHeightPercent = (crop.height / origH) * 100;

  // Render individual resize handle
  const renderHandle = (
    handle: HandleType,
    cursorClass: string,
    positionClass: string
  ) => {
    return (
      <div
        key={handle}
        onPointerDown={(e) => handleHandlePointerDown(handle, e)}
        className={`absolute z-30 flex items-center justify-center w-6 h-6 select-none touch-none ${cursorClass} ${positionClass}`}
      >
        <div className="w-2.5 h-2.5 bg-white border-2 border-violet-600 rounded-xs shadow-md pointer-events-none transition-transform hover:scale-125" />
      </div>
    );
  };

  const content = (
    <div
      className={`bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs ${
        inline ? 'w-full' : 'w-full max-w-4xl max-h-[94vh] shadow-2xl'
      }`}
    >
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center text-violet-700">
            <Crop className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-semibold text-base text-slate-900">
              Original Image Framing & Crop Editor
            </h3>
            <p className="text-xs text-slate-500 font-mono">
              {originalData.original_filename} • Original: {origW} × {origH} px
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

      {/* Visual Crop Canvas */}
      <div
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        className="p-4 sm:p-6 bg-slate-900/5 flex items-center justify-center overflow-hidden flex-1 min-h-[340px] max-h-[460px] select-none"
      >
        <div className="relative inline-block select-none touch-none rounded-xl overflow-hidden shadow-sm border border-slate-300 bg-slate-950/20">
          <img
            ref={imgRef}
            src={sourceUrl}
            alt="Original framing preview"
            className="max-h-[420px] max-w-full w-auto object-contain block pointer-events-none select-none"
            draggable={false}
          />

          {/* Dark Overlay Outside Selection */}
          <div
            className="absolute inset-0 bg-slate-950/65 pointer-events-none"
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

          {/* Interactive Crop Selection Box */}
          <div
            onPointerDown={handleBoxPointerDown}
            className={`absolute border-2 border-violet-500 shadow-[0_0_20px_rgba(124,58,237,0.5)] touch-none select-none ${
              dragState?.type === 'move' ? 'cursor-grabbing' : 'cursor-grab'
            }`}
            style={{
              left: `${overlayLeftPercent}%`,
              top: `${overlayTopPercent}%`,
              width: `${overlayWidthPercent}%`,
              height: `${overlayHeightPercent}%`,
            }}
            title="Drag to reposition crop area"
          >
            {/* Rule of Thirds 3x3 Grid */}
            <div className="w-full h-full grid grid-cols-3 grid-rows-3 pointer-events-none opacity-70">
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

            {/* Center Crosshair Marker */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-80">
              <div className="w-2.5 h-2.5 rounded-full bg-violet-600 border border-white shadow-xs" />
            </div>

            {/* Corner Resize Handles */}
            {renderHandle('nw', 'cursor-nwse-resize', '-top-3 -left-3')}
            {renderHandle('ne', 'cursor-nesw-resize', '-top-3 -right-3')}
            {renderHandle('se', 'cursor-nwse-resize', '-bottom-3 -right-3')}
            {renderHandle('sw', 'cursor-nesw-resize', '-bottom-3 -left-3')}

            {/* Edge Resize Handles */}
            {renderHandle('n', 'cursor-ns-resize', '-top-3 left-1/2 -translate-x-1/2')}
            {renderHandle('s', 'cursor-ns-resize', '-bottom-3 left-1/2 -translate-x-1/2')}
            {renderHandle('w', 'cursor-ew-resize', 'top-1/2 -left-3 -translate-y-1/2')}
            {renderHandle('e', 'cursor-ew-resize', 'top-1/2 -right-3 -translate-y-1/2')}
          </div>
        </div>
      </div>

      {/* Dimensions & Presets Bar */}
      <div className="px-5 py-3 bg-violet-50/70 border-t border-violet-100 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Live Pixel Dimension Display & Inputs */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <span className="font-semibold text-slate-700">Crop Area:</span>
          <div className="flex items-center gap-1.5 bg-white px-2.5 py-1 rounded-lg border border-violet-200 shadow-2xs">
            <span className="text-slate-500 font-medium">Width</span>
            <input
              type="number"
              min={10}
              max={origW}
              value={inputWidth}
              onChange={(e) => handleWidthChange(e.target.value)}
              onBlur={handleInputBlur}
              className="w-16 px-1.5 py-0.5 text-center font-mono font-bold text-violet-700 border border-slate-200 rounded-md focus:border-violet-500 focus:outline-hidden"
            />
            <span className="text-slate-400 font-bold">×</span>
            <span className="text-slate-500 font-medium">Height</span>
            <input
              type="number"
              min={10}
              max={origH}
              value={inputHeight}
              onChange={(e) => handleHeightChange(e.target.value)}
              onBlur={handleInputBlur}
              className="w-16 px-1.5 py-0.5 text-center font-mono font-bold text-violet-700 border border-slate-200 rounded-md focus:border-violet-500 focus:outline-hidden"
            />
            <span className="text-slate-500 font-mono">px</span>
          </div>

          {/* Aspect Ratio Lock Toggle */}
          <button
            type="button"
            onClick={handleToggleLock}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg border font-medium transition-colors cursor-pointer ${
              lockAspect
                ? 'bg-violet-600 text-white border-violet-600 shadow-2xs'
                : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
            }`}
            title={lockAspect ? 'Aspect ratio locked' : 'Aspect ratio free'}
          >
            {lockAspect ? (
              <>
                <Lock className="w-3.5 h-3.5" />
                <span>Locked</span>
              </>
            ) : (
              <>
                <Unlock className="w-3.5 h-3.5 text-slate-400" />
                <span>Unlocked</span>
              </>
            )}
          </button>
        </div>

        {/* Aspect Ratio Presets Dropdown */}
        <div className="flex items-center gap-2">
          <span className="text-slate-600 font-medium">Preset:</span>
          <select
            value={preset}
            onChange={(e) => handlePresetChange(e.target.value as AspectPresetKey)}
            className="px-3 py-1 bg-white border border-slate-200 rounded-lg text-xs font-semibold text-slate-800 shadow-2xs focus:border-violet-500 focus:outline-hidden cursor-pointer"
          >
            {ASPECT_PRESETS.map((p) => (
              <option key={p.key} value={p.key}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Footer Controls & Actions */}
      <div className="p-4 sm:p-5 bg-slate-50 border-t border-slate-200 space-y-3">
        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
            {errorMessage}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleResetCrop}
              className="text-xs text-slate-700 hover:text-slate-900 flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-300 bg-white hover:bg-slate-100 transition-colors cursor-pointer font-medium shadow-2xs"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
              <span>Reset Crop</span>
            </button>
          </div>

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
                  <span>Saving Crop...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Done</span>
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

export default OriginalCropEditor;
