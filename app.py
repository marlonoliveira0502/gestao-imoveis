import os, threading, requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from database import get_db, init_db, get_config, set_config
from scraper import sincronizar

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'imoveis-marlon-2024-secret')

# ─── Credenciais de acesso ──────────────────────────────────────────────────
APP_USER    = os.environ.get('APP_USER',   'marlon')
APP_PASS    = os.environ.get('APP_PASS',   'invest2024')
OWNER_EMAIL  = os.environ.get('OWNER_EMAIL', 'marllonmba@gmail.com')
RESEND_KEY   = os.environ.get('RESEND_API_KEY', '')

# Credenciais ImoGestão (para sincronização)
IMOB_CPF  = os.environ.get('IMOB_CPF',  '59711809249')
IMOB_PASS = os.environ.get('IMOB_PASS', '1Ev5Ew')

# Log de sincronização em memória
sync_log  = []
sync_running = False

# ─── Auth ────────────────────────────────────────────────────────────────────
def get_senha_atual():
    """Retorna a senha atual (DB tem prioridade sobre env var)."""
    return get_config('app_pass', APP_PASS)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('usuario') == APP_USER and request.form.get('senha') == get_senha_atual():
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = 'Usuário ou senha incorretos'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/alterar-senha', methods=['POST'])
@login_required
def alterar_senha():
    d = request.json
    senha_atual = get_senha_atual()
    if d.get('senha_atual') != senha_atual:
        return jsonify({'erro': 'Senha atual incorreta'}), 400
    nova = d.get('nova_senha', '').strip()
    if len(nova) < 4:
        return jsonify({'erro': 'A nova senha deve ter pelo menos 4 caracteres'}), 400
    set_config('app_pass', nova)
    return jsonify({'ok': True})

def _serializer():
    return URLSafeTimedSerializer(app.secret_key, salt='recuperar-senha')

