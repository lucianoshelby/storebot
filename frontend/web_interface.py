# storebot/frontend/web_interface.py
import sys
import os
# Ajuste o caminho se o backend não for encontrado.
# Se 'frontend' e 'backend' são pastas irmãs dentro de 'storebot':
sys.path.insert(0, 'C:\\Users\\Gestão MX\\Documents\\StoreBot')

from flask import Flask, render_template, request, redirect, url_for, flash, current_app
from flask_socketio import SocketIO, emit
import uuid
import time
from threading import Thread
from datetime import datetime
import logging

# Importar módulos do backend
from backend import database_manager
from backend import csv_processor
from backend import wpp_connector
from backend import auth_manager
from backend.config import DEFAULT_MESSAGE_DELAY_SECONDS

# Configuração do Flask
app = Flask(__name__)
app.secret_key = os.urandom(24) # Necessário para 'flash messages'

# Configurar pastas de upload (relativas à pasta 'frontend')
UPLOAD_FOLDER_CSV = 'uploaded_csvs'
UPLOAD_FOLDER_IMAGES = 'uploaded_campaign_images'
ALLOWED_EXTENSIONS_CSV = {'csv'}
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER_CSV'] = UPLOAD_FOLDER_CSV
app.config['UPLOAD_FOLDER_IMAGES'] = UPLOAD_FOLDER_IMAGES

# Criar pastas de upload se não existirem
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER_CSV), exist_ok=True)
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER_IMAGES), exist_ok=True)

