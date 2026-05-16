#!/usr/bin/env python3
# Agildo Cheats — trainer de memória para Linux (/proc). Uso ético: jogos offline / single-player.
from __future__ import annotations

import os
import struct
import sys
import xml.etree.ElementTree as ET
from typing import Optional

import psutil
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

VERSAO_APP = "15.3"
# Limite de endereços guardados (evita listas gigantes na RAM)
MAX_RESULTADOS_SCAN = 300_000
# Linhas visíveis na tabela do scanner
MAX_LINHAS_TABELA = 200

# Índices das abas (evita confusão nos comentários)
TAB_CONEXAO = 0
TAB_SCANNER = 1
TAB_CT = 2
TAB_TELEPORT = 3

STYLESHEET = """
    QWidget { background-color: #0a0a0a; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; font-size: 14px; }
    QLabel#Title { color: #ff0033; font-family: 'Consolas', monospace; font-size: 28px; font-weight: 900; }
    QLineEdit, QComboBox { background-color: #151515; border: 2px solid #333; border-radius: 6px; padding: 10px; color: #ffffff; font-weight: bold; }
    QTableWidget { background-color: #111; border: 1px solid #333; gridline-color: #222; }
    QHeaderView::section { background-color: #222; padding: 6px; border: none; color: #aaa; font-weight: bold; }
    QPushButton { background-color: #252525; border: 1px solid #444; border-radius: 6px; padding: 12px; color: #ffffff; font-weight: bold; }
    QPushButton:hover { background-color: #333; border-color: #ff0033; }
    QPushButton#Connect { background-color: #065f46; color: white; font-size: 14px; border: 1px solid #059669; }
    QPushButton#Connect:hover { background-color: #059669; }
    QPushButton#Teleport { background-color: #4a148c; border: 1px solid #7c43bd; color: white; font-size: 16px; }
    QPushButton#Teleport:hover { background-color: #6a1b9a; }
    QProgressBar { border: 1px solid #333; border-radius: 4px; text-align: center; background-color: #111; color: white; }
    QProgressBar::chunk { background-color: #ff0033; }
    /* Caixa «Congelar» — contraste alto no fundo escuro da tabela */
    QCheckBox { color: #f0f0f0; spacing: 6px; font-weight: bold; }
    QCheckBox::indicator {
        width: 22px;
        height: 22px;
        border: 2px solid #ff4d6d;
        border-radius: 4px;
        background-color: #2a2a2a;
    }
    QCheckBox::indicator:hover {
        border-color: #ff99aa;
        background-color: #3d2028;
    }
    QCheckBox::indicator:checked {
        background-color: #ff0033;
        border-color: #ffffff;
        image: none;
    }
    QCheckBox::indicator:checked:hover {
        background-color: #ff3355;
    }
"""

# Estilo extra na célula da coluna Congelar (fundo ligeiramente distinto)
ESTILO_CELULA_CONGELAR = "background-color: #1c1c24;"


def valor_para_bytes(valor, tipo_combo: str) -> tuple[bytes, int]:
    """Converte valor do utilizador para bytes little-endian conforme o tipo seleccionado."""
    if "DOUBLE" in tipo_combo:
        return struct.pack("<d", float(valor)), 8
    if "FLOAT" in tipo_combo:
        return struct.pack("<f", float(valor)), 4
    if "com sinal" in tipo_combo.lower():
        return struct.pack("<i", int(valor)), 4
    return struct.pack("<I", int(valor)), 4


def regioes_memoria_escaneaveis(pid: int) -> list[tuple[int, int]]:
    """Regiões rw-p legíveis (heap/dados); ignora mapeamentos anónimos muito altos."""
    regioes = []
    maps_path = f"/proc/{pid}/maps"
    with open(maps_path, "r", encoding="utf-8", errors="replace") as f:
        for linha in f:
            if "rw-p" not in linha:
                continue
            # Heurística: pular blocos anónimos altos (menos ruído em alguns jogos)
            if linha.startswith("7f"):
                continue
            partes = linha.split()
            if not partes:
                continue
            inicio, fim = (int(x, 16) for x in partes[0].split("-"))
            if fim > inicio:
                regioes.append((inicio, fim))
    return regioes


