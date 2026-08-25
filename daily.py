import os
import io
import base64
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = 'routine_planner_secret_key'

# Define absolute path to the SQLite database in the current directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'routine_planner.db')

def get_db_connection():
    """Establish and return a database connection with row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the SQLite database with routines table with a clean schema and seed sample tasks if empty."""
    print(f"DEBUG: Using database path -> {DATABASE}")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create routines table ensuring clean structural format
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            period TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            category TEXT NOT NULL DEFAULT 'General'
        )
    ''')

    # Insert default sample tasks if table is empty
    cursor.execute('SELECT COUNT(*) FROM routines')
    count = cursor.fetchone()[0]
    print(f"DEBUG: Existing routines count in DB: {count}")
    
    if count == 0:
        sample_tasks = [
            ('Morning Jog', '06:00 AM', 'AM', 'Monday', 'Completed', 'Health'),
            ('Team Standup', '09:30 AM', 'AM', 'Monday', 'Pending', 'Work'),
            ('Read Book', '02:00 PM', 'PM', 'Monday', 'Pending', 'Personal'),
            ('Gym Workout', '06:00 PM', 'PM', 'Monday', 'Completed', 'Health'),
            ('Review Code', '10:00 AM', 'AM', 'Tuesday', 'Pending', 'Work')
        ]
        cursor.executemany('''
            INSERT INTO routines (title, time_slot, period, day_of_week, status, category)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_tasks)
        conn.commit()
        print("DEBUG: Seeded default sample tasks into database.")
    
    conn.close()

