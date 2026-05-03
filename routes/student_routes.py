<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>إدارة المقررات — جامعة حائل</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --navy:     #0b3c5d;
            --navy-mid: #0d4f7a;
            --navy-lt:  #1a6494;
            --bg:       #f0f4f8;
            --white:    #ffffff;
            --text:     #1a2332;
            --muted:    #64748b;
            --danger:   #dc2626;
            --danger-lt:#fee2e2;
            --success:  #16a34a;
            --success-lt:#dcfce7;
            --border:   #dde4ed;
            --shadow:   0 4px 24px rgba(11,60,93,.10);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Tajawal', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

        /* HEADER */
        .top-header {
            background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 60%, var(--navy-lt) 100%);
            padding: 0 40px; display: flex; align-items: center;
            justify-content: space-between; height: 70px;
            box-shadow: 0 2px 20px rgba(0,0,0,.2);
            position: sticky; top: 0; z-index: 100;
        }
        .logo { display: flex; align-items: center; gap: 12px; color: var(--white); }
        .logo-icon {
            width: 42px; height: 42px; background: rgba(255,255,255,.12);
            border-radius: 10px; display: flex; align-items: center;
            justify-content: center; font-size: 22px;
            border: 1px solid rgba(255,255,255,.2);
        }
        .logo-text { font-size: 18px; font-weight: 700; }
        .logo-sub  { font-size: 12px; opacity: .7; font-weight: 400; }
        .back-btn {
            display: flex; align-items: center; gap: 8px;
            color: rgba(255,255,255,.85); text-decoration: none;
            font-size: 14px; font-weight: 500;
            background: rgba(255,255,255,.1);
            border: 1px solid rgba(255,255,255,.2);
            border-radius: 9px; padding: 8px 16px; transition: all .2s;
        }
        .back-btn:hover { background: rgba(255,255,255,.2); color: var(--white); }

        /* PAGE */
        .page { max-width: 1300px; margin: 0 auto; padding: 36px 24px; display: flex; flex-direction: column; gap: 28px; }

        /* CARD */
        .card { background: var(--white); border-radius: 18px; box-shadow: var(--shadow); overflow: hidden; }
        .card-header {
            background: linear-gradient(135deg, var(--navy) 0%, var(--navy-mid) 100%);
            padding: 22px 28px; display: flex; align-items: center; gap: 12px;
        }
        .card-header-icon {
            width: 40px; height: 40px; background: rgba(255,255,255,.15);
            border-radius: 10px; display: flex; align-items: center;
            justify-content: center; font-size: 18px;
        }
        .card-header h2 { color: var(--white); font-size: 17px; font-weight: 700; }
        .card-header p  { color: rgba(255,255,255,.65); font-size: 12px; margin-top: 2px; }
        .card-body { padding: 28px; }

        /* FORM */
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-full  { grid-column: 1 / -1; }
        .form-group label { font-size: 13px; font-weight: 600; color: var(--navy); }
        .form-group label span { color: var(--danger); margin-right: 2px; }
        .input-wrap { position: relative; }
        .input-icon {
            position: absolute; right: 14px; top: 50%;
            transform: translateY(-50%); font-size: 15px;
            opacity: .45; pointer-events: none;
        }
        .form-group input,
        .form-group select {
            width: 100%; padding: 11px 42px 11px 14px;
            border: 1.5px solid var(--border); border-radius: 10px;
            font-size: 14px; font-family: 'Tajawal', sans-serif;
            color: var(--text); background: #f8fafc;
            transition: all .2s; outline: none;
        }
        .form-group input:focus,
        .form-group select:focus {
            border-color: var(--navy); background: var(--white);
            box-shadow: 0 0 0 3px rgba(11,60,93,.08);
        }
        .form-group input::placeholder { color: #a0aec0; }

        /* DAYS */
        .days-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 2px; }
        .day-label {
            display: flex; align-items: center; gap: 5px;
            background: #f1f5f9; border: 1.5px solid var(--border);
            border-radius: 9px; padding: 8px 16px; cursor: pointer;
            font-size: 13px; font-weight: 600; color: var(--text);
            transition: all .2s; user-select: none;
        }
        .day-label input[type="checkbox"] { display: none; }
        .day-label.checked { background: var(--navy); color: var(--white); border-color: var(--navy); }

        .submit-btn {
            width: 100%;
            background: linear-gradient(135deg, var(--navy) 0%, var(--navy-lt) 100%);
            color: var(--white); border: none; border-radius: 12px;
            padding: 13px; font-size: 15px; font-weight: 700;
            font-family: 'Tajawal', sans-serif; cursor: pointer;
            margin-top: 10px; transition: all .2s;
            display: flex; align-items: center; justify-content: center; gap: 8px;
            box-shadow: 0 4px 14px rgba(11,60,93,.3);
        }
        .submit-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(11,60,93,.4); }
        .submit-btn:active { transform: translateY(0); }

        /* STATS */
        .stats-bar {
            display: flex; align-items: center; padding: 18px 28px;
            border-bottom: 1px solid var(--border); background: #f8fafc;
        }
        .stats-bar .count { font-size: 14px; color: var(--muted); font-weight: 500; }
        .stats-bar .count strong { color: var(--navy); font-size: 22px; font-weight: 800; margin-left: 6px; }

        /* TABLE */
        .table-wrap { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; min-width: 950px; }
        thead th {
            background: #f1f5f9; color: var(--navy); font-size: 12px;
            font-weight: 700; padding: 13px 16px; text-align: right;
            letter-spacing: .4px; border-bottom: 2px solid var(--border);
        }
        tbody tr { transition: background .15s; animation: fadeIn .3s ease both; }
        tbody tr:hover { background: #f8fafc; }
        tbody tr:not(:last-child) td { border-bottom: 1px solid #eef2f7; }
        td { padding: 13px 16px; font-size: 13px; color: var(--text); vertical-align: middle; }

        .course-cell { display: flex; align-items: center; gap: 11px; }
        .course-avatar {
            width: 38px; height: 38px; border-radius: 10px;
            background: linear-gradient(135deg, var(--navy) 0%, var(--navy-lt) 100%);
            display: flex; align-items: center; justify-content: center;
            color: var(--white); font-size: 14px; font-weight: 700; flex-shrink: 0;
        }
        .course-name { font-weight: 600; color: var(--navy); }
        .course-id   { font-size: 11px; color: var(--muted); margin-top: 2px; }

        .badge { display: inline-block; border-radius: 7px; padding: 3px 10px; font-size: 12px; font-weight: 600; }
        .badge-section  { background: #e0f2fe; color: #0369a1; font-family: monospace; }
        .badge-active   { background: var(--success-lt); color: var(--success); }
        .badge-inactive { background: var(--danger-lt); color: var(--danger); }
        .badge-room     { background: #fef3c7; color: #92400e; }

        .day-pill {
            display: inline-block; background: #ede9fe; color: #6d28d9;
            border-radius: 6px; padding: 2px 7px; font-size: 11px;
            font-weight: 700; margin: 2px 2px 0 0;
        }

        .delete-btn {
            display: inline-flex; align-items: center; gap: 5px;
            background: var(--danger-lt); color: var(--danger);
            border: 1px solid #fecaca; border-radius: 8px;
            padding: 6px 12px; font-size: 12px; font-weight: 700;
            font-family: 'Tajawal', sans-serif; text-decoration: none;
            cursor: pointer; transition: all .2s;
        }
        .delete-btn:hover { background: var(--danger); color: var(--white); border-color: var(--danger); }

        .empty { text-align: center; padding: 60px 20px; color: var(--muted); }
        .empty-icon { font-size: 48px; margin-bottom: 12px; }
        .empty p    { font-size: 15px; }

        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        @media (max-width: 768px) { .form-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>

<header class="top-header">
    <div class="logo">
        <div class="logo-icon">🎓</div>
        <div>
            <div class="logo-text">جامعة حائل</div>
            <div class="logo-sub">نظام الحضور والغياب</div>
        </div>
    </div>
    <a class="back-btn" href="/admin/dashboard">← العودة للوحة الأدمن</a>
</header>

<div class="page">

    <!-- فورم الإضافة -->
    <div class="card">
        <div class="card-header">
            <div class="card-header-icon">➕</div>
            <div>
                <h2>إضافة مقرر جديد</h2>
                <p>أدخل بيانات المقرر والجدول الدراسي</p>
            </div>
        </div>
        <div class="card-body">
            <form method="post" action="/admin/sessions/add" id="addForm">
                <div class="form-grid">

                    <div class="form-group">
                        <label>اسم المقرر <span>*</span></label>
                        <div class="input-wrap">
                            <span class="input-icon">📚</span>
                            <input type="text" name="course_name" placeholder="مثال: CS401 — هياكل بيانات" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>رقم الشعبة <span>*</span></label>
                        <div class="input-wrap">
                            <span class="input-icon">🔢</span>
                            <input type="text" name="session_number" placeholder="مثال: 1 أو A1" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>الدكتور المسؤول <span>*</span></label>
                        <div class="input-wrap">
                            <span class="input-icon">👨‍🏫</span>
                            <select name="doctor_id" required>
                                <option value="">— اختر الدكتور —</option>
                                {% for d in doctors %}
                                    <option value="{{ d[0] }}">{{ d[1] }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>وقت البداية <span>*</span></label>
                        <div class="input-wrap">
                            <span class="input-icon">🕐</span>
                            <input type="time" name="start_time" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>وقت النهاية <span>*</span></label>
                        <div class="input-wrap">
                            <span class="input-icon">🕔</span>
                            <input type="time" name="end_time" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>اسم القاعة</label>
                        <div class="input-wrap">
                            <span class="input-icon">🏛️</span>
                            <input type="text" name="room_name" placeholder="مثال: B12">
                        </div>
                    </div>

                    <div class="form-group">
                        <label>كود القاعة</label>
                        <div class="input-wrap">
                            <span class="input-icon">🔑</span>
                            <input type="text" name="room_code" placeholder="6 أرقام" maxlength="6" pattern="\d{6}">
                        </div>
                    </div>

                    <div class="form-group">
                        <label>السعة الاستيعابية</label>
                        <div class="input-wrap">
                            <span class="input-icon">👥</span>
                            <input type="number" name="capacity" placeholder="مثال: 40" min="1" max="500">
                        </div>
                    </div>

                    <div class="form-group form-full">
                        <label>أيام المحاضرة <span>*</span></label>
                        <input type="hidden" name="days" id="daysInput" value="">
                        <div class="days-wrap">
                            <label class="day-label"><input type="checkbox" value="الأحد"> الأحد</label>
                            <label class="day-label"><input type="checkbox" value="الاثنين"> الاثنين</label>
                            <label class="day-label"><input type="checkbox" value="الثلاثاء"> الثلاثاء</label>
                            <label class="day-label"><input type="checkbox" value="الأربعاء"> الأربعاء</label>
                            <label class="day-label"><input type="checkbox" value="الخميس"> الخميس</label>
                        </div>
                    </div>

                </div>
                <button class="submit-btn" type="submit">✅ إضافة المقرر</button>
            </form>
        </div>
    </div>

    <!-- جدول المقررات -->
    <div class="card">
        <div class="card-header">
            <div class="card-header-icon">📋</div>
            <div>
                <h2>المقررات المضافة</h2>
                <p>جميع المقررات والشعب المسجلة في النظام</p>
            </div>
        </div>

        <div class="stats-bar">
            <div class="count">إجمالي المقررات <strong>{{ sessions | length }}</strong></div>
        </div>

        <div class="table-wrap">
            {% if sessions %}
            <table>
                <thead>
                    <tr>
                        <th>المقرر</th>
                        <th>الشعبة</th>
                        <th>الدكتور</th>
                        <th>الأيام</th>
                        <th>الوقت</th>
                        <th>القاعة</th>
                        <th>السعة</th>
                        <th>الحالة</th>
                        <th>حذف</th>
                    </tr>
                </thead>
                <tbody>
                    {% for s in sessions %}
                    <tr style="animation-delay: {{ loop.index0 * 0.04 }}s">
                        <td>
                            <div class="course-cell">
                                <div class="course-avatar">{{ s[1][0] if s[1] else '؟' }}</div>
                                <div>
                                    <div class="course-name">{{ s[1] }}</div>
                                    <div class="course-id">#{{ s[0] }}</div>
                                </div>
                            </div>
                        </td>
                        <td><span class="badge badge-section">{{ s[2] or '—' }}</span></td>
                        <td>{{ s[3] }}</td>
                        <td>
                            {% if s[9] %}
                                {% for day in s[9].split(',') %}
                                    <span class="day-pill">{{ day.strip() }}</span>
                                {% endfor %}
                            {% else %}
                                <span style="color:#9ca3af">—</span>
                            {% endif %}
                        </td>
                        <td style="font-family:monospace; font-size:12px; color:var(--muted);">
                            {{ s[5] or '—' }} — {{ s[6] or '—' }}
                        </td>
                        <td>
                            {% if s[7] %}
                                <span class="badge badge-room">{{ s[7] }}{% if s[8] %} ({{ s[8] }}){% endif %}</span>
                            {% else %}<span style="color:#9ca3af">—</span>{% endif %}
                        </td>
                        <td>
                            {% if s[10] %}
                                <span style="font-weight:600;">{{ s[10] }}</span>
                                <span style="color:var(--muted);font-size:11px;"> طالب</span>
                            {% else %}—{% endif %}
                        </td>
                        <td>
                            {% if s[4] == 1 %}
                                <span class="badge badge-active">✓ نشطة</span>
                            {% else %}
                                <span class="badge badge-inactive">✗ مغلقة</span>
                            {% endif %}
                        </td>
                        <td>
                            <a class="delete-btn"
                               href="/admin/sessions/delete/{{ s[0] }}"
                               onclick="return confirm('هل أنت متأكد من حذف مقرر {{ s[1] }}؟')">
                                🗑 حذف
                            </a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="empty">
                <div class="empty-icon">📚</div>
                <p>لا توجد مقررات مضافة بعد.</p>
            </div>
            {% endif %}
        </div>
    </div>

</div>

<script>
const dayLabels = document.querySelectorAll('.day-label');
const daysInput = document.getElementById('daysInput');

function updateDaysInput() {
    const selected = [];
    dayLabels.forEach(lbl => {
        if (lbl.querySelector('input[type="checkbox"]').checked)
            selected.push(lbl.querySelector('input[type="checkbox"]').value);
    });
    daysInput.value = selected.join(',');
}

dayLabels.forEach(lbl => {
    lbl.addEventListener('click', function(e) {
        e.preventDefault();
        const cb = this.querySelector('input[type="checkbox"]');
        cb.checked = !cb.checked;
        this.classList.toggle('checked', cb.checked);
        updateDaysInput();
    });
});

document.getElementById('addForm').addEventListener('submit', function(e) {
    if (!daysInput.value) {
        e.preventDefault();
        alert('الرجاء اختيار يوم واحد على الأقل للمحاضرة.');
    }
});
</script>

</body>
</html>