# Inicializar Flask-SocketIO
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# --- Função de Disparo em Background ---
def process_campaign_dispatches_web(flask_app_context, socketio_instance, campaign_id):
    with flask_app_context: # Essencial para acesso ao current_app e configurações em threads
        try:
            current_app.logger.info(f"THREAD: Iniciando processamento para campaign_id: {campaign_id}")
            campaign_details = database_manager.get_campaign_details(campaign_id)

            if not campaign_details:
                current_app.logger.error(f"THREAD: Campanha {campaign_id} não encontrada.")
                socketio_instance.emit('campaign_error', {'campaign_id': campaign_id, 'message': 'Campanha não encontrada.'})
                return

            message_template = campaign_details['message_template']
            image_filename_from_db = campaign_details['image_filename']
            image_full_path_for_send = None

            if image_filename_from_db:
                # Caminho construído a partir da raiz da aplicação Flask (pasta 'frontend')
                # e da pasta de upload de imagens configurada.
                image_path_relative_to_frontend = os.path.join(current_app.config['UPLOAD_FOLDER_IMAGES'], image_filename_from_db)
                image_full_path_for_send = os.path.join(current_app.root_path, image_path_relative_to_frontend)

                if not os.path.exists(image_full_path_for_send):
                    current_app.logger.warning(f"THREAD: Imagem {image_filename_from_db} não encontrada em {image_full_path_for_send}. Enviando sem imagem.")
                    socketio_instance.emit('campaign_log', {
                        'campaign_id': campaign_id,
                        'message': f"AVISO: Imagem da campanha '{image_filename_from_db}' não encontrada. Disparos seguirão sem imagem."
                    })
                    image_full_path_for_send = None

            pending_dispatches = database_manager.get_pending_dispatches_for_campaign(campaign_id)
            if not pending_dispatches:
                current_app.logger.info(f"THREAD: Nenhum disparo pendente para {campaign_id}.")
                # Se não há contatos desde o início, pode ser um status diferente.
                # Assumindo que se chegou aqui e não há pendentes, é porque já foram processados ou não havia contatos.
                # O status da campanha já deve ter sido atualizado ao final do processamento anterior.
                # Se esta é a primeira vez e não há contatos, a criação da campanha deve lidar com isso.
                # Vamos emitir 'campaign_finished' apenas para garantir que o frontend saiba.
                final_status_check = database_manager.get_campaign_details(campaign_id)['status']
                if final_status_check not in ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]:
                     database_manager.update_campaign_status(campaign_id, "COMPLETED") # Default se não houver pendentes.
                     final_status_check = "COMPLETED"

                socketio_instance.emit('campaign_finished', {
                    'campaign_id': campaign_id,
                    'status': final_status_check,
                    'message': 'Nenhum contato pendente encontrado ou campanha já finalizada.'
                })
                return

            total_pending = len(pending_dispatches)
            success_count = 0
            failure_count = 0

            socketio_instance.emit('campaign_progress', {
                'campaign_id': campaign_id, 'processed': 0, 'total': total_pending,
                'success': 0, 'failed': 0,
                'status_text': f"Iniciando disparos para {total_pending} contatos..."
            })

            for i, dispatch_row in enumerate(pending_dispatches):
                log_id = dispatch_row['log_id']
                contact_phone = dispatch_row['contact_phone']
                contact_name = dispatch_row['contact_name'] if dispatch_row['contact_name'] else ""

                current_app.logger.info(f"THREAD: Processando {i+1}/{total_pending} para Campanha {campaign_id}: Contato='{contact_name}', Telefone='{contact_phone}'")
                socketio_instance.emit('dispatch_update', {
                    'campaign_id': campaign_id, 'log_id': log_id, 'contact_phone': contact_phone,
                    'contact_name': contact_name, 'status': 'PROCESSING',
                    'message': f"Processando {contact_name} ({contact_phone})..."
                })

                personalized_message = message_template.replace("{{nome}}", contact_name if contact_name else "cliente").strip()
                api_response_data_str = "{}"
                sent_successfully = False

                if not auth_manager.get_current_jwt_token(): # Garante token JWT
                    auth_manager.generate_jwt_token()

                if image_full_path_for_send:
                    current_app.logger.info(f"THREAD: Enviando imagem '{os.path.basename(image_full_path_for_send)}' para {contact_phone}")
                    sent_successfully, api_response_data = wpp_connector.send_whatsapp_image_message(
                        contact_phone, image_full_path_for_send, personalized_message
                    )
                else:
                    current_app.logger.info(f"THREAD: Enviando texto para {contact_phone}")
                    sent_successfully, api_response_data = wpp_connector.send_whatsapp_message(
                        contact_phone, personalized_message
                    )
                api_response_data_str = str(api_response_data)

                if sent_successfully:
                    success_count += 1
                    database_manager.update_dispatch_log(log_id, "SENT_SUCCESS", personalized_message, api_response_data_str)
                    socketio_instance.emit('dispatch_update', {
                        'campaign_id': campaign_id, 'log_id': log_id, 'contact_phone': contact_phone,
                        'status': 'SENT_SUCCESS', 'api_response': api_response_data_str,
                        'message': f"Sucesso: {contact_name} ({contact_phone})"
                    })
                else:
                    failure_count += 1
                    database_manager.update_dispatch_log(log_id, "SENT_FAILED", personalized_message, api_response_data_str)
                    socketio_instance.emit('dispatch_update', {
                        'campaign_id': campaign_id, 'log_id': log_id, 'contact_phone': contact_phone,
                        'status': 'SENT_FAILED', 'api_response': api_response_data_str,
                        'message': f"Falha: {contact_name} ({contact_phone})"
                    })

                socketio_instance.emit('campaign_progress', {
                    'campaign_id': campaign_id, 'processed': i + 1, 'total': total_pending,
                    'success': success_count, 'failed': failure_count,
                    'status_text': f"Processado {i+1} de {total_pending}..."
                })

                if i < total_pending - 1: # Não aplicar delay após a última mensagem
                    current_app.logger.info(f"THREAD: Aguardando {DEFAULT_MESSAGE_DELAY_SECONDS} segundos...")
                    time.sleep(DEFAULT_MESSAGE_DELAY_SECONDS)

            final_status = "COMPLETED"
            if failure_count > 0 and success_count > 0:
                final_status = "COMPLETED_WITH_ERRORS"
            elif failure_count > 0 and success_count == 0:
                final_status = "FAILED"
            
            database_manager.update_campaign_status(campaign_id, final_status)
            current_app.logger.info(f"THREAD: Processamento da campanha {campaign_id} concluído. Status: {final_status}")
            socketio_instance.emit('campaign_finished', {
                'campaign_id': campaign_id, 'status': final_status,
                'success_count': success_count, 'failure_count': failure_count,
                'total_dispatches': total_pending
            })
        except Exception as e:
            current_app.logger.error(f"THREAD: Erro catastrófico processando campanha {campaign_id}: {e}", exc_info=True)
            database_manager.update_campaign_status(campaign_id, "FAILED")
            socketio_instance.emit('campaign_error', {'campaign_id': campaign_id, 'message': f'Erro interno no servidor: {str(e)}'})


