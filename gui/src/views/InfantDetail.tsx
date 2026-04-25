import { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import * as d3 from 'd3';
import { useAppStore, type Infant } from '../stores/useAppStore';

function ChartContainer({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-bg-secondary border border-border p-4">
      <h3 className="text-sm font-medium text-text-secondary mb-3">{title}</h3>
      {children}
    </div>
  );
}

function EnergyHistoryChart({ data }: { data: Infant['energyHistory'] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 120;
    const margin = { top: 10, right: 10, bottom: 25, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3
      .scaleLinear()
      .domain([0, data.length - 1])
      .range([0, innerWidth]);

    const yScale = d3
      .scaleLinear()
      .domain([0, 100])
      .range([innerHeight, 0]);

    const gradient = svg
      .append('defs')
      .append('linearGradient')
      .attr('id', 'energy-detail-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '0%')
      .attr('y2', '100%');

    gradient
      .append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#4ade80')
      .attr('stop-opacity', 0.4);
    gradient
      .append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#4ade80')
      .attr('stop-opacity', 0);

    const area = d3
      .area<{ timestamp: number; energy: number }>()
      .x((_, i) => xScale(i))
      .y0(innerHeight)
      .y1((d) => yScale(d.energy))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'url(#energy-detail-gradient)')
      .attr('d', area);

    const line = d3
      .line<{ timestamp: number; energy: number }>()
      .x((_, i) => xScale(i))
      .y((d) => yScale(d.energy))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#4ade80')
      .attr('stroke-width', 2)
      .attr('d', line);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat(() => ''))
      .attr('color', '#6b7280')
      .selectAll('text')
      .attr('fill', '#6b7280');

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(4))
      .attr('color', '#6b7280')
      .selectAll('text')
      .attr('fill', '#6b7280')
      .style('font-size', '10px');
  }, [data]);

  return (
    <div ref={containerRef} className="w-full h-32">
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}

function ConfidenceChart({ data }: { data: Infant['confidenceHistory'] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 120;
    const margin = { top: 10, right: 10, bottom: 25, left: 40 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    svg.attr('width', width).attr('height', height);

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3
      .scaleLinear()
      .domain([0, data.length - 1])
      .range([0, innerWidth]);

    const confidenceMax = d3.max(data, (d) => d.confidence) ?? 100;
    const yScale = d3
      .scaleLinear()
      .domain([0, Math.max(confidenceMax, 100)])
      .range([innerHeight, 0]);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#c084fc')
      .attr('stroke-width', 2)
      .attr('d', (d) =>
        d3
          .line<{ timestamp: number; confidence: number; surprise: number }>()
          .x((_, i) => xScale(i))
          .y((d) => yScale(d.confidence))
          .curve(d3.curveMonotoneX)(d)
      );

    const barWidth = innerWidth / data.length;
    data.forEach((d, i) => {
      if (d.surprise > 5) {
        g.append('rect')
          .attr('x', xScale(i) - barWidth / 2)
          .attr('y', 0)
          .attr('width', barWidth)
          .attr('height', innerHeight)
          .attr('fill', '#f59e0b')
          .attr('opacity', Math.min(d.surprise / 30, 0.3));
      }
    });

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat(() => ''))
      .attr('color', '#6b7280');

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(4))
      .attr('color', '#6b7280')
      .selectAll('text')
      .attr('fill', '#6b7280')
      .style('font-size', '10px');
  }, [data]);

  return (
    <div ref={containerRef} className="w-full h-32">
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}

