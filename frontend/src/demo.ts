export type Finding = {
  id: number;
  time: number;
  title: string;
  observation: string;
  explanation: string;
};
export const findings: Finding[] = [
  {
    id: 1,
    time: 44,
    title: "Наличные вне зоны контроля",
    observation:
      "На демонстрационной иллюстрации банкноты находятся на краю рабочей поверхности рядом с клиентской зоной.",
    explanation:
      "Здесь будет объяснение наблюдаемого действия и его связи с правилом. Иллюстрация не доказывает нарушение.",
  },
  {
    id: 2,
    time: 78,
    title: "Передача наличных",
    observation:
      "Пример события: передача наличных между участниками кассовой операции.",
    explanation:
      "Сам факт передачи не является нарушением. Для вывода нужны анализ последовательности действий и подтверждённое нормативное основание.",
  },
];
export const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
export function validateVideo(file: Pick<File, "name" | "size">) {
  if (!/\.(mov|mp4)$/i.test(file.name))
    return "Выберите видео в формате .mov или .mp4.";
  if (file.size === 0) return "Файл пуст. Выберите другую запись.";
  if (file.size > 200 * 1024 * 1024) return "Размер файла превышает 200 МБ.";
  return "";
}
