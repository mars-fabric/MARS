// components/dag/DAGControls.tsx

'use client';

import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  ArrowDownUp,
  ArrowLeftRight,
  RotateCcw,
} from 'lucide-react';
import { useReactFlow } from '@xyflow/react';

interface DAGControlsProps {
  layout: 'horizontal' | 'vertical';
  onLayoutChange: (layout: 'horizontal' | 'vertical') => void;
}

export function DAGControls({ layout, onLayoutChange }: DAGControlsProps) {
  const { zoomIn, zoomOut, fitView, setViewport } = useReactFlow();

  const handleReset = () => {
    setViewport({ x: 0, y: 0, zoom: 1 });
    setTimeout(() => fitView({ padding: 0.2 }), 50);
  };

  return (
    <div className="absolute bottom-4 left-4 z-10 flex items-center space-x-1 bg-gray-800/90 backdrop-blur rounded-lg p-1 border border-gray-700">
      {/* Zoom Controls */}
      <button
        onClick={() => zoomIn({ duration: 300 })}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Zoom In"
      >
        <ZoomIn className="w-4 h-4 text-gray-300" />
      </button>
      <button
        onClick={() => zoomOut({ duration: 300 })}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Zoom Out"
      >
        <ZoomOut className="w-4 h-4 text-gray-300" />
      </button>
      <button
        onClick={() => fitView({ padding: 0.2, duration: 300 })}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Fit View"
      >
        <Maximize2 className="w-4 h-4 text-gray-300" />
      </button>

      <div className="w-px h-6 bg-gray-600 mx-1" />

      {/* Layout Toggle */}
      <button
        onClick={() => onLayoutChange('vertical')}
        className={`p-2 rounded transition-colors ${
          layout === 'vertical' ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-gray-700 text-gray-300'
        }`}
        title="Vertical Layout"
      >
        <ArrowDownUp className="w-4 h-4" />
      </button>
      <button
        onClick={() => onLayoutChange('horizontal')}
        className={`p-2 rounded transition-colors ${
          layout === 'horizontal' ? 'bg-blue-500/20 text-blue-400' : 'hover:bg-gray-700 text-gray-300'
        }`}
        title="Horizontal Layout"
      >
        <ArrowLeftRight className="w-4 h-4" />
      </button>

      <div className="w-px h-6 bg-gray-600 mx-1" />

      {/* Reset */}
      <button
        onClick={handleReset}
        className="p-2 hover:bg-gray-700 rounded transition-colors"
        title="Reset View"
      >
        <RotateCcw className="w-4 h-4 text-gray-300" />
      </button>
    </div>
  );
}
