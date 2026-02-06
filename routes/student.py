from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from models import db, Student, LessonAssignment, StudentProgress, Task
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
    tasks_data = []

    for task in lesson.tasks:
        progress = StudentProgress.query.filter_by(
            student_id=current_user.id, task_id=task.id
        ).first()
        tasks_data.append({
            'task': task,
            'is_completed': progress.is_completed if progress else False
        })

    return render_template('student/lesson.html', lesson=lesson, tasks_data=tasks_data)


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

    # Получаем прогресс
    progress = StudentProgress.query.filter_by(
        student_id=current_user.id, task_id=task_id
    ).first()

    # Получаем соседние задания
    all_tasks = lesson.tasks
    current_index = next((i for i, t in enumerate(all_tasks) if t.id == task_id), 0)
    prev_task = all_tasks[current_index - 1] if current_index > 0 else None
    next_task = all_tasks[current_index + 1] if current_index < len(all_tasks) - 1 else None

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
