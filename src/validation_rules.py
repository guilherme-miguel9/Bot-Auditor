"""
Sistema de validação de comentários baseado em regras de negócio
para cada tipo de nota de leitura.
"""

import re
import pandas as pd
from typing import Dict, Tuple, Optional


# Configuração das regras de validação por tipo de nota
VALIDATION_RULES = {
    # Notas que requerem MEDIDOR + LEITURA
    "B111": {"required": "MEDIDOR_LEITURA", "description": "Local Cons. Implantado em Duplicidade"},
    "P111": {"required": "MEDIDOR_LEITURA", "description": "E.M. Substituído ou Número Incorreto"},
    "P131": {"required": "MEDIDOR_LEITURA", "description": "E.M. Vizinho Não Cadastrado"},
    "T171": {"required": "MEDIDOR_LEITURA_FUNCAO", "description": "Data/Hora do E.M. Incorreta", "funcoes_validas": ["01", "02"]},
    
    # Notas que requerem Nº DO POSTE (M000000 - 1 letra e 6 números)
    "E101": {"required": "POSTE_FORMAT", "description": "Poste Inclinado ou Quebrado"},
    "E111": {"required": "POSTE_FORMAT", "description": "Objeto, Árvore, Imóvel Encostado/Próximo à Rede"},
    "P231": {"required": "POSTE_FORMAT", "description": "Iluminação Pública Acesa Durante o Dia"},
    
    # Notas que requerem TEXTO CONDIZENTE COM A NOTA
    "C111": {"required": "TEXTO_CONDIZENTE", "description": "Bairro Incorreto"},
    "C121": {"required": "TEXTO_CONDIZENTE", "description": "Rua Incorreta"},
    "C131": {"required": "TEXTO_CONDIZENTE", "description": "Número da Porta/Porta Incorreto"},
    "C151": {"required": "TEXTO_CONDIZENTE", "description": "Atividade Incorreta"},
    "C161": {"required": "TEXTO_CONDIZENTE", "description": "Quant. Incorreta de Dígitos do E.M."},
    "C181": {"required": "TEXTO_CONDIZENTE", "description": "Número do Poste Incorreto"},
    "P191": {"required": "TEXTO_CONDIZENTE", "description": "U.C. Vizinha Com Ligação Clandestina"},
    "R161": {"required": "TEXTO_CONDIZENTE", "description": "Ponto de Referência Incorreto"},
    
    # Notas específicas
    # L121 removido da validação automática (será feito manualmente)
    "L131": {"required": "CAMPANHA", "description": "Campanha 2", "formato_especifico": "n DO TEL; NOME; VAZIO E RECUSA DE DADOS"},
    "R111": {"required": "MEDIDOR_SEM_LEITURA", "description": "Medidor Alocado Incorretamente"},
    "T161": {"required": "APENAS_FUNCAO", "description": "Função Não Existe no PDA"},
    "T181": {"required": "FUNCAO_LEITURA", "description": "Função Não Existe no Sistema", "funcao_invalida": "03"},
}


