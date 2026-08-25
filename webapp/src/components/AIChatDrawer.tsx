import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  Send,
  Plus,
  Trash2,
  Sparkles,
  Zap,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Layers,
  ChevronRight,
  ShieldCheck,
  Bot,
  User,
  X,
  Edit2,
  CornerDownLeft
} from 'lucide-react';
import {
  ChatSessionSummary,
  ChatSessionDetail,
  ChatMessage,
  CircuitPatchAction,
  GeneratePCBResponse
} from '../types';

interface AIChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  circuitData: any;
  genResponse: GeneratePCBResponse | null;
  onApplyPatch: (patches: CircuitPatchAction[]) => Promise<void>;
  apiBase: string;
}

export const AIChatDrawer: React.FC<AIChatDrawerProps> = ({
  isOpen,
  onClose,
  projectId,
  circuitData,
  genResponse,
  onApplyPatch,
  apiBase,
}) => {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ChatSessionDetail | null>(null);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [appliedPatches, setAppliedPatches] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 1. Fetch sessions list on open
  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen, projectId]);

  const loadSessions = async () => {
    try {
      const res = await fetch(`${apiBase}/chat/sessions?project_id=${projectId || 'default'}`);
      if (res.ok) {
        const data = await res.json();
        const sessList: ChatSessionSummary[] = data.sessions || [];
        setSessions(sessList);
        if (sessList.length > 0 && !activeSessionId) {
          selectSession(sessList[0].session_id);
        }
      }
    } catch (err) {
      console.error('Failed to load chat sessions:', err);
    }
  };

  const selectSession = async (sessionId: string) => {
    setActiveSessionId(sessionId);
    try {
      const res = await fetch(`${apiBase}/chat/sessions/${sessionId}?project_id=${projectId || 'default'}`);
      if (res.ok) {
        const data = await res.json();
        setActiveSession(data.session);
      }
    } catch (err) {
      console.error('Failed to fetch session detail:', err);
    }
  };

  const handleCreateSession = async () => {
    try {
      const title = `Session ${sessions.length + 1}`;
      const res = await fetch(`${apiBase}/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId || 'default', title }),
      });
      if (res.ok) {
        const data = await res.json();
        await loadSessions();
        if (data.session) {
          selectSession(data.session.session_id);
        }
      }
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${apiBase}/chat/sessions/${sessionId}?project_id=${projectId || 'default'}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        const remaining = sessions.filter((s) => s.session_id !== sessionId);
        setSessions(remaining);
        if (activeSessionId === sessionId && remaining.length > 0) {
          selectSession(remaining[0].session_id);
        } else if (remaining.length === 0) {
          handleCreateSession();
        }
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputPrompt;
    if (!text.trim() || !activeSessionId || isLoading) return;

    setInputPrompt('');
    setIsLoading(true);

    // Optimistic user message append
    const tempUserMsg: ChatMessage = {
      id: `temp_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    if (activeSession) {
      setActiveSession({
        ...activeSession,
        messages: [...activeSession.messages, tempUserMsg],
      });
    }

    try {
      const res = await fetch(`${apiBase}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId || 'default',
          session_id: activeSessionId,
          message: text,
          circuit_data: circuitData,
          audit_data: genResponse?.audit,
          visual_data: genResponse?.visual_inspection,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.session) {
          setActiveSession(data.session);
        }
      }
    } catch (err) {
      console.error('Send message failed:', err);
    } finally {
      setIsLoading(false);
      setTimeout(scrollToBottom, 100);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [activeSession?.messages, isLoading]);

  const handleApplyCardPatch = async (patchKey: string, patches: CircuitPatchAction[]) => {
    try {
      setAppliedPatches((prev) => ({ ...prev, [patchKey]: true }));
      await onApplyPatch(patches);
    } catch (err) {
      console.error('Failed to apply card patch:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-[520px] bg-[#0c0e15] border-l border-zinc-800 shadow-2xl z-50 flex flex-col font-sans select-none animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="h-14 border-b border-zinc-800 px-4 flex items-center justify-between bg-[#10121b]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-zinc-100 font-mono">PULSELAB CO-PILOT</h2>
              <span className="text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-mono border border-emerald-500/30">
                LOCAL LLM ACTIVE
              </span>
            </div>
            <p className="text-[10px] text-zinc-500">Continuous Human + AI Circuit & PCB Co-Design</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Multi-Session Tabs Bar */}
      <div className="border-b border-zinc-800 bg-[#08090d] px-3 py-2 flex items-center gap-1.5 overflow-x-auto scrollbar-none">
        {sessions.map((s) => (
          <div
            key={s.session_id}
            onClick={() => selectSession(s.session_id)}
            className={`group flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-mono cursor-pointer border transition-all ${
              activeSessionId === s.session_id
                ? 'bg-zinc-800/90 text-amber-300 border-amber-500/40 shadow'
                : 'bg-zinc-900/60 text-zinc-400 border-zinc-800 hover:bg-zinc-850 hover:text-zinc-200'
            }`}
          >
            <MessageSquare className="w-3 h-3 text-zinc-400 group-hover:text-amber-400" />
            <span className="truncate max-w-[110px]">{s.title}</span>
            <button
              onClick={(e) => handleDeleteSession(s.session_id, e)}
              className="opacity-0 group-hover:opacity-100 hover:text-rose-400 transition-opacity ml-1"
            >
              ✕
            </button>
          </div>
        ))}

        <button
          onClick={handleCreateSession}
          className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-900/80 hover:bg-zinc-800 border border-dashed border-zinc-700 transition-colors whitespace-nowrap"
          title="Start New Chat Session"
        >
          <Plus className="w-3 h-3" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Design Context Status Bar */}
      <div className="px-4 py-2 bg-zinc-900/40 border-b border-zinc-800/60 flex items-center justify-between text-[11px] text-zinc-400 font-mono">
        <div className="flex items-center gap-2">
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          <span>{circuitData?.circuit?.length || 0} Parts</span>
          <span className="text-zinc-600">•</span>
          <span>{circuitData?.board_width || 75}x{circuitData?.board_height || 50}mm</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] ${
              genResponse?.audit?.passed ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
            }`}
          >
            {genResponse?.audit?.passed ? 'DRC: CLEAN' : `DRC: ${genResponse?.audit?.errors_count || 0} ERR`}
          </span>
          <span className="bg-cyan-500/10 text-cyan-300 px-1.5 py-0.5 rounded text-[10px]">
            VISUAL: {genResponse?.visual_inspection?.visual_score || 100}%
          </span>
        </div>
      </div>

      {/* Messages Thread Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans text-xs">
        {activeSession?.messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-zinc-500">
            <Bot className="w-10 h-10 text-zinc-600 mb-2" />
            <h3 className="text-sm font-semibold text-zinc-300">Continuous AI Hardware Assistant</h3>
            <p className="text-xs text-zinc-500 max-w-xs mt-1">
              Ask for component additions, schematic modifications, decoupling cap adjustments, or DRC debugging.
            </p>

            {/* Quick Suggestion Chips */}
            <div className="mt-6 flex flex-col gap-2 w-full max-w-xs">
              <button
                onClick={() => handleSendMessage('Add a green status LED on GPIO5 with a 330 ohm current limiting resistor')}
                className="text-left px-3 py-2 bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800 rounded-lg text-zinc-300 text-xs transition-colors"
              >
                💡 Add status LED on GPIO5
              </button>
              <button
                onClick={() => handleSendMessage('Explain any current DRC violations and suggest how to resolve them')}
                className="text-left px-3 py-2 bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800 rounded-lg text-zinc-300 text-xs transition-colors"
              >
                🔍 Analyze DRC & Visual violations
              </button>
              <button
                onClick={() => handleSendMessage('Add a piezo buzzer circuit driven by an NPN transistor')}
                className="text-left px-3 py-2 bg-zinc-900/80 hover:bg-zinc-800 border border-zinc-800 rounded-lg text-zinc-300 text-xs transition-colors"
              >
                🔊 Add piezo buzzer circuit
              </button>
            </div>
          </div>
        )}

        {activeSession?.messages.map((msg, idx) => {
          const isUser = msg.role === 'user';
          return (
            <div key={msg.id || idx} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
              {!isUser && (
                <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div className={`max-w-[85%] space-y-2`}>
                <div
                  className={`p-3 rounded-xl leading-relaxed whitespace-pre-wrap ${
                    isUser
                      ? 'bg-indigo-600 text-white rounded-tr-none'
                      : 'bg-zinc-900/90 text-zinc-200 border border-zinc-800 rounded-tl-none'
                  }`}
                >
                  {msg.content}
                </div>

                {/* Circuit Patch Action Cards */}
                {msg.patches && msg.patches.length > 0 && (
                  <div className="bg-zinc-950 border border-amber-500/40 rounded-xl p-3 space-y-2 shadow-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-amber-400 font-mono text-[11px] font-bold">
                        <Zap className="w-3.5 h-3.5 fill-current" />
                        <span>PROPOSED CIRCUIT PATCH ({msg.patches.length})</span>
                      </div>
                      <span className="text-[10px] text-zinc-500">1-Click Apply</span>
                    </div>

                    <div className="space-y-1.5 text-[11px] font-mono bg-zinc-900/80 p-2 rounded border border-zinc-800 text-zinc-300">
                      {msg.patches.map((p, pIdx) => (
                        <div key={pIdx} className="flex items-center justify-between">
                          <span className="text-amber-300 font-bold">{p.action_type}</span>
                          <span className="text-zinc-200">{p.label} ({p.etype || p.value || ''})</span>
                        </div>
                      ))}
                    </div>

                    <button
                      onClick={() => handleApplyCardPatch(`patch_${msg.id}`, msg.patches!)}
                      disabled={appliedPatches[`patch_${msg.id}`]}
                      className={`w-full py-2 px-3 rounded-lg font-bold text-xs flex items-center justify-center gap-2 transition-all ${
                        appliedPatches[`patch_${msg.id}`]
                          ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 cursor-default'
                          : 'bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-zinc-950 shadow-md'
                      }`}
                    >
                      {appliedPatches[`patch_${msg.id}`] ? (
                        <>
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Applied to Design</span>
                        </>
                      ) : (
                        <>
                          <Zap className="w-3.5 h-3.5 fill-current" />
                          <span>Apply Patch to Design</span>
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>

              {isUser && (
                <div className="w-7 h-7 rounded-lg bg-zinc-800 flex items-center justify-center text-zinc-300 shrink-0 mt-0.5">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          );
        })}

        {isLoading && (
          <div className="flex gap-3 justify-start">
            <div className="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5">
              <Bot className="w-4 h-4 animate-spin" />
            </div>
            <div className="bg-zinc-900/90 text-zinc-400 border border-zinc-800 rounded-xl p-3 text-xs flex items-center gap-2 font-mono">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span>Reasoning & synthesizing hardware response...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box Footer */}
      <div className="p-3 border-t border-zinc-800 bg-[#0d0e14]">
        <div className="relative bg-zinc-950 border border-zinc-800 rounded-xl focus-within:border-indigo-500 transition-colors p-2">
          <textarea
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            placeholder="Ask AI or instruct a circuit change (e.g. 'Add an RGB LED on GPIO13')..."
            rows={2}
            className="w-full bg-transparent text-xs text-zinc-200 placeholder-zinc-600 focus:outline-none resize-none"
          />

          <div className="flex items-center justify-between pt-1 text-[11px] text-zinc-500">
            <span>Press <kbd className="bg-zinc-800 px-1 py-0.5 rounded text-[10px]">Enter</kbd> to send</span>
            <button
              onClick={() => handleSendMessage()}
              disabled={!inputPrompt.trim() || isLoading}
              className="p-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg transition-colors"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
