from flask import Flask, render_template, request, redirect, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pulp import LpMaximize, LpProblem, LpVariable, lpSum
from flask import flash
from datetime import datetime, timedelta

app = Flask(__name__)

# MySQL configuration
app.secret_key = 'my_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/oro_app'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Database models for usr, task and subtask
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

# Create table in db
with app.app_context():
    db.create_all()

# Decorator for authentication
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


# Route to redirect to landing page
@app.route('/')
def root():
    return redirect('/landing')

# Route to redirect to landing page
@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        #Process form data
        username = request.form['username']
        password = request.form['password']
        # hashing the password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        # check if the username alredy exist in db
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "Numele de utilizator este deja folosit.", 400

        # add new the user in the db
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

        # check the username and password
        user = User.query.filter_by(username=username).first()
        # Validate username and password
        if not user or not check_password_hash(user.password, password):
            return "The name is already used", 400

        # store user's info in the session
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect('/index')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect('/landing')

# display the dashboard with all the chores
@app.route('/index')
@login_required
def index():
    tasks = Task.query.all() # Retrieve all tasks from the database
    subtasks = Subtask.query.all() # Retrieve all subtasks from the database
    optimization_results = session.get('optimization_results', {})   # Get optimization results from the session.
    return render_template('index.html', tasks=tasks, subtasks=subtasks, optimization_results=optimization_results)

# route to optimize tasks for a specific day
@app.route('/optimize_day/<day>', methods=['POST'])
@login_required
def optimize_day(day):
    try:
        # Get available time for the day
        time_available = float(request.form['time_available'])

        # Fetch tasks and subtasks for the day
        tasks = Task.query.filter_by(day=day).all()
        subtasks = Subtask.query.filter(Subtask.task_id.in_([task.id for task in tasks])).all()

        # Group subtasks by task
        subtasks_by_task = {task.id: [subtask for subtask in subtasks if subtask.task_id == task.id] for task in tasks}

        # Define the linear progr problem for optimization
        problem = LpProblem(f"Optimize_Chores_{day}", LpMaximize)

        # Decision variables fro tasks (1 if is selected or 0 otherwise)
        task_vars = {task.id: LpVariable(f"task_{task.id}", 0, 1, cat="Binary") for task in tasks}
        subtask_vars = {subtask.id: LpVariable(f"subtask_{subtask.id}", 0, 1, cat="Binary") for subtask in subtasks}

        # Objective: Maximize the total priority of all task and subtasks
        problem += lpSum(
            task_vars[task.id] * task.priority +
            lpSum(subtask_vars[subtask.id] * subtask.priority for subtask in subtasks_by_task[task.id])
            for task in tasks
        )

        # Constraint: Total duration of seleted tasks and subtask cannot exceed available time
        problem += lpSum(
            task_vars[task.id] * task.duration +
            lpSum(subtask_vars[subtask.id] * subtask.duration for subtask in subtasks_by_task[task.id])
            for task in tasks
        ) <= time_available

        # Constraint: Subtasks can only be done if their task is done
        for task in tasks:
            for subtask in subtasks_by_task[task.id]:
                problem += subtask_vars[subtask.id] <= task_vars[task.id]

        # Solve the optimization problem
        problem.solve()

        # Process results
        tasks_to_do = [] # List of tasks to complete
        tasks_to_skip = [] # List of tasks to skip

        for task in tasks:
            # check the value of the variable to find if the task is selected
            if task_vars[task.id].varValue == 1:
                tasks_to_do.append(task)
            else:
                tasks_to_skip.append(task)

        # Reschedule skipped tasks to the next day
        for task in tasks_to_skip:
            task.day = get_next_day(task.day) # aasign the next day
            db.session.commit()

        # Save optimization results in session
        session['optimization_results'] = {
            day: {
                "tasks_to_do": [{"id": t.id, "name": t.name, "duration": t.duration} for t in tasks_to_do],
                "tasks_to_skip": [{"id": t.id, "name": t.name, "duration": t.duration} for t in tasks_to_skip],
            }
        }
        session.modified = True

        return redirect('/index')
    except Exception as e:
        return f"An error occurred during optimization: {str(e)}", 400


@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if request.method == 'POST':
        try:
            # extract data from the form
            name = request.form['name']
            category = request.form['category']
            day = request.form['day']
            priority = int(request.form['priority'])
            duration = float(request.form['duration'])

            # validate the data that was introduced
            if not name.strip() or not category.strip() or priority < 1 or duration <= 0:
                return "Invalid input data.", 400

            # create a new object Task
            new_task = Task(name=name, category=category, day=day, priority=priority, duration=duration)

            db.session.add(new_task)
            db.session.commit()

            # redirect to dashboard
            return redirect('/index')
        except Exception as e:
            return f"An error occurred: {str(e)}", 400
    return render_template('add_task.html')

