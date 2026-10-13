import React, { useMemo, useState } from 'react';
import { Archive, Download, Loader2, ListChecks, AlertCircle, Check } from 'lucide-react';
import { api, RATIO_SIZE_TABLE, SIZE_KEYS } from '../services/api';
import type { RatioOutput, SizeKey, ComparisonRow } from '../services/api';

interface DownloadAllProps {
  imageId: string;
  /** Latest generated outputs (each carries its Large/Medium/Small variants). */
  outputs: RatioOutput[];
  /** Generation revision the outputs belong to; sent so the server rejects stale selections. */
  revision?: number;
  /** Comparison rows if in comparison mode. */
  comparisonRows?: ComparisonRow[];
  /** User preferred method per ratio safe_key ('standard' | 'ai'). */
  preferences?: Record<string, 'standard' | 'ai'>;
}

const SIZE_HEADERS: Record<SizeKey, string> = { large: 'Large', medium: 'Medium', small: 'Small' };

export const DownloadAll: React.FC<DownloadAllProps> = ({
  imageId,
  outputs,
  revision,
  comparisonRows,
  preferences = {},
}) => {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const isComparison = Boolean(comparisonRows && comparisonRows.length > 0);

  const prevPrefsRef = React.useRef<string>('');
  const prevRevRef = React.useRef<number | undefined>(undefined);

  // Collect all outputs to inspect (either from comparisonRows or from flat outputs)
  const allOutputs = useMemo(() => {
    if (isComparison && comparisonRows) {
      const list: RatioOutput[] = [];
      comparisonRows.forEach((r) => {
        if (r.standard) list.push({ ...r.standard, method: 'standard' });
        if (r.ai) list.push({ ...r.ai, method: 'ai' });
      });
      return list;
    }
    return outputs;
  }, [isComparison, comparisonRows, outputs]);

  // Set of selection_ids that were actually generated and ready
  const available = useMemo(() => {
    const ids = new Set<string>();
    allOutputs.forEach((o) => {
      // Disallow unavailable or failed AI outputs
      if (o.status === 'unavailable' || o.status === 'failed') return;
      o.variants?.forEach((v) => {
        ids.add(v.selection_id);
        if (v.legacy_selection_id) ids.add(v.legacy_selection_id);
      });
    });
    return ids;
  }, [allOutputs]);

  // Canonical list of selectable IDs
  const allIds = useMemo(() => {
    const ids: string[] = [];
    if (isComparison) {
      RATIO_SIZE_TABLE.forEach((r) => {
        (['standard', 'ai'] as const).forEach((m) => {
          SIZE_KEYS.forEach((s) => {
            const sid = `${m}:${r.safe_key}:${s}`;
            if (available.has(sid)) ids.push(sid);
          });
        });
      });
    } else {
      RATIO_SIZE_TABLE.forEach((r) => {
        SIZE_KEYS.forEach((s) => {
          const sid = `${r.safe_key}:${s}`;
          const stdId = `standard:${r.safe_key}:${s}`;
          if (available.has(sid)) ids.push(sid);
          else if (available.has(stdId)) ids.push(stdId);
        });
      });
    }
    return ids;
  }, [isComparison, available]);

  // Automatically select the 15 preferred items by default, and update when preference toggles change
  React.useEffect(() => {
    if (available.size === 0) return;
    const prefsKey = JSON.stringify(preferences);
    if (prefsKey === prevPrefsRef.current && revision === prevRevRef.current) {
      return;
    }
    prevPrefsRef.current = prefsKey;
    prevRevRef.current = revision;

    const next = new Set<string>();
    if (isComparison) {
      RATIO_SIZE_TABLE.forEach((r) => {
        const pref = preferences[r.safe_key] || 'standard';
        SIZE_KEYS.forEach((s) => {
          const sid = `${pref}:${r.safe_key}:${s}`;
          if (available.has(sid)) {
            next.add(sid);
          } else {
            const fallbackSid = `standard:${r.safe_key}:${s}`;
            if (available.has(fallbackSid)) next.add(fallbackSid);
          }
        });
      });
    } else {
      RATIO_SIZE_TABLE.forEach((r) => {
        SIZE_KEYS.forEach((s) => {
          const sid = `${r.safe_key}:${s}`;
          const stdId = `standard:${r.safe_key}:${s}`;
          if (available.has(sid)) next.add(sid);
          else if (available.has(stdId)) next.add(stdId);
        });
      });
    }
    setSelected(next);
  }, [available, isComparison, preferences, revision]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(allIds));
  const clearAll = () => setSelected(new Set());

  // Convenience: Select preferred versions across all ratios
  const selectPreferred = (largeOnly = false) => {
    const next = new Set<string>();
    RATIO_SIZE_TABLE.forEach((r) => {
      const pref = preferences[r.safe_key] || 'standard';
      const sizesToSelect = largeOnly ? (['large'] as const) : SIZE_KEYS;
      sizesToSelect.forEach((s) => {
        const sid = `${pref}:${r.safe_key}:${s}`;
        if (available.has(sid)) {
          next.add(sid);
        } else {
          // Fall back to standard if preferred AI is not available
          const fallbackSid = `standard:${r.safe_key}:${s}`;
          if (available.has(fallbackSid)) next.add(fallbackSid);
        }
      });
    });
    setSelected(next);
  };

  // Convenience: Select all Standard (15)
  const selectAllStandard = () => {
    const next = new Set<string>();
    RATIO_SIZE_TABLE.forEach((r) => {
      SIZE_KEYS.forEach((s) => {
        const sid = `${r.safe_key}:${s}`;
        const stdSid = `standard:${r.safe_key}:${s}`;
        if (available.has(stdSid)) next.add(stdSid);
        else if (available.has(sid)) next.add(sid);
      });
    });
    setSelected(next);
  };

  // Convenience: Select all AI (15)
  const selectAllAI = () => {
    const next = new Set<string>();
    RATIO_SIZE_TABLE.forEach((r) => {
      SIZE_KEYS.forEach((s) => {
        const aiSid = `ai:${r.safe_key}:${s}`;
        if (available.has(aiSid)) next.add(aiSid);
      });
    });
    setSelected(next);
  };

  const count = selected.size;

  const handleDownload = async () => {
    if (count === 0 || isDownloading) return;
    setIsDownloading(true);
    setError(null);
    try {
      const ordered = allIds.filter((id) => selected.has(id));
      const blob = await api.downloadSelectedZip(imageId, ordered, revision);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ratio-studio-${isComparison ? 'comparison' : 'selected'}.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || 'Failed to create ZIP archive.');
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
            <p className="text-xs text-slate-500">
              {isComparison
                ? 'Select any combination of Standard (Without AI) and AI Enhanced sizes.'
                : `Pick any combination of the ${allIds.length} generated sizes.`}
            </p>
          </div>
        </div>

        {/* Quick Selection Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {isComparison && (
            <>
              <button
                type="button"
                onClick={() => selectPreferred(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-600 hover:bg-violet-700 text-white shadow-2xs cursor-pointer flex items-center gap-1"
                title="Select all sizes for the chosen preferred method of each ratio"
              >
                <Check className="w-3.5 h-3.5" />
                <span>Select Preferred (15)</span>
              </button>
              <button
                type="button"
                onClick={selectAllStandard}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 cursor-pointer"
              >
                All Standard (15)
              </button>
              <button
                type="button"
                onClick={selectAllAI}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 cursor-pointer"
              >
                All AI (15)
              </button>
            </>
          )}

          {!isComparison && (
            <button
              type="button"
              onClick={selectAll}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-violet-50 hover:bg-violet-100 text-violet-700 border border-violet-200 cursor-pointer"
            >
              Select All
            </button>
          )}

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

      {/* Selection Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
            <tr>
              <th className="px-4 py-2.5">Ratio</th>
              {isComparison && <th className="px-4 py-2.5">Method</th>}
              {SIZE_KEYS.map((s) => (
                <th key={s} className="px-4 py-2.5">
                  {SIZE_HEADERS[s]}
                </th>
              ))}
              <th className="px-4 py-2.5 text-center">Row</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {RATIO_SIZE_TABLE.map((row) => {
              const pref = preferences[row.safe_key] || 'standard';

              if (isComparison) {
                return (['standard', 'ai'] as const).map((method) => {
                  const isPreferredRow = pref === method;
                  const rowIds = SIZE_KEYS.map((s) => `${method}:${row.safe_key}:${s}`);
                  const rowAvailable = rowIds.filter((id) => available.has(id));
                  const rowFull =
                    rowAvailable.length > 0 && rowAvailable.every((id) => selected.has(id));

                  const toggleRow = () => {
                    setSelected((prev) => {
                      const next = new Set(prev);
                      const allSelected = rowAvailable.every((id) => next.has(id));
                      rowAvailable.forEach((id) =>
                        allSelected ? next.delete(id) : next.add(id)
                      );
                      return next;
                    });
                  };

                  return (
                    <tr
                      key={`${row.safe_key}-${method}`}
                      className={`hover:bg-slate-50/70 transition-colors ${
                        isPreferredRow ? 'bg-violet-50/20' : ''
                      }`}
                    >
                      {/* Ratio Name (only shown on standard row or visually grouped) */}
                      <td className="px-4 py-2.5 font-medium text-slate-900 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span>{row.name}</span>
                          {isPreferredRow && (
                            <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-violet-100 text-violet-700">
                              Preferred
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Method Column */}
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <span
                          className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border ${
                            method === 'ai'
                              ? 'bg-purple-50 text-purple-700 border-purple-200'
                              : 'bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                        >
                          {method === 'ai' ? 'AI Enhanced' : 'Standard'}
                        </span>
                      </td>

                      {/* Size Checkboxes */}
                      {SIZE_KEYS.map((s) => {
                        const id = `${method}:${row.safe_key}:${s}`;
                        const [w, h] = row.sizes[s];
                        const enabled = available.has(id);
                        return (
                          <td key={s} className="px-4 py-2.5">
                            <label
                              className={`flex items-center gap-2 ${
                                enabled ? 'cursor-pointer' : 'opacity-40 cursor-not-allowed'
                              }`}
                            >
                              <input
                                type="checkbox"
                                checked={selected.has(id)}
                                disabled={!enabled}
                                onChange={() => toggle(id)}
                                aria-label={`${row.name} ${method} ${SIZE_HEADERS[s]} ${w}×${h}`}
                                className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500 cursor-pointer"
                              />
                              <span className="font-mono text-slate-700 whitespace-nowrap">
                                {w} × {h}
                              </span>
                            </label>
                          </td>
                        );
                      })}

                      {/* Select All for this method row */}
                      <td className="px-4 py-2.5 text-center">
                        <input
                          type="checkbox"
                          checked={rowFull}
                          disabled={rowAvailable.length === 0}
                          onChange={toggleRow}
                          aria-label={`Select all ${method} sizes for ${row.name}`}
                          className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500 cursor-pointer"
                        />
                      </td>
                    </tr>
                  );
                });
              }

              // Non-comparison single mode row
              const rowIds = SIZE_KEYS.map((s) => `${row.safe_key}:${s}`).filter((id) =>
                available.has(id)
              );
              const rowFull = rowIds.length > 0 && rowIds.every((id) => selected.has(id));

              const toggleRow = () => {
                setSelected((prev) => {
                  const next = new Set(prev);
                  const full = rowIds.every((id) => next.has(id));
                  rowIds.forEach((id) => (full ? next.delete(id) : next.add(id)));
                  return next;
                });
              };

              return (
                <tr key={row.safe_key} className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 font-medium text-slate-900 whitespace-nowrap">
                    {row.name}
                  </td>
                  {SIZE_KEYS.map((s) => {
                    const id = `${row.safe_key}:${s}`;
                    const [w, h] = row.sizes[s];
                    const enabled = available.has(id);
                    return (
                      <td key={s} className="px-4 py-2.5">
                        <label
                          className={`flex items-center gap-2 ${
                            enabled ? 'cursor-pointer' : 'opacity-40 cursor-not-allowed'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selected.has(id)}
                            disabled={!enabled}
                            onChange={() => toggle(id)}
                            aria-label={`${row.name} ${SIZE_HEADERS[s]} ${w}×${h}`}
                            className="w-4 h-4 rounded text-violet-600 border-slate-300 focus:ring-violet-500 cursor-pointer"
                          />
                          <span className="font-mono text-slate-700 whitespace-nowrap">
                            {w} × {h}
                          </span>
                        </label>
                      </td>
                    );
                  })}
                  <td className="px-4 py-2.5 text-center">
                    <input
                      type="checkbox"
                      checked={rowFull}
                      disabled={rowIds.length === 0}
                      onChange={toggleRow}
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

      {/* Footer */}
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
              <span>Packaging ZIP...</span>
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
