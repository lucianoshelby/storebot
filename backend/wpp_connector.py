# wpp_connector.py
import requests
import json
import base64
import os
import mimetypes # ### NOVA LINHA ### Importar mimetypes
import sys
sys.path.insert(0, 'C:\\Users\\Gestão MX\\Documents\\StoreBot') # Ajuste o caminho conforme necessário

from backend.config import (
    WPPCONNECT_SERVER_URL,
    WPPCONNECT_API_ENDPOINT_SEND_IMAGE,
    WPPCONNECT_API_ENDPOINT_SEND_TEXT,
    # WPPCONNECT_SESSION_NAME # Removido se não usado diretamente aqui, já está em config
)

from backend.auth_manager import generate_jwt_token, get_current_jwt_token # Ajuste conforme necessário
#import backend.auth_manager # auth_manager em vez de from auth_manager import ... para clareza

# ... (função send_whatsapp_message permanece a mesma) ...

def send_whatsapp_message(phone_number, message):
    """
    Envia uma mensagem de texto simples para um número do WhatsApp.
    """
    if not phone_number or not message:
        print("Erro (Texto): Número de telefone e mensagem são obrigatórios.")
        return False, {"error": "Número de telefone e mensagem são obrigatórios."}

    jwt_token = get_current_jwt_token()
    if not jwt_token:
        print("Erro (Texto): Falha ao obter token JWT. Tentando gerar um novo...")
        if not generate_jwt_token():
            print("Erro Crítico (Texto): Falha ao obter/gerar token JWT para autenticação.")
            return False, {"error": "Falha ao obter/gerar token JWT para autenticação."}
        jwt_token = get_current_jwt_token()
        if not jwt_token:
            print("Erro Crítico (Texto): Token JWT ainda indisponível após tentativa de geração.")
            return False, {"error": "Token JWT ainda indisponível após tentativa de geração."}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}"
    }

    payload = {
        "phone": phone_number,
        "message": message,
        "isGroup": False, # Assumindo que não é para grupos por padrão
        # "isNewsletter": False, # Opcional, pode remover se não usar
        # "isLid": False, # Opcional, pode remover se não usar
    }

    # WPPCONNECT_API_ENDPOINT_SEND_TEXT deve estar definido em config.py
    # Ex: WPPCONNECT_API_ENDPOINT_SEND_TEXT = f"/api/{WPPCONNECT_SESSION_NAME}/send-message"
    full_api_url = f"{WPPCONNECT_SERVER_URL}{WPPCONNECT_API_ENDPOINT_SEND_TEXT}"

    print(f"Debug (Texto): Enviando para {full_api_url} com payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(full_api_url, headers=headers, json=payload, timeout=30) # Timeout de 30s

        if 200 <= response.status_code < 300:
            print(f"Mensagem de texto enviada com sucesso para {phone_number}. Status: {response.status_code}")
            try:
                return True, response.json()
            except ValueError: # requests.exceptions.JSONDecodeError
                print(f"Sucesso no envio, mas resposta não era JSON: {response.text}")
                return True, {"status_code": response.status_code, "raw_response": response.text}
        else:
            print(f"Falha ao enviar mensagem de texto para {phone_number}. Status: {response.status_code}, Resposta: {response.text}")
            response_json_content = None
            try:
                response_json_content = response.json()
            except ValueError: # requests.exceptions.JSONDecodeError
                print("Debug (Texto): Resposta do servidor não era JSON válido.")
            return False, {"status_code": response.status_code, "error": response.text, "response_json": response_json_content}

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao enviar mensagem de texto para {phone_number}: {e}")
        return False, {"error": str(e)}
    except Exception as e:
        print(f"Erro inesperado em send_whatsapp_message: {e}")
        return False, {"error": str(e)}

def send_whatsapp_image_message(phone_number, image_path, caption=""):
    if not phone_number or not image_path:
        return False, {"error": "Número de telefone e caminho da imagem são obrigatórios."}

    print(f"Debug (Imagem): Tentando acessar imagem em: {os.path.abspath(image_path)}")
    if not os.path.exists(image_path):
        print(f"Debug (Imagem): ERRO - Arquivo de imagem NÃO ENCONTRADO em: {os.path.abspath(image_path)}")
        return False, {"error": f"Arquivo de imagem não encontrado em: {image_path}"}
    if os.path.getsize(image_path) == 0:
        print(f"Debug (Imagem): ERRO - Arquivo de imagem está VAZIO: {os.path.abspath(image_path)}")
        return False, {"error": f"Arquivo de imagem está vazio: {image_path}"}

    jwt_token = get_current_jwt_token()
    if not jwt_token:
        print("Debug (Imagem): Falha ao obter token JWT. Tentando gerar um novo...")
        if not generate_jwt_token():
             return False, {"error": "Falha ao obter/gerar token JWT para autenticação."}
        jwt_token = get_current_jwt_token()
        if not jwt_token:
            return False, {"error": "Token JWT ainda indisponível após tentativa de geração."}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {jwt_token}"
    }

    image_base64_pure = None
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            image_base64_pure = base64.b64encode(image_bytes).decode('utf-8')
    except Exception as e:
        print(f"Debug (Imagem): ERRO ao ler e converter imagem para base64 pura: {e}")
        return False, {"error": f"Erro ao processar imagem: {str(e)}"}

    if not image_base64_pure:
        print("Debug (Imagem): ERRO CRÍTICO - String base64 pura da imagem ficou vazia APÓS a conversão.")
        return False, {"error": "Falha interna: string base64 pura da imagem ficou vazia."}
    
    # ### ALTERAÇÃO: Determinar MIME type e adicionar prefixo Data URL ###
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        # Tenta inferir pelo nome do arquivo se o guess_type falhar
        extension = os.path.splitext(image_path)[1].lower()
        if extension == ".png":
            mime_type = "image/png"
        elif extension in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif extension == ".gif":
            mime_type = "image/gif"
        elif extension == ".webp":
            mime_type = "image/webp"
        else:
            print(f"Debug (Imagem): AVISO - Não foi possível determinar o tipo MIME para {image_path}. Usando 'image/jpeg' como padrão.")
            mime_type = "image/jpeg" # Um padrão comum, mas pode não ser o ideal.

    image_base64_with_prefix = f"data:{mime_type};base64,{image_base64_pure}"
    # ### FIM DA ALTERAÇÃO ###

    print(f"Debug (Imagem): String base64 PURA (início): {image_base64_pure[:80]}...")
    print(f"Debug (Imagem): String base64 COM PREFIXO (início): {image_base64_with_prefix[:120]}...") # Log da string com prefixo


    filename = os.path.basename(image_path)

    payload = {
        "phone": phone_number,
        "base64": image_base64_with_prefix, # ### ALTERAÇÃO: Usar a string com prefixo ###
        "filename": filename,
        "caption": caption,
        "isGroup": False
    }

    payload_to_log = payload.copy()
    if len(payload_to_log.get("base64", "")) > 200:
        payload_to_log["base64"] = payload_to_log["base64"][:80] + f"... (total {len(payload_to_log.get('base64',''))} chars)"
    print(f"Debug (Imagem): Payload JSON a ser enviado (base64 com prefixo, truncada para log):\n{json.dumps(payload_to_log, indent=2)}")

    # A URL da API é construída usando WPPCONNECT_API_ENDPOINT_SEND_IMAGE do config.py
    # Ex: full_api_url = f"{config.WPPCONNECT_SERVER_URL}{config.WPPCONNECT_API_ENDPOINT_SEND_IMAGE}"
    # Certifique-se que WPPCONNECT_API_ENDPOINT_SEND_IMAGE em config.py é:
    # f"/api/{WPPCONNECT_SESSION_NAME}/send-image"
    
    # Corrigindo a obtenção da URL da API (assumindo que está em config.py)
    full_api_url = f"{WPPCONNECT_SERVER_URL}{WPPCONNECT_API_ENDPOINT_SEND_IMAGE}"


    try:
        response = requests.post(full_api_url, headers=headers, json=payload, timeout=60)

        if 200 <= response.status_code < 300:
            print(f"Imagem enviada com sucesso para {phone_number}. Status: {response.status_code}")
            return True, response.json()
        else:
            print(f"Falha ao enviar imagem para {phone_number}. Status: {response.status_code}, Resposta: {response.text}")
            response_json_content = None
            try:
                response_json_content = response.json()
            except ValueError: # requests.exceptions.JSONDecodeError em versões mais novas de requests
                print("Debug (Imagem): Resposta do servidor não era JSON válido.")
            return False, {"status_code": response.status_code, "error": response.text, "response_json": response_json_content}

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao enviar imagem para {phone_number}: {e}")
        return False, {"error": str(e)}
    except Exception as e:
        print(f"Erro inesperado em send_whatsapp_image_message: {e}")
        return False, {"error": str(e)}


