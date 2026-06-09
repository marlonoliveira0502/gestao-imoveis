import sqlite3
import os
import json

DB_PATH = os.environ.get('DB_PATH', 'imoveis.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS unidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'apartamento',
    descricao TEXT,
    aluguel REAL,
    area REAL DEFAULT 0,
    obs TEXT
);
CREATE TABLE IF NOT EXISTS inquilinos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cpf TEXT,
    tel TEXT,
    email TEXT,
    obs TEXT
);
CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unidade_id INTEGER NOT NULL,
    inquilino_id INTEGER NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'novo',
    valor REAL,
    inicio TEXT,
    fim TEXT,
    obs TEXT,
    FOREIGN KEY (unidade_id) REFERENCES unidades(id),
    FOREIGN KEY (inquilino_id) REFERENCES inquilinos(id)
);
CREATE TABLE IF NOT EXISTS pagamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato_id INTEGER NOT NULL,
    ano INTEGER,
    mes INTEGER,
    bruto REAL,
    comissao REAL,
    liquido REAL,
    tipo_comissao TEXT DEFAULT 'mensal',
    data_pgto TEXT,
    status TEXT DEFAULT 'pago',
    obs TEXT,
    FOREIGN KEY (contrato_id) REFERENCES contratos(id)
);
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_config(chave, default=None):
    conn = get_db()
    row = conn.execute('SELECT valor FROM config WHERE chave=?', (chave,)).fetchone()
    conn.close()
    return row['valor'] if row else default

def set_config(chave, valor):
    conn = get_db()
    conn.execute('INSERT OR REPLACE INTO config (chave, valor) VALUES (?,?)', (chave, valor))
    conn.commit()
    conn.close()

def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    # Seed se vazio
    if conn.execute('SELECT COUNT(*) FROM unidades').fetchone()[0] == 0:
        seed_data(conn)
    conn.close()

