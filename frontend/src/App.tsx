import React, { useState } from 'react';
import { Header } from './components/Header';
import { ImageUploader } from './components/ImageUploader';
import { ImageQueueBar } from './components/ImageQueueBar';
import { ConversionSettings } from './components/ConversionSettings';
import { RatioCard } from './components/RatioCard';
import { DownloadAll } from './components/DownloadAll';
import { CropEditor } from './components/CropEditor';
import { OriginalCropEditor } from './components/OriginalCropEditor';
import { PreviewModal } from './components/PreviewModal';
import type { UploadResponse, RatioOutput, ConvertSettings } from './services/api';
import { api } from './services/api';
import { AlertCircle, Crop, RotateCcw, Home, Check } from 'lucide-react';

export type ProcessingMode = 'smart_crop' | 'safe_fit' | 'manual_crop';

export const App: React.FC = () => {
  const [images, setImages] = useState<UploadResponse[]>([]);
  const [activeImageId, setActiveImageId] = useState<string>('');
  // Mode-isolated outputs map: imageId -> mode -> RatioOutput[]
  const [outputsByModeMap, setOutputsByModeMap] = useState<Record<string, Record<string, RatioOutput[]>>>({});
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isBatchGenerating, setIsBatchGenerating] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<RatioOutput | null>(null);
  const [previewModalItem, setPreviewModalItem] = useState<RatioOutput | null>(null);
  const [isEditingOriginal, setIsEditingOriginal] = useState<boolean>(false);
  const [isEditingCrop, setIsEditingCrop] = useState<boolean>(false);
  // Generation revision per image (used so ZIP requests can never mix old and new outputs)
  const [revisionMap, setRevisionMap] = useState<Record<string, number>>({});

  const [settings, setSettings] = useState<ConvertSettings>({
    image_id: '',
    mode: 'smart_crop',
    bg_color_hex: '#F8FAFC',
    is_transparent: false,
    export_format: 'jpeg',
    quality: 90,
    sharpen: false,
    denoise: false,
  });

  const activeImage = images.find((img) => img.image_id === activeImageId) || images[0] || null;
  // Strictly display outputs for active image and current selected mode, sorted in specified vertical order:
  // 1. Square (1:1), 2. Portrait (4:5), 3. Portrait (3:4), 4. Landscape (16:9), 5. Landscape (5:4)
  const ratioOrder = ['square_1x1', 'portrait_4x5', 'portrait_3x4', 'landscape_16x9', 'landscape_5x4'];
  const rawOutputs = activeImage
    ? (outputsByModeMap[activeImage.image_id]?.[settings.mode] || [])
    : [];
  const currentOutputs = [...rawOutputs].sort((a, b) => {
    const idxA = ratioOrder.indexOf(a.safe_key);
    const idxB = ratioOrder.indexOf(b.safe_key);
    return (idxA !== -1 ? idxA : 99) - (idxB !== -1 ? idxB : 99);
  });

  const handleUploadSuccess = (uploadedList: UploadResponse[]) => {
    setImages((prev) => {
      const combined = [...prev, ...uploadedList];
      return combined;
    });

    if (!activeImageId && uploadedList.length > 0) {
      setActiveImageId(uploadedList[0].image_id);
      setSettings((prev) => ({
        ...prev,
        image_id: uploadedList[0].image_id,
      }));
      // Inline left panel editor is already displayed directly
      setIsEditingOriginal(false);
    }
    setErrorMessage(null);
  };

  const handleSelectImage = (imageId: string) => {
    setActiveImageId(imageId);
    setSettings((prev) => ({
      ...prev,
      image_id: imageId,
    }));
    setIsEditingCrop(false);
  };

  const handleRemoveImage = async (imageId: string) => {
    const remaining = images.filter((img) => img.image_id !== imageId);
    setImages(remaining);

    setOutputsByModeMap((prev) => {
      const copy = { ...prev };
      delete copy[imageId];
      return copy;
    });

    if (activeImageId === imageId) {
      if (remaining.length > 0) {
        setActiveImageId(remaining[0].image_id);
        setSettings((prev) => ({ ...prev, image_id: remaining[0].image_id }));
      } else {
        setActiveImageId('');
      }
    }

    try {
      await api.deleteSession(imageId);
    } catch {
      // Ignore background delete errors
    }
  };

  const handleAddImages = (newImages: UploadResponse[]) => {
    setImages((prev) => [...prev, ...newImages]);
    if (!activeImageId && newImages.length > 0) {
      setActiveImageId(newImages[0].image_id);
      setSettings((prev) => ({ ...prev, image_id: newImages[0].image_id }));
    }
  };

  const handleReset = async () => {
    for (const img of images) {
      try {
        await api.deleteSession(img.image_id);
      } catch {
        // Ignore session delete errors on reset
      }
    }
    setImages([]);
    setActiveImageId('');
    setOutputsByModeMap({});
    setErrorMessage(null);
    setEditingItem(null);
    setPreviewModalItem(null);
    setIsEditingCrop(false);
  };

  const handleRevertToRaw = async () => {
    if (!activeImage) return;
    try {
      const reset = await api.resetOriginalFraming(activeImage.image_id);
      setImages((prev) =>
        prev.map((img) => (img.image_id === reset.image_id ? reset : img))
      );
      setOutputsByModeMap((prev) => ({ ...prev, [reset.image_id]: {} }));
      setRevisionMap((prev) => {
        const copy = { ...prev };
        delete copy[reset.image_id];
        return copy;
      });
      setIsEditingCrop(true);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to revert image.'
      );
    }
  };

  const handleBatchConvertAll = async () => {
    if (images.length === 0) return;
    setIsBatchGenerating(true);
    setErrorMessage(null);

    const currentMode = settings.mode;

    for (const img of images) {
      const imageSettings: ConvertSettings = {
        ...settings,
        image_id: img.image_id,
        mode: currentMode,
      };

      try {
        const response = await api.convertImage(imageSettings);
        setOutputsByModeMap((prev) => ({
          ...prev,
          [img.image_id]: {
            ...(prev[img.image_id] || {}),
            [currentMode]: response.outputs,
          },
        }));
        if (response.revision !== undefined) {
          setRevisionMap((prev) => ({ ...prev, [img.image_id]: response.revision as number }));
        }
      } catch (err: any) {
        console.error(`Failed to convert ${img.original_filename}:`, err);
      }
    }

    setIsBatchGenerating(false);
  };

  const handleUpdateSingleRatio = (updated: RatioOutput) => {
    if (!activeImage) return;
    const currentMode = settings.mode;
    setOutputsByModeMap((prev) => {
      const existingForMode = prev[activeImage.image_id]?.[currentMode] || [];
      const updatedList = existingForMode.map((item) =>
        item.safe_key === updated.safe_key ? updated : item
      );
      return {
        ...prev,
        [activeImage.image_id]: {
          ...(prev[activeImage.image_id] || {}),
          [currentMode]: updatedList,
        },
      };
    });
  };

  const handleUpdateOriginalSuccess = async (updatedData: UploadResponse) => {
    // 1. Update the image entry in images list with new dimensions, version, and master crop status
    setImages((prev) =>
      prev.map((img) => (img.image_id === updatedData.image_id ? updatedData : img))
    );

    // 2. Drop outputs from any previous generation so old results/selections can never be shown or downloaded
    setOutputsByModeMap((prev) => ({ ...prev, [updatedData.image_id]: {} }));
    setRevisionMap((prev) => {
      const copy = { ...prev };
      delete copy[updatedData.image_id];
      return copy;
    });

    // 3. Generate all ratios (and their Large/Medium/Small sizes) from this finalized working image only
    setIsGenerating(true);
    setErrorMessage(null);

    const activeMode = settings.mode || 'smart_crop';
    const activeSettings: ConvertSettings = {
      ...settings,
      image_id: updatedData.image_id,
      mode: activeMode,
    };

    try {
      const response = await api.convertImage(activeSettings);
      setOutputsByModeMap((prev) => ({
        ...prev,
        [updatedData.image_id]: {
          ...(prev[updatedData.image_id] || {}),
          [activeMode]: response.outputs,
        },
      }));
      if (response.revision !== undefined) {
        setRevisionMap((prev) => ({ ...prev, [updatedData.image_id]: response.revision as number }));
      }
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to auto-generate 5 ratios after applying framing.'
      );
    } finally {
      setIsGenerating(false);
    }
  };

  // Convert outputsByModeMap to a flat imageOutputsMap for ImageQueueBar progress indicators
  const queueOutputsMap: Record<string, RatioOutput[]> = {};
  for (const img of images) {
    const modeOutputs = outputsByModeMap[img.image_id]?.[settings.mode];
    if (modeOutputs && modeOutputs.length > 0) {
      queueOutputsMap[img.image_id] = modeOutputs;
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col selection:bg-violet-600 selection:text-white">
      <Header onGoHome={images.length > 0 ? handleReset : undefined} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
        {/* Intro Hero */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
            Professional Image Ratio Studio
          </h1>
          <p className="text-sm text-slate-500 max-w-xl mx-auto">
            Upload your original image, fine-tune composition & framing, and instantly generate all 5 standard commercial aspect ratios.
          </p>
        </div>

        {/* Global Error Alert */}
        {errorMessage && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm max-w-3xl mx-auto shadow-sm">
            <AlertCircle className="w-5 h-5 shrink-0 text-red-600" />
            <div className="flex-1">
              <p className="font-semibold text-red-900">Processing Notice</p>
              <p className="text-xs text-red-700">{errorMessage}</p>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-xs font-medium underline text-red-700 hover:text-red-900 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Upload or Multi-Image Workspace Section */}
        {images.length === 0 ? (
          <div className="max-w-2xl mx-auto">
            <ImageUploader
              onUploadSuccess={handleUploadSuccess}
              isLoading={isUploading}
              setIsLoading={setIsUploading}
            />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Multi-Image Queue Bar */}
            <ImageQueueBar
              images={images}
              activeImageId={activeImageId}
              onSelectImage={handleSelectImage}
              onRemoveImage={handleRemoveImage}
              onAddImages={handleAddImages}
              imageOutputsMap={queueOutputsMap}
              onBatchConvertAll={handleBatchConvertAll}
              isBatchConverting={isBatchGenerating}
              onGoHome={handleReset}
            />

            {/* Upper Section: Manual Crop Editor (when uncropped or editing) OR Approved Cropped Image View */}
            <div className="space-y-6 max-w-4xl mx-auto">
              {activeImage && (!activeImage.is_cropped_master || isEditingCrop ? (
                <OriginalCropEditor
                  originalData={activeImage}
                  onApply={(updated) => {
                    handleUpdateOriginalSuccess(updated);
                    setIsEditingCrop(false);
                  }}
                  onClose={activeImage.is_cropped_master ? () => setIsEditingCrop(false) : undefined}
                  onChangeImage={handleReset}
                  inline={true}
                />
              ) : (
                /* Approved Cropped Working Image Card - Raw background is removed, showing ONLY what was cropped */
                <div className="bg-white border border-slate-200 rounded-2xl flex flex-col overflow-hidden shadow-xs">
                  {/* Header */}
                  <div className="p-4 sm:p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center text-violet-700">
                        <Check className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-base text-slate-900">
                            Approved Cropped Image
                          </h3>
                          <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                            Active Working Source
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 font-mono">
                          {activeImage.original_filename} • Cropped: {activeImage.width} × {activeImage.height} px
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setIsEditingCrop(true)}
                        className="py-1.5 px-3.5 rounded-xl border border-violet-200 bg-violet-50 hover:bg-violet-100 text-violet-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-2xs"
                        title="Adjust or re-crop the original image"
                      >
                        <Crop className="w-3.5 h-3.5" />
                        <span>Adjust / Re-Crop</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleRevertToRaw}
                        className="py-1.5 px-3 rounded-xl border border-slate-200 hover:border-amber-300 bg-white hover:bg-amber-50 text-slate-700 hover:text-amber-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-2xs"
                        title="Revert to untouched raw original"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-amber-600" />
                        <span>Revert to Raw</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleReset}
                        className="py-1.5 px-3 rounded-xl border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-2xs"
                        title="Return to Home Screen to upload a new image"
                      >
                        <Home className="w-3.5 h-3.5 text-slate-500" />
                        <span>Home Screen</span>
                      </button>
                    </div>
                  </div>

                  {/* Clean Cropped Image Preview - Only the cropped region is displayed */}
                  <div className="p-4 sm:p-6 bg-slate-900/5 flex flex-col items-center justify-center min-h-[300px] max-h-[440px] overflow-hidden select-none">
                    <div className="relative inline-block rounded-xl overflow-hidden shadow-sm border border-slate-300 bg-white">
                      <img
                        src={activeImage.original_url}
                        alt="Approved cropped working area"
                        className="max-h-[380px] max-w-full w-auto object-contain block mx-auto rounded-lg"
                      />
                    </div>
                  </div>

                  {/* Dimensions Bar */}
                  <div className="px-5 py-3 bg-violet-50/70 border-t border-violet-100 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-700">Active Working Dimensions:</span>
                      <span className="font-mono font-bold text-violet-700 bg-white px-2 py-0.5 rounded-md border border-violet-200">
                        {activeImage.width} × {activeImage.height} px
                      </span>
                      <span className="text-slate-400">•</span>
                      <span className="text-slate-600">
                        The 5 aspect ratios below are generated exclusively from this cropped area.
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsEditingCrop(true)}
                      className="text-xs font-semibold text-violet-700 hover:text-violet-900 underline cursor-pointer"
                    >
                      Change crop selection
                    </button>
                  </div>
                </div>
              ))}

              {/* Compact Export Settings */}
              <ConversionSettings
                settings={settings}
                setSettings={setSettings}
              />
            </div>

            {/* Lower Section: Horizontal Generated 5 Ratio Outputs & Download Selection */}
            <div className="space-y-6 pt-4">
              <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-6 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2 mb-6">
                  <div>
                    <h3 className="font-semibold text-slate-900 text-base">
                      Generated Ratio Outputs
                    </h3>
                    <p className="text-xs text-slate-500">
                      {currentOutputs.length > 0
                        ? 'All 5 commercial aspect ratios displayed horizontally side-by-side'
                        : 'Your framing will generate all 5 ratios automatically'}
                    </p>
                  </div>
                </div>

                {/* Empty state before Apply & Update or when generating */}
                {isGenerating ? (
                  <div className="py-20 text-center space-y-3 bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
                    <div className="w-12 h-12 mx-auto rounded-full bg-violet-100 flex items-center justify-center text-violet-600 animate-spin">
                      <div className="w-6 h-6 border-2 border-violet-600 border-t-transparent rounded-full" />
                    </div>
                    <p className="text-base font-semibold text-slate-800">
                      Generating 5 Ratios...
                    </p>
                    <p className="text-xs text-slate-500 max-w-md mx-auto">
                      Applying product-safe framing & seamless background continuation.
                    </p>
                  </div>
                ) : currentOutputs.length === 0 ? (
                  <div className="py-20 text-center space-y-3 bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
                    <div className="w-14 h-14 mx-auto rounded-2xl bg-violet-50 text-violet-500 flex items-center justify-center border border-violet-100">
                      <div className="w-7 h-7 border-2 border-dashed border-violet-400 rounded-lg" />
                    </div>
                    <div>
                      <h4 className="text-base font-semibold text-slate-800">
                        Your five images will appear here
                      </h4>
                      <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                        Adjust composition or position above and click <span className="font-semibold text-violet-700">Apply & Update</span> to generate all 5 sizes.
                      </p>
                    </div>
                  </div>
                ) : (
                  /* Horizontal Layout: 5 Ratio Cards Side-by-Side on top, then Choose Images to Download below */
                  <div className="space-y-8">
                    {/* Five Horizontal Ratio Cards (side-by-side left to right, horizontal scroll on small screens) */}
                    <div className="w-full">
                      <div className="overflow-x-auto pb-4 pt-1 -mx-2 px-2">
                        <div className="grid grid-flow-col auto-cols-[280px] sm:auto-cols-[300px] xl:auto-cols-[minmax(0,1fr)] xl:grid-cols-5 gap-4 min-w-max xl:min-w-0">
                          {currentOutputs.map((item) => (
                            <div key={item.safe_key} className="w-full flex">
                              <RatioCard
                                item={item}
                                imageId={activeImage.image_id}
                                onOpenPreviewModal={(it: RatioOutput) => setPreviewModalItem(it)}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Choose Images to Download + Download Selected ZIP (placed BELOW horizontal cards) */}
                    {activeImage && (
                      <DownloadAll
                        key={`${activeImage.image_id}-${revisionMap[activeImage.image_id] ?? 0}`}
                        imageId={activeImage.image_id}
                        outputs={currentOutputs}
                        revision={revisionMap[activeImage.image_id]}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Supported Ratios Specification Table */}
        <section className="pt-8 border-t border-slate-200 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-sm text-slate-900">Standard Output Dimensions</h3>
              <p className="text-xs text-slate-500">
                High-resolution export targets generated with proportional resizing and balanced framing.
              </p>
            </div>
            <span className="text-xs font-mono font-medium text-violet-700 bg-violet-100 px-3 py-1 rounded-full border border-violet-200">
              5 Standard Sizes
            </span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-50 text-slate-600 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Ratio</th>
                  <th className="px-4 py-3">Exact Dimensions</th>
                  <th className="px-4 py-3">Orientation</th>
                  <th className="px-4 py-3">Framing Style</th>
                  <th className="px-4 py-3">Quality</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-slate-800">
                <tr className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-sans font-medium text-slate-900">Square (1:1)</td>
                  <td className="px-4 py-2.5 text-violet-700 font-semibold">2048 × 2048</td>
                  <td className="px-4 py-2.5 text-slate-500">Square</td>
                  <td className="px-4 py-2.5 text-emerald-700 font-sans font-medium">Full-frame, subject centered</td>
                  <td className="px-4 py-2.5 text-slate-500">High Precision Resampling</td>
                </tr>
                <tr className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-sans font-medium text-slate-900">Portrait (4:5)</td>
                  <td className="px-4 py-2.5 text-violet-700 font-semibold">1600 × 2000</td>
                  <td className="px-4 py-2.5 text-slate-500">Portrait</td>
                  <td className="px-4 py-2.5 text-emerald-700 font-sans font-medium">Full-frame prominent framing</td>
                  <td className="px-4 py-2.5 text-slate-500">High Precision Resampling</td>
                </tr>
                <tr className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-sans font-medium text-slate-900">Portrait (3:4)</td>
                  <td className="px-4 py-2.5 text-violet-700 font-semibold">1536 × 2048</td>
                  <td className="px-4 py-2.5 text-slate-500">Portrait</td>
                  <td className="px-4 py-2.5 text-emerald-700 font-sans font-medium">Full-frame prominent framing</td>
                  <td className="px-4 py-2.5 text-slate-500">High Precision Resampling</td>
                </tr>
                <tr className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-sans font-medium text-slate-900">Landscape (16:9)</td>
                  <td className="px-4 py-2.5 text-violet-700 font-semibold">2560 × 1440</td>
                  <td className="px-4 py-2.5 text-slate-500">Landscape</td>
                  <td className="px-4 py-2.5 text-emerald-700 font-sans font-medium">Full-frame panoramic view</td>
                  <td className="px-4 py-2.5 text-slate-500">High Precision Resampling</td>
                </tr>
                <tr className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-sans font-medium text-slate-900">Landscape (5:4)</td>
                  <td className="px-4 py-2.5 text-violet-700 font-semibold">2000 × 1600</td>
                  <td className="px-4 py-2.5 text-slate-500">Landscape</td>
                  <td className="px-4 py-2.5 text-emerald-700 font-sans font-medium">Full-frame balanced proportions</td>
                  <td className="px-4 py-2.5 text-slate-500">High Precision Resampling</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {/* Original Image Framing Editor Modal */}
      {isEditingOriginal && activeImage && (
        <OriginalCropEditor
          originalData={activeImage}
          onClose={() => setIsEditingOriginal(false)}
          onApply={handleUpdateOriginalSuccess}
        />
      )}

      {/* Individual Ratio Crop Modal */}
      {editingItem && activeImage && (
        <CropEditor
          item={editingItem}
          originalData={activeImage}
          onClose={() => setEditingItem(null)}
          onSave={handleUpdateSingleRatio}
        />
      )}

      {/* Full-screen Inspection Modal */}
      {previewModalItem && activeImage && (
        <PreviewModal
          item={previewModalItem}
          imageId={activeImage.image_id}
          onClose={() => setPreviewModalItem(null)}
        />
      )}
    </div>
  );
};

export default App;
