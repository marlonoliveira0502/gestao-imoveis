"""
Scraper para o sistema ImoGestão (sistema.imogestao.com.br)
Extrai demonstrativos de repasse e atualiza o banco de dados.
"""
import re
import requests
from bs4 import BeautifulSoup
from database import get_db

BASE_URL = "https://sistema.imogestao.com.br/cliente"
IMOB_ID  = "755489"   # idpro fixo do proprietário
SESSION_COOKIES = {}

MESES = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',
         7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
MESES_REV = {v:k for k,v in MESES.items()}


def login(cpf: str, senha: str, imob_nome: str = "Invest Imobiliária") -> requests.Session:
    """Faz login no ImoGestão e retorna sessão autenticada."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        'Referer': f'{BASE_URL}/',
        'X-Requested-With': 'XMLHttpRequest',
    })

    cpf_clean = cpf.replace('.','').replace('-','').replace('/','')

    # ID fixo da Invest Imobiliária (id=306 confirmado via acoes.php?p=geral&tx=invest)
    IMOB_CE = "306"

    # 1. Buscar página inicial para obter cookies de sessão e nome dinâmico dos campos
    r = session.get(f"{BASE_URL}/", timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    # Extrair nomes dinâmicos dos campos CPF/senha (ex: "2449" e "x2449")
    cc_field = None
    for inp in soup.find_all('input'):
        name = inp.get('name', '')
        if name and name.isdigit():
            cc_field = name
            cs_field = 'x' + name
            break
    if not cc_field:
        # fallback: procurar no JS da página
        m = re.search(r'cc:\s*\$\("#(\d+)"\)', r.text)
        if m:
            cc_field = m.group(1)
            cs_field = 'x' + cc_field
        else:
            cc_field, cs_field = 'cc', 'cs'

    # 2. POST para acoes.asp com acao=login (fluxo AJAX real do ImoGestão)
    r3 = session.post(f"{BASE_URL}/acoes.asp", data={
        'acao': 'login',
        cc_field: cpf_clean,
        cs_field: senha,
        'ce': IMOB_CE,
        'c': '',
        'd': '',
    }, timeout=30)

    try:
        resp = r3.json()
    except Exception:
        raise ValueError(f"Cloudflare ou resposta inválida: {r3.status_code} {r3.text[:300]}")

    if resp.get('erro', 1) != 0:
        raise ValueError(f"Login recusado pelo ImoGestão: {resp.get('mensagem', str(resp))}")

    # 3. GET login.php?cc=XX&h=XX para ativar a sessão
    session.get(f"{BASE_URL}/login.php?cc={resp['cc']}&h={resp['h']}", timeout=30)

    # 4. Verificar acesso à central do cliente
    r5 = session.get(f"{BASE_URL}/centralcliente.asp", timeout=30)
    if not any(kw in r5.text for kw in ["Manuel Marlon", "Central do Cliente", "locador", "Bem-vindo"]):
        raise ValueError(f"Sessão não estabelecida. Status: {r5.status_code}")

    return session


def get_dimob_links(session: requests.Session) -> list[dict]:
    """Retorna lista de {contrato, ano, url} do relatório DIMOB."""
    r = session.get(f"{BASE_URL}/dimob.asp")
    soup = BeautifulSoup(r.text, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if 'dimob_locador.asp' in href:
            links.append(f"{BASE_URL}/{href}" if not href.startswith('http') else href)
    return list(dict.fromkeys(links))  # dedup


def parse_dimob_page(session: requests.Session, url: str) -> dict | None:
    """Extrai dados mensais de um comprovante anual DIMOB."""
    r = session.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    text = soup.get_text('\n')

    # Número do contrato
    m = re.search(r'Contrato\s+(\d+)', text)
    if not m:
        return None
    contrato_num = int(m.group(1))

    # Ano
    m2 = re.search(r'Ano-calendário:\s*(\d{4})', text)
    ano = int(m2.group(1)) if m2 else None

    # Tabela de rendimentos (linha por mês)
    rows = []
    in_table = False
    for line in text.split('\n'):
        line = line.strip()
        if 'Rendimentos (em Reais)' in line:
            in_table = True
            continue
        if in_table:
            if 'Total' in line:
                break
            parts = line.split()
            if len(parts) >= 2 and parts[0] in MESES_REV:
                try:
                    bruto   = float(parts[1].replace('.','').replace(',','.'))
                    comissao= float(parts[2].replace('.','').replace(',','.')) if len(parts) > 2 else 0
                    liquido = round(bruto - comissao, 2)
                    rows.append({
                        'mes': MESES_REV[parts[0]],
                        'bruto': bruto,
                        'comissao': comissao,
                        'liquido': liquido,
                    })
                except Exception:
                    pass

    return {'contrato_num': contrato_num, 'ano': ano, 'meses': rows}


def get_demonstrativos_mensais(session: requests.Session) -> list[dict]:
    """Acessa a página de Locações e retorna os 3 demonstrativos mensais recentes."""
    r = session.get(f"{BASE_URL}/locacoes.asp")
    soup = BeautifulSoup(r.text, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        if 'demonstrativo3.asp' in a['href']:
            href = a['href']
            full = f"{BASE_URL}/{href}" if not href.startswith('http') else href
            links.append(full)
    return list(dict.fromkeys(links))


def parse_demonstrativo_mensal(session: requests.Session, url: str) -> list[dict]:
    """Extrai pagamentos de um demonstrativo mensal de repasse."""
    r = session.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    text = soup.get_text('\n')
    results = []

    # Extrair mês/ano do período
    m = re.search(r'pagos entre\s+\S+\s+a\s+\S+/(\d+)/(\d{4})', text)
    if not m:
        m = re.search(r'(\d+)/(\d{4})', text)
    mes_rel = int(m.group(1)) if m else None
    ano_rel = int(m.group(2)) if m else None

    # Blocos por locação
    blocks = re.split(r'Locação Nº\s+(\d+)', text)
    i = 1
    while i < len(blocks):
        loc_num = int(blocks[i]) if blocks[i].isdigit() else None
        content = blocks[i+1] if i+1 < len(blocks) else ''

        # Locatário
        inq_m = re.search(r'Locatário:\s*(.+?)\s*-\s*CPF', content)
        locatario = inq_m.group(1).strip() if inq_m else ''

        # Competência
        comp_m = re.search(r'(\d+)/(\d{4})\s+Aluguel período', content)
        if comp_m:
            mes_comp = int(comp_m.group(1))
            ano_comp = int(comp_m.group(2))
        else:
            mes_comp, ano_comp = mes_rel, ano_rel

        # Valores
        val_m = re.search(r'Aluguel período[^\n]+\n\s*([\d.,]+)', content)
        bruto = float(val_m.group(1).replace('.','').replace(',','.')) if val_m else 0

        tax_m = re.search(r'Taxa de Administração[^\n]*\n?\s*-?([\d.,]+)', content)
        comissao_raw = float(tax_m.group(1).replace('.','').replace(',','.')) if tax_m else 0

        # Renovação
        ren_m = re.search(r'Renova[çc]ão[^\n]+\n?\s*-?([\d.,]+)', content, re.I)
        if ren_m:
            comissao_raw = float(ren_m.group(1).replace('.','').replace(',','.'))
            tipo = 'primeiro_renovacao'
        else:
            tipo = 'mensal' if bruto else None

        # Data de pagamento
        data_m = re.search(r'(\d{2}/\d{2}/\d{4})\s+Repasse ref loca[çc]ão nº\s+' + str(loc_num), content)
        data_pgto = ''
        if data_m:
            d,mo,y = data_m.group(1).split('/')
            data_pgto = f"{y}-{mo}-{d}"

        if loc_num and bruto > 0 and mes_comp and ano_comp:
            results.append({
                'locacao_num': loc_num,
                'locatario': locatario,
                'ano': ano_comp,
                'mes': mes_comp,
                'bruto': bruto,
                'comissao': comissao_raw,
                'liquido': round(bruto - comissao_raw, 2),
                'tipo_comissao': tipo or 'mensal',
                'data_pgto': data_pgto,
                'status': 'pago',
            })
        i += 2
    return results


def find_contrato_id_by_locacao(conn, locacao_num: int) -> int | None:
    """Mapeia número de locação do ImoGestão para ID de contrato no DB."""
    # Tenta buscar pelo campo obs
    row = conn.execute(
        "SELECT id FROM contratos WHERE obs LIKE ?", (f'%Loc. {locacao_num}%',)
    ).fetchone()
    return row['id'] if row else None


def sincronizar(cpf: str, senha: str, log_fn=print) -> dict:
    """
    Sincroniza dados do ImoGestão com o banco local.
    Retorna {'inseridos': N, 'atualizados': N, 'erros': [...]}
    """
    result = {'inseridos': 0, 'atualizados': 0, 'erros': []}
    try:
        log_fn("🔐 Fazendo login no ImoGestão...")
        session = login(cpf, senha)
        log_fn("✅ Login realizado com sucesso")

        conn = get_db()

        # 1. Demonstrativos mensais recentes (mais precisos)
        log_fn("📋 Buscando demonstrativos mensais recentes...")
        dem_links = get_demonstrativos_mensais(session)
        log_fn(f"   Encontrados {len(dem_links)} demonstrativos")

        for url in dem_links:
            try:
                pagamentos = parse_demonstrativo_mensal(session, url)
                for p in pagamentos:
                    contrato_id = find_contrato_id_by_locacao(conn, p['locacao_num'])
                    if not contrato_id:
                        log_fn(f"  ⚠️  Locação {p['locacao_num']} não encontrada no DB")
                        continue
                    existing = conn.execute(
                        'SELECT id FROM pagamentos WHERE contrato_id=? AND ano=? AND mes=?',
                        (contrato_id, p['ano'], p['mes'])
                    ).fetchone()
                    if existing:
                        conn.execute(
                            'UPDATE pagamentos SET bruto=?,comissao=?,liquido=?,tipo_comissao=?,data_pgto=?,status=?,obs=? WHERE id=?',
                            (p['bruto'],p['comissao'],p['liquido'],p['tipo_comissao'],p['data_pgto'],p['status'],p.get('obs',''),existing['id'])
                        )
                        result['atualizados'] += 1
                    else:
                        conn.execute(
                            'INSERT INTO pagamentos (contrato_id,ano,mes,bruto,comissao,liquido,tipo_comissao,data_pgto,status,obs) VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (contrato_id,p['ano'],p['mes'],p['bruto'],p['comissao'],p['liquido'],p['tipo_comissao'],p['data_pgto'],p['status'],p.get('obs','Sincronizado automaticamente'))
                        )
                        result['inseridos'] += 1
            except Exception as e:
                result['erros'].append(f"Demonstrativo {url}: {e}")

        # 2. Comprovantes DIMOB anuais (histórico)
        log_fn("📊 Buscando comprovantes anuais DIMOB...")
        dimob_links = get_dimob_links(session)
        log_fn(f"   Encontrados {len(dimob_links)} comprovantes")

        for url in dimob_links:
            try:
                data = parse_dimob_page(session, url)
                if not data:
                    continue
                contrato_id = find_contrato_id_by_locacao(conn, data['contrato_num'])
                if not contrato_id:
                    continue
                for m in data['meses']:
                    if m['bruto'] == 0:
                        continue
                    existing = conn.execute(
                        'SELECT id FROM pagamentos WHERE contrato_id=? AND ano=? AND mes=?',
                        (contrato_id, data['ano'], m['mes'])
                    ).fetchone()
                    if not existing:
                        tipo = 'mensal'
                        if m['comissao'] / m['bruto'] > 0.45:
                            tipo = 'primeiro_renovacao'
                        elif m['comissao'] >= m['bruto'] * 0.99:
                            tipo = 'primeiro_novo'
                        conn.execute(
                            'INSERT INTO pagamentos (contrato_id,ano,mes,bruto,comissao,liquido,tipo_comissao,data_pgto,status,obs) VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (contrato_id,data['ano'],m['mes'],m['bruto'],m['comissao'],m['liquido'],tipo,'','pago','DIMOB – sincronizado')
                        )
                        result['inseridos'] += 1
            except Exception as e:
                result['erros'].append(f"DIMOB {url}: {e}")

        conn.commit()
        conn.close()
        log_fn(f"✅ Sincronização concluída: {result['inseridos']} inseridos, {result['atualizados']} atualizados")
    except Exception as e:
        result['erros'].append(str(e))
        log_fn(f"❌ Erro: {e}")
    return result
