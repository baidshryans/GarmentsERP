import { useState } from 'react';
import { HelpCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import HelpDrawer from './HelpDrawer';

export default function HelpButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Help & Manual"
        title="Help & Manual"
        onClick={() => setOpen(true)}
      >
        <HelpCircle className="size-5" />
      </Button>
      <HelpDrawer open={open} onOpenChange={setOpen} />
    </>
  );
}
