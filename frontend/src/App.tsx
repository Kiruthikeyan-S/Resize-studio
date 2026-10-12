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
import { AlertCircle } from 'lucide-react';

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

    // 2. Automatically generate the 5 aspect ratios right away from this finalized master image
    setIsGenerating(true);
    setErrorMessage(null);

    const activeSettings: ConvertSettings = {
      ...settings,
      image_id: updatedData.image_id,
      mode: 'smart_crop',
    };

    try {
      const response = await api.convertImage(activeSettings);
      setOutputsByModeMap((prev) => ({
        ...prev,
        [updatedData.image_id]: {
          ...(prev[updatedData.image_id] || {}),
          [settings.mode]: response.outputs,
        },
      }));
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

  const convertedImagesCount = images.filter(
    (img) => (outputsByModeMap[img.image_id]?.[settings.mode]?.length || 0) > 0
  ).length;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col selection:bg-violet-600 selection:text-white">
      <Header />

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
            />

            {/* Upper Section: Original Image Framing Editor & Compact Export Settings */}
            <div className="space-y-6 max-w-4xl mx-auto">
              {activeImage && (
                <OriginalCropEditor
                  originalData={activeImage}
                  onApply={handleUpdateOriginalSuccess}
                  onChangeImage={handleReset}
                  inline={true}
                />
              )}

              {/* Compact Export Settings */}
              <ConversionSettings
                settings={settings}
                setSettings={setSettings}
              />
            </div>

            {/* Lower Section: Horizontal Full-Width Generated 5 Ratio Outputs */}
            <div className="space-y-6 pt-4">
              <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-6 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2 mb-6">
                  <div>
                    <h3 className="font-semibold text-slate-900 text-base">
                      Generated Ratio Outputs
                    </h3>
                    <p className="text-xs text-slate-500">
                      {currentOutputs.length > 0
                        ? 'All 5 standard commercial aspect ratios displayed side-by-side'
                        : 'Your framing will generate 5 ratios automatically across the width'}
                    </p>
                  </div>
                  {currentOutputs.length > 0 && (
                    <span className="text-xs font-mono font-medium text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200 self-start sm:self-auto">
                      5 Outputs Ready
                    </span>
                  )}
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
                      Applying your framing adjustments across Square, Portrait (4:5, 3:4), and Landscape (16:9, 5:4).
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
                        Adjust composition or position above and click <span className="font-semibold text-violet-700">Apply & Update</span> to generate all 5 sizes side-by-side.
                      </p>
                    </div>
                  </div>
                ) : (
                  /* Horizontal Layout: ZIP card on top, then all 5 ratio cards side-by-side */
                  <div className="space-y-6">
                    {/* Download ZIP Archive card at top */}
                    {activeImage && (
                      <DownloadAll
                        imageId={activeImage.image_id}
                        totalOutputs={currentOutputs.length}
                        allImageIds={images
                          .filter((img) => (outputsByModeMap[img.image_id]?.[settings.mode]?.length || 0) > 0)
                          .map((img) => img.image_id)}
                        totalConvertedImages={convertedImagesCount}
                        mode={settings.mode}
                      />
                    )}

                    {/* All 5 Ratios in Horizontal Row Grid (5 columns on large screens) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                      {currentOutputs.map((item) => (
                        <div key={item.safe_key} className="w-full">
                          <RatioCard
                            item={item}
                            imageId={activeImage.image_id}
                            onUpdate={handleUpdateSingleRatio}
                            onOpenCropEditor={(it: RatioOutput) => setEditingItem(it)}
                            onOpenPreviewModal={(it: RatioOutput) => setPreviewModalItem(it)}
                          />
                        </div>
                      ))}
                    </div>
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
