from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
import base64

app = Flask(__name__)

# 簡易記憶體內資料庫（可改為 SQLite）
pending_refills = []  # 每筆記錄為 dict，包含 pick_id, time, status, message（提示訊息）

# 一維條碼產生器（使用 Code128）
def generate_barcode(data):
    CODE128 = barcode.get_barcode_class('code128')
    writer = ImageWriter()
    writer.set_options({'write_text': False})  # 不顯示條碼文字
    code = CODE128(data, writer=writer)
    buffer = io.BytesIO()
    code.write(buffer)
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{img_str}'

# 首頁
@app.route('/')
def index():
    return '''
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin: 0; padding: 0; text-align: center; font-family: sans-serif; }
    .container { max-width: 600px; margin: 0 auto; padding: 1rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: center; }
    h2, h3 { margin: 0.5rem 0; }
    ul { list-style: none; padding: 0; margin: 1rem 0; }
    ul li { margin: 0.5rem 0; }
    a { text-decoration: none; color: #0066cc; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <h2>缺貨通報系統</h2>
    <ul>
        <li><a href="/report">1. 揀貨人員通報缺貨</a></li>
        <li><a href="/list">2. 補貨清單</a></li>
    </ul>
  </div>
</body>
</html>
    '''

# 缺貨通報頁
@app.route('/report', methods=['GET'])
def report():
    return render_template_string('''
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin: 0; padding: 0; text-align: center; font-family: sans-serif; }
    .container { max-width: 600px; margin: 0 auto; padding: 1rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: center; }
    h2, h3 { margin: 0.5rem 0; }
    #popup {
      display:none;position:fixed;top:20px;right:20px;background:#4CAF50;color:#fff;
      padding:10px 20px;border-radius:8px;z-index:1000;font-weight:bold;
      box-shadow:0 0 10px rgba(0,0,0,0.2);
    }
    button {
      cursor: pointer;
      padding: 0.5rem 1rem;
      margin: 0.5rem 0;
      border: none;
      background-color: #0066cc;
      color: #fff;
      border-radius: 4px;
    }
    button:hover {
      background-color: #0052a3;
    }
  </style>
</head>
<body>
<div class="container">
    <h2>缺貨通報</h2>

    <div id="popup"></div>

    <form id="report-form" style="margin:1rem 0;">
        <label>揀位號碼：
          <input type="text" name="pick_id" required style="padding:0.4rem;">
        </label>
        <button type="submit">通報缺貨</button>
    </form>

    <h3>待補貨清單（即時顯示）</h3>
    <div id="refill-table" style="margin:1rem 0;"></div>
</div>

<script>
// 提交表單
document.getElementById("report-form").addEventListener("submit", function (e) {
    e.preventDefault();
    const formData = new FormData(this);
    fetch("/report-ajax", {
        method: "POST",
        body: formData
    }).then(() => {
        showPopup("缺貨通報成功！");
        setTimeout(() => {
            hidePopup();
        }, 1500);
        this.reset();
        loadRefillTable();
    });
});

function loadRefillTable() {
    fetch("/refill-table")
        .then(res => res.text())
        .then(html => {
            document.getElementById("refill-table").innerHTML = html;
        });
}

// 初始化與每3秒更新
loadRefillTable();
setInterval(loadRefillTable, 3000);

function showPopup(msg) {
    const popup = document.getElementById("popup");
    popup.textContent = msg;
    popup.style.display = "block";
}
function hidePopup() {
    document.getElementById("popup").style.display = "none";
}
</script>
</body>
</html>
''', refills=pending_refills)

