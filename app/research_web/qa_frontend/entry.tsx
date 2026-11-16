import { createRoot } from 'react-dom/client';
import Chat, { type ChatProps } from './pages/Chat';
import './qa.css';

export function mountQA(element: HTMLElement) {
  const root = createRoot(element);
  return {
    render: (props: ChatProps) => root.render(<Chat key={props.sessionId || 'new'} {...props} />),
    dispose: () => root.unmount(),
  };
}