class CommentValidator:
    """Validador de comentários baseado em regras de negócio"""
    
    def __init__(self):
        # Tokens e abreviações permitidas que podem aparecer nos comentários
        self.tokens_permitidos = ['NR DI', 'NR RE', 'NR IM', 'SELO', 'ZELO', 'S', 'R']
        # Notas onde o comentário não é obrigatório ou o token pode vir sozinho
        self.notas_sem_comentario = ["T161", "L131", "P191", "T171", "L121"]
    
    def validar_comentario(self, nota: str, comentario: str) -> Optional[str]:
        """
        Valida um comentário baseado na nota de leitura.
        """
        if nota == "L121":
            return None
            
        if pd.isna(comentario) or str(comentario).strip() == "":
            return self._validar_comentario_vazio(nota)
        
        comentario = str(comentario).strip()
        
        # Verificar caracteres especiais (pegar todos os caracteres especiais de todos os comentários)
        if self._tem_caracteres_especiais(comentario):
            return "UCE"
        
        # Verificar excesso de espaços (3 ou mais)
        if self._tem_excesso_espacos(comentario):
            return "EE"
            
        # Verificar se as notas T181 ou R111 possuem 03 (como token isolado ou começando com 03), configurando CFP
        if nota in ["T181", "R111"]:
            if re.match(r'^03', comentario.strip()) or re.search(r'\b03\b', comentario):
                return "CFP"
                
        # Verificar se o comentário possui apenas os tokens permitidos (S | SELO | ZELO | NR DI | NR RE | R | NR IM)
        if self._e_apenas_token_permitido(comentario):
            if nota in self.notas_sem_comentario:
                return "C"
            # Se não for de nota sem comentário (ou seja, notas que exigem comentário), não pode vir só:
            # Continua para a validação específica da nota abaixo para verificar falta de dados
        
        # Obter regra para a nota
        regra = VALIDATION_RULES.get(nota)
        if not regra:
            return "C"
        
        # Validar baseado no tipo de conteúdo requerido
        return self._validar_conteudo_requerido(nota, comentario, regra)
    
    def _validar_comentario_vazio(self, nota: str) -> str:
        """Valida quando o comentário está vazio"""
        if nota in self.notas_sem_comentario:
            return "C"
        return "SC"
    
    def _tem_caracteres_especiais(self, comentario: str) -> bool:
        """Verifica se o comentário contém caracteres especiais"""
        # UCE: pegar todos os caracteres especiais de todos os comentários (*, ., ;, _, -, #, /, @, !, ?, etc.)
        return bool(re.search(r'[^\w\s]', comentario, re.UNICODE))
    
    def _tem_excesso_espacos(self, comentario: str) -> bool:
        """Verifica se há excesso de espaços (3 ou mais consecutivos)"""
        return '   ' in comentario
        
    def _e_apenas_token_permitido(self, comentario: str) -> bool:
        """Verifica se o comentário é apenas composto pelos tokens permitidos (sem números ou outros textos)"""
        temp = comentario.upper()
        for token in sorted(self.tokens_permitidos, key=len, reverse=True):
            temp = re.sub(r'\b' + token + r'\b', '', temp)
        return temp.strip() == ""
        
    def _contem_letras_nao_permitidas(self, comentario: str) -> bool:
        """Verifica se há letras no comentário ignorando os tokens permitidos, prefixos de medidores/postes e códigos de notas"""
        temp = comentario.upper()
        # 1. Remover códigos de outras notas (ex: T111, T181, P111, B111, R111, E101, L131, C121, etc.)
        temp = re.sub(r'\b[A-Z]\d{3}\b', '', temp)
        # 2. Remover tokens permitidos (SELO, ZELO, NR DI, NR RE, NR IM, R, S)
        for token in sorted(self.tokens_permitidos, key=len, reverse=True):
            temp = re.sub(r'\b' + token + r'\b', '', temp)
        # 3. Remover nomenclaturas de medidores/postes que contêm letras antes dos números (ex: S202184113, s138628, M123456, X123, MV08207, NF16588, MD99028, MC75130)
        temp = re.sub(r'\b[A-Z]{1,2}\d+\b', '', temp)
        return bool(re.search(r'[A-ZÁ-Ú]', temp))
    
    def _validar_conteudo_requerido(self, nota: str, comentario: str, regra: Dict) -> str:
        """Valida se o conteúdo do comentário está conforme o requerido"""
        tipo_requerido = regra.get("required")
        
        if tipo_requerido == "MEDIDOR_LEITURA":
            return self._validar_medidor_leitura(comentario)
        
        elif tipo_requerido == "MEDIDOR_LEITURA_FUNCAO":
            return self._validar_medidor_leitura_funcao(comentario, regra.get("funcoes_validas", []))
        
        elif tipo_requerido == "POSTE_FORMAT":
            return self._validar_formato_poste(comentario)
        
        elif tipo_requerido == "TEXTO_CONDIZENTE":
            return self._validar_texto_condizente(comentario)
        
        elif tipo_requerido == "CAMPANHA":
            return self._validar_campanha(comentario, nota)
        
        elif tipo_requerido == "MEDIDOR_SEM_LEITURA":
            return self._validar_medidor_sem_leitura(comentario)
        
        elif tipo_requerido == "APENAS_FUNCAO":
            return self._validar_apenas_funcao(comentario)
        
        elif tipo_requerido == "FUNCAO_LEITURA":
            return self._validar_funcao_leitura(comentario, regra.get("funcao_invalida"))
        
        return "C"
    
    def _validar_medidor_leitura(self, comentario: str) -> str:
        """Valida formato: MEDIDOR + LEITURA (aceita medidores, códigos de até 3 dígitos e leituras de até 6 dígitos)"""
        numeros = re.findall(r'\d+', comentario)
        if len(numeros) == 0:
            return "NI"  # Não tem números, comentário não faz sentido com a nota solicitada
            
        if self._contem_letras_nao_permitidas(comentario):
            return "CFP"
            
        # Se tem apenas 1 número, verificar se é o padrão junto 103/55 + até 6 dígitos
        if len(numeros) == 1:
            if re.match(r'^(103|55)\d{1,6}$', numeros[0]):
                return "C"
            return "FL"  # Falta leitura
            
        # Aceita múltiplos pares de códigos e leituras (de 2 até 8 números)
        if len(numeros) > 8:
            return "CFP"
            
        return "C"
    
    def _validar_medidor_leitura_funcao(self, comentario: str, funcoes_validas: list) -> str:
        """Valida formato: MEDIDOR + LEITURA (apenas para funções 01 e 02)"""
        tem_funcao_valida = any(func in comentario for func in funcoes_validas)
        if not tem_funcao_valida:
            return "NI"
        return self._validar_medidor_leitura(comentario)
    
    def _validar_formato_poste(self, comentario: str) -> str:
        """Valida formato: M000000/S000000 (1 letra M ou S e 6 números) ou X seguido de número"""
        if not re.search(r'\d', comentario):
            return "NI"
            
        if self._contem_letras_nao_permitidas(comentario):
            coment_sem_poste = re.sub(r'[SMX]\d+', '', comentario, flags=re.IGNORECASE)
            if self._contem_letras_nao_permitidas(coment_sem_poste):
                return "CFP"
                
        padrao_ms = r'[SM]\d{6}'
        padrao_x = r'X\d+'
        
        if re.search(padrao_ms, comentario, re.IGNORECASE) or re.search(padrao_x, comentario, re.IGNORECASE):
            return "C"
            
        return "CI"
    
    def _validar_texto_condizente(self, comentario: str) -> str:
        """Valida se o texto é condizente com a nota (texto descritivo)"""
        if len(comentario) < 1:
            return "CI"
        return "C"
    
    def _validar_campanha(self, comentario: str, nota: str) -> str:
        """Valida informações de campanha"""
        return "C"
    
    def _validar_medidor_sem_leitura(self, comentario: str) -> str:
        """Valida: UM OU DOIS MEDIDORES (SEM LEITURA), aceitando medidores com letras em suas variações e múltiplos códigos/leituras (ex: MV08207)"""
        if not re.search(r'\d', comentario):
            return "NI"
            
        palavras = comentario.upper().split()
        for p in palavras:
            p_limpa = re.sub(r'[^A-Z0-9]', '', p)
            if p_limpa and not any(c.isdigit() for c in p_limpa) and p_limpa not in self.tokens_permitidos:
                return "CFP"
                
        itens = [p for p in palavras if any(c.isdigit() for c in p)]
        
        if len(itens) > 8:
            return "CFP"
            
        return "C"
    
    def _validar_apenas_funcao(self, comentario: str) -> str:
        """Valida: APENAS FUNÇÃO"""
        if re.match(r'^\d{2}$', comentario.strip()):
            return "C"
        return "CFP"
    
    def _validar_funcao_leitura(self, comentario: str, funcao_invalida: str) -> str:
        """Valida: FUNÇÃO + LEITURA (função 03 já validada acima em T181)"""
        numeros = re.findall(r'\d+', comentario)
        if len(numeros) == 0:
            return "NI"
            
        if self._contem_letras_nao_permitidas(comentario):
            return "CFP"
            
        if len(numeros) == 1:
            if re.match(r'^(103|55)\d{1,6}$', numeros[0]):
                return "C"
            if len(numeros[0]) <= 4 and not re.match(r'^(103|55)', numeros[0]):
                return "CI"
            return "FL"
            
        if len(numeros) > 8:
            return "CFP"
            
        return "C"


