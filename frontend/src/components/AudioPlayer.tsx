import { useEffect, useRef, useState } from "react";
import { mediaUrl } from "../api";

// Coordinate all AudioPlayer instances so only one plays at a time
let activeAudioElement: HTMLAudioElement | null = null;

export interface AudioPlayerProps {
  mediaPath?: string | null;
  blobUrl?: string | null;
  title?: string;
  downloadFilename?: string;
  onStatusChange?: (status: string) => void;
}

export default function AudioPlayer({
  mediaPath,
  blobUrl,
  title = "Audio playback",
  downloadFilename = "caninesense-audio.wav",
  onStatusChange,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [resolvedUrl, setResolvedUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "playing" | "paused" | "stopped" | "ended" | "error">("idle");
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [reloadTick, setReloadTick] = useState(0);

  function updateStatus(next: typeof status) {
    setStatus(next);
    onStatusChange?.(next);
  }

  useEffect(() => {
    let cancelled = false;
    let createdObjectUrl: string | null = null;

    // Stop any current playback on source change
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setCurrentTime(0);
    setDuration(0);
    setError("");

    if (blobUrl) {
      setResolvedUrl(blobUrl);
      setLoading(false);
      updateStatus("ready");
      return () => {
        if (audioRef.current) {
          audioRef.current.pause();
        }
      };
    }

    if (!mediaPath) {
      setResolvedUrl(null);
      setLoading(false);
      updateStatus("idle");
      return;
    }

    setLoading(true);
    updateStatus("loading");

    mediaUrl(mediaPath)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        createdObjectUrl = url;
        setResolvedUrl(url);
        setLoading(false);
        updateStatus("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        setResolvedUrl(null);
        setLoading(false);
        setError(err instanceof Error ? err.message : "Could not load audio media");
        updateStatus("error");
      });

    return () => {
      cancelled = true;
      if (audioRef.current) {
        if (activeAudioElement === audioRef.current) {
          activeAudioElement = null;
        }
        audioRef.current.pause();
      }
      if (createdObjectUrl) {
        URL.revokeObjectURL(createdObjectUrl);
      }
    };
  }, [mediaPath, blobUrl, reloadTick]);

  function handlePlay() {
    const el = audioRef.current;
    if (!el || !resolvedUrl) return;
    if (activeAudioElement && activeAudioElement !== el) {
      activeAudioElement.pause();
    }
    activeAudioElement = el;
    el.play()
      .then(() => updateStatus("playing"))
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Playback blocked by browser");
        updateStatus("error");
      });
  }

  function handlePause() {
    const el = audioRef.current;
    if (!el) return;
    el.pause();
    updateStatus("paused");
  }

  function handleStop() {
    const el = audioRef.current;
    if (!el) return;
    el.pause();
    el.currentTime = 0;
    setCurrentTime(0);
    updateStatus("stopped");
  }

  function handleReplay() {
    const el = audioRef.current;
    if (!el || !resolvedUrl) return;
    if (activeAudioElement && activeAudioElement !== el) {
      activeAudioElement.pause();
    }
    activeAudioElement = el;
    el.currentTime = 0;
    setCurrentTime(0);
    el.play()
      .then(() => updateStatus("playing"))
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Playback failed");
        updateStatus("error");
      });
  }

  function handleSeek(nextTime: number) {
    const el = audioRef.current;
    if (!el || !Number.isFinite(nextTime)) return;
    el.currentTime = nextTime;
    setCurrentTime(nextTime);
  }

  function handleDownload() {
    if (!resolvedUrl) return;
    const a = document.createElement("a");
    a.href = resolvedUrl;
    a.download = downloadFilename;
    a.click();
  }

  function fmtTime(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) return "0:00.0";
    const mins = Math.floor(sec / 60);
    const rem = sec - mins * 60;
    return `${mins}:${rem < 10 ? "0" : ""}${rem.toFixed(1)}`;
  }

  const badgeClass =
    status === "playing"
      ? "badge ok"
      : status === "error"
        ? "badge bad"
        : status === "loading"
          ? "badge warn"
          : "badge";

  return (
    <div
      className="audio-player-box"
      style={{
        border: "1px solid var(--line)",
        borderRadius: 14,
        padding: "12px 14px",
        background: "#fbf6ee",
        marginTop: 10,
      }}
    >
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <strong style={{ fontSize: "0.88rem" }}>{title}</strong>
        <span className={badgeClass} data-testid="audio-player-status">
          {status === "loading"
            ? "Loading media…"
            : status === "playing"
              ? "Playing"
              : status === "paused"
                ? "Paused"
                : status === "stopped"
                  ? "Stopped"
                  : status === "ended"
                    ? "Finished"
                    : status === "error"
                      ? "Media error"
                      : status === "ready"
                        ? "Ready"
                        : "Idle"}
        </span>
      </div>

      {error && (
        <div className="error" style={{ marginBottom: 8 }}>
          <div>{error}</div>
          <button
            className="btn ghost"
            type="button"
            style={{ marginTop: 6, padding: "5px 12px", fontSize: "0.8rem" }}
            onClick={() => setReloadTick((t) => t + 1)}
          >
            Retry loading audio
          </button>
        </div>
      )}

      <audio
        ref={audioRef}
        src={resolvedUrl || undefined}
        preload="metadata"
        onLoadedMetadata={(e) => {
          const d = e.currentTarget.duration;
          if (Number.isFinite(d) && d > 0) setDuration(d);
        }}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
        onPlay={() => updateStatus("playing")}
        onPause={() => {
          if (audioRef.current && audioRef.current.currentTime > 0 && !audioRef.current.ended) {
            updateStatus("paused");
          }
        }}
        onEnded={() => updateStatus("ended")}
        onError={() => {
          if (resolvedUrl) {
            setError("Audio stream could not be decoded by the browser.");
            updateStatus("error");
          }
        }}
        style={{ display: "none" }}
      />

      <div className="row" style={{ gap: 8, alignItems: "center" }}>
        {status === "playing" ? (
          <button
            className="btn accent"
            type="button"
            onClick={handlePause}
            disabled={!resolvedUrl || loading}
            style={{ padding: "6px 14px", fontSize: "0.84rem" }}
          >
            Pause
          </button>
        ) : (
          <button
            className="btn accent"
            type="button"
            onClick={handlePlay}
            disabled={!resolvedUrl || loading}
            style={{ padding: "6px 14px", fontSize: "0.84rem" }}
          >
            {status === "paused" ? "Resume" : "Play"}
          </button>
        )}

        <button
          className="btn ghost"
          type="button"
          onClick={handleStop}
          disabled={!resolvedUrl || loading || (status !== "playing" && status !== "paused" && currentTime === 0)}
          style={{ padding: "6px 12px", fontSize: "0.84rem" }}
        >
          Stop
        </button>

        <button
          className="btn ghost"
          type="button"
          onClick={handleReplay}
          disabled={!resolvedUrl || loading}
          style={{ padding: "6px 12px", fontSize: "0.84rem" }}
        >
          Replay
        </button>

        <div style={{ flex: 1, minWidth: 130, display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="range"
            min={0}
            max={duration > 0 ? duration : 1}
            step={0.01}
            value={Math.min(currentTime, duration || 1)}
            onChange={(e) => handleSeek(Number(e.target.value))}
            disabled={!resolvedUrl || loading || duration <= 0}
            aria-label="Audio playback progress"
            style={{ flex: 1, accentColor: "var(--accent)" }}
          />
          <span className="tiny" style={{ whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>
            {fmtTime(currentTime)} / {fmtTime(duration)}
          </span>
        </div>

        <button
          className="btn ghost"
          type="button"
          onClick={handleDownload}
          disabled={!resolvedUrl || loading}
          style={{ padding: "6px 12px", fontSize: "0.82rem" }}
        >
          Download WAV
        </button>
      </div>
    </div>
  );
}
