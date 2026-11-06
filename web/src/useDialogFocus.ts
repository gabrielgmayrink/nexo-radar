import { useEffect, type RefObject } from 'react';

// Keep keyboard navigation inside an open drawer and return to its trigger.
export function useDialogFocus(active: boolean, ref: RefObject<HTMLElement | null>, returnFocus?: RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!active || !ref.current) return;
    const panel = ref.current;
    const previous = returnFocus?.current || (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const controls = () => Array.from(panel.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input, select, textarea, [tabindex="0"]',
    )).filter(element => element.getClientRects().length > 0);
    const frame = requestAnimationFrame(() => (controls()[0] || panel).focus());
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const items = controls();
      const first = items[0], last = items[items.length - 1];
      if (!first) { event.preventDefault(); panel.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener('keydown', trap);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', trap);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
      else document.getElementById('results')?.focus();
    };
  }, [active, ref, returnFocus]);
}
