import React, { useEffect, useRef } from 'react';

interface OscilloscopeProps {
  data: number[];
  trigger: number;
}

export const Oscilloscope: React.FC<OscilloscopeProps> = ({ data, trigger }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear background
    ctx.fillStyle = '#0a0b0d';
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = '#1f2023';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += width / 10) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += height / 8) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Draw center line
    ctx.strokeStyle = '#2a2b2e';
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    // Draw data
    if (data.length > 0) {
      ctx.strokeStyle = '#00ff00';
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      const step = width / (data.length - 1);
      data.forEach((val, i) => {
        const x = i * step;
        // Scale voltage to height (assuming 5kV max, centered)
        const y = height / 2 - (val / 5000) * (height / 2.5);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Glow effect
      ctx.shadowBlur = 10;
      ctx.shadowColor = '#00ff00';
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Trigger indicator
    ctx.fillStyle = '#ffff00';
    ctx.font = '10px monospace';
    ctx.fillText('TRIG T: 0ns', 10, 20);
    ctx.fillText('V/DIV: 1kV', 10, 35);

  }, [data, trigger]);

  return (
    <div className="relative w-full h-48 rounded-lg overflow-hidden border border-zinc-800">
      <canvas 
        ref={canvasRef} 
        width={600} 
        height={200} 
        className="w-full h-full"
      />
      <div className="absolute top-2 right-2 flex gap-2">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-[10px] text-green-500 font-mono uppercase">Live</span>
      </div>
    </div>
  );
};