def seed_data(conn):
    unidades = [
        ('AP-101','apartamento',"Apto. 101 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1682,0,'Cód. imob: 1067'),
        ('AP-102','apartamento',"Apto. 102 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1600,0,'Cód. imob: 1072'),
        ('AP-103','apartamento',"Apto. 103 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1600,0,'Cód. imob: 1073'),
        ('FL-204','flat',      "Apto. 204 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",937.26,0,'Cód. imob: 1108'),
        ('FL-205','flat',      "Apto. 205 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1000,0,'Cód. imob: 1103'),
        ('AP-206','apartamento',"Apto. 206 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1563.90,0,'Cód. imob: 1084'),
        ('AP-207','apartamento',"Apto. 207 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1563.90,0,'Cód. imob: 1090'),
        ('AP-208','apartamento',"Apto. 208 – Cond. Oliveira's Garden, Rua 07, Qd. 57, Lt. 16 – Vale do Itacaiúnas, Marabá/PA",1563.90,0,'Cód. imob: 1093'),
    ]
    conn.executemany('INSERT INTO unidades (codigo,tipo,descricao,aluguel,area,obs) VALUES (?,?,?,?,?,?)', unidades)

    inquilinos = [
        ('Cristiano Silva Correa','600.395.742-53','','','Loc. 558 – AP-101 (ativo)'),
        ('Célia Cristina Teixeira Pereira','674.486.822-53','','','Loc. 565 – AP-206 (ativo)'),
        ('Marcio Antônio Albino Junior','063.739.061-08','','','Loc. 570 – AP-208 (ativo)'),
        ('Rafaela de Oliveira Silva','120.695.839-10','','','Loc. 596 – FL-204 (ativo)'),
        ('Nadiny Karine dos Santos Ferreira Alves','073.084.305-02','','','Loc. 601 – FL-205 (ativo)'),
        ('Maria Aparecida Correa','329.363.462-15','','','Loc. 625 – AP-102 (ativo)'),
        ('Kamila Stephany Silva Oyama','704.748.941-00','','','Loc. 632 – AP-103 (ativo)'),
        ('Nelson Teles de Menezes Neto','886.452.825-34','','','Loc. 569 – AP-207 (desocupação)'),
        ('Augusto Amorim Melo Araujo','012.049.952-57','','','Loc. 557 – AP-102 (encerrado set/2025)'),
        ('Dunax Lubrificantes LTDA','05.092.901/0032-70','','','Loc. 571 – AP-103 (encerrado dez/2025)'),
        ('Lucas Souza Gomes e Silva','095.490.166-50','','','Loc. 582 – FL-204 (encerrado mar/2025)'),
    ]
    conn.executemany('INSERT INTO inquilinos (nome,cpf,tel,email,obs) VALUES (?,?,?,?,?)', inquilinos)

    contratos = [
        (1,1,'novo',1682,'2024-10-10','2027-04-09','Loc. 558 – reajuste 10/2026'),
        (6,2,'novo',1563.90,'2024-12-05','2027-06-04','Loc. 565 – reajuste 12/2026'),
        (8,3,'novo',1563.90,'2024-12-20','2027-06-19','Loc. 570 – renovação fev/2026'),
        (4,4,'renovacao',937.26,'2025-04-08','2026-10-07','Loc. 596 – renovação 6 meses'),
        (5,5,'novo',1000,'2025-05-10','2027-11-09','Loc. 601 – reajuste 05/2027'),
        (2,6,'novo',1600,'2025-10-28','2028-04-27','Loc. 625 – reajuste 10/2026'),
        (3,7,'novo',1600,'2026-01-05','2028-07-04','Loc. 632 – reajuste 01/2027'),
        (7,8,'novo',1563.90,'2024-12-24','2026-04-30','Loc. 569 – em desocupação'),
        (2,9,'novo',1600,'2024-10-10','2025-09-30','Loc. 557 – anterior AP-102'),
        (3,10,'novo',1600,'2025-01-06','2025-12-31','Loc. 571 – anterior AP-103'),
        (4,11,'novo',900,'2025-02-10','2025-03-31','Loc. 582 – anterior FL-204'),
    ]
    conn.executemany('INSERT INTO contratos (unidade_id,inquilino_id,tipo,valor,inicio,fim,obs) VALUES (?,?,?,?,?,?,?)', contratos)

    # Pagamentos históricos completos
    pagamentos = [
        # 2026 Jan/Fev
        (1,2026,1,1682,153.22,1528.78,'mensal','','pago','IR 2026'),
        (1,2026,2,1682,153.22,1528.78,'mensal','','pago','IR 2026'),
        (2,2026,1,1500,135,1365,'mensal','','pago','IR 2026'),
        (2,2026,2,1500,135,1365,'mensal','','pago','IR 2026'),
        (3,2026,1,1500,135,1365,'mensal','','pago','IR 2026'),
        (3,2026,2,1563.90,706.95,856.95,'primeiro_renovacao','','pago','Renovação – 50% Invest Imobiliária'),
        (4,2026,1,900,100,800,'mensal','','pago','IR 2026'),
        (4,2026,2,900,100,800,'mensal','','pago','IR 2026'),
        (5,2026,1,1000,100,900,'mensal','','pago','IR 2026'),
        (5,2026,2,1000,100,900,'mensal','','pago','IR 2026'),
        (6,2026,1,1600,145,1455,'mensal','','pago','IR 2026'),
        (6,2026,2,1600,145,1455,'mensal','','pago','IR 2026'),
        (7,2026,1,1600,1600,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (7,2026,2,150,0,150,'isento','','pago','IR 2026 – valor parcial'),
        (8,2026,1,1563.90,141.39,1422.51,'mensal','','pago','IR 2026'),
        (8,2026,2,1563.90,141.39,1422.51,'mensal','','pago','IR 2026'),
        # 2026 Mar (demonstrativo exato)
        (1,2026,3,1682,168.20,1513.80,'mensal','2026-04-13','pago',''),
        (2,2026,3,1563.90,141.39,1422.51,'mensal','2026-04-06','pago',''),
        (8,2026,3,1563.90,141.39,1422.51,'mensal','2026-04-28','pago',''),
        (3,2026,3,1563.90,141.39,1422.51,'mensal','2026-04-20','pago',''),
        (4,2026,3,900,100,800,'mensal','2026-04-08','pago',''),
        (5,2026,3,1000,100,900,'mensal','2026-04-08','pago',''),
        (6,2026,3,1600,145,1455,'mensal','2026-04-29','pago',''),
        (7,2026,3,1600,145,1455,'mensal','2026-04-06','pago',''),
        # 2026 Abr (demonstrativo exato)
        (1,2026,4,1682,168.20,1513.80,'mensal','2026-05-11','pago',''),
        (2,2026,4,1563.90,141.39,1422.51,'mensal','2026-05-06','pago',''),
        (3,2026,4,1563.90,141.39,1422.51,'mensal','2026-05-20','pago',''),
        (4,2026,4,937.26,468.63,468.63,'primeiro_renovacao','2026-05-08','pago','Renovação 6 meses – 50%'),
        (5,2026,4,1000,100,900,'mensal','2026-05-08','pago',''),
        (6,2026,4,1600,145,1455,'mensal','2026-06-01','pago','Pago com atraso'),
        (7,2026,4,1600,145,1455,'mensal','2026-05-07','pago',''),
        # 2025 – Augusto (contrato 9)
        (9,2024,10,1600,1600,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (9,2025,1,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,2,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,3,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,4,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,5,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,6,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,7,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,8,1600,145,1455,'mensal','','pago','IR 2025'),
        (9,2025,9,1600,145,1455,'mensal','','pago','IR 2025'),
        # 2025 – Cristiano (contrato 1)
        (1,2024,10,1600,1600,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (1,2025,1,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,2,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,3,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,4,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,5,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,6,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,7,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,8,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,9,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,10,1600,145,1455,'mensal','','pago','IR 2025'),
        (1,2025,11,1657.40,753.70,903.70,'primeiro_renovacao','','pago','Renovação – 50% Invest Imobiliária'),
        (1,2025,12,1682,153.22,1528.78,'mensal','','pago','IR 2025'),
        # 2025 – Célia (contrato 2)
        (2,2024,12,1500,1500,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (2,2025,3,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,5,4500,420,4080,'mensal','','pago','3 meses acumulados (fev-abr/2025)'),
        (2,2025,6,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,7,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,8,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,9,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,10,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,11,1500,135,1365,'mensal','','pago','IR 2025'),
        (2,2025,12,1500,135,1365,'mensal','','pago','IR 2025'),
        # 2025 – Nelson (contrato 8)
        (8,2024,12,1500,1500,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (8,2025,2,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,3,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,4,1500,150,1350,'mensal','','pago','IR 2025'),
        (8,2025,5,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,6,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,7,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,8,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,9,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,10,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,11,1500,135,1365,'mensal','','pago','IR 2025'),
        (8,2025,12,1500,135,1365,'mensal','','pago','IR 2025'),
        # 2025 – Marcio (contrato 3)
        (3,2024,12,1500,1500,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (3,2025,2,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,3,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,4,1500,150,1350,'mensal','','pago','IR 2025'),
        (3,2025,5,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,6,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,7,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,8,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,9,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,10,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,11,1500,135,1365,'mensal','','pago','IR 2025'),
        (3,2025,12,1500,135,1365,'mensal','','pago','IR 2025'),
        # 2025 – Dunax (contrato 10)
        (10,2025,1,1600,1600,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (10,2025,3,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,4,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,5,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,6,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,7,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,8,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,9,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,10,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,11,1600,145,1455,'mensal','','pago','IR 2025'),
        (10,2025,12,1600,145,1455,'mensal','','pago','IR 2025'),
        # 2025 – Lucas (contrato 11)
        (11,2025,2,900,0,900,'isento','','pago','Único mês – s/ comissão (IR 2025)'),
        # 2025 – Rafaela (contrato 4)
        (4,2025,5,450,0,450,'isento','','pago','1º repasse – imob reteve 50% (IR 2025)'),
        (4,2025,6,900,100,800,'mensal','','pago','IR 2025'),
        (4,2025,7,900,100,800,'mensal','','pago','IR 2025'),
        (4,2025,8,900,100,800,'mensal','','pago','IR 2025'),
        (4,2025,9,900,100,800,'mensal','','pago','IR 2025'),
        (4,2025,10,900,100,800,'mensal','','pago','IR 2025'),
        (4,2025,11,900,100,800,'mensal','','pago','IR 2025'),
        (4,2025,12,900,90,810,'mensal','','pago','IR 2025'),
        # 2025 – Nadiny (contrato 5)
        (5,2025,5,1000,1000,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (5,2025,7,1000,100,900,'mensal','','pago','IR 2025'),
        (5,2025,8,1000,100,900,'mensal','','pago','IR 2025'),
        (5,2025,9,1000,100,900,'mensal','','pago','IR 2025'),
        (5,2025,10,1000,100,900,'mensal','','pago','IR 2025'),
        (5,2025,11,1000,100,900,'mensal','','pago','IR 2025'),
        (5,2025,12,1000,100,900,'mensal','','pago','IR 2025'),
        # 2025 – Maria (contrato 6)
        (6,2025,10,1600,1600,0,'primeiro_novo','','pago','1º mês – imobiliária retém 100%'),
        (6,2025,12,1600,145,1455,'mensal','','pago','IR 2025'),
    ]
    conn.executemany(
        'INSERT INTO pagamentos (contrato_id,ano,mes,bruto,comissao,liquido,tipo_comissao,data_pgto,status,obs) VALUES (?,?,?,?,?,?,?,?,?,?)',
        pagamentos
    )
    conn.commit()
