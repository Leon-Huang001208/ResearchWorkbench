import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function safeSourceURL(value: unknown) {
  if (typeof value !== 'string') return undefined;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export default function Content({ children, onSource }: { children: string; onSource?: (id: string) => void }) {
  return <Markdown remarkPlugins={[remarkGfm]} skipHtml disallowedElements={['img']} components={{
    a: ({ href, children: label }) => {
      const citation = /^#src-(S\d+)$/.exec(href || '');
      if (citation) {
        return onSource
          ? <button type="button" className="qa-citation" onClick={() => onSource(citation[1])} aria-label={`查看来源 ${citation[1]}`}>{label}</button>
          : <sup>{label}</sup>;
      }
      const url = safeSourceURL(href);
      return url ? <a href={url} target="_blank" rel="noopener noreferrer">{label}</a> : <span>{label}</span>;
    },
  }}>{children}</Markdown>;
}
