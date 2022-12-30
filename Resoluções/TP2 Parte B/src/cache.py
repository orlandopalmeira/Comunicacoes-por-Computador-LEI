from query import Query
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
    
    def __eq__(self, obj) -> bool:
        if isinstance(obj,_CacheEntry):
            return self.name == obj.name and self.type_of_value == obj.type_of_value and self.value == obj.value
        return False


    def passTimeEntry(self) -> None:
        """
        Esta função avança 1 segundo no tempo desta entrada.
        """
        if self.origin == 2:
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
    
    def changeData2(self, entry):
        if isinstance(entry, _CacheEntry):
            self.changeData(entry.name,entry.type_of_value,entry.value,entry.ttl,entry.priority,entry.origin,entry.timestamp)
        else:
            raise TypeError("O argumento entry fornecido não é do tipo _CacheEntry")

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

    def __findEntry(self,entry: _CacheEntry):
        result = -1
        for i in range(len(self.entries)):
            if self.entries[i] == entry:
                result = i
                break
        return result

    def addEntry(self,name: str, type_of_value: int, value, ttl: int, priority: int, origin):
        """
        Este método adiciona uma entrada na cache.
        """
        if self._isFull():
            toInsert = _CacheEntry(name,type_of_value,value,ttl,priority,origin,self.timestamp,self.N,1)
            i = self.__findEntry(toInsert)
            if i > -1:
                self.entries[i].changeData2(_CacheEntry(name,type_of_value,value,ttl,priority,origin,self.timestamp,i,1))
            else:
                self.N += 1
                self.entries.append(toInsert)
        else:
            p = self._findFreeEntry()
            toInsert = _CacheEntry(name,type_of_value,value,ttl,priority,origin,self.timestamp,self.N,1)
            i = self.__findEntry(toInsert)
            if i > -1:
                self.entries[i].changeData2(_CacheEntry(name,type_of_value,value,ttl,priority,origin,self.timestamp,i,1))
            else:
                self.entries[p].changeData(name,type_of_value,value,ttl,priority,origin,self.timestamp)
    
    def addEntryString(self, entry: str, origin):
        int_from_type_of_value = {'SOASP': 0, 'SOAADMIN': 1, 'SOASERIAL': 2, 'SOAREFRESH': 3, 'SOARETRY': 4,
                                   'SOAEXPIRE': 5, 'NS': 6, 'A': 7, 'CNAME': 8, 'MX': 9, 'PTR': 10}
        aux = entry.split(' ')
        #'SOASP','SOAADMIN','SOASERIAL','SOAREFRESH','SOARETRY','SOAEXPIRE','NS','A','CNAME','MX','PTR'
        if aux[1] in {'NS','A','MX'}: # campos que suportam prioridades
            if len(aux) == 4:
                self.addEntry(aux[0],int_from_type_of_value[aux[1]],aux[2],int(aux[3]),-1,origin)
            elif len(aux) > 4:
                self.addEntry(aux[0],int_from_type_of_value[aux[1]],aux[2],int(aux[3]),int(aux[4]),origin)
        else:
            self.addEntry(aux[0],int_from_type_of_value[aux[1]],aux[2],int(aux[3]),-1,origin)
    
    def addEntriesString(self, entries, origin):
        for entry in entries:
            self.addEntryString(entry, origin)

    def addEntriesFromQuery(self, query: Query, origin):
        if query.response_values is not None:
            self.addEntriesString(query.response_values,origin)
        if query.authorities_values is not None:
            self.addEntriesString(query.authorities_values,origin)
        if query.extra_values is not None:
            self.addEntriesString(query.extra_values,origin)

    def existsDomain(self,domain: str):
        """
        Esta função verifica se existe nesta cache um certo domínio/nome.
        """
        for entry in self.entries:
            if entry.status == 1 and entry.name == domain:
                return True

        return False

    def existsDomain2(self,domain: str):
        res = False
        for entry in self.entries:
            if entry.status == 1 and entry.name in domain and entry.name != '.':
                return True
        return res

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

    def __getAuthoritiesValues2(self, name: str):
        res = []
        ns = list(filter(lambda x: x.type_of_value == 6,self.entries)) # recolhe só os NS's
        print(name) # debug
        for x in ns: print(x) # debug
        for elem in ns:
            if elem.name in name:
                p = '' if elem.priority == -1 else f' {elem.priority}'
                res.append(f'{elem.name} NS {elem.value} {elem.ttl}{p}')
        return res

    def __getExtraValues2(self, response_values = [], authorities_values = []):
        res = []
        a = list(filter(lambda x: x.type_of_value == 7,self.entries))
        rv_values = set(map(lambda s: s.split(' ')[2],response_values)) # vai buscar o campo value 
        av_values = set(map(lambda s: s.split(' ')[2],authorities_values)) # vai buscar o campo value 
        for elem in a:
            print(f'elem.name = {elem.name}') # debug
            if (elem.name in rv_values) or (elem.name in av_values):
                p = '' if elem.priority == -1 else f' {elem.priority}'
                res.append(f'{elem.name} A {elem.value} {elem.ttl}{p}')
        
        return res


    def getQueryResponse(self, name: str, type_of_value: str):
        """
        Esta função calcula a resposta a uma queria a partir da cache.
        """
        int_from_type_of_value = {'SOASP': 0, 'SOAADMIN': 1, 'SOASERIAL': 2, 'SOAREFRESH': 3, 'SOARETRY': 4,
                                  'SOAEXPIRE': 5, 'NS': 6, 'A': 7, 'CNAME': 8, 'MX': 9, 'PTR': 10}
        '''
        if self.responseCode1(name,int_from_type_of_value[type_of_value]):
            print("Response code 1") # debug
            authorities_values = self.__getAuthoritiesValues2(name)
            extra_values = self.__getExtraValues2(authorities_values=authorities_values)
            return ([],authorities_values,extra_values)
        elif self.responseCode2(name):
            print("Response code 2") # debug
            authorities_values = self.__getAuthoritiesValues2(name)
            extra_values = self.__getExtraValues2(authorities_values=authorities_values)
            return ([],authorities_values,extra_values)
        else:
            print("Response code not in [1,2]") # debug
            response_values = self.__getResponseValues(name,type_of_value)
            authorities_values = self.__getAuthoritiesValues2(name)
            extra_values = self.__getExtraValues2(response_values=response_values,authorities_values=authorities_values)
            return (response_values,authorities_values,extra_values) '''
        response_values = self.__getResponseValues(name,type_of_value)
        authorities_values = self.__getAuthoritiesValues2(name)
        extra_values = self.__getExtraValues2(response_values=response_values,authorities_values=authorities_values)
        return (response_values,authorities_values,extra_values)
