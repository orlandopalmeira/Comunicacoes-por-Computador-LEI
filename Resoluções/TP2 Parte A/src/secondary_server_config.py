import os
from datetime import datetime

class SSConfig:
    """
    Classe para armazenar as informações/configurações de um servidor secundário.
    """
    def __init__(self, ip_addr: str, port: int, domain: str, sp_server: str, 
                 file_log_path: str, file_all_log_path: str, st_list: set,
                 limitation) -> None:
        self.ip_addr = ip_addr # endereço_ip deste servidor
        self.port = port # porta de atendimento
        self.domain = domain # domínio a que pertence
        self.sp_server = sp_server # servidor primário
        self.file_log_path = file_log_path # ficheiro de log
        self.file_all_log_path = file_all_log_path # ficheiro de log all
        self.st_list = st_list # lista com os servidores de topo (formato (IP,PORTA))
        self.limitation = limitation  # o limitation pode ser None (não é limitado pelas entradas DD) ou pode ser um set de domínios (é limitado pelas entradas DD)

    @staticmethod
    def __read_st_list_file(file_path: str):
        """
        Lê o ficheiro com a lista dos ST.
        """
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
    def fileToSSConfig(file_path: str, ipAddr = '', port = 5353, domain = ''):
        """
        Função que transforma as informações de um ficheiro de configuração
        numa configuração de um servidor secundário.
        """
        if os.path.exists(file_path):
            file = open(file_path,"r") # ficheiro de configuração
            lines = list(filter(lambda l: ('#' not in l) and l != '\n',file.readlines())) # apaga as linhas de comentário e linhas vazias
            lines = list(map(lambda s: s.replace('\n',''),lines))
            spServer = '' # ip do servidor primário do domínio deste servidor secundário
            fileLog = '' # caminho para o ficheiro de log
            fileAllLog = '' # caminho para o ficheiro de log ALL
            STlist = set() # lista com os servidores de topo
            limitation = None # lista com os domínios para os quais este servidor pode responder
            for line in lines:
                line = line.split(' ')
                if '#' in line[0]: # linha de comentário ignorada
                    continue
                elif line[1] == 'SP': # servidor primário do domínio deste servidor secundário
                    spServer = line[2].replace('\n','')
                elif line[1] == 'LG': # ficheiros de LOG
                    if line[0] == 'all': # ficheiro de log ALL
                        fileAllLog = line[2].replace('\n','')
                        open(fileAllLog,"a").close()
                    else: # line[0] == dominio (ficheiro de log deste servidor secundário)
                        fileLog = line[2].replace('\n','')
                        open(fileLog,"a").close()
                elif line[1] == 'ST':
                    STlist = SSConfig.__read_st_list_file(line[2])
                    if not isinstance(STlist,set):
                        return (STlist,None)
                elif line[1] == 'DD':
                    if limitation is None:
                        limitation = set()
                    limitation.add(line[0])
                else:
                    return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 type-of-value \'{line[1]}\' is invalid for secondary servers config files',None)
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EV 127.0.0.1 conf-file-read \'{file_path}\'',
                    SSConfig(ipAddr,port,domain,spServer,fileLog,fileAllLog,STlist,limitation))
        else:
            return  (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} SP 127.0.0.1 conf-file \'{file_path}\' does not exist',None)

        