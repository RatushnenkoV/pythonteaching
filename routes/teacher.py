from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from models import db, Teacher, SchoolClass, Student, Topic, Lesson, Task, TestCase, LessonAssignment, StudentProgress
from utils.login_generator import generate_unique_login
from functools import wraps

teacher_bp = Blueprint('teacher', __name__)


def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not isinstance(current_user, Teacher):
            flash('Доступ только для учителей', 'error')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function


@teacher_bp.route('/')
@login_required
@teacher_required
def dashboard():
    classes = SchoolClass.query.filter_by(teacher_id=current_user.id).all()
    topics = Topic.query.filter_by(teacher_id=current_user.id, parent_id=None).all()
    return render_template('teacher/dashboard.html', classes=classes, topics=topics)


# ==================== КЛАССЫ ====================

@teacher_bp.route('/classes')
@login_required
@teacher_required
def classes():
    classes = SchoolClass.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/classes.html', classes=classes)


@teacher_bp.route('/classes/create', methods=['POST'])
@login_required
@teacher_required
def create_class():
    name = request.form.get('name')
    if name:
        school_class = SchoolClass(name=name, teacher_id=current_user.id)
        db.session.add(school_class)
        db.session.commit()
        flash('Класс создан', 'success')
    return redirect(url_for('teacher.classes'))


@teacher_bp.route('/classes/<int:class_id>')
@login_required
@teacher_required
def class_detail(class_id):
    school_class = SchoolClass.query.get_or_404(class_id)
    if school_class.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.classes'))
    return render_template('teacher/class_detail.html', school_class=school_class)


@teacher_bp.route('/classes/<int:class_id>/edit', methods=['POST'])
@login_required
@teacher_required
def edit_class(class_id):
    school_class = SchoolClass.query.get_or_404(class_id)
    if school_class.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.classes'))

    name = request.form.get('name')
    if name:
        school_class.name = name
        db.session.commit()
        flash('Класс обновлён', 'success')
    return redirect(url_for('teacher.class_detail', class_id=class_id))


@teacher_bp.route('/classes/<int:class_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_class(class_id):
    school_class = SchoolClass.query.get_or_404(class_id)
    if school_class.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.classes'))

    db.session.delete(school_class)
    db.session.commit()
    flash('Класс удалён', 'success')
    return redirect(url_for('teacher.classes'))


@teacher_bp.route('/classes/<int:class_id>/add_students', methods=['POST'])
@login_required
@teacher_required
def add_students(class_id):
    school_class = SchoolClass.query.get_or_404(class_id)
    if school_class.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.classes'))

    names_text = request.form.get('names', '')
    names = [name.strip() for name in names_text.split('\n') if name.strip()]

    if names:
        existing_logins = [s.login.lower() for s in Student.query.all()]
        added = []
        for name in names:
            login = generate_unique_login(existing_logins)
            existing_logins.append(login.lower())
            student = Student(login=login, name=name, class_id=class_id)
            db.session.add(student)
            added.append(f'{name} ({login})')

        db.session.commit()
        flash(f'Добавлено учеников: {len(added)}', 'success')

    return redirect(url_for('teacher.class_detail', class_id=class_id))


@teacher_bp.route('/classes/<int:class_id>/import_students', methods=['POST'])
@login_required
@teacher_required
def import_students(class_id):
    school_class = SchoolClass.query.get_or_404(class_id)
    if school_class.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.classes'))

    file = request.files.get('file')
    if not file:
        flash('Файл не выбран', 'error')
        return redirect(url_for('teacher.class_detail', class_id=class_id))

    names = []
    try:
        content = file.read().decode('utf-8-sig')  # utf-8-sig для Excel CSV
    except:
        try:
            file.seek(0)
            content = file.read().decode('cp1251')  # Windows кодировка
        except:
            flash('Не удалось прочитать файл', 'error')
            return redirect(url_for('teacher.class_detail', class_id=class_id))

    # Парсим содержимое
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        # Разделители: запятая, точка с запятой, табуляция
        for sep in [';', ',', '\t']:
            if sep in line:
                parts = line.split(sep)
                for part in parts:
                    part = part.strip().strip('"').strip("'")
                    if part and len(part) > 2:
                        names.append(part)
                break
        else:
            # Если разделителей нет - вся строка это ФИО
            if len(line) > 2:
                names.append(line)

    if names:
        existing_logins = [s.login.lower() for s in Student.query.all()]
        added = 0
        for name in names:
            login = generate_unique_login(existing_logins)
            existing_logins.append(login.lower())
            student = Student(login=login, name=name, class_id=class_id)
            db.session.add(student)
            added += 1

        db.session.commit()
        flash(f'Импортировано учеников: {added}', 'success')
    else:
        flash('Не удалось найти имена в файле', 'error')

    return redirect(url_for('teacher.class_detail', class_id=class_id))


@teacher_bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    class_id = student.class_id
    school_class = SchoolClass.query.get(class_id)

    if school_class.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.classes'))

    db.session.delete(student)
    db.session.commit()
    flash('Ученик удалён', 'success')
    return redirect(url_for('teacher.class_detail', class_id=class_id))


# ==================== ТЕМЫ И УРОКИ ====================

@teacher_bp.route('/lessons')
@login_required
@teacher_required
def lessons():
    class_id = request.args.get('class_id', type=int)
    topic_id = request.args.get('topic_id', type=int)

    # Если выбрана тема - показываем содержимое темы
    if topic_id:
        topic = Topic.query.get_or_404(topic_id)
        if topic.teacher_id != current_user.id:
            flash('Нет доступа', 'error')
            return redirect(url_for('teacher.lessons'))
        topics = topic.children
        lessons_list = topic.lessons
        parent = topic
        selected_class = topic.school_class
        breadcrumbs = []
        current = topic
        while current:
            breadcrumbs.insert(0, current)
            current = current.parent
        return render_template('teacher/lessons.html',
                               topics=topics,
                               lessons=lessons_list,
                               parent=parent,
                               selected_class=selected_class,
                               breadcrumbs=breadcrumbs,
                               classes=None,
                               view_mode='topics')

    # Если выбран класс - показываем темы этого класса и назначенные уроки
    if class_id:
        selected_class = SchoolClass.query.get_or_404(class_id)
        if selected_class.teacher_id != current_user.id:
            flash('Нет доступа', 'error')
            return redirect(url_for('teacher.lessons'))
        topics = Topic.query.filter_by(teacher_id=current_user.id, class_id=class_id, parent_id=None).all()
        return render_template('teacher/lessons.html',
                               topics=topics,
                               lessons=[],
                               parent=None,
                               selected_class=selected_class,
                               breadcrumbs=[],
                               classes=None,
                               view_mode='topics')

    # Иначе показываем список классов
    classes = SchoolClass.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/lessons.html',
                           topics=[],
                           lessons=[],
                           parent=None,
                           selected_class=None,
                           breadcrumbs=[],
                           classes=classes,
                           view_mode='classes')