# --- Rotas Flask ---
@app.route('/')
def index():
    return render_template('index.html', title="Dashboard StoreBot")

@app.route('/lists', methods=['GET', 'POST'])
def manage_lists():
    # Usa app.root_path para garantir que o caminho é relativo à pasta 'frontend'
    csv_upload_folder_abs = os.path.join(app.root_path, app.config['UPLOAD_FOLDER_CSV'])
    os.makedirs(csv_upload_folder_abs, exist_ok=True)

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Nenhum arquivo selecionado no formulário!', 'danger')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado para upload!', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_CSV):
            filename_to_save = file.filename # Considerar usar secure_filename e uuid para nomes únicos
            filepath_abs = os.path.join(csv_upload_folder_abs, filename_to_save)
            
            try:
                file.save(filepath_abs)
                contacts = csv_processor.load_contacts_from_csv(filepath_abs)
                num_contacts = len(contacts) if contacts else 0
                if num_contacts > 0:
                    flash(f"Arquivo '{filename_to_save}' carregado com sucesso! ({num_contacts} contatos)", 'success')
                elif contacts is None:
                     flash(f"Erro ao ler o arquivo '{filename_to_save}'. Verifique o formato.", 'danger')
                     if os.path.exists(filepath_abs): os.remove(filepath_abs)
                else:
                    flash(f"Arquivo '{filename_to_save}' carregado, mas nenhum contato válido encontrado.", 'warning')
            except Exception as e:
                flash(f"Erro crítico ao salvar/processar '{filename_to_save}': {str(e)}", 'danger')
            return redirect(url_for('manage_lists'))
        else:
            flash('Tipo de arquivo CSV inválido! Apenas .csv são permitidos.', 'danger')
            return redirect(request.url)

    uploaded_files = []
    if os.path.exists(csv_upload_folder_abs):
        try:
            uploaded_files = sorted([
                f for f in os.listdir(csv_upload_folder_abs) 
                if os.path.isfile(os.path.join(csv_upload_folder_abs, f)) and allowed_file(f, ALLOWED_EXTENSIONS_CSV)
            ])
        except Exception as e:
            flash(f"Erro ao listar arquivos CSV: {str(e)}", 'danger')
            
    return render_template('manage_lists.html', 
                           title="Gerenciar Listas", 
                           uploaded_files=uploaded_files,
                           csv_upload_folder=app.config['UPLOAD_FOLDER_CSV'])