def detectar_base_modulo(pid: int, nome_processo: str) -> int:
    """Escolhe base do executável para ponteiros «modulo+offset» (.CT)."""
    nome_lower = nome_processo.lower()
    candidato_nome = 0
    candidato_exe = 0
    maps_path = f"/proc/{pid}/maps"
    with open(maps_path, "r", encoding="utf-8", errors="replace") as f:
        for linha in f:
            if "r-xp" not in linha:
                continue
            partes = linha.split()
            if len(partes) < 2:
                continue
            inicio = int(partes[0].split("-")[0], 16)
            caminho = partes[-1] if len(partes) >= 6 else ""
            if nome_lower and nome_lower in caminho.lower():
                return inicio
            if caminho and caminho.startswith("/") and candidato_exe == 0:
                candidato_exe = inicio
            if candidato_nome == 0:
                candidato_nome = inicio
    return candidato_exe or candidato_nome


def aviso_acesso_memoria(parent: QWidget, pid: int, erro: OSError) -> None:
    """Mensagem quando /proc/PID/mem não está acessível."""
    QMessageBox.warning(
        parent,
        "Acesso à memória",
        f"Não foi possível aceder a /proc/{pid}/mem.\n\n"
        f"• Executa como root, ou\n"
        f"• echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope\n\n"
        f"Detalhe: {erro}",
    )


class MemScanThread(QThread):
    progress = pyqtSignal(int)
    found = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, pid, valor, tipo_combo, modo="FIRST", lista_anterior=None):
        super().__init__()
        self.pid = pid
        self.valor = valor
        self.tipo_combo = tipo_combo
        self.modo = modo
        self.lista_anterior = lista_anterior or []
        self.parar = False

    def run(self):
        encontrados: list[int] = []
        fd = None
        try:
            alvo, tamanho = valor_para_bytes(self.valor, self.tipo_combo)
            fd = os.open(f"/proc/{self.pid}/mem", os.O_RDONLY)

            if self.modo == "FIRST":
                regioes = regioes_memoria_escaneaveis(self.pid)
                total = max(len(regioes), 1)
                for i, (inicio, fim) in enumerate(regioes):
                    if self.parar:
                        break
                    try:
                        os.lseek(fd, inicio, os.SEEK_SET)
                        bloco = os.read(fd, fim - inicio)
                        if not bloco:
                            continue
                        offset = 0
                        while len(encontrados) < MAX_RESULTADOS_SCAN:
                            idx = bloco.find(alvo, offset)
                            if idx == -1:
                                break
                            encontrados.append(inicio + idx)
                            offset = idx + tamanho
                    except OSError:
                        continue
                    self.progress.emit(int((i + 1) / total * 100))
            else:
                total = max(len(self.lista_anterior), 1)
                for i, endereco in enumerate(self.lista_anterior):
                    if self.parar:
                        break
                    try:
                        os.lseek(fd, endereco, os.SEEK_SET)
                        if os.read(fd, tamanho) == alvo:
                            encontrados.append(endereco)
                    except OSError:
                        continue
                    if i % 50 == 0:
                        self.progress.emit(int((i + 1) / total * 100))

            self.found.emit(encontrados)
        except OSError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if fd is not None:
                os.close(fd)


