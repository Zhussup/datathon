import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// Ввод/правка X-API-Key. Ключ хранится в localStorage("forte-api-key"); apiOptions()
// в api.ts уже умеет его читать — здесь только UI и валидация.
export function ApiKeyModal({
  open,
  initialValue,
  onClose,
  onSave,
}: {
  open: boolean;
  initialValue: string;
  onClose: () => void;
  onSave: (key: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setValue(initialValue);
    setError("");
    inputRef.current?.focus();
  }, [open, initialValue]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "Enter") {
        event.preventDefault();
        submit();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, value]);

  if (!open) return null;

  const valid = value.trim().length > 0 && !/\s/.test(value);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Введите ключ.");
      return;
    }
    if (/\s/.test(trimmed)) {
      setError("Ключ не должен содержать пробелов.");
      return;
    }
    onSave(trimmed);
  }

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="api-modal-title"
      className="api-modal"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="api-modal-card">
        <h2 id="api-modal-title">API-ключ</h2>
        <p>
          Ключ доступа к сервису анализа. Хранится локально в этом браузере.
        </p>
        <input
          ref={inputRef}
          className="api-modal-input"
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            if (error) setError("");
          }}
          placeholder="forte-hack-2026"
          aria-label="API-ключ"
        />
        {error && (
          <p className="api-modal-error" role="alert">
            {error}
          </p>
        )}
        <div className="api-modal-actions">
          <button type="button" onClick={onClose}>
            Отмена
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!valid}
            aria-label="Сохранить ключ"
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
