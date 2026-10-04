const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

// Exercise the real IPC handler and spawn arguments without launching Electron
// or transcription. Run `npm run build:electron` before this test.
const compiledDirectory = path.resolve(__dirname, "../dist-electron");
const mainSource = fs.readFileSync(path.join(compiledDirectory, "main.js"), "utf8");
const preloadSource = fs.readFileSync(path.join(compiledDirectory, "preload.js"), "utf8");
const options = {
  input: "/音声 フォルダ/test.wav",
  output: "/字幕 出力",
  title: " テスト 字幕 ",
  model: "small",
  format: "srt",
  language: "ja",
};

function loadMain(isPackaged) {
  const handlers = new Map();
  const calls = [];
  const electron = {
    app: { isPackaged, whenReady: () => ({ then() {} }), on() {} },
    ipcMain: { handle: (name, handler) => handlers.set(name, handler) },
  };
  const childProcess = {
    spawn(command, args, spawnOptions) {
      calls.push({ command, args: Array.from(args), options: spawnOptions });
      const child = new EventEmitter();
      child.stdout = new EventEmitter();
      child.stderr = new EventEmitter();
      child.stdout.setEncoding = child.stderr.setEncoding = () => {};
      queueMicrotask(() => child.emit("close", 0));
      return child;
    },
  };
  vm.runInNewContext(mainSource, {
    exports: {},
    __dirname: compiledDirectory,
    process: { platform: "darwin", resourcesPath: "/test-resources", env: {} },
    setInterval: () => 1,
    clearInterval() {},
    require(name) {
      if (name === "electron") return electron;
      if (name === "node:child_process") return childProcess;
      if (name === "node:fs") return { existsSync: () => true };
      if (name === "./shared.js") return require(path.join(compiledDirectory, "shared.js"));
      return require(name);
    },
  });
  return { generate: handlers.get("subtitle:generate"), calls };
}

for (const isPackaged of [false, true]) {
  for (const enabled of [undefined, false, true]) {
    test(`IPC sends word timestamps=${enabled} (packaged=${isPackaged})`, async () => {
      const { generate, calls } = loadMain(isPackaged);
      const input = enabled === undefined ? options : { ...options, wordTimestamps: enabled };
      const result = await generate(null, input);
      assert.equal(result.success, true);
      assert.equal(calls.length, 1);
      assert.equal(calls[0].options.shell, false);
      const expected = [
        "--input", options.input, "--output", options.output, "--title", options.title.trim(),
        "--model", "small", "--format", "srt", "--language", "ja",
      ];
      if (enabled) expected.push("--word-timestamps");
      if (!isPackaged) expected.unshift(path.resolve(compiledDirectory, "../subtitle.py"));
      assert.deepEqual(calls[0].args, expected);
    });
  }
}

test("IPC rejects non-boolean word timestamp values without spawning", async () => {
  for (const value of ["false", "true", 0, 1, null, {}, []]) {
    const { generate, calls } = loadMain(false);
    const result = await generate(null, { ...options, wordTimestamps: value });
    assert.equal(result.success, false);
    assert.equal(result.error, "Invalid word timestamps option.");
    assert.equal(calls.length, 0);
  }
});

test("preload forwards the selected boolean from Renderer to IPC", async () => {
  let api;
  const calls = [];
  vm.runInNewContext(preloadSource, {
    exports: {},
    require(name) {
      assert.equal(name, "electron");
      return {
        contextBridge: { exposeInMainWorld: (_name, value) => { api = value; } },
        ipcRenderer: { invoke: async (...args) => { calls.push(args); return { success: true }; } },
      };
    },
  });
  for (const enabled of [false, true]) {
    const input = { ...options, wordTimestamps: enabled };
    await api.generateSubtitle(input);
    const [channel, payload] = calls.at(-1);
    assert.equal(channel, "subtitle:generate");
    assert.equal(payload, input);
    assert.equal(payload.wordTimestamps, enabled);
  }
});
