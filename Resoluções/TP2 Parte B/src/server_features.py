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
            answer = ServerFeatures.answer_query(roles,query,dest_ip,debug_mode)
            if answer is not None: # é possível responder à query
                (resp,conf) = answer
                sock.sendto(str(resp).encode('utf-8'),dest_ip)
                
        else: # a query não foi descodificada correctamente
            sock.sendto(str(Query(0,0,3,0,0,0,'',0,None,None,None)).encode('utf-8'),dest_ip)
        sock.close()

    @staticmethod
    def answer_query(roles: dict, query: Query, dest_ip, debug_mode: bool):
        """
        Esta função serve para responder a uma query.
        """
        
        type_of_value_from_int = ('SOASP','SOAADMIN','SOASERIAL','SOAREFRESH','SOARETRY','SOAEXPIRE',
                                  'NS','A','CNAME','MX','PTR')
        
        tup = ServerFeatures.available_to_answer2(roles,query.name)
        if tup[0]: # É capaz de responder à querie
            conf,cache,database = tup[2],tup[3],tup[4] 
            authoritative = isinstance(conf,(SPConfig,SSConfig)) # resposta autoritariva?
            recursive = query.flags in {2,3,6,7} # estamos em modo recursivo?

            if tup[1] == 0: # deve procurar na cache
                print("Supostamente tenho a informação na cache") # debug
                (resp_values,auth_values,ext_values) = cache.getQueryResponse(query.name,type_of_value_from_int[query.type_of_value])
                flags = (1 if authoritative else 0 ) + (2 if recursive else 0)
                #res_code = 1 if cache.responseCode1(query.name,query.type_of_value) else (2 if cache.responseCode2(query.name) else 0)
                res_code = 2 if cache.responseCode2(query.name) else (1 if not resp_values else 0)
                log = conf.file_all_log_path if isinstance(conf,SRConfig) else conf.file_log_path
                ServerFeatures.add_event_log_file(log,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} QR {dest_ip[0]}:{dest_ip[1]} {query.stringQueryDebug()}',debug_mode)
                r = Query(query.message_id,flags,res_code,len(resp_values),len(auth_values),len(ext_values),
                        query.name,query.type_of_value,resp_values,auth_values,ext_values)
                ServerFeatures.add_event_log_file(log,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} RP {dest_ip[0]}:{dest_ip[1]} {r.stringQueryDebug()}',debug_mode)
                return (r,conf)
            elif tup[1] == 1: # deve procurar na base de dados
                (resp_values,auth_values,ext_values) = database.getQueryResponse(query.name,type_of_value_from_int[query.type_of_value])
                flags = (1 if authoritative else 0 ) + (2 if recursive else 0)
                #res_code = 1 if database.responseCode1(query.name,query.type_of_value) else (2 if database.responseCode2(query.name) else 0)
                res_code = 2 if database.responseCode2(query.name) else (1 if not resp_values else 0)
                log = conf.file_all_log_path if isinstance(conf,SRConfig) else conf.file_log_path
                ServerFeatures.add_event_log_file(log,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} QR {dest_ip[0]}:{dest_ip[1]} {query.stringQueryDebug()}',debug_mode)
                r = Query(query.message_id,flags,res_code,len(resp_values),len(auth_values),len(ext_values),
                        query.name,query.type_of_value,resp_values,auth_values,ext_values)
                ServerFeatures.add_event_log_file(log,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} RP {dest_ip[0]}:{dest_ip[1]} {r.stringQueryDebug()}',debug_mode)
                return (r,conf)

        if "resolver" in roles: # se for um SR sem informação na cache, ele vai tentar falar com os outros servidores
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # socket para falar com servidores
            (conf,cach,_) = roles["resolver"]
            top_servers = conf.st_list
            resp = None
            ServerFeatures.add_event_log_file(conf.file_all_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} QR {dest_ip[0]}:{dest_ip[1]} {query.stringQueryDebug()}',debug_mode)
            if query.flags in {2,3,6,7}: # modo recursivo
                resp = ServerFeatures.__recursive(sock,cach,top_servers,query,conf,debug_mode)
                if resp is not None:
                    resp.flags = 2
            else: # modo iterativo
                resp = ServerFeatures.__iterative(sock,cach,top_servers,query,conf,debug_mode)
                if resp is not None:
                    resp.flags = 0
            if resp is not None:
                ServerFeatures.add_event_log_file(conf.file_all_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} RP {dest_ip[0]}:{dest_ip[1]} {resp.stringQueryDebug()}',debug_mode)
                sock.close()
                return (resp,conf)
            sock.close()
        return None

    @staticmethod
    def __iterative(s: socket.socket, cach, topservers: list, query: Query, conf: SRConfig, debug_mode: bool):
        # TODO: Comunicação iterativa
        name = query.name
        successful = False
        server = topservers[0]
        if query.name in conf.direct_domains:
            server = (conf.direct_domains[query.name],5300)
        elif query.type_of_value == 10: # query.type_of_value == PTR
            server = conf.st_reverse[0]
        result = None
        attempts = 0
        print("Vou perguntar aos outros")
        while not successful and attempts < 100:
            s.sendto(str(query).encode('utf-8'),server)
            print(f"Vou perguntar ao {server}") # debug
            ServerFeatures.add_event_log_file(conf.file_all_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} QE {server[0]}:{server[1]} {query.stringQueryDebug()}',debug_mode)
            #s.sendto(query.encode(),server)
            r = Query.fromString(s.recv(4096).decode('utf-8'))
            if r is not None:
                ServerFeatures.add_event_log_file(conf.file_all_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} RR {server[0]}:{server[1]} {r.stringQueryDebug()}',debug_mode)
            #r = Query.decode(s.recv(4096))
            if r is not None:
                cach.addEntriesFromQuery(r,2) # origin=2 significa origin = others
                if r.response_code == 0: # já tem a resposta
                    result = r
                    successful = True
                elif r.response_code == 1: # tem o domínio mas não tem a resposta completa (por exemplo, só tem o NS e não tem o MX)
                    auths = list(filter(lambda x: x.split(' ')[0] == name, r.authorities_values)) # domain NS server_name ttl prioridade
                    serv_name = auths[0].split(' ')[2]
                    servs_ips = list(filter(lambda x: x.split(' ')[0] == serv_name,r.extra_values)) # server_name A ip_server ttl prioridade
                    server = (servs_ips[0].split(' ')[2],5300)
                elif r.response_code == 2: #  o domínio não existe, mas pode haver informações úteis
                    auths = list(filter(lambda x: x.split(' ')[0] in name, r.authorities_values)) # domain NS server_name ttl prioridade
                    auths.sort(key=lambda x:len(x.split(' ')[0]), reverse=True)
                    serv_name = auths[0].split(' ')[2]
                    servs_ips = list(filter(lambda x: x.split(' ')[0] == serv_name,r.extra_values)) # server_name A ip_server ttl prioridade
                    server = (servs_ips[0].split(' ')[2],5300)
                else: break
            else:
                break
            attempts += 1

        return result

    @staticmethod
    def __recursive(s: socket.socket, cach, topservers: list, query: Query, conf, debug_mode: bool):
        # TODO: Comunicação recursiva se houver tempo
        return ServerFeatures.__iterative(s,cach,topservers,query,conf,debug_mode)
    
    @staticmethod
    def available_to_answer2(roles: dict, domain: str) -> tuple:
        try:
            for tup in roles.values():
                conf,cache,db = tup
                if isinstance(conf,(SPConfig,SSConfig)): # Servidores primários e secundários
                    if conf.limitation is None or (conf.limitation is not None and len(conf.limitation) > 0): # Não é limitado pelo DD
                        if cache.existsDomain2(domain):
                            return (True,0,conf,cache,db)
                        elif db.existsDomain2(domain):
                            return (True,1,conf,cache,db)

                    else: # É limitado pelo DD
                        if domain in conf.limitation:
                            if cache.existsDomain2(domain):
                                return (True,0,conf,cache,db)
                            elif db.existsDomain2(domain):
                                return (True,1,conf,cache,db)

                elif isinstance(conf,SRConfig): # Servidores de resolução
                    if cache.existsDomain2(domain):
                        return (True,0,conf,cache,db)
            return (False, None)
        except:
            return (False, None)

        

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

                elif isinstance(conf,SRConfig): # Servidores de resolução
                    if cache.existsDomain(domain):
                        return (True,0,conf,cache,db)
            return (False, None)
        except:
            return (False, None)


    @staticmethod
    def atendimentoTCP(spconf: SPConfig, roles: dict, ip_addr: str, port: int = 5200, debug_mode: bool = True):
        """
        Esta função implementa atendimento TCP do servidor primário para receber pedidos de transferência de zona.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip_addr, port))
        s.listen()
        while True:
            connection, addr = s.accept()
            threading.Thread(target=ServerFeatures.__processaTCP,args=(connection,str(addr[0]),spconf,roles,debug_mode)).start()
        s.close()
    
    @staticmethod
    def __processaTCP(connection: socket.socket, ip_dest:str, spconf: SPConfig, roles: dict,debug_mode: bool = True):
        domain = connection.recv(1024).decode('utf-8')
        if domain in roles: # domínio existe
            db = roles[domain][2]
            if ip_dest in spconf.ss_servers and db.domain == domain: # o servidor secundário e o domínio são válidos
                ServerFeatures.send_zone_transfer(connection,ip_dest,spconf,db,debug_mode)
            else:
                connection.sendall('DENIED'.encode('utf-8')) # Informa o SS que recusou o seu pedido de transferencia de zona
                connection.close()
                ServerFeatures.add_event_log_file(spconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {ip_dest} SP (Zone Transfer was denied)',debug_mode)
        else: 
            connection.sendall('DENIED'.encode('utf-8')) # Informa o SS que recusou o seu pedido de transferencia de zona
            connection.close()
            ServerFeatures.add_event_log_file(spconf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {ip_dest} SP (Zone Transfer was denied)',debug_mode)
        connection.close()

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
        sucessfull = False # transferencia de zona bem sucedida
        attempts = 0 # número de tentativas
        nozt = False # Tranferência de zona desnecessária
        denied = False # Transferência de zona negada pelo SP
        try:
            while not denied and not sucessfull and attempts <= max_attempts and not nozt:
                s.connect((ip_dest,dest_port)) # o SS conecta-se ao SP
                #s.sendall('SOASERIAL'.encode('utf-8')) # O SS envia a mensagem a pedir a versao da BD
                s.sendall(domain.encode('utf-8'))
                data = s.recv(1024) # recv é bloqueante, o SS recebe a versão da base de dados do SP
                if data == 'DENIED': # o SP recusou a transferência de zona
                    denied = True
                    continue
                version = int(data.decode('utf-8')) # aqui já temos a versão da BD 
                if version > ss_db_version: # O SS só continua se a sua versão da base de dados for mais antiga que a do SP 
                    #s.sendall(str(domain).encode('utf-8')) # O SS envia o seu ip e domínio ao SP
                    s.sendall('ok'.encode('utf-8'))
                    data = s.recv(1024).decode('utf-8') # recebe do SP o numero de entradas//recv é bloqueante, se o SP aceitar este SS então envia o nº de entradas da base de dados. Se não aceitar, envia 'DENIED'.
                    n_entries = int(data) # O SP enviou o número de entradas da sua base de dados.
                    s.sendall(str(n_entries).encode('utf-8')) # O SS aceita o número de entradas e envia essa resposta ao servidor
                    attempts += 1
                    sucessfull = ServerFeatures.__ask_zone_transfer_aux(s,lines,n_entries)
                    if not sucessfull: # a transf de zona não foi bem sucedida, faz uma pausa
                        sleep(soaretry) 
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
        Esta função implementa o envio da transferência de zona.
        """
        try:
            connection.sendall(str(database.soaserial[0]).encode('utf-8')) # envia a sua versão da base de dados ao SS
            data = connection.recv(1024).decode('utf-8') # descodifica a resposta do SS
            if data != 'NOZT': # o SS quer mesmo fazer a transferencia de zona
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
