import { useEffect, useRef, useState } from 'react';

let _mermaidPromise = null;
function loadMermaid() {
  if (!_mermaidPromise) {
    _mermaidPromise = import('mermaid').then((m) => {
      m.default.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral' });
      return m.default;
    });
  }
  return _mermaidPromise;
}

export default function MermaidDiagram({ code, id }) {
  const ref = useRef(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadMermaid()
      .then((mermaid) => mermaid.render(`mmd-${id}-${Math.abs(hash(code))}`, code))
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch(() => !cancelled && setError(true));
    return () => { cancelled = true; };
  }, [code, id]);

  if (error) {
    return (
      <details className="my-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm">
        <summary>Diagram could not be rendered — show source</summary>
        <pre className="overflow-x-auto text-xs">{code}</pre>
      </details>
    );
  }
  return <div className="mermaid-diagram my-4 flex justify-center" ref={ref} aria-label="workflow diagram" />;
}

function hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h << 5) - h + str.charCodeAt(i) | 0;
  return h;
}
