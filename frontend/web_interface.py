# web_interface.py
import sys
sys.path.insert(0, 'C:\\Users\\Gestão MX\\Documents\\StoreBot') # Ajuste o caminho conforme necessário
from flask import Flask, render_template, request, redirect, url_for, flash
import os
import uuid # Para nomes de arquivo únicos, se necessário
# Importar seus módulos existentes
from backend import database_manager
from backend import csv_processor
# config.py também será usado implicitamente pelos outros módulos

# Configuração básica do Flask
app = Flask(__name__)
app.secret_key = os.urandom(24) # Necessário para 'flash messages'

# Configurar pastas de upload
# (Idealmente, isso viria do config.py)
UPLOAD_FOLDER_CSV = 'uploaded_csvs'
UPLOAD_FOLDER_IMAGES = 'uploaded_campaign_images'
ALLOWED_EXTENSIONS_CSV = {'csv'}
ALLOWED_EXTENSIONS_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER_CSV'] = UPLOAD_FOLDER_CSV
app.config['UPLOAD_FOLDER_IMAGES'] = UPLOAD_FOLDER_IMAGES

# Criar pastas de upload se não existirem
os.makedirs(UPLOAD_FOLDER_CSV, exist_ok=True)
os.makedirs(UPLOAD_FOLDER_IMAGES, exist_ok=True)

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

from datetime import datetime

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

@app.route('/')
def index():
    """Página inicial / Dashboard (placeholder por enquanto)."""
    # No futuro, pode mostrar campanhas, status, etc.
    return render_template('index.html', title="Dashboard StoreBot")

@app.route('/lists', methods=['GET', 'POST'])
def manage_lists():
    """Página para fazer upload de novas listas CSV e ver as existentes."""
    # Garante que a pasta de upload para CSVs existe
    os.makedirs(app.config['UPLOAD_FOLDER_CSV'], exist_ok=True)

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Nenhum arquivo selecionado no formulário!', 'danger')
            return redirect(request.url)
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado para upload!', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_CSV):
            # Para evitar nomes de arquivo com caracteres problemáticos e garantir unicidade:
            # filename_secure = secure_filename(file.filename) # Importar secure_filename de werkzeug.utils
            # filename_to_save = f"{uuid.uuid4().hex[:8]}_{filename_secure}"
            # Por simplicidade, vamos usar o nome original, mas CUIDADO com sobrescrita e caracteres.
            filename_to_save = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER_CSV'], filename_to_save)
            
            try:
                file.save(filepath)
                # Validar o CSV após o upload (opcional, mas recomendado)
                contacts = csv_processor.load_contacts_from_csv(filepath) # do backend/csv_processor.py
                num_contacts = len(contacts) if contacts else 0

                if num_contacts > 0:
                    flash(f"Arquivo '{filename_to_save}' carregado com sucesso! ({num_contacts} contatos encontrados)", 'success')
                elif contacts is None: # csv_processor pode retornar None em caso de erro de arquivo
                     flash(f"Erro ao tentar ler o arquivo '{filename_to_save}'. Verifique o formato e o console do servidor.", 'danger')
                     if os.path.exists(filepath): os.remove(filepath) # Remove arquivo inválido
                else: # Lista vazia, mas arquivo lido sem erro fatal
                    flash(f"Arquivo '{filename_to_save}' carregado, mas nenhum contato válido foi encontrado. Verifique o conteúdo do CSV.", 'warning')
            except Exception as e:
                flash(f"Erro crítico ao salvar ou processar o arquivo '{filename_to_save}': {str(e)}", 'danger')
            
            return redirect(url_for('manage_lists'))
        else:
            flash('Tipo de arquivo CSV inválido! Apenas arquivos .csv são permitidos.', 'danger')
            return redirect(request.url)

    # Método GET: Listar arquivos CSV existentes na pasta de upload
    uploaded_files = []
    csv_upload_folder_path = app.config['UPLOAD_FOLDER_CSV']
    if os.path.exists(csv_upload_folder_path):
        try:
            # Lista apenas arquivos, ignorando subdiretórios, e que sejam CSV
            uploaded_files = sorted([
                f for f in os.listdir(csv_upload_folder_path) 
                if os.path.isfile(os.path.join(csv_upload_folder_path, f)) and allowed_file(f, ALLOWED_EXTENSIONS_CSV)
            ])
        except Exception as e:
            flash(f"Erro ao listar arquivos CSV da pasta '{csv_upload_folder_path}': {str(e)}", 'danger')
            
    return render_template('manage_lists.html', 
                           title="Gerenciar Listas de Contatos", 
                           uploaded_files=uploaded_files,
                           csv_upload_folder=csv_upload_folder_path)