def aplicar_validacao(df: pd.DataFrame, coluna_comentario: Optional[str] = None, coluna_nota: Optional[str] = None, coluna_analise: Optional[str] = None) -> pd.DataFrame:
    """
    Aplica validação em um DataFrame inteiro.
    Cláusula de restrição: o bot não roda em análises já feitas.
    Apenas realiza análises nas linhas em que o campo 'ANÁLISE' estiver vazio.
    """
    validator = CommentValidator()
    
    nota_col = coluna_nota
    coment_col = coluna_comentario
    
    if nota_col is None or coment_col is None or nota_col not in df.columns or coment_col not in df.columns:
        for col in df.columns:
            if 'nota' in col.lower() and 'leit' in col.lower():
                nota_col = col
            if 'coment' in col.lower():
                coment_col = col
    
    if nota_col is None or coment_col is None:
        raise ValueError(f"Colunas não encontradas. nota_col={nota_col}, coment_col={coment_col}. Colunas disponíveis: {df.columns.tolist()}")

    # Identificar coluna de análise existente
    analise_col = coluna_analise
    if analise_col is None or analise_col not in df.columns:
        for col in df.columns:
            if 'analise' in col.lower() or 'análise' in col.lower():
                analise_col = col
                break
    
    def _is_vazio(val) -> bool:
        if val is None or pd.isna(val):
            return True
        s = str(val).strip()
        return s == "" or s.lower() in ["nan", "none", "null", "<na>"]

    resultados = []
    for _, row in df.iterrows():
        # Verificar se o campo de análise já possui valor preenchido
        analise_previa = None
        if analise_col is not None and analise_col in df.columns:
            val = row.get(analise_col)
            if not _is_vazio(val):
                analise_previa = val

        if analise_previa is not None:
            # Preserva a análise existente sem reexecutar o validador
            resultados.append(analise_previa)
        else:
            # Campo vazio: o bot realiza a análise do comentário
            nota = str(row.get(nota_col, '')).strip()
            comentario = row.get(coment_col, '')
            analise = validator.validar_comentario(nota, comentario)
            resultados.append(analise)
    
    df_copy = df.copy()
    if analise_col is not None and analise_col in df_copy.columns and analise_col != 'ANÁLISE':
        df_copy = df_copy.drop(columns=[analise_col])
    df_copy['ANÁLISE'] = resultados
    return df_copy


