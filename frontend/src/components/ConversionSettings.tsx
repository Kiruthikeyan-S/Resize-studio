import React from 'react';
import { Sliders, Maximize2, Shield, Play, Palette, Check } from 'lucide-react';
import type { ConvertSettings } from '../services/api';

interface ConversionSettingsProps {
  settings: ConvertSettings;
  setSettings: React.Dispatch<React.SetStateAction<ConvertSettings>>;
  onGenerate: () => void;
  isGenerating: boolean;
}

export const ConversionSettings: React.FC<ConversionSettingsProps> = ({
  settings,
  setSettings,
  onGenerate,
  isGenerating,
}) => {
  const options = [
    {
      id: 'smart_crop',
      title: 'Option A — Full-Frame Photo',
      badge: 'Recommended',
      description: 'Makes the image fill the frame so the subject appears large, prominent, and visually striking.',
      note: 'Best for attractive product photography and social media. Peripheral background may be trimmed.',
      icon: Maximize2,
    },
    {
      id: 'safe_fit',
      title: 'Option B — Entire Image Visible',
      badge: '100% Preserved',
      description: 'Keeps the complete original image fully visible. No important content or edges are cut.',
      note: 'Best when the full subject and wide environment must remain visible. Clean padding is added.',
      icon: Shield,
    },
  ];

  const formats: ('jpeg' | 'png' | 'webp')[] = ['jpeg', 'png', 'webp'];
  const colorPresets = [
    { name: 'Pure White', hex: '#FFFFFF' },
    { name: 'Light Gray', hex: '#F1F5F9' },
    { name: 'Dark Slate', hex: '#1E293B' },
    { name: 'Pitch Black', hex: '#000000' },
  ];

  return (
    <div className="w-full bg-white border border-slate-200 rounded-2xl p-5 sm:p-6 space-y-6 shadow-xs">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center">
            <Sliders className="w-4 h-4" />
          </div>
          <h3 className="font-semibold text-slate-900 text-base">Choose Output Style</h3>
        </div>
        <span className="text-xs text-slate-500 bg-slate-100 px-3 py-1 rounded-full font-medium border border-slate-200">
          Step 2 of 2
        </span>
      </div>

      {/* Two Clear Selectable Options */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Framing Style
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {options.map((opt) => {
            const Icon = opt.icon;
            const isSelected = settings.mode === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setSettings((prev) => ({ ...prev, mode: opt.id as any }))}
                className={`relative text-left p-5 rounded-2xl border-2 transition-all flex flex-col justify-between cursor-pointer ${
                  isSelected
                    ? 'border-violet-600 bg-violet-50/40 shadow-sm shadow-violet-100'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                          isSelected ? 'bg-violet-600 text-white' : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                      </div>
                      <span className="font-bold text-sm text-slate-900">{opt.title}</span>
                    </div>
                    <span
                      className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${
                        isSelected
                          ? 'text-violet-700 bg-violet-100 border-violet-200'
                          : 'text-slate-600 bg-slate-100 border-slate-200'
                      }`}
                    >
                      {opt.badge}
                    </span>
                  </div>

                  <p className="text-xs text-slate-700 font-medium leading-relaxed mb-2">
                    {opt.description}
                  </p>
                  <p className="text-[11px] text-slate-500 leading-normal">
                    {opt.note}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-end">
                  <span
                    className={`text-xs font-semibold flex items-center gap-1.5 ${
                      isSelected ? 'text-violet-700' : 'text-slate-400'
                    }`}
                  >
                    {isSelected ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-violet-600" /> Selected
                      </>
                    ) : (
                      'Select this option'
                    )}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Padding Color Chooser (Available for Option B — Entire Image Visible) */}
      {settings.mode === 'safe_fit' && (
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-800 flex items-center gap-2">
              <Palette className="w-3.5 h-3.5 text-violet-600" /> Padding Background Color
            </span>
            <span className="text-[11px] text-slate-500">
              Clean studio border around original image
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-4 pt-1">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-600">Preset:</span>
              <div className="flex items-center gap-2">
                {colorPresets.map((color) => (
                  <button
                    key={color.hex}
                    type="button"
                    onClick={() =>
                      setSettings((prev) => ({
                        ...prev,
                        bg_color_hex: color.hex,
                        is_transparent: false,
                      }))
                    }
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-all flex items-center gap-1.5 ${
                      !settings.is_transparent &&
                      settings.bg_color_hex.toLowerCase() === color.hex.toLowerCase()
                        ? 'border-violet-600 bg-white text-violet-700 shadow-xs'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <span
                      className="w-3 h-3 rounded-full border border-slate-300"
                      style={{ backgroundColor: color.hex }}
                    />
                    <span>{color.name}</span>
                  </button>
                ))}

                <div className="flex items-center gap-1 ml-2 pl-2 border-l border-slate-200">
                  <span className="text-xs text-slate-500">Custom:</span>
                  <input
                    type="color"
                    value={settings.bg_color_hex}
                    onChange={(e) =>
                      setSettings((prev) => ({
                        ...prev,
                        bg_color_hex: e.target.value,
                        is_transparent: false,
                      }))
                    }
                    className="w-7 h-7 rounded border border-slate-200 bg-white cursor-pointer"
                    title="Custom Color"
                  />
                </div>
              </div>
            </div>

            {/* Transparent Option for PNG / WebP */}
            <label className="flex items-center gap-2 cursor-pointer ml-auto text-xs text-slate-700 font-medium">
              <input
                type="checkbox"
                checked={settings.is_transparent}
                onChange={(e) =>
                  setSettings((prev) => ({
                    ...prev,
                    is_transparent: e.target.checked,
                  }))
                }
                className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500"
              />
              <span>Transparent Padding (PNG/WebP)</span>
            </label>
          </div>
        </div>
      )}

      {/* Export Format & Quality Controls */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
        {/* Export Format */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Export Format
          </label>
          <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200">
            {formats.map((fmt) => (
              <button
                key={fmt}
                type="button"
                onClick={() => setSettings((prev) => ({ ...prev, export_format: fmt }))}
                className={`flex-1 py-1.5 text-xs font-semibold uppercase rounded-lg transition-colors cursor-pointer ${
                  settings.export_format === fmt
                    ? 'bg-white text-violet-700 shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {fmt}
              </button>
            ))}
          </div>
        </div>

        {/* Quality Slider */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Output Quality
            </label>
            <span className="text-xs font-bold text-slate-800">{settings.quality}%</span>
          </div>
          <input
            type="range"
            min={50}
            max={100}
            value={settings.quality}
            disabled={settings.export_format === 'png'}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, quality: parseInt(e.target.value, 10) }))
            }
            className="w-full accent-violet-600 bg-slate-200 h-2 rounded-lg cursor-pointer disabled:opacity-40"
          />
        </div>

        {/* Sharpen Toggle */}
        <div className="space-y-1.5 flex flex-col justify-end">
          <label className="flex items-center gap-2.5 p-2.5 rounded-xl bg-slate-50 border border-slate-200 cursor-pointer hover:border-slate-300 transition-colors">
            <input
              type="checkbox"
              checked={settings.sharpen}
              onChange={(e) =>
                setSettings((prev) => ({ ...prev, sharpen: e.target.checked }))
              }
              className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500"
            />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-900">Enhance Details</span>
              <span className="text-[10px] text-slate-500">Subtle edge sharpening</span>
            </div>
          </label>
        </div>

        {/* Denoise Toggle */}
        <div className="space-y-1.5 flex flex-col justify-end">
          <label className="flex items-center gap-2.5 p-2.5 rounded-xl bg-slate-50 border border-slate-200 cursor-pointer hover:border-slate-300 transition-colors">
            <input
              type="checkbox"
              checked={settings.denoise}
              onChange={(e) =>
                setSettings((prev) => ({ ...prev, denoise: e.target.checked }))
              }
              className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500"
            />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-slate-900">Reduce Noise</span>
              <span className="text-[10px] text-slate-500">Smooth color gradients</span>
            </div>
          </label>
        </div>
      </div>

      {/* Action CTA */}
      <div className="pt-2">
        <button
          type="button"
          onClick={onGenerate}
          disabled={isGenerating}
          className="w-full py-3.5 px-6 rounded-xl bg-violet-600 hover:bg-violet-700 text-white font-semibold text-sm shadow-md shadow-violet-200 flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50 disabled:pointer-events-none active:scale-[0.99]"
        >
          {isGenerating ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Generating 5 Aspect Ratios...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>Generate 5 Aspect Ratios</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
