import os

os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = r".venv\Lib\site-packages\PyQt5\Qt5\plugins\platforms"

import sys

sys.stdout.reconfigure(encoding='utf-8')
import json
import random
import time
import serial
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QTextEdit, QGroupBox, QComboBox, QPushButton)
from PyQt5.QtCore import QThread, pyqtSignal

# ==============================================
# 硬件配置
# ==============================================
SERIAL_PORT = "COM6"
BAUD_RATE = 9600

# ==============================================
# 豆包 AI API 配置
# ==============================================
# 1. API Key
DOUBAN_API_KEY = "ark-08a7b7fc-2248-4998-b1f5-5f6e1069199e-e2b66"

# 2. 模型接入点 ID
MODEL_ENDPOINT_ID = "doubao-seed-2-0-pro-260215"

# 3. 官方最新 API 地址
API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"

# ==============================================
# 控制策略
# ==============================================
STRATEGY_CONFIG = {
    "节能优先": {"cool_temp": 30, "heat_temp": 18, "dehumidify_hum": 85},
    "舒适优先": {"cool_temp": 26, "heat_temp": 22, "dehumidify_hum": 70}
}


# ==============================================
# 【豆包AI】调用函数
# ==============================================
def get_ai_decision(temp, humidity):
    if not DOUBAN_API_KEY or not MODEL_ENDPOINT_ID:
        print("⚠️ 请配置 API Key 和模型接入点 ID")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {DOUBAN_API_KEY}",
            "Content-Type": "application/json"
        }

        prompt = f"""
        你是智能环境控制助手。
        当前温度：{temp}℃，湿度：{humidity}%
        请输出控制指令，仅返回JSON，无其他文字。
        可选技能：
        control_ac：动作 cool/heat/off
        control_dehumidifier：动作 on/off
        格式示例：{{"skill":"control_ac","params":{{"action":"cool"}}}}
        """

        #  使用接入点 ID 作为模型
        data = {
            "model": MODEL_ENDPOINT_ID,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }

        response = requests.post(API_URL, headers=headers, json=data, timeout=8)
        result = response.json()

        # 调试：打印返回结果
        print("🔍 AI 返回:", result)

        return json.loads(result["choices"][0]["message"]["content"].strip())

    except Exception as e:
        print(f"❌ AI 调用失败: {e}")
        return None


# ===================== 串口读取数据 =====================
ser = None


def init_serial():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("✅ Wokwi 串口连接成功")
    except:
        print("❌ 串口连接失败，使用模拟数据")


def read_sensor_data():
    global ser
    try:
        if ser and ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            if "," in line:
                t, h = line.split(",")
                return {"temp": round(float(t), 1), "humidity": round(float(h), 1)}
    except:
        pass

    temp = round(22 + random.uniform(-2, 8), 1)
    humidity = round(50 + random.uniform(-10, 30), 1)
    return {"temp": temp, "humidity": humidity}


# ===================== 本地决策 & 执行 =====================
def get_local_decision(temp, humidity, strategy):
    c = STRATEGY_CONFIG[strategy]
    if temp > c["cool_temp"]: return '{"skill":"control_ac","params":{"action":"cool"}}'
    if temp < c["heat_temp"]: return '{"skill":"control_ac","params":{"action":"heat"}}'
    if humidity > c["dehumidify_hum"]: return '{"skill":"control_dehumidifier","params":{"action":"on"}}'
    return '{"skill":"control_ac","params":{"action":"off"}}'


def control_ac(action): return f"✅ 空调：{action}"


def control_dehumidifier(action): return f"✅ 除湿机：{action}"


skills = {"control_ac": control_ac, "control_dehumidifier": control_dehumidifier}


def local_rule_fallback(t, h):
    if t > 32: return "⚠️ 温度过高，强制制冷"
    if h > 90: return "⚠️ 湿度过高，强制除湿"
    return None


def execute_decision(json_str):
    try:
        d = json.loads(json_str)
        return skills[d["skill"]](**d["params"])
    except:
        return "❌ 执行失败"


# ===================== 最终决策（AI优先 + 本地兜底） =====================
def get_final_decision(temp, humidity, strategy):
    ai_result = get_ai_decision(temp, humidity)
    if ai_result:
        return json.dumps(ai_result)
    print("🔄 降级使用本地策略")
    return get_local_decision(temp, humidity, strategy)


