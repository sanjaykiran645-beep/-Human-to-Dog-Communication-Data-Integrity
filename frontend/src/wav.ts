/** Encode Float32 PCM as a 16-bit mono WAV Blob. Used so microphone capture does not depend on WEBM/Opus. */

function merge(chunks: Float32Array[]): Float32Array {
  let n = 0;
  for (const c of chunks) n += c.length;
  const out = new Float32Array(n);
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
  }
  return out;
}

function writeString(view: DataView, offset: number, s: string) {
  for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
}

export function encodeWav(chunks: Float32Array[], sampleRate: number): Blob {
  const samples = merge(chunks);
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function recordPcmWav(maxSeconds = 60): Promise<{ stop: () => void; done: Promise<File> }> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  proc.onaudioprocess = (e) => {
    chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  };
  src.connect(proc);
  proc.connect(ctx.destination);
  let resolveFile: (f: File) => void;
  const done = new Promise<File>((res) => {
    resolveFile = res;
  });
  const started = Date.now();
  const stop = () => {
    try {
      proc.disconnect();
      src.disconnect();
    } catch {
      /* ignore */
    }
    stream.getTracks().forEach((t) => t.stop());
    const elapsed = (Date.now() - started) / 1000;
    if (elapsed > maxSeconds) chunks.splice(Math.floor((chunks.length * maxSeconds) / elapsed));
    const blob = encodeWav(chunks, ctx.sampleRate);
    void ctx.close();
    resolveFile(new File([blob], "microphone.wav", { type: "audio/wav" }));
  };
  return { stop, done };
}
