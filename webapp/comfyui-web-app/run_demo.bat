@echo off
chcp 65001 >nul
echo [INFO] 正在启动 AI 大模型路由适配器演示程序...
python ai_router_adapter/demo.py %*
pause
