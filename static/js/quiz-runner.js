// Множество правильно отвеченных вопросов
const answeredCorrectly = new Set(answeredIds || []);

// Змейка-маскот
function showSnake(imageName) {
    const img = document.createElement('img');
    img.src = `/static/imgs/snakes/${imageName}`;
    img.className = 'snake-bounce';
    img.alt = '';
    document.body.appendChild(img);
    img.addEventListener('animationend', () => img.remove());
}

// Отключить inputs для вопроса
function disableQuestion(elementId) {
    const container = document.getElementById('element-' + elementId);
    if (!container) return;
    container.querySelectorAll('input').forEach(i => i.disabled = true);
    const btn = container.querySelector('.check-answer-btn');
    if (btn) btn.disabled = true;
}

// Обработчик кнопок "Ответить"
document.querySelectorAll('.check-answer-btn').forEach(btn => {
    btn.addEventListener('click', async function() {
        const elementId = parseInt(this.dataset.elementId);
        const type = this.dataset.type;
        let answer;

        if (type === 'single_choice') {
            const checked = document.querySelector('input[name="q_' + elementId + '"]:checked');
            if (!checked) return;
            answer = parseInt(checked.value);
        } else if (type === 'multiple_choice') {
            const checked = document.querySelectorAll('input[name="q_' + elementId + '"]:checked');
            if (checked.length === 0) return;
            answer = Array.from(checked).map(el => parseInt(el.value));
        } else if (type === 'text_input') {
            const input = document.getElementById('input_' + elementId);
            if (!input || !input.value.trim()) return;
            answer = input.value;
        }

        try {
            const response = await fetch('/student/task/' + taskId + '/quiz/check', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({element_id: elementId, answer: answer})
            });
            const result = await response.json();
            const feedbackEl = document.getElementById('feedback-' + elementId);

            if (result.correct) {
                feedbackEl.innerHTML = '<span class="text-success"><i class="bi bi-check-circle-fill"></i> Правильно!</span>';
                disableQuestion(elementId);
                answeredCorrectly.add(elementId);

                // Проверяем, все ли вопросы отвечены
                if (answeredCorrectly.size === totalQuestions) {
                    await completeQuiz();
                    showSnake('happy.png');
                }
            } else {
                feedbackEl.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle-fill"></i> Неправильно. Попробуйте ещё раз.</span>';
                showSnake('thinking.png');
            }
        } catch (error) {
            console.error('Ошибка:', error);
        }
    });
});

async function completeQuiz() {
    try {
        const response = await fetch('/student/task/' + taskId + '/quiz/complete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });

        if (response.ok) {
            // Блокируем все оставшиеся inputs
            document.querySelectorAll('.check-answer-btn').forEach(b => b.disabled = true);
            document.querySelectorAll('.quiz-question-card input').forEach(i => i.disabled = true);

            // Показываем уведомление
            const alert = document.createElement('div');
            alert.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-3';
            alert.innerHTML = '<div class="alert alert-success shadow"><i class="bi bi-check-circle-fill"></i> Тест пройден!</div>';
            document.body.appendChild(alert);
        }
    } catch (error) {
        console.error('Ошибка:', error);
    }
}
