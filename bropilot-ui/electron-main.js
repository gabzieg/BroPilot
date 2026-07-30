const { app, BrowserWindow, globalShortcut, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow;

// Interpretador que roda o bropilot_core. Convenção: mesma do CLI standalone
// (ver CLAUDE.md) — ative o venv com as dependências (tiktoken, lancedb,
// ollama/openai...) ANTES de rodar `npm run electron`, o subprocess herda o
// PATH do shell que abriu o Electron. Override via env var pra quem usa
// outro caminho/venv sem mexer em código.
const PYTHON_BIN = process.env.BROPILOT_PYTHON || 'python';
const REPO_ROOT = path.resolve(__dirname, '..');

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        frame: false, // Sem bordas
        transparent: true, // Fundo transparente para o Glassmorphism
        alwaysOnTop: true, // Sempre em cima do BG3
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    // Carrega o Vite Dev Server
    // Em produção, isso apontaria para o `dist/index.html`
    mainWindow.loadURL('http://localhost:5173').catch(() => {
        console.log("Falha ao conectar no Vite. Você iniciou o npm run dev?");
    });

    // Deixa a janela clicável ou não
    // mainWindow.setIgnoreMouseEvents(true); // Se quiser que clique passe reto pro jogo
}

/**
 * Roda `python -m bropilot_core.cli --ask "<pergunta>"` como subprocess e
 * devolve o JSON já parseado ({answer, sources, party_had_live_stats} ou
 * {error}). Processo novo por pergunta — paga cold start do RAG a cada vez,
 * trade-off aceito (decisão: subprocess por chamada, não servidor
 * persistente) em troca de não ter lifecycle de processo pra gerenciar.
 */
function askBroPilot(question) {
    return new Promise((resolve, reject) => {
        const proc = spawn(
            PYTHON_BIN,
            ['-m', 'bropilot_core.cli', '--ask', question],
            { cwd: REPO_ROOT }
        );

        let stdout = '';
        let stderr = '';
        proc.stdout.on('data', (chunk) => { stdout += chunk; });
        proc.stderr.on('data', (chunk) => { stderr += chunk; });

        proc.on('error', (err) => {
            // spawn falhou antes de rodar (ex: PYTHON_BIN não existe no PATH)
            reject(new Error(`Falha ao iniciar "${PYTHON_BIN}": ${err.message}`));
        });

        proc.on('close', (code) => {
            const saida = stdout.trim();
            if (!saida) {
                reject(new Error(stderr.trim() || `bropilot_core.cli saiu com código ${code} sem stdout`));
                return;
            }
            try {
                resolve(JSON.parse(saida));
            } catch (err) {
                reject(new Error(`Resposta não é JSON válido: ${saida.slice(0, 200)}`));
            }
        });
    });
}

app.whenReady().then(() => {
    createWindow();

    // Ponte real: renderer manda a pergunta, main spawna o Python e devolve
    // a resposta. cli.py --ask já imprime {answer, sources, ...} OU
    // {error: "..."} no stdout — askBroPilot() nunca lança por erro DE
    // NEGÓCIO (Ollama offline, índice ausente etc), só por falha de spawn/
    // parse; então o catch aqui cobre a exceção real e repassa como
    // {error} pro renderer tratar igual.
    ipcMain.on('bropilot:ask', async (event, question) => {
        try {
            const payload = await askBroPilot(question);
            event.sender.send('bropilot:answer', payload);
        } catch (err) {
            event.sender.send('bropilot:answer', { error: err.message });
        }
    });

    // Registra o Atalho Global do MVP: Ctrl + 0 — só alterna o painel; quem
    // decide o que mostrar é o renderer (renderer.js).
    const ret = globalShortcut.register('CommandOrControl+0', () => {
        if (mainWindow) mainWindow.webContents.send('bropilot:toggle');
    });

    if (!ret) {
        console.log('Falha ao registrar o atalho global');
    }

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') app.quit();
});
