import json
from urllib.parse import quote
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, Response
from flask_login import login_required, current_user
from models import db, Teacher, SchoolClass, Student, Topic, Lesson, Task, TestCase, LessonAssignment, StudentProgress, QuizElement, QuizOption, QuizAnswer
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


# ==================== ПАПКИ И УРОКИ ====================

@teacher_bp.route('/lessons')
@login_required
@teacher_required
def lessons():
    topic_id = request.args.get('topic_id', type=int)

    # Если выбрана папка - показываем содержимое папки
    if topic_id:
        topic = Topic.query.get_or_404(topic_id)
        if topic.teacher_id != current_user.id:
            flash('Нет доступа', 'error')
            return redirect(url_for('teacher.lessons'))
        topics = topic.children
        lessons_list = topic.lessons
        parent = topic
        breadcrumbs = []
        current = topic
        while current:
            breadcrumbs.insert(0, current)
            current = current.parent
        return render_template('teacher/lessons.html',
                               topics=topics,
                               lessons=lessons_list,
                               parent=parent,
                               breadcrumbs=breadcrumbs)

    # Иначе показываем корневые папки и уроки без папки
    topics = Topic.query.filter_by(teacher_id=current_user.id, parent_id=None).all()
    root_lessons = Lesson.query.filter_by(teacher_id=current_user.id, topic_id=None).all()
    return render_template('teacher/lessons.html',
                           topics=topics,
                           lessons=root_lessons,
                           parent=None,
                           breadcrumbs=[])


