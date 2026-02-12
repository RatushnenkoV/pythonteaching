// Python ключевые слова и встроенные функции для автодополнения
const pythonKeywords = [
    // Ключевые слова
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
    'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from',
    'global', 'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not',
    'or', 'pass', 'raise', 'return', 'try', 'while', 'with', 'yield',
    'True', 'False', 'None',
    // Встроенные функции
    'print', 'input', 'len', 'range', 'int', 'str', 'float', 'bool',
    'list', 'dict', 'set', 'tuple', 'type', 'abs', 'max', 'min', 'sum',
    'round', 'sorted', 'reversed', 'enumerate', 'zip', 'map', 'filter',
    'open', 'format', 'chr', 'ord', 'hex', 'bin', 'oct', 'pow', 'divmod',
    'isinstance', 'issubclass', 'hasattr', 'getattr', 'setattr', 'delattr',
    'callable', 'iter', 'next', 'slice', 'super', 'property', 'staticmethod',
    'classmethod', 'vars', 'dir', 'help', 'id', 'hash', 'repr', 'ascii',
    'all', 'any', 'eval', 'exec', 'compile', 'globals', 'locals',
    // Методы строк
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'index',
    'count', 'sort', 'reverse', 'copy', 'join', 'split', 'strip',
    'lstrip', 'rstrip', 'replace', 'find', 'rfind', 'upper', 'lower',
    'capitalize', 'title', 'startswith', 'endswith', 'isdigit', 'isalpha',
    'isalnum', 'isspace', 'isupper', 'islower', 'center', 'ljust', 'rjust',
    'zfill', 'format', 'encode', 'decode', 'keys', 'values', 'items',
    'get', 'update', 'add', 'discard', 'union', 'intersection', 'difference'
];

// Функция автодополнения для Python
function pythonHint(cm) {
    const cursor = cm.getCursor();
    const token = cm.getTokenAt(cursor);
    const start = token.start;
    const end = cursor.ch;
    const currentWord = token.string.slice(0, end - start);

    if (currentWord.length < 1) return null;

    // Собираем слова из документа (переменные пользователя)
    const docWords = new Set();
    const content = cm.getValue();
    const wordRegex = /[a-zA-Z_][a-zA-Z0-9_]*/g;
    let match;
    while ((match = wordRegex.exec(content)) !== null) {
        if (match[0] !== currentWord && match[0].length > 1) {
            docWords.add(match[0]);
        }
    }

    // Объединяем Python слова и слова из документа
    const allWords = [...new Set([...pythonKeywords, ...docWords])];

    // Фильтруем по текущему вводу
    const filtered = allWords.filter(word =>
        word.toLowerCase().startsWith(currentWord.toLowerCase()) && word !== currentWord
    );

    if (filtered.length === 0) return null;

    // Сортируем: сначала точные совпадения по регистру, потом остальные
    filtered.sort((a, b) => {
        const aStarts = a.startsWith(currentWord);
        const bStarts = b.startsWith(currentWord);
        if (aStarts && !bStarts) return -1;
        if (!aStarts && bStarts) return 1;
        return a.localeCompare(b);
    });

    return {
        list: filtered.slice(0, 10), // Максимум 10 подсказок
        from: CodeMirror.Pos(cursor.line, start),
        to: CodeMirror.Pos(cursor.line, end)
    };
}

// Инициализация редактора CodeMirror
const editor = CodeMirror.fromTextArea(document.getElementById('code'), {
    mode: 'python',
    theme: 'monokai',
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    autoCloseBrackets: true,
    hintOptions: { hint: pythonHint, completeSingle: false },
    extraKeys: {
        'Tab': function(cm) {
            cm.replaceSelection('    ', 'end');
        },
        'Ctrl-Space': 'autocomplete'
    },
    readOnly: isCompleted
});

// Автоматически показывать подсказки при вводе
editor.on('inputRead', (cm, change) => {
    if (change.origin === '+input' && /[a-zA-Z_]/.test(change.text[0])) {
        const cursor = cm.getCursor();
        const token = cm.getTokenAt(cursor);
        // Показывать подсказки только если введено минимум 2 символа
        if (token.string.length >= 2) {
            cm.showHint({ completeSingle: false });
        }
    }
});

// Обрамление выделенного текста скобками/кавычками
const bracketPairs = {
    '(': ')',
    '[': ']',
    '{': '}',
    '"': '"',
    "'": "'"
};

editor.on('beforeChange', (cm, change) => {
    if (change.origin === '+input' && change.text.length === 1) {
        const char = change.text[0];
        if (bracketPairs[char] && cm.somethingSelected()) {
            const selections = cm.getSelections();
            const newSelections = selections.map(sel => char + sel + bracketPairs[char]);
            cm.replaceSelections(newSelections);
            change.cancel();
        }
    }
});

const consoleEl = document.getElementById('console');
const consoleInputLine = document.getElementById('consoleInputLine');
const consoleInput = document.getElementById('consoleInput');
const consolePrompt = document.getElementById('consolePrompt');
const runBtn = document.getElementById('runBtn');
const checkBtn = document.getElementById('checkBtn');

