import os
import sys
import time
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QLineEdit,
    QPushButton, QProgressBar, QVBoxLayout, QHBoxLayout, QGridLayout,
    QStackedWidget, QScrollArea, QFileDialog, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QIcon, QDesktopServices

# Adicionar o diretório raiz e o subdiretório src ao PATH de forma segura para PyInstaller e dev
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)
src_dir = os.path.join(base_dir, 'src')
if os.path.exists(src_dir):
    sys.path.insert(0, src_dir)

# Importação resiliente de regras de validação para modo CLI e modo PyInstaller (.exe / macOS app)
aplicar_validacao_func = None
try:
    from src.validation_rules import aplicar_validacao
    aplicar_validacao_func = aplicar_validacao
except ImportError:
    try:
        from validation_rules import aplicar_validacao
        aplicar_validacao_func = aplicar_validacao
    except ImportError as err:
        print(f"Aviso ao importar validation_rules: {err}")

try:
    from src.validar_comentarios import carregar_dados, normalizar_colunas
except ImportError:
    try:
        from validar_comentarios import carregar_dados, normalizar_colunas
    except ImportError:
        pass


class RaisedGlassCard(QFrame):
    """Card com elevação e profundidade visual estilizado via PySide6 / QSS"""
    def __init__(self, parent=None, bg_color="#181A24", border_color="#282C3E", border_radius=18):
        super().__init__(parent)
        self.setObjectName("RaisedGlassCard")
        self.setStyleSheet(f"""
            QFrame#RaisedGlassCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {border_radius}px;
            }}
        """)


