const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../ghost/static/app.js"), "utf8");

async function setup(configured = true) {
  const items = {};
  const calls = [];
  let failure = false;
  function element() {
    return {
      disabled: false, hidden: false, value: "", textContent: "", children: [], handlers: {},
      classList: { toggle() {} },
      addEventListener(name, callback) { this.handlers[name] = callback; },
      appendChild(item) { this.children.push(item); },
      scrollIntoView() {}, focus() {},
      querySelectorAll() {
        return this.children.map((item) => ({ remove: () => this.children.splice(this.children.indexOf(item), 1) }));
      },
    };
  }
  for (const id of ["#composer", "#message", "#send", "#clear", "#status", "#feedback", "#conversation", "#welcome", "#dot"]) items[id] = element();
  const context = {
    document: { querySelector: (id) => items[id], createElement: () => element() },
    fetch: async (url, options) => {
      if (url === "/api/status") return { ok: true, json: async () => ({ configured, model: "test-model" }) };
      calls.push(JSON.parse(options.body));
      return failure
        ? { ok: false, json: async () => ({ detail: "额度不足" }) }
        : { ok: true, json: async () => ({ reply: "<script>plain text</script>" }) };
    },
  };
  vm.runInNewContext(source, context);
  await new Promise(setImmediate);
  return {
    items, calls,
    fail: () => { failure = true; },
    recover: () => { failure = false; },
    send: async (value) => {
      items["#message"].value = value;
      await items["#composer"].handlers.submit({ preventDefault() {} });
    },
  };
}

test("missing configuration disables sending without API calls", async () => {
  const app = await setup(false);
  assert.equal(app.items["#send"].disabled, true);
  await app.send("hello");
  assert.equal(app.calls.length, 0);
});

test("conversation carries bounded history and renders model output as text", async () => {
  const app = await setup();
  for (let index = 0; index < 11; index++) await app.send("message " + index);
  assert.equal(app.calls.at(-1).messages.length, 19);
  assert.equal(app.calls.at(-1).messages[0].role, "user");
  const output = app.items["#conversation"].children.at(-1);
  assert.equal(output.textContent, "<script>plain text</script>");
  assert.equal(output.innerHTML, undefined);
  app.items["#clear"].handlers.click();
  await app.send("fresh");
  assert.equal(app.calls.at(-1).messages.length, 1);
});

test("failed requests restore input and are excluded from subsequent context", async () => {
  const app = await setup();
  app.fail();
  await app.send("retry me");
  assert.equal(app.items["#message"].value, "retry me");
  assert.equal(app.items["#send"].disabled, false);
  app.recover();
  await app.send("retry me");
  assert.equal(app.calls.at(-1).messages.length, 1);
});