@app.route('/campaigns/new', methods=['GET', 'POST'])
def create_campaign():
    # Pasta de upload de CSVs (relativa ao 'frontend')
    csv_upload_folder_abs = os.path.join(app.root_path, app.config['UPLOAD_FOLDER_CSV'])
    # Pasta de upload de imagens da campanha (relativa ao 'frontend')
    campaign_images_folder_abs = os.path.join(app.root_path, app.config['UPLOAD_FOLDER_IMAGES'])
    os.makedirs(campaign_images_folder_abs, exist_ok=True)


    if request.method == 'POST':
        campaign_name_form = request.form.get('campaign_name')
        selected_csv_filename = request.form.get('csv_file')
        message_template = request.form.get('message_template')
        campaign_image_file = request.files.get('campaign_image')

        if not campaign_name_form or not selected_csv_filename or not message_template:
            flash('Nome da campanha, lista CSV e template da mensagem são obrigatórios!', 'danger')
            available_csvs = []
            if os.path.exists(csv_upload_folder_abs):
                available_csvs = [f for f in os.listdir(csv_upload_folder_abs) if allowed_file(f, ALLOWED_EXTENSIONS_CSV)]
            return render_template('create_campaign.html', title="Criar Campanha", available_csv_files=available_csvs, csv_upload_folder=app.config['UPLOAD_FOLDER_CSV']), 400

        csv_filepath_abs = os.path.join(csv_upload_folder_abs, selected_csv_filename)
        if not os.path.exists(csv_filepath_abs):
            flash(f"Arquivo CSV '{selected_csv_filename}' não encontrado!", 'danger')
            return redirect(url_for('create_campaign'))

        image_filename_for_db = None
        if campaign_image_file and campaign_image_file.filename != '':
            if allowed_file(campaign_image_file.filename, ALLOWED_EXTENSIONS_IMAGES):
                original_filename, file_extension = os.path.splitext(campaign_image_file.filename)
                image_filename_for_db = f"{original_filename}_{uuid.uuid4().hex[:8]}{file_extension}"
                image_save_path_abs = os.path.join(campaign_images_folder_abs, image_filename_for_db)
                try:
                    campaign_image_file.save(image_save_path_abs)
                    flash(f"Imagem da campanha '{campaign_image_file.filename}' carregada como '{image_filename_for_db}'.", 'info')
                except Exception as e:
                    flash(f"Erro ao salvar imagem da campanha: {str(e)}", 'danger')
                    image_filename_for_db = None
            else:
                flash('Tipo de arquivo de imagem inválido!', 'danger')
                return redirect(url_for('create_campaign'))
        
        campaign_id = "camp_web_" + uuid.uuid4().hex[:10]
        
        if not database_manager.add_campaign(
            campaign_id, selected_csv_filename, message_template, image_filename_for_db
        ):
            flash(f"Falha ao registrar a campanha '{campaign_id}' no BD.", 'danger')
            return redirect(url_for('create_campaign'))

        contacts = csv_processor.load_contacts_from_csv(csv_filepath_abs)
        if not contacts:
            flash(f"Nenhum contato válido no CSV '{selected_csv_filename}'. Campanha '{campaign_id}' criada, mas sem contatos.", 'warning')
            database_manager.update_campaign_status(campaign_id, "FAILED_NO_CONTACTS")
            return redirect(url_for('list_campaigns'))

        contacts_added_to_log = 0
        for contact_data in contacts:
            phone = contact_data.get('telefone')
            name = contact_data.get('nome', '')
            if phone:
                log_id = database_manager.add_dispatch_contact(campaign_id, phone, name, status='PENDING')
                if log_id: contacts_added_to_log +=1
        
        if contacts_added_to_log == 0 :
             flash(f"Campanha '{campaign_name_form}' (ID: {campaign_id}) criada, mas NENHUM contato foi adicionado à fila.", 'warning')
             database_manager.update_campaign_status(campaign_id, "FAILED_NO_CONTACTS")
        else:
            flash(f"Campanha '{campaign_name_form}' (ID: {campaign_id}) criada! {contacts_added_to_log} contatos preparados.", 'success')
        
        return redirect(url_for('list_campaigns'))

    available_csvs = []
    if os.path.exists(csv_upload_folder_abs):
        try:
            available_csvs = sorted([f for f in os.listdir(csv_upload_folder_abs) if allowed_file(f, ALLOWED_EXTENSIONS_CSV)])
        except Exception as e:
            flash(f"Erro ao listar CSVs: {str(e)}", "danger")
            
    return render_template('create_campaign.html', 
                           title="Criar Nova Campanha", 
                           available_csv_files=available_csvs,
                           csv_upload_folder=app.config['UPLOAD_FOLDER_CSV'])


@app.route('/campaigns')
def list_campaigns():
    all_campaigns_rows = database_manager.get_campaigns_with_status([
        'PENDING', 'IN_PROGRESS', 'COMPLETED', 
        'COMPLETED_WITH_ERRORS', 'FAILED_NO_CONTACTS', 'PAUSED', 'FAILED' 
    ])
    campaigns_for_template = [dict(campaign) for campaign in all_campaigns_rows] if all_campaigns_rows else []
    return render_template('list_campaigns.html', 
                           title="Minhas Campanhas", 
                           campaigns=campaigns_for_template)

@app.route('/campaigns/<campaign_id>/details')
def campaign_details_page(campaign_id):
    campaign = database_manager.get_campaign_details(campaign_id)
    if not campaign:
        flash(f"Campanha {campaign_id} não encontrada.", "danger")
        return redirect(url_for('list_campaigns'))
    
    # Futuramente, buscar logs de 'dispatch_log' para esta campanha
    # logs = database_manager.get_dispatches_for_campaign(campaign_id) # Exemplo
    flash(f"Página de detalhes para campanha {campaign_id} (Em desenvolvimento - logs e mais infos aqui).", "info")
    # Por enquanto, redireciona, mas idealmente teria seu próprio template.
    # return render_template('campaign_details.html', campaign=dict(campaign), logs=logs)
    return redirect(url_for('list_campaigns'))


