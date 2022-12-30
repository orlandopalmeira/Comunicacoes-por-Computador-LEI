import os
from datetime import datetime

class SRConfig:
    """
    Classe para armazenar as informações/configurações de um dns resolver.
    """
    def __init__(self, ip_addr: str, port: int, file_all_log_path: str, st_list, st_reverse, direct_domains) -> None:
        self.ip_addr = ip_addr
        self.port = port
        self.file_all_log_path = file_all_log_path
        self.st_list = st_list # lista com os servidores de topo (formato (IP,PORTA))
        self.st_reverse = st_reverse # lista com os servidores de topo de DNS reverso(formato (IP,PORTA))
        self.direct_domains = direct_domains # domain -> server_ip

    @staticmethod
    def __read_st_list_file(file_path: str):
        """
        Lê o ficheiro com a lista dos ST e dos ST do reverso.
        """
        result1 = list()
        result2 = list()
        if os.path.exists(file_path):
            file = open(file_path,"r")
            lines = list(map(lambda l: l.replace('\n',''),file.readlines())) 
            lines = list(filter(lambda l: '#' not in l,lines))

            for line in lines:
                try:
                    aux = line.split(':')
                    if aux[0] == 'reverse':
                        result2.append((aux[1],int(aux[2])))
                    else:
                        if len(aux) == 2:
                            result1.append((aux[0],int(aux[1])))
                        else:
                            result1.append((aux[0],None))
                except:
                    file.close()
                    return f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 incorrect entry sp-config-file -> line:\'{line}\''

            file.close()
            return (result1,result2)
        else:
            return f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 st-list-file \'{file_path}\' does not exist'
    
    # TODO: Esta função ainda não está feita!!!!
    @staticmethod
    def fileToSRConfig(file_path: str, ipAddr = '', port = 5300):
        STlist = list() # lista com os servidores de topo
        STREVList = list() # lista com os servidores de topo do DNS reverso
        fileAllLog = '' # caminho para o ficheiro de log ALL
        direct_domains = None # lista com os domínios para os quais este servidor não contacta os ST
        if os.path.exists(file_path):
            file = open(file_path,"r") # ficheiro de configuração
            lines = list(filter(lambda l: ('#' not in l) and l != '\n',file.readlines())) # apaga as linhas de comentário e linhas vazias
            lines = list(map(lambda s: s.replace('\n',''),lines))
            for line in lines:
                line = line.split(' ')
                if '#' in line[0]: # linha de comentário ignorada
                    continue
                elif line[1] == 'DD':
                    if direct_domains is None:
                        direct_domains = dict()
                    direct_domains[line[0]] = line[2]
                elif line[1] == 'ST':
                    r = SRConfig.__read_st_list_file(line[2])
                    if not isinstance(r,tuple):
                        return (r,None)
                    else:
                        STlist,STREVList = r[0],r[1]
                elif line[1] == 'LG':
                    if line[0] == 'all':
                        fileAllLog = line[2].replace('\n','')
                        open(fileAllLog,"a").close()
                else:
                    return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 type-of-value \'{line[1]}\' is invalid for resolver servers config files',None)
            
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EV 127.0.0.1 conf-file-read \'{file_path}\'',
                    SRConfig(ipAddr,port,fileAllLog,STlist,STREVList,direct_domains))

        else:
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 conf-file \'{file_path}\' does not exist',None)
