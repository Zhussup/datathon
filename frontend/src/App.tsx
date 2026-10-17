import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { DemoScene } from "./DemoScene";
import { findings, formatTime, validateVideo } from "./demo";

type Stage = "ready" | "processing" | "done";
export default function App() {
  const [section, setSection] = useState<"analysis" | "guide">("analysis");
  const [tab, setTab] = useState<"events" | "about">("events");
  const [selected, setSelected] = useState(1);
  const [demoVerdict, setDemoVerdict] = useState<"violation" | "no_violation">(
    "violation",
  );
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [stage, setStage] = useState<Stage>("done");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(44);
  const [duration, setDuration] = useState(105);
  const input = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const player = useRef<HTMLDivElement>(null);
  const results = useRef<HTMLElement>(null);
  const isDemo = !file;
  const visibleFindings = demoVerdict === "violation" ? findings : [];
  useEffect(() => {
    if (!file) {
      setVideoUrl("");
      return;
    }
    const url = URL.createObjectURL(file);
    setVideoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    if (stage !== "processing") return;
    const timer = window.setInterval(
      () => setProgress((p) => Math.min(p + 5, 100)),
      160,
    );
    return () => window.clearInterval(timer);
  }, [stage]);
  useEffect(() => {
    if (progress === 100 && stage === "processing") {
      setStage("done");
      setTab("events");
    }
  }, [progress, stage]);
  useEffect(() => {
    if (!playing || !isDemo) return;
    const timer = window.setInterval(
      () => setTime((t) => Math.min(t + 1, 105)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [playing, isDemo]);
  useEffect(() => {
    if (isDemo && time >= duration) setPlaying(false);
  }, [isDemo, time, duration]);
  function chooseFile(next?: File) {
    if (!next) return;
    const message = validateVideo(next);
    setError(message);
    if (message) return;
    setFile(next);
    setStage("ready");
    setPlaying(false);
    setProgress(0);
    setTime(0);
    setDuration(0);
  }
  function openDemo() {
    setFile(null);
    setStage("done");
    setProgress(0);
    setError("");
    setPlaying(false);
    setTime(44);
    setDuration(105);
    setSelected(1);
    setDemoVerdict("violation");
    setTab("events");
    if (input.current) input.current.value = "";
  }
  function seek(next: number) {
    const clamped = Math.max(0, Math.min(next, duration));
    setTime(clamped);
    if (video.current) video.current.currentTime = clamped;
  }
  function selectFinding(id: number) {
    setSelected(id);
    if (isDemo) seek(findings[id - 1].time);
  }
  async function togglePlayback() {
    if (isDemo) {
      if (time >= duration) setTime(0);
      setPlaying(!playing);
      return;
    }
    if (!video.current) return;
    if (video.current.paused) {
      try {
        await video.current.play();
      } catch {
        setError(
          "Браузер не смог воспроизвести запись. Попробуйте MP4 с кодеком H.264.",
        );
      }
    } else video.current.pause();
  }
  async function fullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await player.current?.requestFullscreen();
    } catch {
      setError("Полноэкранный режим недоступен в этом браузере.");
    }
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={() => setSection("analysis")}
          aria-label="Forte Vision, главная"
        >
          <span className="brand-mark">
            f<span>•</span>
          </span>
          <span>
            forte<span className="brand-vision">vision</span>
          </span>
        </a>
        <span className="sidebar-label">РАБОЧЕЕ ПРОСТРАНСТВО</span>
        <nav aria-label="Основная навигация">
          <button
            className={`nav-item ${section === "analysis" ? "active" : ""}`}
            onClick={() => setSection("analysis")}
          >
            <Icon name="grid" />
            Проверка видео
            <span className="nav-indicator" />
          </button>
          <button
            className={`nav-item ${section === "guide" ? "active" : ""}`}
            onClick={() => setSection("guide")}
          >
            <Icon name="file" />
            Как это работает
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-symbol">
            <Icon name="shield" size={23} />
          </div>
          <strong>Данные под контролем</strong>
          <p>
            Видеозаписи остаются
            <br />в вашем браузере.
          </p>
          <span className="local-status">
            <i />
            Локальный деморежим
          </span>
        </div>
        <div className="sidebar-footer">
          <span className="mini-brand">forte</span>
          <span>Datathon 2026</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Рабочее пространство
            <Icon name="chevron" size={13} />
            <span>
              {section === "analysis" ? "Проверка видео" : "Как это работает"}
            </span>
          </div>
          <span className="demo-pill">
            <i />
            Frontend demo
          </span>
          <span className="avatar" aria-label="Рабочее пространство Forte">
            FV
          </span>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span />
                FORTE VISION
              </div>
              <h1>
                {section === "analysis"
                  ? "Каждая деталь под контролем."
                  : "От записи — к понятному результату."}
              </h1>
              <p>
                {section === "analysis"
                  ? "Проверяйте кассовые операции. Находите важное. Принимайте решения."
                  : "Три шага для проверки визуально наблюдаемых событий."}
              </p>
            </div>
            <div className="heading-icon">
              <Icon name="eye" size={29} />
            </div>
          </div>
          {section === "guide" ? (
            <section className="panel guide-panel">
              <span className="section-kicker">ПРОЦЕСС ПРОВЕРКИ</span>
              <h2>Всё начинается с видео</h2>
              <div className="guide-grid">
                {[
                  "Загрузите запись",
                  "Дождитесь анализа",
                  "Изучите события",
                ].map((title, i) => (
                  <article key={title}>
                    <span className="step-number">0{i + 1}</span>
                    <h3>{title}</h3>
                    <p>
                      {
                        [
                          "Выберите .mov или .mp4, до 200 МБ. В текущем прототипе запись открывается только в браузере.",
                          "Деморежим показывает этапы обработки. Модель и серверная часть пока не подключены.",
                          "Проверьте таймкод, кадр, наблюдение и нормативный источник. Итоговое решение принимает проверяющий.",
                        ][i]
                      }
                    </p>
                  </article>
                ))}
              </div>
              <div className="notice">
                <Icon name="info" />
                <span>
                  Нормативные ссылки появятся после проверки источников.
                  Демопримеры не являются юридическим заключением.
                </span>
              </div>
              <button
                className="primary-button"
                onClick={() => setSection("analysis")}
              >
                Перейти к проверке
                <Icon name="arrow" size={17} />
              </button>
            </section>
          ) : (
            <>
              <div className="steps-bar">
                {[
                  "Загрузите видео",
                  "Запустите проверку",
                  "Изучите результат",
                ].map((title, i) => (
                  <div className="step" key={title}>
                    <span className="step-icon">
                      <Icon
                        name={i === 0 ? "upload" : i === 1 ? "eye" : "check"}
                      />
                    </span>
                    <div>
                      <strong>
                        <span>0{i + 1}</span>
                        {title}
                      </strong>
                      <p>
                        {
                          [
                            "Запись кассовой операции",
                            "Анализ видимых действий",
                            "События, таймкоды и обоснования",
                          ][i]
                        }
                      </p>
                    </div>
                    {i < 2 && <Icon name="chevron" size={16} />}
                  </div>
                ))}
              </div>
              <div className="analysis-layout">
                <div className="upload-column">
                  <section className="panel upload-panel">
                    <div className="panel-title">
                      <span className="title-icon">
                        <Icon name="upload" size={18} />
                      </span>
                      <h2>Новая проверка</h2>
                      <span className="muted-number">01</span>
                    </div>
                    <input
                      ref={input}
                      type="file"
                      accept=".mov,.mp4,video/quicktime,video/mp4"
                      className="visually-hidden"
                      aria-label="Выбрать видеозапись"
                      onChange={(e) => {
                        chooseFile(e.target.files?.[0]);
                        e.target.value = "";
                      }}
                    />
                    <div
                      className={`upload-zone ${dragging ? "dragging" : ""}`}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={(e) => {
                        if (!e.currentTarget.contains(e.relatedTarget as Node))
                          setDragging(false);
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        chooseFile(e.dataTransfer.files[0]);
                      }}
                    >
                      <span className="upload-visual">
                        <Icon name={file ? "film" : "upload"} size={27} />
                      </span>
                      <h3>{file ? file.name : "Перетащите видео сюда"}</h3>
                      <p>
                        {file
                          ? `${(file.size / 1024 / 1024).toFixed(1)} МБ · файл выбран`
                          : "или выберите файл на устройстве"}
                      </p>
                      <button
                        className="primary-button"
                        onClick={() => input.current?.click()}
                      >
                        {file ? "Заменить видео" : "Выбрать видео"}
                        <Icon name="arrow" size={17} />
                      </button>
                      <span className="upload-meta">MOV, MP4 · до 200 МБ</span>
                    </div>
                    {file && (
                      <div className="analyze-actions">
                        <button
                          className="primary-button"
                          disabled={stage === "processing"}
                          onClick={() => {
                            setProgress(0);
                            setStage("processing");
                            setPlaying(false);
                            video.current?.pause();
                          }}
                        >
                          {stage === "processing"
                            ? "Демонстрация обработки…"
                            : "Запустить демопроверку"}
                          <Icon name="play" size={16} />
                        </button>
                        <button
                          className="icon-button"
                          aria-label="Удалить выбранное видео"
                          onClick={openDemo}
                        >
                          <Icon name="close" size={18} />
                        </button>
                        <p>Имитация этапов. AI-анализ не подключён.</p>
                      </div>
                    )}
                    {error && (
                      <p className="error-message" role="alert">
                        {error}
                      </p>
                    )}
                    <div className="upload-footnote">
                      <Icon name="shield" size={15} />
                      <span>Видео не отправляется во внешние сервисы</span>
                    </div>
                  </section>
                  <section className="demo-card">
                    <span className="demo-card-icon">
                      <Icon name="play" size={20} />
                    </span>
                    <span className="section-kicker">ПОПРОБУЙТЕ СЕЙЧАС</span>
                    <h3>Посмотрите на примере</h3>
                    <p>
                      Изучите, как выглядит результат
                      <br />
                      проверки видеозаписи.
                    </p>
                    <button
                      className="text-button"
                      onClick={() => {
                        openDemo();
                        results.current?.scrollIntoView({
                          behavior: "smooth",
                          block: "nearest",
                        });
                      }}
                    >
                      Открыть демопример
                      <Icon name="arrow" size={17} />
                    </button>
                    <div className="demo-decoration" />
                  </section>
                  <div className="helper-note">
                    <Icon name="info" size={17} />
                    <p>
                      Система помогает заметить возможные нарушения.
                      Окончательное решение остаётся за проверяющим.
                    </p>
                  </div>
                </div>
                <section ref={results} className="panel results-panel">
                  <div className="panel-title">
                    <span className="title-icon">
                      <Icon name="film" size={18} />
                    </span>
                    <h2>
                      {file ? "Проверка видеозаписи" : "Результат проверки"}
                    </h2>
                    <span className="outline-badge">
                      {isDemo ? "ДЕМОПРИМЕР" : "ЛОКАЛЬНОЕ ВИДЕО"}
                    </span>
                  </div>
                  <div className="video-meta">
                    <div className="file-symbol">
                      <Icon name="file" size={18} />
                    </div>
                    <div>
                      <strong title={file?.name}>
                        {file?.name || "cashdesk_demo.mov"}
                      </strong>
                      <p>
                        {isDemo
                          ? "Иллюстрация · 01:45 · без звука"
                          : `${(file.size / 1024 / 1024).toFixed(1)} МБ · только в браузере`}
                      </p>
                    </div>
                    <span className="complete-badge">
                      <Icon
                        name={stage === "done" ? "check" : "clock"}
                        size={13}
                      />
                      {stage === "done"
                        ? isDemo
                          ? "Пример результата"
                          : "Демонстрация завершена"
                        : stage === "processing"
                          ? "Демообработка"
                          : "Готово к просмотру"}
                    </span>
                  </div>
                  {isDemo && (
                    <div className="demo-scenarios">
                      <span>Демосценарий</span>
                      <button
                        className={demoVerdict === "violation" ? "active" : ""}
                        aria-pressed={demoVerdict === "violation"}
                        onClick={() => setDemoVerdict("violation")}
                      >
                        С событиями
                      </button>
                      <button
                        className={
                          demoVerdict === "no_violation" ? "active" : ""
                        }
                        aria-pressed={demoVerdict === "no_violation"}
                        onClick={() => setDemoVerdict("no_violation")}
                      >
                        Без нарушений
                      </button>
                    </div>
                  )}
                  <div className="video-player" ref={player}>
                    {isDemo ? (
                      <DemoScene
                        time={demoVerdict === "violation" ? time : 0}
                      />
                    ) : (
                      <video
                        ref={video}
                        src={videoUrl || undefined}
                        playsInline
                        muted
                        preload="metadata"
                        onLoadedMetadata={(e) =>
                          setDuration(
                            Number.isFinite(e.currentTarget.duration)
                              ? e.currentTarget.duration
                              : 0,
                          )
                        }
                        onTimeUpdate={(e) =>
                          setTime(e.currentTarget.currentTime)
                        }
                        onPlay={() => setPlaying(true)}
                        onPause={() => setPlaying(false)}
                        onEnded={() => setPlaying(false)}
                        onError={() =>
                          setError(
                            "Кодек этого видео не поддерживается браузером. Для предпросмотра используйте MP4 (H.264).",
                          )
                        }
                      />
                    )}
                    <div className="video-top-label">
                      <i />
                      {isDemo
                        ? "Демонстрационный пример"
                        : "Локальный предпросмотр"}
                    </div>
                    {!playing && (
                      <button
                        className="video-center-play"
                        onClick={togglePlayback}
                        aria-label="Воспроизвести"
                      >
                        <Icon name="play" size={24} />
                      </button>
                    )}
                    <div className="video-controls">
                      <button
                        aria-label={playing ? "Пауза" : "Воспроизвести видео"}
                        onClick={togglePlayback}
                      >
                        <Icon name={playing ? "pause" : "play"} size={17} />
                      </button>
                      <span>
                        {formatTime(time)}
                        <span className="video-total">
                          {" "}
                          / {formatTime(duration)}
                        </span>
                      </span>
                      <div className="timeline">
                        <input
                          aria-label="Позиция видео"
                          type="range"
                          min="0"
                          max={duration || 1}
                          step="0.1"
                          value={Math.min(time, duration)}
                          disabled={!duration}
                          onChange={(e) => seek(Number(e.target.value))}
                        />
                        {isDemo &&
                          visibleFindings.map((f) => (
                            <button
                              key={f.id}
                              style={{ left: `${(f.time / 105) * 100}%` }}
                              onClick={() => selectFinding(f.id)}
                              aria-label={`Событие ${f.id}, ${formatTime(f.time)}`}
                            />
                          ))}
                      </div>
                      <button
                        aria-label="Полноэкранный режим"
                        onClick={fullscreen}
                      >
                        <Icon name="expand" size={17} />
                      </button>
                    </div>
                  </div>
                  {stage === "processing" ? (
                    <div className="processing-state" role="status">
                      <div className="processing-heading">
                        <span className="spinner" />
                        <strong>
                          {progress < 35
                            ? "Подготовка видеозаписи"
                            : progress < 75
                              ? "Демонстрация поиска событий"
                              : "Подготовка деморезультата"}
                        </strong>
                        <span>{progress}%</span>
                      </div>
                      <progress max="100" value={progress} />
                      <p>Имитация обработки. Видео не анализируется моделью.</p>
                    </div>
                  ) : file ? (
                    <div className="local-result" role="status">
                      <span className="title-icon">
                        <Icon name="info" />
                      </span>
                      <div>
                        <h3>
                          {stage === "done"
                            ? "Демонстрация обработки завершена"
                            : "Видео готово к просмотру"}
                        </h3>
                        <p>
                          {stage === "done"
                            ? "AI-модель пока не подключена, поэтому вердикт по вашей записи не сформирован. Откройте демопример, чтобы изучить карточки событий."
                            : "Запустите демопроверку, чтобы посмотреть этапы обработки. Все действия выполняются в браузере."}
                        </p>
                        <button className="text-button" onClick={openDemo}>
                          Посмотреть пример результата
                          <Icon name="arrow" size={16} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div
                        className={`result-summary ${demoVerdict === "no_violation" ? "success-summary" : ""}`}
                      >
                        <span className="warning-icon">
                          {demoVerdict === "violation" ? (
                            "!"
                          ) : (
                            <Icon name="check" size={16} />
                          )}
                        </span>
                        <div>
                          <strong>
                            {demoVerdict === "violation"
                              ? "Обнаружены признаки возможных нарушений"
                              : "Нарушение не обнаружено"}
                          </strong>
                          <p>
                            {demoVerdict === "violation"
                              ? "2 демонстрационных события требуют внимания"
                              : "Демонстрационный результат без событий"}
                          </p>
                        </div>
                        <span className="event-count">
                          {demoVerdict === "violation" ? "02" : "00"}
                        </span>
                      </div>
                      <div
                        className="result-tabs"
                        role="tablist"
                        aria-label="Результаты"
                        onKeyDown={(e) => {
                          if (
                            ![
                              "ArrowLeft",
                              "ArrowRight",
                              "Home",
                              "End",
                            ].includes(e.key)
                          )
                            return;
                          e.preventDefault();
                          const next =
                            e.key === "Home"
                              ? "events"
                              : e.key === "End"
                                ? "about"
                                : tab === "events"
                                  ? "about"
                                  : "events";
                          setTab(next);
                          document.getElementById(`${next}-tab`)?.focus();
                        }}
                      >
                        <button
                          id="events-tab"
                          aria-controls="events-panel"
                          role="tab"
                          aria-selected={tab === "events"}
                          tabIndex={tab === "events" ? 0 : -1}
                          className={tab === "events" ? "selected" : ""}
                          onClick={() => setTab("events")}
                        >
                          События<span>{visibleFindings.length}</span>
                        </button>
                        <button
                          id="about-tab"
                          aria-controls="about-panel"
                          role="tab"
                          aria-selected={tab === "about"}
                          tabIndex={tab === "about" ? 0 : -1}
                          className={tab === "about" ? "selected" : ""}
                          onClick={() => setTab("about")}
                        >
                          О проверке
                        </button>
                        <span className="tabs-helper">
                          <Icon name="clock" size={13} />
                          Таймкоды кликабельны
                        </span>
                      </div>
                      {tab === "events" ? (
                        <div
                          className="findings"
                          id="events-panel"
                          role="tabpanel"
                          aria-labelledby="events-tab"
                        >
                          {visibleFindings.length === 0 && (
                            <div className="empty-result">
                              <span className="empty-check">
                                <Icon name="shield" size={26} />
                              </span>
                              <h3>Нет событий для проверки</h3>
                              <p>
                                В этом демосценарии признаки возможных нарушений
                                не обнаружены.
                              </p>
                            </div>
                          )}
                          {visibleFindings.map((f) => (
                            <article
                              className={`finding ${selected === f.id ? "expanded" : ""}`}
                              key={f.id}
                            >
                              <button
                                className="finding-header"
                                onClick={() => selectFinding(f.id)}
                                aria-expanded={selected === f.id}
                              >
                                <span className="finding-index">0{f.id}</span>
                                <span className="finding-heading">
                                  <strong>{f.title}</strong>
                                  <span>Возможное нарушение · демопример</span>
                                </span>
                                <span className="time-badge">
                                  <Icon name="play" size={11} />
                                  {formatTime(f.time)}
                                </span>
                                <Icon name="chevron" size={16} />
                              </button>
                              {selected === f.id && (
                                <div className="finding-details">
                                  <div className="evidence-thumb">
                                    <DemoScene time={f.time} />
                                    <span>
                                      <Icon name="eye" size={11} />
                                      Иллюстрация события
                                    </span>
                                  </div>
                                  <div>
                                    <span className="detail-label">
                                      ЧТО ВИДНО
                                    </span>
                                    <p>{f.observation}</p>
                                    <span className="detail-label">
                                      ОБОСНОВАНИЕ
                                    </span>
                                    <p>{f.explanation}</p>
                                    <div className="source-note">
                                      <Icon name="file" size={14} />
                                      <span>
                                        Нормативный источник: не подключён в
                                        демо
                                      </span>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </article>
                          ))}
                        </div>
                      ) : (
                        <div
                          className="about-result"
                          id="about-panel"
                          role="tabpanel"
                          aria-labelledby="about-tab"
                        >
                          <Icon name="shield" size={25} />
                          <h3>Прозрачная проверка</h3>
                          <p>
                            Это демонстрация интерфейса. События заданы заранее
                            и не являются результатом анализа видео. Кадры
                            показаны в виде иллюстраций. Нормативные источники
                            ещё не подключены.
                          </p>
                          <p>
                            Видеозаписи не отправляются во внешние сервисы.
                            Серверная часть и AI-модель не подключены.
                          </p>
                          <div className="clean-example">
                            <Icon name="check" size={17} />
                            <div>
                              <strong>Нарушение не обнаружено</strong>
                              <p>
                                Пример второго возможного вердикта. При таком
                                результате список событий будет пуст.
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </section>
              </div>
            </>
          )}
          <footer className="page-footer">
            <span>
              Forte Vision<span className="footer-divider">/</span>Внимание к
              деталям. Уверенность в решениях.
            </span>
            <span>
              Прототип для Datathon 2026
              <span className="footer-dot" />
              v0.1
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
