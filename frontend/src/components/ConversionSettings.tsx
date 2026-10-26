import React from 'react';
import { Sliders } from 'lucide-react';
import type { ConvertSettings } from '../services/api';

interface ConversionSettingsProps {
  settings: ConvertSettings;
  setSettings: React.Dispatch<React.SetStateAction<ConvertSettings>>;
}

export const ConversionSettings: React.FC<ConversionSettingsProps> = ({
  settings,
  setSettings,
}) => {
  const formats: ('jpeg' | 'png' | 'webp')[] = ['jpeg', 'png', 'webp'];

  return (
    <div className="w-full bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 space-y-4 shadow-xs">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-violet-50 text-violet-600 flex items-center justify-center">
            <Sliders className="w-3.5 h-3.5" />
          </div>
          <h3 className="font-semibold text-slate-900 text-sm">Export Settings</h3>
        </div>
        <span className="text-[11px] text-slate-500 font-medium">
          Applied automatically to all 5 ratios
        </span>
      </div>

      {/* Export Format & Quality Controls in Compact Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Export Format */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-600">
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

        {/* Standard Fit Mode */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-600">
            Standard Fit Mode
          </label>
          <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200">
            {[
              { id: 'stretch', label: 'Stretch' },
              { id: 'contain', label: 'Contain' },
              { id: 'cover', label: 'Cover' },
            ].map(({ id, label }) => {
              const active = (settings.standard_fit || 'stretch') === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSettings((prev) => ({ ...prev, standard_fit: id as any }))}
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                    active
                      ? 'bg-white text-violet-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  title={
                    id === 'stretch'
                      ? 'Fill canvas (allows stretch)'
                      : id === 'contain'
                      ? 'Preserve complete image with clean background'
                      : 'Crop to fill canvas without distortion'
                  }
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Quality Slider */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center">
            <label className="text-xs font-semibold text-slate-600">
              Output Quality
            </label>
            <span className="text-xs font-bold text-violet-700 font-mono">{settings.quality}%</span>
          </div>
          <input
            type="range"
            min={60}
            max={100}
            value={settings.quality}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, quality: Number(e.target.value) }))
            }
            className="w-full accent-violet-600 bg-slate-200 h-2 rounded-lg cursor-pointer"
          />
        </div>

        {/* Method B Foreground Choice */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center">
            <label className="text-xs font-semibold text-slate-600">
              Method B Foreground
            </label>
            <span className="text-[10px] text-slate-400 font-normal">Method A untouched</span>
          </div>
          <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200">
            {[
              { id: 'original', label: 'Original (100%)' },
              { id: 'enhanced', label: 'Real-ESRGAN' },
            ].map(({ id, label }) => {
              const active = (settings.foreground_mode || (settings.enhance_foreground ? 'enhanced' : 'original')) === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() =>
                    setSettings((prev) => ({
                      ...prev,
                      foreground_mode: id as 'original' | 'enhanced',
                      enhance_foreground: id === 'enhanced',
                    }))
                  }
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                    active
                      ? 'bg-white text-violet-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  title={
                    id === 'original'
                      ? 'Preserves 100% of approved pixels with zero alteration'
                      : 'CNN Real-ESRGAN super-resolution for crisper apparent detail'
                  }
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Detail Enhancement / Sharpen */}
        <div className="space-y-1.5 flex flex-col justify-end">
          <label className="flex items-center gap-2 p-2 rounded-xl bg-slate-50 border border-slate-200 cursor-pointer hover:bg-slate-100/70 transition-colors">
            <input
              type="checkbox"
              checked={settings.sharpen}
              onChange={(e) =>
                setSettings((prev) => ({ ...prev, sharpen: e.target.checked }))
              }
              className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500 cursor-pointer"
            />
            <span className="text-xs font-medium text-slate-700">Sharpen Output Details</span>
          </label>
        </div>
      </div>
    </div>
  );
};
