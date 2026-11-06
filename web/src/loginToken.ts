// Capture once, before requests, and remove authentication links from history.
let captured = false;
let pending = '';
let setup = '';
export function getLoginToken() {
  if (!captured) {
    captured = true;
    if (window.location.hash.startsWith('#login=') || window.location.hash.startsWith('#setup=')) {
      if (window.location.hash.startsWith('#setup=')) setup = window.location.hash.slice(7);
      else pending = window.location.hash.slice(7);
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }
  return pending;
}
export function clearLoginToken() { pending = ''; }
export function getSetupToken() { getLoginToken(); return setup; }
export function clearSetupToken() { setup = ''; }
