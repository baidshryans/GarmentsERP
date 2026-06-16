import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import HelpDrawer from './HelpDrawer';

vi.mock('./useManual', () => ({
  useManual: () => ({
    getSection: (id) => ({ id, title: 'Recording a Payment', markdown: 'Open the enrollment and click Pay.' }),
    search: (q) =>
      q.includes('pay')
        ? [{ section: { id: '14-3', title: 'Recording a Payment', chapterId: '14-gold' }, snippet: 'click Pay to record a payment' }]
        : [],
  }),
}));
vi.mock('./MarkdownView', () => ({ default: ({ markdown }) => <div>{markdown}</div> }));

describe('HelpDrawer', () => {
  it('shows search results as the user types', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <HelpDrawer open onOpenChange={() => {}} />
      </MemoryRouter>
    );
    await user.type(screen.getByPlaceholderText(/search the manual/i), 'pay');
    expect(await screen.findByText('Recording a Payment')).toBeInTheDocument();
  });
});
