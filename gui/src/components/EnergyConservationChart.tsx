import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

interface EnergyData {
  timestamp: number;
  T: number;
  V: number;
  E: number;
}

interface EnergyConservationChartProps {
  data?: EnergyData[];
}

const MAX_POINTS = 100;

export function EnergyConservationChart({ data = [] }: EnergyConservationChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [localData, setLocalData] = useState<EnergyData[]>([]);

  useEffect(() => {
    if (data.length > 0) {
      setLocalData((prev) => [...prev.slice(-MAX_POINTS + 1), ...data]);
    }
  }, [data]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 200;
    const margin = { top: 20, right: 80, bottom: 30, left: 50 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    svg.attr('width', width).attr('height', height);

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const displayData = localData.length > 0 ? localData : [
      { timestamp: 0, T: 0, V: 0, E: 0 },
    ];

    const xScale = d3
      .scaleLinear()
      .domain([0, Math.max(displayData.length - 1, 1)])
      .range([0, innerWidth]);

    const allEnergies = displayData.flatMap((d) => [d.T, d.V, d.E]);
    const maxE = Math.max(...allEnergies, 1);
    const yScale = d3
      .scaleLinear()
      .domain([0, maxE * 1.1])
      .range([innerHeight, 0]);

    const lineT = d3
      .line<EnergyData>()
      .x((_, i) => xScale(i))
      .y((d) => yScale(d.T))
      .curve(d3.curveMonotoneX);

    const lineV = d3
      .line<EnergyData>()
      .x((_, i) => xScale(i))
      .y((d) => yScale(d.V))
      .curve(d3.curveMonotoneX);

    const lineE = d3
      .line<EnergyData>()
      .x((_, i) => xScale(i))
      .y((d) => yScale(d.E))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(displayData)
      .attr('fill', 'none')
      .attr('stroke', '#4ade80')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4,2')
      .attr('d', lineT);

    g.append('path')
      .datum(displayData)
      .attr('fill', 'none')
      .attr('stroke', '#fbbf24')
      .attr('stroke-width', 2)
      .attr('stroke-dasharray', '4,2')
      .attr('d', lineV);

    g.append('path')
      .datum(displayData)
      .attr('fill', 'none')
      .attr('stroke', '#c084fc')
      .attr('stroke-width', 3)
      .attr('d', lineE);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat(() => ''))
      .attr('color', '#475569')
      .selectAll('text')
      .attr('fill', '#9ca3af')
      .style('font-size', '10px');

    g.append('g')
      .call(
        d3
          .axisLeft(yScale)
          .ticks(5)
          .tickFormat((d) => `${Number(d).toFixed(1)}`)
      )
      .attr('color', '#475569')
      .selectAll('text')
      .attr('fill', '#9ca3af')
      .style('font-size', '10px');

    const legend = svg
      .append('g')
      .attr('transform', `translate(${width - margin.right + 10}, ${margin.top})`);

    [
      { label: 'T', color: '#4ade80' },
      { label: 'V', color: '#fbbf24' },
      { label: 'E', color: '#c084fc' },
    ].forEach((item, i) => {
      const legendItem = legend
        .append('g')
        .attr('transform', `translate(0, ${i * 20})`);

      legendItem
        .append('line')
        .attr('x1', 0)
        .attr('x2', 20)
        .attr('y1', 0)
        .attr('y2', 0)
        .attr('stroke', item.color)
        .attr('stroke-width', 2);

      legendItem
        .append('text')
        .attr('x', 25)
        .attr('y', 4)
        .attr('fill', item.color)
        .style('font-size', '11px')
        .text(item.label);
    });

    if (localData.length > 0) {
      const last = localData[localData.length - 1];
      const drift = last.E > 0 ? ((last.E - last.T - last.V) / last.E) * 100 : 0;
      
      g.append('text')
        .attr('x', innerWidth / 2)
        .attr('y', -8)
        .attr('text-anchor', 'middle')
        .attr('fill', Math.abs(drift) < 0.1 ? '#4ade80' : '#f87171')
        .style('font-size', '12px')
        .style('font-weight', 'bold')
        .text(`Total Energy: ${last.E.toFixed(4)} (drift: ${drift.toFixed(2)}%)`);
    }
  }, [localData]);

  return (
    <div ref={containerRef} className="w-full rounded-xl bg-[#0f172a] border border-[#334155] p-4">
      <div className="text-sm text-gray-400 mb-2">
        Energy Conservation: E = T + V
      </div>
      <svg ref={svgRef} className="w-full" style={{ height: '200px' }} />
      {localData.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-500 text-sm">
          Waiting for simulation...
        </div>
      )}
    </div>
  );
}