from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from models import db, Student, LessonAssignment, StudentProgress, Task, QuizElement, QuizOption, QuizAnswer
from functools import wraps
from datetime import datetime

student_bp = Blueprint('student', __name__)


def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not isinstance(current_user, Student):
            flash('Доступ только для учеников', 'error')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function


@student_bp.route('/')
@login_required
@student_required
def dashboard():
    # Получаем уроки, назначенные классу ученика
    assignments = LessonAssignment.query.filter_by(class_id=current_user.class_id).all()
    lessons_data = []

    for assignment in assignments:
        lesson = assignment.lesson
        tasks = lesson.tasks
        total_tasks = len(tasks)

        # Считаем выполненные задания
        completed_tasks = 0
        for task in tasks:
            progress = StudentProgress.query.filter_by(
                student_id=current_user.id, task_id=task.id
            ).first()
            if progress and progress.is_completed:
                completed_tasks += 1

        lessons_data.append({
            'lesson': lesson,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks
        })

    return render_template('student/dashboard.html', lessons_data=lessons_data)


@student_bp.route('/lesson/<int:lesson_id>')
@login_required
@student_required
def lesson(lesson_id):
    # Проверяем, что урок назначен классу ученика
    assignment = LessonAssignment.query.filter_by(
        lesson_id=lesson_id, class_id=current_user.class_id
    ).first()

    if not assignment:
        flash('Урок не доступен', 'error')
        return redirect(url_for('student.dashboard'))

    lesson = assignment.lesson

    regular_tasks = []
    bonus_tasks = []

    all_regular_completed = True
    for task in lesson.tasks:
        progress = StudentProgress.query.filter_by(
            student_id=current_user.id, task_id=task.id
        ).first()
        item = {
            'task': task,
            'is_completed': progress.is_completed if progress else False
        }
        if task.is_bonus:
            bonus_tasks.append(item)
        else:
            regular_tasks.append(item)
            if not item['is_completed']:
                all_regular_completed = False

    return render_template('student/lesson.html',
                           lesson=lesson,
                           regular_tasks=regular_tasks,
                           bonus_tasks=bonus_tasks,
                           show_bonus=all_regular_completed and len(regular_tasks) > 0)


@student_bp.route('/task/<int:task_id>')
@login_required
@student_required
def task(task_id):
    task = Task.query.get_or_404(task_id)
    lesson = task.lesson

    # Проверяем доступ
    assignment = LessonAssignment.query.filter_by(
        lesson_id=lesson.id, class_id=current_user.class_id
    ).first()

    if not assignment:
        flash('Задание не доступно', 'error')
        return redirect(url_for('student.dashboard'))

    # Проверяем доступ к бонусным заданиям
    if task.is_bonus:
        all_regular = [t for t in lesson.tasks if not t.is_bonus]
        all_regular_done = all(
            StudentProgress.query.filter_by(
                student_id=current_user.id, task_id=t.id, is_completed=True
            ).first() is not None
            for t in all_regular
        ) if all_regular else True
        if not all_regular_done:
            flash('Сначала выполните все основные задания', 'error')
            return redirect(url_for('student.lesson', lesson_id=lesson.id))

    # Получаем прогресс
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id, task_id=task_id
    ).first()

    # Получаем соседние задания
    all_tasks = lesson.tasks
    current_index = next((i for i, t in enumerate(all_tasks) if t.id == task_id), 0)
    prev_task = all_tasks[current_index - 1] if current_index > 0 else None
    next_task = all_tasks[current_index + 1] if current_index < len(all_tasks) - 1 else None

    # Проверяем доступность следующего задания
    next_task_available = True
    if next_task and next_task.is_bonus:
        regular_tasks = [t for t in all_tasks if not t.is_bonus]
        next_task_available = all(
            StudentProgress.query.filter_by(
                student_id=current_user.id, task_id=t.id, is_completed=True
            ).first() is not None
            for t in regular_tasks
        ) if regular_tasks else True

    if task.task_type == 'quiz':
        # Считаем количество вопросов (не текстовых блоков)
        question_ids = [e.id for e in task.quiz_elements if e.element_type != 'text']
        question_count = len(question_ids)

        # Получаем уже отвеченные вопросы
        answered = QuizAnswer.query.filter(
            QuizAnswer.student_id == current_user.id,
            QuizAnswer.element_id.in_(question_ids),
            QuizAnswer.is_correct == True
        ).all() if question_ids else []
        answered_ids = [a.element_id for a in answered]

        return render_template('student/quiz.html',
                               task=task,
                               lesson=lesson,
                               progress=progress,
                               prev_task=prev_task,
                               next_task=next_task,
                               next_task_available=next_task_available,
                               current_index=current_index + 1,
                               total_tasks=len(all_tasks),
                               question_count=question_count,
                               answered_ids=answered_ids)

    # Получаем тесты для задания (скрываем данные скрытых тестов)
    tests = []
    for tc in task.test_cases:
        if tc.is_hidden:
            tests.append({'input': tc.input_data, 'output': tc.expected_output, 'hidden': True})
        else:
            tests.append({'input': tc.input_data, 'output': tc.expected_output, 'hidden': False})

    return render_template('student/task.html',
                           task=task,
                           lesson=lesson,
                           progress=progress,
                           prev_task=prev_task,
                           next_task=next_task,
                           next_task_available=next_task_available,
                           tests=tests,
                           current_index=current_index + 1,
                           total_tasks=len(all_tasks))


