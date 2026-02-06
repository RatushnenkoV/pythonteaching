// Инициализация редактора CodeMirror
const editor = CodeMirror.fromTextArea(document.getElementById('code'), {
    mode: 'python',
    theme: 'monokai',
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    extraKeys: {
        'Tab': function(cm) {
            cm.replaceSelection('    ', 'end');
        }
    },
    readOnly: isCompleted
});

const consoleEl = document.getElementById('console');
const consoleInputLine = document.getElementById('consoleInputLine');
const consoleInput = document.getElementById('consoleInput');
const consolePrompt = document.getElementById('consolePrompt');
const runBtn = document.getElementById('runBtn');
const checkBtn = document.getElementById('checkBtn');

let pyodide = null;
let pyodideReady = false;
let inputResolve = null; // Для асинхронного ввода
let collectedInputs = []; // Собранные входные данные
let inputIndex = 0;
let isCollectingInputs = false;
let expectedInputCount = 0;

// Вывод в консоль
function consoleLog(text, className = '') {
    const line = document.createElement('div');
    if (className) line.className = className;
    line.textContent = text;
    consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function clearConsole() {
    consoleEl.innerHTML = '';
}

// Показать строку ввода
function showInputLine(prompt = '') {
    consolePrompt.textContent = prompt || '>>>';
    consoleInputLine.style.display = 'flex';
    consoleInput.value = '';
    consoleInput.focus();
}

// Скрыть строку ввода
function hideInputLine() {
    consoleInputLine.style.display = 'none';
}

// Ожидание ввода пользователя
function waitForInput(prompt = '') {
    return new Promise((resolve) => {
        showInputLine(prompt);
        inputResolve = resolve;
    });
}

// Обработка Enter в поле ввода
consoleInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        const value = consoleInput.value;

        // Показываем ввод в консоли
        consoleLog(consolePrompt.textContent + ' ' + value, 'user-input');
        hideInputLine();

        if (inputResolve) {
            inputResolve(value);
            inputResolve = null;
        }
    }
});

// Загрузка Pyodide
async function loadPyodideAndPackages() {
    consoleLog('Загрузка Python...', 'info');
    try {
        pyodide = await loadPyodide();
        pyodideReady = true;
        consoleLog('Python готов к работе!', 'success');
    } catch (error) {
        consoleLog('Ошибка загрузки Python: ' + error.message, 'error');
    }
}

// Подсчёт вызовов input() в коде
function countInputCalls(code) {
    // Простой подсчёт - ищем input( не в комментариях и строках
    // Это упрощённый метод, но работает для большинства случаев
    const lines = code.split('\n');
    let count = 0;

    for (const line of lines) {
        // Пропускаем комментарии
        const commentIndex = line.indexOf('#');
        const codePart = commentIndex >= 0 ? line.substring(0, commentIndex) : line;

        // Считаем input( в коде (упрощённо)
        const matches = codePart.match(/\binput\s*\(/g);
        if (matches) {
            count += matches.length;
        }
    }

    return count;
}

// Запуск Python кода с заданными входными данными
async function runPythonCode(code, inputs = []) {
    if (!pyodideReady) {
        return { output: '', error: 'Python ещё загружается...' };
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
        return { output: output.trim(), error: null };
    } catch (error) {
        return { output: '', error: error.message };
    }
}

// Сохранение кода на сервер
async function saveCode() {
    const code = editor.getValue();
    try {
        await fetch(`/student/task/${taskId}/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });
    } catch (error) {
        console.error('Ошибка сохранения:', error);
    }
}

// Интерактивный сбор входных данных
async function collectInputsInteractively(code) {
    const inputCount = countInputCalls(code);

    if (inputCount === 0) {
        return [];
    }

    consoleLog(`Программа ожидает ${inputCount} ${inputCount === 1 ? 'значение' : 'значений'} для ввода:`, 'info');

    const inputs = [];
    for (let i = 0; i < inputCount; i++) {
        const value = await waitForInput(`Ввод ${i + 1}/${inputCount}:`);
        inputs.push(value);
    }

    return inputs;
}

// Кнопка "Запустить"
runBtn.addEventListener('click', async () => {
    if (!pyodideReady) {
        clearConsole();
        consoleLog('Python ещё загружается, подождите...', 'info');
        return;
    }

    clearConsole();
    hideInputLine();

    const code = editor.getValue();
    await saveCode();

    // Собираем входные данные интерактивно
    const inputs = await collectInputsInteractively(code);

    if (inputs.length > 0) {
        consoleLog('', ''); // Пустая строка
    }

    consoleLog('Выполнение...', 'info');
    const result = await runPythonCode(code, inputs);

    // Очищаем только сообщение "Выполнение..."
    consoleEl.lastChild.remove();

    if (result.error) {
        consoleLog(result.error, 'error');
    } else {
        consoleLog(result.output || '(нет вывода)');
    }
});

// Кнопка "Проверить"
checkBtn.addEventListener('click', async () => {
    if (!pyodideReady) {
        clearConsole();
        consoleLog('Python ещё загружается, подождите...', 'info');
        return;
    }

    if (tests.length === 0) {
        clearConsole();
        consoleLog('Нет тестов для проверки', 'info');
        return;
    }

    clearConsole();
    hideInputLine();
    consoleLog('Проверка решения...', 'info');

    const code = editor.getValue();
    await saveCode();

    let allPassed = true;

    for (let i = 0; i < tests.length; i++) {
        const test = tests[i];
        const isHidden = test.hidden;
        const testInputs = test.input ? test.input.split('\n') : [];

        consoleLog(`\nТест ${i + 1}${isHidden ? ' (скрытый)' : ''}:`, 'info');

        const result = await runPythonCode(code, testInputs);

        if (result.error) {
            if (isHidden) {
                consoleLog('Ошибка выполнения', 'error');
            } else {
                consoleLog('Ошибка: ' + result.error, 'error');
            }
            allPassed = false;
            break;
        }

        const expected = (test.output || '').trim();
        // Убираем echo ввода из результата для сравнения
        let actual = result.output.trim();

        // Для сравнения нам нужен только финальный вывод без echo входных данных
        // Разбиваем по строкам и берём последние строки
        const actualLines = actual.split('\n');
        const expectedLines = expected.split('\n');

        // Сравниваем последние N строк, где N = количество строк в expected
        const relevantLines = actualLines.slice(-expectedLines.length);
        actual = relevantLines.join('\n');

        if (actual === expected) {
            consoleLog('Пройден!', 'success');
        } else {
            consoleLog('Не пройден!', 'error');
            if (!isHidden) {
                consoleLog('Ожидалось: ' + expected);
                consoleLog('Получено: ' + actual);
            }
            allPassed = false;
            break;
        }
    }

    if (allPassed) {
        consoleLog('\n=== Все тесты пройдены! ===', 'success');

        // Отмечаем задание как выполненное
        try {
            const response = await fetch(`/student/task/${taskId}/complete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });

            if (response.ok) {
                // Блокируем редактор
                editor.setOption('readOnly', true);
                runBtn.disabled = true;
                checkBtn.disabled = true;

                // Показываем уведомление
                const alert = document.createElement('div');
                alert.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-3';
                alert.innerHTML = `
                    <div class="alert alert-success shadow">
                        <i class="bi bi-check-circle-fill"></i> Задание выполнено!
                    </div>
                `;
                document.body.appendChild(alert);
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    }
});

// Автосохранение при изменении
let saveTimeout;
editor.on('change', () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveCode, 2000);
});

// Загрузка Pyodide при старте
loadPyodideAndPackages();
