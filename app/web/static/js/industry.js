/* ============================================================
   AlphaFoundry — Industry Chain Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

async function loadIndustryChain() {
    const industry = document.getElementById('industry-select').value;
    try {
        const data = await apiCall('GET', `/api/graph/industry-chain/${encodeURIComponent(industry)}`);
        renderIndustryGraph(data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadPropagationPath() {
    const eventId = document.getElementById('event-id').value.trim();
    if (!eventId) return toast('请输入事件 ID', 'error');
    try {
        const data = await apiCall('GET', `/api/graph/propagation/${encodeURIComponent(eventId)}`);
        renderPropagationGraph(data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderIndustryGraph(data) {
    const container = document.getElementById('industry-graph');
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = container.clientHeight;

    const nodes = data.nodes || [];
    const links = data.edges || [];

    if (!nodes.length) {
        container.innerHTML = '<div class="empty-state">暂无产业链数据</div>';
        return;
    }

    const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);

    const color = d3.scaleOrdinal()
        .domain(['upstream', 'midstream', 'downstream'])
        .range(['#e53e3e', '#3182ce', '#38a169']);

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg.append('g').selectAll('line').data(links).enter().append('line')
        .attr('stroke', '#94a3b8').attr('stroke-width', 2);

    const linkLabel = svg.append('g').selectAll('text').data(links).enter().append('text')
        .attr('font-size', '10px').attr('fill', '#64748b').text(d => d.label);

    const node = svg.append('g').selectAll('circle').data(nodes).enter().append('circle')
        .attr('r', 12).attr('fill', d => color(d.group)).call(drag(simulation));

    const nodeLabel = svg.append('g').selectAll('text').data(nodes).enter().append('text')
        .attr('font-size', '12px').attr('fill', '#1a202c').text(d => d.label);

    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        linkLabel.attr('x', d => (d.source.x + d.target.x) / 2).attr('y', d => (d.source.y + d.target.y) / 2);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        nodeLabel.attr('x', d => d.x + 16).attr('y', d => d.y + 4);
    });

    function drag(simulation) {
        function dragstarted(event) {
            event.sourceEvent.preventDefault();
            event.sourceEvent.stopPropagation();
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        function dragged(event) {
            event.sourceEvent.preventDefault();
            event.sourceEvent.stopPropagation();
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
    }
}

function renderPropagationGraph(data) {
    const container = document.getElementById('propagation-graph');
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = container.clientHeight;
    const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width / 2).attr('y', height / 2).attr('text-anchor', 'middle').attr('fill', '#64748b').text('传播路径可视化');
}

export { loadIndustryChain, loadPropagationPath, renderIndustryGraph, renderPropagationGraph };
