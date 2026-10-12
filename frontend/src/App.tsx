import React, { useState } from 'react';
import { Header } from './components/Header';
import { ImageUploader } from './components/ImageUploader';
import { OriginalPreview } from './components/OriginalPreview';
import { ConversionSettings } from './components/ConversionSettings';
import { PreviewGrid } from './components/PreviewGrid';
import { DownloadAll } from './components/DownloadAll';
import { CropEditor } from './components/CropEditor';
import { PreviewModal } from './components/PreviewModal';
import type { UploadResponse, RatioOutput, ConvertSettings } from './services/api';
import { api } from './services/api';
import { AlertCircle } from 'lucide-react';

export const App: React.FC = () => {
  const [originalData, setOriginalData] = useState<UploadResponse | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [outputs, setOutputs] = useState<RatioOutput[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState<RatioOutput | null>(null);
  const [previewModalItem, setPreviewModalItem] = useState<RatioOutput | null>(null);

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

  const handleUploadSuccess = (data: UploadResponse) => {
    setOriginalData(data);
    setOutputs([]);
    setErrorMessage(null);
    setSettings((prev) => ({
      ...prev,
      image_id: data.image_id,
    }));
  };

  const handleReset = async () => {
    if (originalData) {
      try {
        await api.deleteSession(originalData.image_id);
      } catch (err) {
        // Ignore session delete errors on reset
      }
    }
    setOriginalData(null);
    setOutputs([]);
    setErrorMessage(null);
    setEditingItem(null);
    setPreviewModalItem(null);
  };

  const handleGenerate = async (customMode?: 'smart_crop' | 'safe_fit' | 'manual_crop') => {
    if (!originalData) return;
    setIsGenerating(true);
    setErrorMessage(null);

    const activeSettings = {
      ...settings,
      image_id: originalData.image_id,
      mode: customMode || settings.mode,
    };

    try {
      const response = await api.convertImage(activeSettings);
      setOutputs(response.outputs);
    } catch (err: any) {
      setErrorMessage(
        err.response?.data?.detail || err.message || 'Failed to generate aspect ratios.'
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSwitchToSafeFit = () => {
    setSettings((prev) => ({ ...prev, mode: 'safe_fit' }));
    handleGenerate('safe_fit');
  };

  const handleUpdateSingleRatio = (updated: RatioOutput) => {
    setOutputs((prev) =>
      prev.map((item) => (item.safe_key === updated.safe_key ? updated : item))
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col selection:bg-violet-600 selection:text-white">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 space-y-8">
        {/* Intro Hero */}
        <div className="text-center max-w-2xl mx-auto space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
            Professional Image Ratio Converter
          </h1>
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

        {/* Upload or Original Image Preview Section */}
        {!originalData ? (
          <div className="max-w-2xl mx-auto">
            <ImageUploader
              onUploadSuccess={handleUploadSuccess}
              isLoading={isUploading}
              setIsLoading={setIsUploading}
            />
          </div>
        ) : (
          <div className="space-y-6">
            <OriginalPreview originalData={originalData} onReset={handleReset} />

            <ConversionSettings
              settings={settings}
              setSettings={setSettings}
              onGenerate={() => handleGenerate()}
              isGenerating={isGenerating}
            />

            {/* Output Grid and ZIP Download */}
            {outputs.length > 0 && (
              <div className="space-y-6 pt-4 animate-fade-in">
                <DownloadAll
                  imageId={originalData.image_id}
                  totalOutputs={outputs.length}
                />

                <PreviewGrid
                  outputs={outputs}
                  imageId={originalData.image_id}
                  onUpdateRatio={handleUpdateSingleRatio}
                  onOpenCropEditor={(item) => setEditingItem(item)}
                  onOpenPreviewModal={(item) => setPreviewModalItem(item)}
                  onSwitchToSafeFit={handleSwitchToSafeFit}
                />
              </div>
            )}
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

      {/* Interactive Crop Modal */}
      {editingItem && (
        <CropEditor
          item={editingItem}
          originalData={originalData}
          onClose={() => setEditingItem(null)}
          onSave={handleUpdateSingleRatio}
        />
      )}

      {/* Full-screen Inspection Modal */}
      {previewModalItem && originalData && (
        <PreviewModal
          item={previewModalItem}
          imageId={originalData.image_id}
          onClose={() => setPreviewModalItem(null)}
        />
      )}

    </div>
  );
};

export default App;
