"""
Script principal para validação de comentários usando regras de negócio.
Substitui os modelos de ML por validação baseada em regras específicas.
"""

import pandas as pd
import sys
import os

# Adicionar o diretório src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.validation_rules import CommentValidator, aplicar_validacao


def normalizar_colunas(df):
    """Normaliza nomes das colunas"""
    df.columns = [str(col).strip().replace('\n', '').replace('\r', '').replace('.', '').replace(' ', '_') for col in df.columns]
    return df


def carregar_dados(caminho_arquivo, aba_excel=None, header_row=0):
    """Carrega dados CSV ou Excel (incluindo .xlsm)"""
    print(f"Carregando dados de: {caminho_arquivo}")
    
    if caminho_arquivo.endswith('.xlsx') or caminho_arquivo.endswith('.xls') or caminho_arquivo.endswith('.xlsm'):
        # Carregar Excel (incluindo .xlsm com macros)
        xls = pd.ExcelFile(caminho_arquivo)
        print(f"Abas disponíveis: {xls.sheet_names}")
        
        if aba_excel and aba_excel in xls.sheet_names:
            df = pd.read_excel(caminho_arquivo, sheet_name=aba_excel, header=header_row, dtype={"Nº_Serie": str})
            print(f"Aba Excel carregada: {aba_excel}")
        elif aba_excel:
            print(f"Aba '{aba_excel}' não encontrada. Usando primeira aba disponível.")
            df = pd.read_excel(caminho_arquivo, header=header_row, dtype={"Nº_Serie": str})
            print(f"Primeira aba Excel carregada: {xls.sheet_names[0]}")
        else:
            df = pd.read_excel(caminho_arquivo, header=header_row, dtype={"Nº_Serie": str})
            print(f"Primeira aba Excel carregada: {xls.sheet_names[0]}")
    else:
        # Carregar CSV
        df = pd.read_csv(caminho_arquivo, sep=';', dtype={"Nº_Serie": str})
    
    # Normalizar colunas APÓS carregar com header correto
    df = normalizar_colunas(df)
    
    # Filtrar linhas com Data válida (se existir a coluna)
    if "Data" in df.columns:
        df = df[df["Data"].notnull() & (df["Data"] != "")]
    
    print(f"Total de linhas carregadas: {len(df)}")
    return df


def validar_arquivo(caminho_entrada, caminho_saida, aba_excel=None, header_row=0):
    """
    Valida comentários de um arquivo e salva o resultado.
    
    Args:
        caminho_entrada: Caminho do CSV/Excel de entrada
        caminho_saida: Caminho do Excel de saída
        aba_excel: Nome da aba Excel (opcional)
        header_row: Linha do cabeçalho (padrão: 0)
    """
    # Carregar dados
    df = carregar_dados(caminho_entrada, aba_excel, header_row)
    
    # Encontrar coluna de análise (pode ter nomes diferentes após normalização)
    analise_col = None
    for col in df.columns:
        if 'analise' in col.lower() or 'análise' in col.lower():
            analise_col = col
            break
    
    # Encontrar coluna de nota para preservar a análise de L121
    nota_col = None
    for col in df.columns:
        if 'nota' in col.lower() and 'leit' in col.lower():
            nota_col = col
            break
            
    if analise_col is None:
        print("Coluna ANÁLISE não encontrada. Colunas disponíveis:")
        print(df.columns.tolist())
        # Criar coluna ANÁLISE vazia
        df['ANÁLISE'] = None
        analise_col = 'ANÁLISE'
    else:
        print(f"Coluna de análise encontrada: {analise_col}")
        # Renomear para padronizar
        df = df.rename(columns={analise_col: 'ANÁLISE'})
        analise_col = 'ANÁLISE'
    
    # Estatísticas antes da validação (cláusula de restrição: apenas vazios são analisados)
    def _is_vazio_series(s):
        return s.isna() | (s.astype(str).str.strip() == '') | (s.astype(str).str.strip().str.lower().isin(['nan', 'none', 'null', '<na>']))

    mask_vazio = _is_vazio_series(df['ANÁLISE'])
    linhas_vazias = int(mask_vazio.sum())
    linhas_preenchidas = len(df) - linhas_vazias

    print("\n=== Estatísticas antes da validação ===")
    print(f"Total de linhas: {len(df)}")
    print(f"Linhas com ANÁLISE já preenchida (serão preservadas): {linhas_preenchidas}")
    print(f"Linhas com ANÁLISE vazia (serão analisadas pelo bot): {linhas_vazias}")
    
    if linhas_preenchidas > 0:
        print("\nDistribuição das análises existentes (mantidas):")
        print(df.loc[~mask_vazio, 'ANÁLISE'].value_counts())
    
    # Aplicar validação
    print("\n=== Aplicando validação baseada em regras ===")
    df_validado = aplicar_validacao(df)
    
    # Estatísticas depois da validação
    print("\n=== Estatísticas após validação ===")
    print(f"Total de linhas: {len(df_validado)}")
    print("\nDistribuição de ANÁLISE:")
    print(df_validado['ANÁLISE'].value_counts())
    
    # Salvar resultado
    df_validado.to_excel(caminho_saida, index=False)
    print(f"\nResultado salvo em: {caminho_saida}")
    
    return df_validado


