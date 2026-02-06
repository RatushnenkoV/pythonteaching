# WSGI файл для продакшен-серверов (PythonAnywhere, Gunicorn и др.)
from app import app as application

# Для PythonAnywhere этот файл не нужен напрямую,
# но он полезен для других WSGI серверов

if __name__ == "__main__":
    application.run()
