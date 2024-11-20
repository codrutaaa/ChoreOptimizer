from flask import Flask, render_template, request, redirect, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pulp import LpMaximize, LpProblem, LpVariable, lpSum

app = Flask(__name__)

# Configurare MySQL
app.secret_key = 'my_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/oro_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Modele de date
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Float, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, nullable=False, default=1)

class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Float, nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, nullable=False, default=1)

# Crearea tabelelor în baza de date
with app.app_context():
    db.create_all()


# Decorator pentru autentificare
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


# Rute
@app.route('/')
def root():
    return redirect('/landing')

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Hash-ul parolei folosind o metodă sigură
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        # Verificăm dacă utilizatorul există deja
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "Numele de utilizator este deja folosit.", 400

        # Creăm utilizatorul
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect('/login')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            return "Numele de utilizator sau parola sunt greșite.", 400

        session['user_id'] = user.id
        session['username'] = user.username
        return redirect('/index')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect('/landing')

@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    tasks = Task.query.all()
    subtasks = Subtask.query.all()
    optimization_results = session.get('optimization_results', {})
    return render_template('index.html', tasks=tasks, optimization_results=optimization_results)


@app.route('/optimize_day/<day>', methods=['POST'])
@login_required
def optimize_day(day):
    try:
        # Preluăm timpul disponibil
        time_available = float(request.form['time_available'])

        # Preluăm task-urile și subtask-urile pentru ziua respectivă
        tasks = Task.query.filter_by(day=day).all()
        subtasks = Subtask.query.filter(Subtask.task_id.in_([task.id for task in tasks])).all()
        subtasks_by_task = {task.id: [subtask for subtask in subtasks if subtask.task_id == task.id] for task in tasks}

        # Configurăm problema de optimizare
        problema = LpProblem(f"Optimize_Tasks_{day}", LpMaximize)

        # Variabile de decizie
        task_vars = {task.id: LpVariable(f"task_{task.id}", 0, 1, cat="Binary") for task in tasks}
        subtask_vars = {subtask.id: LpVariable(f"subtask_{subtask.id}", 0, 1, cat="Binary") for subtask in subtasks}

        # Funcția obiectiv: maximizăm prioritățile task-urilor și subtask-urilor
        problema += lpSum(
            task_vars[task.id] * task.priority +
            lpSum(subtask_vars[subtask.id] * subtask.priority for subtask in subtasks_by_task[task.id])
            for task in tasks
        )

        # Constrângerea: timpul total nu trebuie să depășească timpul disponibil
        problema += lpSum(
            task_vars[task.id] * task.duration +
            lpSum(subtask_vars[subtask.id] * subtask.duration for subtask in subtasks_by_task[task.id])
            for task in tasks
        ) <= time_available

        # Constrângerea: un task este selectat doar dacă toate subtask-urile sale sunt selectate
        for task in tasks:
            for subtask in subtasks_by_task[task.id]:
                problema += subtask_vars[subtask.id] <= task_vars[task.id]

        # Rezolvăm problema de optimizare
        problema.solve()

        # Pregătim rezultatele
        tasks_to_do = []
        tasks_to_skip = []
        subtasks_to_do = []
        subtasks_to_skip = []

        for task in tasks:
            if task_vars[task.id].varValue == 1:
                tasks_to_do.append({"id": task.id, "name": task.name, "duration": task.duration})
            else:
                tasks_to_skip.append({"id": task.id, "name": task.name, "duration": task.duration})

        for subtask in subtasks:
            if subtask_vars[subtask.id].varValue == 1:
                subtasks_to_do.append({"id": subtask.id, "name": subtask.name, "duration": subtask.duration})
            else:
                subtasks_to_skip.append({"id": subtask.id, "name": subtask.name, "duration": subtask.duration})

        # Salvăm rezultatele în sesiune
        if 'optimization_results' not in session:
            session['optimization_results'] = {}
        session['optimization_results'][day] = {
            "tasks_to_do": tasks_to_do,
            "tasks_to_skip": tasks_to_skip,
            "subtasks_to_do": subtasks_to_do,
            "subtasks_to_skip": subtasks_to_skip
        }
        session.modified = True

        return redirect('/index')
    except Exception as e:
        return f"An error occurred during optimization: {str(e)}", 400


 
