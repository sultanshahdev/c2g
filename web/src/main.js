import * as monaco from 'monaco-editor';
import EditorWorker from 'monaco-editor/editor/editor.worker?worker';
import './style.css';

self.MonacoEnvironment = { getWorker() { return new EditorWorker(); } };
const state = document.querySelector('#state'), position = document.querySelector('#position'), versionEl = document.querySelector('#version');
let pythonVersion = 0, applyingRemote = false, sequence = 0, ready = false, processing = false;
const pending = [];
const editor = monaco.editor.create(document.querySelector('#editor'), {
  value: '# c2g Monaco feasibility spike\nprint("ready")\n', language: 'python', theme: 'vs-dark', automaticLayout: true,
  lineNumbers: 'on', minimap: {enabled: true}, wordWrap: 'on', bracketPairColorization: {enabled: true}, autoIndent: 'full'
});
const model = editor.getModel();
function status(text) { state.textContent = text; versionEl.textContent = `CRDT v${pythonVersion}`; }
function renderPeers(ui) { const add=(id,items,connect)=>{const root=document.querySelector(id);root.replaceChildren(...items.map(item=>{const row=document.createElement('div');row.className='peer';row.textContent=`${item.username} — ${item.state||item.endpoint||`${item.host}:${item.port}`}`;const button=document.createElement('button');button.textContent=connect?' Connect':' Disconnect';button.onclick=async()=>{const result=connect?await window.pywebview.api.connect_discovered(item.host,item.port):await window.pywebview.api.disconnect_peer(item.peer_id);status(result.accepted?(result.status||'Connecting'):result.reason);};row.append(button);return row;}));};add('#connected',ui.connected||[],false);add('#discovered',ui.discovered||[],true);document.querySelector('#peers').textContent=`${(ui.connected||[]).length} Peers`;}
function applyPatch(patch) {
  applyingRemote = true;
  const start = model.getPositionAt(patch.offset), end = model.getPositionAt(patch.offset + patch.length);
  editor.executeEdits('c2g-remote', [{range: new monaco.Range(start.lineNumber,start.column,end.lineNumber,end.column), text: patch.text, forceMoveMarkers: true}]);
  applyingRemote = false;
}
async function drain(){if(processing||!ready||!pending.length)return;processing=true;const tx=pending[0];try{const result=await window.pywebview.api.apply_local_transaction({transaction_id:tx.id,base_version:pythonVersion,changes:tx.changes});if(result.accepted){pythonVersion=result.version;pending.shift();status(pending.length?'Saving local edits…':'Synced');}else{pending.length=0;applyingRemote=true;model.setValue(result.text||'');applyingRemote=false;pythonVersion=result.version;status(`Recovered: ${result.reason}`);}}catch(error){status(`Bridge error: ${error}`)}finally{processing=false;drain();}}
model.onDidChangeContent(event=>{if(applyingRemote||!ready)return;pending.push({id:`js-${++sequence}`,changes:event.changes.map(c=>({rangeOffset:c.rangeOffset,rangeLength:c.rangeLength,text:c.text}))});status('Saving local edits…');drain();});
editor.onDidChangeCursorPosition(e => position.textContent = `Ln ${e.position.lineNumber}, Col ${e.position.column}`);
window.addEventListener('pywebviewready', async () => {
  const initial = await window.pywebview.api.editor_ready();
  applyingRemote = true; model.setValue(initial.text); applyingRemote = false;
  pythonVersion = initial.version; ready = true; renderPeers(initial.ui_state); document.querySelector('#document').textContent=initial.document_id; status('Ready');
  window.c2gApplyRemotePatch = payload => { applyPatch(payload.patch); pythonVersion = payload.version; status('Remote patch applied'); };
});
window.c2gReceive=payload=>{if(payload.type==='remote_patch')window.c2gApplyRemotePatch(payload);else if(payload.type==='network'){renderPeers(payload.ui_state);status(payload.kind.replaceAll('_',' '));}};
document.querySelector('#connect-form').addEventListener('submit',async event=>{event.preventDefault();const result=await window.pywebview.api.connect(document.querySelector('#endpoint').value);status(result.accepted?(result.status||'Connecting'):result.reason);});
document.querySelector('#save').onclick=async()=>{const result=await window.pywebview.api.export_document();status(result.accepted?`Exported ${result.path}`:`Export failed: ${result.reason}`);};
