Instructions for starting the app:
- First make sure you have downloanded the needed libraries and Django framework.
- Then open "gmt458_team14 Project" folder on terminal.
- Type "python manage.py runserver" on terminal.
- And ctrl+click to the localhost address.

If you have any issues while starting the app:
- First migrate the database with "python manage.py makemigrations" and "python manage.py migrate" commands on terminal
- Then load data with "python manage.py load_resident_data" command and again migrate the database just in case.
- If you still have issues with starting the application; delete all __pycache__ (.pyc) files and also "0001_initial.py", "0002_initial.py" (NOT THE __init__.py) files.
- Then try again migrate and load data process.
 