@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        try:
            # Preluare date din formular
            name = request.form['name']
            category = request.form['category']
            day = request.form['day']
            priority = int(request.form['priority'])
            duration = float(request.form['duration'])

            # Validare date
            if not name.strip() or not category.strip() or priority < 1 or duration <= 0:
                return "Invalid input data.", 400

            # Creare nou task
            new_task = Task(name=name, category=category, day=day, priority=priority, duration=duration)
            db.session.add(new_task)
            db.session.commit()

            # Redirecționare către pagina index
            return redirect('/index')  # Schimbat din '/' în '/index'
        except Exception as e:
            return f"An error occurred: {str(e)}", 400
    return render_template('add_task.html')



@app.route('/add_subtask/<int:task_id>', methods=['POST'])
@login_required
def add_subtask(task_id):
    try:
        name = request.form['name']
        hours = float(request.form['hours'])
        minutes = int(request.form['minutes'])
        duration = hours + minutes / 60

        task = Task.query.get(task_id)
        if not task:
            return "Task-ul principal nu a fost găsit.", 404

        existing_subtasks = Subtask.query.filter_by(task_id=task_id).all()
        total_subtask_time = sum(subtask.duration for subtask in existing_subtasks)

        if total_subtask_time + duration > task.duration:
            return f"Timpul total al subtask-urilor ({total_subtask_time + duration} ore) depășește durata task-ului principal ({task.duration} ore).", 400

        new_subtask = Subtask(name=name, duration=duration, task_id=task_id)
        db.session.add(new_subtask)
        db.session.commit()
        return redirect('/index')
    except Exception as e:
        return f"Eroare: {str(e)}", 400

@app.route('/optimize', methods=['POST'])
@login_required
def optimize_tasks():
    try:
        # Preluăm timpul disponibil de la utilizator
        time_available_per_day = request.json['time_available_per_day']

        # Preluăm toate sarcinile și subtask-urile din baza de date
        tasks = Task.query.all()
        subtasks = Subtask.query.all()

        # Grupăm sarcinile pe zile
        tasks_by_day = {day: [task for task in tasks if task.day == day] for day in time_available_per_day.keys()}
        subtasks_by_task = {task.id: [subtask for subtask in subtasks if subtask.task_id == task.id] for task in tasks}

        optimization_results = {}

        # Optimizăm pentru fiecare zi
        for day, day_tasks in tasks_by_day.items():
            # Definim problema de optimizare
            problem = LpProblem(f"Optimize_Tasks_{day}", LpMaximize)

            # Variabile de decizie
            task_vars = {task.id: LpVariable(f"task_{task.id}", 0, 1, cat="Binary") for task in day_tasks}
            subtask_vars = {subtask.id: LpVariable(f"subtask_{subtask.id}", 0, 1, cat="Binary") for task in day_tasks for subtask in subtasks_by_task[task.id]}

            # Funcția obiectiv: maximizăm prioritățile subtask-urilor
            problem += lpSum(subtask_vars[subtask.id] * subtask.priority for task in day_tasks for subtask in subtasks_by_task[task.id])

            # Constrângere: timpul total al subtask-urilor nu poate depăși timpul disponibil
            problem += lpSum(subtask_vars[subtask.id] * subtask.duration for task in day_tasks for subtask in subtasks_by_task[task.id]) <= time_available_per_day[day]

            # Constrângere: un task este complet doar dacă toate subtask-urile sunt completate
            for task in day_tasks:
                for subtask in subtasks_by_task[task.id]:
                    problem += subtask_vars[subtask.id] <= task_vars[task.id]

            # Rezolvăm problema
            problem.solve()

            # Generăm rezultatele pentru ziua curentă
            tasks_to_do = []
            subtasks_to_do = []
            subtasks_to_skip = []

            for task in day_tasks:
                if task_vars[task.id].varValue == 1:
                    tasks_to_do.append({"id": task.id, "name": task.name})
                for subtask in subtasks_by_task[task.id]:
                    if subtask_vars[subtask.id].varValue == 1:
                        subtasks_to_do.append({"id": subtask.id, "name": subtask.name, "task_id": task.id})
                    else:
                        subtasks_to_skip.append({"id": subtask.id, "name": subtask.name, "task_id": task.id})

            # Rezultatele pentru zi
            optimization_results[day] = {
                "tasks_to_do": tasks_to_do,
                "subtasks_to_do": subtasks_to_do,
                "subtasks_to_skip": subtasks_to_skip,
            }

        # Returnăm rezultatele ca JSON
        return jsonify({"success": True, "optimization_results": optimization_results})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == '__main__':
    app.run(debug=True)
