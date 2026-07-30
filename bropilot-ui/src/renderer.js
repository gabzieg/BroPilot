// Ponte do overlay: fala com o processo main via IPC, que por sua vez spawna
// `python -m bropilot_core.cli --ask` (ver electron-main.js). Sem
// contextBridge de propósito — a janela já roda com nodeIntegration:true /
// contextIsolation:false (config existente do protótipo), então
// require('electron') funciona direto aqui.
const { ipcRenderer } = require('electron');

const panel = document.getElementById('bropilot-panel');
const statusIndicator = document.querySelector('.status-indicator');
const assistantText = document.getElementById('assistant-text');
const input = document.getElementById('question-input');

function showThinking() {
    statusIndicator.classList.add('thinking');
    assistantText.innerText = 'Analisando ficha e consultando RAG...';
}

function showAnswer(payload) {
    statusIndicator.classList.remove('thinking');
    if (payload.error) {
        assistantText.innerText = `Erro: ${payload.error}`;
        return;
    }
    const fontes = payload.sources && payload.sources.length
        ? `<br><small>fontes: ${payload.sources.join(', ')}</small>`
        : '';
    assistantText.innerHTML = `${payload.answer}${fontes}`;
}

// Ctrl+0 (registrado no main) só manda "toggle" — quem decide focar o input
// é aqui, porque só o renderer sabe se o painel estava escondido ou não.
ipcRenderer.on('bropilot:toggle', () => {
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) {
        input.focus();
    }
});

ipcRenderer.on('bropilot:answer', (_event, payload) => {
    showAnswer(payload);
});

input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    const question = input.value.trim();
    if (!question) return;
    showThinking();
    ipcRenderer.send('bropilot:ask', question);
    input.value = '';
});
