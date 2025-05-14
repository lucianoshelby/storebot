# csv_processor.py
import csv
import re # Para limpeza de números de telefone

def clean_phone_number(phone_str):
    """Remove caracteres não numéricos de um número de telefone."""
    if not phone_str:
        return None
    return re.sub(r'\D', '', phone_str)

def load_contacts_from_csv(filepath):
    """
    Carrega contatos de um arquivo CSV com colunas 'telefone' e 'nome'.
    Tenta detectar automaticamente se o delimitador é ',' ou ';'.
    Retorna uma lista de dicionários.
    """
    contacts = []
    delimiters_to_try = [',', ';'] # Ordem de preferência para tentativa

    try:
        with open(filepath, mode='r', encoding='utf-8', newline='') as csvfile:
            # newline='' é importante para lidar corretamente com diferentes finais de linha
            
            reader = None
            used_delimiter = None

            for delimiter_char in delimiters_to_try:
                csvfile.seek(0) # Retorna ao início do arquivo para cada tentativa de delimitador
                try:
                    # Tenta criar um DictReader e verifica se as colunas esperadas estão presentes
                    # O DictReader usa a primeira linha como cabeçalho por padrão.
                    temp_reader_check = csv.DictReader(csvfile, delimiter=delimiter_char)
                    
                    # Verifica se as colunas obrigatórias existem nos fieldnames
                    if 'telefone' in temp_reader_check.fieldnames and 'nome' in temp_reader_check.fieldnames:
                        # Delimitador correto encontrado, configurar o reader final
                        csvfile.seek(0) # Retorna ao início para o reader definitivo
                        reader = csv.DictReader(csvfile, delimiter=delimiter_char)
                        used_delimiter = delimiter_char
                        print(f"Info: Lendo CSV '{filepath}' com delimitador: '{used_delimiter}'")
                        break # Sai do loop de tentativas de delimitador
                except Exception:
                    # Se houver erro ao tentar com este delimitador (ex: formato inconsistente para ele),
                    # simplesmente continua para o próximo delimitador na lista.
                    continue 
            
            if not reader:
                print(f"Erro: As colunas 'telefone' e 'nome' não foram encontradas no arquivo CSV '{filepath}' utilizando os delimitadores {delimiters_to_try}.")
                print("Verifique se o arquivo CSV usa um desses delimitadores e se os nomes das colunas estão corretos no cabeçalho.")
                return []

            for i, row in enumerate(reader):
                line_number = i + 1 + 1 # +1 para index 0, +1 para pular cabeçalho
                
                # É uma boa prática verificar se as chaves existem na linha,
                # pois arquivos CSV podem ter linhas inconsistentes.
                phone_val = row.get('telefone')
                name_val = row.get('nome')

                if phone_val is None or name_val is None:
                    print(f"Aviso: Linha {line_number} no CSV (conteúdo: {row}) não contém as chaves 'telefone' ou 'nome' esperadas. Ignorando.")
                    continue

                phone = clean_phone_number(phone_val)
                name = name_val.strip() # Remove espaços extras do nome

                if phone: # Telefone é obrigatório
                    contacts.append({'telefone': phone, 'nome': name if name else ''})
                    if not name:
                         print(f"Aviso: Contato na linha {line_number} (telefone: {phone}) não possui nome.")
                else:
                    print(f"Aviso: Linha {line_number} (conteúdo: {row}) ignorada por falta de número de telefone válido após limpeza.")
            
            if not contacts:
                print(f"Aviso: Nenhum contato válido foi carregado do arquivo '{filepath}' após o processamento.")
            return contacts

    except FileNotFoundError:
        print(f"Erro: Arquivo CSV não encontrado em '{filepath}'.")
        return []
    except Exception as e:
        print(f"Erro inesperado ao processar o arquivo CSV '{filepath}': {e}")
        return []

if __name__ == '__main__':
    # Para testar, crie os seguintes arquivos na pasta 'contacts/':

    # 1. contacts/lista_teste_virgula.csv
    # Conteúdo:
    # telefone,nome
    # 11999999991,Teste Virgula Um
    # 11988888882,Teste Virgula Dois

    # 2. contacts/lista_teste_ponto_virgula.csv
    # Conteúdo:
    # telefone;nome
    # 22777777771;Teste Ponto Virgula Um
    # 22666666662;Teste Ponto Virgula Dois

    # Você pode criar esses arquivos manualmente ou descomentar o código abaixo para criá-los.
    '''
    import os
    if not os.path.exists('contacts'):
        os.makedirs('contacts')

    with open('contacts/lista_teste_virgula.csv', 'w', newline='', encoding='utf-8') as f_v:
        writer_v = csv.writer(f_v, delimiter=',')
        writer_v.writerow(['telefone', 'nome'])
        writer_v.writerow(['11999999991', 'Teste Virgula Um'])
        writer_v.writerow(['11988888882', 'Teste Virgula Dois'])

    with open('contacts/lista_teste_ponto_virgula.csv', 'w', newline='', encoding='utf-8') as f_pv:
        writer_pv = csv.writer(f_pv, delimiter=';')
        writer_pv.writerow(['telefone', 'nome'])
        writer_pv.writerow(['22777777771', 'Teste Ponto Virgula Um'])
        writer_pv.writerow(['22666666662', 'Teste Ponto Virgula Dois'])
    print("Arquivos de teste CSV criados em 'contacts/'.")
    '''

    print("\n--- Testando com arquivo delimitado por vírgula ---")
    test_csv_path_virgula = 'contacts/lista_teste_virgula.csv' 
    loaded_contacts_v = load_contacts_from_csv(test_csv_path_virgula)
    if loaded_contacts_v:
        print(f"Contatos Carregados de '{test_csv_path_virgula}':")
        for contact in loaded_contacts_v:
            print(contact)
    else:
        print(f"Nenhum contato carregado de '{test_csv_path_virgula}'. Verifique se o arquivo existe e os logs.")

    print("\n--- Testando com arquivo delimitado por ponto e vírgula ---")
    test_csv_path_ponto_virgula = 'C:\\Users\\Gestão MX\\Documents\\StoreBot\\contacts\\lista_teste.csv'
    loaded_contacts_pv = load_contacts_from_csv(test_csv_path_ponto_virgula)
    if loaded_contacts_pv:
        print(f"Contatos Carregados de '{test_csv_path_ponto_virgula}':")
        for contact in loaded_contacts_pv:
            print(contact)
    else:
        print(f"Nenhum contato carregado de '{test_csv_path_ponto_virgula}'. Verifique se o arquivo existe e os logs.")