def analisar_por_nota(df):
    """Analisa a distribuição de análises por tipo de nota"""
    print("\n=== Análise por tipo de nota ===")
    
    # Encontrar a coluna de nota (pode ter nomes diferentes após normalização)
    nota_col = None
    for col in df.columns:
        if 'nota' in col.lower() and 'leit' in col.lower():
            nota_col = col
            break
    
    if nota_col is None:
        print("Coluna de nota não encontrada. Colunas disponíveis:")
        print(df.columns.tolist())
        return
    
    print(f"Usando coluna de nota: {nota_col}")
    
    # Agrupar por nota e análise
    analise_por_nota = df.groupby([nota_col, 'ANÁLISE']).size().unstack(fill_value=0)
    
    print(analise_por_nota)
    
    # Identificar notas com mais problemas
    print("\n=== Notas com maior número de não conformes ===")
    nao_conformes = df[df['ANÁLISE'] != 'C'].groupby(nota_col).size().sort_values(ascending=False)
    print(nao_conformes.head(10))


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validar comentários de leitura baseado em regras de negócio')
    parser.add_argument('--input', '-i', required=True, help='Arquivo CSV/Excel de entrada')
    parser.add_argument('--output', '-o', required=True, help='Arquivo Excel de saída')
    parser.add_argument('--sheet', '-s', default='Aud_Coment_Geral', help='Nome da aba Excel (padrão: Aud_Coment_Geral)')
    parser.add_argument('--header', '-r', type=int, default=0, help='Linha do cabeçalho (padrão: 0)')
    parser.add_argument('--analyze', '-a', action='store_true', help='Mostrar análise detalhada por nota')
    
    args = parser.parse_args()
    
    # Validar arquivo
    df_validado = validar_arquivo(args.input, args.output, args.sheet, args.header)
    
    # Análise adicional se solicitado
    if args.analyze:
        analisar_por_nota(df_validado)


if __name__ == "__main__":
    # Exemplo de uso direto (sem argumentos de linha de comando)
    if len(sys.argv) == 1:
        print("=== Executando validação no arquivo de exemplo ===")
        input_file = "data/new/mvc_0003_AGO_01.csv"
        output_file = "validado_regras_negocio.xlsx"
        
        if os.path.exists(input_file):
            df = validar_arquivo(input_file, output_file)
            analisar_por_nota(df)
        else:
            print(f"Arquivo não encontrado: {input_file}")
            print("\nUso para Excel:")
            print("python src/validar_comentarios.py --input arquivo.xlsx --output saida.xlsx --sheet Aud_Coment_Geral")
            print("\nUso para CSV:")
            print("python src/validar_comentarios.py --input arquivo.csv --output saida.xlsx")
    else:
        main()
