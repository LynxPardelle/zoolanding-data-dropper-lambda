import assert from 'node:assert/strict';
import test from 'node:test';

import {
  fetchAssociatedPullRequests,
  fetchTargetBranchSha,
  validatePromotionEvidence,
} from '../tools/verify-promotion-commit.mjs';

const repository = 'LynxPardelle/zoolanding-data-dropper-lambda';
const mergeSha = 'a'.repeat(40);
const baseSha = 'b'.repeat(40);
const headSha = 'c'.repeat(40);

function evidence(overrides = {}) {
  const pullRequest = {
    state: 'closed',
    merged_at: '2026-07-15T10:00:00Z',
    merge_commit_sha: mergeSha,
    base: { ref: 'test', sha: baseSha, repo: { full_name: repository } },
    head: { ref: 'dev', sha: headSha, repo: { full_name: repository } },
  };
  return {
    repository,
    sha: mergeSha,
    ref: 'refs/heads/test',
    sourceBranch: 'dev',
    targetBranch: 'test',
    eventName: 'push',
    event: {
      after: mergeSha,
      before: baseSha,
      created: false,
      deleted: false,
      forced: false,
    },
    targetTipSha: mergeSha,
    parents: [baseSha, headSha],
    pullRequests: [pullRequest],
    ...overrides,
  };
}

test('accepts only the exact same-repository merged dev-to-test PR evidence', () => {
  assert.doesNotThrow(() => validatePromotionEvidence(evidence()));

  const valid = evidence().pullRequests[0];
  for (const pullRequest of [
    { ...valid, state: 'open' },
    { ...valid, merged_at: null },
    { ...valid, merge_commit_sha: 'd'.repeat(40) },
    { ...valid, head: { ...valid.head, ref: 'feature' } },
    { ...valid, base: { ...valid.base, ref: 'main' } },
    { ...valid, head: { ...valid.head, repo: { full_name: 'someone/fork' } } },
    { ...valid, base: { ...valid.base, repo: { full_name: 'someone/fork' } } },
  ]) {
    assert.throws(
      () => validatePromotionEvidence(evidence({ pullRequests: [pullRequest] })),
      /promotion_pr_not_found/,
    );
  }
});

test('accepts API 2026 associated PRs with null or absent merge_commit_sha', () => {
  const withNull = evidence().pullRequests[0];
  withNull.merge_commit_sha = null;
  assert.doesNotThrow(() => validatePromotionEvidence(evidence({ pullRequests: [withNull] })));

  const withoutField = structuredClone(evidence().pullRequests[0]);
  delete withoutField.merge_commit_sha;
  assert.doesNotThrow(() => validatePromotionEvidence(evidence({ pullRequests: [withoutField] })));
});

test('requires exact two-parent order, push predecessor, target ref, and current tip', () => {
  for (const invalid of [
    { parents: [baseSha] },
    { pullRequests: [{ ...evidence().pullRequests[0], base: { ...evidence().pullRequests[0].base, sha: 'e'.repeat(40) } }] },
    { parents: [baseSha, 'd'.repeat(40)] },
    { event: { ...evidence().event, before: 'e'.repeat(40) } },
    { ref: 'refs/heads/main' },
    { targetTipSha: 'f'.repeat(40) },
  ]) {
    assert.throws(() => validatePromotionEvidence(evidence(invalid)), /promotion_/);
  }
});

test('rejects ambiguous, direct, forced, created, and deleted promotions', () => {
  const valid = evidence().pullRequests[0];
  assert.throws(
    () => validatePromotionEvidence(evidence({ pullRequests: [valid, structuredClone(valid)] })),
    /promotion_pr_ambiguous/,
  );
  assert.throws(() => validatePromotionEvidence(evidence({ parents: [baseSha] })), /promotion_merge_commit_required/);
  for (const field of ['forced', 'created', 'deleted']) {
    assert.throws(
      () => validatePromotionEvidence(evidence({ event: { ...evidence().event, [field]: true } })),
      /promotion_push_not_allowed/,
    );
  }
});

test('associated-PR lookup retries empty responses and accepts null merge SHA', async () => {
  let calls = 0;
  let requestedHeaders;
  const withNull = evidence().pullRequests[0];
  withNull.merge_commit_sha = null;

  const result = await fetchAssociatedPullRequests({
    apiUrl: 'https://api.github.com',
    repository,
    sha: mergeSha,
    githubToken: 'synthetic-test-token',
    attempts: 3,
    retryDelayMs: 0,
    sleep: async () => {},
    fetchImpl: async (_url, options) => {
      calls += 1;
      requestedHeaders = options.headers;
      return {
        ok: true,
        status: 200,
        json: async () => calls < 3 ? [] : [withNull],
      };
    },
  });

  assert.equal(calls, 3);
  assert.equal(requestedHeaders['X-GitHub-Api-Version'], '2026-03-10');
  assert.deepEqual(result, [withNull]);
});

test('target lookup returns only an exact SHA and fails closed on malformed evidence', async () => {
  const common = {
    apiUrl: 'https://api.github.com',
    repository,
    targetBranch: 'test',
    githubToken: 'synthetic-test-token',
    attempts: 1,
    retryDelayMs: 0,
    sleep: async () => {},
  };

  assert.equal(await fetchTargetBranchSha({
    ...common,
    fetchImpl: async () => ({ ok: true, json: async () => ({ commit: { sha: mergeSha } }) }),
  }), mergeSha);
  await assert.rejects(fetchTargetBranchSha({
    ...common,
    fetchImpl: async () => ({ ok: true, json: async () => ({ commit: { sha: 'not-a-sha' } }) }),
  }), /promotion_api_invalid_response/);
});
