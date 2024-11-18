from flask import Flask, render_template, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
from pulp import LpMaximize, LpProblem, LpVariable, lpSum

app = Flask(__name__)

# Configurare MySQL
app.secret_key = 'my_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/oro_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Modele de date
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    duration = db.Column(db.Float, nullable=False)  # Durata în ore
    completed = db.Column(db.Boolean, default=False)


class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Float, nullable=False)  # Durata în ore
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)


# Crearea bazei de date
with app.app_context():
    db.create_all()


@app.route('/')
def index():
    tasks = Task.query.all()
    subtasks = Subtask.query.all()
    return render_template('index.html', tasks=tasks, subtasks=subtasks)


@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        try:
            name = request.form['name']
            category = request.form['category']
            day = request.form['day']
            duration = float(request.form['duration'])  # Asigură-te că valoarea este numerică

            new_task = Task(name=name, category=category, day=day, duration=duration)
            db.session.add(new_task)
            db.session.commit()
            return redirect('/')
        except KeyError as e:
            return f"Lipsesc datele necesare: {str(e)}", 400
        except ValueError:
            return "Durata trebuie să fie un număr valid.", 400
    return render_template('add_task.html')


@app.route('/add_subtask/<int:task_id>', methods=['POST'])
def add_subtask(task_id):
    name = request.form['name']
    duration = float(request.form['duration'])
    new_subtask = Subtask(name=name, duration=duration, task_id=task_id)
    db.session.add(new_subtask)
    db.session.commit()
    return redirect('/')


@app.route('/optimize', methods=['POST'])
def optimize_tasks():
    try:
        time_available = float(request.json['time_available'])

        # Luăm toate sarcinile și subtasks
        tasks = Task.query.all()
        subtasks = Subtask.query.all()

        # Creăm modelul de optimizare
        problema = LpProblem("Optimize_Tasks", LpMaximize)

        # Variabile de decizie
        task_vars = {task.id: LpVariable(f"task_{task.id}", 0, 1, cat="Binary") for task in tasks}
        subtask_vars = {subtask.id: LpVariable(f"subtask_{subtask.id}", 0, 1, cat="Binary") for subtask in subtasks}

        # Funcția obiectiv: maximizăm numărul de sarcini și subtasks finalizate
        problema += lpSum(task_vars[task.id] for task in tasks) + lpSum(
            subtask_vars[subtask.id] for subtask in subtasks)

        # Constrângere: timpul total nu poate depăși timpul disponibil
        problema += lpSum(task_vars[task.id] * task.duration for task in tasks) + \
                    lpSum(subtask_vars[subtask.id] * subtask.duration for subtask in subtasks) <= time_available

        # Constrângere: o subtask poate fi finalizată doar dacă sarcina principală este completată
        for subtask in subtasks:
            problema += subtask_vars[subtask.id] <= task_vars[subtask.task_id]

        # Rezolvăm problema
        problema.solve()

        # Organizăm rezultatele
        tasks_to_do = []
        tasks_to_skip = []
        subtasks_to_do = []
        subtasks_to_skip = []

        for task in tasks:
            if task_vars[task.id].varValue == 1:
                tasks_to_do.append(task)
            else:
                tasks_to_skip.append(task)

        for subtask in subtasks:
            if subtask_vars[subtask.id].varValue == 1:
                subtasks_to_do.append(subtask)
            else:
                subtasks_to_skip.append(subtask)

        # Reprogramăm sarcinile omise
        for task in tasks_to_skip:
            task.day = get_next_available_day(task.day)  # Funcție pentru a găsi ziua următoare liberă
            db.session.commit()

        for subtask in subtasks_to_skip:
            parent_task = Task.query.get(subtask.task_id)
            subtask.task_id = parent_task.id
            subtask.completed = False
            db.session.commit()

        # Returnăm rezultatele într-un format clar
        return jsonify({
            "success": True,
            "tasks_to_do": [{"id": t.id, "name": t.name} for t in tasks_to_do],
            "tasks_to_skip": [{"id": t.id, "name": t.name} for t in tasks_to_skip],
            "subtasks_to_do": [{"id": st.id, "name": st.name} for st in subtasks_to_do],
            "subtasks_to_skip": [{"id": st.id, "name": st.name} for st in subtasks_to_skip],
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# Funcție pentru a găsi următoarea zi liberă
def get_next_available_day(current_day):
    days = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]
    current_index = days.index(current_day)
    next_index = (current_index + 1) % len(days)
    return days[next_index]


if __name__ == '__main__':
    app.run(debug=True)
