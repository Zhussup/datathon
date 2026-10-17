import type { CSSProperties } from "react";
import { Icon } from "./Icon";
import { formatTime } from "./video";
import type { JobResult } from "./api";

// Вердикт реального анализа: карточки-эпизоды, крошки кадров-доказательств,
// переход к кадру в плеере. Разметка и классы повторяют демо-вердикт.
export function Verdict({
  visible,
  result,
  onSeek,
  onReset,
}: {
  visible: boolean;
  result: JobResult;
  onSeek: (seconds: number) => void;
  onReset: () => void;
}) {
  const findings = result.violations;
  const flagged = result.verdict === "violation" && findings.length > 0;
  return (
    <section
      className="demo-verdict"
      data-visible={visible}
      aria-hidden={!visible}
      inert={!visible}
      aria-label="Вердикт проверки"
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
      </div>
      <div className="verdict-title status-swap verdict-enter" aria-live="polite">
        <h2 data-active={flagged} aria-hidden={!flagged}>
          Есть моменты
          <br />
          для проверки.
        </h2>
        <h2 data-active={!flagged} aria-hidden={flagged}>
          Без замечаний.
          <br />
          Всё в порядке.
        </h2>
      </div>
      <div className="verdict-results">
        <div
          className="verdict-result"
          data-active={flagged}
          aria-hidden={!flagged}
          inert={!flagged}
        >
          {findings.map((violation, index) => {
            const at = violation.evidence_frames[0]?.timestamp_sec ?? violation.timecode_sec;
            return (
              <button
                key={violation.rule_id ?? index}
                className="verdict-moment verdict-enter"
                style={{ "--moment-index": index } as CSSProperties}
                onClick={() => onSeek(at)}
                aria-label={`Открыть эпизод ${index + 1} на ${formatTime(violation.timecode_sec)}`}
              >
                {violation.evidence_frames.some((frame) => frame.image_base64) && (
                  <span className="verdict-frames" aria-hidden="true">
                    {violation.evidence_frames
                      .filter((frame) => frame.image_base64)
                      .map((frame) => (
                        <img
                          key={frame.timestamp_sec}
                          src={`data:image/jpeg;base64,${frame.image_base64}`}
                          alt=""
                          onClick={(event) => {
                            event.stopPropagation();
                            onSeek(frame.timestamp_sec);
                          }}
                        />
                      ))}
                  </span>
                )}
                <span className="moment-heading">
                  <span className="event-time">{formatTime(violation.timecode_sec)}</span>
                  <span className="event-index">0{index + 1}</span>
                  <Icon name="arrow" size={15} />
                </span>
                <h3>{violation.type}</h3>
                <p>{violation.description}</p>
                {violation.npa && <p className="verdict-npa">{violation.npa}</p>}
              </button>
            );
          })}
        </div>
        <div
          className="verdict-result"
          data-active={!flagged}
          aria-hidden={flagged}
          inert={flagged}
        >
          <div className="verdict-empty verdict-enter">
            <Icon name="shield" size={28} />
            <h3>Нарушений не обнаружено</h3>
            <p>Запись просмотрена целиком: значимых признаков не найдено.</p>
          </div>
        </div>
      </div>
      <div className="verdict-footer verdict-enter">
        <p>
          {flagged
            ? `Эпизодов с признаками: ${findings.length}. Нажмите эпизод — откроется кадр.`
            : "Вердикт по всей записи. Кадры-доказательства будут приложены к находкам."}
        </p>
        <button onClick={onReset}>
          Новое видео <Icon name="upload" size={14} />
        </button>
      </div>
    </section>
  );
}