def _enviar_email_recuperacao(link):
    if not RESEND_KEY:
        raise ValueError('RESEND_API_KEY não configurada nas variáveis de ambiente do Render.')
    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
      <h2 style="color:#1e3a5f">🏢 Gestão de Imóveis</h2>
      <p>Você solicitou a recuperação de senha. Clique no botão abaixo para criar uma nova senha:</p>
      <div style="text-align:center;margin:28px 0">
        <a href="{link}" style="background:#2563eb;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:1rem">
          Redefinir Senha
        </a>
      </div>
      <p style="color:#64748b;font-size:.85rem">Este link expira em <strong>30 minutos</strong>. Se você não solicitou a recuperação, ignore este e-mail.</p>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
      <p style="color:#94a3b8;font-size:.78rem">Gestão de Imóveis · Manuel Marlon · Invest Imobiliária · Marabá/PA</p>
    </div>"""
    resp = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {RESEND_KEY}', 'Content-Type': 'application/json'},
        json={
            'from': 'Gestão de Imóveis <onboarding@resend.dev>',
            'to':   [OWNER_EMAIL],
            'subject': 'Recuperação de Senha – Gestão de Imóveis',
            'html': html,
        },
        timeout=15
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f'Erro ao enviar e-mail: {resp.text}')

@app.route('/esqueci-senha', methods=['GET','POST'])
def esqueci_senha():
    msg = erro = None
    if request.method == 'POST':
        try:
            token = _serializer().dumps('reset')
            link  = url_for('redefinir_senha', token=token, _external=True)
            _enviar_email_recuperacao(link)
            msg = f'Link de recuperação enviado para {OWNER_EMAIL}. Verifique sua caixa de entrada (e spam).'
        except Exception as e:
            erro = str(e)
    return render_template('forgot.html', msg=msg, erro=erro)

@app.route('/redefinir-senha/<token>', methods=['GET','POST'])
def redefinir_senha(token):
    try:
        _serializer().loads(token, max_age=1800)  # 30 min
    except SignatureExpired:
        return render_template('recover.html', msg=None, erro='Link expirado. Solicite um novo.', token=None)
    except BadSignature:
        return render_template('recover.html', msg=None, erro='Link inválido.', token=None)

    msg = erro = None
    if request.method == 'POST':
        nova = request.form.get('nova_senha','').strip()
        conf = request.form.get('confirmar','').strip()
        if len(nova) < 4:
            erro = 'A senha deve ter pelo menos 4 caracteres'
        elif nova != conf:
            erro = 'As senhas não coincidem'
        else:
            set_config('app_pass', nova)
            msg = 'Senha redefinida com sucesso! Faça login com a nova senha.'
            token = None  # invalida o token após uso
    return render_template('recover.html', msg=msg, erro=erro, token=token)

# ─── Páginas ──────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('app.html')

# ─── API – Unidades ──────────────────────────────────────────────────────────
@app.route('/api/unidades', methods=['GET'])
@login_required
def get_unidades():
    conn = get_db()
    rows = conn.execute('SELECT * FROM unidades ORDER BY codigo').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/unidades', methods=['POST'])
@login_required
def create_unidade():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO unidades (codigo,tipo,descricao,aluguel,area,obs) VALUES (?,?,?,?,?,?)',
        (d['codigo'],d.get('tipo','apartamento'),d.get('descricao',''),d.get('aluguel',0),d.get('area',0),d.get('obs',''))
    )
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return jsonify({'id': new_id}), 201

@app.route('/api/unidades/<int:uid>', methods=['PUT'])
@login_required
def update_unidade(uid):
    d = request.json
    conn = get_db()
    conn.execute(
        'UPDATE unidades SET codigo=?,tipo=?,descricao=?,aluguel=?,area=?,obs=? WHERE id=?',
        (d['codigo'],d.get('tipo','apartamento'),d.get('descricao',''),d.get('aluguel',0),d.get('area',0),d.get('obs',''),uid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/unidades/<int:uid>', methods=['DELETE'])
@login_required
def delete_unidade(uid):
    conn = get_db()
    conn.execute('DELETE FROM unidades WHERE id=?', (uid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── API – Inquilinos ────────────────────────────────────────────────────────
@app.route('/api/inquilinos', methods=['GET'])
@login_required
def get_inquilinos():
    conn = get_db()
    rows = conn.execute('SELECT * FROM inquilinos ORDER BY nome').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/inquilinos', methods=['POST'])
@login_required
def create_inquilino():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO inquilinos (nome,cpf,tel,email,obs) VALUES (?,?,?,?,?)',
        (d['nome'],d.get('cpf',''),d.get('tel',''),d.get('email',''),d.get('obs',''))
    )
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return jsonify({'id': new_id}), 201

@app.route('/api/inquilinos/<int:iid>', methods=['PUT'])
@login_required
def update_inquilino(iid):
    d = request.json
    conn = get_db()
    conn.execute(
        'UPDATE inquilinos SET nome=?,cpf=?,tel=?,email=?,obs=? WHERE id=?',
        (d['nome'],d.get('cpf',''),d.get('tel',''),d.get('email',''),d.get('obs',''),iid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/inquilinos/<int:iid>', methods=['DELETE'])
@login_required
def delete_inquilino(iid):
    conn = get_db()
    conn.execute('DELETE FROM inquilinos WHERE id=?', (iid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── API – Contratos ─────────────────────────────────────────────────────────
@app.route('/api/contratos', methods=['GET'])
@login_required
def get_contratos():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.*, u.codigo as unidade_codigo, i.nome as inquilino_nome
        FROM contratos c
        JOIN unidades u ON u.id = c.unidade_id
        JOIN inquilinos i ON i.id = c.inquilino_id
        ORDER BY c.inicio DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/contratos', methods=['POST'])
@login_required
def create_contrato():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO contratos (unidade_id,inquilino_id,tipo,valor,inicio,fim,obs) VALUES (?,?,?,?,?,?,?)',
        (d['unidade_id'],d['inquilino_id'],d.get('tipo','novo'),d.get('valor',0),d.get('inicio',''),d.get('fim',''),d.get('obs',''))
    )
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return jsonify({'id': new_id}), 201

@app.route('/api/contratos/<int:cid>', methods=['PUT'])
@login_required
def update_contrato(cid):
    d = request.json
    conn = get_db()
    conn.execute(
        'UPDATE contratos SET unidade_id=?,inquilino_id=?,tipo=?,valor=?,inicio=?,fim=?,obs=? WHERE id=?',
        (d['unidade_id'],d['inquilino_id'],d.get('tipo','novo'),d.get('valor',0),d.get('inicio',''),d.get('fim',''),d.get('obs',''),cid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/contratos/<int:cid>', methods=['DELETE'])
@login_required
def delete_contrato(cid):
    conn = get_db()
    conn.execute('DELETE FROM contratos WHERE id=?', (cid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── API – Pagamentos ────────────────────────────────────────────────────────
@app.route('/api/pagamentos', methods=['GET'])
@login_required
def get_pagamentos():
    ano  = request.args.get('ano',  type=int)
    mes  = request.args.get('mes',  type=int)
    cid  = request.args.get('contrato_id', type=int)
    uid  = request.args.get('unidade_id',  type=int)

    sql = '''
        SELECT p.*, c.unidade_id, c.inquilino_id,
               u.codigo as unidade_codigo, i.nome as inquilino_nome
        FROM pagamentos p
        JOIN contratos c ON c.id = p.contrato_id
        JOIN unidades  u ON u.id = c.unidade_id
        JOIN inquilinos i ON i.id = c.inquilino_id
        WHERE 1=1
    '''
    params = []
    if ano:  sql += ' AND p.ano=?';          params.append(ano)
    if mes:  sql += ' AND p.mes=?';          params.append(mes)
    if cid:  sql += ' AND p.contrato_id=?';  params.append(cid)
    if uid:  sql += ' AND c.unidade_id=?';   params.append(uid)
    sql += ' ORDER BY p.ano DESC, p.mes DESC, u.codigo'

    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/pagamentos', methods=['POST'])
@login_required
def create_pagamento():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO pagamentos (contrato_id,ano,mes,bruto,comissao,liquido,tipo_comissao,data_pgto,status,obs) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (d['contrato_id'],d['ano'],d['mes'],d.get('bruto',0),d.get('comissao',0),d.get('liquido',0),
         d.get('tipo_comissao','mensal'),d.get('data_pgto',''),d.get('status','pago'),d.get('obs',''))
    )
    conn.commit(); new_id = cur.lastrowid; conn.close()
    return jsonify({'id': new_id}), 201

@app.route('/api/pagamentos/<int:pid>', methods=['PUT'])
@login_required
def update_pagamento(pid):
    d = request.json
    conn = get_db()
    conn.execute(
        'UPDATE pagamentos SET contrato_id=?,ano=?,mes=?,bruto=?,comissao=?,liquido=?,tipo_comissao=?,data_pgto=?,status=?,obs=? WHERE id=?',
        (d['contrato_id'],d['ano'],d['mes'],d.get('bruto',0),d.get('comissao',0),d.get('liquido',0),
         d.get('tipo_comissao','mensal'),d.get('data_pgto',''),d.get('status','pago'),d.get('obs',''),pid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/api/pagamentos/<int:pid>', methods=['DELETE'])
@login_required
def delete_pagamento(pid):
    conn = get_db()
    conn.execute('DELETE FROM pagamentos WHERE id=?', (pid,))
    conn.commit(); conn.close()
    return jsonify({'ok': True})

# ─── API – Dashboard ─────────────────────────────────────────────────────────
@app.route('/api/dashboard')
@login_required
def dashboard():
    ano = request.args.get('ano', type=int) or __import__('datetime').date.today().year
    mes = request.args.get('mes', type=int) or __import__('datetime').date.today().month
    conn = get_db()
    total_unidades   = conn.execute('SELECT COUNT(*) FROM unidades').fetchone()[0]
    contratos_ativos = conn.execute(
        "SELECT COUNT(*) FROM contratos WHERE inicio <= date('now') AND fim >= date('now')"
    ).fetchone()[0]
    pags = conn.execute(
        'SELECT SUM(bruto) as tb, SUM(comissao) as tc, SUM(liquido) as tl FROM pagamentos WHERE ano=? AND mes=?',
        (ano, mes)
    ).fetchone()
    alertas = conn.execute(
        "SELECT c.id, u.codigo, i.nome, c.fim FROM contratos c JOIN unidades u ON u.id=c.unidade_id JOIN inquilinos i ON i.id=c.inquilino_id WHERE c.fim BETWEEN date('now') AND date('now','+60 days') AND c.fim >= date('now')"
    ).fetchall()
    conn.close()
    return jsonify({
        'total_unidades': total_unidades,
        'contratos_ativos': contratos_ativos,
        'bruto': round(pags['tb'] or 0, 2),
        'comissao': round(pags['tc'] or 0, 2),
        'liquido': round(pags['tl'] or 0, 2),
        'alertas': [dict(a) for a in alertas],
    })

@app.route('/api/relatorio')
@login_required
def relatorio():
    ano = request.args.get('ano', type=int)
    mes = request.args.get('mes', type=int)
    conn = get_db()
    sql = 'SELECT p.ano, p.mes, SUM(p.bruto) as bruto, SUM(p.comissao) as comissao, SUM(p.liquido) as liquido, COUNT(*) as qtd FROM pagamentos p WHERE 1=1'
    params = []
    if ano: sql += ' AND p.ano=?'; params.append(ano)
    if mes: sql += ' AND p.mes=?'; params.append(mes)
    sql += ' GROUP BY p.ano, p.mes ORDER BY p.ano, p.mes'
    rows = conn.execute(sql, params).fetchall()

    sql2 = '''SELECT u.codigo, u.tipo, SUM(p.bruto) as bruto, SUM(p.comissao) as comissao, SUM(p.liquido) as liquido, COUNT(*) as meses
              FROM pagamentos p JOIN contratos c ON c.id=p.contrato_id JOIN unidades u ON u.id=c.unidade_id
              WHERE 1=1'''
    params2 = []
    if ano: sql2 += ' AND p.ano=?'; params2.append(ano)
    sql2 += ' GROUP BY u.id ORDER BY u.codigo'
    rows2 = conn.execute(sql2, params2).fetchall()
    conn.close()
    return jsonify({'por_mes': [dict(r) for r in rows], 'por_unidade': [dict(r) for r in rows2]})

# ─── API – Sincronização ImoGestão ───────────────────────────────────────────
@app.route('/api/sincronizar', methods=['POST'])
@login_required
def api_sincronizar():
    global sync_running, sync_log
    if sync_running:
        return jsonify({'erro': 'Sincronização já em andamento'}), 409
    sync_log = []
    sync_running = True

    def run():
        global sync_running
        def log(msg):
            sync_log.append(msg)
        resultado = sincronizar(IMOB_CPF, IMOB_PASS, log_fn=log)
        sync_log.append(f"RESULTADO:{resultado['inseridos']}:{resultado['atualizados']}:{len(resultado['erros'])}")
        sync_running = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'status': 'iniciado'})

@app.route('/api/sincronizar/status')
@login_required
def sync_status():
    return jsonify({'rodando': sync_running, 'log': sync_log})

# ─── Exportar dados ──────────────────────────────────────────────────────────
@app.route('/api/export')
@login_required
def export_data():
    conn = get_db()
    data = {
        'unidades':   [dict(r) for r in conn.execute('SELECT * FROM unidades').fetchall()],
        'inquilinos': [dict(r) for r in conn.execute('SELECT * FROM inquilinos').fetchall()],
        'contratos':  [dict(r) for r in conn.execute('SELECT * FROM contratos').fetchall()],
        'pagamentos': [dict(r) for r in conn.execute('SELECT * FROM pagamentos').fetchall()],
    }
    conn.close()
    import json
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=imoveis_backup.json'}
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

# Garante init em produção
init_db()
