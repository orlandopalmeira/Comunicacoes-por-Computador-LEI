import socket

from time import sleep
from signal import signal, alarm, SIGALRM, SIG_IGN
import threading
from datetime import datetime

from primary_server_config import SPConfig
from secondary_server_config import SSConfig
from resolver_server_config import SRConfig
import database as DB
from query import Query


class ServerFeatures:
    """
    Esta classe implementa uma série de funcionalidades exclusivas dos servidores.
    """

    @staticmethod
    def atendimentoUDP(roles: dict, serv_ip_addr: str, port: int = 5300, debug_mode: bool = True):
        """
        Esta função implementa o atendimento UDP do servidor para receber queries.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind((serv_ip_addr,port))

        while True:
            msg, add = s.recvfrom(4096) # esta função é bloqueante
            threading.Thread(target=ServerFeatures.__processaUDP,args=(roles,msg,add,debug_mode)).start()

        s.close()
        
 
    @staticmethod
    def __processaUDP(roles: dict, msg: bytes, dest_ip, debug_mode: bool = True): # Atenção, o dest_ip é do tipo _RetAddress
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        query = Query.fromString(msg.decode('utf-8'))
        if query is not None: # a query foi descodificada correctamente
            answer = ServerFeatures.answer_query(roles,query)
            if answer is not None: # é possível responder à query
                (resp,conf) = answer
                ServerFeatures.add_event_log_file(conf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} QR {dest_ip[0]}:{dest_ip[1]} {query.stringQueryDebug()}',debug_mode)
                sock.sendto(str(resp).encode('utf-8'),dest_ip)
                ServerFeatures.add_event_log_file(conf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} QE {dest_ip[0]}:{dest_ip[1]} {resp.stringQueryDebug()}',debug_mode)

        else: # a query não foi descodificada correctamente
            sock.sendto(str(Query(0,0,3,0,0,0,'',0,None,None,None)).encode('utf-8'),dest_ip)
        sock.close()

    @staticmethod
    def answer_query(roles: dict, query: Query):
        """
        Esta função serve para responder a uma query.
        """
        
        type_of_value_from_int = ('SOASP','SOAADMIN','SOASERIAL','SOAREFRESH','SOARETRY','SOAEXPIRE',
                                   'NS','A','CNAME','MX','PTR')
        
        tup = ServerFeatures.available_to_answer(roles,query.name)
        if tup[0]: # É capaz de responder à querie
            conf,cache,database = tup[2],tup[3],tup[4]
            authoritative = isinstance(conf,(SPConfig,SSConfig)) # resposta autoritariva?
            recursive = query.flags in {2,3,6,7} # estamos em modo recursivo?

            if tup[1] == 0: # deve procurar na cache
                (resp_values,auth_values,ext_values) = cache.getQueryResponse(query.name,type_of_value_from_int[query.type_of_value])
                flags = (1 if authoritative else 0 ) + (2 if recursive else 0)
                res_code = 1 if cache.responseCode1(query.name,query.type_of_value) else (2 if cache.responseCode2(query.name) else 0)
                r = Query(query.message_id,flags,res_code,len(resp_values),len(auth_values),len(ext_values),
                          query.name,query.type_of_value,resp_values,auth_values,ext_values)
                return (r,conf)
            elif tup[1] == 1: # deve procurar na base de dados
                (resp_values,auth_values,ext_values) = database.getQueryResponse(query.name,type_of_value_from_int[query.type_of_value])
                flags = (1 if authoritative else 0 ) + (2 if recursive else 0)
                res_code = 1 if database.responseCode1(query.name,query.type_of_value) else (2 if database.responseCode2(query.name) else 0)
                r = Query(query.message_id,flags,res_code,len(resp_values),len(auth_values),len(ext_values),
                          query.name,query.type_of_value,resp_values,auth_values,ext_values)
                return (r,conf)
        return None

    @staticmethod
    def available_to_answer(roles: dict, domain: str) -> tuple:
        """
        Esta função avalia se um servidor consegue fornecer informações sobre um certo domínio.\n
        """
        try:
            for tup in roles.values():
                conf,cache,db = tup
                if isinstance(conf,(SPConfig,SSConfig)): # Servidores primários e secundários
                    if conf.limitation is None: # Não é limitado pelo DD
                        if cache.existsDomain(domain):
                            return (True,0,conf,cache,db)
                        elif db.existsDomain(domain):
                            return (True,1,conf,cache,db)

                    else: # É limitado pelo DD
                        if domain in conf.limitation:
                            if cache.existsDomain(domain):
                                return (True,0,conf,cache,db)
                            elif db.existsDomain(domain):
                                return (True,1,conf,cache,db)

                elif isinstance(conf,SRConfig): # Servidores de resoluçãoç
                    if cache.existsDomain(domain):
                        return (True,0,conf,cache,db)
            return (False, None)
        except:
            return (False, None)


    @staticmethod
    def atendimentoTCP(spconf: SPConfig, database: DB.DataBase, ip_addr: str, port: int = 5200, debug_mode: bool = True):
        """
        Esta função implementa atendimento TCP do servidor primário para receber pedidos de transferência de zona.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip_addr, port))
        s.listen()
        while True:
            connection, addr = s.accept()
            threading.Thread(target=ServerFeatures.__processaTCP,args=(connection,str(addr[0]),spconf,database,debug_mode)).start()

        s.close()
    
    @staticmethod
    def __processaTCP(connection: socket.socket, ip_dest:str, spconf: SPConfig, database: DB.DataBase, debug_mode: bool = True):
        data = connection.recv(1024).decode('utf-8')
        if data == 'SOASERIAL':
            ServerFeatures.send_zone_transfer(connection,ip_dest,spconf,database,debug_mode)
        connection.close()

    @staticmethod
    def __timeouthandler(signum,frame):
        raise TimeoutError('Timeout over')

    @staticmethod
    def __ask_zone_transfer_aux(socket: socket.socket, lines: list, n_entries: int) -> bool:
        """
        Implementa a receção das entradas e retorna True se essa receção foi bem sucedida. Se não, retorna False.
        """
        try:
            i = 1 # indica o índice da entrada a receber (serve para verificar se a última entrada recebida é correcta)
            count = 0 # conta o nº de entradas recebidas
            s = socket # apenas para não estar sempre a escrever 'socket'
            data = [''] # armazena a mensagem recebida pelo SP
            while data and data[0] != 'ZTDONE': # Enquanto o SP não enviar 'ZTDONE' 
                data = s.recv(2048).decode('utf-8').split(',') # recebe a entrada do SP
                if not data or data[0] == 'ZTDONE': # 'ZTDONE' -> fim da transf de zona
                    continue
                index,entry = int(data[0]),data[1] # faz parsing do que o SP enviou
                s.sendall(str(index).encode('utf-8')) # envia ao SP o índice da linha recebida

                if index != i: # o SP enviou uma linha com índice incorrecto
                    lines.clear() # apaga tudo o que recebeu até agora dado que deve ser considerado como inválido
                    return False # transf de zona mal sucedida
                
                lines.append(entry) # adiciona a entrada na lista
                count += 1 # declara que recebeu mais uma entrada
                i += 1 # incrementa o índice esperado
            
            s.close()
            if count == n_entries: # O número de entradas é igual ao esperado (correu tudo bem)
                return True # transf de zona bem sucedida
            else: # O número de entradas é diferente do esperado (algo correu mal)
                lines.clear() # apaga tudo o que recebeu uma vez que deve ser considerado como inválido
                return False # transferência de zona mal sucedida
        except:
            socket.close()
            lines.clear()
            return False # transferência de zona mal sucedida

    @staticmethod
    def ask_zone_transfer(domain: str, ssconf: SSConfig, src_ip: str, ss_db_version: int, ip_dest: str, dest_port: int = 5200, time_one_try: int = 5, soaretry: int = 5, max_attempts: int = 4, debug_mode: bool = True):
        """
        Esta função implementa o pedido da transferência de zona.\n
        O argumento 'time' é o tempo limite que o SS tem para ir verificando as linhas recebidas. Se o tempo se esgotar, ele desiste da transferencia de zona.\n
        O argumento 'soaretry' é o tempo que o SS espera para voltar a tentar fazer a transferência de zona.
        O argumento 'max_attempts' indica o número máximo de tentativas que o SS pode usar para fazer a transferência de zona.
        """
        lines = [] # armazena as linhas recebidas
        n_entries = 0 # número de entradas da base de dados (informação dada pelo SP)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # cria um socket apenas para a transf de zona
        sucessfull = False
        attempts = 0
        nozt = False
        denied = False
        try:
            while not denied and not sucessfull and attempts <= max_attempts and not nozt:
                s.connect((ip_dest,dest_port)) # o SS conecta-se ao SP
                s.sendall('SOASERIAL'.encode('utf-8')) # O SS envia a mensagem a pedir a versao da BD
                data = s.recv(1024) # recv é bloqueante, o SS recebe a versão da base de dados do SP
                version = int(data.decode('utf-8'))
                if version > ss_db_version: # O SS só continua se a sua versão da base de dados for mais antiga que a do SP 
                    s.sendall(str(domain).encode('utf-8')) # O SS envia o seu ip e domínio ao SP
                    data = s.recv(1024).decode('utf-8') # recv é bloqueante, se o SP aceitar este SS então envia o nº de entradas da base de dados. Se não aceitar, envia 'DENIED'.
                    if data != 'DENIED': # O SP aceitou o pedido deste SS
                        n_entries = int(data) # O SP enviou o número de entradas da sua base de dados.
                        s.sendall(str(n_entries).encode('utf-8')) # O SS aceita o número de entradas e envia essa resposta ao servidor
                        try:
                            attempts += 1
                            sucessfull = ServerFeatures.__ask_zone_transfer_aux(s,lines,n_entries)
                            alarm(0) # cancela o alarme
                        except TimeoutError:
                            pass
                        if not sucessfull: # a transf de zona não foi bem sucedida, faz uma pausa
                            sleep(soaretry)
                    else:
                        s.close()
                        denied = True
                else:
                    s.sendall('NOZT'.encode('utf-8')) # diz ao SP que não precisa da transferência de zona (NOZT)
                    nozt = True
        except:
            s.close()
        if sucessfull:
            ServerFeatures.add_event_log_file(ssconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} ZT {ip_dest} SS',debug_mode)
        elif not nozt:
            ServerFeatures.add_event_log_file(ssconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {ip_dest} SS',debug_mode)
        s.close()
        return (nozt,lines)

    @staticmethod
    def send_zone_transfer(connection: socket.socket, ip_dest:str , spconf: SPConfig, database: DB.DataBase,debug_mode: bool):
        """
        Esta função implementa o envio da transferência de zona.\n
        (Parece estar a funcionar)
        """
        # Esta função parte do princípio que a mensagem 'SOASERIAL' do SP já foi processada
        try:
            connection.sendall(str(database.soaserial[0]).encode('utf-8')) # envia a sua versão da base de dados ao SS
            data = connection.recv(1024).decode('utf-8') # descodifica a resposta do SS
            if data != 'NOZT': # o SS quer mesmo fazer a transferencia de zona
                domain,ip_ss = data,ip_dest
                if (spconf.domain == domain) and (database.domain == domain) and (ip_ss in spconf.ss_servers): # O SP valida o domínio e o ip informados
                    n_entries = len(database.entradas) # calcula o nº de entradas da sua base de dados
                    connection.sendall(str(n_entries).encode('utf-8')) # envia o numero de entradas da base de dados ao SS
                    entries_from_ss = int(connection.recv(1024).decode('utf-8')) # se o SS aceitar o numero de entradas, este SP recebe esse numero de entradas de volta do SS
                    if entries_from_ss == n_entries: # o SS aceitou receber o número de entradas comunicado
                        i = 1 # indice que indica o número da entrada que estamos a enviar
                        for entry in database.entradas:
                            connection.sendall(f'{i},{entry}'.encode('utf-8')) # envia ao SS a entrada com o número de ordem
                            i_ss = int(connection.recv(1024).decode('utf-8')) # o SS responde com o índice que recebeu
                            if i_ss != i: # o SS não recebeu a entrada que devia
                                break
                            i += 1
                        connection.sendall('ZTDONE'.encode('utf-8')) # Envia ao SS uma mensagem a informar o fim da transferência de zona
                        connection.close()

                        if i-1 == n_entries: # correu tudo bem
                            ServerFeatures.add_event_log_file(spconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} ZT {ip_dest} SP',debug_mode)
                            return
                        else:
                            ServerFeatures.add_event_log_file(spconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {ip_dest} SP',debug_mode)
                            return

                else:
                    connection.sendall('DENIED'.encode('utf-8')) # Informa o SS que recusou o seu pedido de transferencia de zona
                    connection.close()
                    ServerFeatures.add_event_log_file(spconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {ip_dest} SP (Zone Transfer was denied)',debug_mode)
        except:
            connection.close()
            ServerFeatures.add_event_log_file(spconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {ip_dest} SP',debug_mode)
          
    @staticmethod
    def add_event_log_file(log_file_path: str, event: str, debug_mode: bool = True) -> None:
        """
        Regista um evento num ficheiro de log fornecido. Também imprime no stdout se o componente estiver em modo debug.
        """
        file = open(log_file_path,"a")
        file.write(event if event[-1:] == '\n' else event + '\n')
        file.close()
        if debug_mode:
            print(event)
