export type SubtitleModel = "tiny" | "base" | "small" | "medium" | "large-v3";
export type SubtitleFormat = "srt" | "vtt" | "txt";
export type SubtitleLanguage = "ja" | "en";

export type GenerateSubtitleOptions = {
  input: string;
  output: string;
  title: string;
  model: SubtitleModel;
  format: SubtitleFormat;
  language: SubtitleLanguage;
};

export type SubtitleLogLevel = "stdout" | "stderr" | "info" | "error";

export type SubtitleLogEvent = {
  level: SubtitleLogLevel;
  message: string;
  timestamp: string;
};

export type GenerateSubtitleResult = {
  success: boolean;
  exitCode: number | null;
  outputPath?: string;
  error?: string;
  stopped?: boolean;
};

export type StopSubtitleResult = {
  stopped: boolean;
  message: string;
};

export type CopyTextResult = {
  success: boolean;
  message: string;
};

export const subtitleModels: SubtitleModel[] = [
  "tiny",
  "base",
  "small",
  "medium",
  "large-v3",
];

export const subtitleFormats: SubtitleFormat[] = ["srt", "vtt", "txt"];
export const subtitleLanguages: SubtitleLanguage[] = ["ja", "en"];
