import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({ gfm: true, breaks: false });

// Allow rendered Mermaid SVG to survive sanitization.
const SVG_TAGS = ['svg', 'path', 'g', 'rect', 'circle', 'ellipse', 'line', 'polyline',
  'polygon', 'text', 'tspan', 'marker', 'defs', 'foreignobject', 'style'];
const SVG_ATTR = ['viewbox', 'd', 'points', 'transform', 'marker-end', 'marker-start',
  'orient', 'refx', 'refy', 'markerwidth', 'markerheight', 'x', 'y', 'x1', 'x2', 'y1', 'y2',
  'cx', 'cy', 'r', 'rx', 'ry', 'fill', 'stroke', 'stroke-width', 'text-anchor', 'font-size',
  'font-family', 'class', 'id', 'width', 'height', 'style', 'dominant-baseline'];

export function renderMarkdown(md) {
  const html = marked.parse(String(md || ''));
  return DOMPurify.sanitize(html, {
    ADD_TAGS: SVG_TAGS,
    ADD_ATTR: SVG_ATTR,
  });
}
