import { useEffect, useRef, useState } from "react";
import { mediaUrl } from "../api";

// Coordinator for all AudioPlayer instances so only one plays at a time
interface AudioCoordinatorEntry {
  id: string;
  element: HTMLAudioElement;
  onExternalPause: () => void;
  onExternalStop: () => void;
}

const activeAudioEntries = new Map<string, AudioCoordinatorEntry>();
type PlaybackStateListener = (isPlaying: boolean) => void;
const playbackListeners = new Set<PlaybackStateListener>();

function notifyPlaybackState() {
  const isPlaying = Array.from(activeAudioEntries.values()).some(
    (entry) => !entry.element.paused && !entry.element.ended && entry.element.currentTime > 0
  );
  playbackListeners.forEach((fn) => {
    try {
      fn(isPlaying);
    } catch {
      /* ignore */
    }
  });
}

export function subscribeAudioPlayback(listener: PlaybackStateListener): () => void {
  playbackListeners.add(listener);
  return () => {
    playbackListeners.delete(listener);
  };
}

export function pauseAllOtherAudio(currentId: string) {
  activeAudioEntries.forEach((entry, id) => {
    if (id !== currentId) {
      try {
        entry.onExternalPause();
      } catch {
        /* ignore */
      }
    }
  });
  notifyPlaybackState();
}

export function stopAllActiveAudio() {
  activeAudioEntries.forEach((entry) => {
    try {
      entry.onExternalStop();
    } catch {
      /* ignore */
    }
  });
  if (typeof document !== "undefined") {
    document.querySelectorAll("audio, video").forEach((media) => {
      try {
        const el = media as HTMLMediaElement;
        el.pause();
        el.currentTime = 0;
      } catch {
        /* ignore */
      }
    });
  }
  notifyPlaybackState();
}

export interface AudioPlayerProps {
  mediaPath?: string | null;
  blobUrl?: string | null;
  title?: string;
  downloadFilename?: string;
  disabled?: boolean;
  onStatusChange?: (status: string) => void;
}

export default function AudioPlayer({
  mediaPath,
  blobUrl,
  title = "Audio playback",
  downloadFilename = "caninesense-audio.wav",
  disabled = false,
  onStatusChange,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playerId = useRef<string>(Math.random().toString(36).substring(2, 9));
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
    const el = audioRef.current;
    if (!el) return;

    const entry: AudioCoordinatorEntry = {
      id: playerId.current,
      element: el,
      onExternalPause: () => {
        if (!el.paused) {
          el.pause();
          updateStatus("paused");
        }
      },
      onExternalStop: () => {
        el.pause();
        el.currentTime = 0;
        setCurrentTime(0);
        updateStatus("stopped");
      },
    };

    activeAudioEntries.set(playerId.current, entry);
    return () => {
      activeAudioEntries.delete(playerId.current);
      notifyPlaybackState();
    };
  }, [resolvedUrl]);

  useEffect(() => {
    if (disabled && status === "playing" && audioRef.current) {
      audioRef.current.pause();
      updateStatus("paused");
      notifyPlaybackState();
    }
  }, [disabled, status]);

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
        notifyPlaybackState();
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
        audioRef.current.pause();
      }
      if (createdObjectUrl) {
        URL.revokeObjectURL(createdObjectUrl);
      }
      notifyPlaybackState();
    };
  }, [mediaPath, blobUrl, reloadTick]);

  function handlePlay() {
    const el = audioRef.current;
    if (!el || !resolvedUrl || disabled) return;
    pauseAllOtherAudio(playerId.current);
    el.play()
      .then(() => {
        updateStatus("playing");
        notifyPlaybackState();
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Playback blocked by browser");
        updateStatus("error");
        notifyPlaybackState();
      });
  }

  function handlePause() {
    const el = audioRef.current;
    if (!el) return;
    el.pause();
    updateStatus("paused");
    notifyPlaybackState();
  }

  function handleStop() {
    const el = audioRef.current;
    if (!el) return;
    el.pause();
    el.currentTime = 0;
    setCurrentTime(0);
    updateStatus("stopped");
    notifyPlaybackState();
  }

  function handleReplay() {
    const el = audioRef.current;
    if (!el || !resolvedUrl || disabled) return;
    pauseAllOtherAudio(playerId.current);
    el.currentTime = 0;
    setCurrentTime(0);
    el.play()
      .then(() => {
        updateStatus("playing");
        notifyPlaybackState();
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Playback failed");
        updateStatus("error");
        notifyPlaybackState();
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
        onPlay={() => {
          updateStatus("playing");
          pauseAllOtherAudio(playerId.current);
          notifyPlaybackState();
        }}
        onPause={() => {
          if (audioRef.current && audioRef.current.currentTime > 0 && !audioRef.current.ended) {
            updateStatus("paused");
          }
          notifyPlaybackState();
        }}
        onEnded={() => {
          updateStatus("ended");
          notifyPlaybackState();
        }}
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
            disabled={disabled || !resolvedUrl || loading}
            style={{ padding: "6px 14px", fontSize: "0.84rem" }}
          >
            Pause
          </button>
        ) : (
          <button
            className="btn accent"
            type="button"
            onClick={handlePlay}
            disabled={disabled || !resolvedUrl || loading}
            style={{ padding: "6px 14px", fontSize: "0.84rem" }}
          >
            {status === "paused" ? "Resume" : "Play"}
          </button>
        )}

        <button
          className="btn ghost"
          type="button"
          onClick={handleStop}
          disabled={disabled || !resolvedUrl || loading || (status !== "playing" && status !== "paused" && currentTime === 0)}
          style={{ padding: "6px 12px", fontSize: "0.84rem" }}
        >
          Stop
        </button>

        <button
          className="btn ghost"
          type="button"
          onClick={handleReplay}
          disabled={disabled || !resolvedUrl || loading}
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
            disabled={disabled || !resolvedUrl || loading || duration <= 0}
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
