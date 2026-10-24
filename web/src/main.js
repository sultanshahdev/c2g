import * as monaco from 'monaco-editor';
import EditorWorker from 'monaco-editor/editor/editor.worker?worker';
import './style.css';

self.MonacoEnvironment = { getWorker() { return new EditorWorker(); } };
const state = document.querySelector('#state'), position = document.querySelector('#position'), versionEl = document.querySelector('#version');
let pythonVersion = 0, applyingRemote = false, sequence = 0;
const editor = monaco.editor.create(document.querySelector('#editor'), {
  value: '# c2g Monaco feasibility spike\nprint("ready")\n', language: 'python', theme: 'vs-dark', automaticLayout: true,
  lineNumbers: 'on', minimap: {enabled: true}, wordWrap: 'on', bracketPairColorization: {enabled: true}, autoIndent: 'full'
});
const model = editor.getModel();
function status(text) { state.textContent = text; versionEl.textContent = `CRDT v${pythonVersion}`; }
function applyPatch(patch) {
  applyingRemote = true;
  const selection = editor.getSelection();
  const start = model.getPositionAt(patch.offset), end = model.getPositionAt(patch.offset + patch.length);
  editor.executeEdits('c2g-remote', [{range: new monaco.Range(start.lineNumber,start.column,end.lineNumber,end.column), text: patch.text, forceMoveMarkers: true}]);
  if (selection) editor.setSelection(selection); // Monaco transforms tracked model positions for normal edits.
  applyingRemote = false;
}
model.onDidChangeContent(async event => {
  if (applyingRemote || !window.pywebview?.api) return;
  const tx = {transaction_id: `js-${++sequence}`, base_version: pythonVersion, changes: event.changes.map(c => ({rangeOffset:c.rangeOffset,rangeLength:c.rangeLength,text:c.text}))};
  const result = await window.pywebview.api.apply_local_transaction(tx);
  if (!result.accepted) { status(`Rejected: ${result.reason}`); return; }
  pythonVersion = result.version; status('Synced');
});
editor.onDidChangeCursorPosition(e => position.textContent = `Ln ${e.position.lineNumber}, Col ${e.position.column}`);
window.addEventListener('pywebviewready', async () => {
  const initial = await window.pywebview.api.editor_ready();
  applyingRemote = true; model.setValue(initial.text); applyingRemote = false;
  pythonVersion = initial.version; status('Connected');
  window.c2gApplyRemotePatch = payload => { applyPatch(payload.patch); pythonVersion = payload.version; status('Remote patch applied'); };
});