def generate_progress_chart():
    """Generate a base64 encoded matplotlib progress chart based on structured DB records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT day_of_week, status, COUNT(*) FROM routines GROUP BY day_of_week, status')
    data = cursor.fetchall()
    conn.close()

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    completed_counts = {day: 0 for day in days}
    pending_counts = {day: 0 for day in days}

    for row in data:
        day = row['day_of_week']
        status = row['status']
        count_val = row[2]
        if day in completed_counts:
            if status == 'Completed':
                completed_counts[day] = count_val
            else:
                pending_counts[day] = count_val

    comp_vals = [completed_counts[d] for d in days]
    pend_vals = [pending_counts[d] for d in days]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=100)
    fig.patch.set_facecolor('#ffffff')
    ax.set_facecolor('#f8fafc')

    x = range(len(days))
    width = 0.35

    ax.bar([i - width/2 for i in x], comp_vals, width, label='Completed', color='#10b981', edgecolor='#059669', linewidth=1)
    ax.bar([i + width/2 for i in x], pend_vals, width, label='Pending', color='#f59e0b', edgecolor='#d97706', linewidth=1)

    ax.set_ylabel('Number of Tasks', fontsize=11, fontweight='bold', color='#334155')
    ax.set_title('Weekly Routine Progress Overview', fontsize=13, fontweight='bold', color='#1e293b', pad=15)
    ax.set_xticks(list(x))
    ax.set_xticklabels([d[:3] for d in days], fontsize=10, color='#475569')
    ax.legend(frameon=True, facecolor='#ffffff', edgecolor='#e2e8f0')
    ax.grid(axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')

    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['bottom', 'left']:
        ax.spines[spine].set_color('#cbd5e1')

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    chart_url = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)
    return chart_url

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Routine Planner & Progress Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen pb-16">
    <header class="bg-gradient-to-r from-indigo-600 to-violet-600 shadow-md text-white py-5 px-6 mb-8">
        <div class="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
            <div class="flex items-center space-x-3">
                <div class="bg-white/10 p-3 rounded-xl backdrop-blur-md">
                    <i class="fa-solid fa-calendar-check text-2xl text-white"></i>
                </div>
                <div>
                    <h1 class="text-2xl font-bold tracking-tight">Routine Planner & Visual Dashboard</h1>
                    <p class="text-indigo-100 text-sm">Organize your daily AM/PM slots, toggle completion, and monitor performance analytics.</p>
                </div>
            </div>
            <div class="flex items-center gap-3 bg-white/10 backdrop-blur-md px-4 py-2 rounded-xl text-sm font-medium">
                <i class="fa-regular fa-calendar-days"></i>
                <span>Today: <strong class="text-white">{{ today_date }}</strong></span>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-4 rounded-xl text-sm font-medium shadow-sm flex items-center justify-between {% if category == 'success' %}bg-emerald-50 text-emerald-800 border border-emerald-200{% else %}bg-rose-50 text-rose-800 border border-rose-200{% endif %}">
                        <div class="flex items-center gap-2">
                            <i class="fa-solid {% if category == 'success' %}fa-circle-check text-emerald-600{% else %}fa-triangle-exclamation text-rose-600{% endif %}"></i>
                            <span>{{ message }}</span>
                        </div>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between">
                <div>
                    <div class="flex items-center justify-between mb-4">
                        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                            <i class="fa-solid fa-chart-pie text-indigo-600"></i> Visual Progress Analytics
                        </h2>
                    </div>
                    <p class="text-sm text-slate-500 mb-4">Real-time breakdown of routine task performance across days of the week.</p>
                </div>
                <div class="flex justify-center items-center bg-slate-50 rounded-xl p-3 border border-slate-100">
                    {% if chart %}
                        <img src="data:image/png;base64,{{ chart }}" alt="Routine Progress Chart" class="rounded-lg shadow-sm max-h-[320px] w-auto object-contain">
                    {% else %}
                        <p class="text-slate-400 py-12">No data available for charting yet.</p>
                    {% endif %}
                </div>
            </div>

            <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col justify-between">
                <div>
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2 mb-4">
                        <i class="fa-solid fa-plus-circle text-indigo-600"></i> Add Routine Slot
                    </h2>
                    <form action="{{ url_for('add_routine') }}" method="POST" class="space-y-4">
                        <div>
                            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Task Title</label>
                            <input type="text" name="title" required placeholder="e.g., Morning Meditation" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800">
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Time Slot</label>
                                <input type="text" name="time_slot" required placeholder="e.g., 07:00 AM" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800">
                            </div>
                            <div>
                                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">AM / PM</label>
                                <select name="period" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800">
                                    <option value="AM">AM</option>
                                    <option value="PM">PM</option>
                                </select>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Day of Week</label>
                                <select name="day_of_week" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800">
                                    {% for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] %}
                                        <option value="{{ d }}">{{ d }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">Category</label>
                                <select name="category" class="w-full bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800">
                                    <option value="General">General</option>
                                    <option value="Health">Health</option>
                                    <option value="Work">Work</option>
                                    <option value="Personal">Personal</option>
                                    <option value="Study">Study</option>
                                </select>
                            </div>
                        </div>
                        <button type="submit" class="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 px-4 rounded-xl transition shadow-sm text-sm">
                            <i class="fa-solid fa-check mr-2"></i> Save Routine Slot
                        </button>
                    </form>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="p-6 border-b border-slate-100 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        <i class="fa-solid fa-list-check text-indigo-600"></i> Routine Planner Chart & Management
                    </h2>
                    <p class="text-sm text-slate-500">Click on any status pill to quickly toggle between Completed and Pending states.</p>
                </div>
                <form method="GET" action="{{ url_for('index') }}" class="flex items-center gap-2">
                    <label class="text-xs font-semibold text-slate-500 uppercase">Filter Day:</label>
                    <select name="filter_day" onchange="this.form.submit()" class="bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        <option value="All" {% if selected_day == 'All' %}selected{% endif %}>All Days</option>
                        {% for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] %}
                            <option value="{{ d }}" {% if selected_day == d %}selected{% endif %}>{{ d }}</option>
                        {% endfor %}
                    </select>
                </form>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-slate-50 text-slate-500 text-xs font-semibold uppercase tracking-wider border-b border-slate-200">
                            <th class="py-3.5 px-6">Task Title</th>
                            <th class="py-3.5 px-6">Time Slot</th>
                            <th class="py-3.5 px-6">Period</th>
                            <th class="py-3.5 px-6">Day</th>
                            <th class="py-3.5 px-6">Category</th>
                            <th class="py-3.5 px-6">Status (Click to Toggle)</th>
                            <th class="py-3.5 px-6 text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 text-sm">
                        {% if routines %}
                            {% for routine in routines %}
                                <tr class="hover:bg-slate-50/70 transition">
                                    <td class="py-4 px-6 font-medium text-slate-900">{{ routine.title }}</td>
                                    <td class="py-4 px-6 text-slate-600 font-mono">{{ routine.time_slot }}</td>
                                    <td class="py-4 px-6">
                                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold {% if routine.period == 'AM' %}bg-amber-100 text-amber-800 border border-amber-200{% else %}bg-indigo-100 text-indigo-800 border border-indigo-200{% endif %}">
                                            {{ routine.period }}
                                        </span>
                                    </td>
                                    <td class="py-4 px-6 text-slate-700 font-medium">{{ routine.day_of_week }}</td>
                                    <td class="py-4 px-6">
                                        <span class="text-xs bg-slate-100 text-slate-700 px-2.5 py-1 rounded-lg border border-slate-200 font-medium">{{ routine.category }}</span>
                                    </td>
                                    <td class="py-4 px-6">
                                        <a href="{{ url_for('toggle_status', id=routine.id) }}" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition shadow-sm {% if routine.status == 'Completed' %}bg-emerald-100 text-emerald-800 border border-emerald-200 hover:bg-emerald-200{% else %}bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100{% endif %}">
                                            {% if routine.status == 'Completed' %}
                                                <i class="fa-solid fa-check-circle text-emerald-600"></i> Completed
                                            {% else %}
                                                <i class="fa-regular fa-clock text-amber-600"></i> Pending
                                            {% endif %}
                                        </a>
                                    </td>
                                    <td class="py-4 px-6 text-right">
                                        <a href="{{ url_for('delete_routine', id=routine.id) }}" onclick="return confirm('Are you sure you want to delete this routine?')" class="text-slate-400 hover:text-rose-600 p-2 transition">
                                            <i class="fa-solid fa-trash-can"></i>
                                        </a>
                                    </td>
                                </tr>
                            {% endfor %}
                        {% else %}
                            <tr>
                                <td colspan="7" class="py-12 text-center text-slate-400">
                                    <div class="flex flex-col items-center justify-center space-y-2">
                                        <i class="fa-regular fa-folder-open text-3xl"></i>
                                        <p>No routine slots found for the selected view.</p>
                                    </div>
                                </td>
                            </tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <footer class="text-center text-xs text-slate-400 mt-16">
        <p>&copy; 2026 Routine Planner Dashboard. Powered by Flask, SQLite & Matplotlib.</p>
    </footer>
</body>
</html>
"""

