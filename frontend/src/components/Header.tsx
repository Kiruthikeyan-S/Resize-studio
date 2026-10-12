import React from 'react';
import { Layers } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="w-full bg-white border-b border-slate-200 sticky top-0 z-40 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo and Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-600 flex items-center justify-center shadow-md shadow-violet-200">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight text-slate-900">Ratio Studio</span>
            </div>
            <p className="text-xs text-slate-500 font-medium">Professional Multi-Ratio Image Converter</p>
          </div>
        </div>

      </div>
    </header>
  );
};
