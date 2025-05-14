# No seu session_manager.py ou main_console.py
import requests
import time
import os
import base64
from config import WPPCONNECT_SERVER_URL, WPPCONNECT_SESSION_NAME
# Certifique-se que auth_manager.py está no mesmo diretório ou no PYTHONPATH
import auth_manager # Usaremos para obter o token JWT

# Tente instalar: pip install qrcode[pil]
try:
    import qrcode
    # from PIL import Image # Importado por qrcode[pil]
    # import io
    QRCODE_LIB_AVAILABLE = True
except ImportError:
    QRCODE_LIB_AVAILABLE = False
    print("********************************************************************************************")
    print("AVISO: Biblioteca 'qrcode' com dependência 'Pillow' não encontrada.")
    print("Para exibir QR Code no console ou salvar como imagem, instale com: pip install qrcode[pil]")
    print("Sem ela, apenas os dados brutos do QR Code (urlcode ou base64) serão mostrados.")
    print("********************************************************************************************")

def start_and_get_qr_code():
    """
    Tenta iniciar a sessão e obter/exibir o QR code,
    utilizando principalmente a resposta do /status-session.
    Retorna True se conectado, False se QR foi mostrado/salvo ou se ocorreu um erro.
    """
    # Etapa 0: Obter token JWT
    # É crucial que generate_jwt_token() no auth_manager use a SECRET_KEY correta.
    print("Obtendo token JWT...")
    jwt_token = auth_manager.get_current_jwt_token()
    if not jwt_token:
        if not auth_manager.generate_jwt_token():
            print("ERRO CRÍTICO: Falha ao gerar token JWT inicial. Verifique sua SECRET_KEY e a conexão com o servidor.")
            return False
        jwt_token = auth_manager.get_current_jwt_token()
        if not jwt_token:
            print("ERRO CRÍTICO: Token JWT indisponível mesmo após tentar gerar.")
            return False
    print("Token JWT obtido.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}"
    }

    # Etapa 1: Tentar "acordar" ou iniciar a sessão.
    # O endpoint /start-session pode preparar o servidor para gerar um novo QR se necessário.
    start_url = f"{WPPCONNECT_SERVER_URL}/api/{WPPCONNECT_SESSION_NAME}/start-session"
    try:
        print(f"Enviando comando para iniciar/verificar sessão '{WPPCONNECT_SESSION_NAME}' em {start_url}...")
        # O corpo {"waitQrCode": True} é da documentação Swagger para /start-session
        start_response = requests.post(start_url, headers=headers, json={"waitQrCode": True}, timeout=20)
        if 200 <= start_response.status_code < 300:
            print(f"Comando start-session processado. Resposta: {start_response.json()}")
        else:
            print(f"Aviso: Resposta do start-session (Status: {start_response.status_code}): {start_response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Aviso: Erro ao tentar o comando start-session (a sessão pode já estar em um estado que não requer start): {e}")
    except ValueError: # JSONDecodeError
        print(f"Aviso: Resposta do start-session não foi JSON válido: {start_response.text if 'start_response' in locals() else 'N/A'}")


    # Etapa 2: Verificar o status da sessão e obter QR code da resposta do /status-session
    status_url = f"{WPPCONNECT_SERVER_URL}/api/{WPPCONNECT_SESSION_NAME}/status-session"
    print(f"Verificando status e solicitando QR Code de: {status_url}")
    try:
        status_response = requests.get(status_url, headers=headers, timeout=15)
        status_response.raise_for_status()
        
        session_data = status_response.json()
        print(f"Resposta completa do /status-session: {session_data}") # Log completo da resposta

        current_status = session_data.get('status')
        print(f"Status atual da sessão: {current_status}")

        if current_status == 'CONNECTED':
            print("Sucesso! Sessão já está conectada.")
            return True

        # Tentar obter dados do QR Code da resposta do status
        qr_data_for_ascii = session_data.get('urlcode')
        qr_base64_image = session_data.get('qrcode') # Formato: "data:image/png;base64,iVBOR..."

        if QRCODE_LIB_AVAILABLE and qr_data_for_ascii:
            print("\n--- ESCANEIE O QR CODE ABAIXO COM SEU WHATSAPP ---")
            try:
                qr_gen = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
                qr_gen.add_data(qr_data_for_ascii)
                qr_gen.make(fit=True)
                qr_gen.print_tty() # Imprime no console
                print("--------------------------------------------------")
                print("Após escanear, aguarde alguns instantes e verifique o status novamente.")
                return False # Indica que o QR foi mostrado, aguardando escaneamento
            except Exception as e_qr_ascii:
                print(f"Erro ao tentar exibir QR Code como ASCII: {e_qr_ascii}")
                # Fallback para base64 se ASCII falhar e base64 existir
                if not (QRCODE_LIB_AVAILABLE and qr_base64_image): # Evitar recursão ou processamento duplo
                    print(f"Dados urlcode: {qr_data_for_ascii}")

        if QRCODE_LIB_AVAILABLE and qr_base64_image: # Pode ser o fallback ou a primeira opção se urlcode não existir
            print("Tentando processar QR Code a partir da imagem base64...")
            try:
                if "base64," in qr_base64_image: # Remove o prefixo "data:image/png;base64,"
                    qr_base64_image_data = qr_base64_image.split(',', 1)[1]
                else:
                    qr_base64_image_data = qr_base64_image
                
                img_data = base64.b64decode(qr_base64_image_data)
                img_filename = "qrcode_to_scan.png"
                with open(img_filename, "wb") as f:
                    f.write(img_data)
                print(f"\nQR Code salvo como '{img_filename}'.")
                print("Por favor, abra o arquivo de imagem e escaneie com seu WhatsApp.")
                print("Após escanear, aguarde alguns instantes e verifique o status novamente.")
                # Tentar abrir a imagem (opcional, depende do SO)
                # try:
                #     if os.name == 'nt': os.startfile(img_filename)
                #     elif os.name == 'posix': subprocess.call(('xdg-open', img_filename))
                # except Exception as e_open:
                #     print(f"(Não foi possível abrir a imagem automaticamente: {e_open})")
                return False # Indica que o QR foi salvo, aguardando escaneamento
            except Exception as e_img:
                print(f"Erro ao salvar imagem do QR Code a partir de base64: {e_img}")
                print(f"String base64 (início): {qr_base64_image[:100]}...") # Log para debug
        
        # Se não conseguiu exibir/salvar QR code mas ele deveria estar disponível
        if not (qr_data_for_ascii or qr_base64_image):
            print(f"Status da sessão: {current_status}, mas dados do QR Code (urlcode ou qrcode) não foram encontrados na resposta.")
        elif not QRCODE_LIB_AVAILABLE:
             print("Os dados do QR Code foram recebidos, mas a biblioteca 'qrcode[pil]' não está instalada para exibi-los ou salvá-los como imagem.")
             print(f"urlcode (para gerar QR): {qr_data_for_ascii}")
             print(f"qrcode (base64, início): {qr_base64_image[:100] if qr_base64_image else 'N/A'}...")

        print("Verifique os logs do wppconnect-server se a conexão não ocorrer.")
        return False # QR não foi conectado

    except requests.exceptions.RequestException as e:
        print(f"Erro de requisição ao obter status/QR Code: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"Resposta da API (status-session): {e.response.status_code} - {e.response.json()}")
            except ValueError:
                print(f"Resposta da API (status-session): {e.response.status_code} - {e.response.text}")
        return False
    except ValueError: # JSONDecodeError
         print(f"Erro: A resposta do /status-session não foi um JSON válido. Resposta: {status_response.text if 'status_response' in locals() else 'N/A'}")
         return False
    except Exception as e_gen:
        print(f"Erro inesperado ao processar status/QR Code: {e_gen}")
        return False

# As funções check_session_status() e logout_session() que sugeri anteriormente
# podem ser mantidas como estão, pois também devem usar o token JWT nos headers.