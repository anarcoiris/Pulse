/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { EMPSimulator } from './components/EMPSimulator';
import { Shield, Zap } from 'lucide-react';

export default function App() {
  return (
    <div className="min-h-screen bg-[#0a0b0d] text-zinc-100 font-sans selection:bg-red-500/30">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-[#151619]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-600 rounded flex items-center justify-center shadow-[0_0_20px_rgba(220,38,38,0.4)]">
              <Zap className="text-white w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight leading-none">EMP PULSE GEN</h1>
              <p className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest mt-1">High-Voltage Simulation v1.0.4</p>
            </div>
          </div>
          
          <div className="hidden md:flex items-center gap-6">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <Shield className="w-3 h-3 text-green-500" />
              <span>INTERLOCK: ACTIVE</span>
            </div>
            <div className="h-4 w-px bg-zinc-800" />
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span>HV STATUS: NOMINAL</span>
            </div>
          </div>
        </div>
      </header>

      <main className="py-8">
        <EMPSimulator />
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 py-8 mt-12 bg-[#151619]/30">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <p className="text-[10px] text-zinc-600 font-mono uppercase tracking-[0.2em]">
            Theoretical Model based on PFN Impedance Matching & RC Charging Curves
          </p>
          <p className="text-[9px] text-zinc-700 mt-2">
            © 2026 High-Voltage Research Lab. For Educational Simulation Purposes Only.
          </p>
        </div>
      </footer>
    </div>
  );
}
