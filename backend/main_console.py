# main_console.py
import time
import datetime
import uuid # Para gerar IDs de campanha únicos
import os   # Para basename de arquivos
import json # Para manipulação de JSON
import database_manager
import csv_processor
import wpp_connector
import auth_manager # Para garantir que o token está sendo gerenciado
import session_manager # Importar o módulo que criamos ou onde colocamos as funções de sessão

from config import DEFAULT_MESSAGE_DELAY_SECONDS

def initialize_app():
    """Inicializa componentes necessários, como tabelas do BD e token JWT."""
    print("Inicializando StoreBot...")
    database_manager.create_tables()
    print("Banco de dados verificado/criado.")
    
    if not auth_manager.get_current_jwt_token():
        print("Tentando gerar token JWT inicial...")
        if not auth_manager.generate_jwt_token():
            print("ERRO CRÍTICO: Falha ao gerar token JWT. Verifique sua SECRET_KEY no config.py e a conexão com o servidor wppconnect.")
            print("O StoreBot não poderá funcionar sem um token JWT válido.")
            return False
        print("Token JWT obtido com sucesso.")
    else:
        print("Token JWT já disponível.")
    return True

def start_new_campaign():
    print("\n--- Iniciando Nova Campanha de Disparos ---")
    csv_filepath = input("Caminho do arquivo CSV de contatos (ex: contacts/lista.csv): ").strip()
    if not os.path.exists(csv_filepath):
        print(f"Erro: Arquivo CSV '{csv_filepath}' não encontrado.")
        return

    message_template = input("Digite o template da mensagem (use {{nome}} para personalizar): ").strip()
    if not message_template:
        print("Erro: Template da mensagem não pode ser vazio.")
        return

    image_path_input = input("Caminho da imagem para enviar (opcional, deixe em branco se não houver): ").strip()
    image_filename_for_db = None
    image_full_path_for_send = None

    if image_path_input:
        if not os.path.exists(image_path_input):
            print(f"Erro: Arquivo de imagem '{image_path_input}' não encontrado.")
            return
        image_filename_for_db = os.path.basename(image_path_input)
        image_full_path_for_send = image_path_input # Usaremos o caminho completo para envio

    # Gerar ID de campanha
    campaign_id = "camp_" + uuid.uuid4().hex[:12]
    csv_filename_for_db = os.path.basename(csv_filepath)

    # Registrar campanha no BD
    if not database_manager.add_campaign(campaign_id, csv_filename_for_db, message_template, image_filename_for_db):
        print(f"Falha ao registrar a campanha '{campaign_id}' no banco de dados.")
        return
    
    print(f"Campanha '{campaign_id}' registrada. Carregando contatos...")
    contacts = csv_processor.load_contacts_from_csv(csv_filepath)

    if not contacts:
        print("Nenhum contato válido carregado do CSV. A campanha não pode prosseguir.")
        database_manager.update_campaign_status(campaign_id, "FAILED_NO_CONTACTS") # Um novo status
        return

    print(f"{len(contacts)} contatos carregados. Adicionando à fila de disparo...")
    for contact in contacts:
        database_manager.add_dispatch_contact(campaign_id, contact['telefone'], contact['nome'])
    
    print("Contatos adicionados à fila. Iniciando processamento da campanha...")
    database_manager.update_campaign_status(campaign_id, "IN_PROGRESS")
    process_campaign_dispatches(campaign_id, message_template, image_full_path_for_send)


