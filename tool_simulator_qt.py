import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QAction, QMenu, 
                             QFrame, QComboBox, QRadioButton, QButtonGroup, 
                             QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
                             QDialog, QLineEdit, QProgressBar, QStackedWidget, QMessageBox,
                             QGridLayout, QAbstractItemView)
from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF, pyqtSignal, QPropertyAnimation, QEasingCurve, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QIcon

# ==========================================
# 1. 自定義元件：機台示意圖 (Schematic)
# ==========================================
class ToolSchematic(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 400)
        self.lp1_state = "NO FOUP"
        self.lp2_state = "NO FOUP"
        
        # 晶圓動畫相關
        self.wafer_visible = False
        self.wafer_pos = QPointF(-100, -100) # 初始在畫面外
        
        # 定義各個站點的座標 (對應 React SVG 的座標)
        self.positions = {
            'port1': QPointF(100, 110),
            'port2': QPointF(100, 290),
            'robot': QPointF(300, 200),
            'aligner': QPointF(270, 330),
            'loadlock': QPointF(490, 200),
            'chuck': QPointF(690, 200)
        }

    def update_lp_state(self, port_num, state):
        if port_num == 1:
            self.lp1_state = state
        else:
            self.lp2_state = state
        self.update() # 觸發重繪

    def set_wafer_position(self, pos_name):
        if pos_name in self.positions:
            self.wafer_pos = self.positions[pos_name]
            self.wafer_visible = True
        else:
            self.wafer_visible = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 繪製 Process Module (黃色區域)
        painter.setPen(QPen(QColor("#854d0e"), 3))
        painter.setBrush(QBrush(QColor("#fef08a")))
        painter.drawRoundedRect(420, 30, 360, 340, 8, 8)

        # Loadlock (三角形)
        path = QPolygonF([QPointF(430, 80), QPointF(530, 80), QPointF(570, 170), QPointF(530, 260), QPointF(430, 260)])
        painter.setBrush(QBrush(QColor("#fde047")))
        painter.setPen(QPen(QColor("#ca8a04"), 2))
        painter.drawPolygon(path)
        
        # Loadlock Circle
        painter.setBrush(QBrush(QColor("#f1f5f9")))
        painter.setPen(QPen(QColor("#94a3b8"), 2))
        painter.drawEllipse(QPointF(490, 170), 45, 45)
        
        # Chuck Unit
        painter.setBrush(QBrush(QColor("#fcd34d")))
        painter.setPen(QPen(QColor("#b45309"), 2))
        painter.drawRoundedRect(620, 100, 140, 200, 4, 4)
        painter.setBrush(QBrush(QColor("white")))
        painter.drawRect(630, 120, 120, 160)
        painter.setBrush(QBrush(QColor(191, 219, 254, 100))) # 半透明藍
        painter.setPen(QPen(QColor("#60a5fa"), 2, Qt.DashLine))
        painter.drawEllipse(QPointF(690, 200), 55, 55)

        # 繪製 EFEM (藍色區域)
        painter.setPen(QPen(QColor("#1e40af"), 3))
        painter.setBrush(QBrush(QColor("#60a5fa")))
        painter.drawRoundedRect(190, 30, 220, 340, 8, 8)

        # Robot
        painter.setBrush(QBrush(QColor("#94a3b8")))
        painter.setPen(QPen(QColor("#334155"), 3))
        painter.drawEllipse(QPointF(300, 200), 55, 55)
        
        # Robot Arms (簡單示意)
        painter.setBrush(QBrush(QColor("#f8fafc")))
        painter.save()
        painter.translate(300, 200)
        painter.rotate(-20)
        painter.drawRoundedRect(-60, 10, 70, 20, 6, 6)
        painter.rotate(185) # rotated 165 from base
        painter.drawRoundedRect(15, -5, 55, 18, 6, 6)
        painter.restore()

        # Aligner
        painter.setBrush(QBrush(QColor("#94a3b8")))
        painter.drawRoundedRect(215, 300, 110, 60, 4, 4)
        painter.setBrush(QBrush(QColor("#cbd5e1")))
        painter.drawEllipse(QPointF(270, 330), 20, 20)

        # 繪製 Load Ports
        self.draw_loadport(painter, 20, 30, "LOAD PORT 1", self.lp1_state)
        self.draw_loadport(painter, 20, 210, "LOAD PORT 2", self.lp2_state)

        # 繪製 Wafer (如果可見)
        if self.wafer_visible:
            painter.setBrush(QBrush(QColor("#22c55e"))) # Green
            painter.setPen(QPen(QColor("#14532d"), 2))
            # 簡單的移動動畫邏輯會由 Timer 控制 set_wafer_position 來達成
            painter.drawEllipse(self.wafer_pos, 40, 40)

    def draw_loadport(self, painter, x, y, label, state):
        # 外框
        painter.setPen(QPen(QColor("#334155"), 3))
        painter.setBrush(QBrush(QColor("#94a3b8")))
        painter.drawRoundedRect(x, y, 160, 160, 4, 4)
        
        # 內部凹槽
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(100, 116, 139, 80)))
        painter.drawRoundedRect(x+5, y+5, 150, 150, 2, 2)

        # 標籤文字
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(QRectF(x, y+20, 160, 20), Qt.AlignCenter, label)

        # 狀態顯示框
        # 根據狀態變色
        is_active = state != "NO FOUP"
        bg_color = QColor("#2563eb") if is_active else QColor("#1e293b")
        text_color = QColor("#ffffff") if is_active else QColor("#60a5fa")

        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(x+20, y+55, 120, 80, 4, 4)
        
        painter.setPen(text_color)
        painter.setFont(QFont("Monospace", 10, QFont.Bold))
        painter.drawText(QRectF(x+20, y+55, 120, 80), Qt.AlignCenter, state)


