class _CacheEntry:
    """
    Esta classe privada implementa uma entrada da cache.
    """
    type_of_value_from_int = ('SOASP','SOAADMIN','SOASERIAL','SOAREFRESH','SOARETRY','SOAEXPIRE',
                                   'NS','A','CNAME','MX','PTR')
    int_from_type_of_value = {'SOASP': 0, 'SOAADMIN': 1, 'SOASERIAL': 2, 'SOAREFRESH': 3, 'SOARETRY': 4,
                                   'SOAEXPIRE': 5, 'NS': 6, 'A': 7, 'CNAME': 8, 'MX': 9, 'PTR': 10}
    origin_from_int = ('FILE','SP','OTHERS')
    def __init__(self, name: str, type_of_value: int, value, ttl: int, priority: int, origin,
                 timestamp: int,index: int, status: int) -> None:
        self.name = name
        self.type_of_value = type_of_value
        self.value = value
        self.ttl = ttl
        self.priority = priority
        self.origin = origin # File->0, SP->1, OTHERS->2
        self.timestamp = timestamp
        self.index = index
        self.status = status # 0 = FREE, 1 = VALID

    def __str__(self) -> str:
        status = 'FREE' if self.status == 0 else 'VALID'
        return f'{self.name} {_CacheEntry.type_of_value_from_int[self.type_of_value]} {self.value} {self.ttl} {self.priority} {_CacheEntry.origin_from_int[self.origin]} {self.timestamp} {self.index} {status}'
    
    def passTimeEntry(self) -> None:
        """
        Esta função avança 1 segundo no tempo desta entrada.
        """
        self.ttl -= 1
        self.status = 1 if self.ttl > 0 else 0

    def changeData(self, name, type_of_value, value, ttl, priority, origin,
                   timestamp) -> None:
        """
        Esta função actualiza o valor da entrada.
        """
        self.name = name
        self.type_of_value = type_of_value
        self.value = value
        self.ttl = ttl
        self.priority = priority
        self.origin = origin
        self.timestamp = timestamp
        self.status = 1


class Cache:

    # NAME | TYPE-OF-VALUE | VALUE | TTL | PRIORITY | ORIGIN (FILE,SP,OTHERS) |
    # TEMPO DESDE QUE O SERVIDOR ARRANCOU ATÉ INSERIR A ENTRADA
    # INDEX ([1,N]) | STATUS (FREE:0 OR VALID:1)

    def __init__(self) -> None:
        self.timestamp = 0 # em segundos
        self.entries = list([_CacheEntry('',-1,None,0,-1,None,0,1,0)])
        self.N = 1
        
    def __str__(self) -> str:
        res = ''
        for entry in self.entries:
            res += f'{str(entry)}\n'
        return res

    def passTime(self) -> None:
        """
        Esta função avança 1 segundo na cache.
        """
        self.timestamp += 1
        for entry in self.entries:
            entry.passTimeEntry()

    def _findFreeEntry(self) -> int:
        """
        Esta função devolve o índice da primeira entrada da tabela da cache com estado 'FREE'.
        Se não houver entradas livres, devolve -1.
        """
        for i in range(self.N):
            if self.entries[i].status == 0:
                return i

        return -1

    def _isFull(self) -> bool:
        """
        Esta função verifica se a cache está cheia, ou seja, todas as entradas têm status 'VALID'.
        """
        result = True
        for entry in self.entries:
            if entry.status == 0:
                result = False
                break
        return result

    def addEntry(self,name: str, type_of_value, value, ttl: int, priority: int, origin):
        """
        Este método adiciona uma entrada na cache.
        """
        if self._isFull():
            self.N += 1
            self.entries.append(_CacheEntry(name,type_of_value,value,ttl,priority,origin,self.timestamp,self.N,1))
        else:
            p = self._findFreeEntry()
            self.entries[p].changeData(name,type_of_value,value,ttl,priority,origin,self.timestamp)
    
    def existsDomain(self,domain: str):
        """
        Esta função verifica se existe nesta cache um certo domínio/nome.
        """
        for entry in self.entries:
            if entry.status == 1 and entry.name == domain:
                return True

        return False

    def responseCode1(self, name:str,type_of_value: int):
        aux = [x for x in self.entries if (x.status == 1) and (x.type_of_value == type_of_value)]
        aux = set(map(lambda e: e.name,aux))
        return self.existsDomain(name) and (name not in aux)

    def responseCode2(self, name:str):
        return not self.existsDomain(name)


    def __getResponseValues(self,name: str, type_of_value: str):
        """
        Esta função devolve os response values de uma query.
        """
        int_from_type_of_value = {'SOASP': 0, 'SOAADMIN': 1, 'SOASERIAL': 2, 'SOAREFRESH': 3, 'SOARETRY': 4,
                                  'SOAEXPIRE': 5, 'NS': 6, 'A': 7, 'CNAME': 8, 'MX': 9, 'PTR': 10}
        type_of_value_from_int = ('SOASP','SOAADMIN','SOASERIAL','SOAREFRESH','SOARETRY','SOAEXPIRE',
                                   'NS','A','CNAME','MX','PTR')

        result = []
        for entry in self.entries:
            if (entry.name == name) and (entry.type_of_value == int_from_type_of_value[type_of_value]):
                prio = '' if entry.priority == -1 else f' {entry.priority}'
                string = f'{entry.name} {type_of_value_from_int[entry.type_of_value]} {entry.value} {entry.ttl}{prio}'
                result.append(string)
        return result
    
    def __getAuthoritiesValues(self,name: str):
        """
        Esta função devolve os authorities values de uma query.
        """
        return self.__getResponseValues(name,'NS')

    def __getExtraValues(self, response_values: list, authorities_values: list):
        """
        Esta função devolve os extra values de uma query.
        """
        rv_values = set(map(lambda s: s.split(' ')[2],response_values)) # vai buscar o campo value 
        av_values = set(map(lambda s: s.split(' ')[2],authorities_values)) # vai buscar o campo value 
        result = []
        for entry in self.entries:
            if (entry.type_of_value == 7) and ((entry.name in rv_values) or (entry.name in av_values)):
                prio = '' if entry.priority == -1 else f' {entry.priority}'
                string = f'{entry.name} A {entry.value} {entry.ttl}{prio}'
                result.append(string)
        return result

    def getQueryResponse(self, name: str, type_of_value: str):
        """
        Esta função calcula a resposta a uma queria a partir da cache.
        """
        response_values = self.__getResponseValues(name,type_of_value)
        authorities_values = self.__getAuthoritiesValues(name)
        extra_values = self.__getExtraValues(response_values,authorities_values)
        return (response_values,authorities_values,extra_values)