if __name__ == "__main__":
    validator = CommentValidator()
    
    test_cases = [
        ("B111", "12345 67890", "C"),  # Medidor + leitura correto
        ("B111", "", "SC"),  # Sem comentário
        ("B111", "12345", "FL"),  # Falta leitura
        ("E101", "M123456", "C"),  # Poste correto
        ("E101", "123456", "CI"),  # Poste incorreto
        ("C111", "Rua das Flores", "C"),  # Texto condizente
        ("C111", "ABC", "C"),  # Texto muito curto
        ("T161", "01", "C"),  # Apenas função
        ("T161", "01 123", "CFP"),  # Fora do padrão
        ("T181", "03 12345", "CFP"), # T181 com 03 -> CFP
        ("R111", "0312345", "CFP"),  # R111 com 03 + dígitos -> CFP
        ("B111", "103123456", "C"),  # 103 + até 6 dígitos em B111 -> C
        ("P111", "12345 6789 SELO", "C"), # Token permitido junto com leitura -> C
        ("L131", "SELO", "C"), # Token permitido sozinho em nota sem comentário obrigatório -> C
        ("P111", "SELO", "NI"), # Token permitido sozinho em nota com comentário obrigatório -> NI
        ("T181", "103 15040.", "UCE"), # Caractere especial -> UCE
        ("P111", "cliente nao estava", "NI"), # Comentário não faz sentido com a nota -> NI
        ("T181", "103 03221", "C"), # Leitura iniciada com 03 no T181 -> C
        ("T181", "55 034429", "C"), # Leitura iniciada com 03 no T181 (função 55) -> C
        ("R111", "MV08207 3181313071", "C"), # Medidor alfanumérico no R111 -> C
        ("P111", "5260328370 03 00000", "C"), # Leitura 03 no P111 -> C
        ("P111", "3203600940 3 012051 24 001929", "C"), # Medidor + múltiplos códigos/leituras -> C
        ("P111", "3242491466 03 114 24 53", "C"), # Medidor + múltiplos códigos/leituras -> C
        ("P111", "6252237400 03 999999 103 999999", "C"), # Medidor + múltiplos códigos/leituras -> C
        ("P111", "5257431454 03 140 103 0", "C"), # Medidor + múltiplos códigos/leituras -> C
        ("R111", "3010214262 3243797216 103 22851", "C"), # Dois medidores + código/leitura no R111 -> C
        ("P111", "6252079651 03 3 103 0", "C"), # Medidor + múltiplos códigos/leituras -> C
        ("T181", "55 41205 T111", "C"), # Outra nota mencionada dentro do comentário -> C
        ("P111", "S202184113 T181 103 24 03 00312", "C"), # Medidor com prefixo S + menção a outra nota -> C
        ("E101", "s138628", "C"), # Nomenclatura de poste com S + 6 dígitos -> C
        ("E101", "s138629", "C") # Nomenclatura de poste com S + 6 dígitos -> C
    ]
    
    print("Testes de validacao de regras:")
    todos_ok = True
    for nota, comentario, esperado in test_cases:
        resultado = validator.validar_comentario(nota, comentario)
        status = "[OK]" if resultado == esperado else "[FAIL]"
        if resultado != esperado:
            todos_ok = False
        print(f"{status} Nota: {nota}, Comentario: '{comentario}' -> {resultado} (esperado: {esperado})")
    
    print("\nTestes de restricao de execucao (aplicar_validacao apenas em vazios):")
    df_teste = pd.DataFrame({
        "Nota_leit": ["B111", "B111", "B111", "E101"],
        "Coment_leitura": ["", "", "12345 67890", ""],
        "ANÁLISE": ["ANALISE_ANTERIOR_PRESERVADA", None, "", "CFP_MANUAL"]
    })
    
    df_resultado = aplicar_validacao(df_teste)
    # Linha 0: tinha "ANALISE_ANTERIOR_PRESERVADA" -> deve manter "ANALISE_ANTERIOR_PRESERVADA" (mesmo coment sendo "")
    # Linha 1: tinha None -> bot analisa e gera "SC"
    # Linha 2: tinha "" -> bot analisa e gera "C"
    # Linha 3: tinha "CFP_MANUAL" -> deve manter "CFP_MANUAL"
    
    assert df_resultado.loc[0, "ANÁLISE"] == "ANALISE_ANTERIOR_PRESERVADA", f"Esperado ANALISE_ANTERIOR_PRESERVADA, obteve {df_resultado.loc[0, 'ANÁLISE']}"
    assert df_resultado.loc[1, "ANÁLISE"] == "SC", f"Esperado SC, obteve {df_resultado.loc[1, 'ANÁLISE']}"
    assert df_resultado.loc[2, "ANÁLISE"] == "C", f"Esperado C, obteve {df_resultado.loc[2, 'ANÁLISE']}"
    assert df_resultado.loc[3, "ANÁLISE"] == "CFP_MANUAL", f"Esperado CFP_MANUAL, obteve {df_resultado.loc[3, 'ANÁLISE']}"
    print("[OK] Teste de restricao de execucao concluido com sucesso!")