// Web Worker для выполнения Python
let pyodideWorker = null;
let pyodideReady = false;
let workerResolve = null; // Callback для результата от воркера
let inputResolve = null; // Для асинхронного ввода

// Таймаут для выполнения кода (в миллисекундах)
const EXECUTION_TIMEOUT = 5000;

// Создание нового воркера
function createWorker() {
    if (pyodideWorker) {
        pyodideWorker.terminate();
    }

    pyodideWorker = new Worker('/static/js/pyodide-worker.js');
    pyodideReady = false;

    pyodideWorker.onmessage = function(e) {
        const { type, output, error } = e.data;

        if (type === 'ready') {
            pyodideReady = true;
            consoleLog('Python готов к работе!', 'success');
        } else if (type === 'result' || type === 'error') {
            if (workerResolve) {
                workerResolve({ output: output || '', error: error || null });
                workerResolve = null;
            }
        }
    };

    pyodideWorker.onerror = function(e) {
        console.error('Worker error:', e);
        if (workerResolve) {
            workerResolve({ output: '', error: 'Ошибка выполнения' });
            workerResolve = null;
        }
    };

    // Инициализируем Pyodide в воркере
    pyodideWorker.postMessage({ type: 'init' });
}

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

// Загрузка Pyodide через Web Worker
function loadPyodideAndPackages() {
    consoleLog('Загрузка Python...', 'info');
    createWorker();
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

// Запуск Python кода с заданными входными данными (через Web Worker)
async function runPythonCode(code, inputs = [], timeout = EXECUTION_TIMEOUT) {
    if (!pyodideReady) {
        return { output: '', error: 'Python ещё загружается...' };
    }

    return new Promise((resolve) => {
        let timeoutId;
        let resolved = false;

        // Устанавливаем callback для результата
        workerResolve = (result) => {
            if (!resolved) {
                resolved = true;
                clearTimeout(timeoutId);
                resolve(result);
            }
        };

        // Таймаут - прерываем воркер и создаём новый
        timeoutId = setTimeout(() => {
            if (!resolved) {
                resolved = true;
                workerResolve = null;

                // Прерываем зависший воркер
                consoleLog('Прерывание выполнения...', 'info');
                createWorker(); // Это terminate() старый и создаст новый

                resolve({
                    output: '',
                    error: 'Превышено время выполнения (5 секунд). Программа была прервана.\nВозможно, она зациклилась. Проверьте условия циклов while и for.',
                    timeout: true
                });
            }
        }, timeout);

        // Отправляем код на выполнение
        pyodideWorker.postMessage({ type: 'run', code, inputs });
    });
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

// Ожидание готовности Python (после перезагрузки воркера)
async function waitForPyodide() {
    if (pyodideReady) return true;

    return new Promise((resolve) => {
        const checkInterval = setInterval(() => {
            if (pyodideReady) {
                clearInterval(checkInterval);
                resolve(true);
            }
        }, 100);

        // Максимум 30 секунд ожидания
        setTimeout(() => {
            clearInterval(checkInterval);
            resolve(pyodideReady);
        }, 30000);
    });
}

// Кнопка "Запустить"
runBtn.addEventListener('click', async () => {
    clearConsole();
    hideInputLine();

    if (!pyodideReady) {
        consoleLog('Python загружается, подождите...', 'info');
        await waitForPyodide();
        if (!pyodideReady) {
            consoleLog('Не удалось загрузить Python. Обновите страницу.', 'error');
            return;
        }
        clearConsole();
    }

    const code = editor.getValue();
    await saveCode();

    // Собираем входные данные интерактивно
    const inputs = await collectInputsInteractively(code);

    if (inputs.length > 0) {
        consoleLog('', ''); // Пустая строка
    }

    consoleLog('Выполнение...', 'info');
    const result = await runPythonCode(code, inputs);

    // Если был таймаут, ждём перезагрузки Python
    if (result.timeout) {
        clearConsole();
        consoleLog(result.error, 'error');
        consoleLog('\nПерезагрузка Python...', 'info');
        await waitForPyodide();
        consoleLog('Python готов. Исправьте код и попробуйте снова.', 'success');
    } else if (result.error) {
        // Убираем "Выполнение..." перед выводом ошибки
        if (consoleEl.lastChild) consoleEl.lastChild.remove();
        consoleLog(result.error, 'error');
    } else {
        // Убираем "Выполнение..." перед выводом результата
        if (consoleEl.lastChild) consoleEl.lastChild.remove();
        consoleLog(result.output || '(нет вывода)');
    }
});

// Кнопка "Проверить"
checkBtn.addEventListener('click', async () => {
    clearConsole();
    hideInputLine();

    if (!pyodideReady) {
        consoleLog('Python загружается, подождите...', 'info');
        await waitForPyodide();
        if (!pyodideReady) {
            consoleLog('Не удалось загрузить Python. Обновите страницу.', 'error');
            return;
        }
        clearConsole();
    }

    if (tests.length === 0) {
        consoleLog('Нет тестов для проверки', 'info');
        return;
    }

    consoleLog('Проверка решения...', 'info');

    const code = editor.getValue();

    // Проверяем, не совпадает ли код с вставленным текстом
    const isCopied = lastPastedText && code.trim() === lastPastedText.trim();
    if (isCopied) {
        showCheatingWarning();
        showSnake('stressed.png');
    }

    await saveCode();

    let allPassed = true;

    for (let i = 0; i < tests.length; i++) {
        const test = tests[i];
        const isHidden = test.hidden;
        const testInputs = test.input ? test.input.split('\n') : [];

        consoleLog(`\nТест ${i + 1}${isHidden ? ' (скрытый)' : ''}:`, 'info');

        const result = await runPythonCode(code, testInputs);

        // Если был таймаут, прерываем проверку и ждём перезагрузки
        if (result.timeout) {
            consoleLog(result.error, 'error');
            consoleLog('\nПерезагрузка Python...', 'info');
            await waitForPyodide();
            consoleLog('Python готов. Исправьте код и попробуйте снова.', 'success');
            return;
        }

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

    if (!allPassed) {
        showSnake('thinking.png');
    }

    if (allPassed) {
        consoleLog('\n=== Все тесты пройдены! ===', 'success');
        if (!isCopied) {
            showSnake('happy.png');
        }

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
                if (isCopied) {
                    alert.innerHTML = `
                        <div class="alert alert-warning shadow">
                            <i class="bi bi-exclamation-triangle-fill"></i> Задача выполнена копированием
                        </div>
                    `;
                } else {
                    alert.innerHTML = `
                        <div class="alert alert-success shadow">
                            <i class="bi bi-check-circle-fill"></i> Задание выполнено!
                        </div>
                    `;
                }
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

// ===== Змейка-маскот =====
function showSnake(imageName) {
    const img = document.createElement('img');
    img.src = `/static/imgs/snakes/${imageName}`;
    img.className = 'snake-bounce';
    img.alt = '';
    document.body.appendChild(img);
    img.addEventListener('animationend', () => img.remove());
}

// ===== Отслеживание активности ученика =====
const PASTE_THRESHOLD = 15;
let lastPastedText = null;

function showPasteWarning() {
    const existing = document.getElementById('pasteWarning');
    if (existing) existing.remove();

    const warning = document.createElement('div');
    warning.id = 'pasteWarning';
    warning.className = 'position-fixed top-0 end-0 m-3';
    warning.style.zIndex = '9999';
    warning.innerHTML = `
        <div class="alert alert-warning shadow-sm d-flex align-items-center" role="alert">
            <i class="bi bi-clipboard-check me-2"></i>
            <div>
                <strong>Вставка обнаружена</strong><br>
                <small>Учитель увидит это в журнале</small>
            </div>
        </div>
    `;
    document.body.appendChild(warning);
    setTimeout(() => warning.remove(), 4000);
}

function showCheatingWarning() {
    const existing = document.getElementById('cheatingWarning');
    if (existing) existing.remove();

    const warning = document.createElement('div');
    warning.id = 'cheatingWarning';
    warning.className = 'position-fixed top-0 end-0 m-3';
    warning.style.zIndex = '9999';
    warning.innerHTML = `
        <div class="alert alert-danger shadow-sm d-flex align-items-center" role="alert">
            <i class="bi bi-emoji-frown me-2"></i>
            <div>
                <strong>Списывать не хорошо</strong><br>
                <small>Попробуйте решить задание самостоятельно</small>
            </div>
        </div>
    `;
    document.body.appendChild(warning);
    setTimeout(() => warning.remove(), 5000);
}

async function recordActivity(eventType, textContent = null) {
    try {
        await fetch(`/student/task/${taskId}/activity`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event_type: eventType, text_content: textContent })
        });
    } catch (error) {
        console.error('Ошибка записи активности:', error);
    }
}

// Отслеживание вставки в редактор
editor.on('beforeChange', (cm, change) => {
    if (change.origin === 'paste') {
        const pastedText = change.text.join('\n');
        if (pastedText.length >= PASTE_THRESHOLD && !isCompleted) {
            lastPastedText = pastedText;
            showPasteWarning();
            recordActivity('paste', pastedText);
        }
    }
});

// Отслеживание копирования из описания задания
const descriptionEl = document.querySelector('.task-description');
if (descriptionEl) {
    descriptionEl.addEventListener('copy', () => {
        if (isCompleted) return;
        const selectedText = window.getSelection().toString();
        if (selectedText.length > 0) {
            recordActivity('copy', selectedText);
        }
    });
}

// Отслеживание ухода со страницы (переключение вкладки)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && !isCompleted) {
        recordActivity('leave');
    }
});

// Загрузка Pyodide при старте
loadPyodideAndPackages();