@student_bp.route('/task/<int:task_id>/save', methods=['POST'])
@login_required
@student_required
def save_code(task_id):
    task = Task.query.get_or_404(task_id)
    lesson = task.lesson

    # Проверяем доступ
    assignment = LessonAssignment.query.filter_by(
        lesson_id=lesson.id, class_id=current_user.class_id
    ).first()

    if not assignment:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    # Получаем или создаём прогресс
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id, task_id=task_id
    ).first()

    if progress and progress.is_completed:
        return jsonify({'success': False, 'error': 'Задание уже выполнено'}), 400

    code = request.json.get('code', '')

    if not progress:
        progress = StudentProgress(student_id=current_user.id, task_id=task_id, code=code)
        db.session.add(progress)
    else:
        progress.code = code

    db.session.commit()
    return jsonify({'success': True})


@student_bp.route('/task/<int:task_id>/complete', methods=['POST'])
@login_required
@student_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    lesson = task.lesson

    # Проверяем доступ
    assignment = LessonAssignment.query.filter_by(
        lesson_id=lesson.id, class_id=current_user.class_id
    ).first()

    if not assignment:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    code = request.json.get('code', '')

    # Получаем или создаём прогресс
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id, task_id=task_id
    ).first()

    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            task_id=task_id,
            code=code,
            is_completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(progress)
    else:
        progress.code = code
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'success': True})


@student_bp.route('/task/<int:task_id>/quiz/check', methods=['POST'])
@login_required
@student_required
def quiz_check(task_id):
    task = Task.query.get_or_404(task_id)
    lesson = task.lesson

    assignment = LessonAssignment.query.filter_by(
        lesson_id=lesson.id, class_id=current_user.class_id
    ).first()
    if not assignment:
        return jsonify({'correct': False, 'error': 'Нет доступа'}), 403

    data = request.get_json()
    element_id = data.get('element_id')
    answer = data.get('answer')

    element = QuizElement.query.get_or_404(element_id)
    if element.task_id != task_id:
        return jsonify({'correct': False, 'error': 'Неверный элемент'}), 400

    correct = False

    if element.element_type == 'single_choice':
        option = QuizOption.query.get(answer)
        if option and option.element_id == element_id:
            correct = option.is_correct

    elif element.element_type == 'multiple_choice':
        if isinstance(answer, list):
            selected = set(answer)
            correct_ids = {opt.id for opt in element.options if opt.is_correct}
            correct = selected == correct_ids
        else:
            correct = False

    elif element.element_type == 'text_input':
        if element.correct_answer and isinstance(answer, str):
            correct = answer.strip().lower() == element.correct_answer.strip().lower()

    # Сохраняем ответ по вопросу
    quiz_answer = QuizAnswer.query.filter_by(
        student_id=current_user.id, element_id=element_id
    ).first()

    if not quiz_answer:
        quiz_answer = QuizAnswer(
            student_id=current_user.id,
            element_id=element_id,
            is_correct=correct,
            had_errors=not correct
        )
        db.session.add(quiz_answer)
    else:
        if correct:
            quiz_answer.is_correct = True
        else:
            quiz_answer.had_errors = True

    # Обновляем общий прогресс если неверно
    if not correct:
        progress = StudentProgress.query.filter_by(
            student_id=current_user.id, task_id=task_id
        ).first()
        if not progress:
            progress = StudentProgress(student_id=current_user.id, task_id=task_id, has_errors=True)
            db.session.add(progress)
        else:
            progress.has_errors = True

    db.session.commit()
    return jsonify({'correct': correct})


@student_bp.route('/task/<int:task_id>/quiz/complete', methods=['POST'])
@login_required
@student_required
def quiz_complete(task_id):
    task = Task.query.get_or_404(task_id)
    lesson = task.lesson

    assignment = LessonAssignment.query.filter_by(
        lesson_id=lesson.id, class_id=current_user.class_id
    ).first()
    if not assignment:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403

    progress = StudentProgress.query.filter_by(
        student_id=current_user.id, task_id=task_id
    ).first()

    if not progress:
        progress = StudentProgress(
            student_id=current_user.id,
            task_id=task_id,
            is_completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(progress)
    else:
        progress.is_completed = True
        progress.completed_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'success': True})
