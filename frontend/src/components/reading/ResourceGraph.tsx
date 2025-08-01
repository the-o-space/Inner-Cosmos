import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { ResourceGraph, ResourceNode } from '../../data/resourcesData';
import { createSimulation } from '../../utils/simulation';
import { renderGraph } from '../../utils/renderer';
import './ResourceGraph.css';

interface ResourceGraphProps {
  data: ResourceGraph;
  width?: number;
  height?: number;
}

const DEFAULT_WIDTH = 800;
const DEFAULT_HEIGHT = 600;

const ResourceGraphComponent: React.FC<ResourceGraphProps> = ({
  data,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedNode, setSelectedNode] = useState<ResourceNode | null>(null);
  const [ready, setReady] = useState(false);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;
    setReady(false);
    setInitialized(false);
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    const simulation = createSimulation(data, width, height);
    setReady(true);
    renderGraph(svg, data, simulation, width, height, setSelectedNode);
    const timer = setTimeout(() => setInitialized(true), 100);
    return () => {
      clearTimeout(timer);
      simulation.stop();
    };
  }, [data, width, height]);

  // Get children of selected node
  const getNodeChildren = (node: ResourceNode): ResourceNode[] => {
    const childLinks = data.links.filter(link => 
      link.source === node.id && link.type === 'parent'
    );
    return childLinks.map(link => {
      const targetId = link.target;
      return data.nodes.find(n => n.id === targetId);
    }).filter((n): n is ResourceNode => n !== undefined);
  };

  const selectedNodeChildren = selectedNode ? getNodeChildren(selectedNode) : [];

  return (
    <div className="reading-graph-wrapper">
      <div className={`reading-graph-container ${initialized ? 'initialized' : ''}`}>
        <svg 
          ref={svgRef} 
          width={width} 
          height={height} 
          style={{ visibility: ready ? 'visible' : 'hidden' }}
        />
      </div>
      
      {selectedNode && (
        <div className="selected-node-details">
          <div className="selected-node-header">
            <h3>{selectedNode.title}</h3>
            {selectedNode.author && <p className="author">by {selectedNode.author}</p>}
            {selectedNode.description && <p className="description">{selectedNode.description}</p>}
            {selectedNode.url && (
              <a 
                href={selectedNode.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="external-link"
              >
                Learn more →
              </a>
            )}
          </div>
          
          {selectedNodeChildren.length > 0 && (
            <div className="node-children">
              <h4>Related Items</h4>
              <ul className="children-list">
                {selectedNodeChildren.map(child => (
                  <li key={child.id} onClick={() => setSelectedNode(child)}>
                    <span className="child-title">{child.title}</span>
                    {child.author && <span className="child-author">by {child.author}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ResourceGraphComponent; 