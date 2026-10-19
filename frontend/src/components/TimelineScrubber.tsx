import { useCallback, useEffect, useRef } from "react";
import type { TimelineMarker } from "../types";

interface Props {
  min: number;
  max: number;
  value: number;
  markers: TimelineMarker[];
  onChange: (minute: number) => void;
}

/**
 * Time scrubber: a track with per-minute markers (Goal / Stoppage)
 * and a draggable handle. Clicking, dragging, or using arrow keys
 * moves the current minute and re-renders the summary.
 */
export function TimelineScrubber({ min, max, value, markers, onChange }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const pct = (minute: number) => {
    if (max <= min) return 0;
    return ((minute - min) / (max - min)) * 100;
  };

  const minuteFromClientX = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return value;
      const rect = track.getBoundingClientRect();
      const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      return Math.round(min + ratio * (max - min));
    },
    [min, max, value],
  );

  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!draggingRef.current) return;
      onChange(minuteFromClientX(e.clientX));
    }
    function onUp() {
      draggingRef.current = false;
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [minuteFromClientX, onChange]);

  const startDrag = (e: React.PointerEvent) => {
    draggingRef.current = true;
    onChange(minuteFromClientX(e.clientX));
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") onChange(Math.max(min, value - 1));
    else if (e.key === "ArrowRight") onChange(Math.min(max, value + 1));
    else if (e.key === "Home") onChange(min);
    else if (e.key === "End") onChange(max);
    else return;
    e.preventDefault();
  };

  return (
    <div className="scrubber" aria-label="Match minute scrubber">
      <div
        ref={trackRef}
        className="scrubber__track"
        role="slider"
        tabIndex={0}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={`${value} minutes`}
        aria-label="Scrub to a minute of the match"
        onPointerDown={startDrag}
        onKeyDown={onKeyDown}
      >
        <div className="scrubber__rail" />
        <div
          className="scrubber__fill"
          style={{ width: `${Math.max(pct(value), 1)}%` }}
        />

        {markers.map((m) => (
          <button
            key={`${m.kind}-${m.minute}`}
            type="button"
            className={`scrubber__marker scrubber__marker--${m.kind}`}
            style={{ left: `${pct(m.minute)}%` }}
            title={`Minute ${m.minute} — ${m.kind === "goal" ? "Goal" : "Stoppage"}`}
            aria-label={`Jump to minute ${m.minute}: ${m.kind === "goal" ? "Goal" : "Stoppage"}`}
            onPointerDown={(e) => {
              e.stopPropagation();
              draggingRef.current = false;
              onChange(m.minute);
            }}
          />
        ))}

        <div
          className="scrubber__handle"
          style={{ left: `${pct(value)}%` }}
        />
      </div>

      <div className="scrubber__minmax">
        <span>0'</span>
        <span>{max}'</span>
      </div>

      <div className="scrubber__legend">
        <span className="item">
          <span className="swatch swatch--goal" /> Goal
        </span>
        <span className="item">
          <span className="swatch swatch--stoppage" /> Stoppage
        </span>
      </div>
    </div>
  );
}
