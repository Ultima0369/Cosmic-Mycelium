import { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import * as d3 from 'd3';
import { Scale, type FractalMessage } from '../stores/useFractalStore';

interface TranslationFlowProps {
  messages: FractalMessage[];
  activeMessageId: string | null;
}

const SCALES = [
  { id: Scale.NANO, label: 'NANO', y: 40, color: '#6366f1' },
  { id: Scale.INFANT, label: 'INFANT', y: 140, color: '#c084fc' },
  { id: Scale.MESH, label: 'MESH', y: 240, color: '#4ade80' },
  { id: Scale.SWARM, label: 'SWARM', y: 340, color: '#fbbf24' },
];

export function TranslationFlow({ messages, activeMessageId }: TranslationFlowProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const activeMessage = messages.find(m => m.id === activeMessageId);

  useEffect(() => {
    if (!svgRef.current || !activeMessage) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('.particle').remove();

    const fromScale = SCALES.find(s => s.id === activeMessage.from_scale);
    const toScale = SCALES.find(s => s.id === activeMessage.to_scale);

    if (!fromScale || !toScale) return;

    const particle = svg.append('circle')
      .attr('class', 'particle')
      .attr('r', 8)
      .attr('fill', activeMessage.fidelity > 0.7 ? '#4ade80' : activeMessage.fidelity > 0.4 ? '#fbbf24' : '#f87171')
      .attr('cx', 150)
      .attr('cy', fromScale.y)
      .attr('opacity', 0.9);

    particle.transition()
      .duration(800)
      .ease(d3.easeCubicInOut)
      .attr('cy', toScale.y)
      .on('end', function() {
        d3.select(this)
          .transition()
          .duration(300)
          .attr('r', 20)
          .attr('opacity', 0)
          .remove();
      });

  }, [activeMessage]);

  const getTransitionType = (from: Scale, to: Scale): string => {
    if (from === Scale.INFANT && to === Scale.MESH) return '压缩';
    if (from === Scale.MESH && to === Scale.SWARM) return '抽象';
    if (from === Scale.MESH && to === Scale.INFANT) return '展开';
    if (from === Scale.SWARM && to === Scale.MESH) return '实例化';
    return '转发';
  };

  return (
    <div className="flex-1 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] p-4 overflow-hidden">
      <h3 className="font-medium mb-4 text-[var(--text-primary)]">翻译流程</h3>
      
      <div className="relative h-[400px]">
        <svg
          ref={svgRef}
          width="100%"
          height="400"
          className="absolute inset-0"
        >
          {SCALES.map((scale) => (
            <g key={scale.id}>
              <line
                x1="50"
                y1={scale.y}
                x2="250"
                y2={scale.y}
                stroke={scale.color}
                strokeWidth="2"
                strokeOpacity="0.3"
              />
              <circle
                cx="150"
                cy={scale.y}
                r="24"
                fill="none"
                stroke={scale.color}
                strokeWidth="2"
                strokeOpacity="0.5"
              />
              <text
                x="150"
                y={scale.y + 4}
                textAnchor="middle"
                fill={scale.color}
                fontSize="12"
                fontWeight="600"
              >
                {scale.label}
              </text>
            </g>
          ))}

          <g>
            <line x1="150" y1="164" x2="150" y2="216" stroke="#c084fc" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="150" y1="264" x2="150" y2="316" stroke="#4ade80" strokeWidth="1" strokeDasharray="4 4" />
          </g>

          <AnimatePresence>
            {activeMessage && (
              <motion.text
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                x="150"
                y="380"
                textAnchor="middle"
                fill="var(--text-secondary)"
                fontSize="11"
              >
                {getTransitionType(activeMessage.from_scale, activeMessage.to_scale)} · 保真度 {activeMessage.fidelity.toFixed(2)}
              </motion.text>
            )}
          </AnimatePresence>
        </svg>
      </div>

      <div className="mt-4 grid grid-cols-4 gap-2">
        {SCALES.map((scale) => (
          <div
            key={scale.id}
            className="flex items-center gap-2 px-2 py-1 rounded bg-[var(--bg-tertiary)] text-xs"
          >
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: scale.color }}
            />
            <span style={{ color: scale.color }}>{scale.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}