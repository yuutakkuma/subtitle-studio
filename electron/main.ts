import { app, BrowserWindow, clipboard, dialog, ipcMain } from "electron";
import type { BrowserWindow as BrowserWindowType } from "electron";
import { ChildProcess, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {
  GenerateSubtitleOptions,
  GenerateSubtitleResult,
  SubtitleFormat,
  SubtitleLanguage,
  SubtitleLogEvent,
  SubtitleModel,
  subtitleFormats,
  subtitleLanguages,
  subtitleModels,
} from "./shared.js";

const projectRoot = path.resolve(__dirname, "..");
const isDev = Boolean(process.env.VITE_DEV_SERVER_URL);
const bundledCliName = process.platform === "win32" ? "subtitle-cli.exe" : "subtitle-cli";

let mainWindow: BrowserWindowType | null = null;
let isGenerating = false;
let currentChild: ChildProcess | null = null;
let stopRequested = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1040,
    height: 820,
    minWidth: 760,
    minHeight: 620,
    title: "Whisper Subtitle",
    backgroundColor: "#0f172a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    void mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
  } else {
    void mainWindow.loadFile(path.join(projectRoot, "dist", "index.html"));
  }
}

function sendLog(level: SubtitleLogEvent["level"], message: string) {
  mainWindow?.webContents.send("subtitle:log", {
    level,
    message,
    timestamp: new Date().toISOString(),
  } satisfies SubtitleLogEvent);
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isModel(value: unknown): value is SubtitleModel {
  return typeof value === "string" && subtitleModels.includes(value as SubtitleModel);
}

function isFormat(value: unknown): value is SubtitleFormat {
  return typeof value === "string" && subtitleFormats.includes(value as SubtitleFormat);
}

function isLanguage(value: unknown): value is SubtitleLanguage {
  return typeof value === "string" && subtitleLanguages.includes(value as SubtitleLanguage);
}

function validateOptions(value: unknown): GenerateSubtitleOptions {
  if (!value || typeof value !== "object") {
    throw new Error("Invalid options.");
  }

  const options = value as Partial<GenerateSubtitleOptions>;

  if (!isNonEmptyString(options.input)) throw new Error("Audio file is required.");
  if (!isNonEmptyString(options.output)) throw new Error("Output directory is required.");
  if (!isNonEmptyString(options.title)) throw new Error("Output file name is required.");
  if (!isModel(options.model)) throw new Error("Invalid model.");
  if (!isFormat(options.format)) throw new Error("Invalid output format.");
  if (!isLanguage(options.language)) throw new Error("Invalid language.");

  return {
    input: options.input,
    output: options.output,
    title: options.title.trim(),
    model: options.model,
    format: options.format,
    language: options.language,
  };
}

type SubtitleRunner = {
  command: string;
  argsPrefix: string[];
  cwd: string;
};

function getSubtitleRunner(): SubtitleRunner {
  const bundledCliPath = path.join(process.resourcesPath, "bin", bundledCliName);

  if (app.isPackaged && fs.existsSync(bundledCliPath)) {
    return {
      command: bundledCliPath,
      argsPrefix: [],
      cwd: path.dirname(bundledCliPath),
    };
  }

  if (process.env.PYTHON_PATH && process.env.PYTHON_PATH.trim().length > 0) {
    return {
      command: process.env.PYTHON_PATH,
      argsPrefix: [path.join(projectRoot, "subtitle.py")],
      cwd: projectRoot,
    };
  }

  const venvPython = process.platform === "win32"
    ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
    : path.join(projectRoot, ".venv", "bin", "python");

  if (fs.existsSync(venvPython)) {
    return {
      command: venvPython,
      argsPrefix: [path.join(projectRoot, "subtitle.py")],
      cwd: projectRoot,
    };
  }

  return {
    command: process.platform === "win32" ? "python" : "python3",
    argsPrefix: [path.join(projectRoot, "subtitle.py")],
    cwd: projectRoot,
  };
}

function formatElapsed(ms: number) {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

ipcMain.handle("subtitle:select-audio-file", async () => {
  const result = await dialog.showOpenDialog({
    title: "音声ファイルを選択",
    properties: ["openFile"],
    filters: [
      {
        name: "Audio Files",
        extensions: ["wav", "mp3", "m4a", "aac", "flac"],
      },
      { name: "All Files", extensions: ["*"] },
    ],
  });

  return result.canceled ? null : result.filePaths[0] ?? null;
});

ipcMain.handle("subtitle:select-output-directory", async () => {
  const result = await dialog.showOpenDialog({
    title: "出力先フォルダを選択",
    properties: ["openDirectory", "createDirectory"],
  });

  return result.canceled ? null : result.filePaths[0] ?? null;
});

ipcMain.handle("subtitle:stop", async () => {
  if (!isGenerating || !currentChild) {
    return {
      stopped: false,
      message: "No subtitle generation is running.",
    };
  }

  stopRequested = true;
  sendLog("info", "Stop requested. Terminating subtitle process...");
  currentChild.kill(process.platform === "win32" ? undefined : "SIGTERM");

  return {
    stopped: true,
    message: "Stop requested.",
  };
});

ipcMain.handle("subtitle:copy-text", async (_event, text: unknown) => {
  if (typeof text !== "string") {
    return {
      success: false,
      message: "Invalid clipboard text.",
    };
  }

  clipboard.writeText(text);

  return {
    success: true,
    message: "Copied to clipboard.",
  };
});

ipcMain.handle("subtitle:generate", async (_event, unsafeOptions): Promise<GenerateSubtitleResult> => {
  if (isGenerating) {
    return {
      success: false,
      exitCode: null,
      error: "Subtitle generation is already running.",
    };
  }

  let options: GenerateSubtitleOptions;

  try {
    options = validateOptions(unsafeOptions);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid options.";
    sendLog("error", message);
    return { success: false, exitCode: null, error: message };
  }

  isGenerating = true;
  stopRequested = false;
  const outputPath = path.join(options.output, `${options.title}.${options.format}`);
  const runner = getSubtitleRunner();
  const args = [
    ...runner.argsPrefix,
    "--input",
    options.input,
    "--output",
    options.output,
    "--title",
    options.title,
    "--model",
    options.model,
    "--format",
    options.format,
    "--language",
    options.language,
  ];

  sendLog("info", "Subtitle generation started.");
  sendLog("info", `Runner: ${runner.command}`);
  sendLog("info", `Arguments: ${args.map((arg) => JSON.stringify(arg)).join(" ")}`);

  return await new Promise((resolve) => {
    let isResolved = false;
    let stderrText = "";
    const startedAt = Date.now();
    let heartbeat: NodeJS.Timeout | null = null;

    const finish = (result: GenerateSubtitleResult) => {
      if (isResolved) return;
      isResolved = true;
      if (heartbeat) {
        clearInterval(heartbeat);
      }
      isGenerating = false;
      currentChild = null;
      resolve(result);
    };

    const child = spawn(runner.command, args, {
      cwd: runner.cwd,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
      },
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });

    currentChild = child;
    heartbeat = setInterval(() => {
      sendLog("info", `Still running... elapsed ${formatElapsed(Date.now() - startedAt)}.`);
    }, 10000);

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");

    child.stdout.on("data", (data: string) => {
      sendLog("stdout", data);
    });

    child.stderr.on("data", (data: string) => {
      stderrText += data;
      sendLog("stderr", data);

      if (stderrText.includes("the following arguments are required")) {
        child.kill();
        sendLog("error", "Subtitle generation failed.");
        finish({
          success: false,
          exitCode: null,
          error: "subtitle-cli reported missing required arguments.",
        });
      }
    });

    child.on("error", (error) => {
      sendLog("error", error.message);
      finish({
        success: false,
        exitCode: null,
        error: error.message,
      });
    });

    child.on("close", (code) => {
      sendLog("info", `Process exited with code ${code ?? "unknown"}.`);

      if (stopRequested) {
        sendLog("info", "Subtitle generation stopped.");
        finish({
          success: false,
          exitCode: code,
          error: "Subtitle generation stopped.",
          stopped: true,
        });
        return;
      }

      if (code === 0) {
        sendLog("info", "Subtitle generated successfully.");
        finish({ success: true, exitCode: code, outputPath });
        return;
      }

      sendLog("error", "Subtitle generation failed.");
      finish({
        success: false,
        exitCode: code,
        error: `subtitle-cli exited with code ${code ?? "unknown"}.`,
      });
    });
  });
});

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
