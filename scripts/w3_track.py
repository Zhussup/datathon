"""W3.1: простой IoU-трекер людей между кадрами (без supervision.ByteTrack).

Использует детекции person из внешней модели (COCO-веса rfdetr) и сопоставляет
боксы между кадрами по IoU. На выходе — треки {track_id: [(t, xyxy), ...]}.

Это замена supervision.ByteTrack, потому что в sv 0.31 трекер переехал в
отдельный пакет (supervision-track), который не установлен. На нашем 1-fps
видео простой IoU-матчинг работает так же хорошо: кадры раз в секунду,
люди между кадрами не успевают «телепортироваться».
"""
from __future__ import annotations


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a; bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def track(detections_by_t: dict[float, list[tuple[float, float, float, float]]],
          iou_threshold: float = 0.3, max_gap: int = 2) -> dict[int, list[tuple[float, tuple]]]:
    """detections_by_t: {t: [box, ...]} -> tracks: {id: [(t, box), ...]}.

    max_gap: сколько пустых кадров между детекциями можно простить.
    """
    tracks: dict[int, list[tuple[float, tuple]]] = {}
    next_id = 1
    last_seen: dict[int, float] = {}
    times = sorted(detections_by_t.keys())
    for t in times:
        boxes = detections_by_t[t]
        if not boxes:
            continue
        # матчим боксы с активными треками
        used = [False] * len(boxes)
        for tid, last_t in sorted(last_seen.items(), key=lambda kv: kv[1], reverse=True):
            if t - last_t > max_gap:
                continue
            last_box = tracks[tid][-1][1]
            best, best_iou = -1, 0.0
            for i, b in enumerate(boxes):
                if used[i]:
                    continue
                v = iou(last_box, b)
                if v > best_iou:
                    best_iou, best = v, i
            if best >= 0 and best_iou >= iou_threshold:
                tracks[tid].append((t, boxes[best]))
                used[best] = True
                last_seen[tid] = t
        # новые боксы → новые треки
        for i, b in enumerate(boxes):
            if not used[i]:
                tid = next_id; next_id += 1
                tracks[tid] = [(t, b)]
                last_seen[tid] = t
    return tracks
