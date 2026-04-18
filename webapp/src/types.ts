export interface SimState {
  vCap: number;          // Current capacitor voltage (V)
  vSource: number;       // Source voltage (V)
  isCharging: boolean;   // Charging switch state
  isArmed: boolean;      // Safety interlock state
  isDischarging: boolean; // Discharge event active
  pulseHistory: number[]; // History for oscilloscope
  lastPulseTime: number;  // Timestamp of last pulse
  energyJoules: number;   // Stored energy (J = 0.5 * C * V^2)
}

export const SIM_CONSTANTS = {
  C_TOTAL: 0.6e-6,       // 0.6 uF
  R_LIMIT: 10000,        // 10k Ohm (Charging resistor)
  Z_0: 50,               // 50 Ohm impedance
  V_MAX: 5000,           // 5kV
  PULSE_DURATION_NS: 100, // 100ns
};
