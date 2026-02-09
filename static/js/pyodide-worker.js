// Web Worker для выполнения Python кода через Pyodide
// Этот файл выполняется в отдельном потоке, что позволяет прерывать зацикленные программы

importScripts('https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js');

let pyodide = null;

// Инициализация Pyodide
async function initPyodide() {
    pyodide = await loadPyodide();
    self.postMessage({ type: 'ready' });
}

// Выполнение Python кода
async function runPython(code, inputs) {
    if (!pyodide) {
        self.postMessage({ type: 'error', error: 'Python ещё загружается...' });
        return;
    }

    // Перехват stdout
    pyodide.runPython(`
import sys

class MockStdout:
    def __init__(self):
        self.data = []
    def write(self, text):
        self.data.append(text)
    def flush(self):
        pass

sys.stdout = MockStdout()
sys.stderr = MockStdout()
    `);

    // Установка функции input
    pyodide.globals.set('__inputs__', inputs);
    pyodide.globals.set('__input_index__', 0);

    pyodide.runPython(`
def input(prompt=''):
    global __input_index__
    if prompt:
        sys.stdout.write(str(prompt))
    if __input_index__ < len(__inputs__):
        val = __inputs__[__input_index__]
        __input_index__ += 1
        sys.stdout.write(str(val) + '\\n')
        return val
    return ''

import builtins
builtins.input = input
    `);

    try {
        pyodide.runPython(code);
        const stdout = pyodide.runPython('sys.stdout.data');
        const output = stdout.toJs().join('');
        self.postMessage({ type: 'result', output: output.trim(), error: null });
    } catch (error) {
        self.postMessage({ type: 'result', output: '', error: error.message });
    }
}

// Обработка сообщений от основного потока
self.onmessage = async function(e) {
    const { type, code, inputs } = e.data;

    if (type === 'init') {
        await initPyodide();
    } else if (type === 'run') {
        await runPython(code, inputs || []);
    }
};
