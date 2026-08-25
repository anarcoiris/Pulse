import React, { useState, useRef, useEffect } from 'react';
import { CircuitDesignSchema } from '../types';
import { ZoomIn, ZoomOut, Maximize2, Cpu, Zap, Hash } from 'lucide-react';

interface SchematicViewerProps {
  circuitData: CircuitDesignSchema | null;
  selectedNet: string | null;
  onSelectNet: (net: string | null) => void;
}

export const SchematicViewer: React.FC<SchematicViewerProps> = ({
  circuitData,
  selectedNet,
  onSelectNet,
}) => {
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 100, y: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setPan({ x: 60, y: 60 });
    }
  }, [circuitData]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0 || e.button === 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 0.85;
    setZoom((prev) => Math.max(0.4, Math.min(4.0, prev * factor)));
  };

  if (!circuitData || !circuitData.circuit || circuitData.circuit.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-zinc-950 text-zinc-400 p-8 border border-zinc-800 rounded-xl">
        <Cpu className="w-12 h-12 text-zinc-600 mb-3" />
        <h3 className="text-base font-semibold text-zinc-200">No Schematic Generated</h3>
        <p className="text-xs text-zinc-500 max-w-sm text-center mt-1">
          Generate a circuit to view electrical connectivity, component pins, and nets.
        </p>
      </div>
    );
  }

  // Group components into grid layout
  const comps = circuitData.circuit;
  const cols = Math.min(4, Math.max(2, Math.ceil(Math.sqrt(comps.length))));

  return (
    <div className="relative w-full h-full bg-[#08090d] rounded-xl overflow-hidden border border-zinc-800 shadow-2xl flex flex-col select-none">
      {/* Control Bar Header */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-zinc-900/90 backdrop-blur-md px-3 py-2 rounded-lg border border-zinc-800 text-xs text-zinc-300 shadow-lg">
        <button
          onClick={() => setZoom((z) => Math.min(4, z * 1.2))}
          className="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-400 hover:text-white"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.4, z * 0.8))}
          className="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-400 hover:text-white"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          onClick={() => {
            setZoom(1.0);
            setPan({ x: 60, y: 60 });
          }}
          className="p-1.5 hover:bg-zinc-800 rounded transition-colors text-zinc-400 hover:text-white"
          title="Reset View"
        >
          <Maximize2 className="w-4 h-4" />
        </button>

        <div className="h-4 w-px bg-zinc-700 mx-1" />
        <div className="text-[11px] font-mono text-zinc-400">
          <span>{comps.length} Symbols</span>
        </div>
      </div>

      {/* Schematic SVG Canvas */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        className="w-full h-full cursor-grab active:cursor-grabbing flex-1"
      >
        <svg className="w-full h-full">
          {/* Subtle Grid */}
          <defs>
            <pattern id="sch-grid" width={20 * zoom} height={20 * zoom} patternUnits="userSpaceOnUse">
              <circle cx={10 * zoom} cy={10 * zoom} r="1" fill="#27272a" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#sch-grid)" />

          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
            {comps.map((comp, idx) => {
              const col = idx % cols;
              const row = Math.floor(idx / cols);
              const x = col * 260 + 40;
              const y = row * 220 + 40;

              const pinsEntries = comp.pins
                ? Object.entries(comp.pins)
                : comp.n1 || comp.n2
                ? [
                    ['1', comp.n1 || 'NC'],
                    ['2', comp.n2 || 'NC'],
                  ]
                : [
                    ['1', 'VCC'],
                    ['2', 'GND'],
                  ];

              const boxHeight = Math.max(80, pinsEntries.length * 22 + 40);

              return (
                <g key={`sch-comp-${idx}`} className="group">
                  {/* Symbol Block Rect */}
                  <rect
                    x={x}
                    y={y}
                    width={180}
                    height={boxHeight}
                    rx="4"
                    fill="#18181b"
                    stroke="#3f3f46"
                    strokeWidth="1.5"
                    className="group-hover:stroke-indigo-500 transition-colors drop-shadow-md"
                  />

                  {/* Header Title */}
                  <rect x={x} y={y} width={180} height={26} fill="#27272a" rx="4" />
                  <text
                    x={x + 10}
                    y={y + 17}
                    fill="#f4f4f5"
                    fontSize="12"
                    fontWeight="bold"
                    fontFamily="monospace"
                  >
                    {comp.label}
                  </text>
                  <text
                    x={x + 170}
                    y={y + 17}
                    fill="#a1a1aa"
                    fontSize="10"
                    fontFamily="monospace"
                    textAnchor="end"
                  >
                    {comp.value}
                  </text>

                  {/* Pins & Net Stubs */}
                  {pinsEntries.map(([pinNum, netName], pIdx) => {
                    const pinY = y + 42 + pIdx * 22;
                    const isHighlighted = selectedNet && netName === selectedNet;

                    return (
                      <g
                        key={`pin-${pIdx}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectNet(netName);
                        }}
                        className="cursor-pointer group/pin"
                      >
                        {/* Pin Terminal Line */}
                        <line
                          x1={x - 15}
                          y1={pinY}
                          x2={x}
                          y2={pinY}
                          stroke={isHighlighted ? '#38bdf8' : '#e4e4e7'}
                          strokeWidth={isHighlighted ? '2.5' : '1.5'}
                        />
                        <circle
                          cx={x - 15}
                          cy={pinY}
                          r="2.5"
                          fill={isHighlighted ? '#38bdf8' : '#f59e0b'}
                        />

                        {/* Pin Number */}
                        <text
                          x={x + 8}
                          y={pinY + 4}
                          fill="#71717a"
                          fontSize="9"
                          fontFamily="monospace"
                        >
                          {pinNum}
                        </text>

                        {/* Net Name Tag */}
                        <g transform={`translate(${x - 18}, ${pinY})`}>
                          <rect
                            x={- (netName.length * 6.5 + 8)}
                            y="-9"
                            width={netName.length * 6.5 + 8}
                            height="18"
                            rx="3"
                            fill={isHighlighted ? '#0284c7' : '#27272a'}
                            stroke={isHighlighted ? '#38bdf8' : '#52525b'}
                            strokeWidth="1"
                          />
                          <text
                            x={- (netName.length * 6.5 + 4) / 2}
                            y="3.5"
                            fill={isHighlighted ? '#ffffff' : '#e0e7ff'}
                            fontSize="9.5"
                            fontWeight={isHighlighted ? 'bold' : 'normal'}
                            fontFamily="monospace"
                            textAnchor="middle"
                          >
                            {netName}
                          </text>
                        </g>
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
};
