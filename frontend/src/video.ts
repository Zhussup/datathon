export const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;

export const demoTimestamp = (duration: number, position = 0.42) =>
  Number.isFinite(duration) && duration > 0 && Number.isFinite(position)
    ? duration * Math.min(0.99, Math.max(0, position))
    : 0;

export function validateVideo(file: Pick<File, "name" | "size">) {
  if (!/\.(mov|mp4)$/i.test(file.name))
    return "Выберите видео в формате .mov или .mp4.";
  if (file.size === 0) return "Файл пуст. Выберите другую запись.";
  if (file.size > 200 * 1024 * 1024) return "Размер файла превышает 200 МБ.";
  return "";
}
