import { useEffect, useRef, useState } from "react";
import type { DragEvent } from "react";
import { Icon } from "./Icon";
import { LoadingMark } from "./LoadingMark";
import { DemoVerdict } from "./DemoVerdict";
import { Verdict } from "./Verdict";
import { formatTime, validateVideo } from "./video";
import { finishTransition, transition } from "./motion";
import { apiOptions, awaitJob, uploadForAnalysis } from "./api";
import type { ApiOptions, Job, JobResult } from "./api";

type Stage =
  | "idle"
  | "opening"
  | "upload-finishing"
  | "uploaded"
  | "checking-intro"
  | "checking"
  | "check-finishing"
  | "ready"
  | "error";
type Theme = "light" | "dark";
type ApiState = "off" | "pending" | "live";

const statusCopy = {
  opening: {
    label: "ШАГ 01 / ЗАГРУЗКА",
    title: ["Открываем", "ваше видео."],
    description: "Подготавливаем запись для просмотра.",
  },
  uploaded: {
    label: "ВИДЕО ЗАГРУЖЕНО",
    title: ["Видео загружено.", "Можно начинать."],
    description: "Запись открыта. Сейчас перейдём к проверке.",
  },
  checking: {
    label: "ШАГ 02 / ИИ · ДЕМО",
    title: ["Проверяем", "видеозапись."],
    description: "Демонстрация анализа. Пока можно посмотреть запись слева.",
  },
  error: {
    label: "НЕ УДАЛОСЬ ОТКРЫТЬ",
    title: ["Попробуем", "другое видео?"],
    description:
      "Не получилось прочитать запись. Выберите MP4 с кодеком H.264.",
  },
  ready: {
    label: "ШАГ 03 / ДЕМО-ВЕРДИКТ",
    title: ["Проверка завершена.", "Вердикт готов."],
    description:
      "Пример результата — ниже. Откройте отмеченный фрагмент для просмотра.",
  },
} as const;

// Для реального запуска описания шагов другие: не демо, а локальный анализ.
const liveStageCopy = {
  checking: {
    label: "ШАГ 02 / ИИ · АНАЛИЗ",
    description: "Локальный анализ записи. Пока можно посмотреть запись слева.",
  },
  ready: {
    label: "ШАГ 03 / ВЕРДИКТ",
    description: "Анализ завершён. Откройте отмеченный фрагмент для просмотра.",
  },
} as const;