@app.route('/')
def index():
    """Render main dashboard with structured routines list and Matplotlib chart."""
    selected_day = request.args.get('filter_day', 'All')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if selected_day != 'All':
        cursor.execute('SELECT * FROM routines WHERE day_of_week = ? ORDER BY id DESC', (selected_day,))
    else:
        cursor.execute('SELECT * FROM routines ORDER BY id DESC')
        
    routines = cursor.fetchall()
    conn.close()

    chart_base64 = generate_progress_chart()
    today_str = datetime.now().strftime('%A, %B %d, %Y')

    return render_template_string(
        TEMPLATE,
        routines=routines,
        chart=chart_base64,
        selected_day=selected_day,
        today_date=today_str
    )

@app.route('/add', methods=['POST'])
def add_routine():
    """Add a new structured routine task to the database."""
    title = request.form.get('title')
    time_slot = request.form.get('time_slot')
    period = request.form.get('period', 'AM')
    day_of_week = request.form.get('day_of_week', 'Monday')
    category = request.form.get('category', 'General')

    if title and time_slot:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO routines (title, time_slot, period, day_of_week, status, category)
            VALUES (?, ?, ?, ?, 'Pending', ?)
        ''', (title, time_slot, period, day_of_week, category))
        conn.commit()
        conn.close()
        flash('Routine time slot successfully saved to database!', 'success')
    else:
        flash('Please fill in all required task fields.', 'error')

    return redirect(url_for('index'))

@app.route('/toggle/<int:id>')
def toggle_status(id):
    """Toggle routine task status between Completed and Pending in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM routines WHERE id = ?', (id,))
    row = cursor.fetchone()
    
    if row:
        new_status = 'Pending' if row['status'] == 'Completed' else 'Completed'
        conn.execute('UPDATE routines SET status = ? WHERE id = ?', (new_status, id))
        conn.commit()
        flash(f'Routine status updated to {new_status} in DB!', 'success')
        
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_routine(id):
    """Delete a routine task from database."""
    conn = get_db_connection()
    conn.execute('DELETE FROM routines WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Routine slot deleted from database successfully.', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Check if existing database is corrupted or unstructured, recreate cleanly if necessary
    if os.path.exists(DATABASE):
        try:
            conn = sqlite3.connect(DATABASE)
            conn.execute('SELECT COUNT(*) FROM routines')
            conn.close()
        except sqlite3.OperationalError:
            print("WARNING: Existing database file is corrupted or unstructured. Recreating clean database...")
            os.remove(DATABASE)
            
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)