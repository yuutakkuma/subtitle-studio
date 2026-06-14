import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Clipboard,
  FileAudio,
  FolderOpen,
  Loader2,
  Play,
  Square,
  TriangleAlert,
} from "lucide-react";
import {
  GenerateSubtitleResult,
  SubtitleFormat,
  SubtitleLanguage,
  SubtitleLogEvent,
  SubtitleModel,
  subtitleFormats,
  subtitleLanguages,
  subtitleModels,
} from "../electron/shared";

type StoredSettings = {
  model?: SubtitleModel;
  format?: SubtitleFormat;
  language?: SubtitleLanguage;
  output?: string;
};

type Status = "idle" | "running" | "success" | "failed" | "stopped";

const settingsKey = "whisper-subtitle-settings";

function readStoredSettings(): StoredSettings {
  try {
    return JSON.parse(localStorage.getItem(settingsKey) ?? "{}") as StoredSettings;
  } catch {
    return {};
  }
}

function App() {
  const stored = useMemo(readStoredSettings, []);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState(stored.output ?? "");
  const [title, setTitle] = useState("subtitle");
  const [model, setModel] = useState<SubtitleModel>(stored.model ?? "large-v3");
  const [format, setFormat] = useState<SubtitleFormat>(stored.format ?? "srt");
  const [language, setLanguage] = useState<SubtitleLanguage>(stored.language ?? "ja");
  const [logs, setLogs] = useState<SubtitleLogEvent[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<GenerateSubtitleResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [copyMessage, setCopyMessage] = useState("");
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const canGenerate =
    input.trim().length > 0 &&
    output.trim().length > 0 &&
    title.trim().length > 0 &&
    model.length > 0 &&
    format.length > 0 &&
    language.length > 0 &&
    status !== "running";

  useEffect(() => {
    const unsubscribe = window.subtitle.onLog((event) => {
      const parts = event.message.split(/\r?\n/).filter((line) => line.length > 0);
      const nextProgress = getProgressFromLog(event.message);
      if (event.message.includes("Still running")) {
        setProgress((current) => Math.min(Math.max(current + 3, 50), 75));
      } else if (nextProgress !== null) {
        setProgress((current) => Math.max(current, nextProgress));
      }
      setLogs((current) => [
        ...current,
        ...(parts.length > 0 ? parts : [event.message]).map((message) => ({
          ...event,
          message,
        })),
      ]);
    });

    return unsubscribe;
  }, []);

  useEffect(() => {
    const settings: StoredSettings = {
      model,
      format,
      language,
      output,
    };
    localStorage.setItem(settingsKey, JSON.stringify(settings));
  }, [model, format, language, output]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [logs]);

  const selectAudioFile = async () => {
    const selected = await window.subtitle.selectAudioFile();
    if (selected) {
      setInput(selected);
    }
  };

  const selectOutputDirectory = async () => {
    const selected = await window.subtitle.selectOutputDirectory();
    if (selected) {
      setOutput(selected);
    }
  };

  const generate = async () => {
    if (!canGenerate) return;

    setStatus("running");
    setResult(null);
    setLogs([]);
    setProgress(5);

    try {
      const nextResult = await window.subtitle.generateSubtitle({
        input,
        output,
        title: title.trim(),
        model,
        format,
        language,
      });

      setResult(nextResult);
      setStatus(nextResult.success ? "success" : nextResult.stopped ? "stopped" : "failed");
      setProgress((current) => (nextResult.success ? 100 : current));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected IPC error.";
      setResult({
        success: false,
        exitCode: null,
        error: message,
      });
      setStatus("failed");
      setLogs((current) => [
        ...current,
        {
          level: "error",
          message,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  const stopGeneration = async () => {
    if (status !== "running") return;

    try {
      const stopResult = await window.subtitle.stopSubtitle();
      setLogs((current) => [
        ...current,
        {
          level: stopResult.stopped ? "info" : "error",
          message: stopResult.message,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to stop subtitle generation.";
      setLogs((current) => [
        ...current,
        {
          level: "error",
          message,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  const copyLogs = async () => {
    if (logs.length === 0) return;

    const text = logs
      .map((log) => `[${formatTime(log.timestamp)}] ${log.message}`)
      .join("\n");

    try {
      const result = await window.subtitle.copyText(text);
      setCopyMessage(result.success ? "コピーしました" : result.message);
    } catch (error) {
      setCopyMessage(error instanceof Error ? error.message : "コピーに失敗しました");
    }

    window.setTimeout(() => {
      setCopyMessage("");
    }, 2000);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);

    const [file] = Array.from(event.dataTransfer.files);
    if (!file) return;

    const filePath = window.subtitle.getDroppedFilePath(file);
    if (filePath) {
      setInput(filePath);
    }
  };

  return (
    <main className="h-screen overflow-hidden bg-zinc-100 text-zinc-950 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto flex h-screen min-h-0 w-full max-w-5xl flex-col px-6 py-8">
        <header className="mb-7 shrink-0 flex flex-wrap items-end justify-between gap-4 border-b border-zinc-300 pb-5 dark:border-zinc-800">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">Subtitle Studio</h1>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              音声ファイルから SRT / VTT / TXT 字幕を生成します。
            </p>
          </div>
          <StatusBadge status={status} />
        </header>

        <section className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,0.85fr)]">
          <div className="min-h-0 space-y-5 overflow-y-auto pr-1">
            <div
              className={[
                "rounded border border-dashed p-5 transition",
                isDragging
                  ? "border-teal-500 bg-teal-50 dark:bg-teal-950/30"
                  : "border-zinc-300 bg-white dark:border-zinc-800 dark:bg-zinc-900",
              ].join(" ")}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
            >
              <FieldLabel label="音声ファイル" />
              <div className="mt-2 flex gap-3">
                <ReadonlyPath value={input} placeholder="音声ファイルを選択またはドロップ" />
                <IconButton onClick={selectAudioFile} label="選択" icon={<FileAudio size={18} />} />
              </div>
            </div>

            <div className="rounded border border-zinc-300 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <FieldLabel label="出力先フォルダ" />
              <div className="mt-2 flex gap-3">
                <ReadonlyPath value={output} placeholder="出力先フォルダを選択" />
                <IconButton onClick={selectOutputDirectory} label="選択" icon={<FolderOpen size={18} />} />
              </div>
            </div>

            <div className="rounded border border-zinc-300 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <label className="block">
                <FieldLabel label="出力ファイル名" />
                <input
                  className="mt-2 w-full rounded border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 dark:border-zinc-700 dark:bg-zinc-950"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="subtitle"
                  disabled={status === "running"}
                />
              </label>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <SelectField
                label="モデル"
                value={model}
                options={subtitleModels}
                onChange={(event) => setModel(event.target.value as SubtitleModel)}
              />
              <SelectField
                label="出力形式"
                value={format}
                options={subtitleFormats}
                onChange={(event) => setFormat(event.target.value as SubtitleFormat)}
              />
              <SelectField
                label="言語"
                value={language}
                options={subtitleLanguages}
                onChange={(event) => setLanguage(event.target.value as SubtitleLanguage)}
              />
            </div>

            <div className="space-y-3 rounded border border-zinc-300 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex gap-3">
                <button
                  className="flex h-12 flex-1 items-center justify-center gap-2 rounded bg-teal-600 px-4 text-sm font-semibold text-white transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:bg-zinc-400 disabled:text-zinc-100 dark:disabled:bg-zinc-700"
                  disabled={!canGenerate}
                  onClick={generate}
                >
                  {status === "running" ? (
                    <Loader2 className="animate-spin" size={18} />
                  ) : (
                    <Play size={18} />
                  )}
                  字幕生成
                </button>

                <button
                  className="flex h-12 w-32 items-center justify-center gap-2 rounded border border-red-300 bg-white px-4 text-sm font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:border-zinc-300 disabled:text-zinc-400 dark:border-red-900 dark:bg-zinc-950 dark:text-red-300 dark:hover:bg-red-950/30 dark:disabled:border-zinc-700 dark:disabled:text-zinc-500"
                  disabled={status !== "running"}
                  onClick={stopGeneration}
                  type="button"
                >
                  <Square size={16} />
                  停止
                </button>
              </div>

              <ProgressMeter progress={progress} status={status} />
            </div>

            {result && (
              <div
                className={[
                  "rounded border px-4 py-3 text-sm",
                  result.success
                    ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100"
                    : "border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100",
                ].join(" ")}
              >
                <div className="flex items-center gap-2 font-semibold">
                  {result.success ? <CheckCircle2 size={18} /> : <TriangleAlert size={18} />}
                  {result.success
                    ? "Subtitle generated successfully."
                    : result.stopped
                      ? "Subtitle generation stopped."
                      : "Subtitle generation failed."}
                </div>
                {result.outputPath && <p className="mt-2 break-all">{result.outputPath}</p>}
                {result.error && <p className="mt-2 break-all">{result.error}</p>}
              </div>
            )}
          </div>

          <section className="flex min-h-0 flex-col overflow-hidden rounded border border-zinc-300 bg-white dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex shrink-0 items-center justify-between gap-3 border-b border-zinc-300 px-4 py-3 dark:border-zinc-800">
              <h2 className="text-base font-semibold">ログ</h2>
              <div className="flex items-center gap-2">
                {copyMessage && (
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {copyMessage}
                  </span>
                )}
                <button
                  className="flex h-8 items-center gap-2 rounded border border-zinc-300 bg-white px-3 text-xs font-medium transition hover:border-teal-500 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-950 dark:hover:text-teal-300"
                  disabled={logs.length === 0}
                  onClick={copyLogs}
                  type="button"
                >
                  <Clipboard size={14} />
                  コピー
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4 font-mono text-xs leading-5">
              {logs.length === 0 ? (
                <p className="text-zinc-500">実行ログがここに表示されます。</p>
              ) : (
                logs.map((log, index) => (
                  <div
                    key={`${log.timestamp}-${index}`}
                    className={[
                      "whitespace-pre-wrap break-words",
                      log.level === "stderr" || log.level === "error"
                        ? "text-red-600 dark:text-red-300"
                        : log.level === "info"
                          ? "text-sky-700 dark:text-sky-300"
                          : "text-zinc-800 dark:text-zinc-200",
                    ].join(" ")}
                  >
                    <span className="text-zinc-400">[{formatTime(log.timestamp)}]</span>{" "}
                    {log.message}
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}

function FieldLabel({ label }: { label: string }) {
  return <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{label}</span>;
}

function ReadonlyPath({ value, placeholder }: { value: string; placeholder: string }) {
  return (
    <input
      className="min-w-0 flex-1 rounded border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm outline-none dark:border-zinc-700 dark:bg-zinc-950"
      value={value}
      placeholder={placeholder}
      readOnly
      title={value}
    />
  );
}

function IconButton({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className="flex h-10 shrink-0 items-center gap-2 rounded border border-zinc-300 bg-white px-3 text-sm font-medium transition hover:border-teal-500 hover:text-teal-700 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:hover:text-teal-300"
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  );
}

function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly T[];
  onChange: (event: ChangeEvent<HTMLSelectElement>) => void;
}) {
  return (
    <label className="block rounded border border-zinc-300 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <FieldLabel label={label} />
      <select
        className="mt-2 w-full rounded border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-500/20 dark:border-zinc-700 dark:bg-zinc-950"
        value={value}
        onChange={onChange}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const text = {
    idle: "待機中",
    running: "実行中",
    success: "完了",
    failed: "失敗",
    stopped: "停止",
  }[status];

  const tone = {
    idle: "border-zinc-300 text-zinc-600 dark:border-zinc-700 dark:text-zinc-300",
    running: "border-sky-300 text-sky-700 dark:border-sky-700 dark:text-sky-300",
    success: "border-emerald-300 text-emerald-700 dark:border-emerald-800 dark:text-emerald-300",
    failed: "border-red-300 text-red-700 dark:border-red-800 dark:text-red-300",
    stopped: "border-amber-300 text-amber-700 dark:border-amber-800 dark:text-amber-300",
  }[status];

  return <div className={`rounded border px-3 py-1 text-sm font-medium ${tone}`}>{text}</div>;
}

function ProgressMeter({ progress, status }: { progress: number; status: Status }) {
  const visibleProgress = status === "idle" ? 0 : progress;
  const label = status === "running"
    ? `実行中... ${visibleProgress}%`
    : status === "success"
      ? "完了 100%"
      : status === "stopped"
        ? `停止 ${visibleProgress}%`
        : status === "failed"
          ? `失敗 ${visibleProgress}%`
          : "待機中 0%";

  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs text-zinc-600 dark:text-zinc-400">
        <span>{label}</span>
        <span>目安</span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-zinc-200 dark:bg-zinc-800">
        <div
          className={[
            "h-full rounded transition-all duration-500",
            status === "failed"
              ? "bg-red-500"
              : status === "stopped"
                ? "bg-amber-500"
                : "bg-teal-500",
          ].join(" ")}
          style={{ width: `${visibleProgress}%` }}
        />
      </div>
    </div>
  );
}

function getProgressFromLog(message: string) {
  if (message.includes("Subtitle generation started")) return 5;
  if (message.includes("Runner:")) return 8;
  if (message.includes("Loading model")) return 20;
  if (message.includes("Transcribing audio")) return 45;
  if (message.includes("Still running")) return 50;
  if (message.includes("Detected language")) return 80;
  if (message.includes("Formatting subtitles")) return 90;
  if (message.includes("Generated:")) return 95;
  if (message.includes("Subtitle generated successfully")) return 100;
  return null;
}

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(timestamp));
}

export default App;
