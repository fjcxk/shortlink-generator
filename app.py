from flask import Flask, request, redirect, render_template
import mysql.connector
import string
import random
from urllib.parse import urlparse

app = Flask(__name__)

# MySQL 配置
db_config = {
    'host': '172.18.0.2',
    'user': 'root',
    'password': '1234',
    'database': 'shortlink',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_bin',
    'autocommit': True  # 开启自动提交，避免事务锁
}

# 生成短码
def generate_short_code():
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(6))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        long_url = request.form['long_url'].strip()
        if not urlparse(long_url).scheme:
            long_url = f'http://{long_url}'

        conn = None
        cursor = None
        short_url = None
        
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()

            # 第一步：查询长链接是否已存在
            cursor.execute(
                'SELECT short_code FROM links WHERE long_url = %s LIMIT 1',
                (long_url,)
            )
            existing = cursor.fetchone()

            if existing:  # 存在则直接复用
                short_code = existing[0]
                print(f"复用已有短码: {short_code}")
            else:         # 不存在则生成新短码
                max_retries = 5
                inserted = False
                
                for _ in range(max_retries):
                    short_code = generate_short_code()
                    try:
                        cursor.execute(
                            'INSERT INTO links (long_url, short_code) VALUES (%s, %s)',
                            (long_url, short_code)
                        )
                        inserted = True
                        break
                    except mysql.connector.errors.IntegrityError:
                        print(f"短码冲突: {short_code}, 重试...")
                        continue
                
                if not inserted:
                    return "生成失败，请重试", 500

            short_url = f'http://localhost:5000/{short_code}'
            return render_template('index.html', short_url=short_url)

        except Exception as e:
            print(f"数据库错误: {e}")
            return "服务器错误", 500
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    return render_template('index.html')

# 短链接跳转
@app.route('/<short_code>')
def redirect_to_long_url(short_code):
    try:
        short_code = short_code.strip()
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT long_url FROM links WHERE BINARY short_code = %s',
            (short_code,)
        )
        result = cursor.fetchone()
        
        if result:
            long_url = result[0]
            if not urlparse(long_url).scheme:
                long_url = f'http://{long_url}'  
            return redirect(long_url)
        else:
            return '短链接不存在', 404
    except Exception as e:
        print(f"[ERROR] 数据库查询失败: {e}")
        return '服务器错误', 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)