class MetricBadge(QFrame):
    """Badge indicador de status e métricas operacionais"""
    def __init__(self, parent=None, label="", value="-", color="#3B82F6"):
        super().__init__(parent)
        self.setObjectName("MetricBadge")
        self.setStyleSheet("""
            QFrame#MetricBadge {
                background-color: #14161F;
                border: 1px solid #252838;
                border-radius: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_lbl = QLabel(label, self)
        self.label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_lbl.setStyleSheet("color: #8E93B0; font-size: 12px; font-weight: bold; border: none; background: transparent;")

        self.value_lbl = QLabel(str(value), self)
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold; border: none; background: transparent;")

        layout.addWidget(self.label_lbl)
        layout.addWidget(self.value_lbl)

    def update_value(self, value):
        self.value_lbl.setText(str(value))


class ValidationWorker(QThread):
    """Thread de processamento em segundo plano para auditoria operacional de planilhas"""
    progress_signal = Signal(float, str, str)  # percent, status, detail
    success_signal = Signal(dict, float, str, int)  # dist_dict, elapsed, output_path, total_rows
    error_signal = Signal(str)  # error_message

    def __init__(self, file_path, sheet_name, output_path):
        super().__init__()
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.output_path = output_path

    def run(self):
        start_time = time.time()
        try:
            aba = self.sheet_name.strip() or None
            self.progress_signal.emit(0.25, "Carregando dados da planilha...", "Lendo estrutura de dados na memória do sistema...")

            try:
                from src.validar_comentarios import carregar_dados
                df = carregar_dados(self.file_path, aba)
            except Exception:
                if self.file_path.endswith('.xlsx') or self.file_path.endswith('.xls') or self.file_path.endswith('.xlsm'):
                    xls = pd.ExcelFile(self.file_path)
                    aba_use = aba if aba and aba in xls.sheet_names else xls.sheet_names[0]
                    df = pd.read_excel(self.file_path, sheet_name=aba_use, dtype={"Nº_Serie": str})
                else:
                    df = pd.read_csv(self.file_path, sep=';', dtype={"Nº_Serie": str})
                df.columns = [str(col).strip().replace('\n', '').replace('\r', '').replace('.', '').replace(' ', '_') for col in df.columns]

            analise_col = None
            for col in df.columns:
                if 'analise' in col.lower() or 'análise' in col.lower():
                    analise_col = col
                    break

            nota_col = None
            for col in df.columns:
                if 'nota' in col.lower() and 'leit' in col.lower():
                    nota_col = col
                    break

            if analise_col is None:
                df['ANÁLISE'] = None
                analise_col = 'ANÁLISE'
            else:
                df = df.rename(columns={analise_col: 'ANÁLISE'})
                analise_col = 'ANÁLISE'

            # Cláusula de restrição: o bot só analisa registros onde o campo 'ANÁLISE' estiver vazio
            def _is_vazio_series(s):
                return s.isna() | (s.astype(str).str.strip() == '') | (s.astype(str).str.strip().str.lower().isin(['nan', 'none', 'null', '<na>']))

            mask_vazio = _is_vazio_series(df['ANÁLISE'])
            total_pendentes = int(mask_vazio.sum())
            total_mantidos = len(df) - total_pendentes

            if total_mantidos > 0:
                status_msg = f"Analisando {total_pendentes:,} registros pendentes..."
                detalhe_msg = f"{total_mantidos:,} análises pré-existentes preservadas intactas."
            else:
                status_msg = f"Analisando {len(df):,} comentários com Regras Operacionais..."
                detalhe_msg = "Verificando prefixos S, notas no texto, limites e formatações de poste..."

            self.progress_signal.emit(
                0.50,
                status_msg,
                detalhe_msg
            )

            # Aplicar validação por regras de forma resiliente
            func_val = aplicar_validacao_func
            if func_val is None:
                try:
                    from src.validation_rules import aplicar_validacao as func_val
                except ImportError:
                    from validation_rules import aplicar_validacao as func_val

            try:
                df = func_val(df, coluna_comentario='Coment_leitura', coluna_nota='Nota_leit', coluna_analise='ANÁLISE')
            except TypeError:
                df = func_val(df)

            self.progress_signal.emit(
                0.75,
                "Gravando planilha Excel validada na mesma pasta...",
                "Salvando todas as classificações e indicadores gerados..."
            )

            df.to_excel(self.output_path, index=False)

            elapsed = round(time.time() - start_time, 1)
            dist = df['ANÁLISE'].value_counts().to_dict()

            if total_mantidos > 0:
                detalhe_concluido = f"Concluído! {total_pendentes:,} analisados, {total_mantidos:,} mantidos. Salvo em: {self.output_path}"
            else:
                detalhe_concluido = f"Planilha gravada perfeitamente em: {self.output_path}"

            self.progress_signal.emit(
                1.00,
                f"✔ Auditoria Concluída com Sucesso em {elapsed}s!",
                detalhe_concluido
            )

            self.success_signal.emit(dist, elapsed, self.output_path, len(df))

        except Exception as e:
            self.error_signal.emit(str(e))


class AuditorComentariosApp(QMainWindow):
    """Painel principal de Auditoria de Registros Operacionais em PySide6 - Paleta Azul Escuro Navy & Sidebar Funcional"""
    def __init__(self):
        super().__init__()

        # Configuração da Janela Principal
        self.setWindowTitle("Auditoria de Registros Operacionais — Sistema de Validação")
        self.resize(1080, 760)
        self.setMinimumSize(940, 660)

        # Ícone da aplicação
        icon_path = os.path.join(base_dir, 'assets', 'app_icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Estilo Global (Dark Navy Blue Palette)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F111A;
            }
            QWidget {
                color: #FFFFFF;
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #0F111A;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #222636;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #33394E;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Estado da Aplicação
        self.selected_file_path = ""
        self.sheet_name = "Aud_Coment_Geral"
        self.output_file_path = ""
        self.is_processing = False

        # Histórico de Sessão
        self.last_run_time = "Nenhuma auditoria executada nesta sessão"
        self.last_total_rows = 0
        self.last_elapsed_secs = 0.0

        # Central Widget & Layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar (Lateral Esquerdo)
        sidebar = self._build_sidebar()
        main_layout.addWidget(sidebar)

        # 2. Main Stacked Container (Painel Central Multifuncional)
        self.stacked_widget = QStackedWidget(self)
        main_layout.addWidget(self.stacked_widget, stretch=1)

        # Views
        self.views = {}
        self.views["visao_geral"] = self._create_visao_geral_view()
        self.views["planilhas"] = self._create_planilhas_view()
        self.views["historico"] = self._create_historico_view()

        for key in ["visao_geral", "planilhas", "historico"]:
            self.stacked_widget.addWidget(self.views[key])

        self._switch_view("visao_geral")

    def _build_sidebar(self):
        sidebar_frame = QFrame(self)
        sidebar_frame.setFixedWidth(240)
        sidebar_frame.setStyleSheet("""
            QFrame {
                background-color: #14161F;
                border-right: 1px solid #222636;
            }
        """)

        layout = QVBoxLayout(sidebar_frame)
        layout.setContentsMargins(16, 26, 16, 20)
        layout.setSpacing(10)

        # Logo e Identidade
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(4, 0, 4, 10)
        logo_layout.setSpacing(12)

        icon_lbl = QLabel("⬡", sidebar_frame)
        icon_lbl.setFixedSize(42, 42)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("""
            QLabel {
                background-color: #1E2A4A;
                color: #3B82F6;
                font-size: 24px;
                font-weight: bold;
                border-radius: 12px;
                border: none;
            }
        """)
        logo_layout.addWidget(icon_lbl)

        title_lbl = QLabel("Auditoria de\nRegistros Operacionais", sidebar_frame)
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        logo_layout.addWidget(title_lbl, stretch=1)

        layout.addLayout(logo_layout)

        # Divisor
        divider = QFrame(sidebar_frame)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #222636; border: none;")
        layout.addWidget(divider)
        layout.addSpacing(10)

        # Navigation Buttons
        self.nav_buttons = {}
        nav_configs = [
            ("visao_geral", "⚡ Visão Geral"),
            ("planilhas", "📁 Planilha & Pastas"),
            ("historico", "📊 Histórico Auditoria"),
        ]

        for tab_id, text in nav_configs:
            btn = QPushButton(text, sidebar_frame)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, tid=tab_id: self._switch_view(tid))
            layout.addWidget(btn)
            self.nav_buttons[tab_id] = btn

        layout.addStretch(1)

        # Card de informações operacionais na parte inferior do sidebar
        info_card = RaisedGlassCard(sidebar_frame, bg_color="#11131C", border_color="#222636", border_radius=14)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(4)

        info_title = QLabel("Auditoria Operacional v2.1", info_card)
        info_title.setStyleSheet("color: #D8DBE8; font-size: 12px; font-weight: bold; border: none; background: transparent;")
        info_desc = QLabel("Paleta Azul Escuro Navy,\nregras de negócio dinâmicas\ne checagem em background.", info_card)
        info_desc.setStyleSheet("color: #6C728E; font-size: 11px; border: none; background: transparent;")

        info_layout.addWidget(info_title)
        info_layout.addWidget(info_desc)

        layout.addWidget(info_card)
        return sidebar_frame

    def _switch_view(self, tab_id):
        self.current_tab = tab_id
        for tid, btn in self.nav_buttons.items():
            if tid == tab_id:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1E3A8A;
                        color: #FFFFFF;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 12px;
                        text-align: left;
                        padding-left: 14px;
                        border: none;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #8E93B0;
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 12px;
                        text-align: left;
                        padding-left: 14px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #1E2436;
                        color: #FFFFFF;
                    }
                """)

        view_index = list(self.views.keys()).index(tab_id)
        self.stacked_widget.setCurrentIndex(view_index)

        if tab_id == "historico":
            self._update_historico_view()

    # =========================================================================
    # VIEW 1: VISÃO GERAL
    # =========================================================================
    def _create_visao_geral_view(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # Header
        header_lbl = QLabel("Auditoria Operacional de Comentários", container)
        header_lbl.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: bold; background: transparent;")
        sub_lbl = QLabel("Selecione a planilha Excel ou CSV para processar todas as regras operacionais instantaneamente.", container)
        sub_lbl.setStyleSheet("color: #8E93B0; font-size: 13px; background: transparent;")
        layout.addWidget(header_lbl)
        layout.addWidget(sub_lbl)

        # CARD 1: SELEÇÃO DA PLANILHA
        file_card = RaisedGlassCard(container, bg_color="#181A24", border_color="#282C3E", border_radius=18)
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(22, 16, 22, 16)
        file_layout.setSpacing(12)

        file_card_title = QLabel("Arquivo de Auditoria (.xlsx, .xlsm, .csv)", file_card)
        file_card_title.setStyleSheet("color: #D8DBE8; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        file_layout.addWidget(file_card_title)

        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self.file_entry = QLineEdit(file_card)
        self.file_entry.setPlaceholderText("Nenhum arquivo carregado... Clique em 'Selecionar Planilha'")
        self.file_entry.setFixedHeight(46)
        self.file_entry.setStyleSheet("""
            QLineEdit {
                background-color: #0F111A;
                border: 1px solid #25293A;
                border-radius: 12px;
                padding-left: 14px;
                color: #FFFFFF;
                font-size: 13px;
            }
        """)
        input_row.addWidget(self.file_entry, stretch=1)

        select_btn = QPushButton("📁 Selecionar Planilha", file_card)
        select_btn.setFixedSize(175, 46)
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #1D4ED8;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                border-radius: 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1E40AF;
            }
        """)
        select_btn.clicked.connect(self._select_file)
        input_row.addWidget(select_btn)
        file_layout.addLayout(input_row)

        # Opções de Aba
        options_box = QFrame(file_card)
        options_box.setStyleSheet("""
            QFrame {
                background-color: #12141D;
                border: 1px solid #222636;
                border-radius: 12px;
            }
        """)
        options_layout = QHBoxLayout(options_box)
        options_layout.setContentsMargins(16, 10, 16, 10)
        options_layout.setSpacing(12)

        opt_lbl = QLabel("Nome da Aba Excel:", options_box)
        opt_lbl.setStyleSheet("color: #A0A5C0; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        options_layout.addWidget(opt_lbl)

        self.sheet_entry = QLineEdit(self.sheet_name, options_box)
        self.sheet_entry.setFixedHeight(36)
        self.sheet_entry.setStyleSheet("""
            QLineEdit {
                background-color: #181A24;
                border: 1px solid #282C3E;
                border-radius: 8px;
                padding-left: 10px;
                color: #FFFFFF;
                font-size: 13px;
            }
        """)
        self.sheet_entry.textChanged.connect(self._on_sheet_name_changed)
        options_layout.addWidget(self.sheet_entry, stretch=1)

        file_layout.addWidget(options_box)
        layout.addWidget(file_card)

        # CARD 2: STATUS E PROGRESSO
        self.progress_card = RaisedGlassCard(container, bg_color="#181A24", border_color="#282C3E", border_radius=18)
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.setContentsMargins(22, 16, 22, 16)
        progress_layout.setSpacing(10)

        self.status_lbl = QLabel("Pronto para iniciar auditoria operacional", self.progress_card)
        self.status_lbl.setStyleSheet("color: #A0A5C0; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        progress_layout.addWidget(self.status_lbl)

        self.progress_bar = QProgressBar(self.progress_card)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0F111A;
                border-radius: 5px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 5px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)

        self.progress_detail_lbl = QLabel("Aguardando seleção de planilha para análise de regras operacionais", self.progress_card)
        self.progress_detail_lbl.setStyleSheet("color: #6C728E; font-size: 12px; border: none; background: transparent;")
        progress_layout.addWidget(self.progress_detail_lbl)

        layout.addWidget(self.progress_card)

        # CARD 3: DASHBOARD DE MÉTRICAS
        self.results_card = RaisedGlassCard(container, bg_color="#181A24", border_color="#282C3E", border_radius=18)
        results_layout = QVBoxLayout(self.results_card)
        results_layout.setContentsMargins(22, 16, 22, 16)
        results_layout.setSpacing(12)

        metrics_title = QLabel("Indicadores e Distribuição da Auditoria", self.results_card)
        metrics_title.setStyleSheet("color: #D8DBE8; font-size: 15px; font-weight: bold; border: none; background: transparent;")
        results_layout.addWidget(metrics_title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        self.badges = {}
        metric_configs = [
            ("Conforme (C)", "C", "#2ECC71", 0, 0, 1, 1),
            ("Fora Padrão (CFP)", "CFP", "#E74C3C", 0, 1, 1, 1),
            ("Sem Coment. (SC)", "SC", "#F39C12", 0, 2, 1, 1),
            ("Falta Leitura (FL)", "FL", "#9B59B6", 0, 3, 1, 1),
            ("Nota Incorreta (NI)", "NI", "#FF5C4D", 1, 0, 1, 1),
            ("Espaço Exc. (EE)", "EE", "#3498DB", 1, 1, 1, 1),
            ("Coment. Inc. (CI)", "CI", "#F1C40F", 1, 2, 1, 1),
            ("Caractere Esp. (UCE)", "UCE", "#E67E22", 1, 3, 1, 1),
            ("% Inconf. / Conforme", "RAZAO_INCONF_C", "#F39C12", 2, 1, 1, 2),
        ]

        for label, key, color, r, c, rspan, cspan in metric_configs:
            badge = MetricBadge(self.results_card, label=label, value="-", color=color)
            grid_layout.addWidget(badge, r, c, rspan, cspan)
            self.badges[key] = badge

        results_layout.addLayout(grid_layout)
        layout.addWidget(self.results_card)

        # RODAPÉ DE AÇÃO
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(14)

        self.action_btn = QPushButton("▶ Executar Auditoria e Gerar Planilha", container)
        self.action_btn.setFixedHeight(52)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setStyleSheet("""
            QPushButton {
                background-color: #1D4ED8;
                color: #FFFFFF;
                font-size: 15px;
                font-weight: bold;
                border-radius: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1E40AF;
            }
            QPushButton:disabled {
                background-color: #1E2436;
                color: #6C728E;
            }
        """)
        self.action_btn.clicked.connect(self._start_validation_thread)
        footer_layout.addWidget(self.action_btn, stretch=1)

        self.open_excel_btn = QPushButton("📁 Abrir Planilha Validada", container)
        self.open_excel_btn.setFixedHeight(52)
        self.open_excel_btn.setFixedWidth(210)
        self.open_excel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_excel_btn.setEnabled(False)
        self.open_excel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E2436;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                border-radius: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2A324A;
            }
            QPushButton:disabled {
                background-color: #14161F;
                color: #4A4E69;
            }
        """)
        self.open_excel_btn.clicked.connect(self._open_generated_file)
        footer_layout.addWidget(self.open_excel_btn)

        layout.addLayout(footer_layout)
        return scroll

    def _on_sheet_name_changed(self, text):
        self.sheet_name = text.strip()
        self._update_planilha_info()

    # =========================================================================
    # VIEW 2: PLANILHAS & PASTAS
    # =========================================================================
    def _create_planilhas_view(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        header_lbl = QLabel("Gestão de Planilhas e Diretórios de Saída", container)
        header_lbl.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: bold; background: transparent;")
        layout.addWidget(header_lbl)

        card = RaisedGlassCard(container, bg_color="#181A24", border_color="#282C3E", border_radius=18)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(14)

        card_title = QLabel("Detalhes dos Arquivos de Origem e Validado", card)
        card_title.setStyleSheet("color: #D8DBE8; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        card_layout.addWidget(card_title)

        self.planilha_info_lbl = QLabel(
            "Nenhum arquivo selecionado no momento.\nVá em 'Visão Geral' e selecione sua planilha de auditoria.",
            card
        )
        self.planilha_info_lbl.setStyleSheet("color: #8E93B0; font-size: 13px; border: none; background: transparent;")
        card_layout.addWidget(self.planilha_info_lbl)

        btn_box = QHBoxLayout()
        open_folder_btn = QPushButton("📂 Abrir Pasta de Destino no Finder / Explorer", card)
        open_folder_btn.setFixedHeight(44)
        open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E3A8A;
                color: #FFFFFF;
                font-size: 13px;
                font-weight: bold;
                border-radius: 12px;
                padding-left: 16px;
                padding-right: 16px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        open_folder_btn.clicked.connect(self._open_target_folder)
        btn_box.addWidget(open_folder_btn)
        btn_box.addStretch(1)

        card_layout.addLayout(btn_box)
        layout.addWidget(card)
        layout.addStretch(1)

        return scroll

    def _update_planilha_info(self):
        if self.selected_file_path:
            info_text = (
                f"📄 Arquivo Origem:\n{self.selected_file_path}\n\n"
                f"📑 Aba Excel Selecionada:\n{self.sheet_name}\n\n"
                f"💾 Arquivo Validado a Gerar:\n{self.output_file_path}"
            )
            self.planilha_info_lbl.setText(info_text)
            self.planilha_info_lbl.setStyleSheet("color: #D8DBE8; font-size: 13px; border: none; background: transparent;")

    # =========================================================================
    # VIEW 3: HISTÓRICO DA AUDITORIA
    # =========================================================================
    def _create_historico_view(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        header_lbl = QLabel("Histórico e Resumo de Performance da Sessão", container)
        header_lbl.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: bold; background: transparent;")
        layout.addWidget(header_lbl)

        card = RaisedGlassCard(container, bg_color="#181A24", border_color="#282C3E", border_radius=18)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 24, 22, 24)

        self.historico_txt_lbl = QLabel(
            "Nenhuma execução realizada até o momento nesta sessão aberta do aplicativo.",
            card
        )
        self.historico_txt_lbl.setStyleSheet("color: #8E93B0; font-size: 14px; border: none; background: transparent;")
        card_layout.addWidget(self.historico_txt_lbl)

        layout.addWidget(card)
        layout.addStretch(1)
        return scroll

    def _update_historico_view(self):
        if self.last_total_rows > 0:
            msg = (
                f"🕒 Última Execução Realizada em: {self.last_run_time}\n\n"
                f"📊 Total de Linhas Analisadas: {self.last_total_rows:,} comentários\n"
                f"⚡ Tempo Total de Processamento: {self.last_elapsed_secs} segundos\n"
                f"📁 Planilha de Saída Gravada: {self.output_file_path}"
            )
            self.historico_txt_lbl.setText(msg)
            self.historico_txt_lbl.setStyleSheet("color: #D8DBE8; font-size: 14px; border: none; background: transparent;")

    # =========================================================================
    # AÇÕES DO SISTEMA E PROCESSAMENTO EM THREAD
    # =========================================================================
    def _select_file(self):
        if self.is_processing:
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione a Planilha de Auditoria",
            "",
            "Arquivos Excel / CSV (*.xlsx *.xlsm *.xls *.csv);;Todos os Arquivos (*.*)"
        )
        if file_path:
            self.selected_file_path = file_path
            self.file_entry.setText(file_path)
            base_dir_path = os.path.dirname(file_path)
            file_name, _ = os.path.splitext(os.path.basename(file_path))
            self.output_file_path = os.path.join(base_dir_path, f"{file_name}_VALIDADO.xlsx")

            self.status_lbl.setText(f"Planilha selecionada: {os.path.basename(file_path)}")
            self.status_lbl.setStyleSheet("color: #2ECC71; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.progress_detail_lbl.setText(f"Destino de saída: {self.output_file_path}")

            self._update_planilha_info()

    def _open_target_folder(self):
        target_path = self.selected_file_path or self.output_file_path
        if target_path and os.path.exists(target_path):
            folder = os.path.dirname(target_path)
        else:
            folder = os.path.abspath(".")
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _start_validation_thread(self):
        if self.is_processing:
            return
        file_path = self.file_entry.text().strip()
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Atenção", "Por favor, selecione um arquivo válido antes de executar a análise.")
            return

        self.selected_file_path = file_path
        if not self.output_file_path:
            base_dir_path = os.path.dirname(file_path)
            file_name, _ = os.path.splitext(os.path.basename(file_path))
            self.output_file_path = os.path.join(base_dir_path, f"{file_name}_VALIDADO.xlsx")

        self.is_processing = True
        self.action_btn.setEnabled(False)
        self.action_btn.setText("⏳ Processando Regras Operacionais...")
        self.open_excel_btn.setEnabled(False)

        self.progress_bar.setValue(10)
        self.status_lbl.setText("Carregando planilha e normalizando colunas...")
        self.status_lbl.setStyleSheet("color: #3B82F6; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.progress_detail_lbl.setText("Lendo estrutura de dados na memória do sistema...")

        self.worker = ValidationWorker(self.selected_file_path, self.sheet_name, self.output_file_path)
        self.worker.progress_signal.connect(self._on_worker_progress)
        self.worker.success_signal.connect(self._on_worker_success)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.start()

    def _on_worker_progress(self, percent, status_text, detail_text):
        self.progress_bar.setValue(int(percent * 100))
        self.status_lbl.setText(status_text)
        self.progress_detail_lbl.setText(detail_text)

    def _on_worker_success(self, dist, elapsed, out_path, total_rows):
        self.is_processing = False
        self.action_btn.setEnabled(True)
        self.action_btn.setText("▶ Executar Auditoria e Gerar Planilha")

        self.open_excel_btn.setEnabled(True)
        self.open_excel_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ECC71;
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                border-radius: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #27AE60;
            }
        """)

        self.status_lbl.setText(f"✔ Auditoria Concluída com Sucesso em {elapsed}s!")
        self.status_lbl.setStyleSheet("color: #2ECC71; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.progress_detail_lbl.setText(f"Planilha gravada perfeitamente em: {out_path}")

        total_c = dist.get('C', 0)
        inconf_keys = ['CFP', 'SC', 'FL', 'NI', 'EE', 'CI', 'UCE']
        total_inconf = sum(dist.get(k, 0) for k in inconf_keys)

        if total_c > 0:
            razao_val = (total_inconf / total_c) * 100.0
            razao_str = f"{razao_val:.2f}%".replace('.', ',')
        else:
            razao_str = "0,0%" if total_inconf == 0 else "N/A"

        for key, badge in self.badges.items():
            if key == "RAZAO_INCONF_C":
                badge.update_value(razao_str)
            else:
                val = dist.get(key, 0)
                badge.update_value(f"{val:,}".replace(',', '.'))

        # Salvar estatísticas no histórico
        self.last_run_time = time.strftime("%d/%m/%Y às %H:%M:%S")
        self.last_total_rows = total_rows
        self.last_elapsed_secs = elapsed

        QMessageBox.information(self, "Sucesso", "A auditoria da planilha foi concluída com êxito!\n\nArquivo validado gravado na pasta original.")

    def _on_worker_error(self, error_message):
        self.is_processing = False
        self.action_btn.setEnabled(True)
        self.action_btn.setText("▶ Executar Auditoria e Gerar Planilha")

        self.status_lbl.setText("Erro ao processar planilha")
        self.status_lbl.setStyleSheet("color: #E74C3C; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.progress_detail_lbl.setText(f"Detalhes do erro: {error_message}")

        QMessageBox.critical(self, "Erro na Auditoria", f"Ocorreu um erro durante o processamento:\n\n{error_message}")

    def _open_generated_file(self):
        if self.output_file_path and os.path.exists(self.output_file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_file_path))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuditorComentariosApp()
    window.show()
    sys.exit(app.exec())
