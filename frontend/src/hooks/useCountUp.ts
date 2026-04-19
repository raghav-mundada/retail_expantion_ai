/**
 * useCountUp — animates a number from 0 (or `from`) to `to` over `duration` ms.
 * Returns the current display value. Starts when `active` flips to true.
 */
import { useEffect, useRef, useState } from 'react';

interface Options {
  from?:     number;
  to:        number;
  duration?: number;  // ms, default 800
  active?:   boolean; // start trigger, default true
  easing?:   (t: number) => number;
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

export function useCountUp({
  from     = 0,
  to,
  duration = 800,
  active   = true,
  easing   = easeOutCubic,
}: Options): number {
  const [value, setValue] = useState(active ? from : from);
  const rafRef   = useRef<number>(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) { setValue(from); return; }

    startRef.current = null;
    cancelAnimationFrame(rafRef.current);

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const t       = Math.min(elapsed / duration, 1);
      setValue(from + (to - from) * easing(t));
      if (t < 1) rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [active, from, to, duration, easing]);

  return value;
}
