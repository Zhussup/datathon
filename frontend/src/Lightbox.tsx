import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "./Icon";
import { formatTime } from "./video";
import type { EvidenceFrame } from "./api";

// Полноразмерный просмотр кадра-доказательства. Поверх всего через портал — внутри
// .status-panel / .demo-verdict идёт борьба с position: absolute и overflow.
// Навигация ←/→ и Esc/клик-по-фону; reduced-motion глушится глобальным media-блоком
// в style.css, отдельных JS-проверок не нужно.
export function Lightbox({
  frames,
  initialIndex,
  videoName,
  onClose,
  onSeek,
}: {
  frames: EvidenceFrame[];
  initialIndex: number;
  videoName?: string;
  onClose: () => void;
  onSeek?: (seconds: number) => void;
}) {
  const [index, setIndex] = useState(initialIndex);
  const containerRef = useRef<HTMLDivElement>(null);
  const restoredFocus = useRef<Element | null>(null);
  const total = frames.length;
  const canNavigate = total > 1;
  const current = frames[index];

  useEffect(() => {
    restoredFocus.current = document.activeElement;
    containerRef.current?.focus();
    return () => {
      const target = restoredFocus.current as HTMLElement | null;
      target?.focus?.();
    };
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      const tag = (event.target as HTMLElement | null)?.tagName ?? "";
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (canNavigate && event.key === "ArrowLeft") {
        event.preventDefault();
        setIndex((i) => (i - 1 + total) % total);
      } else if (canNavigate && event.key === "ArrowRight") {
        event.preventDefault();
        setIndex((i) => (i + 1) % total);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canNavigate, total, onClose]);

  return createPortal(
    <div
      ref={containerRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="lightbox-caption"
      className="lightbox"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <button
        type="button"
        className="lightbox-close"
        onClick={onClose}
        aria-label="Закрыть кадр"
      >
        <Icon name="close" size={22} />
      </button>
      {canNavigate && (
        <button
          type="button"
          className="lightbox-nav lightbox-prev"
          onClick={() => setIndex((i) => (i - 1 + total) % total)}
          aria-label="Предыдущий кадр"
        >
          <Icon name="arrow" size={22} />
        </button>
      )}
      {current && (
        <img
          key={current.timestamp_sec}
          className="lightbox-img"
          src={`data:image/jpeg;base64,${current.image_base64}`}
          alt={`Кадр-доказательство на ${formatTime(current.timestamp_sec)}`}
          onClick={(event) => event.stopPropagation()}
        />
      )}
      {canNavigate && (
        <button
          type="button"
          className="lightbox-nav lightbox-next"
          onClick={() => setIndex((i) => (i + 1) % total)}
          aria-label="Следующий кадр"
        >
          <Icon name="arrow" size={22} />
        </button>
      )}
      <div className="lightbox-caption" id="lightbox-caption">
        {formatTime(current.timestamp_sec)}
        {canNavigate && ` · ${index + 1} / ${total}`}
        {videoName && ` · ${videoName}`}
        {onSeek && (
          <button
            type="button"
            className="lightbox-seek"
            onClick={() => {
              onSeek(current.timestamp_sec);
              onClose();
            }}
          >
            <Icon name="arrow" size={12} />
            К кадру в плеере
          </button>
        )}
      </div>
    </div>,
    document.body,
  );
}
