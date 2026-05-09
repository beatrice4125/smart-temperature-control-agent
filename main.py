# -*- coding: utf-8 -*-
import sys

sys.stdout.reconfigure(encoding='utf-8')

import json
import random
import time


# 模拟传感器数据
def read_sensor_data():
    temp = round(22 + random.uniform(-2, 8), 1)
    humidity = round(50 + random.uniform(-10, 30), 1)
    return {"temp": temp, "humidity": humidity}


# Agent短期记忆
memory = []


def add_to_memory(temp, humidity, decision):
    memory.append({"temp": temp, "humidity": humidity, "decision": decision})
    if len(memory) > 5:
        memory.pop(0)


# 本地决策逻辑（模拟AI，不用API也能跑）
def get_local_decision(temp, humidity):
    if temp > 28:
        return '{"skill": "control_ac", "params": {"action": "cool"}}'
    elif temp < 20:
        return '{"skill": "control_ac", "params": {"action": "heat"}}'
    elif humidity > 70:
        return '{"skill": "control_dehumidifier", "params": {"action": "on"}}'
    else:
        return '{"skill": "control_ac", "params": {"action": "off"}}'


# 可调用的技能函数
def control_ac(action):
    print(f"✅ Executed AC control: {action}")


def control_dehumidifier(action):
    print(f"✅ Executed dehumidifier control: {action}")


skills = {
    "control_ac": control_ac,
    "control_dehumidifier": control_dehumidifier
}


# 本地规则兜底
def local_rule_fallback(temp, humidity):
    if temp > 30:
        print("⚠️ Local fallback: temp too high, cooling on")
        control_ac("cool")
        return True
    if humidity > 85:
        print("⚠️ Local fallback: humidity too high, dehumidifier on")
        control_dehumidifier("on")
        return True
    return False


# 解析并执行决策
def execute_decision(decision_json):
    try:
        decision = json.loads(decision_json)
        skill_name = decision.get("skill")
        params = decision.get("params", {})

        if skill_name in skills:
            skills[skill_name](**params)
            print("📝 Decision executed successfully\n")
        else:
            print("❌ Unknown skill:", skill_name)
    except Exception as e:
        print("❌ Failed to parse decision:", e)


# 主循环
if __name__ == "__main__":
    print("Smart Environment Agent Started...\n")
    while True:
        # 1. 获取传感器数据
        data = read_sensor_data()
        print(f"📊 Received sensor data: temp={data['temp']}°C, humidity={data['humidity']}%")

        # 2. 先执行本地兜底规则
        if local_rule_fallback(data["temp"], data["humidity"]):
            add_to_memory(data["temp"], data["humidity"], "Local fallback executed")
            time.sleep(1)
            continue

        # 3. 调用本地决策
        decision = get_local_decision(data["temp"], data["humidity"])
        print(f"🤖 Decision: {decision}")

        # 4. 执行决策
        execute_decision(decision)

        # 5. 加入记忆
        add_to_memory(data["temp"], data["humidity"], decision)

        time.sleep(1)