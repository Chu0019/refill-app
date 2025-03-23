from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import io
import base64
import os

app = Flask(__name__)

# 模擬資料庫
pending_refills = []  # 每筆記錄: {pick_id, time, status, message}

# 條碼產生器（Code128）
def generate_barcode(data):
    CODE128 = barcode.get_barcode_class('code128')
    writer = ImageWriter()
    writer.set_options({'write_text': False})  # 不顯示條碼下方文字
    code = CODE128(data, writer=writer)
    buffer = io.BytesIO()
    code.write(buffer)
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{img_str}'

# 首頁選單頁面
@app.route('/')
def index():
    return '''
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; }
        ul { list-style: none; padding: 0; }
        li { margin: 10px 0; }
        a { text-decoration: none; font-size: 18px; color: #007BFF; }
      </style>
    </head>
    <body>
      <h2>補貨系統</h2>
      <div>
        <ul>
          <li><a href="/report">缺貨通報（支援掃描）</a></li>
          <li><a href="/list">補貨清單（含條碼）</a></li>
        </ul>
      </div>
    </body>
    </html>
    '''

# 缺貨通報頁面（支援條碼掃描）
@app.route('/report', methods=['GET', 'POST'])
def report():
    if request.method == 'POST':
        pick_id = request.form['pick_id'].strip().upper()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        pending_refills.append({
            'pick_id': pick_id,
            'time': now,
            'status': '待補貨',
            'message': f"揀位 {pick_id} 缺貨通報成功 ✅"
        })
        return jsonify({'message': f"✅ 揀位 {pick_id} 缺貨通報成功"})

    # GET：顯示頁面與掃描功能
    return render_template_string('''
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
      <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 8px; }
        #qr-reader { max-width: 100%; margin: 10px auto; }
        #scan-section { display: none; }
        @media(max-width: 600px) {
          table, thead, tbody, th, td, tr { display: block; }
        }
      </style>
    </head>
    <body>
      <h2>缺貨通報（掃描或輸入）</h2>
      <!-- 掃描按鈕與掃描器區域 -->
      <button onclick="startScanner()">開啟相機掃描</button>
      <div id="scan-section">
        <div id="qr-reader" style="width:300px;"></div>
      </div>
      
      <!-- 手動輸入與通報表單 -->
      <form id="report-form">
        <input type="text" name="pick_id" placeholder="請輸入揀位號碼" required>
        <button type="submit">通報缺貨</button>
      </form>
      <div id="msg" style="margin-top:10px;font-weight:bold;color:green"></div>

      <!-- 清單區塊 -->
      <h3>待補貨清單（即時顯示）</h3>
      <div id="refill-table"></div>

      <script>
        let scanner;
        let scannerInitiated = false;

        // 啟動掃描器
        function startScanner() {
          document.getElementById('scan-section').style.display = 'block';
          if (!scannerInitiated) {
            scanner = new Html5Qrcode("qr-reader");
            scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 },
              (decodedText, decodedResult) => {
                document.querySelector('input[name=pick_id]').value = decodedText;
                scanner.stop().then(() => {
                  document.getElementById('scan-section').style.display = 'none';
                });
                if (navigator.vibrate) navigator.vibrate(100);
              });
            scannerInitiated = true;
          }
        }

        // 提交缺貨表單
        document.getElementById("report-form").addEventListener("submit", function(e) {
          e.preventDefault();
          const formData = new FormData(this);
          fetch("/report", { method: "POST", body: formData })
            .then(res => res.json()).then(data => {
              document.getElementById("msg").textContent = data.message;
              loadRefillTable();
            });
          this.reset();
        });

        // 每 3 秒更新待補貨清單
        function loadRefillTable() {
          fetch("/refill-table").then(res => res.text()).then(html => {
            document.getElementById("refill-table").innerHTML = html;
          });
        }
        setInterval(loadRefillTable, 3000);
        window.onload = loadRefillTable;
      </script>
    </body>
    </html>
    ''')

# 待補貨清單資料表（只顯示時間、狀態、訊息）
@app.route('/refill-table')
def refill_table():
    rows = [
        f"<tr><td>{item['time']}</td><td>{item['status']}</td><td>{item['message']}</td></tr>"
        for item in pending_refills if item['status'] == '待補貨'
    ]
    return f'''<table border="1" style="width:100%; max-width:800px; margin:auto; text-align:center; font-size: 14px;"><tr><th>時間</th><th>狀態</th><th>訊息</th></tr>{''.join(rows)}</table>'''

# 補貨清單主頁與補貨完成操作
@app.route('/list', methods=['GET','POST'])
def list_page():
    if request.method == 'POST':
        pick_id = request.form['pick_id']
        for item in pending_refills:
            if item['pick_id'] == pick_id and item['status'] == '待補貨':
                item['status'] = '已補貨'
                item['message'] = f"揀位 {pick_id} 補貨完成 ✅"
        return ('', 204)

    # 顯示補貨清單頁面
    return render_template_string('''
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; }
        table { width: 100%; max-width: 800px; margin: auto; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
        th, td { border: 1px solid #ccc; padding: 6px; }
        img { max-width: 100%; height: auto; }
        button { font-size: 14px; padding: 4px 10px; }
        @media(max-width: 600px) {
          table, thead, tbody, th, td, tr { display: block; }
        }
      </style>
    </head>
    <body>
      <h2>補貨清單</h2>
      <div id="list-table"></div>
      <script>
        // 按下補貨完成按鈕
        function markRefilled(pickId) {
          fetch("/list", {
            method: "POST",
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ pick_id: pickId })
          }).then(() => loadListTable());
        }

        // 自動載入清單內容
        function loadListTable() {
          fetch("/list-table")
            .then(res => res.text())
            .then(html => {
              document.getElementById("list-table").innerHTML = html;
            });
        }
        setInterval(loadListTable, 3000);
        window.onload = loadListTable;
      </script>
    </body>
    </html>
    ''')

# 補貨清單內容（顯示條碼與補貨按鈕）
@app.route('/list-table')
def list_table():
    rows = []
    for item in pending_refills:
        if item['status'] == '待補貨':
            barcode_img = generate_barcode(item['pick_id'])
            rows.append(f'''
                <tr>
                  <td>{item['time']}</td>
                  <td>{item['status']}</td>
                  <td>
                      <img src="{barcode_img}" style="width: 100%; max-width: 280px; height: auto;"><br>
                      <button onclick="markRefilled('{item['pick_id']}')">補貨完成</button>
                  </td>
                </tr>
            ''')
    return f"""<table border='1' style='width:100%; max-width:800px; margin:auto; text-align:center; font-size:14px;'>
    <tr><th>時間</th><th>狀態</th><th>操作</th></tr>
    {''.join(rows)}
    </table>"""


# 啟動 Flask 伺服器
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))  # Render 會提供 PORT
    app.run(host='0.0.0.0', port=port)