# test_db.py
import database_manager as dbm # Nosso módulo do banco de dados
import datetime
import uuid # Para gerar IDs únicos para teste
import os
import json # Para simular a resposta da API

# Tenta obter o nome do arquivo do banco de dados do módulo database_manager
# ou define um padrão se não estiver acessível diretamente.
DB_FILE_NAME = getattr(dbm, 'DATABASE_NAME', 'storebot.db')


def run_all_db_tests():
    print("--- Iniciando Testes do Banco de Dados ---")

    # Opcional: Remover o arquivo .db existente para um teste totalmente limpo
    if os.path.exists(DB_FILE_NAME):
        print(f"Removendo banco de dados existente '{DB_FILE_NAME}' para um teste limpo...")
        try:
            os.remove(DB_FILE_NAME)
        except PermissionError:
            print(f"AVISO: Não foi possível remover '{DB_FILE_NAME}'. O arquivo pode estar em uso.")
            print("Os testes continuarão, mas podem usar dados preexistentes se a remoção falhar.")

    # 1. Testar criação de tabelas
    print("\n[TESTE 1] Criando tabelas...")
    dbm.create_tables()
    print("Função create_tables() executada.")
    print(f"Verifique se o arquivo '{DB_FILE_NAME}' foi criado/atualizado.")
    print("Recomendado: Abra o arquivo com 'DB Browser for SQLite' para inspecionar o schema.")

    # 2. Testar Operações de Campanhas
    print("\n[TESTE 2] Operações de Campanhas...")
    campaign_id_1 = "camp_test_" + uuid.uuid4().hex[:8]
    csv_file_1 = "lista_A.csv"
    msg_template_1 = "Olá {{nome}}, oferta especial!"
    img_file_1 = "promo_A.jpg"

    print(f"Adicionando campanha: {campaign_id_1}...")
    assert dbm.add_campaign(campaign_id_1, csv_file_1, msg_template_1, img_file_1) == True, "Falha ao adicionar campanha 1"

    details_1 = dbm.get_campaign_details(campaign_id_1)
    assert details_1 is not None, f"Falha ao obter detalhes da campanha {campaign_id_1}"
    assert details_1['campaign_id'] == campaign_id_1
    assert details_1['csv_filename'] == csv_file_1
    assert details_1['message_template'] == msg_template_1
    assert details_1['image_filename'] == img_file_1
    assert details_1['status'] == 'PENDING' # Status padrão ao adicionar
    print(f"Detalhes da campanha '{campaign_id_1}' recuperados: {dict(details_1)}")

    print(f"Atualizando status da campanha '{campaign_id_1}' para 'IN_PROGRESS'...")
    assert dbm.update_campaign_status(campaign_id_1, "IN_PROGRESS") == True, "Falha ao atualizar status"
    details_1_updated = dbm.get_campaign_details(campaign_id_1)
    assert details_1_updated['status'] == 'IN_PROGRESS'
    print("Status da campanha atualizado com sucesso.")

    campaign_id_2 = "camp_test_" + uuid.uuid4().hex[:8]
    dbm.add_campaign(campaign_id_2, "lista_B.csv", "Msg para {{nome}}", status='COMPLETED')
    print(f"Adicionada campanha de teste 2: {campaign_id_2} com status COMPLETED")

    in_progress_campaigns = dbm.get_campaigns_with_status(['IN_PROGRESS'])
    assert len(in_progress_campaigns) >= 1, "Nenhuma campanha IN_PROGRESS encontrada quando esperado"
    assert any(c['campaign_id'] == campaign_id_1 for c in in_progress_campaigns), f"Campanha {campaign_id_1} não encontrada entre as IN_PROGRESS"
    print(f"Campanhas em progresso encontradas: {[dict(c) for c in in_progress_campaigns]}")

    # 3. Testar Operações de Logs de Disparo
    print("\n[TESTE 3] Operações de Logs de Disparo...")
    contact1_phone = "5562999990001"
    contact1_name = "Carlos Teste"
    contact2_phone = "5562999990002"
    contact2_name = "Ana Testadora"

    print(f"Adicionando contatos à fila da campanha '{campaign_id_1}'...")
    log_id_1 = dbm.add_dispatch_contact(campaign_id_1, contact1_phone, contact1_name)
    assert log_id_1 is not None, "Falha ao adicionar contato 1 ao log"
    print(f"Contato 1 (Log ID: {log_id_1}) adicionado com status PENDING.")

    log_id_2 = dbm.add_dispatch_contact(campaign_id_1, contact2_phone, contact2_name, status='PENDING') # Status explícito
    assert log_id_2 is not None, "Falha ao adicionar contato 2 ao log"
    print(f"Contato 2 (Log ID: {log_id_2}) adicionado com status PENDING.")

    pending_for_camp1 = dbm.get_pending_dispatches_for_campaign(campaign_id_1)
    assert len(pending_for_camp1) == 2, f"Esperado 2 disparos pendentes, encontrado {len(pending_for_camp1)}"
    print(f"Disparos pendentes para '{campaign_id_1}' antes da atualização: {[dict(d) for d in pending_for_camp1]}")

    print(f"Atualizando log ID {log_id_1} para SENT_SUCCESS...")
    msg_sent_to_contact1 = msg_template_1.replace("{{nome}}", contact1_name)
    api_resp_contact1 = json.dumps({'api_status':'ok', 'id':'msg123'}) # Simular resposta JSON
    assert dbm.update_dispatch_log(log_id_1, "SENT_SUCCESS", msg_sent_to_contact1, api_resp_contact1) == True, f"Falha ao atualizar log ID {log_id_1}"

    pending_for_camp1_after = dbm.get_pending_dispatches_for_campaign(campaign_id_1)
    assert len(pending_for_camp1_after) == 1, f"Esperado 1 disparo pendente após atualização, encontrado {len(pending_for_camp1_after)}"
    if pending_for_camp1_after: # Para evitar erro se a lista estiver inesperadamente vazia
        assert pending_for_camp1_after[0]['log_id'] == log_id_2, "O disparo pendente restante não é o esperado"
    print(f"Disparos pendentes para '{campaign_id_1}' após atualização: {[dict(d) for d in pending_for_camp1_after]}")

    # Verificar detalhes do log atualizado
    conn_check = dbm.get_db_connection()
    cursor_check = conn_check.cursor()
    cursor_check.execute("SELECT * FROM dispatch_log WHERE log_id = ?", (log_id_1,))
    updated_log_1_details = cursor_check.fetchone()
    conn_check.close()

    assert updated_log_1_details is not None, f"Não foi possível recuperar o log ID {log_id_1} atualizado"
    assert updated_log_1_details['status'] == "SENT_SUCCESS"
    assert updated_log_1_details['personalized_message_text'] == msg_sent_to_contact1
    assert updated_log_1_details['api_response'] == api_resp_contact1
    assert updated_log_1_details['sent_at'] is not None # Deve ter sido preenchido
    print(f"Detalhes verificados do log ID {log_id_1} (status SENT_SUCCESS): {dict(updated_log_1_details)}")

    print("\n--- Testes do Banco de Dados Concluídos ---")
    print(f"Se todos os 'asserts' passaram, as funções básicas estão operando como esperado.")
    print(f"Recomendação final: Abra o arquivo '{DB_FILE_NAME}' com um visualizador de SQLite (como DB Browser for SQLite) para inspecionar os dados e a estrutura das tabelas.")

if __name__ == '__main__':
    run_all_db_tests()