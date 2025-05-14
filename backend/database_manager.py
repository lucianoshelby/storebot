# database_manager.py
import sys
sys.path.insert(0, 'C:\\Users\\Gestão MX\\Documents\\StoreBot')
import sqlite3
import os
import datetime # Para timestamps
from backend.config import DATABASE_NAME

# get_db_connection() e create_tables() permanecem como antes

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    """Cria as tabelas no banco de dados se elas não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        campaign_id TEXT PRIMARY KEY,
        csv_filename TEXT,
        message_template TEXT,
        image_filename TEXT, /* Apenas o nome do arquivo, não o caminho completo */
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'PENDING' /* PENDING, IN_PROGRESS, COMPLETED, COMPLETED_WITH_ERRORS, PAUSED */
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dispatch_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT,
        contact_phone TEXT NOT NULL,
        contact_name TEXT,
        personalized_message_text TEXT, /* Mensagem após substituir {{nome}} */
        sent_at DATETIME,
        status TEXT NOT NULL, /* PENDING, SENT_SUCCESS, SENT_FAILED */
        api_response TEXT,
        FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id)
    )
    """)

    conn.commit()
    conn.close()
    # Comentado para não poluir o console toda vez que for importado
    # print(f"Banco de dados '{DATABASE_NAME}' e tabelas verificados/criados.")

# --- Novas Funções ---

def add_campaign(campaign_id, csv_filename, message_template, image_filename=None, status='PENDING'):
    """Adiciona uma nova campanha ao banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO campaigns (campaign_id, csv_filename, message_template, image_filename, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (campaign_id, csv_filename, message_template, image_filename, status, datetime.datetime.now()))
        conn.commit()
        print(f"Campanha '{campaign_id}' adicionada ao banco de dados.")
        return True
    except sqlite3.Error as e:
        print(f"Erro ao adicionar campanha '{campaign_id}': {e}")
        return False
    finally:
        conn.close()

def update_campaign_status(campaign_id, status):
    """Atualiza o status de uma campanha."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE campaigns SET status = ? WHERE campaign_id = ?", (status, campaign_id))
        conn.commit()
        print(f"Status da campanha '{campaign_id}' atualizado para '{status}'.")
        return True
    except sqlite3.Error as e:
        print(f"Erro ao atualizar status da campanha '{campaign_id}': {e}")
        return False
    finally:
        conn.close()

def get_campaign_details(campaign_id):
    """Recupera os detalhes de uma campanha específica."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,))
        campaign = cursor.fetchone()
        return campaign # Retorna um objeto sqlite3.Row ou None
    except sqlite3.Error as e:
        print(f"Erro ao buscar detalhes da campanha '{campaign_id}': {e}")
        return None
    finally:
        conn.close()

def add_dispatch_contact(campaign_id, contact_phone, contact_name, status='PENDING'):
    """Adiciona um contato à fila de disparos de uma campanha."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO dispatch_log (campaign_id, contact_phone, contact_name, status)
        VALUES (?, ?, ?, ?)
        """, (campaign_id, contact_phone, contact_name, status))
        conn.commit()
        return cursor.lastrowid # Retorna o ID do log inserido
    except sqlite3.Error as e:
        print(f"Erro ao adicionar contato '{contact_phone}' ao log de disparo da campanha '{campaign_id}': {e}")
        return None
    finally:
        conn.close()

def update_dispatch_log(log_id, status, personalized_message_text=None, api_response=None):
    """Atualiza um registro no log de disparos."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        timestamp = datetime.datetime.now()
        if personalized_message_text:
            cursor.execute("""
            UPDATE dispatch_log 
            SET status = ?, personalized_message_text = ?, sent_at = ?, api_response = ?
            WHERE log_id = ?
            """, (status, personalized_message_text, timestamp, api_response, log_id))
        else: # Não atualiza a mensagem se não for fornecida (ex: ao marcar como PENDING inicialmente)
            cursor.execute("""
            UPDATE dispatch_log 
            SET status = ?, sent_at = ?, api_response = ?
            WHERE log_id = ?
            """, (status, timestamp, api_response, log_id))
        conn.commit()
        # print(f"Log de disparo ID {log_id} atualizado para status '{status}'.")
        return True
    except sqlite3.Error as e:
        print(f"Erro ao atualizar log de disparo ID {log_id}: {e}")
        return False
    finally:
        conn.close()

def get_pending_dispatches_for_campaign(campaign_id):
    """Retorna todos os contatos com status 'PENDING' para uma campanha."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        SELECT * FROM dispatch_log 
        WHERE campaign_id = ? AND status = 'PENDING'
        """, (campaign_id,))
        pending_dispatches = cursor.fetchall()
        return pending_dispatches # Lista de objetos sqlite3.Row
    except sqlite3.Error as e:
        print(f"Erro ao buscar disparos pendentes para campanha '{campaign_id}': {e}")
        return []
    finally:
        conn.close()

def get_campaigns_with_status(status_list=['PENDING', 'IN_PROGRESS', 'PAUSED']):
    """Lista campanhas com um determinado status (ou lista de status)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        placeholders = ','.join('?' for _ in status_list)
        query = f"SELECT * FROM campaigns WHERE status IN ({placeholders}) ORDER BY created_at DESC"
        cursor.execute(query, status_list)
        campaigns = cursor.fetchall()
        return campaigns
    except sqlite3.Error as e:
        print(f"Erro ao buscar campanhas com status {status_list}: {e}")
        return []
    finally:
        conn.close()

if __name__ == '__main__':
    print("Executando create_tables para garantir que o schema está atualizado...")
    create_tables()
    print("Schema do banco de dados verificado/atualizado.")

    # Bloco de teste opcional para as novas funções
    # test_campaign_id = "test_campaign_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # add_campaign(test_campaign_id, "test.csv", "Olá {{nome}}", "test_image.png")
    # campaign_details = get_campaign_details(test_campaign_id)
    # if campaign_details:
    #     print(f"Detalhes da campanha de teste: {dict(campaign_details)}")
    
    # log_id = add_dispatch_contact(test_campaign_id, "5500999998888", "Teste Contato DB")
    # if log_id:
    #     print(f"Contato de teste adicionado ao log com ID: {log_id}")
    #     update_dispatch_log(log_id, "SENT_SUCCESS", "Olá Teste Contato DB", '{"api_status":"ok"}')

    # pending = get_pending_dispatches_for_campaign(test_campaign_id) # Deveria estar vazio agora
    # print(f"Pendentes para {test_campaign_id}: {pending}")

    # campaigns_pending = get_campaigns_with_status(['PENDING'])
    # print(f"Campanhas pendentes: {[dict(c) for c in campaigns_pending]}")
    # update_campaign_status(test_campaign_id, "COMPLETED")