# ==========================================
# 2. 自定義元件：控制面板 (Panels)
# ==========================================

# Production Mode: Load Port 面板
class LoadPortPanel(QFrame):
    auto_toggled = pyqtSignal(bool) # Signal: True for Auto, False for Manual

    def __init__(self, port_id):
        super().__init__()
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("background-color: #cbd5e1; border: 2px solid #94a3b8; border-radius: 10px;")
        self.setFixedWidth(240)
        self.is_auto = False
        
        layout = QVBoxLayout()
        
        # Header
        header = QFrame()
        header.setStyleSheet("background-color: #94a3b8; border-radius: 5px;")
        h_layout = QVBoxLayout(header)
        title_label = QLabel(f"LoadPort {port_id} - Carrier ID")
        title_label.setFont(QFont("Arial", 9, QFont.Bold))
        self.id_display = QLabel("Scanning...")
        self.id_display.setStyleSheet("background-color: white; border: 1px solid gray; padding: 2px; border-radius: 2px;")
        self.id_display.setFont(QFont("Courier", 10, QFont.Bold))
        h_layout.addWidget(title_label)
        h_layout.addWidget(self.id_display)
        layout.addWidget(header)

        # Slot Map (Simulated with Table)
        self.slot_table = QTableWidget(25, 2)
        self.slot_table.horizontalHeader().hide()
        self.slot_table.verticalHeader().hide()
        self.slot_table.setStyleSheet("background-color: white;")
        self.slot_table.setColumnWidth(0, 40)
        self.slot_table.setColumnWidth(1, 140)
        for i in range(25):
            slot_num = 25 - i
            self.slot_table.setItem(i, 0, QTableWidgetItem(str(slot_num)))
            self.slot_table.setItem(i, 1, QTableWidgetItem("")) # Empty bar
        layout.addWidget(self.slot_table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_auto = QPushButton("Go Auto")
        self.btn_auto.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 8px;")
        self.btn_auto.clicked.connect(self.toggle_auto)
        
        self.btn_unload = QPushButton("Unload")
        self.btn_unload.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 8px;")
        
        btn_layout.addWidget(self.btn_auto)
        btn_layout.addWidget(self.btn_unload)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def toggle_auto(self):
        self.is_auto = not self.is_auto
        if self.is_auto:
            self.btn_auto.setText("Go Manual")
            self.btn_auto.setStyleSheet("background-color: #16a34a; color: white; font-weight: bold; padding: 8px;") # Green
        else:
            self.btn_auto.setText("Go Auto")
            self.btn_auto.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; padding: 8px;") # Slate
        self.auto_toggled.emit(self.is_auto)

    def set_carrier_id(self, text):
        self.id_display.setText(text)

# Engineering Mode: 控制面板
class EngineeringPanel(QFrame):
    load_wafer_clicked = pyqtSignal(str) # Signal sending selected port

    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            EngineeringPanel { background-color: #f0f0f0; border: 2px solid #888; }
            QGroupBox { font-weight: bold; border: 1px solid #aaa; margin-top: 6px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        """)
        self.setFixedWidth(500)
        
        main_layout = QHBoxLayout()
        
        # Left: Slot Map
        left_layout = QVBoxLayout()
        self.carrier_label = QLabel("")
        self.carrier_label.setStyleSheet("background-color: #e0e0e0; border: 1px solid #aaa; font-weight: bold; padding: 4px;")
        self.carrier_label.setAlignment(Qt.AlignCenter)
        
        self.eng_table = QTableWidget(25, 2)
        self.eng_table.setHorizontalHeaderLabels(["Slot", "Status"])
        self.eng_table.verticalHeader().hide()
        self.eng_table.setColumnWidth(0, 40)
        self.eng_table.setColumnWidth(1, 100)
        for i in range(25):
            self.eng_table.setItem(i, 0, QTableWidgetItem(str(25-i)))
            self.eng_table.setItem(i, 1, QTableWidgetItem("Vacant"))
        
        left_layout.addWidget(self.carrier_label)
        left_layout.addWidget(self.eng_table)
        
        # Right: Controls
        right_layout = QVBoxLayout()
        
        # Front End Group
        fe_group = QGroupBox("Front End")
        fe_layout = QVBoxLayout()
        fe_layout.addWidget(QLabel("Port 1: 300  Port 2: 300"))
        
        self.port_combo = QComboBox()
        self.port_combo.addItems(["1", "2"])
        fe_layout.addWidget(QLabel("Select Port:"))
        fe_layout.addWidget(self.port_combo)
        
        self.btn_load_map = QPushButton("Load Carrier / Map")
        self.btn_load_map.clicked.connect(self.on_load_map)
        fe_layout.addWidget(self.btn_load_map)
        fe_layout.addWidget(QPushButton("Unload Carrier"))
        fe_group.setLayout(fe_layout)
        
        # Back End Group
        be_group = QGroupBox("Back End")
        be_layout = QVBoxLayout()
        
        # Recipe Radio
        self.rb_with_rcp = QRadioButton("With Recipe")
        self.rb_no_rcp = QRadioButton("Without Recipe")
        self.rb_no_rcp.setChecked(True)
        self.rb_with_rcp.toggled.connect(self.on_recipe_toggled)
        be_layout.addWidget(self.rb_with_rcp)
        self.lbl_loaded_rcp = QLabel("") # To show loaded filename
        self.lbl_loaded_rcp.setStyleSheet("color: blue; font-size: 10px;")
        be_layout.addWidget(self.lbl_loaded_rcp)
        be_layout.addWidget(self.rb_no_rcp)
        
        # E-Chuck
        be_layout.addWidget(QLabel("E-Chuck Condition"))
        be_layout.addWidget(QComboBox())
        
        self.btn_load_wafer = QPushButton("Load Wafer")
        self.btn_load_wafer.setEnabled(False) # Default Disabled
        self.btn_load_wafer.clicked.connect(self.on_load_wafer)
        
        self.btn_unload_wafer = QPushButton("Unload Wafer")
        self.btn_unload_wafer.setEnabled(False)
        
        be_layout.addWidget(self.btn_load_wafer)
        be_layout.addWidget(self.btn_unload_wafer)
        be_group.setLayout(be_layout)
        
        right_layout.addWidget(fe_group)
        right_layout.addWidget(be_group)
        
        main_layout.addLayout(left_layout, 35)
        main_layout.addLayout(right_layout, 65)
        self.setLayout(main_layout)

        self.port_states = {'1': 'NO FOUP', '2': 'NO FOUP'} # Reference from main

    def update_port_states(self, p1, p2):
        self.port_states['1'] = p1
        self.port_states['2'] = p2

    def on_load_map(self):
        selected = self.port_combo.currentText()
        state = self.port_states[selected]
        
        if state == "CLAMPED":
            self.carrier_label.setText("GGA2330")
            # Set Slot 1 to Occupied (Index 24 because 25 is top)
            self.eng_table.setItem(24, 1, QTableWidgetItem("Occupied"))
            self.eng_table.item(24, 1).setBackground(QColor("#dbeafe")) # Light blue
            
            # Enable Load Wafer Buttons
            self.btn_load_wafer.setEnabled(True)
            self.btn_unload_wafer.setEnabled(True)
        else:
            QMessageBox.warning(self, "Error", f"Port {selected} is not CLAMPED (Current: {state}).")
            self.carrier_label.setText("")
            self.eng_table.setItem(24, 1, QTableWidgetItem("Vacant"))
            self.btn_load_wafer.setEnabled(False)

    def on_recipe_toggled(self, checked):
        if checked and self.rb_with_rcp.isChecked():
            # Show File Explorer
            dlg = FileExplorerDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                selected_file = dlg.selected_file
                # Show Loading
                progress = LoadingDialog(self)
                progress.exec_()
                self.lbl_loaded_rcp.setText(f"Loaded: {selected_file}")
            else:
                self.rb_no_rcp.setChecked(True)
        else:
            self.lbl_loaded_rcp.setText("")

    def on_load_wafer(self):
        selected = self.port_combo.currentText()
        self.load_wafer_clicked.emit(selected)

# ==========================================
# 3. 彈出視窗 (Dialogs)
# ==========================================
class FileExplorerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Recipe File")
        self.setFixedSize(400, 350)
        self.selected_file = None
        
        layout = QVBoxLayout()
        
        # Address Bar (Mock)
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("Address:"))
        addr_edit = QLineEdit("C:\\System\\Recipes\\Engineering\\")
        addr_edit.setReadOnly(True)
        addr_layout.addWidget(addr_edit)
        layout.addLayout(addr_layout)

        # File List
        self.list_widget = QTableWidget(4, 2)
        self.list_widget.setHorizontalHeaderLabels(["Name", "Type"])
        self.list_widget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.list_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.verticalHeader().hide()
        
        files = [
            ("ai_testing.xml", "XML"),
            ("maintenance.xml", "XML"),
            ("process_A.rcp", "Recipe"),
            ("data.dat", "Data")
        ]
        
        for i, (name, ftype) in enumerate(files):
            self.list_widget.setItem(i, 0, QTableWidgetItem(name))
            self.list_widget.setItem(i, 1, QTableWidgetItem(ftype))
            
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.list_widget)
        
        # File Name Input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("File name:"))
        self.filename_edit = QLineEdit("ai_testing.xml")
        input_layout.addWidget(self.filename_edit)
        layout.addLayout(input_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_open = QPushButton("Open")
        btn_open.clicked.connect(self.accept_file)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def on_selection_changed(self):
        rows = self.list_widget.selectionModel().selectedRows()
        if rows:
            filename = self.list_widget.item(rows[0].row(), 0).text()
            self.filename_edit.setText(filename)

    def accept_file(self):
        text = self.filename_edit.text()
        if text:
            self.selected_file = text
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "Please select a file or enter a file name.")

class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint)
        self.setFixedSize(200, 100)
        self.setStyleSheet("background-color: white; border: 1px solid gray;")
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Loading Recipe...", alignment=Qt.AlignCenter))
        
        bar = QProgressBar()
        bar.setRange(0, 0) # Indeterminate mode
        layout.addWidget(bar)
        self.setLayout(layout)
        
        # Auto close after 2 sec
        QTimer.singleShot(2000, self.accept)

class WaferProgressOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 41, 59, 240); 
                color: white; 
                border-radius: 8px;
                border: 1px solid #475569;
            }
            QLabel { color: white; font-weight: bold; }
        """)
        self.setFixedSize(300, 60)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("PROCESSING: WAFER TRANSFER", alignment=Qt.AlignCenter))
        
        self.bar = QProgressBar()
        self.bar.setStyleSheet("QProgressBar { height: 8px; background: #334155; border: none; border-radius: 4px; } QProgressBar::chunk { background-color: #22c55e; border-radius: 4px; }")
        self.bar.setRange(0, 0) # Loading animation
        layout.addWidget(self.bar)
        
        lbl_layout = QHBoxLayout()
        for lbl in ["ROBOT", "ALIGN", "LL", "CHUCK"]:
            l = QLabel(lbl)
            l.setStyleSheet("color: #94a3b8; font-size: 9px;")
            lbl_layout.addWidget(l)
        layout.addLayout(lbl_layout)
        
        self.setLayout(layout)

# ==========================================
# 4. 主視窗 (Main Window)
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tool Behavior Simulator (PyQt5)")
        self.resize(1024, 768)
        
        # State Variables
        self.system_mode = "Standby" # Standby, Engineering, Production
        self.lp1_auto = False
        self.lp2_auto = False
        self.lp1_foup = "NO FOUP"
        self.lp2_foup = "NO FOUP"
        
        self.init_ui()
        self.setup_menu()
        
    def init_ui(self):
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout: Top (Toolbar) + Content (Splitter or HBox)
        main_layout = QVBoxLayout(central_widget)
        
        # 1. Header / Status Bar
        header = QFrame()
        header.setStyleSheet("background-color: white; border-bottom: 1px solid #e2e8f0;")
        header_layout = QHBoxLayout(header)
        header_layout.addWidget(QLabel("Tool Behavior Simulator", styleSheet="font-weight: bold; font-size: 16px;"))
        header_layout.addStretch()
        header_layout.addWidget(QLabel("CONNECTED", styleSheet="color: gray; font-family: monospace;"))
        main_layout.addWidget(header)
        
        # 2. Toolbar (Custom, mimics the React buttons)
        self.toolbar_frame = QFrame()
        self.toolbar_frame.setStyleSheet("background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;")
        tb_layout = QHBoxLayout(self.toolbar_frame)
        
        self.tb_btn_wafer = QPushButton("Wafer Load")
        self.tb_btn_system = QPushButton("System")
        self.tb_btn_recipe = QPushButton("Recipe")
        self.tb_btn_job = QPushButton("Job Execution")
        
        for btn in [self.tb_btn_wafer, self.tb_btn_system, self.tb_btn_recipe, self.tb_btn_job]:
            btn.setEnabled(False) # Default disabled
            btn.setStyleSheet("""
                QPushButton { padding: 5px 10px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f1f5f9; color: #94a3b8; }
                QPushButton:enabled { background: white; color: #334155; }
                QPushButton:hover:enabled { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
                QPushButton:checked { background: #dbeafe; border: 2px solid #3b82f6; }
            """)
            btn.setCheckable(True)
            tb_layout.addWidget(btn)
            
        self.tb_btn_wafer.clicked.connect(self.on_wafer_load_tool_clicked)
        tb_layout.addStretch()
        main_layout.addWidget(self.toolbar_frame)
        
        # 3. Content Area
        content_layout = QHBoxLayout()
        
        # Left Panel (Stacked)
        self.left_stack = QStackedWidget()
        self.left_stack.setFixedWidth(520) # Width to fit Eng Panel
        
        # Page 0: Standby
        p0 = QLabel("System Standby\n\nPlease switch mode.")
        p0.setAlignment(Qt.AlignCenter)
        self.left_stack.addWidget(p0)
        
        # Page 1: Production (2 Ports)
        p1 = QWidget()
        p1_layout = QHBoxLayout(p1)
        self.lp1_panel = LoadPortPanel(1)
        self.lp2_panel = LoadPortPanel(2)
        
        # Connect Auto Toggles
        self.lp1_panel.auto_toggled.connect(lambda s: setattr(self, 'lp1_auto', s))
        self.lp2_panel.auto_toggled.connect(lambda s: setattr(self, 'lp2_auto', s))
        
        p1_layout.addWidget(self.lp1_panel)
        p1_layout.addWidget(self.lp2_panel)
        self.left_stack.addWidget(p1)
        
        # Page 2: Engineering (Wafer Load Module)
        self.eng_panel = EngineeringPanel()
        self.eng_panel.load_wafer_clicked.connect(self.run_wafer_loading_sequence)
        self.left_stack.addWidget(self.eng_panel)
        
        content_layout.addWidget(self.left_stack)
        
        # Right Panel (Schematic)
        self.schematic = ToolSchematic()
        
        # Progress Overlay (Floating child of the window to use absolute/fixed positioning relative to window)
        self.progress_overlay = WaferProgressOverlay(self)
        self.progress_overlay.hide()
        
        content_layout.addWidget(self.schematic)
        main_layout.addLayout(content_layout)

    def setup_menu(self):
        menubar = self.menuBar()
        
        menubar.addMenu('File')
        menubar.addMenu('View')
        menubar.addMenu('Samples')
        menubar.addMenu('Utilities')
        
        # Mode Menu
        mode_menu = menubar.addMenu('Mode')
        
        # Productive Submenu
        prod_menu = QMenu('Productive Mode', self)
        mode_menu.addMenu(prod_menu)
        
        eng_action = QAction('Engineering', self)
        eng_action.triggered.connect(self.set_engineering_mode)
        prod_menu.addAction(eng_action)
        
        prod_action = QAction('Production', self)
        prod_action.triggered.connect(self.set_production_mode)
        prod_menu.addAction(prod_action)
        
        # Simulation Menu
        sim_menu = menubar.addMenu('Simulations')
        wafer_arr_menu = QMenu('Wafer Arrival', self)
        sim_menu.addMenu(wafer_arr_menu)
        
        arr_p1 = QAction('Arrive to port 1', self)
        arr_p1.triggered.connect(lambda: self.run_wafer_arrival(1))
        wafer_arr_menu.addAction(arr_p1)
        
        arr_p2 = QAction('Arrive to port 2', self)
        arr_p2.triggered.connect(lambda: self.run_wafer_arrival(2))
        wafer_arr_menu.addAction(arr_p2)

    def resizeEvent(self, event):
        # Keep progress bar at bottom center
        super().resizeEvent(event)
        w = self.progress_overlay.width()
        h = self.progress_overlay.height()
        self.progress_overlay.move(int((self.width() - w) / 2), self.height() - h - 50)

    # --- Mode Switching Logic ---
    def set_engineering_mode(self):
        self.system_mode = "Engineering"
        self.enable_toolbar(True)
        # Default view in Eng mode is mostly empty until tool selected
        # But for simplicity, we switch stack to Eng panel but keep buttons logic
        self.left_stack.setCurrentIndex(0) # Back to standby placeholder until tool selected
        print("Switched to Engineering Mode")

    def set_production_mode(self):
        self.system_mode = "Production"
        self.enable_toolbar(False)
        self.left_stack.setCurrentIndex(1) # Production Panels
        # Reset Eng buttons if active
        self.tb_btn_wafer.setChecked(False)
        print("Switched to Production Mode")

    def enable_toolbar(self, enable):
        self.tb_btn_wafer.setEnabled(enable)
        self.tb_btn_system.setEnabled(enable)
        self.tb_btn_recipe.setEnabled(enable)
        self.tb_btn_job.setEnabled(enable)

    def on_wafer_load_tool_clicked(self, checked):
        if checked:
            # Sync state to Eng Panel before showing
            self.eng_panel.update_port_states(self.lp1_foup, self.lp2_foup)
            self.left_stack.setCurrentWidget(self.eng_panel)
        else:
            self.left_stack.setCurrentIndex(0) # Hide

    # --- Simulation Logic: Wafer Arrival ---
    def run_wafer_arrival(self, port_num):
        if self.system_mode != "Production":
            QMessageBox.warning(self, "Error", "Please switch to Production Mode first.")
            return
        
        is_auto = self.lp1_auto if port_num == 1 else self.lp2_auto
        if not is_auto:
            QMessageBox.warning(self, "Error", f"Load Port {port_num} must be in Auto Mode ('Go Auto').")
            return

        print(f"Starting Wafer Arrival for Port {port_num}")
        
        # Sequence: NO FOUP -> (2s) PRESENT -> (2s) PLACED -> (2s) CLAMPED
        def step1():
            self.schematic.update_lp_state(port_num, "PRESENT")
            QTimer.singleShot(2000, step2)
        
        def step2():
            self.schematic.update_lp_state(port_num, "PLACED")
            QTimer.singleShot(2000, step3)
            
        def step3():
            state = "CLAMPED"
            self.schematic.update_lp_state(port_num, state)
            
            # Update state variables
            if port_num == 1: self.lp1_foup = state
            else: self.lp2_foup = state
            
            # Update Production Panel UI
            panel = self.lp1_panel if port_num == 1 else self.lp2_panel
            panel.set_carrier_id("GGA2330")
            
            # Also update Eng Panel state in background
            self.eng_panel.update_port_states(self.lp1_foup, self.lp2_foup)

        # Start sequence after 2s
        QTimer.singleShot(2000, step1)

    # --- Simulation Logic: Wafer Loading (Movement) ---
    def run_wafer_loading_sequence(self, selected_port):
        print(f"Starting Wafer Movement from Port {selected_port}")
        self.progress_overlay.show()
        
        # 0s: Init at Port
        self.schematic.set_wafer_position(f'port{selected_port}')
        
        # Sequence
        QTimer.singleShot(2000, lambda: self.schematic.set_wafer_position('robot'))
        QTimer.singleShot(4000, lambda: self.schematic.set_wafer_position('aligner'))
        QTimer.singleShot(6000, lambda: self.schematic.set_wafer_position('robot'))
        QTimer.singleShot(8000, lambda: self.schematic.set_wafer_position('loadlock'))
        QTimer.singleShot(10000, lambda: self.schematic.set_wafer_position('chuck'))
        
        # End
        def finish():
            self.progress_overlay.hide()
            # self.schematic.set_wafer_position('none') # Optional: clear wafer
            
        QTimer.singleShot(12000, finish)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())