@app.route('/campaigns/new', methods=['GET', 'POST'])
def create_campaign():
    # Assegurar que o token JWT está disponível e válido antes de operações críticas
    # (Pode ser feito aqui ou com um decorador, ou assumir que initialize_app cuidou disso)
    # if not auth_manager.get_current_jwt_token():
    #     if not auth_manager.generate_jwt_token():
    #         flash("Erro crítico: Falha ao obter token de autenticação para o servidor WPPConnect. Tente recarregar ou verificar o status do servidor.", "danger")
    #         return redirect(url_for('index')) # Ou uma página de erro

    if request.method == 'POST':
        campaign_name_form = request.form.get('campaign_name') # Usado para referência, não salvo no BD diretamente como nome da campanha
        selected_csv_filename = request.form.get('csv_file')
        message_template = request.form.get('message_template')
        campaign_image_file = request.files.get('campaign_image')

        if not campaign_name_form or not selected_csv_filename or not message_template:
            flash('Nome da campanha, lista CSV e template da mensagem são obrigatórios!', 'danger')
            # Re-popula a lista de CSVs para o template em caso de erro
            available_csvs = []
            if os.path.exists(app.config['UPLOAD_FOLDER_CSV']):
                available_csvs = [f for f in os.listdir(app.config['UPLOAD_FOLDER_CSV']) if allowed_file(f, ALLOWED_EXTENSIONS_CSV)]
            return render_template('create_campaign.html', title="Criar Campanha", available_csv_files=available_csvs, csv_upload_folder=app.config['UPLOAD_FOLDER_CSV']), 400


        csv_filepath = os.path.join(app.config['UPLOAD_FOLDER_CSV'], selected_csv_filename)
        if not os.path.exists(csv_filepath):
            flash(f"Arquivo CSV '{selected_csv_filename}' não encontrado na pasta de uploads!", 'danger')
            return redirect(url_for('create_campaign'))

        image_filename_for_db = None
        if campaign_image_file and campaign_image_file.filename != '':
            if allowed_file(campaign_image_file.filename, ALLOWED_EXTENSIONS_IMAGES):
                # Adicionar um UUID ao nome do arquivo para evitar conflitos e manter o original
                original_filename, file_extension = os.path.splitext(campaign_image_file.filename)
                image_filename_for_db = f"{original_filename}_{uuid.uuid4().hex[:8]}{file_extension}"
                
                image_save_path = os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], image_filename_for_db)
                try:
                    campaign_image_file.save(image_save_path)
                    flash(f"Imagem da campanha '{campaign_image_file.filename}' carregada como '{image_filename_for_db}'.", 'info')
                except Exception as e:
                    flash(f"Erro ao salvar imagem da campanha: {str(e)}", 'danger')
                    image_filename_for_db = None # Prossegue sem imagem se salvar falhar
            else:
                flash('Tipo de arquivo de imagem inválido! Use PNG, JPG, GIF ou WEBP.', 'danger')
                return redirect(url_for('create_campaign'))
        
        campaign_id = "camp_web_" + uuid.uuid4().hex[:10] # ID único para a campanha
        
        # 1. Registrar campanha no BD (usando selected_csv_filename como referência de nome)
        if not database_manager.add_campaign(
            campaign_id, 
            selected_csv_filename, # Nome do CSV como "nome" da campanha por enquanto
            message_template, 
            image_filename_for_db # Pode ser None
        ):
            flash(f"Falha crítica ao registrar a campanha '{campaign_id}' no banco de dados.", 'danger')
            return redirect(url_for('create_campaign'))

        # 2. Carregar contatos do CSV
        contacts = csv_processor.load_contacts_from_csv(csv_filepath)
        if not contacts:
            flash(f"Nenhum contato válido encontrado ou falha ao ler o CSV '{selected_csv_filename}'. A campanha foi criada (ID: {campaign_id}), mas não há contatos para disparo.", 'warning')
            database_manager.update_campaign_status(campaign_id, "FAILED_NO_CONTACTS")
            return redirect(url_for('list_campaigns'))

        # 3. Adicionar contatos à fila de disparo (dispatch_log) com status PENDING
        contacts_added_to_log = 0
        for contact_data in contacts:
            phone = contact_data.get('telefone')
            name = contact_data.get('nome', '')
            if phone:
                log_id = database_manager.add_dispatch_contact(campaign_id, phone, name, status='PENDING')
                if log_id:
                    contacts_added_to_log +=1
        
        if contacts_added_to_log == 0 :
             flash(f"Campanha '{campaign_name_form}' (ID: {campaign_id}) criada, mas NENHUM contato foi adicionado à fila (verifique o CSV).", 'warning')
             database_manager.update_campaign_status(campaign_id, "FAILED_NO_CONTACTS")
        else:
            flash(f"Campanha '{campaign_name_form}' (ID: {campaign_id}) criada com sucesso! {contacts_added_to_log} contatos preparados para disparo.", 'success')
        
        return redirect(url_for('list_campaigns'))

    # Método GET: Exibir o formulário
    available_csvs = []
    csv_upload_folder_path = app.config['UPLOAD_FOLDER_CSV']
    if os.path.exists(csv_upload_folder_path):
        try:
            available_csvs = sorted([f for f in os.listdir(csv_upload_folder_path) if allowed_file(f, ALLOWED_EXTENSIONS_CSV)])
        except Exception as e:
            flash(f"Erro ao listar arquivos CSV disponíveis: {str(e)}", "danger")
            
    return render_template('create_campaign.html', 
                           title="Criar Nova Campanha", 
                           available_csv_files=available_csvs,
                           csv_upload_folder=csv_upload_folder_path)


