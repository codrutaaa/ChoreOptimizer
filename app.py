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
            # Preluăm datele din formular
            name = request.form['name']
            category = request.form['category']
            day = request.form['day']
            duration = float(request.form['duration'])

            # Validăm dacă toate câmpurile sunt completate corect
            if duration <= 0:
                return "Durata trebuie să fie un număr pozitiv.", 400

            # Creăm task-ul și îl adăugăm în baza de date
            new_task = Task(name=name, category=category, day=day, duration=duration)
            db.session.add(new_task)
            db.session.commit()
            return redirect('/')
        except KeyError as e:
            return f"Lipsesc câmpurile necesare: {str(e)}", 400
        except ValueError:
            return "Durata trebuie să fie un număr valid.", 400
    return render_template('add_task.html')



@app.route('/add_subtask/<int:task_id>', methods=['POST'])
def add_subtask(task_id):
    name = request.form['name']
    duration = float(request.form['duration'])

    # Găsim task-ul principal
    task = Task.query.get(task_id)
    if not task:
        return "Task-ul principal nu a fost găsit.", 404

    # Calculăm timpul total al subtask-urilor existente
    existing_subtasks = Subtask.query.filter_by(task_id=task_id).all()
    total_subtask_time = sum(subtask.duration for subtask in existing_subtasks)

    # Verificăm dacă noul subtask depășește durata task-ului principal
    if total_subtask_time + duration > task.duration:
        return f"Timpul total al subtask-urilor ({total_subtask_time + duration} ore) depășește durata task-ului principal ({task.duration} ore).", 400

    # Adăugăm subtask-ul dacă validarea trece
    new_subtask = Subtask(name=name, duration=duration, task_id=task_id)
    db.session.add(new_subtask)
    db.session.commit()
    return redirect('/')


@app.route('/optimize', methods=['POST'])
def optimize_tasks():
    try:
        time_available_per_day = request.json['time_available_per_day']  # Ex: {"Luni": 3, "Marți": 4, ...}
        tasks = Task.query.all()
        subtasks = Subtask.query.all()

        tasks_by_day = {day: [task for task in tasks if task.day == day] for day in time_available_per_day.keys()}
        subtasks_by_task = {task.id: [subtask for subtask in subtasks if subtask.task_id == task.id] for task in tasks}

        optimization_results = {}

        for day, day_tasks in tasks_by_day.items():
            problema = LpProblem(f"Optimize_Tasks_{day}", LpMaximize)

            task_vars = {task.id: LpVariable(f"task_{task.id}", 0, 1, cat="Binary") for task in day_tasks}
            subtask_vars = {subtask.id: LpVariable(f"subtask_{subtask.id}", 0, 1, cat="Binary") for task in day_tasks for subtask in subtasks_by_task[task.id]}

            # Funcția obiectiv: maximizăm numărul de subtask-uri finalizate
            problema += lpSum(subtask_vars[subtask.id] for task in day_tasks for subtask in subtasks_by_task[task.id])

            # Constrângere: timpul total nu poate depăși timpul disponibil
            problema += lpSum(subtask_vars[subtask.id] * subtask.duration for task in day_tasks for subtask in subtasks_by_task[task.id]) <= time_available_per_day[day]

            # Constrângere: un task este complet doar dacă toate subtask-urile sale sunt completate
            for task in day_tasks:
                for subtask in subtasks_by_task[task.id]:
                    problema += subtask_vars[subtask.id] <= task_vars[task.id]

            problema.solve()

            tasks_to_do = []
            tasks_to_skip = []
            subtasks_to_do = []
            subtasks_to_skip = []

            for task in day_tasks:
                for subtask in subtasks_by_task[task.id]:
                    if subtask_vars[subtask.id].varValue == 1:
                        subtasks_to_do.append(subtask)
                    else:
                        subtasks_to_skip.append(subtask)

                # Task-ul principal este considerat complet doar dacă toate subtask-urile sale sunt finalizate
                if all(subtask_vars[subtask.id].varValue == 1 for subtask in subtasks_by_task[task.id]):
                    tasks_to_do.append(task)
                else:
                    tasks_to_skip.append(task)

            optimization_results[day] = {
                "tasks_to_do": [{"id": t.id, "name": t.name} for t in tasks_to_do],
                "tasks_to_skip": [{"id": t.id, "name": t.name} for t in tasks_to_skip],
                "subtasks_to_do": [{"id": st.id, "name": st.name} for st in subtasks_to_do],
                "subtasks_to_skip": [{"id": st.id, "name": st.name} for st in subtasks_to_skip],
            }

        return jsonify({"success": True, "optimization_results": optimization_results})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == '__main__':
    app.run(debug=True)
