import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { api, mediaUrl } from "../api";

export interface SpectrogramViewerProps {
  spectrogramDataPath?: string | null;
  spectrogramImagePath?: string | null;
  waveformPath?: string | null;
  title?: string;
  compact?: boolean;
}

function dbToRgb(db: number, minDb = -80, maxDb = 0): [number, number, number] {
  const norm = Math.max(0, Math.min(1, (db - minDb) / Math.max(1e-6, maxDb - minDb)));
  // CanineSense laboratory palette stops:
  // 0.00 -> #F7F3EC (247, 243, 236)
  // 0.30 -> #E8D5B5 (232, 213, 181)
  // 0.60 -> #C45C26 (196, 92, 38)
  // 0.82 -> #6B2B12 (107, 43, 18)
  // 1.00 -> #1C1917 (28, 25, 23)
  const stops: Array<[number, [number, number, number]]> = [
    [0.0, [247, 243, 236]],
    [0.3, [232, 213, 181]],
    [0.6, [196, 92, 38]],
    [0.82, [107, 43, 18]],
    [1.0, [28, 25, 23]],
  ];
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (norm >= t0 && norm <= t1) {
      const u = (norm - t0) / (t1 - t0);
      return [
        Math.round(c0[0] + u * (c1[0] - c0[0])),
        Math.round(c0[1] + u * (c1[1] - c0[1])),
        Math.round(c0[2] + u * (c1[2] - c0[2])),
      ];
    }
  }
  return [28, 25, 23];
}

