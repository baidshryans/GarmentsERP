export function slugify(heading) {
  return String(heading)
    .trim()
    .toLowerCase()
    .replace(/[^\w\s.-]/g, '') // keep word chars, whitespace, dot, dash
    .replace(/\./g, '-')       // 14.3 -> 14-3
    .replace(/\s+/g, '-')      // spaces -> dash
    .replace(/-+/g, '-')       // collapse repeats
    .replace(/^-+|-+$/g, '');  // trim leading/trailing dashes
}

export function stripMarkdown(md) {
  return String(md)
    .replace(/```[\s\S]*?```/g, ' ')  // drop fenced code (incl. mermaid)
    .replace(/`([^`]+)`/g, '$1')      // inline code
    .replace(/^#{1,6}\s+/gm, '')      // heading hashes
    .replace(/\*\*([^*]+)\*\*/g, '$1')// bold
    .replace(/\*([^*]+)\*/g, '$1')    // italic
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '') // images
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1') // links -> text
    .replace(/^\s*[-*+]\s+/gm, '')    // list bullets
    .replace(/\|/g, ' ')              // table pipes
    .replace(/[ \t]+/g, ' ')
    .trim();
}

export function parseManual(raw) {
  const lines = String(raw).split('\n');
  const sections = [];
  let inFence = false;
  let lastChapterId = null;
  let current = null;
  const bodyLines = [];

  const flush = () => {
    if (current) {
      current.markdown = bodyLines.join('\n').trim();
      current.plainText = stripMarkdown(current.markdown);
      sections.push(current);
    }
    bodyLines.length = 0;
  };

  for (const line of lines) {
    if (/^```/.test(line)) inFence = !inFence;
    const h = !inFence && line.match(/^(#{2,3})\s+(.*\S)\s*$/);
    if (h) {
      flush();
      const level = h[1].length === 2 ? 'chapter' : 'section';
      const title = h[2].trim();
      const id = slugify(title);
      if (level === 'chapter') lastChapterId = id;
      current = {
        id,
        title,
        level,
        chapterId: level === 'chapter' ? id : lastChapterId,
        markdown: '',
        plainText: '',
      };
    } else if (current) {
      bodyLines.push(line);
    }
  }
  flush();

  const toc = [];
  for (const s of sections) {
    if (s.level === 'chapter') {
      toc.push({ id: s.id, title: s.title, children: [] });
    } else {
      const parent = toc[toc.length - 1];
      if (parent) parent.children.push({ id: s.id, title: s.title });
    }
  }
  return { sections, toc };
}
