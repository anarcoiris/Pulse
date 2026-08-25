/**
 * PulseLab Generative EDA Platform - TypeScript Type Definitions
 */

export interface ComponentSpec {
  etype: string;
  value: string;
  symbol?: string;
  footprint?: string;
  footprint_id?: string;
  position?: [number, number];
  rotation?: number;
  pins?: Record<string, string>;
  n1?: string;
  n2?: string;
  label: string;
  jlcpcb_part?: string;
}

export interface NetClassParams {
  clearance: number;
  trace_width: number;
  via_dia: number;
  via_drill: number;
  nets?: string[];
}

export interface CircuitDesignSchema {
  name: string;
  version: string;
  board_width: number;
  board_height: number;
  net_classes?: Record<string, NetClassParams>;
  circuit: ComponentSpec[];
}

export interface VectorPad {
  number: string;
  x: number;
  y: number;
  width: number;
  height: number;
  shape: string;
  net: string;
  layer: string;
}

export interface VectorComponent {
  ref: string;
  value: string;
  footprint: string;
  x: number;
  y: number;
  layer: string;
  rotation: number;
  width?: number;
  height?: number;
  thickness?: number;
  package_type?: string;
  body_color?: string;
  pin1_corner?: string;
  courtyard_margin?: number;
  lead_type?: string;
  pads: VectorPad[];
  lines?: [[number, number], [number, number], string][];
  circles?: [[number, number], number, string][];
}

export interface VectorTrace {
  start: [number, number];
  end: [number, number];
  width: number;
  layer: string;
  net: string;
}

export interface VectorVia {
  x: number;
  y: number;
  diameter: number;
  drill: number;
  net: string;
}

export interface VectorMountingHole {
  x: number;
  y: number;
  drill: number;
  pad_dia: number;
  ref: string;
}

export interface VectorZone {
  net: string;
  layer: string;
  polygon: [number, number][];
}

export interface PCBVectors2D {
  board: {
    width: number;
    height: number;
    origin_x: number;
    origin_y: number;
    corner_radius: number;
  };
  components: VectorComponent[];
  traces: VectorTrace[];
  vias: VectorVia[];
  zones: VectorZone[];
  mounting_holes: VectorMountingHole[];
}

export interface Mesh3DComponent {
  ref: string;
  value: string;
  x: number;
  y: number;
  z: number;
  width: number;
  length: number;
  height: number;
  rotation: number;
  package_type: string;
  body_color?: string;
  color: string;
}

export interface Mesh3DData {
  board: {
    width: number;
    height: number;
    thickness: number;
    color: string;
    copper_color: string;
    silkscreen_color: string;
  };
  components: Mesh3DComponent[];
}

export interface ProviderItem {
  part_number?: string;
  mpn?: string;
  manufacturer?: string;
  stock?: number;
  unit_price_usd?: number;
  library_type?: string;
  datasheet_url?: string;
  in_stock?: boolean;
}

export interface BOMRow {
  label: string;
  value: string;
  etype: string;
  footprint: string;
  jlcpcb: ProviderItem;
  pcbway: ProviderItem;
  recommendation: string;
}

export interface DRCFinding {
  rule: string;
  severity: "error" | "warning" | "info";
  location: string;
  message: string;
}

export interface VisualViolation {
  rule_id: string;
  severity: "error" | "warning" | "info";
  component_ref: string;
  location: [number, number];
  message: string;
  suggested_fix: string;
}

export interface CourtyardInfo {
  ref: string;
  x: number;
  y: number;
  width: number;
  height: number;
  margin: number;
  rotation: number;
  package_type: string;
}

export interface VisualInspectionReport {
  passed: boolean;
  visual_score: number;
  violations_count: number;
  violations: VisualViolation[];
  courtyards: CourtyardInfo[];
  radar?: {
    clearance: number;
    signal_integrity: number;
    thermal: number;
    rf_compliance: number;
    ergonomics: number;
  };
  stats: Record<string, any>;
}

export interface GeneratePCBResponse {
  success: boolean;
  project_id: string;
  board_width: number;
  board_height: number;
  sch_path: string;
  pcb_path: string;
  audit: {
    passed: boolean;
    errors_count: number;
    warnings_count: number;
    info_count: number;
    findings: DRCFinding[];
  };
  visual_inspection?: VisualInspectionReport;
  crosscheck: {
    parity_match: boolean;
    sch_symbols_count: number;
    pcb_footprints_count: number;
    mismatches: string[];
  };
  supply_chain: {
    bom: BOMRow[];
    total_cost_jlc: number;
    total_cost_pcbway: number;
    components_in_stock: number;
    total_components: number;
  };
  vectors_2d: PCBVectors2D;
  mesh_3d: Mesh3DData;
}

export interface PresetInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  dimensions: [number, number];
  components_count: number;
}

export interface CircuitPatchAction {
  action_type: "ADD_COMPONENT" | "REMOVE_COMPONENT" | "UPDATE_COMPONENT" | "REROUTE" | string;
  label?: string;
  etype?: string;
  value?: string;
  footprint?: string;
  pins?: Record<string, string>;
  position?: [number, number];
  rotation?: number;
  description?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  patches?: CircuitPatchAction[];
  metadata?: Record<string, any>;
}

export interface ChatSessionSummary {
  session_id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message: string;
}

export interface ChatSessionDetail {
  session_id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface AgentStep {
  step_number: number;
  phase: string;
  action: string;
  description: string;
  details?: Record<string, any>;
  timestamp: string;
  elapsed_s: number;
}

export interface AgentRunResult {
  success: boolean;
  project_id: string;
  run_id: string;
  prompt: string;
  circuit_data: CircuitDesignSchema;
  components_count: number;
  pin_coverage: {
    average_coverage: number | null;
    per_component: Array<{
      label: string;
      value: string;
      generated_pins: number;
      total_pins: number;
      coverage: number;
      source: string;
    }>;
    unmatched: Array<{ label: string; value: string }>;
  };
  semantic_issues: Array<{
    msg: string;
    severity: "warning" | "critical";
    proposal: string;
  }>;
  critical_issues_count: number;
  drc_errors_count: number;
  drc_warnings_count: number;
  visual_score: number;
  visual_violations_count: number;
  correction_cycles: number;
  steps: AgentStep[];
  pcb_path: string;
  sch_path: string;
  output_dir: string;
  vectors_2d: VectorLayerCollection;
  mesh_3d: Mesh3DCollection;
  supply_chain: SupplyChainSummary;
}

