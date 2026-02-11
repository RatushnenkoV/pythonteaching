from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class Teacher(UserMixin, db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    classes = db.relationship('SchoolClass', backref='teacher', lazy=True, cascade='all, delete-orphan')
    topics = db.relationship('Topic', backref='teacher', lazy=True, cascade='all, delete-orphan')
    lessons = db.relationship('Lesson', backref='teacher', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"teacher_{self.id}"


class SchoolClass(db.Model):
    __tablename__ = 'school_classes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='school_class', lazy=True, cascade='all, delete-orphan')
    assignments = db.relationship('LessonAssignment', backref='school_class', lazy=True, cascade='all, delete-orphan')


class Student(UserMixin, db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    progress = db.relationship('StudentProgress', backref='student', lazy=True, cascade='all, delete-orphan')
    quiz_answers = db.relationship('QuizAnswer', backref='student', lazy=True, cascade='all, delete-orphan')
    activity_events = db.relationship('ActivityEvent', backref='student', lazy=True, cascade='all, delete-orphan')

    def get_id(self):
        return f"student_{self.id}"


class Topic(db.Model):
    __tablename__ = 'topics'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('topics.id', ondelete='CASCADE'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    children = db.relationship('Topic', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade='all, delete-orphan')
    lessons = db.relationship('Lesson', backref='topic', lazy=True, cascade='all, delete-orphan')
    school_class = db.relationship('SchoolClass', backref='topics', lazy=True)


class Lesson(db.Model):
    __tablename__ = 'lessons'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='lesson', lazy=True, order_by='Task.order', cascade='all, delete-orphan')
    assignments = db.relationship('LessonAssignment', backref='lesson', lazy=True, cascade='all, delete-orphan')


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    task_type = db.Column(db.String(20), default='code')  # 'code' | 'quiz'
    is_bonus = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, nullable=True)
    default_code = db.Column(db.Text, nullable=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    test_cases = db.relationship('TestCase', backref='task', lazy=True, order_by='TestCase.order', cascade='all, delete-orphan')
    quiz_elements = db.relationship('QuizElement', backref='task', lazy=True, order_by='QuizElement.order', cascade='all, delete-orphan')
    progress = db.relationship('StudentProgress', backref='task', lazy=True, cascade='all, delete-orphan')
    activity_events = db.relationship('ActivityEvent', backref='task', lazy=True, cascade='all, delete-orphan')


class TestCase(db.Model):
    __tablename__ = 'test_cases'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    input_data = db.Column(db.Text, nullable=True)
    expected_output = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)


class LessonAssignment(db.Model):
    __tablename__ = 'lesson_assignments'

    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('school_classes.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('lesson_id', 'class_id', name='unique_lesson_class'),)


class StudentProgress(db.Model):
    __tablename__ = 'student_progress'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    code = db.Column(db.Text, nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    has_errors = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    paste_count = db.Column(db.Integer, default=0)
    has_pastes = db.Column(db.Boolean, default=False)
    has_copies = db.Column(db.Boolean, default=False)
    has_leaves = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint('student_id', 'task_id', name='unique_student_task'),)


class QuizElement(db.Model):
    __tablename__ = 'quiz_elements'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    element_type = db.Column(db.String(20), nullable=False)  # 'text' | 'single_choice' | 'multiple_choice' | 'text_input'
    content = db.Column(db.Text, nullable=True)
    correct_answer = db.Column(db.Text, nullable=True)  # для text_input
    order = db.Column(db.Integer, default=0)

    options = db.relationship('QuizOption', backref='element', lazy=True, order_by='QuizOption.order', cascade='all, delete-orphan')
    answers = db.relationship('QuizAnswer', backref='element', lazy=True, cascade='all, delete-orphan')


class QuizOption(db.Model):
    __tablename__ = 'quiz_options'

    id = db.Column(db.Integer, primary_key=True)
    element_id = db.Column(db.Integer, db.ForeignKey('quiz_elements.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)


class QuizAnswer(db.Model):
    __tablename__ = 'quiz_answers'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    element_id = db.Column(db.Integer, db.ForeignKey('quiz_elements.id'), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    had_errors = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint('student_id', 'element_id', name='unique_student_element'),)


class ActivityEvent(db.Model):
    __tablename__ = 'activity_events'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    event_type = db.Column(db.String(20), nullable=False)  # 'paste' | 'copy' | 'leave'
    text_content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
