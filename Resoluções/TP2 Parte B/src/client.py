import socket
from sys import argv
from query import Query
from random import randint
from signal import signal, alarm, SIGALRM

# argumentos: ip_do_servidor_a_quem_pergunta | domínio(nome completo -> termina com '.') | tipo valor (NS,MX,A,PTR) | -t <timeout_seconds> |
# flag_sem_modo_debug | flag_usar_modo_recursivo

# para não usar o modo debug, deve ser dado o seguinte argumento: --no-debug
# para usar o modo recursivo, deve ser dado o seguinte argumento: -r
# para personalizar o timeout deve ser dado o seguinte argumento: -t <tempo_em_segundos>

def timeout_handler(signum, frame):
    """
    Como o cliente deve agir se o tempo de espera definido for ultrapassado.
    """
    raise TimeoutError('Timeout over')


# arguments
args = argv[1:] # retira o primeiro argumento (é inútil)

# modes
debug_mode = False if '--no-debug' in args else True
recursive_mode = True if '-r' in args else False #TODO: implement -> Recursive mode

# server ip and its port
server_ip = args[0]
port = 5300

#timeout (default: 10 seconds)
timeout = int(args[args.index('-t')+1]) if '-t' in args else 10

# Query values
type_of_values = {'NS':6, 'MX':9, 'A':7, 'PTR':10}
message_id = randint(1,65535)
flags = 6 if recursive_mode else 4
name = args[1]
type_of_value = type_of_values[args[2]]
query = Query(message_id,flags,0,0,0,0,name,type_of_value,None,None,None)

if name[-1:] == '.': # o nome está completo?
    try:
        sckt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # criação do socket
        if debug_mode:
            sckt.sendto(str(query).encode('utf-8'), (server_ip,port)) # envia para o servidor (debug)
        else:
            sckt.sendto(query.encode(),(server_ip,port)) # envia para o servidor (no debug)
        signal(SIGALRM, timeout_handler) # regista o que deve fazer quando o tempo de espera superar o timeout
        alarm(timeout) # inicia o tempo de espera
        try: 
            response, add = sckt.recvfrom(4096) # recebe do servidor, recvfrom é bloqueante por defeito
            alarm(0) # cancela o alarme porque já recebeu a resposta do servidor
            query_res = Query.fromString(response.decode('utf-8')) # converte a resposta do servidor numa query de resposta
            if query_res is not None:
                query_res.printQuery()

        except TimeoutError:
            print(f"Timeout of {timeout} seconds is over")
        except:
            print('Something went wrong')
    except:
        print('Something went wrong')
else:
    print(f'O nome \'{name}\' está incompleto.\nCertifique-se que termina com \'.\'')