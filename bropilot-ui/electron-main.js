const { app, BrowserWindow, globalShortcut, ipcMain } = require('electron');
const path = require('path');

let mainWindow;

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

app.whenReady().then(() => {
    createWindow();

    // Registra o Atalho Global do MVP: Ctrl + 0
    const ret = globalShortcut.register('CommandOrControl+0', () => {
        console.log('Atalho Ctrl+0 pressionado!');
        
        mainWindow.webContents.executeJavaScript(`
            document.getElementById('bropilot-panel').classList.remove('hidden');
            document.querySelector('.status-indicator').classList.add('thinking');
            document.getElementById('assistant-text').innerText = "Analisando ficha e consultando RAG...";
            
            // Simular o LLM respondendo após 3 segundos
            setTimeout(() => {
                document.querySelector('.status-indicator').classList.remove('thinking');
                document.getElementById('assistant-text').innerHTML = "<b>🔥 Mentor:</b> Use <i>Ação Surto</i> no Líder Goblin. Ele está com Status [Desprotegido] e você tem Action Points sobrando. A Shadowheart aprovará um ataque letal.";
            }, 3000);
        `);
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
