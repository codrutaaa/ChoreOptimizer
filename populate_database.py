from app import app, db, Task, Subtask

def populate_database():
    # Creează contextul aplicației
    with app.app_context():
        # Șterge datele existente (opțional)
        db.drop_all()
        db.create_all()

        # Adaugă sarcini (tasks)
        tasks = [
            Task(name="Clean the kitchen", category="Cleaning", day="Monday", duration=1.5, priority=2),
            Task(name="Do the laundry", category="Housework", day="Tuesday", duration=2.0, priority=3),
            Task(name="Buy groceries", category="Shopping", day="Wednesday", duration=1.0, priority=2),
            Task(name="Study for exam", category="Study", day="Thursday", duration=3.0, priority=5),
            Task(name="Mow the lawn", category="Outdoor", day="Friday", duration=1.5, priority=2),
        ]

        # Adaugă tasks în baza de date
        db.session.add_all(tasks)
        db.session.commit()

        # Adaugă subtasks
        subtasks = [
            Subtask(name="Wipe counters", duration=0.5, task_id=1, priority=1),
            Subtask(name="Clean dishes", duration=0.5, task_id=1, priority=1),
            Subtask(name="Sort clothes", duration=0.5, task_id=2, priority=1),
            Subtask(name="Start washing machine", duration=0.5, task_id=2, priority=1),
            Subtask(name="Pick fruits and vegetables", duration=0.5, task_id=3, priority=1),
            Subtask(name="Read lecture notes", duration=1.5, task_id=4, priority=2),
            Subtask(name="Practice problems", duration=1.5, task_id=4, priority=2),
            Subtask(name="Cut grass", duration=1.0, task_id=5, priority=1),
        ]

        # Adaugă subtasks în baza de date
        db.session.add_all(subtasks)
        db.session.commit()

        print("Database successfully populated with sample data!")

if __name__ == "__main__":
    populate_database()
