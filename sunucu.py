from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import datetime
import os
import uuid
import html
import cgi
import time

# --- KONFİGÜRASYON ---
MY_IP = "192.168.7.23"
PORT = 12345
DB_FILE = "nova_ultra_db.json"
UPLOAD_DIR = "uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

messages = []
polls = {}
active_users = {}


def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages.extend(data.get("messages", []))
                polls.update(data.get("polls", {}))
        except:
            pass


def save_db():
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump({"messages": messages, "polls": polls}, f, ensure_ascii=False)


load_db()


class NovaUltraHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.get_ui().encode())

        elif self.path.startswith('/get_sync'):
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            u_name = query.get('u', ['Anonim'])[0]
            active_users[u_name] = time.time()

            now = time.time()
            to_delete = [u for u, last in active_users.items() if now - last > 30]
            for u in to_delete: del active_users[u]

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "messages": messages,
                "polls": polls,
                "users": list(active_users.keys())
            }).encode())

        elif self.path.startswith('/uploads/'):
            try:
                file_path = self.path[1:]
                with open(file_path, 'rb') as f:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(f.read())
            except:
                self.send_error(404)

    def do_POST(self):
        if self.path == '/upload':
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST'})
            u_name = form.getvalue("u", "Anonim")
            file_item = form['file']
            if file_item.filename:
                ext = os.path.splitext(file_item.filename)[1].lower()
                safe_name = f"{uuid.uuid4()}{ext}"
                with open(os.path.join(UPLOAD_DIR, safe_name), 'wb') as f:
                    f.write(file_item.file.read())

                messages.append({
                    "id": str(uuid.uuid4()), "u": html.escape(u_name), "t": safe_name,
                    "orig": html.escape(file_item.filename), "s": datetime.datetime.now().strftime("%H:%M"),
                    "type": "image" if ext in ['.jpg', '.jpeg', '.png', '.gif'] else "file"
                })
                save_db()
            self.send_response(200)
            self.end_headers()
            return

        length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(length).decode())

        if self.path == '/send':
            messages.append({"id": str(uuid.uuid4()), "u": html.escape(data['u']), "t": html.escape(data['t']),
                             "s": datetime.datetime.now().strftime("%H:%M"), "type": "text"})
        elif self.path == '/delete':
            messages[:] = [m for m in messages if not (m['id'] == data['id'])]
        elif self.path == '/clear_all':  # ARTIK HERKES SİLEBİLİR
            messages.clear()
            polls.clear()
        elif self.path == '/create_poll':
            p_id = str(uuid.uuid4())[:6]
            polls[p_id] = {"q": html.escape(data['q']), "opts": {html.escape(o.strip()): 0 for o in data['opts']},
                           "voters": []}
            messages.append(
                {"id": str(uuid.uuid4()), "u": "SİSTEM", "t": f"📊 Anket: {data['q']}", "type": "poll", "p_id": p_id,
                 "s": "Şimdi"})
        elif self.path == '/vote':
            p = polls.get(data['p_id'])
            if p and data['u'] not in p['voters'] and data['opt'] in p['opts']:
                p['opts'][data['opt']] += 1
                p['voters'].append(data['u'])

        save_db()
        self.send_response(200)
        self.end_headers()

    def get_ui(self):
        return """
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <title>NovaChat: Herkese Açık</title>
            <style>
                :root { --p: #6366f1; --bg: #0b0e14; --c: #161b22; --t: #e6edf3; }
                body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--t); margin: 0; display: flex; height: 100vh; overflow:hidden; }
                .sidebar { width: 260px; background: var(--c); padding: 20px; border-right: 1px solid #333; display: flex; flex-direction: column; }
                .user-list { flex: 1; margin-top: 15px; overflow-y: auto; }
                .user-item { padding: 8px; margin-bottom: 5px; background: #0d1117; border-radius: 5px; display: flex; align-items: center; font-size: 0.9em; }
                .user-status { width: 8px; height: 8px; background: #10b981; border-radius: 50%; margin-right: 10px; }
                .chat-main { flex: 1; display: flex; flex-direction: column; }
                #chat-box { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
                .msg { max-width: 80%; }
                .me { align-self: flex-end; }
                .bubble { padding: 10px 15px; border-radius: 12px; background: #21262d; word-wrap: break-word; }
                .me .bubble { background: var(--p); }
                .img-msg { max-width: 100%; border-radius: 8px; margin-top: 5px; }
                .input-area { padding: 15px; background: #161b22; display: flex; gap: 10px; align-items: center; }
                #clear-btn { background: #ef4444; color: white; border: none; padding: 10px; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; margin-bottom: 15px; }
                input[type="text"] { flex: 1; padding: 10px; border-radius: 8px; border: 1px solid #333; background: #0d1117; color: white; outline: none; }
                .poll-card { background: #0d1117; padding: 10px; border-radius: 8px; border-left: 4px solid var(--p); }
            </style>
        </head>
        <body>
            <div class="sidebar">
                <h2 style="color:var(--p); margin: 0 0 20px 0;">NovaChat</h2>
                <button id="clear-btn" onclick="clearAll()">🗑️ Tüm Sohbeti Temizle</button>
                <div style="font-size:0.75em; color:#888; text-transform:uppercase; margin-bottom:10px;">AKTİF KİŞİLER</div>
                <div class="user-list" id="user-list"></div>
                <button onclick="createPoll()" style="background:#10b981; color:white; border:none; padding:10px; border-radius:8px; cursor:pointer; margin-top:10px;">📊 Anket Yap</button>
            </div>
            <div class="chat-main">
                <div id="chat-box"></div>
                <div class="input-area">
                    <label style="cursor:pointer; font-size:1.5em;" for="file-in">📁</label>
                    <input type="file" id="file-in" style="display:none" onchange="uploadFile()">
                    <input type="text" id="m-in" placeholder="Bir şeyler yaz..." onkeypress="if(event.key==='Enter') send()">
                    <button onclick="send()" style="padding:10px 20px; background:var(--p); color:white; border:none; border-radius:8px; cursor:pointer;">Gönder</button>
                </div>
            </div>

            <script>
                let user = prompt("Adınız:") || "Anonim";
                let displayedIds = new Set();

                async function load() {
                    const r = await fetch(`/get_sync?u=${encodeURIComponent(user)}`);
                    const data = await r.json();

                    // Aktif kullanıcıları listele
                    document.getElementById('user-list').innerHTML = data.users.map(u => 
                        `<div class="user-item"><div class="user-status"></div>${u}</div>`).join('');

                    const box = document.getElementById('chat-box');
                    // Eğer sunucudaki mesaj sayısı azaldıysa (temizlendiyse) ekranı sıfırla
                    if (data.messages.length < displayedIds.size) { 
                        box.innerHTML = ""; 
                        displayedIds.clear(); 
                    }

                    data.messages.forEach(m => {
                        if (!displayedIds.has(m.id)) {
                            const div = document.createElement('div');
                            div.className = `msg ${m.u === user ? 'me' : ''}`;
                            div.id = "msg-" + m.id;

                            let content = m.t;
                            if(m.type === 'image') content = `<a href="/uploads/${m.t}" target="_blank"><img src="/uploads/${m.t}" class="img-msg"></a>`;
                            else if(m.type === 'file') content = `<a href="/uploads/${m.t}" target="_blank" style="color:#a5b4fc; text-decoration:none;">📄 ${m.orig}</a>`;
                            else if(m.type === 'poll') {
                                const p = data.polls[m.p_id];
                                content = `<div class="poll-card"><strong>${p.q}</strong>` + 
                                    Object.keys(p.opts).map(o => `<button style="width:100%; margin-top:5px; padding:5px; cursor:pointer;" onclick="vote('${m.p_id}', '${o}')">${o} (${p.opts[o]})</button>`).join('') + `</div>`;
                            }

                            div.innerHTML = `<small style="display:block; font-size:0.7em; margin-bottom:2px; opacity:0.6;">${m.u} • ${m.s}</small>
                                             <div class="bubble">${content}</div>
                                             ${m.u === user ? `<div style="font-size:0.65em; margin-top:2px; cursor:pointer; opacity:0.5;" onclick="deleteMsg('${m.id}')">Sil</div>` : ''}`;
                            box.appendChild(div);
                            displayedIds.add(m.id);
                            box.scrollTop = box.scrollHeight;
                        }
                    });
                }

                async function send() {
                    const inp = document.getElementById('m-in');
                    if(!inp.value.trim()) return;
                    await fetch('/send', { method: 'POST', body: JSON.stringify({u: user, t: inp.value}) });
                    inp.value = "";
                }

                async function uploadFile() {
                    const fIn = document.getElementById('file-in');
                    const formData = new FormData();
                    formData.append('file', fIn.files[0]);
                    formData.append('u', user);
                    await fetch('/upload', { method: 'POST', body: formData });
                    fIn.value = "";
                }

                async function deleteMsg(id) {
                    await fetch('/delete', { method: 'POST', body: JSON.stringify({id, u: user}) });
                    document.getElementById("msg-"+id).remove();
                    displayedIds.delete(id);
                }

                async function clearAll() {
                    if(confirm("Tüm sohbeti herkes için temizlemek istediğine emin misin?")) {
                        await fetch('/clear_all', { method: 'POST', body: JSON.stringify({u: user}) });
                    }
                }

                async function createPoll() {
                    const q = prompt("Soru:");
                    const o = prompt("Seçenekler (virgülle ayır):").split(',');
                    if(q && o) await fetch('/create_poll', { method: 'POST', body: JSON.stringify({q, opts: o}) });
                }

                async function vote(p_id, opt) {
                    await fetch('/vote', { method: 'POST', body: JSON.stringify({p_id, opt, u: user}) });
                }

                setInterval(load, 1500);
            </script>
        </body>
        </html>
        """


def run():
    print(f"[*] Sunucu Başlatıldı: http://{MY_IP}:{PORT}")
    HTTPServer(('0.0.0.0', PORT), NovaUltraHandler).serve_forever()


if __name__ == "__main__":
    run()