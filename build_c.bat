@echo off
setlocal
cd /d "%~dp0"
if not exist c_core\build mkdir c_core\build
where cl >nul 2>nul
if errorlevel 1 (echo MSVC cl.exe not found. Open an x64 Native Tools Command Prompt for Visual Studio Build Tools and run this script there. & exit /b 2)
cl /nologo /TC /std:c11 /W4 /O2 /Fo:c_core\build\ /LD /DSMARTSPEND_BUILD /Ic_core\include c_core\src\transaction_list.c c_core\src\undo_stack.c c_core\src\cooling_queue.c c_core\src\category_array.c c_core\src\transaction_algorithms.c /link /OUT:c_core\build\smartspend.dll /IMPLIB:c_core\build\smartspend.lib
if errorlevel 1 (echo DLL build failed. See compiler output above. & exit /b 1)
cl /nologo /TC /std:c11 /W4 /Fo:c_core\build\ /DSMARTSPEND_BUILD /Ic_core\include c_core\tests\test_smartspend.c c_core\src\transaction_list.c c_core\src\undo_stack.c c_core\src\cooling_queue.c c_core\src\category_array.c c_core\src\transaction_algorithms.c /Fe:c_core\build\test_smartspend.exe
if errorlevel 1 (echo C test executable build failed. & exit /b 1)
c_core\build\test_smartspend.exe
if errorlevel 1 (echo C tests failed. & exit /b 1)
echo C DLL and C test executable built successfully for this compiler architecture.
