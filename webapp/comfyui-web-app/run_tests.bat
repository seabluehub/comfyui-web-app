@echo off
chcp 65001 >nul
echo [INFO] 正在启动 AI 大模型路由适配器自动化测试套件...
python -m pytest ai_router_adapter/tests/test_router_pipeline.py -v
if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo [SUCCESS] 所有自动化测试用例验证通过！
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo [ERROR] 测试存在未通过项，请检查上方日志。
    echo ========================================================
)
pause
