import React from 'react';
import { DRCFinding } from '../types';
import { ShieldCheck, AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';

interface DRCReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  auditPassed: boolean;
  errorsCount: number;
  warningsCount: number;
  infoCount: number;
  parityMatch: boolean;
  findings: DRCFinding[];
  schCount: number;
  pcbCount: number;
}

export const DRCReportModal: React.FC<DRCReportModalProps> = ({
  isOpen,
  onClose,
  auditPassed,
  errorsCount,
  warningsCount,
  infoCount,
  parityMatch,
  findings,
  schCount,
  pcbCount,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-700 w-full max-w-3xl rounded-xl shadow-2xl p-6 flex flex-col max-h-[85vh] text-zinc-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                auditPassed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
              }`}
            >
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <span>KiCad Topological DRC & Quality Gate</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded font-mono ${
                    auditPassed
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                  }`}
                >
                  {auditPassed ? 'PASSED (0 ERRORS)' : `${errorsCount} ERRORS`}
                </span>
              </h2>
              <p className="text-xs text-zinc-400 mt-0.5 font-mono">
                Verification of Rules R001–R014 & 100% SCH ↔ PCB Reference Parity
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white font-bold text-xl p-1"
          >
            ×
          </button>
        </div>

        {/* Quality Metrics Strip */}
        <div className="grid grid-cols-4 gap-3 mb-4">
          <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg">
            <div className="text-[10px] font-mono uppercase text-zinc-500">SCH ↔ PCB Parity</div>
            <div className="text-base font-bold text-emerald-400 font-mono mt-0.5 flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4" />
              <span>{parityMatch ? '100% MATCH' : 'MISMATCH'}</span>
            </div>
            <div className="text-[10px] text-zinc-400 mt-0.5">
              {schCount} SCH / {pcbCount} PCB symbols
            </div>
          </div>

          <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg">
            <div className="text-[10px] font-mono uppercase text-zinc-500">Errors</div>
            <div
              className={`text-base font-bold font-mono mt-0.5 ${
                errorsCount === 0 ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {errorsCount}
            </div>
            <div className="text-[10px] text-zinc-400 mt-0.5">Topological blockers</div>
          </div>

          <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg">
            <div className="text-[10px] font-mono uppercase text-zinc-500">Warnings</div>
            <div className="text-base font-bold text-amber-400 font-mono mt-0.5">{warningsCount}</div>
            <div className="text-[10px] text-zinc-400 mt-0.5">Design considerations</div>
          </div>

          <div className="bg-zinc-950/60 border border-zinc-800 p-3 rounded-lg">
            <div className="text-[10px] font-mono uppercase text-zinc-500">Info Notices</div>
            <div className="text-base font-bold text-sky-400 font-mono mt-0.5">{infoCount}</div>
            <div className="text-[10px] text-zinc-400 mt-0.5">Stitching vias & notes</div>
          </div>
        </div>

        {/* Findings List */}
        <div className="flex-1 overflow-y-auto divide-y divide-zinc-800 border border-zinc-800 rounded-lg p-2 bg-zinc-950/40">
          {findings.length === 0 ? (
            <div className="p-8 text-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
              <div className="font-semibold text-zinc-200 text-sm">Perfect Quality Audit Score!</div>
              <div className="text-xs text-zinc-500 mt-1">
                No electrical shorts, dangling single-pin stubs, or footprint reference anomalies found.
              </div>
            </div>
          ) : (
            findings.map((f, idx) => {
              const isError = f.severity === 'error';
              const isWarn = f.severity === 'warning';

              return (
                <div key={`finding-${idx}`} className="p-3 hover:bg-zinc-900/60 rounded-lg transition-colors">
                  <div className="flex items-center gap-2">
                    {isError ? (
                      <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                    ) : isWarn ? (
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                    ) : (
                      <Info className="w-4 h-4 text-sky-400 flex-shrink-0" />
                    )}
                    <span className="font-mono font-bold text-xs text-zinc-300">[{f.rule}]</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-mono uppercase font-bold ${
                        isError
                          ? 'bg-rose-500/20 text-rose-400'
                          : isWarn
                          ? 'bg-amber-500/20 text-amber-400'
                          : 'bg-sky-500/20 text-sky-400'
                      }`}
                    >
                      {f.severity}
                    </span>
                    <span className="text-xs text-zinc-400 font-mono">{f.location}</span>
                  </div>
                  <div className="text-xs text-zinc-300 mt-1.5 ml-6">{f.message}</div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
