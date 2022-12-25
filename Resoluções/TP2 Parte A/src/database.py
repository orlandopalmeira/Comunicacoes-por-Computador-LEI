import os
from datetime import datetime
from cache import Cache
from secondary_server_config import SSConfig
import server_features as SFT

class DataBase:
    """
    Classe que armazena uma base de dados.
    """
    type_of_value_from_int = ('SOASP','SOAADMIN','SOASERIAL','SOAREFRESH','SOARETRY','SOAEXPIRE',
                                   'NS','A','CNAME','MX','PTR')
    int_from_type_of_value = {'SOASP': 0, 'SOAADMIN': 1, 'SOASERIAL': 2, 'SOAREFRESH': 3, 'SOARETRY': 4,
                                   'SOAEXPIRE': 5, 'NS': 6, 'A': 7, 'CNAME': 8, 'MX': 9, 'PTR': 10}
    def __init__(self,domain: str, macros: dict, soasp, soaadmin, soaserial,
                 soarefresh, soaretry, soaexpire, ns, a, cname, mx, ptr, entradas) -> None:
        self.domain = domain # domínio ao qual esta BD pertence
        self.macros = macros # parametro -> valor
        self.soasp = soasp # (nome_servidor,TTL)
        self.soaadmin = soaadmin # (email,TTL)
        self.soaserial = soaserial # (versao,TTL)
        self.soarefresh = soarefresh # (intervalo_temporal,TTL)
        self.soaretry = soaretry # (intervalo_temporal,TTL)
        self.soaexpire = soaexpire # (intervalo_temporal,TTL)
        self.ns = ns # domínio -> lista((nome_servidor,TTL,prioridade))
        self.a = a # nome_servidor -> lista((endereço_ip,TTL,prioridade))
        self.cname = cname # nome_canonico -> (nome_normal,TTL)
        self.mx = mx # domínio -> lista((nome_servidor,TTL,prioridade))
        self.ptr = ptr # endereço_ip -> (nome_servidor,ttl)
        self.entradas = entradas # linhas do ficheiro de base de dados. É utilizado na transferência de zona.
        self.valid = True 
    
    def __str__(self) -> str:
        res = ''
        for entrada in self.entradas:
            res += f'{entrada}\n'
        return res
    
    def refresh(self, ss_conf: SSConfig, lines: list, debug_mode: bool):
        new_db = DataBase.fromLines(lines,domain=ss_conf.domain)
        SFT.ServerFeatures.add_event_log_file(ss_conf.file_log_path,new_db[0],debug_mode)
        if new_db[1] is not None: # Base de dados incorrecta
            self.domain = new_db[1].domain
            self.macros = new_db[1].macros
            self.soasp = new_db[1].soasp
            self.soaadmin = new_db[1].soaadmin
            self.soaserial = new_db[1].soaserial
            self.soarefresh = new_db[1].soarefresh
            self.soaretry = new_db[1].soaretry
            self.soaexpire = new_db[1].soaexpire
            self.ns = new_db[1].ns
            self.a = new_db[1].a
            self.cname = new_db[1].cname
            self.mx = new_db[1].mx
            self.ptr = new_db[1].ptr
            self.entradas = new_db[1].entradas
            self.valid = new_db[1].valid


    def existsDomain(self,name: str) -> bool:
        name_ = self.cname[name][0] if name in self.cname else name
        return self.valid and ((name_ in self.ns) or (name_ in self.a) or (name_ in self.mx) or (name_ in self.cname) or (name_ in self.ptr))

    def responseCode1(self, name: str, type_of_value: int):
        t_value = DataBase.type_of_value_from_int[type_of_value]
        if t_value == 'NS':
            return self.existsDomain(name) and (name not in self.ns)
        elif t_value == 'A':
            return self.existsDomain(name) and (name not in self.a)
        elif t_value == 'MX':
            return self.existsDomain(name) and (name not in self.mx)
        elif t_value == 'PTR':
            return self.existsDomain(name) and (name not in self.ptr)
        return False

    def responseCode2(self, name: str):
        return not self.existsDomain(name)

    @staticmethod
    def __replace_defaults(string: str, macros: dict):
        """
        Substitui os DEFAULT's na string dada.
        """
        isDomain = lambda x: isinstance(x, str) and x.count('.') > 0
        for default in macros:
            if default in string:
                if (default == '@') or (isDomain(macros[default])):
                    string = string.replace(default,'.'+ str(macros[default]))
                else:
                    string = string.replace(default,str(macros[default]))

        while '..' in string:
            string = string.replace('..','.')

        return string.lstrip('.') if string != '.' else string
    
    @staticmethod
    def __complete_names_and_domains(string: str, macros: dict):
        """
        Completa nomes caso sejam incompletos (não acabem em '.').
        """
        if string[-1:] != '.' and '@' in macros: # se não tiver o ponto final, significa que o nome/domínio não está completo, pelo que se acrescentará o valor do default @
            string += '.' + macros['@']

        while '..' in string:
            string = string.replace('..','.')
        
        return string.lstrip('.') if string != '.' else string
    
    @staticmethod
    def __replace_defaults_and_complete(string: str, macros: dict):
        string = DataBase.__replace_defaults(string,macros)
        string = DataBase.__complete_names_and_domains(string,macros)
        return string

    @staticmethod
    def __complete_and_replace_defaults(string: str, macros: dict):
        string = DataBase.__complete_names_and_domains(string,macros)
        string = DataBase.__replace_defaults(string,macros)
        return string

    @staticmethod
    def fileToDatabase(file_db: str, domain: str):
        """
        Esta função converte um ficheiro numa base de dados.
        """
        if os.path.exists(file_db):
            file = open(file_db,"r") # ficheiro de configuração
            lines = list(filter(lambda l: ('#' not in l) and l != '\n',file.readlines())) # apaga as linhas de comentário e linhas vazias
            lines = list(map(lambda s: s.replace('\n',''),lines)) # tira os \n de cada linha
            return DataBase.fromLines(lines,file_path=file_db,domain=domain) 
        else:
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} SP 127.0.0.1 db-file \'{file_db}\' does not exist', None)
    
    @staticmethod
    def fromLines(lines: list, file_path: str = 'zone_transfer', domain: str  = 'nothing.com.'): # 
        """
        Esta função recebe as entradas do ficheiro de base de dados e converte-as numa base de dados.
        """
        # Variáveis de instância da base de dados
        macros = dict() # parametro -> valor
        soasp = None # (nome_servidor,TTL)
        soaadmin = None # (email,TTL)
        soaserial = None # (versao,TTL)
        soarefresh = None # (intervalo_temporal,TTL)
        soaretry = None # (intervalo_temporal,TTL)
        soaexpire = None # (intervalo_temporal,TTL)
        ns = dict() # domínio -> lista((nome_servidor,TTL,prioridade))
        a = dict() # nome_servidor -> lista((endereço_ip,TTL,prioridade))
        cname = dict() # nome_canonico -> (nome_normal,TTL)
        mx = dict() # domínio -> lista((nome_servidor,TTL,prioridade))
        ptr = dict() # endereço_ip -> (nome_servidor,ttl)
        entradas = lines
        # Variáveis auxiliares da função
        lines = list(map(lambda l: l.replace('\n','').split(' '),lines))
        macros_lines = list(filter(lambda l: 'DEFAULT' in l,lines))
        try: 
            for line in macros_lines: # obtenção das macros (defaults)
                if line[1] == 'DEFAULT':
                    if len(line) == 3:
                        macros[line[0]] = int(line[2]) if line[2].isnumeric() else line[2]
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect DEFAULT[\'{line[0]}\'=\'{line[2]}\']', None)

            for line in lines:
                if line[1] == 'DEFAULT':
                    continue
                elif line[1] == 'SOASP':
                    if len(line) == 4:
                        soasp = (DataBase.__replace_defaults_and_complete(line[2],macros),
                                int(DataBase.__replace_defaults(line[3],macros)))
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect SOASP -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'SOAADMIN':
                    if len(line) == 4:
                        soaadmin = (DataBase.__replace_defaults_and_complete(line[2],macros),
                                    int(DataBase.__replace_defaults(line[3],macros)))
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect SOAADMIN -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'SOASERIAL':
                    if len(line) == 4:
                        soaserial = (int(DataBase.__replace_defaults(line[2],macros)),
                                    int(DataBase.__replace_defaults(line[3],macros)))
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect SOASERIAL -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'SOAREFRESH':
                    if len(line) == 4:
                        soarefresh = (int(DataBase.__replace_defaults(line[2],macros)),
                                        int(DataBase.__replace_defaults(line[3],macros)))
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect SOAREFRESH -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'SOARETRY':
                    if len(line) == 4:
                        soaretry = (int(DataBase.__replace_defaults(line[2],macros)),
                                    int(DataBase.__replace_defaults(line[3],macros)))
                    else: 
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect SOARETRY -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'SOAEXPIRE':
                    if len(line) == 4:
                        soaexpire = (int(DataBase.__replace_defaults(line[2],macros)),
                                    int(DataBase.__replace_defaults(line[3],macros)))
                    else: 
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect SOAEXPIRE -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'NS':
                    if len(line) in [4,5]: # avalia se existe um numero de campos correcto
                        ns_dominio = DataBase.__replace_defaults_and_complete(line[0],macros)
                        ns_server_name = DataBase.__replace_defaults_and_complete(line[2],macros) 
                        ns_ttl = int(DataBase.__replace_defaults(line[3],macros))
                        ns_priority = int(DataBase.__replace_defaults(line[4],macros)) if len(line) == 5 else -1 # se a prioridade não for mencionada, terá o valor -1
                        if ns_dominio in ns: # já existe algum servidor autoritativo para o domínio?
                            ns[ns_dominio].append((ns_server_name,ns_ttl,ns_priority))
                        else:
                            ns[ns_dominio] = [(ns_server_name,ns_ttl,ns_priority)]
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect NS -> line:\'{" ".join(line)}\'', None)                                        
                elif line[1] == 'A':
                    if len(line) in [4,5]: # avalia se existe um numero de campos correcto
                        a_server_name = DataBase.__replace_defaults_and_complete(line[0],macros)
                        a_ip_addr = line[2]
                        a_ttl = int(DataBase.__replace_defaults(line[3],macros))
                        a_priority = int(DataBase.__replace_defaults(line[4],macros)) if len(line) == 5 else -1
                        if a_server_name in a:
                            a[a_server_name].append((a_ip_addr,a_ttl,a_priority)) 
                        else:
                            a[a_server_name] = [((a_ip_addr,a_ttl,a_priority))]
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect A -> line:\'{" ".join(line)}\'', None) 
                elif line[1] == 'CNAME':
                    if len(line) == 4:
                        n_canonico = DataBase.__replace_defaults_and_complete(line[0],macros)
                        n_normal = DataBase.__replace_defaults_and_complete(line[2],macros)
                        cname_ttl = int(DataBase.__replace_defaults(line[3],macros))
                        if (n_normal not in cname) and (n_canonico not in cname): # verifica que (i) um nome canónico não aponta para outro nome canónico e (ii) que não existe um nome canónico a apontar para dois nomes diferentes
                            cname[n_canonico] = (n_normal,cname_ttl)
                        else:
                            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect CNAME -> line:\'{" ".join(line)}\'', None)
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect CNAME -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'MX':
                    if len(line) in [4,5]: # verifica se o número de campos está correcto
                        mx_dominio = DataBase.__replace_defaults_and_complete(line[0],macros)
                        mx_server_name = DataBase.__replace_defaults_and_complete(line[2],macros)
                        mx_ttl = int(DataBase.__replace_defaults(line[3],macros))
                        mx_priority = int(DataBase.__replace_defaults(line[4],macros)) if len(line) == 5 else -1
                        if mx_dominio in mx:
                            mx[mx_dominio].append((mx_server_name,mx_ttl,mx_priority))
                        else:
                            mx[mx_dominio] = [(mx_server_name,mx_ttl,mx_priority)]
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect MX -> line:\'{" ".join(line)}\'', None)
                elif line[1] == 'PTR':
                    if len(line) == 4:
                        ptr_ip_addr = line[0]
                        ptr_server_name = DataBase.__replace_defaults_and_complete(line[2],macros)
                        ptr_ttl = int(DataBase.__replace_defaults(line[3],macros))
                        ptr[ptr_ip_addr] = (ptr_server_name,ptr_ttl)
                    else:
                        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect PTR -> line:\'{" ".join(line)}\'', None)
                else:
                    return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' incorrect TYPE-OF-VALUE -> line:\'{" ".join(line)}\'', None)
            
            # Ordenação conforme as prioridades
            for k in ns:
                ns[k].sort(key=lambda x: x[2])
            
            for k in a:
                a[k].sort(key=lambda x: x[2])
            
            for k in mx:
                mx[k].sort(key=lambda x: x[2])
        except:
            return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} FL 127.0.0.1 db-file \'{file_path}\' something went wrong',None)
        return (f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} EV 127.0.0.1 db-file \'{file_path}\' was read\'',
                DataBase(domain,macros,soasp,soaadmin,soaserial,soarefresh,soaretry,soaexpire,ns,a,cname,mx,ptr,entradas))

    def addEntriesInCache(self,cache: Cache, origin: int) -> None:
        """
        Adiciona todas as entradas desta base de dados numa cache.
        """
        cache.addEntry(self.domain,DataBase.int_from_type_of_value['SOASP'],self.soasp[0],
                       self.soasp[1],-1,origin)
        if self.soaadmin is not None:                       
            cache.addEntry(self.domain,DataBase.int_from_type_of_value['SOAADMIN'],self.soaadmin[0],
                       self.soaadmin[1],-1,origin)
        cache.addEntry(self.domain,DataBase.int_from_type_of_value['SOASERIAL'],self.soaserial[0],
                       self.soaserial[1],-1,origin)
        cache.addEntry(self.domain,DataBase.int_from_type_of_value['SOAREFRESH'],self.soarefresh[0],
                       self.soarefresh[1],-1,origin)
        cache.addEntry(self.domain,DataBase.int_from_type_of_value['SOARETRY'],self.soaretry[0],
                       self.soaretry[1],-1,origin)
        cache.addEntry(self.domain,DataBase.int_from_type_of_value['SOAEXPIRE'],self.soaexpire[0],
                       self.soaexpire[1],-1,origin)
        
        for dom in self.ns:
            for (server_name,ttl,priority) in self.ns[dom]:
                cache.addEntry(dom,DataBase.int_from_type_of_value['NS'],server_name,ttl,priority,origin)

        for server_name in self.a:
            for (ip_addr,ttl,priority) in self.a[server_name]:
                cache.addEntry(server_name,DataBase.int_from_type_of_value['A'],ip_addr,ttl,priority,origin)
        
        for canonic in self.cname:
            (normal,ttl) = self.cname[canonic]
            cache.addEntry(canonic,DataBase.int_from_type_of_value['CNAME'],normal,ttl,-1,origin)
        
        for dom in self.mx:
            for (server_name, ttl, priority) in self.mx[dom]:
                cache.addEntry(dom,DataBase.int_from_type_of_value['MX'],server_name,ttl,priority,origin)

        for ip_addr in self.ptr:
            (server_name,ttl) = self.ptr[ip_addr]
            cache.addEntry(ip_addr,DataBase.int_from_type_of_value['PTR'],server_name,ttl,-1,origin)
    

    def __getResponseValues(self, name: str, type_of_value: str):
        """
        Esta função devolve os response values de uma query.
        """
        name_ = self.cname[name][0] if name in self.cname else name
        result = []
        if type_of_value.upper() in {'NS','A','MX','PTR'}:
            if type_of_value.upper() == 'NS':
                if name_ in self.ns:
                    for (serv_name,ttl,prio) in self.ns[name_]:
                        p = '' if prio == -1 else f' {prio}'
                        result.append(f'{name_} NS {serv_name} {ttl}{p}')

            elif type_of_value.upper() == 'A':
                if name_ in self.a:
                    for (ip_add,ttl,prio) in self.a[name_]:
                        p = '' if prio == -1 else f' {prio}'
                        result.append(f'{name_} A {ip_add} {ttl}{p}')

            elif type_of_value.upper() == 'MX':
                if name_ in self.mx:
                    for (serv_name,ttl,prio) in self.mx[name_]:
                        p = '' if prio == -1 else f' {prio}'
                        result.append(f'{name_} MX {serv_name} {ttl}{p}')
            
            elif type_of_value.upper() == 'PTR':
                #TODO: Não sei se isto pode ser feito assim
                # Aqui o name é o endereço IP
                if name_ in self.ptr:
                    (serv_name,ttl) = self.ptr[name_]
                    result.append(f'{name_} PTR {serv_name} {ttl}')

        return result

    def __getAuthoritiesValues(self, name: str):
        """
        Esta função devolve os authorities values de uma query.
        """
        return self.__getResponseValues(name,'NS')
    
    def __getExtraValues(self, response_values, authorities_values):
        """
        Esta função devolve os extra values de uma query.
        """
        rv_values = set(map(lambda s: s.split(' ')[2],response_values)) # vai buscar o campo value 
        av_values = set(map(lambda s: s.split(' ')[2],authorities_values)) # vai buscar o campo value 
        result = []
        for serv_name in self.a:
            for (ip_add,ttl,prio) in self.a[serv_name]:
                if (serv_name in rv_values) or (av_values in av_values):
                    p = '' if prio == -1 else f' {prio}'
                    result.append(f'{serv_name} A {ip_add} {ttl}{p}')
        return result

    def getQueryResponse(self, name: str, type_of_value: str):
        response_values = self.__getResponseValues(name,type_of_value)
        authorities_values = self.__getAuthoritiesValues(name)
        extra_values = self.__getExtraValues(response_values,authorities_values)
        return (response_values,authorities_values,extra_values)
