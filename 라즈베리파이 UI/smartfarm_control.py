import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt, QTime, QSize  # QSize 추가
from PyQt5.QtGui import QFont, QIcon
import pyqtgraph as pg
import serial
import mysql.connector
from datetime import datetime, timedelta

# MariaDB 설정
db_config = {
    'host': 'localhost',
    'user': 'jung',
    'password': '1234',
    'database': 'sensor_data'
}

# 데이터 읽기 스레드
class SerialThread(QThread):
    data_signal = pyqtSignal(float, float, int)

    def __init__(self):
        super().__init__()
        self.ser = None
        self.running = True

    def run(self):
        try:
            self.ser = serial.Serial('/dev/ttyACM0', 115200)
            while self.running:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8').strip()
                    print(f"Received data: {line}")
                    
                    if line and line.count(',') == 2:
                        try:
                            temp, humid, light = map(int, line.split(','))
                            print(f"Parsed values - Temp: {temp}, Humid: {humid}, Light: {light}")
                            
                            if (0 <= temp <= 50 and 
                                0 <= humid <= 100 and 
                                0 <= light <= 4000):
                                self.data_signal.emit(temp, humid, light)
                                print("Data emitted successfully")
                            else:
                                print("Values out of range")
                        except ValueError as ve:
                            print(f"Error parsing values: {ve}")
        except Exception as e:
            print(f"Serial Error: {e}")
            
    def send_command(self, command):
        try:
            if self.ser:
                self.ser.write(command.encode())
                print(f"Sent command: {command}")
        except Exception as e:
            print(f"Error sending command: {e}")
            
    def stop(self):
        self.running = False
        if self.ser:
            self.ser.close()

    def __del__(self):
        self.stop()

class SmartFarmUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initData()
        self.initUI()
        self.initThread()
        self.initTimer()
        self.check_automation_timer = QTimer()
        self.check_automation_timer.timeout.connect(self.check_automation_conditions)
        self.check_automation_timer.start(5000)

    def initData(self):
        # 기존 코드에 자동화 상태 변수 추가
        self.temp_data = []
        self.humid_data = []
        self.time_data = []
        
        self.led_status = False
        self.fan_status = False
        self.pump_status = False
        self.automation_status = False
        
        self.led_start_time = None
        self.fan_start_time = None
        self.pump_start_time = None
        
        # 자동화 임계값 설정
        self.TEMP_THRESHOLD = 28  # 온도 28도 이상이면 팬 가동
        self.HUMID_THRESHOLD = 20  # 습도 20% 이하면 펌프 가동
        self.LIGHT_THRESHOLD = 2000  # 조도 2000 이하면 LED 가동

    def initUI(self):
        # 메인 윈도우 아이콘 설정
        self.setWindowIcon(QIcon('icons/smartfarm.png'))
        self.setWindowTitle('Smart Farm Monitor')
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f7f0;
            }
            QPushButton {
                font-size: 14px;
                padding: 8px;
                border-radius: 4px;
                min-width: 100px;
                border: 1px solid #ccc;
            }
            QLabel {
                font-size: 14px;
                padding: 5px;
                color: #2c3e50;
            }
            QFrame {
                border: 1px solid #dcdde1;
                border-radius: 5px;
                background-color: white;
            }
        """)
        
        # 메인 위젯 및 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 상단 상태 표시줄
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)

        # 현재 시간
        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet('font-size: 24px; font-weight: bold;')
        status_layout.addWidget(self.time_label)

        # 스마트팜 시스템 타이틀
        title_frame = QFrame()
        title_frame.setStyleSheet('''
           QFrame {
               background: linear-gradient(135deg, #4BB543, #00D100);
               border-radius: 12px;
               margin: 0px 20px;
               padding: 12px;
               border: 2px solid #45a049;
               box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
           }
           QLabel {
               color: black;
               font-size: 24px;
               font-weight: bold;
               text-shadow: 1px 1px 2px rgba(255, 255, 255, 0.5);
           }
        ''')
        title_layout = QHBoxLayout(title_frame)
        title_layout.setContentsMargins(10, 5, 10, 5)

        system_icon = QLabel()
        system_icon.setPixmap(QIcon('icons/smartfarm.png').pixmap(QSize(32, 32)))
        system_icon.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(system_icon)

        system_title = QLabel('스마트팜 시스템')
        system_title.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(system_title)

        status_layout.addWidget(title_frame, 1)

        # 조도 상태
        self.light_status = QLabel('조도: --')
        self.light_status.setStyleSheet('font-size: 18px;')
        self.light_icon = QLabel()
        status_layout.addWidget(self.light_status)
        status_layout.addWidget(self.light_icon)

        layout.addWidget(status_frame)
        
        
        # 그래프와 컨트롤 레이아웃
        main_content = QHBoxLayout()
        
        # 왼쪽: 그래프들
        graphs_frame = QFrame()
        graphs_layout = QVBoxLayout(graphs_frame)
        
        # 온도 그래프 설정
        temp_header = QHBoxLayout()
        temp_icon = QLabel()
        temp_icon.setPixmap(QIcon('icons/temperature.png').pixmap(QSize(40, 40)))
        temp_header.addWidget(temp_icon)
        
        self.temp_graph = pg.PlotWidget(height=200)
        self.temp_graph.setBackground('w')
        self.temp_graph.setTitle(f'온도 (°C)', color='k', size='14pt')
        self.temp_graph.showGrid(x=True, y=True)
        self.temp_graph.setLabel('left', '온도', color='k')
        self.temp_graph.setLabel('bottom', '시간', color='k')
        self.temp_graph.setYRange(0, 50)
        self.temp_graph.getAxis('bottom').setStyle(showValues=False)
        self.temp_line = self.temp_graph.plot(pen=pg.mkPen('r', width=2))
        
        graphs_layout.addLayout(temp_header)
        graphs_layout.addWidget(self.temp_graph)
        
        # 습도 그래프 설정
        humid_header = QHBoxLayout()
        humid_icon = QLabel()
        humid_icon.setPixmap(QIcon('icons/humidity.png').pixmap(QSize(40, 40)))
        humid_header.addWidget(humid_icon)
        
        self.humid_graph = pg.PlotWidget(height=200)
        self.humid_graph.setBackground('w')
        self.humid_graph.setTitle(f'습도 (%)', color='k', size='14pt')
        self.humid_graph.showGrid(x=True, y=True)
        self.humid_graph.setLabel('left', '습도', color='k')
        self.humid_graph.setLabel('bottom', '시간', color='k')
        self.humid_graph.setYRange(0, 100)
        self.humid_graph.getAxis('bottom').setStyle(showValues=False)
        self.humid_line = self.humid_graph.plot(pen=pg.mkPen('b', width=2))
        
        graphs_layout.addLayout(humid_header)
        graphs_layout.addWidget(self.humid_graph)
        
        main_content.addWidget(graphs_frame, stretch=7)
        
        # 오른쪽: 컨트롤 패널
        control_frame = QFrame()
        control_layout = QVBoxLayout(control_frame)
        
        # 비상 버튼
        self.emergency_btn = QPushButton('비상 정지')
        self.emergency_btn.setIcon(QIcon('icons/emergency.png'))
        self.emergency_btn.setIconSize(QSize(32, 32))
        self.emergency_btn.setStyleSheet('''
            background-color: red;
            color: white;
            font-weight: bold;
            padding: 15px;
            border: none;
        ''')
        self.emergency_btn.clicked.connect(self.emergency_stop)
        control_layout.addWidget(self.emergency_btn)

        # 자동화 버튼
        self.auto_btn = QPushButton('자동화: OFF')
        self.auto_btn.setStyleSheet('''
            background-color: #ffebee;
            color: black;
            border: 1px solid #dcdde1;
            padding: 15px;
            min-height: 50px;
            font-size: 16px;
        ''')
        self.auto_btn.clicked.connect(self.toggle_automation)
        control_layout.addWidget(self.auto_btn)
        
        # 각 컨트롤 그룹
        control_info = {
            'led': {'icon': 'led.png', 'text': 'LED'},
            'fan': {'icon': 'fan.png', 'text': 'Fan'},
            'pump': {'icon': 'pump.png', 'text': 'Pump'}
        }
        
        for name, info in control_info.items():
            group_frame = QFrame()
            group_layout = QVBoxLayout(group_frame)
            
            btn = QPushButton(f'{info["text"]}: OFF')
            btn.setIcon(QIcon(f'icons/{info["icon"]}'))
            btn.setIconSize(QSize(32, 32))
            btn.setStyleSheet('''
                background-color: #ffebee;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            setattr(self, f'{name}_btn', btn)
            btn.clicked.connect(lambda checked, n=name: getattr(self, f'toggle_{n}')())
            
            time_label = QLabel(f'{info["text"]} 가동시간: 00:00:00')
            time_label.setAlignment(Qt.AlignCenter)
            time_label.setStyleSheet('font-size: 13px; min-height: 30px;')
            setattr(self, f'{name}_time', time_label)
            
            group_layout.addWidget(btn)
            group_layout.addWidget(time_label)
            control_layout.addWidget(group_frame)
            
        main_content.addWidget(control_frame, stretch=3)
        layout.addLayout(main_content)
        
        self.setGeometry(100, 100, 1200, 700)

    def initThread(self):
        self.thread = SerialThread()
        self.thread.data_signal.connect(self.update_data)
        self.thread.start()

    def initTimer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_current_time)
        self.timer.start(1000)
        
        self.operation_timer = QTimer()
        self.operation_timer.timeout.connect(self.update_operation_times)
        self.operation_timer.start(1000)

    def update_current_time(self):
        current_time = QTime.currentTime()
        self.time_label.setText(f'현재 시간: {current_time.toString("HH:mm:ss")}')

    def update_operation_times(self):
        current_time = datetime.now()
        
        if self.led_status and self.led_start_time:
            duration = current_time - self.led_start_time
            self.led_time.setText(f'LED 가동시간: {str(duration).split(".")[0]}')
        
        if self.fan_status and self.fan_start_time:
            duration = current_time - self.fan_start_time
            self.fan_time.setText(f'Fan 가동시간: {str(duration).split(".")[0]}')
        
        if self.pump_status and self.pump_start_time:
            duration = current_time - self.pump_start_time
            self.pump_time.setText(f'Pump 가동시간: {str(duration).split(".")[0]}')

    def toggle_automation(self):
        self.automation_status = not self.automation_status
        
        # 모든 장치 초기화
        self.led_status = False
        self.fan_status = False
        self.pump_status = False
        self.thread.send_command('l\n')
        self.thread.send_command('f\n')
        self.thread.send_command('p\n')
        
        # LED, Fan, Pump 버튼/시간 초기화
        button_style = '''
            background-color: #ffebee;
            color: black;
            border: 1px solid #dcdde1;
            padding: 15px;
            min-height: 50px;
            font-size: 16px;
        '''
        self.led_btn.setText('LED: OFF')
        self.fan_btn.setText('Fan: OFF')
        self.pump_btn.setText('Pump: OFF')
        self.led_btn.setStyleSheet(button_style)
        self.fan_btn.setStyleSheet(button_style)
        self.pump_btn.setStyleSheet(button_style)
        
        self.led_time.setText('LED 가동시간: 00:00:00')
        self.fan_time.setText('Fan 가동시간: 00:00:00')
        self.pump_time.setText('Pump 가동시간: 00:00:00')
        
        # 자동화 버튼 상태 업데이트
        if self.automation_status:
            self.auto_btn.setText('자동화: ON')
            self.auto_btn.setStyleSheet('''
                background-color: #4CAF50;
                color: white;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
        else:
            self.auto_btn.setText('자동화: OFF')
            self.auto_btn.setStyleSheet('''
                background-color: #ffebee;
                color: black;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')

    def check_automation_conditions(self):
        if not self.automation_status:
            return
            
        try:
            # 최근 데이터 가져오기
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT temperature, humidity, light 
                FROM sensor_data 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                temp, humid, light = result
                
                # 온도에 따른 팬 제어
                if temp >= self.TEMP_THRESHOLD and not self.fan_status:
                    self.toggle_fan(True)
                    self.thread.send_command('F\n')
                elif temp < self.TEMP_THRESHOLD and self.fan_status:
                    self.toggle_fan(False)
                    self.thread.send_command('f\n')
                
                # 습도에 따른 펌프 제어
                if humid <= self.HUMID_THRESHOLD and not self.pump_status:
                    self.toggle_pump(True)
                    self.thread.send_command('P\n')
                elif humid > self.HUMID_THRESHOLD and self.pump_status:
                    self.toggle_pump(False)
                    self.thread.send_command('p\n')
                
                # 조도에 따른 LED 제어
                if light <= self.LIGHT_THRESHOLD and not self.led_status:
                    self.toggle_led(True)
                    self.thread.send_command('L\n')
                elif light > self.LIGHT_THRESHOLD and self.led_status:
                    self.toggle_led(False)
                    self.thread.send_command('l\n')
                    
        except Exception as e:
            print(f"Automation check error: {e}")

    def update_data(self, temp, humid, light):
        # 데이터 추가
        self.temp_data.append(temp)
        self.humid_data.append(humid)
        
        if len(self.temp_data) > 60:
            self.temp_data = self.temp_data[-60:]
            self.humid_data = self.humid_data[-60:]
            
        self.time_data = list(range(len(self.temp_data)))
        
        self.temp_line.setData(self.time_data, self.temp_data)
        self.humid_line.setData(self.time_data, self.humid_data)
        
        self.temp_graph.setTitle(f'온도 (°C): {temp}', color='k', size='14pt')
        self.humid_graph.setTitle(f'습도 (%): {humid}', color='k', size='14pt')
        
        # 데이터 제한 (최근 60개만 표시)
        if len(self.temp_data) > 60:
            self.temp_data = self.temp_data[-60:]
            self.humid_data = self.humid_data[-60:]
            
        # 시간 데이터 업데이트 (항상 0부터 시작하는 인덱스 사용)
        self.time_data = list(range(len(self.temp_data)))
        
        # 그래프 업데이트
        self.temp_line.setData(self.time_data, self.temp_data)
        self.humid_line.setData(self.time_data, self.humid_data)
        
        # 그래프 제목 업데이트
        self.temp_graph.setTitle(f'온도 (°C): {temp}', color='k', size='14pt')
        self.humid_graph.setTitle(f'습도 (%): {humid}', color='k', size='14pt')
        
        # x축 범위 자동 조정
        self.temp_graph.setXRange(max(0, len(self.time_data)-60), len(self.time_data), padding=0)
        self.humid_graph.setXRange(max(0, len(self.time_data)-60), len(self.time_data), padding=0)
        
        # 조도 상태 업데이트
        if light >= 2000:
            self.light_icon.setPixmap(QIcon('icons/light_bright.png').pixmap(QSize(32, 32)))
            light_status = "밝음"
        else:
            self.light_icon.setPixmap(QIcon('icons/light_dark.png').pixmap(QSize(32, 32)))
            light_status = "어두움"
        self.light_status.setText(f'조도: {light} ({light_status})')
        
        # 데이터베이스 저장
        self.save_to_database(temp, humid, light)


    def save_to_database(self, temp, humid, light):
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            query = """
                INSERT INTO sensor_data 
                (temperature, humidity, light) 
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (temp, humid, light))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Database Error: {e}")
    def emergency_stop(self):
        # 모든 장치 끄기
        self.led_status = False
        self.fan_status = False
        self.pump_status = False
        self.automation_status = False
        
        # UART 명령어 전송
        self.thread.send_command('E\n')
        self.thread.send_command('f\n')
        self.thread.send_command('p\n')
        
        # 버튼 상태 업데이트
        button_style = '''
            background-color: #ffebee;
            color: black;
            border: 1px solid #dcdde1;
            padding: 15px;
            min-height: 50px;
            font-size: 16px;
        '''
        
        self.led_btn.setText('LED: OFF')
        self.fan_btn.setText('Fan: OFF')
        self.pump_btn.setText('Pump: OFF')
        self.auto_btn.setText('자동화: OFF')
        
        self.led_btn.setStyleSheet(button_style)
        self.fan_btn.setStyleSheet(button_style)
        self.pump_btn.setStyleSheet(button_style)
        self.auto_btn.setStyleSheet(button_style)
        
        # 가동 시간 초기화
        self.led_start_time = None
        self.fan_start_time = None
        self.pump_start_time = None
        
        self.led_time.setText('LED 가동시간: 00:00:00')
        self.fan_time.setText('Fan 가동시간: 00:00:00')
        self.pump_time.setText('Pump 가동시간: 00:00:00')

    def toggle_led(self, state=None):
        if state is None:  # 수동으로 버튼을 눌렀을 때
            self.led_status = not self.led_status
            if self.automation_status:  # 자동화가 켜져있었다면 끄기
                self.automation_status = False
                self.auto_btn.setText('자동화: OFF')
                self.auto_btn.setStyleSheet('''
                    background-color: #ffebee;
                    color: black;
                    border: 1px solid #dcdde1;
                    padding: 15px;
                    min-height: 50px;
                    font-size: 16px;
                ''')
        else:  # 자동화에 의해 호출되었을 때
            self.led_status = state
            
        if self.led_status:
            self.thread.send_command('L\n')
            self.led_btn.setText('LED: ON')
            self.led_btn.setStyleSheet('''
                background-color: #4CAF50;
                color: white;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            self.led_start_time = datetime.now()
        else:
            self.thread.send_command('l\n')
            self.led_btn.setText('LED: OFF')
            self.led_btn.setStyleSheet('''
                background-color: #ffebee;
                color: black;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            self.led_start_time = None
            self.led_time.setText('LED 가동시간: 00:00:00')

    def toggle_fan(self, state=None):
        if state is None:  # 수동으로 버튼을 눌렀을 때
            self.fan_status = not self.fan_status
            if self.automation_status:  # 자동화가 켜져있었다면 끄기
                self.automation_status = False
                self.auto_btn.setText('자동화: OFF')
                self.auto_btn.setStyleSheet('''
                    background-color: #ffebee;
                    color: black;
                    border: 1px solid #dcdde1;
                    padding: 15px;
                    min-height: 50px;
                    font-size: 16px;
                ''')
        else:  # 자동화에 의해 호출되었을 때
            self.fan_status = state
            
        if self.fan_status:
            self.thread.send_command('F\n')
            self.fan_btn.setText('Fan: ON')
            self.fan_btn.setStyleSheet('''
                background-color: #4CAF50;
                color: white;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            self.fan_start_time = datetime.now()
        else:
            self.thread.send_command('f\n')
            self.fan_btn.setText('Fan: OFF')
            self.fan_btn.setStyleSheet('''
                background-color: #ffebee;
                color: black;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            self.fan_start_time = None
            self.fan_time.setText('Fan 가동시간: 00:00:00')

    def toggle_pump(self, state=None):
        if state is None:  # 수동으로 버튼을 눌렀을 때
            self.pump_status = not self.pump_status
            if self.automation_status:  # 자동화가 켜져있었다면 끄기
                self.automation_status = False
                self.auto_btn.setText('자동화: OFF')
                self.auto_btn.setStyleSheet('''
                    background-color: #ffebee;
                    color: black;
                    border: 1px solid #dcdde1;
                    padding: 15px;
                    min-height: 50px;
                    font-size: 16px;
                ''')
        else:  # 자동화에 의해 호출되었을 때
            self.pump_status = state
            
        if self.pump_status:
            self.thread.send_command('P\n')
            self.pump_btn.setText('Pump: ON')
            self.pump_btn.setStyleSheet('''
                background-color: #4CAF50;
                color: white;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            self.pump_start_time = datetime.now()
        else:
            self.thread.send_command('p\n')
            self.pump_btn.setText('Pump: OFF')
            self.pump_btn.setStyleSheet('''
                background-color: #ffebee;
                color: black;
                border: 1px solid #dcdde1;
                padding: 15px;
                min-height: 50px;
                font-size: 16px;
            ''')
            self.pump_start_time = None
            self.pump_time.setText('Pump 가동시간: 00:00:00')

def create_database():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='jung',
            password='1234'
        )
        cursor = conn.cursor()
        
        # 데이터베이스 생성 및 테이블 설정
        cursor.execute("CREATE DATABASE IF NOT EXISTS sensor_data")
        cursor.execute("USE sensor_data")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                temperature FLOAT,
                humidity FLOAT,
                light INT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 변경사항 저장 및 연결 종료
        conn.commit()
        cursor.close()
        conn.close()
        print("Database setup completed")
        return True
        
    except Exception as e:
        print(f"Database setup error: {e}")
        return False

def main():
    # 데이터베이스 설정
    if not create_database():
        sys.exit(1)
        
    # PyQt 애플리케이션 실행
    app = QApplication(sys.argv)
    window = SmartFarmUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
