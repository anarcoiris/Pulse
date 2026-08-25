import React, { useState, useRef, useEffect, useCallback } from 'react';
import { PCBVectors2D, VectorComponent, VectorPad, VisualInspectionReport, VisualViolation } from '../types';
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  Layers,
  Crosshair,
  ShieldCheck,
  Grid,
  RotateCw,
  Move,
  CheckCircle,
  AlertTriangle,
  Info,
  Sliders,
  RefreshCw,
  Eye,
  Lock,
  Unlock
} from 'lucide-react';

interface PCBViewer2DProps {
  vectors: PCBVectors2D | null;
  boardWidth: number;
  boardHeight: number;
  selectedNet: string | null;
  onSelectNet: (net: string | null) => void;
  onUpdateComponentPosition?: (ref: string, newPos: [number, number], newRot?: number) => void;
  visualInspection?: VisualInspectionReport | null;
}

export const PCBViewer2D: React.FC<PCBViewer2DProps> = ({
  vectors,
  boardWidth,
  boardHeight,
  selectedNet,
  onSelectNet,
  onUpdateComponentPosition,
  visualInspection,
}) => {
  const [zoom, setZoom] = useState(8.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // Selection & Interactive Drag State
  const [selectedCompRef, setSelectedCompRef] = useState<string | null>(null);
  const [draggingCompRef, setDraggingCompRef] = useState<string | null>(null);
  const [dragCurrentPos, setDragCurrentPos] = useState<{ x: number; y: number } | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [hasCollision, setHasCollision] = useState(false);

  // Hover States
  const [hoveredComp, setHoveredComp] = useState<VectorComponent | null>(null);
  const [hoveredPad, setHoveredPad] = useState<{ comp: VectorComponent; pad: VectorPad } | null>(null);
  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);

  // Layer Visibility & Overlays
  const [showFCu, setShowFCu] = useState(true);
  const [showBCu, setShowBCu] = useState(true);
  const [showSilk, setShowSilk] = useState(true);
  const [showPads, setShowPads] = useState(true);
  const [showVias, setShowVias] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showClearance, setShowClearance] = useState(false);
  const [showInspection, setShowInspection] = useState(true);
  const [gridMode, setGridMode] = useState<'1mm' | '0.5mm' | '2.54mm' | '0.1mm' | 'off'>('1mm');
  const [lockLayout, setLockLayout] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Center view on load
  useEffect(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setPan({
        x: rect.width / 2,
        y: rect.height / 2,
      });
      const fitZoom = Math.min((rect.width - 120) / boardWidth, (rect.height - 120) / boardHeight);
      setZoom(Math.max(3.0, Math.min(12.0, fitZoom)));
    }
  }, [boardWidth, boardHeight, vectors]);

  // Grid step in mm
  const gridStep =
    gridMode === '1mm'
      ? 1.0
      : gridMode === '0.5mm'
      ? 0.5
      : gridMode === '2.54mm'
      ? 2.54
      : gridMode === '0.1mm'
      ? 0.1
      : 0;

  const snapToGrid = useCallback(
    (val: number) => {
      if (gridStep <= 0) return Number(val.toFixed(2));
      return Number((Math.round(val / gridStep) * gridStep).toFixed(2));
    },
    [gridStep]
  );

  // Collision detection during drag
  const checkDragCollision = useCallback(
    (targetRef: string, testX: number, testY: number, targetComp: VectorComponent) => {
      if (!vectors) return false;
      const targetW = targetComp.width || 3.0;
      const targetH = targetComp.height || 2.0;
      const targetMargin = targetComp.courtyard_margin || 0.35;
      const edgeKeepout = 2.5;

      const bw = vectors.board.width;
      const bh = vectors.board.height;

      // Board edge collision (unless external connector)
      const isConnector = targetComp.package_type === 'CONNECTOR' || targetComp.package_type === 'HEADER';
      if (!isConnector) {
        if (
          Math.abs(testX) + (targetW / 2 + targetMargin) > bw / 2 - edgeKeepout ||
          Math.abs(testY) + (targetH / 2 + targetMargin) > bh / 2 - edgeKeepout
        ) {
          return true;
        }
      } else {
        if (Math.abs(testX) > bw / 2 + 1.0 || Math.abs(testY) > bh / 2 + 1.0) {
          return true;
        }
      }

      // Check courtyard overlap against all other components
      for (const other of vectors.components) {
        if (other.ref === targetRef) continue;
        const otherW = other.width || 3.0;
        const otherH = other.height || 2.0;
        const otherMargin = other.courtyard_margin || 0.35;

        const reqDx = (targetW + otherW) / 2 + (targetMargin + otherMargin);
        const reqDy = (targetH + otherH) / 2 + (targetMargin + otherMargin);

        const dx = Math.abs(testX - other.x);
        const dy = Math.abs(testY - other.y);

        if (dx < reqDx && dy < reqDy) {
          return true;
        }
      }

      return false;
    },
    [vectors]
  );

  // Keyboard Shortcuts (Rotate, Deselect)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedCompRef || lockLayout) return;

      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        const comp = vectors?.components.find((c) => c.ref === selectedCompRef);
        if (comp && onUpdateComponentPosition) {
          const delta = e.shiftKey ? -90 : 90;
          const newRot = (comp.rotation + delta + 360) % 360;
          onUpdateComponentPosition(comp.ref, [comp.x, comp.y], newRot);
        }
      } else if (e.key === 'Escape') {
        setSelectedCompRef(null);
        setDraggingCompRef(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedCompRef, vectors, onUpdateComponentPosition, lockLayout]);

  // Mouse Handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    // If not clicking a component, pan the board
    if (e.button === 0 || e.button === 1) {
      if (!draggingCompRef) {
        setIsPanning(true);
        setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      }
    }
  };

  const handleComponentMouseDown = (e: React.MouseEvent, comp: VectorComponent) => {
    e.stopPropagation();
    if (lockLayout) return;

    setSelectedCompRef(comp.ref);
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const mouseBoardX = (e.clientX - rect.left - pan.x) / zoom;
      const mouseBoardY = (e.clientY - rect.top - pan.y) / zoom;

      setDraggingCompRef(comp.ref);
      setDragOffset({
        x: mouseBoardX - comp.x,
        y: mouseBoardY - comp.y,
      });
      setDragCurrentPos({ x: comp.x, y: comp.y });
      setHasCollision(false);
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const mouseBoardX = (e.clientX - rect.left - pan.x) / zoom;
      const mouseBoardY = (e.clientY - rect.top - pan.y) / zoom;

      setCursorPos({
        x: Number(mouseBoardX.toFixed(2)),
        y: Number(mouseBoardY.toFixed(2)),
      });

      // Handle Component Dragging
      if (draggingCompRef && vectors) {
        const comp = vectors.components.find((c) => c.ref === draggingCompRef);
        if (comp) {
          const rawX = mouseBoardX - dragOffset.x;
          const rawY = mouseBoardY - dragOffset.y;
          const snappedX = snapToGrid(rawX);
          const snappedY = snapToGrid(rawY);

          setDragCurrentPos({ x: snappedX, y: snappedY });
          const collision = checkDragCollision(draggingCompRef, snappedX, snappedY, comp);
          setHasCollision(collision);
        }
        return;
      }
    }

    // Handle Pan
    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    if (draggingCompRef && dragCurrentPos && onUpdateComponentPosition && vectors) {
      const comp = vectors.components.find((c) => c.ref === draggingCompRef);
      if (comp && (comp.x !== dragCurrentPos.x || comp.y !== dragCurrentPos.y)) {
        onUpdateComponentPosition(comp.ref, [dragCurrentPos.x, dragCurrentPos.y], comp.rotation);
      }
    }

    setIsPanning(false);
    setDraggingCompRef(null);
    setDragCurrentPos(null);
    setHasCollision(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    setZoom((prev) => Math.max(1.0, Math.min(35.0, prev * zoomFactor)));
  };

  const resetView = () => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setPan({ x: rect.width / 2, y: rect.height / 2 });
      const fitZoom = Math.min((rect.width - 120) / boardWidth, (rect.height - 120) / boardHeight);
      setZoom(Math.max(3.0, Math.min(12.0, fitZoom)));
    }
  };

  const rotateSelected = (clockwise: boolean = true) => {
    if (!selectedCompRef || !vectors || !onUpdateComponentPosition || lockLayout) return;
    const comp = vectors.components.find((c) => c.ref === selectedCompRef);
    if (comp) {
      const delta = clockwise ? 90 : -90;
      const newRot = (comp.rotation + delta + 360) % 360;
      onUpdateComponentPosition(comp.ref, [comp.x, comp.y], newRot);
    }
  };

  if (!vectors) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-zinc-950 text-zinc-400 p-8 border border-zinc-800/80 rounded-xl">
        <h3 className="text-base font-semibold text-zinc-200">No PCB Layout Generated Yet</h3>
        <p className="text-xs text-zinc-500 max-w-sm text-center mt-1">
          Input a natural language prompt or pick a preset from the sidebar, then click "Generate Circuit & PCB".
        </p>
      </div>
    );
  }

  const { board, components, traces, vias, zones, mounting_holes } = vectors;
  const bw = board.width;
  const bh = board.height;
  const cr = board.corner_radius || 1.5;

  const selectedComp = components.find((c) => c.ref === selectedCompRef);

  return (
    <div className="relative w-full h-full bg-[#090a0f] overflow-hidden rounded-xl border border-zinc-800 shadow-2xl flex flex-col select-none font-sans">
      {/* Top Header Controls Bar */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-zinc-900/95 backdrop-blur-md px-3 py-2 rounded-lg border border-zinc-800 text-xs text-zinc-300 shadow-xl">
        <div className="flex items-center gap-1.5 font-bold text-amber-400 pr-2 border-r border-zinc-700">
          <Layers className="w-4 h-4" />
          <span>2D INTERACTIVE CAD</span>
        </div>

        {/* Grid Selector */}
        <div className="flex items-center gap-1.5 pl-1 pr-2 border-r border-zinc-700">
          <Grid className="w-3.5 h-3.5 text-zinc-400" />
          <span className="text-zinc-400 text-[11px]">Grid:</span>
          <select
            value={gridMode}
            onChange={(e) => setGridMode(e.target.value as any)}
            className="bg-zinc-800 text-zinc-200 border border-zinc-700 rounded px-1.5 py-0.5 text-xs outline-none focus:border-amber-500 cursor-pointer"
          >
            <option value="1mm">1.0 mm (Standard)</option>
            <option value="0.5mm">0.5 mm (Fine)</option>
            <option value="2.54mm">2.54 mm (100 mil)</option>
            <option value="0.1mm">0.1 mm (Ultra)</option>
            <option value="off">Free (Off)</option>
          </select>
        </div>

        {/* Lock / Unlock Edits */}
        <button
          onClick={() => setLockLayout(!lockLayout)}
          title={lockLayout ? 'Unlock Layout Dragging' : 'Lock Layout Positions'}
          className={`flex items-center gap-1 px-2 py-1 rounded transition-colors ${
            lockLayout ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
          }`}
        >
          {lockLayout ? <Lock className="w-3 h-3" /> : <Unlock className="w-3 h-3" />}
          <span>{lockLayout ? 'Locked' : 'Editable'}</span>
        </button>

        {/* DRC Clearance Visualizer Toggle */}
        <button
          onClick={() => setShowClearance(!showClearance)}
          className={`flex items-center gap-1 px-2 py-1 rounded transition-colors ${
            showClearance ? 'bg-red-500/20 text-red-400 border border-red-500/40' : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Clearance (6 mil)</span>
        </button>

        {/* Visual Inspection Overlays Toggle */}
        <button
          onClick={() => setShowInspection(!showInspection)}
          className={`flex items-center gap-1 px-2 py-1 rounded transition-colors ${
            showInspection ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          <span>Inspection Gate</span>
        </button>
      </div>

      {/* Selected Component Floating Action Toolbar */}
      {selectedComp && (
        <div className="absolute top-16 left-4 z-20 flex items-center gap-3 bg-zinc-900/95 backdrop-blur-md px-3.5 py-2 rounded-lg border border-amber-500/50 shadow-2xl text-xs text-zinc-200 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="flex items-center gap-1.5 font-mono font-bold text-amber-400">
            <Move className="w-3.5 h-3.5" />
            <span>{selectedComp.ref}</span>
            <span className="text-[10px] text-zinc-400 font-sans font-normal px-1.5 py-0.5 bg-zinc-800 rounded">
              {selectedComp.package_type || 'PART'}
            </span>
          </div>

          <div className="flex items-center gap-2 text-zinc-400 font-mono text-[11px]">
            <span>X: <strong className="text-zinc-200">{selectedComp.x.toFixed(2)}mm</strong></span>
            <span>Y: <strong className="text-zinc-200">{selectedComp.y.toFixed(2)}mm</strong></span>
            <span>Rot: <strong className="text-zinc-200">{selectedComp.rotation}°</strong></span>
          </div>

          <button
            onClick={() => rotateSelected(true)}
            disabled={lockLayout}
            title="Rotate 90° Clockwise (Shortcut: R)"
            className="flex items-center gap-1 px-2 py-1 bg-amber-500 hover:bg-amber-400 text-zinc-950 font-bold rounded transition-colors shadow"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Rotate 90°</span>
          </button>

          <button
            onClick={() => setSelectedCompRef(null)}
            className="text-zinc-500 hover:text-zinc-300 text-xs px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Top Right Zoom & Pan Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1 bg-zinc-900/90 backdrop-blur-md p-1.5 rounded-lg border border-zinc-800 shadow-lg">
        <button
          onClick={() => setZoom((prev) => Math.min(prev * 1.25, 35.0))}
          className="p-1.5 hover:bg-zinc-800 rounded text-zinc-300 transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => setZoom((prev) => Math.max(prev * 0.8, 1.0))}
          className="p-1.5 hover:bg-zinc-800 rounded text-zinc-300 transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={resetView}
          className="p-1.5 hover:bg-zinc-800 rounded text-zinc-300 transition-colors"
          title="Fit Board"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>

      {/* Bottom Left Live Coordinate HUD */}
      <div className="absolute bottom-4 left-4 z-20 flex items-center gap-3 bg-zinc-900/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-zinc-800 text-[11px] text-zinc-400 font-mono shadow-lg">
        <div className="flex items-center gap-1.5 text-zinc-300">
          <Crosshair className="w-3.5 h-3.5 text-amber-400" />
          <span>Origin: (0,0) Center</span>
        </div>
        {cursorPos && (
          <div className="flex items-center gap-2 border-l border-zinc-700 pl-2">
            <span>X: <strong className="text-zinc-200">{cursorPos.x.toFixed(2)} mm</strong></span>
            <span>Y: <strong className="text-zinc-200">{cursorPos.y.toFixed(2)} mm</strong></span>
          </div>
        )}
        {hoveredComp && (
          <div className="border-l border-zinc-700 pl-2 text-amber-300 font-bold">
            [{hoveredComp.ref}: {hoveredComp.value}]
          </div>
        )}
        {hoveredPad && (
          <div className="border-l border-zinc-700 pl-2 text-cyan-300 font-bold">
            Pad {hoveredPad.pad.number} → Net: {hoveredPad.pad.net || 'NC'}
          </div>
        )}
      </div>

      {/* Layer Visibility Floating Dock */}
      <div className="absolute bottom-4 right-4 z-20 flex items-center gap-3 bg-zinc-900/95 backdrop-blur-md px-3 py-2 rounded-lg border border-zinc-800 text-xs shadow-xl">
        <div className="flex items-center gap-1.5 font-bold text-zinc-400 pr-2 border-r border-zinc-700">
          <Layers className="w-3.5 h-3.5 text-zinc-400" />
          <span>LAYERS</span>
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-white">
          <input
            type="checkbox"
            checked={showFCu}
            onChange={(e) => setShowFCu(e.target.checked)}
            className="accent-amber-500 rounded w-3 h-3"
          />
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-zinc-300 text-[11px]">F.Cu</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-white">
          <input
            type="checkbox"
            checked={showBCu}
            onChange={(e) => setShowBCu(e.target.checked)}
            className="accent-cyan-500 rounded w-3 h-3"
          />
          <span className="w-2 h-2 rounded-full bg-cyan-500" />
          <span className="text-zinc-300 text-[11px]">B.Cu</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-white">
          <input
            type="checkbox"
            checked={showSilk}
            onChange={(e) => setShowSilk(e.target.checked)}
            className="accent-zinc-200 rounded w-3 h-3"
          />
          <span className="w-2 h-2 rounded-full bg-zinc-200" />
          <span className="text-zinc-300 text-[11px]">Silk</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-white">
          <input
            type="checkbox"
            checked={showPads}
            onChange={(e) => setShowPads(e.target.checked)}
            className="accent-yellow-400 rounded w-3 h-3"
          />
          <span className="w-2 h-2 rounded-full bg-yellow-400" />
          <span className="text-zinc-300 text-[11px]">Pads</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-white">
          <input
            type="checkbox"
            checked={showVias}
            onChange={(e) => setShowVias(e.target.checked)}
            className="accent-emerald-400 rounded w-3 h-3"
          />
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-zinc-300 text-[11px]">Vias</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer hover:text-white">
          <input
            type="checkbox"
            checked={showZones}
            onChange={(e) => setShowZones(e.target.checked)}
            className="accent-blue-400 rounded w-3 h-3"
          />
          <span className="w-2 h-2 rounded-full bg-blue-400" />
          <span className="text-zinc-300 text-[11px]">GND Pour</span>
        </label>
      </div>

      {/* SVG Canvas Workspace */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        className={`w-full h-full flex-1 ${
          draggingCompRef ? 'cursor-grabbing' : isPanning ? 'cursor-grab' : 'cursor-default'
        }`}
      >
        <svg className="w-full h-full">
          {/* Background Grid Patterns */}
          <defs>
            <pattern id="pcb-grid-01mm" width={0.1 * zoom} height={0.1 * zoom} patternUnits="userSpaceOnUse">
              <path d={`M ${0.1 * zoom} 0 L 0 0 0 ${0.1 * zoom}`} fill="none" stroke="#11151f" strokeWidth="0.25" />
            </pattern>
            <pattern id="pcb-grid-fine" width={1 * zoom} height={1 * zoom} patternUnits="userSpaceOnUse">
              <path d={`M ${1 * zoom} 0 L 0 0 0 ${1 * zoom}`} fill="none" stroke="#141926" strokeWidth="0.5" />
            </pattern>
            <pattern id="pcb-grid-05mm" width={0.5 * zoom} height={0.5 * zoom} patternUnits="userSpaceOnUse">
              <path d={`M ${0.5 * zoom} 0 L 0 0 0 ${0.5 * zoom}`} fill="none" stroke="#161c2b" strokeWidth="0.4" />
            </pattern>
            <pattern id="pcb-grid-imperial" width={2.54 * zoom} height={2.54 * zoom} patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="0.75" fill="#2d3748" />
            </pattern>
          </defs>

          {gridMode === '0.1mm' && <rect width="100%" height="100%" fill="url(#pcb-grid-01mm)" />}
          {gridMode === '0.5mm' && <rect width="100%" height="100%" fill="url(#pcb-grid-05mm)" />}
          {gridMode === '1mm' && <rect width="100%" height="100%" fill="url(#pcb-grid-fine)" />}
          {gridMode === '2.54mm' && <rect width="100%" height="100%" fill="url(#pcb-grid-imperial)" />}

          {/* Main Transformed Board Group (Origin Centered at pan.x, pan.y) */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            {/* Board Substrate Base (FR4 Matte Dark) centered at (0, 0) */}
            <rect
              x={-bw / 2}
              y={-bh / 2}
              width={bw}
              height={bh}
              rx={cr}
              ry={cr}
              fill="#0b1120"
              stroke="#38bdf8"
              strokeWidth="0.35"
              className="filter drop-shadow-[0_0_25px_rgba(56,189,248,0.25)]"
            />

            {/* Board Keepout Perimeter Line */}
            <rect
              x={-bw / 2 + 2.5}
              y={-bh / 2 + 2.5}
              width={bw - 5.0}
              height={bh - 5.0}
              rx={cr}
              fill="none"
              stroke="#3b82f6"
              strokeWidth="0.08"
              strokeDasharray="1.0 1.0"
              strokeOpacity="0.4"
            />

            {/* Copper Zones (Ground Pours) */}
            {showZones &&
              zones.map((z, idx) => {
                const isHighlighted = selectedNet && z.net === selectedNet;
                return (
                  <rect
                    key={`zone-${idx}`}
                    x={-bw / 2 + 0.8}
                    y={-bh / 2 + 0.8}
                    width={bw - 1.6}
                    height={bh - 1.6}
                    rx={cr}
                    fill={z.layer === 'F.Cu' ? (isHighlighted ? '#fbbf24' : '#f59e0b') : '#06b6d4'}
                    fillOpacity={isHighlighted ? 0.35 : 0.12}
                    stroke={isHighlighted ? '#fbbf24' : '#3b82f6'}
                    strokeWidth="0.1"
                    strokeDasharray="0.6 0.6"
                  />
                );
              })}

            {/* Bottom Copper Traces (B.Cu Cyan) */}
            {showBCu &&
              traces
                .filter((tr) => tr.layer !== 'F.Cu')
                .map((tr, idx) => {
                  const isHighlighted = selectedNet && tr.net === selectedNet;
                  return (
                    <g key={`tr-b-${idx}`}>
                      {showClearance && (
                        <line
                          x1={tr.start[0]}
                          y1={tr.start[1]}
                          x2={tr.end[0]}
                          y2={tr.end[1]}
                          stroke="#ef4444"
                          strokeWidth={tr.width + 0.4}
                          strokeOpacity="0.2"
                          strokeLinecap="round"
                        />
                      )}
                      <line
                        x1={tr.start[0]}
                        y1={tr.start[1]}
                        x2={tr.end[0]}
                        y2={tr.end[1]}
                        stroke={isHighlighted ? '#38bdf8' : '#06b6d4'}
                        strokeWidth={isHighlighted ? Math.max(0.4, tr.width * 1.5) : tr.width}
                        strokeLinecap="round"
                        strokeDasharray="0.8 0.4"
                        strokeOpacity="0.85"
                        className="cursor-pointer hover:stroke-cyan-300"
                        onClick={() => onSelectNet(tr.net)}
                      />
                    </g>
                  );
                })}

            {/* Top Copper Traces (F.Cu Amber Gold) */}
            {showFCu &&
              traces
                .filter((tr) => tr.layer === 'F.Cu')
                .map((tr, idx) => {
                  const isHighlighted = selectedNet && tr.net === selectedNet;
                  return (
                    <g key={`tr-f-${idx}`}>
                      {showClearance && (
                        <line
                          x1={tr.start[0]}
                          y1={tr.start[1]}
                          x2={tr.end[0]}
                          y2={tr.end[1]}
                          stroke="#ef4444"
                          strokeWidth={tr.width + 0.4}
                          strokeOpacity="0.25"
                          strokeLinecap="round"
                        />
                      )}
                      <line
                        x1={tr.start[0]}
                        y1={tr.start[1]}
                        x2={tr.end[0]}
                        y2={tr.end[1]}
                        stroke={isHighlighted ? '#fbbf24' : '#f59e0b'}
                        strokeWidth={isHighlighted ? Math.max(0.45, tr.width * 1.6) : tr.width}
                        strokeLinecap="round"
                        className="cursor-pointer hover:stroke-yellow-300"
                        onClick={() => onSelectNet(tr.net)}
                      />
                    </g>
                  );
                })}

            {/* Vias with Annular Ring & Drill Center */}
            {showVias &&
              vias.map((v, idx) => {
                const isHighlighted = selectedNet && v.net === selectedNet;
                return (
                  <g key={`via-${idx}`} onClick={() => onSelectNet(v.net)} className="cursor-pointer">
                    {showClearance && (
                      <circle cx={v.x} cy={v.y} r={(v.diameter + 0.4) / 2} fill="#ef4444" fillOpacity="0.2" />
                    )}
                    {/* Outer Copper Pad */}
                    <circle
                      cx={v.x}
                      cy={v.y}
                      r={v.diameter / 2}
                      fill={isHighlighted ? '#38bdf8' : '#10b981'}
                      stroke="#047857"
                      strokeWidth="0.08"
                    />
                    {/* Drill Hole */}
                    <circle cx={v.x} cy={v.y} r={v.drill / 2} fill="#090a0f" />
                  </g>
                );
              })}

            {/* Mounting Holes */}
            {mounting_holes.map((mh, idx) => (
              <g key={`mh-${idx}`}>
                <circle
                  cx={mh.x}
                  cy={mh.y}
                  r={mh.pad_dia / 2}
                  fill="#eab308"
                  fillOpacity="0.35"
                  stroke="#ca8a04"
                  strokeWidth="0.1"
                />
                <circle cx={mh.x} cy={mh.y} r={mh.drill / 2} fill="#090a0f" stroke="#eab308" strokeWidth="0.08" />
                <text
                  x={mh.x}
                  y={mh.y - mh.pad_dia / 2 - 0.5}
                  fontSize="0.85"
                  fill="#a1a1aa"
                  textAnchor="middle"
                  fontFamily="monospace"
                >
                  {mh.ref}
                </text>
              </g>
            ))}

            {/* Components & Footprints */}
            {components.map((comp, idx) => {
              const isSelected = selectedCompRef === comp.ref;
              const isDraggingThis = draggingCompRef === comp.ref;

              // Render position: use dragCurrentPos if actively dragging this component
              const curX = isDraggingThis && dragCurrentPos ? dragCurrentPos.x : comp.x;
              const curY = isDraggingThis && dragCurrentPos ? dragCurrentPos.y : comp.y;

              const compW = comp.width || 3.0;
              const compH = comp.height || 2.0;
              const margin = comp.courtyard_margin || 0.35;
              const pkgType = comp.package_type || 'GENERIC';
              const bodyColor = comp.body_color || '#18181b';

              const padPad = 0.35;
              const boundMinX = comp.pads.length ? Math.min(...comp.pads.map((p) => p.x - p.width / 2)) - padPad : curX - compW / 2;
              const boundMaxX = comp.pads.length ? Math.max(...comp.pads.map((p) => p.x + p.width / 2)) + padPad : curX + compW / 2;
              const boundMinY = comp.pads.length ? Math.min(...comp.pads.map((p) => p.y - p.height / 2)) - padPad : curY - compH / 2;
              const boundMaxY = comp.pads.length ? Math.max(...comp.pads.map((p) => p.y + p.height / 2)) + padPad : curY + compH / 2;
              const boxW = Math.max(compW, boundMaxX - boundMinX);
              const boxH = Math.max(compH, boundMaxY - boundMinY);

              return (
                <g
                  key={`comp-${idx}`}
                  onMouseDown={(e) => handleComponentMouseDown(e, comp)}
                  onMouseEnter={() => setHoveredComp(comp)}
                  onMouseLeave={() => setHoveredComp(null)}
                  className={`group cursor-pointer ${isDraggingThis ? 'opacity-80' : ''}`}
                >
                  {/* Selected / Dragging Courtyard Envelope & Collision Highlight */}
                  {(isSelected || isDraggingThis) && (
                    <rect
                      x={curX - (boxW + 2 * margin) / 2}
                      y={curY - (boxH + 2 * margin) / 2}
                      width={boxW + 2 * margin}
                      height={boxH + 2 * margin}
                      rx="0.4"
                      fill={hasCollision ? '#ef4444' : '#10b981'}
                      fillOpacity={hasCollision ? 0.35 : 0.15}
                      stroke={hasCollision ? '#ef4444' : '#10b981'}
                      strokeWidth="0.2"
                      strokeDasharray={hasCollision ? '0.6 0.6' : undefined}
                      className={hasCollision ? 'animate-pulse' : ''}
                    />
                  )}

                  {/* Component Physical Body Shape */}
                  <rect
                    x={curX - boxW / 2}
                    y={curY - boxH / 2}
                    width={boxW}
                    height={boxH}
                    rx="0.25"
                    fill={bodyColor}
                    stroke={isSelected ? '#fbbf24' : '#52525b'}
                    strokeWidth={isSelected ? '0.3' : '0.12'}
                    className="transition-all duration-150 filter drop-shadow-sm"
                  />

                  {/* Pin 1 Corner Indicator Notch & Dot for ICs */}
                  {(pkgType === 'MCU' || pkgType === 'IC' || pkgType === 'REGULATOR') && (
                    <>
                      <circle cx={curX - boxW / 2 + 0.6} cy={curY - boxH / 2 + 0.6} r="0.25" fill="#ffffff" />
                      <rect
                        x={curX - 0.4}
                        y={curY - boxH / 2}
                        width="0.8"
                        height="0.25"
                        fill="#27272a"
                        rx="0.1"
                      />
                    </>
                  )}

                  {/* Tactile Button Metallic Actuator */}
                  {pkgType === 'BUTTON' && (
                    <circle cx={curX} cy={curY} r={Math.min(boxW, boxH) * 0.25} fill="#d4d4d8" stroke="#a1a1aa" strokeWidth="0.1" />
                  )}

                  {/* Connector Outward Mating Arrow */}
                  {pkgType === 'CONNECTOR' && (
                    <polygon
                      points={`${curX - 0.8},${curY - boxH / 2 + 0.5} ${curX + 0.8},${curY - boxH / 2 + 0.5} ${curX},${curY - boxH / 2 - 0.8}`}
                      fill="#38bdf8"
                      fillOpacity="0.8"
                    />
                  )}

                  {/* Silkscreen Reference & Value Labels */}
                  {showSilk && (
                    <g>
                      <text
                        x={curX}
                        y={curY - boxH / 2 - 0.6}
                        fontSize="0.85"
                        fill="#ffffff"
                        textAnchor="middle"
                        fontFamily="monospace"
                        fontWeight="bold"
                      >
                        {comp.ref}
                      </text>
                      <text
                        x={curX}
                        y={curY + boxH / 2 + 1.1}
                        fontSize="0.70"
                        fill="#a1a1aa"
                        textAnchor="middle"
                        fontFamily="monospace"
                      >
                        {comp.value}
                      </text>
                    </g>
                  )}

                  {/* Component Solder Pads */}
                  {showPads &&
                    comp.pads.map((pad, pIdx) => {
                      const isPadHighlighted = selectedNet && pad.net === selectedNet;
                      const padDeltaX = pad.x - comp.x;
                      const padDeltaY = pad.y - comp.y;
                      const padX = curX + padDeltaX;
                      const padY = curY + padDeltaY;

                      return (
                        <g
                          key={`pad-${idx}-${pIdx}`}
                          onMouseEnter={() => setHoveredPad({ comp, pad })}
                          onMouseLeave={() => setHoveredPad(null)}
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectNet(pad.net);
                          }}
                        >
                          {/* Pad Clearance Ring */}
                          {showClearance && (
                            <rect
                              x={padX - (pad.width + 0.3) / 2}
                              y={padY - (pad.height + 0.3) / 2}
                              width={pad.width + 0.3}
                              height={pad.height + 0.3}
                              rx="0.2"
                              fill="#ef4444"
                              fillOpacity="0.2"
                            />
                          )}

                          {/* Thermal Relief Spokes for Ground-Connected Pads */}
                          {showZones && pad.net && (pad.net.toUpperCase().includes('GND') || pad.net === '0V') && (
                            <g className="pointer-events-none opacity-80">
                              <line
                                x1={padX - pad.width / 2 - 0.35}
                                y1={padY}
                                x2={padX + pad.width / 2 + 0.35}
                                y2={padY}
                                stroke="#f59e0b"
                                strokeWidth="0.18"
                                strokeLinecap="round"
                              />
                              <line
                                x1={padX}
                                y1={padY - pad.height / 2 - 0.35}
                                x2={padX}
                                y2={padY + pad.height / 2 + 0.35}
                                stroke="#f59e0b"
                                strokeWidth="0.18"
                                strokeLinecap="round"
                              />
                            </g>
                          )}

                          {/* Solder Pad Metal */}
                          <rect
                            x={padX - pad.width / 2}
                            y={padY - pad.height / 2}
                            width={pad.width}
                            height={pad.height}
                            rx="0.12"
                            fill={isPadHighlighted ? '#38bdf8' : '#eab308'}
                            stroke={isPadHighlighted ? '#0284c7' : '#ca8a04'}
                            strokeWidth="0.08"
                            className="transition-colors duration-150"
                          />

                          {/* Pad Number Label */}
                          <text
                            x={padX}
                            y={padY + 0.25}
                            fontSize="0.5"
                            fill="#090a0f"
                            textAnchor="middle"
                            fontFamily="monospace"
                            fontWeight="bold"
                          >
                            {pad.number}
                          </text>
                        </g>
                      );
                    })}
                </g>
              );
            })}

            {/* Visual Inspection Violation Markers Overlay */}
            {showInspection &&
              visualInspection &&
              visualInspection.violations.map((v, vIdx) => {
                const isErr = v.severity === 'error';
                return (
                  <g key={`viol-${vIdx}`} className="cursor-pointer">
                    <circle
                      cx={v.location[0]}
                      cy={v.location[1]}
                      r="1.4"
                      fill={isErr ? '#ef4444' : '#f59e0b'}
                      fillOpacity="0.3"
                      className="animate-ping"
                    />
                    <circle
                      cx={v.location[0]}
                      cy={v.location[1]}
                      r="0.8"
                      fill={isErr ? '#ef4444' : '#f59e0b'}
                      stroke="#ffffff"
                      strokeWidth="0.15"
                    />
                    <text
                      x={v.location[0]}
                      y={v.location[1] + 0.3}
                      fontSize="0.6"
                      fill="#ffffff"
                      textAnchor="middle"
                      fontWeight="bold"
                    >
                      !
                    </text>
                  </g>
                );
              })}
          </g>
        </svg>
      </div>
    </div>
  );
};