def process_campaign_dispatches(campaign_id, message_template, image_to_send_path=None):
    """Processa os disparos pendentes para uma campanha."""
    print(f"\n--- Processando Disparos para Campanha: {campaign_id} ---")
    
    pending_dispatches = database_manager.get_pending_dispatches_for_campaign(campaign_id)
    if not pending_dispatches:
        print("Nenhum disparo pendente encontrado para esta campanha.")
        # Verificar se há falhas para decidir o status final
        # (implementação mais completa de status pode ser feita depois)
        database_manager.update_campaign_status(campaign_id, "COMPLETED")
        return

    total_pending = len(pending_dispatches)
    print(f"Encontrados {total_pending} disparos pendentes.")
    
    success_count = 0
    failure_count = 0

    for i, dispatch_row in enumerate(pending_dispatches):
        log_id = dispatch_row['log_id']
        contact_phone = dispatch_row['contact_phone']
        contact_name = dispatch_row['contact_name'] if dispatch_row['contact_name'] else "" # Garantir que não é None

        print(f"\nProcessando {i+1}/{total_pending}: Contato='{contact_name}', Telefone='{contact_phone}'")

        # Personalizar mensagem
        personalized_message = message_template.replace("{{nome}}", contact_name if contact_name else "cliente").strip()
        
        api_response_data = None
        sent_successfully = False

        if image_to_send_path:
            print(f"Enviando mensagem com imagem: '{os.path.basename(image_to_send_path)}'...")
            sent_successfully, api_response_data = wpp_connector.send_whatsapp_image_message(
                contact_phone, 
                image_to_send_path, 
                personalized_message # Legenda é a própria mensagem personalizada
            )
        else:
            print("Enviando mensagem de texto...")
            sent_successfully, api_response_data = wpp_connector.send_whatsapp_message(
                contact_phone, 
                personalized_message
            )

        if sent_successfully:
            success_count += 1
            print(f"Sucesso! Resposta: {api_response_data}")
            database_manager.update_dispatch_log(log_id, "SENT_SUCCESS", personalized_message, json.dumps(api_response_data))
        else:
            failure_count += 1
            print(f"Falha! Detalhes: {api_response_data}")
            database_manager.update_dispatch_log(log_id, "SENT_FAILED", personalized_message, json.dumps(api_response_data)) # Salva a mensagem mesmo em falha

        # Delay entre mensagens
        if i < total_pending - 1: # Não aplicar delay após a última mensagem
            print(f"Aguardando {DEFAULT_MESSAGE_DELAY_SECONDS} segundos antes do próximo envio...")
            time.sleep(DEFAULT_MESSAGE_DELAY_SECONDS)

    print("\n--- Processamento da Campanha Concluído ---")
    print(f"Resumo: {success_count} envios com sucesso, {failure_count} falhas.")
    
    final_status = "COMPLETED"
    if failure_count > 0 and success_count > 0:
        final_status = "COMPLETED_WITH_ERRORS"
    elif failure_count > 0 and success_count == 0:
        final_status = "FAILED" # Todas falharam
    database_manager.update_campaign_status(campaign_id, final_status)

def list_and_resume_campaign():
    print("\n--- Retomar Campanha Pendente ---")
    # Listar campanhas que estão PENDING, IN_PROGRESS ou PAUSED (ou com falhas para retry - mais complexo)
    # Por simplicidade, vamos listar as que têm status IN_PROGRESS ou PENDING
    campaigns_to_resume = database_manager.get_campaigns_with_status(['IN_PROGRESS', 'PENDING'])
    
    if not campaigns_to_resume:
        print("Nenhuma campanha pendente ou em progresso para retomar.")
        return

    print("Campanhas disponíveis para retomar:")
    for idx, camp_row in enumerate(campaigns_to_resume):
        print(f"{idx + 1}. ID: {camp_row['campaign_id']} | CSV: {camp_row['csv_filename']} | Msg: \"{camp_row['message_template'][:30]}...\" | Img: {camp_row['image_filename']} | Status: {camp_row['status']}")

    try:
        choice_idx = int(input("Escolha o número da campanha para retomar (0 para cancelar): ")) - 1
        if choice_idx < 0 or choice_idx >= len(campaigns_to_resume):
            if choice_idx + 1 == 0:
                print("Retomada cancelada.")
            else:
                print("Escolha inválida.")
            return
        
        selected_campaign_row = campaigns_to_resume[choice_idx]
        campaign_id_to_resume = selected_campaign_row['campaign_id']
        
        # Precisamos dos detalhes da campanha para a mensagem e imagem
        # A função get_campaign_details poderia ser usada, mas já temos a linha.
        message_template = selected_campaign_row['message_template']
        image_filename = selected_campaign_row['image_filename']
        image_full_path_for_send = None
        if image_filename:
            # Assumindo que as imagens das campanhas ficam na pasta 'images_to_send/'
            # Ou poderíamos pedir o caminho da imagem novamente, ou armazenar o caminho completo no BD (menos portatil)
            # Por agora, vamos assumir que a imagem precisa estar na pasta padrão.
            potential_image_path = os.path.join("images_to_send", image_filename)
            if os.path.exists(potential_image_path):
                image_full_path_for_send = potential_image_path
            else:
                print(f"Aviso: Arquivo de imagem '{image_filename}' da campanha não encontrado em 'images_to_send/'. A campanha será retomada sem imagem.")

        print(f"Retomando campanha '{campaign_id_to_resume}'...")
        if selected_campaign_row['status'] == 'PENDING': # Se estava pendente, marcar como em progresso
             database_manager.update_campaign_status(campaign_id_to_resume, "IN_PROGRESS")
        process_campaign_dispatches(campaign_id_to_resume, message_template, image_full_path_for_send)

    except ValueError:
        print("Entrada inválida.")

