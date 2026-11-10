function newClipSeed(current, excluded = []) {
  let next = crypto.getRandomValues(new Uint32Array(1))[0];
  const used = new Set([Number(current), ...excluded]);
  // Advance on collisions instead of retrying a possibly repeating random source.
  while (used.has(next)) next = (next + 1) % 4294967296;
  return next;
}

function initializeClipSeed(input, excluded = []) {
  input.value = newClipSeed(input.value, excluded);
  input.dataset.seedReady = 'true';
}

function consumeClipSeed(input, randomize, excluded = []) {
  // A draft edit or New seed belongs to the next request, even with Randomize on.
  if (randomize && (input.dataset.seedReady !== 'true' || input.value === '-1')) {
    initializeClipSeed(input, excluded);
  }
  const value = Number(input.value);
  if (input.value === '' || !Number.isSafeInteger(value) || value < -1) {
    // Let the server report invalid drafts through its normal cleanup/error path.
    return input.value === '' ? '' : value;
  }
  input.dataset.seedReady = 'false';
  return value;
}
