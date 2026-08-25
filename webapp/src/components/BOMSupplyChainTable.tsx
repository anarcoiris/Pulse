import React, { useState } from 'react';
import { BOMRow, ProviderItem } from '../types';
import { ShoppingCart, CheckCircle2, AlertTriangle, XCircle, Search, RefreshCw, ExternalLink, ArrowRightLeft } from 'lucide-react';

interface BOMSupplyChainTableProps {
  bom: BOMRow[];
  totalCostJLC: number;
  totalCostPCBWay: number;
  onReplacePart: (label: string, newPartNumber: string, newMpn?: string) => Promise<void>;
  onSearchProviders: (query: string) => Promise<Record<string, ProviderItem[]>>;
}

export const BOMSupplyChainTable: React.FC<BOMSupplyChainTableProps> = ({
  bom,
  totalCostJLC,
  totalCostPCBWay,
  onReplacePart,
  onSearchProviders,
}) => {
  const [replacingLabel, setReplacingLabel] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Record<string, ProviderItem[]> | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  const inStockCount = bom.filter(
    (b) => (b.jlcpcb?.stock && b.jlcpcb.stock > 0) || (b.pcbway?.stock && b.pcbway.stock > 0)
  ).length;

  const handleOpenReplace = (row: BOMRow) => {
    setReplacingLabel(row.label);
    setSearchQuery(row.value);
    handleSearch(row.value);
  };

  const handleSearch = async (query: string) => {
    if (!query) return;
    setIsSearching(true);
    try {
      const res = await onSearchProviders(query);
      setSearchResults(res);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleConfirmReplace = async (newPart: ProviderItem) => {
    if (!replacingLabel || !newPart.part_number) return;
    await onReplacePart(replacingLabel, newPart.part_number, newPart.mpn);
    setReplacingLabel(null);
    setSearchResults(null);
  };

  return (
    <div className="w-full h-full bg-[#090a0f] rounded-xl overflow-hidden border border-zinc-800 flex flex-col p-6 text-zinc-200">
      {/* Top Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl shadow-lg">
          <div className="text-[11px] font-mono uppercase text-zinc-400">Total BOM Cost (JLCPCB)</div>
          <div className="text-2xl font-bold text-amber-400 mt-1 font-mono">${totalCostJLC.toFixed(2)}</div>
          <div className="text-[10px] text-zinc-500 mt-1">Per prototype unit</div>
        </div>

        <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl shadow-lg">
          <div className="text-[11px] font-mono uppercase text-zinc-400">Total BOM Cost (PCBWay)</div>
          <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono">${totalCostPCBWay.toFixed(2)}</div>
          <div className="text-[10px] text-zinc-500 mt-1">Per prototype unit</div>
        </div>

        <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl shadow-lg">
          <div className="text-[11px] font-mono uppercase text-zinc-400">Supply Chain Availability</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">
            {inStockCount} / {bom.length}
          </div>
          <div className="text-[10px] text-emerald-500/80 mt-1">
            {((inStockCount / Math.max(1, bom.length)) * 100).toFixed(0)}% components ready
          </div>
        </div>

        <div className="bg-zinc-900/80 border border-zinc-800 p-4 rounded-xl shadow-lg flex items-center justify-between">
          <div>
            <div className="text-[11px] font-mono uppercase text-zinc-400">Preferred SMT Catalog</div>
            <div className="text-lg font-bold text-zinc-100 mt-1">JLCPCB SMT</div>
            <div className="text-[10px] text-zinc-500 mt-0.5">Basic parts 0 setup fee</div>
          </div>
          <ShoppingCart className="w-8 h-8 text-amber-500 opacity-80" />
        </div>
      </div>

      {/* Main Table */}
      <div className="flex-1 overflow-y-auto border border-zinc-800/80 rounded-xl bg-zinc-950/60">
        <table className="w-full text-left text-xs">
          <thead className="bg-zinc-900/90 sticky top-0 border-b border-zinc-800 text-zinc-400 font-mono text-[11px]">
            <tr>
              <th className="py-3 px-4">Designator</th>
              <th className="py-3 px-4">Value / Part</th>
              <th className="py-3 px-4">Package</th>
              <th className="py-3 px-4">JLCPCB Stock & Price</th>
              <th className="py-3 px-4">PCBWay Stock & Price</th>
              <th className="py-3 px-4">Supplier Recommendation</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-850">
            {bom.map((row, idx) => {
              const jlc = row.jlcpcb;
              const pcbway = row.pcbway;
              const jlcInStock = jlc?.in_stock || (jlc?.stock && jlc.stock > 0);
              const pcbwayInStock = pcbway?.in_stock || (pcbway?.stock && pcbway.stock > 0);

              return (
                <tr key={`bom-${idx}`} className="hover:bg-zinc-900/50 transition-colors">
                  <td className="py-3 px-4 font-mono font-bold text-amber-400">{row.label}</td>
                  <td className="py-3 px-4">
                    <div className="font-semibold text-zinc-100">{row.value}</div>
                    <div className="text-[10px] text-zinc-500 font-mono">{row.etype}</div>
                  </td>
                  <td className="py-3 px-4 font-mono text-zinc-400 text-[11px] max-w-[140px] truncate">
                    {row.footprint || 'Standard'}
                  </td>

                  {/* JLCPCB */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1.5">
                      {jlcInStock ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-rose-400" />
                      )}
                      <span className="font-mono text-zinc-200">{jlc?.part_number || 'N/A'}</span>
                      {jlc?.library_type === 'basic' && (
                        <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1 py-0.5 rounded font-mono">
                          BASIC
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] text-zinc-400 font-mono mt-0.5">
                      {jlcInStock ? `${jlc?.stock} in stock · $${(jlc?.unit_price_usd || 0).toFixed(3)}` : 'Out of stock'}
                    </div>
                  </td>

                  {/* PCBWay */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-1.5">
                      {pcbwayInStock ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 text-zinc-600" />
                      )}
                      <span className="font-mono text-zinc-300">{pcbway?.part_number || 'N/A'}</span>
                    </div>
                    <div className="text-[10px] text-zinc-400 font-mono mt-0.5">
                      {pcbwayInStock ? `${pcbway?.stock} in stock · $${(pcbway?.unit_price_usd || 0).toFixed(3)}` : 'N/A'}
                    </div>
                  </td>

                  {/* Recommendation */}
                  <td className="py-3 px-4">
                    <span className="text-[11px] bg-zinc-800 text-zinc-300 px-2 py-1 rounded border border-zinc-700 font-mono">
                      {row.recommendation || 'Standard SMT'}
                    </span>
                  </td>

                  {/* Action */}
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => handleOpenReplace(row)}
                      className="inline-flex items-center gap-1 bg-zinc-800 hover:bg-indigo-600 text-zinc-300 hover:text-white px-2.5 py-1.5 rounded text-xs transition-colors font-medium"
                    >
                      <ArrowRightLeft className="w-3.5 h-3.5" />
                      <span>Replace</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Replacement Modal Drawer */}
      {replacingLabel && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-700 w-full max-w-2xl rounded-xl shadow-2xl p-6 flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <ArrowRightLeft className="w-4 h-4 text-indigo-400" />
                  <span>Replace Part for {replacingLabel}</span>
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Select an in-stock alternative from JLCPCB or PCBWay catalogs.
                </p>
              </div>
              <button
                onClick={() => setReplacingLabel(null)}
                className="text-zinc-400 hover:text-white font-bold text-lg p-1"
              >
                ×
              </button>
            </div>

            {/* Search Input */}
            <div className="flex gap-2 mb-4">
              <div className="relative flex-1">
                <Search className="w-4 h-4 absolute left-3 top-3 text-zinc-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch(searchQuery)}
                  placeholder="Search by part number, value, or manufacturer..."
                  className="w-full bg-zinc-950 border border-zinc-700 rounded-lg pl-9 pr-4 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <button
                onClick={() => handleSearch(searchQuery)}
                disabled={isSearching}
                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
              >
                {isSearching ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                <span>Search</span>
              </button>
            </div>

            {/* Search Results List */}
            <div className="flex-1 overflow-y-auto divide-y divide-zinc-800 border border-zinc-800 rounded-lg p-2 bg-zinc-950/40">
              {searchResults ? (
                <>
                  {Object.entries(searchResults).map(([providerName, items]) => (
                    <div key={providerName} className="py-2">
                      <div className="text-[10px] font-mono uppercase text-zinc-400 px-2 mb-1">
                        {providerName.toUpperCase()} RESULTS ({items.length})
                      </div>
                      {items.length === 0 ? (
                        <div className="text-xs text-zinc-500 px-2 py-1 italic">No results found</div>
                      ) : (
                        items.map((item, idx) => (
                          <div
                            key={`res-${idx}`}
                            className="flex items-center justify-between p-2.5 hover:bg-zinc-900 rounded-lg transition-colors"
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-amber-400 text-xs">
                                  {item.part_number}
                                </span>
                                <span className="font-semibold text-zinc-200 text-xs">{item.mpn}</span>
                                {item.library_type === 'basic' && (
                                  <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1 rounded font-mono">
                                    BASIC
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-zinc-400 mt-0.5">
                                {item.manufacturer} · {item.package} · {item.stock} in stock · $
                                {(item.unit_price_usd || 0).toFixed(3)}/unit
                              </div>
                            </div>

                            <button
                              onClick={() => handleConfirmReplace(item)}
                              className="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded text-xs font-semibold transition-colors"
                            >
                              Select & Apply
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  ))}
                </>
              ) : (
                <div className="text-center py-8 text-xs text-zinc-500">
                  Search to discover alternatives and live supplier inventory.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
