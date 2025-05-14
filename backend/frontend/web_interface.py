# web_interface.py
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

@app.route('/')
def index():
    """Página inicial / Dashboard (placeholder por enquanto)."""
    # No futuro, pode mostrar campanhas, status, etc.
    return render_template('index.html', title="Dashboard StoreBot")

@app.route('/lists', methods=['GET', 'POST'])
def manage_lists():
    """Página para fazer upload de novas listas CSV e ver as existentes."""
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Nenhum arquivo selecionado!', 'danger')
            return redirect(request.url)

        file = request.files['csv_file']

        if file.filename == '':
            flash('Nenhum arquivo selecionado!', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS_CSV):
            # Para evitar sobrescrever, podemos adicionar um UUID ao nome do arquivo
            # ou usar o nome original se não houver conflito.
            # Por simplicidade, vamos usar o nome original por enquanto.
            # Cuidado: isso pode sobrescrever arquivos com o mesmo nome.
            filename = file.filename 
            filepath = os.path.join(app.config['UPLOAD_FOLDER_CSV'], filename)

            try:
                file.save(filepath)
                # Validar o CSV (opcional aqui, mas bom)
                contacts = csv_processor.load_contacts_from_csv(filepath)
                if contacts:
                    flash(f"Arquivo '{filename}' carregado com sucesso! ({len(contacts)} contatos encontrados)", 'success')
                else:
                    # Se load_contacts_from_csv retornar lista vazia, pode ser erro de formato ou arquivo vazio.
                    # A função csv_processor já imprime erros no console.
                    flash(f"Arquivo '{filename}' carregado, mas nenhum contato válido encontrado ou houve um erro de formato. Verifique o console do servidor.", 'warning')
                    # Poderíamos remover o arquivo se a validação for crítica aqui: os.remove(filepath)
            except Exception as e:
                flash(f"Erro ao salvar ou processar o arquivo '{filename}': {str(e)}", 'danger')

            return redirect(url_for('manage_lists'))
        else:
            flash('Tipo de arquivo CSV inválido!', 'danger')
            return redirect(request.url)

    # Listar arquivos CSV existentes na pasta de upload
    uploaded_files = []
    try:
        uploaded_files = [f for f in os.listdir(UPLOAD_FOLDER_CSV) if allowed_file(f, ALLOWED_EXTENSIONS_CSV)]
    except Exception as e:
        flash(f"Erro ao listar arquivos CSV: {str(e)}", 'danger')

    return render_template('manage_lists.html', title="Gerenciar Listas", uploaded_files=uploaded_files)

# --- Outras rotas (criar campanha, status, etc.) virão aqui ---

if __name__ == '__main__':
    # Inicializar tabelas do BD
    database_manager.create_tables()
    # Flask-SocketIO será integrado aqui depois
    app.run(debug=True, host='0.0.0.0', port=5001) # Usando porta 5001 para não conflitar com wppconnect-server se local