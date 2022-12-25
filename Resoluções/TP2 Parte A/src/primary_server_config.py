import os
from datetime import datetime

class SPConfig:
    """
    Classe para armazenar as informações/configurações de um servidor primário.
    """
    def __init__(self,ip_addr: str, port: int, zone_transfer_port: int ,domain: str, ss_servers: list, 
                 file_db_path: str, file_log_path: str, file_all_log_path: str,
                 st_list: set, limitation) -> None:
        self.ip_addr = ip_addr # endereço ip do servidor 
        self.port = port # porta de atendimento de queries
        self.zone_transfer_port = zone_transfer_port # porta de atendimento para pedidos de transferência de zona
        self.domain = domain # domínio ao qual pertence
        self.ss_servers = ss_servers # servidores secundários do domínio a que pertence
        self.file_db_path = file_db_path # caminho para o ficheiro de base de dados
        self.file_log_path = file_log_path # caminho para o ficheiro de log do sp do dominio
        self.file_all_log_path = file_all_log_path # caminho para o ficheiro de log all
        self.st_list = st_list # lista com os servidores de topo (formato (IP,PORTA))
        self.limitation = limitation # o limitation pode ser None (não é limitado pelas entradas DD) ou pode ser um set de domínios (é limitado pelas entradas DD)
    
    @staticmethod
    def __read_st_list_file(file_path: str):
        result = set()
        if os.path.exists(file_path):
            file = open(file_path,"r")
            lines = list(map(lambda l: l.replace('\n',''),file.readlines()))
             
            for line in lines:
                try:
                    aux = line.split(':')
                    if len(aux) == 2:
                        result.add((line[0],int(line[1])))
                    else:
                        result.add((line[0],None))
                except:
                    file.close()
                    return f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 incorrect entry sp-config-file -> line:\'{line}\''

            file.close()
            return result
        else:
            return f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 st-list-file \'{file_path}\' does not exist'

    @staticmethod
    def fileToSPConfig(file_path: str, ipAddr = '', port = 5353, zone_transfer_port = 5352, domain = ''):
        """
        Função que transforma as informações de um ficheiro de configuração
        numa configuração de um servidor primário.
        """
        if os.path.exists(file_path): # o ficheiro de configuração existe?
            file = open(file_path,"r") # ficheiro de configuração
            lines = list(filter(lambda l: ('#' not in l) and l != '\n',file.readlines())) # apaga as linhas de comentário e linhas vazias
            lines = list(map(lambda s: s.replace('\n',''),lines))
            ssServers = [] # lista de IP's de servidores secundários
            fileDBPath = '' # caminho para o ficheiro de base de dados
            fileLog = '' # caminho para o ficheiro de log
            fileAllLog = '' # caminho para o ficheiro de log ALL
            STlist = set() # lista com os servidores de topo
            limitation = None # limitação segundo as entradas DD
            for line in lines:
                try:
                    line = line.split(' ')
                    if '#' in line[0]: # linha de comentário ignorada
                        continue
                    elif line[1] == 'DB': # ficheiro da base de dados
                        fileDBPath = line[2].replace('\n','')
                    elif line[1] == 'SS': # adiciona um endereço de um servidor secundário
                        ssServers.append(line[2].replace('\n',''))
                    elif line[1] == 'LG': # guarda o caminho para um dos ficheiros de log
                        if line[0] == 'all':
                            fileAllLog = line[2].replace('\n','')
                            open(fileAllLog,"a").close() # criaçao do ficheiro de log se não estiver criado
                        else:
                            fileLog = line[2].replace('\n','')
                            open(fileLog,"a").close() # criaçao do ficheiro de log se não estiver criado
                    elif line[1] == 'ST':
                        STlist = SPConfig.__read_st_list_file(line[2])
                        if not isinstance(STlist,set):
                            return (STlist,None)
                    elif line[1] == 'DD':
                        if limitation is None:
                            limitation = set()
                        limitation.add(line[0])
                    else: # tipos de valores não permitidos para ficheiros de configuração de servidores primários
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 type-of-value \'{line[1]}\' is invalid for primary servers config files',None)
                except:
                    return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 conf-file \'{file_path}\' incorrect entry -> line:\'{line}\'',None)

            file.close()
            
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EV 127.0.0.1 conf-file-read \'{file_path}\'',
                    SPConfig(ipAddr,port,zone_transfer_port,domain,ssServers,fileDBPath,fileLog,fileAllLog,STlist,limitation))
        else:
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 conf-file \'{file_path}\' does not exist',None)