@teacher_bp.route('/topics/create', methods=['POST'])
@login_required
@teacher_required
def create_topic():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id', type=int)
    class_id = request.form.get('class_id', type=int)

    if name and class_id:
        # Проверяем доступ к классу
        school_class = SchoolClass.query.get(class_id)
        if school_class and school_class.teacher_id == current_user.id:
            topic = Topic(name=name, parent_id=parent_id, class_id=class_id, teacher_id=current_user.id)
            db.session.add(topic)
            db.session.commit()
            flash('Тема создана', 'success')

    if parent_id:
        return redirect(url_for('teacher.lessons', topic_id=parent_id))
    if class_id:
        return redirect(url_for('teacher.lessons', class_id=class_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/topics/<int:topic_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if topic.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    parent_id = topic.parent_id
    class_id = topic.class_id
    db.session.delete(topic)
    db.session.commit()
    flash('Тема удалена', 'success')

    if parent_id:
        return redirect(url_for('teacher.lessons', topic_id=parent_id))
    if class_id:
        return redirect(url_for('teacher.lessons', class_id=class_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/lessons/create', methods=['POST'])
@login_required
@teacher_required
def create_lesson():
    title = request.form.get('title')
    topic_id = request.form.get('topic_id', type=int)

    if title and topic_id:
        topic = Topic.query.get(topic_id)
        if topic and topic.teacher_id == current_user.id:
            lesson = Lesson(title=title, topic_id=topic_id, teacher_id=current_user.id)
            db.session.add(lesson)
            db.session.commit()
            flash('Урок создан', 'success')
            return redirect(url_for('teacher.lesson_edit', lesson_id=lesson.id))

    return redirect(url_for('teacher.lessons', topic_id=topic_id))


@teacher_bp.route('/lessons/import', methods=['POST'])
@login_required
@teacher_required
def import_lessons():
    import json
    topic_id = request.form.get('topic_id', type=int)

    if not topic_id:
        flash('Выберите тему для импорта', 'error')
        return redirect(url_for('teacher.lessons'))

    topic = Topic.query.get(topic_id)
    if not topic or topic.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    file = request.files.get('file')
    if not file:
        flash('Файл не выбран', 'error')
        return redirect(url_for('teacher.lessons', topic_id=topic_id))

    try:
        content = file.read().decode('utf-8')
        data = json.loads(content)
    except Exception as e:
        flash(f'Ошибка чтения файла: {str(e)}', 'error')
        return redirect(url_for('teacher.lessons', topic_id=topic_id))

    lessons_data = data.get('lessons', [])
    if not lessons_data:
        flash('В файле нет уроков для импорта', 'error')
        return redirect(url_for('teacher.lessons', topic_id=topic_id))

    imported_count = 0
    for lesson_data in lessons_data:
        title = lesson_data.get('title', 'Без названия')
        lesson = Lesson(title=title, topic_id=topic_id, teacher_id=current_user.id)
        db.session.add(lesson)
        db.session.flush()  # Получаем ID урока

        tasks_data = lesson_data.get('tasks', [])
        for order, task_data in enumerate(tasks_data, 1):
            task = Task(
                lesson_id=lesson.id,
                title=task_data.get('title', 'Без названия'),
                description=task_data.get('description', ''),
                default_code=task_data.get('default_code', None),
                order=order
            )
            db.session.add(task)
            db.session.flush()  # Получаем ID задания

            tests_data = task_data.get('tests', [])
            for test_order, test_data in enumerate(tests_data, 1):
                test = TestCase(
                    task_id=task.id,
                    input_data=test_data.get('input', ''),
                    expected_output=test_data.get('output', ''),
                    is_hidden=test_data.get('hidden', False),
                    order=test_order
                )
                db.session.add(test)

        imported_count += 1

    db.session.commit()
    flash(f'Импортировано уроков: {imported_count}', 'success')
    return redirect(url_for('teacher.lessons', topic_id=topic_id))


@teacher_bp.route('/lessons/<int:lesson_id>')
@login_required
@teacher_required
def lesson_edit(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    classes = SchoolClass.query.filter_by(teacher_id=current_user.id).all()
    assigned_class_ids = [a.class_id for a in lesson.assignments]

    return render_template('teacher/lesson_edit.html',
                           lesson=lesson,
                           classes=classes,
                           assigned_class_ids=assigned_class_ids)


@teacher_bp.route('/lessons/<int:lesson_id>/edit', methods=['POST'])
@login_required
@teacher_required
def update_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    title = request.form.get('title')
    if title:
        lesson.title = title
        db.session.commit()
        flash('Урок обновлён', 'success')

    return redirect(url_for('teacher.lesson_edit', lesson_id=lesson_id))


@teacher_bp.route('/lessons/<int:lesson_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    topic_id = lesson.topic_id
    db.session.delete(lesson)
    db.session.commit()
    flash('Урок удалён', 'success')

    return redirect(url_for('teacher.lessons', topic_id=topic_id))


@teacher_bp.route('/lessons/<int:lesson_id>/assign', methods=['POST'])
@login_required
@teacher_required
def assign_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    class_ids = request.form.getlist('class_ids', type=int)
    original_topic = lesson.topic
    original_class_id = original_topic.class_id

    # Удаляем старые назначения
    LessonAssignment.query.filter_by(lesson_id=lesson_id).delete()

    # Добавляем новые назначения
    for class_id in class_ids:
        assignment = LessonAssignment(lesson_id=lesson_id, class_id=class_id)
        db.session.add(assignment)

        # Если класс отличается от класса темы урока - создаём копию урока в этом классе
        if class_id != original_class_id:
            # Проверяем, есть ли уже тема с таким именем в целевом классе
            target_topic = Topic.query.filter_by(
                name=original_topic.name,
                class_id=class_id,
                teacher_id=current_user.id
            ).first()

            # Если темы нет - создаём
            if not target_topic:
                target_topic = Topic(
                    name=original_topic.name,
                    class_id=class_id,
                    teacher_id=current_user.id
                )
                db.session.add(target_topic)
                db.session.flush()

            # Проверяем, есть ли уже копия урока в этой теме
            existing_copy = Lesson.query.filter_by(
                title=lesson.title,
                topic_id=target_topic.id,
                teacher_id=current_user.id
            ).first()

            if not existing_copy:
                # Создаём копию урока
                lesson_copy = Lesson(
                    title=lesson.title,
                    topic_id=target_topic.id,
                    teacher_id=current_user.id
                )
                db.session.add(lesson_copy)
                db.session.flush()

                # Копируем задания
                for task in lesson.tasks:
                    task_copy = Task(
                        lesson_id=lesson_copy.id,
                        title=task.title,
                        description=task.description,
                        default_code=task.default_code,
                        order=task.order
                    )
                    db.session.add(task_copy)
                    db.session.flush()

                    # Копируем тесты
                    for test in task.test_cases:
                        test_copy = TestCase(
                            task_id=task_copy.id,
                            input_data=test.input_data,
                            expected_output=test.expected_output,
                            is_hidden=test.is_hidden,
                            order=test.order
                        )
                        db.session.add(test_copy)

                # Также назначаем копию этому классу
                copy_assignment = LessonAssignment(lesson_id=lesson_copy.id, class_id=class_id)
                db.session.add(copy_assignment)

    db.session.commit()
    flash('Урок назначен классам', 'success')

    return redirect(url_for('teacher.lesson_edit', lesson_id=lesson_id))


# ==================== ЗАДАНИЯ ====================

@teacher_bp.route('/lessons/<int:lesson_id>/tasks/create', methods=['POST'])
@login_required
@teacher_required
def create_task(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    title = request.form.get('title')
    if title:
        max_order = db.session.query(db.func.max(Task.order)).filter_by(lesson_id=lesson_id).scalar() or 0
        task = Task(lesson_id=lesson_id, title=title, order=max_order + 1)
        db.session.add(task)
        db.session.commit()
        flash('Задание создано', 'success')
        return redirect(url_for('teacher.task_edit', task_id=task.id))

    return redirect(url_for('teacher.lesson_edit', lesson_id=lesson_id))


@teacher_bp.route('/tasks/<int:task_id>')
@login_required
@teacher_required
def task_edit(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    return render_template('teacher/task_edit.html', task=task)


@teacher_bp.route('/tasks/<int:task_id>/edit', methods=['POST'])
@login_required
@teacher_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    title = request.form.get('title')
    description = request.form.get('description')
    default_code = request.form.get('default_code', '')

    if title:
        task.title = title
    task.description = description
    task.default_code = default_code if default_code.strip() else None
    db.session.commit()
    flash('Задание обновлено', 'success')

    return redirect(url_for('teacher.task_edit', task_id=task_id))


@teacher_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    lesson_id = task.lesson_id
    db.session.delete(task)
    db.session.commit()
    flash('Задание удалено', 'success')

    return redirect(url_for('teacher.lesson_edit', lesson_id=lesson_id))


# ==================== ТЕСТЫ ====================

@teacher_bp.route('/tasks/<int:task_id>/tests/create', methods=['POST'])
@login_required
@teacher_required
def create_test(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    input_data = request.form.get('input_data', '')
    expected_output = request.form.get('expected_output', '')
    is_hidden = request.form.get('is_hidden') == '1'

    if expected_output:
        max_order = db.session.query(db.func.max(TestCase.order)).filter_by(task_id=task_id).scalar() or 0
        test = TestCase(task_id=task_id, input_data=input_data, expected_output=expected_output,
                       is_hidden=is_hidden, order=max_order + 1)
        db.session.add(test)
        db.session.commit()
        flash('Тест добавлен', 'success')

    return redirect(url_for('teacher.task_edit', task_id=task_id))


@teacher_bp.route('/tests/<int:test_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_test(test_id):
    test = TestCase.query.get_or_404(test_id)
    if test.task.lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    task_id = test.task_id
    db.session.delete(test)
    db.session.commit()
    flash('Тест удалён', 'success')

    return redirect(url_for('teacher.task_edit', task_id=task_id))


# ==================== ЖУРНАЛ ====================

@teacher_bp.route('/journal')
@login_required
@teacher_required
def journal():
    classes = SchoolClass.query.filter_by(teacher_id=current_user.id).all()
    class_id = request.args.get('class_id', type=int)
    lesson_id = request.args.get('lesson_id', type=int)

    if class_id:
        school_class = SchoolClass.query.get_or_404(class_id)
        if school_class.teacher_id != current_user.id:
            flash('Нет доступа', 'error')
            return redirect(url_for('teacher.journal'))

        students = school_class.students

        # Получаем все уроки, назначенные этому классу
        assignments = LessonAssignment.query.filter_by(class_id=class_id).all()
        lessons = [a.lesson for a in assignments]

        # Показываем задания только если выбран конкретный урок
        all_tasks = []
        progress_matrix = {}

        if lesson_id:
            selected_lesson = Lesson.query.get(lesson_id)
            if selected_lesson and selected_lesson in lessons:
                all_tasks = selected_lesson.tasks

                # Создаём матрицу прогресса
                for student in students:
                    progress_matrix[student.id] = {}
                    for task in all_tasks:
                        progress = StudentProgress.query.filter_by(
                            student_id=student.id, task_id=task.id
                        ).first()
                        progress_matrix[student.id][task.id] = progress.is_completed if progress else False
            else:
                lesson_id = None

        return render_template('teacher/journal.html',
                               classes=classes,
                               selected_class=school_class,
                               students=students,
                               lessons=lessons,
                               selected_lesson_id=lesson_id,
                               all_tasks=all_tasks,
                               progress_matrix=progress_matrix)

    return render_template('teacher/journal.html', classes=classes, selected_class=None)
