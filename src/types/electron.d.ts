import type {
  GenerateSubtitleOptions,
  GenerateSubtitleResult,
  SubtitleLogEvent,
  StopSubtitleResult,
} from "../../electron/shared";

declare global {
  interface Window {
    subtitle: {
      selectAudioFile: () => Promise<string | null>;
      selectOutputDirectory: () => Promise<string | null>;
      generateSubtitle: (options: GenerateSubtitleOptions) => Promise<GenerateSubtitleResult>;
      stopSubtitle: () => Promise<StopSubtitleResult>;
      onLog: (callback: (event: SubtitleLogEvent) => void) => () => void;
      getDroppedFilePath: (file: File) => string;
    };
  }
}

export {};
