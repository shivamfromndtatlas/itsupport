@echo off
echo ============================================
echo  IT Support App - First Time Setup
echo ============================================
echo.

cd /d "%~dp0"
call venv\Scripts\activate

echo [1/3] Running Django migrations...
python manage.py makemigrations
python manage.py migrate

echo.
echo [2/3] Creating Super Admin user...
python manage.py shell -c "from apps.users.models import User; User.objects.filter(email='admin@company.com').exists() or User.objects.create_superuser(email='admin@company.com', password='Admin@1234', full_name='Super Admin')"

echo.
echo [3/3] Collecting static files...
python manage.py collectstatic --noinput

echo.
echo ============================================
echo  Setup complete!
echo  Super Admin Login:
echo    Email: admin@company.com
echo    Password: Admin@1234
echo ============================================
pause
