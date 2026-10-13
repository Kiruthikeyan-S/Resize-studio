import React, { useMemo, useState } from 'react';
import { Archive, Download, Loader2, ListChecks, AlertCircle } from 'lucide-react';
import { api, RATIO_SIZE_TABLE, SIZE_KEYS } from '../services/api';
import type { RatioOutput, SizeKey } from '../services/api';

interface DownloadAllProps {
  imageId: string;
  /** Latest generated outputs (each carries its Large/Medium/Small variants). */
  outputs: RatioOutput[];
  /** Generation revision the outputs belong to; sent so the server rejects stale selections. */
  revision?: number;
}

const SIZE_HEADERS: Record<SizeKey, string> = { large: 'Large', medium: 'Medium', small: 'Small' };
const selId = (safeKey: string, size: SizeKey) => `${safeKey}:${size}`;

/**
 * Selection table + custom ZIP download.
 * Selection only controls which already-generated files are packaged; nothing is regenerated.
 * The parent remounts this component (via key) for every new generation, which clears the selection.
 */
export const DownloadAll: React.FC<DownloadAllProps> = ({ imageId, outputs, revision }) => {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only sizes the backend actually generated for the current revision are selectable.
  const available = useMemo(() => {
    const ids = new Set<string>();
    outputs.forEach((o) => o.variants?.forEach((v) => ids.add(v.selection_id)));
    return ids;
  }, [outputs]);

  const allIds = useMemo(
    () => RATIO_SIZE_TABLE.flatMap((r) => SIZE_KEYS.map((s) => selId(r.safe_key, s))).filter((id) => available.has(id)),
    [available]
  );

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const rowIds = (safeKey: string) => SIZE_KEYS.map((s) => selId(safeKey, s)).filter((id) => available.has(id));

  const toggleRow = (safeKey: string) =>
    setSelected((prev) => {
      const ids = rowIds(safeKey);
      const next = new Set(prev);
      const full = ids.every((id) => next.has(id));
      ids.forEach((id) => (full ? next.delete(id) : next.add(id)));
      return next;
    });

  const selectAll = () => setSelected(new Set(allIds));
  const clearAll = () => setSelected(new Set());

  const count = selected.size;

  const handleDownload = async () => {
    if (count === 0 || isDownloading) return;
    setIsDownloading(true);
    setError(null);
    try {
      // Preserve table order so the manifest/ZIP order is predictable.
      const ordered = allIds.filter((id) => selected.has(id));
      const blob = await api.downloadSelectedZip(imageId, ordered, revision);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'ratio-studio-selected.zip';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Failed to create ZIP.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="w-full bg-white border border-violet-200/80 rounded-2xl shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-4 sm:p-5 border-b border-slate-100 bg-gradient-to-r from-violet-50 via-white to-slate-50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-100 border border-violet-200 flex items-center justify-center shrink-0">
            <ListChecks className="w-5 h-5 text-violet-600" />
          </div>
          <div>
            <h4 className="font-semibold text-sm text-slate-900">Choose Images to Download</h4>
            <p className="text-xs text-slate-500">Pick any combination of the {allIds.length} generated sizes.</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={selectAll}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200 cursor-pointer"
          >
            Select All
          </button>
          <button
            type="button"
            onClick={clearAll}
            disabled={count === 0}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Selection table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
            <tr>
              <th className="px-4 py-2.5">Ratio</th>
              {SIZE_KEYS.map((s) => (
                <th key={s} className="px-4 py-2.5">{SIZE_HEADERS[s]}</th>
              ))}
              <th className="px-4 py-2.5 text-center">All sizes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {RATIO_SIZE_TABLE.map((row) => {
              const ids = rowIds(row.safe_key);
              const rowFull = ids.length > 0 && ids.every((id) => selected.has(id));
              return (
                <tr key={row.safe_key} className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-medium text-slate-900 whitespace-nowrap">{row.name}</td>
                  {SIZE_KEYS.map((s) => {
                    const id = selId(row.safe_key, s);
                    const [w, h] = row.sizes[s];
                    const enabled = available.has(id);
                    return (
                      <td key={s} className="px-4 py-2.5">
                        <label className={`flex items-center gap-2 ${enabled ? 'cursor-pointer' : 'opacity-40 cursor-not-allowed'}`}>
                          <input
                            type="checkbox"
                            checked={selected.has(id)}
                            disabled={!enabled}
                            onChange={() => toggle(id)}
                            aria-label={`${row.name} ${SIZE_HEADERS[s]} ${w}×${h}`}
                            className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500"
                          />
                          <span className="font-mono text-slate-700 whitespace-nowrap">{w} × {h}</span>
                        </label>
                      </td>
                    );
                  })}
                  <td className="px-4 py-2.5 text-center">
                    <input
                      type="checkbox"
                      checked={rowFull}
                      disabled={ids.length === 0}
                      onChange={() => toggleRow(row.safe_key)}
                      aria-label={`Select all sizes for ${row.name}`}
                      className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500 cursor-pointer"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer: live count + ZIP button */}
      <div className="p-4 sm:p-5 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-800" aria-live="polite">
            {count} of {allIds.length} images selected
          </p>
          {error && (
            <p className="text-[11px] text-rose-600 flex items-center gap-1">
              <AlertCircle className="w-3 h-3 shrink-0" />
              <span>{error}</span>
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={handleDownload}
          disabled={count === 0 || isDownloading}
          className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 active:scale-[0.99] text-xs font-semibold text-white shadow-xs flex items-center justify-center gap-2 transition-all whitespace-nowrap cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isDownloading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Packaging...</span>
            </>
          ) : (
            <>
              {count > 0 ? <Download className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
              <span>Download Selected ZIP{count > 0 ? ` (${count})` : ''}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default DownloadAll;
