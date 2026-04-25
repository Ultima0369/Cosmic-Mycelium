import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { type EnergyDataPoint } from '../stores/useSystemStore';

interface EnergyChartProps {
  data: EnergyDataPoint[];
}

export function EnergyChart({ data }: EnergyChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.length === 0) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 200;
    const margin = { top: 20, right: 20, bottom: 30, left: 50 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    svg.attr('width', width).attr('height', height);

    const g = svg
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3
      .scaleTime()
      .domain(d3.extent(data, (d) => new Date(d.timestamp)) as [Date, Date])
      .range([0, innerWidth]);

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.totalEnergy) ?? 100])
      .nice()
      .range([innerHeight, 0]);

    const gradient = svg
      .append('defs')
      .append('linearGradient')
      .attr('id', 'energy-gradient')
      .attr('x1', '0%')
      .attr('y1', '0%')
      .attr('x2', '0%')
      .attr('y2', '100%');

    gradient
      .append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#c084fc')
      .attr('stop-opacity', 0.4);

    gradient
      .append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#c084fc')
      .attr('stop-opacity', 0);

    const area = d3
      .area<EnergyDataPoint>()
      .x((d) => xScale(new Date(d.timestamp)))
      .y0(innerHeight)
      .y1((d) => yScale(d.totalEnergy))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'url(#energy-gradient)')
      .attr('d', area);

    const line = d3
      .line<EnergyDataPoint>()
      .x((d) => xScale(new Date(d.timestamp)))
      .y((d) => yScale(d.totalEnergy))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#c084fc')
      .attr('stroke-width', 2)
      .attr('d', line);

    g.append('g')
      .attr('transform', `translate(0,${innerHeight})`)
      .call(d3.axisBottom(xScale).ticks(5).tickFormat((d) => {
        const date = d as Date;
        return `${date.getMinutes()}:${date.getSeconds().toString().padStart(2, '0')}`;
      }))
      .attr('color', '#9ca3af')
      .selectAll('text')
      .attr('fill', '#9ca3af')
      .style('font-size', '10px');

    g.append('g')
      .call(d3.axisLeft(yScale).ticks(5))
      .attr('color', '#9ca3af')
      .selectAll('text')
      .attr('fill', '#9ca3af')
      .style('font-size', '10px');

    g.append('text')
      .attr('x', innerWidth / 2)
      .attr('y', -5)
      .attr('text-anchor', 'middle')
      .attr('fill', '#f3f4f6')
      .style('font-size', '12px')
      .text('Total Energy Flow');
  }, [data]);

  return (
    <div ref={containerRef} className="w-full rounded-xl bg-bg-secondary border border-border p-4">
      <svg ref={svgRef} className="w-full" />
      {data.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-text-secondary">
          Waiting for data...
        </div>
      )}
    </div>
  );
}