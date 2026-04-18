import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Zap, Shield, Power, AlertTriangle, Activity, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Oscilloscope } from './Oscilloscope';
import { SimState, SIM_CONSTANTS } from '../types';

export const EMPSimulator: React.FC = () => {
  const [state, setState] = useState<SimState>({
    vCap: 0,
    vSource: 5000,
    isCharging: false,
    isArmed: false,
    isDischarging: false,
    pulseHistory: new Array(100).fill(0),
    lastPulseTime: 0,
    energyJoules: 0,
  });

  const [logs, setLogs] = useState<string[]>(["SYSTEM READY", "INTERLOCK ACTIVE"]);
  const requestRef = useRef<number>(null);
  const lastUpdateRef = useRef<number>(performance.now());

  const addLog = (msg: string) => {
    setLogs(prev => [msg, ...prev].slice(0, 5));
  };

  const updateSim = useCallback((time: number) => {
    const dt = (time - lastUpdateRef.current) / 1000; // seconds
    lastUpdateRef.current = time;

    setState(prev => {
      let nextVCap = prev.vCap;

      // Charging logic: V(t) = Vsource * (1 - e^-t/RC)
      // Differential form: dV = (Vsource - Vcap) * (dt / RC)
      if (prev.isCharging) {
        const dV = (prev.vSource - prev.vCap) * (dt / (SIM_CONSTANTS.R_LIMIT * SIM_CONSTANTS.C_TOTAL));
        nextVCap = Math.min(prev.vSource, prev.vCap + dV);
      } else {
        // Natural discharge (Bleeder resistor simulation)
        const dV = prev.vCap * (dt / (1000000 * SIM_CONSTANTS.C_TOTAL)); // 1M Ohm bleeder
        nextVCap = Math.max(0, prev.vCap - dV);
      }

      const energy = 0.5 * SIM_CONSTANTS.C_TOTAL * Math.pow(nextVCap, 2);

      return {
        ...prev,
        vCap: nextVCap,
        energyJoules: energy,
      };
    });

    requestRef.current = requestAnimationFrame(updateSim);
  }, []);

  useEffect(() => {
    requestRef.current = requestAnimationFrame(updateSim);
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [updateSim]);

  const handleFire = () => {
    if (!state.isArmed) {
      addLog("FIRE ABORTED: SYSTEM NOT ARMED");
      return;
    }
    if (state.vCap < 1000) {
      addLog("FIRE ABORTED: INSUFFICIENT CHARGE");
      return;
    }

    // Generate pulse data for oscilloscope
    // A PFN pulse is roughly rectangular with some ringing
    const pulseData = new Array(100).fill(0).map((_, i) => {
      if (i < 10) return 0;
      if (i < 40) return (state.vCap / 2) * (1 + 0.1 * Math.sin(i * 0.5)); // Main pulse ~V/2
      if (i < 50) return (state.vCap / 4) * Math.exp(-(i - 40) * 0.5); // Fall off
      return 0;
    });

    setState(prev => ({
      ...prev,
      isDischarging: true,
      vCap: 0,
      pulseHistory: pulseData,
      lastPulseTime: Date.now(),
    }));

    addLog(`PULSE GENERATED: ${Math.round(state.vCap / 2)}V @ 100ns`);
    
    setTimeout(() => {
      setState(prev => ({ ...prev, isDischarging: false }));
    }, 500);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 max-w-7xl mx-auto">
      {/* Left Column: Controls */}
      <div className="lg:col-span-4 space-y-6">
        <Card className="hardware-panel text-zinc-100">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-xl font-mono flex items-center gap-2">
                <Power className="w-5 h-5 text-zinc-400" />
                POWER CONTROL
              </CardTitle>
              <Badge variant={state.isCharging ? "default" : "secondary"} className={state.isCharging ? "bg-green-600" : ""}>
                {state.isCharging ? "CHARGING" : "IDLE"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <Label className="text-zinc-400 uppercase text-xs font-bold tracking-widest">Source Voltage (V)</Label>
                <span className="font-mono text-zinc-100">{state.vSource}V</span>
              </div>
              <Slider
                value={[state.vSource]}
                min={1000}
                max={5000}
                step={100}
                onValueChange={(val) => setState(prev => ({ ...prev, vSource: val[0] }))}
                disabled={state.isCharging}
              />
            </div>

            <Separator className="bg-zinc-800" />

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-zinc-100">Charge Switch (S1)</Label>
                <p className="text-xs text-zinc-500">Enable HV charging circuit</p>
              </div>
              <Switch
                checked={state.isCharging}
                onCheckedChange={(val) => {
                  setState(prev => ({ ...prev, isCharging: val }));
                  addLog(val ? "CHARGING CIRCUIT CLOSED" : "CHARGING CIRCUIT OPEN");
                }}
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-zinc-100">Safety Interlock (S2)</Label>
                <p className="text-xs text-zinc-500">Arm SCR/IGBT trigger</p>
              </div>
              <Switch
                checked={state.isArmed}
                onCheckedChange={(val) => {
                  setState(prev => ({ ...prev, isArmed: val }));
                  addLog(val ? "SYSTEM ARMED - DANGER" : "SYSTEM DISARMED");
                }}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="hardware-panel text-zinc-100">
          <CardHeader>
            <CardTitle className="text-xl font-mono flex items-center gap-2">
              <Activity className="w-5 h-5 text-zinc-400" />
              SYSTEM LOGS
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="lcd-display p-3 rounded h-32 overflow-hidden text-[10px] space-y-1">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-2">
                  <span className="opacity-50">[{new Date().toLocaleTimeString()}]</span>
                  <span className={log.includes("PULSE") ? "text-yellow-400" : log.includes("DANGER") ? "text-red-500" : ""}>
                    {log}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Right Column: Visualization */}
      <div className="lg:col-span-8 space-y-6">
        <Card className="hardware-panel text-zinc-100 overflow-hidden">
          <div className="p-6 flex flex-col md:flex-row gap-8">
            {/* Voltage Gauge */}
            <div className="flex-1 space-y-4">
              <div className="flex justify-between items-end">
                <div className="space-y-1">
                  <Label className="text-zinc-400 uppercase text-xs font-bold tracking-widest">Capacitor Potential</Label>
                  <div className="text-4xl font-mono font-bold text-zinc-100">
                    {Math.round(state.vCap).toLocaleString()}<span className="text-xl text-zinc-500 ml-1">V</span>
                  </div>
                </div>
                <div className="text-right space-y-1">
                  <Label className="text-zinc-400 uppercase text-xs font-bold tracking-widest">Stored Energy</Label>
                  <div className="text-xl font-mono text-zinc-300">
                    {state.energyJoules.toFixed(2)}<span className="text-sm text-zinc-500 ml-1">J</span>
                  </div>
                </div>
              </div>

              {/* Progress Bar Gauge */}
              <div className="h-4 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
                <motion.div
                  className="h-full bg-gradient-to-r from-blue-600 via-yellow-500 to-red-600"
                  initial={{ width: 0 }}
                  animate={{ width: `${(state.vCap / 5000) * 100}%` }}
                  transition={{ type: "spring", bounce: 0, duration: 0.1 }}
                />
              </div>

              <div className="grid grid-cols-5 text-[10px] text-zinc-500 font-mono">
                <span>0V</span>
                <span>1.25kV</span>
                <span>2.5kV</span>
                <span>3.75kV</span>
                <span className="text-right">5kV</span>
              </div>
            </div>

            {/* Fire Button Section */}
            <div className="flex flex-col items-center justify-center gap-4 px-8 border-l border-zinc-800">
              <AnimatePresence>
                {state.isArmed && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    className="flex items-center gap-2 text-red-500 animate-pulse"
                  >
                    <AlertTriangle className="w-4 h-4" />
                    <span className="text-[10px] font-bold tracking-tighter uppercase">High Voltage Armed</span>
                  </motion.div>
                )}
              </AnimatePresence>
              
              <button
                onClick={handleFire}
                disabled={!state.isArmed || state.vCap < 1000}
                className={`
                  relative w-24 h-24 rounded-full border-4 flex items-center justify-center transition-all duration-200
                  ${state.isArmed && state.vCap >= 1000 
                    ? "bg-red-600 border-red-400 hover:bg-red-500 active:scale-95 glow-red cursor-pointer" 
                    : "bg-zinc-800 border-zinc-700 cursor-not-allowed opacity-50"}
                `}
              >
                <Zap className={`w-10 h-10 ${state.isArmed ? "text-white" : "text-zinc-600"}`} />
                <div className="absolute -bottom-8 text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Trigger</div>
              </button>
            </div>
          </div>
        </Card>

        {/* Oscilloscope Card */}
        <Card className="hardware-panel text-zinc-100">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-mono flex items-center gap-2">
                <Activity className="w-4 h-4 text-green-500" />
                PFN DISCHARGE WAVEFORM
              </CardTitle>
              <div className="flex gap-4 text-[10px] font-mono text-zinc-500">
                <span>TIMEBASE: 20ns/div</span>
                <span>COUPLING: DC</span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Oscilloscope data={state.pulseHistory} trigger={state.lastPulseTime} />
            <div className="mt-4 flex items-start gap-3 p-3 bg-zinc-900/50 rounded border border-zinc-800">
              <Info className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                The Pulse Forming Network (PFN) converts stored energy into a rectangular pulse. 
                With an impedance of <span className="text-zinc-200">50Ω</span> and total capacitance of <span className="text-zinc-200">0.6μF</span>, 
                the theoretical pulse width is approximately <span className="text-zinc-200">100ns</span>. 
                Output voltage is <span className="text-zinc-200">V_cap / 2</span> under matched load conditions.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