@teacher_bp.route('/topics/create', methods=['POST'])
@login_required
@teacher_required
def create_topic():
    name = request.form.get('name')
    parent_id = request.form.get('parent_id', type=int)

    if name:
        topic = Topic(name=name, parent_id=parent_id if parent_id else None, teacher_id=current_user.id)
        db.session.add(topic)
        db.session.commit()
        flash('Папка создана', 'success')

    if parent_id:
        return redirect(url_for('teacher.lessons', topic_id=parent_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/topics/<int:topic_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if topic.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    # Проверяем наличие уроков в папке и во всех подпапках
    def has_lessons(t):
        if t.lessons:
            return True
        for child in t.children:
            if has_lessons(child):
                return True
        return False

    if has_lessons(topic):
        flash('Нельзя удалить папку, в которой есть уроки. Сначала переместите или удалите уроки.', 'error')
        if topic.parent_id:
            return redirect(url_for('teacher.lessons', topic_id=topic.parent_id))
        return redirect(url_for('teacher.lessons'))

    parent_id = topic.parent_id
    db.session.delete(topic)
    db.session.commit()
    flash('Папка удалена', 'success')

    if parent_id:
        return redirect(url_for('teacher.lessons', topic_id=parent_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/topics/<int:topic_id>/move', methods=['POST'])
@login_required
@teacher_required
def move_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if topic.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    target_id = request.form.get('target_id', type=int)

    # Нельзя переместить в себя
    if target_id == topic_id:
        flash('Нельзя переместить папку в саму себя', 'error')
        return redirect(url_for('teacher.lessons', topic_id=topic.parent_id))

    # Нельзя переместить в потомка
    if target_id is not None:
        target = Topic.query.get_or_404(target_id)
        if target.teacher_id != current_user.id:
            flash('Нет доступа', 'error')
            return redirect(url_for('teacher.lessons'))
        current_node = target
        while current_node is not None:
            if current_node.id == topic_id:
                flash('Нельзя переместить папку в её подпапку', 'error')
                return redirect(url_for('teacher.lessons', topic_id=topic.parent_id))
            current_node = current_node.parent

    # Если уже на месте
    if topic.parent_id == target_id:
        flash('Папка уже находится здесь', 'info')
        return redirect(url_for('teacher.lessons', topic_id=target_id))

    old_parent_id = topic.parent_id
    topic.parent_id = target_id
    db.session.commit()
    flash(f'Папка «{topic.name}» перемещена', 'success')

    if old_parent_id:
        return redirect(url_for('teacher.lessons', topic_id=old_parent_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/api/folder-tree')
@login_required
@teacher_required
def folder_tree():
    all_topics = Topic.query.filter_by(teacher_id=current_user.id).all()

    def build_tree(parent_id):
        nodes = []
        for t in all_topics:
            if t.parent_id == parent_id:
                nodes.append({
                    'id': t.id,
                    'name': t.name,
                    'children': build_tree(t.id)
                })
        return nodes

    return jsonify(build_tree(None))


@teacher_bp.route('/lessons/create', methods=['POST'])
@login_required
@teacher_required
def create_lesson():
    title = request.form.get('title')
    topic_id = request.form.get('topic_id', type=int)

    if title:
        # Если указана папка — проверяем доступ
        if topic_id:
            topic = Topic.query.get(topic_id)
            if not topic or topic.teacher_id != current_user.id:
                flash('Нет доступа', 'error')
                return redirect(url_for('teacher.lessons'))

        lesson = Lesson(title=title, topic_id=topic_id if topic_id else None, teacher_id=current_user.id)
        db.session.add(lesson)
        db.session.commit()
        flash('Урок создан', 'success')
        return redirect(url_for('teacher.lesson_edit', lesson_id=lesson.id))

    return redirect(url_for('teacher.lessons', topic_id=topic_id))


@teacher_bp.route('/lessons/import', methods=['POST'])
@login_required
@teacher_required
def import_lessons():
    topic_id = request.form.get('topic_id', type=int)

    # Проверяем доступ к папке (если указана)
    if topic_id:
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

    file_type = data.get('type', '')

    if file_type == 'folder':
        # Импорт папки с подпапками и уроками
        counts = _import_folder_data(data, topic_id, current_user.id)
        flash(f'Импортировано: папок — {counts["folders"]}, уроков — {counts["lessons"]}', 'success')
    elif file_type == 'lesson':
        # Импорт одного урока
        _import_lesson_data(data, topic_id, current_user.id)
        flash('Урок импортирован', 'success')
    elif 'lessons' in data:
        # Старый формат: список уроков
        for lesson_data in data['lessons']:
            _import_lesson_data(lesson_data, topic_id, current_user.id)
        flash(f'Импортировано уроков: {len(data["lessons"])}', 'success')
    else:
        flash('Неизвестный формат файла', 'error')
        return redirect(url_for('teacher.lessons', topic_id=topic_id))

    db.session.commit()
    return redirect(url_for('teacher.lessons', topic_id=topic_id))


def _import_lesson_data(lesson_data, topic_id, teacher_id):
    """Импортирует один урок из словаря данных."""
    title = lesson_data.get('title', 'Без названия')
    lesson = Lesson(title=title, topic_id=topic_id if topic_id else None, teacher_id=teacher_id)
    db.session.add(lesson)
    db.session.flush()

    for order, task_data in enumerate(lesson_data.get('tasks', []), 1):
        task_type = task_data.get('task_type', 'code')
        task = Task(
            lesson_id=lesson.id,
            title=task_data.get('title', 'Без названия'),
            task_type=task_type,
            is_bonus=task_data.get('is_bonus', False),
            description=task_data.get('description', ''),
            default_code=task_data.get('default_code', None),
            order=order
        )
        db.session.add(task)
        db.session.flush()

        if task_type == 'quiz':
            for el_order, el_data in enumerate(task_data.get('elements', []), 1):
                element = QuizElement(
                    task_id=task.id,
                    element_type=el_data.get('element_type', 'text'),
                    content=el_data.get('content', ''),
                    correct_answer=el_data.get('correct_answer', None),
                    order=el_order
                )
                db.session.add(element)
                db.session.flush()

                for opt_order, opt_data in enumerate(el_data.get('options', []), 1):
                    option = QuizOption(
                        element_id=element.id,
                        text=opt_data.get('text', ''),
                        is_correct=opt_data.get('is_correct', False),
                        order=opt_order
                    )
                    db.session.add(option)
        else:
            for test_order, test_data in enumerate(task_data.get('tests', []), 1):
                test = TestCase(
                    task_id=task.id,
                    input_data=test_data.get('input', ''),
                    expected_output=test_data.get('output', ''),
                    is_hidden=test_data.get('hidden', False),
                    order=test_order
                )
                db.session.add(test)

    return lesson


def _import_folder_data(folder_data, parent_topic_id, teacher_id):
    """Рекурсивно импортирует папку с подпапками и уроками."""
    counts = {'folders': 0, 'lessons': 0}

    # Создаём саму папку
    folder_name = folder_data.get('name', 'Без названия')
    topic = Topic(name=folder_name, parent_id=parent_topic_id if parent_topic_id else None, teacher_id=teacher_id)
    db.session.add(topic)
    db.session.flush()
    counts['folders'] += 1

    # Импортируем уроки в эту папку
    for lesson_data in folder_data.get('lessons', []):
        _import_lesson_data(lesson_data, topic.id, teacher_id)
        counts['lessons'] += 1

    # Рекурсивно импортируем подпапки
    for subfolder_data in folder_data.get('folders', []):
        sub_counts = _import_folder_data(subfolder_data, topic.id, teacher_id)
        counts['folders'] += sub_counts['folders']
        counts['lessons'] += sub_counts['lessons']

    return counts


@teacher_bp.route('/export-all')
@login_required
@teacher_required
def export_all():
    root_topics = Topic.query.filter_by(teacher_id=current_user.id, parent_id=None).all()
    root_lessons = Lesson.query.filter_by(teacher_id=current_user.id, topic_id=None).all()

    folders = []
    for topic in root_topics:
        folder_data = _export_folder(topic)
        del folder_data['type']
        folders.append(folder_data)

    lessons = []
    for lesson in root_lessons:
        lesson_data = _export_lesson(lesson)
        del lesson_data['type']
        lessons.append(lesson_data)

    data = {
        'type': 'folder',
        'name': 'Все уроки',
        'folders': folders,
        'lessons': lessons
    }

    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote('Все уроки.json')}
    )


@teacher_bp.route('/topics/<int:topic_id>/export')
@login_required
@teacher_required
def export_topic(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if topic.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    data = _export_folder(topic)
    filename = f'{topic.name}.json'

    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


def _export_lesson(lesson):
    """Экспортирует один урок в словарь."""
    tasks = []
    for task in lesson.tasks:
        task_data = {'title': task.title, 'task_type': task.task_type, 'is_bonus': task.is_bonus}

        if task.task_type == 'quiz':
            elements = []
            for el in task.quiz_elements:
                el_data = {'element_type': el.element_type, 'content': el.content or ''}
                if el.element_type == 'text_input':
                    el_data['correct_answer'] = el.correct_answer or ''
                elif el.element_type in ('single_choice', 'multiple_choice'):
                    el_data['options'] = [
                        {'text': opt.text, 'is_correct': opt.is_correct}
                        for opt in el.options
                    ]
                elements.append(el_data)
            task_data['elements'] = elements
        else:
            task_data['description'] = task.description or ''
            task_data['default_code'] = task.default_code or ''
            tests = []
            for test in task.test_cases:
                tests.append({
                    'input': test.input_data or '',
                    'output': test.expected_output,
                    'hidden': test.is_hidden
                })
            task_data['tests'] = tests

        tasks.append(task_data)
    return {
        'type': 'lesson',
        'title': lesson.title,
        'tasks': tasks
    }


def _export_folder(topic):
    """Рекурсивно экспортирует папку с подпапками и уроками."""
    lessons = []
    for lesson in topic.lessons:
        lesson_data = _export_lesson(lesson)
        del lesson_data['type']  # Убираем type у вложенных уроков
        lessons.append(lesson_data)

    folders = []
    for child in topic.children:
        folder_data = _export_folder(child)
        del folder_data['type']  # Убираем type у вложенных папок
        folders.append(folder_data)

    return {
        'type': 'folder',
        'name': topic.name,
        'folders': folders,
        'lessons': lessons
    }


@teacher_bp.route('/lessons/<int:lesson_id>/export')
@login_required
@teacher_required
def export_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    data = _export_lesson(lesson)
    filename = f'{lesson.title}.json'

    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"}
    )


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

    if topic_id:
        return redirect(url_for('teacher.lessons', topic_id=topic_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/lessons/<int:lesson_id>/move', methods=['POST'])
@login_required
@teacher_required
def move_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))

    target_id = request.form.get('target_id', type=int)  # None = корень

    # Проверяем доступ к целевой папке (если не корень)
    if target_id is not None:
        target = Topic.query.get_or_404(target_id)
        if target.teacher_id != current_user.id:
            flash('Нет доступа', 'error')
            return redirect(url_for('teacher.lessons'))

    if lesson.topic_id == target_id:
        flash('Урок уже находится здесь', 'info')
        return redirect(url_for('teacher.lessons', topic_id=target_id))

    old_topic_id = lesson.topic_id
    lesson.topic_id = target_id
    db.session.commit()
    flash(f'Урок «{lesson.title}» перемещён', 'success')

    if old_topic_id:
        return redirect(url_for('teacher.lessons', topic_id=old_topic_id))
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/lessons/<int:lesson_id>/assign', methods=['POST'])
@login_required
@teacher_required
def assign_lesson(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    class_ids = data.get('class_ids', [])

    # Удаляем старые назначения
    LessonAssignment.query.filter_by(lesson_id=lesson_id).delete()

    # Добавляем новые назначения
    for class_id in class_ids:
        assignment = LessonAssignment(lesson_id=lesson_id, class_id=class_id)
        db.session.add(assignment)

    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/lessons/<int:lesson_id>/autosave', methods=['POST'])
@login_required
@teacher_required
def lesson_autosave(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    if lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    if data.get('title'):
        lesson.title = data['title']
    db.session.commit()
    return jsonify({'success': True})


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
    task_type = request.form.get('task_type', 'code')
    if task_type not in ('code', 'quiz'):
        task_type = 'code'
    is_bonus = request.form.get('is_bonus') == 'on'

    if title:
        max_order = db.session.query(db.func.max(Task.order)).filter_by(lesson_id=lesson_id).scalar() or 0
        task = Task(lesson_id=lesson_id, title=title, task_type=task_type, is_bonus=is_bonus, order=max_order + 1)
        db.session.add(task)
        db.session.commit()
        flash('Задание создано', 'success')
        if task.task_type == 'quiz':
            return redirect(url_for('teacher.quiz_edit', task_id=task.id))
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

    if task.task_type == 'quiz':
        return redirect(url_for('teacher.quiz_edit', task_id=task_id))

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
    task.is_bonus = 'is_bonus' in request.form
    db.session.commit()
    flash('Задание обновлено', 'success')

    return redirect(url_for('teacher.task_edit', task_id=task_id))


@teacher_bp.route('/tasks/<int:task_id>/autosave', methods=['POST'])
@login_required
@teacher_required
def autosave_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    if data.get('title'):
        task.title = data['title']
    if 'description' in data:
        task.description = data['description']
    if 'default_code' in data:
        code = data['default_code']
        task.default_code = code if code and code.strip() else None
    if 'is_bonus' in data:
        task.is_bonus = bool(data['is_bonus'])
    db.session.commit()

    return jsonify({'success': True})


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


# ==================== КВИЗ (ТЕСТЫ) ====================

@teacher_bp.route('/tasks/<int:task_id>/quiz')
@login_required
@teacher_required
def quiz_edit(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        flash('Нет доступа', 'error')
        return redirect(url_for('teacher.lessons'))
    if task.task_type != 'quiz':
        return redirect(url_for('teacher.task_edit', task_id=task_id))
    return render_template('teacher/quiz_edit.html', task=task)


@teacher_bp.route('/tasks/<int:task_id>/quiz/autosave', methods=['POST'])
@login_required
@teacher_required
def quiz_autosave(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403
    data = request.get_json()
    if data.get('title'):
        task.title = data['title']
    if 'is_bonus' in data:
        task.is_bonus = bool(data['is_bonus'])
    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/tasks/<int:task_id>/quiz/add-element', methods=['POST'])
@login_required
@teacher_required
def quiz_add_element(task_id):
    task = Task.query.get_or_404(task_id)
    if task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    element_type = data.get('element_type', 'text')
    if element_type == 'question':
        element_type = 'single_choice'

    max_order = db.session.query(db.func.max(QuizElement.order)).filter_by(task_id=task_id).scalar() or 0
    element = QuizElement(task_id=task_id, element_type=element_type, content='', order=max_order + 1)
    db.session.add(element)
    db.session.commit()

    return jsonify({'success': True, 'element': {
        'id': element.id,
        'element_type': element.element_type,
        'order': element.order
    }})


@teacher_bp.route('/quiz-elements/<int:element_id>/autosave', methods=['POST'])
@login_required
@teacher_required
def quiz_element_autosave(element_id):
    element = QuizElement.query.get_or_404(element_id)
    if element.task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    if 'content' in data:
        element.content = data['content']
    if 'element_type' in data and data['element_type'] in ('single_choice', 'multiple_choice', 'text_input'):
        element.element_type = data['element_type']
    if 'correct_answer' in data:
        element.correct_answer = data['correct_answer']
    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/quiz-elements/<int:element_id>/delete', methods=['POST'])
@login_required
@teacher_required
def quiz_element_delete(element_id):
    element = QuizElement.query.get_or_404(element_id)
    if element.task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    db.session.delete(element)
    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/quiz-elements/<int:element_id>/move', methods=['POST'])
@login_required
@teacher_required
def quiz_element_move(element_id):
    element = QuizElement.query.get_or_404(element_id)
    if element.task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    direction = data.get('direction', 'up')
    elements = QuizElement.query.filter_by(task_id=element.task_id).order_by(QuizElement.order).all()

    idx = next((i for i, e in enumerate(elements) if e.id == element_id), None)
    if idx is None:
        return jsonify({'success': False})

    if direction == 'up' and idx > 0:
        elements[idx].order, elements[idx - 1].order = elements[idx - 1].order, elements[idx].order
    elif direction == 'down' and idx < len(elements) - 1:
        elements[idx].order, elements[idx + 1].order = elements[idx + 1].order, elements[idx].order

    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/quiz-elements/<int:element_id>/options/add', methods=['POST'])
@login_required
@teacher_required
def quiz_option_add(element_id):
    element = QuizElement.query.get_or_404(element_id)
    if element.task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    max_order = db.session.query(db.func.max(QuizOption.order)).filter_by(element_id=element_id).scalar() or 0
    option = QuizOption(element_id=element_id, text='', is_correct=False, order=max_order + 1)
    db.session.add(option)
    db.session.commit()
    return jsonify({'success': True, 'option': {
        'id': option.id,
        'text': option.text,
        'is_correct': option.is_correct,
        'order': option.order
    }})


@teacher_bp.route('/quiz-options/<int:option_id>/update', methods=['POST'])
@login_required
@teacher_required
def quiz_option_update(option_id):
    option = QuizOption.query.get_or_404(option_id)
    if option.element.task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    data = request.get_json()
    if 'text' in data:
        option.text = data['text']
    if 'is_correct' in data:
        # Для single_choice — снять правильность с остальных
        if option.element.element_type == 'single_choice' and data['is_correct']:
            for opt in option.element.options:
                opt.is_correct = False
        option.is_correct = data['is_correct']
    db.session.commit()
    return jsonify({'success': True})


@teacher_bp.route('/quiz-options/<int:option_id>/delete', methods=['POST'])
@login_required
@teacher_required
def quiz_option_delete(option_id):
    option = QuizOption.query.get_or_404(option_id)
    if option.element.task.lesson.teacher_id != current_user.id:
        return jsonify({'success': False}), 403

    db.session.delete(option)
    db.session.commit()
    return jsonify({'success': True})


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

                        entry = {
                            'completed': progress.is_completed if progress else False,
                            'has_errors': progress.has_errors if progress else False
                        }

                        # Детальная статистика для тестов
                        if task.task_type == 'quiz':
                            question_ids = [e.id for e in task.quiz_elements if e.element_type != 'text']
                            total_q = len(question_ids)
                            if total_q > 0:
                                answers = QuizAnswer.query.filter(
                                    QuizAnswer.student_id == student.id,
                                    QuizAnswer.element_id.in_(question_ids)
                                ).all()
                                correct_clean = sum(1 for a in answers if a.is_correct and not a.had_errors)
                                correct_errors = sum(1 for a in answers if a.is_correct and a.had_errors)
                                not_answered = total_q - sum(1 for a in answers if a.is_correct)
                                entry['quiz'] = {
                                    'total': total_q,
                                    'clean': correct_clean,
                                    'errors': correct_errors,
                                    'pending': not_answered
                                }

                        progress_matrix[student.id][task.id] = entry
            else:
                lesson_id = None

        # Подсчёт статистики
        stats = {'completed': 0, 'errors': 0, 'not_done': 0}
        for student in students:
            for task in all_tasks:
                p = progress_matrix.get(student.id, {}).get(task.id, {})
                if p.get('completed') and not p.get('has_errors'):
                    stats['completed'] += 1
                elif p.get('completed') and p.get('has_errors'):
                    stats['errors'] += 1
                else:
                    stats['not_done'] += 1

        return render_template('teacher/journal.html',
                               classes=classes,
                               selected_class=school_class,
                               students=students,
                               lessons=lessons,
                               selected_lesson_id=lesson_id,
                               all_tasks=all_tasks,
                               progress_matrix=progress_matrix,
                               stats=stats)

    return render_template('teacher/journal.html', classes=classes, selected_class=None)