@app.route('/campaigns/<campaign_id>/start', methods=['POST'])
def start_campaign_processing_route(campaign_id):
    campaign = database_manager.get_campaign_details(campaign_id)
    if not campaign:
        flash(f"Campanha {campaign_id} não encontrada!", 'danger')
        return redirect(url_for('list_campaigns'))

    # Permite reiniciar campanhas que falharam ou completaram com erros
    allowed_statuses_to_start = ['PENDING', 'PAUSED', 'FAILED', 'COMPLETED_WITH_ERRORS']
    if campaign['status'] not in allowed_statuses_to_start:
        flash(f"Campanha {campaign_id} não pode ser iniciada (status atual: {campaign['status']}).", 'warning')
        return redirect(url_for('list_campaigns'))

    database_manager.update_campaign_status(campaign_id, "IN_PROGRESS")
    flash(f"Iniciando disparos para a campanha '{campaign['csv_filename']}' (ID: {campaign_id}).", 'info')

    socketio.emit('campaign_status_update', {
        'campaign_id': campaign_id,
        'status': 'IN_PROGRESS',
        'message': 'Processamento da campanha iniciado...'
    })

    thread = Thread(target=process_campaign_dispatches_web, args=(current_app.app_context(), socketio, campaign_id))
    thread.daemon = True
    thread.start()
    
    return redirect(url_for('list_campaigns'))


# --- Handlers Socket.IO ---
@socketio.on('connect')
def handle_connect():
    current_app.logger.info(f"Cliente conectado: {request.sid}")
    emit('response', {'data': 'Conectado ao servidor StoreBot!', 'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    current_app.logger.info(f"Cliente desconectado: {request.sid}")

@socketio.on('my_event') # Exemplo de handler customizado
def handle_my_custom_event(json_data):
    current_app.logger.info(f'Recebido my_event de {request.sid}: {str(json_data)}')
    emit('my_response', json_data, broadcast=False, to=request.sid) # Envia de volta para o emissor

@app.route('/lists/delete/<path:filename>', methods=['POST'])
def delete_list_file(filename):
    # Caminho absoluto para a pasta de upload de CSVs
    csv_upload_folder_abs = os.path.join(app.root_path, app.config['UPLOAD_FOLDER_CSV'])
    filepath_to_delete = os.path.join(csv_upload_folder_abs, filename)

    # Validação de segurança básica para evitar traversal (embora <path:filename> ajude)
    # Garante que o arquivo a ser deletado está de fato dentro da pasta de uploads designada.
    if not os.path.normpath(filepath_to_delete).startswith(os.path.normpath(csv_upload_folder_abs)):
        flash('Tentativa de exclusão de arquivo inválida.', 'danger')
        return redirect(url_for('manage_lists'))

    if os.path.exists(filepath_to_delete):
        try:
            # Antes de excluir, verifique se o CSV não está sendo usado por alguma campanha PENDING ou IN_PROGRESS
            # Esta é uma verificação opcional, mas recomendada.
            # Para simplificar agora, vamos pular essa verificação, mas considere adicioná-la.
            # Ex: campaigns_using_list = database_manager.get_campaigns_by_csv(filename, statuses=['PENDING', 'IN_PROGRESS'])
            # if campaigns_using_list:
            #     flash(f"A lista '{filename}' está em uso por campanhas ativas e não pode ser excluída.", 'warning')
            #     return redirect(url_for('manage_lists'))

            os.remove(filepath_to_delete)
            flash(f"Lista '{filename}' excluída com sucesso.", 'success')
        except Exception as e:
            flash(f"Erro ao excluir a lista '{filename}': {str(e)}", 'danger')
    else:
        flash(f"Lista '{filename}' não encontrada para exclusão.", 'warning')
    
    return redirect(url_for('manage_lists'))

if __name__ == '__main__':
    database_manager.create_tables()
    # Use app.logger em vez de current_app.logger aqui
    app.logger.info("StoreBot: Tabelas do banco de dados verificadas/criadas.")
    app.logger.info("StoreBot: Iniciando servidor Flask com SocketIO na porta 5001...")
    
    # O uso de use_reloader=True com eventlet/gevent pode às vezes ser problemático
    # Se você tiver problemas com threads duplicadas ou inicialização estranha,
    # tente use_reloader=False durante o desenvolvimento do SocketIO.
    # Para produção, o reloader deve estar sempre desabilitado.
    socketio.run(app, debug=True, host='0.0.0.0', port=5001, use_reloader=True)