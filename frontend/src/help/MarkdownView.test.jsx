import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import MarkdownView from './MarkdownView';

vi.mock('./MermaidDiagram', () => ({ default: () => <div data-testid="mermaid" /> }));

describe('MarkdownView', () => {
  it('renders markdown headings and paragraphs', () => {
    render(<MarkdownView markdown={'## Sales\n\nCreate an invoice here.'} />);
    expect(screen.getByText('Create an invoice here.')).toBeInTheDocument();
  });
  it('mounts a MermaidDiagram for a mermaid code block', () => {
    render(<MarkdownView markdown={'```mermaid\ngraph TD; A-->B\n```'} />);
    expect(screen.getByTestId('mermaid')).toBeInTheDocument();
  });
  it('highlights matched terms', () => {
    const { container } = render(
      <MarkdownView markdown={'Record a payment now.'} highlightTerms={['payment']} />
    );
    expect(container.querySelector('mark')).not.toBeNull();
  });
  it('shows a match count when highlightTerms match multiple times', () => {
    const { getByText } = render(
      <MarkdownView markdown={'payment one. payment two. payment three.'} highlightTerms={['payment']} />
    );
    expect(getByText(/3 matches/i)).toBeInTheDocument();
  });
});
