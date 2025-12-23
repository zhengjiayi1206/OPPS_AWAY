import { app, BrowserWindow, session, systemPreferences } from 'electron'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const ASR_PORT = process.env.ASR_PORT || '5001'
let pythonProcess = null
const logPath = path.join(app.getPath('userData'), 'python-server.log')

function logLine(message) {
  try {
    fs.appendFileSync(logPath, `${new Date().toISOString()} ${message}\n`)
  } catch {
    // ignore logging failures
  }
}

function getPythonCommand() {
  if (app.isPackaged) {
    const binaryName = process.platform === 'win32' ? 'python_asr_server.exe' : 'python_asr_server'
    return path.join(process.resourcesPath, 'server', binaryName)
  }
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN
  const venvPython =
    process.platform === 'win32'
      ? path.join(app.getAppPath(), '.venv', 'Scripts', 'python.exe')
      : path.join(app.getAppPath(), '.venv', 'bin', 'python')
  if (fs.existsSync(venvPython)) return venvPython
  return process.platform === 'win32' ? 'python' : 'python3'
}

function startPythonServer() {
  if (pythonProcess) return
  const command = getPythonCommand()
  const args = []

  if (!app.isPackaged) {
    args.push('server/python_asr_server.py')
  } else if (process.platform !== 'win32' && fs.existsSync(command)) {
    // Ensure packaged binary is executable on macOS/Linux
    try {
      fs.chmodSync(command, 0o755)
    } catch (error) {
      logLine(`chmod failed for ${command}: ${error}`)
    }
  }

  pythonProcess = spawn(command, args, {
    env: {
      ...process.env,
      PORT: ASR_PORT,
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  pythonProcess.on('spawn', () => {
    logLine(`python server spawned: ${command} ${args.join(' ')}`)
  })
  pythonProcess.stdout?.on('data', (chunk) => {
    logLine(`py: ${chunk.toString().trim()}`)
  })
  pythonProcess.stderr?.on('data', (chunk) => {
    logLine(`py err: ${chunk.toString().trim()}`)
  })
  pythonProcess.on('error', (error) => {
    logLine(`python spawn error: ${error}`)
  })
  pythonProcess.on('exit', (code) => {
    if (code !== null) {
      if (code !== 0) console.error(`Python server exited with code ${code}`)
      logLine(`python server exited with code ${code}`)
    } else {
      logLine('python server exited with null code')
    }
    pythonProcess = null
  })
}

function stopPythonServer() {
  if (!pythonProcess) return
  pythonProcess.kill()
  pythonProcess = null
}

async function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(app.getAppPath(), 'electron', 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  const devServerUrl = process.env.VITE_DEV_SERVER_URL
  if (devServerUrl) {
    await mainWindow.loadURL(devServerUrl)
  } else {
    const indexPath = path.join(app.getAppPath(), 'dist', 'index.html')
    await mainWindow.loadFile(indexPath)
  }
}

app.whenReady().then(async () => {
  session.defaultSession.setPermissionRequestHandler((_, permission, callback) => {
    if (permission === 'media') {
      callback(true)
      return
    }
    callback(false)
  })
  if (process.platform === 'darwin') {
    try {
      await systemPreferences.askForMediaAccess('microphone')
    } catch (error) {
      console.warn('Failed to request microphone access:', error)
    }
  }
  startPythonServer()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  stopPythonServer()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