export default function SpectrogramViewer({
  spectrogramDataPath,
  spectrogramImagePath,
  waveformPath,
  title = "Time–Frequency STFT Spectrogram",
  compact = false,
}: SpectrogramViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [specData, setSpecData] = useState<any>(null);
  const [waveUrl, setWaveUrl] = useState<string | null>(null);
  const [specImgUrl, setSpecImgUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [freqUnit, setFreqUnit] = useState<"Hz" | "kHz">("Hz");
  const [maxFreqHz, setMaxFreqHz] = useState<number>(8000);
  const [zoom, setZoom] = useState<number>(1);
  const [panRatio, setPanRatio] = useState<number>(0);
  const [viewMode, setViewMode] = useState<"interactive" | "image">("interactive");
  const [hoverInfo, setHoverInfo] = useState<{
    timeSec: number;
    freqHz: number;
    db: number;
    x: number;
    y: number;
  } | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let createdWave: string | null = null;
    let createdSpec: string | null = null;

    setSpecData(null);
    setWaveUrl(null);
    setSpecImgUrl(null);
    setError("");
    setHoverInfo(null);

    if (!spectrogramDataPath && !spectrogramImagePath && !waveformPath) {
      setLoading(false);
      return;
    }

    setLoading(true);
    const tasks: Promise<void>[] = [];

    if (spectrogramDataPath) {
      tasks.push(
        api<any>(spectrogramDataPath)
          .then((d) => {
            if (!cancelled) setSpecData(d);
          })
          .catch((e) => {
            if (!cancelled) setError(e instanceof Error ? e.message : "Could not load spectrogram data");
          })
      );
    }

    if (waveformPath) {
      tasks.push(
        mediaUrl(waveformPath)
          .then((u) => {
            if (cancelled) {
              URL.revokeObjectURL(u);
              return;
            }
            createdWave = u;
            setWaveUrl(u);
          })
          .catch(() => {})
      );
    }

    if (spectrogramImagePath) {
      tasks.push(
        mediaUrl(spectrogramImagePath)
          .then((u) => {
            if (cancelled) {
              URL.revokeObjectURL(u);
              return;
            }
            createdSpec = u;
            setSpecImgUrl(u);
          })
          .catch(() => {})
      );
    }

    Promise.allSettled(tasks).then(() => {
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
      if (createdWave) URL.revokeObjectURL(createdWave);
      if (createdSpec) URL.revokeObjectURL(createdSpec);
    };
  }, [spectrogramDataPath, spectrogramImagePath, waveformPath, reloadKey]);

  // Render interactive STFT spectrogram on HTML5 canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !specData?.grid) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const grid = specData.grid;
    const times: number[] = grid.times_sec || [];
    const freqs: number[] = grid.freqs_hz || [];
    const dbMatrix: number[][] = grid.db || [];
    const minDb: number = grid.min_db ?? -80;
    const maxDb: number = grid.max_db ?? 0;

    if (!times.length || !freqs.length || !dbMatrix.length) return;

    const width = canvas.width;
    const height = canvas.height;
    const padLeft = 58;
    const padRight = 18;
    const padTop = 16;
    const padBottom = 34;
    const plotW = Math.max(10, width - padLeft - padRight);
    const plotH = Math.max(10, height - padTop - padBottom);

    ctx.fillStyle = "#F7F3EC";
    ctx.fillRect(0, 0, width, height);

    // Filter frequency bins up to selected ceiling
    const nyquist = specData.stft_config?.nyquist_hz || freqs[freqs.length - 1] || 8000;
    const ceilingHz = Math.min(maxFreqHz, nyquist);
    const fIndices: number[] = [];
    for (let i = 0; i < freqs.length; i++) {
      if (freqs[i] <= ceilingHz) fIndices.push(i);
    }
    const nF = Math.max(1, fIndices.length);

    // Compute visible time slice for zoom & pan
    const totalT = times.length;
    const visibleT = Math.max(2, Math.floor(totalT / zoom));
    const maxStartT = Math.max(0, totalT - visibleT);
    const startT = Math.min(maxStartT, Math.floor(panRatio * maxStartT));
    const endT = Math.min(totalT - 1, startT + visibleT - 1);
    const nT = Math.max(1, endT - startT + 1);

    // Draw spectrogram heatmap pixels
    const offscreen = document.createElement("canvas");
    offscreen.width = nT;
    offscreen.height = nF;
    const offCtx = offscreen.getContext("2d");
    if (offCtx) {
      const imgData = offCtx.createImageData(nT, nF);
      const data = imgData.data;
      for (let fy = 0; fy < nF; fy++) {
        const fIdx = fIndices[nF - 1 - fy]; // flip so low freq is at bottom
        const row = dbMatrix[fIdx] || [];
        for (let tx = 0; tx < nT; tx++) {
          const tIdx = startT + tx;
          const dbVal = row[tIdx] ?? minDb;
          const [r, g, b] = dbToRgb(dbVal, minDb, maxDb);
          const p = (fy * nT + tx) * 4;
          data[p] = r;
          data[p + 1] = g;
          data[p + 2] = b;
          data[p + 3] = 255;
        }
      }
      offCtx.putImageData(imgData, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(offscreen, padLeft, padTop, plotW, plotH);
    }

    // Plot border
    ctx.strokeStyle = "#D6C9B6";
    ctx.lineWidth = 1;
    ctx.strokeRect(padLeft, padTop, plotW, plotH);

    // Frequency axis ticks & labels (vertical)
    ctx.fillStyle = "#57534E";
    ctx.font = "11px Outfit, system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    const nFreqTicks = 5;
    for (let i = 0; i <= nFreqTicks; i++) {
      const frac = i / nFreqTicks;
      const fVal = frac * ceilingHz;
      const yPos = padTop + plotH - frac * plotH;
      ctx.beginPath();
      ctx.moveTo(padLeft - 4, yPos);
      ctx.lineTo(padLeft, yPos);
      ctx.strokeStyle = "#78716C";
      ctx.stroke();
      const label = freqUnit === "kHz" ? `${(fVal / 1000).toFixed(1)}k` : `${Math.round(fVal)}`;
      ctx.fillText(label, padLeft - 7, yPos);
    }

    // Time axis ticks & labels (horizontal)
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const tStartSec = times[startT] ?? 0;
    const tEndSec = times[endT] ?? specData.duration_sec ?? 1;
    const nTimeTicks = 6;
    for (let i = 0; i <= nTimeTicks; i++) {
      const frac = i / nTimeTicks;
      const tVal = tStartSec + frac * (tEndSec - tStartSec);
      const xPos = padLeft + frac * plotW;
      ctx.beginPath();
      ctx.moveTo(xPos, padTop + plotH);
      ctx.lineTo(xPos, padTop + plotH + 4);
      ctx.strokeStyle = "#78716C";
      ctx.stroke();
      ctx.fillText(`${tVal.toFixed(2)}s`, xPos, padTop + plotH + 6);
    }

    // Axis titles
    ctx.fillStyle = "#57534E";
    ctx.font = "500 11px Outfit, system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Time (seconds)", padLeft + plotW / 2, height - 12);

    ctx.save();
    ctx.translate(14, padTop + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`Frequency (${freqUnit})`, 0, 0);
    ctx.restore();

    // Draw interactive hover crosshair if active
    if (hoverInfo) {
      ctx.save();
      ctx.strokeStyle = "rgba(28, 25, 23, 0.7)";
      ctx.setLineDash([4, 3]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hoverInfo.x, padTop);
      ctx.lineTo(hoverInfo.x, padTop + plotH);
      ctx.moveTo(padLeft, hoverInfo.y);
      ctx.lineTo(padLeft + plotW, hoverInfo.y);
      ctx.stroke();
      ctx.restore();
    }
  }, [specData, freqUnit, maxFreqHz, zoom, panRatio, hoverInfo]);

  function handleCanvasMouseMove(e: MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas || !specData?.grid) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    const padLeft = 58;
    const padRight = 18;
    const padTop = 16;
    const padBottom = 34;
    const plotW = canvas.width - padLeft - padRight;
    const plotH = canvas.height - padTop - padBottom;

    if (cx < padLeft || cx > padLeft + plotW || cy < padTop || cy > padTop + plotH) {
      setHoverInfo(null);
      return;
    }

    const times: number[] = specData.grid.times_sec || [];
    const freqs: number[] = specData.grid.freqs_hz || [];
    const dbMatrix: number[][] = specData.grid.db || [];
    const nyquist = specData.stft_config?.nyquist_hz || freqs[freqs.length - 1] || 8000;
    const ceilingHz = Math.min(maxFreqHz, nyquist);

    const totalT = times.length;
    const visibleT = Math.max(2, Math.floor(totalT / zoom));
    const maxStartT = Math.max(0, totalT - visibleT);
    const startT = Math.min(maxStartT, Math.floor(panRatio * maxStartT));
    const endT = Math.min(totalT - 1, startT + visibleT - 1);

    const uX = (cx - padLeft) / plotW;
    const uY = 1 - (cy - padTop) / plotH;

    const tIdx = Math.min(endT, Math.max(startT, Math.round(startT + uX * (endT - startT))));
    const targetFreq = uY * ceilingHz;
    let bestFIdx = 0;
    let bestDiff = Infinity;
    for (let i = 0; i < freqs.length; i++) {
      const d = Math.abs(freqs[i] - targetFreq);
      if (d < bestDiff) {
        bestDiff = d;
        bestFIdx = i;
      }
    }

    const timeSec = times[tIdx] ?? 0;
    const freqHz = freqs[bestFIdx] ?? targetFreq;
    const db = dbMatrix[bestFIdx]?.[tIdx] ?? -80;

    setHoverInfo({ timeSec, freqHz, db, x: cx, y: cy });
  }

  const cfg = specData?.stft_config;
  const metrics = specData?.signal_metrics;

  return (
    <div className="spectrogram-viewer" style={{ marginTop: compact ? 8 : 12 }}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <strong style={{ fontSize: "0.95rem" }}>{title}</strong>
          {cfg && (
            <div className="tiny">
              STFT {cfg.window} window · N={cfg.n_fft} · hop={cfg.hop_length} · Δf={cfg.freq_resolution_hz} Hz · Δt=
              {(cfg.time_resolution_sec * 1000).toFixed(1)} ms
            </div>
          )}
        </div>
        {specData && (
          <div className="row" style={{ gap: 6 }}>
            <button
              className={`btn ${freqUnit === "Hz" ? "" : "ghost"}`}
              type="button"
              style={{ padding: "4px 10px", fontSize: "0.76rem" }}
              onClick={() => setFreqUnit("Hz")}
            >
              Hz
            </button>
            <button
              className={`btn ${freqUnit === "kHz" ? "" : "ghost"}`}
              type="button"
              style={{ padding: "4px 10px", fontSize: "0.76rem" }}
              onClick={() => setFreqUnit("kHz")}
            >
              kHz
            </button>
            <select
              value={maxFreqHz}
              onChange={(e) => setMaxFreqHz(Number(e.target.value))}
              aria-label="Maximum frequency"
              style={{ width: "auto", padding: "4px 8px", fontSize: "0.76rem" }}
            >
              <option value={4000}>0–4 kHz</option>
              <option value={8000}>0–8 kHz</option>
              <option value={11025}>Full Nyquist</option>
            </select>
            <select
              value={zoom}
              onChange={(e) => {
                setZoom(Number(e.target.value));
                setPanRatio(0);
              }}
              aria-label="Spectrogram time zoom"
              style={{ width: "auto", padding: "4px 8px", fontSize: "0.76rem" }}
            >
              <option value={1}>Zoom 1×</option>
              <option value={2}>Zoom 2×</option>
              <option value={4}>Zoom 4×</option>
            </select>
            {specImgUrl && (
              <button
                className="btn ghost"
                type="button"
                style={{ padding: "4px 10px", fontSize: "0.76rem" }}
                onClick={() => setViewMode(viewMode === "interactive" ? "image" : "interactive")}
              >
                {viewMode === "interactive" ? "Static PNG" : "Interactive STFT"}
              </button>
            )}
          </div>
        )}
      </div>

      {loading && <div className="empty">Computing Short-Time Fourier Transform (STFT) and rendering spectrogram…</div>}

      {error && !loading && (
        <div className="error">
          <div>{error}</div>
          <button
            className="btn ghost"
            type="button"
            style={{ marginTop: 6, padding: "5px 12px", fontSize: "0.8rem" }}
            onClick={() => setReloadKey((k) => k + 1)}
          >
            Retry spectrogram
          </button>
        </div>
      )}

      {!loading && !error && !specData && !specImgUrl && (
        <div className="empty">Select or analyze an audio signal to inspect its waveform and spectrogram.</div>
      )}

      {waveUrl && (
        <div style={{ marginBottom: 8 }}>
          <img
            src={waveUrl}
            alt="Amplitude waveform over time"
            style={{ width: "100%", borderRadius: 10, border: "1px solid var(--line)", display: "block" }}
          />
        </div>
      )}

      {specData && viewMode === "interactive" && (
        <div
          style={{
            border: "1px solid var(--line)",
            borderRadius: 12,
            padding: 10,
            background: "#F7F3EC",
          }}
        >
          <canvas
            ref={canvasRef}
            width={680}
            height={compact ? 210 : 250}
            onMouseMove={handleCanvasMouseMove}
            onMouseLeave={() => setHoverInfo(null)}
            style={{ width: "100%", height: "auto", display: "block", cursor: "crosshair", borderRadius: 8 }}
          />

          {zoom > 1 && (
            <div className="row" style={{ marginTop: 6, gap: 8 }}>
              <span className="tiny">Pan time window:</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={panRatio}
                onChange={(e) => setPanRatio(Number(e.target.value))}
                style={{ flex: 1, accentColor: "var(--accent)" }}
              />
            </div>
          )}

          {/* Color scale legend and live cursor readout */}
          <div className="row" style={{ justifyContent: "space-between", marginTop: 8, gap: 12 }}>
            <div className="row" style={{ gap: 6, alignItems: "center" }}>
              <span className="tiny">Intensity (dBFS):</span>
              <span className="tiny">-80 dB</span>
              <div
                style={{
                  width: 110,
                  height: 10,
                  borderRadius: 99,
                  border: "1px solid #D6C9B6",
                  background: "linear-gradient(90deg, #F7F3EC 0%, #E8D5B5 30%, #C45C26 60%, #6B2B12 82%, #1C1917 100%)",
                }}
              />
              <span className="tiny">0 dB</span>
            </div>

            <div className="tiny" style={{ fontVariantNumeric: "tabular-nums" }} data-testid="spectrogram-readout">
              {hoverInfo ? (
                <strong>
                  Cursor: t = {hoverInfo.timeSec.toFixed(3)}s · f ={" "}
                  {freqUnit === "kHz" ? `${(hoverInfo.freqHz / 1000).toFixed(2)} kHz` : `${Math.round(hoverInfo.freqHz)} Hz`}{" "}
                  · {hoverInfo.db.toFixed(1)} dBFS
                </strong>
              ) : (
                <span>Hover over spectrogram to inspect time, frequency, and dBFS intensity</span>
              )}
            </div>
          </div>

          {metrics && (
            <div className="row" style={{ marginTop: 8, gap: 6 }}>
              <span className="badge">
                Peak freq:{" "}
                {metrics.is_silent || metrics.peak_freq_hz == null
                  ? "None (silent)"
                  : freqUnit === "kHz"
                    ? `${(metrics.peak_freq_hz / 1000).toFixed(2)} kHz`
                    : `${Math.round(metrics.peak_freq_hz)} Hz`}
              </span>
              <span className="badge">RMS: {metrics.rms_db} dBFS</span>
              <span className="badge">Dynamic range: {metrics.dynamic_range_db} dB</span>
              {metrics.is_silent && <span className="badge warn">Silent signal detected</span>}
              {metrics.is_near_silent && <span className="badge warn">Near-silent signal</span>}
              {metrics.is_clipped && <span className="badge bad">Clipping detected ({(metrics.clipping_ratio * 100).toFixed(1)}%)</span>}
            </div>
          )}
        </div>
      )}

      {specImgUrl && (viewMode === "image" || !specData) && (
        <img
          src={specImgUrl}
          alt="STFT Spectrogram"
          style={{ width: "100%", borderRadius: 12, border: "1px solid var(--line)", display: "block" }}
        />
      )}
    </div>
  );
}