@app.route('/add_subtask/<int:task_id>', methods=['POST'])
@login_required
def add_subtask(task_id):
    try:
        # Get the form data
        name = request.form['name']
        hours = float(request.form['hours'])
        minutes = int(request.form['minutes'])
        duration = hours + minutes / 60

        # Fetch the main task
        task = Task.query.get(task_id)
        if not task:
            return "Task not found", 404

        # Validate the total subtask duration
        existing_subtasks = Subtask.query.filter_by(task_id=task_id).all()
        total_subtask_time = sum(subtask.duration for subtask in existing_subtasks)
        if total_subtask_time + duration > task.duration:
            flash(f"Total subtask time exceeds the main task duration of {task.duration} hours.", "danger")
            return redirect('/index')

        # Add the subtask
        new_subtask = Subtask(name=name, duration=duration, task_id=task_id)
        db.session.add(new_subtask)
        db.session.commit()

        # Redirect back to the dashboard
        return redirect('/index')
    except Exception as e:
        return f"Error: {str(e)}", 400

@app.route('/optimize', methods=['POST'])
@login_required
def optimize_tasks():
    try:
        # Get the available time for each day from the user.
        time_available_per_day = request.json['time_available_per_day']

        # Fetch the tasks and subtasks
        tasks = Task.query.all()
        subtasks = Subtask.query.all()

        # group the tasks by days
        tasks_by_day = {day: [task for task in tasks if task.day == day] for day in time_available_per_day.keys()}
        # group the subtask by the parent task
        subtasks_by_task = {task.id: [subtask for subtask in subtasks if subtask.task_id == task.id] for task in tasks}

        optimization_results = {}

        # optimization for each day
        for day, day_tasks in tasks_by_day.items():
            # define the optimization problem
            problem = LpProblem(f"Optimize_Tasks_{day}", LpMaximize)

            # decisions variables for task and subtasks
            task_vars = {task.id: LpVariable(f"task_{task.id}", 0, 1, cat="Binary") for task in day_tasks}
            subtask_vars = {subtask.id: LpVariable(f"subtask_{subtask.id}", 0, 1, cat="Binary") for task in day_tasks for subtask in subtasks_by_task[task.id]}

            # Objective: Maximize priority of subtasks
            problem += lpSum(subtask_vars[subtask.id] * subtask.priority for task in day_tasks for subtask in subtasks_by_task[task.id])

            # Constraint: total time of subtasks cannot exceed the available time
            problem += lpSum(subtask_vars[subtask.id] * subtask.duration for task in day_tasks for subtask in subtasks_by_task[task.id]) <= time_available_per_day[day]

            # Constraint: tasks are considered complete only if all subtask are completed
            for task in day_tasks:
                for subtask in subtasks_by_task[task.id]:
                    problem += subtask_vars[subtask.id] <= task_vars[task.id]

            # solve the problem
            problem.solve()

            # process results for the curent day
            tasks_to_do = []
            subtasks_to_do = []
            subtasks_to_skip = []

            for task in day_tasks:
                if task_vars[task.id].varValue == 1: # Check if task is selected.
                    tasks_to_do.append({"id": task.id, "name": task.name})
                for subtask in subtasks_by_task[task.id]:
                    if subtask_vars[subtask.id].varValue == 1: # Check if subtask is selected.
                        subtasks_to_do.append({"id": subtask.id, "name": subtask.name, "task_id": task.id})
                    else:
                        subtasks_to_skip.append({"id": subtask.id, "name": subtask.name, "task_id": task.id})

            # store the results for the current day
            optimization_results[day] = {
                "tasks_to_do": tasks_to_do,
                "subtasks_to_do": subtasks_to_do,
                "subtasks_to_skip": subtasks_to_skip,
            }

        # return the results as a JSON
        return jsonify({"success": True, "optimization_results": optimization_results})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# function to get the next day
def get_next_day(current_day):
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    current_index = days_of_week.index(current_day) # Find the index of the current day.
    next_index = (current_index + 1) % len(days_of_week)
    return days_of_week[next_index]

# route to reschedule a task
@app.route('/reschedule/<int:task_id>', methods=['POST'])
@login_required
def reschedule_task(task_id):
    try:
        # Fetch the task by its ID
        task = Task.query.get(task_id)
        if not task:
            return "Task not found.", 404

        # Get the next day
        next_day = get_next_day(task.day)

        # update the task's day to the next day
        task.day = next_day
        db.session.commit()

        # Redirect back to the dashboard
        return redirect('/index')
    except Exception as e:
        return f"Error: {str(e)}", 400

@app.route('/delete_task/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    try:
        task = Task.query.get(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        # Șterge și subtasks asociate
        Subtask.query.filter_by(task_id=task_id).delete()
        db.session.delete(task)
        db.session.commit()

        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
