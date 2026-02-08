from flask import Flask, redirect, url_for
from flask_login import LoginManager
from models import db, Teacher, Student
from sqlalchemy import event
from sqlalchemy.engine import Engine
import os

app = Flask(__name__)

# Конфигурация
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# База данных: в продакшене используем /data для Volume
if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('FLASK_ENV') == 'production':
    # Создаём папку /data если её нет
    os.makedirs('/data', exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/database.db'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Продакшен настройки
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True

db.init_app(app)


# Включаем поддержку внешних ключей в SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.index'
login_manager.login_message = 'Пожалуйста, войдите в систему.'
login_manager.login_message_category = 'info'


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('auth.index'))


@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('teacher_'):
        teacher_id = int(user_id.split('_')[1])
        return Teacher.query.get(teacher_id)
    elif user_id.startswith('student_'):
        student_id = int(user_id.split('_')[1])
        return Student.query.get(student_id)
    return None


# Регистрация blueprints
from routes import auth_bp, teacher_bp, student_bp

app.register_blueprint(auth_bp)
app.register_blueprint(teacher_bp, url_prefix='/teacher')
app.register_blueprint(student_bp, url_prefix='/student')


# Создание таблиц при первом запуске
with app.app_context():
    db.create_all()

    # Миграции для новых столбцов
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)

    # Миграция: добавляем class_id в таблицу topics
    columns = [col['name'] for col in inspector.get_columns('topics')]
    if 'class_id' not in columns:
        db.session.execute(text('ALTER TABLE topics ADD COLUMN class_id INTEGER REFERENCES school_classes(id)'))
        db.session.commit()

    # Миграция: добавляем is_hidden в таблицу test_cases
    columns = [col['name'] for col in inspector.get_columns('test_cases')]
    if 'is_hidden' not in columns:
        db.session.execute(text('ALTER TABLE test_cases ADD COLUMN is_hidden BOOLEAN DEFAULT 0'))
        db.session.commit()

    # Миграция: добавляем default_code в таблицу tasks
    columns = [col['name'] for col in inspector.get_columns('tasks')]
    if 'default_code' not in columns:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN default_code TEXT'))
        db.session.commit()

    # Миграция: добавляем task_type в таблицу tasks
    if 'task_type' not in columns:
        db.session.execute(text("ALTER TABLE tasks ADD COLUMN task_type VARCHAR(20) DEFAULT 'code'"))
        db.session.commit()

    # Миграция: добавляем is_bonus в таблицу tasks
    if 'is_bonus' not in columns:
        db.session.execute(text('ALTER TABLE tasks ADD COLUMN is_bonus BOOLEAN DEFAULT 0'))
        db.session.commit()

    # Миграция: добавляем has_errors в таблицу student_progress
    sp_columns = [col['name'] for col in inspector.get_columns('student_progress')]
    if 'has_errors' not in sp_columns:
        db.session.execute(text('ALTER TABLE student_progress ADD COLUMN has_errors BOOLEAN DEFAULT 0'))
        db.session.commit()

    # Миграция: делаем topic_id nullable в таблице lessons
    # SQLite не поддерживает ALTER COLUMN, поэтому пересоздаём таблицу
    lessons_columns = inspector.get_columns('lessons')
    topic_id_col = next((c for c in lessons_columns if c['name'] == 'topic_id'), None)
    if topic_id_col and topic_id_col.get('nullable') is False:
        db.session.execute(text('PRAGMA foreign_keys=OFF'))
        db.session.execute(text('''
            CREATE TABLE lessons_new (
                id INTEGER PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                topic_id INTEGER REFERENCES topics(id),
                teacher_id INTEGER NOT NULL REFERENCES teachers(id),
                created_at DATETIME
            )
        '''))
        db.session.execute(text('INSERT INTO lessons_new SELECT * FROM lessons'))
        db.session.execute(text('DROP TABLE lessons'))
        db.session.execute(text('ALTER TABLE lessons_new RENAME TO lessons'))
        db.session.execute(text('PRAGMA foreign_keys=ON'))
        db.session.commit()


if __name__ == '__main__':
    # Только для локальной разработки
    app.run(host='0.0.0.0', debug=True, port=8080)