export default function App() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [videoError, setVideoError] = useState(false);
  const [prepared, setPrepared] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [duration, setDuration] = useState(0);
  const [apiState, setApiState] = useState<ApiState>("off");
  const [jobId, setJobId] = useState("");
  const [result, setResult] = useState<JobResult | null>(null);
  const [failReason, setFailReason] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const openingStarted = useRef(0);
  const uploadEpoch = useRef(0);
  const pollAbort = useRef<AbortController | null>(null);
  const split =
    stage === "checking" ||
    stage === "check-finishing" ||
    stage === "ready" ||
    stage === "error";
  const copyStage =
    stage === "checking-intro" || stage === "check-finishing"
      ? "checking"
      : stage === "upload-finishing"
        ? "opening"
        : stage;
  const busy =
    stage === "opening" || stage === "checking-intro" || stage === "checking";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "dark" ? "#151515" : "#f8f7f5");
    try {
      localStorage.setItem("forte-theme", theme);
    } catch {
      /* Theme still works if storage is disabled. */
    }
  }, [theme]);

  useEffect(() => {
    if (!file) {
      setUrl("");
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  useEffect(() => {
    if (stage !== "opening" &&
      stage !== "uploaded" &&
      stage !== "checking-intro" &&
      stage !== "checking"
    )
      return;
    if (stage === "opening" && !prepared) return;
    // Реальная проверка не ограничена демо-таймером — ждём ответ воркера.
    if (stage === "checking" && apiState !== "off") return;
    // Only the checking phase is a demo; opening waits for a decoded frame.
    const timer = window.setTimeout(
      () =>
        transition(() =>
          setStage(
            stage === "opening"
              ? videoError
                ? "error"
                : "upload-finishing"
              : stage === "uploaded"
                ? videoError
                  ? "error"
                  : "checking-intro"
                : stage === "checking-intro"
                  ? videoError
                    ? "error"
                    : "checking"
                  : "check-finishing",
          ),
        ),
      stage === "opening"
        ? Math.max(0, 800 - (performance.now() - openingStarted.current))
        : stage === "uploaded"
          ? 1300
          : stage === "checking-intro"
            ? 560
            : 4200,
    );
    return () => window.clearTimeout(timer);
  }, [stage, file, prepared, videoError, apiState]);

  useEffect(() => {
    if (stage !== "opening") return;
    const timer = window.setTimeout(() => {
      transition(() => {
        setVideoError(true);
        setStage("error");
      });
    }, 20000);
    return () => window.clearTimeout(timer);
  }, [stage, file]);

  function chooseFile(next?: File) {
    if (!next) return;
    const message = validateVideo(next);
    setError(message);
    if (message) return;
    openingStarted.current = performance.now();
    const opts = apiOptions();
    transition(() => {
      setFile(next);
      setStage("opening");
      setVideoError(false);
      setPrepared(false);
      setDuration(0);
      setJobId("");
      setResult(null);
      setFailReason("");
      setApiState(opts ? "pending" : "off");
    });
    if (opts) void startUpload(next, opts);
  }

  // Файл уходит в локальный сервис сразу при выборе; пока он едет, интерфейс
  // живёт своей хореографией. Если сервис недоступен — тихо переходим в демо.
  async function startUpload(uploading: File, opts: ApiOptions) {
    const epoch = uploadEpoch.current;
    try {
      const id = await uploadForAnalysis(uploading, opts);
      if (uploadEpoch.current !== epoch) return;
      setJobId(id);
      setApiState("live");
    } catch {
      if (uploadEpoch.current !== epoch) return;
      setApiState("off");
    }
  }

  useEffect(() => {
    if (stage !== "checking" || apiState !== "live" || !jobId) return;
    const opts = apiOptions();
    if (!opts) return;
    const controller = new AbortController();
    pollAbort.current = controller;
    let cancelled = false;
    awaitJob(jobId, opts, controller.signal)
      .then((job: Job) => {
        if (cancelled) return;
        if (job.status === "done" && job.verdict) {
          setResult({ verdict: job.verdict, violations: job.violations ?? [] });
          transition(() => setStage("check-finishing"));
        } else {
          transition(() => {
            setFailReason(job.error || "Проверка не удалась.");
            setStage("error");
          });
        }
      })
      .catch((caught: unknown) => {
        const reason = caught instanceof Error ? caught : undefined;
        if (cancelled || reason?.name === "AbortError") return;
        transition(() => {
          setFailReason(reason?.message || "Сервис недоступен.");
          setStage("error");
        });
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [stage, apiState, jobId]);

  function openPicker() {
    finishTransition();
    input.current?.click();
  }

  function reset() {
    transition(() => {
      uploadEpoch.current += 1;
      pollAbort.current?.abort();
      setFile(null);
      setStage("idle");
      setError("");
      setVideoError(false);
      setPrepared(false);
      setDuration(0);
      setJobId("");
      setResult(null);
      setFailReason("");
      setApiState("off");
    });
  }

  // Тексты этапов: при ошибке обработки показываем причину, при живом анализе — не демо.
  function stageText(stageName: string, field: "label" | "description", fallback: string) {
    if (stageName === "error" && failReason) return failReason;
    return liveStageCopy[stageName as keyof typeof liveStageCopy]?.[field] ?? fallback;
  }

  function seekTo(seconds: number) {
    if (!video.current) return;
    video.current.currentTime = seconds;
    video.current.scrollIntoView({
      block: "center",
      behavior: matchMedia("(prefers-reduced-motion: reduce)")
        .matches
        ? "instant"
        : "smooth",
    });
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length > 1) {
      setError("Загрузите одно видео за раз.");
      return;
    }
    chooseFile(event.dataTransfer.files[0]);
  }

  return (
    <div
      className={`app ${split ? "app-split" : ""} ${dragging ? "is-dragging" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        if (event.dataTransfer.types.includes("Files")) setDragging(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setDragging(false);
      }}
      onDrop={drop}
    >
      <header className="site-header">
        <button
          className="wordmark"
          onClick={reset}
          aria-label="Forte Vision — на главную"
        >
          forte<span className="brand-dot">.</span>
          <span className="wordmark-divider" />
          <span className="wordmark-product">vision</span>
        </button>
        <div className="header-right">
          <span className="header-caption">Увидеть больше.</span>
          <div
            className="theme-switch"
            role="group"
            aria-label="Тема оформления"
          >
            <button
              aria-label="Светлая тема"
              aria-pressed={theme === "light"}
              onClick={() => setTheme("light")}
            >
              <Icon name="sun" size={18} />
            </button>
            <button
              aria-label="Тёмная тема"
              aria-pressed={theme === "dark"}
              onClick={() => setTheme("dark")}
            >
              <Icon name="moon" size={18} />
            </button>
          </div>
        </div>
      </header>

      <input
        ref={input}
        className="visually-hidden"
        type="file"
        accept=".mov,.mp4,video/quicktime,video/mp4"
        aria-label="Выбрать видеофайл"
        tabIndex={-1}
        onChange={(event) => {
          chooseFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />

      <main className={`main-content ${stage !== "idle" ? "has-video" : ""}`}>
        {stage === "idle" ? (
          <section className="intro" aria-labelledby="intro-title">
            <span className="eyebrow">
              <span className="status-dot" />
              ВИДЕОАНАЛИТИКА КАССОВЫХ ОПЕРАЦИЙ
            </span>
            <h1 id="intro-title">
              <span className="hero-line">
                <span>
                  Внимание к <em>деталям.</em>
                </span>
              </span>
              <span className="hero-line">
                <span>Уверенность в решениях.</span>
              </span>
            </h1>
            <p className="intro-description">
              Загрузите видео. Всё важное — в фокусе.
            </p>
            <button className="upload-button" onClick={openPicker}>
              <Icon name="upload" size={23} />
              <span>Загрузить видео</span>
              <Icon name="arrow" size={23} />
            </button>
            <p className="file-hint">
              или перетащите файл сюда
              <span />
              MOV, MP4 · до 200 МБ
            </p>
            {error && (
              <p className="error-message" role="alert">
                <Icon name="info" size={16} />
                {error}
              </p>
            )}
            <span className="intro-index" aria-hidden="true">
              01 — 03
            </span>
          </section>
        ) : (
          <section
            className={`review ${split ? "is-split" : ""}`}
            aria-label="Проверка видеозаписи"
          >
            <div className="review-toolbar" aria-hidden={!split} inert={!split}>
              <div className="review-title">
                <span className="eyebrow">ВАША ЗАПИСЬ</span>
                <h1 title={file?.name}>{file?.name}</h1>
              </div>
              <button className="secondary-button" onClick={openPicker}>
                <Icon name="upload" size={17} />
                Другое видео
              </button>
            </div>
            <div className="review-body">
              <div className="video-column" aria-hidden={!split} inert={!split}>
                <div className="video-frame">
                  <video
                    ref={video}
                    key={url}
                    src={url || undefined}
                    controls={!videoError}
                    aria-label="Просмотр выбранного видео"
                    aria-hidden={videoError}
                    playsInline
                    preload="auto"
                    onLoadedMetadata={(event) => {
                      setDuration(
                        Number.isFinite(event.currentTarget.duration)
                          ? event.currentTarget.duration
                          : 0,
                      );
                    }}
                    onLoadedData={() => setPrepared(true)}
                    onError={() => {
                      setVideoError(true);
                      setPrepared(true);
                      if (stage !== "opening")
                        transition(() => setStage("error"));
                    }}
                  />
                  {videoError && (
                    <div className="video-fallback">
                      <Icon name="film" size={38} />
                      <h2>Не удалось открыть видео</h2>
                      <p>
                        Этот кодек не поддерживается браузером.
                        <br />
                        Попробуйте MP4 с кодеком H.264.
                      </p>
                      <button className="secondary-button" onClick={openPicker}>
                        Выбрать другое видео
                        <Icon name="arrow" size={16} />
                      </button>
                    </div>
                  )}
                </div>
                <div className="video-caption">
                  <span>
                    <span className="status-dot" />
                    Локальный просмотр
                  </span>
                  <span>
                    {file && `${(file.size / 1024 / 1024).toFixed(1)} МБ`}
                    {duration > 0 && ` / ${formatTime(duration)}`}
                  </span>
                </div>
                <p className="video-note">
                  <Icon name="shield" size={14} />
                  Ваша запись остаётся в этом браузере.
                </p>
              </div>

              <div
                data-result={stage === "ready"}
                className={`status-panel ${stage === "ready" || stage === "uploaded" ? "status-ready" : ""} ${stage === "error" ? "status-error" : ""}`}
                role="status"
                aria-live="polite"
              >
                <div
                  className="status-progress"
                  aria-hidden={stage === "ready"}
                  inert={stage === "ready"}
                >
                  <div
                    className="status-visual"
                    data-complete={
                      stage === "ready" ||
                      stage === "uploaded" ||
                      stage === "error"
                    }
                  >
                    <LoadingMark
                      busy={busy}
                      onComplete={() => {
                        if (stage === "upload-finishing")
                          transition(() => setStage("uploaded"));
                        if (stage === "check-finishing")
                          transition(() => setStage("ready"));
                      }}
                    />
                    <span
                      className="ready-mark"
                      data-active={stage === "error"}
                      aria-hidden="true"
                    >
                      <Icon name="info" size={29} />
                    </span>
                  </div>
                  <div className="status-copy">
                    {Object.entries(statusCopy).map(([textStage, copy]) => (
                      <div
                        key={textStage}
                        className="status-copy-layer"
                        data-stage={textStage}
                        data-active={textStage === copyStage}
                        aria-hidden={textStage !== copyStage}
                      >
                        <span className="eyebrow">
                          {stageText(textStage, "label", copy.label)}
                        </span>
                        <h2>
                          {copy.title[0]}
                          <br />
                          <span>{copy.title[1]}</span>
                        </h2>
                        <p className="status-description">
                          {stageText(textStage, "description", copy.description)}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div
                    className={`loading-track ${stage === "upload-finishing" || stage === "check-finishing" ? "is-finishing" : ""} ${stage === "ready" || stage === "uploaded" ? "is-complete" : ""} ${stage === "error" ? "is-failed" : ""}`}
                    aria-hidden="true"
                  >
                    <span />
                  </div>
                  <div
                    className="status-details"
                    data-expanded={split && stage !== "error"}
                  >
                    <p
                      className="opening-file"
                      title={file?.name}
                      aria-hidden={split}
                    >
                      {file?.name}
                    </p>
                    <div
                      className="review-steps"
                      aria-hidden={!split || stage === "error"}
                    >
                      <div className="done">
                        <Icon name="check" size={15} />
                        <span>Видео загружено</span>
                      </div>
                      <div
                        className="status-step"
                        data-done={stage === "ready"}
                      >
                        <span className="status-step-icon" aria-hidden="true">
                          <LoadingMark
                            busy={
                              stage === "checking-intro" || stage === "checking"
                            }
                            small
                          />
                        </span>
                        <span className="status-swap">
                          <span
                            data-active={stage !== "ready"}
                            aria-hidden={stage === "ready"}
                          >
                            Проверяем операции
                          </span>
                          <span
                            data-active={stage === "ready"}
                            aria-hidden={stage !== "ready"}
                          >
                            Анализ завершён
                          </span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <button className="cancel-button status-swap" onClick={reset}>
                    <span
                      data-active={stage !== "ready" && stage !== "error"}
                      aria-hidden={stage === "ready" || stage === "error"}
                    >
                      Отменить <Icon name="close" size={15} />
                    </span>
                    <span
                      data-active={stage === "ready" || stage === "error"}
                      aria-hidden={stage !== "ready" && stage !== "error"}
                    >
                      Начать заново
                      <Icon name="arrow" size={15} />
                    </span>
                  </button>
                </div>
                {result ? (
                  <Verdict
                    key={url}
                    visible={stage === "ready"}
                    result={result}
                    onReset={reset}
                    onSeek={seekTo}
                  />
                ) : (
                  <DemoVerdict
                    key={url}
                    visible={stage === "ready"}
                    duration={duration}
                    onReset={reset}
                    onSeek={seekTo}
                  />
                )}
              </div>
            </div>
            {error && (
              <p className="error-message review-error" role="alert">
                <Icon name="info" size={16} />
                {error}
              </p>
            )}
          </section>
        )}
      </main>

      <footer className="site-footer">
        <span className="footer-privacy">
          <Icon name="shield" size={15} />
          Локально. Конфиденциально.
        </span>
        <span className="footer-demo">
          <span className="status-dot" />
          {result ? "Локальный анализ записи" : "Демонстрация интерфейса"}
        </span>
        <span className="footer-edition">
          FORTE VISION<span>2026</span>
        </span>
      </footer>
      {dragging && (
        <div className="drop-overlay">
          <Icon name="upload" size={44} />
          <span>Отпустите видео здесь</span>
          <p>MOV, MP4 · до 200 МБ</p>
        </div>
      )}
    </div>
  );
}
