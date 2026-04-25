import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Scale, type HeatmapCell, type EchoPattern as EchoPatternType } from '../stores/useFractalStore';

interface EchoHeatmapProps {
  heatmapData: HeatmapCell[];
  patterns: EchoPatternType[];
}

const SCALE_ORDER = [Scale.NANO, Scale.INFANT, Scale.MESH, Scale.SWARM];
const SCALE_LABELS: Record<Scale, string> = {
  [Scale.NANO]: 'Nano',
  [Scale.INFANT]: 'Infant',
  [Scale.MESH]: 'Mesh',
  [Scale.SWARM]: 'Swarm',
};

function getIntensityColor(intensity: number): string {
  if (intensity === 0) return 'bg-[var(--bg-tertiary)]';
  if (intensity < 0.3) return 'bg-emerald-900/60';
  if (intensity < 0.6) return 'bg-emerald-700/70';
  if (intensity < 0.9) return 'bg-emerald-500/80';
  return 'bg-emerald-400';
}

function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'high': return 'text-danger';
    case 'medium': return 'text-warning';
    default: return 'text-success';
  }
}

export function EchoHeatmap({ heatmapData, patterns }: EchoHeatmapProps) {
  const matrix = useMemo(() => {
    const m: Record<string, number> = {};
    for (const cell of heatmapData) {
      m[`${cell.fromScale}-${cell.toScale}`] = cell.intensity;
    }
    return m;
  }, [heatmapData]);

  const maxIntensity = useMemo(() => {
    return Math.max(...heatmapData.map(c => c.intensity), 1);
  }, [heatmapData]);

  const patternsBySeverity = useMemo(() => {
    return {
      high: patterns.filter(p => p.severity === 'high'),
      medium: patterns.filter(p => p.severity === 'medium'),
      low: patterns.filter(p => p.severity === 'low'),
    };
  }, [patterns]);

  const detectedInvariants = useMemo(() => {
    const invariantCount = patterns.length;
    const highSeverityCount = patterns.filter(p => p.severity === 'high').length;
    
    if (highSeverityCount > 2) {
      return { type: 'danger', text: `检测到 ${highSeverityCount} 个高危模式` };
    }
    if (invariantCount > 10) {
      return { type: 'warning', text: `发现 ${invariantCount} 个普遍不变量` };
    }
    if (invariantCount > 0) {
      return { type: 'success', text: `${invariantCount} 个模式已记录` };
    }
    return { type: 'neutral', text: '未检测到模式' };
  }, [patterns]);

  return (
    <div className="w-80 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] p-4">
      <h3 className="font-medium mb-4 text-[var(--text-primary)]">回声探测器</h3>

      <div className="mb-4">
        <h4 className="text-xs text-[var(--text-secondary)] mb-2">跨层级热力图</h4>
        <div className="grid grid-cols-5 gap-1">
          <div />
          {SCALE_ORDER.map(scale => (
            <div key={scale} className="text-xs text-center text-[var(--text-secondary)]">
              {SCALE_LABELS[scale]}
            </div>
          ))}
          
          {SCALE_ORDER.map(from => (
            <motion.div key={from} className="contents">
              <div className="text-xs text-[var(--text-secondary)] flex items-center">
                {SCALE_LABELS[from]}
              </div>
              {SCALE_ORDER.map(to => {
                const key = `${from}-${to}`;
                const intensity = (matrix[key] || 0) / maxIntensity;
                return (
                  <motion.div
                    key={key}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className={`w-8 h-8 rounded flex items-center justify-center text-xs ${getIntensityColor(intensity)}`}
                    whileHover={{ scale: 1.1 }}
                  >
                    {intensity > 0 ? intensity.toFixed(1) : ''}
                  </motion.div>
                );
              })}
            </motion.div>
          ))}
        </div>
      </div>

      <div className="mb-4">
        <h4 className="text-xs text-[var(--text-secondary)] mb-2">已记录模式 ({patterns.length})</h4>
        <div className="max-h-32 overflow-y-auto space-y-1">
          {patterns.slice(0, 8).map(pattern => (
            <div
              key={pattern.id}
              className="flex items-center justify-between px-2 py-1 rounded bg-[var(--bg-tertiary)] text-xs"
            >
              <span className="truncate max-w-[120px]">{pattern.signature}</span>
              <span className={getSeverityColor(pattern.severity)}>
                {pattern.severity === 'high' ? '●●' : pattern.severity === 'medium' ? '●○' : '○○'}
              </span>
            </div>
          ))}
          {patterns.length === 0 && (
            <div className="text-xs text-[var(--text-secondary)] py-2 text-center">
              暂无记录
            </div>
          )}
        </div>
      </div>

      <div>
        <h4 className="text-xs text-[var(--text-secondary)] mb-2">普遍不变量检测</h4>
        <div className={`px-3 py-2 rounded text-sm ${
          detectedInvariants.type === 'danger' ? 'bg-danger/20 text-danger' :
          detectedInvariants.type === 'warning' ? 'bg-warning/20 text-warning' :
          detectedInvariants.type === 'success' ? 'bg-success/20 text-success' :
          'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
        }`}>
          {detectedInvariants.text}
        </div>
        
        <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
          <div className="text-center">
            <div className="text-danger font-semibold">{patternsBySeverity.high.length}</div>
            <div className="text-[var(--text-secondary)]">高危</div>
          </div>
          <div className="text-center">
            <div className="text-warning font-semibold">{patternsBySeverity.medium.length}</div>
            <div className="text-[var(--text-secondary)]">中危</div>
          </div>
          <div className="text-center">
            <div className="text-success font-semibold">{patternsBySeverity.low.length}</div>
            <div className="text-[var(--text-secondary)]">低危</div>
          </div>
        </div>
      </div>
    </div>
  );
}