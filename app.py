
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime, timedelta
import webbrowser
from threading import Timer

app = Flask(__name__)
BUGS_FILE = "bugs.json"

# ================ ПРИОРИТЕТЫ ДЛЯ СОРТИРОВКИ ================

STATUS_ORDER = {
    'new': 0,           # Новые - первые
    'in_progress': 1,   # В работе - вторые
    'fixed': 2,         # Исправленные - третьи
    'closed': 3         # Закрытые - последние
}

PRIORITY_ORDER = {
    'critical': 0,      # Критические - выше
    'high': 1,
    'medium': 2,
    'low': 3
}

# ================ ЗАГРУЗКА/СОХРАНЕНИЕ ДАННЫХ ================

def load_bugs():
    """Загрузка багов из файла"""
    if os.path.exists(BUGS_FILE):
        try:
            with open(BUGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_bugs(bugs):
    """Сохранение багов в файл"""
    with open(BUGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bugs, f, ensure_ascii=False, indent=2)

def sort_bugs(bugs):
    """Сортировка багов: сначала по статусу, потом по приоритету"""
    return sorted(bugs, key=lambda x: (
        STATUS_ORDER.get(x.get('status', 'new'), 999),
        PRIORITY_ORDER.get(x.get('priority', 'medium'), 999),
        -datetime.strptime(x.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M")),
                           "%Y-%m-%d %H:%M").timestamp()
    ))

def clean_old_closed_bugs(bugs):
    """Удаление закрытых багов старше 24 часов"""
    now = datetime.now()
    cleaned_bugs = []

    for bug in bugs:
        if bug.get('status') == 'closed':
            closed_time = datetime.strptime(bug.get('updated_at', bug.get('created_at')), "%Y-%m-%d %H:%M")
            hours_passed = (now - closed_time).total_seconds() / 3600

            if hours_passed < 24:
                hours_left = 24 - hours_passed
                bug['hours_until_delete'] = round(hours_left, 1)
                cleaned_bugs.append(bug)
        else:
            cleaned_bugs.append(bug)

    return cleaned_bugs

# ================ ГЛАВНАЯ СТРАНИЦА ================

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Баг-трекер КЭТ</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: Arial, sans-serif; 
            background: #f0f2f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        
        /* Шапка */
        .header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; }
        .header a {
            color: white;
            text-decoration: none;
            background: #3498db;
            padding: 10px 20px;
            border-radius: 5px;
            margin-left: 10px;
        }
        
        /* Статистика */
        .stats {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .stat-number {
            font-size: 32px;
            font-weight: bold;
            color: #2c3e50;
        }
        
        /* Форма быстрого добавления */
        .quick-add {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .quick-add h3 {
            color: #2c3e50;
            margin-bottom: 15px;
        }
        .quick-add-form {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr auto;
            gap: 10px;
        }
        .quick-add-form input, .quick-add-form select {
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        .quick-add-form button {
            padding: 10px 20px;
            background: #27ae60;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        .quick-add-form button:hover {
            background: #219a52;
        }
        
        /* Поиск */
        .search-box {
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .search-box input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        
        /* Список багов */
        .bug-list {
            display: grid;
            gap: 15px;
        }
        .bug-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            border-left: 5px solid #3498db;
            transition: transform 0.2s, opacity 0.2s;
        }
        .bug-card:hover { transform: translateX(5px); }
        
        /* Стили для разных статусов */
        .bug-card.status-new { background: #fff; }
        .bug-card.status-in_progress { background: #fff3e0; }
        .bug-card.status-fixed { background: #e8f5e8; }
        .bug-card.status-closed { 
            background: #f0f0f0; 
            opacity: 0.8;
            border-left-color: #95a5a6;
        }
        
        /* Цвета приоритетов */
        .bug-card.priority-critical { border-left-color: #e74c3c; }
        .bug-card.priority-high { border-left-color: #f39c12; }
        .bug-card.priority-medium { border-left-color: #f1c40f; }
        .bug-card.priority-low { border-left-color: #2ecc71; }
        
        .bug-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .bug-title {
            font-size: 18px;
            font-weight: bold;
        }
        .bug-title a {
            color: #2c3e50;
            text-decoration: none;
        }
        .bug-title a:hover { color: #3498db; }
        
        .badge {
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 5px;
        }
        .badge.critical { background: #e74c3c; color: white; }
        .badge.high { background: #f39c12; color: white; }
        .badge.medium { background: #f1c40f; color: black; }
        .badge.low { background: #2ecc71; color: white; }
        .badge.new { background: #3498db; color: white; }
        .badge.progress { background: #f39c12; color: white; }
        .badge.fixed { background: #27ae60; color: white; }
        .badge.closed { background: #95a5a6; color: white; }
        
        .bug-info {
            display: flex;
            gap: 20px;
            color: #7f8c8d;
            font-size: 14px;
            margin: 10px 0;
            flex-wrap: wrap;
        }
        
        .bug-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #ecf0f1;
        }
        
        /* Информация об автоудалении */
        .auto-delete-info {
            font-size: 12px;
            color: #e74c3c;
            margin-top: 5px;
            padding: 5px;
            background: #fde8e8;
            border-radius: 5px;
            text-align: center;
        }
        
        /* Кнопка добавления */
        .add-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: #e74c3c;
            color: white;
            font-size: 30px;
            text-align: center;
            line-height: 60px;
            text-decoration: none;
            box-shadow: 0 5px 15px rgba(231, 76, 60, 0.4);
            display: none; /* Скрываем, так как есть быстрая форма */
        }
        
        /* Кнопки */
        .btn {
            padding: 8px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            margin: 2px;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-secondary { background: #95a5a6; color: white; }
        
        .empty-state {
            text-align: center;
            padding: 50px;
            background: white;
            border-radius: 10px;
            color: #7f8c8d;
        }
        
        /* Легенда сортировки */
        .sort-legend {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            padding: 10px;
            background: white;
            border-radius: 5px;
            font-size: 12px;
            color: #7f8c8d;
        }
        .sort-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .sort-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .sort-dot.new { background: #3498db; }
        .sort-dot.progress { background: #f39c12; }
        .sort-dot.fixed { background: #27ae60; }
        .sort-dot.closed { background: #95a5a6; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Шапка -->
        <div class="header">
            <h1>Баг-трекер</h1>
            <div>
                <a href="/stats">Статистика</a>
                <a href="/import">Импорт из тестов</a>
                <a href="/add" class="btn btn-primary">Подробное добавление</a>
            </div>
        </div>
        
        <!-- Статистика -->
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total }}</div>
                <div>Всего багов</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.new }}</div>
                <div>Новых</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.critical }}</div>
                <div>🔴 Критических</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.in_progress }}</div>
                <div>В работе</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats.closed_today }}</div>
                <div>Закрыто сегодня</div>
            </div>
        </div>
        
        <!-- Быстрое добавление бага -->
        <div class="quick-add">
            <h3>⚡ Быстрое добавление бага</h3>
            <form class="quick-add-form" method="POST" action="/quick-add">
                <input type="text" name="title" placeholder="Название бага" required>
                <select name="priority">
                    <option value="critical">🔴 Критический</option>
                    <option value="high">🟠 Высокий</option>
                    <option value="medium" selected>🟡 Средний</option>
                    <option value="low">🔵 Низкий</option>
                </select>
                <select name="category">
                    <option value="auth">Авторизация</option>
                    <option value="employees">Сотрудники</option>
                    <option value="departments">Отделы</option>
                    <option value="ui">Интерфейс</option>
                    <option value="api">API</option>
                    <option value="other">Другое</option>
                </select>
                <button type="submit">Добавить</button>
            </form>
        </div>
        
        <!-- Легенда сортировки -->
        <div class="sort-legend">
            <div class="sort-item">
                <span class="sort-dot new"></span>
                <span>Новые (вверху)</span>
            </div>
            <div class="sort-item">
                <span class="sort-dot progress"></span>
                <span>В работе</span>
            </div>
            <div class="sort-item">
                <span class="sort-dot fixed"></span>
                <span>Исправленные</span>
            </div>
            <div class="sort-item">
                <span class="sort-dot closed"></span>
                <span>Закрытые (будут удалены через 24ч)</span>
            </div>
        </div>
        
        <!-- Поиск -->
        <div class="search-box">
            <form method="GET">
                <input type="text" name="search" placeholder="🔍 Поиск по названию..." value="{{ search }}">
            </form>
        </div>
        
        <!-- Список багов -->
        <div class="bug-list">
            {% if bugs %}
                {% for bug in bugs %}
                <div class="bug-card priority-{{ bug.priority }} status-{{ bug.status }}" id="bug-{{ bug.id }}">
                    <div class="bug-header">
                        <div class="bug-title">
                            <a href="/bug/{{ bug.id }}">#{{ bug.id }}: {{ bug.title }}</a>
                        </div>
                        <div>
                            <span class="badge {{ bug.priority }}">{{ bug.priority_display }}</span>
                            <span class="badge {{ bug.status }}">{{ bug.status_display }}</span>
                        </div>
                    </div>
                    
                    <div class="bug-info">
                        <span>{{ bug.category_display }}</span>
                        <span>{{ bug.assigned_to or 'не назначен' }}</span>
                        <span>{{ bug.created_at[:10] }}</span>
                        {% if bug.related_req %}
                        <span>{{ bug.related_req }}</span>
                        {% endif %}
                    </div>
                    
                    <div class="bug-footer">
                        <small>{{ bug.description[:100] }}...</small>
                        <div>
                            <a href="/bug/{{ bug.id }}" class="btn btn-primary">Подробнее</a>
                            {% if bug.status != 'closed' %}
                            <button class="btn btn-success" onclick="quickClose({{ bug.id }})">✔️ Закрыть</button>
                            {% endif %}
                        </div>
                    </div>
                    
                    {% if bug.status == 'closed' and bug.hours_until_delete %}
                    <div class="auto-delete-info">
                        Автоудаление через {{ bug.hours_until_delete }} ч.
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h3>Багов пока нет</h3>
                    <p>Используйте форму быстрого добавления выше</p>
                </div>
            {% endif %}
        </div>
    </div>
    
    <script>
        function quickClose(bugId) {
            if (confirm('Закрыть баг? Он будет автоматически удален через 24 часа')) {
                fetch('/api/update_status', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: bugId, status: 'closed'})
                }).then(() => location.reload());
            }
        }
        
        // Автоматическое обновление каждые 30 секунд
        setInterval(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

# ================ СТРАНИЦА ДОБАВЛЕНИЯ ================

ADD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Добавить баг</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f0f2f5;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        .form-card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #2c3e50;
            font-weight: bold;
        }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        textarea {
            min-height: 100px;
            resize: vertical;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-right: 10px;
        }
        .btn-primary {
            background: #3498db;
            color: white;
        }
        .btn-secondary {
            background: #95a5a6;
            color: white;
        }
        .btn:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="form-card">
            <h1>Подробное добавление бага</h1>
            
            <form method="POST">
                <div class="form-group">
                    <label>Название *</label>
                    <input type="text" name="title" required>
                </div>
                
                <div class="form-group">
                    <label>Описание *</label>
                    <textarea name="description" required></textarea>
                </div>
                
                <div class="form-group">
                    <label>Приоритет</label>
                    <select name="priority">
                        <option value="critical">🔴 Критический</option>
                        <option value="high">🟠 Высокий</option>
                        <option value="medium" selected>🟡 Средний</option>
                        <option value="low">🔵 Низкий</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Категория</label>
                    <select name="category">
                        <option value="auth">Авторизация</option>
                        <option value="employees">Сотрудники</option>
                        <option value="departments">Отделы</option>
                        <option value="ui">Интерфейс</option>
                        <option value="api">API</option>
                        <option value="other">Другое</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Автор</label>
                    <input type="text" name="author" value="Тестировщик">
                </div>
                
                <div class="form-group">
                    <label>Связанное требование (FR-...)</label>
                    <input type="text" name="related_req" placeholder="FR-08">
                </div>
                
                <div>
                    <button type="submit" class="btn btn-primary">Создать баг</button>
                    <a href="/" class="btn btn-secondary">Отмена</a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

# ================ ДЕТАЛЬНАЯ СТРАНИЦА ================

DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Баг #{{ bug.id }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f0f2f5;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .bug-card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        h1 {
            color: #2c3e50;
            margin: 0;
        }
        .badge {
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
            margin-left: 5px;
        }
        .badge.critical { background: #e74c3c; color: white; }
        .badge.high { background: #f39c12; color: white; }
        .badge.medium { background: #f1c40f; color: black; }
        .badge.low { background: #2ecc71; color: white; }
        .badge.new { background: #3498db; color: white; }
        .badge.progress { background: #f39c12; color: white; }
        .badge.fixed { background: #27ae60; color: white; }
        .badge.closed { background: #95a5a6; color: white; }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .info-item {
            text-align: center;
        }
        .info-label {
            color: #7f8c8d;
            font-size: 12px;
        }
        .info-value {
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .description {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            line-height: 1.6;
        }
        
        .actions {
            display: flex;
            gap: 10px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
        }
        .btn-warning { background: #f39c12; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-primary { background: #3498db; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #3498db;
            text-decoration: none;
        }
        
        .delete-info {
            margin-top: 20px;
            padding: 10px;
            background: #f8d7da;
            border-radius: 5px;
            color: #721c24;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="bug-card">
            <div class="header">
                <h1>#{{ bug.id }}: {{ bug.title }}</h1>
                <div>
                    <span class="badge {{ bug.priority }}">{{ bug.priority_display }}</span>
                    <span class="badge {{ bug.status }}">{{ bug.status_display }}</span>
                </div>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Создан</div>
                    <div class="info-value">{{ bug.created_at }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Автор</div>
                    <div class="info-value">{{ bug.created_by }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Категория</div>
                    <div class="info-value">{{ bug.category_display }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Назначен</div>
                    <div class="info-value" id="assigned">{{ bug.assigned_to or 'не назначен' }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Требование</div>
                    <div class="info-value">{{ bug.related_req or 'не указано' }}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Обновлен</div>
                    <div class="info-value">{{ bug.updated_at[:10] }}</div>
                </div>
            </div>
            
            <h3>Описание</h3>
            <div class="description">
                {{ bug.description }}
            </div>
            
            <h3>⚡ Действия</h3>
            <div class="actions">
                <button class="btn btn-warning" onclick="updateStatus('{{ bug.id }}', 'in_progress')">
                    Взять в работу
                </button>
                <button class="btn btn-success" onclick="updateStatus('{{ bug.id }}', 'fixed')">
                    Исправлен
                </button>
                <button class="btn btn-secondary" onclick="updateStatus('{{ bug.id }}', 'closed')">
                    Закрыть (удалится через 24ч)
                </button>
                <button class="btn btn-primary" onclick="assignToMe('{{ bug.id }}')">
                    Назначить на меня
                </button>
                <a href="/bug/{{ bug.id }}/delete" class="btn btn-danger" 
                   onclick="return confirm('Удалить баг навсегда?')">
                    🗑Удалить сейчас
                </a>
            </div>
            
            {% if bug.status == 'closed' %}
            <div class="delete-info">
                Этот баг будет автоматически удален через 24 часа после закрытия
            </div>
            {% endif %}
            
            <a href="/" class="back-link">← Назад к списку</a>
        </div>
    </div>
    
    <script>
        function updateStatus(bugId, status) {
            fetch('/api/update_status', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: bugId, status: status})
            }).then(() => location.reload());
        }
        
        function assignToMe(bugId) {
            fetch('/api/assign', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: bugId, assignee: 'Текущий пользователь'})
            }).then(() => location.reload());
        }
    </script>
</body>
</html>
"""

# ================ СТАТИСТИКА ================

STATS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Статистика</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #f0f2f5;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        .card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 30px;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid #ecf0f1;
        }
        .stat-label {
            color: #7f8c8d;
        }
        .stat-value {
            font-weight: bold;
            color: #2c3e50;
        }
        .total {
            font-size: 48px;
            color: #3498db;
            text-align: center;
            margin: 20px 0;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #3498db;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>Статистика по багам</h1>
            
            <div class="total">{{ stats.total }}</div>
            
            <h3>По статусам:</h3>
            {% for status, count in stats.by_status.items() %}
            <div class="stat-row">
                <span class="stat-label">{{ status }}</span>
                <span class="stat-value">{{ count }}</span>
            </div>
            {% endfor %}
            
            <h3 style="margin-top: 20px;">По приоритетам:</h3>
            {% for priority, count in stats.by_priority.items() %}
            <div class="stat-row">
                <span class="stat-label">{{ priority }}</span>
                <span class="stat-value">{{ count }}</span>
            </div>
            {% endfor %}
            
            <a href="/" class="back-link">← На главную</a>
        </div>
    </div>
</body>
</html>
"""

# ================ МАРШРУТЫ ================

@app.route('/')
def index():
    """Главная страница"""
    bugs = load_bugs()

    # Автоматическое удаление старых закрытых багов
    bugs = clean_old_closed_bugs(bugs)
    save_bugs(bugs)

    # Поиск
    search = request.args.get('search', '')
    if search:
        bugs = [b for b in bugs if search.lower() in b.get('title', '').lower()]

    # Сортировка
    bugs = sort_bugs(bugs)

    # Добавляем отображаемые значения
    priority_map = {
        'critical': '🔴 Критический',
        'high': '🟠 Высокий',
        'medium': '🟡 Средний',
        'low': '🔵 Низкий'
    }
    status_map = {
        'new': 'Новый',
        'in_progress': 'В работе',
        'fixed': 'Исправлен',
        'closed': 'Закрыт'
    }
    category_map = {
        'auth': 'Авторизация',
        'employees': 'Сотрудники',
        'departments': 'Отделы',
        'ui': 'Интерфейс',
        'api': 'API',
        'other': 'Другое'
    }

    for bug in bugs:
        bug['priority_display'] = priority_map.get(bug.get('priority'), bug.get('priority', ''))
        bug['status_display'] = status_map.get(bug.get('status'), bug.get('status', ''))
        bug['category_display'] = category_map.get(bug.get('category'), bug.get('category', ''))

    # Статистика
    today = datetime.now().strftime("%Y-%m-%d")
    stats = {
        'total': len(bugs),
        'new': len([b for b in bugs if b.get('status') == 'new']),
        'critical': len([b for b in bugs if b.get('priority') == 'critical']),
        'in_progress': len([b for b in bugs if b.get('status') == 'in_progress']),
        'closed_today': len([b for b in bugs if b.get('status') == 'closed' and b.get('updated_at', '')[:10] == today])
    }

    return render_template_string(INDEX_HTML, bugs=bugs, stats=stats, search=search)

@app.route('/add', methods=['GET', 'POST'])
def add_bug():
    """Подробное добавление бага"""
    if request.method == 'POST':
        bugs = load_bugs()

        # Новый ID
        new_id = 1
        if bugs:
            new_id = max([b.get('id', 0) for b in bugs]) + 1

        # Создаем баг
        new_bug = {
            'id': new_id,
            'title': request.form.get('title', ''),
            'description': request.form.get('description', ''),
            'priority': request.form.get('priority', 'medium'),
            'category': request.form.get('category', 'other'),
            'status': 'new',
            'created_by': request.form.get('author', 'Тестировщик'),
            'assigned_to': '',
            'related_req': request.form.get('related_req', ''),
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        bugs.append(new_bug)
        save_bugs(bugs)

        return redirect(url_for('index'))

    return render_template_string(ADD_HTML)

@app.route('/quick-add', methods=['POST'])
def quick_add_bug():
    """Быстрое добавление бага с главной страницы"""
    bugs = load_bugs()

    # Новый ID
    new_id = 1
    if bugs:
        new_id = max([b.get('id', 0) for b in bugs]) + 1

    # Создаем баг с минимальными полями
    new_bug = {
        'id': new_id,
        'title': request.form.get('title', ''),
        'description': 'Быстрое добавление без описания',  # Заполнитель
        'priority': request.form.get('priority', 'medium'),
        'category': request.form.get('category', 'other'),
        'status': 'new',
        'created_by': 'Быстрое добавление',
        'assigned_to': '',
        'related_req': '',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    bugs.append(new_bug)
    save_bugs(bugs)

    return redirect(url_for('index'))

@app.route('/bug/<int:bug_id>')
def bug_detail(bug_id):
    """Детальная страница"""
    bugs = load_bugs()
    bug = next((b for b in bugs if b.get('id') == bug_id), None)

    if not bug:
        return "Баг не найден", 404

    # Добавляем отображаемые значения
    priority_map = {
        'critical': '🔴 Критический',
        'high': '🟠 Высокий',
        'medium': '🟡 Средний',
        'low': '🔵 Низкий'
    }
    status_map = {
        'new': 'Новый',
        'in_progress': 'В работе',
        'fixed': 'Исправлен',
        'closed': 'Закрыт'
    }
    category_map = {
        'auth': 'Авторизация',
        'employees': 'Сотрудники',
        'departments': 'Отделы',
        'ui': 'Интерфейс',
        'api': 'API',
        'other': 'Другое'
    }

    bug['priority_display'] = priority_map.get(bug.get('priority'), bug.get('priority', ''))
    bug['status_display'] = status_map.get(bug.get('status'), bug.get('status', ''))
    bug['category_display'] = category_map.get(bug.get('category'), bug.get('category', ''))

    return render_template_string(DETAIL_HTML, bug=bug)

@app.route('/bug/<int:bug_id>/delete')
def delete_bug(bug_id):
    """Мгновенное удаление бага"""
    bugs = load_bugs()
    bugs = [b for b in bugs if b.get('id') != bug_id]
    save_bugs(bugs)
    return redirect(url_for('index'))

@app.route('/api/update_status', methods=['POST'])
def update_status():
    """Обновление статуса (API)"""
    data = request.get_json()
    bugs = load_bugs()

    for bug in bugs:
        if bug.get('id') == data.get('id'):
            bug['status'] = data.get('status', bug.get('status'))
            bug['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break

    save_bugs(bugs)
    return jsonify({'success': True})

@app.route('/api/assign', methods=['POST'])
def assign():
    """Назначение бага (API)"""
    data = request.get_json()
    bugs = load_bugs()

    for bug in bugs:
        if bug.get('id') == data.get('id'):
            bug['assigned_to'] = data.get('assignee', '')
            bug['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            break

    save_bugs(bugs)
    return jsonify({'success': True})

@app.route('/stats')
def statistics():
    """Статистика"""
    bugs = load_bugs()

    status_map = {
        'new': 'Новый',
        'in_progress': 'В работе',
        'fixed': 'Исправлен',
        'closed': 'Закрыт'
    }
    priority_map = {
        'critical': '🔴 Критический',
        'high': '🟠 Высокий',
        'medium': '🟡 Средний',
        'low': '🔵 Низкий'
    }

    stats = {
        'total': len(bugs),
        'by_status': {},
        'by_priority': {}
    }

    for bug in bugs:
        status = status_map.get(bug.get('status'), bug.get('status', ''))
        stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

        priority = priority_map.get(bug.get('priority'), bug.get('priority', ''))
        stats['by_priority'][priority] = stats['by_priority'].get(priority, 0) + 1

    return render_template_string(STATS_HTML, stats=stats)

@app.route('/import')
def import_from_tests():
    """Импорт из test_report.json"""
    test_file = 'test_report.json'
    imported = 0

    if os.path.exists(test_file):
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                report = json.load(f)

            bugs = load_bugs()
            existing_titles = [b.get('title', '') for b in bugs]

            for result in report.get('results', []):
                if result.get('status') == 'FAIL':
                    title = f"[ТЕСТ] {result.get('name', '')}"
                    if title not in existing_titles:
                        new_id = 1
                        if bugs:
                            new_id = max([b.get('id', 0) for b in bugs]) + 1

                        new_bug = {
                            'id': new_id,
                            'title': title,
                            'description': f"Ошибка в тесте: {result.get('message', '')}",
                            'priority': 'medium',
                            'category': 'other',
                            'status': 'new',
                            'created_by': 'Автотест',
                            'assigned_to': '',
                            'related_req': result.get('requirement_id', ''),
                            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        }
                        bugs.append(new_bug)
                        imported += 1

            if imported > 0:
                save_bugs(bugs)
                return f"Импортировано {imported} багов. <a href='/'>Вернуться</a>"
            else:
                return "Новых багов не найдено. <a href='/'>Вернуться</a>"

        except Exception as e:
            return f"Ошибка: {e}"

    return "Файл test_report.json не найден. Сначала запустите тесты."

def open_browser():
    """Открыть браузер"""
    webbrowser.open('http://localhost:5000')

# ================ ЗАПУСК ================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                      Группа 3-2ИС, 2026                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)


    # Открываем браузер через 1.5 секунды
    Timer(1.5, open_browser).start()

    # Запускаем сервер
    app.run(debug=True, port=5000)