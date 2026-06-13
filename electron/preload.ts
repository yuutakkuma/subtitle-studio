import { contextBridge, ipcRenderer, webUtils } from "electron";
import {
  GenerateSubtitleOptions,
  GenerateSubtitleResult,
  SubtitleLogEvent,
  StopSubtitleResult,
} from "./shared.js";

const subtitleApi = {
  selectAudioFile: () => ipcRenderer.invoke("subtitle:select-audio-file") as Promise<string | null>,
  selectOutputDirectory: () =>
    ipcRenderer.invoke("subtitle:select-output-directory") as Promise<string | null>,
  generateSubtitle: (options: GenerateSubtitleOptions) =>
    ipcRenderer.invoke("subtitle:generate", options) as Promise<GenerateSubtitleResult>,
  stopSubtitle: () => ipcRenderer.invoke("subtitle:stop") as Promise<StopSubtitleResult>,
  onLog: (callback: (event: SubtitleLogEvent) => void) => {
    const listener = (_event: Electron.IpcRendererEvent, logEvent: SubtitleLogEvent) => {
      callback(logEvent);
    };

    ipcRenderer.on("subtitle:log", listener);

    return () => {
      ipcRenderer.removeListener("subtitle:log", listener);
    };
  },
  getDroppedFilePath: (file: File) => webUtils.getPathForFile(file),
};

contextBridge.exposeInMainWorld("subtitle", subtitleApi);
