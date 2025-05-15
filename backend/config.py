# config.py
WPPCONNECT_SERVER_URL = "http://localhost:21465"  # URL base do seu wppconnect-server
WPPCONNECT_SESSION_NAME = "Principal"         # Nome da sessão que você configurou no servidor
WPPCONNECT_SECRET_KEY = "zz91j6i" # Se o seu servidor usa uma chave de API/Token
WPPCONNECT_API_ENDPOINT_GENERATE_TOKEN = f"/api/{WPPCONNECT_SESSION_NAME}/{WPPCONNECT_SECRET_KEY}/generate-token" # Endpoint para gerar token
WPPCONNECT_API_ENDPOINT_SEND_TEXT = f"/api/{WPPCONNECT_SESSION_NAME}/send-message"
WPPCONNECT_API_ENDPOINT_SEND_IMAGE = f"/api/{WPPCONNECT_SESSION_NAME}/send-image" # Para enviar imagens
# Adicionaremos o endpoint para enviar arquivos/imagens depois
# WPPCONNECT_API_ENDPOINT_SEND_FILE = f"/api/{WPPCONNECT_SESSION_NAME}/send-file"
WPPCONNECT_API_ENDPOINT_SEND_TEXT = f"/api/{WPPCONNECT_SESSION_NAME}/send-message"
# Configurações do Banco de Dados
DATABASE_NAME = "storebot.db"

# Outras configurações
DEFAULT_MESSAGE_DELAY_SECONDS = 5 # Delay entre mensagens