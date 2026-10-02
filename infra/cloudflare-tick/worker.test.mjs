// Run with: node --test infra/cloudflare-tick/   (CI: Frontend job)
import assert from "node:assert/strict";
import { test } from "node:test";

import worker, { tick } from "./worker.js";

const ENV = { API_URL: "https://api.example.com/", JOBS_TICK_TOKEN: "t".repeat(40) };
const OK_BODY = { enqueued: ["purge_job_tables"], already_enqueued: [], ticked_at: "x" };
const noSleep = async () => {};

function reply(status, body = {}) {
  return new Response(JSON.stringify(body), { status });
}

test("posts to the tick endpoint with the shared secret", async () => {
  const calls = [];
  const body = await tick(ENV, {
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return reply(202, OK_BODY);
    },
    sleep: noSleep,
  });

  assert.deepEqual(body, OK_BODY);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.example.com/api/v1/admin/jobs/tick");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers["X-Jobs-Tick-Token"], ENV.JOBS_TICK_TOKEN);
});

test("retries once while the API wakes up", async () => {
  const replies = [() => Promise.reject(new TypeError("fetch failed")), () => reply(202, OK_BODY)];
  let slept = 0;
  const body = await tick(ENV, {
    fetchImpl: async () => replies.shift()(),
    sleep: async () => {
      slept += 1;
    },
  });

  assert.deepEqual(body, OK_BODY);
  assert.equal(slept, 1);
});

test("does not retry a refused token, and never puts the token in the error", async () => {
  let calls = 0;
  await assert.rejects(
    tick(ENV, {
      fetchImpl: async () => {
        calls += 1;
        return reply(403);
      },
      sleep: noSleep,
    }),
    (error) => {
      assert.match(error.message, /HTTP 403/);
      assert.ok(!error.message.includes(ENV.JOBS_TICK_TOKEN));
      return true;
    },
  );
  assert.equal(calls, 1);
});

test("fails clearly when the Worker is not configured", async () => {
  await assert.rejects(tick({}, { sleep: noSleep }), /API_URL and JOBS_TICK_TOKEN/);
});

test("the scheduled handler hands the tick to waitUntil", async () => {
  const waited = [];
  const original = globalThis.fetch;
  globalThis.fetch = async () => reply(202, OK_BODY);
  try {
    await worker.scheduled({}, ENV, { waitUntil: (promise) => waited.push(promise) });
    assert.equal(waited.length, 1);
    assert.deepEqual(await waited[0], OK_BODY);
  } finally {
    globalThis.fetch = original;
  }
});

test("visiting the Worker's URL does nothing", async () => {
  const response = await worker.fetch();
  assert.equal(response.status, 404);
});