def main_menu():
    if not initialize_app(): # Tenta inicializar e obter token
        return # Sai se não conseguir o token inicial

    # Verificar conexão com WhatsApp
    # Idealmente, o session_manager teria uma função para isso que é chamada aqui.
    print("\nVerificando status da conexão WhatsApp...")
    if not session_manager.check_session_status(): # Usando a função que criamos
        print("AVISO: Sessão WhatsApp não está conectada. Tentando conectar...")
        if not session_manager.start_and_get_qr_code():
             input("Pressione Enter após tentar escanear o QR Code (se mostrado)...")
        if not session_manager.check_session_status():
            print("ERRO: Não foi possível conectar à sessão do WhatsApp. Verifique o servidor wppconnect e escaneie o QR Code.")
            print("Algumas funcionalidades podem não operar corretamente.")
            # Poderia optar por sair aqui ou permitir continuar com aviso.
    else:
        print("Sessão WhatsApp conectada.")


    while True:
        print("\n--- StoreBot - Menu Principal ---")
        print("1. Iniciar Nova Campanha de Disparos")
        print("2. Retomar Campanha Pendente")
        print("3. Gerenciar Conexão WhatsApp") # Usaria funções do session_manager
        print("4. Sair")
        choice = input("Escolha uma opção: ").strip()

        if choice == '1':
            start_new_campaign()
        elif choice == '2':
            list_and_resume_campaign()
        elif choice == '3':
            # Aqui chamaria um submenu ou funções diretas do session_manager
            # Exemplo de submenu para session_manager:
            session_manager.manage_whatsapp_connection_menu() # Supondo que criamos essa função no session_manager
        elif choice == '4':
            print("Saindo do StoreBot...")
            break
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == '__main__':
    # Criar o session_manager.py se ainda não foi criado e adicionar as funções
    # start_and_get_qr_code, check_session_status, logout_session
    # e uma função de menu como manage_whatsapp_connection_menu()
    
    # Exemplo de como session_manager.py poderia ter o menu:
    # def manage_whatsapp_connection_menu():
    #     while True:
    #         print("\n--- Gerenciar Conexão WhatsApp ---")
    #         print("1. Conectar/Verificar QR Code")
    #         print("2. Verificar Status da Conexão")
    #         print("3. Desconectar Sessão")
    #         print("0. Voltar ao Menu Principal")
    #         sub_choice = input("Escolha uma opção: ")
    #         if sub_choice == '1':
    #             if not check_session_status():
    #                 start_and_get_qr_code()
    #                 input("Pressione Enter após escanear o QR Code (se aplicável)...")
    #                 check_session_status()
    #             else:
    #                 print("Sessão já está conectada.")
    #         elif sub_choice == '2':
    #             check_session_status()
    #         elif sub_choice == '3':
    #             logout_session()
    #         elif sub_choice == '0':
    #             break
    #         else:
    #             print("Opção inválida.")

    # No momento, vou assumir que session_manager.py existe com as funções
    # check_session_status e start_and_get_qr_code como definidas anteriormente.
    # Para simplificar, vou integrar a chamada direta aqui.

    if 'session_manager' not in globals() or not hasattr(session_manager, 'check_session_status'):
        print("AVISO: session_manager.py não encontrado ou não configurado completamente. As funções de gerenciamento de conexão podem estar limitadas.")
        # Criar funções placeholder se o módulo não existir para evitar erros,
        # ou instruir o usuário a criá-lo.
        # Por agora, vamos apenas prosseguir. Se o usuário não escolher a opção 3, não será um problema imediato.
        class PlaceholderSessionManager:
            def check_session_status(self): print("Placeholder: check_session_status"); return True
            def start_and_get_qr_code(self): print("Placeholder: start_and_get_qr_code"); return False
            def logout_session(self): print("Placeholder: logout_session"); return True
            def manage_whatsapp_connection_menu(self):
                print("Opção de Gerenciar Conexão não implementada completamente sem session_manager.py")
        session_manager = PlaceholderSessionManager()


    main_menu()