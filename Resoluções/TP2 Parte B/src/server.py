import socket
import threading
from sys import argv
from ast import literal_eval
from datetime import datetime
from time import sleep

import server_features as SFT
import primary_server_config as SPC
import secondary_server_config as SSC
import resolver_server_config as SRC
import cache 
import database as DB
 
# argumentos: ip_deste_servidor + argumentos de servidor primário + argumentos de servidor secundário | 
# argumentos para servidor primário: -sp ('<nome_completo_domínio>','<path_ficheiro_config>') OS ARGUMENTOS DENTRO DESTE TUPLO TÊM DE ESTAR DENTRO DE PELICAS
# argumentos para servidor secundário: -ss ('<nome_completo_domínio>','<path_ficheiro_config>') OS ARGUMENTOS DENTRO DESTE TUPLO TÊM DE ESTAR DENTRO DE PELICAS
# argumentos para servidor de resolução: -sr ('<nome_completo_domínio>','<path_ficheiro_config>')
# para desativar o modo debug usar o argumento --no-debug

# arguments
args = argv[1:] # retira o primeiro argumento (é inútil)
len_args = len(args)

debug_mode = False if '--no-debug' in args else True

# oficios deste servidor (primario,secundario,resolucao)
roles = dict() # domínio -> tuple(objecto configuração,cache,base de dados (se for o caso, senão None))

#verificação de erros
correct_configs_and_databases = True # flag que indica se as configurações ou bases de dados foram feitas correctamente

# ip and ports
my_ip = args[0] # ip deste servidor

i = 0
while i < len_args: # este ciclo processa os argumentos fornecidos
    if args[i].lower() == '-sp':
        (dom,conf) = literal_eval(args[i+1])
        config = SPC.SPConfig.fileToSPConfig(conf,my_ip,5300,5200,dom) 
        if config[1] is not None: # Configuração correcta
            SFT.ServerFeatures.add_event_log_file(config[1].file_log_path,config[0],debug_mode)
            db = DB.DataBase.fileToDatabase(config[1].file_db_path,dom)
            SFT.ServerFeatures.add_event_log_file(config[1].file_log_path,db[0],debug_mode)
            if db[1] is not None: # Base de dados correcta
                roles[dom] = (config[1],cache.Cache(),db[1]) # configuração, cache, base de dados
                pass
            else:
                correct_configs_and_databases = False
                break
        else:
            correct_configs_and_databases = False
            break
        i += 1 
    elif args[i].lower() == '-ss':
        (dom,conf) = literal_eval(args[i+1])
        aux = (SSC.SSConfig.fileToSSConfig(conf,ipAddr=my_ip,domain=dom,port=5300),cache.Cache())
        if aux[0][1] is None: # Configuração incorrecta
            print(aux[0][0])
            correct_configs_and_databases = False
            break

        roles[dom] = (aux[0][1],aux[1],None) # configuração, cache, base de dados(ainda None porque não fez a transferência de zona)
        i += 1
    elif args[i].lower() == '-sr':
        (dom,conf) = literal_eval(args[i+1])
        aux = (SRC.SRConfig.fileToSRConfig(conf,my_ip,5300),cache.Cache())
        if aux[0][1] is None:
            print(aux[0][0])
            correct_configs_and_databases = False
            break
        #roles[dom] = (aux[0][1],aux[1],None) 
        roles["resolver"] = (aux[0][1],aux[1],None)
        i += 1
    else:
        pass
    i += 1

###############################################################################################################################

def watch_caches():
    """
    Esta função actualiza os TTL da cache. (É executada por uma thread auxiliar do servidor)
    """
    while True:
        for (_,cach,_) in roles.values():
            if isinstance(cach,cache.Cache):
                cach.passTime()
        sleep(1)


