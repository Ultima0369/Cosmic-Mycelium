import { Scale, type ScaleCount } from '../stores/useSystemStore';

interface ScaleCardProps {
  data: ScaleCount;
}

const scaleColors: Record<Scale, string> = {
  [Scale.NANO]: 'from-cyan-500 to-blue-500',
  [Scale.INFANT]: 'from-green-400 to-emerald-600',
  [Scale.MESH]: 'from-purple-500 to-violet-600',
  [Scale.SWARM]: 'from-orange-400 to-amber-600',
};

const scaleIcons: Record<Scale, string> = {
  [Scale.NANO]: '⚛',
  [Scale.INFANT]: '🐝',
  [Scale.MESH]: '🕸',
  [Scale.SWARM]: '🌌',
};

const scaleDescriptions: Record<Scale, string> = {
  [Scale.NANO]: 'Neurons / Synapses',
  [Scale.INFANT]: 'Individual Bees',
  [Scale.MESH]: 'Local Swarm',
  [Scale.SWARM]: 'Global Civilization',
};

export function ScaleCard({ data }: ScaleCardProps) {
  const { scale, count, energy } = data;
  const gradient = scaleColors[scale];
  const icon = scaleIcons[scale];
  const description = scaleDescriptions[scale];

  return (
    <div className="relative overflow-hidden rounded-xl bg-bg-secondary border border-border p-4 hover:border-accent/50 transition-colors">
      <div
        className={`absolute inset-0 opacity-10 bg-gradient-to-br ${gradient}`}
      />
      <div className="relative">
        <div className="flex items-center justify-between mb-2">
          <span className="text-2xl">{icon}</span>
          <span className="text-xs text-text-secondary">{description}</span>
        </div>
        <div className="text-3xl font-bold text-text-primary mb-1">
          {count.toLocaleString()}
        </div>
        <div className="text-sm text-text-secondary">
          Energy: <span className="text-accent font-mono">{energy.toFixed(1)}</span>
        </div>
        <div className="mt-3 h-1 bg-bg-tertiary rounded-full overflow-hidden">
          <div
            className={`h-full bg-gradient-to-r ${gradient} transition-all duration-500`}
            style={{ width: `${Math.min(100, (energy / 1000) * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}