class AgildoCheatsV15(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Agildo Cheats V{VERSAO_APP} - Mass Edit & Freeze")
        self.resize(950, 750)
        self.setStyleSheet(STYLESHEET)

        self.pid = None
        self.game_module_base = 0
        self.current_game_name = ""
        self.saved_coords = None
        self.current_results: list[int] = []
        self.worker: Optional[MemScanThread] = None
        self.procs_all: list[str] = []

        main_layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel(f"💀 AGILDO CHEATS V{VERSAO_APP}", objectName="Title"))
        top.addStretch()
        self.lbl_status = QLabel("DISCONNECTED", styleSheet="color: red; font-weight: bold;")
        top.addWidget(self.lbl_status)
        main_layout.addLayout(top)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Aba conexão
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        self.input_search = QLineEdit(placeholderText="🔍 Buscar processo...")
        self.input_search.textChanged.connect(self.filtrar_procs)
        l1.addWidget(self.input_search)
        self.list_procs = QListWidget()
        l1.addWidget(self.list_procs)
        btn_con = QPushButton("🔗 CONECTAR AO JOGO", objectName="Connect")
        btn_con.clicked.connect(self.anexar_processo)
        l1.addWidget(btn_con)
        self.tabs.addTab(t1, "1. CONEXÃO")

        # Aba scanner
        t2 = QWidget()
        l2 = QVBoxLayout(t2)
        gp_scan = QFrame()
        gp_scan.setStyleSheet("background-color: #111; border: 1px solid #333; padding: 10px; border-radius: 8px;")
        l_gp = QVBoxLayout(gp_scan)

        r1 = QHBoxLayout()
        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "INT32 sem sinal (4 Bytes)",
            "INT32 com sinal (4 Bytes)",
            "FLOAT (4 Bytes)",
            "DOUBLE (8 Bytes)",
        ])
        self.input_val = QLineEdit(placeholderText="Valor actual (ex.: 500)")
        r1.addWidget(QLabel("Tipo:"))
        r1.addWidget(self.combo_type)
        r1.addWidget(QLabel("Valor:"))
        r1.addWidget(self.input_val)
        l_gp.addLayout(r1)

        r2 = QHBoxLayout()
        self.btn_first = QPushButton("🔎 FIRST SCAN")
        self.btn_first.clicked.connect(lambda: self.iniciar_scan("FIRST"))
        self.btn_next = QPushButton("🎯 NEXT SCAN")
        self.btn_next.clicked.connect(lambda: self.iniciar_scan("NEXT"))
        self.btn_next.setEnabled(False)
        self.btn_stop = QPushButton("⏹ PARAR")
        self.btn_stop.clicked.connect(self.parar_scan)
        self.btn_stop.setEnabled(False)
        r2.addWidget(self.btn_first)
        r2.addWidget(self.btn_next)
        r2.addWidget(self.btn_stop)
        l_gp.addLayout(r2)
        l2.addWidget(gp_scan)

        self.prog = QProgressBar()
        self.prog.setFixedHeight(5)
        self.prog.setTextVisible(False)
        l2.addWidget(self.prog)
        self.lbl_info = QLabel("Aguardando scan...")
        l2.addWidget(self.lbl_info)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Endereço", "Valor", "Congelar"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(2, 110)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.menu_contexto_scan)
        self.table.doubleClicked.connect(self.editar_valor_unico)
        l2.addWidget(self.table)
        self.tabs.addTab(t2, "2. SCANNER MANUAL")

        # Aba CT
        t3 = QWidget()
        l3 = QVBoxLayout(t3)
        btn_open = QPushButton("📂 ABRIR FICHEIRO .CT / XML")
        btn_open.clicked.connect(self.importar_ct)
        l3.addWidget(btn_open)
        self.table_ct = QTableWidget(0, 2)
        self.table_ct.setHorizontalHeaderLabels(["DESCRIÇÃO", "VALOR"])
        self.table_ct.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_ct.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_ct.customContextMenuRequested.connect(self.menu_contexto_ct)
        self.table_ct.doubleClicked.connect(self.editar_ct_selecionado)
        l3.addWidget(self.table_ct)
        self.tabs.addTab(t3, "3. IMPORTADOR .CT")

        self.setup_aba_teleport()

        self.listar_procs()
        self.timer_monitor = QTimer()
        self.timer_monitor.timeout.connect(self.loop_monitor)
        self.timer_monitor.start(200)

    def closeEvent(self, event):
        self.parar_scan()
        self.timer_monitor.stop()
        super().closeEvent(event)

    def abrir_mem(self, escrita: bool = False):
        if not self.pid:
            return None
        flags = os.O_RDWR if escrita else os.O_RDONLY
        try:
            return os.open(f"/proc/{self.pid}/mem", flags)
        except OSError as e:
            aviso_acesso_memoria(self, self.pid, e)
            return None

    # --- Teleport ---
    def setup_aba_teleport(self):
        t4 = QWidget()
        l4 = QVBoxLayout(t4)
        gp_addr = QFrame()
        gp_addr.setStyleSheet("border: 1px solid #333; border-radius: 8px; padding: 10px;")
        l_addr = QGridLayout(gp_addr)
        l_addr.addWidget(QLabel("Endereço X (hex):"), 0, 0)
        self.input_addr_x = QLineEdit()
        self.input_addr_x.setPlaceholderText("Endereço do eixo X")
        self.input_addr_x.textChanged.connect(self.auto_fill_yz)
        l_addr.addWidget(self.input_addr_x, 0, 1)
        l_addr.addWidget(QLabel("Endereço Z (hex):"), 1, 0)
        self.input_addr_z = QLineEdit()
        l_addr.addWidget(self.input_addr_z, 1, 1)
        l_addr.addWidget(QLabel("Endereço Y (hex):"), 2, 0)
        self.input_addr_y = QLineEdit()
        l_addr.addWidget(self.input_addr_y, 2, 1)
        l4.addWidget(QLabel("📡 CONFIGURAÇÃO"))
        l4.addWidget(gp_addr)

        gp_mon = QFrame()
        gp_mon.setStyleSheet("background-color: #111; border-radius: 8px; padding: 15px;")
        l_mon = QHBoxLayout(gp_mon)
        self.lbl_cur_x = QLabel("X: 0.00")
        self.lbl_cur_x.setStyleSheet("font-size: 18px; color: cyan;")
        self.lbl_cur_z = QLabel("Z: 0.00")
        self.lbl_cur_z.setStyleSheet("font-size: 18px; color: cyan;")
        self.lbl_cur_y = QLabel("Y: 0.00")
        self.lbl_cur_y.setStyleSheet("font-size: 18px; color: yellow;")
        l_mon.addWidget(self.lbl_cur_x)
        l_mon.addWidget(self.lbl_cur_z)
        l_mon.addWidget(self.lbl_cur_y)
        l4.addWidget(QLabel("📍 POSIÇÃO ACTUAL"))
        l4.addWidget(gp_mon)

        gp_act = QFrame()
        l_act = QHBoxLayout(gp_act)
        btn_save = QPushButton("💾 SALVAR LOCAL")
        btn_save.setStyleSheet("background-color: #0d47a1; color: white;")
        btn_save.clicked.connect(self.teleport_save)
        self.btn_load = QPushButton("🌌 TELEPORTAR")
        self.btn_load.setObjectName("Teleport")
        self.btn_load.clicked.connect(self.teleport_load)
        self.btn_load.setEnabled(False)
        l_act.addWidget(btn_save)
        l_act.addWidget(self.btn_load)
        l4.addWidget(gp_act)

        gp_nudge = QGridLayout()
        gp_nudge.addWidget(self._btn_nudge("🔼 Subir", "y", 2.0), 0, 1)
        gp_nudge.addWidget(self._btn_nudge("Norte", "z", 1.0), 1, 1)
        gp_nudge.addWidget(self._btn_nudge("Oeste", "x", -1.0), 2, 0)
        gp_nudge.addWidget(self._btn_nudge("🔽 Descer", "y", -2.0), 2, 1)
        gp_nudge.addWidget(self._btn_nudge("Leste", "x", 1.0), 2, 2)
        gp_nudge.addWidget(self._btn_nudge("Sul", "z", -1.0), 3, 1)
        l4.addWidget(QLabel("🕹️ CONTROLE FINO"))
        l4.addLayout(gp_nudge)
        self.tabs.addTab(t4, "4. TELEPORT")

    def _btn_nudge(self, texto, eixo, delta):
        b = QPushButton(texto)
        b.clicked.connect(lambda _=False, a=eixo, d=delta: self.nudge(a, d))
        return b

    def auto_fill_yz(self, texto):
        try:
            base_x = int(texto, 16)
            self.input_addr_z.setText(hex(base_x + 4))
            self.input_addr_y.setText(hex(base_x + 8))
        except ValueError:
            pass

    def read_floats(self):
        if not self.pid:
            return (0.0, 0.0, 0.0)
        fd = self.abrir_mem(False)
        if fd is None:
            return (0.0, 0.0, 0.0)
        try:
            def ler(addr_str):
                if not addr_str:
                    return 0.0
                os.lseek(fd, int(addr_str, 16), os.SEEK_SET)
                return struct.unpack("<f", os.read(fd, 4))[0]

            x = ler(self.input_addr_x.text())
            z = ler(self.input_addr_z.text())
            y = ler(self.input_addr_y.text())
            return (x, z, y)
        except OSError:
            return (0.0, 0.0, 0.0)
        finally:
            os.close(fd)

    def write_coords(self, x, z, y):
        fd = self.abrir_mem(True)
        if fd is None:
            return
        try:
            def escrever(addr_str, val):
                if not addr_str:
                    return
                os.lseek(fd, int(addr_str, 16), os.SEEK_SET)
                os.write(fd, struct.pack("<f", val))

            escrever(self.input_addr_x.text(), x)
            escrever(self.input_addr_z.text(), z)
            escrever(self.input_addr_y.text(), y)
        except OSError as e:
            aviso_acesso_memoria(self, self.pid, e)
        finally:
            os.close(fd)

    def teleport_save(self):
        self.saved_coords = self.read_floats()
        self.btn_load.setText(f"TELEPORTAR ({self.saved_coords[0]:.1f}, {self.saved_coords[2]:.1f})")
        self.btn_load.setEnabled(True)

    def teleport_load(self):
        if self.saved_coords:
            self.write_coords(*self.saved_coords)

    def nudge(self, axis, amount):
        x, z, y = self.read_floats()
        if axis == "x":
            x += amount
        elif axis == "z":
            z += amount
        elif axis == "y":
            y += amount
        self.write_coords(x, z, y)

    # --- Processos ---
    def listar_procs(self):
        self.list_procs.clear()
        self.procs_all = []
        for proc in psutil.process_iter(["pid", "name"]):
            info = proc.info
            self.procs_all.append(f"[{info['pid']}] {info['name']}")
        self.list_procs.addItems(self.procs_all)

    def filtrar_procs(self, txt):
        self.list_procs.clear()
        filtro = txt.lower()
        self.list_procs.addItems([p for p in self.procs_all if filtro in p.lower()])

    def anexar_processo(self):
        item = self.list_procs.currentItem()
        if not item:
            return
        self.pid = int(item.text().split("]")[0][1:])
        self.current_game_name = item.text().split("] ", 1)[1]
        self.lbl_status.setText(f"CONNECTED: {self.current_game_name}")
        self.lbl_status.setStyleSheet("color: #00ff00; font-weight: bold;")

        fd = self.abrir_mem(False)
        if fd is None:
            self.pid = None
            self.lbl_status.setText("SEM ACESSO À MEMÓRIA")
            self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
            return
        os.close(fd)

        self.game_module_base = detectar_base_modulo(self.pid, self.current_game_name)
        self.tabs.setCurrentIndex(TAB_SCANNER)
        self.btn_next.setEnabled(bool(self.current_results))

    # --- Scanner ---
    def iniciar_scan(self, modo):
        if not self.pid:
            QMessageBox.warning(self, "Scanner", "Liga-te a um processo primeiro.")
            return
        val_str = self.input_val.text().replace(",", ".")
        tipo = self.combo_type.currentText()
        try:
            if "FLOAT" in tipo or "DOUBLE" in tipo:
                valor = float(val_str)
            else:
                valor = int(val_str)
        except ValueError:
            QMessageBox.warning(self, "Scanner", "Valor inválido.")
            return

        self.parar_scan()
        self.btn_first.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_info.setText("⏳ A escanear...")
        self.prog.setValue(0)

        lista = self.current_results if modo == "NEXT" else None
        self.worker = MemScanThread(self.pid, valor, tipo, modo, lista)
        self.worker.progress.connect(self.prog.setValue)
        self.worker.found.connect(self.scan_fim)
        self.worker.error.connect(self.scan_erro)
        self.worker.start()

    def _widget_checkbox_congelar(self) -> QWidget:
        """Checkbox grande e visível na coluna Congelar."""
        contentor = QWidget()
        contentor.setStyleSheet(ESTILO_CELULA_CONGELAR)
        layout = QHBoxLayout(contentor)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox("❄")
        chk.setToolTip("Congelar este valor (reaplica a cada 200 ms)")
        chk.setMinimumSize(28, 28)
        layout.addWidget(chk)
        return contentor

    def parar_scan(self):
        if self.worker and self.worker.isRunning():
            self.worker.parar = True
            self.lbl_info.setText("A cancelar scan…")

    def _repor_botoes_scan(self):
        self.btn_first.setEnabled(True)
        self.btn_next.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.worker = None

    def scan_erro(self, mensagem):
        self._repor_botoes_scan()
        self.lbl_info.setText("Erro no scan")
        aviso_acesso_memoria(self, self.pid or 0, OSError(mensagem))

    def scan_fim(self, resultados):
        self._repor_botoes_scan()
        self.current_results = resultados
        total = len(resultados)
        truncado = total >= MAX_RESULTADOS_SCAN
        msg = f"🎯 Encontrados: {total}"
        if truncado:
            msg += f" (limite {MAX_RESULTADOS_SCAN}; refina com NEXT SCAN)"
        if self.worker and self.worker.parar:
            msg = f"Scan cancelado — {total} endereços até ao cancelamento"
        self.lbl_info.setText(msg)

        self.table.setRowCount(0)
        limite = min(total, MAX_LINHAS_TABELA)
        self.table.setUpdatesEnabled(False)
        valor_txt = self.input_val.text()
        for i, addr in enumerate(resultados[:limite]):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(hex(addr)))
            self.table.setItem(i, 1, QTableWidgetItem(valor_txt))
            self.table.setCellWidget(i, 2, self._widget_checkbox_congelar())
        self.table.setUpdatesEnabled(True)
        self.btn_next.setEnabled(total > 0)

    def menu_contexto_scan(self, pos):
        menu = QMenu()
        act = menu.addAction("✏️ Editar seleccionados")
        act.triggered.connect(self.editar_selecionados_scan)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def editar_selecionados_scan(self):
        linhas = sorted({i.row() for i in self.table.selectedIndexes()})
        if not linhas:
            return
        novo, ok = QInputDialog.getText(self, "Edição em massa", f"Novo valor para {len(linhas)} itens:")
        if not ok or not novo:
            return
        fd = self.abrir_mem(True)
        if fd is None:
            return
        try:
            data, _ = valor_para_bytes(novo.replace(",", "."), self.combo_type.currentText())
            for r in linhas:
                addr = int(self.table.item(r, 0).text(), 16)
                os.lseek(fd, addr, os.SEEK_SET)
                os.write(fd, data)
                self.table.item(r, 1).setText(novo)
            QMessageBox.information(self, "Sucesso", "Valores alterados.")
        except (OSError, ValueError, struct.error) as e:
            QMessageBox.warning(self, "Erro", str(e))
        finally:
            os.close(fd)

    def editar_valor_unico(self):
        self.table.selectRow(self.table.currentRow())
        self.editar_selecionados_scan()

    def aplicar_congelamento(self):
        if not self.pid:
            return
        fd = self.abrir_mem(True)
        if fd is None:
            return
        tipo = self.combo_type.currentText()
        try:
            for r in range(self.table.rowCount()):
                chk_w = self.table.cellWidget(r, 2)
                if not chk_w:
                    continue
                chk = chk_w.findChild(QCheckBox)
                if not chk or not chk.isChecked():
                    continue
                addr = int(self.table.item(r, 0).text(), 16)
                val_str = self.table.item(r, 1).text().replace(",", ".")
                data, _ = valor_para_bytes(val_str, tipo)
                os.lseek(fd, addr, os.SEEK_SET)
                os.write(fd, data)
        except (OSError, ValueError, struct.error):
            pass
        finally:
            os.close(fd)

    # --- Cheat Engine .CT ---
    def importar_ct(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar tabela",
            os.path.expanduser("~"),
            "Ficheiros (*.CT *.ct *.xml);;Todos (*)",
        )
        if not path:
            return
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            self.table_ct.setRowCount(0)

            def processar(no):
                for entry in no.findall("CheatEntry"):
                    if entry.find("Address") is not None:
                        desc_el = entry.find("Description")
                        desc = desc_el.text.strip('"') if desc_el is not None and desc_el.text else "Sem nome"
                        addr = entry.find("Address").text
                        off_node = entry.find("Offsets")
                        offsets = [o.text for o in off_node.findall("Offset")] if off_node is not None else []
                        vt_el = entry.find("VariableType")
                        vtype = vt_el.text if vt_el is not None else "4 Bytes"
                        row = self.table_ct.rowCount()
                        self.table_ct.insertRow(row)
                        self.table_ct.setItem(row, 0, QTableWidgetItem(desc))
                        self.table_ct.setItem(row, 1, QTableWidgetItem("---"))
                        self.table_ct.item(row, 0).setData(
                            Qt.ItemDataRole.UserRole,
                            {"base": addr, "offsets": offsets, "type": vtype},
                        )
                    sub = entry.find("CheatEntries")
                    if sub is not None:
                        processar(sub)

            raiz = root.find("CheatEntries")
            processar(raiz if raiz is not None else root)
            QMessageBox.information(self, "Sucesso", f"Itens: {self.table_ct.rowCount()}")
        except ET.ParseError as e:
            QMessageBox.critical(self, "Erro", f"XML inválido: {e}")
        except OSError as e:
            QMessageBox.critical(self, "Erro", str(e))

    def monitorar_tabela_ct(self):
        if not self.pid or self.table_ct.rowCount() == 0:
            return
        fd = self.abrir_mem(False)
        if fd is None:
            return
        try:
            for row in range(self.table_ct.rowCount()):
                data = self.table_ct.item(row, 0).data(Qt.ItemDataRole.UserRole)
                addr = self.resolver_ponteiro(fd, data["base"], data["offsets"])
                item_val = self.table_ct.item(row, 1)
                if addr:
                    os.lseek(fd, addr, os.SEEK_SET)
                    if "Float" in data["type"]:
                        val = struct.unpack("<f", os.read(fd, 4))[0]
                        item_val.setText(f"{val:.2f}")
                    else:
                        val = struct.unpack("<I", os.read(fd, 4))[0]
                        item_val.setText(str(val))
                    item_val.setForeground(Qt.GlobalColor.green)
                else:
                    item_val.setText("???")
                    item_val.setForeground(Qt.GlobalColor.darkGray)
        except OSError:
            pass
        finally:
            os.close(fd)

    def resolver_ponteiro(self, fd, base_str, offsets):
        try:
            if "+" in base_str:
                addr = self.game_module_base + int(base_str.split("+")[1], 16)
            else:
                addr = int(base_str, 16)
            for off_str in offsets:
                os.lseek(fd, addr + int(off_str, 16), os.SEEK_SET)
                ptr = os.read(fd, 8)
                addr = struct.unpack("<Q", ptr)[0]
                if addr == 0:
                    return None
            return addr
        except (OSError, ValueError, struct.error):
            return None

    def menu_contexto_ct(self, pos):
        menu = QMenu()
        act = menu.addAction("✏️ Mudar valor")
        act.triggered.connect(self.editar_ct_selecionado)
        menu.exec(self.table_ct.viewport().mapToGlobal(pos))

    def editar_ct_selecionado(self):
        row = self.table_ct.currentRow()
        if row < 0:
            return
        data = self.table_ct.item(row, 0).data(Qt.ItemDataRole.UserRole)
        novo, ok = QInputDialog.getText(self, "Editar", "Valor:")
        if not ok:
            return
        fd = self.abrir_mem(True)
        if fd is None:
            return
        try:
            addr = self.resolver_ponteiro(fd, data["base"], data["offsets"])
            if not addr:
                return
            os.lseek(fd, addr, os.SEEK_SET)
            if "Float" in data["type"]:
                os.write(fd, struct.pack("<f", float(novo.replace(",", "."))))
            else:
                os.write(fd, struct.pack("<I", int(novo)))
        except (OSError, ValueError, struct.error) as e:
            QMessageBox.warning(self, "Erro", str(e))
        finally:
            os.close(fd)

    def loop_monitor(self):
        idx = self.tabs.currentIndex()
        if idx == TAB_SCANNER:
            self.aplicar_congelamento()
        elif idx == TAB_CT:
            self.monitorar_tabela_ct()
        elif idx == TAB_TELEPORT:
            self.update_teleport_ui()

    def update_teleport_ui(self):
        x, z, y = self.read_floats()
        self.lbl_cur_x.setText(f"X: {x:.2f}")
        self.lbl_cur_z.setText(f"Z: {z:.2f}")
        self.lbl_cur_y.setText(f"Y: {y:.2f}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AgildoCheatsV15()
    win.show()
    sys.exit(app.exec())
