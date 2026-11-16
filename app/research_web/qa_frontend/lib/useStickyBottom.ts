// 粘底滚动：仅当用户在底部 ~80px 内时自动跟随；上滑（滚轮/触摸/拖动）即停止跟随，回到底部恢复
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

const THRESHOLD = 80;

export function useStickyBottom(target: RefObject<HTMLElement | null> | "window", dep: unknown) {
  const follow = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const el = useCallback((): HTMLElement | null => target === "window" ? (document.scrollingElement as HTMLElement) : target.current, [target]);
  const dist = useCallback(() => { const s = el(); return s ? s.scrollHeight - s.scrollTop - s.clientHeight : 0; }, [el]);

  useEffect(() => {
    const s = el(); if (!s) return;
    const on: EventTarget = target === "window" ? window : s;
    const onScroll = () => { const b = dist() < THRESHOLD; follow.current = b; setAtBottom(b); };
    const onWheel = (e: Event) => { if ((e as WheelEvent).deltaY < 0) { follow.current = false; setAtBottom(dist() < THRESHOLD); } };
    const onTouch = () => { follow.current = false; };
    on.addEventListener("scroll", onScroll, { passive: true });
    on.addEventListener("wheel", onWheel, { passive: true });
    on.addEventListener("touchmove", onTouch, { passive: true });
    return () => { on.removeEventListener("scroll", onScroll); on.removeEventListener("wheel", onWheel); on.removeEventListener("touchmove", onTouch); };
  }, [el, dist, target]);

  useEffect(() => {
    if (!follow.current) { setAtBottom(dist() < THRESHOLD); return; }
    const s = el(); if (s) s.scrollTop = s.scrollHeight;
  }, [dep, el, dist]);

  const toBottom = useCallback(() => { follow.current = true; const s = el(); if (s) s.scrollTop = s.scrollHeight; setAtBottom(true); }, [el]);
  return { atBottom, toBottom };
}
