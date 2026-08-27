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
  ExternalLink,
  MessageSquare
} from 'lucide-react';
import { LLMServiceStatus, LLMTestResult, LLMPresetInfo } from '../types';

interface LLMEnginePanelProps {
  status: LLMServiceStatus | null;
  onRefresh: () => Promise<void>;
  apiBase: string;
}

export const LLMEnginePanel: React.FC<LLMEnginePanelProps> = ({
  status,
  onRefresh,
  apiBase,
}) => {
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
    <div className="h-full w-full bg-[#08090e] text-zinc-100 p-6 overflow-y-auto flex flex-col font-sans space-y-6">
      {/* Top Banner */}
      <div className="bg-[#0f111a] border border-zinc-800 rounded-2xl p-5 flex items-center justify-between shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 via-cyan-500 to-amber-500 flex items-center justify-center shadow-[0_0_25px_rgba(99,102,241,0.4)]">
            <Cpu className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-white tracking-tight font-mono">
                PulseLab Local LLM Engine & Architecture Hub
              </h2>
              <span
                className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border flex items-center gap-1.5 ${
                  status?.online
                    ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                    : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    status?.online ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                  }`}
                />
                {status?.online ? 'ENGINE ONLINE' : 'ENGINE OFFLINE'}
              </span>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              Hardware Synthesis, Function Calling, Prompt Compilation & Semantic DRC Review Engine
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onRefresh}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-mono text-zinc-300 bg-zinc-900/80 hover:bg-zinc-800 rounded-xl border border-zinc-800 transition-colors"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Scan & Refresh</span>
          </button>
        </div>
      </div>

      {/* Telemetry Row */}
      <div className="grid grid-cols-4 gap-3 text-xs">
        <div className="bg-zinc-950/80 border border-zinc-800/90 rounded-xl p-4 flex flex-col shadow-md">
          <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            <span>Active Service</span>
          </span>
          <span className="text-sm font-semibold text-zinc-100 mt-1.5 capitalize font-mono truncate">
            {status?.service_type || 'None'}
          </span>
          <span className="text-[10px] text-zinc-500 font-mono mt-0.5 truncate">
            {status?.active_endpoint || 'http://127.0.0.1:11434/v1'}
          </span>
        </div>

        <div className="bg-zinc-950/80 border border-zinc-800/90 rounded-xl p-4 flex flex-col shadow-md">
          <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
            <Bot className="w-3.5 h-3.5 text-cyan-400" />
            <span>Active Model</span>
          </span>
          <span className="text-sm font-semibold text-emerald-300 mt-1.5 truncate font-mono" title={status?.active_model}>
            {status?.active_model || 'None'}
          </span>
          <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
            Port: {status?.port || 11434}
          </span>
        </div>

        <div className="bg-zinc-950/80 border border-zinc-800/90 rounded-xl p-4 flex flex-col shadow-md">
          <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5 text-amber-400" />
            <span>Ollama Engine (:11434)</span>
          </span>
          <span className="text-sm font-semibold mt-1.5 font-mono flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${status?.ports_status?.['11434'] ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
            <span>{status?.ports_status?.['11434'] ? 'Active (Docker / Host)' : 'Idle'}</span>
          </span>
          <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
            {status?.ollama_models?.length || 0} Models Available
          </span>
        </div>

        <div className="bg-zinc-950/80 border border-zinc-800/90 rounded-xl p-4 flex flex-col shadow-md">
          <span className="text-[10px] font-mono text-zinc-500 uppercase flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-sky-400" />
            <span>llama-server (:11440)</span>
          </span>
          <span className="text-sm font-semibold mt-1.5 font-mono flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${status?.ports_status?.['11440'] ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
            <span>{status?.ports_status?.['11440'] ? 'Active (CUDA GPU 0)' : 'Standby'}</span>
          </span>
          <span className="text-[10px] text-zinc-500 font-mono mt-0.5">
            {status?.gguf_files?.length || 0} GGUFs on disk
          </span>
        </div>
      </div>

      {/* Backend Architecture Selector */}
      <div className="bg-zinc-950/70 border border-zinc-800 rounded-2xl p-5 space-y-3 shadow-lg">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-zinc-200 flex items-center gap-2 font-mono uppercase text-[11px]">
            <Layers className="w-4 h-4 text-indigo-400" />
            <span>1. Inference Backend Architecture</span>
          </label>
          <span className="text-[11px] text-zinc-500 font-mono">
            Hardware: NVIDIA GTX 1080 (8GB VRAM)
          </span>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <button
            onClick={() => {
              setSelectedBackend('auto');
              setPortOverride(11434);
            }}
            className={`p-3.5 rounded-xl text-xs font-mono font-medium border transition-all flex flex-col items-start cursor-pointer ${
              selectedBackend === 'auto'
                ? 'bg-indigo-600/20 text-indigo-200 border-indigo-500/60 shadow-lg shadow-indigo-500/10'
                : 'bg-zinc-900/40 text-zinc-400 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/70'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-white text-xs">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span>Auto Multi-Lane Routing</span>
            </div>
            <span className="text-[11px] text-zinc-400 mt-1">Automatic task-based routing with failover</span>
          </button>

          <button
            onClick={() => {
              setSelectedBackend('ollama');
              setPortOverride(11434);
            }}
            className={`p-3.5 rounded-xl text-xs font-mono font-medium border transition-all flex flex-col items-start cursor-pointer ${
              selectedBackend === 'ollama'
                ? 'bg-cyan-600/20 text-cyan-200 border-cyan-500/60 shadow-lg shadow-cyan-500/10'
                : 'bg-zinc-900/40 text-zinc-400 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/70'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-white text-xs">
              <Server className="w-4 h-4 text-cyan-400" />
              <span>Ollama Runtime (:11434)</span>
            </div>
            <span className="text-[11px] text-zinc-400 mt-1">Direct Docker/Host Ollama inference container</span>
          </button>

          <button
            onClick={() => {
              setSelectedBackend('llamacpp');
              setPortOverride(11440);
            }}
            className={`p-3.5 rounded-xl text-xs font-mono font-medium border transition-all flex flex-col items-start cursor-pointer ${
              selectedBackend === 'llamacpp'
                ? 'bg-amber-600/20 text-amber-200 border-amber-500/60 shadow-lg shadow-amber-500/10'
                : 'bg-zinc-900/40 text-zinc-400 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/70'
            }`}
          >
            <div className="flex items-center gap-2 font-bold text-white text-xs">
              <Zap className="w-4 h-4 text-amber-400" />
              <span>llama.cpp Lane (:11440)</span>
            </div>
            <span className="text-[11px] text-zinc-400 mt-1">Direct GGUF execution + MTP draft decoding</span>
          </button>
        </div>
      </div>

      {/* Curated Presets Grid */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-zinc-200 flex items-center gap-2 font-mono uppercase text-[11px]">
            <Flame className="w-4 h-4 text-amber-400" />
            <span>2. Curated Hardware Models & Quick-Picks</span>
          </label>
          <span className="text-[11px] text-indigo-400 font-mono">1-Click Instant Activation</span>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {status?.presets?.map((preset) => {
            const isSelected = selectedModel === preset.model;
            return (
              <div
                key={preset.id}
                onClick={() => handleSelectPreset(preset)}
                className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between ${
                  isSelected
                    ? 'bg-indigo-950/40 border-indigo-500/60 shadow-xl shadow-indigo-600/15'
                    : 'bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700 hover:bg-zinc-900/50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white font-mono">{preset.name}</span>
                    <span
                      className={`text-[9px] px-2 py-0.5 rounded-full font-mono border font-semibold ${
                        preset.backend === 'ollama'
                          ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                          : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                      }`}
                    >
                      {preset.backend.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1.5 line-clamp-2 leading-relaxed">{preset.description}</p>
                </div>

                <div className="mt-3 pt-2.5 border-t border-zinc-850 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-indigo-300 truncate max-w-[170px]">🎯 {preset.recommended_for}</span>
                  {isSelected ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-bold text-xs">
                      <Check className="w-3.5 h-3.5" /> ACTIVE
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

      {/* Model Selection & Parameters */}
      <div className="bg-zinc-950/70 border border-zinc-800 rounded-2xl p-5 space-y-4 shadow-lg">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-zinc-200 flex items-center gap-2 font-mono uppercase text-[11px]">
            <Sliders className="w-4 h-4 text-indigo-400" />
            <span>3. Model Selection & Tuning</span>
          </label>

          <button
            type="button"
            onClick={() => setIsCustomModel(!isCustomModel)}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-mono underline cursor-pointer"
          >
            {isCustomModel ? '← Pick from Discovered Models' : '+ Enter Custom Model / HF Tag'}
          </button>
        </div>

        {!isCustomModel ? (
          <div>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700/80 rounded-xl px-4 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-indigo-500 font-mono cursor-pointer"
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
                <optgroup label="🦙 All Ollama Registry & Local Models">
                  {status.ollama_models.map((m) => (
                    <option key={`ollama_panel_${m}`} value={m}>
                      {m}
                    </option>
                  ))}
                </optgroup>
              )}

              {status?.gguf_files && status.gguf_files.length > 0 && (
                <optgroup label="📁 Local llama.cpp .GGUF Model Files">
                  {status.gguf_files.map((g) => (
                    <option key={`gguf_panel_${g.name}`} value={g.name}>
                      {g.name} ({g.size_gb} GB)
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>
        ) : (
          <div>
            <input
              type="text"
              value={customModelInput}
              onChange={(e) => setCustomModelInput(e.target.value)}
              placeholder="e.g. hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M or qwen2.5-coder:7b"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-2.5 text-xs text-zinc-100 font-mono placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
            />
          </div>
        )}

        {/* Parameters Grid */}
        <div className="grid grid-cols-4 gap-3 pt-1">
          <div>
            <label className="text-[11px] font-mono text-zinc-400 block mb-1">Context Window:</label>
            <select
              value={contextSize}
              onChange={(e) => setContextSize(Number(e.target.value))}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono focus:outline-none"
            >
              <option value={16384}>16,384 tokens</option>
              <option value={32768}>32,768 tokens (Default)</option>
              <option value={65536}>65,536 tokens</option>
              <option value={98304}>98,304 tokens (96k)</option>
              <option value={131072}>131,072 tokens (128k)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-mono text-zinc-400 block mb-1">Thinking Mode:</label>
            <select
              value={thinkingMode}
              onChange={(e) => setThinkingMode(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 font-mono focus:outline-none"
            >
              <option value="low">Low (Reasoning on)</option>
              <option value="none">None (Fast JSON/DRC)</option>
              <option value="high">High (Deep Architecture)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-mono text-zinc-400 block mb-1">Temperature ({temperature}):</label>
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(parseFloat(e.target.value))}
              className="w-full mt-2 accent-indigo-500"
            />
          </div>

          <div>
            <label className="text-[11px] font-mono text-zinc-400 block mb-1">Service Port:</label>
            <input
              type="number"
              value={portOverride}
              onChange={(e) => setPortOverride(Number(e.target.value))}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-xs text-zinc-200 font-mono focus:outline-none"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleLaunchOrSwitch}
            disabled={isLaunching}
            className="flex-1 bg-gradient-to-r from-indigo-600 via-cyan-600 to-indigo-700 hover:from-indigo-500 hover:to-cyan-500 text-white rounded-xl px-5 py-3 text-xs font-bold flex items-center justify-center gap-2 shadow-xl shadow-indigo-600/20 disabled:opacity-50 transition-all cursor-pointer"
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
            className="bg-zinc-900 hover:bg-rose-950/40 text-zinc-300 hover:text-rose-300 border border-zinc-800 hover:border-rose-800/40 rounded-xl px-4 py-3 text-xs font-semibold flex items-center gap-2 disabled:opacity-40 transition-colors cursor-pointer"
          >
            <Square className="w-4 h-4 text-rose-400" />
            <span>{isStopping ? 'Stopping...' : 'Stop Engine'}</span>
          </button>

          <button
            onClick={() => setShowPullDrawer(!showPullDrawer)}
            className="bg-zinc-900 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 rounded-xl px-4 py-3 text-xs font-medium flex items-center gap-2 transition-colors cursor-pointer"
          >
            <Download className="w-4 h-4 text-cyan-400" />
            <span>Pull Model</span>
            {showPullDrawer ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Model Puller Sub-Drawer */}
        {showPullDrawer && (
          <div className="p-4 bg-[#0a0b12] border border-zinc-800 rounded-xl space-y-2 mt-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-zinc-300 font-semibold flex items-center gap-2">
                <Download className="w-4 h-4 text-cyan-400" />
                <span>Pull Model into Ollama Container</span>
              </span>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={pullModelInput}
                onChange={(e) => setPullModelInput(e.target.value)}
                placeholder="e.g. hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M"
                className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-100 font-mono placeholder-zinc-600 focus:outline-none"
              />
              <button
                onClick={handlePullModel}
                disabled={isPulling || !pullModelInput}
                className="bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg px-4 py-2 text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                <span>{isPulling ? 'Pulling...' : 'Pull Model'}</span>
              </button>
            </div>
          </div>
        )}

        {actionMessage && (
          <p className="text-xs text-zinc-300 font-mono bg-zinc-900/90 p-3 rounded-xl border border-zinc-800 flex items-center gap-2">
            <span className="text-indigo-400 font-bold">ℹ️</span> {actionMessage}
          </p>
        )}
      </div>

      {/* Live Benchmark & Inference Console */}
      <div className="bg-zinc-950/70 border border-zinc-800 rounded-2xl p-5 space-y-3 shadow-lg">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono uppercase text-zinc-200 font-bold flex items-center gap-2">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <span>4. Live Inference Benchmark & Architecture Console</span>
          </span>
          <button
            onClick={handleTestInference}
            disabled={isTesting || !status?.online}
            className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-zinc-950 rounded-xl px-4 py-2 text-xs font-bold flex items-center gap-2 disabled:opacity-40 transition-all cursor-pointer shadow-lg shadow-amber-500/20"
          >
            <Zap className="w-4 h-4 fill-current" />
            <span>{isTesting ? 'Generating Response...' : 'Run Benchmark Ping'}</span>
          </button>
        </div>

        <textarea
          value={testPrompt}
          onChange={(e) => setTestPrompt(e.target.value)}
          rows={2}
          placeholder="Enter prompt to benchmark..."
          className="w-full bg-zinc-900/90 border border-zinc-800 rounded-xl p-3 text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-indigo-500 resize-none font-sans"
        />

        {/* Test Result Display */}
        {testResult && (
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between text-xs font-mono">
              <div className="text-zinc-400">
                Model: <span className="text-zinc-200">{testResult.model_used}</span> | Endpoint:{' '}
                <span className="text-zinc-200">{testResult.endpoint}</span>
              </div>
              <div className="flex items-center gap-2">
                {testResult.latency_ms && (
                  <span className="text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20 font-bold">
                    ⚡ {testResult.latency_ms} ms
                  </span>
                )}
                {testResult.tokens_per_sec && (
                  <span className="text-cyan-400 bg-cyan-500/10 px-2.5 py-1 rounded-lg border border-cyan-500/20 font-bold">
                    🚀 {testResult.tokens_per_sec} t/s
                  </span>
                )}
              </div>
            </div>

            {testResult.success ? (
              <div className="space-y-2">
                {testResult.reasoning && (
                  <div className="bg-[#0b0d14] p-4 rounded-xl border border-amber-500/25 text-amber-200/90 text-xs font-mono leading-relaxed max-h-48 overflow-y-auto">
                    <div className="text-[10px] uppercase font-bold text-amber-400 mb-1.5 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Reasoning Trace (&lt;think&gt;):</span>
                    </div>
                    {testResult.reasoning}
                  </div>
                )}
                <div className="bg-[#0b0d14] p-4 rounded-xl border border-zinc-800 text-zinc-100 text-xs font-sans leading-relaxed">
                  {testResult.response || 'Inference executed cleanly with active model.'}
                </div>
              </div>
            ) : (
              <div className="p-4 bg-rose-950/20 border border-rose-800/30 rounded-xl text-xs text-rose-300 flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{testResult.error}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
