import React, { useState, useEffect } from 'react';
import {
  CircuitDesignSchema,
  GeneratePCBResponse,
  PresetInfo,
  ProviderItem,
  CircuitPatchAction,
} from './types';
import { PCBViewer2D } from './components/PCBViewer2D';
import { PCBViewer3D } from './components/PCBViewer3D';
import { SchematicViewer } from './components/SchematicViewer';
import { BOMSupplyChainTable } from './components/BOMSupplyChainTable';
import { DRCReportModal } from './components/DRCReportModal';
import { AIChatDrawer } from './components/AIChatDrawer';
import confetti from 'canvas-confetti';
import {
  Cpu,
  Layers,
  Box,
  FileCode,
  ShoppingCart,
  ShieldCheck,
  Download,
  Sparkles,
  Play,
  RotateCcw,
  Sliders,
  Terminal,
  Cloud,
  Server,
  Zap,
  CheckCircle,
  ExternalLink,
  ChevronRight,
  MessageSquare,
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

export default function App() {
  // Navigation & Active Tabs
  const [activeTab, setActiveTab] = useState<'pcb2d' | 'pcb3d' | 'schematic' | 'bom'>('pcb2d');
  const [isDRCModalOpen, setIsDRCModalOpen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);

  // AI & Generation States
  const [prompt, setPrompt] = useState('ESP32-S3 TFT Console with 5 tactile buttons, USB-C, and AMS1117-3.3 power supply');
  const [selectedProvider, setSelectedProvider] = useState<'auto' | 'local' | 'openai' | 'gemini' | 'groq'>('auto');
  const [cloudApiKey, setCloudApiKey] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStep, setGenerationStep] = useState<string>('');

  // Project & Circuit Data
  const [presets, setPresets] = useState<PresetInfo[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>('esp32_tft_console');
  const [circuitData, setCircuitData] = useState<CircuitDesignSchema | null>(null);
  const [jsonText, setJsonText] = useState<string>('');
  const [genResponse, setGenResponse] = useState<GeneratePCBResponse | null>(null);
  const [selectedNet, setSelectedNet] = useState<string | null>(null);

  // Fetch initial presets and health on mount
  useEffect(() => {
    fetchPresets();
    loadPresetDetails('esp32_tft_console');
  }, []);

  const fetchPresets = async () => {
    try {
      const res = await fetch(`${API_BASE}/presets`);
      if (res.ok) {
        const data = await res.json();
        setPresets(data.presets || []);
      }
    } catch (err) {
      console.warn('FastAPI backend not running or reachable yet:', err);
    }
  };

  const loadPresetDetails = async (presetId: string) => {
    setSelectedPresetId(presetId);
    try {
      const res = await fetch(`${API_BASE}/presets/${presetId}`);
      if (res.ok) {
        const data = await res.json();
        setCircuitData(data);
        setJsonText(JSON.stringify(data, null, 2));
        await handleRunGeneratePCB(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // 1. AI Prompt Compilation
  const handlePromptCompile = async () => {
    if (!prompt) return;
    setIsGenerating(true);
    setGenerationStep('Synthesizing electronic circuit from prompt...');
    try {
      const res = await fetch(`${API_BASE}/prompt-to-circuit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          provider: selectedProvider,
          api_key: cloudApiKey || undefined,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.circuit_data) {
          setCircuitData(data.circuit_data);
          setJsonText(JSON.stringify(data.circuit_data, null, 2));
          // Auto trigger PCB Generation
          await handleRunGeneratePCB(data.circuit_data);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsGenerating(false);
      setGenerationStep('');
    }
  };

  // 2. Full PCB Generation Pipeline
  const handleRunGeneratePCB = async (customData?: CircuitDesignSchema) => {
    const payload = customData || circuitData;
    if (!payload) return;

    setIsGenerating(true);
    setGenerationStep('Running AutoPlacement & KiCad Synthesis...');
    try {
      const res = await fetch(`${API_BASE}/generate-pcb`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          circuit_data: payload,
          project_id: genResponse?.project_id,
        }),
      });

      if (res.ok) {
        const data: GeneratePCBResponse = await res.json();
        setGenResponse(data);
        if (data.audit?.passed && data.crosscheck?.parity_match) {
          confetti({ particleCount: 50, spread: 60, origin: { y: 0.8 } });
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsGenerating(false);
      setGenerationStep('');
    }
  };

  // 3. Replace Part in Supply Chain
  const handleReplacePart = async (label: string, newPartNumber: string, newMpn?: string) => {
    if (!circuitData) return;
    setIsGenerating(true);
    setGenerationStep(`Replacing ${label} with ${newPartNumber}...`);
    try {
      const res = await fetch(`${API_BASE}/supply-chain/replace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          circuit_data: circuitData,
          target_label: label,
          new_part_number: newPartNumber,
          new_mpn: newMpn,
        }),
      });
      if (res.ok) {
        const data: GeneratePCBResponse = await res.json();
        setGenResponse(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsGenerating(false);
      setGenerationStep('');
    }
  };

  // 4. Interactive Component Drag/Rotate Updates
  const handleUpdateComponentPosition = async (ref: string, newPos: [number, number], newRot?: number) => {
    if (!circuitData) return;

    // Update in local state immediately for responsive feedback
    const updatedCircuit = circuitData.circuit.map((comp) => {
      if (comp.label === ref || comp.etype === ref) {
        return {
          ...comp,
          position: [newPos[0], newPos[1]] as [number, number],
          rotation: newRot !== undefined ? newRot : comp.rotation,
        };
      }
      return comp;
    });

    const updatedData: CircuitDesignSchema = {
      ...circuitData,
      circuit: updatedCircuit,
    };

    setCircuitData(updatedData);
    setJsonText(JSON.stringify(updatedData, null, 2));

    // Call update API endpoint
    try {
      const res = await fetch(`${API_BASE}/update-component-position`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          circuit_data: updatedData,
          project_id: genResponse?.project_id,
          label: ref,
          position: newPos,
          rotation: newRot,
        }),
      });
      if (res.ok) {
        const data: GeneratePCBResponse = await res.json();
        setGenResponse(data);
      }
    } catch (err) {
      console.error('Update component position failed:', err);
    }
  };

  // 5. Search Providers
  const handleSearchProviders = async (query: string): Promise<Record<string, ProviderItem[]>> => {
    try {
      const res = await fetch(`${API_BASE}/supply-chain/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 5 }),
      });
      if (res.ok) {
        const data = await res.json();
        return data.results || {};
      }
    } catch (err) {
      console.error(err);
    }
    return {};
  };

  // 6. Apply AI Chat Patch
  const handleApplyChatPatch = async (patches: CircuitPatchAction[]) => {
    if (!circuitData) return;
    setIsGenerating(true);
    setGenerationStep('Applying AI Circuit Patch & Re-Routing...');
    try {
      const res = await fetch(`${API_BASE}/chat/apply-patch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: genResponse?.project_id || 'default',
          circuit_data: circuitData,
          patches,
        }),
      });
      if (res.ok) {
        const data: GeneratePCBResponse = await res.json();
        setGenResponse(data);
        if (data.audit?.passed) {
          confetti({ particleCount: 60, spread: 70, origin: { y: 0.7 } });
        }
      }
    } catch (err) {
      console.error('Apply chat patch failed:', err);
    } finally {
      setIsGenerating(false);
      setGenerationStep('');
    }
  };

  return (
    <div className="h-screen w-screen bg-[#07080b] text-zinc-100 flex flex-col font-sans overflow-hidden select-none">
      {/* Top Header Navbar */}
      <header className="h-14 border-b border-zinc-800 bg-[#0d0e13]/90 backdrop-blur-md px-6 flex items-center justify-between z-40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-amber-500 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.4)]">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-white font-mono">PULSELAB FORGE</h1>
              <span className="text-[9px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded font-mono border border-indigo-500/30">
                PROMPT-TO-PCB v2.0
              </span>
            </div>
          </div>
        </div>

        {/* Quick Actions & Downloads */}
        <div className="flex items-center gap-3">
          {/* AI Co-Pilot Drawer Toggle */}
          <button
            onClick={() => setIsChatOpen(!isChatOpen)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              isChatOpen
                ? 'bg-indigo-600 text-white border-indigo-400 shadow-lg shadow-indigo-600/30'
                : 'bg-zinc-900 hover:bg-zinc-800 text-indigo-300 border-indigo-500/40 hover:border-indigo-400'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5 text-amber-400" />
            <span>AI Co-Pilot</span>
          </button>

          {/* Visual Inspection Badge */}
          {genResponse?.visual_inspection && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono border bg-cyan-500/10 text-cyan-300 border-cyan-500/30">
              <CheckCircle className="w-3.5 h-3.5 text-cyan-400" />
              <span>VISUAL: {genResponse.visual_inspection.visual_score}%</span>
            </div>
          )}

          {/* DRC Status Badge */}
          {genResponse && (
            <button
              onClick={() => setIsDRCModalOpen(true)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono border transition-all ${
                genResponse.audit.passed
                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-300 border-rose-500/30 hover:bg-rose-500/20'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>{genResponse.audit.passed ? 'DRC: 100% CLEAN' : `DRC: ${genResponse.audit.errors_count} ERRORS`}</span>
            </button>
          )}

          {/* Preset Select Dropdown */}
          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1 text-xs">
            <span className="text-zinc-500 text-[11px]">Preset:</span>
            <select
              value={selectedPresetId}
              onChange={(e) => loadPresetDetails(e.target.value)}
              className="bg-transparent text-zinc-200 text-xs font-medium focus:outline-none cursor-pointer"
            >
              {presets.map((p) => (
                <option key={p.id} value={p.id} className="bg-zinc-900">
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* KiCad Download */}
          {genResponse?.project_id && (
            <a
              href={`${API_BASE}/export/kicad/${genResponse.project_id}`}
              download
              className="flex items-center gap-1.5 bg-zinc-850 hover:bg-zinc-800 text-zinc-300 hover:text-white px-3 py-1.5 rounded-lg text-xs font-medium border border-zinc-700 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-sky-400" />
              <span>KiCad</span>
            </a>
          )}

          {/* Gerber ZIP Download */}
          {genResponse?.project_id && (
            <a
              href={`${API_BASE}/export/gerber/${genResponse.project_id}`}
              download
              className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Gerber ZIP</span>
            </a>
          )}
        </div>
      </header>

      {/* Main Studio Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Control Drawer: Prompt & Circuit Spec */}
        <aside className="w-96 border-r border-zinc-800/80 bg-[#0a0b10] flex flex-col z-30">
          {/* Prompt Section */}
          <div className="p-4 border-b border-zinc-800">
            <div className="flex items-center justify-between mb-2">
              <label className="text-[11px] font-mono uppercase text-zinc-400 font-bold flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>AI Circuit Prompt</span>
              </label>
              <div className="flex items-center gap-1 text-[10px] text-zinc-500 font-mono">
                <Cloud className="w-3 h-3 text-sky-400" />
                <span>RAG Active</span>
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Describe your circuit (e.g. ESP32-S3 console with display, buttons, and power...)"
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 resize-none font-sans"
            />

            {/* Provider Selection */}
            <div className="grid grid-cols-2 gap-2 mt-2">
              <select
                value={selectedProvider}
                onChange={(e) => setSelectedProvider(e.target.value as any)}
                className="bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-xs text-zinc-300 focus:outline-none font-mono"
              >
                <option value="auto">Auto (Smart RAG)</option>
                <option value="local">Local Ollama</option>
                <option value="openai">OpenAI (GPT-4o)</option>
                <option value="gemini">Google Gemini</option>
                <option value="groq">Groq Cloud</option>
              </select>

              <button
                onClick={handlePromptCompile}
                disabled={isGenerating}
                className="bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow-md shadow-indigo-600/20 disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Compile AI</span>
              </button>
            </div>

            {selectedProvider !== 'auto' && selectedProvider !== 'local' && (
              <input
                type="password"
                value={cloudApiKey}
                onChange={(e) => setCloudApiKey(e.target.value)}
                placeholder="Optional API Key override"
                className="w-full mt-2 bg-zinc-950 border border-zinc-800 rounded-lg px-2.5 py-1 text-[11px] text-zinc-300 placeholder-zinc-600 focus:outline-none font-mono"
              />
            )}
          </div>

          {/* JSON Spec Editor Header */}
          <div className="px-4 py-2 bg-zinc-900/60 border-b border-zinc-800 flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase text-zinc-400 font-bold flex items-center gap-1.5">
              <FileCode className="w-3.5 h-3.5 text-sky-400" />
              <span>CircuitDesignSchema JSON</span>
            </span>
            <button
              onClick={() => {
                try {
                  const parsed = JSON.parse(jsonText);
                  setCircuitData(parsed);
                  handleRunGeneratePCB(parsed);
                } catch (e) {
                  alert('Invalid JSON syntax');
                }
              }}
              className="text-[10px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-2 py-0.5 rounded font-mono transition-colors"
            >
              Apply JSON
            </button>
          </div>

          {/* JSON Textarea */}
          <div className="flex-1 p-2 bg-[#050608] overflow-hidden">
            <textarea
              value={jsonText}
              onChange={(e) => {
                setJsonText(e.target.value);
                try {
                  setCircuitData(JSON.parse(e.target.value));
                } catch {}
              }}
              spellCheck={false}
              className="w-full h-full bg-transparent text-[11px] font-mono text-zinc-300 resize-none focus:outline-none p-2 leading-relaxed"
            />
          </div>

          {/* Primary Action Button */}
          <div className="p-4 border-t border-zinc-800 bg-[#0d0e13]">
            <button
              onClick={() => handleRunGeneratePCB()}
              disabled={isGenerating}
              className="w-full py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-zinc-950 font-bold text-xs rounded-lg shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-current" />
              <span>Generate Circuit & PCB</span>
            </button>
          </div>
        </aside>

        {/* Central Workspace Canvas */}
        <main className="flex-1 flex flex-col bg-[#07080b] overflow-hidden">
          {/* Workspace Tabs Navigation */}
          <div className="h-11 border-b border-zinc-800 bg-[#0c0d12] px-4 flex items-center justify-between">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setActiveTab('pcb2d')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'pcb2d'
                    ? 'bg-zinc-800 text-white font-semibold shadow-inner'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <Layers className="w-3.5 h-3.5 text-amber-400" />
                <span>2D PCB Layout</span>
              </button>

              <button
                onClick={() => setActiveTab('pcb3d')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'pcb3d'
                    ? 'bg-zinc-800 text-white font-semibold shadow-inner'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <Box className="w-3.5 h-3.5 text-sky-400" />
                <span>3D WebGL Board</span>
              </button>

              <button
                onClick={() => setActiveTab('schematic')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'schematic'
                    ? 'bg-zinc-800 text-white font-semibold shadow-inner'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                <span>Schematic</span>
              </button>

              <button
                onClick={() => setActiveTab('bom')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === 'bom'
                    ? 'bg-zinc-800 text-white font-semibold shadow-inner'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <ShoppingCart className="w-3.5 h-3.5 text-emerald-400" />
                <span>Supply Chain & BOM</span>
              </button>
            </div>

            {/* Status Feedback */}
            {isGenerating && (
              <div className="flex items-center gap-2 text-xs text-amber-400 font-mono animate-pulse">
                <div className="w-2 h-2 rounded-full bg-amber-400" />
                <span>{generationStep || 'Processing...'}</span>
              </div>
            )}
          </div>

          {/* Viewport Content */}
          <div className="flex-1 p-4 overflow-hidden relative">
            {activeTab === 'pcb2d' && (
              <PCBViewer2D
                vectors={genResponse?.vectors_2d || null}
                boardWidth={genResponse?.board_width || circuitData?.board_width || 75}
                boardHeight={genResponse?.board_height || circuitData?.board_height || 50}
                selectedNet={selectedNet}
                onSelectNet={setSelectedNet}
                onUpdateComponentPosition={handleUpdateComponentPosition}
                visualInspection={genResponse?.visual_inspection || null}
              />
            )}

            {activeTab === 'pcb3d' && (
              <PCBViewer3D
                meshData={genResponse?.mesh_3d || null}
                vectors={genResponse?.vectors_2d || null}
                boardWidth={genResponse?.board_width || circuitData?.board_width || 75}
                boardHeight={genResponse?.board_height || circuitData?.board_height || 50}
              />
            )}

            {activeTab === 'schematic' && (
              <SchematicViewer
                circuitData={circuitData}
                selectedNet={selectedNet}
                onSelectNet={setSelectedNet}
              />
            )}

            {activeTab === 'bom' && (
              <BOMSupplyChainTable
                bom={genResponse?.supply_chain.bom || []}
                totalCostJLC={genResponse?.supply_chain.total_cost_jlc || 0}
                totalCostPCBWay={genResponse?.supply_chain.total_cost_pcbway || 0}
                onReplacePart={handleReplacePart}
                onSearchProviders={handleSearchProviders}
              />
            )}
          </div>
        </main>
      </div>

      {/* DRC Report Modal */}
      {genResponse && (
        <DRCReportModal
          isOpen={isDRCModalOpen}
          onClose={() => setIsDRCModalOpen(false)}
          auditPassed={genResponse.audit.passed}
          errorsCount={genResponse.audit.errors_count}
          warningsCount={genResponse.audit.warnings_count}
          infoCount={genResponse.audit.info_count}
          parityMatch={genResponse.crosscheck.parity_match}
          findings={genResponse.audit.findings}
          schCount={genResponse.crosscheck.sch_symbols_count}
          pcbCount={genResponse.crosscheck.pcb_footprints_count}
        />
      )}

      {/* Multi-Session AI Co-Pilot Chat Drawer */}
      <AIChatDrawer
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        projectId={genResponse?.project_id || 'default'}
        circuitData={circuitData}
        genResponse={genResponse}
        onApplyPatch={handleApplyChatPatch}
        apiBase={API_BASE}
      />
    </div>
  );
}
