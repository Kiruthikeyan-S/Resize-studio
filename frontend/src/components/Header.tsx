import React from 'react';
import { Layers, Home, Activity } from 'lucide-react';
import { UsageDashboardModal } from './UsageDashboardModal';
import { TokenBadge } from './TokenBadge';

interface HeaderProps {
  onGoHome?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onGoHome }) => {
  const [showUsageModal, setShowUsageModal] = React.useState(false);
  return (
    <header className="w-full bg-white border-b border-slate-200 sticky top-0 z-40 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo and Brand - Clickable to return Home */}
        <div
          onClick={onGoHome}
          className={`flex items-center gap-3 ${onGoHome ? 'cursor-pointer select-none group' : ''}`}
          title={onGoHome ? 'Return to Home Screen' : undefined}
        >
          <div className="w-10 h-10 rounded-xl bg-violet-600 group-hover:bg-violet-700 transition-colors flex items-center justify-center shadow-md shadow-violet-200">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight text-slate-900 group-hover:text-violet-700 transition-colors">
                Ratio Studio
              </span>
            </div>
            <p className="text-xs text-slate-500 font-medium">Professional Multi-Ratio Image Converter</p>
          </div>
        </div>

        {/* Right Navigation / Token Quota & Home Screen Option */}
        <div className="flex items-center gap-3">
          <TokenBadge />
          <button
            type="button"
            onClick={() => setShowUsageModal(true)}
            className="py-1.5 px-3 rounded-xl border border-orange-200 hover:border-orange-300 bg-orange-50 hover:bg-orange-100/80 text-orange-800 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shadow-2xs"
            title="View Cloudflare Workers AI Usage & Diagnostics"
          >
            <Activity className="w-3.5 h-3.5 text-orange-600" />
            <span className="hidden sm:inline">AI Usage</span>
            <span className="sm:hidden">AI</span>
          </button>

          {onGoHome && (
            <button
              type="button"
              onClick={onGoHome}
              className="py-1.5 px-3.5 rounded-xl border border-slate-200 hover:border-violet-300 bg-slate-50 hover:bg-violet-50 text-slate-700 hover:text-violet-700 text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer shadow-2xs"
              title="Return to Home Screen to upload new images"
            >
              <Home className="w-4 h-4 text-violet-600" />
              <span>Home Screen</span>
            </button>
          )}
        </div>
      </div>
      <UsageDashboardModal
        isOpen={showUsageModal}
        onClose={() => setShowUsageModal(false)}
      />
    </header>
  );
};

export default Header;
