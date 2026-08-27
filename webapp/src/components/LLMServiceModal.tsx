import React, { useState, useEffect } from 'react';
import {
  Server,
  Activity,
  Zap,
  Play,
  Square,
  RotateCw,
  Terminal,
  CheckCircle2,
  AlertTriangle,
  X,
  HardDrive,
  Bot,
  Sliders,
  Check,
  Download,
  Flame,
  Cpu,
  Layers,
  ChevronDown,
  ChevronUp,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { LLMServiceStatus, LLMTestResult, LLMPresetInfo } from '../types';

interface LLMServiceModalProps {
  isOpen: boolean;
  onClose: () => void;
  status: LLMServiceStatus | null;
  onRefresh: () => Promise<void>;
  apiBase?: string;
}

const getApiBase = () => {
  if (typeof window !== 'undefined') {
    if (window.location.port === '3000' || window.location.port === '5173') {
      return 'http://127.0.0.1:8000/api/v1';
    }
    return '/api/v1';
  }
  return 'http://127.0.0.1:8000/api/v1';
};

export const LLMServiceModal: React.FC<LLMServiceModalProps> = ({
  isOpen,
  onClose,
  status,
  onRefresh,
  apiBase: propApiBase,
}) => {
  const apiBase = propApiBase || getApiBase();
  const [selectedBackend, setSelectedBackend] = useState<'auto' | 'ollama' | 'llamacpp'>('auto');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [customModelInput, setCustomModelInput] = useState<string>('');
  const [isCustomModel, setIsCustomModel] = useState<boolean>(false);
  const [portOverride, setPortOverride] = useState<number>(11434);
  const [contextSize, setContextSize] = useState<number>(32768);
  const [temperature, setTemperature] = useState<number>(0.6);
  const [thinkingMode, setThinkingMode] = useState<string>('low');

  // Action states
  const [isLaunching, setIsLaunching] = useState<boolean>(false);
  const [isStopping, setIsStopping] = useState<boolean>(false);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [isPulling, setIsPulling] = useState<boolean>(false);
  const [pullModelInput, setPullModelInput] = useState<string>('hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M');
  const [showPullDrawer, setShowPullDrawer] = useState<boolean>(false);
  const [testPrompt, setTestPrompt] = useState<string>('Explain how an AMS1117-3.3 regulator and decoupling capacitors stabilize a 5V USB to 3.3V rail.');
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);
  const [actionMessage, setActionMessage] = useState<string>('');

  useEffect(() => {
    if (status) {
      if (status.active_model && !selectedModel) {
        setSelectedModel(status.active_model);
      }
      if (status.active_backend) {
        setSelectedBackend(status.active_backend as any);
      }
      if (status.port) {
        setPortOverride(status.port);
      }
      if (status.context_size) {
        setContextSize(status.context_size);
      }
      if (status.temperature !== undefined) {
        setTemperature(status.temperature);
      }
      if (status.thinking_mode) {
        setThinkingMode(status.thinking_mode);
      }
    }
  }, [status]);

  if (!isOpen) return null;

  const handleSelectPreset = (preset: LLMPresetInfo) => {
    setSelectedModel(preset.model);
    setSelectedBackend(preset.backend);
    setPortOverride(preset.port);
    setIsCustomModel(false);
    setActionMessage(`Selected preset: ${preset.name}`);
  };

  const handleLaunchOrSwitch = async () => {
    const finalModel = isCustomModel && customModelInput.trim() ? customModelInput.trim() : selectedModel;
    if (!finalModel) {
      setActionMessage('Please select or specify a model first.');
      return;
    }

    setIsLaunching(true);
    setActionMessage(`Activating model '${finalModel}' on ${selectedBackend} backend...`);
    try {
      const res = await fetch(`${apiBase}/llm/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: finalModel,
          provider: selectedBackend,
          port: portOverride,
          context_size: contextSize,
          temperature: temperature,
          thinking_mode: thinkingMode,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setActionMessage(data.message || 'LLM Engine activated successfully.');
        await onRefresh();
      }
    } catch (err: any) {
      setActionMessage(`Launch error: ${err.message}`);
    } finally {
      setIsLaunching(false);
    }
  };

  const handleStop = async () => {
    setIsStopping(true);
    setActionMessage('Stopping LLM Service...');
    try {
      const res = await fetch(`${apiBase}/llm/stop`, { method: 'POST' });
      if (res.ok) {
        setActionMessage('LLM Service stopped.');
        await onRefresh();
      }
    } catch (err: any) {
      setActionMessage(`Stop error: ${err.message}`);
    } finally {
      setIsStopping(false);
    }
  };

  const handlePullModel = async () => {
    if (!pullModelInput.trim()) return;
    setIsPulling(true);
    setActionMessage(`Triggered pull for '${pullModelInput.trim()}'...`);
    try {
      const res = await fetch(`${apiBase}/llm/pull`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: pullModelInput.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setActionMessage(data.message || `Started downloading ${pullModelInput}`);
      }
    } catch (err: any) {
      setActionMessage(`Pull failed: ${err.message}`);
    } finally {
      setIsPulling(false);
    }
  };

  const handleTestInference = async () => {
    const finalModel = isCustomModel && customModelInput.trim() ? customModelInput.trim() : selectedModel || status?.active_model;
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${apiBase}/llm/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: testPrompt,
          model: finalModel,
          max_tokens: 512,
          temperature: temperature,
        }),
      });
      if (res.ok) {
        const data: LLMTestResult = await res.json();
        setTestResult(data);
      }
    } catch (err: any) {
      setTestResult({
        success: false,
        error: err.message,
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0c0e14] border border-zinc-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col font-sans max-h-[92vh]">
        {/* Modal Header */}
        <div className="p-5 border-b border-zinc-800/80 bg-[#11131c] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 via-cyan-500 to-amber-500 flex items-center justify-center shadow-[0_0_20px_rgba(99,102,241,0.35)]">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-white tracking-tight font-mono">
                  PulseLab Local LLM Hub
                </h2>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-full border flex items-center gap-1.5 ${
                    status?.online
                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                      : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      status?.online ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                    }`}
                  />
                  {status?.online ? 'ENGINE ONLINE' : 'ENGINE OFFLINE'}
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Hardware Synthesis, Tool-Calling, AI Co-Pilot & Semantic DRC Engines
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onRefresh}
              className="p-2 text-zinc-400 hover:text-white bg-zinc-900/60 hover:bg-zinc-800 rounded-lg border border-zinc-800 transition-colors"
              title="Refresh status & scan models"
            >
              <RotateCw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-2 text-zinc-400 hover:text-white bg-zinc-900/60 hover:bg-zinc-800 rounded-lg border border-zinc-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Status & Port Telemetry Row */}
          <div className="grid grid-cols-4 gap-2.5 text-xs">
            <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3 flex flex-col">
              <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1">
                <Activity className="w-3 h-3 text-indigo-400" />
                <span>Active Service</span>
              </span>
              <span className="text-xs font-semibold text-zinc-100 mt-1 capitalize font-mono truncate">
                {status?.service_type || 'None'}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate">
                {status?.active_endpoint || 'http://127.0.0.1:11434/v1'}
              </span>
            </div>

            <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3 flex flex-col">
              <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1">
                <Bot className="w-3 h-3 text-cyan-400" />
                <span>Active Model</span>
              </span>
              <span className="text-xs font-semibold text-emerald-300 mt-1 truncate font-mono" title={status?.active_model}>
                {status?.active_model || 'None'}
              </span>
              <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
                Port: {status?.port || 11434}
              </span>
            </div>

            <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3 flex flex-col">
              <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1">
                <Server className="w-3 h-3 text-amber-400" />
                <span>Ollama :11434</span>
              </span>
              <span className="text-xs font-semibold mt-1 font-mono flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${status?.ports_status?.['11434'] ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                <span>{status?.ports_status?.['11434'] ? 'Active (Docker)' : 'Idle'}</span>
              </span>
              <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
                {status?.ollama_models?.length || 0} Models Pulled
              </span>
            </div>

            <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-xl p-3 flex flex-col">
              <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1">
                <Zap className="w-3 h-3 text-sky-400" />
                <span>llama-server :11440</span>
              </span>
              <span className="text-xs font-semibold mt-1 font-mono flex items-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${status?.ports_status?.['11440'] ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
                <span>{status?.ports_status?.['11440'] ? 'Active (CUDA)' : 'Standby'}</span>
              </span>
              <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
                {status?.gguf_files?.length || 0} GGUFs on disk
              </span>
            </div>
          </div>

          {/* Backend Selector Tabs */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-3 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5 font-mono uppercase text-[11px]">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                <span>1. Select Backend Architecture</span>
              </label>
              <span className="text-[10px] text-zinc-500 font-mono">
                Hardware: GTX 1080 (8GB VRAM)
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => {
                  setSelectedBackend('auto');
                  setPortOverride(11434);
                }}
                className={`py-2 px-3 rounded-lg text-xs font-mono font-medium border transition-all flex flex-col items-start ${
                  selectedBackend === 'auto'
                    ? 'bg-indigo-600/20 text-indigo-200 border-indigo-500/50 shadow-md shadow-indigo-500/10'
                    : 'bg-zinc-900/50 text-zinc-400 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-semibold text-white">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Auto Multi-Lane</span>
                </div>
                <span className="text-[10px] text-zinc-400 mt-0.5">Dynamic routing with auto fallback</span>
              </button>

              <button
                onClick={() => {
                  setSelectedBackend('ollama');
                  setPortOverride(11434);
                }}
                className={`py-2 px-3 rounded-lg text-xs font-mono font-medium border transition-all flex flex-col items-start ${
                  selectedBackend === 'ollama'
                    ? 'bg-cyan-600/20 text-cyan-200 border-cyan-500/50 shadow-md shadow-cyan-500/10'
                    : 'bg-zinc-900/50 text-zinc-400 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-semibold text-white">
                  <Server className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Ollama Runtime (:11434)</span>
                </div>
                <span className="text-[10px] text-zinc-400 mt-0.5">Docker Container / ollama-planner</span>
              </button>

              <button
                onClick={() => {
                  setSelectedBackend('llamacpp');
                  setPortOverride(11440);
                }}
                className={`py-2 px-3 rounded-lg text-xs font-mono font-medium border transition-all flex flex-col items-start ${
                  selectedBackend === 'llamacpp'
                    ? 'bg-amber-600/20 text-amber-200 border-amber-500/50 shadow-md shadow-amber-500/10'
                    : 'bg-zinc-900/50 text-zinc-400 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-semibold text-white">
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  <span>llama.cpp Lane (:11440)</span>
                </div>
                <span className="text-[10px] text-zinc-400 mt-0.5">Direct GGUF execution + MTP</span>
              </button>
            </div>
          </div>

          {/* Curated Presets Grid */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5 font-mono uppercase text-[11px]">
                <Flame className="w-3.5 h-3.5 text-amber-400" />
                <span>2. Recommended Hardware Models & Presets</span>
              </label>
              <span className="text-[10px] text-indigo-400 font-mono">1-Click Fast Configuration</span>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              {status?.presets?.map((preset) => {
                const isSelected = selectedModel === preset.model;
                return (
                  <div
                    key={preset.id}
                    onClick={() => handleSelectPreset(preset)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                      isSelected
                        ? 'bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-600/10'
                        : 'bg-zinc-950/50 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/40'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white font-mono">{preset.name}</span>
                        <span
                          className={`text-[9px] px-1.5 py-0.5 rounded font-mono border ${
                            preset.backend === 'ollama'
                              ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                              : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                          }`}
                        >
                          {preset.backend.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-400 mt-1 line-clamp-2">{preset.description}</p>
                    </div>

                    <div className="mt-2 pt-2 border-t border-zinc-850 flex items-center justify-between text-[10px] font-mono">
                      <span className="text-indigo-300 truncate max-w-[190px]">🎯 {preset.recommended_for}</span>
                      {isSelected ? (
                        <span className="text-emerald-400 flex items-center gap-1 font-bold">
                          <Check className="w-3 h-3" /> ACTIVE
                        </span>
                      ) : (
                        <span className="text-zinc-500 hover:text-zinc-300">Select →</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Model Selection & Custom Input */}
          <div className="bg-zinc-950/60 border border-zinc-800/80 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5 font-mono uppercase text-[11px]">
                <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                <span>3. Model Selection & Parameters</span>
              </label>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsCustomModel(!isCustomModel)}
                  className="text-[10px] text-indigo-400 hover:text-indigo-300 font-mono underline"
                >
                  {isCustomModel ? '← Pick from Discovered Models' : '+ Enter Custom Model / HF Tag'}
                </button>
              </div>
            </div>

            {!isCustomModel ? (
              <div className="space-y-1">
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-700/80 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500 font-mono"
                >
                  <optgroup label="✨ High-Capacity Reasoning & Distill Models">
                    <option value="hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M">
                      hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M (Ollama)
                    </option>
                    <option value="Qwen3.8-9B-Q4_K_M.gguf">Qwen3.8-9B-Q4_K_M.gguf (llama.cpp)</option>
                    <option value="Qwen3.8-4B-Q4_K_M.gguf">Qwen3.8-4B-Q4_K_M.gguf (llama.cpp)</option>
                    <option value="qwythos-9b-96k:latest">qwythos-9b-96k:latest (Ollama)</option>
                  </optgroup>

                  {status?.ollama_models && status.ollama_models.length > 0 && (
                    <optgroup label="🦙 All Ollama Library & Local Pulled Models">
                      {status.ollama_models.map((m) => (
                        <option key={`ollama_${m}`} value={m}>
                          {m}
                        </option>
                      ))}
                    </optgroup>
                  )}

                  {status?.gguf_files && status.gguf_files.length > 0 && (
                    <optgroup label="📁 Local llama.cpp .GGUF Model Files">
                      {status.gguf_files.map((g) => (
                        <option key={`gguf_${g.name}`} value={g.name}>
                          {g.name} ({g.size_gb} GB)
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </div>
            ) : (
              <div className="space-y-1">
                <input
                  type="text"
                  value={customModelInput}
                  onChange={(e) => setCustomModelInput(e.target.value)}
                  placeholder="e.g. hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M or qwen2.5-coder:7b"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}

            {/* Inference Parameters Row */}
            <div className="grid grid-cols-4 gap-2 pt-1">
              <div>
                <label className="text-[10px] font-mono text-zinc-400 block mb-1">Context Size:</label>
                <select
                  value={contextSize}
                  onChange={(e) => setContextSize(Number(e.target.value))}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-[11px] text-zinc-200 font-mono focus:outline-none"
                >
                  <option value={16384}>16,384 tokens</option>
                  <option value={32768}>32,768 tokens (Default)</option>
                  <option value={65536}>65,536 tokens</option>
                  <option value={98304}>98,304 tokens (96k)</option>
                  <option value={131072}>131,072 tokens (128k)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-zinc-400 block mb-1">Thinking Mode:</label>
                <select
                  value={thinkingMode}
                  onChange={(e) => setThinkingMode(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1.5 text-[11px] text-zinc-200 font-mono focus:outline-none"
                >
                  <option value="low">Low (Reasoning on)</option>
                  <option value="none">None (Fast JSON/DRC)</option>
                  <option value="high">High (Deep Architecture)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono text-zinc-400 block mb-1">Temperature ({temperature}):</label>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full mt-1.5 accent-indigo-500"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono text-zinc-400 block mb-1">Service Port:</label>
                <input
                  type="number"
                  value={portOverride}
                  onChange={(e) => setPortOverride(Number(e.target.value))}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-2 py-1 text-[11px] text-zinc-200 font-mono focus:outline-none"
                />
              </div>
            </div>

            {/* Launch & Manage Buttons */}
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleLaunchOrSwitch}
                disabled={isLaunching}
                className="flex-1 bg-gradient-to-r from-indigo-600 via-cyan-600 to-indigo-700 hover:from-indigo-500 hover:to-cyan-500 text-white rounded-lg px-4 py-2.5 text-xs font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 disabled:opacity-50 transition-all cursor-pointer"
              >
                <Play className="w-4 h-4 fill-white" />
                <span>
                  {isLaunching
                    ? 'Activating Model & Setting Routing...'
                    : `Apply & Launch Model: ${selectedModel ? selectedModel.split('/').pop() : 'Select Model'}`}
                </span>
              </button>

              <button
                onClick={handleStop}
                disabled={isStopping || !status?.online}
                className="bg-zinc-900 hover:bg-rose-950/40 text-zinc-300 hover:text-rose-300 border border-zinc-800 hover:border-rose-800/40 rounded-lg px-3.5 py-2.5 text-xs font-medium flex items-center gap-1.5 disabled:opacity-40 transition-colors cursor-pointer"
              >
                <Square className="w-3.5 h-3.5 text-rose-400" />
                <span>{isStopping ? 'Stopping...' : 'Stop'}</span>
              </button>

              <button
                onClick={() => setShowPullDrawer(!showPullDrawer)}
                className="bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-lg px-3 py-2.5 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                title="Pull new model from HuggingFace / Ollama library"
              >
                <Download className="w-3.5 h-3.5 text-cyan-400" />
                <span>Pull Model</span>
                {showPullDrawer ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            </div>

            {/* Model Puller Sub-Drawer */}
            {showPullDrawer && (
              <div className="p-3 bg-[#08090e] border border-zinc-800 rounded-lg space-y-2 mt-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-zinc-300 font-semibold flex items-center gap-1.5">
                    <Download className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Pull Model from HuggingFace / Ollama Registry</span>
                  </span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={pullModelInput}
                    onChange={(e) => setPullModelInput(e.target.value)}
                    placeholder="e.g. hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M"
                    className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2.5 py-1.5 text-xs text-zinc-100 font-mono placeholder-zinc-600 focus:outline-none"
                  />
                  <button
                    onClick={handlePullModel}
                    disabled={isPulling || !pullModelInput}
                    className="bg-cyan-600 hover:bg-cyan-500 text-white rounded px-3 py-1.5 text-xs font-semibold flex items-center gap-1 disabled:opacity-50"
                  >
                    <span>{isPulling ? 'Pulling...' : 'Pull'}</span>
                  </button>
                </div>
              </div>
            )}

            {actionMessage && (
              <p className="text-[11px] text-zinc-300 font-mono bg-zinc-900/90 p-2 rounded border border-zinc-800 flex items-center gap-1.5">
                <span className="text-indigo-400 font-bold">ℹ️</span> {actionMessage}
              </p>
            )}
          </div>

          {/* Interactive Live Benchmark & Inference Tester */}
          <div className="bg-[#0a0b10] border border-zinc-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase text-zinc-300 font-bold flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                <span>4. Real-Time Inference Tester & Benchmark</span>
              </span>
              <button
                onClick={handleTestInference}
                disabled={isTesting || !status?.online}
                className="bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-500 hover:to-amber-600 text-white rounded-lg px-3 py-1.5 text-xs font-semibold flex items-center gap-1.5 disabled:opacity-40 transition-all cursor-pointer shadow-md shadow-amber-600/20"
              >
                <Zap className="w-3.5 h-3.5 fill-white" />
                <span>{isTesting ? 'Generating...' : 'Benchmark Ping'}</span>
              </button>
            </div>

            <textarea
              value={testPrompt}
              onChange={(e) => setTestPrompt(e.target.value)}
              rows={2}
              placeholder="Enter test prompt for hardware synthesis or circuit validation..."
              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-2.5 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 resize-none font-sans"
            />

            {/* Test Result Display */}
            {testResult && (
              <div className="space-y-2 pt-1">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <div className="text-zinc-400">
                    Model: <span className="text-zinc-200">{testResult.model_used}</span> | Endpoint:{' '}
                    <span className="text-zinc-200">{testResult.endpoint}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {testResult.latency_ms && (
                      <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        ⚡ {testResult.latency_ms} ms
                      </span>
                    )}
                    {testResult.tokens_per_sec && (
                      <span className="text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                        🚀 {testResult.tokens_per_sec} t/s
                      </span>
                    )}
                  </div>
                </div>

                {testResult.success ? (
                  <div className="space-y-2">
                    {testResult.reasoning && (
                      <div className="bg-zinc-950/80 p-3 rounded-lg border border-amber-500/20 text-amber-200/90 text-xs font-mono leading-relaxed max-h-36 overflow-y-auto">
                        <div className="text-[10px] uppercase font-bold text-amber-400 mb-1 flex items-center gap-1">
                          <span>🧠 Reasoning Trace (&lt;think&gt;):</span>
                        </div>
                        {testResult.reasoning}
                      </div>
                    )}
                    <div className="bg-zinc-950 p-3.5 rounded-lg border border-zinc-800 text-zinc-100 text-xs font-sans leading-relaxed">
                      {testResult.response || 'Inference executed cleanly with active model.'}
                    </div>
                  </div>
                ) : (
                  <div className="p-3 bg-rose-950/20 border border-rose-800/30 rounded-lg text-xs text-rose-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>{testResult.error}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-zinc-800 bg-[#0f1118] flex items-center justify-between text-[11px] text-zinc-500 font-mono">
          <span>PulseLab EDA Engine v2.1 • Dual Inference Controller</span>
          <div className="flex items-center gap-3">
            <span className="text-zinc-400">GTX 1080 (Primary GPU)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
