# Exemplo em um auth_manager.py ou wpp_connector.py
import requests
from config import WPPCONNECT_SERVER_URL, WPPCONNECT_SESSION_NAME, WPPCONNECT_SECRET_KEY

current_jwt_token = None

def generate_jwt_token():
    global current_jwt_token
    url = f"{WPPCONNECT_SERVER_URL}/api/{WPPCONNECT_SESSION_NAME}/{WPPCONNECT_SECRET_KEY}/generate-token"
    try:
        response = requests.post(url, timeout=10)
        response.raise_for_status() # Levanta exceção para erros HTTP
        # Assumindo que o token está no corpo da resposta, ex: {"token": "seu_jwt"}
        # Ou pode estar em um header específico. Verifique a resposta real.
        token_data = response.json() # Ajuste isso conforme a resposta real
        if "token" in token_data:
             current_jwt_token = token_data["token"]
             print("Token JWT gerado com sucesso.")
             return True
        # Se a resposta for diretamente o token como string:
        # current_jwt_token = response.text 
        # print("Token JWT gerado com sucesso.")
        # return True
        else:
            print(f"Erro ao gerar token JWT: 'token' não encontrado na resposta - {token_data}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Falha ao gerar token JWT: {e}")
        return False
    except ValueError: # Erro ao decodificar JSON
        print(f"Falha ao decodificar JSON da resposta do token: {response.text}")
        return False


def get_current_jwt_token():
    # Poderia adicionar lógica para verificar se o token expirou e gerar um novo se necessário.
    # Por enquanto, apenas retorna o token atual ou tenta gerar um novo se não existir.
    if not current_jwt_token:
        generate_jwt_token()
    return current_jwt_token