def soaexpire_detect(ss_conf: SSC.SSConfig, database: DB.DataBase):
    """
    Esta função vigia uma base de dados e quando o tempo de SOAEXPIRE termina, ela renova a base de dados do SS pedindo uma transferência de zona.
    """
    timer = database.soaexpire[0]
    print(database)
    while timer >= 0:
        #print(timer) # debug
        if timer <= 0:
            database.valid = False # declara a sua actual base de dados como inválida para não responder a pedidos a que ela tenha resposta.
            # sleep(1000) # para testar se o servidor deixa de responder quando a base de dados é inválida
            res = SFT.ServerFeatures.ask_zone_transfer(ss_conf.domain,ss_conf,my_ip,database.soaserial[0],
                                                       ss_conf.sp_server,5200,10,database.soaretry[0],5,debug_mode) # linhas recebidas na transferência de zona
            if res[0]: # a base de dados fica igual porque a versão é a mesma
                database.valid = True
            if res[1]: # base de dados recebida correctamente
                database.refresh(ss_conf,res[1],debug_mode) # renova a base de dadoss
                print(database)
                
            timer = database.soaexpire[0] # renova o temporizador
        timer -= 1
        sleep(1) 
    

# Variáveis que armazenam as threads deste servidor 
watch_caches_thread = threading.Thread(target=watch_caches,args=())
udp_thread = None
tcp_thread = None

if correct_configs_and_databases:
    for dom in roles: # cria as caches, efetua as transferências de zona necessárias no arranque e abre o atendimento TCP se este servidor for primário.
        (conf,cach,db) = roles[dom]
        if isinstance(conf,SPC.SPConfig): # Servidor primário
            db.addEntriesInCache(cach,0)
            watch_caches_thread.start()
            if tcp_thread is None: # abre o atendimento TCP
                tcp_thread = threading.Thread(target=SFT.ServerFeatures.atendimentoTCP,args=(conf,roles,my_ip,5200,debug_mode))
                tcp_thread.start()
            if udp_thread is None: # abre o atendimento UDP
                udp_thread = threading.Thread(target=SFT.ServerFeatures.atendimentoUDP,args=(roles,my_ip,5300,debug_mode))
                udp_thread.start()
            SFT.ServerFeatures.add_event_log_file(conf.file_all_log_path,f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ST 127.0.0.1:5300 Port=5300;Mode={'debug' if debug_mode else 'shy'}",debug_mode)

        elif isinstance(conf,SSC.SSConfig): # Servidor secundário
            (_,lines) = SFT.ServerFeatures.ask_zone_transfer(conf.domain,conf,my_ip,-1,conf.sp_server,5200,5,5,4,debug_mode)
            if lines: # transferência de zona bem sucedida
                db = DB.DataBase.fromLines(lines,'zone_transfer',dom)
                if db[1] is None: # erro na criação da base de dados
                    SFT.ServerFeatures.add_event_log_file(conf.file_log_path,db[0],debug_mode)
                else: # base de dados correcta
                    roles[dom] = (conf,cach,db[1])
                    db[1].addEntriesInCache(roles[dom][1],1)
                    watch_caches_thread.start()
                    threading.Thread(target=soaexpire_detect,args=(conf,db[1])).start()
                    if udp_thread is None: # abre o atendimento UDP
                        udp_thread = threading.Thread(target=SFT.ServerFeatures.atendimentoUDP,args=(roles,my_ip,5300,debug_mode))
                        udp_thread.start()
                    SFT.ServerFeatures.add_event_log_file(conf.file_all_log_path,f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ST 127.0.0.1:5300 Port=5300;Mode={'debug' if debug_mode else 'shy'}",debug_mode)

            else: # Erro na transferência de zona
                SFT.ServerFeatures.add_event_log_file(conf.file_log_path,f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EZ {conf.sp_server} SS',debug_mode)

        elif isinstance(conf,SRC.SRConfig): # servidor de resolução
            if udp_thread is None:
                udp_thread = threading.Thread(target=SFT.ServerFeatures.atendimentoUDP,args=(roles,my_ip,5300,debug_mode))
                udp_thread.start()
            watch_caches_thread.start()
            SFT.ServerFeatures.add_event_log_file(conf.file_all_log_path,f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ST 127.0.0.1:5300 Port=5300;Mode={'debug' if debug_mode else 'shy'}",debug_mode)
        else:
            break
else:
    print("Something went wrong.")