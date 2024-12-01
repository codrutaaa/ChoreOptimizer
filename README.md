# Chore Optimizer

Chore Optimizer is a web application designed to help users organize and optimize their daily chores effectively. It simplifies task management by allowing users to plan, break down chores into subtasks, and optimize their time efficiently using advanced algorithms.

---

## Features

- **Organize Chores**: Add and categorize daily chores based on time, duration, and priority.
- **Manage Subtasks**: Break larger chores into smaller, manageable subtasks. The app ensures that the total duration of subtasks does not exceed the main chore's time allocation.
- **Time Optimization**: Enter your available time for a specific day, and the app provides a list of chores and subtasks that can be completed within that time.
- **Modern UI**: Clean, user-friendly design built with Bootstrap.
- **Pop-Up Alerts**: Informative pop-ups notify users about input errors (e.g., exceeding time limits) without redirecting them to another page.
- **Secure Authentication**: Includes signup, login, and logout functionality to manage personalized chore data securely.

---

## How It Works

1. **Add Chores**:
   - Go to "Add Task" to create a chore, providing details like duration, category, and the day it is scheduled for.

2. **Add Subtasks**:
   - On the dashboard, click the "Add Subtask" button under a chore card to define subtasks. Subtasks cannot exceed the total duration of the main chore.

3. **Optimize Chores**:
   - Input your available time for a specific day, and the app uses `PuLP` to optimize which chores and subtasks to complete.

---

## Optimization Algorithm

- **Powered by PuLP**:
  - Chore Optimizer uses `PuLP`, a Python library for linear programming, to maximize productivity.
  - It prioritizes chores and subtasks based on their duration and importance, ensuring the most value is achieved within the available time.

- **Process**:
  - **Inputs**: Task duration, priority, and available time for the day.
  - **Output**: A breakdown of:
    - Chores and subtasks to complete.
    - Chores and subtasks to postpone.

---
