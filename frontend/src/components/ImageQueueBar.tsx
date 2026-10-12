import React, { useRef } from 'react';
import { Plus, X, CheckCircle2, Clock, Images, Sparkles } from 'lucide-react';
import type { UploadResponse } from '../services/api';
import { api } from '../services/api';

interface ImageQueueBarProps {
  images: UploadResponse[];
  activeImageId: string;
  onSelectImage: (imageId: string) => void;
  onRemoveImage: (imageId: string) => void;
  onAddImages: (newImages: UploadResponse[]) => void;
  imageOutputsMap: Record<string, any[]>;
  onBatchConvertAll?: () => void;
  isBatchConverting?: boolean;
}

export const ImageQueueBar: React.FC<ImageQueueBarProps> = ({
  images,
  activeImageId,
  onSelectImage,
  onRemoveImage,
  onAddImages,
  imageOutputsMap,
  onBatchConvertAll,
  isBatchConverting = false,
}) => {
  const addFileInputRef = useRef<HTMLInputElement>(null);

  const handleAddFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const files = Array.from(e.target.files);
    try {
      if (files.length === 1) {
        const single = await api.uploadImage(files[0]);
        onAddImages([single]);
      } else {
        const batch = await api.uploadMultipleImages(files);
        onAddImages(batch);
      }
    } catch (err) {
      console.error('Failed to add images:', err);
    } finally {
      if (addFileInputRef.current) addFileInputRef.current.value = '';
    }
  };

  const activeIndex = images.findIndex((img) => img.image_id === activeImageId);
  const unconvertedCount = images.filter((img) => !imageOutputsMap[img.image_id]?.length).length;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs space-y-3">
      {/* Hidden file input for adding more images */}
      <input
        type="file"
        ref={addFileInputRef}
        onChange={handleAddFiles}
        accept="image/jpeg,image/png,image/webp"
        multiple
        className="hidden"
      />

      {/* Header with info and actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center">
            <Images className="w-4 h-4" />
          </div>
          <div>
            <span className="text-sm font-semibold text-slate-900">
              Uploaded Images Queue
            </span>
            <span className="ml-2 text-xs font-medium text-slate-500">
              ({images.length} {images.length === 1 ? 'image' : 'images'} total • Active: #{activeIndex + 1})
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {images.length > 1 && onBatchConvertAll && (
            <button
              type="button"
              onClick={onBatchConvertAll}
              disabled={isBatchConverting}
              className="py-1.5 px-3 rounded-xl bg-violet-50 hover:bg-violet-100 text-violet-700 font-semibold text-xs flex items-center gap-1.5 transition-colors cursor-pointer border border-violet-200 disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>
                {isBatchConverting
                  ? 'Converting All...'
                  : unconvertedCount > 0
                  ? `Convert All (${images.length} Images)`
                  : 'Re-convert All Images'}
              </span>
            </button>
          )}

          <button
            type="button"
            onClick={() => addFileInputRef.current?.click()}
            className="py-1.5 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add More</span>
          </button>
        </div>
      </div>

      {/* Thumbnails Carousel / Strip */}
      <div className="flex items-center gap-3 overflow-x-auto pb-1 scrollbar-thin scrollbar-thumb-slate-200">
        {images.map((img, idx) => {
          const isActive = img.image_id === activeImageId;
          const hasOutputs = (imageOutputsMap[img.image_id]?.length || 0) > 0;

          return (
            <div
              key={img.image_id}
              onClick={() => onSelectImage(img.image_id)}
              className={`relative shrink-0 flex items-center gap-2.5 p-2 pr-3 rounded-xl border-2 transition-all cursor-pointer select-none max-w-[240px] ${
                isActive
                  ? 'border-violet-600 bg-violet-50/60 shadow-xs'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/70'
              }`}
            >
              {/* Thumbnail */}
              <div className="w-12 h-12 rounded-lg bg-slate-100 overflow-hidden flex items-center justify-center shrink-0 border border-slate-200">
                <img
                  src={img.original_url}
                  alt={img.original_filename}
                  className="w-full h-full object-cover"
                />
              </div>

              {/* Info */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-bold text-slate-400">#{idx + 1}</span>
                  <p className="text-xs font-semibold text-slate-900 truncate" title={img.original_filename}>
                    {img.original_filename}
                  </p>
                </div>
                <p className="text-[10px] text-slate-500 font-medium">
                  {img.width} × {img.height} px
                </p>
                <div className="flex items-center gap-1 mt-0.5">
                  {hasOutputs ? (
                    <span className="text-[10px] font-semibold text-emerald-600 flex items-center gap-1">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                      5 Ratios Ready
                    </span>
                  ) : (
                    <span className="text-[10px] text-slate-400 flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" />
                      Not generated
                    </span>
                  )}
                </div>
              </div>

              {/* Remove button */}
              {images.length > 1 && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveImage(img.image_id);
                  }}
                  className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer shrink-0"
                  title="Remove image from queue"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