# ===================== 后台线程 =====================
class Worker(QThread):
    data_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.strategy = "节能优先"
        self.auto_mode = True

    def run(self):
        init_serial()
        while self.running:
            data = read_sensor_data()
            self.data_signal.emit(data)

            if self.auto_mode:
                fb = local_rule_fallback(data["temp"], data["humidity"])
                if fb:
                    self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] {fb}")
                    time.sleep(1)
                    continue

                dec = get_final_decision(data["temp"], data["humidity"], self.strategy)
                self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] 🤖 决策：{dec}")
                self.log_signal.emit(f"[{time.strftime('%H:%M:%S')}] {execute_decision(dec)}")
            time.sleep(1)


# ===================== 主界面 =====================
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("智能环境调控Agent - AI版")
        self.setGeometry(100, 100, 900, 700)
        self.worker = Worker()
        self.build_ui()
        self.worker.start()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)

        # 数据显示
        top = QHBoxLayout()
        self.t_lab = QLabel("温度：-- ℃")
        self.h_lab = QLabel("湿度：-- %")
        self.t_lab.setStyleSheet("font-size:16px; color:red; font-weight:bold")
        self.h_lab.setStyleSheet("font-size:16px; color:blue; font-weight:bold")
        self.cb = QComboBox()
        self.cb.addItems(["节能优先", "舒适优先"])
        self.cb.currentTextChanged.connect(lambda s: setattr(self.worker, "strategy", s))
        top.addWidget(self.t_lab)
        top.addWidget(self.h_lab)
        top.addWidget(QLabel("策略："))
        top.addWidget(self.cb)
        lay.addLayout(top)

        # 手动控制 + 设备列表
        mid = QHBoxLayout()
        g1 = QGroupBox("手动控制")
        v1 = QVBoxLayout(g1)
        self.btn_mode = QPushButton("切换到手动模式")
        self.btn_mode.setCheckable(True)
        self.btn_mode.clicked.connect(self.switch_mode)

        self.manual_btns = []
        btn_list = [
            ("空调制冷", lambda: self.exec_manual("control_ac", "cool")),
            ("空调制热", lambda: self.exec_manual("control_ac", "heat")),
            ("空调关闭", lambda: self.exec_manual("control_ac", "off")),
            ("除湿机开启", lambda: self.exec_manual("control_dehumidifier", "on")),
            ("除湿机关闭", lambda: self.exec_manual("control_dehumidifier", "off"))
        ]
        for t, f in btn_list:
            b = QPushButton(t)
            b.clicked.connect(f)
            b.setEnabled(False)
            self.manual_btns.append(b)
            v1.addWidget(b)
        v1.addWidget(self.btn_mode)

        # 已接入设备
        g2 = QGroupBox("已接入设备")
        v2 = QVBoxLayout(g2)
        skill_info = QTextEdit()
        skill_info.setReadOnly(True)
        skill_info.setPlainText("✅ 空调：制冷/制热/关闭\n✅ 除湿机：开启/关闭")
        v2.addWidget(skill_info)
        mid.addWidget(g1)
        mid.addWidget(g2)
        lay.addLayout(mid)

        # 日志
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("background:#2c3e50; color:white;")
        lay.addWidget(self.log)

        self.worker.data_signal.connect(self.update_data)
        self.worker.log_signal.connect(self.log.append)

    def switch_mode(self, checked):
        self.worker.auto_mode = not checked
        for b in self.manual_btns: b.setEnabled(checked)
        self.btn_mode.setText("切换到自动模式" if checked else "切换到手动模式")
        self.log.append(f"[{time.strftime('%H:%M:%S')}] 模式：{'手动' if checked else '自动'}")

    def exec_manual(self, skill, act):
        cmd = json.dumps({"skill": skill, "params": {"action": act}})
        self.log.append(f"[{time.strftime('%H:%M:%S')}] 👤 手动指令：{cmd}")
        self.log.append(f"[{time.strftime('%H:%M:%S')}] {execute_decision(cmd)}")

    def update_data(self, d):
        self.t_lab.setText(f"温度：{d['temp']} ℃")
        self.h_lab.setText(f"湿度：{d['humidity']} %")

    def closeEvent(self, e):
        self.worker.running = False
        e.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Window()
    win.show()
    sys.exit(app.exec_())