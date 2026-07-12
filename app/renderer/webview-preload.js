// Polyfill missing Performance API methods that VS Code's input-latency
// tracker uses — prevents "mgt.clearMarks is not a function" console error.
(function () {
  if (typeof performance === 'undefined') return;
  const noop = () => {};
  const noopArr = () => [];
  if (typeof performance.clearMarks    !== 'function') performance.clearMarks    = noop;
  if (typeof performance.clearMeasures !== 'function') performance.clearMeasures = noop;
  if (typeof performance.mark          !== 'function') performance.mark          = noop;
  if (typeof performance.measure       !== 'function') performance.measure       = noop;
  if (typeof performance.getEntriesByName !== 'function') performance.getEntriesByName = noopArr;

  const globalObj = typeof globalThis !== 'undefined' ? globalThis : window;
  const marks = globalObj && globalObj.MonacoPerformanceMarks;
  if (marks && typeof marks === 'object') {
    if (typeof marks.clearMarks !== 'function') marks.clearMarks = noop;
    if (typeof marks.mark !== 'function') marks.mark = noop;
    if (typeof marks.getMarks !== 'function') marks.getMarks = noopArr;
  }
})();