@app.route('/report-ajax', methods=['POST'])
def report_ajax():
    pick_id = request.form['pick_id'].strip().upper()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 只檢查是否有 '待補貨' 狀態相同ID
    existing_waiting = next((item for item in pending_refills 
                             if item['pick_id'] == pick_id and item['status'] == '待補貨'), None)

    if existing_waiting:
        # 若已有同一揀位處於 待補貨 狀態
        existing_waiting['message'] = f"揀位 {pick_id} 已在補貨清單中"
    else:
        # 即使以前補貨完成(已補貨)，也可重新建立新紀錄(二次通報)
        pending_refills.append({
            'pick_id': pick_id,
            'time': now,
            'status': '待補貨',
            'message': f"揀位 {pick_id} 缺貨已通報"
        })

    return '', 204

@app.route('/refill-table')
def refill_table():
    table_html = '''
    <table>
        <tr><th>時間</th><th>狀態</th><th>訊息</th></tr>
        {% for item in refills %}
            <tr>
                <td>{{ item.time }}</td>
                <td>{{ item.status }}</td>
                <td>{{ item.message if 'message' in item else '' }}</td>
            </tr>
        {% endfor %}
    </table>
    '''
    return render_template_string(table_html, refills=pending_refills, generate_barcode=generate_barcode)

# 缺貨清單頁（供列印或掃描）
@app.route('/list')
def list_refills():
    return render_template_string('''
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body { margin: 0; padding: 0; text-align: center; font-family: sans-serif; }
    .container { max-width: 600px; margin: 0 auto; padding: 1rem; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: center; }
    h2, h3 { margin: 0.5rem 0; }
    button {
      cursor: pointer;
      padding: 0.5rem 1rem;
      margin: 0.5rem 0;
      border: none;
      background-color: #0066cc;
      color: #fff;
      border-radius: 4px;
    }
    button:hover {
      background-color: #0052a3;
    }
  </style>
</head>
<body>
<div class="container">
    <h2>待補貨清單</h2>
    <div id="list-table">
      <!-- 這裡由 JavaScript AJAX 載入 /list-table -->
    </div>
</div>
<script>
function submitRefill(e, pickId) {
    e.preventDefault();
    fetch("/list-table", {
        method: "POST",
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'pick_id=' + encodeURIComponent(pickId)
    }).then(() => {
        loadListTable();
        const refillTable = document.getElementById("refill-table");
        if (refillTable) {
            fetch("/refill-table")
                .then(res => res.text())
                .then(html => {
                    refillTable.innerHTML = html;
                });
        }
    });
}

function loadListTable() {
    fetch("/list-table")
        .then(res => res.text())
        .then(html => {
            document.getElementById("list-table").innerHTML = html;
        });
}

// 初次載入
loadListTable();
// 每3秒更新
setInterval(loadListTable, 3000);
</script>
</body>
</html>
''', refills=pending_refills, generate_barcode=generate_barcode)

@app.route('/list-table', methods=['GET', 'POST'])
def list_table():
    if request.method == 'POST':
        pick_id = request.form['pick_id']
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for item in reversed(pending_refills):
            if item['pick_id'] == pick_id and item['status'] == '待補貨':
                item['status'] = '已補貨'
                item['refill_time'] = now
                item['message'] = f"揀位 {pick_id} 已補貨"
                break
    table_html = '''
    <h3>待補貨項目</h3>
    <table>
        <tr><th>揀位</th><th>時間</th><th>狀態</th><th>操作</th></tr>
        {% for item in refills %}
            {% if item.status == '待補貨' %}
            <tr>
                <td>{{ item.pick_id }}</td>
                <td>{{ item.time }}</td>
                <td>{{ item.status }}</td>
                <td>
                    <img src="{{ generate_barcode(item.pick_id) }}" width="120"><br>
                    <form onsubmit="submitRefill(event, '{{ item.pick_id }}'); return false;">
                        <button type="submit">補貨完成</button>
                    </form>
                </td>
            </tr>
            {% endif %}
        {% endfor %}
    </table>
    '''
    return render_template_string(table_html, refills=pending_refills, generate_barcode=generate_barcode)

if __name__ == '__main__':
    app.run(debug=True)
