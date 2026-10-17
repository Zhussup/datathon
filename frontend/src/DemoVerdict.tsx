import { useState } from "react";
import type { CSSProperties } from "react";
import { Icon } from "./Icon";
import { demoTimestamp, formatTime } from "./video";

const moments = [
  {
    position: 0.18,
    title: "Наличные без присмотра",
    description: "Пример: сотрудник отошёл, оставив наличные на рабочем столе.",
  },
  {
    position: 0.42,
    title: "Передача вне рабочей зоны",
    description:
      "Пример: передача наличных происходит за пределами кассового окна.",
  },
  {
    position: 0.72,
    title: "Обзор операции перекрыт",
    description:
      "Пример: действия с наличными не видны в кадре. Нужна проверка контекста.",
  },
];

export function DemoVerdict({
  visible,
  duration,
  onSeek,
  onReset,
}: {
  visible: boolean;
  duration: number;
  onSeek: (seconds: number) => void;
  onReset: () => void;
}) {
  const [review, setReview] = useState(true);
  return (
    <section
      className="demo-verdict"
      data-visible={visible}
      aria-hidden={!visible}
      inert={!visible}
      aria-label="Демонстрационный вердикт"
    >
      <svg
        className="verdict-frame"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <rect
          x="0.5"
          y="0.5"
          width="99"
          height="99"
          rx="4"
          pathLength="1"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="verdict-heading verdict-enter">
        <span className="eyebrow">РЕЗУЛЬТАТ ПРОВЕРКИ</span>
        <span className="demo-badge">ДЕМО</span>
      </div>
      <div
        className="verdict-title status-swap verdict-enter"
        aria-live="polite"
      >
        <h2 data-active={review} aria-hidden={!review}>
          Есть моменты
          <br />
          для проверки.
        </h2>
        <h2 data-active={!review} aria-hidden={review}>
          Без замечаний.
          <br />
          Всё в порядке.
        </h2>
      </div>
      <div
        className="verdict-options verdict-enter"
        role="group"
        aria-label="Демо-сценарий"
      >
        <button aria-pressed={review} onClick={() => setReview(true)}>
          Есть замечания
        </button>
        <button aria-pressed={!review} onClick={() => setReview(false)}>
          Без замечаний
        </button>
      </div>
      <div className="verdict-results">
        <div
          className="verdict-result"
          data-active={review}
          aria-hidden={!review}
          inert={!review}
        >
          {moments.map((moment, index) => {
            const timestamp = demoTimestamp(duration, moment.position);
            return (
              <button
                key={moment.position}
                className="verdict-moment verdict-enter"
                style={{ "--moment-index": index } as CSSProperties}
                onClick={() => onSeek(timestamp)}
                disabled={duration <= 0}
                aria-label={`Открыть демоэпизод ${index + 1} на ${formatTime(timestamp)}`}
              >
                <span className="moment-heading">
                  <span className="event-time">{formatTime(timestamp)}</span>
                  <span className="event-index">0{index + 1}</span>
                  <Icon name="arrow" size={15} />
                </span>
                <h3>{moment.title}</h3>
                <p>{moment.description}</p>
              </button>
            );
          })}
        </div>
        <div
          className="verdict-result"
          data-active={!review}
          aria-hidden={review}
          inert={review}
        >
          <div className="verdict-empty verdict-enter">
            <Icon name="shield" size={28} />
            <h3>Замечаний нет</h3>
            <p>Так выглядит результат без событий, требующих внимания.</p>
          </div>
        </div>
      </div>
      <div className="verdict-footer verdict-enter">
        <p>
          Демо-сценарий, не анализ вашей записи. Таймкоды показывают навигацию
          по видео.
        </p>
        <button onClick={onReset}>
          Новое видео <Icon name="upload" size={14} />
        </button>
      </div>
    </section>
  );
}
