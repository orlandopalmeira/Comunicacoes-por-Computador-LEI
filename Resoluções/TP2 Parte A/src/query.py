from ast import literal_eval

class Query:
    """
    Esta classe armazena uma query.
    """

    def __init__(self, message_id: int, flags: int, response_code: int, number_of_values: int,
                 number_of_authorities: int, number_of_extra_values: int, name: str, type_of_value: int, 
                 response_values, authorities_values, extra_values):
        # HEADER
        self.message_id = message_id # 2 bytes
        self.flags = flags # 1 byte
        self.response_code = response_code # 1 byte
        self.number_of_values = number_of_values # 1 byte
        self.number_of_authorities = number_of_authorities # 1 byte
        self.number_of_extra_values = number_of_extra_values # 1 byte
        # end of header
        # DATA
        # Query info
        self.name = name # string de tamanho variável?
        self.type_of_value = type_of_value # (NS=6, MX=9, A=7, PTR=10) 1 byte
        # end of query info
        self.response_values = response_values # string de tamanho variável?
        self.authorities_values = authorities_values # string de tamanho variável?
        self.extra_values = extra_values # string de tamanho variável?
        # end of data 

    def __str__(self) -> str:
        flag_calc = ('','A','R','R+A','Q','Q+A','Q+R','Q+R+A')
        return f'{str(self.message_id)}%{flag_calc[self.flags]}%{str(self.response_code)}%{str(self.number_of_values)}%{str(self.number_of_authorities)}%{str(self.number_of_extra_values)}%{self.name}%{str(self.type_of_value)}%{str(self.response_values)}%{str(self.authorities_values)}%{str(self.extra_values)}'

    def stringQueryDebug(self) -> str:
        flag_calc = ('','A','R','R+A','Q','Q+A','Q+R','Q+R+A')
        type_value_calc = {6:'NS', 7:'A', 9:'MX', 10:'PTR'}
        string = f'{self.message_id},{flag_calc[self.flags]},{self.response_code},{self.number_of_values},{self.number_of_authorities},{self.number_of_extra_values};{self.name},{type_value_calc[self.type_of_value]};'
        
        if self.response_values is not None:
            for r in self.response_values:
                string += f'{r},'
            string = string[:-1] + ';'
        if self.authorities_values is not None:
            for a in self.authorities_values:
                string += f'{a},'
            string = string[:-1] + ';'
        if self.extra_values is not None:
            for e in self.extra_values:
                string += f'{e},'
            string = string[:-1] + ';'
        return string


    def printQuery(self):
        flag_calc = ('','A','R','R+A','Q','Q+A','Q+R','Q+R+A')
        type_value_calc = {6:'NS', 7:'A', 9:'MX', 10:'PTR'}
        string = f'# Header\nMESSAGE-ID = {self.message_id}, FLAGS = {flag_calc[self.flags]}, RESPONSE-CODE = {self.response_code},\n'
        string += f'N-VALUES = {self.number_of_values}, N-AUTHORITIES = {self.number_of_authorities}, N-EXTRA-VALUES = {self.number_of_extra_values};\n'
        string += f'# Data: Query Info\nQUERY-INFO.NAME = {self.name}, QUERY-INFO.TYPE = {type_value_calc[self.type_of_value]};\n'
        string += '# Data: List of Response, Authorities and Extra Values\n'

        if self.response_values is not None:
            for r in self.response_values:
                string += f'RESPONSE-VALUES = {r},\n'
            string = string[:-2] + ';\n'

        if self.authorities_values is not None:
            for a in self.authorities_values:
                string += f'AUTHORITIES-VALUES = {a},\n'
            string = string[:-2] + ';\n'

        if self.extra_values is not None:
            for e in self.extra_values:
                string += f'EXTRA-VALUES = {e},\n'
            string = string[:-2] + ';\n'

        print(string)
        

    @staticmethod
    def fromString(string: str):
        """
        Converte uma string numa query.
        """
        try:
            flag_calc = {'': 0, 'Q': 4, 'R': 2, 'A': 1, 'Q+R': 6, 'Q+A': 5, 'R+A': 3, 'Q+R+A': 7}
            fields = string.split('%')
            message_id = int(fields[0])
            flags = flag_calc[fields[1]]
            response_code = int(fields[2])
            number_of_values = int(fields[3])
            number_of_authorities = int(fields[4])
            number_of_extra_values = int(fields[5])
            name = fields[6]
            type_of_value = int(fields[7])
            response_values = literal_eval(fields[8])
            authorities_values = literal_eval(fields[9])
            extra_values = literal_eval(fields[10])
            return Query(message_id,flags,response_code,number_of_values,number_of_authorities,number_of_extra_values,
                         name,type_of_value,response_values,authorities_values,extra_values)
        except:
            return None

    
    def encode(self) -> bytes:
        """
        Codifica uma query em bytes
        """
        result = b''
        result += self.message_id.to_bytes(2,'big')
        result += self.flags.to_bytes(1,'big')
        result += self.response_code.to_bytes(1,'big')
        result += self.number_of_values.to_bytes(1,'big')
        result += self.number_of_authorities.to_bytes(1,'big')
        result += self.number_of_extra_values.to_bytes(1,'big')
        result += self.name.encode('utf-8') # TODO arranjar maneira de converter em bytes
        result += self.type_of_value.to_bytes(1,'big')
        result += self.response_values.encode('utf-8') # TODO arranjar maneira de converter em bytes
        result += self.authorities_values.encode('utf-8') # TODO arranjar maneira de converter em bytes
        result += self.extra_values.encode('utf-8') # TODO arranjar maneira de converter em bytes
        return result
    
    @staticmethod
    def decode():
        """
        Descodifica bytes e converte-os numa query.
        """
        # TODO: Descodificação da query de bytes para objecto
        return None