@app.route('/campaigns')
def list_campaigns():
    """Página para listar todas as campanhas."""
    # Buscar todas as campanhas, ordenadas pela mais recente primeiro
    all_campaigns_rows = database_manager.get_campaigns_with_status([
        'PENDING', 'IN_PROGRESS', 'COMPLETED', 
        'COMPLETED_WITH_ERRORS', 'FAILED_NO_CONTACTS', 'PAUSED', 'FAILED' 
    ]) # get_campaigns_with_status já ordena por created_at DESC
    
    campaigns_for_template = [dict(campaign) for campaign in all_campaigns_rows] if all_campaigns_rows else []
    
    return render_template('list_campaigns.html', 
                           title="Minhas Campanhas", 
                           campaigns=campaigns_for_template)

# --- Placeholder para futuras rotas de detalhes e início de campanha ---
@app.route('/campaigns/<campaign_id>/details')
def campaign_details_page(campaign_id):
    # Esta função será implementada depois para mostrar os logs de disparo
    flash(f"Página de detalhes para campanha {campaign_id} (Em desenvolvimento).", "info")
    return redirect(url_for('list_campaigns'))

@app.route('/campaigns/<campaign_id>/start', methods=['POST'])
def start_campaign_processing(campaign_id):
    # Esta função será implementada depois para iniciar os disparos em background
    flash(f"Funcionalidade de iniciar campanha {campaign_id} (Em desenvolvimento).", "info")
    # Aqui você chamaria a lógica para iniciar o process_campaign_dispatches em background
    # e talvez atualizar o status da campanha para IN_PROGRESS
    # database_manager.update_campaign_status(campaign_id, "IN_PROGRESS")
    return redirect(url_for('list_campaigns'))


if __name__ == '__main__':
    # Inicializar tabelas do BD
    database_manager.create_tables()
    # Flask-SocketIO será integrado aqui depois
    app.run(debug=True, host='0.0.0.0', port=5001) # Usando porta 5001 para não conflitar com wppconnect-server se local