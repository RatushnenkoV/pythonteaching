from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from sqlalchemy import func
from models import db, Teacher, Student

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def index():
    return render_template('auth/login.html')


@auth_bp.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')

        # Case-insensitive поиск
        teacher = Teacher.query.filter(func.lower(Teacher.username) == username.lower()).first()
        if teacher and teacher.check_password(password):
            login_user(teacher)
            return redirect(url_for('teacher.dashboard'))
        flash('Неверный логин или пароль', 'error')

    return render_template('auth/teacher_login.html')


@auth_bp.route('/teacher/register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        if not username or not password:
            flash('Заполните все поля', 'error')
            return render_template('auth/teacher_register.html')

        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return render_template('auth/teacher_register.html')

        # Case-insensitive проверка существования
        if Teacher.query.filter(func.lower(Teacher.username) == username.lower()).first():
            flash('Такой логин уже существует', 'error')
            return render_template('auth/teacher_register.html')

        teacher = Teacher(username=username)
        teacher.set_password(password)
        db.session.add(teacher)
        db.session.commit()

        flash('Регистрация успешна! Теперь войдите.', 'success')
        return redirect(url_for('auth.teacher_login'))

    return render_template('auth/teacher_register.html')


@auth_bp.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        login = request.form.get('login', '').strip()

        # Case-insensitive поиск
        student = Student.query.filter(func.lower(Student.login) == login.lower()).first()
        if student:
            login_user(student)
            return redirect(url_for('student.dashboard'))
        flash('Неверный логин', 'error')

    return render_template('auth/student_login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.index'))
