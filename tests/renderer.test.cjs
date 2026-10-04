const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

const source = fs.readFileSync(path.resolve(__dirname, "../src/App.tsx"), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
    esModuleInterop: true,
  },
});

function renderCheckbox(stored) {
  const exports = {};
  vm.runInNewContext(outputText, {
    exports,
    localStorage: { getItem: () => stored },
    require(name) {
      if (name === "../electron/shared") return require("../dist-electron/shared.js");
      if (name === "../package.json") return require("../package.json");
      return require(name);
    },
  });
  const html = renderToStaticMarkup(React.createElement(exports.default));
  assert.match(html, /単語ごとの時刻を取得する/);
  const checkbox = html.match(/<input\b[^>]*type="checkbox"[^>]*>/);
  assert.ok(checkbox, "The setting must be rendered as a checkbox");
  return checkbox[0];
}

for (const [label, stored] of [
  ["no settings", null],
  ["legacy settings", JSON.stringify({ model: "small", format: "vtt", language: "ja" })],
  ["saved false", JSON.stringify({ wordTimestamps: false })],
  ["string true", JSON.stringify({ wordTimestamps: "true" })],
  ["invalid JSON", "{"],
  ["null JSON", "null"],
  ["array JSON", "[]"],
]) {
  test(`word timestamps defaults to unchecked with ${label}`, () => {
    assert.doesNotMatch(renderCheckbox(stored), /\bchecked=/);
  });
}

test("word timestamps restores a saved boolean true", () => {
  assert.match(renderCheckbox(JSON.stringify({ wordTimestamps: true })), /\bchecked=/);
});
