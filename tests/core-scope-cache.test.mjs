import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

// The cache is optional browser state: every test installs its own tab storage.
function fakeStorage() {
  const rows = new Map();
  return {
    getItem: key => (rows.has(key) ? rows.get(key) : null),
    setItem: (key, value) => {rows.set(key, String(value));},
    removeItem: key => {rows.delete(key);},
  };
}

function installStorage(storage = fakeStorage()) {
  globalThis.window = {sessionStorage: storage};
  return storage;
}

const cache = await loadModule('features/live/scope-cache.ts');

test('remembers and re-reads workspaces per identity only', () => {
  installStorage();
  cache.rememberWorkspaces('actor-a', [
    {id: 'ws-1', name: 'Acme', roles: ['operator'], membershipId: 'm-1'},
  ]);
  assert.deepEqual(cache.cachedWorkspaces('actor-a'), [
    {id: 'ws-1', name: 'Acme', roles: ['operator'], membershipId: 'm-1'},
  ]);
  assert.equal(cache.cachedWorkspaces('actor-b'), null);
});

test('projects stay scoped to their workspace and feed the project name lookup', () => {
  installStorage();
  cache.rememberProjects('actor-a', 'ws-1', [
    {id: 'p-1', name: 'Spring offer', status: 'active'},
  ]);
  cache.rememberProjects('actor-a', 'ws-2', [
    {id: 'p-2', name: 'Autumn offer', status: 'draft'},
  ]);
  assert.deepEqual(cache.cachedProjects('actor-a', 'ws-1'), [
    {id: 'p-1', name: 'Spring offer', status: 'active'},
  ]);
  assert.equal(cache.cachedProjects('actor-a', 'ws-3'), null);
  assert.equal(cache.cachedProjectName('actor-a', 'ws-1', 'p-1'), 'Spring offer');
  assert.equal(cache.cachedProjectName('actor-a', 'ws-2', 'p-1'), null);
  assert.equal(cache.cachedProjectName('actor-b', 'ws-1', 'p-1'), null);
});

test('clearScopeCache drops everything and sign-out state cannot leak', () => {
  installStorage();
  cache.rememberWorkspaces('actor-a', [{id: 'ws-1', name: 'Acme', roles: [], membershipId: null}]);
  cache.clearScopeCache();
  assert.equal(cache.cachedWorkspaces('actor-a'), null);
});

test('corrupt or oversized cache entries are ignored instead of painted', () => {
  const storage = installStorage();
  storage.setItem('buyeros.scope-cache.v1', '{not json');
  assert.equal(cache.cachedWorkspaces('actor-a'), null);
  storage.setItem('buyeros.scope-cache.v1', JSON.stringify({
    version: 1,
    identities: { 'actor-a': {workspaces: [{id: 'ws-1'}]} },
  }));
  assert.equal(cache.cachedWorkspaces('actor-a'), null);
});

test('missing browser storage keeps the cache optional', () => {
  delete globalThis.window;
  assert.equal(cache.cachedWorkspaces('actor-a'), null);
  cache.rememberWorkspaces('actor-a', [{id: 'ws-1', name: 'Acme', roles: [], membershipId: null}]);
  cache.clearScopeCache();
});