if __name__ == '__main__':
    # --- BLOCO DE TESTE ---
    # Lembre-se:
    # 1. Seu wppconnect-server deve estar rodando.
    # 2. Sua WPPCONNECT_SECRET_KEY e WPPCONNECT_SESSION_NAME em config.py devem estar corretas.
    # 3. A sessão no wppconnect-server precisa estar conectada (QR Code escaneado).
    
    print("Iniciando teste do wpp_connector com autenticação JWT...")

    # Primeiro, tentar gerar/garantir que temos um token JWT
    # Opcional: Chamar generate_jwt_token() explicitamente aqui se quiser forçar uma nova geração para o teste.
    # if not generate_jwt_token():
    # print("Falha ao gerar token JWT para o teste inicial. Verifique a SECRET_KEY e a conexão com o servidor.")
    # exit()

    # Teste de envio de mensagem de texto
    """test_phone_text = "62993003740"  # Substitua pelo seu número
    test_message_text = "Olá! Este é um teste de MENSAGEM DE TEXTO do StoreBot com JWT. 🤖"

    if test_phone_text == "55SEUNUMERODETESTE_TEXTO":
        print("\n!!! ATENÇÃO TEXTO !!!")
        print("Edite wpp_connector.py e substitua '55SEUNUMERODETESTE_TEXTO' para testar o envio de texto.")
    else:
        print(f"\nTentando enviar mensagem de TEXTO para: {test_phone_text}")
        success_text, response_text = send_whatsapp_message(test_phone_text, test_message_text)
        if success_text:
            print(f"Teste de envio de TEXTO bem-sucedido! Resposta da API: {response_text}")
        else:
            print(f"Falha no teste de envio de TEXTO. Detalhes: {response_text}")"""

    #print("-" * 30)

    # Teste de envio de imagem
    test_phone_image = "62993003740"  # Substitua pelo seu número
    # Crie uma imagem de teste na raiz do projeto ou ajuste o caminho
    # Ex: crie uma pasta 'test_media' e coloque 'test_image.png' dentro.
    test_image_path = "C:\\Users\\Gestão MX\\Documents\\StoreBot\\backend\\imagem.jpg" # Adapte este caminho para uma imagem de teste real
    test_caption_image = "Olha que imagem legal! Teste do StoreBot com JWT e imagem. 🖼️"

    if test_phone_image == "55SEUNUMERODETESTE_IMAGEM":
        print("\n!!! ATENÇÃO IMAGEM !!!")
        print("Edite wpp_connector.py e substitua '55SEUNUMERODETESTE_IMAGEM' e configure 'test_image_path' para testar o envio de imagem.")
    elif not os.path.exists(test_image_path):
        print(f"\n!!! ATENÇÃO IMAGEM !!!")
        print(f"Arquivo de imagem para teste não encontrado em: {test_image_path}")
        print("Crie o arquivo ou ajuste o caminho 'test_image_path' no wpp_connector.py para testar o envio de imagem.")
    else:
        print(f"\nTentando enviar IMAGEM para: {test_phone_image}")
        success_image, response_image = send_whatsapp_image_message(test_phone_image, test_image_path, test_caption_image)
        if success_image:
            print(f"Teste de envio de IMAGEM bem-sucedido! Resposta da API: {response_image}")
        else:
            print(f"Falha no teste de envio de IMAGEM. Detalhes: {response_image}")