function MyelinationChart({ data }: { data: Infant['myelinationPaths'] }) {
  return (
    <div className="space-y-2">
      {data.map((item) => (
        <div key={item.pathId} className="flex items-center gap-3">
          <span className="w-20 text-xs text-text-secondary font-mono">
            {item.pathId}
          </span>
          <div className="flex-1 h-4 rounded-full bg-bg-tertiary overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${item.strength * 100}%` }}
              transition={{ duration: 0.5 }}
              className="h-full rounded-full bg-gradient-to-r from-accent to-accent/50"
            />
          </div>
          <span className="w-12 text-xs text-text-secondary text-right">
            {(item.strength * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function TraumaTimeline({ events }: { events: Infant['traumaEvents'] }) {
  const sorted = [...events].sort((a, b) => b.timestamp - a.timestamp);

  return (
    <div className="space-y-2 max-h-48 overflow-y-auto">
      {sorted.length === 0 ? (
        <div className="text-sm text-text-secondary">No trauma events recorded</div>
      ) : (
        sorted.map((event, i) => (
          <div
            key={i}
            className="flex items-center gap-3 p-2 rounded-lg bg-bg-tertiary/50"
          >
            <div className="w-2 h-2 rounded-full bg-danger" />
            <div className="flex-1">
              <div className="text-sm text-text-primary">{event.type}</div>
              <div className="text-xs text-text-secondary">
                {new Date(event.timestamp).toLocaleString()}
              </div>
            </div>
            <div className="text-xs text-danger">
              {(event.intensity * 100).toFixed(0)}%
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function BreathIndicator({ phase }: { phase: Infant['breathPhase'] }) {
  const phases: { key: Infant['breathPhase']; label: string; color: string }[] = [
    { key: 'CONTRACT', label: 'CONTRACT', color: 'text-danger' },
    { key: 'DIFFUSE', label: 'DIFFUSE', color: 'text-success' },
    { key: 'SUSPEND', label: 'SUSPEND', color: 'text-warning' },
  ];

  return (
    <div className="flex items-center gap-4">
      {phases.map((p) => (
        <motion.div
          key={p.key}
          animate={
            phase === p.key
              ? { scale: 1.1, opacity: 1 }
              : { scale: 1, opacity: 0.4 }
          }
          className={`px-4 py-2 rounded-lg bg-bg-tertiary border ${p.color} border-current`}
        >
          {p.label}
        </motion.div>
      ))}
    </div>
  );
}

export function InfantDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { infants } = useAppStore();

  const infant = infants.find((i) => i.id === id);

  useEffect(() => {
    if (!infant) {
      navigate('/infants');
    }
  }, [infant, navigate]);

  if (!infant) {
    return null;
  }

  const getStatusBadge = (status: Infant['status']) => {
    const styles = {
      active: 'bg-success/20 text-success',
      suspended: 'bg-warning/20 text-warning',
      dead: 'bg-danger/20 text-danger',
    };
    return styles[status];
  };

  return (
    <div className="min-h-screen bg-bg-primary p-6">
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/infants')}
              className="p-2 rounded-lg hover:bg-bg-secondary transition-colors"
            >
              <svg
                className="w-5 h-5 text-text-secondary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
            <div>
              <h1 className="text-2xl font-bold text-text-primary">
                {infant.name}
              </h1>
              <p className="text-sm text-text-secondary font-mono">{infant.id}</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span
              className={`px-3 py-1 rounded-lg text-sm font-medium ${getStatusBadge(infant.status)}`}
            >
              {infant.status}
            </span>
            <span className="text-sm text-text-secondary">
              Age: {infant.age} cycles
            </span>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartContainer title="Physical State">
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 rounded-lg bg-bg-tertiary">
              <div className="text-xs text-text-secondary mb-1">Position q</div>
              <div className="font-mono text-sm text-text-primary">
                [{infant.position.q.map((v) => v.toFixed(2)).join(', ')}]
              </div>
            </div>
            <div className="p-3 rounded-lg bg-bg-tertiary">
              <div className="text-xs text-text-secondary mb-1">Momentum p</div>
              <div className="font-mono text-sm text-text-primary">
                [{infant.position.p.map((v) => v.toFixed(2)).join(', ')}]
              </div>
            </div>
          </div>
          <div className="mt-4">
            <EnergyHistoryChart data={infant.energyHistory} />
          </div>
        </ChartContainer>

        <ChartContainer title="Confidence & Surprise">
          <ConfidenceChart data={infant.confidenceHistory} />
          <div className="mt-2 flex items-center justify-between text-xs">
            <span className="text-text-secondary">Confidence</span>
            <span className="text-accent">{infant.confidence.toFixed(1)}%</span>
          </div>
        </ChartContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <ChartContainer title="Myelination Paths">
          <MyelinationChart data={infant.myelinationPaths} />
        </ChartContainer>

        <ChartContainer title="Breath Rhythm">
          <div className="flex flex-col items-center gap-4">
            <BreathIndicator phase={infant.breathPhase} />
            <div className="text-sm text-text-secondary">
              Current phase: {infant.breathPhase}
            </div>
          </div>
        </ChartContainer>
      </div>

      <ChartContainer title="Trauma Events">
        <TraumaTimeline events={infant.traumaEvents} />
      </ChartContainer>
    </div>
  );
}

export default InfantDetail;