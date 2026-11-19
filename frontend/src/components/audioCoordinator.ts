// Coordinator for all AudioPlayer instances so only one plays at a time.
export interface AudioCoordinatorEntry {
  id: string;
  element: HTMLAudioElement;
  onExternalPause: () => void;
  onExternalStop: () => void;
}

export const activeAudioEntries = new Map<string, AudioCoordinatorEntry>();
export type PlaybackStateListener = (isPlaying: boolean) => void;
const playbackListeners = new Set<PlaybackStateListener>();

export function notifyPlaybackState() {
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
